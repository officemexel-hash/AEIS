# Moduł `sylion.aeis.advisor.engine`
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

Dokumentacja techniczna silnika doradczego AEIS — rule engine, LLM-as-judge, D-ladder, builder kart i Evidence Pack.

---

## Spis treści

1. [Cel modułu](#1-cel-modułu)
2. [Architektura modułu](#2-architektura-modułu)
3. [Konfiguracja](#3-konfiguracja)
4. [Funkcje (fasada serwisu)](#4-funkcje-fasada-serwisu)
5. [Eventy](#5-eventy)
6. [Tabele bazy danych](#6-tabele-bazy-danych)
7. [Przykład użycia](#7-przykład-użycia)
8. [Komendy weryfikacyjne](#8-komendy-weryfikacyjne)
9. [Troubleshooting](#9-troubleshooting)
10. [Powiązania](#10-powiązania)

---

## 1. Cel modułu

`sylion.aeis.advisor.engine` jest sercem warstwy doradczej. Subskrybuje 16 kanonicznych lifecycle hooks (H01–H16), 11 companion topics oraz 4 wewnętrzne advisor-eventy (preferences, pricing, subscription ROI). Dla każdego eventu pipeline:

1. **rule_engine.match_event_to_rules** — dopasowuje topic + payload do reguł zdefiniowanych deklaratywnie w DSL i zapisanych w `advisor_engine.rule_definitions`.
2. **CardContext build** — buduje kontekst karty (preferencje operatora, snapshot pricing/history/council, ryzyko, koszt, blast radius, autonomia).
3. **LLM judge — rationale call** — woła model judge przez `llm_judge.client`; każdy call zapisuje pełny prompt + odpowiedź do `advisor_engine.llm_judge_audit` (forever retention).
4. **Confidence calculator** — 4 komponenty (council_match, history_match, pricing_quality, historical_acceptance) z mnożnikiem `0.8` dla local fallback.
5. **D-ladder assigner** — domyślny D-level per `recommendation_type` + 5 reguł upgrade U1-U5 (cost magnitude, blast radius, reversibility, hard preferences, autonomy), cap D5.
6. **Evidence pack gate** — D5/D4 → `d5_full`, D3 + cost/subscription/funding/autonomy/scaling/final_approval → `d3_light`, w pozostałych przypadkach pomija.
7. **Evidence pack creation** — gdy wymagany, woła trzy osobne LLM calls (rationale, rollback_plan, fidelity_test) i zapisuje pakiet do `advisor_evidence.evidence_packs`.
8. **Card builder** — buduje header (40+ pól) + body (DecisionCard / FundingCard / SecurityCard / ScalingCard / OnboardingCard), waliduje przez `card_builder.validators`.
9. **Persist + emit** — wstawia rekord do `advisor_engine.recommendations`, zapisuje firing do `rule_firing_history`, emituje `recommendation_emitted` (lub `validation_failed` w razie błędów).

Drugi cel: **synchroniczna bramka** dla H13 (`production.deploy_requested`) i H16 (`final_approval.requested`). Endpoint wołający `evaluate_gate(...)` blokuje się do `timeout_s` i otrzymuje `GateDecision(decision=proceed|block|defer_to_human_gate)`. Karta D5 lub recommendation_type `REC_TYPE_BLOCK_PRODUCTION_DEPLOY` skutkuje statusem `block` (HTTP 423 w warstwie REST).

Trzeci cel: **lifecycle Evidence Pack** — operator może podpisywać pakiet (`sign_evidence_pack`) i finalizować go (`finalize_evidence_pack`). Pakiet bez kompletu sygnatur dla D5 nie pozwala na proceed bramki produkcyjnej (logika sentinel + governance).

---

## 2. Architektura modułu

### 2.1. Pliki źródłowe

Wszystkie ścieżki względem `src/sylion-pipeline/sylion/aeis/advisor/engine/`.

| Plik / katalog | Rola |
| --- | --- |
| `service.py` | `AdvisorEngineService` — singleton fasada (`get_engine_service()`, `reset_engine_service()`); metody `attach_to_event_bus`, `submit_event`, `evaluate_gate`, `list_recommendations`, `get_recommendation`, `list_audits_for_card`, `get_evidence_pack`, `sign_evidence_pack`, `finalize_evidence_pack`, `list_rules`, `invalidate_rule_cache` |
| `orchestrator.py` | `process_event(topic, payload, operator_id, ...)` — pełen pipeline event → karta(y); helpery `_build_card_context`, `_call_rationale_judge`, `_create_evidence_pack` |
| `_db.py` | Insert/fetch dla `recommendations`, `llm_judge_audit`, `rule_definitions`, `rule_firing_history`, `evidence_packs`, `evidence_pack_signatures`; helpery serializacji envelope; sprint3 dodał: `fetch_recent_audit_entries(limit)`, `fetch_avg_confidence(operator_id, limit)`, `fetch_human_gate_metrics(operator_id)`, `fetch_configuration_counts()` |
| `_models.py` | `AdvisorCardEnvelope`, `AdvisorCardHeader` (40+ pól), `DecisionCard`, `FundingCard`, `SecurityCard`, `ScalingCard`, `OnboardingCard`, `Money`, `Impact`, `Alternative`, `EvidencePack`, `Rule`, `RuleFiring`, `CardContext`; stałe `CARD_TYPES`, `RISK_LEVELS`, `CONFIDENCE_LABELS`, `CARD_SOURCES`, `DECISION_LEVELS`, `PRIORITIES`, `PUSH_PRIORITIES`, `IMPACT_CONFIDENCES`, `CARD_ACTIONS`, `GATE_DECISIONS`; helper `confidence_label_for(score)` |
| `grpc_server.py` | gRPC servicer mapujący proto na fasadę |
| `rule_engine/` | `default_rules.py` (seed), `dsl.py` (eval declarative DSL), `loader.py` (cache + invalidate), `matcher.py` (`match_event_to_rules`) |
| `llm_judge/` | `client.py` (HTTP call + stub fallback), `prompts.py` (rationale, evidence_rationale/rollback/fidelity, alternatives_ranking, risk_assessment), `parser.py` (`parse_json_response`), `audit.py` (`record_audit`), `fallback.py` (`resolve_judge_model`, local fallback) |
| `d_ladder/assigner.py` | `assign_d_level` z mapą domyślną i U1-U5 |
| `d_ladder/evidence_gate.py` | `EvidencePackRequirement` enum + `determine_evidence_pack_requirement` |
| `card_builder/header.py` | `build_header(...)` |
| `card_builder/decision_card.py` | `build_decision_card(...)` |
| `card_builder/funding_card.py` | `build_funding_card(...)` |
| `card_builder/envelope.py` | `build_envelope(header, body)` |
| `card_builder/validators.py` | `validate_envelope` + `EnvelopeValidationError` |
| `confidence/calculator.py` | `calculate_confidence` (4 komponenty + 0.8 multiplier) |
| `confidence/components/` | `council_match.py`, `history_match.py`, `pricing_quality.py`, `historical_acceptance.py` |
| `lifecycle/subscribers.py` | `register_lifecycle_subscribers(event_bus)` — 16 hooks + 11 companion + 4 internal |
| `lifecycle/handlers.py` | `dispatch_event(event)` — woła `process_event` i koniecznie persistuje firing |
| `lifecycle/sync_gate.py` | `evaluate_gate(...)` — synchroniczna bramka dla H13/H16 |

### 2.2. Zależności

Manifest `aeis.advisor.engine.json#depends_on`:
- `sylion.aeis.advisor.preferences`,
- `sylion.aeis.advisor.pricing`,
- `sylion.aeis.advisor.history`,
- `sylion.aeis.advisor.role_resolver`,
- `sylion.governance.council_hybrid`.

Pośrednie:
- `sylion.aeis.advisor._db` — wspólny pool psycopg.
- `sylion.core.event_bus.SylionEvent`, `sylion.core.event_backbone`, `sylion.core.event_bus_factory`.

### 2.3. Storage

| Schemat | Tabele |
| --- | --- |
| `advisor_engine` | `recommendations`, `llm_judge_audit`, `rule_definitions`, `rule_firing_history` |
| `advisor_evidence` | `evidence_packs`, `evidence_pack_signatures` |

Custom enum types: `card_type`, `card_source`, `confidence_label`, `risk_level`, `decision_level`, `priority`, `card_action`, `impact_confidence`.

**Uwaga dot. kolumn BOOLEAN (sprint2, commit 7e3b38d):**
Kolumny BOOLEAN w `recommendations` (`history_based`, `dont_learn`, `human_gate_required`,
`mobile_allowed`, `requires_biometric`, `used_local_fallback`) oraz w `llm_judge_audit`
(`was_local_fallback`) i `rule_definitions` (`is_active`) są przekazywane do psycopg jako
Python `bool` (nie `int()`). Psycopg3 obsługuje natywny Python `bool` dla kolumn BOOLEAN —
użycie `int()` było reliktem kompatybilności z SQLite i zostało usunięte.

### 2.4. Workery / harmonogram

- `register_lifecycle_subscribers(event_bus)` — bootstrap subskrypcji. Wywoływany raz przez `attach_to_event_bus`.
- `dispatch_event` — synchroniczny handler per event z thread-pool-a EventBus.
- `evaluate_gate` — synchroniczne wywołanie z endpointu, default `timeout_s=5.0`.
- Brak osobnych workerów (rule cache invalidate jest manualny przez `invalidate_rule_cache()` lub `force=True` przy `load_active_rules`).

### 2.5. LOC budget

Manifest `loc_max=3500`, `loc_max_default=1500`. Klasa decyzji: D3 (Evidence Pack: `docs/claude_parallel/aeis_advisor/_handoff/evidence_pack_b003_loc_budget.md`). Uzasadnienie: silnik agreguje rule_engine + d_ladder + confidence + card_builder + service w spójną granicę emisji karty.

---

## 3. Konfiguracja

### 3.1. Zmienne środowiskowe

| Zmienna | Opis |
| --- | --- |
| `ADVISOR_PG_DSN` | DSN wspólnego pool-a |
| `SYLION_EVENT_BUS_URL` | URL Kafki/Redpandy |
| `ADVISOR_LLM_JUDGE_DEFAULT_MODEL` | Override default rationale judge model (fallback: `claude-sonnet-4-6`) |
| `ADVISOR_LLM_JUDGE_LOCAL_FALLBACK_MODEL` | Default local fallback (np. `qwen-coder:7b` przez Ollama) |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, ... | Konsumowane przez `llm_judge.client` (proxy do pricing adapters lub bezpośredni HTTP) |

### 3.2. Wartości domyślne

- `confidence_score` clipped do `[0, 1]`.
- `LOCAL_FALLBACK_MULTIPLIER = 0.8` (`confidence/calculator.py`).
- `COMPONENT_WEIGHTS = {"council_match": 0.4, "history_match": 0.4, "pricing_quality": 0.2}`.
- D-ladder default mapping (`d_ladder/assigner.py:_DEFAULT_MAPPING`) — np. `REC_TYPE_BUDGET_CONFIG=D2`, `REC_TYPE_AUTONOMY_POLICY=D3`, `REC_TYPE_BLOCK_PRODUCTION_DEPLOY=D5`.
- D-ladder funding default mapping (`_FUNDING_DEFAULT_MAPPING`) — np. `FUNDING_FORM_COMPANY=D3`, `FUNDING_DEADLINE_WARNING=D1`.
- Hard change preference keys (`_HARD_CHANGE_PREFERENCE_KEYS`) — 8 kluczy → bump min D3 przez U4.
- Cost thresholds (U1): `>10_000=+3`, `>1_000=+2`, `>100=+1`.
- U3 reversibility: `rollback>=1d=+1`, `rollback_data_loss → min D4`.
- U5 autonomy: `manual` + non-D0 → min D3.
- Evidence pack template: `d5_full` dla D4/D5, `d3_light` dla D3 cost/subscription/funding/autonomy/scaling/final_approval, w pozostałych przypadkach `none`.
- Rule firing decision: `emit`, `failed`, `schema_validation_failed`, `skip_low_confidence`, `skip_blocked_provider` (lista enumeratywna).

### 3.3. Pliki konfiguracyjne

- Reguły domyślne: `rule_engine/default_rules.py` (seed → `seed_default_rules()` na starcie singletona).
- Prompty LLM: `llm_judge/prompts.py` (rationale, evidence_rationale, evidence_rollback, evidence_fidelity, alternatives_ranking, risk_assessment).

---

## 4. Funkcje (fasada serwisu)

`AdvisorEngineService` jest singleton — `get_engine_service()` wywołuje `init_engine_schema()` (no-op w PG-only) i `seed_default_rules()`.

### 4.1. `attach_to_event_bus(event_bus) -> int`

Subskrybuje `dispatch_event` na 31 topic-ach (16 hooks + 11 companion + 4 internal advisor). Zwraca liczbę aktywnych subskrypcji. Idempotentne wewnątrz singletona.

### 4.2. `submit_event(*, topic, payload, operator_id, triggering_event_id="") -> list[dict]`

Driver dla testów + REST adapterów. Woła `process_event(...)` i konwertuje envelope na dict-y.

### 4.3. `evaluate_gate(*, topic, payload, operator_id, timeout_s=5.0, triggering_event_id="") -> GateDecision`

Synchroniczna bramka (H13/H16). Zwraca dataclass:
- `decision: "proceed" | "block" | "defer_to_human_gate"`,
- `blocking_card_id: str`,
- `created_human_gate_ticket_id: str`,
- `reason: str`.

Logika bloku: `recommendation_type == "REC_TYPE_BLOCK_PRODUCTION_DEPLOY"` lub `card.header.d_level == "D5"`. Logika defer: `recommendation_type == "REC_TYPE_HUMAN_GATE_BATCH"`.

W razie wyjątku w pipeline zwraca `proceed` z `reason="engine_error:..."` (fail-open dla safety endpoint-a).

### 4.4. `list_recommendations(*, operator_id, limit=50) -> list[dict]`

Zwraca karty operatora od najnowszej. Każdy element to dict z `envelope_version`, `header` (40+ pól), `body` (JSONB).

### 4.5. `get_recommendation(*, card_id) -> dict | None`

Pojedyncza karta po `card_id`.

### 4.6. `list_audits_for_card(*, card_id) -> list[dict]`

Wszystkie wpisy `llm_judge_audit` powiązane z kartą (sortowane `created_at ASC`). Każdy zawiera **pełny prompt i pełną odpowiedź** modelu (forever retention).

### 4.7. `get_evidence_pack(*, pack_id) -> dict | None`

Zwraca pakiet + `signatures` (lista podpisów).

### 4.8. `sign_evidence_pack(*, pack_id, signer_id, signer_role, signature_payload) -> str`

Insertuje wiersz do `advisor_evidence.evidence_pack_signatures`. `signer_role` ∈ `{"operator", "council_member", "governance", "sentinel"}`.

### 4.9. `finalize_evidence_pack(*, pack_id) -> bool`

Aktualizuje `evidence_packs.status="finalized"` i `finalized_at=NOW()`. Zwraca `False` gdy pakiet nie istnieje.

### 4.10. `list_rules() -> list[dict]`

Wymusza `force=True` reload cache, zwraca wszystkie aktywne reguły (z DSL precondition).

### 4.11. `invalidate_rule_cache() -> None`

Kasuje `loader._cache`.

---

### 4.12. gRPC Servicer — `EngineServicer` (sprint3)

Plik: `sylion/aeis/advisor/engine/grpc_server.py`. Cienka warstwa RPC mapująca proto na in-process `AdvisorEngineService`. Importuje stubs z `_generated/engine_pb2_grpc`; jeśli brak — degrades gracefully (stub=`object`).

| RPC | Opis |
|-----|------|
| `ListRecommendations(ListRecommendationsRequest)` | Woła `list_recommendations(operator_id, limit)`. Zwraca `ListRecommendationsResponse{recommendations[]}`. |
| `GetCard(GetCardRequest{card_id})` | Woła `get_recommendation(card_id)`. Jeśli brak → `NOT_FOUND`. Zwraca `GetCardResponse{card}`. |
| `RecordAction(RecordActionRequest)` | Woła `actions_service.HandleAction(...)`. Zwraca `RecordActionResponse` z polami: `action_event_id`, `soft_learning_triggered`, `hard_learning_pending_confirmation`, `created_human_gate_ticket_id`, `created_masterplan_proposal_id`, `saved_preference_id`, `error_message`, `recorded_at`. |
| `FinalizeEvidence(FinalizeEvidenceRequest{evidence_pack_id})` | Woła `finalize_evidence_pack(pack_id)`. Zwraca `FinalizeEvidenceResponse`. |

Rejestracja serwera: `register_engine_service(server, service=None) -> bool` — zwraca `False` gdy brak stubów.

---

## 5. Eventy

### 5.1. Emitowane (manifest `events_emit`)

| Topic | Trigger | Kluczowe pola payload |
| --- | --- | --- |
| `aeis.advisor.engine.recommendation_emitted` | Pomyślny insert karty | `card_id`, `rule_id`, `operator_id`, `risk_level`, `d_level`, `card_type`, `project_id`, `evidence_pack_id` |
| `aeis.advisor.engine.recommendation_skipped` | Reguła odrzuciła kartę (np. low confidence) | `rule_id`, `reason`, `topic` |
| `aeis.advisor.engine.llm_judge_call_started` | Przed wysyłką do modelu | `audit_id`, `model_id`, `purpose` |
| `aeis.advisor.engine.llm_judge_call_completed` | Sukces, audit zapisany | `audit_id`, `model_id`, `cost_usd`, `latency_ms` |
| `aeis.advisor.engine.llm_judge_call_failed` | Wyjątek modelu | `audit_id`, `model_id`, `error` |
| `aeis.advisor.engine.confidence_calculated` | Po `calculate_confidence` | `card_id`, `final_score`, `breakdown` |
| `aeis.advisor.engine.evidence_pack_required` | `_create_evidence_pack` | `evidence_pack_id`, `decision_class`, `d_level`, `operator_id`, `pack_template` |
| `aeis.advisor.engine.evidence_pack_finalized` | `finalize_evidence_pack` | `evidence_pack_id` |
| `aeis.advisor.engine.deploy_blocked` | Gate `block` | `card_id`, `reason` |
| `aeis.advisor.engine.deploy_proceeded` | Gate `proceed` | `event_id`, `topic` |
| `aeis.advisor.engine.deploy_deferred_to_human_gate` | Gate `defer` | `card_id`, `ticket_id` |
| `aeis.advisor.engine.local_fallback_used` | Lokalny model judge | `card_id`, `operator_id` |
| `aeis.advisor.engine.cost_ceiling_hit` | Próg kosztu w pricing | `operator_id`, `provider_id`, `current_usd`, `ceiling_usd` |
| `aeis.advisor.events.validation_failed` | Schema validation envelope | `errors`, `rule_id`, `topic` |

### 5.2. Subskrybowane

Manifest deklaruje 21 topic-ów (16 hooks + 5 companion zawężonych do listy poniżej):

```
aeis.system.model_setup_requested, aeis.system.api_provider_setup_requested,
aeis.system.budget_config_requested, aeis.idea.intake.completed,
aeis.idea.sot_model_selection_requested, aeis.council.formation_requested,
aeis.system.autonomy_policy_change_requested, aeis.idea.sot_drafted,
aeis.masterplan.created, aeis.system.runtime_topology_change_requested,
aeis.system.vps_scaling_requested, aeis.system.skill_selection_requested,
aeis.production.deploy_requested, aeis.testing.started,
aeis.human_gate.ticket_pending, aeis.final_approval.requested,
aeis.system.budget_threshold_crossed, aeis.council.formed,
aeis.advisor.preferences.updated, aeis.advisor.pricing.refreshed,
aeis.advisor.subscription.roi_computed
```

W kodzie (`subscribers.py`) subscriber rejestruje 31 topic-ów (uwzględniając rozszerzony zestaw companion: `aeis.idea.sot_approved/rejected`, `aeis.bundle.created`, `aeis.production.deployed/deploy_blocked`, `aeis.testing.completed`, `aeis.human_gate.ticket_decided`, `aeis.security.audit_completed`, `aeis.governance.policy_changed`, plus `aeis.advisor.preferences.reset`).

---

## 6. Tabele bazy danych

### 6.1. `advisor_engine.recommendations`

**Cel:** Główna tabela kart AdvisorCard (header denormalized, body w JSONB).

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `card_id` | UUID PK | |
| `envelope_version` | TEXT NOT NULL | np. `"1.0.0"` |
| `schema_version` | TEXT NOT NULL | |
| `card_type` | `advisor_engine.card_type` | `decision/funding/security/scaling/onboarding` |
| `parent_card_id` | UUID FK → self | dla rewizji karty |
| `title` | TEXT NOT NULL | |
| `rationale` | TEXT NOT NULL | max ~8000 chars w runtime |
| `confidence_score` | DOUBLE PRECISION | CHECK [0, 1] |
| `confidence_label` | enum | `low/med/high/very_high/certain` |
| `sources` | `card_source[]` | `rule_engine/llm_judge/history_match/council_vote/hybrid` |
| `risk_level` | enum | `low/medium/high/critical` |
| `risk_explanation` | TEXT | |
| `project_domain` | TEXT NOT NULL | |
| `project_type` | TEXT | |
| `project_id` | UUID | |
| `idea_id` | UUID | |
| `d_level` | enum | `D0..D5` |
| `evidence_pack_id` | UUID | FK → evidence_packs |
| `history_based` | BOOLEAN | |
| `related_history_card_ids` | UUID[] | |
| `historical_acceptance_rate` | DOUBLE PRECISION | CHECK [0, 1] |
| `expires_at` | TIMESTAMPTZ | |
| `priority` | enum | `low/normal/high/urgent` |
| `tags` | TEXT[] | append-only via `append_card_tag` |
| `dont_learn` | BOOLEAN | |
| `human_gate_required` | BOOLEAN | |
| `mobile_allowed` | BOOLEAN | |
| `requires_biometric` | BOOLEAN | |
| `push_priority` | TEXT | |
| `used_local_fallback` | BOOLEAN | |
| `local_fallback_reason` | TEXT | |
| `audit_trail_id` | UUID | |
| `llm_judge_audit_id` | UUID | |
| `operator_id` | UUID | |
| `emitting_module` | TEXT | |
| `body_jsonb` | JSONB | DecisionCard / FundingCard / etc. |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

**CHECK:** `confidence_label_matches_score` (gwarantuje spójność label vs. score).

### 6.2. `advisor_engine.llm_judge_audit`

**Cel:** Append-only forever retention log każdego LLM call-a.

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `audit_id` | UUID PK | |
| `card_id` | UUID | NULL gdy call abortowany przed emisją karty |
| `operator_id` | UUID NOT NULL | |
| `judge_purpose` | TEXT | `rationale/alternatives_ranking/risk_assessment/funding_scoring/consortium_matching/evidence_rationale/evidence_rollback/evidence_fidelity/other` |
| `model_id` | TEXT FK → `advisor_pricing.provider_models` | |
| `prompt_full` | TEXT | bez truncation |
| `response_full` | TEXT | bez truncation |
| `prompt_tokens`, `response_tokens` | INTEGER | |
| `cost_usd` | NUMERIC(20,8) | |
| `latency_ms` | INTEGER | |
| `was_local_fallback` | BOOLEAN | |
| `fallback_reason` | TEXT | |
| `parent_audit_id` | UUID FK → self | dla ensemble calls |
| `created_at` | TIMESTAMPTZ | |

**Append-only enforcement:** Trigger `advisor_engine.audit_block_modifications()` rzuca `RAISE EXCEPTION 'llm_judge_audit is append-only'` na `UPDATE`/`DELETE`.

**Indeksy:**
- `idx_llm_audit_card` (`card_id`) WHERE NOT NULL,
- `idx_llm_audit_operator_created` (`operator_id`, `created_at DESC`),
- `idx_llm_audit_purpose_model` (`judge_purpose`, `model_id`).

### 6.3. `advisor_engine.rule_definitions`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `rule_id` | TEXT PK | `split_large_module`, `block_prod_deploy_unsafe_sot`, ... |
| `version` | INTEGER | |
| `description` | TEXT | |
| `hook_event_pattern` | TEXT | regex topic |
| `precondition` | JSONB | DSL eval'd at app layer |
| `recommendation_type` | TEXT | enum w runtime |
| `default_d_level` | enum | |
| `is_active` | BOOLEAN | |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### 6.4. `advisor_engine.rule_firing_history`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `firing_id` | UUID PK | |
| `rule_id` | TEXT | |
| `rule_version` | INTEGER | |
| `triggering_event_id` | UUID | → advisor_events.events |
| `context_jsonb` | JSONB | |
| `produced_card_id` | UUID | NULL gdy reguła firowała ale nie wystawiła karty |
| `decision_taken` | TEXT | `emit/skip_low_confidence/skip_blocked_provider/failed/schema_validation_failed` |
| `fired_at` | TIMESTAMPTZ | |

**Indeksy:**
- `idx_rule_firing_rule` (`rule_id`, `fired_at DESC`),
- `idx_rule_firing_event` (`triggering_event_id`).

### 6.5. `advisor_evidence.evidence_packs`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `evidence_pack_id` | UUID PK | |
| `card_id` | UUID UNIQUE | |
| `d_level` | enum | |
| `pack_template` | TEXT | CHECK ∈ `{"d3_light", "d5_full"}` |
| `decision_class` | TEXT | `subscription_change/production_deploy/scaling_decision/autonomy_change/advisor_recommendation` |
| `domain` | TEXT NOT NULL | |
| `rationale`, `rollback_plan`, `fidelity_test` | TEXT NOT NULL | każde generowane osobnym LLM call-em |
| `confidence_breakdown` | JSONB | `{council_match, history_match, pricing_quality, historical_acceptance_rate, used_local_fallback, raw_score, final_score}` |
| `historical_acceptance_rate` | DOUBLE PRECISION | |
| `llm_judge_audit_ids` | UUID[] | |
| `simulation_results` | JSONB | dla funding cards |
| `council_vote_id` | UUID | |
| `attachments` | JSONB | |
| `created_by` | UUID NOT NULL | |
| `created_at`, `finalized_at` | TIMESTAMPTZ | |
| `status` | TEXT | `draft/finalized/rejected` |

**Indeksy:**
- `idx_evidence_packs_card` (`card_id`),
- `idx_evidence_packs_class` (`decision_class`, `created_at DESC`).

### 6.6. `advisor_evidence.evidence_pack_signatures`

| Kolumna | Typ | Opis |
| --- | --- | --- |
| `signature_id` | UUID PK | |
| `evidence_pack_id` | UUID FK → packs ON DELETE CASCADE | |
| `signer_id` | UUID NOT NULL | |
| `signer_role` | TEXT | `operator/council_member/governance/sentinel` |
| `signature_payload` | TEXT | crypto signature |
| `signed_at` | TIMESTAMPTZ | |

**Sample queries:**

```sql
-- Karty z fallbackiem lokalnym w ostatnich 7 dniach
SELECT card_id, title, confidence_score FROM advisor_engine.recommendations
WHERE used_local_fallback = true AND created_at > NOW() - INTERVAL '7 days';

-- Audyt LLM dla karty
SELECT judge_purpose, model_id, cost_usd, latency_ms
FROM advisor_engine.llm_judge_audit
WHERE card_id = '<uuid>' ORDER BY created_at;

-- Pakiety czekające na podpis
SELECT p.evidence_pack_id, p.decision_class, count(s.signature_id) AS sigs
FROM advisor_evidence.evidence_packs p
LEFT JOIN advisor_evidence.evidence_pack_signatures s USING (evidence_pack_id)
WHERE p.status = 'draft' GROUP BY 1, 2 ORDER BY sigs ASC;
```

---

## 7. Przykład użycia

### 7.1. Bootstrap engine + subskrypcja

```python
from sylion.aeis.advisor.engine.service import get_engine_service
from sylion.core.event_bus import get_event_bus

engine = get_engine_service()
subscribed = engine.attach_to_event_bus(get_event_bus())
print(f"engine subscribed to {subscribed} topics")
```

### 7.2. Submit lifecycle event (test / REST adapter)

```python
from sylion.aeis.advisor.engine.service import get_engine_service

engine = get_engine_service()
cards = engine.submit_event(
    topic="aeis.system.budget_config_requested",
    payload={
        "project_type": "external_paid_service",
        "project_domain": "saas",
        "estimated_cost_usd": 5_000,
        "is_production": False,
    },
    operator_id="op-001",
)
for card in cards:
    print(card["header"]["card_id"], card["header"]["d_level"], card["header"]["confidence_score"])
```

### 7.3. Synchroniczna bramka H13

```python
from sylion.aeis.advisor.engine.service import get_engine_service

engine = get_engine_service()
decision = engine.evaluate_gate(
    topic="aeis.production.deploy_requested",
    payload={"project_id": "proj-1", "is_production": True},
    operator_id="op-001",
    timeout_s=5.0,
)
if decision.decision == "block":
    print("blocked by card", decision.blocking_card_id, decision.reason)
elif decision.decision == "defer_to_human_gate":
    print("deferred to HG ticket", decision.created_human_gate_ticket_id)
else:
    print("proceed")
```

### 7.4. Evidence Pack lifecycle

```python
from sylion.aeis.advisor.engine.service import get_engine_service

engine = get_engine_service()
pack = engine.get_evidence_pack(pack_id="<uuid>")
print(pack["decision_class"], len(pack["signatures"]))

sig_id = engine.sign_evidence_pack(
    pack_id="<uuid>",
    signer_id="op-001",
    signer_role="operator",
    signature_payload="0xabc...",
)
engine.finalize_evidence_pack(pack_id="<uuid>")
```

### 7.5. Pytest — golden test rule firing

```python
import pytest
from sylion.aeis.advisor.engine.service import reset_engine_service, get_engine_service

@pytest.fixture(autouse=True)
def fresh_engine():
    reset_engine_service()
    yield
    reset_engine_service()

def test_block_card_emits_for_unsafe_sot():
    engine = get_engine_service()
    cards = engine.submit_event(
        topic="aeis.production.deploy_requested",
        payload={"project_id": "p", "sot_status": "draft"},
        operator_id="op-1",
    )
    block_cards = [c for c in cards if c["header"]["d_level"] == "D5"]
    assert block_cards, "expected at least one D5 BLOCK card"
```

---

## 8. Komendy weryfikacyjne

```bash
# 1. Liczba kart per d_level
psql "$ADVISOR_PG_DSN" -c "SELECT d_level, count(*) FROM advisor_engine.recommendations GROUP BY 1 ORDER BY 1;"

# 2. LLM audit forever-retention check (powinno być monotonicznie rosnące)
psql "$ADVISOR_PG_DSN" -c "SELECT count(*) FROM advisor_engine.llm_judge_audit;"

# 3. Append-only test (powinno failować z 'llm_judge_audit is append-only')
psql "$ADVISOR_PG_DSN" -c "UPDATE advisor_engine.llm_judge_audit SET cost_usd = 0 WHERE audit_id = (SELECT audit_id FROM advisor_engine.llm_judge_audit LIMIT 1);"

# 4. Pytesty modułu (golden tests z manifestu)
pytest tests/aeis/advisor/engine/ -q

# 5. Sanity ServiceFacade
python -c "from sylion.aeis.advisor.engine.service import get_engine_service; s = get_engine_service(); print(len(s.list_rules()))"

# 6. Pakiety bez kompletu sygnatur dla D5
psql "$ADVISOR_PG_DSN" -c "SELECT evidence_pack_id FROM advisor_evidence.evidence_packs WHERE d_level = 'D5' AND status = 'draft';"
```

---

## 9. Troubleshooting

| Problem | Diagnoza | Naprawa |
| --- | --- | --- |
| `submit_event` zwraca pustą listę | Brak dopasowanej reguły dla topic-u | Sprawdź `list_rules()`, dodaj seed lub `register` |
| Karta D5 ale brak Evidence Pack | `EvidencePackRequirement` mapuje błędnie? | `d_level=D5` zawsze daje `FULL` — patrz `evidence_gate.py`. Sprawdź czy `_create_evidence_pack` był wołany |
| `validation_failed` event przy każdej karcie | `card_builder/validators.py` rzuca błędy | Sprawdź `rule_firing_history.context_jsonb.errors` |
| `llm_judge_audit` insert failuje na FK `model_id` | Brak modelu w `provider_models` | `RefreshPricing(provider_id)` lub re-init katalogu |
| Confidence zawsze ~0.0 | Wszystkie snapshoty puste (council/history/pricing) | Po stronie `_build_card_context` snapshoty są stub-ami; połącz z preferences/pricing/history |
| `evaluate_gate` zwraca `proceed` mimo D5 BLOCK | `cards` puste z powodu wyjątku w pipeline | Włącz `log.exception` — `sync_gate` fail-open |
| `dispatch_event` rzuca w jednym z handlerów | `try/except` w subscriber | Inspect `log.exception` w `engine.lifecycle.subscribers` |
| `seed_default_rules` nie wstawia reguł | `rule_definitions` ma już rekordy lub `is_active=false` | `INSERT ... ON CONFLICT DO UPDATE`; sprawdź `is_active` |
| `local_fallback_used` event pomimo cloud judge | `routing.forced_local=True` (preferencja runtime) lub `response.was_stub=True` (klient stub) | Inspect `audit.fallback_reason` |
| `finalize_evidence_pack` zwraca `False` | Pakiet nie istnieje lub nie ma poprzedniego draftu | Sprawdź `get_evidence_pack(pack_id)` |
| Trigger `audit_block_modifications` blokuje legalny update | Każdy UPDATE/DELETE jest zabroniony — celowe | Insert nowy wiersz z `parent_audit_id` zamiast UPDATE |
| Cap D5 zawsze | Wartość `current_idx > _LEVEL_INDEX["D5"]` po U1+U2 | Oczekiwane — patrz `assigner._bump` (min cap) |

---

## 10. Powiązania

- [01_preferences.md](01_preferences.md) — preferencje wpływają na U4 (hard preference keys), U5 (autonomy), filtr blocked providers w pricing snapshot.
- [02_pricing.md](02_pricing.md) — `pricing_snapshot` w `CardContext`; `model_id` FK na `provider_models`.
- [03_actions.md](03_actions.md) — operator akcje na karcie modyfikują `recommendations.tags[]` / `body_jsonb`; `dont_learn` propaguje do history.
- [04_events.md](04_events.md) — wszystkie `aeis.advisor.engine.*` audytowane przez `audit_subscriber`.
- [06_history.md](06_history.md) — `record_card_emission` subskrybuje `recommendation_emitted`; `history_match` i `historical_acceptance` zasilają confidence przez snapshot-y.
- [30_event_taxonomy_full.md](30_event_taxonomy_full.md) — payload schema dla 14 topic-ów `aeis.advisor.engine.*`.
- `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` — DDL `advisor_engine.*` + `advisor_evidence.*`.
- `docs/claude_parallel/aeis_advisor/00_architecture/03_advisor_card_schema.md` — kanoniczny schema `AdvisorCardEnvelope`.
- `docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md` — 16 hooks H01-H16.
- `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` — D-ladder spec + U1-U5.
