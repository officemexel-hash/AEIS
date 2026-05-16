# W19 Policy Plane Production Runbook

> **Audience**: Operator (founder), on-call SRE, DPO
> **Scope**: rolling out the W19 jinja2 sandbox-based policy evaluator
> from PROPOSED skeleton (sprint 2) to production-active (1% → 100%)
> **Companion docs**:
> - [`dpo_recovery_runbook.md`](./dpo_recovery_runbook.md) — audit chain incidents
> - [`ADR-003`](../decisions/ADR-003-W19-evaluator-unblock-2026-04-28.md) — option B (jinja sandbox + 1% staged)
> **Status**: PRODUCTION (sprint 4 deliverable, 2026-04-28)

---

## Table of Contents

1. [Pre-deploy checklist](#1-pre-deploy-checklist)
2. [ADR-003 sign-off workflow](#2-adr-003-sign-off-workflow)
3. [Canary dial procedure](#3-canary-dial-procedure)
4. [Observability gates](#4-observability-gates)
5. [Rollback triggers](#5-rollback-triggers)
6. [Incident response](#6-incident-response)
7. [DPO involvement criteria](#7-dpo-involvement-criteria)
8. [Council split-brain procedure](#8-council-split-brain-procedure)
9. [jinja2 CVE response](#9-jinja2-cve-response)
10. [Policy template version migration](#10-policy-template-version-migration)
11. [Operator UI walkthrough](#11-operator-ui-walkthrough)

---

## 1. Pre-deploy checklist

Before flipping the W19 evaluator on, verify EVERY box:

| # | Check | Command / artefact | Expected |
|---|-------|---------------------|----------|
| 1 | Sprint 4 keystone commits present | `git log --oneline --grep '\[v2 cron\] sprint 4'` | ≥5 commits (StagedRolloutGate, Council vote, RoutingGate, chaos, PgPolicyRegistry) |
| 2 | All chaos tests green | `pytest tests/aeis_v2/test_w19_chaos.py` | 11/11 pass |
| 3 | All gate tests green | `pytest tests/aeis_v2/test_w19_routing_gate.py tests/aeis_v2/test_w19_staged_rollout.py` | 37/37 pass |
| 4 | jinja2 installed in target env | `pip show jinja2` | 3.x |
| 5 | psycopg installed | `pip show psycopg` | 3.x |
| 6 | PG `policies` table created | `reg.ensure_schema()` once, then `\d policies` | table + partial idx |
| 7 | At least one policy authored + reviewed | `reg.list_policies()` | ≥1 enabled=False (await Council) |
| 8 | Audit chain monitor scheduled | crontab `audit_chain_monitor.py` hourly | runs |
| 9 | Slack webhook configured (optional) | `$SYLION_SLACK_WEBHOOK` set | URL |
| 10 | DPO has read [DPO recovery runbook](./dpo_recovery_runbook.md) | sign-off in incident channel | yes |

**Stop here if ANY box fails. Resolve before proceeding.**

---

## 2. ADR-003 sign-off workflow

ADR-003 ships PROPOSED. The sign-off endpoint at
`POST /api/v1/council/sign-off-adr/{adr_id}` flips it to ACCEPTED only
when the Council Hybrid gate passes.

### Step-by-step

```bash
# 1. Dry-run the Council vote — no file mutation.
python scripts/v2/run_w19_adr003_council_vote.py

# Expected output:
#   Council vote on ADR-003-W19-evaluator-unblock-2026-04-28.md:
#   approve=N reject=M conditional=K errors=0
#   approve_majority=True
#   [planner]            approve  conf=0.90  ms=...
#   [architect]          approve  conf=0.85  ms=...
#   ...

# 2. Review the per-role rationales. If any role's verdict surprises
# you, investigate (read its rationale text); re-run if needed.

# 3. APPLY the vote — file flips to ACCEPTED if approve_majority is True.
python scripts/v2/run_w19_adr003_council_vote.py --apply

# Expected:
#   apply_signoff: status=ok gate_passed=True new_status=ACCEPTED
```

If `gate_passed=False`, the Council majority did NOT approve. Review
the rationales, address the dissent, and re-run after operator
intervention.

### Sanity checks

```bash
# ADR-003 status:
grep "Status:" docs/v2/decisions/ADR-003-W19-evaluator-unblock-2026-04-28.md
# Expected: > **Status**: ACCEPTED

# Sign-off audit chain integrity:
python -c "
from sylion.aeis_v2.audit_chain import verify_chain
from pathlib import Path
faults = verify_chain(Path('src/sylion-pipeline/sylion/logs/v2/adr_signoff.jsonl'))
print('OK' if not faults else f'FAULTS: {faults}')
"
```

---

## 3. Canary dial procedure

Successive observability gates between phases:

| Stage | Percent | Min observation period | Exit criteria → next stage |
|-------|---------|------------------------|----------------------------|
| 0 → 1% | `1` | 4 hours | 0 deny errors, p95 render ≤ 50 ms, audit chain clean |
| 1 → 5% | `5` | 12 hours | same as above |
| 5 → 25% | `25` | 24 hours | same + 0 chaos vectors observed |
| 25 → 50% | `50` | 48 hours | same |
| 50 → 100% | `100` | 7 days | same + DPO sign-off recorded |

### Apply a stage

```bash
# 1. Set the env var on the federation router process(es).
export SYLION_W19_EVALUATOR_DISABLED=0   # flag on
export SYLION_W19_STAGED_ROLLOUT_PERCENT=1

# 2. Restart federation routers (rolling — don't bounce all at once).

# 3. Confirm the gate sees it:
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8421/api/v1/health/v2 | jq .
# Expected services.audit_chain="up" + status="ok"

# 4. Confirm metrics surface:
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8421/api/v1/metrics/v2 | grep sylion_v2_audit_chain
```

### Per-stage smoke

After each stage flip, run for 5 minutes and check:

- `sylion_v2_audit_chain_violations_total{module="federation_policy"}` is `0`
- `adapter_bus_dispatch_total{outcome="failure"}` rate is unchanged from baseline
- No new entries in `audit_chain_alert.jsonl`

**If any check fails → see [§5 Rollback triggers](#5-rollback-triggers)**.

---

## 4. Observability gates

### 4.1 Metrics

The `/api/v1/metrics/v2` endpoint surfaces these W19-relevant series:

| Metric | Purpose | Alert threshold |
|--------|---------|-----------------|
| `sylion_v2_audit_chain_size{module="federation_policy"}` | gate emit volume | sudden drop = gate not firing |
| `sylion_v2_audit_chain_violations_total{module="federation_policy"}` | tampering | > 0 → page DPO |
| `adapter_bus_circuit_state{adapter,state="open"}` | upstream health | open > 5 min → page SRE |
| `adapter_bus_dispatch_total{outcome="failure"}` | upstream errors | rate spike > 3× baseline |

### 4.2 Audit chains

Monitor `audit_chain_monitor.py` runs (hourly cron). Every run emits a
`audit_chain_alert.run` row to `audit_chain_alert.jsonl` — the absence
of these heartbeats means the cron itself is broken.

```bash
# DPO daily check:
python scripts/v2/verify_audit_chains.py
# Expected: "N clean / N total" — no [FAULT] rows
```

### 4.3 Logs

The federation router's stdout will carry one line per `RoutingGate.check`
when DEBUG is enabled. INFO level only logs failures + denies. The
chained `federation_policy.jsonl` is the durable record.

---

## 5. Rollback triggers

Roll back the canary percent (or disable entirely) if ANY trigger fires:

| Trigger | Detection | Response |
|---------|-----------|----------|
| Deny rate > 5% of evaluated traffic | `outcome="deny" / "rolled_out=true"` ratio in last 5 min | drop percent by ≥ one stage; investigate template |
| p95 render time > 100 ms | `elapsed_ms` in audit content | drop to 0; suspect timeout regression |
| Audit chain violation count > 0 | metrics endpoint or monitor cron | drop to 0; engage DPO runbook |
| Sandbox escape detected | `outcome="error"` + `reason` contains "blocked token" or "security" | drop to 0; engage [§9 jinja2 CVE response](#9-jinja2-cve-response) |
| Operator panic | gut feeling | drop to 0 — never wrong to back off |

### Emergency disable

```bash
export SYLION_W19_EVALUATOR_DISABLED=1
# Restart routers — gate now returns outcome="skipped" reason="evaluator_flag_off"
# for 100% of decisions. Existing in-flight decisions are unaffected.
```

This is the **kill switch**: it bypasses the canary percent entirely.

---

## 6. Incident response

When a rollback trigger fires:

1. **Drop the percent** (or kill switch) — protect blast radius first.
2. **Snapshot evidence**: tail the federation_policy chain + the
   audit_chain_alert chain + the policy that was active.
3. **Notify**: DPO + operator + SRE in the incident channel.
4. **Diagnose**: walk the [DPO recovery runbook §6](./dpo_recovery_runbook.md#6-post-mortem-template) for a chain-tamper
   incident, OR read the failed `outcome="error"` rows for a render
   regression.
5. **Fix forward**: author a corrected policy via PgPolicyRegistry
   `update_policy(...)` — version increments automatically; old
   version stays in the audit chain.
6. **Re-canary**: start at the previous-but-one stage (e.g. if you
   rolled back from 25%, restart at 5%, not 25%).
7. **Post-mortem**: use the [DPO post-mortem template](./dpo_recovery_runbook.md#6-post-mortem-template).

---

## 7. DPO involvement criteria

Engage the DPO whenever:

- Audit chain violations affect modules with PII (gdpr_dsr, gdpr_hard_purge).
- Article 33 GDPR notification window is in play (72-hour clock).
- A policy template references PII fields (operator-time review).
- Council sign-off is contested (split-brain — see §8).
- Roll-back to 0% is required AND the violation persisted longer than
  the SLA window for the affected article (Article 12.3 = 1 month).

---

## 8. Council split-brain procedure

If the Council vote is **5-4 or 4-5** (a single-vote majority either
direction):

1. The dispatcher script (`run_w19_adr003_council_vote.py`) prints the
   per-role rationales — read them carefully.
2. Identify the **decisive role**: the role whose verdict, if flipped,
   would change the outcome. Most often this is the `critic` role.
3. **Re-run** the vote with a verbal sweep through the dissenting
   roles' rationales addressed in a follow-up ADR or operator note.
4. If the same split persists for 2 consecutive rounds, escalate to
   the operator + DPO; the gate stays PROPOSED until cleared.

The sign-off endpoint refuses to flip on a non-majority — see
`apply_signoff` returning `status="no_majority_approve"`.

---

## 9. jinja2 CVE response

If a CVE is published against the jinja2 version we run:

1. **Drop percent to 0** (or kill switch).
2. Patch jinja2 in the deployment manifest; redeploy.
3. **Re-run the chaos test suite** against the new jinja2 version:
   `pytest tests/aeis_v2/test_w19_chaos.py -v`. All 11 must pass.
4. **Re-canary** from 1% with extended observation (24h instead of 4h)
   until p95 render time + deny rate match baseline.

---

## 10. Policy template version migration

Versions auto-increment on every `update_policy()`. Migration
recipes:

| Scenario | Action |
|----------|--------|
| Author a new template variant | `create_policy("new-id", enabled=False, ...)` — Council reviews + flips enabled later |
| Replace an existing active template | `update_policy("existing-id", template_str=NEW, enabled=True)` — version bumps; old version stays in audit chain |
| Disable a misbehaving policy | `update_policy("p", enabled=False)` — gate falls back to "no policy template, skipped" |
| Roll back to a previous version | `update_policy("p", template_str=PREVIOUS_TEMPLATE_FROM_AUDIT)` — pulls from `policy_registry.jsonl` content rows |

The audit chain (`policy_registry.jsonl`) records every `template_str`
on every change, so the operator can always reconstruct any prior version.

---

## 11. Operator UI walkthrough

The `/v2/admin` dashboard surfaces W19 status (sprint 4 deliverable, follow-up commit):

- **W19 panel**: rollout percent, render count 24h, deny rate, p95
  render ms, sandbox violations count, audit chain status, last
  Council vote outcome.
- **Council panel**: latest sign-off attempts (status, approve count,
  gate_passed).
- **Audit panel**: per-module chain integrity (clean / violated).

The operator can flip canary stages directly from the W19 panel via a
gated POST to `/api/v1/policy-v2/canary` (RBAC: owner only) — under
the hood that just sets `SYLION_W19_STAGED_ROLLOUT_PERCENT` and
restarts the routers.

---

## Appendix — Exit criteria for "W19 PRODUCTION COMPLETE"

The W19 layer is declared **PRODUCTION COMPLETE** when:

1. ADR-003 status = ACCEPTED (verified by sha256 in audit chain)
2. `SYLION_W19_STAGED_ROLLOUT_PERCENT = 100` for ≥ 7 days
3. Zero rollback triggers in that 7-day window
4. DPO sign-off recorded in `adr_signoff.jsonl`
5. All 11 chaos tests green on the latest jinja2 version
6. `verify_chain` returns `[]` for every chain in `logs/v2/`

This document gets updated when **any** of the above criteria are hit.
