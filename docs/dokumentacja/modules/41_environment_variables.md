# 41 — Environment Variables — kompletna lista
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> **Cel dokumentu**
> Niniejszy dokument zawiera wyczerpującą referencję wszystkich zmiennych
> środowiskowych konsumowanych przez stack SYLION AEIS Advisor — backend
> Python (FastAPI + AEIS), frontend Next.js, pipeline LLM (litellm + Ollama),
> warstwa security i monitoring.
>
> Każda zmienna ma określone: nazwę, typ, czy jest wymagana, wartość
> domyślną, znaczenie biznesowe, miejsce użycia w kodzie i implikacje
> security. Sekcja 7 zawiera gotowy szablon `.env.example` do wklejenia.

---

## Spis treści

1. [Konwencje nazewnicze](#1-konwencje-nazewnicze)
2. [Backend env vars (Python)](#2-backend-env-vars-python)
   1. [Database](#21-database)
   2. [LLM providers](#22-llm-providers)
   3. [Auth i sekrety](#23-auth-i-sekrety)
   4. [Logging](#24-logging)
   5. [Feature flags](#25-feature-flags)
   6. [AEIS Advisor — specyfika](#26-aeis-advisor--specyfika)
   7. [Mobile gateway](#27-mobile-gateway)
   8. [Funding (opt-in)](#28-funding-opt-in)
   9. [Event bus i NATS](#29-event-bus-i-nats)
   10. [Cache i Redis](#210-cache-i-redis)
   11. [Observability i tracing](#211-observability-i-tracing)
   12. [Streaming i ABR](#212-streaming-i-abr)
   13. [Cellular / SDR](#213-cellular--sdr)
   14. [Build verification](#214-build-verification)
   15. [Anti-hallucination i fact-check](#215-anti-hallucination-i-fact-check)
   16. [Device harness](#216-device-harness)
3. [Frontend env vars (Next.js)](#3-frontend-env-vars-nextjs)
4. [Docker compose env vars](#4-docker-compose-env-vars)
5. [CI/CD env vars](#5-cicd-env-vars)
6. [Bezpieczeństwo env vars](#6-bezpieczenstwo-env-vars)
7. [.env.example template](#7-envexample-template)
8. [Cross-references](#8-cross-references)

---

## 1. Konwencje nazewnicze

### 1.1 Prefixy

| Prefix | Zakres | Przykład |
|---|---|---|
| `SYLION_` | core'owe ustawienia systemu | `SYLION_ENV`, `SYLION_HOME` |
| `SYLION_AEIS_` | warstwa AEIS | `SYLION_AEIS_ENV` |
| `SYLION_ADVISOR_` | konkretne pod-moduły AEIS Advisor | `SYLION_ADVISOR_LOCAL_ONLY` |
| `SYLION_DB_` | warstwa bazodanowa | `SYLION_DB_MODE`, `SYLION_DB_URL` |
| `SYLION_LLM_` | wybór modelu / providera | `SYLION_LLM_PROVIDER`, `SYLION_LLM_MODEL` |
| `SYLION_FUNDING_` | Funding Autopilot | `SYLION_FUNDING_RESULTS_ROOT` |
| `SYLION_TRACING_` | OpenTelemetry | `SYLION_TRACING_ENABLED` |
| `SYLION_RBAC_` | feature flags RBAC | `SYLION_RBAC_DISABLED` |
| `SYLION_AUTH_` | feature flags auth | `SYLION_AUTH_BYPASS` |
| `SYLION_RATE_LIMIT_` | rate limiter | `SYLION_RATE_LIMIT_DISABLED` |
| `SYLION_MOBILE_` | mobile gateway | `SYLION_MOBILE_SIGNING_SECRET` |
| `DASHBOARD_` | dashboard / SQLite legacy | `DASHBOARD_PORT`, `DASHBOARD_HOST` |
| `STREAM_` | warstwa streamingu | `STREAM_LATENCY_P95_MS` |
| `BENCH_` | benchmark thresholds | `BENCH_SETUP_P95_MS` |
| `SIGNALING_` | WebRTC signaling | `SIGNALING_MAX_ROOMS` |
| `AUDIO_` | audio pipeline | `AUDIO_OPUS_BITRATE_BPS` |
| `ABR_` | adaptive bitrate | `ABR_INITIAL_RUNG` |
| `INPUT_` | input protocol | `INPUT_PROTOCOL_HMAC_KEY` |
| `METRICS_` | metryki | `METRICS_MAX_SAMPLES` |
| `DEVICE_` | device harness | `DEVICE_PIXEL_SERIAL` |
| `BUILD_` | build verification | `BUILD_VERIFICATION_ENABLED` |
| `CLAIM_` | provenance claiming | `CLAIM_PROVENANCE_ENABLED` |
| `PROVENANCE_` | provenance config | `PROVENANCE_CONTEXT_WINDOW` |
| `DEDUP_` | semantic dedup | `DEDUP_SIMILARITY_THRESHOLD` |
| `BENCHMARK_` | benchmark harness | `BENCHMARK_ENABLED` |
| `FACT_CHECKER_` | anti-hallucination | `FACT_CHECKER_MODEL_ID` |
| `OLLAMA_` | lokalny Ollama | `OLLAMA_API_BASE`, `OLLAMA_BASE_URL` |
| `LITELLM_` | litellm config | `LITELLM_LOCAL_MODEL_COST_MAP` |
| `NATS_` | NATS JetStream | `NATS_URL`, `NATS_STREAM` |
| `REDIS_` | Redis backend | `REDIS_URL` |
| `NEXT_PUBLIC_` | client-side Next.js | `NEXT_PUBLIC_API_URL` |
| (bez prefixu) | klucze API providerów | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` |

### 1.2 Konwencje wartości

| Konwencja | Wartości | Notes |
|---|---|---|
| boolean | `1`/`0`, `true`/`false`, `yes`/`no`, `on`/`off` | parser akceptuje wszystkie; pusta = `false` |
| listy | comma-separated | `STREAM_SECURITY_PINNED_CERTS=fp1,fp2,fp3` |
| URLs | pełna forma z protokołem | `postgresql://…`, `http://…`, `nats://…` |
| sekrety | base64 / hex / raw token | nigdy nie loguj |
| ścieżki | absolutne lub relatywne do CWD | preferuj absolutne w prod |

### 1.3 Source of truth — gdzie zmienne są definiowane

| Lokacja | Zakres | Kiedy ładowane |
|---|---|---|
| `src/sylion-pipeline/.env.example` | szablon (referencja) | nigdy — tylko dla dokumentacji |
| `.env.generated` | sekrety z installera | start-server.* |
| `.env` | operator-edytowalny | start-server.* (opcjonalnie) |
| `os.environ` | proces rodzic | startup app.py |
| `docker-compose.yml` | service-level env | docker compose up |
| `Dockerfile` | image-level ENV | build time |

### 1.4 Precedence

```
Process env > .env > .env.generated > Dockerfile ENV > .env.example
```

W kodzie zwykle:

```python
value = os.environ.get("KEY", "default")
```

co oznacza: jeśli zmienna nie jest ustawiona, zwracany jest `default`.

---

## 2. Backend env vars (Python)

Wszystkie zmienne są ładowane przez `os.environ.get(...)` lub
`os.getenv(...)` w pakiecie `sylion`. Sekcje 2.1-2.16 grupują je tematycznie.

### 2.1 Database

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_DB_MODE` | nie | `sqlite` | enum: `sqlite`/`postgres` | wybór backendu DB | `sylion.db.__init__`, `sylion.api.app` |
| `SYLION_DB_URL` | warunkowo | — | URL | DSN dla Postgres (`postgresql://user:pass@host:port/db` lub `postgresql+asyncpg://…`) | `sylion.db.pool`, `sylion.db.pg_migration`, `sylion.aeis.advisor._db` |
| `SYLION_DB_PATH` | nie | `sylion_aeis.db` | path | path do pliku SQLite | `sylion.project_mode.store`, `sylion.funding_autopilot.config` |
| `SYLION_USE_LEGACY_DB_PATH` | nie | `0` | bool | pozostaje wymuszone na `0`; legacy dashboard DB zostal usuniety w R3.13 | `scripts/start-server.ps1` |
| `ALEMBIC_DATABASE_URL` | nie | wartość z `alembic.ini` | URL | override DSN w czasie migracji | Alembic `env.py` |

#### Przykład Postgres

```dotenv
SYLION_DB_MODE=postgres
SYLION_DB_URL=postgresql+asyncpg://sylion:sylion_dev@localhost:5432/sylion
```

#### Przykład SQLite (default w dev)

```dotenv
SYLION_DB_MODE=sqlite
SYLION_DB_PATH=sylion_aeis.db
```

> **Uwaga:** zmiana `SYLION_DB_MODE` z `sqlite` na `postgres` **nie**
> przenosi danych. Użyj `scripts/migrate_to_postgres.py` aby zmigrować.

---

### 2.2 LLM providers

#### 2.2.1 API keys (zewnętrzne providerzy)

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `ANTHROPIC_API_KEY` | rekomendowane | — | secret `sk-ant-…` | klucz Anthropic (Claude Sonnet/Opus/Haiku) | `engine.llm_judge.client`, `cognitive.llm_adapter`, `api.ai_providers_routes` |
| `OPENAI_API_KEY` | nie | — | secret `sk-…` | klucz OpenAI (GPT-5, GPT-4.1, o3) | `engine.llm_judge.client`, `cognitive.llm_adapter` |
| `GOOGLE_API_KEY` | nie | — | secret `AIza…` | klucz Google AI (Gemini 2.5 Pro/Flash) | `engine.llm_judge.client`, funding scorer |
| `XAI_API_KEY` | nie | — | secret `xai-…` | klucz xAI (Grok 3) | `cognitive.llm_adapter` |
| `DEEPSEEK_API_KEY` | nie | — | secret `sk-…` | klucz DeepSeek (V3, R1) | `cognitive.llm_adapter` |
| `PERPLEXITY_API_KEY` | nie | — | secret `pplx-…` | klucz Perplexity (Sonar Pro/Sonar) | `cognitive.llm_adapter` |
| `OPENHANDS_API_KEY` | nie | — | secret `oh-…` | klucz OpenHands (uniwersalny) | `cognitive.llm_adapter` |

> **System uruchomi się bez żadnego z tych kluczy** — fallbackiem jest
> `qwen2.5` przez Ollama (jeśli zainstalowane) lub stub (`SYLION_LLM_PROVIDER=stub`).

#### 2.2.2 Wybór providera i modelu

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_LLM_PROVIDER` | nie | `stub` | enum: `anthropic`/`openai`/`google`/`xai`/`deepseek`/`perplexity`/`ollama`/`stub` | aktywny provider | `cognitive.llm_adapter`, `api.app` |
| `SYLION_LLM_MODEL` | nie | provider-specific | string | konkretny model (np. `claude-sonnet-4-6`, `gpt-5`, `qwen2.5:7b-instruct`) | `cognitive.llm_adapter`, `api.app` |
| `SYLION_LLM_MAX_TOKENS` | nie | `4096` | int | limit tokenów per call | `cognitive.llm_adapter` |
| `SYLION_LLM_COST_PER_1K` | nie | `0.0` | float | manual override stawki kosztu (tokenów/1k USD) | `cognitive.llm_adapter` |
| `SYLION_LLM_API_KEY` | nie | — | secret | generic fallback klucz | `cognitive.llm_adapter` |
| `SYLION_LLM_BASE_URL` | nie | — | URL | override base URL providera | `cognitive.llm_adapter` |

#### 2.2.3 Ollama (lokalny LLM)

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `OLLAMA_API_BASE` | nie | `http://localhost:11434` | URL | endpoint Ollama (legacy nazwa) | `.env.example` |
| `OLLAMA_BASE_URL` | nie | `http://localhost:11434` | URL | endpoint Ollama (preferowana nazwa) | `engine.llm_judge.client`, `pricing.adapters.ollama_adapter`, `cognitive.llm_adapter` |
| `OLLAMA_API_KEY` | nie | `ollama` | string | dummy key (litellm wymaga) | provider config |

#### 2.2.4 LiteLLM tuning

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `LITELLM_LOCAL_MODEL_COST_MAP` | nie | `False` | bool | użyj lokalnej mapy kosztów (offline) | `litellm` runtime |
| `LITELLM_DO_NOT_TRACK` | nie | `False` | bool | wyłącz telemetrię litellm | `litellm` runtime |

#### Mapowanie provider → env var (`api.ai_providers_routes.ENV_KEYS`)

| Provider | ENV var |
|---|---|
| `anthropic` | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `google` | `GOOGLE_API_KEY` |
| `xai` | `XAI_API_KEY` |
| `deepseek` | `DEEPSEEK_API_KEY` |
| `perplexity` | `PERPLEXITY_API_KEY` |

---

### 2.3 Auth i sekrety

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_INTERNAL_API_KEY` | tak (prod) | — | secret 32+ bytes | wewnętrzny klucz dla orchestrator-dashboard | `sylion.security.*`, `sylion.api.app` |
| `SYLION_JWT_SECRET` | tak (prod) | derived from `SYLION_INTERNAL_API_KEY` | secret 64+ bytes | sekret podpisu JWT | `sylion.security.jwt_auth` |
| `SYLION_API_KEY_FILE` | nie | — | path | docker secret path (alternatywa do `SYLION_INTERNAL_API_KEY`) | `docker-compose.yml` |
| `SYLION_DB_PASSWORD_FILE` | nie | — | path | docker secret path do hasła DB | `docker-compose.yml` |
| `SYLION_VAULT_SECRET` | nie | hardcoded fallback | secret | sekret szyfrowania `key_vault` | `sylion.security.key_vault` |
| `SYLION_AGE_IDENTITY` | nie | — | inline age key | klucz prywatny SOPS (inline) | `sylion.security.sops_provider` |
| `SYLION_AGE_IDENTITY_FILE` | nie | — | path | path do age key file | `sylion.security.sops_provider` |
| `SYLION_AEIS_ENV` | nie | `dev` | enum: `dev`/`staging`/`production` | środowisko AEIS (decyduje o secrets dir) | `sylion.security.sops_provider`, `sylion.api.app`, `sylion.security.startup_check` |
| `SYLION_SECRETS_DIR` | nie | `secrets/{env}` | path | katalog z plikami sekretów SOPS | `sylion.security.sops_provider` |
| `SYLION_ALLOW_DEFAULT_KEYS` | nie | `false` | bool | guard dla default API keys w prod (pozwól na hardcoded) | `sylion.security.startup_check` |

---

### 2.4 Logging

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `LOG_LEVEL` | nie | `INFO` | enum: `DEBUG`/`INFO`/`WARNING`/`ERROR` | poziom logowania | `sylion.api.app`, root logger |
| `SYLION_LOG_FILE` | nie | — | bool | zapisz logi do `SYLION_HOME/logs/` | log handler |
| `SYLION_LOG_JSON` | nie | — | bool | format logów JSON (vs human-readable) | log handler |

---

### 2.5 Feature flags

| Nazwa | Wymagane | Default | Typ | Opis | Używane w | Production-safe? |
|---|---|---|---|---|---|---|
| `SYLION_ENV` | nie | `development` | enum | `production`/`staging`/`development` | wszędzie | n/a |
| `SYLION_RBAC_DISABLED` | nie | `0` | bool | wyłącz RBAC enforcement | `sylion.security.rbac`, `sylion.api.rbac_enforcement` | **NIE** |
| `SYLION_AUTH_BYPASS` | nie | `0` | bool | wyłącz auth (każdy request jako admin) | dev-only | **NIE** |
| `SYLION_RATE_LIMIT_DISABLED` | nie | `0` | bool | wyłącz rate limiter | `sylion.api.rate_limit` | **NIE** |
| `SYLION_TRUST_PROXY` | nie | `0` | bool | ufaj X-Forwarded-For (za reverse proxy) | `sylion.api.rate_limit` | tak (z Caddy/nginx) |
| `SYLION_VERSION` | nie | `6.0.0` | string | wersja aplikacji wyświetlana w UI | sylion.api.app | tak |

> **Reguła operacyjna:** wszystkie flagi `*_DISABLED` muszą być `0` lub
> nieustawione w produkcji. `start-server.ps1/.bat/.sh` ustawia je na `1`
> tylko dla dev — produkcja używa innych skryptów (`scripts/install_worker_service.ps1`
> + dedykowanego `.env`).

---

### 2.6 AEIS Advisor — specyfika

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_ADVISOR_LOCAL_ONLY` | nie | `0` | bool | wymuś tylko lokalne LLM (Ollama) — fallback dla offline / brak kluczy | `aeis.advisor.engine.llm_judge.fallback` |
| `SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY` | nie | computed | int | miesięczny budżet tokenów dla funding scoringu | `aeis.advisor.funding.token_budget` |
| `SYLION_ADVISOR_FUNDING_STUB_LLM` | nie | `0` | bool | wymuś stub w funding scorerze (testy / brak kluczy) | `aeis.advisor.funding.scoring.llm_scorer` |

> **Decyzja architektoniczna:** zmienne `SYLION_ADVISOR_*` istnieją by
> umożliwić **deterministyczne, lokalne uruchomienie** każdego sub-modułu
> bez zewnętrznych zależności — kluczowe dla testów regresyjnych.

---

### 2.7 Mobile gateway

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_MOBILE_SIGNING_SECRET` | tak (prod) | `operator-mobile-dev-secret` | secret 32+ bytes | sekret podpisu device-bound JWT | `sylion.api.app` (mobile gateway init) |

> Etap 1 używa device-bound JWT z dodatkowym headerem `X-Biometric-Verified`
> dla akcji D3+. Patrz `sylion/aeis/advisor/mobile_gateway/openapi.yaml`.

---

### 2.8 Funding (opt-in)

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_FUNDING_RESULTS_ROOT` | nie | `results/funding/` | path | katalog wyników funding autopilot | `sylion.funding_autopilot.config` |

---

### 2.9 Event bus i NATS

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_EVENT_MODE` | nie | `sqlite` (lub `inprocess`) | enum: `inprocess`/`sqlite`/`nats`/`redis` | backend event bus | `sylion.core.event_backbone`, `sylion.core.event_bus_factory`, `sylion.core.nats_event_bus` |
| `NATS_URL` | warunkowo | `nats://localhost:4222` | URL | DSN do NATS JetStream | `sylion.core.event_backbone`, `nats_event_bus` |
| `NATS_STREAM` | nie | `SYLION` | string | nazwa stream'u NATS | `sylion.core.event_backbone` |

#### Decyzja: który `SYLION_EVENT_MODE`?

| Tryb | Kiedy | Trade-off |
|---|---|---|
| `inprocess` | dev, testy jednostkowe | brak persistence, brak HA |
| `sqlite` | dev, single-host staging | persistence, ale tylko jeden proces |
| `nats` | staging / produkcja | HA, multi-process, wymaga NATS server |
| `redis` | low-latency, multi-process | wymaga Redis server |

---

### 2.10 Cache i Redis

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_CACHE_URL` | nie | `""` (in-memory LRU) | URL `redis://…` | backend cache | `sylion.infra.cache` |
| `REDIS_URL` | warunkowo | `redis://localhost:6379/0` | URL | DSN do Redis (event bus / rate limiter) | `sylion.core.event_backbone`, docker-compose |

---

### 2.11 Observability i tracing

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `SYLION_TRACING_ENABLED` | nie | `0` | bool | aktywuj OpenTelemetry tracing | `sylion.observability.tracing` |
| `SYLION_TRACING_SERVICE` | nie | `sylion-aeis` | string | service name w traces | `sylion.observability.tracing` |
| `SYLION_TRACING_OTLP_ENDPOINT` | nie | `http://localhost:4317` | URL gRPC | endpoint OTLP exporter | `sylion.observability.tracing` |
| `SYLION_TRACING_SAMPLE_RATIO` | nie | `1.0` | float [0,1] | próbka traces (1.0 = wszystkie) | `sylion.observability.tracing` |

> Zero overhead jeśli `SYLION_TRACING_ENABLED=0` — moduł `tracing.py`
> no-op'uje wszystkie spans.

---

### 2.12 Streaming i ABR

#### 2.12.1 Streaming thresholds

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `STREAM_LATENCY_P50_MS` | `80` | int | latencja P50 |
| `STREAM_LATENCY_P95_MS` | `150` | int | latencja P95 |
| `STREAM_LATENCY_P99_MS` | `300` | int | latencja P99 |
| `STREAM_INPUT_LATENCY_MS` | `50` | int | latencja inputu |
| `STREAM_FRAME_DROP_MAX_PCT` | `1.0` | float | max % drop'niętych klatek |
| `STREAM_AV_SYNC_DRIFT_MS` | `50` | int | max dryf A/V |
| `STREAM_RECONNECT_TIMEOUT_S` | `3` | int | timeout reconnectu |
| `STREAM_TURN_FALLBACK_S` | `5` | int | fallback turn |
| `STREAM_MIN_BITRATE_KBPS` | `500` | int | minimum bitrate |
| `STREAM_MAX_BITRATE_KBPS` | `8000` | int | maks bitrate |
| `STREAM_TARGET_FPS` | `30` | int | docelowe FPS |
| `STREAM_MAX_RESOLUTION` | `1920x1080` | string `WxH` | max rozdzielczość |
| `STREAM_CODEC_VIDEO` | `H.264` | enum | kodek wideo |
| `STREAM_CODEC_AUDIO` | `Opus` | enum | kodek audio |
| `STREAM_OPUS_SAMPLE_RATE` | `48000` | int Hz | sample rate Opus |
| `STREAM_BATTERY_THRESHOLD_PCT` | `20` | int | próg redukcji jakości |

#### 2.12.2 Stream security

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `STREAM_SECURITY_PROD` | `true` | bool | tryb produkcyjny |
| `STREAM_SECURITY_WEAK_BLOCK` | `true` | bool | blokuj słabe szyfry |
| `STREAM_SECURITY_RELAY_ONLY` | `true` | bool | wymagaj relay |
| `STREAM_SECURITY_SIG_RATE` | `50` | int msg/s | rate limit signaling |
| `STREAM_SECURITY_DC_RATE` | `200` | int msg/s | rate limit data channel |
| `STREAM_SECURITY_PINNED_CERTS` | `""` | comma-separated fingerprints | pinned TLS certs |

#### 2.12.3 Audio

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `AUDIO_OPUS_BITRATE_BPS` | `32000` | int bps | bitrate Opus |
| `AUDIO_OPUS_DTX` | `true` | bool | Discontinuous Transmission |
| `AUDIO_JITTER_BUFFER_MS` | `200` | int ms | bufor jittera |
| `AUDIO_ECHO_CANCEL` | `true` | bool | echo cancellation |

#### 2.12.4 ABR (Adaptive Bitrate)

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `ABR_INITIAL_RUNG` | `1` | int | startowy rung |
| `ABR_RAMP_UP_THRESHOLD` | `1.5` | float | próg wzrostu |
| `ABR_RAMP_DOWN_THRESHOLD` | `0.8` | float | próg spadku |
| `ABR_NACK_REDUCTION_PCT` | `0.15` | float | redukcja przy NACK |
| `ABR_THERMAL_MAX_RUNG` | `1` | int | max rung przy przegrzaniu |

#### 2.12.5 Signaling

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `SIGNALING_MAX_ROOMS` | `50` | int | max liczba pokoi |
| `SIGNALING_HEARTBEAT_S` | `10` | int s | heartbeat |
| `SIGNALING_STALE_TIMEOUT_S` | `30` | int s | timeout pokoju |
| `SIGNALING_STUN_URLS` | `stun:stun.l.google.com:19302` | URL | STUN |
| `SIGNALING_TURN_URLS` | `""` | URL | TURN |
| `SIGNALING_TURN_USERNAME` | `""` | string | TURN user |
| `SIGNALING_TURN_CREDENTIAL` | `""` | secret | TURN cred (przechowuj w secrets!) |

#### 2.12.6 Input protocol

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `INPUT_PROTOCOL_HMAC_KEY` | wbudowany | secret | HMAC dla wejść (REQ w prod) |
| `INPUT_REPLAY_WINDOW_S` | `5.0` | float | okno replay protection |
| `INPUT_MAX_BATCH_SIZE` | `32` | int | max batch wejść |

---

### 2.13 Cellular / SDR

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `SYLION_BTS_MODE` | `zmq` | enum: `zmq`/`rf` | tryb BTS (symulacja vs. real RF) |
| `SYLION_TX_GAIN` | `-10` | int dBm | moc nadawania |
| `SYLION_FARADAY_CONFIRMED` | — | string `yes` | wymagane dla `rf` mode |
| `SYLION_PHANTOM_PATH` | — | path | path do phantoma SDR |

> **Bezpieczeństwo:** tryb `rf` jest legalny **tylko** w klatce Faradaya.
> Brak `SYLION_FARADAY_CONFIRMED=yes` blokuje uruchomienie w trybie RF.

---

### 2.14 Build verification

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `BUILD_VERIFICATION_ENABLED` | `true` | bool | włącz weryfikację buildu pre-deploy |
| `BUILD_RUN_TESTS` | `true` | bool | uruchom testy w ramach weryfikacji |
| `BUILD_TEST_TIMEOUT_S` | `120` | int s | timeout testów |
| `BUILD_VET_TIMEOUT_S` | `30` | int s | timeout vet |
| `BUILD_BUILD_TIMEOUT_S` | `60` | int s | timeout buildu |

---

### 2.15 Anti-hallucination i fact-check

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `FACT_CHECKER_ENABLED` | `true` | bool | włącz Fact Checker (Layer 5) |
| `FACT_CHECKER_MODEL_ID` | `anthropic/claude-sonnet-4-6` | string litellm-format | model używany przez fact checker |
| `FACT_CHECKER_MODEL` | `claude` | string alias | krótki alias modelu |
| `FACT_CHECKER_MAX_ITEMS` | `50` | int | max itemów na run |
| `FACT_CHECKER_CONTEXT_LINES` | `20` | int | linie kontekstu |
| `CLAIM_PROVENANCE_ENABLED` | `true` | bool | provenance claiming |
| `PROVENANCE_CONTEXT_WINDOW` | `10` | int | okno kontekstu provenance |
| `PROVENANCE_MIN_MATCH_RATIO` | `0.3` | float | min ratio dopasowania |
| `SEMANTIC_DEDUP_ENABLED` | `true` | bool | semantyczna dedup |
| `DEDUP_SIMILARITY_THRESHOLD` | `0.75` | float [0,1] | próg podobieństwa |
| `DEDUP_MODEL_NAME` | `all-MiniLM-L6-v2` | string | model sentence-transformers |
| `BENCHMARK_ENABLED` | `true` | bool | benchmark harness |
| `BENCHMARK_OUTPUT_DIR` | `""` (= RESULTS_DIR) | path | katalog wyjściowy |
| `BENCH_SETUP_P95_MS` | `2000` | int ms | próg setup P95 |
| `BENCH_INPUT_PHOTON_P95_MS` | `100` | int ms | próg input→photon P95 |
| `BENCH_ABR_RAMPUP_MS` | `5000` | int ms | próg ramp-up ABR |
| `BENCH_RECONNECT_P95_MS` | `4000` | int ms | próg reconnect P95 |
| `BENCH_FRAME_DROP_FAIL_PCT` | `0.05` | float | próg frame drop fail |
| `BENCH_AV_SYNC_FAIL_MS` | `80` | int ms | próg AV sync fail |

---

### 2.16 Device harness

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `DEVICE_HARNESS_DRY_RUN` | `true` | bool | nie wysyłaj poleceń do urządzeń |
| `DEVICE_PIXEL_SERIAL` | `""` (auto-detect) | string | ADB serial Pixel 8 |
| `DEVICE_ROUTER_HOST` | `192.168.8.1` | IP/host | host routera |
| `DEVICE_ROUTER_USER` | `root` | string | user SSH |
| `DEVICE_ROUTER_SSH_KEY` | `""` | path | klucz SSH (REQ jeśli używasz device harness) |

---

### 2.17 Core pipeline (pozostałe)

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `CONSENSUS_THRESHOLD` | `3` | int | min konsensus do akceptacji |
| `MAX_AGENT_STEPS` | `50` | int | max kroki agenta na etap |
| `RESULTS_DIR` | `./results` | path | katalog wyników |
| `MEMORY_DIR` | `./memory` | path | katalog pamięci agentów |
| `VERIFY_COUNT` | `3` | int | liczba weryfikatorów |
| `MIN_AGREEMENT` | `0.66` | float [0,1] | min zgodność weryfikatorów |
| `MAX_COST_USD_PER_DAY` | `50.0` | float USD | dzienny limit kosztów API |
| `BUDGET_WARNING_THRESHOLD` | `0.80` | float [0,1] | próg ostrzeżenia o budżecie |
| `PIPELINE_MIN_SLOTS` | `3` | int | min sloty pipeline |
| `SYLION_HOME` | `~/sylion` (Linux/macOS), `%USERPROFILE%\sylion` (Windows) | path | katalog domowy |
| `SYLION_UPLOADS_DIR` | `<pipeline_dir>/workspace_uploads` | path | uploads |
| `SYLION_PROJECT_RESULTS_ROOT` | computed | path | override results root dla project mode |
| `SYLION_SKILLS_DIR` | computed | path | katalog skill packów |
| `SESSION_COOKIE_SECURE` | `1` | bool | wymagaj HTTPS dla session cookie |
| `SYLION_EXTERNAL_DASHBOARD` | — | bool | używaj zewnętrznego dashboardu zamiast wbudowanego |
| `WEB_CONCURRENCY` | `1` | int | liczba workerów Gunicorn |
| `DASHBOARD_PORT` | `8421` | int | port dashboardu (legacy) |
| `DASHBOARD_HOST` | `127.0.0.1` | IP | bind dashboardu |
| `SYLION_HTTP_PORT` | `8421` | int | port HTTP w Docker mode |
| `SYLION_GRPC_PORT` | `50051` | int | port gRPC w Docker mode |
| `SYLION_WORKERS` | `1` (Dockerfile), `2` (docker-compose) | int | liczba workerów w Docker |

---

### 2.18 Metrics

| Nazwa | Default | Typ | Opis |
|---|---|---|---|
| `METRICS_MAX_SAMPLES` | `10000` | int | max próbek per metryka |
| `METRICS_ALERT_DEDUP_S` | `60` | int s | okno deduplikacji alertów |
| `METRICS_LOG_DIR` | `""` (wyłączone) | path | katalog logów metryk |

---

## 3. Frontend env vars (Next.js)

Next.js rozróżnia trzy typy zmiennych:

- **Server-side only** (bez prefixu) — dostępne tylko w `getServerSideProps`,
  Server Actions, Server Components.
- **Client-side** (`NEXT_PUBLIC_*`) — wkompilowane w bundle, dostępne
  globalnie. **Nigdy nie umieszczaj w nich sekretów**.
- **Build-time** — używane podczas `next build`.

### 3.1 Public (klient + serwer)

| Nazwa | Wymagane | Default | Typ | Opis | Używane w |
|---|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | nie | `http://127.0.0.1:8010` | URL | base URL backendu API | `lib/api/client.ts`, `lib/api/hooks.ts`, `lib/api/advisor.ts`, `lib/api/orchestration.ts`, `lib/hooks/advisor.ts`, `components/onboarding/FirstRunBanner.tsx`, `app/(app)/operator-mobile/_mobile.ts` |

### 3.2 Server-only (jeśli dodawane)

W obecnej kodzie nie ma jawnych server-only env vars. Jeśli dodawane, należy
zachować konwencję: prefix `SYLION_` lub `INTERNAL_`, nigdy `NEXT_PUBLIC_`.

### 3.3 Built-in Next.js

| Nazwa | Default | Opis |
|---|---|---|
| `NODE_ENV` | `development`/`production`/`test` | ustawiane przez `next` |
| `PORT` | `3000` | port `next dev`/`next start` |
| `HOSTNAME` | `0.0.0.0` | bind hostname |
| `NEXT_TELEMETRY_DISABLED` | — | wyłącza telemetrię Next.js (`1`) |

### 3.4 Lokacja `.env*`

Next.js ładuje (kolejność rosnącego priorytetu):

1. `.env`
2. `.env.development` / `.env.production` / `.env.test`
3. `.env.local`
4. `.env.development.local` / `.env.production.local`
5. `process.env`

**Zaleceniem dla SYLION** jest używanie wyłącznie `.env.local` w katalogu
`src/sylion-frontend/`. Plik ten **nie jest** commitowany.

---

## 4. Docker compose env vars

`docker-compose.yml` definiuje następujące env vars per serwis:

### 4.1 sylion-dashboard (FastAPI + gRPC)

| Nazwa | Wartość | Opis |
|---|---|---|
| `SYLION_HOME` | `/var/lib/sylion` | katalog domowy w kontenerze |
| `SYLION_WORKERS` | `2` | liczba workerów |
| `SYLION_API_KEY_FILE` | `/run/secrets/sylion_api_key` | docker secret z kluczem |
| `SYLION_DB_PASSWORD_FILE` | `/run/secrets/sylion_db_password` | docker secret z hasłem |
| `REDIS_URL` | `redis://redis:6379/0` | Redis (service name = `redis`) |

### 4.2 grafana

| Nazwa | Wartość | Opis |
|---|---|---|
| `GF_SECURITY_ADMIN_PASSWORD__FILE` | `/run/secrets/sylion_db_password` | hasło admin Grafany |
| `GF_USERS_ALLOW_SIGN_UP` | `false` | nie pozwalaj na rejestrację |
| `GF_SERVER_ROOT_URL` | `%(protocol)s://%(domain)s/grafana/` | base URL |
| `GF_SERVER_SERVE_FROM_SUB_PATH` | `true` | serwuj z sub-path |

### 4.3 alertmanager (placeholder env vars do envsubst)

| Nazwa | Opis |
|---|---|
| `PAGERDUTY_ROUTING_KEY` | klucz PagerDuty |
| `SLACK_WEBHOOK_URL` | webhook Slack |
| `SMTP_AUTH_PASSWORD` | hasło SMTP |

> Alertmanager nie expanduje env vars natywnie — operator musi zrobić
> `envsubst < alertmanager.yml.tpl > alertmanager.yml` przed mount'em, lub
> użyć Phase 4 secret refs.

### 4.4 Dockerfile ENV (image-level)

Z `src/sylion-pipeline/Dockerfile`:

| Nazwa | Wartość | Opis |
|---|---|---|
| `SYLION_HOME` | `/var/lib/sylion` | path do volume |
| `SYLION_WORKERS` | `1` | default — override w compose |
| `PYTHONUNBUFFERED` | `1` | nie buforuj stdout/stderr |
| `PYTHONDONTWRITEBYTECODE` | `1` | nie pisz `.pyc` |
| `PYTHONFAULTHANDLER` | `1` | dump traceback przy SIGSEGV |
| `PATH` | `/venv/bin:$PATH` | aktywuj venv |
| `VIRTUAL_ENV` | `/venv` | venv path |

---

## 5. CI/CD env vars

### 5.1 GitHub Actions (jeśli używane)

| Nazwa | Opis |
|---|---|
| `GITHUB_TOKEN` | auto-generated, dla checkout, releases |
| `GHCR_USERNAME` / `GHCR_TOKEN` | push do ghcr.io |
| `ANTHROPIC_API_KEY` | testy LLM E2E |
| `OPENAI_API_KEY` | testy LLM E2E |
| `SYLION_AEIS_ENV` | `staging` / `production` per environment |

### 5.2 pre-commit / pre-push hooks

| Nazwa | Opis |
|---|---|
| `PRE_COMMIT_HOME` | cache pre-commit |
| `RUFF_CACHE_DIR` | cache ruff |

---

## 6. Bezpieczeństwo env vars

### 6.1 Sekrety (NIE commit'ować, NIE logować)

| Kategoria | Zmienne |
|---|---|
| LLM API keys | `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`, `PERPLEXITY_API_KEY`, `OPENHANDS_API_KEY` |
| Internal secrets | `SYLION_INTERNAL_API_KEY`, `SYLION_JWT_SECRET`, `SYLION_VAULT_SECRET` |
| Mobile gateway | `SYLION_MOBILE_SIGNING_SECRET` |
| SOPS | `SYLION_AGE_IDENTITY`, `SYLION_AGE_IDENTITY_FILE` |
| Database | `SYLION_DB_URL` (z hasłem inline), `SYLION_DB_PASSWORD_FILE` |
| TURN | `SIGNALING_TURN_CREDENTIAL` |
| Input | `INPUT_PROTOCOL_HMAC_KEY` |
| External | `PAGERDUTY_ROUTING_KEY`, `SLACK_WEBHOOK_URL`, `SMTP_AUTH_PASSWORD` |

### 6.2 Rotacja kluczy

| Klucz | Częstotliwość | Procedura |
|---|---|---|
| `SYLION_INTERNAL_API_KEY` | 90 dni | wygeneruj nowy → update `.env.generated` → restart |
| `SYLION_JWT_SECRET` | 90 dni | wygeneruj nowy → wszyscy operatorzy muszą się ponownie zalogować |
| `SYLION_MOBILE_SIGNING_SECRET` | 30 dni | wygeneruj nowy → mobile apps muszą się re-pair'ować |
| LLM API keys | per provider rotation policy | usuń stary w panelu providera, dodaj nowy do `.env` |
| `SIGNALING_TURN_CREDENTIAL` | 30 dni | rotacja per krzywa AAA TURN |
| `SOPS age identity` | rzadko (compromise only) | re-encrypt wszystkie sekrety |

### 6.3 Generowanie nowych sekretów

```bash
# JWT secret (64 bytes hex)
python -c "import secrets; print(secrets.token_hex(32))"

# Internal API key
python -c "import secrets; print('internal_' + secrets.token_urlsafe(32))"

# HMAC key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# age identity (SOPS)
age-keygen -o key.txt
```

### 6.4 Storage zaleceniem

| Środowisko | Mechanizm |
|---|---|
| dev | `.env` lokalnie, gitignore |
| staging | SOPS-encrypted YAML w repo (`secrets/staging.yaml`) |
| production | docker secrets / Kubernetes secrets / cloud KMS (AWS/GCP/Azure) |

### 6.5 Audyt env vars

System przy starcie (`sylion.security.startup_check`) waliduje:

- W produkcji: brak `SYLION_RBAC_DISABLED=1`, `SYLION_AUTH_BYPASS=1`,
  `SYLION_RATE_LIMIT_DISABLED=1`.
- `SYLION_JWT_SECRET` ma min 32 bytes entropii.
- `SYLION_INTERNAL_API_KEY` nie jest pustym ani placeholder'em.
- Jeśli `SYLION_LLM_PROVIDER` ustawiony, odpowiedni `*_API_KEY` istnieje.
- `SESSION_COOKIE_SECURE=1` jeśli `SYLION_AEIS_ENV=production`.

Naruszenie → `RuntimeError("startup check failed: …")`.

---

## 7. .env.example template

Pełny szablon do skopiowania jako `.env`:

```dotenv
# =============================================================================
# SYLION Pipeline — .env (operator-edited, NIE commitować)
# =============================================================================

# === Środowisko ===
SYLION_ENV=development
SYLION_AEIS_ENV=dev
SYLION_VERSION=6.0.0

# === Database ===
# Tryb sqlite (default) — bez Postgres:
SYLION_DB_MODE=sqlite
SYLION_DB_PATH=sylion_aeis.db
SYLION_USE_LEGACY_DB_PATH=0

# Albo tryb postgres (zalecany):
# SYLION_DB_MODE=postgres
# SYLION_DB_URL=postgresql+asyncpg://sylion:sylion_dev@localhost:5432/sylion

# === LLM API keys ===
# Min 1 klucz, albo SYLION_LLM_PROVIDER=ollama / stub
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=
GOOGLE_API_KEY=
XAI_API_KEY=
DEEPSEEK_API_KEY=
PERPLEXITY_API_KEY=

# === LLM provider selector ===
SYLION_LLM_PROVIDER=anthropic
SYLION_LLM_MODEL=claude-sonnet-4-6
SYLION_LLM_MAX_TOKENS=4096

# Ollama (local LLM, opcjonalnie):
# SYLION_LLM_PROVIDER=ollama
# SYLION_LLM_MODEL=qwen2.5:7b-instruct
OLLAMA_BASE_URL=http://localhost:11434

# litellm tuning
LITELLM_LOCAL_MODEL_COST_MAP=True
LITELLM_DO_NOT_TRACK=True

# === Auth & secrets ===
# Wygeneruj: python -c "import secrets; print(secrets.token_hex(32))"
SYLION_INTERNAL_API_KEY=
SYLION_JWT_SECRET=
SYLION_MOBILE_SIGNING_SECRET=operator-mobile-dev-secret
SYLION_VAULT_SECRET=

# === Feature flags (DEV ONLY — NIE w prod) ===
SYLION_RBAC_DISABLED=1
SYLION_AUTH_BYPASS=1
SYLION_RATE_LIMIT_DISABLED=1
SYLION_TRUST_PROXY=0

# === HTTP server ===
DASHBOARD_PORT=8421
DASHBOARD_HOST=127.0.0.1
SESSION_COOKIE_SECURE=0
WEB_CONCURRENCY=1

# === Logging ===
LOG_LEVEL=INFO
# SYLION_LOG_FILE=1
# SYLION_LOG_JSON=1

# === Event bus ===
SYLION_EVENT_MODE=sqlite
# NATS (opcjonalnie):
# SYLION_EVENT_MODE=nats
# NATS_URL=nats://localhost:4222
# NATS_STREAM=SYLION

# === Cache ===
# SYLION_CACHE_URL=redis://localhost:6379/0
# REDIS_URL=redis://localhost:6379/0

# === Tracing (opt-in) ===
SYLION_TRACING_ENABLED=0
# SYLION_TRACING_OTLP_ENDPOINT=http://localhost:4317
# SYLION_TRACING_SERVICE=sylion-aeis
# SYLION_TRACING_SAMPLE_RATIO=1.0

# === AEIS Advisor ===
SYLION_ADVISOR_LOCAL_ONLY=0
# SYLION_ADVISOR_FUNDING_TOKEN_BUDGET_MONTHLY=1000000
# SYLION_ADVISOR_FUNDING_STUB_LLM=0

# === Funding ===
# SYLION_FUNDING_RESULTS_ROOT=results/funding/

# === Core pipeline ===
CONSENSUS_THRESHOLD=3
MAX_AGENT_STEPS=50
RESULTS_DIR=./results
MEMORY_DIR=./memory
VERIFY_COUNT=3
MIN_AGREEMENT=0.66
MAX_COST_USD_PER_DAY=50.0
BUDGET_WARNING_THRESHOLD=0.80
PIPELINE_MIN_SLOTS=3

# === Fact Checker ===
FACT_CHECKER_ENABLED=true
FACT_CHECKER_MODEL_ID=anthropic/claude-sonnet-4-6
FACT_CHECKER_MODEL=claude
FACT_CHECKER_MAX_ITEMS=50
FACT_CHECKER_CONTEXT_LINES=20

# === Build verification ===
BUILD_VERIFICATION_ENABLED=true
BUILD_RUN_TESTS=true
BUILD_TEST_TIMEOUT_S=120
BUILD_VET_TIMEOUT_S=30
BUILD_BUILD_TIMEOUT_S=60

# === Provenance / Dedup ===
CLAIM_PROVENANCE_ENABLED=true
PROVENANCE_CONTEXT_WINDOW=10
PROVENANCE_MIN_MATCH_RATIO=0.3
SEMANTIC_DEDUP_ENABLED=true
DEDUP_SIMILARITY_THRESHOLD=0.75
DEDUP_MODEL_NAME=all-MiniLM-L6-v2

# === Benchmark ===
BENCHMARK_ENABLED=true
BENCH_SETUP_P95_MS=2000
BENCH_INPUT_PHOTON_P95_MS=100
BENCH_ABR_RAMPUP_MS=5000
BENCH_RECONNECT_P95_MS=4000
BENCH_FRAME_DROP_FAIL_PCT=0.05
BENCH_AV_SYNC_FAIL_MS=80

# === Streaming ===
STREAM_LATENCY_P50_MS=80
STREAM_LATENCY_P95_MS=150
STREAM_LATENCY_P99_MS=300
STREAM_INPUT_LATENCY_MS=50
STREAM_FRAME_DROP_MAX_PCT=1.0
STREAM_AV_SYNC_DRIFT_MS=50
STREAM_RECONNECT_TIMEOUT_S=3
STREAM_TURN_FALLBACK_S=5
STREAM_MIN_BITRATE_KBPS=500
STREAM_MAX_BITRATE_KBPS=8000
STREAM_TARGET_FPS=30
STREAM_MAX_RESOLUTION=1920x1080
STREAM_CODEC_VIDEO=H.264
STREAM_CODEC_AUDIO=Opus
STREAM_OPUS_SAMPLE_RATE=48000
STREAM_BATTERY_THRESHOLD_PCT=20

# === Stream security ===
STREAM_SECURITY_PROD=true
STREAM_SECURITY_WEAK_BLOCK=true
STREAM_SECURITY_RELAY_ONLY=true
STREAM_SECURITY_SIG_RATE=50
STREAM_SECURITY_DC_RATE=200
STREAM_SECURITY_PINNED_CERTS=

# === Audio ===
AUDIO_OPUS_BITRATE_BPS=32000
AUDIO_OPUS_DTX=true
AUDIO_JITTER_BUFFER_MS=200
AUDIO_ECHO_CANCEL=true

# === ABR ===
ABR_INITIAL_RUNG=1
ABR_RAMP_UP_THRESHOLD=1.5
ABR_RAMP_DOWN_THRESHOLD=0.8
ABR_NACK_REDUCTION_PCT=0.15
ABR_THERMAL_MAX_RUNG=1

# === Signaling ===
SIGNALING_MAX_ROOMS=50
SIGNALING_HEARTBEAT_S=10
SIGNALING_STALE_TIMEOUT_S=30
SIGNALING_STUN_URLS=stun:stun.l.google.com:19302
SIGNALING_TURN_URLS=
SIGNALING_TURN_USERNAME=
SIGNALING_TURN_CREDENTIAL=

# === Input protocol ===
INPUT_PROTOCOL_HMAC_KEY=
INPUT_REPLAY_WINDOW_S=5.0
INPUT_MAX_BATCH_SIZE=32

# === SDR / RF (opt-in) ===
SYLION_BTS_MODE=zmq
SYLION_TX_GAIN=-10
# SYLION_FARADAY_CONFIRMED=yes
# SYLION_PHANTOM_PATH=

# === Metrics ===
METRICS_MAX_SAMPLES=10000
METRICS_ALERT_DEDUP_S=60
METRICS_LOG_DIR=

# === Device harness ===
DEVICE_HARNESS_DRY_RUN=true
DEVICE_PIXEL_SERIAL=
DEVICE_ROUTER_HOST=192.168.8.1
DEVICE_ROUTER_USER=root
DEVICE_ROUTER_SSH_KEY=
```

### 7.1 Frontend `.env.local`

```dotenv
# src/sylion-frontend/.env.local
NEXT_PUBLIC_API_URL=http://127.0.0.1:8010
```

### 7.2 Walidacja po edycji

Po zmianie `.env`:

```bash
# Restart backend
.\scripts\start-server.ps1

# Restart frontend (nowy terminal):
cd src/sylion-frontend
npm run dev
```

Sprawdź `curl http://127.0.0.1:8010/health` — powinno zwrócić `{"status":"ok"}`.

---

## 8. Cross-references

| Plik | Zakres |
|---|---|
| `40_setup_step_by_step.md` | jak skonfigurować env od zera |
| `42_configuration_files.md` | manifesty, YAML, docker-compose, package.json |
| `02_operational_manual.md` | runbook produkcyjny, rotacja sekretów |
| `03_governance_audit_compliance.md` | RBAC, JWT, security policy |
| `04_dla_developera.md` | dodawanie nowych env vars (konwencje) |

---

> **Reguły dodawania nowych env vars (dla developerów)**
>
> 1. Prefix musi należeć do tabeli 1.1.
> 2. Default musi być sensowny dla dev — system uruchamia się bez ręcznej
>    konfiguracji.
> 3. Walidacja w startup check (`sylion.security.startup_check`) — jeśli
>    zmienna jest sekretna, sprawdź entropy i obecność w prod.
> 4. Wpis do `.env.example` z komentarzem PL.
> 5. Wpis do tego pliku (sekcja 2.x lub 3.x).
> 6. Test E2E: brak zmiennej → fallback działa, obecność → aktywuje feature.
