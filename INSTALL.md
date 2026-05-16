# Instalacja — SYLION Pipeline v6.2.0

## Pre-requisites

- Python 3.11 albo 3.12
- `pip` + `venv`
- Wolny port `8422`
- 2 GB RAM, 1 GB wolnego dysku

Opcjonalnie:
- Docker + obraz `ollama/ollama` lub lokalny `ollama` CLI
- PostgreSQL (jeśli używasz dashboard-level multi-tenant — standardowo SQLite wystarczy)

## Kroki

### 1. Rozpakuj i wejdź do katalogu

```bash
unzip sylion-pipeline-6.2.0-*.zip -d sylion-6.2.0
cd sylion-6.2.0
```

### 2. Uruchom installer

```bash
./scripts/install.sh
```

Installer:
1. Sprawdza Python ≥3.11
2. Tworzy `.venv/`
3. Instaluje zależności z `src/sylion-pipeline/requirements.txt` (jeśli istnieje)
4. Generuje `.env.generated` z nowym JWT secret (B-001)
5. Tworzy świeżą bazę w `src/sylion-pipeline/dashboard/sylion_dashboard.db` (brak pre-seeded *.db w paczce — B-002)
6. Uruchamia smoke test na `127.0.0.1:8422`

### 3. Start serwera (dev, lokalnie)

```bash
cd src/sylion-pipeline/dashboard
source ../../../.venv/bin/activate
export SYLION_JWT_SECRET=$(cat ../../../.env.generated | grep SYLION_JWT_SECRET | cut -d= -f2-)
export DASHBOARD_DB_PATH=sylion_dashboard.db
export SYLION_ENV=dev SESSION_COOKIE_SECURE=0
python3 -m uvicorn app:app --host 127.0.0.1 --port 8422 --timeout-graceful-shutdown 10
```

Serwer odpowiada na:
- `http://127.0.0.1:8422/api/health` → `{"status":"ok","version":"6.2.0",...}`
- `http://127.0.0.1:8422/api/version`

### 4. Weryfikacja

```bash
./scripts/verify.sh
```

Skrypt curluje `/api/health`, `/api/version`, `/api/auth/setup-status`, sprawdza czy version=6.2.0.

## Upgrade z v6.0.0 (in-place)

1. Zatrzymaj poprzednią instancję (`systemctl stop sylion` lub kill PID).
2. Backup bazy: `cp dashboard/sylion_dashboard.db dashboard/sylion_dashboard.db.bak-v600`.
3. Rozpakuj nową paczkę nad starą (overwrite kodu, nie bazy).
4. Uruchom serwer — `init_db` migruje idempotentnie.
5. Weryfikacja: `curl http://127.0.0.1:8422/api/version` → `6.2.0`.

**Ważne**: jeżeli miałeś zmienną `SYLION_VERSION` w env — teraz odłącz (`unset SYLION_VERSION`). Priorytet: env > `VERSION` file > `MANIFEST.json`.

## Konfiguracja (env)

| Zmienna | Default | Opis |
|---------|---------|------|
| `SYLION_JWT_SECRET` | auto-gen | Sekret JWT. Bez wartości → generowany do `.env.generated` (B-001). |
| `DASHBOARD_DB_PATH` | `sylion_dashboard.db` | Ścieżka DB SQLite (B-006). |
| `SYLION_USE_LEGACY_DB_PATH` | `0` | `1` = stare zachowanie pre-B-006. |
| `SYLION_OLLAMA_DNS_FALLBACK` | `1` | `0` wyłącza fallback `ollama→localhost` (CONN-001). |
| `SYLION_METRICS_BEARER` | (none) | Token dla remote `/api/metrics` (B-008). |
| `SYLION_METRICS_OPEN` | `0` | `1` = dev escape, otwiera `/api/metrics` publicznie. |
| `SYLION_BOOKGUARDIAN_NO_MEMOIZE` | `0` | `1` wyłącza memoize BookGuardian (PIPELINE-011). |
| `LITELLM_DO_NOT_TRACK` | `True` | B-009 — wyłącza telemetrię litellm. |

## Troubleshooting

- **`ModuleNotFoundError: openhands`** — `PYTHONPATH` musi zawierać `src/sylion-pipeline` (dodawane przez installer).
- **`/api/version` zwraca stary string** — `unset SYLION_VERSION` albo zmień na `6.2.0`.
- **Ollama nie łączy się** — sprawdź `/etc/hosts` lub ustaw `SYLION_OLLAMA_DNS_FALLBACK=1`.
- **Metrics 403 z remote IP** — ustaw `SYLION_METRICS_BEARER=...` i wywołaj z nagłówkiem `Authorization: Bearer ...` albo zaloguj się jako `owner`/`operator`.

## Linki

- [README.md](./README.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [ROLLBACK.md](./ROLLBACK.md)
- [ULTRA_TEST_REPORT_v2.md](./ULTRA_TEST_REPORT_v2.md)
