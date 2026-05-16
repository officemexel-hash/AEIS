# Worktree Assessment — Human Gate Orchestrator + Operator Mobile

**Worktree:** `C:\Users\razor\Desktop\pipeline_glm\.claude\worktrees\serene-mccarthy-6bb664\`
**Branch:** `claude/serene-mccarthy-6bb664`
**Last commit:** `f5411e4` — *Wave 25: 8 route files + 12 backend modules + 4 frontend pages + test fixes* (2026-04-22 16:09 +0200)
**Distance from master:** 0 commits (worktree HEAD == master tip `f5411e4`). The Human Gate code therefore lives in the shared master history of this worktree, not as a divergent feature branch. The main working copy of the repo (`C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\`) does **not** contain `decision_orchestrator/` or `operator_mobile/` at all — which means the worktree is ahead of whatever the audited main snapshot reflects.
**Mode:** read-only. No files were modified; no branch switched.

---

## 1. Inventory

### 1a. `sylion/decision_orchestrator/` (18 files, 1938 LoC Python)

| File | LoC | Role |
|---|---:|---|
| `__init__.py` | 34 | Public re-exports (Decision, Store, PolicyEngine, ...). |
| `models.py` | 132 | Dataclasses: `Decision`, `DecisionBatch`, `DecisionEvent`, `ApprovalEvent`; enums for priority/risk/type/status. |
| `schemas.py` | 111 | Pydantic v2 request/response models. |
| `store.py` | 308 | Thread-safe SQLite store (decisions, batches, events, approval_events). WAL enabled. |
| `services.py` | 72 | Singleton `OrchestratorServices` wiring every sub-service. |
| `policy_engine.py` | 138 | Autonomy levels 0-5, hard gates, budget gates, risk gates, `AutonomyPolicy`. |
| `decision_classifier.py` | 69 | Rule-based P0-P4 priority + LOW/MEDIUM/HIGH/CRITICAL risk assignment. |
| `decision_queue.py` | 49 | Prioritised views + `expire_overdue`. |
| `approval_service.py` | 222 | Intake / approve / reject / defer / delegate / batch FSM — core state machine. |
| `batch_compiler.py` | 98 | Auto-grouping of pending P2-P4 low/medium decisions. |
| `delegation_service.py` | 118 | Role-based routing + `auto_escalate_overdue`. |
| `dependency_graph.py` | 76 | `is_ready`, `blocked_by`, `ready_set`, `cycle_check` (DFS). |
| `notification_router.py` | 115 | Channel plugin system (`DashboardChannel`, `MobileChannel`). |
| `timeout_handler.py` | 68 | SLA defaults + `tick()` (escalate + expire). |
| `audit_log.py` | 35 | Persisted event trail wrapper. |
| `decision_learning.py` | 93 | Rule mining from approval history + promote/demote. |
| `aeis_adapter.py` | 75 | Agent-event → `Decision` adapter. |
| `routes.py` | 276 | FastAPI router `/api/v1/decisions/**` — 26 endpoints. |

### 1b. `sylion/operator_mobile/` (13 files, 1376 LoC Python)

| File | LoC | Role |
|---|---:|---|
| `__init__.py` | 24 | Public re-exports. |
| `models.py` | 67 | `OperatorDevice`, `ApprovalToken`, `PushNotification`, `DeviceStatus`. |
| `schemas.py` | 112 | Pydantic models for all mobile endpoints. |
| `store.py` | 161 | SQLite (operator_devices, approval_tokens, push_notifications). |
| `services.py` | 59 | `MobileServices` singleton, auto-attaches `MobileChannel` to the orchestrator router. |
| `device_registry.py` | 108 | Register/trust/revoke/mode/follow-me, SHA256 fingerprint, 8-digit pairing code. |
| `approval_tokens.py` | 46 | Short-lived one-shot tokens bound to (decision, device, operator). |
| `biometric_challenge.py` | 104 | Real HMAC-SHA256 challenge/response; constant-time compare. |
| `push_gateway.py` | 86 | Pluggable transport, lockscreen-redacted payload, audit row per push. |
| `notification_policy.py` | 60 | Mode→priority whitelist, Follow-Me window, module filters, lockscreen redaction. |
| `emergency_alerts.py` | 110 | P0 repeat-until-ack loop with backoff and resolution tracking. |
| `operator_digest.py` | 91 | Morning-briefing summary (pending/critical/overdue/velocity). |
| `routes.py` | 350 | FastAPI router `/api/v1/operator-mobile/**` — 20 endpoints. |

### 1c. Bonus: `sylion/operator_mobile_testing/` (Pixel Live Test)

| File | LoC |
|---|---:|
| `__init__.py` | 22 |
| `adb_device_manager.py` | 89 |
| `pixel_test_runner.py` | 185 |
| `routes.py` | 63 |

### 1d. Tests

| File | LoC |
|---|---:|
| `tests/test_decision_orchestrator.py` | 180 |
| `tests/test_decision_orchestrator_http.py` | 167 |
| `tests/test_operator_mobile.py` | 126 |
| `tests/test_pixel_live_test.py` | 39 |
| `tests/test_human_gate.py` | 385 (targets a separate `sylion.governance.human_gate` — not this module) |

**Totals:** ~3,400 LoC production + ~500 LoC dedicated tests + 185 LoC pixel runner.

### 1e. Router registration

`sylion/api/router.py` at lines 70-72 and 137-139 imports and mounts all three routers (`decision_orchestrator`, `operator_mobile`, `operator_mobile_testing`). Wiring is complete.

### 1f. Frontend

No frontend page named `mobile/` or `operator/` exists. `gates/page.tsx` consumes governance/human-gate hooks but it is the pre-existing gates surface, not a new operator-mobile UI. `HumanGatePanel.tsx` similarly pre-dates this work. No new frontend screens for the Operator Mobile subsystem were added in this worktree.

---

## 2. Coverage vs. Spec

### 2a. Human Gate Orchestrator — 13 submodules

| # | Submodule | Status | File(s) | Tests? |
|---|---|---|---|---|
| 01 | Decision Intake | IMPLEMENTED | `aeis_adapter.py` + `approval_service.intake` | YES (orch tests) |
| 02 | Decision Classifier | IMPLEMENTED | `decision_classifier.py` | YES |
| 03 | Autonomy Policy Engine | IMPLEMENTED | `policy_engine.py` (levels 0-5, hard gates, budget gates) | YES |
| 04 | Decision Queue | PARTIAL | `decision_queue.py` — priority views OK; per-type queues (financial/legal/technical/production/security) are query-derived not materialised | YES |
| 05 | Batch Approval Engine | IMPLEMENTED | `batch_compiler.py` + batch FSM in `approval_service.py` | YES |
| 06 | Delegation Engine | IMPLEMENTED | `delegation_service.py` with `EscalationHierarchy` per-type routing | YES |
| 07 | Execution Continuity | MISSING | No work-stealing / deadlock detection / frozen-dependent handling beyond the `dependency_graph.ready_set` view | NO |
| 08 | Decision Dependency Graph | IMPLEMENTED | `dependency_graph.py` (is_ready, blocked_by, cycles) | YES |
| 09 | Risk-Based Auto Approval | IMPLEMENTED | `policy_engine.py` (auto_approve list, level fall-through) | YES |
| 10 | Notification Routing | PARTIAL | `notification_router.py` — dashboard + mobile channel only. SMS/Email/Slack are named constants in `_CRITICAL_CHANNELS` but have no transport class. | YES (routing covered; SMS/email not) |
| 11 | Decision SLA | IMPLEMENTED | `timeout_handler.py` with default P0-P4 caps + `tick()` | YES |
| 12 | Audit Trail | IMPLEMENTED | `audit_log.py` + persisted `DecisionEvent` rows | YES |
| 13 | Decision Learning | IMPLEMENTED | `decision_learning.py` — mine, promote, demote, confidence threshold | PARTIAL (routes tested, mining logic light) |

Coverage: **11 IMPLEMENTED / 2 PARTIAL / 1 MISSING = ~85%** (weighted: ~80% — "Execution Continuity" is significant).

Spec-required files **not present**: `fallback_engine.py`, `autonomy_profiles.py`. Functionality partly absorbed into `policy_engine.py` and `timeout_handler.py`, but no explicit fallback engine.

### 2b. Operator Mobile — 12 submodules

| # | Submodule | Status | File(s) | Tests? |
|---|---|---|---|---|
| 01 | Global Critical Inbox | IMPLEMENTED | `routes.py` (`/decisions/pending`, `/decisions/critical`) + `decision_queue.critical` | YES (HTTP) |
| 02 | Module Channels | PARTIAL | Per-device `operator_mode` + module whitelist in `notification_policy.MODE_MODULE_FILTER`; no first-class "channel subscription" table | Partial |
| 03 | Push Notification Engine | IMPLEMENTED | `push_gateway.py` + `emergency_alerts.py` (repeat-until-ack, backoff, lockscreen redaction) | YES |
| 04 | Mobile Human Gate | IMPLEMENTED | routes: approve/reject/defer/delegate — flows through `ApprovalService` | YES (full HTTP flow test) |
| 05 | Secure Approval Layer | IMPLEMENTED | `biometric_challenge.py` (real HMAC), `approval_tokens.py` (TTL + single-use + binding), device trust enforcement on every approve path | YES |
| 06 | Operator Modes | IMPLEMENTED | `device_registry.set_mode` + 9 whitelisted modes; Follow Me window in policy | YES |
| 07 | System Status | IMPLEMENTED (thin) | `/system-status` returns counts + autonomy level. Not as rich as spec (no docker/VPS stats). | Partial |
| 08 | Batch Approval | IMPLEMENTED (via orchestrator) | Mobile reuses orchestrator `/batches` endpoints; no dedicated mobile view | YES (via orch tests) |
| 09 | Escalation System | IMPLEMENTED | shared with `delegation_service.EscalationHierarchy` | YES |
| 10 | Voice / Chat Operator | MISSING | No voice endpoint, no LLM-backed chat | NO |
| 11 | Audit & Compliance | IMPLEMENTED | Every approval through mobile routes persists `ApprovalEvent` + `DecisionEvent` with device/ip/biometric metadata | YES |
| 12 | Operator Preferences | PARTIAL | `/devices/{id}/notifications/preferences` accepts free-form JSON blob; no typed preference model | Partial |

Coverage: **8 IMPLEMENTED / 3 PARTIAL / 1 MISSING = ~75%**.

Spec-required files **not present**: `mobile_auth.py`, `priority_classifier.py`, `mobile_decision_view.py`, `escalation_service.py` (as standalone), `operator_status.py`, `notification_preferences.py` (as service), `module_channels.py`, `audit_service.py` (as standalone), `pixel_live_test.py` (replaced by dedicated `operator_mobile_testing/` module).

### 2c. Pixel Live Test Mode — bonus

15 spec tests → actual runner covers device detection, registration, decision creation, push, approval, audit, reconnect, token expiry as methods on `PixelTestRunner.run_full`. Fully skips ADB steps when device not attached rather than failing. Tests: `test_pixel_live_test.py` (39 LoC — light).

### 2d. Database tables

Spec lists 23 tables. Actually created:
- `decisions`, `decision_events`, `decision_batches`, `decision_audit_log` (via `decision_events`), `approval_events` — **5/9 orchestrator tables**.
- `operator_devices`, `approval_tokens`, `push_notifications` — **3/10 mobile tables**.

Missing tables: `decision_dependencies` (modelled as JSON column), `decision_policies`, `autonomy_profiles`, `delegations`, `escalations`, `decision_timeouts`, `decision_fallbacks`, `decision_learning_rules`, `operator_mobile_sessions`, `operator_notification_preferences` (free-form JSON), `operator_status`, `operator_modes` (on device row), `operator_module_channels`, `operator_push_tokens` (on device), `operator_device_trust` (status enum), `operator_mobile_audit`, `operator_follow_me_sessions` (device field), all `mobile_test_*`.

Many are absorbed as JSON columns on parent rows — defensible for v1 but not spec-strict.

### 2e. Endpoints

Spec lists 17 orchestrator + 18 mobile + 11 pixel-test endpoints. Actual:
- Orchestrator: 26 endpoints including learning/hierarchy/auto-compile/notify — **exceeds** spec count.
- Mobile: 20 endpoints — covers ~15 of 18 spec lines (missing: explicit `/alerts/test`, `/channels`, `/audit` dedicated routes; digest/emergency added).
- Pixel test: 3 endpoints (`/adb/devices`, `/run-all`, `/qa-report`) — runner is all-in-one rather than per-test.

---

## 3. Quality Assessment

Per-file signals (Y = yes, N = no, P = partial):

| File | Type hints | Docstrings | Integrated | Tests |
|---|---|---|---|---|
| `decision_orchestrator/models.py` | Y | Y | Y | Y |
| `decision_orchestrator/schemas.py` | Y | Y | Y | Y |
| `decision_orchestrator/store.py` | Y | Y | Y | Y |
| `decision_orchestrator/services.py` | Y | Y | Y | Y |
| `decision_orchestrator/policy_engine.py` | Y | Y | Y | Y |
| `decision_orchestrator/decision_classifier.py` | Y | Y | Y | Y |
| `decision_orchestrator/decision_queue.py` | Y | Y | Y | Y |
| `decision_orchestrator/approval_service.py` | Y | Y | Y | Y |
| `decision_orchestrator/batch_compiler.py` | Y | Y | Y | P |
| `decision_orchestrator/delegation_service.py` | Y | Y | Y | P |
| `decision_orchestrator/dependency_graph.py` | Y | Y | Y | P |
| `decision_orchestrator/notification_router.py` | Y | Y | Y | P |
| `decision_orchestrator/timeout_handler.py` | Y | Y | Y | P |
| `decision_orchestrator/audit_log.py` | Y | Y | Y | Y |
| `decision_orchestrator/decision_learning.py` | Y | Y | Y | P |
| `decision_orchestrator/aeis_adapter.py` | Y | Y | Y | Y |
| `decision_orchestrator/routes.py` | Y | Y | Y | Y |
| `operator_mobile/models.py` | Y | Y | Y | Y |
| `operator_mobile/schemas.py` | Y | Y | Y | Y |
| `operator_mobile/store.py` | Y | Y | Y | Y |
| `operator_mobile/services.py` | Y | Y | Y | Y |
| `operator_mobile/device_registry.py` | Y | Y | Y | Y |
| `operator_mobile/approval_tokens.py` | Y | Y | Y | Y |
| `operator_mobile/biometric_challenge.py` | Y | Y | Y | P |
| `operator_mobile/push_gateway.py` | Y | Y | Y | Y |
| `operator_mobile/notification_policy.py` | Y | Y | Y | Y |
| `operator_mobile/emergency_alerts.py` | Y | Y | Y | P |
| `operator_mobile/operator_digest.py` | Y | Y | Y | P |
| `operator_mobile/routes.py` | Y | Y | Y | Y |

- **Typing:** 100% use `from __future__ import annotations`, PEP 604 unions (`str | None`), return annotations everywhere. Mypy-friendly.
- **Docstrings:** every module has a file-level docstring explaining intent; most classes/functions have one-line descriptions. Quality is good, terse, intention-revealing.
- **Integration:** the mobile package explicitly imports the orchestrator services; `notification_router.MobileChannel` wires the two together; `approval_service` is reused from mobile routes (no duplication). No isolated stub files found.
- **Stubs / mocks:** `LocalRecordTransport` is a deliberate in-process transport with `set_transport()` hook for production FCM/APNs — not a stub in the bad sense. No `raise NotImplementedError`, no `pass`-only bodies, no `TODO` bodies. `biometric_challenge.py` uses real `hmac.compare_digest` with SHA-256.
- **Tests:** ~500 LoC of pytest across three test files, all using real SQLite `:memory:` stores and a FastAPI `TestClient` — no mocks. Full mobile approval flow is covered end-to-end (register → trust → request token → biometric → approve → audit verified).
- **Manifest / governance:** I could not find a `MANIFEST.json` entry for `decision_orchestrator` or `operator_mobile` — they are **not** declared in the worktree's top-level `MANIFEST.json`. This is a governance gap.

---

## 4. Comparison with main

- Main working tree `src/sylion-pipeline/sylion/` contains **no** `decision_orchestrator/` and **no** `operator_mobile/` and **no** `operator_mobile_testing/`. Every file in those three packages is 100% new relative to the audited main snapshot.
- The worktree HEAD (`f5411e4`) equals what `git log -10` reports for `main` in the audit prompt, so git-history-wise the code is already "on main" in this worktree — the discrepancy is that the physical main working copy on disk has not been synced to this commit, OR the audit prompt's "main" refers to an older snapshot. Net effect: these files are **committed** and available to anyone who checks out `f5411e4`.

---

## 5. Git Context

- **Branch:** `claude/serene-mccarthy-6bb664` (pointing at `f5411e4`, same as master).
- **Last commit touching this tree:** `f5411e4 Wave 25: 8 route files + 12 backend modules + 4 frontend pages + test fixes` (2026-04-22).
- **Commit history:** Waves 17-25 visible in `git log`. Human Gate modules were added incrementally over multiple waves; file mtimes + wave labels suggest Orchestrator and Mobile landed across waves 20-25.
- **Divergence from `main`:** 0 commits. No rebase / merge required.

---

## 6. RECOMMENDATION: **A) MERGE**

Merge the worktree's Human Gate Orchestrator and Operator Mobile into main, then close the remaining spec gaps as follow-up tickets.

Rationale:
1. **Coverage is high** — ~85% of the Orchestrator submodules and ~75% of the Mobile submodules are implemented with real logic, not stubs. Everything in the "must have before production" layer (policy engine, approval FSM, SLA handler, audit trail, device pairing, biometric HMAC, short-lived tokens, push gateway with lockscreen redaction, emergency repeat-until-ack) is functional.
2. **Quality is high.** 100% type-hinted, full docstrings, no NotImplementedError bodies, no placeholder mocks. The mobile biometric path uses real `hmac.compare_digest` — the only way to make it more real is to swap the in-process challenge map for Redis.
3. **Integration is tight.** `MobileChannel` on the orchestrator's notification router is auto-registered from `MobileServices.__init__`; all mobile approve/reject/defer/delegate routes flow through the single `ApprovalService` state machine — there is no duplicated FSM.
4. **Tests exist and exercise real code paths** (SQLite in-memory + FastAPI TestClient, no mocks). ~500 LoC of tests covering both unit and HTTP layers. A rebuild would throw this away.
5. **Router wiring is in place** (`sylion/api/router.py` mounts all three routers). Merging is a matter of bringing the files across, not re-integrating.
6. **Rebuild cost dominates.** Reproducing ~3,400 LoC of coherent, tested code to the same standard would cost days; the gaps (Execution Continuity Engine, Voice/Chat Operator, typed notification preferences, dedicated SMS/Email/Slack transports, per-queue materialisation) are additive, not structural — they can land as a "Wave 26+" effort on top of the merged base.
7. **Caveats to address post-merge:** (a) add a `MANIFEST.json` entry for governance visibility; (b) implement or explicitly park `ExecutionContinuityEngine` + `FallbackEngine` (those are nontrivial and partially absent); (c) SMS/Email/Slack transports are named but unimplemented — either write them or remove from `_CRITICAL_CHANNELS`; (d) no dedicated frontend screens for the mobile surface (console still uses legacy `gates/page.tsx`) — a new operator-mobile dashboard page should be a follow-up; (e) spec called for ~23 DB tables; actual schema collapses many into JSON columns — fine for v1, revisit if reporting needs normalisation.

Verdict: **merge now, plan a Wave 26 "Human Gate hardening" ticket for the deltas above.** Do **not** rebuild — the existing code is materially correct and well above the quality bar of a throw-away first pass.
