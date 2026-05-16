# 42 — Configuration Files — kompletny rejestr
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> **Cel dokumentu**
> Dokumentacja wszystkich plików konfiguracyjnych w stack'u SYLION AEIS
> Advisor: manifestów modułów, YAML-ów, Dockerfile, docker-compose,
> package.json, tsconfig, playwright, pytest, alembic. Każda sekcja zawiera
> path, role, schemat lub kompletne pola, oraz konkretny przykład.

---

## Spis treści

1. [Konwencje organizacji configów](#1-konwencje-organizacji-configow)
2. [Backend manifesty (sylion/contracts/manifests/)](#2-backend-manifesty)
3. [role_routing_defaults.yaml — full breakdown](#3-role_routing_defaultsyaml)
4. [mobile_gateway/openapi.yaml — full breakdown](#4-mobile_gatewayopenapiyaml)
5. [docker-compose.yml — sekcja po sekcji](#5-docker-composeyml)
6. [Dockerfile — RUN steps explained](#6-dockerfile)
7. [Frontend configs](#7-frontend-configs)
8. [Test configs](#8-test-configs)
9. [Alembic migrations dir structure](#9-alembic-migrations-dir-structure)
10. [Inne configi (Caddy, monitoring)](#10-inne-configi-caddy-monitoring)
11. [Cross-references](#11-cross-references)

---

## 1. Konwencje organizacji configów

### 1.1 Lokacja per kategoria

| Kategoria | Path | Format |
|---|---|---|
| Module manifests | `src/sylion-pipeline/sylion/contracts/manifests/*.json` | JSON |
| Module routing defaults | `src/sylion-pipeline/sylion/aeis/advisor/role_resolver/role_routing_defaults.yaml` | YAML |
| Mobile gateway OpenAPI | `src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/openapi.yaml` | OpenAPI 3.0.3 |
| Docker | `src/sylion-pipeline/Dockerfile`, `docker-compose.yml` | Dockerfile, YAML |
| Monitoring | `src/sylion-pipeline/deploy/monitoring/*.yaml`, `*.yml` | YAML |
| Reverse proxy | `src/sylion-pipeline/Caddyfile` | Caddyfile |
| Frontend build | `src/sylion-frontend/{package.json,tsconfig.json,next.config.ts}` | JSON / TS |
| Frontend tests | `src/sylion-frontend/playwright.config.ts` | TS |
| Backend tests | `src/sylion-pipeline/pytest.ini`, `pyproject.toml` | INI / TOML |
| Alembic | `src/sylion-pipeline/alembic.ini`, `alembic/` | INI + Python |
| Project Python | `src/sylion-pipeline/pyproject.toml`, `requirements.txt`, `requirements-lock.txt` | TOML / pip |
| Claude Code | `.claude/settings.local.json` | JSON |

### 1.2 Versioning configów

| Plik | Wersjonowany w git? | Schema validation | Override path |
|---|---|---|---|
| Manifesty `*.json` | tak | `sylion.contracts.schema_validator` | nie (static) |
| `role_routing_defaults.yaml` | tak | `routing_table.py` (Python validator) | runtime override przez Settings UI |
| `openapi.yaml` | tak | `swagger-cli validate` | nie |
| `docker-compose.yml` | tak | `docker compose config` | profiles + env |
| `Dockerfile` | tak | `hadolint` | build args |
| `package.json` | tak | npm | nie |
| `.env*` | NIE | manualna | env precedence |

### 1.3 Reguła "manifest owns module"

Każdy moduł SYLION ma dokładnie jeden manifest `*.json` w
`sylion/contracts/manifests/`, który jest jedynym źródłem prawdy o:

- ID modułu (`module_id`)
- Klasie modułu (`module_kind`: `KERNEL`/`COGNITIVE`/`SURFACE`/`AEIS`/`ADVISOR`/…)
- Wersji kontraktu (`contract_version`)
- Zależnościach (`depends_on`)
- Eventach (subscribe / emit)
- Storage (Postgres schemas + SQLite tables)
- Lifecycle stage (`draft`/`active`/`deprecated`)
- LoC budget
- Golden tests path

---

## 2. Backend manifesty

### 2.1 Spis manifestów (`src/sylion-pipeline/sylion/contracts/manifests/`)

Aktualna lista manifestów (Etap 1 + AEIS rozszerzenia):

| Manifest | Moduł | Klasa |
|---|---|---|
| `aeis.advisor.actions.json` | AEIS Advisor — Actions | ADVISOR |
| `aeis.advisor.engine.json` | AEIS Advisor — Engine | ADVISOR |
| `aeis.advisor.events.json` | AEIS Advisor — Event taxonomy | ADVISOR |
| `aeis.advisor.funding.json` | AEIS Advisor — Funding | ADVISOR |
| `aeis.advisor.history.json` | AEIS Advisor — History | ADVISOR |
| `aeis.advisor.mobile_gateway.json` | AEIS Advisor — Mobile Gateway | ADVISOR |
| `aeis.advisor.orchestration_config.json` | AEIS Advisor — Orchestration Config | ADVISOR |
| `aeis.advisor.preferences.json` | AEIS Advisor — Preferences | ADVISOR |
| `aeis.advisor.pricing.json` | AEIS Advisor — Pricing | ADVISOR |
| `aeis.advisor.role_resolver.json` | AEIS Advisor — Role Resolver | ADVISOR |
| `aeis.advisor.scaling.json` | AEIS Advisor — Scaling | ADVISOR |
| `aeis.advisor.subscription.json` | AEIS Advisor — Subscription | ADVISOR |
| `aeis.advisor.variants.json` | AEIS Advisor — Variants | ADVISOR |
| `aeis.improvement_queue.json` | AEIS Improvement Queue | AEIS |
| `aeis.integration_controller.json` | AEIS Integration Controller | AEIS |
| `aeis.self_explanation.json` | AEIS Self Explanation | AEIS |
| `aeis.self_healing_orchestrator.json` | AEIS Self Healing | AEIS |
| `aeis.self_limitation.json` | AEIS Self Limitation | AEIS |
| `aeis.self_observation.json` | AEIS Self Observation | AEIS |
| `aeis.self_preservation.json` | AEIS Self Preservation | AEIS |
| `cellular.attack_vectors.json` | Cellular RAN Lab | KERNEL |
| `cellular.control_plane.json` | Cellular Control Plane | KERNEL |
| `cellular.core_network.json` | Cellular Core Network | KERNEL |
| `cellular.evidence_writer.json` | Cellular Evidence Writer | KERNEL |
| `cellular.ran_lab.json` | Cellular RAN Lab | KERNEL |
| `cellular.rf_isolation.json` | Cellular RF Isolation | KERNEL |
| `cellular.ue_emulator.json` | Cellular UE Emulator | KERNEL |
| `cognitive.agent_runtime.json` | Agent Runtime | COGNITIVE |
| `cognitive.chat_engine.json` | Chat Engine | COGNITIVE |
| `cognitive.code_agent.json` | Code Agent | COGNITIVE |
| `cognitive.context_builder.json` | Context Builder | COGNITIVE |
| `cognitive.evaluator.json` | Evaluator | COGNITIVE |
| `cognitive.feedback_collector.json` | Feedback Collector (rating + survey) | COGNITIVE |
| `cognitive.idea_vault.json` | IdeaVault (15-state lifecycle) | COGNITIVE |
| `cognitive.knowledge_distiller.json` | Knowledge Distiller | COGNITIVE |
| `cognitive.llm_adapter.json` | LLM Adapter | COGNITIVE |
| `cognitive.model_registry.json` | Model Registry | COGNITIVE |
| `cognitive.model_router.json` | Model Router | COGNITIVE |
| `cognitive.planner.json` | Planner | COGNITIVE |
| `cognitive.reasoner.json` | Reasoner | COGNITIVE |

### 2.2 Schemat manifestu (kanoniczny)

```json
{
  "module_id": "sylion.aeis.advisor.engine",
  "module_kind": "ADVISOR",
  "owner_plan": "advisor_layer_etap1",
  "implementation_strategy": "greenfield",
  "contract_version": "1.0.0",
  "depends_on": [
    "sylion.aeis.advisor.preferences",
    "sylion.aeis.advisor.pricing",
    "sylion.aeis.advisor.history",
    "sylion.aeis.advisor.role_resolver",
    "sylion.governance.council_hybrid"
  ],
  "lifecycle_stage": "draft",
  "events_emit": [
    "aeis.advisor.engine.recommendation_emitted",
    "aeis.advisor.engine.recommendation_skipped",
    "aeis.advisor.engine.evidence_pack_finalized",
    "aeis.advisor.engine.deploy_blocked"
  ],
  "events_subscribe": [
    "aeis.idea.intake.completed",
    "aeis.council.formation_requested",
    "aeis.production.deploy_requested"
  ],
  "storage": {
    "postgres_schemas": ["advisor_engine", "advisor_evidence"],
    "sqlite_tables_dev": [
      "advisor_engine_recommendations",
      "advisor_engine_llm_judge_audit",
      "advisor_evidence_packs"
    ]
  },
  "loc_budget": {
    "loc_max": 3500,
    "loc_max_default": 1500,
    "exception_evidence_pack": "docs/.../evidence_pack_b003_loc_budget.md",
    "exception_decision_class": "D3",
    "rationale_summary": "Engine module aggregates rule_engine + d_ladder + confidence + service into a single coherent boundary."
  },
  "golden_tests": {
    "path": "tests/aeis/advisor/engine/",
    "minimum_required": [
      "rule_fires_on_matching_event",
      "llm_judge_audit_recorded_with_full_prompt_and_response",
      "confidence_components_match_expected_formula",
      "d5_card_without_evidence_pack_is_rejected"
    ]
  }
}
```

### 2.3 Pola — szczegółowy opis

| Pole | Typ | Wymagane | Opis |
|---|---|---|---|
| `module_id` | string `domain.subdomain.module` | tak | unikalny identyfikator modułu |
| `module_kind` | enum | tak | `KERNEL`/`COGNITIVE`/`SURFACE`/`AEIS`/`ADVISOR`/`GOVERNANCE`/`INFRA`/`SECURITY`/`OBSERVABILITY` |
| `owner_plan` | string | tak | nazwa workpackage / planu, do którego należy moduł |
| `implementation_strategy` | enum | tak | `greenfield`/`refactor`/`adapter`/`legacy_wrapper` |
| `contract_version` | semver | tak | wersja kontraktu (zmiana minor = backwards compat) |
| `depends_on` | string[] | tak | lista module_id zależności |
| `lifecycle_stage` | enum | tak | `draft`/`alpha`/`beta`/`active`/`deprecated`/`retired` |
| `events_emit` | string[] | tak | event taxonomy `domain.subject.action` |
| `events_subscribe` | string[] | tak | events na które moduł reaguje |
| `storage` | object | warunkowo | schemas Postgres + tabele SQLite (dla persistent modułów) |
| `storage.postgres_schemas` | string[] | nie | nazwy schemas (multi-schema dla logicznej separacji) |
| `storage.sqlite_tables_dev` | string[] | nie | nazwy tabel w trybie dev (SQLite mono-DB) |
| `loc_budget` | object | tak | budżet linii kodu |
| `loc_budget.loc_max` | int | tak | hard cap LoC |
| `loc_budget.loc_max_default` | int | tak | default cap (1500) |
| `loc_budget.exception_evidence_pack` | path | warunkowo | jeśli `loc_max > loc_max_default` — wymaga evidence pack |
| `loc_budget.exception_decision_class` | enum D0-D5 | warunkowo | klasa decyzji dla wyjątku |
| `golden_tests` | object | tak | minimalne testy regresyjne |
| `golden_tests.path` | path | tak | katalog z testami |
| `golden_tests.minimum_required` | string[] | tak | lista nazw testów które MUSZĄ istnieć |

### 2.4 Walidacja manifestów

```bash
cd src/sylion-pipeline
python -m sylion.contracts.validate_manifests
```

Wyjście:

```
[OK] sylion.aeis.advisor.engine — schema valid, deps resolved, events tax OK
[OK] sylion.aeis.advisor.preferences — …
[FAIL] sylion.cognitive.foo — depends_on contains unknown module: sylion.legacy.bar
```

### 2.5 Reguły zmian manifestu

| Zmiana | Wymaga | Decision Class |
|---|---|---|
| dodanie nowego event'u w `events_emit` | bump `contract_version` minor | D2 |
| usunięcie event'u z `events_emit` | bump major + `lifecycle_stage=deprecated` | D4 |
| dodanie zależności (`depends_on`) | review zależności, brak cykli | D2 |
| zmiana `module_kind` | refactor + cascade analysis | D5 |
| zmiana `loc_budget.loc_max` powyżej default | evidence pack + D3 approval | D3 |
| zmiana `storage.postgres_schemas` | migracja Alembic | D3 |

---

## 3. role_routing_defaults.yaml

### 3.1 Lokacja

`src/sylion-pipeline/sylion/aeis/advisor/role_resolver/role_routing_defaults.yaml`

### 3.2 Cel

Plik definiuje **domyślne mappingi** rola/cel → model LLM dla 4 poziomów
risk (`low`/`medium`/`high`/`critical`). Operator może je override'ować w
runtime przez Settings UI; ten plik jest fallbackiem.

### 3.3 Struktura

```yaml
roles:
  <role_name>:
    low: <model_id_or_list>
    medium: <model_id_or_list>
    high: <model_id_or_list>
    critical: <model_id_or_list>

purposes:
  <purpose_name>:
    low: <model_id_or_list>
    medium: <model_id_or_list>
    high: <model_id_or_list>
    critical: <model_id_or_list>
```

### 3.4 Pełna treść (referencyjna)

```yaml
# Default role routing configuration.
# Operator-editable defaults. Loaded by routing_table.py as reference.
# For runtime resolution, use routing_table.DEFAULT_ROUTING_BY_ROLE and
# routing_table.DEFAULT_ROUTING_BY_PURPOSE.

roles:
  planner:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  worker:
    low: qwen2.5:72b-instruct
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7
  critic:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  governance:
    low: claude-sonnet-4-6
    medium: claude-opus-4-7
    high: claude-opus-4-7
    critical: claude-opus-4-7
  local_verifier:
    low: qwen2.5:7b-instruct
    medium: qwen2.5:72b-instruct
    high: qwen2.5:72b-instruct
    critical: qwen2.5:72b-instruct

purposes:
  rationale_generation:
    low: qwen2.5:7b-instruct
    medium: claude-sonnet-4-6
    high: claude-sonnet-4-6
    critical: claude-opus-4-7
  alternatives_ranking:
    low: qwen2.5:72b-instruct
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  risk_assessment:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
  funding_scoring:
    low: gemini-2.5-pro
    medium: gemini-2.5-pro
    high:
      - claude-opus-4-7
      - gemini-2.5-pro
    critical:
      - claude-opus-4-7
      - gpt-5
  consortium_matching:
    low: claude-sonnet-4-6
    medium: claude-sonnet-4-6
    high: claude-opus-4-7
    critical: claude-opus-4-7
```

### 3.5 Role — opis

| Rola | Zastosowanie | Domyślny preferowany model |
|---|---|---|
| `planner` | dekompozycja celów, generacja masterplanu | Sonnet (low/med), Opus (high/crit) |
| `worker` | implementacja konkretnych zadań | Qwen 72B / Sonnet / Opus |
| `critic` | ocena pracy plannera/workera | Sonnet / Opus |
| `governance` | decyzje D3+ governance | Opus mostly |
| `local_verifier` | tani lokalny weryfikator | Qwen (różne rozmiary) |

### 3.6 Purposes — opis

| Purpose | Zastosowanie |
|---|---|
| `rationale_generation` | generowanie uzasadnień dla rekomendacji Advisor'a |
| `alternatives_ranking` | ranking alternatyw |
| `risk_assessment` | ocena ryzyka decyzji |
| `funding_scoring` | scoring projektów funding (Gemini multi-model) |
| `consortium_matching` | matching projektów do konsorcjów |

### 3.7 Multi-model arrays (consensus)

Gdy wartość to lista (np. `funding_scoring.high: [claude-opus-4-7, gemini-2.5-pro]`),
oznacza to że dla tego risk level system uruchamia oba modele równolegle i
wymaga konsensusu. Patrz `aeis.advisor.funding.scoring.llm_scorer`.

### 3.8 Override w runtime

Operator może override'ować przez:

1. UI → Settings → "Routing rules".
2. Endpoint `PATCH /api/advisor/preferences/routing` z payloadem JSON.
3. Override jest persisted w tabeli `advisor_preferences_routing_overrides`.

### 3.9 Walidacja

Plik jest walidowany przy starcie przez `routing_table.load_defaults()`:

- Każdy model_id musi być znany w `model_registry`.
- 4 risk levels per rola/purpose są wymagane.
- Listy nie mogą być puste.

---

## 4. mobile_gateway/openapi.yaml

### 4.1 Lokacja

`src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/openapi.yaml`

### 4.2 Cel

Specyfikacja OpenAPI 3.0.3 dla **mobile gateway** AEIS Advisor. Etap 1
implementuje gateway in-process; Etap 2 zamieni go na real gRPC client +
Kotlin Multiplatform mobile.

### 4.3 Struktura na wysokim poziomie

```yaml
openapi: 3.0.3
info:
  title: SYLION AEIS Advisor — Mobile Gateway
  version: 0.1.0
servers:
  - url: /mobile/v1
security:
  - bearerAuth: []
components:
  securitySchemes: …
  parameters: …
  schemas: …
paths:
  /cards: …
  /cards/{card_id}: …
  /cards/{card_id}/actions: …
  /sessions: …
```

### 4.4 Security

Wszystkie endpointy wymagają `bearerAuth` (JWT device-bound). Akcje na
kartach D3+ dodatkowo wymagają header'a `X-Biometric-Verified: true`.

```yaml
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
  parameters:
    BiometricVerifiedHeader:
      name: X-Biometric-Verified
      in: header
      required: false
      schema:
        type: string
        enum: ["true", "false"]
```

### 4.5 Główne schemas

| Schema | Opis |
|---|---|
| `AdvisorCardEnvelope` | wrapper proto-derived karty Advisor |
| `CardListResponse` | paginowana lista kart + cursor |
| `CardActionRequest` | payload akcji (approve/reject/defer) |
| `CardActionResponse` | wynik akcji |
| `SessionDescriptor` | opis sesji mobile |
| `ErrorResponse` | standardowy format błędu |

### 4.6 Główne endpointy

| Path | Method | Opis | Wymaga biometric? |
|---|---|---|---|
| `/cards` | GET | lista kart (paginated) | nie |
| `/cards/{card_id}` | GET | szczegóły karty | nie |
| `/cards/{card_id}/actions` | POST | wykonanie akcji | tak (jeśli D3+) |
| `/sessions` | POST | utworzenie sesji mobile | nie |
| `/sessions/{session_id}` | DELETE | zamknięcie sesji | nie |

### 4.7 Etap 1 vs Etap 2

| Aspekt | Etap 1 | Etap 2 |
|---|---|---|
| Backend | in-process advisor engine | gRPC client → engine |
| Schema | `additionalProperties: true` (luźny envelope) | proto-generated kanoniczny |
| Klient | brak (ScrolldThru API) | Kotlin Multiplatform |
| TLS | optional (Caddy) | mandatory mTLS |

### 4.8 Generacja kodu z OpenAPI

```bash
# TypeScript client
npx openapi-typescript-codegen \
  --input src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/openapi.yaml \
  --output src/sylion-frontend/src/lib/api/mobile_gen \
  --client fetch

# Kotlin client (Etap 2)
openapi-generator-cli generate \
  -i src/sylion-pipeline/sylion/aeis/advisor/mobile_gateway/openapi.yaml \
  -g kotlin \
  -o mobile-app/shared/api
```

---

## 5. docker-compose.yml

### 5.1 Lokacja

`src/sylion-pipeline/docker-compose.yml`

### 5.2 Top-level

```yaml
name: sylion

x-logging: &default-logging
  driver: json-file
  options:
    max-size: "10m"
    max-file: "5"

x-healthcheck-defaults: &hc-defaults
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 15s
```

`x-logging` i `x-healthcheck-defaults` to YAML anchory reused per service.

### 5.3 Secrets

```yaml
secrets:
  sylion_api_key:
    external: true          # docker secret create sylion_api_key <file>
  sylion_db_password:
    external: true
  caddy_tls_cert:
    external: true
  caddy_tls_key:
    external: true
```

Tworzenie sekretów przed uruchomieniem:

```bash
echo "internal_$(openssl rand -hex 32)" | docker secret create sylion_api_key -
echo "$(openssl rand -base64 24)" | docker secret create sylion_db_password -
docker secret create caddy_tls_cert ./certs/fullchain.pem
docker secret create caddy_tls_key ./certs/privkey.pem
```

### 5.4 Volumes

```yaml
volumes:
  sylion-data:        # SQLite, uploads
  caddy-data:         # ACME certs
  caddy-config:       # Caddy auto-config
  redis-data:         # Redis persistence
  prometheus-data:    # TSDB
  grafana-data:       # dashboards state
  loki-data:          # log indexes
  tempo-data:         # traces
  alertmanager-data:  # alert state
```

### 5.5 Serwisy — przegląd

| Service | Image | Port (host) | Profiles |
|---|---|---|---|
| `sylion-dashboard` | `ghcr.io/sylion/sylion-dashboard:latest` (build local) | 127.0.0.1:8421 | default |
| `caddy` | `caddy:2.8-alpine` | :80, :443, :443/udp | default |
| `redis` | `redis:7.2-alpine` | (internal only) | default |
| `prometheus` | `prom/prometheus:v2.52.0` | 127.0.0.1:9090 | `monitoring` |
| `grafana` | `grafana/grafana:10.4.2` | 127.0.0.1:3000 | `monitoring` |
| `loki` | `grafana/loki:2.9.6` | 127.0.0.1:3100 | `monitoring` |
| `promtail` | `grafana/promtail:2.9.6` | (internal only) | `monitoring` |
| `alertmanager` | `prom/alertmanager:v0.27.0` | 127.0.0.1:9093 | `monitoring` |
| `tempo` | `grafana/tempo:2.4.1` | 127.0.0.1:3200, 4317 | `monitoring` |

### 5.6 sylion-dashboard — sekcje

#### Build

```yaml
build:
  context: .
  dockerfile: Dockerfile
  target: runtime         # multi-stage final stage
image: ghcr.io/sylion/sylion-dashboard:latest
container_name: sylion-dashboard
restart: unless-stopped
```

#### Ports

```yaml
ports:
  - "127.0.0.1:8421:8421"   # bind do loopback — Caddy jest publiczną twarzą
```

#### Volumes + secrets

```yaml
volumes:
  - sylion-data:/var/lib/sylion
secrets:
  - sylion_api_key
  - sylion_db_password
```

#### Environment

```yaml
environment:
  SYLION_HOME: /var/lib/sylion
  SYLION_WORKERS: "2"
  SYLION_API_KEY_FILE: /run/secrets/sylion_api_key
  SYLION_DB_PASSWORD_FILE: /run/secrets/sylion_db_password
  REDIS_URL: redis://redis:6379/0
```

#### Healthcheck

```yaml
healthcheck:
  <<: *hc-defaults
  test: ["CMD", "curl", "-f", "http://localhost:8421/health"]
```

#### Resources

```yaml
deploy:
  resources:
    limits:
      cpus: "0.5"
      memory: 512M
    reservations:
      cpus: "0.1"
      memory: 128M
```

#### Hardening

```yaml
read_only: true
tmpfs:
  - /tmp
  - /var/run
security_opt:
  - no-new-privileges:true
```

### 5.7 caddy

```yaml
caddy:
  image: caddy:2.8-alpine
  ports: ["80:80", "443:443", "443:443/udp"]    # HTTP/3 QUIC
  volumes:
    - ./Caddyfile:/etc/caddy/Caddyfile:ro
    - caddy-data:/data
    - caddy-config:/config
  secrets:
    - caddy_tls_cert
    - caddy_tls_key
  depends_on:
    sylion-dashboard:
      condition: service_healthy
```

### 5.8 redis

```yaml
redis:
  image: redis:7.2-alpine
  command:
    - redis-server
    - --save 60 1
    - --loglevel warning
    - --maxmemory 64mb
    - --maxmemory-policy allkeys-lru
  volumes: [redis-data:/data]
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
```

### 5.9 Profile `monitoring`

```bash
docker compose up -d                          # tylko core
docker compose --profile monitoring up -d     # + prometheus, grafana, loki, …
```

### 5.10 prometheus — volumes

```yaml
volumes:
  - ./deploy/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  - ./deploy/monitoring/prometheus_alerts.yml:/etc/prometheus/rules/prometheus_alerts.yml:ro
  - ./deploy/monitoring/prometheus_recording_rules.yml:/etc/prometheus/rules/prometheus_recording_rules.yml:ro
  - ./deploy/monitoring/prometheus_slo_burn.yml:/etc/prometheus/rules/prometheus_slo_burn.yml:ro
  - prometheus-data:/prometheus
```

### 5.11 grafana — provisioning

```yaml
volumes:
  - grafana-data:/var/lib/grafana
  - ./deploy/grafana/provisioning:/etc/grafana/provisioning:ro
  - ./deploy/monitoring:/var/lib/grafana/dashboards:ro
environment:
  GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/sylion_db_password
  GF_USERS_ALLOW_SIGN_UP: "false"
  GF_SERVER_ROOT_URL: "%(protocol)s://%(domain)s/grafana/"
  GF_SERVER_SERVE_FROM_SUB_PATH: "true"
```

### 5.12 alertmanager — caveat

Plik `alertmanager.yml` zawiera placeholdery `${PAGERDUTY_ROUTING_KEY}`,
`${SLACK_WEBHOOK_URL}`, `${SMTP_AUTH_PASSWORD}`. Alertmanager **nie**
expanduje env vars natywnie. Rozwiązanie:

```bash
envsubst < deploy/monitoring/alertmanager.yml.tpl > deploy/monitoring/alertmanager.yml
```

W Phase 4 plan jest podmiana na `native_alertmanager_config` secret refs.

### 5.13 tempo — porty

```yaml
ports:
  - "127.0.0.1:3200:3200"   # tempo HTTP
  - "127.0.0.1:4317:4317"   # OTLP gRPC ingest
```

`SYLION_TRACING_OTLP_ENDPOINT=http://tempo:4317` z innego serwisu w
compose'ie.

---

## 6. Dockerfile

### 6.1 Lokacja

`src/sylion-pipeline/Dockerfile`

### 6.2 Strategia: multi-stage

| Stage | Base | Cel |
|---|---|---|
| `builder` | `python:3.12-slim` | build deps + venv + wheels |
| `runtime` | `python:3.12-slim` | minimalny image, non-root, hardened |

### 6.3 Stage `builder` — krok po kroku

```dockerfile
FROM python:3.12-slim AS builder

# 1. build deps (compiled wheels: bcrypt, cryptography, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        libssl-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# 2. izolowany venv w /venv
ENV VIRTUAL_ENV=/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 3. install z lock file (reproducible builds)
COPY requirements-lock.txt .
RUN pip install --upgrade pip==24.3.1 && \
    pip install --no-cache-dir -r requirements-lock.txt
```

### 6.4 Stage `runtime` — krok po kroku

```dockerfile
FROM python:3.12-slim AS runtime

# 1. labels OCI
LABEL org.opencontainers.image.title="SYLION AEIS" \
      org.opencontainers.image.description="SYLION AEIS v3.5 — Unified FastAPI + gRPC Server" \
      org.opencontainers.image.licenses="MIT"

# 2. runtime deps + hardening (suid/sgid bits removal)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

# 3. copy venv from builder stage
COPY --from=builder /venv /venv

# 4. non-root user (UID/GID 10001, no shell, no home login)
RUN groupadd --gid 10001 sylion && \
    adduser --uid 10001 --gid 10001 \
            --system --no-create-home \
            --shell /usr/sbin/nologin \
            sylion

# 5. ENV vars (image-level)
ENV SYLION_HOME=/var/lib/sylion \
    SYLION_WORKERS=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/venv/bin:$PATH"

# 6. dirs
RUN mkdir -p $SYLION_HOME && \
    chown -R sylion:sylion $SYLION_HOME

# 7. app source
WORKDIR /app
COPY --chown=sylion:sylion . .

# 8. cleanup dev/test artifacts
RUN rm -rf tests/ docs/ .git/ .github/ *.md requirements*.txt \
           docker-compose*.yml .env* Makefile

# 9. drop to non-root
USER sylion

# 10. persistent volume
VOLUME /var/lib/sylion

# 11. ports: 8421 HTTP, 50051 gRPC
EXPOSE 8421 50051

# 12. healthcheck — /health (NIE /api/health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8421/health || exit 1

# 13. tini jako PID 1 (signal handling, zombie reaping)
ENTRYPOINT ["/usr/bin/tini", "--"]

# 14. unified server entry (FastAPI + gRPC)
CMD ["python", "-m", "sylion.server", "--host", "0.0.0.0"]
```

### 6.5 Build args

Image jest budowany bez build args, ale można przekazać:

```bash
docker build \
  --target runtime \
  -t ghcr.io/sylion/sylion-dashboard:dev \
  src/sylion-pipeline/
```

### 6.6 Hardening checklist

- [x] non-root user (UID 10001)
- [x] read-only root filesystem (w docker-compose)
- [x] tmpfs dla `/tmp`, `/var/run`
- [x] `no-new-privileges`
- [x] suid/sgid bits removed
- [x] no-create-home, no-shell
- [x] tini jako PID 1
- [x] healthcheck z retry
- [x] volume tylko `/var/lib/sylion`
- [x] cleanup dev artifacts (tests/, docs/, .git/)

---

## 7. Frontend configs

### 7.1 package.json

Lokacja: `src/sylion-frontend/package.json`

```json
{
  "name": "sylion-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "eslint"
  },
  "dependencies": {
    "@base-ui/react": "^1.4.1",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "framer-motion": "^12.38.0",
    "lucide-react": "^1.8.0",
    "next": "16.2.4",
    "react": "19.2.4",
    "react-dom": "19.2.4",
    "recharts": "^3.8.1",
    "shadcn": "^4.3.1",
    "tailwind-merge": "^3.5.0",
    "tw-animate-css": "^1.4.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.59.1",
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.2.4",
    "playwright": "^1.59.1",
    "tailwindcss": "^4",
    "typescript": "^5"
  },
  "overrides": {
    "postcss": "^8.5.10"
  }
}
```

#### Scripts breakdown

| Script | Polecenie | Cel |
|---|---|---|
| `dev` | `next dev` | dev server z HMR (hot module reload) |
| `build` | `next build` | produkcyjny build do `.next/` |
| `start` | `next start` | uruchom zbudowany bundle |
| `lint` | `eslint` | walidacja kodu |

#### Dependencies — kategorie

| Kategoria | Pakiet | Cel |
|---|---|---|
| Framework | `next@16.2.4` | App Router, RSC, Server Actions |
| Framework | `react@19.2.4`, `react-dom@19.2.4` | runtime |
| UI components | `@base-ui/react` | bezgłowe komponenty (Dialog, Popover, …) |
| UI styling | `class-variance-authority`, `clsx`, `tailwind-merge` | composing class names |
| UI design system | `shadcn` | shadcn/ui components |
| UI animations | `framer-motion`, `tw-animate-css` | animacje |
| UI icons | `lucide-react` | ikony SVG |
| UI charts | `recharts` | wykresy |

#### DevDependencies — kategorie

| Kategoria | Pakiet | Cel |
|---|---|---|
| TypeScript | `typescript@^5`, `@types/*` | typy + kompilator |
| Linting | `eslint@^9`, `eslint-config-next` | walidacja |
| Testing | `@playwright/test`, `playwright` | E2E |
| Styling | `@tailwindcss/postcss`, `tailwindcss@^4` | Tailwind v4 |

#### Overrides

```json
"overrides": {
  "postcss": "^8.5.10"
}
```

Wymusza wersję `postcss` 8.5.10+ dla wszystkich zależności tranzytywnych
(security CVE).

### 7.2 tsconfig.json

Lokacja: `src/sylion-frontend/tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "react-jsx",
    "incremental": true,
    "plugins": [
      { "name": "next" }
    ],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": [
    "next-env.d.ts",
    "**/*.ts",
    "**/*.tsx",
    ".next/types/**/*.ts",
    ".next/dev/types/**/*.ts",
    "**/*.mts"
  ],
  "exclude": ["node_modules"]
}
```

#### Kluczowe opcje

| Opcja | Wartość | Cel |
|---|---|---|
| `target` | `ES2017` | minimalna wersja JS (pre-2018 browsers) |
| `strict` | `true` | wszystkie strict checks (recommend) |
| `moduleResolution` | `bundler` | Next.js / webpack-style resolver |
| `jsx` | `react-jsx` | nowy transform (React 17+) |
| `paths.@/*` | `./src/*` | alias dla importów |

### 7.3 next.config.ts

Lokacja: `src/sylion-frontend/next.config.ts`

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
```

Obecnie minimalny — wszystkie defaults Next.js 16 są OK. Typowe rozszerzenia
gdy potrzebne:

```typescript
const nextConfig: NextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [{ hostname: "localhost" }]
  },
  experimental: {
    typedRoutes: true
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8010/api/:path*" }
    ];
  }
};
```

### 7.4 tailwind / postcss

Tailwind v4 nie wymaga osobnego `tailwind.config.ts` — konfiguracja przez CSS
custom properties w `src/app/globals.css`.

`postcss.config.mjs`:

```javascript
export default {
  plugins: {
    "@tailwindcss/postcss": {}
  }
};
```

### 7.5 eslint.config.mjs

```javascript
import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });

export default [
  ...compat.extends("next/core-web-vitals", "next/typescript")
];
```

Flat config (ESLint 9+) — `next/core-web-vitals` + `next/typescript`.

---

## 8. Test configs

### 8.1 pytest.ini (backend)

Lokacja: `src/sylion-pipeline/pytest.ini`

Typowa zawartość (dla SYLION):

```ini
[pytest]
minversion = 9.0
testpaths = tests
addopts = -ra --strict-markers --strict-config
asyncio_mode = auto
markers =
    slow: oznacza testy wolne (>1s)
    integration: testy integracyjne (wymagają DB)
    e2e: testy end-to-end (wymagają pełnego stacku)
    smoke: smoke tests (zawsze uruchamiane na CI)
filterwarnings =
    ignore::DeprecationWarning:sqlalchemy.*
```

#### Uruchamianie

```bash
cd src/sylion-pipeline
pytest                          # wszystkie
pytest -m smoke                 # tylko smoke
pytest -m "not slow"            # bez wolnych
pytest tests/aeis/advisor/      # konkretny katalog
pytest -k "advisor and engine"  # nazwa zawiera słowo
pytest --cov=sylion             # z coverage
```

### 8.2 playwright.config.ts (frontend E2E)

Lokacja: `src/sylion-frontend/playwright.config.ts`

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    actionTimeout: 8_000,
  },
  webServer: {
    command: "npm run dev",
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

#### Pola

| Pole | Wartość | Cel |
|---|---|---|
| `testDir` | `./e2e` | katalog testów |
| `timeout` | 30s | per-test timeout |
| `expect.timeout` | 10s | per-assertion timeout |
| `fullyParallel` | `true` | równoległa egzekucja w pliku |
| `retries` | 0 | brak retry (CI ustawia 1-2) |
| `reporter` | `list` + `html` | format raportów |
| `use.baseURL` | `http://localhost:3000` | base dla `page.goto("/foo")` |
| `use.trace` | `on-first-retry` | nagrywaj trace przy retry |
| `use.screenshot` | `only-on-failure` | screenshot tylko przy fail |
| `webServer.command` | `npm run dev` | auto-start frontu |
| `webServer.reuseExistingServer` | `true` | używa istniejącego jeśli :3000 zajęty |

#### Uruchamianie

```bash
cd src/sylion-frontend
npx playwright install chromium       # raz
npx playwright test                   # wszystkie
npx playwright test --headed          # z widoczną przeglądarką
npx playwright test --ui              # interaktywny UI
npx playwright test e2e/advisor.spec  # konkretny plik
npx playwright show-report            # ostatni raport HTML
```

### 8.3 pyproject.toml (backend)

Lokacja: `src/sylion-pipeline/pyproject.toml`

Najczęściej zawiera config dla:

- `[tool.ruff]` — linting
- `[tool.mypy]` — typing
- `[tool.pytest.ini_options]` — alternatywa do pytest.ini
- `[build-system]` — jeśli pakiet jest publikowany

Przykładowy zarys:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100
select = ["E", "F", "W", "I", "B", "UP"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-first-party = ["sylion"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]
```

---

## 9. Alembic migrations dir structure

### 9.1 alembic.ini

Lokacja: `src/sylion-pipeline/alembic.ini`

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://sylion:sylion_dev@localhost:5432/sylion

[post_write_hooks]
hooks = ruff
ruff.type = console_scripts
ruff.entrypoint = ruff
ruff.options = check --fix REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
```

#### Kluczowe pola

| Pole | Cel |
|---|---|
| `script_location` | katalog z migracjami (`alembic/`) |
| `prepend_sys_path` | dodaj `.` do PYTHONPATH (dla `sylion.*` imports) |
| `sqlalchemy.url` | default DSN — override przez `ALEMBIC_DATABASE_URL` |
| `post_write_hooks.ruff` | auto-format nowych migracji |

### 9.2 Struktura `alembic/`

```
alembic/
├── env.py              # konfiguracja kontekstu (async/sync)
├── script.py.mako      # template dla nowych migracji
└── versions/
    ├── 20260420_advisor_etap1_b001.py
    ├── 20260420_advisor_etap1_b002_idea_vault.py
    ├── 20260421_council_hybrid_init.py
    └── …
```

### 9.3 Naming convention

`{YYYYMMDD}_{nazwa_workpackage}_b{nr_breaktask}_{opis}.py`

Przykłady:

- `20260420_advisor_etap1_b001_initial.py`
- `20260420_advisor_etap1_b003_engine_evidence.py`
- `20260421_council_hybrid_b002_voting_table.py`

### 9.4 Komendy

```bash
cd src/sylion-pipeline

# stwórz nową migrację
alembic revision -m "advisor_engine_evidence_pack"

# autogeneracja (z modeli SQLAlchemy)
alembic revision --autogenerate -m "advisor_engine_evidence_pack"

# upgrade do najnowszej
alembic upgrade head

# upgrade o jedną wersję
alembic upgrade +1

# downgrade
alembic downgrade -1
alembic downgrade base   # wszystko

# history
alembic history --verbose

# current
alembic current

# show specific revision
alembic show 20260420_advisor_etap1_b001
```

### 9.5 SQLite vs Postgres

Alembic w SYLION jest **opcjonalne** dla SQLite — moduły same tworzą
`CREATE TABLE IF NOT EXISTS` przy first-touch. Dla Postgres Alembic jest
**wymagane**.

Walidacja:

```python
# sylion/db/__init__.py
def db_mode() -> str:
    return os.environ.get("SYLION_DB_MODE", "sqlite")

# sylion/api/app.py startup
if db_mode() == "postgres":
    # Sprawdź alembic_version
    assert alembic_version() == HEAD, "Run: alembic upgrade head"
```

---

## 10. Inne configi

### 10.1 Caddyfile

Lokacja: `src/sylion-pipeline/Caddyfile`

Przykładowy:

```caddyfile
{
  email admin@example.com
  admin off
}

example.com {
  encode zstd gzip

  # TLS — używa docker secrets
  tls /run/secrets/caddy_tls_cert /run/secrets/caddy_tls_key

  # Reverse proxy do dashboard
  reverse_proxy /api/* sylion-dashboard:8421
  reverse_proxy /health sylion-dashboard:8421

  # Grafana sub-path (jeśli profile monitoring)
  handle_path /grafana/* {
    reverse_proxy grafana:3000
  }

  # Static (frontend)
  reverse_proxy /* sylion-frontend:3000

  # HSTS
  header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
  header X-Content-Type-Options "nosniff"
  header X-Frame-Options "DENY"
  header Referrer-Policy "strict-origin-when-cross-origin"

  log {
    output stdout
    format json
  }
}
```

### 10.2 deploy/monitoring/prometheus.yml

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/rules/*.yml

alerting:
  alertmanagers:
    - static_configs:
        - targets: ["alertmanager:9093"]

scrape_configs:
  - job_name: sylion-dashboard
    static_configs:
      - targets: ["sylion-dashboard:8421"]
    metrics_path: /api/metrics/prom

  - job_name: redis
    static_configs:
      - targets: ["redis:6379"]
```

### 10.3 deploy/monitoring/loki-config.yaml

Standardowy single-binary Loki config (filesystem chunks, BoltDB index).

### 10.4 deploy/monitoring/promtail-config.yaml

```yaml
server:
  http_listen_port: 9080

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    relabel_configs:
      - source_labels: ['__meta_docker_container_name']
        target_label: 'container'
```

### 10.5 deploy/monitoring/alertmanager.yml

```yaml
route:
  receiver: pagerduty
  group_by: [alertname, severity]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h

receivers:
  - name: pagerduty
    pagerduty_configs:
      - routing_key: "${PAGERDUTY_ROUTING_KEY}"   # envsubst before mount
        severity: "{{ .CommonLabels.severity }}"

  - name: slack
    slack_configs:
      - api_url: "${SLACK_WEBHOOK_URL}"
        channel: "#sylion-alerts"
```

### 10.6 deploy/monitoring/tempo-config.yaml

```yaml
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: "0.0.0.0:4317"

ingester:
  trace_idle_period: 10s
  max_block_bytes: 1048576

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/traces
```

### 10.7 .claude/settings.local.json

Lokacja: `.claude/settings.local.json`

Konfiguracja Claude Code per-projekt: permissions allowlist, env vars dla
agents, hooks. Plik **nie jest** krytyczny dla runtime SYLION — używany
tylko przez deweloperów Claude Code.

```json
{
  "permissions": {
    "allow": [
      "Bash(npm install:*)",
      "Bash(npm run dev:*)",
      "Bash(pytest:*)",
      "Bash(alembic:*)"
    ],
    "deny": []
  },
  "env": {
    "SYLION_AEIS_ENV": "dev"
  }
}
```

---

## 11. Cross-references

| Plik | Zakres |
|---|---|
| `40_setup_step_by_step.md` | jak skonfigurować od zera |
| `41_environment_variables.md` | env vars używane w configach |
| `02_operational_manual.md` | runbook produkcyjny |
| `04_dla_developera.md` | rozwijanie modułów, dodawanie manifestów |
| `00_architektura_systemu.md` | wysokopoziomowa architektura |
| `01_modul_aeis_advisor.md` | szczegóły AEIS Advisor + jego config |
| `03_governance_audit_compliance.md` | RBAC, JWT, audit log configs |

---

> **Reguły operacyjne**
>
> 1. **Manifest jest jedynym źródłem prawdy** o module — kod musi być z nim
>    zgodny, walidacja w CI.
> 2. **Zmiana manifestu = zmiana kontraktu** — bump `contract_version`
>    minor / major.
> 3. **Config files w git** — wszystkie poza `.env*`, sekretami, secrets/.
> 4. **YAML lint** — `yamllint` przy pre-commit.
> 5. **JSON Schema validation** — manifesty walidowane w CI przez
>    `sylion.contracts.validate_manifests`.
> 6. **Dockerfile lint** — `hadolint` przy pre-commit.
> 7. **Compose lint** — `docker compose config` musi zwrócić exit 0.
