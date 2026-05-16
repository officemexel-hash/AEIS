# 00 — ADVISOR LAYER (W13) — Pełen deep dive

> **Status**: 🟢 Active draft (uzupełnienie 41-fazowego manuala)
> **Cel**: opisać **proaktywną inteligencję** AEIS — najważniejszą lukę w oryginalnym manualu
> **Pozycja**: Czytaj **PO** `00_ARCHITEKTURA_W1_W19.md`, **PRZED** wracaniem do 41 faz
>
> **Krytyczny insight**:
> Manual 41-fazowy opisywał workflow **reaktywnie** — operator klika,
> system reaguje. Advisor Layer (W13) działa **proaktywnie** — system
> sam zauważa, sugeruje, ostrzega, eskaluje.
>
> **Bez Advisor**: AEIS = wykonawca poleceń.
> **Z Advisor**: AEIS = inteligentny współpracownik.

---

# CZĘŚĆ I — Filozofia Advisor Layer

## 1.1. Czym Advisor JEST

Advisor to **aktywna inteligencja** AEIS — system który:
- **Obserwuje** każdą akcję operatora i każdy artifact w runtime
- **Łączy** kontekst z różnych warstw (Memory W9, Cost W11, Council W3, etc.)
- **Generuje** AdvisorCards — sugestie, rekomendacje, ostrzeżenia, hard gates
- **Adaptuje** swoje zachowanie na podstawie historii decyzji operatora
- **Eskaluje** krytyczne sprawy do hard gates (operator MUSI zdecydować)

## 1.2. Czym Advisor NIE JEST

- **NIE jest Council** — Council deliberuje przy konkretnej decyzji (W3). Advisor obserwuje continuously i reaguje na patterns.
- **NIE jest Guards** — Guards walidują artifacts post-factum (W11-W13 cross-cutting). Advisor **uprzedza** problemy zanim się staną.
- **NIE jest workflow engine** — Workflow (W6) wykonuje plan. Advisor **kwestionuje plan** lub sugeruje lepszy.

## 1.3. AdvisorCard jako podstawowy artifact

Każde "wystąpienie" Advisora to **AdvisorCard** — strukturalne sugestie z:
- **Trigger** — co zauważył Advisor (np. "Cost spike na Phase 4 = 2x estimate")
- **Rationale** — dlaczego to ważne (z evidence z różnych warstw)
- **Suggestion** — co operator powinien rozważyć
- **Confidence** — jak pewny jest Advisor (0.0-1.0, z historii podobnych decyzji)
- **Risk** — co się stanie jeśli operator zignoruje
- **Rollback** — jak cofnąć jeśli operator zaakceptuje, a potem zmieni zdanie
- **Decision class** — D0/D1/D2/D3/D4/D5 (D0 informational, D5 systemic)
- **Hard gate flag** — czy to jest hard gate (mandatory operator decision)

```yaml
example_advisor_card:
  id: "card_2026_05_15_abc123"
  type: "Subscription Advisor"
  trigger: "Anthropic PAYG approached $4.20/$5.00 cap (84%)"
  rationale: |
    Ostatnie 5 dni spending pattern:
    - Day 1: $0.40
    - Day 2: $0.85 (Council deliberation)
    - Day 3: $1.10 (build start)
    - Day 4: $0.95
    - Day 5: $0.90
    Trend: sustainable $0.85/day = $25.50/month forecast
    Vs Anthropic Pro tier $20/month z $30 quota
    ROI analysis: subscription saves $5.50/month + reduces decision friction
  suggestion: "Upgrade do Anthropic Pro tier subscription"
  confidence: 0.87
  risk: |
    Ignore: PAYG hard cap blokuje workflow w 1-2 dni
    Accept: $20/month commitment, free quota recovery
  rollback: "Anuluj subscription w pierwszym billing cycle (7 dni grace)"
  decision_class: "D3"
  hard_gate: true
  evidence_pack: "evidence_packs/subscription_2026_05_15.json"
```

---

# CZĘŚĆ II — 4 filary Advisor Layer

