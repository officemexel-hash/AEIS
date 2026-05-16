# API_REFERENCE

## Canonical API Metadata

- FastAPI app title is `SYLION AEIS`. Dowod: `src/sylion-pipeline/sylion/api/app.py:376-381`.
- FastAPI app version is `3.5.0`. Dowod: `src/sylion-pipeline/sylion/api/app.py:376-381`.
- Public documentation and schema endpoints exposed by the runtime are `/docs`, `/openapi.json` and `/redoc`. Dowod: `src/sylion-pipeline/sylion/api/app.py:399-407`, `scripts/verify.ps1:43-50`.
- Current-tree OpenAPI introspection returned OpenAPI `3.1.0`, `1170` unique path templates and `250` component schemas. Dowod: local import of `sylion.api.app:app` and evaluation of `app.openapi()` in the current repository on `2026-04-24`.
- Current-tree route introspection returned `1433` route objects in `app.routes`. Dowod: local import of `sylion.api.app:app` and evaluation of `app.routes` in the current repository on `2026-04-24`.

## Public And Bootstrap Endpoints

| Path | Methods | Why it is public | Dowod |
| --- | --- | --- | --- |
| `/health` | `GET` | Explicit public path in middleware | `src/sylion-pipeline/sylion/api/app.py:399-407`, `src/sylion-pipeline/sylion/api/app.py:448-473` |
| `/docs` | `GET` | Explicit public path in middleware | `src/sylion-pipeline/sylion/api/app.py:399-407`, `scripts/verify.ps1:48-50` |
| `/openapi.json` | `GET` | Explicit public path in middleware | `src/sylion-pipeline/sylion/api/app.py:399-407`, `scripts/verify.ps1:43-45` |
| `/redoc` | `GET` | Explicit public path in middleware | `src/sylion-pipeline/sylion/api/app.py:399-407` |
| `/api/v1/auth/status` | `GET` | `/api/v1/auth/` prefix is public | `src/sylion-pipeline/sylion/api/app.py:405-421`, `src/sylion-pipeline/sylion/api/auth_routes.py:151-166` |
| `/api/v1/auth/setup` | `POST` | `/api/v1/auth/` prefix is public | `src/sylion-pipeline/sylion/api/app.py:405-421`, `src/sylion-pipeline/sylion/api/auth_routes.py:169-205` |
| `/api/v1/auth/login` | `POST` | `/api/v1/auth/` prefix is public | `src/sylion-pipeline/sylion/api/app.py:405-421`, `src/sylion-pipeline/sylion/api/auth_routes.py:208-220` |
| `/api/v1/auth/providers/list` | `GET` | `/api/v1/auth/` prefix is public | `src/sylion-pipeline/sylion/api/app.py:405-421`, `src/sylion-pipeline/sylion/api/auth_routes.py:82-86`, `scripts/verify.ps1:58-60` |

## Health And Auth Contracts

- `/health` returns `status`, `version`, `modules`, `endpoints`, `db_mode` and `event_mode`. Dowod: `src/sylion-pipeline/sylion/api/app.py:448-461`.
- `/health` adds `db_health` only when PostgreSQL mode is active and adds `nats_health` only when event mode is `nats`. Dowod: `src/sylion-pipeline/sylion/api/app.py:463-471`.
- `/api/v1/auth/status` returns `setup_complete`, `needs_setup`, `user_count`, `provider_count`, `session_count` and `local_provider_configured`. Dowod: `src/sylion-pipeline/sylion/api/auth_routes.py:151-166`.
- `/api/v1/auth/setup` creates the first local admin account and returns `user`, `token`, `token_id`, `session_id`, `provider_id` and `expires_at`. Dowod: `src/sylion-pipeline/sylion/api/auth_routes.py:169-205`.
- `/api/v1/auth/login` authenticates against the local provider and returns the provider-auth payload from `AuthProvider.authenticate`. Dowod: `src/sylion-pipeline/sylion/api/auth_routes.py:208-220`.

## Operator-Critical Endpoints

| Area | Path | Methods | Dowod |
| --- | --- | --- | --- |
| Build factory snapshot | `/api/v1/build-state` | `GET` | `src/sylion-pipeline/sylion/api/build_state_routes.py:15-30` |
| Worker fleet | `/api/v1/workers` | `GET`, `POST` | `src/sylion-pipeline/sylion/api/worker_routes.py:111-128` |
| Worker auto-assignment | `/api/v1/workers/assignments/orchestrate` | `POST` | `src/sylion-pipeline/sylion/api/worker_routes.py:226-229` |
| Pipeline submission | `/api/v1/pipeline/ideas` | `POST` | `src/sylion-pipeline/sylion/api/pipeline_routes.py:125-136` |
| Pipeline run list | `/api/v1/pipeline/runs` | `GET` | `src/sylion-pipeline/sylion/api/pipeline_routes.py:162-168` |
| Pipeline state stats | `/api/v1/pipeline/state-machine/stats` | `GET` | `src/sylion-pipeline/sylion/api/pipeline_routes.py:294-299` |
| Contract freeze status | `/api/v1/contracts/freeze/status` | `GET` | local OpenAPI introspection on `2026-04-24`; freeze state shape in `src/sylion-pipeline/sylion/contracts/freeze_manager.py:115-126` |
| Integration drift summary | `/api/v1/integration/drift/summary` | `GET` | local OpenAPI introspection on `2026-04-24`; summary shape in `src/sylion-pipeline/sylion/integration/drift_detector.py:253-260` |
| Observability snapshot | `/api/v1/observability/snapshot` | `GET` | local OpenAPI introspection on `2026-04-24` |

