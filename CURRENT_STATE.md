# CURRENT_STATE

## Runtime Scope

- Root release installer defines release `6.2.0` and AEIS API runtime `3.5.0`. Dowod: `scripts/install.ps1:4-5`.
- Root backend helper starts `uvicorn sylion.api.app:app` on `127.0.0.1:8010`. Dowod: `scripts/start-server.ps1:33-37`.
- Root backend helper sets `SYLION_DB_PATH=sylion_aeis.db`, `SYLION_ENV=development` and `PYTHONPATH=src\sylion-pipeline` before starting the API. Dowod: `scripts/start-server.ps1:23-27`.
- Root frontend helper changes into `src/sylion-frontend` and runs `npm run dev`. Dowod: `start_frontend.ps1:1-2`.
- Frontend package is `sylion-frontend@0.1.0` and currently depends on Next `16.2.4`, React `19.2.4` and React DOM `19.2.4`. Dowod: `src/sylion-frontend/package.json:2-24`.
- Frontend dev configuration leaves `NEXT_PUBLIC_API_URL` empty and relies on same-origin API calls. Dowod: `src/sylion-frontend/.env.local:1`.
- Frontend dev rewrites `/api/v1/*` and `/backend-health` to `http://127.0.0.1:8010`. Dowod: `src/sylion-frontend/next.config.ts`.
- Separate dashboard runtime is started by `python dashboard/start.py`, binds to host `127.0.0.1` by default and uses port `8421` by default. Dowod: `src/sylion-pipeline/dashboard/start.py:309-317`, `src/sylion-pipeline/dashboard/start.py:402-427`.

## Ports In Code

| Surface | Bind / port | Dowod |
| --- | --- | --- |
| Root AEIS API helper | `127.0.0.1:8010` | `scripts/start-server.ps1:33-37` |
| Frontend dev server | `npm run dev` from `src/sylion-frontend`; API rewrite target `8010` | `start_frontend.ps1:1-2`, `src/sylion-frontend/.env.local:1`, `src/sylion-frontend/next.config.ts` |
| Dashboard compose service | `127.0.0.1:8421:8421` | `src/sylion-pipeline/docker-compose.yml:24-33` |
| Caddy in dashboard compose | `80`, `443`, `443/udp` | `src/sylion-pipeline/docker-compose.yml:59-66` |
| Grafana in dashboard compose | `127.0.0.1:3000:3000` | `src/sylion-pipeline/docker-compose.yml:149-155` |
| Alertmanager in dashboard compose | `127.0.0.1:9093:9093` | `src/sylion-pipeline/docker-compose.yml:106-117` |
| Prometheus in dashboard compose | `127.0.0.1:9090:9090` | `src/sylion-pipeline/docker-compose.yml:124-141` |
| Full API compose: PostgreSQL | `5432:5432` | `src/sylion-pipeline/docker-compose.full.yml:8-17` |
| Full API compose: NATS client / monitoring | `4222:4222`, `8222:8222` | `src/sylion-pipeline/docker-compose.full.yml:26-37` |
| Full API compose: AEIS API | `8000:8000` | `src/sylion-pipeline/docker-compose.full.yml:47-53` |
| PostgreSQL-only compose: PostgreSQL | `5432:5432` | `src/sylion-pipeline/docker-compose.pg.yml:8-17` |
| PostgreSQL-only compose: AEIS API | `8000:8000` | `src/sylion-pipeline/docker-compose.pg.yml:26-33` |
| Dev overlay: Redis | `127.0.0.1:6379:6379` | `src/sylion-pipeline/docker-compose.dev.yml:58-60` |
| Dev overlay: MailHog | `127.0.0.1:1025:1025`, `127.0.0.1:8025:8025` | `src/sylion-pipeline/docker-compose.dev.yml:62-67` |
| Dev overlay: Adminer | `127.0.0.1:8080:8080` | `src/sylion-pipeline/docker-compose.dev.yml:69-75` |

## Backend Runtime Behavior

- FastAPI app title is `SYLION AEIS` and app version is `3.5.0`. Dowod: `src/sylion-pipeline/sylion/api/app.py:376-381`.
- Default database mode is `sqlite`; PostgreSQL mode is enabled only when `SYLION_DB_MODE=postgres` and `SYLION_DB_URL` is set. Dowod: `src/sylion-pipeline/sylion/api/app.py:287-303`.
- Default event mode is `sqlite`; NATS URL defaults to `nats://localhost:4222`. Dowod: `src/sylion-pipeline/sylion/api/app.py:291-295`.
- During app lifespan, modules are auto-registered from `sylion/contracts/manifests`. Dowod: `src/sylion-pipeline/sylion/api/app.py:317-324`.
- Demo data is seeded only when `SYLION_ENABLE_DEMO_DATA` is truthy. Dowod: `src/sylion-pipeline/sylion/api/app.py:362-364`.
- Default CORS origins are `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:3001` and `http://127.0.0.1:3001` unless `SYLION_CORS_ORIGINS` is set. Dowod: `src/sylion-pipeline/sylion/api/app.py:260-269`, `src/sylion-pipeline/sylion/api/app.py:383-389`.
- Public no-auth paths in middleware are `/health`, `/docs`, `/openapi.json`, `/redoc` and every path under `/api/v1/auth/`. Dowod: `src/sylion-pipeline/sylion/api/app.py:399-407`, `src/sylion-pipeline/sylion/api/app.py:417-438`.
- Global auth enforcement is enabled when `SYLION_AUTH_REQUIRED` is truthy or `SYLION_ENV=production`. Dowod: `src/sylion-pipeline/sylion/api/app.py:33-37`, `src/sylion-pipeline/sylion/api/app.py:437-438`.
- `/health` returns `status`, `version`, `modules`, `endpoints`, `db_mode` and `event_mode`, and conditionally adds `db_health` in PostgreSQL mode and `nats_health` in NATS mode. Dowod: `src/sylion-pipeline/sylion/api/app.py:448-473`.
- Root verify script treats `/health`, `/openapi.json`, `/docs`, `/api/v1/auth/status` and `/api/v1/auth/providers/list` as the minimum release checks. Dowod: `scripts/verify.ps1:38-61`.

