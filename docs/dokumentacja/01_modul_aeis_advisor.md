# AEIS Advisor Layer — moduł deep-dive

> 13. warstwa AEIS, Etap 1. Status: foundation specs ukończone, implementacja w trakcie.
> Namespace: `sylion.aeis.advisor.*`. Ścieżka: `src/sylion-pipeline/sylion/aeis/advisor/`.

## Spis treści

- [1. Cel warstwy](#1-cel-warstwy)
- [2. 4 filary architektury](#2-4-filary-architektury)
- [3. 11 modułów backend](#3-11-modułów-backend)
- [4. 4 surface frontend](#4-4-surface-frontend)
- [5. 16 lifecycle hooks](#5-16-lifecycle-hooks)
- [6. AdvisorCard — kontrakt rekomendacji](#6-advisorcard--kontrakt-rekomendacji)
- [7. Hybrid LLM-as-judge (production-grade)](#7-hybrid-llm-as-judge-production-grade)
- [8. Confidence — 4 komponenty](#8-confidence--4-komponenty)
- [9. 3D preference matrix + 4-level fallback](#9-3d-preference-matrix--4-level-fallback)
- [10. Decision ladder enforcement](#10-decision-ladder-enforcement)
- [11. Funding subsystem](#11-funding-subsystem)
- [12. Mobile gateway (Etap 1 stub → Etap 2)](#12-mobile-gateway-etap-1-stub--etap-2)
- [13. Storage: PG-only (świadoma divergencja)](#13-storage-pg-only-świadoma-divergencja)
- [14. Event bus integration](#14-event-bus-integration)
- [15. Cross-references](#15-cross-references)

---

## 1. Cel warstwy

### Co

AEIS Advisor Layer transformuje AEIS z **pasywnego dashboardu** w **aktywnego asystenta operatora**.
Operator nie szuka informacji — system sam podpowiada, ostrzega, sugeruje "co dalej".

### Misja

- **Każda rekomendacja wyjaśnia**: *dlaczego*, *jaki trade-off*, *jakie ryzyko* (nie tylko *co*).
- **Każda akcja jest odwracalna lub udokumentowana** (Evidence Pack przy D5; lżej niżej).
- **Preferencje uczone soft (auto) i hard (z potwierdzeniem)** — nigdy po cichu.
- **Koszt śledzony per rekomendacja** (token + USD) — bez ukrytych obciążeń.
- **Funding research opt-in** — token-heavy operacje wymagają jawnej zgody.

### Non-goals (v1)

- Zastępowanie osądu operatora.
- Auto-zakup płatnych usług (zawsze HG).
- Hardcoded provider pricing (musi pochodzić z adapterów / profili / live metadata).
- Multi-operator collaboration.
- ML-based learning poza hybrid rule + LLM judge.
- Meta-rekomendacje modyfikujące własną konfigurację Advisor (configurable, default OFF).

---

## 2. 4 filary architektury

### Filar 1 — Adaptive Preference Layer

10+ preferencji operatora, indeksowane macierzą 3D `(user × project_type × project_domain)`.
4-level fallback cascade.

Przykładowe preferencje:
- `autonomy_level` (manual / suggest / auto) — **hard preference**
- `runtime_strategy` (local / VPS / hybrid) — **hard**
- `trusted_providers`, `blocked_providers` — **hard**
- `cost_ceiling_per_risk` (low/med/high/critical/funding) — **hard**
- `funding_advisor_enabled`, `meta_recommendations_enabled` — **hard**
- Soft: `preferred_council_size`, `card_visibility_threshold`, `notification_channels`

### Filar 2 — Contextual Recommendation Engine

Emituje `AdvisorCard` na 16 lifecycle hooks. Hybrid: **rule engine + LLM-as-judge**.

Routing matrix global (nie per-domain). Default w onboardingu, operator może override.

### Filar 3 — Specialized Advisors

| Advisor | Cel |
|---|---|
| `subscription` | ROI advisor dla planów subskrypcyjnych, hard gate na purchase, Evidence Pack D3+ |
| `scaling` | local / VPS / hybrid topologia, staged scaling, auto-detect granicy |
| `funding` | Opt-in. Per-grant scoring profiles, company data, consortium suggestions |
| `role_resolver` | Mapuje abstract role (planner/worker/critic) → konkretny model LLM |
| `variants` | 3 strategiczne warianty: cost-saving / balanced / aggressive |

### Filar 4 — Guided Operator Journey UI

- **Onboarding Wizard** (10 kroków, skip allowed z banerem "incomplete setup").
- **Project Lifecycle Dashboard** — primary entry point po onboardingu.
- **Monitoring Dashboard** — multi-project matrix, throughput, koszty.
- **Live Advisor Feed** — hybrid toast (low-risk) + modal (high-risk) + bubble counter.

---

## 3. 11 modułów backend

| # | Moduł | Cel | Owner stage |
|---|---|---|---|
| 1 | `preferences` | 3D matrix + audit + reset/disable | Codex (Stage 1) |
| 2 | `pricing` | Provider adapters, profiles, live metadata, ASSUMPTION flag | Codex (Stage 1) |
| 3 | `engine` | Hybrid rule + LLM judge, AdvisorCard builder, 16 hooks | Kimi (Stage 2) |
| 4 | `role_resolver` | Mapuj rolę → model | Kimi (Stage 2) |
| 5 | `variants` | 3 strategiczne warianty wykonania | Kimi (Stage 2) |
| 6 | `subscription` | Plan ROI, hard gate purchase, D3+ Evidence Pack | Kimi (Stage 2) |
| 7 | `scaling` | Topology advisor, staged scaling | Kimi (Stage 2) |
| 8 | `funding` | Opt-in, per-grant scoring, consortium | Kimi (Stage 2) |
| 9 | `history` | Event-sourced learning, confidence calc, soft learning | Codex (Stage 3) |
| 10 | `actions` | 7 card actions + konwertery | Codex (Stage 1) |
| 11 | `mobile_gateway` | REST API gateway → internal gRPC | Claude (Etap 2) |

Plus: `events/` (audit subscriber), `proto/`, `_generated/`.

### Struktura katalogu

```
sylion/aeis/advisor/
├── __init__.py
├── _db.py                         # PG connection helpers
├── preferences/
│   ├── service.py
│   ├── resolver.py
│   ├── audit.py
│   └── proto/preferences.proto
├── pricing/
│   ├── service.py
│   └── adapters/
│       ├── anthropic_adapter.py
│       ├── openai_adapter.py
│       ├── google_adapter.py
│       └── ollama_adapter.py
├── engine/
├── role_resolver/
├── variants/
├── subscription/
├── scaling/
├── funding/
├── history/
├── actions/
├── mobile_gateway/
├── events/                        # audit subscriber + proto registry
├── proto/                         # advisor proto definitions
└── _generated/                    # gRPC stubs
```

### Manifesty modułów

Każdy moduł ma 2 manifesty:
1. **Spec YAML** w `docs/claude_parallel/aeis_advisor/00_architecture/03_module_manifests.md` (canonical dla ludzi).
2. **JSON deployment artifact** w `sylion/contracts/manifests/aeis.advisor.{module}.json`.

Auto-rejestracja: `sylion.core.auto_register.auto_register_modules()` przy starcie aplikacji.
Nowy enum: `ModuleKind.ADVISOR` (dodany w `sylion/core/module_registry.py`).

---

## 4. 4 surface frontend

| # | Surface | Cel |
|---|---|---|
| F1 | `surface_feed` | Live Advisor Feed (toast + modal + counter). Max 3 widoczne + queue counter. |
| F2 | `wizard` | Onboarding Wizard (10 kroków) + Settings Configurator |
| F3 | `lifecycle_dashboard` | Project Lifecycle Dashboard (16 hooks visualization, primary po onboardingu) |
| F4 | `monitoring_dashboard` | Operator Monitoring Dashboard (multi-project, throughput, koszty) |

Plus: legacy technical dashboards są nadal dostępne via "Switch to Technical Mode" link
(zawsze widoczny w nawigacji).

### Bubble UX (Live Feed)

```
risk_level == 'low'      →  toast (5s, auto-dismiss)
risk_level == 'medium'   →  toast persistent (manual dismiss)
risk_level == 'high'     →  modal (non-blocking, semi-transparent overlay)
risk_level == 'critical' →  modal blocking (cannot dismiss without action)

Max 3 visible cards   →  queue counter "+N more"
```

---

## 5. 16 lifecycle hooks

Pełna lista z payload + subscriber:

| ID | Event | Faza | Trigger |
|---|---|---|---|
| H01 | `aeis.system.model_setup_requested` | setup | Konfiguracja base model |
| H02 | `aeis.system.api_provider_setup_requested` | setup | Add/edit/remove provider |
| H03 | `aeis.system.budget_config_requested` | setup | Edycja budżetu |
| H04 | `aeis.idea.intake.completed` | ideation | Submit idei |
| H05 | `aeis.idea.sot_model_selection_requested` | drafting | Wybór modelu dla SoT |
| H06 | `aeis.council.formation_requested` | governance | Formowanie rady (D2+) |
| H07 | `aeis.system.autonomy_policy_change_requested` | governance | Zmiana autonomy_level |
| H08 | `aeis.idea.sot_drafted` | drafting | Save draft SoT |
| H09 | `aeis.masterplan.created` | planning | Finalizacja Masterplan |
| H10 | `aeis.system.runtime_topology_change_requested` | execution_setup | Wybór topologii |
| H11 | `aeis.system.vps_scaling_requested` | execution_setup | Add/scale VPS |
| H12 | `aeis.system.skill_selection_requested` | execution_setup | Wybór skills |
| H13 | `aeis.production.deploy_requested` | execution | Deploy prod (synchronous gate, 5s) |
| H14 | `aeis.testing.started` | validation | Start test suite |
| H15 | `aeis.human_gate.ticket_pending` | approval | Nowy HG ticket |
| H16 | `aeis.final_approval.requested` | closure | Final approval |

### Synchronous-gate hooks

Hooks H06 (D5), H13, H16 są **synchroniczne** — endpoint emituje event i CZEKA na advisor
(timeout 5s). Engine zwraca `proceed | block | defer_to_human_gate`:
- `block` → endpoint zwraca **423 Locked** z AdvisorCard wyjaśniającym dlaczego.
- `defer` → endpoint tworzy HG ticket i zwraca **202 Accepted** z `ticket_id`.
- `proceed` → normal flow.

Pozostałe hooks (H01–H05, H07–H12, H14, H15) są asynchroniczne.

### Convention nazewnictwa

```
aeis.<phase>.<entity>.<action>
```

- `<phase>`: `idea`, `council`, `production`, `system`, `testing`, ...
- `<entity>`: `intake`, `formation`, `deploy`, ...
- `<action>`: past-tense (`completed`, `requested`, `pending`, `crossed`)

Advisor-emitowane events: prefix `aeis.advisor.*`.

### Companion events (nie hooks, ale advisor subskrybuje)

| Event | Source | Użyte przez advisor do |
|---|---|---|
| `aeis.system.budget_threshold_crossed` | monitoring_budget_routes | Cost-saving recommendations |
| `aeis.council.formed` | CouncilHybrid | confidence component (council_match) |
| `aeis.advisor.preferences.updated` | preferences (self) | re-evaluate active cards |
| `aeis.advisor.pricing.refreshed` | pricing (self) | invalidate cost estimates |
| `aeis.advisor.engine.recommendation_emitted` | engine (self) | history records action |
| `aeis.idea.sot_approved` | idea_routes | gate dla production deploy |

---

## 6. AdvisorCard — kontrakt rekomendacji

### Hierarchia kart

```
AdvisorCard (abstract base)
├── DecisionCard      ← rekomendacje operacyjne (15 typów)
├── FundingCard       ← rekomendacje grantowe (10 typów)
├── SecurityCard      ← v2 placeholder
├── ScalingCard       ← v2 placeholder
└── OnboardingCard    ← v2 placeholder
```

### Polimorfizm

`AdvisorCardEnvelope` z `oneof body` — pozwala na wielość typów kart w jednym strumieniu.

### Wspólne pola headera

```
card_id              UUID
operator_id          UUID
project_id           optional UUID
created_at           timestamp
risk_level           low | medium | high | critical
d_level              D0–D5
evidence_pack_id     optional UUID (required gdy d_level=D5)
confidence           0.0–1.0
ttl_seconds          optional integer
```

### 7 akcji operatora na karcie

```
accept           →  zaakceptuj rekomendację (action handler aplikuje)
reject           →  odrzuć (history zapisuje signal)
modify           →  zmodyfikuj parametry → konwersja do nowej karty
remind           →  odłóż na później
not-useful       →  signal: ta klasa kart jest mało wartościowa
convert→HG       →  konwertuj na Human Gate ticket
convert→Masterplan → zapisz jako change proposal w Masterplan
```

Plus toggle: `don't learn from this decision` per card (skip_learning=true w history).

### Obowiązkowe sekcje treści

Każda karta ma 3 sekcje narracyjne (LLM-judge generuje):
- `rationale` — dlaczego ta decyzja
- `tradeoff` — co tracimy / co zyskujemy
- `risk` — co może pójść nie tak

---

## 7. Hybrid LLM-as-judge (production-grade)

### Zasada

Engine NIE startuje jako "rules-only, LLM dodamy później". Od dnia 1:
- **Rule engine** decyduje IF advice powinno wystrzelić i WHAT type.
- **LLM judge** produkuje rationale, alternatives ranking, risk assessment, soft criteria scoring.
- **Oba są wymagane** dla valid AdvisorCard.

### Przepływ emit-time

```
1. lifecycle event arrives via event_bus
2. engine subscribes (pattern: aeis.<phase>.*)
3. engine builds context:
   - preferences (resolved via 4-level cascade)
   - history (similar past cards)
   - pricing snapshot (current cost estimates)
4. RULE ENGINE evaluates:
   - should we emit? (anti-spam rules, dedup, TTL)
   - what RecommendationType?
   - initial D-level (default mapping)
5. role_resolver picks LLM judge model:
   - per (risk × project_type × cost_ceiling)
   - default routing matrix from onboarding
6. LLM JUDGE generates:
   - rationale (200–800 słów)
   - alternatives ranked
   - risk assessment
   - soft scoring (0.0–1.0)
7. Engine applies upgrade rules (U1–U6) → final D-level
8. If D≥3 cost/subscription/funding → builds Evidence Pack draft
9. AdvisorCard envelope built, validated against proto
10. Emit via backbone.publish() → event_bus → audit subscriber → PG
11. Full LLM call audited (prompt + response + cost + latency) → llm_judge_audit
    (forever retention)
12. surface_feed renders (toast/modal based on risk_level)
```

### LLM pool default (z onboarding)

| Provider | Model | Rola |
|---|---|---|
| Ollama | `qwen2.5:72b-instruct` | local primary judge |
| Ollama | `qwen2.5:7b-instruct` | local mini (fallback) |
| Anthropic | `claude-sonnet-4-6` | external primary |
| OpenAI | `gpt-5` | external primary |
| Google | `gemini-2.5-pro` | external primary |
| Anthropic | `claude-opus-4-7` | optional adapter |
| Anthropic | `claude-haiku-4-5` | optional adapter |
| Moonshot | Kimi K2 | optional (long context) |
| z.ai | GLM-4.6 | optional |
| xAI | Grok 4 | optional |

---

## 8. Confidence — 4 komponenty

### Wzór

```
confidence = 0.4 · council_match
           + 0.4 · history_match
           + 0.2 · pricing_quality
           + (4. komponent) historical_acceptance_rate
```

Multiplier:
```
if used_local_fallback:
    final = base × 0.8
```

### Komponenty

| Komponent | Co mierzy | Skala |
|---|---|---|
| **council_match** | Jak rekomendacja jest aligned z aktualnymi weighted votes Rady Modeli | 0.0–1.0 |
| **history_match** | Podobne past cards i ich acceptance rate | 0.0–1.0 |
| **pricing_quality** | Świeżość/jakość źródła kosztów (live > profile > assumption) | 0.0–1.0 |
| **historical_acceptance_rate** | Rate akceptacji podobnych kart przez TEGO operatora | 0.0–1.0 |

### Progi

```
high   : confidence > 0.75
medium : 0.50 ≤ confidence ≤ 0.75
low    : confidence < 0.50
```

Confidence breakdown jest **persisted** w `advisor_engine.recommendations.body_jsonb`
i obowiązkowo w Evidence Pack przy D3+.

---

## 9. 3D preference matrix + 4-level fallback

### Macierz

Preferencje są indeksowane przez 3 wymiary:
```
(user_id, project_type, project_domain)
```

`project_type` (z idei): np. `research`, `production_app`, `internal_tool`, `audit`, ...
`project_domain` (z idei): jeden z 14 base immutable + custom z prefiksem.

### 14 base immutable domains

```
funding         software       audit         mobile
infrastructure  data_analytics security      governance
research        marketing      legal         product_management
finance         operations
```

Custom domains: prefix `custom_*` (np. `custom_robotics`).

### 4 risk levels

```
low  →  medium  →  high  →  critical
```

### 4-level fallback cascade

Resolution order od najbardziej szczegółowego do default:

```
Level 1 (most specific): (user, type=X,    domain=Y)
Level 2:                 (user, type=X,    domain=NULL)
Level 3:                 (user, type=NULL, domain=Y)
Level 4:                 (user, type=NULL, domain=NULL)   ← per-user default
Level 5 (fallback):      (NULL, NULL, NULL)               ← system default
```

### Soft learning

Auto-update preferencji z accept/reject signals (NO confirmation):
- Aktualizuje **most specific level that already has an entry**
- LUB tworzy nowy entry jeśli signal kontekstowo specyficzny
- Sygnał z pracy w `(type=research, domain=funding)` → może utworzyć entry na tym poziomie

### Hard learning

Zmiana **hard preference** wymaga operator click (nie auto):
- `autonomy_level`, `runtime_strategy`, `approval_timeout_behavior`
- `trusted_providers`, `blocked_providers`
- `funding_*_enabled`, `meta_recommendations_enabled`

Flow: `RequestHardChange()` → operator confirmation → `ConfirmHardChange()`.

### "Don't learn from this"

Per-card toggle. Gdy operator klika → history flagged `skip_learning=true` dla tej karty;
nie wpływa na preference updates.

---

## 10. Decision ladder enforcement

### Engine assigns D-level

Pseudokod (pełen w `05_decision_ladder.md`):

```python
def assign_d_level(card_context, recommendation_type, suggestion_type=None):
    d = DEFAULT_MAPPING[recommendation_type]
    if suggestion_type:
        d = max(d, FUNDING_DEFAULT_MAPPING[suggestion_type])

    d = apply_rule_u1_cost_magnitude(d, card_context)
    d = apply_rule_u2_blast_radius(d, card_context)
    d = apply_rule_u3_reversibility(d, card_context)
    d = apply_rule_u4_hard_preferences(d, card_context)
    d = apply_rule_u5_autonomy(d, card_context)

    return min(d, DecisionLevel.D5)
```

### Audit trail

Każda karta przechowuje pełną ścieżkę decyzyjną w `body_jsonb`:

```json
{
  "d_level_assignment_trace": {
    "default_from_type": "D2",
    "rules_applied": [
      {"rule": "U1_cost_magnitude", "input": "$1500", "delta": "+2"},
      {"rule": "U2_blast_radius", "input": "production", "delta": "+1"}
    ],
    "final": "D5",
    "capped_at_d5": true
  }
}
```

### Evidence Pack requirement

| Trigger | Template |
|---|---|
| `d_level == D5` | **D5 Full** (mandatory) |
| `d_level == D4` | **D5 Full** |
| Cost/subscription rec @ D3+ | **D3 Light** |
| Funding `FORM_COMPANY` / `CHANGE_LEGAL_FORM` / `REGIONAL_RELOCATION` | **D3 Light** |
| Production deploy override | **D5 Full** |
| Inne | None |

Karta NIE może być wyemitowana zanim Evidence Pack draft nie istnieje (PG constraint).

---

## 11. Funding subsystem

### Cechy

- **Opt-in** — operator musi włączyć `funding_advisor_enabled` (hard preference).
- **Separate token budget** — niezależnie od ogólnego advisor budget.
- **Per-country settings** — PL z województwami, EU z państwami członkowskimi.
- **Per-grant scoring profiles** — KAŻDY grant ma własny profil scoringowy.

### Per-grant scoring profile (kluczowy insight)

Funding scoring NIE jest hardcoded. Każdy program grantowy ma własny `scoring_profile`:

#### Universal pool 7 komponentów (append-only catalog)

```
eligibility            thematic_alignment   capacity
competitive_position   regional_fit         consortium_readiness
timeline_fit
```

#### Per-grant config

- Subset komponentów używanych
- Wagi
- Hard floors (minimum thresholds)
- Custom criteria (per-grant specific)

#### Compute

```python
effective_score = grant.scoring_profile.apply(company_data, idea_data)
```

**Implication**: Ten sam company + ta sama idea → różne granty produkują różne score.
PARP ≠ FENG ≠ Horizon — każdy ma własny profil.

### Schema

```
advisor_funding.scoring_components    -- universal pool, append-only
advisor_funding.scoring_profiles      -- per-grant template
advisor_funding.scoring_history       -- per (company, idea, grant, timestamp) snapshot
```

### 10 typów FundingCard

| Suggestion type | Default D | Evidence Pack |
|---|---|---|
| `FUNDING_GRANT_FIT` | D0 | brak |
| `FUNDING_HOW_TO_QUALIFY` | D1 | brak |
| `FUNDING_FORM_COMPANY` | **D3** | **D3 Light** |
| `FUNDING_CHANGE_LEGAL_FORM` | **D3** | **D3 Light** |
| `FUNDING_REGIONAL_RELOCATION` | **D3** | **D3 Light** |
| `FUNDING_FIND_CONSORTIUM` | D2 | brak |
| `FUNDING_ADJUST_IDEA_FOR_GRANT` | D2 (D3 jeśli zmienia scope) | Light jeśli D3 |
| `FUNDING_DEADLINE_WARNING` | D1 | brak |
| `FUNDING_GAP_CLOSURE_PLAN` | D2 | brak |
| `FUNDING_SCOPE_ADJUSTMENT` | D2 (D3 jeśli zmienia Masterplan) | Light jeśli D3 |

### 3-mode simulator

Operator może symulować scenariusze grantowe:
1. **Single-grant** — jeden grant, what-if scenariusze
2. **Multi-grant comparison** — N grantów, ranking
3. **Consortium impact** — wpływ konsorcjum na score

### Pełny pion (nie dodatek)

Funding to pełny pion procesu:
```
profil firmy → scanning programów → scoring → pakiety dokumentów →
konsorcjum → browser submission → monitoring po grancie
```

---

## 12. Mobile gateway (Etap 1 stub → Etap 2)

### Etap 1 (obecnie)

Tylko `mobile_gateway` jako REST API gateway. Translacja REST→gRPC. Brak rzeczywistej mobile app.

```
Mobile app  →  REST/JSON  →  mobile_gateway  →  internal gRPC  →  advisor modules
```

Cel: stable + auditable interfejs (NIE direct gRPC z mobile).

### Etap 2 (planowane)

- Kotlin Multiplatform, Android first.
- Jetpack Compose UI.
- Firebase FCM dla push.
- Android `BiometricPrompt` + Keystore (device-bound JWT).
- Biometric step-up dla D3+ akcji (operator musi potwierdzić palcem/twarzą).
- Offline cache: 50 last cards + 10 active projects + HG pending + 30 funding deadlines.
- **No write queue offline** — wszystkie write operations wymagają online.

### Etap 3 (deferred)

iOS via SwiftUI shared przez KMP. LocalAuthentication dla biometric.

---

## 13. Storage: PG-only (świadoma divergencja)

### Decyzja

Advisor layer to **pierwsza PG-only rodzina modułów** w SYLION. Świadoma divergencja od
istniejącego pattern (SQLite-dominant), per operator decision: *"musimy przejść na PG po
mojemu, od razu robić docelowy duży system z bazą danych"*.

### Implikacje

1. **No SQLite fallback** dla advisor modules.
2. **Connection pool**: `psycopg[pool]` (sync) lub `asyncpg` (tylko gdzie naprawdę async).
3. **Migracja**:
   - Dopisz advisor schema do `sylion/db/pg_migration._PG_SCHEMA_SQL`
   - Nowy Alembic revision `alembic/versions/20260425_0002_advisor_layer.py`
   - Pełen schema w `02_postgresql_schema.sql`
4. **Test database** — real PG instance (NIE SQLite mocks). Query semantics różnią się
   wystarczająco że mocki maskowałyby bugi.
5. **Local dev** — PG via Docker (`docker-compose.yml`) lub native.

### Schema-per-module

```
advisor_preferences.*       (8 tabel)
advisor_pricing.*           (4 tabele)
advisor_engine.*            (recommendations + llm_judge_audit + ...)
advisor_role_resolver.*
advisor_variants.*
advisor_subscription.*
advisor_scaling.*
advisor_funding.*           (scoring_components, scoring_profiles, scoring_history, ...)
advisor_history.*
advisor_actions.*
advisor_events.*            (audit subscriber: events, validation_failures, proto_registry)
advisor_evidence.*          (evidence_packs, signatures)
```

### Retention

- **History**: forever (partitioned monthly).
- **LLM judge audit**: forever (partitioned monthly).
- **Validation failures**: 90 dni rolling.

---

## 14. Event bus integration

### Decyzja: użyj istniejącego `sylion.core.event_bus`

Audyt repozytorium ujawnił że `sylion/core/event_bus.py` + `event_backbone.py` +
`nats_event_bus.py` są production-ready. **Nie budujemy nowego** PG-based event store
jako primary transport.

### 3 backendy selektowalne

```
SYLION_EVENT_MODE=sqlite   (default — file lub in-memory, single-node)
SYLION_EVENT_MODE=nats     (NATS JetStream — durable, distributed)
SYLION_EVENT_MODE=redis    (Redis Pub/Sub — pattern subscriptions)
```

### API publish

```python
from sylion.core.event_bus import SylionEvent
from sylion.core.event_backbone import get_event_backbone
import time, uuid

event = SylionEvent(
    event_id=str(uuid.uuid4()),
    topic="aeis.advisor.engine.recommendation_emitted",
    payload={"card_id": "...", "risk_level": "high", ...},
    source_module="sylion.aeis.advisor.engine",
    timestamp=time.time(),
    idempotency_key=f"card:{card_id}:emitted",
)
get_event_backbone().publish(event)
```

### API subscribe (pattern match)

```python
def my_handler(event: SylionEvent):
    if event.topic.startswith("aeis.advisor.engine."):
        # ... process ...

get_event_backbone().subscribe("aeis.advisor.*", my_handler)
```

### `advisor_events.events` table

NIE jest primary store. Jest **audit subscriber** dla forever-retention:
1. Subskrybuje wszystkie `aeis.advisor.*` z event_bus.
2. Persistuje do PG z forever retention.
3. Validuje payload przeciw proto registry **przed publish** (rejecting invalid upstream).
4. Provides query/replay API dla advisor history reconstruction.

### Schema validation

Każdy event walidowany przed publish przez helper czytający `advisor_events.proto_registry`.
Failures → `aeis.advisor.events.validation_failed` (logged, NOT stored w main log).

### Outbound adapter pattern

Inter-system events (Slack/email/FCM/webhook) NIE są first-class events. Są emitowane
przez outbound dispatcher gdy internal event matches configured rule:

```
internal: aeis.advisor.engine.recommendation_emitted (high-risk)
        ↓
outbound dispatcher checks rules:
        - "high-risk → Slack #ops + FCM operator-mobile"
        ↓
outbound events:
        - aeis.advisor.outbound.dispatched (channel=slack)
        - aeis.advisor.outbound.dispatched (channel=fcm)
        ↓
adapters consume → Slack API / Firebase
        ↓
on success/failure:
        - aeis.advisor.outbound.delivered
        - aeis.advisor.outbound.failed
```

To utrzymuje internal event log clean (signal only) z support'em dla dowolnej liczby
outbound integracji.

---

## 15. Cross-references

| Temat | Lokalizacja |
|---|---|
| Architektura całego systemu | [00_architektura_systemu.md](./00_architektura_systemu.md) |
| Codzienny workflow | [02_operational_manual.md](./02_operational_manual.md) |
| D0–D5 + Evidence Pack | [03_governance_audit_compliance.md](./03_governance_audit_compliance.md) |
| Onboarding developera | [04_dla_developera.md](./04_dla_developera.md) |
| Master spec (źródło) | `docs/claude_parallel/aeis_advisor/00_architecture/00_master_spec.md` |
| AdvisorCard schema | `docs/claude_parallel/aeis_advisor/00_architecture/01_advisor_card_schema.md` |
| PG schema | `docs/claude_parallel/aeis_advisor/00_architecture/02_postgresql_schema.sql` |
| Module manifests | `docs/claude_parallel/aeis_advisor/00_architecture/03_module_manifests.md` |
| Lifecycle hooks | `docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md` |
| Decision ladder | `docs/claude_parallel/aeis_advisor/00_architecture/05_decision_ladder.md` |
| Evidence Pack templates | `docs/claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md` |
| Event taxonomy | `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` |
| Audit revisions (BINDING) | `docs/claude_parallel/aeis_advisor/00_architecture/08_audit_revisions.md` |
