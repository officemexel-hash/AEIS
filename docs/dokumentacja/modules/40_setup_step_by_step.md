# 40 — Setup SYLION AEIS Advisor — krok po kroku
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> **Cel dokumentu**
> Niniejszy dokument prowadzi operatora przez kompletną instalację stacku
> SYLION AEIS Advisor — od pustej maszyny aż do działającego pełnego stacku
> (backend FastAPI + frontend Next.js + PostgreSQL + opcjonalnie Redis +
> Ollama). Każdy krok zawiera komendy gotowe do wklejenia oraz weryfikacje.
> Zakres: środowisko deweloperskie. Środowiska staging / produkcja są opisane
> osobno w `02_operational_manual.md` (sekcje "Deployment" i "Production
> hardening").

---

## Spis treści

1. [Wymagania systemowe](#1-wymagania-systemowe)
2. [Klonowanie repozytorium i struktura katalogów](#2-klonowanie-repozytorium-i-struktura-katalogow)
3. [Setup PostgreSQL](#3-setup-postgresql)
4. [Backend setup (sylion-pipeline)](#4-backend-setup-sylion-pipeline)
5. [Frontend setup (sylion-frontend)](#5-frontend-setup-sylion-frontend)
6. [Uruchomienie pełnego stacku](#6-uruchomienie-pelnego-stacku)
7. [Sanity checks](#7-sanity-checks)
8. [Pierwszy run jako operator — onboarding wizard](#8-pierwszy-run-jako-operator--onboarding-wizard)
9. [Troubleshooting](#9-troubleshooting)
10. [Cross-references](#10-cross-references)

---

## 1. Wymagania systemowe

### 1.1 Macierz oficjalnie wspieranych platform

| OS | Wersja | Status |
|---|---|---|
| Windows | 10 / 11 (Pro, Enterprise) | wspierany — referencyjny dla operator workstation |
| Linux | Ubuntu 22.04 LTS, Debian 12, Fedora 40 | wspierany — preferowany dla staging / produkcji |
| macOS | 13+ (Ventura), 14 (Sonoma), 15 (Sequoia) | wspierany — best effort, brak CI |
| WSL2 | Ubuntu 22.04 pod Windows 11 | wspierany jako alternatywa dla Linux na Windows |

### 1.2 Wersje runtime

| Runtime | Min | Zalecana | Max | Uwagi |
|---|---|---|---|---|
| Python | 3.11 | 3.12 | 3.13 | wymagane: 3.11+. SYLION dystrybuuje wheels dla 3.12 |
| Node.js | 20.10 | 20 LTS lub 22 LTS | 22 | testowane na 20 LTS i 22 LTS |
| npm | 10 | 10.5+ | — | dostarczany razem z Node.js |
| PostgreSQL | 14 | 16 | 17 | dla deweloperów wystarczy 14, dla prod 16+ |
| Redis | 7.0 | 7.2 | 7.x | opcjonalny — fallback in-memory cache |
| Docker | 24 | 26 | — | opcjonalny dla docker-compose |
| Git | 2.40 | 2.45+ | — | wymagany do klonu repo |

### 1.3 Zasoby sprzętowe

| Komponent | Minimum | Zalecane | Produkcyjne |
|---|---|---|---|
| RAM | 8 GB | 16 GB | 32 GB |
| CPU | 4 rdzenie | 8 rdzeni | 16+ rdzeni |
| Dysk SSD | 20 GB wolnego | 50 GB | 200 GB+ |
| GPU | nie wymagane | RTX 3060+ (Ollama) | RTX 4090 / A100 (lokalne LLM) |

> **Uwaga:** Ollama z modelami `qwen2.5:72b` wymaga ~48 GB VRAM lub równoważnej
> ilości RAM przy CPU offload. Dla deweloperów rekomendujemy `qwen2.5:7b`
> (~5 GB) lub całkowite wyłączenie lokalnych modeli (`SYLION_LLM_PROVIDER=stub`).

### 1.4 Wymagane konta i klucze API (opcjonalnie)

Dla pełnej funkcjonalności AEIS Advisor (LLM Judge, scoring funding, council)
operator może chcieć posiadać konta u dostawców modeli:

| Provider | Typ klucza | Wymagane do | Bez klucza działa? |
|---|---|---|---|
| Anthropic | `sk-ant-...` | Council Hybrid, AEIS Advisor LLM Judge | tak — fallback `qwen2.5` przez Ollama |
| OpenAI | `sk-...` | warianty rationale, fact-checking | tak |
| Google AI | `AIza...` | Funding Scorer (Gemini 2.5 Pro) | tak — stub scoring |
| xAI | `xai-...` | warianty Grok | tak |
| DeepSeek | `sk-...` | analiza kodu | tak |
| Perplexity | `pplx-...` | wyszukiwanie online | tak |

> System uruchomi się **bez żadnego klucza API** — wszystkie surfaces
> renderują się z mockami / lokalnym fallback (`SYLION_ADVISOR_LOCAL_ONLY=1`).
> Klucze są wymagane dopiero gdy operator wyraźnie aktywuje LLM-poweredne
> ścieżki w Settings.

### 1.5 Porty sieciowe

| Port | Usługa | Default bind | Można zmienić? |
|---|---|---|---|
| 8000 | Backend FastAPI (`sylion.api.app`) | 127.0.0.1 | tak (`--port`) |
| 3000 | Frontend Next.js (`next dev`) | 0.0.0.0 | tak (`PORT=…`) |
| 5432 | PostgreSQL | 127.0.0.1 | tak (`pg_hba.conf` + `postgresql.conf`) |
| 6379 | Redis (opcjonalnie) | 127.0.0.1 | tak |
| 11434 | Ollama (opcjonalnie) | 127.0.0.1 | tak (`OLLAMA_HOST`) |
| 8421 | Production unified server (Docker only) | 0.0.0.0 | tak (`SYLION_HTTP_PORT`) |
| 50051 | gRPC server (Docker only) | 0.0.0.0 | tak (`SYLION_GRPC_PORT`) |

---

## 2. Klonowanie repozytorium i struktura katalogów

### 2.1 Klonowanie

```bash
# HTTPS
git clone https://github.com/sylion/pipeline_glm.git
cd pipeline_glm
git checkout main

# SSH (jeśli masz klucz)
git clone git@github.com:sylion/pipeline_glm.git
cd pipeline_glm
git checkout main
```

> **Branch:** w czasie pisania tego dokumentu aktywnie rozwijany jest branch
> `advisor-etap1` zawierający funkcje Etap 1 AEIS Advisor. Operator powinien
> przełączyć się na branch zgodny ze stage'em deployu:
> `git checkout advisor-etap1` (Etap 1) lub `main` (stable).

### 2.2 Layout repozytorium (top-level)

```
pipeline_glm/
├── .claude/              # konfiguracja Claude Code (worktrees, settings)
├── docs/                 # dokumentacja (ten plik tu jest)
│   ├── claude_parallel/  # plany roboczych workpackages
│   ├── dokumentacja/     # finalna dokumentacja operacyjna
│   └── claude_system_audit/
├── scripts/              # installery, bootstrap, deploy
│   ├── install.ps1
│   ├── install.sh
│   ├── start-server.ps1
│   ├── start-server.bat
│   └── start-server.sh
├── src/
│   ├── sylion-pipeline/  # backend Python (FastAPI + AEIS)
│   │   ├── alembic/      # migracje Postgres
│   │   ├── sylion/       # główny pakiet
│   │   ├── tests/
│   │   ├── requirements.txt
│   │   ├── requirements-lock.txt
│   │   ├── pyproject.toml
│   │   ├── pytest.ini
│   │   ├── alembic.ini
│   │   ├── Dockerfile
│   │   └── docker-compose.yml
│   └── sylion-frontend/  # frontend TypeScript (Next.js 16)
│       ├── e2e/          # testy Playwright
│       ├── public/
│       ├── src/
│       │   ├── app/      # Next.js App Router
│       │   ├── components/
│       │   └── lib/
│       ├── package.json
│       ├── tsconfig.json
│       ├── next.config.ts
│       └── playwright.config.ts
├── .env.generated        # wygenerowany przez install.* (NIE commitować)
└── .env                  # operator-edytowalny (NIE commitować)
```

### 2.3 Konwencja katalogów backendu (`src/sylion-pipeline/sylion/`)

```
sylion/
├── api/              # FastAPI app + routes
├── aeis/
│   └── advisor/      # AEIS Advisor (pricing, engine, role_resolver, …)
├── cognitive/        # LLM adapters, planner, evaluator
├── governance/       # council_hybrid, decision_gates
├── contracts/
│   └── manifests/    # JSON manifesty wszystkich modułów
├── core/             # event_backbone, event_bus_factory
├── db/               # pool, migration, schema
├── infra/            # cache, topology
├── observability/    # tracing, metrics
├── security/         # rbac, key_vault, sops_provider
└── server.py         # unified server entry
```

---

## 3. Setup PostgreSQL

System może działać w dwóch trybach:

- **`sqlite`** (default w dev, `SYLION_DB_MODE=sqlite`) — pliki `*.db` w
  katalogu pracy. Zerowa konfiguracja, idealne dla pierwszego runu.
- **`postgres`** (`SYLION_DB_MODE=postgres` + `SYLION_DB_URL=…`) —
  rekomendowane dla pracy z AEIS Advisor (Etap 1+) i obowiązkowe dla stagingu
  / produkcji.

Sekcje 3.1-3.5 dotyczą trybu Postgres. Tryb SQLite wymaga jedynie wolnej
przestrzeni dyskowej.

### 3.1 Lokalna instalacja PostgreSQL na Windows 11

1. Pobierz instalator z https://www.postgresql.org/download/windows/ (EDB
   distribution).
2. Wybierz wersję `16.x` (zalecana).
3. Podczas instalacji zaznacz: `PostgreSQL Server`, `pgAdmin 4`, `Command
   Line Tools`. Pomiń `Stack Builder`.
4. Wybierz katalog danych (default `C:\Program Files\PostgreSQL\16\data`).
5. Ustaw hasło dla użytkownika `postgres` (zapamiętaj je!).
6. Port zostaw `5432`.
7. Locale: `C` lub `en_US.UTF-8`.
8. Po zakończeniu otwórz `psql` (Start → "SQL Shell (psql)") i potwierdź
   hasłem postgres → powinieneś zobaczyć prompt `postgres=#`.

### 3.2 Lokalna instalacja PostgreSQL na Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y postgresql-16 postgresql-contrib-16
sudo systemctl enable --now postgresql
sudo -u postgres psql -c "SELECT version();"
```

### 3.3 Lokalna instalacja PostgreSQL na macOS

```bash
# Homebrew
brew install postgresql@16
brew services start postgresql@16
psql -d postgres -c "SELECT version();"
```

### 3.4 Tworzenie bazy danych i użytkownika

Wszystkie polecenia uruchamiamy w `psql` jako superuser (Windows: SQL Shell;
Linux: `sudo -u postgres psql`).

```sql
-- 1. utwórz dedykowaną rolę i bazę
CREATE ROLE sylion WITH LOGIN PASSWORD 'sylion_dev';
CREATE DATABASE sylion OWNER sylion ENCODING 'UTF8';

-- 2. nadaj minimalne uprawnienia
GRANT ALL PRIVILEGES ON DATABASE sylion TO sylion;

-- 3. (opcjonalnie) włącz rozszerzenie pgcrypto, jeśli używasz UUID v7
\c sylion
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 4. weryfikacja
\du   -- powinieneś zobaczyć rolę sylion
\l    -- powinieneś zobaczyć bazę sylion (owner=sylion)
\q
```

### 3.5 Konfiguracja `pg_hba.conf` (jeśli wymagana)

Default na Windows / Linux pozwala na połączenia z localhost. Jeśli backend
zgłasza `password authentication failed`, edytuj `pg_hba.conf`:

```
# IPv4 local connections — wymaga hasła scram-sha-256
host    sylion          sylion          127.0.0.1/32            scram-sha-256
host    sylion          sylion          ::1/128                 scram-sha-256
```

Restart PostgreSQL po zmianie:

```bash
# Linux
sudo systemctl restart postgresql

# Windows (PowerShell jako Administrator)
Restart-Service postgresql-x64-16
```

### 3.6 Alternatywa: PostgreSQL w Dockerze

```bash
docker run -d \
  --name sylion-postgres \
  -e POSTGRES_USER=sylion \
  -e POSTGRES_PASSWORD=sylion_dev \
  -e POSTGRES_DB=sylion \
  -p 127.0.0.1:5432:5432 \
  -v sylion-pgdata:/var/lib/postgresql/data \
  postgres:16
```

Sanity check:

```bash
docker exec -it sylion-postgres psql -U sylion -d sylion -c "SELECT 1;"
```

---

## 4. Backend setup (sylion-pipeline)

### 4.1 Tworzenie wirtualnego środowiska Python

System dostarcza dwa idempotentne installery, które same tworzą `venv` w
`{repo}/.venv`:

#### Windows PowerShell

```powershell
cd C:\Users\<user>\Desktop\pipeline_glm
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

#### Windows CMD

```cmd
cd C:\Users\<user>\Desktop\pipeline_glm
scripts\install.bat
```

#### Linux / macOS

```bash
cd ~/pipeline_glm
bash scripts/install.sh
```

> Installer wykonuje 8 kroków: detekcja Pythona → walidacja wersji → B-002
> build guard (zero pre-seeded DB) → tworzenie `venv` → aktywacja → instalacja
> wymagań → generacja `.env.generated` z losowymi sekretami → finalna
> weryfikacja. Wszystkie kroki są idempotentne.

### 4.2 Manualne tworzenie venv (jeśli installer się nie powiedzie)

```bash
# Linux / macOS
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/sylion-pipeline/requirements.txt
```

```powershell
# Windows PowerShell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r src\sylion-pipeline\requirements.txt
```

### 4.3 Konfiguracja zmiennych środowiskowych (`.env`)

Backend ładuje zmienne w następującej kolejności (later wins):

1. `src/sylion-pipeline/.env.example` — szablon (NIE używany jako runtime
   źródło, tylko referencja).
2. `{repo}/.env.generated` — produkty installer'a (sekrety: JWT, internal
   API key).
3. `{repo}/.env` — **operator-edytowalny**, lokalna konfiguracja (klucze
   API, providers).
4. Zmienne ustawiane przez `start-server.ps1/bat/sh`.
5. `os.environ` z procesu rodzica.

Skopiuj szablon do edytowalnej kopii:

```bash
cp src/sylion-pipeline/.env.example .env
```

Edytuj minimum jedną sekcję (LLM provider — albo skonfiguruj klucz, albo
przełącz na stub):

```dotenv
# .env (root repozytorium)

# Wybierz jeden ze ścieżek:

# Ścieżka A: pełny LLM (wymaga klucza)
ANTHROPIC_API_KEY=sk-ant-...

# Ścieżka B: lokalny Ollama (zero kosztów, wymaga ollama serve)
SYLION_LLM_PROVIDER=ollama
SYLION_LLM_MODEL=qwen2.5:7b-instruct
OLLAMA_BASE_URL=http://localhost:11434

# Ścieżka C: stub (tylko UI, brak realnych odpowiedzi)
SYLION_LLM_PROVIDER=stub
SYLION_ADVISOR_LOCAL_ONLY=1
```

Pełna lista zmiennych — patrz `41_environment_variables.md`.

### 4.4 Migracje bazy danych

Backend używa Alembic dla schematu Postgres. Migracje są idempotentne i mogą
być uruchamiane wielokrotnie.

```bash
# Aktywuj venv
source .venv/bin/activate          # Linux / macOS
.\.venv\Scripts\Activate.ps1       # Windows PowerShell

# Wymaga: SYLION_DB_URL ustawione w .env
cd src/sylion-pipeline
alembic upgrade head
```

Sprawdź wersję:

```bash
alembic current
# → np. 20260420_advisor_etap1_b001 (head)
```

Tryb SQLite (default w dev) **nie wymaga** migracji Alembic — moduły same
tworzą `CREATE TABLE IF NOT EXISTS` przy pierwszym dotknięciu.

### 4.5 Pierwszy run backendu

```bash
# Z poziomu repo root, po install.*
.\scripts\start-server.ps1   # Windows PowerShell
scripts\start-server.bat     # Windows CMD
bash scripts/start-server.sh # Linux / macOS
```

Skrypt:

1. Weryfikuje, że `.venv` i `.env.generated` istnieją.
2. Ładuje zmienne z `.env.generated` (i `.env` jeśli skrypt rozszerzony).
3. Ustawia `PYTHONPATH=src/sylion-pipeline`.
4. Aktywuje `venv`.
5. Uruchamia uvicorn:
   ```
   python -m uvicorn sylion.api.app:app \
     --host 127.0.0.1 --port 8010 \
     --timeout-graceful-shutdown 10
   ```

Po starcie zobaczysz logi:

```
INFO: Started server process [PID]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8010
```

### 4.6 Manualne uruchomienie bez skryptu

```bash
source .venv/bin/activate
export PYTHONPATH=$PWD/src/sylion-pipeline
export SYLION_ENV=dev
export SYLION_AEIS_ENV=dev
export SYLION_RBAC_DISABLED=1     # tylko dev
export SYLION_AUTH_BYPASS=1       # tylko dev
export SYLION_DB_MODE=sqlite      # albo postgres
cd src/sylion-pipeline
python -m uvicorn sylion.api.app:app --host 127.0.0.1 --port 8010 --reload
```

### 4.7 Dostępne endpointy backendu (po starcie)

| Endpoint | Opis | Wymaga auth? |
|---|---|---|
| `GET /health` | liveness probe | nie |
| `GET /api/health/db` | sprawdzenie połączenia z DB | nie |
| `GET /docs` | Swagger UI | nie (dev) |
| `GET /openapi.json` | spec OpenAPI | nie |
| `POST /api/auth/login` | login + JWT | nie |
| `GET /api/advisor/cards` | lista kart Advisor | tak (lub bypass) |
| `GET /api/projects` | lista projektów | tak |
| `GET /api/observability/health-tree` | drzewo zdrowia | tak |

---

## 5. Frontend setup (sylion-frontend)

### 5.1 Wymagania frontendu

- Node.js 20.10+ (preferowana 20 LTS lub 22 LTS).
- npm 10+ (alternatywnie pnpm 9 lub yarn 4).
- Działający backend pod `http://127.0.0.1:8010` (lub inny — patrz
  `NEXT_PUBLIC_API_URL`).

### 5.2 Instalacja zależności

```bash
cd src/sylion-frontend
npm install
```

Pierwsza instalacja zajmie 2-5 minut (zależnie od dysku i sieci). Tworzony
jest katalog `node_modules/` (~600 MB).

### 5.3 Konfiguracja env frontendu

Frontend Next.js czyta zmienne z `.env.local` w katalogu projektu:

```bash
cd src/sylion-frontend
cp .env.local.example .env.local 2>/dev/null || true
```

Zawartość minimalna (`.env.local`):

```dotenv
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010
```

> **Tylko zmienne z prefixem `NEXT_PUBLIC_`** są dostępne w kodzie klienckim.
> Reszta (np. server-side secrets) jest dostępna tylko w `getServerSideProps`,
> Server Actions i Server Components.

### 5.4 Uruchomienie dev serwera

```bash
cd src/sylion-frontend
npm run dev
```

Wyjście:

```
> sylion-frontend@0.1.0 dev
> next dev

  ▲ Next.js 16.2.4
  - Local:   http://localhost:3000
  - Ready in 3.2s
```

Otwórz przeglądarkę: http://localhost:3000.

### 5.5 Skrypty package.json

| Skrypt | Co robi |
|---|---|
| `npm run dev` | dev serwer z Hot Module Reload (HMR) |
| `npm run build` | build produkcyjny do `.next/` |
| `npm run start` | uruchamia zbudowany bundle (po `build`) |
| `npm run lint` | ESLint walidacja |
| `npx playwright test` | uruchamia testy E2E |

### 5.6 Struktura `src/sylion-frontend/src`

```
src/
├── app/
│   ├── (app)/                # protected routes (sidebar layout)
│   │   ├── advisor/          # AEIS Advisor surfaces
│   │   ├── agents/
│   │   ├── projects/
│   │   ├── council/
│   │   ├── budget/
│   │   ├── audit/
│   │   ├── decisions/
│   │   ├── idea-vault/
│   │   ├── governance/
│   │   ├── observability/
│   │   ├── operator-mobile/
│   │   ├── onboarding/
│   │   └── auth/
│   ├── layout.tsx            # root layout
│   └── page.tsx              # landing
├── components/
│   ├── advisor/
│   ├── council/
│   ├── onboarding/
│   ├── ui/                   # design system (shadcn-style)
│   └── …
└── lib/
    ├── api/                  # client (fetch wrappers + hooks)
    ├── hooks/                # React hooks
    └── utils.ts
```

---

## 6. Uruchomienie pełnego stacku

### 6.1 Wariant A: dwa terminale (najprostszy)

```bash
# Terminal 1 — backend
cd C:\Users\<user>\Desktop\pipeline_glm
.\scripts\start-server.ps1

# Terminal 2 — frontend
cd C:\Users\<user>\Desktop\pipeline_glm\src\sylion-frontend
npm run dev
```

Po uruchomieniu obu serwisów, otwórz http://localhost:3000.

### 6.2 Wariant B: Docker compose (pełna izolacja)

```bash
cd src/sylion-pipeline
docker compose up -d sylion-dashboard caddy redis
docker compose ps
```

Compose uruchomi:

- `sylion-dashboard` (FastAPI + gRPC) na 127.0.0.1:8421
- `caddy` (TLS reverse proxy) na :80, :443, :443/udp
- `redis` (rate limiter + cache)

Z profilem `monitoring` dodatkowo: Prometheus, Grafana, Loki, Promtail,
Alertmanager, Tempo.

```bash
docker compose --profile monitoring up -d
```

### 6.3 Wariant C: WSL2 (Windows Subsystem for Linux)

Identycznie jak Linux, ale z dwoma uwagami:

- PostgreSQL musi być zainstalowany **wewnątrz** WSL2 (nie używaj Windows
  Postgres — wymaga skomplikowanej konfiguracji portów).
- Frontend Next.js domyślnie nasłuchuje `0.0.0.0:3000` w WSL2 — dostępny z
  Windows pod http://localhost:3000.

### 6.4 start-server.ps1 — co robi krok po kroku

Linijka po linijce, dla operatora chcącego zrozumieć / dostosować:

| Linia | Akcja | Przyczyna |
|---|---|---|
| `$ErrorActionPreference = "Stop"` | przerywa skrypt na pierwszym błędzie | bezpieczeństwo |
| `$InstallDir = (Get-Location).Path` | używa CWD jako root | uruchamiać z root repo |
| `$SrcDir = Join-Path $InstallDir "src\sylion-pipeline"` | path do backendu | |
| `$VenvDir = Join-Path $InstallDir ".venv"` | path do venv | |
| `$EnvFile = Join-Path $InstallDir ".env.generated"` | sekrety z installera | |
| guard `Test-Path $VenvDir` | weryfikuje venv | jeśli brak → uruchom install.ps1 |
| guard `Test-Path $EnvFile` | weryfikuje sekrety | jeśli brak → uruchom install.ps1 |
| pętla `Get-Content $EnvFile` | parsuje KEY=VALUE | ładuje sekrety do procesu |
| `$env:SYLION_USE_LEGACY_DB_PATH = "0"` | wymusza nową ścieżkę | |
| `$env:SESSION_COOKIE_SECURE = "0"` | dev-only (HTTP) | prod ustawia "1" |
| `$env:SYLION_ENV = "dev"` | tryb env | |
| `$env:SYLION_AEIS_ENV = "dev"` | tryb AEIS env | |
| `$env:SYLION_RBAC_DISABLED = "1"` | wyłącza RBAC | tylko dev! |
| `$env:SYLION_RATE_LIMIT_DISABLED = "1"` | wyłącza rate limiter | tylko dev! |
| `$env:SYLION_AUTH_BYPASS = "1"` | wyłącza auth | tylko dev! |
| `$env:PYTHONPATH = $SrcDir` | path do pakietu sylion | |
| `$env:LITELLM_LOCAL_MODEL_COST_MAP = "True"` | mapa kosztów lokalnych | unikamy odwołań do API litellm |
| `$env:LITELLM_DO_NOT_TRACK = "True"` | wyłącza telemetrię litellm | privacy |
| `& Activate.ps1` | aktywuje venv | |
| `Set-Location $SrcDir` | wchodzi do backendu | |
| `python -m uvicorn …` | startuje serwer | uvicorn z graceful shutdown 10s |

### 6.5 start-server.bat — różnice względem PS1

`.bat` używa CMD `for /f` do parsowania `.env.generated`, reszta logiki
identyczna. Preferowany dla operatorów bez PowerShell ExecutionPolicy
override.

---

## 7. Sanity checks

### 7.1 Backend health

```bash
curl -s http://127.0.0.1:8010/health
# → {"status":"ok","ts":"2026-04-26T…"}

curl -s http://127.0.0.1:8010/api/health/db
# → {"db_mode":"sqlite","db_url":"…","alive":true}
```

### 7.2 Frontend

Otwórz http://localhost:3000 — powinieneś zobaczyć landing / sidebar SYLION.
Brak komunikatów `Failed to fetch` w konsoli przeglądarki = OK.

### 7.3 OpenAPI spec

```bash
curl -s http://127.0.0.1:8010/openapi.json | head -100
# → {"openapi":"3.1.0","info":{"title":"sylion.api","version":"…"},…}
```

Lub w przeglądarce: http://127.0.0.1:8010/docs.

### 7.4 Smoke test logowania (z bypass off)

```bash
curl -X POST http://127.0.0.1:8010/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"operator@example.com","password":"<haslo>"}'
# → {"access_token":"eyJ…","token_type":"bearer"}
```

W trybie `SYLION_AUTH_BYPASS=1` każdy request jest autoryzowany jako
`operator@dev.local`.

### 7.5 Pierwszy widok AEIS Advisor

W przeglądarce:

1. http://localhost:3000 — landing.
2. Kliknij sidebar "Advisor" (lub bezpośrednio
   http://localhost:3000/advisor).
3. Powinieneś zobaczyć Advisor Bubble (jeśli włączony) lub Advisor List.

Jeśli widzisz `EmptyState` z komunikatem "Brak rekomendacji" — system działa,
ale jeszcze nie wyemitował żadnej karty (normalne na czystej instalacji).

### 7.6 Smoke test event bus

```bash
curl -s http://127.0.0.1:8010/api/observability/health-tree | jq .
```

Pole `eventBus.alive` powinno być `true`.

---

## 8. Pierwszy run jako operator — onboarding wizard

### 8.1 Otwarcie wizard'a

Pierwsze logowanie (lub `SYLION_AUTH_BYPASS=1`) prowadzi operatora do strony
`/onboarding` z banerem `IncompleteBanner` i 10-krokowym wizardem.

### 8.2 10 kroków onboardingu

| # | Krok | Cel | Wymagane do dalszego ruchu? |
|---|---|---|---|
| 1 | **Powitanie** | wprowadzenie do AEIS, akceptacja Terms | tak |
| 2 | **Dane operatora** | imię, organizacja, rola | tak |
| 3 | **API providers** | dodanie kluczy LLM (Anthropic / OpenAI / …) | nie — można pominąć |
| 4 | **Wybór modeli** | dla `planner`, `worker`, `critic`, `governance` | nie |
| 5 | **Budżet miesięczny** | limit USD, próg ostrzeżenia | nie |
| 6 | **Autonomia** | poziom autonomii (D-ladder D0-D5) | tak |
| 7 | **Skills** | wybór skill packów (jeśli dostępne) | nie |
| 8 | **Topologia** | single-host vs multi-host | nie |
| 9 | **Polityka prywatności** | learn / don't-learn flag | tak |
| 10 | **Podsumowanie** | przegląd, akceptacja, finalizacja | tak |

### 8.3 Po finalizacji

Operator dostaje:

- Token JWT (cookie `sylion_session`).
- Domyślny projekt `default-project`.
- Pusty IdeaVault.
- Kalibrację Advisor'a (rekomendacje pojawiają się w bańce).

### 8.4 Re-run wizard'a

Można uruchomić ponownie:

- Profil → Settings → "Powtórz onboarding".
- Albo manualnie: usuń wpis `onboarding_completed` w tabeli
  `system_settings` (Postgres) / `system_settings.json` (SQLite).

---

## 9. Troubleshooting

### 9.1 Backend

#### Problem: `psycopg2 / asyncpg connection refused`

```
sqlalchemy.exc.OperationalError: connection to server at "localhost" (::1),
port 5432 failed: Connection refused
```

**Diagnoza:**

```bash
# Linux
sudo systemctl status postgresql
sudo ss -tlnp | grep 5432

# Windows
Get-Service postgresql-x64-16
netstat -ano | findstr :5432
```

**Fix:**

- Linux: `sudo systemctl start postgresql`
- Windows: `Start-Service postgresql-x64-16`
- Docker: `docker start sylion-postgres`
- Sprawdź `SYLION_DB_URL` w `.env` — host i port się zgadzają?

---

#### Problem: `password authentication failed for user "sylion"`

**Diagnoza:** `pg_hba.conf` wymaga innej metody niż twoja, lub hasło nie pasuje.

**Fix:**

```sql
-- jako superuser postgres:
ALTER ROLE sylion WITH PASSWORD 'sylion_dev';
```

I sprawdź `pg_hba.conf` — linia musi być `scram-sha-256`, nie `peer`.

---

#### Problem: `Address already in use: 8000`

```
ERROR: [Errno 98] Address already in use
```

**Fix:**

```bash
# Linux / macOS
lsof -i :8000
kill -9 <PID>

# Windows PowerShell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
Stop-Process -Id <PID>
```

Lub uruchom backend na innym porcie:

```bash
python -m uvicorn sylion.api.app:app --port 8001
```

---

#### Problem: `ModuleNotFoundError: No module named 'sylion'`

**Diagnoza:** `PYTHONPATH` nie wskazuje na katalog z pakietem.

**Fix:**

```bash
# Linux / macOS
export PYTHONPATH=$PWD/src/sylion-pipeline
```

```powershell
# Windows PowerShell
$env:PYTHONPATH = "$PWD\src\sylion-pipeline"
```

Lub użyj `start-server.ps1` / `.bat` / `.sh` — robią to automatycznie.

---

#### Problem: `alembic.util.exc.CommandError: Can't locate revision identified by 'head'`

**Diagnoza:** brak migracji w `alembic/versions/`, albo zła ścieżka.

**Fix:**

```bash
cd src/sylion-pipeline
ls alembic/versions/        # powinny być pliki *.py

# Reset (DEV ONLY — usuwa dane!):
alembic downgrade base
alembic upgrade head
```

---

#### Problem: `litellm.exceptions.BadRequestError: model_not_found`

**Diagnoza:** `SYLION_LLM_MODEL` jest ustawiony na model, którego provider
nie obsługuje (np. `gpt-5` w Ollama).

**Fix:** wyrównaj `SYLION_LLM_PROVIDER` i `SYLION_LLM_MODEL`. Patrz
`role_routing_defaults.yaml` po listę kanonicznych mappingów.

---

#### Problem: `AnthropicError: 401 Unauthorized`

**Diagnoza:** `ANTHROPIC_API_KEY` nieprawidłowy lub wygasł.

**Fix:** wygeneruj nowy w https://console.anthropic.com → Settings → API
Keys i wklej do `.env`. Restart backendu.

---

### 9.2 Frontend

#### Problem: `npm install` fails on Windows z `node-gyp`

**Diagnoza:** brak Visual Studio Build Tools.

**Fix:**

```powershell
# instaluj jako Administrator
npm install --global --production windows-build-tools
```

Lub użyj WSL2.

---

#### Problem: `EACCES: permission denied, mkdir '/usr/lib/node_modules'`

**Diagnoza:** próba globalnej instalacji bez uprawnień (Linux/macOS).

**Fix:** **NIE używaj sudo!** Zamiast tego skonfiguruj `nvm`:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
nvm install 20
nvm use 20
```

---

#### Problem: `Module not found: Can't resolve '@/lib/api/client'`

**Diagnoza:** `tsconfig.json` `paths` nie zostały załadowane.

**Fix:**

```bash
rm -rf .next
npm run dev
```

Jeśli problem persystuje, sprawdź `tsconfig.json` `compilerOptions.paths`:

```json
"paths": { "@/*": ["./src/*"] }
```

---

#### Problem: `Hydration error: Text content does not match`

**Diagnoza:** server-rendered HTML różni się od klienckiego (np. `Date.now()`
w komponencie).

**Fix:** wynieś niedeterministyczny kod do `useEffect` lub dodaj
`suppressHydrationWarning`.

---

#### Problem: `Failed to fetch` w konsoli przeglądarki

**Diagnoza:** backend nie działa, albo CORS, albo zły `NEXT_PUBLIC_API_URL`.

**Fix:**

1. Sprawdź `curl http://127.0.0.1:8010/health` (z hosta).
2. Sprawdź `.env.local` w `src/sylion-frontend/`.
3. Restart `npm run dev` po zmianie env.

---

#### Problem: `next dev` startuje, ale strona biała

**Diagnoza:** błąd w komponencie React; sprawdź konsolę przeglądarki i
terminal.

**Fix:** najczęściej stale build cache:

```bash
rm -rf .next node_modules/.cache
npm run dev
```

---

### 9.3 Stack-wide

#### Problem: Onboarding wizard nie kończy się

**Diagnoza:** brak handler'a dla finalizacji w backendzie, lub brak DB
write.

**Fix:**

```bash
# sprawdź logi backendu
tail -f src/logs/sylion.log | grep onboarding
```

Sprawdź endpoint `POST /api/onboarding/complete` w sieci (DevTools → Network).

---

#### Problem: AEIS Advisor nie emituje kart

**Diagnoza:** brak event'ów wejściowych (np. `aeis.idea.intake.completed`).

**Fix:** wyzwól event ręcznie (wymaga RBAC bypass lub admin):

```bash
curl -X POST http://127.0.0.1:8010/api/events/test-emit \
  -H "Content-Type: application/json" \
  -d '{"event_type":"aeis.idea.intake.completed","payload":{"idea_id":"test-1"}}'
```

I obserwuj `/api/advisor/cards`.

---

#### Problem: Przeglądarka zwraca 504 Gateway Timeout (Caddy)

**Diagnoza:** `sylion-dashboard` nie działa (docker mode).

**Fix:**

```bash
docker compose ps
docker compose logs sylion-dashboard --tail 100
docker compose restart sylion-dashboard
```

---

#### Problem: Wysokie zużycie RAM (>8 GB)

**Diagnoza:** Ollama załadowała duży model (np. `qwen2.5:72b`).

**Fix:** przełącz na mniejszy model lub wyłącz Ollama:

```dotenv
SYLION_LLM_MODEL=qwen2.5:7b-instruct
```

Lub:

```bash
ollama stop qwen2.5:72b-instruct
```

---

#### Problem: Brak ikon / styl Tailwind nie działa

**Diagnoza:** `tailwind` v4 wymaga PostCSS plugin.

**Fix:**

```bash
cd src/sylion-frontend
rm -rf .next
npm run dev
```

Sprawdź `postcss.config.mjs` zawiera `@tailwindcss/postcss`.

---

#### Problem: Playwright testy timeout'ują na CI

**Diagnoza:** webServer w `playwright.config.ts` ma `reuseExistingServer:
true`, ale serwer nie startuje w CI.

**Fix:** w CI ustaw:

```bash
npx playwright test --reporter=list --workers=1
```

I uruchom `npm run build && npm run start` przed testami.

---

#### Problem: `Permission denied` na `.venv/Scripts/activate.ps1`

**Diagnoza:** PowerShell ExecutionPolicy `Restricted`.

**Fix:**

```powershell
# Per-user, jednorazowo:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Per-skrypt:
powershell -ExecutionPolicy Bypass -File .\scripts\start-server.ps1
```

---

#### Problem: `git checkout main` ostrzega o niewykonalnych zmianach

**Diagnoza:** masz lokalne edycje, które wchodzą w konflikt.

**Fix:**

```bash
git status                      # zobacz co się zmieniło
git stash push -m "wip"         # zachowaj zmiany
git checkout main
git stash pop                   # przywróć
```

---

## 10. Testy E2E — Playwright (sprint3)

Sprint3 dodał 5 testów Playwright weryfikujących kluczowe przepływy interfejsu. Pliki: `src/sylion-frontend/e2e/sprint2_*.spec.ts`.

### 10.1. Wymagania

```bash
cd src/sylion-frontend
npx playwright install --with-deps   # jednorazowo; instaluje Chromium
```

Zmienna `NEXT_PUBLIC_API_URL` musi wskazywać na działający backend (lokalnie `http://127.0.0.1:8010`).

### 10.2. Uruchomienie testów

```bash
cd src/sylion-frontend
# wszystkie testy e2e (headless)
npx playwright test e2e/

# konkretny plik
npx playwright test e2e/sprint2_cockpit_v4.spec.ts

# tryb interaktywny (headed)
npx playwright test e2e/ --headed
```

### 10.3. Pokryte przepływy

| Plik | Scope | Kluczowe asercje |
|------|-------|-----------------|
| `sprint2_cockpit_v4.spec.ts` | Cockpit v4 (hero, orb, metryki, lifecycle) | `.core-orb` visible; 4 `.metric-tile`; lifecycle rail >= 15 faz; `.config-grid` z 4 kartami |
| `sprint2_faq.spec.ts` | System FAQ (lista, filtrowanie, accordion) | 15 wpisow; filtr "human gate" → 1-10 wynikow; akordeon expand/collapse |
| `sprint2_mode_switch.spec.ts` | Przełaczanie trybu offline/online | `ApiOfflineBanner` visible w trybie offline; toggle mode button |
| `sprint2_offline_guard.spec.ts` | `OfflineGuard` komponent | Banner pojawia sie gdy `NEXT_PUBLIC_API_URL` niedostepny |
| `sprint2_wizard.spec.ts` | Onboarding Wizard (kroki 1-3) | Nawigacja 3-krokowa; `Step2Providers` lista; walidacja krok 1 |

### 10.4. Konfiguracja `playwright.config.ts`

Domyslny baseURL: `http://localhost:3000`. Zmien przez `BASE_URL` env jesli frontend działa na innym porcie. Timeout per test: 20 s (ustawiony przez `waitUntil: "networkidle"`).

### 10.5. Integracja CI

```yaml
# przyklad GitHub Actions
- name: Run e2e tests
  run: |
    cd src/sylion-frontend
    npx playwright test e2e/
  env:
    NEXT_PUBLIC_API_URL: http://127.0.0.1:8010
```

---

## 11. Cross-references

| Plik | Zakres |
|---|---|
| `41_environment_variables.md` | pełna lista env vars (Python + Next.js) |
| `42_configuration_files.md` | manifesty, YAML, docker-compose, package.json |
| `02_operational_manual.md` | uruchomienia produkcyjne, deploy, monitoring |
| `04_dla_developera.md` | rozwijanie modulow, conventions, testowanie |
| `00_architektura_systemu.md` | wysoki poziom — 12 warstw, AEIS, Council |
| `01_modul_aeis_advisor.md` | szczegoly AEIS Advisor (Etap 1) |
| `03_governance_audit_compliance.md` | RBAC, audit log, compliance |
| `05_PEŁNY_OPIS_SYSTEMU_decyzje_2026_04_25.md` | decyzje architektoniczne |

---

> **Następne kroki po setupie**
>
> 1. Przeczytaj `01_modul_aeis_advisor.md` aby zrozumieć przepływy decyzji.
> 2. Wygeneruj evidence pack dla pierwszej decyzji D3+ (patrz
>    `03_governance_audit_compliance.md`).
> 3. Skonfiguruj backupy bazy (Postgres `pg_dump` daily — patrz
>    `02_operational_manual.md`).
> 4. Skonfiguruj monitoring (Prometheus + Grafana — `docker compose
>    --profile monitoring`).
