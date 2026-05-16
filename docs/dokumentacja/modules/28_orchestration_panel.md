# 28. Orchestration Panel — Panel konfiguracji meta-orkiestracji
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja modułu `sylion.aeis.advisor.orchestration_config` (sekcja J) oraz
> API REST `/api/v1/orchestration/`. Moduł zarządza 9 domenami konfiguracyjnymi
> sterującymi zachowaniem całego systemu wieloagentowego: routingiem LLM, regułami
> Rady, kadencją audytora, protokołem naprawczym, dispatchem agentów, katalogiem
> testów, regułami formowania zespołów, mapą zdarzeń i rozmowami inter-modeli.

## Spis treści

1. [Cel i lokalizacja](#1-cel-i-lokalizacja)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja i schemat PG](#3-konfiguracja-i-schemat-pg)
4. [Sekcje J1–J9 — domenowe subsystemy](#4-sekcje-j1j9--domenowe-subsystemy)
5. [REST API — endpointy](#5-rest-api--endpointy)
6. [Storage — warstwa danych](#6-storage--warstwa-danych)
7. [Modele danych (_models.py)](#7-modele-danych-_modelspy)
8. [Przykłady użycia](#8-przykłady-użycia)
9. [Weryfikacja i testy](#9-weryfikacja-i-testy)
10. [Cross-references](#10-cross-references)

---

## 1. Cel i lokalizacja

| Pole | Wartość |
|------|---------|
| Pakiet Python | `sylion.aeis.advisor.orchestration_config` |
| Folder | `src/sylion-pipeline/sylion/aeis/advisor/orchestration_config/` |
| Router FastAPI | `src/sylion-pipeline/sylion/api/orchestration_routes.py` |
| Prefix REST | `/api/v1/orchestration/` |
| Schemat PG | `advisor_orchestration` (9 tabel) |
| Migracja Alembic | `alembic/versions/20260426_0002_orchestration_config.py` |
| Manifest | `src/sylion-pipeline/manifests/aeis.advisor.orchestration_config.json` |
| Testy | `tests/aeis/advisor/orchestration_config/test_orchestration_routes.py` |

Moduł `orchestration_config` jest **warstwą konfiguracji meta-orkiestracyjnej** systemu AEIS.
Nie generuje rekomendacji — zamiast tego zarządza parametrami, które rządzą tym jak inne
moduły (engine, council, historia, dispatch) podejmują decyzje. Docelowo panel operatorski
wyświetla i edytuje każdą z 9 sekcji J1–J9 przez dedykowane widgety.

Moduł jest w pełni funkcjonalny bez aktywnego połączenia z bazą danych: używa wbudowanego
magazynu in-memory (`_STORE`) z automatycznym zapasem do PG gdy `SYLION_PG_DSN` jest dostępny.

---

## 2. Architektura modułu

```
orchestration_config/
├── __init__.py          # eksportuje: OrchestrationConfigService, get_orchestration_service
├── _models.py           # 18 dataclass: J1-J9 value objects (LLMJudgeRoutingCell, CouncilRules, …)
├── _db.py               # helpers PG: load/replace/upsert per sekcja (schema: advisor_orchestration)
└── service.py           # OrchestrationConfigService — 30+ metod, singleton thread-safe
```

### 2.1. Wzorzec singleton

```python
_SERVICE: Optional[OrchestrationConfigService] = None
_SVC_LOCK = threading.Lock()

def get_orchestration_service() -> OrchestrationConfigService:
    global _SERVICE
    if _SERVICE is None:
        with _SVC_LOCK:
            if _SERVICE is None:
                _SERVICE = OrchestrationConfigService()
    return _SERVICE
```

Router FastAPI importuje singleton przez `_svc()`, nie przez DI — zachowanie jest zgodne
z pozostałymi serwisami w warstwie Advisor.

### 2.2. Wzorzec PG z fallback

Każda metoda serwisu stosuje ten wzorzec:

1. Próba odczytu z PG (`_pg_call(_db.<fn>)`)
2. Jeśli PG niedostępne lub brak rekordu — fallback do `_STORE` (in-memory)
3. Jeśli `_STORE` pusty — wartość domyślna hardcodowana w metodzie `_default_*`

Flaga `_PG_AVAILABLE` jest ustawiana automatycznie przy pierwszym błędzie PG i pomijana
do końca procesu, co eliminuje zbędne retries przy niedostępnej bazie.

### 2.3. Rejestracja routera

W `src/sylion-pipeline/sylion/api/app.py`:

```python
from sylion.api.orchestration_routes import router as orchestration_router
app.include_router(orchestration_router)
```

---

## 3. Konfiguracja i schemat PG

### 3.1. Zmienne środowiskowe

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `SYLION_PG_DSN` | tak (produkcja) | DSN połączenia z PostgreSQL; fallback in-memory gdy nieobecna |
| `SYLION_DB_URL` | alt. | Alternatywna nazwa DSN (sprawdzana jako fallback) |

### 3.2. Schemat PG — `advisor_orchestration`

Migracja `phase4_0002_orchestration` (bazuje na `phase3_0002_advisor_layer`) tworzy tabele
w schemacie `advisor_orchestration`. Pełna lista tabel (z `advisor_layer.sql`):

| Tabela | Klucz główny | Unikalne | Opis |
|--------|--------------|----------|------|
| `llm_judge_routing` | `config_id UUID` | `(operator_id, recommendation_type, risk_level)` | Macierz routingu LLM (J1) |
| `council_rules` | `rule_id UUID` | `operator_id` | Reguły głosowania Rady (J2) |
| `auditor_cadence` | `cadence_id UUID` | `operator_id` | Harmonogram audytora (J3) |
| `fixer_protocol` | `protocol_id UUID` | `operator_id` | Protokół naprawczy agentów (J4) |
| `dispatch_config` | `dispatch_id UUID` | `operator_id` | Konfiguracja dispatchu wieloagentowego (J5) |
| `test_catalog` | `test_id UUID` | — | Katalog testów (J6) |
| `test_catalog_runs` | `run_id UUID` | — | Historia uruchomień testów (J6) |
| `team_formation_rules` | `rule_id UUID` | — | Reguły formowania zespołów (J7) |
| `active_teams` | `team_id UUID` | — | Aktywne zespoły agentów (J7) |
| `event_map_cache` | `cache_id UUID` | `operator_id` | Cache mapy zdarzeń (J8) |
| `inter_model_conversations` | `config_id UUID` | `operator_id` | Ustawienia rozmów między modelami (J9) |
| `config_kv` | `config_key TEXT` | — | Ogólny magazyn klucz-wartość dla orchestration (JSONB) |

Uruchomienie migracji:

```bash
cd src/sylion-pipeline
alembic upgrade head
```

### 3.3. Domyślny operator_id

Wszystkie tabele używają klucza `operator_id`. Domyślna wartość to:

```
00000000-0000-0000-0000-000000000001
```

Jest to stały UUID zdefiniowany w `_db.py` jako `_DEFAULT_OPERATOR_ID`. W trybie
single-tenant (Etap 1) wystarczy ta jedna wartość.

---

## 4. Sekcje J1–J9 — domenowe subsystemy

### J1 — LLM Judge Routing Matrix

Macierz `(recommendation_type × risk_level) → model_id` definiująca, który model LLM
ocenia rekomendacje danego typu przy danym poziomie ryzyka.

**Domyślne mapowanie:**

| recommendation_type | risk_level | model_id |
|--------------------|------------|----------|
| `cost_optimization` | `low` | `claude-haiku-4-5-20251001` |
| `cost_optimization` | `medium` | `claude-haiku-4-5-20251001` |
| `cost_optimization` | `high` | `claude-sonnet-4-6` |
| `cost_optimization` | `critical` | `claude-opus-4-7` |
| `security` | `high` | `claude-sonnet-4-6` |
| `security` | `critical` | `claude-opus-4-7` |
| (pozostałe) | (wszystkie) | `claude-haiku-4-5-20251001` |

**Presety:**

| Preset | Efekt |
|--------|-------|
| `cost-saving` | Wszystkie komórki → `claude-haiku-4-5-20251001` |
| `balanced` | Domyślna macierz (risk-aware) |
| `aggressive` | Wszystkie komórki → `claude-opus-4-7` |

**Typy rekomendacji** obsługiwane w macierzy:
`cost_optimization`, `scaling`, `security`, `subscription`, `architecture`, `funding`, `onboarding`, `maintenance`

**Poziomy ryzyka:** `low`, `medium`, `high`, `critical`

### J2 — Council Rules

Konfiguracja mechaniki głosowania Rady Modeli.

| Parametr | Domyślna wartość | Opis |
|----------|------------------|------|
| `rank_weights` | Associate(1)=0.6, Engineer(2)=0.8, Senior(3)=1.0, Principal(4)=1.2, Architect(5)=1.5 | Wagi głosów per ranga |
| `critic_gate_enabled` | `true` | Czy Krytyk blokuje przy niskiej pewności |
| `critic_gate_threshold` | `0.6` | Próg pewności Krytyka (0.0–1.0) |
| `quorum_min` | `3` | Minimalna liczba uczestników |
| `quorum_type` | `majority` | Typ kworum: `majority` \| `absolute` \| `supermajority` |

**Wymagania Sentineli per poziom D:**

| Poziom D | Cost Sentinel | Security Sentinel |
|----------|---------------|------------------|
| D3 | nie wymagany | nie wymagany |
| D4 | wymagany | nie wymagany |
| D5 | wymagany | wymagany |

### J3 — Auditor Cadence

| Parametr | Domyślna wartość | Opis |
|----------|------------------|------|
| `tick_frequency_seconds` | `300` | Co ile sekund audytor sprawdza metryki |
| `enabled_dimensions` | 16 wymiarów (patrz poniżej) | Które wymiary audytu są aktywne |
| `phase_boundary_cron` | `0 */4 * * *` | Cron trigger na granicy fazy (co 4h) |

**16 wymiarów audytu** (domyślnie wszystkie aktywne):
`code_quality`, `test_coverage`, `security_posture`, `cost_efficiency`, `performance_budget`,
`api_contract_compliance`, `event_schema_validity`, `preference_drift`, `council_health`,
`escalation_backlog`, `funding_deadlines`, `subscription_roi`, `d_level_distribution`,
`hallucination_rate`, `evidence_pack_completeness`, `agent_error_rate`

### J4 — Fixer Protocol

Konfiguracja protokołu naprawczego w przypadku niepowodzeń agentów.

| Parametr | Domyślna wartość | Opis |
|----------|------------------|------|
| `retry_budgets` | codex=2, kimi=2, claude=2, z_ai=3 | Liczba retry per typ agenta |
| `escalation_path` | `["original_agent", "final_integrator", "operator"]` | Kolejność eskalacji |
| `max_nogo_iterations` | `3` | Maks. cykli "go/no-go" przed eskalacją do operatora |
| `auto_revert_on_critical_security` | `true` | Automatyczny revert przy CRITICAL security event |

### J5 — Multi-Agent Dispatch Config

| Parametr | Domyślna wartość | Opis |
|----------|------------------|------|
| `parallelism_mode` | `wide` | `wide` (bez limitu) \| `capped` (z `max_simultaneous`) |
| `max_simultaneous` | `null` | Limit równoległych agentów (tylko `capped`) |
| `cost_ceiling_usd_per_hour` | `null` | Maks. koszt hourly (USD); null = bez limitu |

**Domyślne reguły alokacji per typ etapu:**

| Etap | Claude | Codex | Kimi |
|------|--------|-------|------|
| `architectural` | 50% | 20% | 30% |
| `production` | 30% | 50% | 20% |
| `testing` | 20% | 40% | 40% |
| `docs` | 60% | 20% | 20% |

**Domyślne uprawnienia sub-agentów:**
`claude=true`, `codex=true`, `kimi=false`, `z_ai=true`

### J6 — Test Catalog

Inwentarz testów modułów Advisor z możliwością wyzwalania uruchomień przez REST.

Każdy `TestEntry` ma:
- `test_id` (UUID)
- `name`, `module`, `suite`, `test_type` (`golden` \| `integration` \| `e2e` \| `sim`)
- `status` (`never_run` \| `pass` \| `fail` \| `skip`)
- `last_run_at`, `last_run_output`

Seeding domyślny tworzy po 3 testy (`golden`, `integration`, `e2e`) dla 5 modułów:
`advisor.engine`, `advisor.preferences`, `advisor.funding`, `advisor.role_resolver`, `advisor.council`

### J7 — Team Formation Rules

Reguły automatycznego formowania zespołów agentów na podstawie wzorca w komunikacie commit.

| Pole | Opis |
|------|------|
| `trigger_pattern` | Regex na prefiks commit message |
| `agent_types` | Typy agentów w zespole |
| `lifetime` | `ephemeral` (rozwiązany po zadaniu) \| `persistent` |
| `action` | Akcja do wykonania (np. `spawn_audit_team`) |
| `enabled` | Czy reguła aktywna |

**Domyślne reguły:**
- `^\[advisor\]\[claude\]\[engine\]` → spawn `[z_ai, claude]`
- `^\[advisor\]\[kimi\]` → spawn `[kimi, z_ai]`

### J8 — Event Map

Dynamiczna mapa zdarzeń przepływających przez moduły Advisor. Składa się z:
- `nodes` — moduły emitujące/subskrybujące zdarzenia
- `edges` — pary (emitter, topic, subscriber) z metryką `events_per_minute`

**Wbudowane krawędzie:**

| Emitter | Topic | Subscriber |
|---------|-------|-----------|
| `advisor.engine` | `aeis.advisor.card.issued` | `advisor.actions` |
| `advisor.engine` | `aeis.advisor.card.issued` | `advisor.history` |
| `advisor.actions` | `aeis.advisor.action.recorded` | `advisor.preferences` |
| `advisor.actions` | `aeis.advisor.action.recorded` | `advisor.history` |
| `advisor.preferences` | `aeis.advisor.preference.updated` | `advisor.engine` |
| `advisor.funding` | `aeis.advisor.funding.grant.matched` | `advisor.engine` |

### J9 — Inter-Model Conversation Settings

Ustawienia eksperymentalnych rozmów między modelami LLM (domyślnie wyłączone).

| Parametr | Domyślna wartość | Opis |
|----------|------------------|------|
| `enabled` | `false` | Czy rozmowy między modelami są aktywne |
| `max_turns` | `4` | Maks. rund rozmowy |
| `arbiter_model_id` | `null` | Model rozstrzygający spory |
| `disagreement_voting` | `true` | Głosowanie przy rozbieżności między modelami |

---

## 5. REST API — endpointy

Wszystkie endpointy działają pod prefixem `/api/v1/orchestration/`.
Pełna lista 24 endpointów (9 grup + health):

### J1 — LLM Judge Routing

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/llm-judge-routing` | Pobierz bieżącą macierz routingu |
| `PUT` | `/llm-judge-routing` | Aktualizuj całą macierz + preset |
| `POST` | `/llm-judge-routing/reset-cell` | Resetuj jedną komórkę do domyślnej |
| `POST` | `/llm-judge-routing/preset/{preset}` | Zastosuj preset (`cost-saving`\|`balanced`\|`aggressive`) |

### J2 — Council Rules

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/council-rules` | Pobierz reguły Rady |
| `PUT` | `/council-rules` | Aktualizuj reguły Rady |
| `POST` | `/council-rules/simulate-vote` | Symulacja głosowania z podanymi głosami |

### J3 — Auditor Cadence

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/auditor-cadence` | Pobierz konfigurację kadencji |
| `PUT` | `/auditor-cadence` | Aktualizuj kadencję |
| `POST` | `/auditor-cadence/trigger-now` | Natychmiastowe wyzwolenie audytu |

### J4 — Fixer Protocol

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/fixer-protocol` | Pobierz protokół naprawczy |
| `PUT` | `/fixer-protocol` | Aktualizuj protokół naprawczy |

### J5 — Dispatch Config

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/dispatch-config` | Pobierz konfigurację dispatchu |
| `PUT` | `/dispatch-config` | Aktualizuj konfigurację dispatchu |

### J6 — Test Catalog

| Metoda | Ścieżka | Query params | Opis |
|--------|---------|-------------|------|
| `GET` | `/test-catalog` | `module`, `status`, `test_type` | Lista testów z filtrowaniem |
| `GET` | `/test-catalog/runs` | `limit` (1–100, domyślnie 20) | Historia uruchomień |
| `POST` | `/test-catalog/run-now` | — | Body: `{test_id?, suite?}` — wyzwól test |

### J7 — Team Formation Rules

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/team-formation-rules` | Reguły + aktywne zespoły |
| `PUT` | `/team-formation-rules` | Zastąp całą listę reguł |
| `POST` | `/team-formation-rules` | Dodaj jedną regułę |

### J8 — Event Map

| Metoda | Ścieżka | Query params | Opis |
|--------|---------|-------------|------|
| `GET` | `/event-map` | `topic_prefix` | Mapa zdarzeń (z opcjonalnym filtrem) |
| `GET` | `/event-map-cache` | `topic_prefix` | Alias `event-map` (cache) |

### J9 — Inter-Model Conversation

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/inter-model-conversation` | Pobierz ustawienia |
| `PUT` | `/inter-model-conversation` | Zaktualizuj ustawienia |

### Health

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `GET` | `/health` | Status modułu: `{"status": "ok", "module": "sylion.aeis.advisor.orchestration_config"}` |

---

## 6. Storage — warstwa danych

### 6.1. Hierarchia źródeł danych

Dla każdej sekcji J1–J9, dane są odczytywane i zapisywane w następującej kolejności:

```
Odczyt:
  1. PG (advisor_orchestration.*) → jeśli wynik to zwróć
  2. _STORE (in-memory dict) → jeśli klucz istnieje to zwróć
  3. wartość domyślna hardcodowana w _default_*()

Zapis:
  1. _STORE[key] = payload
  2. _pg_call(_db.upsert_*, payload)  ← fire-and-forget, błąd logowany + pomijany
```

### 6.2. Klucze _STORE

| Klucz | Sekcja |
|-------|--------|
| `llm_judge_routing` | J1 |
| `council_rules` | J2 |
| `auditor_cadence` | J3 |
| `fixer_protocol` | J4 |
| `dispatch_config` | J5 |
| `test_catalog` | J6 |
| `test_catalog_runs` | J6 |
| `team_formation_rules` | J7 |
| `active_teams` | J7 |
| `inter_model_conversation` | J9 |

Mapa zdarzeń (J8) jest obliczana dynamicznie i opcjonalnie cachowana w PG.

### 6.3. Thread-safety

`_STORE` jest chroniony `threading.Lock()` przez funkcje `_store_get` i `_store_set`.
`OrchestrationConfigService` nie ma własnego locka — operacje na serwisie są bezpieczne
bo wszystkie zapisy wchodzą przez `_store_set`.

---

## 7. Modele danych (_models.py)

| Dataclass | Sekcja | Kluczowe pola |
|-----------|--------|---------------|
| `LLMJudgeRoutingCell` | J1 | `recommendation_type`, `risk_level`, `model_id`, `enabled` |
| `LLMJudgeRoutingMatrix` | J1 | `cells: List[LLMJudgeRoutingCell]`, `preset` |
| `RankWeight` | J2 | `rank: int (1-5)`, `label`, `weight: float` |
| `SentinelRequirement` | J2 | `d_level`, `cost_required`, `security_required` |
| `CouncilRules` | J2 | `rank_weights`, `critic_gate_enabled`, `quorum_min`, `quorum_type`, `sentinel_requirements` |
| `AuditorCadence` | J3 | `tick_frequency_seconds`, `enabled_dimensions`, `phase_boundary_cron` |
| `AgentRetryBudget` | J4 | `agent_type`, `retry_limit` |
| `FixerProtocol` | J4 | `retry_budgets`, `escalation_path`, `max_nogo_iterations`, `auto_revert_on_critical_security` |
| `StageAllocationRule` | J5 | `stage_type`, `claude_ratio`, `codex_ratio`, `kimi_ratio` |
| `DispatchConfig` | J5 | `parallelism_mode`, `max_simultaneous`, `stage_allocation_rules`, `cost_ceiling_usd_per_hour` |
| `TestEntry` | J6 | `test_id`, `name`, `module`, `suite`, `test_type`, `status` |
| `TestCatalogRun` | J6 | `run_id`, `test_id`, `suite`, `status`, `triggered_at`, `output` |
| `TeamFormationRule` | J7 | `rule_id`, `trigger_pattern`, `agent_types`, `lifetime`, `action`, `enabled` |
| `ActiveTeam` | J7 | `team_id`, `rule_id`, `agent_types`, `current_task`, `lifetime` |
| `EventMapNode` | J8 | `module_id`, `events_emitted`, `events_subscribed` |
| `EventMapEdge` | J8 | `emitter`, `topic`, `subscriber`, `events_per_minute` |
| `EventMap` | J8 | `nodes`, `edges`, `generated_at` |
| `InterModelConversationSettings` | J9 | `enabled`, `max_turns`, `arbiter_model_id`, `disagreement_voting` |

---

## 8. Przykłady użycia

### 8.1. Pobranie macierzy routingu LLM

```bash
curl -s http://127.0.0.1:8010/api/v1/orchestration/llm-judge-routing | python3 -m json.tool
```

Odpowiedź (fragment):

```json
{
  "cells": [
    {
      "recommendation_type": "security",
      "risk_level": "critical",
      "model_id": "claude-opus-4-7",
      "enabled": true,
      "is_default": true
    }
  ],
  "preset": "balanced"
}
```

### 8.2. Zastosowanie presetu cost-saving

```bash
curl -s -X POST http://127.0.0.1:8010/api/v1/orchestration/llm-judge-routing/preset/cost-saving
```

Efekt: wszystkie komórki macierzy zmienione na `claude-haiku-4-5-20251001`.

### 8.3. Reset jednej komórki do domyślnej

```bash
curl -s -X POST http://127.0.0.1:8010/api/v1/orchestration/llm-judge-routing/reset-cell \
  -H "Content-Type: application/json" \
  -d '{"recommendation_type": "security", "risk_level": "critical"}'
```

### 8.4. Symulacja głosowania Rady

```bash
curl -s -X POST http://127.0.0.1:8010/api/v1/orchestration/council-rules/simulate-vote \
  -H "Content-Type: application/json" \
  -d '{
    "votes": [
      {"rank": 5, "vote": "for"},
      {"rank": 3, "vote": "for"},
      {"rank": 2, "vote": "against"},
      {"rank": 1, "vote": "abstain"}
    ]
  }'
```

Odpowiedź:

```json
{
  "outcome": "approved",
  "quorum_met": true,
  "for_weight": 2.5,
  "against_weight": 0.8,
  "participating": 3,
  "quorum_min": 3
}
```

### 8.5. Natychmiastowy trigger audytu

```bash
curl -s -X POST http://127.0.0.1:8010/api/v1/orchestration/auditor-cadence/trigger-now
```

Odpowiedź:

```json
{
  "audit_id": "f3a1b2c4-...",
  "triggered_at": "2026-04-26T10:00:00Z",
  "status": "triggered"
}
```

### 8.6. Wyzwolenie testu z katalogu

```bash
# wyzwól wszystkie testy z suite "golden"
curl -s -X POST http://127.0.0.1:8010/api/v1/orchestration/test-catalog/run-now \
  -H "Content-Type: application/json" \
  -d '{"suite": "golden"}'

# pobierz historię uruchomień
curl -s "http://127.0.0.1:8010/api/v1/orchestration/test-catalog/runs?limit=5"
```

### 8.7. Aktualizacja protokołu naprawczego

```bash
curl -s -X PUT http://127.0.0.1:8010/api/v1/orchestration/fixer-protocol \
  -H "Content-Type: application/json" \
  -d '{
    "retry_budgets": [
      {"agent_type": "codex", "retry_limit": 3},
      {"agent_type": "claude", "retry_limit": 2}
    ],
    "escalation_path": ["original_agent", "operator"],
    "max_nogo_iterations": 5,
    "auto_revert_on_critical_security": true
  }'
```

### 8.8. Mapa zdarzeń z filtrem

```bash
# tylko zdarzenia z prefixem "aeis.advisor"
curl -s "http://127.0.0.1:8010/api/v1/orchestration/event-map?topic_prefix=aeis.advisor"
```

---

## 9. Weryfikacja i testy

### 9.1. Testy integracyjne

Plik: `tests/aeis/advisor/orchestration_config/test_orchestration_routes.py` (350 linii)

Testy pokrywają:
- Każdy z 9 endpointów J1–J9 (GET + PUT/POST)
- Presety J1: `cost-saving`, `balanced`, `aggressive`
- Symulację głosowania J2 (quorum: met vs not met)
- Trigger audytu J3
- Filtrowanie katalogu testów J6 po `module`, `status`, `test_type`
- Dodawanie reguł J7
- Filtrowanie event-map po `topic_prefix` (J8)
- Test rejestracji routera w `app.py`

### 9.2. Weryfikacja curl (9/9)

Raport z weryfikacji: `docs/claude_parallel/aeis_advisor/_handoff/codex_section_j_integration_report.md`

Endpointy zweryfikowane:
- `GET /health` → 200 OK
- `GET /llm-judge-routing` → 200, cells obecne
- `PUT /llm-judge-routing` → 200, preset zaktualizowany
- `POST /llm-judge-routing/preset/cost-saving` → 200, wszystkie haiku
- `GET /council-rules` → 200, rank_weights obecne
- `POST /council-rules/simulate-vote` → 200, outcome present
- `GET /auditor-cadence` → 200, tick_frequency_seconds present
- `POST /auditor-cadence/trigger-now` → 200, audit_id present
- `GET /dispatch-config` → 200, stage_allocation_rules present

### 9.3. Rejestracja routera

```bash
python3 -c "
from sylion.api.app import app
paths = [r.path for r in app.routes]
orch = [p for p in paths if '/orchestration' in p]
assert len(orch) >= 9, f'Expected 9+ orchestration routes, got {len(orch)}'
print('OK:', orch)
"
```

---

## 10. LLM Routing Matrix Editor — panel frontendowy (sprint3)

Commit `f32713c` dodał stronę `/orchestration/llm-routing` z edytorem macierzy routingu LLM.

### 10.0.1. Lokalizacja

- `src/sylion-frontend/src/app/(app)/orchestration/llm-routing/page.tsx` — `LLMRoutingPage`

### 10.0.2. Funkcje

| Funkcja | Opis |
|---------|------|
| Wyswietlanie macierzy | Tabela celi `domain x risk_level` z aktualnym modelem per kombo |
| Edycja celi | Inline zmiana modelu dla konkretnej domeny i poziomu ryzyka |
| Domain filter | Filtruj macierz po domenie (fintech, healthcare, gaming, ... 15 opcji) |
| Presety | `cost-saving` (Haiku dla wszystkich), `balanced` (domyslny mix), `aggressive` (Opus dla wszystkich) |
| Bulk update | Zmiana wszystkich celi z wybranym `risk_level` na jeden model jednym kliknieciem |
| Save matrix | POST do `orchestrationApi.updateLLMRouting(cells)` — zapisuje lokalnie zmodyfikowane cele |
| Preview diff | Podglad jakie cele zostana zmienione przed zapisem |

### 10.0.3. Dostepne domeny w edytorze

15 domen: all, fintech, healthcare, ecommerce, saas, marketplace, gaming, iot, media, legal, education, government, ngo, startup, enterprise. Kazda domena ma swoj zestaw typow rekomendacji (`types[]`) filtrowacych widoczne wiersze macierzy.

### 10.0.4. API backend

Edytor korzysta z:
- `orchestrationApi.getLLMRouting()` — pobiera aktualna macierz (`GET /api/v1/orchestration/llm-routing`)
- `orchestrationApi.updateLLMRouting(cells)` — zapisuje zmiany (`PUT /api/v1/orchestration/llm-routing`)
- `api.listRegisteredModels()` — pobiera dostepne modele (z `08_role_resolver.md`)

### 10.0.5. Modele dostepne w dropdown

Fallback (gdy brak backendowych): `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-7`, `gpt-4o-mini`, `gpt-4o`. Jesli backend zwroci liste z `listRegisteredModels()`, lista dynamiczna.

---

## 11. Cross-references

### 11.1. Powiazane moduly backend

| Moduł | Dokument | Relacja |
|-------|----------|---------|
| Engine | [`05_engine.md`](05_engine.md) | J1 (routing LLM) bezpośrednio kontroluje model wybierany przez Engine do oceny kart |
| Council Hybrid | [`33_council_hybrid.md`](33_council_hybrid.md) | J2 (council rules) jest nadrzędna konfiguracja względem domyślnych reguł CouncilHybrid |
| LLM Pool Routing | [`34_llm_pool_routing.md`](34_llm_pool_routing.md) | J1 macierz jest dynamiczna nadpisywaną wersją statycznej routing matrix z 34 |
| Auditor | [`27_audit_viewer.md`](27_audit_viewer.md) | J3 (kadencja) kontroluje harmonogram audytora który generuje wpisy widoczne w `/audit` |
| Events | [`04_events.md`](04_events.md) | J8 (event map) agreguje topologie zdarzeń z modułu events |
| History | [`06_history.md`](06_history.md) | J7 (team formation rules) może triggerować zespoły na podstawie prefixów commit |

### 11.2. Powiazane frontendy

| Komponent | Gdzie uzywany |
|-----------|---------------|
| Orchestration section w `AppSidebar` | `src/sylion-frontend/src/components/layout/AppSidebar.tsx` |
| LLM Routing Matrix Editor | `src/sylion-frontend/src/app/(app)/orchestration/llm-routing/page.tsx` |

### 11.3. D-ladder

Zmiana J2 (council rules) na poziomie, ktory zmienia quorum lub progi Sentineli, jest
decyzja D4 (`cost_required: true`). Zmiana J1 (model routing) wplywajaca na koszty
operacyjne moze byc D3. Patrz: [`31_d_ladder_complete.md`](31_d_ladder_complete.md) §4.

### 11.4. Taksonomia zdarzen

Zdarzenia emitowane posrednio przez orchestration_config (przez trigger audytu J3):
`aeis.audit.triggered` — szczegoly w [`30_event_taxonomy_full.md`](30_event_taxonomy_full.md).

### 11.5. Governance

Modul operuje na `operator_id=00000000-0000-0000-0000-000000000001` (single-tenant Etap 1).
Przy przejsciu na multi-tenant wszystkie endpointy musza otrzymac JWT z `operator_id` w claimie.
Patrz: [`03_governance_audit_compliance.md`](../03_governance_audit_compliance.md) §5.