## Prefix Inventory

Counts below are unique OpenAPI path templates grouped by the first three URL segments in the current tree.

| Prefix | Unique paths | Method totals |
| --- | ---: | --- |
| `/api/v1/governance` | 94 | `DELETE:4, GET:65, POST:38, PUT:2` |
| `/api/v1/monitoring` | 73 | `DELETE:1, GET:50, POST:30, PUT:2` |
| `/api/v1/workspace` | 60 | `DELETE:2, GET:33, POST:36, PUT:3` |
| `/api/v1/security` | 51 | `DELETE:2, GET:28, PATCH:1, POST:31, PUT:1` |
| `/api/v1/aeis` | 48 | `GET:30, POST:25` |
| `/api/v1/funding` | 41 | `GET:23, POST:22, PUT:1` |
| `/api/v1/core` | 39 | `DELETE:3, GET:24, POST:20` |
| `/api/v1/cognitive` | 37 | `DELETE:1, GET:28, POST:15` |
| `/api/v1/memory` | 34 | `DELETE:2, GET:23, POST:13` |
| `/api/v1/execution` | 29 | `DELETE:1, GET:20, POST:15` |
| `/api/v1/cellular` | 28 | `GET:17, POST:17` |
| `/api/v1/projects` | 28 | `DELETE:1, GET:16, POST:11, PUT:5` |
| `/api/v1/quality` | 27 | `DELETE:2, GET:21, POST:11, PUT:1` |
| `/api/v1/skills` | 27 | `GET:21, POST:10` |
| `/api/v1/efficiency` | 24 | `GET:19, POST:7` |
| `/api/v1/rebuild` | 24 | `GET:15, POST:14` |
| `/api/v1/sdr` | 23 | `GET:13, POST:13` |
| `/api/v1/workers` | 22 | `DELETE:1, GET:11, PATCH:3, POST:13` |
| `/api/v1/devices` | 16 | `GET:10, POST:9` |
| `/api/v1/surface` | 15 | `GET:9, POST:9` |
| `/api/v1/contracts` | 14 | `DELETE:1, GET:9, POST:6, PUT:1` |
| `/api/v1/golden-sets` | 14 | `DELETE:2, GET:9, POST:5, PUT:1` |
| `/api/v1/auth` | 14 | `DELETE:1, GET:7, PATCH:1, POST:7` |
| `/api/v1/pipeline` | 13 | `GET:7, POST:7` |
| `/api/v1/audit` | 12 | `GET:7, POST:5` |
| `/api/v1/gates` | 12 | `DELETE:1, GET:9, POST:5, PUT:1` |
| `/api/v1/notification-engine` | 10 | `DELETE:2, GET:4, POST:6, PUT:2` |
| `/api/v1/circuit-breakers` | 10 | `GET:6, POST:5` |
| `/api/v1/security-audit` | 10 | `GET:5, PATCH:1, POST:5` |
| `/api/v1/agents` | 10 | `DELETE:1, GET:7, POST:3, PUT:1` |
| `/api/v1/integration` | 10 | `DELETE:1, GET:5, PATCH:1, POST:6` |
| `/api/v1/bundles` | 9 | `DELETE:1, GET:5, POST:4` |
| `/api/v1/bootstrap` | 9 | `DELETE:2, GET:5, PATCH:1, POST:3` |
| `/api/v1/versions` | 9 | `GET:6, POST:4` |
| `/api/v1/vps` | 9 | `DELETE:1, GET:6, PATCH:2, POST:5` |
| `/api/v1/container` | 9 | `DELETE:4, GET:9, PATCH:3, POST:4` |
| `/api/v1/brain` | 8 | `GET:4, POST:3, PUT:1` |
| `/api/v1/deployments` | 8 | `GET:4, POST:5` |
| `/api/v1/self-healing` | 8 | `DELETE:1, GET:6, POST:3, PUT:1` |
| `/api/v1/capacity` | 8 | `GET:7, POST:2` |
| `/api/v1/model-budget` | 8 | `GET:6, POST:3` |
| `/api/v1/adapters` | 8 | `DELETE:2, GET:5, PATCH:1, POST:3` |
| `/api/v1/profile-swaps` | 8 | `GET:5, POST:4` |
| `/api/v1/rollback` | 8 | `GET:5, POST:5` |
| `/api/v1/hot-swap` | 7 | `DELETE:1, GET:3, POST:4` |
| `/api/v1/execution-guard` | 7 | `DELETE:1, GET:2, POST:5, PUT:1` |
| `/api/v1/evaluator` | 7 | `DELETE:1, GET:4, POST:4, PUT:1` |
| `/api/v1/audit-query` | 7 | `GET:4, POST:3` |
| `/api/v1/connectors` | 7 | `DELETE:1, GET:7, PATCH:1, POST:2, PUT:1` |
| `/api/v1/secrets` | 7 | `DELETE:1, GET:6, POST:2` |
| `/api/v1/security-profiles` | 7 | `DELETE:2, GET:5, PATCH:1, POST:3` |
| `/api/v1/knowledge` | 7 | `DELETE:1, GET:5, POST:3, PUT:1` |
| `/api/v1/model-registry` | 7 | `DELETE:2, GET:4, POST:3, PUT:1` |
| `/api/v1/regression` | 7 | `GET:5, POST:3, PUT:1` |
| `/api/v1/observability` | 7 | `GET:5, POST:4` |
| `/api/v1/health` | 6 | `GET:5, POST:1` |
| `/api/v1/hotswap` | 6 | `GET:3, POST:3` |
| `/api/v1/roles` | 6 | `DELETE:2, GET:3, POST:3, PUT:1` |
| `/api/v1/phantom` | 6 | `GET:3, POST:4` |
| `/api/v1/healing-engine` | 6 | `DELETE:1, GET:4, POST:3, PUT:1` |
| `/api/v1/audit-sink` | 6 | `DELETE:1, GET:3, POST:3, PUT:1` |
| `/api/v1/feedback` | 6 | `GET:6, POST:3` |
| `/api/v1/lifecycle` | 6 | `GET:4, POST:4` |
| `/api/v1/vault` | 6 | `DELETE:1, GET:1, POST:5` |
| `/api/v1/notifications` | 5 | `GET:1, POST:4` |
| `/api/v1/snapshots` | 5 | `DELETE:1, GET:3, POST:3` |
| `/api/v1/evidence-timeline` | 5 | `DELETE:1, GET:5, POST:2` |
| `/api/v1/self-explanation` | 5 | `DELETE:1, GET:4, POST:2, PUT:1` |
| `/api/v1/hardened-audit` | 5 | `GET:3, POST:3` |
| `/api/v1/ideas` | 5 | `DELETE:1, GET:5, POST:2, PUT:1` |
| `/api/v1/integrations` | 5 | `DELETE:1, GET:5, POST:3, PUT:1` |
| `/api/v1/decision-boundaries` | 4 | `DELETE:1, GET:3, POST:2, PUT:1` |
| `/api/v1/decision-snapshots` | 4 | `GET:3, POST:2` |
| `/api/v1/registry` | 3 | `DELETE:1, GET:2, POST:2` |
| `/api/v1/event-backbone` | 3 | `GET:3` |
| `/api/v1/deploy` | 3 | `GET:2, POST:1` |
| `/api/v1/manifests` | 2 | `GET:1, POST:1` |
| `/api/v1/risk` | 2 | `GET:2` |
| `/api/v1/ai-providers` | 2 | `GET:1, POST:1` |
| `/ws/stats` | 1 | `GET:1` |
| `/api/v1/build-state` | 1 | `GET:1` |
| `/health` | 1 | `GET:1` |