## 2.1. Filar 1 — Adaptive Preferences

System **uczy się** preferencji operatora przez czas.

### Macierz 3D preferencji
```
Preference matrix dimensions:
  • user (Robert)
  • project_type (SaaS, Internal Tool, Research, Government, ...)
  • project_domain (CRM, E-commerce, FinTech, HealthTech, ...)
  
4-level fallback (gdy specific brak):
  specific → user → project_type → global default
```

### 10+ preferencji śledzonych

**Hard preferences** (operator MUSI ustawić):
- `autonomy_level` (manual / standard / autonomous)
- `runtime_strategy` (local-first / hybrid / cloud-first)
- `blocked_providers` (np. providers których operator nie ufa)
- `cost_ceilings` (per project / per month / per provider)

**Soft preferences** (system sugeruje na podstawie historii):
- `preferred_council_size` (operator preferuje 9 ról vs 5 vs 12)
- `notification_channels` (email / mobile push / dashboard only)
- `review_depth` (quick / thorough / paranoid)
- `customer_communication_style` (formal / casual / technical)
- `default_test_strategy` (Comprehensive / Standard / Light)
- `default_deploy_strategy` (Canary / Blue-Green / Rolling)

### Adaptive learning examples

```
Po 5 podobnych projektach Polish SaaS:
  Robert wybrał Profile 2 dla wszystkich
  → Adaptive Preference: dla Polish_SaaS + Robert,
    default_resource_profile = "Profile 2 (Solo balanced)"
  
Po 3 projektach gov-funded:
  Robert zawsze włączał Funding Advisor
  → Adaptive Preference: dla gov_funded projects,
    funding_advisor_default = "enabled"

Po 10 Council deliberations:
  Robert zawsze override Critic verdyktu
  → Soft Adaptive: confidence w Critic verdicts spada,
    Critic weight może być adjusted (ale NIE auto — wymaga D3 decision)
```

## 2.2. Filar 2 — Recommendation Engine

System **continuously emituje** AdvisorCards w runtime.

### 16 lifecycle hooks

System emituje AdvisorCard w 16 punktach lifecycle:

| Hook | Kiedy | Przykład |
|---|---|---|
| H1 | Operator login | "Welcome back. 2 projects need attention." |
| H2 | Project inception (faza 16) | "Similar project Customer X CRM took 12 weeks — buduj 10w buffer" |
| H3 | Goal definition (faza 17) | "Goal 'real-time analytics' wymaga +$50/mo vendor pass-through" |
| H4 | Council convening (faza 20) | "Dla KSeF compliance, dodaj Polish Tax Specialist" |
| H5 | Council deliberation (faza 22) | "Verdict consensus 42% — rozważ 2nd round vs operator decision" |
| H6 | Księga generation (faza 25) | "Drift detected vs faza 17 goals — review przed lock" |
| H7 | Model selection (faza 26) | "Anthropic Pro saved 60% PAYG na podobnych projektach" |
| H8 | Skill synthesis (faza 27) | "Skill 'Generate Polish KSeF invoice' v2.4 dostępny w Marketplace" |
| H9 | Masterplan (faza 28) | "Profile 3 by saved 2 weeks za +$43 — customer Y miał deadline buffer" |
| H10 | Pre-flight cost (faza 30) | "Subscription saved $8 vs PAYG dla expected workload" |
| H11 | Build initialization (faza 32) | "Workspace 80% full — cleanup przed start zalecany" |
| H12 | Mid-build issue (faza 34 trigger) | "Customer scope change — Council reconvene zalecane" |
| H13 | Quality Gates (faza 37) | "Coverage drops do 78% — 3 critical paths untested" |
| H14 | Acceptance Testing (faza 38) | "Customer not engaging — proactive reminder zalecany" |
| H15 | Pre-deploy (faza 39) | "DNS propagation incomplete — wait 30 min" |
| H16 | Project closure (faza 41) | "Skill 'Customer Y branding' kandydat do promote (3 reuse)" |

### Hybrid: rule-based + LLM-as-judge

