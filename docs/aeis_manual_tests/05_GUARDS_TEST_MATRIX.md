# AEIS Guards Test Matrix

Status: executed for W14 self-test on 2026-05-08; some non-P5 global surfaces remain noisy.

## Guard Pass Rule

A guard passes only when it blocks a real bad condition, shows the reason to the operator, records audit evidence, and allows progress after the input is corrected.

## Matrix

| Guard | Bad Condition To Trigger | Expected Block | Operator Message | Audit Evidence | Recovery Step | Status |
|---|---|---|---|---|---|---|
| Cost Guard | fast/expensive mode without cost cap or approval | Block expensive execution | P5 bad runtime config reset to local-only; W14 release requires sentinel pass | Execution runtime evidence and production gate sentinel | Add cap/approval | PASS |
| Subscription/Budget Guard | paid model usage while subscription/quota path is available or budget cap missing | Block paid-budget path | Subscription-first policy retained in model/runtime evidence | P5 planning model matrix and W14 production governance | Use subscription quota or add approved cap | PASS |
| Security Guard | unsafe secret/action/data pattern | Block risky action | No external/prod action without gate | P5 `/external-action` block and W14 security sentinel | Remove risk | PASS |
| Secret Redaction Guard | API key appears in UI logs, screenshots, reports, or chat | Block report/pass and redact secret | Secrets not reprinted in reports; terminal stream redacts secret-like payload keys | Terminal stream denylist and no-mock/no-secret evidence | Rotate key and redact evidence | PASS |
| External Action Guard | VPS deploy, paid API, real submit | Block external action | `external_runtime_request_blocked_local_only`; Release Gate strict mode | P4/P5 runtime evidence, W14 release gate | Keep local/read-only | PASS |
| Provenance Guard | scoring/claim without source | Block scoring/claim | Release Gate requires evidence per PASS and audit chain | W14 TestRun evidence packs and release decision | Add source | PASS |
| Quality Guard | release without tests | Block release | Release blocked until charter + T0-T19 + production checks existed | W14 catalog and release gate status | Run tests | PASS |
| Coherence Guard | conflict between idea, Book, and Masterplan | Block or flag inconsistency | Truth Alignment drift would block | Project-scoped truth matrix 14/14 aligned | Align documents | PASS |
| Human Gate Guard | promotion/freeze/build without approval | Block action | Charter approval requires explicit HG D3 action | `tc_03b0f3a6a1ad`, `hg_test_charter_*`, final release decision | Approve via Human Gate | PASS |
| No-Mock Guard | mock/stub/fallback in product or Dashboard | Block pass/release | 0 blocking mock/stub/demo as live | `/test-center/no-mock-scan`: 445 files, 3 allowed non-blocking mentions | Replace with real behavior | PASS |
| Truth Alignment Guard | product behavior diverges from Source of Truth | Block release | Project matrix now shows real feature count, not empty PASS | `/test-center/truth-alignment?project_id=proj_b9c142b06eb4`: 14 aligned, 0 drift | Fix product or truth | PASS |
