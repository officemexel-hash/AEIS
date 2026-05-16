# ADR-001: Five Architectural Decisions (2026-04-27)

> **Status**: ACCEPTED
> **Date**: 2026-04-27
> **Decision-maker**: Robert (operator/founder, founder rank 5)
> **Scope**: SYLION AEIS v2 — charters W15, W16, W17, W19, W7→W13
> **Supersedes**: open questions in `docs/v2/CHARTER_OPEN_QUESTIONS_DELTA.md` §1, §6, §8 (RESOLVED markers cross-link here)
> **Author of record**: cron orchestrator round 2026-04-27 (archival pass; operator's decision text is verbatim)

## Table of contents

1. [Executive summary](#executive-summary)
2. [Decision #1 — W15: Extension JSONB validation](#decision-1-w15--extension-jsonb-validation)
3. [Decision #2 — W16: Idea → App Studio](#decision-2-w16--idea--app-studio)
4. [Decision #3 — W17: Cost-ledger persistence](#decision-3-w17--cost-ledger-persistence)
5. [Decision #4 — W19: Policy DSL syntax + parking strategy](#decision-4-w19--policy-dsl-syntax--parking-strategy)
6. [Decision #5 — W7→W13: Task-to-role matching](#decision-5-w7w13--task-to-role-matching)
7. [Operational note: W19 parking strategy](#operational-note-w19-parking-strategy)
8. [Cross-references](#cross-references)
9. [Implementation dispatch (future cron rounds)](#implementation-dispatch-future-cron-rounds)

---

## Executive summary

On 2026-04-27 the operator (Robert) resolved five architectural fork-points that
had been open in `CHARTER_OPEN_QUESTIONS_DELTA.md` and that were blocking concrete
implementation of W15 manifest validation, W16 app-generation pipeline, W17 cost
tracking, W19 policy enforcement, and W7→W13 task-to-role matching. The resolutions
share a common philosophy — **strict-by-default with explicit opt-out**, **hybrid
pipelines** (cheap heuristic first, expensive model last), and **anti-hallucination
DNA** (no production path that bypasses validation). One resolution is itself a
parking directive: the W19 evaluator is intentionally deferred until the rest of v2
stabilizes, on the explicit operator argument that hardening security before the
surface is stable would force "setki reinstalacji" (hundreds of AEIS reinstallations)
once the surface inevitably shifts. This ADR locks each decision and dispatches the
implementation work to subsequent cron rounds.

---

## Decision #1 — W15: Extension JSONB validation

### Context

W15 ontology runtime stores objects in a hybrid layout: typed columns for the
declared "core" fields plus a JSONB blob `_ext` for extension fields declared by
manifest. Open question (RnD-1 + Q-W15-derived): how strict should write-time
validation of the JSONB blob be? Three positions on the spectrum:

- Loose: anything in JSONB is allowed (fastest dev iteration, biggest hallucination
  surface — LLMs and generators can silently invent fields).
- Strict: only declared fields allowed (safest, but kills R&D iteration).
- Two-tier: strict for production, loose for sandbox.

The operator wanted explicit per-object-type granularity, not a global flag.

### Decision

**Operator decision verbatim**:

> Hybrid with default strict. Three levels per object type, declared in manifest:
> - **strict** (default): only declared extension fields allowed; validation at write-time
> - **declared**: undeclared fields go to `_ext._unvalidated` with warning log (not hard fail)
> - **free**: free-form, but objects of type=free CANNOT go to production (Release Rail enforcement, W14 E6)
>
> Manifest gains `extension_policy: strict` + `extension_fields: [{name, type, indexed, default}]`.
>
> Rationale: anti-hallucination DNA of system requires strict-by-default; free as safety valve for R&D.

### Trade-offs

- **Pros**: surface for hallucinated/typo'd field names is closed by default;
  R&D can still escape via `free` without polluting production; declared-with-warning
  gives a "soft fail" middle ground for migration scenarios where some legacy
  records have stray fields.
- **Cons**: manifest schema gains two new fields and a release-rail check; existing
  W14 manifests need a one-time backfill of `extension_policy: strict`; Release Rail
  (W14 E6) has to learn the `type=free → reject for prod` rule.

### Rationale

The operator emphasized the system's "anti-hallucination DNA" — i.e. that it is
a conscious value of the architecture to refuse silent invention of structure.
A loose default would invert that value. The `free` tier exists explicitly as a
*safety valve*: R&D can iterate without manifest churn, and the cost of using it
is only paid at the production gate (Release Rail).

### Consequences

- Manifest spec (W15) gains:
  - `extension_policy: strict|declared|free` (default `strict`).
  - `extension_fields: [{name, type, indexed, default}]` (catalog of allowed extension fields).
- Compiler (W15) emits per-object-type validators that consult `extension_policy`.
- Release Rail (W14 E6) gains a guardian rule: any object whose type has
  `extension_policy: free` is blocked from `prod` deployment.
- Open P0/P1 list in `MAIN_TASK_v2.md` is unaffected; this is a **new** cron task,
  dispatched separately.

### Cross-reference

- Charter: [`docs/v2/charters/W15_ontology_runtime.md`](../charters/W15_ontology_runtime.md)
- Open questions: `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W15-EXT-VALIDATION + RnD-1 RESOLVED stamp.
- Locked policy reference: PDF §2.5 L8 (hybrid storage columns + JSONB ext) — this decision specializes how the JSONB half is governed.

---

## Decision #2 — W16: Idea → App Studio

### Context

W16 (Apps Builder) needs a path from a bare operator idea ("I want to track
field inspections") to a concrete app manifest. Three approaches were on the
table:

- Templates only (fast, narrow coverage, brittle for novel ideas).
- LLM-only generation (creative, expensive, hallucinates structure).
- Cascade (cheap matchers first, LLM last, with operator gates).

The operator chose the cascade with explicit thresholds and an explicit hand-off
to the Council before any generated manifest reaches production.

### Decision

**Operator decision verbatim**:

> Cascade pipeline:
> 1. **Template matching** (top-N library, ~20 templates: inventory tracker, field inspection, approval workflow, CRM lite, pipeline tracker)
> 2. **Embeddings retrieval** if template match score < 0.7 — surfaces "may be similar to..."
> 3. **LLM generation** if operator rejects all template suggestions — uses templates as few-shot
>
> Every generated manifest passes through Council Hybrid (W3) before becoming production.
>
> Threshold (0.7) is empirical — measure miss rate over 2 months, adjust.

### Trade-offs

- **Pros**: cheap path covers the common case (~20 templates is sufficient for
  inventory/CRM/workflow archetypes); embeddings step bridges similar-but-not-exact
  matches without invoking an LLM; LLM is the last resort and is forced through
  Council Hybrid before promotion. Threshold is measurable and tunable.
- **Cons**: 0.7 is a guess until two months of telemetry land; template library
  needs curation (~20 high-quality templates is non-trivial work); embeddings
  store needs a freshness story (when templates change, vectors must reindex).

### Rationale

Three layers ordered from cheapest to most expensive minimize LLM cost and
hallucination exposure for the >80% of cases that match an existing pattern.
Council Hybrid (W3) acts as the production gate, preserving the
anti-hallucination DNA from Decision #1 at the *application generation* layer.

### Consequences

- W16 G2 charter gains an "idea→app" task with three sub-tasks (template matcher,
  embeddings retriever, LLM fallback).
- Telemetry: track per-stage hit/miss rates; threshold (0.7) is config-flagged for
  tuning without redeploy.
- Council Hybrid (W3) becomes a hard dependency for W16 G2 production promotion.
- Template library (~20 manifests) needs a curation backlog item.

### Cross-reference

- Charter: [`docs/v2/charters/W16_apps_builder.md`](../charters/W16_apps_builder.md)
- Open questions: `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W16-IDEA-STUDIO.
- Council Hybrid: see project memory entry "Council canonical (roles/ranks/weights/critic/sentinels)".

---

## Decision #3 — W17: Cost-ledger persistence

### Context

W17 (Deployment Plane) needs to track LLM call cost across hosts/models for both
operational queries (live dashboard) and audit (provable history). Pure
event-sourcing gives audit guarantees but slow aggregations; pure relational
gives fast reads but no immutable trail. The operator chose hybrid.

### Decision

**Operator decision verbatim**:

> Hybrid: event-sourced ground truth + PG materialized view for fast queries.
> - Each LLM call emits event `cost.recorded` to event_bus (immutable, hash-chained)
> - PG materialized view `mv_cost_ledger` refreshed every 30s (incremental)
> - Reads come from view (fast aggregations); audits from events (provable)
> - Open: refresh-frequency tuning (30s baseline; trigger-based for active sessions, cron for historical may be better)

### Trade-offs

- **Pros**: events provide immutable audit (tie into existing hash-chain pattern,
  Q-CROSS-1); view provides p95<100ms aggregations for dashboard; the two layers
  cannot drift silently because the view is derived from the events, not co-written.
- **Cons**: 30s lag means dashboard is "near real-time", not "real-time" — UI
  must label this; materialized view refresh under load may itself become
  a hotspot (the open sub-question on refresh tuning anticipates this).

### Rationale

This is the same hybrid pattern already locked for hash-chain audit
(`evidence_spine`, Q-CROSS-1) and tiered audit storage (Q-CROSS-4). Re-using a
known pattern is cheaper than inventing a new one and shares operational
muscles (incident response, archival, replay).

### Consequences

- New event type `cost.recorded` on the event bus.
- New PG materialized view `mv_cost_ledger` with incremental refresh.
- Open sub-question: refresh strategy for active sessions (trigger-based push)
  vs historical aggregation (cron). To be revisited at W17 G2 spike.
- Existing cost surface that today reads from a flat table will read from
  the view; back-compat shim if needed.

### Cross-reference

- Charter: [`docs/v2/charters/W17_deployment_plane.md`](../charters/W17_deployment_plane.md)
- Open questions: `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W17-COST-LEDGER.
- Hash-chain: Q-CROSS-1 (`sylion/aeis_v2/hash_chain/`).
- Tiered storage: Q-CROSS-4 (`sylion/aeis_v2/storage/tiered_storage.py`).

---

## Decision #4 — W19: Policy DSL syntax + parking strategy

### Context

W19 (Policy Plane) is the security/RBAC plane. Two questions had to be answered
together: (a) what DSL operators write rules in, and (b) when in the v2 timeline
the evaluator becomes load-bearing. The operator's answer to (b) is the more
consequential one.

### Decision

**Operator decision verbatim**:

> YAML + jinja2 (sandboxed) for default cases.
> ```yaml
> rules:
>   - name: admin_full_access
>     when: "user.role == 'admin'"
>     allow: ["read", "write", "delete"]
> ```
> SandboxedEnvironment must be configured strictly (no `__class__` access).
> If policies grow complex (transitive relationships, "manager's manager owns") — pivot to OPA/Rego.
>
> **CRITICAL OPERATIONAL DIRECTIVE**: W19 evaluator + Release Rail enforcement is PARKED until W15/W16/W17/W18 + W7/W11/W13 are feature-complete. "Setki reinstalacji AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia" — security applied last, once core is stable.

### Trade-offs

- **Pros (DSL choice)**: YAML+jinja2 is approachable for operators familiar with
  Ansible-style config, and `SandboxedEnvironment` already exists in jinja2 with
  proven hardening. Pluggable engine (per Q-W19-6) is preserved as the abstraction
  boundary, so OPA/Rego pivot is a backend swap, not a rewrite.
- **Pros (parking)**: avoids the documented worst case where a half-built security
  layer forces hundreds of reinstall-and-reseed cycles every time the surface
  shifts (the operator's "setki reinstalacji" argument). Defers complexity until
  the surface is stable.
- **Cons (DSL choice)**: jinja2 sandbox requires careful config (no `__class__`,
  no `__bases__`, no `__subclasses__` access — known sandbox-escape vectors); test
  matrix has to cover these.
- **Cons (parking)**: v2 ships without enforced field-level redaction or RBAC for
  an extended window; this is a known gap mitigated by single-tenant scope (PDF L3).

### Rationale (parking)

The operator's argument is operational, not theoretical: AEIS is in active
development, every charter is still moving, and a security plane that enforces
on every call would force a reseed/reinstall on every shape change. Building
W19 last — once W15/W16/W17/W18/W7/W11/W13 are feature-complete — means it
applies to a *stable surface*, and reinstall friction lands once, not hundreds
of times.

### Consequences

- W19 charter §13 Q6 (Q-W19-6) is RESOLVED at the DSL layer (YAML + jinja2 +
  pluggable engine).
- W19 evaluator and Release Rail enforcement are **PARKED**: no cron rounds
  dispatched until the parking trigger fires (W15/W16/W17/W18 + W7/W11/W13 all
  feature-complete).
- Single-tenant policy (PDF L3) carries the security guarantee in the meantime.
- Audit log capture (W19 G2 redaction layer) may proceed *write-side* (hash-chain
  audit) without enforcement.

### Cross-reference

- Charter: [`docs/v2/charters/W19_policy_plane.md`](../charters/W19_policy_plane.md)
- Open questions: `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-W19-6 (RESOLVED stamp), Q-NEW-W19-POLICY-DSL.
- Locked policy reference: PDF §2.5 L12 (minimal JSON rules, with pluggable escape).

---

## Decision #5 — W7→W13: Task-to-role matching

### Context

W13 (Task-to-Role Suggester) consumes the W7 Role Catalog (~30-41 roles) and
proposes roles for a given task. Two extremes: pure tag overlap (cheap, brittle
for synonyms) vs pure embeddings (smooth, expensive, slow first-call). The
operator chose a cascade, mirroring Decision #2's philosophy.

### Decision

**Operator decision verbatim**:

> Hybrid: tag overlap (Jaccard) top-10 → embeddings cosine top-3 → AdvisorCard with reasons → operator picks (or auto = top-1).
>
> Embeddings model: start with `nomic-embed-text` via Ollama (zero-cost local), upgrade if quality < threshold after 2 months.
>
> Role catalog has ~30-41 roles, even weak embeddings model adequate for that count.

### Trade-offs

- **Pros**: Jaccard pre-filter to 10 keeps the embedding workload tiny (~10×3
  cosine ops); local Ollama keeps cost zero; AdvisorCard with reasons preserves
  operator agency; auto=top-1 covers high-confidence cases. ~40 roles is small
  enough that even a 768-dim embedding model is fast.
- **Cons**: Jaccard top-10 may miss synonym-only matches that have no tag
  overlap (mitigated by embeddings step but capped at the top-10 pool); auto=top-1
  bypasses operator review when confidence is high — needs a confidence threshold
  to avoid silent wrong-role assignment.

### Rationale

Same logic as Decision #2: cheap deterministic heuristic first, embeddings only
on the short-list, human only when ambiguous. The role count (~40) is small
enough that even a "weak" local embedding model is adequate — the operator
explicitly traded model strength for zero infra cost.

### Consequences

- W13 charter gains the cascade pipeline (Jaccard → cosine → AdvisorCard).
- W11 provider hookup: Ollama embeddings provider must support `nomic-embed-text`.
- Two-month telemetry trigger to revisit model choice.
- AdvisorCard surface (existing) gains a "task→role" view variant.

### Cross-reference

- Charter: [`docs/v2/charters/W19_policy_plane.md`](../charters/W19_policy_plane.md) (W7 charter is folded into W19/Wave-3 plan currently; this decision attaches to W7 + W13 work)
- Open questions: `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W7-W13-TASK-ROLE.
- Council canonical: 9 roles + 5 ranks (project memory) — separate concept from W7's 30-41 task roles.

---

## Operational note: W19 parking strategy

Decision #4 contains an operational directive that applies beyond W19 itself.
Recording it here so future cron rounds do not re-dispatch W19 work prematurely:

> W19 evaluator + Release Rail enforcement is PARKED until **W15/W16/W17/W18 + W7/W11/W13** are feature-complete. "Setki reinstalacji AEIS przy rozbudowanym systemie bezpieczeństwa to byłaby tragedia" — security applied last, once core is stable.

**Parking trigger**: all of W15, W16, W17, W18 reach G4 (or operator-declared
feature-complete state); all of W7, W11, W13 extensions land. At that point the
parking lifts and W19 evaluator/Release Rail work resumes via standard cron
dispatch.

**What is *not* parked** (clarification, not in operator's verbatim text but
implicit):

- W19 audit log capture (write-side hash-chain) — this is foundational and
  shared with W15/W17/W18 audit infrastructure.
- W19 charter authoring — already done.
- W19 G1 spike work (DSL syntax test, sandbox config audit) — may proceed
  opportunistically, but no production hookup.

**What *is* parked**:

- W19 evaluator service.
- Release Rail RBAC/redaction enforcement at W14 E6.
- W19 G2 redaction engine production deploy.
- W19 G3+ (departure runbook, MFA enforcement, IdP integration).

---

## Cross-references

| Decision | Affected charter | Affected memory entry | Resolves Q-ID |
|---|---|---|---|
| #1 | [W15](../charters/W15_ontology_runtime.md) | — | Q-NEW-W15-EXT-VALIDATION + RnD-1 |
| #2 | [W16](../charters/W16_apps_builder.md) | Council canonical | Q-NEW-W16-IDEA-STUDIO |
| #3 | [W17](../charters/W17_deployment_plane.md) | — | Q-NEW-W17-COST-LEDGER |
| #4 | [W19](../charters/W19_policy_plane.md) | — | Q-W19-6 + Q-NEW-W19-POLICY-DSL |
| #5 | (W7 + W13, no current charter file; folded into W19/Wave-3) | — | Q-NEW-W7-W13-TASK-ROLE |

Linked locked policies (PDF §2 LOCKED list, see `CHARTER_OPEN_QUESTIONS_DELTA.md` §7):

- L8 (hybrid storage columns + JSONB ext) — specialized by Decision #1.
- L12 (policy engine: minimal JSON, pluggable escape) — overridden in syntax by Decision #4 (YAML+jinja2 retains the pluggable interface).
- L3 (single-tenant) — bears the interim security guarantee while Decision #4 parks W19.

---

## Implementation dispatch (future cron rounds)

This ADR is doc-only. Implementation of each decision is dispatched as a
separate cron task in subsequent rounds:

| Decision | Dispatch target | Status |
|---|---|---|
| #1 (extension validation) | future cron task on `manifest.py` | not yet dispatched |
| #2 (idea→app studio) | future W16 G2 task | not yet dispatched |
| #3 (cost-ledger) | future W17 G2 task | not yet dispatched |
| #4 (policy DSL) | **PARKED** — do not dispatch until parking trigger fires | parked |
| #5 (task-role matching) | future W13 task | not yet dispatched |

---

*ADR-001 archived 2026-04-27 by cron orchestrator. Operator decision text is
verbatim; rationale/consequence framing is editorial, with operator explicitly
citing the "anti-hallucination DNA" and "setki reinstalacji" arguments.*
