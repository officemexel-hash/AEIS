# 30. Pełna taksonomia eventów AEIS Advisor
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Cross-cutting documentation — wszystkie eventy advisor (internal + outbound),
> envelope, subskrybenci, retencja, walidacja schematów, replay, partycjonowanie.
> Wersja dokumentu: 1.0 (2026-04-26).

---

## Spis treści

1. [Filozofia i zasięg](#1-filozofia-i-zasięg)
2. [Konwencja nazewnicza](#2-konwencja-nazewnicza)
3. [Format eventu (envelope)](#3-format-eventu-envelope)
4. [Lifecycle hooks (16) — wejścia z kerneli AEIS](#4-lifecycle-hooks-16--wejścia-z-kerneli-aeis)
5. [Towarzyszące zdarzenia kerneli (companion events)](#5-towarzyszące-zdarzenia-kerneli-companion-events)
6. [Internal events advisor — per moduł](#6-internal-events-advisor--per-moduł)
   - 6.1 advisor.preferences
   - 6.2 advisor.pricing
   - 6.3 advisor.engine
   - 6.4 advisor.role_resolver
   - 6.5 advisor.variants
   - 6.6 advisor.subscription
   - 6.7 advisor.scaling
   - 6.8 advisor.funding
   - 6.9 advisor.history
   - 6.10 advisor.actions
   - 6.11 advisor.mobile_gateway
   - 6.12 advisor.events (meta)
   - 6.13 advisor.orchestration_config
7. [Outbound events — dispatcher i adaptery](#7-outbound-events--dispatcher-i-adaptery)
8. [Macierz subskrybentów (kto słucha jakich)](#8-macierz-subskrybentów-kto-słucha-jakich)
9. [Schema versioning](#9-schema-versioning)
10. [Sample event JSON (per typ)](#10-sample-event-json-per-typ)
11. [PG LISTEN/NOTIFY i replay](#11-pg-listennotify-i-replay)
12. [Partycjonowanie i retencja](#12-partycjonowanie-i-retencja)
13. [Walidacja schematów (proto_registry)](#13-walidacja-schematów-proto_registry)
14. [Audit i correlation_id](#14-audit-i-correlation_id)
15. [Trace propagacja (OpenTelemetry)](#15-trace-propagacja-opentelemetry)
16. [Cross-references](#16-cross-references)

---

## 1. Filozofia i zasięg

Taksonomia eventów AEIS Advisor jest **kanonicznym kontraktem komunikacyjnym** między
12 modułami advisor, kernelami AEIS (idea, council, system, production, testing,
human_gate, final_approval, bundle, security) oraz adapterami zewnętrznymi (Slack,
email, FCM, webhook, SMS).

Cele:

- **Audytowalność** — każdy event jest zapisany, zwalidowany i powiązany correlation_id,
  by audytor mógł odtworzyć pełną ścieżkę decyzji.
- **Ewentualna spójność** — moduły advisor reagują asynchronicznie na zdarzenia
  kerneli; sync gates istnieją tylko tam, gdzie wymaga tego model bezpieczeństwa
  (deploy, final approval).
- **Jednolite walidowanie** — każdy event przechodzi przez `proto_registry`, który
  weryfikuje payload względem deskryptora schematu.
- **Replay** — late-joiner (np. mobile po reconnect) odbiera historię od `since`.
- **Cost transparency** — eventy LLM-judge dokumentują koszt + model, są permanentne.

Eventy nie są emitowane po cichu. Każdy producer **musi** zarejestrować typ
w `proto_registry` (lub używać typu już zarejestrowanego). Każdy event trafia do
`advisor_events.events` (partycjonowane po dniu/miesiącu) i wyzwala `NOTIFY` w PG.

---

## 2. Konwencja nazewnicza

Trzy główne przestrzenie nazw:

| Przestrzeń | Producer | Konsument |
|---|---|---|
| `aeis.<phase>.<entity>.<action>` | Istniejące moduły AEIS (lifecycle hooks) | Głównie engine advisor |
| `aeis.advisor.<module>.<action>` | Moduły advisor (warstwa rekomendacji) | Inne moduły advisor + UI + outbound |
| `aeis.advisor.outbound.<adapter>.<action>` | Dispatcher outbound | Zewnętrzne adaptery (Slack/email/FCM/webhook/SMS) |

### Reguły

- Wszystkie segmenty są lower_snake_case.
- `<module>` to nazwa modułu advisor (np. `preferences`, `engine`, `funding`).
- `<action>` to czas przeszły lub stan (`emitted`, `created`, `failed`, `recorded`),
  spójny z konwencją SYLION.
- Nie wolno używać kropek w segmentach.
- Maksymalna długość typu eventu: 128 znaków.

### Przykłady poprawnych nazw

```
aeis.advisor.engine.recommendation_emitted
aeis.advisor.preferences.hard_change_requested
aeis.advisor.outbound.slack.message_sent
aeis.idea.intake.completed
```

### Przykłady niepoprawnych nazw

```
aeis.advisor.engine.recommend                  # za krótkie, brak action verb past
AEIS.Advisor.Engine.RecommendationEmitted      # camelCase niedozwolony
aeis.advisor.engine                            # brak action
aeis.advisor.engine.recommend.emitted          # nadmiarowy segment
```

---

## 3. Format eventu (envelope)

Każdy event ma standardową kopertę (envelope) plus type-specific payload.

```proto
message AdvisorEventEnvelope {
  string event_id = 1;                          // UUID v4
  string event_type = 2;                        // canonical name (zob. §2)
  google.protobuf.Timestamp produced_at = 3;    // czas powstania (UTC)
  string producer_module = 4;                   // np. "sylion.aeis.advisor.engine"
  string operator_id = 5;                       // nullable dla system-level
  string project_id = 6;                        // nullable
  string correlation_id = 7;                    // łączy zdarzenia jednej decyzji
  string causation_id = 8;                      // event_id zdarzenia rodzicielskiego
  string trace_id = 9;                          // OpenTelemetry trace id
  uint32 schema_version = 10;                   // wersja payloadu
  google.protobuf.Any payload = 11;             // type-specific body
}
```

### Pola obowiązkowe vs opcjonalne

| Pole | Wymagane | Opis |
|---|---|---|
| `event_id` | tak | Idempotencja po stronie konsumenta |
| `event_type` | tak | Klucz do `proto_registry` |
| `produced_at` | tak | Generowane przez producenta |
| `producer_module` | tak | Pełna ścieżka modułu |
| `operator_id` | nie | NULL dla system-level (kron, audit) |
| `project_id` | nie | NULL gdy event nie jest scoped do projektu |
| `correlation_id` | tak | Wymagany dla audit reconstruction |
| `causation_id` | nie | NULL dla pierwszego eventu w łańcuchu |
| `trace_id` | nie | Opcjonalny; producent może nie mieć kontekstu OTel |
| `schema_version` | tak | Domyślnie 1 |
| `payload` | tak | Body specyficzne dla `event_type` |

### Płaska reprezentacja JSON

W praktyce envelope jest serializowany do JSON i zapisany jako jedna kolumna
JSONB. Płaska reprezentacja:

```json
{
  "event_id": "9f1c5b...",
  "event_type": "aeis.advisor.engine.recommendation_emitted",
  "produced_at": "2026-04-26T12:34:56.123Z",
  "producer_module": "sylion.aeis.advisor.engine",
  "operator_id": "op-7c9d...",
  "project_id": "proj-12...",
  "correlation_id": "corr-abc-123",
  "causation_id": "5e2f...",
  "trace_id": "00-4bf92f...-00f067aa...",
  "schema_version": 1,
  "payload": {
    "card_id": "card-...",
    "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
    "d_level": "D3",
    "risk_level": "high",
    "rationale_summary": "Operator monthly spend $80 → Pro plan break-even ~14 days",
    "evidence_pack_id": "ep-...",
    "confidence_score": 0.78,
    "ui_url": "https://sylion.local/advisor/cards/card-..."
  }
}
```

---

## 4. Lifecycle hooks (16) — wejścia z kerneli AEIS

Lifecycle hooks to eventy emitowane przez **kernele AEIS** (idea, council,
system, production, testing, human_gate, final_approval), które uruchamiają
advisor. Niektóre są synchronicznymi gates (engine musi odpowiedzieć przed
kontynuacją kernelu).

| # | Topic | Producer kernel | Sync gate? | Cel hooka |
|---|---|---|---|---|
| H01 | `aeis.system.model_setup_requested` | system | nie | Operator chce skonfigurować model SOT |
| H02 | `aeis.system.api_provider_setup_requested` | system | nie | Operator dodaje providera + klucz API |
| H03 | `aeis.system.budget_config_requested` | system | nie | Konfiguracja limitów budżetu |
| H04 | `aeis.idea.intake.completed` | idea | nie | Idea wprowadzona, advisor sugeruje routing |
| H05 | `aeis.idea.sot_model_selection_requested` | idea | nie | Wybór modelu do SOT |
| H06 | `aeis.council.formation_requested` | council | nie | Konfiguracja składu rady |
| H07 | `aeis.system.autonomy_policy_change_requested` | system | nie | Zmiana autonomy_level (D3+) |
| H08 | `aeis.idea.sot_drafted` | idea | nie | SOT gotowy do walidacji |
| H09 | `aeis.masterplan.created` | bundle | nie | Masterplan jest do oceny |
| H10 | `aeis.system.runtime_topology_change_requested` | system | nie | Local→VPS / VPS→Multi-VPS |
| H11 | `aeis.system.vps_scaling_requested` | system | nie | Zwiększenie skali VPS |
| H12 | `aeis.system.skill_selection_requested` | system | nie | Aktywacja/dezaktywacja skilla |
| H13 | `aeis.production.deploy_requested` | production | **TAK** | Deploy do produkcji — engine może zablokować |
| H14 | `aeis.testing.started` | testing | nie | Testing started — info dla advisor |
| H15 | `aeis.human_gate.ticket_pending` | human_gate | nie | Ticket czeka na decyzję operatora |
| H16 | `aeis.final_approval.requested` | final_approval | **TAK** | Ostateczna akceptacja — engine sprawdza ev. pack |

### Synchronous gate flow (H13, H16)

```
1. Kernel publishes hook event with reply-to topic
2. Kernel blocks (max timeout, default 5s)
3. Engine receives event, evaluates D-ladder + Evidence Pack requirements
4. Engine emits decision: 'proceed' | 'block' | 'defer_to_human_gate'
5. Kernel resumes (or aborts if blocked)
```

Implementacja: `sylion.aeis.advisor.events.lifecycle.publish_lifecycle_event`
i `await_advisor_decision`. Domyślny timeout 5s; po przekroczeniu kernel
otrzymuje `'proceed'` z notatką timeout-fallback (zachowanie konfigurowalne
przez `approval_timeout_behavior` preference, hard_change=true).

---

## 5. Towarzyszące zdarzenia kerneli (companion events)

Eventy nie-hookowe, ale konsumowane przez advisor:

```
aeis.system.budget_threshold_crossed
aeis.council.formed
aeis.idea.sot_approved
aeis.idea.sot_rejected
aeis.bundle.created
aeis.production.deployed
aeis.production.deploy_blocked
aeis.testing.completed
aeis.human_gate.ticket_decided
aeis.security.audit_completed
aeis.governance.policy_changed
```

Te eventy **nie wymagają** advisor decision (nie są gates), ale advisor reaguje
na nie: rejestruje uczenie (history), aktualizuje metryki kosztowe (subscription),
wpływa na confidence przyszłych rekomendacji.

---

## 6. Internal events advisor — per moduł

### 6.1 advisor.preferences

| Topic | Trigger | Kluczowe pola payload |
|---|---|---|
| `aeis.advisor.preferences.created` | Nowa preferencja zapisana | `pref_key`, `value`, `scope`, `is_hard_change` |
| `aeis.advisor.preferences.updated` | Wartość preferencji zmieniona | `pref_key`, `old_value`, `new_value`, `scope` |
| `aeis.advisor.preferences.deleted` | Preferencja usunięta (powrót do default) | `pref_key`, `scope` |
| `aeis.advisor.preferences.reset` | Reset całego scope do defaultów | `scope`, `affected_keys[]` |
| `aeis.advisor.preferences.disabled` | Tymczasowe wyłączenie | `pref_key`, `until` |
| `aeis.advisor.preferences.hard_change_requested` | Hard change wymagający potwierdzenia | `pref_key`, `proposed_value`, `confirmation_token` |
| `aeis.advisor.preferences.hard_change_confirmed` | Operator potwierdził | `pref_key`, `value`, `confirmation_token` |
| `aeis.advisor.preferences.hard_change_rejected` | Operator odrzucił | `pref_key`, `reason` |
| `aeis.advisor.preferences.catalog_extended` | Custom domain/type dodany do katalogu | `domain`, `key`, `definition_jsonb` |

**Przykładowy payload `preferences.updated`**:

```json
{
  "pref_key": "autonomy_level",
  "old_value": "manual",
  "new_value": "suggest",
  "scope": {"user_id": "op-7c9d", "project_id": null},
  "is_hard_change": true,
  "confirmed_by_token": "tok-...",
  "changed_at": "2026-04-26T12:34:56Z"
}
```

### 6.2 advisor.pricing

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.pricing.refreshed` | Provider price list odświeżony | `provider`, `models_count`, `source_url`, `fetched_at` |
| `aeis.advisor.pricing.assumption_used` | Brak danych live → użyto assumption | `model_id`, `assumed_value`, `last_known_age_h` |
| `aeis.advisor.pricing.provider_unavailable` | Provider zwrócił błąd | `provider`, `error_kind`, `retry_after_s` |
| `aeis.advisor.pricing.adapter_failed` | Adapter rzucił wyjątek | `adapter_id`, `exception_class`, `traceback_hash` |
| `aeis.advisor.pricing.live_metadata_fetched` | Metadane live (np. tokens/min limit) | `provider`, `metadata_jsonb` |
| `aeis.advisor.pricing.profile_updated` | Profil cenowy modułu zmieniony | `profile_id`, `delta_jsonb` |

### 6.3 advisor.engine

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.engine.recommendation_emitted` | Karta wygenerowana | `card_id`, `recommendation_type`, `d_level`, `risk_level`, `evidence_pack_id`, `rationale_summary`, `confidence_score` |
| `aeis.advisor.engine.recommendation_skipped` | Karta NIE wygenerowana (np. rate limit) | `would_be_type`, `skip_reason` |
| `aeis.advisor.engine.llm_judge_call_started` | LLM-judge wywołanie startuje | `judge_purpose`, `model_id`, `prompt_token_count` |
| `aeis.advisor.engine.llm_judge_call_completed` | LLM-judge response | `judge_purpose`, `model_id`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms` |
| `aeis.advisor.engine.llm_judge_call_failed` | LLM-judge wywołanie failed | `judge_purpose`, `model_id`, `error_kind`, `retry_count` |
| `aeis.advisor.engine.confidence_calculated` | Components confidence wyliczone | `card_id`, `components_jsonb`, `final_score` |
| `aeis.advisor.engine.evidence_pack_required` | Pack wymagany — start tworzenia | `card_id`, `pack_template`, `d_level` |
| `aeis.advisor.engine.evidence_pack_finalized` | Pack finalised — karta może być akceptowana | `card_id`, `pack_id` |
| `aeis.advisor.engine.deploy_blocked` | H13 odpowiedź = block | `project_id`, `block_reason`, `evidence_pack_id` |
| `aeis.advisor.engine.deploy_proceeded` | H13 odpowiedź = proceed | `project_id` |
| `aeis.advisor.engine.deploy_deferred_to_human_gate` | H13 odpowiedź = defer | `project_id`, `human_gate_ticket_id` |
| `aeis.advisor.engine.local_fallback_used` | LLM-judge fallback do lokalnego modelu | `original_model_id`, `fallback_model_id`, `reason` |
| `aeis.advisor.engine.cost_ceiling_hit` | Próg kosztu osiągnięty | `risk_level`, `ceiling_usd`, `attempted_cost_usd` |

### 6.4 advisor.role_resolver

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.role_resolver.routing_decision` | Każda decyzja routingu | `operator_id`, `judge_purpose` lub `role`, `risk_level`, `resolved_model`, `reason`, `estimated_cost_usd` |
| `aeis.advisor.role_resolver.override_applied` | Operator override aktywny | `operator_id`, `override_key`, `resolved_model` |
| `aeis.advisor.role_resolver.fallback_to_local` | Wszystkie zewnętrzne wykluczone | `operator_id`, `judge_purpose`/`role`, `resolved_model`, `reason` |

### 6.5 advisor.variants

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.variants.generated` | N wariantów rekomendacji wygenerowanych | `card_id`, `variant_count`, `model_diversity_score` |
| `aeis.advisor.variants.compared` | Variants porównane, najlepszy wybrany | `card_id`, `winner_variant_id`, `comparison_method` |

### 6.6 advisor.subscription

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.subscription.usage_recorded` | Pojedyncze użycie zarejestrowane | `provider`, `model_id`, `tokens_in`, `tokens_out`, `cost_usd`, `recorded_at` |
| `aeis.advisor.subscription.roi_computed` | ROI dla planu obliczone | `plan_id`, `monthly_observed_usd`, `predicted_savings_usd`, `break_even_days` |
| `aeis.advisor.subscription.plan_recommended` | Karta z propozycją planu | `card_id`, `plan_id`, `confidence_score` |
| `aeis.advisor.subscription.usage_threshold_crossed` | Próg użycia przekroczony | `threshold_pct`, `current_value_usd`, `forecast_eom_usd` |
| `aeis.advisor.subscription.purchase_attempted` | Kliknięcie purchase (zawsze emituje) | `plan_id`, `gate_outcome` |
| `aeis.advisor.subscription.purchase_blocked` | Hard gate zablokował | `plan_id`, `block_reason`, `evidence_pack_id` |
| `aeis.advisor.subscription.plan_catalog_updated` | Katalog planów zmieniony | `plan_ids_added[]`, `plan_ids_removed[]` |

### 6.7 advisor.scaling

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.scaling.topology_recommended` | Karta z topologią | `card_id`, `current_topology`, `proposed_topology`, `predicted_speed_gain` |
| `aeis.advisor.scaling.staging_plan_proposed` | Plan staged rollout | `phases_count`, `total_duration_days` |
| `aeis.advisor.scaling.env_inventory_changed` | Lista envs zmieniła się | `added[]`, `removed[]`, `total_count` |
| `aeis.advisor.scaling.scaling_blocked` | D3+ ale brak Evidence Pack | `card_id`, `block_reason` |

### 6.8 advisor.funding

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.funding.module_enabled` | Operator włączył funding advisor | `operator_id`, `enabled_at` |
| `aeis.advisor.funding.module_disabled` | Operator wyłączył | `operator_id`, `reason` |
| `aeis.advisor.funding.country_filter_changed` | Lista krajów zmieniona | `countries_added[]`, `countries_removed[]` |
| `aeis.advisor.funding.grant_loaded` | Grant załadowany manualnie | `grant_id`, `program_name`, `source` |
| `aeis.advisor.funding.grant_data_refreshed` | Live refresh z systemu zewnętrznego | `provider`, `grants_count` |
| `aeis.advisor.funding.scoring_calculated` | Scoring fit grantu | `grant_id`, `score`, `breakdown_jsonb` |
| `aeis.advisor.funding.eligibility_floor_breached` | Floor (np. legal form) niespełniony | `grant_id`, `floor_kind`, `actual`, `required` |
| `aeis.advisor.funding.consortium_suggested` | Karta consortium | `grant_id`, `partner_candidates[]` |
| `aeis.advisor.funding.simulation_completed` | Symulacja "co jeśli sp. z o.o." | `simulation_id`, `delta_score`, `cost_usd` |
| `aeis.advisor.funding.token_budget_threshold_crossed` | LLM-judge funding przekroczył próg | `threshold_pct`, `model_id` |
| `aeis.advisor.funding.research_initiated` | External research started | `research_id`, `query_summary` |
| `aeis.advisor.funding.research_completed` | External research finished | `research_id`, `results_count` |
| `aeis.advisor.funding.company_data_updated` | Dane firmy zmienione (legal form, country) | `field`, `old`, `new` |
| `aeis.advisor.funding.scoring_history_persisted` | Snapshot scoringu zachowany | `snapshot_id`, `grants_count` |

### 6.9 advisor.history

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.history.action_recorded` | Operator zaakceptował/odrzucił/dismissed kartę | `card_id`, `action`, `latency_to_action_s` |
| `aeis.advisor.history.learning_signal_emitted` | Soft learning signal | `signal_kind`, `pref_key`, `delta` |
| `aeis.advisor.history.soft_learning_applied` | Soft learning faktycznie zaktualizował preferencje | `pref_key`, `new_value` |
| `aeis.advisor.history.hard_change_requested` | Hard change wymagany | `pref_key`, `proposed_value` |
| `aeis.advisor.history.skip_learning_recorded` | Operator wybrał "skip learning" dla danej karty | `card_id`, `reason` |
| `aeis.advisor.history.partition_created` | Nowa partycja history utworzona | `partition_name`, `range_from`, `range_to` |
| `aeis.advisor.history.confidence_components_calculated` | Per-component confidence wyliczone | `card_id`, `components_jsonb` |

### 6.10 advisor.actions

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.actions.action_routed` | Akcja operatora zrouted do executora | `card_id`, `action_kind`, `routed_to` |
| `aeis.advisor.actions.routing_failed` | Brak handlera lub error | `card_id`, `action_kind`, `error_kind` |
| `aeis.advisor.actions.human_gate_ticket_created` | Akcja przekonwertowana na ticket HG | `card_id`, `ticket_id` |
| `aeis.advisor.actions.masterplan_proposal_created` | Akcja stworzyła masterplan proposal | `card_id`, `proposal_id` |
| `aeis.advisor.actions.preference_saved` | Akcja zapisała preferencję | `card_id`, `pref_key`, `value` |
| `aeis.advisor.actions.action_retry_scheduled` | Akcja przeszła w retry (idempotent) | `card_id`, `attempt`, `retry_at` |

### 6.11 advisor.mobile_gateway

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.mobile_gateway.request_handled` | Mobile request obsłużony | `device_id`, `endpoint`, `latency_ms`, `status_code` |
| `aeis.advisor.mobile_gateway.auth_failure` | Auth failed | `device_id`, `failure_kind` |
| `aeis.advisor.mobile_gateway.biometric_step_up_triggered` | Biometric step-up wymagany | `device_id`, `reason` |
| `aeis.advisor.mobile_gateway.device_paired` | Nowe urządzenie sparowane | `device_id`, `paired_at` |
| `aeis.advisor.mobile_gateway.device_unpaired` | Urządzenie usunięte | `device_id`, `reason` |
| `aeis.advisor.mobile_gateway.offline_snapshot_served` | Offline snapshot dostarczony | `device_id`, `snapshot_age_s`, `cards_count` |

### 6.12 advisor.events (meta)

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.events.validation_failed` | Payload niezgodny ze schema | `attempted_event_type`, `validation_errors[]`, `producer_module` |
| `aeis.advisor.events.proto_registered` | Nowy typ zarejestrowany | `event_type`, `proto_message_type`, `version` |
| `aeis.advisor.events.proto_deprecated` | Typ oznaczony jako deprecated | `event_type`, `replacement_type`, `sunset_at` |

### 6.13 advisor.orchestration_config

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.orchestration_config.profile_updated` | Profil orchestration zmieniony | `profile_id`, `delta_jsonb` |
| `aeis.advisor.orchestration_config.skill_priority_changed` | Priorytety skilli przepisane | `skill_id`, `old_priority`, `new_priority` |

---

## 7. Outbound events — dispatcher i adaptery

### 7.1 Dispatcher

Dispatcher (`advisor.outbound`) jest osobnym konsumentem **wszystkich** eventów
advisor i kerneli. Każdy event jest oceniany względem `dispatch_rules`.

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.outbound.dispatched` | Pojedyncze dopasowanie reguły do adaptera | `rule_name`, `adapter_id`, `source_event_id`, `template_rendered` |
| `aeis.advisor.outbound.delivered` | Adapter potwierdził dostarczenie | `adapter_id`, `external_msg_id`, `latency_ms` |
| `aeis.advisor.outbound.failed` | Adapter zwrócił błąd | `adapter_id`, `error_kind`, `retry_count`, `next_retry_at` |
| `aeis.advisor.outbound.dead_lettered` | Max retry osiągnięty | `adapter_id`, `original_event_id`, `final_error` |

### 7.2 Per-adapter

| Topic | Trigger | Pola |
|---|---|---|
| `aeis.advisor.outbound.slack.message_sent` | Slack ack | `channel`, `slack_msg_ts`, `latency_ms` |
| `aeis.advisor.outbound.slack.message_failed` | Slack error | `channel`, `error_kind`, `slack_error_code` |
| `aeis.advisor.outbound.email.sent` | Email wysłany | `to`, `provider_msg_id`, `subject` |
| `aeis.advisor.outbound.email.failed` | Email error | `to`, `error_kind`, `provider_response` |
| `aeis.advisor.outbound.fcm.notification_sent` | FCM push delivered | `device_token`, `fcm_msg_id` |
| `aeis.advisor.outbound.fcm.notification_failed` | FCM error | `device_token`, `error_kind`, `fcm_error_code` |
| `aeis.advisor.outbound.webhook.invoked` | Webhook 2xx | `endpoint_url`, `status_code`, `latency_ms` |
| `aeis.advisor.outbound.webhook.failed` | Webhook 4xx/5xx/timeout | `endpoint_url`, `error_kind`, `status_code` |
| `aeis.advisor.outbound.sms.sent` | SMS wysłany | `to_msisdn`, `provider_msg_id` |
| `aeis.advisor.outbound.sms.failed` | SMS error | `to_msisdn`, `error_kind` |

### 7.3 Przykładowe reguły dispatch_rules

```yaml
- rule_name: high_risk_to_slack_ops
  match_event_pattern: 'aeis.advisor.engine.recommendation_emitted'
  match_predicate: { 'risk_level': ['high', 'critical'] }
  dispatch_to: [slack_adapter_ops_channel]
  template: |
    *{{title}}* ({{risk_level}}, D{{d_level}})
    {{rationale_summary}}
    Action required: {{operator_id}}
    [View card]({{ui_url}})

- rule_name: critical_to_mobile_push
  match_event_pattern: 'aeis.advisor.engine.recommendation_emitted'
  match_predicate: { 'risk_level': ['critical'], 'mobile_allowed': true }
  dispatch_to: [fcm_adapter_default]
  template: |
    {"title": "{{title}}", "body": "{{rationale_summary}}", "priority": "{{push_priority}}"}

- rule_name: deploy_blocked_to_email
  match_event_pattern: 'aeis.advisor.engine.deploy_blocked'
  match_predicate: {}
  dispatch_to: [email_adapter_operator]
  template: |
    Subject: Production deploy blocked: {{project_name}}
    Body: {{block_reason}}\n\nReview at: {{ui_url}}

- rule_name: human_gate_pending_summary
  match_event_pattern: 'aeis.human_gate.ticket_pending'
  match_predicate: { 'pending_count_user': { '$gte': 5 } }
  dispatch_to: [slack_adapter_ops_channel, fcm_adapter_default]
  template: |
    {{pending_count_user}} Human Gate tickets pending. Consider batch review.
```

### 7.4 Retry policy per-adapter

| Adapter | Initial backoff | Max attempts | Total budget |
|---|---|---|---|
| slack | 1s | 5 | ~30s |
| email | 5s | 7 | ~10min |
| fcm | 1s | 5 | ~30s |
| webhook | 2s | 10 | ~60min |
| sms | 5s | 5 | ~5min |

Po wyczerpaniu — `dead_lettered` event + zapis do `advisor_outbound.dead_letter_queue`.

---

## 8. Macierz subskrybentów (kto słucha jakich)

### 8.1 Engine (`advisor.engine`)

Subskrybuje:

```
aeis.idea.intake.completed                       (H04)
aeis.idea.sot_model_selection_requested          (H05)
aeis.idea.sot_drafted                            (H08)
aeis.system.model_setup_requested                (H01)
aeis.system.api_provider_setup_requested         (H02)
aeis.system.budget_config_requested              (H03)
aeis.system.autonomy_policy_change_requested     (H07)
aeis.system.runtime_topology_change_requested    (H10)
aeis.system.vps_scaling_requested                (H11)
aeis.system.skill_selection_requested            (H12)
aeis.council.formation_requested                 (H06)
aeis.production.deploy_requested                 (H13, sync)
aeis.testing.started                             (H14)
aeis.human_gate.ticket_pending                   (H15)
aeis.final_approval.requested                    (H16, sync)
aeis.bundle.created                              (companion)
aeis.advisor.preferences.updated                 (re-eval cards)
aeis.advisor.history.action_recorded             (uczenie)
```

### 8.2 History

```
aeis.advisor.engine.recommendation_emitted
aeis.advisor.actions.action_routed
aeis.advisor.actions.preference_saved
aeis.advisor.preferences.hard_change_confirmed
```

### 8.3 Subscription

```
aeis.advisor.engine.llm_judge_call_completed     (zlicza koszty)
aeis.advisor.pricing.refreshed
aeis.system.budget_threshold_crossed
```

### 8.4 Funding

```
aeis.advisor.funding.module_enabled
aeis.idea.intake.completed
aeis.advisor.funding.country_filter_changed
aeis.advisor.preferences.updated                 (gdy company_data zmieniony)
```

### 8.5 Outbound dispatcher

```
*                                                # ALL events
```

### 8.6 Audit subscriber

```
aeis.advisor.*                                   # ALL advisor topics
```

(Implementacja: `AdvisorAuditSubscriber` w `events/audit_subscriber.py`.)

### 8.7 Mobile gateway

```
aeis.advisor.engine.recommendation_emitted        (push do mobile feed)
aeis.advisor.engine.evidence_pack_required        (badge update)
aeis.advisor.actions.human_gate_ticket_created    (notification)
```

### 8.8 Variants

```
aeis.advisor.engine.recommendation_emitted        (gdy variant_required=true)
```

### 8.9 Scaling

```
aeis.system.runtime_topology_change_requested    (H10)
aeis.system.vps_scaling_requested                (H11)
aeis.advisor.subscription.usage_threshold_crossed
```

---

## 9. Schema versioning

Każdy event ma `schema_version` (pole envelope) oraz wpis w `proto_registry`
z `proto_version`. Przejście między wersjami:

### 9.1 Backward-compatible (additive only) — bump minor (1 → 1, payload extended)

Pola nowo dodane są opcjonalne; konsumenci ignorują nieznane pola.

### 9.2 Backward-incompatible — bump major (1 → 2)

Wymaga:

- Rejestracji nowego typu z sufiksem (np. `recommendation_emitted_v2`) **lub**
- Bumpa `schema_version` w envelope + okresu deprecation w `proto_registry`.

### 9.3 Cykl życia wersji

```
proposed     → registered (proto_registered)
registered   → in_use
in_use       → deprecated (proto_deprecated, sunset_at ustawiony)
deprecated   → sunset (po sunset_at już nie wolno emitować)
sunset       → archived
```

---

## 10. Sample event JSON (per typ)

### 10.1 `aeis.advisor.engine.recommendation_emitted`

```json
{
  "event_id": "9f1c5b2e-...",
  "event_type": "aeis.advisor.engine.recommendation_emitted",
  "produced_at": "2026-04-26T12:34:56.123Z",
  "producer_module": "sylion.aeis.advisor.engine",
  "operator_id": "op-7c9d",
  "project_id": "proj-12",
  "correlation_id": "corr-abc-123",
  "causation_id": "ev-h04",
  "trace_id": "00-4bf92f...",
  "schema_version": 1,
  "payload": {
    "card_id": "card-...",
    "recommendation_type": "REC_TYPE_PURCHASE_PLAN",
    "d_level": "D3",
    "risk_level": "high",
    "evidence_pack_id": "ep-...",
    "rationale_summary": "Operator monthly spend $80 → Pro plan break-even ~14 days",
    "confidence_score": 0.78,
    "ui_url": "https://sylion.local/advisor/cards/card-..."
  }
}
```

### 10.2 `aeis.advisor.engine.llm_judge_call_completed`

```json
{
  "event_type": "aeis.advisor.engine.llm_judge_call_completed",
  "payload": {
    "judge_purpose": "rationale_generation",
    "model_id": "claude-sonnet-4-6",
    "prompt_tokens": 1840,
    "completion_tokens": 612,
    "cost_usd": 0.0344,
    "latency_ms": 1820,
    "evidence_pack_id": "ep-...",
    "card_id": "card-..."
  }
}
```

### 10.3 `aeis.advisor.role_resolver.routing_decision`

```json
{
  "event_type": "aeis.advisor.role_resolver.routing_decision",
  "payload": {
    "operator_id": "op-7c9d",
    "judge_purpose": "alternatives_ranking",
    "risk_level": "high",
    "resolved_model": "claude-opus-4-7",
    "reason": "default_routing",
    "estimated_cost_usd": 0.21,
    "rejected_candidates": [
      {"model_id": "gpt-5", "reason": "blocked_provider"}
    ]
  }
}
```

### 10.4 `aeis.advisor.subscription.purchase_blocked`

```json
{
  "event_type": "aeis.advisor.subscription.purchase_blocked",
  "payload": {
    "plan_id": "anthropic_pro_monthly",
    "block_reason": "missing_evidence_pack",
    "evidence_pack_id": null,
    "card_id": "card-...",
    "operator_action_required": "create_evidence_pack"
  }
}
```

### 10.5 `aeis.advisor.outbound.slack.message_sent`

```json
{
  "event_type": "aeis.advisor.outbound.slack.message_sent",
  "payload": {
    "channel": "ops-alerts",
    "slack_msg_ts": "1714123456.123456",
    "latency_ms": 412,
    "rule_name": "high_risk_to_slack_ops",
    "source_event_id": "9f1c5b2e-..."
  }
}
```

### 10.6 `aeis.advisor.preferences.hard_change_requested`

```json
{
  "event_type": "aeis.advisor.preferences.hard_change_requested",
  "payload": {
    "pref_key": "autonomy_level",
    "current_value": "manual",
    "proposed_value": "auto",
    "confirmation_token": "tok-9f1c5b2e",
    "expires_at": "2026-04-26T13:34:56Z"
  }
}
```

### 10.7 `aeis.advisor.events.validation_failed`

```json
{
  "event_type": "aeis.advisor.events.validation_failed",
  "payload": {
    "attempted_event_type": "aeis.advisor.engine.recommendation_emitted",
    "validation_errors": [
      "missing_required_field: card_id",
      "d_level not in [D0..D5]"
    ],
    "producer_module": "sylion.aeis.advisor.engine",
    "raw_payload_hash": "sha256:..."
  }
}
```

---

## 11. PG LISTEN/NOTIFY i replay

### 11.1 NOTIFY

Każdy INSERT do `advisor_events.events` wyzwala trigger:

```sql
NOTIFY advisor_events_events_<partition>, '{"event_id":"...","event_type":"...","sequence_no":N}'
```

### 11.2 LISTEN — przykład

```python
import psycopg
import json

async with await psycopg.AsyncConnection.connect(dsn) as conn:
    async with conn.cursor() as cur:
        await cur.execute("LISTEN advisor_events_events_2026_04;")
        async for notif in conn.notifies():
            event_summary = json.loads(notif.payload)
            # fetch full event by event_id
            await cur.execute(
                "SELECT payload_jsonb FROM advisor_events.events WHERE event_id = %s",
                (event_summary["event_id"],),
            )
            row = await cur.fetchone()
            handle(row[0])
```

### 11.3 Replay (late-joiner)

```sql
SELECT *
FROM advisor_events.events
WHERE produced_at > $since
  AND (event_type = ANY($interested_types) OR $interested_types IS NULL)
ORDER BY sequence_no ASC
LIMIT $limit;
```

Mobile reconnect:
1. Klient zapisuje `last_seen_sequence_no` lokalnie.
2. Po reconnect wysyła `since=last_seen_produced_at` do `/api/v1/advisor/events/replay`.
3. Backend zwraca w paginacji wszystkie eventy od `since` (filter po typach interesujących mobile).

---

## 12. Partycjonowanie i retencja

### 12.1 Partycje

Tabela `advisor_events.events` jest **partycjonowana po dacie** (range partitioning po `produced_at`):

- Granularność: miesięczna (`advisor_events_events_2026_04`).
- Manager: `sylion.aeis.advisor.events.partition_manager` (cron, tworzy partycje na +1 miesiąc).
- Indexy per partycja: `(event_type)`, `(operator_id)`, `(correlation_id)`, `(produced_at)`.

### 12.2 Retencja (per prefix)

| Prefix eventu | Retencja | Storage tier |
|---|---|---|
| `aeis.advisor.engine.llm_judge_*` | Zawsze | Hot 12mo, cold po (indeksowalne) |
| `aeis.advisor.history.*` | Zawsze | Hot 12mo, archive po |
| `aeis.advisor.preferences.*audit` | Zawsze | Hot |
| `aeis.advisor.subscription.purchase_*` | Zawsze (legal/financial) | Hot |
| `aeis.advisor.engine.recommendation_emitted` | Zawsze | Hot 12mo, archive po |
| `aeis.advisor.outbound.*` | 90 dni | Hot, potem delete |
| `aeis.advisor.events.validation_failed` | 30 dni | Hot, potem delete |
| `aeis.advisor.role_resolver.*` | 12mo | Hot, potem archive |
| `aeis.advisor.mobile_gateway.request_handled` | 30 dni | Hot |
| `aeis.advisor.mobile_gateway.auth_failure` | 1 rok | Hot |
| `aeis.advisor.pricing.*` | 12mo | Hot |
| `aeis.advisor.scaling.*` | 5 lat | Hot 12mo, cold po |
| `aeis.advisor.funding.*` | 5 lat | Hot 12mo, cold po |
| Lifecycle hooks (`aeis.<phase>.*`) | Wg polityki AEIS | — |

### 12.3 Soft delete vs hard purge

- Eventy **nigdy** nie są mutowane (append-only).
- Po retention window: partycja → cold tier → hard purge.
- Wyjątek: eventy financial/legal/audit (`purchase_*`, `llm_judge_*`, `history.*`) — retencja zawsze.

---

## 13. Walidacja schematów (proto_registry)

### 13.1 Flow walidacji

```
1. Producer calls EventBus.publish(event_type, payload)
2. EventBus → ProtoRegistry.lookup(event_type) → RegistryEntry
3. ProtoRegistry.validate(event_type, payload) → (is_valid, errors[])
4. Jeśli valid:
   - INSERT do advisor_events.events (auto-partition)
   - Trigger NOTIFY
5. Jeśli invalid:
   - INSERT do advisor_events.validation_failures
   - EMIT aeis.advisor.events.validation_failed
   - Raise exception do producenta
```

### 13.2 ProtoRegistry API (skrót)

```python
class ProtoRegistry:
    def register(*, event_type, proto_message_type, validator=None,
                 proto_descriptor=b"", proto_version=1, is_internal=True): ...
    def list_entries() -> list[RegistryEntry]: ...
    def validate(event_type: str, payload: dict) -> tuple[bool, list[str]]: ...
```

### 13.3 Custom validator example

```python
def validate_recommendation_emitted(payload):
    errors = []
    if "card_id" not in payload:
        errors.append("missing_card_id")
    if payload.get("d_level") not in {"D0","D1","D2","D3","D4","D5"}:
        errors.append("invalid_d_level")
    if payload.get("risk_level") not in {"low","medium","high","critical"}:
        errors.append("invalid_risk_level")
    return errors

registry.register(
    event_type="aeis.advisor.engine.recommendation_emitted",
    proto_message_type="advisor.engine.RecommendationEmittedV1",
    validator=validate_recommendation_emitted,
    proto_version=1,
)
```

---

## 14. Audit i correlation_id

### 14.1 Filozofia

Każdy łańcuch zdarzeń wywołany pojedynczą akcją operatora (lub kernelem)
ma **wspólne `correlation_id`**. To pozwala audytorowi zrekonstruować pełną
ścieżkę decyzji jedną kwerendą.

### 14.2 Przykład łańcucha

Akcja: operator wprowadza ideę → advisor sugeruje skład rady.

```
correlation_id: corr-abc-123

1. aeis.idea.intake.completed                           causation=null
2. aeis.advisor.engine.recommendation_emitted           causation=#1
3. aeis.advisor.history.action_recorded (operator OK)   causation=#2
4. aeis.advisor.history.learning_signal_emitted         causation=#3
5. aeis.advisor.preferences.updated                     causation=#4
6. aeis.advisor.outbound.dispatched                     causation=#2
7. aeis.advisor.outbound.slack.message_sent             causation=#6
```

### 14.3 Kwerenda audytora

```sql
SELECT
  sequence_no,
  event_type,
  produced_at,
  payload_jsonb -> 'card_id' AS card_id,
  payload_jsonb -> 'd_level' AS d_level
FROM advisor_events.events
WHERE correlation_id = 'corr-abc-123'
ORDER BY sequence_no ASC;
```

---

## 15. Trace propagacja (OpenTelemetry)

Każdy event posiada `trace_id` (W3C trace context). Propagacja:

```
[UI/Mobile] → ui.click_card span (trace_id=T1)
       │
       └─→ POST /api/v1/advisor/cards/{id}/accept (header: traceparent=00-T1-...)
                │
                └─→ engine.IssueCard span (parent=T1) → trace_id=T1
                        │
                        ├─→ llm_judge.completion span
                        ├─→ pg.insert span → NOTIFY
                        └─→ outbound.dispatch span
                                │
                                └─→ slack.api.call span
```

Każdy event emituje z `trace_id=T1`, więc Jaeger/Tempo może zrekonstruować
distributed trace z perspektywy oryginalnego kliknięcia operatora.

---

## 16. Cross-references

- DB schema (proto_registry, events, validation_failures, dispatches): `00_architektura_systemu.md`
- Lifecycle hooks (16 events) — szczegóły kerneli: `01_modul_aeis_advisor.md`
- Per-module manifesty (emits/subscribes): `src/sylion-pipeline/sylion/contracts/manifests/aeis.advisor.*.json`
- D-ladder (eventy zmieniają D-level): `31_d_ladder_complete.md`
- Evidence Pack templates (`evidence_pack_required` event flow): `32_evidence_pack_templates.md`
- Council Hybrid (eventy podpisów krytyka i sentineli): `33_council_hybrid.md`
- LLM pool routing (eventy `routing_decision`): `34_llm_pool_routing.md`
- Walidacja schematów: kod `src/sylion-pipeline/sylion/aeis/advisor/events/proto_registry.py`
- Audit subscriber: `src/sylion-pipeline/sylion/aeis/advisor/events/audit_subscriber.py`
- Lifecycle helper: `src/sylion-pipeline/sylion/aeis/advisor/events/lifecycle.py`
