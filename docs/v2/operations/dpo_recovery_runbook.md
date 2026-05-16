# DPO Recovery Runbook — Audit Chain Violations

> **Audience**: Data Protection Officer (DPO) + on-call SRE
> **Trigger**: `verify_chain(path)` returns a non-empty fault list,
> OR `sylion_v2_audit_chain_violations_total{module="<x>"} > 0` on the
> Prometheus dashboard, OR `/api/v1/health/v2` reports `status="degraded"`
> with `audit_chains.<module>` not in `{present}`.
> **SLO**: First operator response within 1 hour, full incident report
> within 24 hours, decision tree resolution within 7 days.
> **Status**: PRODUCTION (sprint 3 E8 deliverable, 2026-04-28).

---

## Table of Contents

1. [Pre-flight checks](#1-pre-flight-checks)
2. [Step-by-step procedure (10 steps)](#2-step-by-step-procedure)
3. [Decision tree](#3-decision-tree)
4. [Rollback triggers](#4-rollback-triggers)
5. [Stakeholder contacts](#5-stakeholder-contacts)
6. [Post-mortem template](#6-post-mortem-template)
7. [Reference: Tampered fault types](#7-reference-tampered-fault-types)

---

## 1. Pre-flight checks

Before declaring an incident, verify the alarm is real:

| Check | Command | Expected if NOT a real incident |
|-------|---------|----------------------------------|
| Audit file exists & non-empty | `ls -la src/sylion-pipeline/sylion/logs/v2/<module>.jsonl` | non-zero size |
| `verify_chain` faults | `python scripts/v2/verify_audit_chains.py --json` | `"clean": true` for the module |
| Prometheus violations | `curl -H "X-Auth: <auditor>" /api/v1/metrics/v2 \| grep violations_total` | `0` for the module |
| Recent rotation | `ls -la src/sylion-pipeline/sylion/logs/v2/<module>.*.jsonl` | rotation files match retention |
| Disk pressure | `df -h /var/lib/sylion/logs` | < 80% used |

**False alarm conditions** (do NOT escalate):

- Active rotation in flight (`audit_rotation.run_daily` row visible in
  `audit_rotation.jsonl` within last 60s).
- Module just deployed (`gdpr_dsr.jsonl` empty for first 5 minutes is
  expected — not yet triggered any DSR).
- Test/dev environment (env var `SYLION_ENV != production`).

If pre-flight clears the alarm — **stop here**, log the suppression in
`docs/v2/operations/suppressed_alarms.log`, and resume normal duty.

---

## 2. Step-by-step procedure

When a violation is confirmed real, follow these steps in order. Do NOT
skip steps — the legal/compliance defensibility of the recovery
depends on the chain of custody documented at each step.

### Step 1 — Snapshot the evidence (T+0 minutes)

```bash
# Capture an immutable copy BEFORE any further reads or writes.
INCIDENT_ID="audit-violation-$(date -u +%Y%m%dT%H%M%S)"
mkdir -p /var/lib/sylion/incidents/$INCIDENT_ID

cp -p src/sylion-pipeline/sylion/logs/v2/<module>.jsonl \
      /var/lib/sylion/incidents/$INCIDENT_ID/<module>.original.jsonl

sha256sum /var/lib/sylion/incidents/$INCIDENT_ID/<module>.original.jsonl \
  > /var/lib/sylion/incidents/$INCIDENT_ID/<module>.sha256
```

**Why**: every subsequent action could mutate the chain (e.g. a new
DSR request emits a new row); we must preserve the as-found state.
The SHA256 anchors the snapshot to the exact bytes we will analyse.

### Step 2 — Capture the fault report (T+5 minutes)

```bash
python scripts/v2/verify_audit_chains.py \
  --root src/sylion-pipeline/sylion/logs/v2 \
  --json \
  > /var/lib/sylion/incidents/$INCIDENT_ID/fault_report.json

# Pretty-print for the incident channel.
python scripts/v2/verify_audit_chains.py \
  --root src/sylion-pipeline/sylion/logs/v2 \
  > /var/lib/sylion/incidents/$INCIDENT_ID/fault_report.txt
```

The JSON output enumerates every faulty line — line number, reason,
expected vs actual hash. Pin this to the incident ticket.

### Step 3 — Identify the timeline (T+10 minutes)

Determine **the last clean row**:

```bash
python -c "
from pathlib import Path
from sylion.aeis_v2.audit_chain import verify_chain

faults = verify_chain(Path('src/sylion-pipeline/sylion/logs/v2/<module>.jsonl'))
first_fault_line = min(f.line_no for f in faults) if faults else None
print(f'first_fault_line={first_fault_line}')
print(f'last_clean_line={(first_fault_line - 1) if first_fault_line else \"all clean\"}')
"
```

Pull the first fault row's content (under `content.ts`) — that gives the
**approximate tampering timestamp**. Cross-reference with deployment
logs, secret rotations, operator activity.

### Step 4 — Notify stakeholders (T+15 minutes)

Use the template in [§5 Stakeholder contacts](#5-stakeholder-contacts).
Required first-pass notifications:

- **DPO** (data protection officer) — incident lead.
- **Operator** (founder/owner) — must be aware of any GDPR audit gap.
- **SRE on-call** — to gate further changes to the affected module.
- **Security** — only if `module ∈ {security_audit, vault, secrets}`.

Do NOT post the raw audit content (PII risk). Reference the incident
id only.

### Step 5 — Freeze the affected module (T+20 minutes)

To prevent further chain corruption while the investigation runs:

```bash
# Per-module env feature flag suspends emission.
export SYLION_<MODULE>_AUDIT_FROZEN=1

# Or surgical: redirect future emits to a side chain that survives.
mv src/sylion-pipeline/sylion/logs/v2/<module>.jsonl \
   src/sylion-pipeline/sylion/logs/v2/<module>.frozen.$INCIDENT_ID.jsonl
touch src/sylion-pipeline/sylion/logs/v2/<module>.jsonl
```

The frozen path is now the forensic artefact. The empty new file
re-bootstraps a fresh genesis chain so the module stays operational.

**For GDPR DSR specifically**: do NOT freeze — instead bump the audit
emission to a side path (`<module>.recovery.jsonl`) so DSR Article 12.3
deadlines are not breached.

### Step 6 — Categorise the fault (T+30 minutes)

Read `fault_report.json` and classify each fault:

| Reason | Likely cause |
|--------|--------------|
| `json_parse_error` | Disk corruption, partial write (process crash mid-emit), manual edit |
| `missing_field` | Schema drift between writers, test fixture leaked into prod |
| `prev_hash_mismatch` | Row deletion (most common attack), rotation race |
| `content_hash_mismatch` | Direct mutation of an existing row |

A single row with `content_hash_mismatch` followed by clean rows is
**suspicious** — content was tampered, but the attacker did not
recompute downstream hashes. Forensic signal of unsophisticated attempt.

A long run of `prev_hash_mismatch` from line N onward means rows
were **deleted** between (clean) tail and N-1.

### Step 7 — Compute blast radius (T+45 minutes)

Count affected rows + identify what they protect:

```bash
python -c "
import json
from pathlib import Path
faults = json.load(open('/var/lib/sylion/incidents/$INCIDENT_ID/fault_report.json'))
target = next(f for f in faults['files'] if not f['clean'])
print(f'module={target[\"name\"]}')
print(f'fault_count={len(target[\"faults\"])}')
"
```

**Module ↔ risk surface**:

| Module | Affected processes |
|--------|-------------------|
| `gdpr_dsr.jsonl` | Article 15 access, Article 17 erasure ledgers — DSR contract gap |
| `gdpr_hard_purge.jsonl` | Article 12.3 30-day purge proof — could miss legal deadline |
| `replay_fork.jsonl` | A/B routing decisions — internal only, lower risk |
| `council_wedge.jsonl` | Council Hybrid vote ledger — governance trail |
| `adr_signoff.jsonl` | ADR PROPOSED→ACCEPTED transitions — architecture trail |
| `audit_rotation.jsonl` | Rotation history — meta-trail; corruption is "second order" |
| `w19_evaluator.jsonl` | Policy DSL render attempts — security-sensitive |

### Step 8 — Decision (T+60 minutes)

Walk the [decision tree §3](#3-decision-tree). Outcomes:

- **A. INCIDENT** (legal/compliance impact) → external notification path.
- **B. FORENSIC** (suspicious but no compliance gap) → full investigation.
- **C. RECONSTRUCT** (clean cause, contained, rebuildable) → rotate +
  start fresh chain from the last clean row.

### Step 9 — Execute decision (T+1-2 hours)

#### A. Incident path

```text
1. Escalate to legal counsel within 4 hours (GDPR Art. 33: 72 h max).
2. Compose the data subject notification template (only if PII at risk).
3. File the incident in the regulatory ticketing (PUODO portal for PL).
4. DO NOT modify the frozen artefact until counsel signs off.
```

#### B. Forensic path

```text
1. Spin up a forensic worktree:
   git worktree add /tmp/forensic-$INCIDENT_ID origin/main
2. Copy the frozen JSONL into the worktree, run audit_chain in DEBUG.
3. Cross-reference timestamps with system journals + git log.
4. Report findings within 5 business days; close as one of:
     a. False positive (revert freeze)
     b. Reconstruct (jump to path C)
     c. Confirmed incident (jump to path A)
```

#### C. Reconstruct path

```bash
# 1. Identify last clean row (already done in step 3 — first_fault_line - 1).
LAST_CLEAN=<first_fault_line - 1>

# 2. Truncate the frozen artefact to that line, save as recovered baseline.
head -n $LAST_CLEAN \
  /var/lib/sylion/incidents/$INCIDENT_ID/<module>.original.jsonl \
  > /var/lib/sylion/incidents/$INCIDENT_ID/<module>.recovered.jsonl

# 3. Verify the truncated chain.
python scripts/v2/verify_audit_chains.py \
  --root /var/lib/sylion/incidents/$INCIDENT_ID/

# 4. If clean, restore as the active chain.
cp /var/lib/sylion/incidents/$INCIDENT_ID/<module>.recovered.jsonl \
   src/sylion-pipeline/sylion/logs/v2/<module>.jsonl

# 5. Invalidate the in-process cache so the next append starts fresh.
python -c "
from sylion.aeis_v2.audit_chain import invalidate_last_hash_cache
invalidate_last_hash_cache('src/sylion-pipeline/sylion/logs/v2/<module>.jsonl')
"

# 6. Unfreeze the module.
unset SYLION_<MODULE>_AUDIT_FROZEN
```

### Step 10 — Post-mortem (T+1-7 days)

Use the template in [§6 Post-mortem template](#6-post-mortem-template).
Required artefacts:

- Original frozen JSONL + SHA256.
- Fault report JSON.
- Timeline of events (alarm time, freeze time, decision time, recovery time).
- Decision rationale (which path of §3, why).
- Process improvements (what would have caught this earlier?).

Publish to `docs/v2/incidents/$INCIDENT_ID/post_mortem.md`.

---

## 3. Decision tree

```text
                 ┌────────────────────────┐
                 │  Pre-flight cleared?   │
                 └────────────┬───────────┘
                              │ no → false alarm, log & resume
                              ▼ yes
                 ┌────────────────────────┐
                 │ PII or compliance trail │
                 │ in affected module?     │
                 └────────────┬───────────┘
                       no │       │ yes
                          ▼       ▼
              ┌──────────────┐  ┌──────────────────────────────┐
              │ Suspicious   │  │ GDPR Article 33 obligation:  │
              │ pattern?     │  │ 72-hour notification clock    │
              └──────┬───────┘  │ STARTS NOW                   │
                  no│  │ yes    └────────────┬─────────────────┘
                    ▼  ▼                     │
        ┌──────────────────┐                 ▼
        │  Reconstruct     │      ┌──────────────────────────┐
        │  path (C)        │      │  Incident path (A)       │
        │                  │      │  Notify counsel < 4h     │
        │  Truncate, run   │      │  File regulatory ticket  │
        │  fresh chain     │      │  Forensic preservation   │
        └──────────────────┘      └──────────────────────────┘
                    ▲
                    │ no
        ┌──────────────────┐
        │ Forensic path (B)│
        │ Investigate first│
        │ then decide A/C  │
        └──────────────────┘
```

**"Suspicious pattern" definition** (any of):

- More than 1 `content_hash_mismatch` fault.
- Faults span more than 1 calendar day.
- Module is `gdpr_dsr.jsonl`, `gdpr_hard_purge.jsonl`, or `adr_signoff.jsonl`.
- Recent operator activity log shows file-level access (mv, rm, edit)
  on the audit dir.
- Disk-level integrity check (`fsck`, `zfs scrub`) reports recent errors.

---

## 4. Rollback triggers

Abort the in-flight recovery and re-freeze if any of these fire:

| Trigger | Action |
|---------|--------|
| Recovery introduces NEW faults (e.g. truncation broke the chain) | Restore original frozen artefact, jump to path B (forensic) |
| Stakeholder objection within decision window | Pause recovery; convene Council Hybrid vote |
| Same module re-fails verify_chain within 24 hours | Treat as systemic — escalate to security review |
| Data subject inquiry references the affected window | Path A regardless of current path; legal lead takes over |

---

## 5. Stakeholder contacts

> **Replace the placeholders below with real contact info before
> production go-live.** This template was drafted as part of the
> sprint 3 E8 deliverable and is NOT yet populated for prod.

| Role | Person | Contact | SLA |
|------|--------|---------|-----|
| DPO | `<name>` | `<email>`, `<phone>` | 1 h |
| Operator/founder | `<name>` | `<email>`, `<phone>` | 1 h |
| SRE on-call | rotation: `<rota-link>` | PagerDuty `sylion-v2-audit` | 15 min |
| Security | `<name>` | `<email>` | 4 h |
| Legal counsel (GDPR) | `<firm>` | `<email>`, `<phone>` | 4 h |
| Regulator (PUODO PL) | https://uodo.gov.pl/ | webform | 72 h (Article 33) |

### Notification template (Slack/email)

```text
Subject: [SYLION-V2-AUDIT-VIOLATION] $INCIDENT_ID — initial notification

DPO/Operator/Security team,

A SYLION v2 audit chain violation was detected at $TIMESTAMP_UTC.

Module: $MODULE
Incident ID: $INCIDENT_ID
First fault line: $LINE_NO
Reason: $REASON
Suspected timeline: $APPROX_START_TS — $APPROX_END_TS

Action so far:
- Pre-flight passed (alarm is real)
- Frozen artefact: /var/lib/sylion/incidents/$INCIDENT_ID/
- Module emission: $FROZEN_OR_REDIRECTED
- Decision tree: in progress (currently at step 6 — categorisation)

I am following the DPO recovery runbook. Next status update at T+60 min.

— $YOUR_NAME (on-call $ROLE)
```

---

## 6. Post-mortem template

Save to `docs/v2/incidents/$INCIDENT_ID/post_mortem.md`.

```markdown
# SYLION V2 Audit Violation Post-Mortem — $INCIDENT_ID

## Summary
- Module: $MODULE
- Detected: $DETECT_TIMESTAMP_UTC
- Resolved: $RESOLVE_TIMESTAMP_UTC
- Decision path: A (incident) | B (forensic) | C (reconstruct)
- Final status: closed | external-notification-sent | pending

## Timeline
- T+0   $DETECT_TS — alarm fired (source: $SOURCE)
- T+5   evidence snapshot captured ($SHA256)
- T+15  stakeholders notified
- T+30  fault categorisation: $CATEGORY
- T+60  decision: $PATH ($DECISION_RATIONALE)
- T+$X  recovery executed
- T+$Y  module unfrozen + re-verified
- T+$Z  post-mortem published (this doc)

## Root cause
$ROOT_CAUSE_NARRATIVE

## Blast radius
- Rows affected: $N
- Time window: $WINDOW
- Compliance impact: $IMPACT
- Data subject impact: $DSI

## What went well
1. ...
2. ...

## What went poorly
1. ...
2. ...

## Action items
| Owner | Action | Due |
|-------|--------|-----|
| ...   | ...    | ... |

## Lessons learned
$LESSONS

## Sign-off
- DPO: $NAME / $TIMESTAMP
- Operator: $NAME / $TIMESTAMP
- Security: $NAME / $TIMESTAMP
```

---

## 7. Reference: Tampered fault types

Output of `verify_chain` is a `list[Tampered]` — each `Tampered` carries:

- `line_no` — 1-based line number in the JSONL.
- `reason` — one of:
    - `json_parse_error` — line is not valid JSON.
    - `missing_field` — line is JSON but missing one of `prev_hash` /
      `content` / `content_hash`.
    - `prev_hash_mismatch` — the row's `prev_hash` does not equal the
      previous row's `content_hash`. Indicates row deletion or
      out-of-order replay.
    - `content_hash_mismatch` — recomputed `sha256(prev_hash +
      json.dumps(content, sort_keys=True))[:16]` does not equal the
      stored `content_hash`. Indicates direct content mutation.
- `expected` — what verify_chain expected for the offending field.
- `actual`   — what was on disk.

The faulty line is **not** automatically removed. Recovery (path C)
must explicitly truncate to the last clean row and re-emit.

---

## Appendix — Smoke test

The runbook itself has a smoke test under
`tests/aeis_v2/test_dpo_recovery_runbook.py` which:

1. Stages a fake violation in a tmp dir.
2. Walks each step of [§2](#2-step-by-step-procedure) using the
   documented commands.
3. Verifies the recovered chain passes `verify_chain`.

Run on every release to keep the runbook honest:

```bash
python -m pytest tests/aeis_v2/test_dpo_recovery_runbook.py -v
```
