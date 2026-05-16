# ADR-003: W19 Evaluator Unblock — Decision Point (2026-04-28)

> **Status**: PROPOSED (awaiting operator decision + Council Hybrid review)
> **Date**: 2026-04-28
> **Decision-maker**: Robert (operator/founder, founder rank 5) — pending sign-off
> **Reviewer of record**: Council Hybrid (W3) — pending vote
> **Scope**: SYLION AEIS v2 — sprint 2 disposition of the W19 policy plane evaluator
> **Supersedes (conditional)**: ADR-001 Decision #4 *operational directive* (PARKED) if Option B or Option C is accepted; preserves Decision #4 *DSL choice* (YAML + sandboxed jinja2) under Option B and *pluggable engine interface* under Option C.
> **Author of record**: cron orchestrator round 2026-04-28 (sprint 2 opener; ADR drafted from operator brief, no operator verbatim text yet — this ADR records the *trade-offs* the operator will weigh before deciding).
> **Companion**: [ADR-001](ADR-001-five-architectural-decisions-2026-04-27.md) Decision #4 (parked W19 evaluator), [ADR-002](ADR-002-multi-model-routing-matrix-2026-04-27.md) (multi-model routing — same gradual rollout pattern referenced under Option B).

## Table of contents

1. [Status](#status-proposed-awaiting-operator-decision--council-hybrid-review)
2. [Context](#context)
3. [Decision (proposed, 3 options)](#decision-proposed-3-options)
   - [Option A: KEEP PARKED](#option-a-keep-parked-sprint-2-status-quo)
   - [Option B: UNBLOCK with jinja sandbox + 1% staged rollout](#option-b-unblock-with-jinja-sandbox--1-staged-rollout)
   - [Option C: UNBLOCK with OPA Rego external service](#option-c-unblock-with-opa-rego-external-service)
   - [Recommendation](#recommendation)
4. [Trade-offs matrix](#trade-offs-matrix)
5. [Consequences (per option)](#consequences-per-option)
6. [Rollback Plan](#rollback-plan)
7. [Cross-references](#cross-references)

---

## Status: PROPOSED (awaiting operator decision + Council Hybrid review)

This ADR is a **decision point**, not an accepted decision. It enumerates three options for sprint 2, surfaces the trade-offs of each against the operator's "setki reinstalacji" risk argument from ADR-001 Decision #4, and recommends Option B. The actual disposition lands when (a) the operator signs off and (b) Council Hybrid (9 roles, weighted vote, critic signature gate) votes the chosen path. Until then, ADR-001 Decision #4 *PARKED* directive remains in force and no W19 evaluator code is dispatched.

---

## Context

Sprint 1 closed with the following W19 state:

- **W19 catalog MVP wired**: charter authored (`docs/v2/charters/W19_policy_plane.md`), policy DSL syntax decided (YAML + sandboxed jinja2 per ADR-001 Decision #4), audit-log capture (write-side hash-chain) is foundational and shared with W15/W17/W18, so it proceeds independently of the parking directive.
- **W19 evaluator PARKED**: the *enforcement* layer — the runtime evaluator that says "this caller may/may not perform this action on this resource" — is parked per ADR-001 Decision #4. Release Rail RBAC enforcement at W14 E6, W19 G2 redaction engine production deploy, departure runbook, MFA, IdP integration are all parked alongside.

**Sprint 2 priority**: decide whether to lift the parking directive now, lift it under conditions, or extend it through sprint 2.

**The risk argument (operator, ADR-001 Decision #4 verbatim)**:

> "Setki reinstalacji AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia"

Translation: hundreds of AEIS reinstallations forced by post-rollout security policy churn would be a tragedy. The operator's argument is *operational, not theoretical*: AEIS is in active development, every charter is still moving, and a security plane that enforces on every call would force a reseed/reinstall on every shape change. The PARKED directive defers W19 evaluator until W15/W16/W17/W18 + W7/W11/W13 are feature-complete (the "parking trigger") so that the eventual rollout applies to a *stable surface*.

**What changed in sprint 1 to make this re-litigable**:

- W15 ontology runtime is past G2 (manifest validation, OSDK auto-gen, hybrid columns + JSONB ext landed); the surface for *policy/audit ontology types* is now stable enough to attach a guard to.
- ADR-001 Decision #1 closed `extension_policy: strict|declared|free` — the surface contract for object-level governance is locked, which is the precondition the evaluator needs to bind to.
- W17 deployment plane has cost-ledger architecture (ADR-001 Decision #3 — event-sourced + materialized view) so a new event type (`policy.evaluated`) on the bus is a known idiom, not a new pattern.
- ADR-002 multi-model routing established the *staged rollout* pattern (route per task type, fallback chain, env-flag-gated) which gives Option B and Option C a precedent to follow without inventing a new rollout shape.

**Mitigations now available** that weren't available at the time of ADR-001 Decision #4:

- **jinja2 SandboxedEnvironment** with `__class__`/`__bases__`/`__subclasses__` denied — DSL choice is already decided in ADR-001 Decision #4; the runtime is the missing piece.
- **Staged rollout** (1% sessions → 10% → 100%) — gates the blast radius; precedent from ADR-002.
- **Feature flag** `SYLION_W19_EVALUATOR_DISABLED=1` — emergency disable without code revert; one-flag rollback restores parked behavior.
- **Audit JSONL emit per decision** — even if the evaluator is wrong, the decisions are inspectable and replayable.
- **Council Hybrid (W3) review of first 10 rule sets** — leverages the existing 9-role / 5-rank weighted-vote machinery as a content gate before any rule is enforced in production.

These mitigations do not eliminate the "setki reinstalacji" risk; they bound it. The decision below is whether the bounded version of the risk is worth taking now versus later.

---

## Decision (proposed, 3 options)

### Option A: KEEP PARKED (sprint 2 status quo)

Continue with ADR-001 Decision #4 unchanged: W19 evaluator stays parked through sprint 2. Audit-log capture continues. Charter authoring continues. No enforcement runtime. No Release Rail RBAC at W14 E6.

- **Trade-off**: zero risk of a half-built security layer forcing reseed cycles, but also **zero policy enforcement** — operator manually checks compliance for any sensitive operation, and any policy violation is caught (if at all) by post-hoc audit-log review rather than at the call site.
- **Cost**: operator time per manual check + the missed-violation case (any sensitive operation that slips past manual review and only surfaces in audit replay).
- **Reversible**: yes — trivially. Status quo is the cheapest reversal because there is nothing to roll back.
- **When to choose**: if the operator judges that the surface (W15/W16/W17/W18 + W7/W11/W13) is *not yet* stable enough for any enforcement, even gated.

### Option B: UNBLOCK with jinja sandbox + 1% staged rollout

Lift the parking directive *conditionally*:

1. **jinja2 SandboxedEnvironment audit** — security review of the sandbox configuration before the evaluator handles any production traffic. Known sandbox-escape vectors (`__class__`, `__bases__`, `__subclasses__` access; `__import__` exposure; lstrip/rstrip filter abuse on attacker-controlled tags) explicitly closed and tested. Estimated 3 days for the audit + remediation pass.
2. **Staged rollout**: 1% of sessions → 10% → 100%, one week per stage. Rollout gate is "no audit-log decision flagged as wrong by Council Hybrid review of the prior week's first 10 rule sets".
3. **Feature flag**: `SYLION_W19_EVALUATOR_DISABLED=1` env var on backend. When set, evaluator is a no-op (returns `allow` for every check) and emits `policy.evaluator_disabled` event for visibility. Single-flag rollback to parked behavior, no redeploy required to flip it.
4. **Audit JSONL emit**: every policy decision (allow/deny/no-rule) writes `{request_id, actor, resource, action, rule_matched, decision, latency_ms}` to the W19 audit chain. Replay-able, hash-chained, joinable with W17 cost-ledger and W18 terminal events.
5. **Council Hybrid review of first 10 rule sets**: before any rule reaches production, the 9-role council (architect, security, cost, performance, compliance, operator-experience, observability, dev-experience, critic) votes on each of the first 10 rule sets. Critic signature gate enforced.

- **Trade-off**: requires the jinja2 sandbox security audit window (~3 days) and the operational discipline of running a staged rollout. In return: enforced policy at the call site for operations the operator deems sensitive, with the blast radius bounded to 1% of sessions for the first rollout week.
- **Cost**: 3-5 days of focused dev effort (sandbox audit + rule-set bootstrap + staged rollout instrumentation). External pen-test of the sandbox layer **NOT required** at this stage — the staged rollout + feature flag + Council review gate is the substitute (pen-test moves to G2 per W19 charter G2 deliverable). Council Hybrid review consumes ~30 minutes per rule set across 9 reviewers, ~5 hours total for the first 10.
- **Reversible**: yes — `SYLION_W19_EVALUATOR_DISABLED=1` on env, restart backend, evaluator becomes no-op. Audit JSONL preserves every decision so a roll-forward (re-enabling) does not lose history.
- **When to choose**: if the operator judges that the W15/W16/W17/W18 surface is stable enough to attach an evaluator to, *and* that the lean ADR-001 Decision #4 DSL preference (YAML + jinja2) is the right size for the rule set the operator currently has in mind (small, declarative, role-based; no transitive relationships).

### Option C: UNBLOCK with OPA Rego external service

Lift the parking directive *and* commit to industry-standard policy infra:

1. **OPA sidecar** running alongside the backend (separate process or container, depending on W17 deployment plane shape). Policies authored in Rego (Open Policy Agent's declarative policy language).
2. **Policy decision logs** captured natively by OPA (decision log feature) and forwarded to the W19 audit chain as `policy.evaluated` events.
3. **Bundle distribution**: policies versioned in git, bundled to OPA via the existing `_evidence` packaging pattern from W14, signed with the same hash chain as audit events.
4. **Feature flag**: `SYLION_W19_EVALUATOR_DISABLED=1` (same shape as Option B); when set, all checks bypass OPA and return `allow` (or fall back to ADR-001 Decision #4 DSL defaults). Rollback requires both env flag flip *and* OPA sidecar removal/disable in W17 deployment manifest, hence "feature flag + redeploy".
5. **Staged rollout**: same 1% → 10% → 100%, but the staged-rollout machinery now also has to coordinate the OPA sidecar's bundle version with backend rollout state.

- **Trade-off**: more complexity (OPA sidecar to deploy, Rego language to learn, decision-log forwarding to wire), but Rego is industry-standard for policy-as-code (k8s admission, Envoy auth, Terraform sentinel-replacement) and OPA handles transitive relationships (the "manager's manager owns" case ADR-001 Decision #4 flagged as the trigger to pivot from jinja2 to OPA) natively.
- **Cost**: 7-10 days of dev + ops setup. OPA sidecar deployment + bundle pipeline + decision-log forwarding + Rego policy authoring + the same staged rollout instrumentation Option B requires. Requires W17 deployment plane to support multi-process node layouts (already in scope for W17 G2; soft dependency).
- **Reversible**: yes via feature flag, but **the full unwind requires a redeploy** to remove the OPA sidecar from the node manifest — this is heavier than Option B's flag-only rollback.
- **When to choose**: if the operator's current rule set already has transitive relationships ("manager's manager", "owner-of-project-of-this-resource"), or if compliance requirements (SOC 2, ISO 27001 — see W19 charter §11) push for an industry-standard policy engine that auditors recognize.

### Recommendation

**Option B (jinja sandbox + 1% staged rollout)** is the recommended path, on the following grounds:

1. **Aligned with ADR-001 Decision #4 lean preference**. The DSL is already chosen (YAML + jinja2). Option B is the *runtime activation* of an already-decided DSL, not a new architectural commitment.
2. **Jinja2 sandbox audit is bounded work** (3 days). The sandbox escape vectors are well-documented in the security literature (Bo0om-style payload references, jinja2 changelog hardenings). The audit checklist is a known artifact, not an open research problem.
3. **Staged rollout + feature flag matches the ADR-002 precedent**. The cron orchestrator already operates a routing matrix with primary/fallback per task type — extending this pattern to "1%/10%/100% per session cohort" is an operational mechanic the team has muscle for.
4. **Council Hybrid review of first 10 rule sets** is a content-quality gate that doesn't exist for OPA in Option C without additional Rego linting/review tooling.
5. **OPA only if Option B's policies grow complex enough to warrant the OPA dependency**. The trigger to migrate from jinja2 to OPA is documented in ADR-001 Decision #4 ("if policies grow complex — transitive relationships, 'manager's manager owns' — pivot to OPA/Rego") and remains the canonical pivot signal. If Option B ships and the rule set stays declarative-and-role-based, OPA is unnecessary infrastructure debt; if it grows transitive, the pluggable engine interface (W19 charter §13 Q6) makes the pivot a backend swap, not a rewrite.

Option A is acceptable as a *deferral* (sprint 2 → sprint 3) if the operator's read of the surface stability is "not yet". Option C is acceptable as a *leapfrog* if compliance pressure or rule complexity forces it before Option B has had its chance to prove the rule set.

---

## Trade-offs matrix

| Dimension | A: PARKED | B: jinja | C: OPA |
|---|---|---|---|
| Implementation cost | 0 days | 3-5 days | 7-10 days |
| Reversibility | trivial (no-op already) | feature flag (env var, no redeploy) | feature flag + redeploy (OPA sidecar removal) |
| Security risk | none (no eval = no eval bug) | jinja2 sandbox escape vectors (bounded, audit checklist known) | OPA sidecar attack surface (extra process, bundle integrity, decision-log tampering) |
| Performance | no overhead | <1ms per eval (in-process jinja2 SandboxedEnvironment) | network hop ~5-20ms per eval (sidecar IPC) |
| Operator learning curve | zero | low (jinja2 is Ansible-style; YAML rule format already chosen) | medium (Rego is a new declarative language; query construction non-obvious) |
| Industry precedent | n/a | embedded sandboxes (Ansible, Salt, Jinja-templated config systems) | k8s admission controllers, Envoy ext_authz, Terraform Sentinel-replacement, Conftest |
| Reseed risk if surface shifts | none | bounded by feature-flag rollback + staged rollout cohort | bounded the same way + extra step to disable sidecar |
| Audit compliance posture | none beyond manual | jinja2 decisions logged to W19 audit chain (hash-chained) | OPA decision logs forwarded to W19 audit chain (industry-standard format, auditor-friendly) |
| Compatibility with ADR-001 Decision #4 DSL | n/a | direct (Decision #4 chose YAML+jinja2) | preserves pluggable interface (Decision #4 explicit escape hatch) |
| Council Hybrid review fit | n/a | natural — 10 rule sets, weighted vote, critic gate | natural — same gate, but Rego review needs reviewer fluency in Rego |

---

## Consequences (per option)

### If Option A chosen:

- ADR-001 Decision #4 PARKED directive remains in force through sprint 2.
- Sprint 2 backlog re-allocates the W19-evaluator capacity to W15/W16/W17/W18 + W7/W11/W13 forward progress, accelerating the parking trigger.
- Operator owns manual compliance checks for any sensitive operation in the interim. Audit-log review remains the only enforcement signal.
- Sprint 3 ADR will revisit the same decision with one more sprint of surface stability data.

### If Option B chosen:

- **jinja2 sandbox audit checklist** (separate task, dispatched per ADR-002 routing matrix — likely Claude bg or codex exec for the security-pattern review). Checklist covers `__class__`, `__bases__`, `__subclasses__`, `__import__`, `__globals__`, `mro`, attribute access on `cycler`/`joiner`/`namespace` builtins, filter abuse (`format`, `attr`, `getattr`), and Bo0om-style template-injection payloads.
- **Staged rollout**: 1% sessions → 10% → 100%, one week each. Rollout gate is the prior week's audit-log review by Council Hybrid: zero "wrong decision" findings = advance; any finding = freeze and re-run.
- **`SYLION_W19_EVALUATOR_DISABLED=1` env flag** for emergency disable. Documented in W17 deployment plane runbook.
- **Audit JSONL emit** for every policy decision. Hash-chained per ADR-001 Decision #3 cost-ledger pattern (events on bus + materialized view if/when query rate justifies).
- **Council Hybrid review of first 10 rule sets**. Each rule set walks the 9-role council (rank-weighted vote, critic signature gate) before reaching production. Sentinels (cost + security) are the hard gates.
- W19 charter §13 Q6 (pluggable engine interface) remains the abstraction boundary — Option C remains a future pivot via backend swap, not a rewrite.
- ADR-001 Decision #4 *operational directive (PARKED)* is **superseded conditionally**: parked-by-default lifts only when staged rollout reaches 100%; flag-disabled state is the new default until then.

### If Option C chosen:

- **OPA sidecar** added to W17 deployment plane node manifest. Adds ~50-150 MB memory per node, one extra process per node.
- **Rego policy authoring** ramps the team on a new language. Initial 10 rule sets translated from intended jinja2 form to Rego (1-2 days additional vs. Option B).
- **Bundle pipeline**: policies versioned in git, bundled, signed (W14 `_evidence` pattern), distributed to OPA via OPA's bundle service.
- **Decision log forwarding**: OPA decision logs → W19 audit chain. Adapter required (OPA → AuditEvent shape).
- **Feature flag + redeploy rollback**: emergency disable is two-step (env flag + sidecar removal), documented in runbook.
- **Pen-test scope expands**: sidecar IPC channel and bundle distribution endpoint enter the pen-test surface (W19 charter R5, G2/G4 pen-test deliverables).
- W19 charter §13 Q6 *resolves with OPA as the production engine*; the pluggable interface remains for future swap (e.g. Cedar, etc.) but is no longer just an escape hatch.
- ADR-001 Decision #4 *DSL choice (YAML+jinja2)* is **superseded** by OPA/Rego under Option C; ADR-001 Decision #4 *operational directive (PARKED)* is **superseded conditionally** the same way as Option B.

---

## Rollback Plan

Applicable to Option B (primary recommendation) and Option C (with redeploy step):

1. **Set environment flag**: `SYLION_W19_EVALUATOR_DISABLED=1` on the backend env (W17 central plane + every node). Redis-backed config refresh propagates within 60s on running services without restart; restart preferred for full propagation.
2. **Restart backend** (foreground or rolling, per W17 deploy strategy). On restart, the evaluator sees the flag, returns `allow` for every check, and emits a single `policy.evaluator_disabled` event so the disable is visible in the audit chain itself.
3. **All routing/apply continues** unchanged. The downstream code paths that called the evaluator now receive a uniform `allow` and proceed; no callers crash because the contract is `allow|deny|no_rule` and `allow` is a valid response.
4. **No data lost**. The audit JSONL chain preserves every decision the evaluator made up to the disable point. Re-enabling later (`SYLION_W19_EVALUATOR_DISABLED=0`) resumes evaluation; the chain's pre-disable and post-disable segments are joinable by hash continuity (one event marks the disable, one marks the re-enable, the chain is unbroken).

**Option C addendum**: after the env flag is set, also disable the OPA sidecar in the W17 node manifest and redeploy. Sidecar process exit + manifest update are logged. Rolling back the OPA bundle pipeline is a separate, idempotent step (bundle removal does not affect the disabled evaluator).

**Option A rollback**: not applicable — Option A *is* the rolled-back state. The "rollback" question is what happens if Option B/C are activated and the operator needs to retreat; the plan above covers that.

**Reseed avoidance commitment** (the core of the operator's "setki reinstalacji" argument): under Option B, no rule change forces a reseed. Adding/removing/editing a rule is a YAML edit + reload (jinja2 SandboxedEnvironment hot-reloads the rule set; failed rules emit a `policy.rule_load_failed` event and the prior rule set continues serving). Under Option C, Rego bundle updates are similarly hot — OPA reloads bundles without restart. Reseed is required only if an *ontology schema* changes in a way that affects rule attribute references; that is the W15 reseed pattern (already-known operational mechanic) and is not new debt introduced by Option B or Option C.

---

## Cross-references

| Topic | Where |
|---|---|
| ADR-001 Decision #4 — W19 PARKED operational directive | [`ADR-001-five-architectural-decisions-2026-04-27.md`](ADR-001-five-architectural-decisions-2026-04-27.md#decision-4-w19--policy-dsl-syntax--parking-strategy) |
| ADR-001 Decision #4 — DSL choice (YAML + sandboxed jinja2) | [`ADR-001-five-architectural-decisions-2026-04-27.md`](ADR-001-five-architectural-decisions-2026-04-27.md#decision-4-w19--policy-dsl-syntax--parking-strategy) |
| ADR-002 — multi-model routing matrix (gradual rollout precedent) | [`ADR-002-multi-model-routing-matrix-2026-04-27.md`](ADR-002-multi-model-routing-matrix-2026-04-27.md) |
| W19 Charter — Policy Plane | [`../charters/W19_policy_plane.md`](../charters/W19_policy_plane.md) |
| W19 Charter §13 Q6 — pluggable engine | [`../charters/W19_policy_plane.md`](../charters/W19_policy_plane.md) §13 Q6 |
| Open question added by this ADR | `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W19-UNBLOCK §8 |
| Council Hybrid (review gate) | project memory entry "Council canonical (roles/ranks/weights/critic/sentinels)" |
| Locked policy reference | PDF §2.5 L12 (minimal JSON rules, with pluggable escape) — Option B preserves; Option C overrides |
| Cron progress trail | `docs/v2/_cron_log.md` (managed by main agent), `MAIN_TASK_v2.md` Cron progress section |

---

*ADR-003 drafted 2026-04-28 by cron orchestrator (sprint 2 opener). Status PROPOSED until operator sign-off + Council Hybrid vote. The "setki reinstalacji" risk argument from ADR-001 Decision #4 is preserved as the load-bearing constraint; Options B and C are bounded versions of that risk, gated by feature flag + staged rollout + Council content review. Recommendation Option B; Options A and C remain valid alternative dispositions.*
