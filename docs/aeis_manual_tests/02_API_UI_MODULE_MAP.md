# AEIS UI/API/Module Map

Status: not started

## Static Snapshot 2026-05-07 Start

Evidence files:

- `docs/aeis_manual_tests/evidence/api/api_ui_coverage_static_start.json`
- `docs/aeis_manual_tests/evidence/api/api_ui_coverage_static_start.md`
- `docs/aeis_manual_tests/evidence/api/backend_packages_static_start.txt`
- `docs/aeis_manual_tests/evidence/api/router_mounts_static_start.txt`

Initial counts:

| Metric | Count | Notes |
|---|---:|---|
| Frontend routes | 127 | From Next.js `page.tsx` scan. |
| Client API refs | 799 | From frontend API client extraction. |
| Runtime OpenAPI paths seen by extractor | 927 | Extractor reached `http://127.0.0.1:8000/openapi.json`; must still be confirmed as the intended AEIS backend during runtime checkpoint. |
| Backend packages | 37 | Under `src/sylion-pipeline/sylion`. |
| Router mounts | 106 | From `sylion/api/router.py`. |

## Runtime Snapshot 2026-05-07 Start

Evidence files:

- `docs/aeis_manual_tests/evidence/api/health_8010.json`
- `docs/aeis_manual_tests/evidence/api/openapi_8010.json`
- `docs/aeis_manual_tests/evidence/api/frontend_3001_root.json`
- `docs/aeis_manual_tests/evidence/api/api_ui_coverage_runtime_8010.json`
- `docs/aeis_manual_tests/evidence/api/api_ui_coverage_runtime_8010.md`

Runtime ports:

| Component | URL | Evidence |
|---|---|---|
| Backend | `http://127.0.0.1:8010` | `/health` = `ok`, version `3.5.0`, modules `138`, health endpoints count `1957` |
| Frontend | `http://127.0.0.1:3001` | root HTTP `200`, content length `94490` |

Runtime coverage extractor:

| Metric | Count |
|---|---:|
| Frontend routes | 127 |
| Client API refs | 799 |
| Runtime OpenAPI paths | 1606 |

Note: ports `3000` and `8000` were already occupied by a different `.claude/worktrees/...` process and are not used as evidence for this test run.

Static mapper priorities:

| Priority | Surface | Reason |
|---:|---|---|
| 1 | Advisor / Teams / Orchestration | Static risk of duplicate router mounting through aggregate router and app-level routers. |
| 2 | Workspace / Projects / Governance tickets | Main AEIS flow depends on these crossing correctly. |
| 3 | Funding | Business-critical POST-heavy local flow with strict no-external-submit requirement. |
| 4 | Skills / Memory / Model Registry / Model Budget | Mixed old/new client methods and runtime bootstrap state must be proven. |
| 5 | Terminal / Operator Mobile | Stateful/SSE/mobile approval behavior cannot be trusted from static mounts. |
| 6 | Secrets / Cloud Connectors / Integrations | Security-sensitive and has stale fallback comments that need runtime proof. |
| 7 | Test Center / Testing | Broad lab surface with high chance of shell/data-shape drift. |

Static mismatch candidates:

| Surface | Candidate Issue | Required Runtime Check |
|---|---|---|
| Advisor / Teams / Orchestration | May be mounted both inside aggregate router and directly in app. | OpenAPI duplicate/shadow check and route smoke. |
| Evaluator / Model Budget / Integrations | Some frontend methods may call old non-prefixed paths. | Browser/API check for all used calls. |
| Secrets | UI contains defensive fallback wording while backend routes exist. | Verify real `/api/v1/secrets` behavior and no fallback masking. |
| Terminal | UI uses commands, stream, and exec endpoints. | Verify command execution, stream/SSE, and error handling. |
| Runtime / Container | UI labels container control as planned/bookkeeping. | Classify as real runtime control or planning-only. |

## Purpose

Map every key operator surface to API, backend module, runtime status, and evidence.

## Status Values

- `LIVE_ADAPTIVE`: works end-to-end and adapts to project needs.
- `LIVE`: works end-to-end.
- `PARTIAL`: works partially.
- `SHELL`: UI/API exists but real function is absent.
- `BROKEN`: breaks the flow.
- `API_ONLY`: backend exists without operator surface.
- `UI_ONLY`: UI exists without real backend.
- `BLOCKER_FIXED`: blocker was found, fixed, and retested from start.
- `BLOCKER_OPEN`: blocker remains.

## Map

| Surface | UI Route | UI File | API Family | Backend Module | Runtime Evidence | Status | Notes |
|---|---|---|---|---|---|---|---|