**Rule-based** dla obvious patterns:
```python
# Pseudokod
if cost_payg_spending > cap * 0.8 and trend == "sustained":
    emit_subscription_advisor_card()

if council_consensus < 50% and deliberation_round >= 2:
    emit_consensus_warning_card()

if guard_findings_critical > 0:
    emit_hard_gate_card()
```

**LLM-as-judge** dla subtle patterns:
```
LLM judge analizuje:
  - Historia operator decisions (z W9 Memory)
  - Current context (faza, projekt, customer)
  - Available alternatives
  - Risk profile
  - Operator's adaptive preferences
  
  → emit AdvisorCard z LLM-generated rationale + confidence
```

### Każda karta ma:
- **Rationale** — z evidence z różnych warstw
- **Rollback plan** — jak cofnąć decision
- **Risk assessment** — co się stanie
- **Confidence score** — z `aeis/advisor/history/` (historia podobnych decyzji)

## 2.3. Filar 3 — Specialized Advisors

5 wyspecjalizowanych Advisorów dla konkretnych domen.

### 2.3.1. Subscription Advisor

**Cel**: Hard gate na zakup subskrypcji LLM.

**Workflow**:
```
1. CONTINUOUS MONITORING (cross-faza):
   - Spending pattern per provider (Cost Guard W11)
   - Subscription tier exhaustion rate
   - PAYG hard cap proximity
   - Predictable workload patterns

2. TRIGGER CONDITIONS:
   - PAYG > 80% cap dla 5+ days (sustainable concern)
   - Subscription tier exhausted but workload continues
   - Provider price change announced
   - Alternative provider z subscription offered better ROI

3. ROI ANALYSIS:
   ROI = (PAYG_cost - subscription_cost) / subscription_cost
   Włączając:
   - Free tier quota (subscription benefit)
   - Rate limit improvements (productivity)
   - Predictable monthly cost
   - Cost ceiling protection

4. EVIDENCE PACK (D3+):
   - 30-day spending history
   - Workload forecast (next 30/60/90 days)
   - Provider comparison matrix
   - Switching cost estimate
   - Rollback plan (cancel within grace period)

5. HARD GATE:
   Operator MUST decide:
   [● Upgrade do subscription tier]
   [○ Increase PAYG cap z reasoning]
   [○ Switch provider z subscription offering]
   [○ Defer (continue PAYG monitoring)]
```

**Customer Y CRM example**:
```
Day 12 of build (Phase 4 Stripe integration):
  Anthropic PAYG spent: $4.10/$5.00 cap (82%)
  
Subscription Advisor emit AdvisorCard:
  Trigger: PAYG approaching cap z sustainable trend
  
  Analysis:
    - Last 7 days: $0.65/day average
    - Forecast next 14 days (build remaining): $9.10
    - Anthropic Pro tier: $20/month z $30 quota included
    - ROI: $9.10 PAYG - $20 subscription = -$10.90 (NIE worth it)
    BUT:
    - Monthly recurring projects (Customer Z, Customer W planned)
    - Combined forecast: $45/month
    - Subscription saves $25/month
    
  Confidence: 0.91 (z 5 podobnych projektów history)
  
  Hard gate decision: 
    [● Upgrade Anthropic Pro] ← operator chose
    
  Rollback plan: Anuluj w 7-day grace
  Audit chain entry: subscription_advisor_decision_2026_05_27
```

### 2.3.2. Scaling Advisor

**Cel**: local/VPS/hybrid/container/device decisions.

**Triggers**:
- Resource utilization patterns
- Cost-performance trade-offs
- Network latency requirements
- Data sovereignty constraints
- Scalability bottlenecks

**Decisions advised**:
- Switch lokalne → VPS (gdy GPU bottleneck)
- Switch VPS → hybrid (gdy compliance mix)
- Add edge device (gdy offline requirements)
- Container deploy (gdy multi-customer)
- On-prem migration (gdy government customer)