## Status-Carrying Surfaces

- Build-state API aggregates worker status, assignment status, unresolved alerts, open drift counts, freeze status and boolean `build_factory_ready`. Dowod: `src/sylion-pipeline/sylion/core/build_state.py:43-95`, `src/sylion-pipeline/sylion/api/build_state_routes.py:18-30`.
- Worker registry states are `active`, `inactive`, `offline` and `draining`, and assignment states are `pending`, `assigned`, `in_progress`, `completed`, `failed`, `blocked`, `rejected` and `rollback`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:29-33`.
- Pipeline controller persists run statuses including `pending`, `planning`, `generating`, `failed`, `complete` and `cancelled`. Dowod: `src/sylion-pipeline/sylion/core/pipeline_controller.py:33-42`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:177-196`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:235-259`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:371-382`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:414-435`.
- Pipeline state machine states are `idle`, `planning`, `planned`, `generating`, `reviewing`, `complete`, `archived`, `paused` and `cancelled`. Dowod: `src/sylion-pipeline/sylion/pipeline/state_machine.py:37-65`.
- Drift records use status `open` on creation and `resolved` on resolution, with declared drift types `breaking_change`, `missing_dependency`, `version_mismatch`, `event_drift`, `ownership_drift` and `cross_module_leak`. Dowod: `src/sylion-pipeline/sylion/integration/drift_detector.py:30`, `src/sylion-pipeline/sylion/integration/drift_detector.py:52-71`, `src/sylion-pipeline/sylion/integration/drift_detector.py:151-190`, `src/sylion-pipeline/sylion/integration/drift_detector.py:253-260`.
- Freeze status payload exposes `frozen`, `frozen_at`, `frozen_by`, `build_id`, `contract_count`, `event_count` and `dependency_count`. Dowod: `src/sylion-pipeline/sylion/contracts/freeze_manager.py:115-126`.
