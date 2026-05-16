# 00 · RUNTIME STARTUP — jak uruchomić stack do audytu

> Generowane przez audyt `AEIS Canon 2026-04-24`. Źródło prawdy: kod, nie dokumentacja.

## Backend (AEIS API, port 8010)

```powershell
.\scripts\start-server.ps1
```

- Uruchamia `uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010`
- Ustawia: `SYLION_DB_PATH=sylion_aeis.db`, `SYLION_ENV=development`, `PYTHONPATH=src\sylion-pipeline`
- Ładuje `.env.generated` (JWT secret, internal API key, vault secret)
- Dodatkowo `.env` w katalogu głównym zawiera klucze: OPENAI, ANTHROPIC, PERPLEXITY, GOOGLE, ZAI, HETZNER

Dowod: [scripts/start-server.ps1](scripts/start-server.ps1), [.env](.env)

## Frontend (Next.js, port 3001)

```powershell
.\start_frontend.ps1
```

- `npm run dev` w `src/sylion-frontend`
- kanoniczny dev smoke uzywa `http://127.0.0.1:3001`; Next rewrites kieruja `/api/v1/*` do backendu `127.0.0.1:8010`
- Next 16.2.4, React 19.2.4

Dowod: [start_frontend.ps1](start_frontend.ps1), [src/sylion-frontend/package.json](src/sylion-frontend/package.json)

## Legacy dashboard standalone

`src/sylion-pipeline/dashboard/` zostal usuniety w R3.13. Nie uruchamiac `python dashboard/start.py`.

Dowod: `docs/aeis_repair_v2/evidence/R3_13_legacy_dashboard_removal/r3_13_cleanup_summary.json`

## Docker Compose

| Stack | Plik | Usługi |
|---|---|---|
| Dashboard | `src/sylion-pipeline/docker-compose.yml` | Dashboard + Caddy + Redis + Prometheus + Grafana + Alertmanager |
| Full API | `src/sylion-pipeline/docker-compose.full.yml` | API + PostgreSQL + NATS |
| PG-only | `src/sylion-pipeline/docker-compose.pg.yml` | API + PostgreSQL |
| Dev overlay | `src/sylion-pipeline/docker-compose.dev.yml` | MailHog + Adminer + Redis |

## Metryki API (stan po R3.14, 2026-05-13)

- `/health`: `status=ok`, `version=3.5.0`, `modules=138`, `endpoints=1953`
- OpenAPI zawiera funding export download: `/api/v1/funding/application/{application_id}/export/{artifact_type}`
- Funding UI `/funding` ma zakladke `Raporty` z wykresami i eksportami PDF/CSV/XLSX

Dowod: `docs/aeis_repair_v2/evidence/R3_14_funding_reporting_polish/runtime_api_reporting_smoke.json`

## Health check

```bash
curl http://127.0.0.1:8010/health
```

Zwraca: `status`, `version`, `modules`, `endpoints`, `db_mode`, `event_mode`.

Weryfikacja zestawu minimalnego: `.\scripts\verify.ps1` sprawdza `/health`, `/openapi.json`, `/docs`, `/api/v1/auth/status`, `/api/v1/auth/providers/list`.