**Customer Y CRM example**:
```
Phase 32 (Build Initialization):
  
Scaling Advisor analizuje:
  - Customer Y: 50 users expected
  - Polish gov-funded → EU sovereignty required
  - Stripe + KSeF → external integrations
  - Profile 2 selected
  
AdvisorCard emit:
  Trigger: Optimal deployment configuration analysis
  
  Recommendation:
    Production: Hetzner CX31 (Helsinki) — $9/mo
    Staging: Hetzner CX21 (Helsinki) — $4.50/mo
    Dev: Local (Robert's machine)
    
  Alternative considered:
    AWS Frankfurt: $35/mo (4x cost, no benefit)
    On-prem: $0/mo + $5000 hardware (NIE worth dla 50 users)
    Hetzner Falkenstein: same cost, similar latency
  
  Confidence: 0.94
  Hard gate: false (informational)
```

### 2.3.3. Funding Advisor (opt-in)

**Cel**: generate grant applications (token-heavy, dlatego opt-in).

**Triggers**:
- Operator manually invokes
- Project type matches funding programs (cybersecurity, healthtech, AI, R&D)
- Company qualifies (Polish R&D, EU R&D, etc.)
- Active funding programs deadlines approaching

**Output**:
- Grant application draft (zgodne z formularzami programu)
- Consortium matcher (znajduje partnerów)
- Funding scoring (ocena szans)
- Budget allocation suggestions
- Risk analysis dla audit

**Customer Y CRM example**:
```
Faza 17 (Goal definition) — Funding Advisor opt-in invoked:

AdvisorCard emit:
  Trigger: Operator invoked Funding Advisor
  
  Analysis:
    Project type: Polish SaaS CRM z cybersecurity elements
    Robert's company: Polish R&D entity
    
  Matching programs:
    1. FENG SMART 1.1 (R&D innovation) — 30M PLN max
       Match score: 0.78 (KSeF compliance + cybersecurity adjacent)
       Deadline: 2026-09-15
    2. FENG SMART 5.2 (cyber resilience) — 15M PLN max
       Match score: 0.82 (better fit)
       Deadline: 2026-11-30
    3. EU Horizon Europe (cybersecurity) — €5M max
       Match score: 0.65 (need consortium)
       Deadline: 2027-02-15
  
  Recommendation: FENG SMART 5.2 (highest match + reasonable deadline)
  
  Estimated effort: 3-4 weeks application drafting
  Estimated cost: $80-150 (token-heavy LLM generation)
  
  Confidence: 0.74
  
  [Generate application draft]  [Defer]  [Decline]
```

### 2.3.4. Role Resolver Advisor

**Cel**: rola → konkretny model. **Najczęściej używany Advisor**.

**Workflow**:
```
1. Task arrives w Council deliberation OR build phase
2. Role Resolver analizuje:
   - Required skills (z W7 Skills Registry)
   - Capability matrix (W5 — text/code/Polish/long-context/vision/etc.)
   - Cost profile (z W11 — subscription tier first)
   - Operator preferences (Adaptive Preferences W13)
   - Historical success rate (W9 Memory — Skuteczności)
3. Hybrid task→skill matcher:
   - tag_overlap_score (Jaccard, Polish tags) × 0.6
   - cosine_similarity (embeddings) × 0.4
   - hybrid_match() → ranked candidates
4. Emit role assignment z confidence
```

**Customer Y CRM example**:
```
Faza 26 (Model Selection):

Role Resolver Advisor (continuous, dla każdego task):

  Task: "Generate Polish KSeF invoice integration code"
  
  Capability requirements:
    - text+code generation
    - Polish language native
    - long-context (KSeF docs ~80k tokens)
    - precision (compliance critical)
    - cost: medium budget
  
  Candidates ranked:
    1. claude-opus-4-7 z bielik-11b RAG: hybrid match 0.94
       Cost: $1.40/task, quality 0.97
    2. claude-sonnet-4-6 z polish_kseF_skill: 0.87
       Cost: $0.50/task, quality 0.89
    3. gpt-5: 0.71
       Cost: $0.55/task, quality 0.84
    4. bielik-11b standalone: 0.68
       Cost: $0/task, quality 0.78
  
  Recommendation: #1 (claude-opus + bielik RAG)
  
  Reasoning: KSeF compliance critical, +$0.90/task acceptable
  Confidence: 0.93
```