## Status Vocabularies In Code

- Auth bootstrap status surface exposes `setup_complete`, `needs_setup`, `user_count`, `provider_count`, `session_count` and `local_provider_configured`. Dowod: `src/sylion-pipeline/sylion/api/auth_routes.py:151-166`.
- Worker states accepted by the registry are `active`, `inactive`, `offline` and `draining`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:29-33`.
- Assignment states accepted by the registry are `pending`, `assigned`, `in_progress`, `completed`, `failed`, `blocked`, `rejected` and `rollback`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:30-33`.
- New workers are inserted with status `active`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:149-169`.
- New assignments are inserted with status `assigned`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:261-277`.
- Patch proposal submission marks an assignment as `completed`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:350-360`.
- New build topologies are inserted with status `draft`. Dowod: `src/sylion-pipeline/sylion/worker/registry.py:373-382`.
- Worker alerts currently use alert types `stale_heartbeat`, `overloaded` and `budget_warning`. Dowod: `src/sylion-pipeline/sylion/worker/monitor.py:20-28`, `src/sylion-pipeline/sylion/worker/monitor.py:60-101`.
- Worker alert severities currently used in monitor logic are `critical` and `warning`, and alert payloads also expose boolean `resolved`. Dowod: `src/sylion-pipeline/sylion/worker/monitor.py:24-28`, `src/sylion-pipeline/sylion/worker/monitor.py:62-101`, `src/sylion-pipeline/sylion/worker/monitor.py:123-132`.
- Pipeline controller persists run statuses including `pending`, `planning`, `generating`, `failed`, `complete` and `cancelled`. Dowod: `src/sylion-pipeline/sylion/core/pipeline_controller.py:33-42`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:177-196`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:235-259`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:371-382`, `src/sylion-pipeline/sylion/core/pipeline_controller.py:414-435`.
- Pipeline state machine states are `idle`, `planning`, `planned`, `generating`, `reviewing`, `complete`, `archived`, `paused` and `cancelled`. Dowod: `src/sylion-pipeline/sylion/pipeline/state_machine.py:37-47`.
- Active pipeline states are `idle`, `planning`, `planned`, `generating` and `reviewing`. Dowod: `src/sylion-pipeline/sylion/pipeline/state_machine.py:49-51`.
- Build-state snapshot reports worker totals with `active` and `offline`, assignment totals with `assigned`, `in_progress` and `completed`, alert totals with `total_unresolved`, drift totals with `total_open` and `critical`, and boolean `build_factory_ready`. Dowod: `src/sylion-pipeline/sylion/core/build_state.py:43-95`, `src/sylion-pipeline/sylion/api/build_state_routes.py:18-30`.
- Drift records are created with default status `open` and can be resolved to status `resolved`. Dowod: `src/sylion-pipeline/sylion/integration/drift_detector.py:52-71`, `src/sylion-pipeline/sylion/integration/drift_detector.py:151-190`, `src/sylion-pipeline/sylion/integration/drift_detector.py:253-260`.
- Drift types currently declared in code are `breaking_change`, `missing_dependency`, `version_mismatch`, `event_drift`, `ownership_drift` and `cross_module_leak`. Dowod: `src/sylion-pipeline/sylion/integration/drift_detector.py:30`.
- Freeze status exposes `frozen`, `frozen_at`, `frozen_by`, `build_id`, `contract_count`, `event_count` and `dependency_count`. Dowod: `src/sylion-pipeline/sylion/contracts/freeze_manager.py:115-126`.

## API Surface Metrics From Current Tree

- Current-tree introspection of `sylion.api.app.app` returned `1433` route objects in `app.routes`. Dowod: local import of `sylion.api.app:app` in the current repository on `2026-04-24`.
- Current-tree introspection of `sylion.api.app.app.openapi()` returned OpenAPI `3.1.0`, `1170` unique path templates and `250` component schemas. Dowod: local import of `sylion.api.app:app` in the current repository on `2026-04-24`.
- The largest route groups by unique path templates are `/api/v1/governance` (`94`), `/api/v1/monitoring` (`73`), `/api/v1/workspace` (`60`), `/api/v1/security` (`51`), `/api/v1/aeis` (`48`) and `/api/v1/funding` (`41`). Dowod: current-tree grouping of `app.openapi()["paths"]` on `2026-04-24`.
