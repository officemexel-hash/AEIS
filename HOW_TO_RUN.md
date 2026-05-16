# HOW_TO_RUN

## Root Modular AEIS API

1. Install the root runtime with `.\scripts\install.ps1` on PowerShell, `scripts\install.bat` on CMD, or the matching shell script on Unix-like systems. Dowod: `scripts/install.ps1:41-130`.
2. The installer requires Python `3.11+`, creates `.venv` when needed, installs dependencies from the first existing file among `requirements.txt`, `requirements-lock.txt` and `requirements-pg.txt`, and creates `.env.generated` with `SYLION_JWT_SECRET`, `SYLION_INTERNAL_API_KEY` and `SYLION_VAULT_SECRET` when the file does not already exist. Dowod: `scripts/install.ps1:41-119`.
3. Start the root API with `.\scripts\start-server.ps1`. Dowod: `scripts/start-server.ps1:1-37`.
4. That command loads `.env.generated`, sets `SYLION_DB_PATH=sylion_aeis.db`, sets `SYLION_ENV=development`, sets `PYTHONPATH` to `src\sylion-pipeline`, and starts `uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010`. Dowod: `scripts/start-server.ps1:17-37`.
5. Verify the root API with `.\scripts\verify.ps1`. Dowod: `scripts/verify.ps1:1-66`.
6. For the AEIS dev backend, run verification against base URL `http://127.0.0.1:8010` unless `SYLION_BASE` overrides it. Dowod: `scripts/start-server.ps1:33-41`.

## Frontend Dev Server

1. Start the frontend dev server with `.\start_frontend.ps1`. Dowod: `start_frontend.ps1:1-2`.
2. That helper runs `npm run dev` inside `src/sylion-frontend`. Dowod: `start_frontend.ps1:1-2`.
3. The frontend scripts available in `package.json` are `dev`, `build`, `start` and `lint`. Dowod: `src/sylion-frontend/package.json:5-10`.
4. The frontend dev server keeps `NEXT_PUBLIC_API_URL` empty and uses same-origin `/api/v1/*` calls. Dowod: `src/sylion-frontend/.env.local:1`.
5. `next.config.ts` rewrites `/api/v1/*` and `/backend-health` to the AEIS backend on `127.0.0.1:8010`. Dowod: `src/sylion-frontend/next.config.ts`.

## Standalone Dashboard Runtime

1. Start the standalone dashboard runtime with `python dashboard/start.py`. Dowod: `src/sylion-pipeline/dashboard/start.py:3-9`, `src/sylion-pipeline/dashboard/start.py:309-317`.
2. The standalone dashboard default host is `127.0.0.1`. Dowod: `src/sylion-pipeline/dashboard/start.py:315-316`.
3. The standalone dashboard default port is `8421`, or `DASHBOARD_PORT` when that environment variable is set. Dowod: `src/sylion-pipeline/dashboard/start.py:311-316`.
4. The standalone dashboard can seed agents when run with `--seed`. Dowod: `src/sylion-pipeline/dashboard/start.py:313-314`, `src/sylion-pipeline/dashboard/start.py:374-400`.
5. The standalone dashboard runs `uvicorn` with `workers=1`, `proxy_headers=True`, `forwarded_allow_ips="127.0.0.1"` and `timeout_graceful_shutdown=3`. Dowod: `src/sylion-pipeline/dashboard/start.py:406-427`.

## Docker Compose Modes

### Dashboard Stack

- `src/sylion-pipeline/docker-compose.yml` publishes dashboard runtime on `127.0.0.1:8421:8421`. Dowod: `src/sylion-pipeline/docker-compose.yml:24-33`.
- The same file publishes Caddy on `80` and `443`, Redis internally, Alertmanager on `127.0.0.1:9093:9093`, Prometheus on `127.0.0.1:9090:9090`, and Grafana on `127.0.0.1:3000:3000`. Dowod: `src/sylion-pipeline/docker-compose.yml:59-66`, `src/sylion-pipeline/docker-compose.yml:106-117`, `src/sylion-pipeline/docker-compose.yml:124-141`, `src/sylion-pipeline/docker-compose.yml:149-155`.
- Dashboard container command exports `SYLION_INTERNAL_API_KEY` from a Docker secret and starts `python dashboard/start.py --host 0.0.0.0`. Dowod: `src/sylion-pipeline/docker-compose.yml:43-49`.

### Full API Stack

- `src/sylion-pipeline/docker-compose.full.yml` starts PostgreSQL, NATS and the AEIS API. Dowod: `src/sylion-pipeline/docker-compose.full.yml:7-73`.
- PostgreSQL is published on `5432`, NATS on `4222` and `8222`, and the API on `8000`. Dowod: `src/sylion-pipeline/docker-compose.full.yml:15-17`, `src/sylion-pipeline/docker-compose.full.yml:35-37`, `src/sylion-pipeline/docker-compose.full.yml:52-53`.
- The API container in this stack sets `SYLION_DB_MODE=postgres`, `SYLION_DB_URL=postgresql+asyncpg://sylion:sylion_dev@postgres:5432/sylion`, `SYLION_EVENT_MODE=nats` and `NATS_URL=nats://nats:4222`. Dowod: `src/sylion-pipeline/docker-compose.full.yml:56-62`.

### PostgreSQL-Only API Stack

- `src/sylion-pipeline/docker-compose.pg.yml` starts PostgreSQL and the AEIS API without NATS. Dowod: `src/sylion-pipeline/docker-compose.pg.yml:7-48`.
- PostgreSQL is published on `5432` and the API on `8000`. Dowod: `src/sylion-pipeline/docker-compose.pg.yml:15-17`, `src/sylion-pipeline/docker-compose.pg.yml:31-32`.
- The API container in this stack sets `SYLION_DB_MODE=postgres` and `SYLION_DB_URL=postgresql+asyncpg://sylion:sylion_dev@postgres:5432/sylion`. Dowod: `src/sylion-pipeline/docker-compose.pg.yml:35-39`.

### Optional Dev Overlay

- `src/sylion-pipeline/docker-compose.dev.yml` is explicitly marked as an optional local-development layer. Dowod: `src/sylion-pipeline/docker-compose.dev.yml:1-6`.
- The dev overlay expects local files under `./secrets/dev_*`. Dowod: `src/sylion-pipeline/docker-compose.dev.yml:8-23`.
- The dev overlay runs the dashboard container in development mode and starts `python dashboard/start.py --seed --host 0.0.0.0`. Dowod: `src/sylion-pipeline/docker-compose.dev.yml:25-49`.
- The dev overlay publishes Redis on `6379`, MailHog on `1025` and `8025`, and Adminer on `8080`. Dowod: `src/sylion-pipeline/docker-compose.dev.yml:58-75`.