### 2.3.5. Variants Generator

**Cel**: generate alternative plans (cost-saving / balanced / aggressive).

**Trigger**: każdorazowo gdy operator robi major decision (faza 28 masterplan, faza 30 pre-flight cost, faza 39 pre-deploy).

**Output**: 3 plany side-by-side z trade-offs.

**Customer Y CRM example**:
```
Faza 28.4 (Resource Profile selection):

Variants Generator emit AdvisorCard z 5 profilami (Profile 1-5)
+ rationale dla each:
  
  Cost-saving: Profile 1 (Solo budget)
  Balanced: Profile 2 (Solo balanced) ← Robert chose
  Aggressive: Profile 4 (Maximum parallel)
  
  Plus 2 Custom variants:
    - "Customer Y deadline-optimized": Profile 3 + early KSeF integration
    - "Customer Y budget-protected": Profile 1 + extended timeline negotiation
```

## 2.4. Filar 4 — Guided UX

System **prowadzi** operatora przez UX, zwłaszcza dla nowych operatorów lub złożonych decyzji.

### Onboarding Wizard (10 kroków)

**Bezpośrednio mapuje na faza 1 manuala**, ale z dodatkową AdvisorCard support:

| Krok | Co operator robi | Advisor support |
|---|---|---|
| 1 | Master password | "Strength meter recommendations" |
| 2 | Recovery phrase | "Storage best practices" |
| 3 | Profile (locale, tech) | "Language detection z system" |
| 4 | Workspace allocation | "Disk space analysis + backup recommendations" |
| 5 | First provider | "Recommended: start z lokalne (Bielik) — $0 cost" |
| 6 | Mobile pairing | "Optional, ale recommended dla productivity" |
| 7 | Autonomy preset | "Production preset zalecany dla pierwszego projektu" |
| 8 | First Council template | "Public SaaS template universal start" |
| 9 | First test strategy | "Comprehensive zalecane dla learning" |
| 10 | Final review | "Setup verified, ready dla project inception" |

### Live Feed

Continuous stream AdvisorCards w UI:
- **Toast notifications** (non-intrusive, swipe to dismiss)
- **Modal dialogs** (dla hard gates, MUST acknowledge)
- **Bubble counter** (unresolved cards count, np. "3 cards pending")

### Lifecycle Dashboard

Per-project view z:
- Current phase + progress
- Active AdvisorCards
- Pending decisions
- Resolved actions
- Memory of past similar projects (z W9)

### Operator Monitor

Cross-project view z:
- All projects status
- Aggregate AdvisorCards
- Recent decisions
- Resource utilization
- Subscription status
- Audit chain integrity

---

# CZĘŚĆ III — Storage + komponenty

## 3.1. Storage architecture

Advisor Layer używa **PostgreSQL only** (świadoma divergencja od SQLite-dominant pattern reszty repo).

**12 schemas**:
1. `advisor_engine` — rule engine + LLM judge core
2. `advisor_funding` — Funding Advisor specific (consortium, scoring)
3. `advisor_history` — confidence z historii decyzji
4. `advisor_pricing` — subscription + PAYG tracking
5. `advisor_preferences` — adaptive preferences matrix
6. `advisor_actions` — emitted cards + operator responses
7. `advisor_outbound` — notifications dispatch
8. `advisor_subscription` — Subscription Advisor specific
9. `advisor_scaling` — Scaling Advisor specific
10. `advisor_orchestration` — Role Resolver + role pipeline
11. `advisor_evidence` — D3+ Evidence Packs
12. `advisor_events` — lifecycle hooks audit

Migration via `advisor_layer.sql`.

## 3.2. Komponenty kluczowe

