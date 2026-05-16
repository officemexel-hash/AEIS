# SYLION AEIS — Pełny opis systemu i decyzje projektowe

**Data**: 2026-04-26 (decyzje z sesji 2026-04-25 / 2026-04-26)
**Wersja**: 1.0
**Język**: polski
**Status**: dokument kanoniczny — wszystkie decyzje uzgodnione w trakcie sesji planowania

---

## Spis treści

1. [Wprowadzenie — czym jest SYLION AEIS](#1-wprowadzenie)
2. [Architektura wysokopoziomowa](#2-architektura)
3. [Pierwsze uruchomienie + Onboarding](#3-pierwsze-uruchomienie)
4. [Pojęcie operatora i preferencji](#4-operator-preferencje)
5. [Doradca (Advisor Layer) — 4 filary](#5-advisor-layer)
6. [Modele LLM — pula, routing, koszty](#6-modele-llm)
7. [Karty advisor (AdvisorCards)](#7-karty-advisor)
8. [Decyzyjność — D-ladder + Evidence Pack + Council](#8-decyzyjnosc)
9. [Funding Module](#9-funding-module)
10. [Aplikacja mobilna (Etap 2)](#10-aplikacja-mobilna)
11. [Human Gates](#11-human-gates)
12. [Audyt + zgodność](#12-audyt-zgodnosc)
13. [Multi-agent orchestration](#13-multi-agent-orchestration)
14. [Testowanie produkcyjne — 10 person + Stage C](#14-testowanie-produkcyjne)
15. [Production gates (hybrid)](#15-production-gates)
16. [UX i stylistyka](#16-ux-stylistyka)
17. [Roadmap — Etapy 1→7](#17-roadmap)
18. [Słownik](#18-slownik)

---

<a name="1-wprowadzenie"></a>
## 1. Wprowadzenie — czym jest SYLION AEIS

**SYLION AEIS** to **adaptacyjny system inteligencji ekosystemu** który zamienia bierny dashboard w aktywnego asystenta operatora. Pomaga operatorowi prowadzić projekty od pomysłu do produkcji, **proaktywnie sugerując** decyzje, ostrzegając przed ryzykiem, i **uczy się** z czasem preferencji operatora.

### Główne cele
- Redukcja obciążenia poznawczego operatora przy zachowaniu audyt-grade governance
- Każda rekomendacja **wyjaśnia dlaczego**, **jaki trade-off**, **jakie ryzyko** — nie tylko "co"
- Każda akcja jest **odwracalna lub udokumentowana** (Evidence Pack przy D5, lżejszy audyt przy niższych D-levels)
- Preferencje operatora są **uczone soft (auto)** i **hard (z potwierdzeniem)** — nigdy po cichu
- **Koszty śledzone** per-rekomendacja (tokeny + USD) — żadnych ukrytych opłat
- **Funding research** = opt-in (operacje token-heavy wymagają zgody)

### Co system NIE robi (świadome wykluczenia v1)
- Nie zastępuje sądu operatora
- Nigdy nie kupuje subskrypcji bez Human Gate
- Nie ma hardcoded cen providerów (musi przychodzić z adapterów / profilowy / live metadata; jeśli brak → flag ASSUMPTION)
- Nie wspiera multi-operator collaboration (Etap 5+)
- Nie wykonuje real-time push do nie-mobilnych klientów

---

<a name="2-architektura"></a>
## 2. Architektura wysokopoziomowa

System jest podzielony na **12 warstw kanonu** (per AEIS Canonical Full Model):

| # | Warstwa | Zawartość |
|---|---|---|
| 1 | Operator Interface | Dashboardy, mobilna aplikacja, settings |
| 2 | Idea Lifecycle | 15 statusów (intake → archived) |
| 3 | Council Hybrid | 9 ról, 5 rang, weighted vote, critic gate, sentinele |
| 4 | Decision Gates | D0–D5 ladder + Evidence Pack |
| 5 | Source of Truth + Masterplan | Dokumentacja decyzji + plan wykonawczy |
| 6 | Execution Pipeline | Bundle / deployment / staging |
| 7 | Skills Registry | Plan 18 — biblioteka umiejętności |
| 8 | Demand Signal Analyzer | Plan 20 — analiza popytu |
| 9 | Memory + Vault | Pamięć systemowa + Idea Vault |
| 10 | Governance + Evidence Spine | Compliance + audytowalna chronologia |
| 11 | Adapter Bus | Multi-provider LLM (kanonu) |
| 12 | (wewnątrz innych) | — |
| **13 (NOWA)** | **Advisor Layer** | **Cały moduł advisor — opisany w sekcji 5** |

Warstwa 13 (advisor) to **świadomy dodatek** zaprojektowany w trakcie tej sesji. Nie była w oryginalnym kanonie — jest naszym kluczowym dorobkiem.

### Stack techniczny

**Backend**:
- Python 3.11+
- gRPC (`grpcio`)
- Sync-first (FastAPI sync routes, gRPC sync) — match istniejącego repo pattern
- PostgreSQL 15+ (advisor jest **PG-only** — świadoma divergencja od istniejącego SQLite-dominant patternu)
- Migrations: Alembic + `_PG_SCHEMA_SQL` w `pg_migration.py`

**Frontend**:
- Next.js 16 App Router
- React 19 + Compose-style components
- Tailwind + shadcn/ui
- Style: **modern, modernist, high-tech** (klasa Linear/Vercel/Arc)
- Recharts dla wizualizacji

**Mobile** (Etap 2):
- Kotlin Multiplatform (KMP)
- Android first (Compose UI)
- iOS na koniec (Etap 3)

**Event bus** (CRITICAL — używamy istniejącego):
- `sylion.core.event_bus.SylionEvent` + `get_event_backbone()`
- 3 backendy selectable: SQLite (default), NATS (JetStream), Redis (Pub/Sub)
- Konfiguracja przez env `SYLION_EVENT_MODE`

**LLM pool** (default, konfigurowalny w onboardingu):
- Lokalne (Ollama): `qwen2.5:72b-instruct` (primary), `qwen2.5:7b-instruct` (mini)
- Anthropic: `claude-sonnet-4-6`, `claude-opus-4-7`
- OpenAI: `gpt-5`
- Google: `gemini-2.5-pro`, `gemini-2.5-flash`
- Opcjonalne: Moonshot Kimi K2, z.ai GLM-4.6, xAI Grok 4

---

<a name="3-pierwsze-uruchomienie"></a>
## 3. Pierwsze uruchomienie + Onboarding (10 kroków)

### First-run experience

Gdy operator pierwszy raz odpala system:

1. **Auto-redirect**: jeśli `localStorage.advisor_onboarded != true` AND root path → przekierowanie na `/onboarding`
2. **First-run banner** u góry: "Ukończ ustawienia początkowe (10 kroków)" + button "Zacznij teraz"
3. Banner persistent — operator może dismiss ale wraca przy każdym refresh aż do completion
4. Po krok 10: mark `advisor_onboarded=true` (PG + localStorage) → redirect na `/dashboard/operator-monitor` lub `/projects/[id]/lifecycle` (jeśli idea created w krok 10)

### Wizard 10 kroków

Każdy krok:
- **Po polsku** (operator-facing language)
- **Smart default** w "dymku" advisor — wyjaśnienie dlaczego ta wartość zalecana
- **Skip allowed** (z banner persistent "incomplete setup")
- **Save do PG** po kliknięciu Next (przez REST → gRPC `PreferencesService.Set`)

#### Krok 1 — Welcome + cele
Wstęp: "Witaj w SYLION AEIS. Asystent doradczy pomoże Ci prowadzić projekty od pomysłu do produkcji."
Przyciski: "Zacznij setup" / "Pomiń (incomplete setup banner)"

#### Krok 2 — Provider API keys
Multi-input dla:
- Anthropic (klucz API)
- OpenAI (klucz API)
- Google AI (klucz API)
- Opcjonalne: Moonshot, z.ai, xAI
- Local Ollama URL (default `http://localhost:11434`)

Per provider: button "Sprawdź klucz" — test ping API.
Save: do `.env.local` lub PG (operator pref `provider_api_keys`).

#### Krok 3 — Budżety i cost ceilings
4 sliders per risk_level:
- low: $0.10/recommendation (default)
- medium: $0.40
- high: $1.60
- critical: $6.00

Plus: `funding_token_budget_monthly` slider (default 100k tokens).

Save: `cost_ceilings`, `funding_token_budget_monthly` prefs.

#### Krok 4 — Default project domain
Dropdown z 14 base immutable domains:
1. funding
2. software
3. audit
4. mobile
5. infrastructure
6. data_analytics
7. security
8. governance
9. research
10. marketing
11. legal
12. product_management
13. finance
14. operations

Plus button "Dodaj custom domain" (z prefixem `custom:`).
Save: `default_project_domain`.

#### Krok 5 — Default autonomy
Radio:
- **Manual** (operator confirms every action)
- **Suggest** (default — advisor recommends, operator clicks)
- **Auto** (advisor acts on low-risk decisions automatically; D3+ wciąż wymaga HG)

Hard preference (wymaga confirm modal).
Save: `autonomy_level`.

#### Krok 6 — Default Council size + LLM judge routing
- Slider: Council size (default 5, range 1-11)
- Matrix editor: LLM judge per (recommendation_type × risk_level) — defaults z `00_master_spec.md` §5
  - Możesz zmienić każdą komórkę
  - Bulk preset: cost-saving / balanced / aggressive
- Save: `council_size`, `llm_judge_routing_override`

#### Krok 7 — Quality / Speed / Cost slider
3-way slider sumujący się do 1.0:
- Quality: 0.4 (default)
- Speed: 0.3
- Cost: 0.3

Save: `quality_speed_cost`.

#### Krok 8 — Trusted / Blocked providers
Multi-select:
- **Trusted**: providers z przewagą w routing
- **Blocked**: providers nigdy nie używani

Hard preferences (wymaga confirm).
Save: `trusted_providers`, `blocked_providers`.

#### Krok 9 — **FUNDING OPT-IN** (najszerzej omawiany)

Toggle: "Włącz Funding Advisor" (**default OFF** — świadoma decyzja, zżera tokeny).

Jeśli ON, operator widzi:
- **Hierarchical country selector**:
  - **Polska**: collapsible z 16 województwami (mazowieckie, dolnośląskie, małopolskie, łódzkie, podkarpackie, śląskie, wielkopolskie, lubelskie, zachodniopomorskie, kujawsko-pomorskie, lubuskie, podlaskie, pomorskie, świętokrzyskie, warmińsko-mazurskie, opolskie) — checkboxes
  - **Unia Europejska**: collapsible z krajami członkowskimi
  - **Inne**: input free-form
- Toggle: "Zezwalaj na external research via AI" — zżera dodatkowe tokeny, ale pozwala advisorowi szukać dotacji w internecie
- Slider: `funding_token_budget_monthly` (osobny od krok 3!) — default 100k tokenów
- Section "Czy masz firmę?":
  - **Tak** → form prefill (legal_form, KRS, NIP, REGON, PKD)
  - **Nie** → advisor zasugeruje formy + lokalizacje (np. "Załóż sp. z o.o. w mazowieckim — kwalifikuje się pod FENG 2.1")

Save: `funding_advisor_enabled`, `funding_countries` (hierarchical JSON), `funding_research_external_allowed`, `funding_token_budget_monthly`.

#### Krok 10 — First idea (optional)
- Pole: title + domain (dropdown) + type (dropdown z 8 base: research/production/experiment/poc/migration/refactor/integration/hotfix)
- Skip OK
- Jeśli wpisany: POST `/api/v1/advisor/ideas` → idea created → redirect `/projects/<id>/lifecycle`
- Bez tego: redirect `/dashboard/operator-monitor`
- Mark `advisor_onboarded=true`

---

<a name="4-operator-preferencje"></a>
## 4. Pojęcie operatora i preferencji

### 14 project domains (base immutable)

`funding, software, audit, mobile, infrastructure, data_analytics, security, governance, research, marketing, legal, product_management, finance, operations`

Plus operator może dodawać **custom** z prefixem `custom:` (np. `custom:devrel`).

### 8 project types (base immutable)

`research, production, experiment, poc, migration, refactor, integration, hotfix`

Plus custom z prefixem.

### 3D matrix preferencji

Każda preferencja jest indeksowana po:
1. `user_id` (operator)
2. `project_type` (lub wildcard)
3. `project_domain` (lub wildcard)
4. `preference_key` (np. `autonomy_level`)

Wartość: dowolna JSONB.

### 4-level fallback cascade

Gdy advisor pyta o efektywną wartość preferencji:
1. **Level 1**: (user, type=X, domain=Y) — najbardziej specyficzne
2. **Level 2**: (user, type=X, domain=NULL)
3. **Level 3**: (user, type=NULL, domain=Y)
4. **Level 4**: (user, type=NULL, domain=NULL) — per-user default
5. **Level 5**: system default z `preference_key_catalog`

Pierwszy znaleziony wygrywa.

### 10+ preference keys

Domyślne typy preferencji:
1. `autonomy_level` (manual/suggest/auto) — **hard change**
2. `cost_sensitivity` (low/medium/high)
3. `preferred_providers` (lista provider IDs)
4. `runtime_strategy` (local_only/local_plus_vps/hybrid/vps_only) — **hard change**
5. `approval_timeout_behavior` (auto_approve/escalate/hold) — **hard change**
6. `council_size` (1-11)
7. `budget_thresholds` (per-projekt cost ceilings)
8. `quality_speed_cost` (3-way sumujący 1.0)
9. `trusted_providers` (lista) — **hard change**
10. `blocked_providers` (lista) — **hard change**
11. `llm_judge_routing_override` (matrix per recommendation_type × risk)
12. `cost_ceilings` (per risk_level)
13. `funding_advisor_enabled` (bool) — **hard change**
14. `funding_countries` (hierarchical)
15. `funding_token_budget_monthly` (int)
16. `meta_recommendations_enabled` (bool) — **hard change**

### Hard vs Soft learning

**Soft learning** (auto bez pytania):
- Po N akcjach operatora w pewnym kierunku, system aktualizuje preferencję na poziomie najbardziej specyficznym istniejącym
- Np. operator 10× akceptuje Council size 7 dla research/software → preference `council_size` przy (operator, research, software) zostaje ustawiony na 7
- Dotyczy tylko **non-hard** preferences

**Hard learning** (wymaga operator click):
- Dla preferences flagowanych `is_hard_change=true` (autonomy_level, blocked_providers, runtime_strategy, etc.)
- System emituje event `aeis.advisor.preferences.hard_change_requested`
- Operator widzi modal: "Czy na pewno? Ta zmiana wpływa na: ..."
- Confirm → preferencja zapisana
- Reject → no-op, signal logged

### "Don't learn from this" button

Na **każdej** karcie advisor jest button "Nie ucz się z tej decyzji". Toggle:
- Stackable z innym action (np. "Akceptuj + Nie ucz się z tego")
- Sygnał `dont_learn_flag=true` w karcie → soft learning skipped dla tej karty

---

<a name="5-advisor-layer"></a>
## 5. Doradca (Advisor Layer) — 4 filary

### Filar 1: Adaptive Preference Layer

Opisany w sekcji 4. 3D matrix + 4-level cascade + soft/hard learning.

### Filar 2: Contextual Recommendation Engine

Engine subskrybuje **16 lifecycle hooks** w istniejących modułach AEIS (idea_routes, council_workflow, governance_routes, etc.). Po każdym evencie:

1. Rule engine ocenia czy **emit advice for this**
2. Jeśli tak: LLM-as-judge (production-grade, hybrid rule + LLM od dnia 1) generuje rationale + alternatywy + risk assessment
3. **Confidence calculator**: `0.4·council_match + 0.4·history_match + 0.2·pricing_quality + 4. komponent: historical_acceptance_rate. × 0.8 jeśli local fallback`
4. **D-ladder assigner** + 5 upgrade rules
5. Evidence Pack creation (jeśli wymagany)
6. **AdvisorCardEnvelope builder** + schema validator
7. Emit do event bus → surface_feed renders → operator action

### 16 lifecycle hooks

| Hook | Phase | Trigger |
|---|---|---|
| H01 | Setup | Initial model setup |
| H02 | Setup | API/provider setup |
| H03 | Setup | Budget configuration |
| H04 | Idea | Idea intake completed |
| H05 | Idea | SoT model selection |
| H06 | Council | Council formation |
| H07 | Governance | Autonomy policy change |
| H08 | Drafting | SoT drafted |
| H09 | Planning | Masterplan created |
| H10 | Execution Setup | Runtime topology selection |
| H11 | Execution Setup | VPS/env scaling |
| H12 | Execution Setup | Skill selection |
| H13 | Execution | **Production deploy (synchronous gate)** |
| H14 | Validation | Testing started |
| H15 | Approval | Human Gate ticket pending |
| H16 | Closure | **Final approval (synchronous gate)** |

### Filar 3: Specialized Advisors

**Subscription Advisor**: monitoruje token usage, kalkuluje ROI dla planów, **HARD GATE** (nigdy auto-purchase, zawsze D3+ z Evidence Pack + Human Gate).

**Runtime Scaling Advisor**: rekomenduje topology (local / local+VPS / multi-VPS / hybrid), staged scaling, D3+ dla VPS.

**Funding Advisor**: opt-in, opisany szczegółowo w sekcji 9.

**Role Resolver**: mapuje role (planner/worker/critic/governance/local_verifier) na konkretne LLM modele.

**Variants Generator**: 3 strategiczne warianty (cost-saving / balanced / aggressive) + per-context parametryzacja.

### Filar 4: Guided Operator Journey UI

- **Onboarding Wizard** (10 kroków) — opisany w sekcji 3
- **Project Lifecycle Dashboard** — primary screen po onboardingu, wizualizacja 16 faz
- **Live Advisor Feed** — hybrid bubble (toast/modal) opisany w sekcji 7
- **Operator Monitoring Dashboard** — multi-project overview
- **Settings Configurator** — 9 sekcji, edytowalne preferencje
- **Switch to Technical Mode** — **zawsze widoczny przełącznik** w nav

---

<a name="6-modele-llm"></a>
## 6. Modele LLM — pula, routing, koszty

### Default LLM pool (konfigurowalny w onboardingu)

**Local (Ollama — zawsze dostępny baseline)**:
- `qwen2.5:72b-instruct` — primary, mocniejszy w structured/code
- `qwen2.5:7b-instruct` — mini, dla cheap rationale
- (alternatywnie) `llama3.3:70b` — alternative jeśli RAM constraint

**External (default 3)**:
- **Anthropic**: `claude-sonnet-4-6` (balans cost/quality)
- **OpenAI**: `gpt-5` (najnowszy, tool use strong)
- **Google**: `gemini-2.5-pro` (long context 1M+, multimodal)

**Optional adapters (operator może dodać)**:
- Anthropic Opus 4.7, Haiku 4.5
- Moonshot Kimi K2 (long context, code)
- z.ai GLM-4.6 (cheap reasoning)
- xAI Grok 4 (web-aware)

### Routing matrix (per recommendation_type × risk_level)

Domyślne (operator override globalnie w settings):

| Recommendation type | Risk-low | Risk-medium | Risk-high | Risk-critical |
|---|---|---|---|---|
| rationale generation | qwen 7b | Sonnet 4.6 | Sonnet 4.6 | Opus 4.7 |
| alternatives ranking | qwen 72b | Sonnet 4.6 | Opus 4.7 | Opus 4.7 |
| risk assessment | Sonnet 4.6 | Sonnet 4.6 | Opus 4.7 | Opus 4.7 |
| funding scoring | Gemini Flash | Gemini Pro | Opus 4.7 + Gemini Pro | Opus 4.7 + GPT-5 (ensemble) |
| consortium matching | Sonnet 4.6 | Sonnet 4.6 | Opus 4.7 | Opus 4.7 |

**Funding scoring** używa Gemini z powodu długiego kontekstu (czytanie regulaminów konkursów). High-risk: ensemble dwóch modeli dla cross-validation.

### Cost ceilings (defaults, ustawiane w onboardingu)

| Risk level | Default ceiling per recommendation |
|---|---|
| low | $0.10 |
| medium | $0.40 |
| high | $1.60 |
| critical | $6.00 (ensemble allowed) |
| funding_scoring | $3.00 (osobny limit) |

Każdy ceiling: operator może podnieść lub obniżyć w settings.

### Local fallback

Jeśli wybrany model niedostępny (rate limit, brak API key, network down):
1. Engine próbuje fallback per `role_resolver`
2. Local fallback (Ollama) zawsze dostępny baseline
3. Jeśli local użyty: confidence multiplied ×0.8 (penalty za użycie lokalnego mniej-mocnego modelu)
4. Audit log notuje `was_local_fallback=true` + `fallback_reason`

### Mobile-specific routing (Etap 2)

Gdy karta z `header.mobile_allowed=true` AND triggered by mobile gateway:
- low risk → Haiku 4.5 (cheaper) zamiast Sonnet
- medium risk → Sonnet (default)
- high risk → Sonnet (mobile keeps Sonnet to save cost vs desktop's Opus)
- critical → Opus (no compromise)

Gemini Pro → Gemini Flash dla mobile funding scoring.

---

<a name="7-karty-advisor"></a>
## 7. Karty advisor (AdvisorCards)

### Hierarchia kart (proto)

```
AdvisorCardEnvelope (wrapper)
├── header (shared 25+ fields)
└── oneof body:
    ├── DecisionCard (operacyjne rekomendacje)
    ├── FundingCard (funding-specific)
    ├── SecurityCard (placeholder v2)
    ├── ScalingCard (topology/scaling)
    └── OnboardingCard (wizard guidance)
```

### Kluczowe pola header (25+)

- `card_id`, `schema_version`, `card_type`
- `title`, `rationale`
- `confidence_score` (0.0-1.0 float) + `confidence_label` (LOW/MED/HIGH/VERY_HIGH/CERTAIN)
- `sources` (lista: rule_engine, llm_judge, history_match, council_vote, hybrid)
- `risk_level` (4-level enum: low/medium/high/critical)
- `project_domain`, `project_type`, `project_id`, `idea_id`
- `d_level` (D0-D5)
- `evidence_pack_id` (set dla D5)
- `history_based`, `historical_acceptance_rate`
- `expires_at`, `priority`, `tags`
- `dont_learn` (bool — operator clicked "don't learn")
- `human_gate_required` (bool)
- **Mobile fields**: `mobile_allowed`, `requires_biometric`, `push_priority`
- `audit_trail_id`, `llm_judge_audit_id`
- `used_local_fallback`, `local_fallback_reason`

### DecisionCard body fields

- `recommendation` (text)
- `expected_benefit`, `expected_downside`, `quality_impact`
- `cost_impact`, `token_impact`, `time_impact` (Impact type — bezwzględne + delta_vs_baseline_pct + ASSUMPTION flag)
- `alternatives` (max 5 mini-kart każda z `cost_delta_vs_primary`, `risk_level`, `trade_off_summary`)
- `recommendation_type` (enum z 30+ typów)

### FundingCard body fields (sekcja 9 detail)

- `suggestion_type` (enum: GRANT_FIT / FORM_COMPANY / FIND_CONSORTIUM / etc.)
- `headline_recommendation`
- `grant_program_id`, `grant_program_name`, `country`, `region`
- `eligibility_score` (0-100) + `eligibility_breakdown` (per komponent)
- `current_match_summary`, `gaps_to_qualify`, `recommended_actions`
- `consortium_required`, `consortium_suggestions`
- `application_deadline`, `time_to_prepare`
- `simulation_results` (3 modes)
- `match_confidence`

### 9 actions per karta

Każda karta ma 9 buttons:
1. ✓ **Akceptuj** (Accept)
2. ✗ **Odrzuć** (Reject)
3. ✏ **Modyfikuj** (Modify) — operator edits recommendation before accept
4. 🕐 **Przypomnij później** (Remind later)
5. 👎 **Nieprzydatne** (Not useful)
6. → **Konwertuj na Human Gate** (Convert to HG ticket)
7. → **Konwertuj na Masterplan change** (Convert to Masterplan proposal)
8. ⚙ **Zapisz jako preferencję** (Save as preference)
9. 🚫 **Nie ucz się z tego** (Don't learn from this) — TOGGLE, **stackable** z innym action

### Confidence breakdown

Wizualizacja na karcie (4 komponenty):
- `council_match` (0-1) — zgodność z Council voting weights
- `history_match` (0-1) — podobieństwo do akceptowanych w przeszłości
- `pricing_quality` (0-1) — jakość danych pricing (live > profile > assumption)
- `historical_acceptance_rate` (0-1) — operator accept rate dla podobnych

`final_score = 0.4·council + 0.4·history + 0.2·pricing` averaged with 4. komponent. Multiplier ×0.8 jeśli local fallback.

---

<a name="8-decyzyjnosc"></a>
## 8. Decyzyjność — D-ladder + Evidence Pack + Council

### D-ladder D0-D5

| D-level | Nazwa | Audyt | Approval | Evidence | Przykłady |
|---|---|---|---|---|---|
| **D0** | Trivial | Default log | None | None | Skomentuj, zapisz draft |
| **D1** | Minor | Logged event | None | None | Zmiana preference, set tag |
| **D2** | Moderate | Logged | Optional HG | None | Wybór Council size, autonomy=suggest |
| **D3** | Significant | Logged + HG ticket | **HG required** | **Light Evidence** | Add VPS, autonomy=auto, purchase plan |
| **D4** | High-impact | Logged + Council vote | **Council vote** | **Full Evidence Pack** | Multi-VPS, autonomy=auto globalnie |
| **D5** | Critical | Logged + multi-sig | **Multi-signature** | **Full Evidence Pack mandatory** | Production deploy, override safety |

### 5 upgrade rules

D-level może być **upgraded** (nigdy downgraded) per:

1. **U1 cost magnitude**: > $100 → +1, > $1000 → +2, > $10000 → +3
2. **U2 blast radius**: affects multiple projects → +1, affects production → +1
3. **U3 reversibility**: rollback > 1 day → +1, data loss → +2 (min D4)
4. **U4 hard preferences**: changing hard pref → minimum D3
5. **U5 autonomy**: operator pref `manual` → all non-D0 cards become D3+

Cap: D5.

### Evidence Pack templates

**D3 Light** (cost/subscription/funding-FORM_COMPANY etc.):
- rationale (≥200 słów)
- rollback_plan (≥100 słów)
- fidelity_test (≥50 słów)
- confidence_breakdown
- ≥1 signature (operator)

**D5 Full** (always required dla D5):
- All D3 Light fields (with stricter mins: rationale ≥500, rollback ≥300)
- risk_analysis (identified_risks + worst_case_scenario)
- compliance_check (regulatory_constraints_reviewed = true)
- council_vote (vote_id, consensus_reached)
- sentinel_signoffs (cost ✓ + security ✓)
- ≥3 signatures (operator + ≥1 council_member + ≥1 sentinel)

### Council Hybrid

**Skład**: 9 ról × 5 rang × weighted vote.

**Critic gate**: jeśli Critic flag, decyzja blocked (operator może override z explicit Evidence Pack).

**Sentinele**:
- **Cost sentinel** — review cost-impacting decisions D3+
- **Security sentinel** — review security-impacting decisions D3+

**Voting flow**:
1. Operator initiates vote (lub system auto przy D2+)
2. Council members głosują z wagą per rank
3. Critic może block (lub potwierdzić)
4. Sentinel signoffs przy D3+
5. Aggregated result + Evidence Pack finalized

---

<a name="9-funding-module"></a>
## 9. Funding Module (najszerzej omawiany)

### Aktywacja

- **Opt-in**, default OFF (świadoma decyzja operatora bo zżera tokeny)
- Włączane w onboarding krok 9 lub w settings później
- Operator widzi tooltip: "Funding Advisor wykorzystuje tokeny dla research dotacji. Domyślnie wyłączony."

### Per-country settings (hierarchical)

- **Polska**: drill-down do 16 województw (operator wybiera które)
- **Unia Europejska**: drill-down do krajów członkowskich
- **Inne kraje**: free-form input

### Per-idea opt-in

Gdy operator tworzy nowy pomysł (idea intake):
- Banner: "Włącz Funding Advisor dla tego pomysłu? (+~5k tokenów na iterację)"
- Default OFF dla każdego pomysłu (operator opt-in per idea)
- Auto-ON dla pomysłów z `project_domain=funding`

### Per-grant scoring profiles (KEY INSIGHT)

**Najważniejsze**: scoring **NIE jest hardcoded**. Każdy grant ma własny `scoring_profile`:

- Universal pool 7 komponentów: `eligibility, thematic_alignment, capacity, competitive_position, regional_fit, consortium_readiness, timeline_fit`
- Per-grant config: subset komponentów + wagi + hard floors + custom criteria (np. "musi mieć status MŚP")
- `effective_score = grant.scoring_profile.apply(company_data, idea_data)`

**Implication**: ta sama firma + ten sam pomysł → różne granty produkują różne scores. PARP ≠ FENG ≠ Horizon Europe.

Domyślne wagi: `eligibility:30 / thematic:20 / capacity:15 / competitive:10 / regional:10 / consortium:10 / timeline:5`.

**Eligibility hard floor**: jeśli component `eligibility` < 50 → automatic auto-reject score (niezależnie od reszty).

### Bidirectional matching (3 ścieżki)

**Direction A — project → grants**: Mam pomysł → jakie dotacje pasują (lista grantów + per-grant score)

**Direction B — grants → ideas**: Otwarte konkursy → jakie pomysły by się łapały (cross-reference z idea vault)

**Direction C — gap analysis**: Co zrobić z firmą / pomysłem żeby się łapać pod X (np. "Załóż firmę X w województwie Y żeby kwalifikować się pod FENG 2.1")

### Company management

**Pola firmy**:
- legal_name, legal_form (sp_z_o_o, sa, jdg, fundacja, etc.), KRS, NIP, REGON
- pkd_codes (multi-select)
- country (default PL), region (per country — PL → 16 voivodeships)
- size_category (mikro/mała/średnia/duża), employee_count, annual_revenue_usd
- founding_date, is_msme
- innovation_certifications, rd_budget_history

**Personas firmy** (wymagane dla pełnego scoringu):
- Prezes / Owner (full_name, role, ownership_pct)
- Beneficjent rzeczywisty (legal requirement)
- Team members (z experience_summary, qualifications, team_role)
- Każda persona z `is_kp` (key personnel for grant) toggle

**Own + third-party**: operator może dodać firmy własne i firmy zewnętrzne (np. konsultacja, konsorcjant). Flag `is_own`.

### 3-mode simulator

Dostępny per (company × idea × grant) scoring history:

**Mode 1 — Static**: predefined scenariusze ("Co jeśli zmienisz formę prawną na sp. z o.o.")
**Mode 2 — Dynamic**: operator wybiera dowolne pole + nową wartość → re-score
**Mode 3 — AI-generated**: AI proponuje top-3 zmiany maksymalnie zwiększające score

Każda symulacja:
- Zapisana w `scoring_history`
- Pokazuje: nowy score + delta vs bazowy + impact per komponent
- Cost to implement + time to implement (estymata)

### Consortium suggestions

Dla grantów wymagających konsorcjantów:
- Internal pool (`advisor_funding.consortium_pool`)
- Filtered po requirements (entity_type, region, qualifications)
- Operator może dodawać do pool (sugesticje "umów konsultację z biurem rachunkowym")

### Recommendations typy (FundingSuggestionType)

- `FUNDING_GRANT_FIT` — "Twój pomysł łapie się pod grant X" (D0)
- `FUNDING_HOW_TO_QUALIFY` — "Co zrobić żeby się łapać" (D1)
- `FUNDING_FORM_COMPANY` — "Załóż firmę X" (D3+ z Evidence Pack)
- `FUNDING_CHANGE_LEGAL_FORM` — D3+
- `FUNDING_REGIONAL_RELOCATION` — "Założ w innym województwie" (D3+)
- `FUNDING_FIND_CONSORTIUM` — D2
- `FUNDING_ADJUST_IDEA_FOR_GRANT` — D2 (D3 jeśli zmienia scope)
- `FUNDING_DEADLINE_WARNING` — D1
- `FUNDING_GAP_CLOSURE_PLAN` — D2
- `FUNDING_SCOPE_ADJUSTMENT` — D2

### Source data

- **Polskie**: PARP, NCBR, FENG centralny + regionalne (RPO województwa)
- **EU**: Horizon, Erasmus+, EU funds direct
- **Custom upload**: operator może załadować PDF/JSON konkursu manualnie
- **Brak API** — głównie manual/profile-based

---

<a name="10-aplikacja-mobilna"></a>
## 10. Aplikacja mobilna (Etap 2)

### Stack

- **Kotlin Multiplatform (KMP)** — shared business logic
- **Android first** (Compose UI)
- **iOS** — Etap 3 (na końcu)
- Backend interface: **REST przez `mobile_gateway`** (stabilność + audytowalność, nie direct gRPC)
- **Push**: Firebase Cloud Messaging (FCM)
- **Biometric**: Android `BiometricPrompt` + Keystore
- **Offline**: read-only cache (przeglądanie ostatnich)
- **Testing**: Maestro/Appium dla E2E, JUnit/KotlinTest dla unit

### 6 primary screens

1. **Cards / Feed** — stream AdvisorCards, pull-to-refresh, paginated 50 cards
2. **Card Detail** — full Decision/FundingCard view + 9 actions
3. **Project Lifecycle** — 16 phases visualization (compressed)
4. **Onboarding Wizard** — 10 steps (mobile UX)
5. **Funding** — companies, grants, scoring, simulator (per sekcja 9)
6. **Settings** — preferencje (soft only via mobile; hard wymaga desktop)

Plus: Pairing, Human Gate ticket list+detail, Sentinel signoff sheets, Evidence Pack viewer.

### Auth + biometric

**Pairing**:
1. Scan QR z desktop UI
2. POST `/mobile/v1/devices/pair` → device JWT
3. JWT stored encrypted w Android Keystore
4. Refresh token rotated weekly

**Biometric step-up**:
- D0/D1/D2 cards: bez biometric
- **D3+ cards**: BiometricPrompt → success → `X-Biometric-Step-Up` header → server validates

### Push notifications (5 channels via FCM)

- `urgent_recommendations` (D5 / critical risk)
- `human_gate_pending` (HG awaiting decision)
- `funding_deadline_alerts` (T-7d / T-1d)
- `scaling_alerts` (auto-scaling triggers)
- `weekly_summary` (digest, low priority)

**Rules**:
- Lock screen preview: NO PII (only opaque card_id reference)
- Per-device dedup (5 min window)
- Per-device rate limit (max 50 pushes/hour)
- Per-channel quota

### Offline cache scope

- Last 50 recommendations (read-only)
- 10 active project status snapshots
- All pending HG tickets (read + ack-when-online queue)
- Last 30 funding deadlines
- Settings (read-only)

**Sync queue**:
- Actions taken offline → queued → sent on reconnect
- Conflict resolution: server-wins for cards, last-wins for soft preferences

### Mobile-only constraints

- Soft preferences: editable
- **Hard preferences**: read-only on mobile, redirect "Edit on desktop"
- Multi-tab UX: brak (single device)
- Background → foreground (>30 min idle): re-auth required

---

<a name="11-human-gates"></a>
## 11. Human Gates

### Co to jest Human Gate

Human Gate (HG) = checkpoint wymagający **świadomej decyzji operatora** zanim system idzie dalej. Każdy HG to ticket z context, options, time limit.

### Source patterns (skąd HG ticket pochodzi)

1. **Manual** — operator initiates ticket
2. **Advisor card conversion** — operator klika "Konwertuj na HG" na karcie
3. **Workflow** — proces lifecycle wymaga gate (np. D3+ rekomendacja)
4. **Sentinel alert** — sentinel cost/security flagged

### Per-D-level requirements

- **D0/D1**: brak HG
- **D2**: HG optional
- **D3+**: HG mandatory + Evidence Pack
- **D4**: + Council vote
- **D5**: + Multi-signature (operator + Council + Sentinel)

### Synchronous gates (BLOCKING)

**H13 — production deploy**:
- Endpoint emit event AND awaits engine response (timeout 5s)
- Engine returns `proceed` | `block` | `defer_to_human_gate`
- `block` → HTTP 423 Locked z AdvisorCard explanation
- `defer` → HTTP 202 Accepted z ticket_id
- `proceed` → normalny flow

**H16 — final approval**: same pattern

### Batch processing

Gdy `pending_count_user >= 5` low-risk tickets:
- Engine emits `REC_TYPE_BATCH_HUMAN_GATE_TICKETS` card
- Operator może batch-process (5+ na raz, single review)

### Mobile flow

- Push notification: `human_gate_pending`
- Mobile screen: HG ticket list (paginated)
- Per ticket: full context + Evidence Pack inline
- Decision actions: approve / reject / defer / convert back to advisor card
- Biometric step-up dla D3+

---

<a name="12-audyt-zgodnosc"></a>
## 12. Audyt + zgodność (compliance)

### Append-only forever-retention

**Tables append-only** (UPDATE/DELETE blocked by trigger):
- `advisor_preferences.preferences_audit`
- `advisor_engine.llm_judge_audit` (full prompt + response forever)
- `advisor_history.card_actions` (partitioned monthly, forever)
- `advisor_events.events` (proto-validated, partitioned monthly, forever)

### LLM judge audit

Każdy LLM call (rationale generation, alternatives ranking, risk assessment, funding scoring):
- **Pełny prompt + pełna response** zapisane na zawsze
- + tokens, cost, latency, model_id, was_local_fallback, fallback_reason
- + parent_audit_id (dla ensemble calls)

**Wolumen estymata**: 1000 cards/dzień × 5KB per audit row ≈ 1.8GB/rok.

**KI-08** (Known Issue 8): Legal sign-off needed dla forever-retention LLM judge prompts/responses przed production rollout.

### Correlation_id chain

Każde zdarzenie ma `correlation_id` linkujący wszystkie eventy w jednym flow. Audytor może zrekonstruować pełny chain:

```
correlation_id: abc-123
  1. aeis.idea.intake.completed (causation: null) — idea entered
  2. aeis.advisor.engine.recommendation_emitted (causation: 1) — Council size card
  3. aeis.advisor.history.action_recorded (causation: 2) — operator accepted
  4. aeis.advisor.history.learning_signal_emitted (causation: 3) — soft learning trigger
  5. aeis.advisor.preferences.updated (causation: 4) — preference auto-updated
  6. aeis.advisor.outbound.dispatched (causation: 2) — Slack notification
```

### PII redaction

- LLM audit logs **redact PII przed long-term storage**
- Tools: presidio + custom regex (emails, names, phones, PESEL/NIP)
- Sample 100 audit records → verify zero PII
- Test z synthetic PII inputs → verify redaction works

### Retention policy per type

| Type | Retention |
|---|---|
| LLM judge audit | Forever (KI-08 legal review) |
| D5 Evidence Packs | Forever |
| D3 Light Evidence Packs | 5 years |
| D4 Evidence Packs | 10 years |
| card_actions | Forever (partitioned monthly) |
| Outbound dispatches | 90 days |
| validation_failures | 30 days |

### GDPR considerations

- **Operator data isolation**: operator A nie widzi danych operatora B
- **Right to delete**: endpoint `/operator/{id}/delete` dostępny
- **Right to export**: endpoint `/operator/{id}/export` (full data dump)
- Mobile: no location collection without consent
- Lock screen preview: no PII

---

<a name="13-multi-agent-orchestration"></a>
## 13. Multi-agent orchestration (META-poziom)

### Model dyspozycji prac

System SYLION AEIS jest budowany przez **wiele AI w paraleli**:
- **Codex CLI** (OpenAI GPT-5) — backend foundations (preferences, pricing, actions, events, lifecycle hooks)
- **Kimi** (Moonshot K2) — specialized advisors (role_resolver, variants, subscription, scaling)
- **Claude** (Anthropic Opus 4.7) — heavy modules (engine, funding, history, mobile_gateway) + UI surfaces
- **z.ai watchdog** (GLM 4.6) — continuous audit
- **Final Integrator (Claude)** — cross-WP integration tests + Evidence Pack + handoff

### Wide vs cap parallelism

**Wide** (operator decision dla "kombajn" computer + Pro subs):
- Do 22 agentów równolegle w peak
- Stage A (8) + B (7) + C-infra (6) + D (3) + z.ai watchdog
- Plus 10 personas w Stage C

**Cap** (jeśli zasoby ograniczone):
- 6 równoległych agentów
- Queueing per stage

### File ownership boundaries (CRITICAL)

Każdy agent ma **strict file ownership**:
- Codex: `sylion/api/*.py` (16 hooks emit), `module_registry.py`, `pg_migration.py`, alembic, `sylion/aeis/advisor/{preferences,pricing,actions,events,_db}/`
- Kimi: `sylion/aeis/advisor/{role_resolver,variants,subscription,scaling}/`
- Claude: `sylion/aeis/advisor/{engine,funding,history,mobile_gateway}/` + `src/sylion-frontend/src/app/(app)/{advisor,onboarding,projects/[id]/lifecycle,dashboard/operator-monitor,settings/advisor}/`
- z.ai: `_audit_reports/` (READ-ONLY everywhere else)
- Final integrator: `tests/aeis/advisor/_integration/`, `_handoff/` + escalated blocker fixes

**Strict — żaden agent nie tyka cudzych plików**.

### Sync points

Sequential dependencies:
- SP-1: Codex Phase 0 → unblocks Kimi + Claude
- SP-2: Codex Phase 1 (lifecycle hooks) → unblocks Claude engine subscriber wiring
- SP-3: Codex Phase 2 preferences → unblocks Kimi role_resolver, Claude engine pref resolution
- SP-4: Codex Phase 2 pricing → unblocks Kimi sub/scaling, Claude funding
- SP-5: Codex Phase 2 actions → unblocks Claude UI HandleAction button hooks
- SP-6: Kimi role_resolver → unblocks Claude engine LLM judge routing
- SP-FINAL: Cross-WP integration audit GO → unblocks Final Integrator stage

### z.ai watchdog (continuous audit)

Pętla:
1. Co 5 min check git log dla nowych `[advisor]` commits
2. Per commit: full audit przez 16 dimensions
3. Status: PASSED / PASSED_WITH_WARNINGS / BLOCKED
4. Per-commit raport w `_audit_reports/<agent>/<sha>.md`
5. Rolling `_summary.md` + `_blockers.md`
6. Phase boundary deeper audits przy critical commitach
7. Final cross-WP integration audit po skończeniu wszystkich

### Fixer protocol

Gdy z.ai blokuje:
- Original agent fix (max 2 retries)
- Jeśli wciąż blocked → mark `escalated_to_final_integrator`
- Final integrator picks up at end

Max 3 NO-GO iterations przed escalation do operatora.

### Operator UI dla meta-orchestration (Section J)

**8 features** dla operatora żeby zarządzać multi-agent system:

1. **LLM Judge Routing Matrix Editor** — operator override per recommendation_type × risk × project_domain
2. **Council Rules Configuration** — wagi rang, critic gate sensitivity, quorum
3. **Auditor Cadence Settings** — z.ai tick frequency, dimensions enabled, phase boundary triggers
4. **Fixer Protocol Settings** — retry budget per agent, escalation paths, max NO-GO iterations
5. **Multi-Agent Dispatch Config** — wide vs cap, max parallel, allocation rules per stage
6. **Test Catalog Browser** — wszystkich tests z status, run-now button
7. **Team Formation Rules** — trigger conditions per commit pattern, team composition
8. **Inter-Module Event Map** — visual graph emitters → events → subscribers

---

<a name="14-testowanie-produkcyjne"></a>
## 14. Testowanie produkcyjne — 10 person + Stage C

### 4 stage'e (Stage A → D)

**Stage A — Mobile (Etap 2)**: ~40h agent work, 8 agentów (3 Claude UI + 2 Codex backend + 2 Kimi mobile-specific + 1 z.ai security)

**Stage B — Production Hardening**: ~30h, 7 agentów (load tests, perf, security, compliance)

**Stage C — Sim Testing**: 6 agents infra + 10 persona simulators

**Stage D — Test Playbook PL**: 3 agentów dokumentujących

### 10 personas (sim operators)

Każda persona ma:
- Deterministic operator UUID
- Decision heuristic (jak podejmuje decyzje)
- Target preferences after 30 sessions
- Platform allocation (web / mobile / both)
- 25 scenariuszy

| # | Persona | Driver | Platform | Charakterystyka |
|---|---|---|---|---|
| 1 | researcher | Claude | Web (PW+Sel) | suggest mode, mały Council, low ceiling |
| 2 | funding-hunter | Kimi | Web + Mobile | Funding heavy, simulator, company mgmt |
| 3 | production-engineer | Codex | Web + Mobile | D5 deploys, sentinel signoffs, conservative |
| 4 | governance-officer | Claude | Web (PW+Sel) | Audit log, voting, compliance |
| 5 | mobile-first | Codex | Mobile only | Tylko telefon, biometric, push reactor |
| 6 | multi-tenant-operator | Codex | Web + Mobile | 5+ projektów, batch HG, monitoring |
| 7 | legal-compliance-officer | Claude | Web (PW+Sel) | Legal domain, IP, contract reviews |
| 8 | cost-optimizer | Kimi | Web (PW+Sel) | Subscription advisor, cost-saving variants |
| 9 | idea-validator | Claude | Web (PW+Sel) | High-volume intake (10+ ideas/day) |
| 10 | incident-responder | Kimi | Web + Mobile | Hotfix, urgent, sync gates, mobile on-the-go |

### Scenariusze i narzędzia

- **Per persona**: 25 scenariuszy (50% Playwright + 50% Selenium dla web, Appium dla mobile)
- **Per session**: ~1-2 min ultra-fast mode (no human-like delays)
- **30 sessions per persona** dla auto-learning verification

**Razem**: 10 person × 25 scenariuszy × 30 sessions = **7,500 sim sessions**.

### Auto-learning verification protocol

Po 30 sessions per persona:
- Dump preferences after every 5 sessions
- Compare actual vs target preferences
- **Pass criteria**: 9/10 personas show measurable convergence

Przykład:
- Persona "researcher" zawsze accept Council size 5 dla research/software
- Po 30 sessions: preference `council_size` per (researcher, research, software) MUSI = 5

### Voting simulation

50 vote configurations covering:
- Unanimous yes / unanimous no
- Split with critic gate breaking
- Sentinel cost rejects → Council overrides
- Sentinel security rejects → blocking
- Per-rank weight verification
- Quorum scenarios

**Pass criteria**: 100% of 50 produce expected outcome.

---

<a name="15-production-gates"></a>
## 15. Production gates — hybrid (auto + operator)

### Auto gate (10 criteria)

| # | Metric | Threshold |
|---|---|---|
| 1 | Mobile tests on Pixel | 100% pass |
| 2 | Sustained load | ≥1k qps × 30 min, p99 < target |
| 3 | Memory growth | < 5% over 30 min |
| 4 | Security findings | 0 critical, 0 high |
| 5 | PII redaction | 100% on 100-sample |
| 6 | Audit log integrity | 100% append-only enforced |
| 7 | Sim sessions | ≥95% pass |
| 8 | Auto-learning convergence | 9/10 personas |
| 9 | Voting simulation | 100% of 50 configs |
| 10 | Regression vs Etap 1 | 0 regressions |

### Manual operator gate (5 sign-offs)

1. Personal web demo (Playwright recording playback walkthrough)
2. Personal mobile demo (APK on Pixel via ADB)
3. Test playbook completeness review
4. KI-08 legal sign-off (LLM judge retention)
5. Final authorization signature na `HANDOFF_FINAL_PROD.md`

### Decision

```
GO_DECISION = (auto_gate ALL pass) AND (manual_gate ALL signed)
```

Jeśli false: NO-GO, lista blockerów, retry.

---

<a name="16-ux-stylistyka"></a>
## 16. UX i stylistyka

### Modern modernist high-tech (Linear/Vercel/Arc class)

**Kolory**:
- Dark mode primary (z light mode opcjonalnym)
- Akcent per risk_level: low=zielony, medium=amber, high=pomarańczowy, critical=czerwony
- Neutralna paleta dla nav, content

**Typografia**:
- Sans-serif (Inter / Geist / similar)
- Strong hierarchy
- Generous line-height

**Spacing**:
- Generous whitespace
- 4/8/16px scale

**Animacje**:
- Subtelne (Framer Motion)
- Page transitions: 200-300ms ease-out
- Toast: slide-in from right, auto-dismiss 5s
- Modal: fade-in + scale 0.95→1

### Hybrid bubble UI (Live Feed)

- **Low-risk** (low/medium): toast u dołu prawej, auto-dismiss 5s
- **High-risk** (high/critical): modal blocking
- **Persistent counter**: badge na bubble icon w nav
- **Max 3 visible** + queue counter

### Switch to Technical Mode

- **Zawsze widoczny** w TopBar (right side)
- Switch z dwoma opcjami: "Tryb operatora" / "Tryb techniczny"
- Stan w `localStorage.advisor_mode`
- Reorganizes sidebar (operator mode shows advisor sections, technical mode shows legacy nav)

### Polish operator-facing

Wszystkie nav, buttons, labels, banners, error messages — **po polsku**. Code i internal docs — angielski.

Przykłady:
- "Doradca (Live Feed)" zamiast "Advisor Feed"
- "Skarbiec pomysłów" zamiast "Idea Vault"
- "Umiejętności" zamiast "Skills"
- "Ustawienia doradcy" zamiast "Advisor Settings"
- "Rada (Council)" zamiast "Council"
- "Pierwsze uruchomienie" zamiast "Onboarding"

### Sidebar structure (target)

Sekcje (kolejność, w trybie operatora):

1. **Doradca**
   - Doradca (Live Feed) [badge: pending count]
   - Pierwsze uruchomienie [hidden after onboarded]

2. **Projekty**
   - Lista projektów
   - Skarbiec pomysłów
   - Monitoring operatora
   - Lifecycle (per project)

3. **Decyzje**
   - Decyzje
   - Rada (Council)
   - Audyt
   - Evidence Pack

4. **Funding** [only if enabled]
   - Doradca grantów
   - Firmy
   - Granty
   - Symulator

5. **Konfiguracja**
   - Ustawienia doradcy
   - Modele AI
   - Umiejętności

6. **Tryb techniczny** [collapsible, default collapsed]
   - Overview, Pipeline, Workspace, etc. (legacy)

7. **Orkiestracja** [META-orchestration UI, sekcja J]
   - LLM judge routing
   - Reguły Council
   - Cadence audytora
   - Protokoły fixerów
   - Konfiguracja dispatchu
   - Katalog testów
   - Reguły zespołów
   - Mapa eventów

---

<a name="17-roadmap"></a>
## 17. Roadmap — Etapy 1→7

### Etap 1 — Advisor Layer (DONE 2026-04-26)

**Status**: HANDOFF_FINAL.md committed, GO for staging.

**Co zostało dostarczone**:
- 11 modułów backend (advisor.preferences/pricing/actions/events/engine/history/funding/role_resolver/variants/subscription/scaling/mobile_gateway)
- 5 frontend dashboards (Live Feed, Wizard, Lifecycle, Operator Monitor, Settings)
- 16 lifecycle hooks emitujące events
- 21 cross-WP integration tests passing
- 1 narrated end-to-end demo
- 26 Playwright frontend specs
- Polska dokumentacja (5 plików, 112KB w `docs/dokumentacja/`)
- D-ladder + Evidence Pack rules
- Council Hybrid integration
- Subscription HARD GATE
- Per-grant funding scoring profiles
- Mobile gateway scaffold (pełna implementacja w Etap 2)

**Open KIs**: KI-01 do KI-08 (znane issues, żaden critical-blocker dla staging).

### Etap 1 Real Fix (in progress, dispatched dispatched 2026-04-26)

Operator UX gaps po pierwszym przeglądzie dashboardu:
- Polski sidebar z advisor routes
- ModeSwitcher toggle
- First-run banner + auto-redirect
- Wizard end-to-end (real save do PG)
- REAL backend `/api/v1/advisor/*` (nie mock)
- Operator monitor real telemetry
- + Section J meta-orchestration UI (parallel)

### Etap 2 — Operator Mobile (planned)

- Kotlin Multiplatform Android
- 6 primary screens (Cards, Detail, Lifecycle, Wizard, Funding, Settings)
- Biometric + Auth + Push
- Offline cache
- ADB testing on Pixel
- Maestro/Appium E2E
- Estimated: 40h agent work, ~3 days wall clock

### Etap 3 — iOS + ML-based Learning

- iOS via KMP shared business logic + SwiftUI
- ML-based learning beyond hybrid rule + LLM judge
- Estimated: separate planning round after Etap 2

### Etap 4 — Multi-operator Collaboration

- Multiple operator accounts on same project
- Real-time sync of preferences/decisions
- Concurrent editing handling

### Etap 5 — Auto-grant Submission

- Funding Advisor submits grants on operator's behalf (z full Evidence Pack + multi-sig)
- Automated form filling
- Status tracking

### Etap 6 — Real-time Push Prioritization

- Cross-device sync (web + mobile + desktop)
- Smart prioritization (don't push during meetings, sleep hours)
- Operator preference learning

### Etap 7 — Internationalization

- Multiple languages beyond Polish/English
- Localized regulatory data (different countries)
- Currency support

---

<a name="18-slownik"></a>
## 18. Słownik

| Termin | Definicja |
|---|---|
| **AEIS** | Adaptacyjny Ekosystem Inteligencji SYLION |
| **Advisor Layer** | Warstwa 13 — proaktywny doradca operatora |
| **AdvisorCard** | Bazowy typ rekomendacji (DecisionCard, FundingCard, etc.) |
| **AdvisorCardEnvelope** | Wrapper z headerem + `oneof body` polymorphism |
| **D-ladder** | D0–D5 klasyfikacja decyzyjna |
| **Evidence Pack** | Audytowalny zapis decyzji (D3 Light + D5 Full) |
| **3D matrix** | Indeksowanie preferencji po (user, project_type, project_domain) |
| **4-level fallback** | Cascade resolution preferencji (most-specific → system default) |
| **Lifecycle hook** | Jeden z 16 punktów decyzyjnych gdzie advisor injektuje rekomendację |
| **Soft learning** | Auto-update preferencji z akceptacji kart, bez confirmation |
| **Hard learning** | Zmiana preferencji wymagająca operator click |
| **Funding scoring profile** | Per-grant template definiujący komponenty + wagi + hard floors |
| **LLM-as-judge** | LLM call produkujący rationale, alternatives ranking, soft scoring |
| **Outbound adapter** | Bridge dostarczający events do external systems (Slack/email/FCM) |
| **mobile_gateway** | REST API gateway translatujący mobile REST na internal gRPC |
| **ASSUMPTION flag** | Ustawiany na cost estimates gdy brak live data z adapterów |
| **Council match** | Komponent confidence: zgodność z aktualnymi Council voting weights |
| **History match** | Komponent confidence: podobne past recommendations + acceptance rate |
| **Pricing quality** | Komponent confidence: data freshness/source quality |
| **Historical acceptance rate** | 4. komponent confidence — accept rate similar past cards |
| **HG (Human Gate)** | Checkpoint wymagający świadomej decyzji operatora |
| **Synchronous gate** | HG blokujący endpoint do czasu engine response (H13, H16) |
| **Sentinel** | Cost / Security reviewer dla D3+ decisions |
| **Critic gate** | Council member z power-veto (Critic flag = block) |
| **Final Integrator** | Stage 6 agent finalizujący Etap (cross-WP tests + Evidence + handoff) |
| **z.ai watchdog** | Continuous audit agent (read-only, pisze tylko `_audit_reports/`) |

---

## Cross-references

- Architektura systemu (Etap 1): `00_architektura_systemu.md`
- Moduł AEIS Advisor szczegółowo: `01_modul_aeis_advisor.md`
- Operator runbook: `02_operational_manual.md`
- Governance i compliance: `03_governance_audit_compliance.md`
- Dla developera: `04_dla_developera.md`
- Etap 1 HANDOFF: `../claude_parallel/aeis_advisor/_handoff/HANDOFF_FINAL.md`
- Etap 1 known issues: `../claude_parallel/aeis_advisor/_handoff/known_issues.md`
- Production-ready masterplan: `../claude_parallel/aeis_production_ready/`
- Evidence Pack template: `../claude_parallel/aeis_advisor/00_architecture/06_evidence_pack_template.md`

---

**Dokument zamknięty**. Wszystkie dzisiejsze decyzje zachowane. Operator może wracać do tego dokumentu jako kanonicznego reference dla całego systemu SYLION AEIS.