```
aeis/advisor/
├── engine/
│   ├── rule_engine.py        # Rule-based pattern matching
│   ├── llm_judge.py          # LLM-as-judge dla subtle patterns
│   ├── decision_ladder.py    # D-level classification
│   └── confidence.py         # Confidence scoring
├── funding/
│   ├── consortium_matcher.py # Find partner organizations
│   └── funding_scoring.py    # Match score per program
├── history/
│   └── confidence_provider.py # Historical success rates
├── role_resolver.py          # Role → model assignment
└── orchestration_engine.py   # Pipeline orchestration

13 sub-services advisor (per Specialized Advisor + supporting).
```

## 3.3. Audit chain

**Per Advisor decision** entry w `advisor_events.jsonl`:
```json
{
  "id": "evt_2026_05_27_abc",
  "type": "subscription_advisor_decision",
  "card_id": "card_2026_05_27_xyz",
  "operator_response": "accepted",
  "decision_class": "D3",
  "evidence_pack_id": "evidence_2026_05_27_xyz",
  "rationale_hash": "sha256:...",
  "rollback_plan_id": "rollback_2026_05_27_xyz",
  "confidence_score": 0.91,
  "audit_signature": "ed25519:..."
}
```

---

# CZĘŚĆ IV — Integracja z 41 fazami

Każda z 41 faz manuala **ma Advisor hooks**. Tabela:

| Faza | Advisor activity | Karty emitowane (typowe) |
|---|---|---|
| 1 | Onboarding Wizard | guidance every step (10 cards) |
| 2 | Subscription Advisor (initial setup) | "Start z subscription saves $X/mo" |
| 3 | Scaling Advisor | "Hetzner Helsinki dla EU sovereignty" |
| 4 | Adaptive Preferences (defaults) | "Based on Polish customers history" |
| 5 | D-ladder + Hard Gates explained | "Production preset zalecany" |
| 6-10 | Guards activation | per-Guard configuration cards |
| 11-15 | Skills + Templates | "Marketplace skill X used przez Y operatorów" |
| 16 | Idea Lifecycle (W2) | "Similar projects took N weeks" |
| 17 | Goal alignment | "Goal X może wymagać +$Y vendor" |
| 18 | Scope reality check | "Scope creep risk dla customer Y type" |
| 19 | Council customization | "Add Polish Tax Specialist dla KSeF" |
| 20-25 | Council deliberation | role_resolver continuous, drift_detection |
| 26 | Model Selection | role_resolver per task |
| 27 | Skill Synthesis | demand_analyzer suggestions |
| 28 | Masterplan z 28.4 | **Variants Generator** (5 profiles) |
| 29 | Test Plan | "Coverage gaps: 3 modules" |
| 30 | Pre-Flight Cost | **Subscription Advisor hard gate** |
| 31 | Pre-Flight Dry Run | "Run additional integration test" |
| 32 | Build Init | Scaling Advisor "deploy plan validated" |
| 33 | Sequential Phase | continuous monitoring, no cards typowo |
| 34 | Mid-Build Council | "Council reconvene zalecane" |
| 35 | Build Orchestration | "Profile switch zalecany" |
| 36 | Build Completion | "Skills promote candidates" |
| 37 | Quality Gates | "Auto-fix attempt zalecany" |
| 38 | Acceptance Testing | "Customer not engaging — proactive reminder" |
| 39 | Pre-Deploy | **Hard gate**: production deploy authorization |
| 40 | Production Deploy | continuous canary monitoring |
| 41 | Closure | "Skills promote, calibration data extracted" |

**Total**: ~80-150 AdvisorCards per typical D4 project (Customer Y CRM had ~120).

---

# CZĘŚĆ V — Customer Y CRM — Advisor activity ledger

Pełen lifecycle z perspektywy Advisor Layer:

## Setup (faza 1-15): 28 cards
- 10 cards Onboarding Wizard
- 3 cards Subscription Advisor (recommend Bielik lokalne, Anthropic Pro deferred)
- 2 cards Scaling Advisor (Hetzner regions)
- 5 cards Adaptive Preferences (start defaults)
- 4 cards Guards configuration
- 4 cards Skills + Templates (Stripe marketplace skill recommendation)

## Project Inception (faza 16-19): 12 cards
- 1 card Idea Lifecycle ("similar Polish SaaS projects took 8-12 weeks")
- 2 cards Funding Advisor (FENG SMART matching)
- 4 cards Role Resolver (Council role assignments)
- 3 cards Goal alignment (KSeF compliance flagged early)
- 2 cards Scope creep prediction (gov-funded customer pattern)

## Council Deliberation (faza 20-25): 18 cards
- 9 cards Role Resolver (per role model assignment)
- 3 cards drift detection (Council vs Księga consistency)
- 4 cards consensus warnings
- 2 cards Critic challenges flagged

## Planning (faza 26-31): 22 cards
- 5 cards Variants Generator (5 profiles compared)
- 4 cards Subscription Advisor (Anthropic Pro upgrade evaluated)
- 3 cards Scaling Advisor (Hetzner CX31 vs CX41 decision)
- 5 cards Cost ceiling proximity warnings
- 3 cards Test Plan recommendations
- 2 cards Dry Run additional scenarios

## Build (faza 32-36): 18 cards
- 1 card Profile switch consideration (mid-build)
- **Faza 34 trigger** — Council reconvene card (customer scope change)
- 3 cards Cross-worker coordination warnings
- 4 cards Cost spike anomalies
- 5 cards Skills promotion candidates (Customer Y branding patterns)
- 4 cards Build cleanup recommendations

## Testing + Deploy + Closure (faza 37-41): 22 cards
- 7 cards Quality Gates auto-fix recommendations (7 failures)
- 3 cards Customer engagement reminders
- 5 cards Pre-deploy hard gates (mandatory operator decisions)
- 3 cards Production canary monitoring
- 4 cards Closure (skills promote, calibration, archive)

**TOTAL**: ~120 AdvisorCards.

**Operator response distribution**:
- 78% accepted (Advisor confidence calibrated well)
- 12% modified (operator z reasoning — adaptive learning signal)
- 6% deferred (operator nie ready)
- 3% rejected (operator override z reasoning)
- 1% expired (no operator response)

---

# CZĘŚĆ VI — Adaptive learning loop

Po Customer Y CRM closure, Advisor Layer **uczy się**:

```
Memory updates (W9 Skuteczności + W13):
  
Adaptive Preferences updated:
  - For Polish_SaaS + Robert + gov_funded:
    • default_council_size: 9 (vs 12 default) — Robert preferred 9
    • default_runtime: hybrid (lokalne dev + Hetzner staging+prod)
    • default_resource_profile: Profile 2 (Solo balanced)
    • funding_advisor_default: enabled
    • critic_weight_adjustment: +5% (Robert overrode Critic 3x)
  
Specialized Advisors learning:
  - Subscription Advisor: 
    • For multi-project monthly $40+: always recommend Pro tier
    • Confidence model updated z Customer Y outcome
  - Scaling Advisor:
    • Hetzner Helsinki dla EU = 0 issues, confidence 0.96 confirmed
    • CX31 dla 50-user SaaS = optimal, no overprovisioning
  - Role Resolver:
    • claude-opus + bielik RAG dla KSeF: success rate 0.94 → 0.96
    • Confidence boost dla similar future tasks
  - Funding Advisor:
    • FENG SMART matching dla Polish R&D companies: validated
  - Variants Generator:
    • 5-profile structure (z faza 28.4 patch) validated as optimal

Confidence model (advisor_history):
  - 87% historical accuracy → 89% (Customer Y outcomes integrated)
  - Per-Specialized-Advisor confidence trends update
  
Future projects benefit:
  - Faster setup (defaults pre-filled z preferences)
  - Better recommendations (z calibrated models)
  - Fewer "discovery" cards (Advisor zna patterns)
```

---

# CZĘŚĆ VII — Patches do faz 1-41

Ten dokument identyfikuje **gdzie 41-fazowy manual potrzebuje update** żeby uwzględnić Advisor:

## 7.1. Faza 1 (Setup) — patch

**Dodaj do faza 1**:
```
1.X. Onboarding Wizard (W13 Filar 4)
  
  Setup Wizard nie jest tylko 7-step formularz — to W13 Onboarding 
  Wizard z 10 kroków + Advisor support per krok.
  
  Każdy krok ma dedykowany AdvisorCard z:
  - Recommendation based on detected context
  - Best practices
  - Common pitfalls
  - Rollback options
```

## 7.2. Faza 5 (Autonomy) — patch

**Naprawić D-ladder z D1-D5 do D0-D5**:
- Dodać **D0 Informational** (auto, no human, no rollback)
- Decision ladder z 6 klas (nie 5)
- Reguły eskalacji U1-U6 explicit

## 7.3. Faza 7 (Cost Guard) — patch

**Dodać Subscription waterfall** (W11 Adapter Bus):
```
Cost decision priority:
  1. Subscription tier first (free quota)
  2. PAYG po exhaustion
  3. Hard cap blocks
  4. Subscription Advisor (W13) hard gate gdy PAYG sustained 80%+
```

## 7.4. Fazy 20-25 (Council) — patch

**Naprawić Council architecture**:
- 9 ról (NIE 12) — Planner / Critic / Security / Legal / Finance / Governance / QA / Red Team / Council Chair
- 5 rang per rola — primary (1.0) / support (0.7) / observer (0.4) / cost_sentinel (0.35) / security_sentinel (0.35)
- 4 fazy deliberacji — parallel verdicts / discussion / consolidated vote / **critic signature** (mandatory D3+)

## 7.5. Customer Y CRM example — recalculation

**Przy uwzględnieniu subscription waterfall (W11) + Subscription Advisor (W13)**:

Original assumption (wszystko PAYG): $358.50

Z subscription waterfall:
```
Anthropic Pro tier ($20/mo × 3 mo = $60):
  Free quota: $30/mo × 3 = $90 wartości free (subscription benefit)
  
Faktyczne paid spending PAYG:
  Phase 1-15: $0.0003 → $0
  Phase 16-25: $56.60 - subscription_quota_used = ~$26
  Phase 26-31: $32.10 - subscription_quota = ~$2 (most consumed earlier)
  Phase 32-36: $142.30 - subscription_quota = ~$142 (already exhausted)
  Phase 37-41: $127.20 PAYG
  
TOTAL paid: ~$297
TOTAL subscription: $60
GRAND TOTAL: $357 (essentially same, ale z $60 predictable + $297 PAYG)

Per-key cost (9 testowy keys, $5 cap each):
  Average per-key paid usage: $33 — przekracza $5 cap!
  
WNIOSEK: dla Customer Y CRM, $5 per-key cap wymagałby
WIELU keys per provider, lub Subscription tier był NIEZBĘDNY.
```

**To oznacza**: dla testowy plan ($45 total z 9 keys), Customer Y CRM nie zmieściłby się jako proof of concept. Trzeba albo:
1. Use subscription tier first (Anthropic Pro = $20/mo flat)
2. Lub mniej testów per key (fewer iterations)
3. Lub mniejsza scope projekt (smaller D-level)

---

# CZĘŚĆ VIII — Co dalej

Po przeczytaniu tego dokumentu:

1. **Wróć do** `00_ARCHITEKTURA_W1_W19.md` z lepszym zrozumieniem W13
2. **Przeczytaj** `00_PATCHES_FAZ.md` — explicit patches do fazy 5, 7, 20-25 (jeśli zostanie wygenerowany)
3. **Wróć do** 41 faz manuala — teraz z świadomością Advisor hooks per faza

**Kluczowe rozumienie**:
- Bez Advisor: AEIS = workflow executor (operator klika, system wykonuje)
- Z Advisor: AEIS = inteligentny współpracownik (system zauważa, sugeruje, eskaluje)
- 16 lifecycle hooks = continuous AdvisorCards stream
- 5 Specialized Advisors = domain expertise (subscription / scaling / funding / role / variants)
- 4 filary integrate całość: preferences + recommendations + specialists + UX

🎯 **Manual operatora teraz uwzględnia W13** — najważniejszą warstwę proaktywnej inteligencji.
