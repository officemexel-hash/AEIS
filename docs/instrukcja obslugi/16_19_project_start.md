# FAZY 16-19 — Start projektu (Grupa B)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: B — Start projektu (1-4 z 4) — cała grupa B
> **Zależności**: Fazy 1-15 zakończone (full operator setup)
> **Następnik**: Faza 20 (Council Convening — start grupy C)
>
> **Zmiana charakteru od grupy B**:
> Dotychczas konfigurowaliśmy **operatora**. Od fazy 16 operator
> faktycznie **uruchamia projekt** — używa skonfigurowanej
> infrastruktury (providers, environments, autonomy, Guards, skills,
> templates) żeby zbudować konkretny software.
>
> **Nowy pattern dla faz lifecycle projektu**:
> - Każda faza ma **input** (co operator/system już ma) i **output**
>   (co zostaje produced)
> - Each transition is signed audit event (z faza 10 Provenance)
> - Operator może **paused/resumed** w każdej fazie
> - Hard gates aplikują się selektywnie (per autonomy + per faza)
>
> **Wspólna struktura każdej fazy lifecycle**:
> - Sense + miejsce w lifecycle
> - Inputs (z poprzednich faz lub operator)
> - Workflow (step-by-step)
> - Outputs (co zostaje produced)
> - Decision points (gdzie operator/system decydują)
> - Inheritance (co dziedziczy z faz konfiguracji)
> - Edge cases (15-22)
> - Acceptance criteria + transition do następnej fazy

---

# FAZA 16 — Project Inception

> **Spis sekcji**:
> - 16.1 — Sense fazy + start lifecycle projektu
> - 16.2 — 3 ścieżki tworzenia projektu (idea / template / fork)
> - 16.3 — Initial classification (D-level prediction)
> - 16.4 — Workspace allocation (resources reservation)
> - 16.5 — Initial artifacts (project shell)
> - 16.6 — Pre-flight checks
> - 16.7 — Edge cases (18) + transition do fazy 17

---

## 16.1. Sense fazy + start lifecycle

### 16.1.1. Co operator robi w fazie 16

Operator ma **pomysł na projekt** lub **konkretną potrzebę** (customer
request, internal need, research idea). Faza 16 transformuje pomysł w
**workspace project entity** — pierwszy konkretny artifact istniejący w
AEIS.

```
┌──────────────────────────────────────────────────────────────┐
│  Project Inception — od pomysłu do project entity            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (od operator):                                        │
│   • Krótki opis pomysłu (1-3 zdania lub paragraf)            │
│   • Optional: customer context                               │
│   • Optional: deadline                                        │
│   • Optional: budget hint                                    │
│   • Optional: starting reference (similar project, template) │
│                                                              │
│  PROCESSING (AEIS):                                          │
│   • Initial D-level prediction (z pomysłu)                   │
│   • Recommended template selection (Council/Test/Deploy/Cost)│
│   • Workspace resource allocation                             │
│   • Project shell creation (folder structure, audit init)    │
│                                                              │
│  OUTPUT (project entity):                                    │
│   • project_id (unique)                                      │
│   • Initial metadata (name, description, classification)     │
│   • Reserved resources (LLM budget, env capacity)            │
│   • Genesis audit chain entry                                │
│   • Ready dla faza 17 (Goal Definition)                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 16.1.2. Wynik fazy 16 (DoD)

```
✓ Project entity created z unique ID
✓ Initial classification done (D-level estimated)
✓ Templates assigned (Council/Test/Deploy/Cost)
✓ Resources reserved (budget, env, LLM quota)
✓ Project shell scaffolded
✓ Pre-flight checks passed
✓ Audit chain entry: project_inception (signed)
✓ Project state: READY_FOR_GOAL_DEFINITION
```

### 16.1.3. Czas trwania

```
Quick path (template-based, prosty projekt): 5-15 min
Standard path (operator describes pomysł, system analyzes): 15-30 min
Complex path (D5 z stakeholder mapping): 1-2h
```

---

## 16.2. 3 ścieżki tworzenia projektu

### 16.2.1. Ścieżka A — From idea (default, most common)

Operator opisuje pomysł, AEIS analizuje i sugeruje setup:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  New Project — From Idea                                  │
│                                                              │
│  Describe your project (Polish or English):                  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Chcę zbudować dla Customer Y system zarządzania klient-│ │
│  │ -ami z modułem płatności (Stripe). Polska jurysdykcja, │ │
│  │ KSeF compliance wymagana. Customer ma deadline 2026-06,│ │
│  │ budget €3000, użytkownicy: 10-50 customer's employees. │ │
│  │ Wymaga PL + EN UI.                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Optional context:                                           │
│   Customer: [Customer Y                                ]    │
│   Project type hint: [○ Auto-detect ▼]                       │
│   Reference projects (similar work): [+ Add reference]       │
│                                                              │
│  AEIS analysis (preview):                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Detected:                                             │ │
│  │   • Type: SaaS (CRM + payment)                         │ │
│  │   • D-level: D4 (production, payment, customer-facing) │ │
│  │   • Compliance: GDPR + KSeF + PCI DSS (payment)        │ │
│  │   • Multilanguage: PL + EN                             │ │
│  │   • Scale: small-medium (10-50 users)                  │ │
│  │   • Customer-funded (deadline + budget given)          │ │
│  │                                                        │ │
│  │  Recommended templates:                                │ │
│  │   • Council: Public SaaS z payment (12 roles)          │ │
│  │   • Test: Comprehensive (L1-L5, mandatory L5)          │ │
│  │   • Deploy: Canary do production                       │ │
│  │   • Cost: Strict customer-funded                       │ │
│  │                                                        │ │
│  │  Estimated:                                            │ │
│  │   • Cost: $400-700 (using LARGE budget template)       │ │
│  │   • Time: 4-6 weeks                                    │ │
│  │   • Risk: medium-high (D4 + customer + payment)        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  [Accept analysis + create]  [Customize]  [Cancel]           │
└──────────────────────────────────────────────────────────────┘
```

**Co AEIS analizuje z opisu**:

```
LLM-based analysis extracts:
  • Project type (SaaS / mobile / desktop / library / etc.)
  • Domain (e-commerce / fintech / healthcare / etc.)
  • Stakeholders (customer / internal / public / regulator)
  • Compliance hints (GDPR / KSeF / PCI / HIPAA / etc.)
  • Languages / locales
  • Scale (users, transactions)
  • Constraints (deadline, budget, technology)
  • Integration requirements (Stripe, OAuth, etc.)

Cost: ~$0.30 (one analysis call, claude-sonnet)
```

### 16.2.2. Ścieżka B — From template

Operator wybiera predefined project template:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  New Project — From Template                              │
│                                                              │
│  Choose template:                                            │
│                                                              │
│  ┌─ POLISH SAAS WITH PAYMENT ──────────────────────────┐    │
│  │  Pre-configured for:                                 │    │
│  │   • Polish market + KSeF                             │    │
│  │   • Stripe payment integration                       │    │
│  │   • PL + EN multilanguage                            │    │
│  │   • Customer-facing                                  │    │
│  │   • D4 default                                       │    │
│  │  Templates included:                                  │    │
│  │   • Council: Public SaaS z payment                   │    │
│  │   • Test: Comprehensive                              │    │
│  │   • Deploy: Canary                                   │    │
│  │  Estimated: $400-700, 4-6 weeks                      │    │
│  │  [Use template]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ INTERNAL CRM ──────────────────────────────────────┐     │
│  │  Pre-configured for:                                 │    │
│  │   • Internal team usage                              │    │
│  │   • No payment                                       │    │
│  │   • Polish only                                      │    │
│  │   • D2-D3 default                                    │    │
│  │  Estimated: $100-200, 2-3 weeks                      │    │
│  │  [Use template]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ RESEARCH EXPERIMENT ───────────────────────────────┐     │
│  │  Pre-configured for:                                 │    │
│  │   • Quick prototype                                  │    │
│  │   • Research preset autonomy                         │    │
│  │   • D1-D2                                            │    │
│  │  Estimated: $20-50, days                             │    │
│  │  [Use template]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ EDGE/IOT INTEGRATION ──────────────────────────────┐     │
│  │  Pre-configured for:                                 │    │
│  │   • Edge devices (RPi, NUC)                          │    │
│  │   • Sovereign processing                             │    │
│  │   • D3-D4                                            │    │
│  │  [Use template]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ GOVERNMENT CLASSIFIED ─────────────────────────────┐     │
│  │  Pre-configured for:                                 │    │
│  │   • TLP:RED workloads                                │    │
│  │   • Air-gapped or sovereign                          │    │
│  │   • D5 default                                       │    │
│  │   • Conservative autonomy                            │    │
│  │  [Use template]                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  [+ More templates]  [Custom from scratch]                   │
└──────────────────────────────────────────────────────────────┘
```

### 16.2.3. Ścieżka C — From fork (existing project)

Operator forkuje istniejący projekt:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  New Project — Fork Existing                              │
│                                                              │
│  Source project: [Sylion Tailor v3 (closed) ▼]               │
│                                                              │
│  Fork strategy:                                              │
│                                                              │
│  [● Continue evolution — Sylion Tailor v4]                   │
│      Inherits: codebase, learnings, customer relationship    │
│      Skips: re-do design from scratch                        │
│      Use case: next version of same product                  │
│                                                              │
│  [○ Adapt for new customer — Sylion Tailor for Customer Z]   │
│      Inherits: solution architecture, skills                 │
│      Customize: branding, customer-specific features         │
│      Use case: customer-specific variant                     │
│                                                              │
│  [○ Apply pattern to new domain]                             │
│      Inherits: only proven patterns + skills                  │
│      Reuses: Council templates, test strategies              │
│      Use case: similar problem, different domain             │
│                                                              │
│  Diff preview:                                               │
│  [Show what's preserved vs new]                              │
│                                                              │
│  Risk:                                                       │
│   ⚠ Forking inherits old assumptions — review carefully      │
│   ⚠ Customer-specific data NIE forks (privacy)               │
│                                                              │
│  [Create fork]                                               │
└──────────────────────────────────────────────────────────────┘
```

---

## 16.3. Initial classification — D-level prediction

### 16.3.1. D-level definition (recap)

```
D1 — Trivial (prototype, throwaway)
D2 — Light (internal tool, low impact)
D3 — Standard (production app, moderate impact)
D4 — Critical (customer-facing, payment, deadlines)
D5 — Mission-critical (government, financial regulation, classified)
```

### 16.3.2. D-level prediction algorithm

```python
def predict_d_level(project_description, context):
    factors = analyze_project(project_description)
    
    # Base D-level
    d = 1
    
    # Factors increasing D-level
    if factors.has_payment:           d = max(d, 4)
    if factors.has_customer_data:     d = max(d, 3)
    if factors.is_customer_facing:    d = max(d, 3)
    if factors.has_deadline:          d = max(d, 3)
    if factors.compliance_required:   d = max(d, 4)
    if factors.classified:            d = 5
    if factors.financial_regulated:   d = 5
    if factors.affects_health_safety: d = 5
    if factors.large_scale_users:     d = max(d, 4)
    if factors.budget_high:           d = max(d, 4)
    
    # Factors decreasing D-level
    if factors.is_research:           d = min(d, 2)
    if factors.is_internal_tool:     d = min(d, 3)
    if factors.is_throwaway:          d = 1
    
    return d
```

### 16.3.3. Operator override

```
┌──────────────────────────────────────────────────────────────┐
│  D-level Classification                                      │
│                                                              │
│  AEIS predicted: D4                                          │
│  Reasoning:                                                  │
│   • Has payment integration (Stripe)                          │
│   • Customer-facing                                           │
│   • External deadline                                         │
│   • Compliance required (GDPR + KSeF + PCI)                   │
│                                                              │
│  Operator override:                                          │
│   [● Accept D4 (recommended)]                                 │
│   [○ Lower to D3 (operator confident in lower stakes)]        │
│   [○ Raise to D5 (operator needs maximum oversight)]          │
│                                                              │
│  Implications of D-level:                                    │
│   D4 means:                                                   │
│    • Council: full board (12 roles)                          │
│    • Tests: comprehensive (L1-L5)                            │
│    • Deploy: canary z operator approval                      │
│    • Hard gates: production deploy + payment + cost spikes   │
│    • Autonomy preset: Production (more conservative)         │
│                                                              │
│  Lifecycle implications:                                     │
│   D4 projects typically:                                     │
│    • 4-6 weeks duration                                       │
│    • $400-700 cost                                           │
│    • 15-25 operator interactions                             │
│    • 3-5 Council deliberation rounds                          │
│    • 2-3 build phases                                         │
│                                                              │
│  [Confirm D-level]                                           │
└──────────────────────────────────────────────────────────────┘
```

### 16.3.4. D-level może zmienić się w trakcie

```
Ważne: D-level predicted teraz to estimate. Może zmienić się gdy:
  • Faza 17 (Goal Definition) — operator dodaje wymagania
  • Faza 18 (Scope Definition) — scope rośnie/maleje
  • Faza 25 (Book Finalization) — full understanding
  • Faza 28 (Masterplan) — final scope clear

Każda zmiana D-level:
  • Loguje audit chain entry
  • Notification do operator
  • Może zmienić templates (Council, Test, Deploy)
  • Może zmienić budget cap
  • Może wymagać re-approval workflow
```

---

## 16.4. Workspace allocation

### 16.4.1. Resource reservation

```
┌──────────────────────────────────────────────────────────────┐
│  Workspace Allocation — Customer Y CRM                       │
│                                                              │
│  Reserved resources:                                         │
│                                                              │
│  Budget:                                                     │
│   Template:        LARGE ($250 hard cap — z faza 4)          │
│   Customer cap:    €500 (per customer policy z faza 15)      │
│   Effective cap:   $250 (lower of two)                       │
│   Reserved upfront: $25 (10% buffer per autonomy preset)     │
│                                                              │
│  LLM quota:                                                  │
│   Anthropic monthly: 8% of $200 ($16 reserved)               │
│   OpenAI monthly:    5% of $100 ($5 reserved)                │
│   Local:             unlimited (free)                        │
│                                                              │
│  Environments:                                               │
│   Dev:      local-dev (free, available)                      │
│   Staging:  to be created (Hetzner CX21, ~€4.20/mo)          │
│   Prod:     to be created (Hetzner CX31, ~€8.40/mo)          │
│                                                              │
│  Storage:                                                    │
│   Workspace:    ~/.sylion/<op>/projects/customer_y_crm/      │
│   Estimated:   500 MB - 2 GB (typical for SaaS project)      │
│                                                              │
│  Time slots:                                                 │
│   Operator availability: estimated 8-15h over 4-6 weeks      │
│   Hard gate response: required (Production preset)           │
│                                                              │
│  [Confirm allocation]  [Adjust]                              │
└──────────────────────────────────────────────────────────────┘
```

### 16.4.2. Resource conflicts

Co jeśli reserved resources NIE dostępne (e.g., monthly LLM quota
exhausted)?

```
⚠ Resource conflict

  Required: 8% of Anthropic monthly quota ($16)
  Available: 3% remaining ($6)
  Difference: $10 short
  
  Akcje:
   [Use lower-quota model dla this project]
       claude-sonnet → claude-haiku (cheaper)
   [Defer project until next month]
   [Increase Anthropic monthly limit]
       Operator approves higher cap
   [Use OpenRouter as fallback]
```

---

## 16.5. Initial artifacts (project shell)

### 16.5.1. Folder structure scaffolded

```
~/.sylion/<op>/projects/customer_y_crm/
├── metadata.json           # project entity definition
├── audit/
│   ├── chain.jsonl         # project's audit chain (linked do workspace)
│   └── genesis.json        # genesis entry
├── ksiega/                 # będzie wypełnione w fazach 20-25
│   └── (empty)
├── council/                # będzie wypełnione w fazach 22-25
│   └── (empty)
├── masterplan/             # będzie wypełnione w fazach 28-31
│   └── (empty)
├── code/                   # będzie wypełnione w fazach 32-36
│   └── (empty)
├── tests/                  # będzie wypełnione w fazach 32-36
│   └── (empty)
├── deployments/            # będzie wypełnione w fazach 39-41
│   └── (empty)
└── reports/                # ongoing
    └── (empty)
```

### 16.5.2. Metadata initial

```json
{
  "id": "proj_customer_y_crm_2026_05_01",
  "name": "Customer Y CRM",
  "display_name": "CRM dla Customer Y",
  "description": "<operator's idea>",
  "created_at": "2026-05-01T14:32:18Z",
  "created_by": "robert.k",
  "status": "INCEPTION",
  "phase": "16",
  
  "classification": {
    "d_level": 4,
    "type": "saas",
    "industry": "general",
    "is_customer_facing": true,
    "is_customer_funded": true,
    "customer": "Customer Y",
    "compliance": ["gdpr", "ksef", "pci_dss"],
    "languages": ["pl", "en"],
    "scale": "small_medium",
    "deadline": "2026-06-30"
  },
  
  "templates": {
    "council": "ct_public_saas_payment",
    "test_strategy": "ts_comprehensive",
    "deployment": "dt_canary_production",
    "cost_policy": "cp_strict_customer"
  },
  
  "budgets": {
    "hard_cap_usd": 250,
    "customer_cap_eur": 500,
    "effective_cap_usd": 250,
    "reserved_upfront_usd": 25,
    "spent_usd": 0
  },
  
  "autonomy": {
    "preset": "Production",
    "overrides": {}
  },
  
  "estimated": {
    "cost_usd": 400,
    "duration_weeks": 5,
    "operator_interactions": 18
  }
}
```

### 16.5.3. Genesis audit entry

```jsonl
{"ts":"2026-05-01T14:32:18Z","event":"project.genesis",
 "project":"proj_customer_y_crm_2026_05_01",
 "actor":{"type":"operator","id":"robert.k","device":"desktop"},
 "data":{
   "name":"Customer Y CRM",
   "d_level":4,
   "templates":[...],
   "budgets":[...],
   "operator_idea":"<full description>"
 },
 "prev_hash":"<workspace chain head>",
 "hash":"<this entry hash>",
 "signature":"<operator's Ed25519 signature>"}
```

---

## 16.6. Pre-flight checks

### 16.6.1. Mandatory checks przed project creation

```
┌──────────────────────────────────────────────────────────────┐
│  Project Inception — Pre-Flight Checks                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Operator setup:                                             │
│   ✓ Workspace exists                                         │
│   ✓ At least 1 LLM provider configured                       │
│   ✓ At least 1 environment available                         │
│   ✓ Autonomy preset configured                               │
│                                                              │
│  Resources:                                                  │
│   ✓ Budget available (z workspace cap)                       │
│   ✓ LLM quota sufficient                                     │
│   ✓ Storage available (>1 GB free)                           │
│                                                              │
│  Templates:                                                  │
│   ✓ Council template selected                                │
│   ✓ Test strategy selected                                   │
│   ✓ Deploy template selected                                 │
│   ✓ Cost policy selected                                     │
│                                                              │
│  Compliance:                                                 │
│   ✓ Project compliance NIE conflicts z workspace             │
│   ✓ Data residency rules satisfied (if applicable)           │
│   ✓ Customer policy aligned (if customer project)            │
│                                                              │
│  Guards:                                                     │
│   ✓ All 5 Guards active                                      │
│   ✓ Coherence Guard ready                                    │
│   ✓ Cost Guard ready (z budget cap defined)                  │
│   ✓ Security Guard ready (compliance frameworks loaded)      │
│   ✓ Quality Guard ready                                      │
│   ✓ Provenance Guard ready (signing key available)           │
│                                                              │
│  All checks passed. Ready to create project.                 │
│  [Create project]  [Cancel]                                  │
└──────────────────────────────────────────────────────────────┘
```

### 16.6.2. Soft warnings

```
⚠ Soft warnings (operator decyduje)

  • Operator has 7 active projects (high concurrent load)
    Recommendation: complete some before starting new
  
  • Customer Y has 2 active projects already
    Total customer cap: €500 — already 60% used
    Recommendation: confirm budget headroom z customer
  
  • LLM quota Anthropic 88% used this month (will hit cap soon)
    Recommendation: budget conservative or wait until next month
```

---

## 16.7. Edge Cases — Project Inception (18 cases)

### Kategoria A — Idea analysis issues (4 cases)

**EC-A1**: AEIS misclassifies project type
- Trigger: operator's description ambiguous, AEIS guesses wrong (e.g., research vs internal tool)
- Akcje: operator override, provide hint, switch template

**EC-A2**: D-level prediction conflict
- Trigger: AEIS predicts D2, operator believes D4 (or vice versa)
- Akcje: operator override z reason, audit log

**EC-A3**: Compliance hints missed
- Trigger: project needs HIPAA, AEIS didn't detect
- Akcje: operator manually adds compliance, system reconfigures templates

**EC-A4**: Description too vague
- Trigger: 1-line description, AEIS can't analyze
- Akcje: prompt operator dla more context, suggest questions, offer template path instead

### Kategoria B — Template fit issues (4 cases)

**EC-B1**: No template matches project
- Trigger: novel project type
- Akcje: closest template + customize, build custom template w fazie 12

**EC-B2**: Template z fazy 12 nie skonfigurowany
- Trigger: operator skipped fazę 12 customization, default templates dont fit
- Akcje: use defaults z warning, prompt operator do faza 12

**EC-B3**: Template z removed dependencies
- Trigger: template references skill that was removed
- Akcje: install missing skill, use alternative, modify template

**EC-B4**: Template version mismatch
- Trigger: template updated since last use, operator preferences incompatible
- Akcje: migrate, fork old version, manual review

### Kategoria C — Resource conflicts (4 cases)

**EC-C1**: Budget cap exceeded by customer policy
- Trigger: workspace cap $250, customer policy €500 (~$540)
- Akcje: lower of two enforced, operator notified

**EC-C2**: LLM quota exhausted
- Trigger: monthly Anthropic cap hit
- Akcje: defer, switch providers, increase cap

**EC-C3**: Environment unavailable
- Trigger: production environment not configured (faza 3 incomplete)
- Akcje: complete faza 3, use existing dev/staging only, defer

**EC-C4**: Concurrent project overload
- Trigger: operator has 8 active projects, system suggests max 5
- Akcje: complete others first, allow override z warning, dedicate resources

### Kategoria D — Customer-specific issues (3 cases)

**EC-D1**: Customer NIE w workspace
- Trigger: operator references new customer, no policy yet
- Akcje: create customer profile inline, defer until customer setup, use default policy

**EC-D2**: Customer policy conflict z project goals
- Trigger: customer requires sovereign EU only, project includes US-based service
- Akcje: redesign architecture, decline project, customer waiver

**EC-D3**: Customer credentials missing
- Trigger: project needs customer's API keys (not provided)
- Akcje: pause inception, request from customer, mock for development

### Kategoria E — Recovery / migration (3 cases)

**EC-E1**: Inception interrupted (crash)
- Trigger: AEIS crashed mid-inception
- Akcje: resume from last checkpoint, restart inception, verify partial state

**EC-E2**: Template database corruption
- Trigger: templates dla project not loadable
- Akcje: restore z backup, use defaults, recreate templates

**EC-E3**: Project ID collision
- Trigger: extremely rare — UUID collision
- Akcje: regenerate ID, log incident

---

## 16.8. Acceptance + transition do fazy 17

```bash
$ aeis-cli phase16-acceptance-test --project proj_customer_y_crm

[1/8] Project entity created                          ✓ PASS
[2/8] D-level classified                              ✓ PASS (D4)
[3/8] Templates assigned                              ✓ PASS (4 templates)
[4/8] Resources reserved                              ✓ PASS
[5/8] Pre-flight checks                               ✓ PASS
[6/8] Audit chain genesis entry                       ✓ PASS
[7/8] Project state: READY_FOR_GOAL_DEFINITION        ✓ PASS
[8/8] Inheritance from workspace setup                ✓ PASS

DoD: 8/8 ✓
Phase 16 ACCEPTED. Ready dla Phase 17 (Goal Definition).
```

**Transition trigger**: operator klika "Continue to Goal Definition" lub
auto-trigger po project creation (per autonomy preset).

---

# FAZA 17 — Goal Definition

> **Spis sekcji**:
> - 17.1 — Sense fazy + co goals znaczą dla projektu
> - 17.2 — Multi-level goals (project / phase / module)
> - 17.3 — SMART goals framework
> - 17.4 — Acceptance criteria definition
> - 17.5 — Success metrics
> - 17.6 — Stakeholder mapping (per project)
> - 17.7 — Edge cases (18) + transition do fazy 18

---

## 17.1. Sense fazy

### 17.1.1. Co operator robi w fazie 17

Operator dopiero wygenerował project entity (faza 16). Faza 17 to
**explicit articulation goals** — co dokładnie projekt ma osiągnąć.

```
┌──────────────────────────────────────────────────────────────┐
│  Goal Definition — co projekt ma osiągnąć                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z fazy 16):                                          │
│   • Project entity z initial classification                  │
│   • Operator's original idea description                      │
│   • Templates assigned                                       │
│                                                              │
│  PROCESSING (operator + AEIS):                               │
│   • Operator articuluje primary goals                        │
│   • Operator definiuje secondary goals                        │
│   • System sugeruje SMART formatting                         │
│   • Acceptance criteria established                          │
│   • Success metrics defined                                   │
│   • Stakeholder mapping                                       │
│                                                              │
│  OUTPUT (goals document):                                    │
│   • Primary goals (1-3)                                      │
│   • Secondary goals (3-7)                                     │
│   • Acceptance criteria                                       │
│   • Success metrics                                           │
│   • Stakeholders + their needs                                │
│   • Project state: READY_FOR_SCOPE_DEFINITION                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 17.1.2. Czemu goals są ważne

Goals są **podstawą wszystkich późniejszych decisions**:

```
Faza 17 goals → Faza 18 scope (decyduje co IN/OUT)
              → Faza 19 Council (decyduje kogo invite)
              → Faza 20-25 Council deliberation (debates pattern)
              → Faza 25 Księga (formal documentation)
              → Faza 28 Masterplan (build plan)
              → Faza 35 Build (implementation)
              → Faza 37 Quality gates (acceptance verification)
              → Faza 41 Closure (success measurement)
```

Goals napisane źle = whole project may go wrong direction.

### 17.1.3. Wynik fazy 17 (DoD)

```
✓ Primary goals defined (SMART format)
✓ Secondary goals defined
✓ Acceptance criteria explicit
✓ Success metrics measurable
✓ Stakeholders mapped
✓ Goals validated z templates (Council/test/deploy)
✓ Audit chain entry: goals_defined (signed)
✓ Project state: READY_FOR_SCOPE_DEFINITION
```

---

## 17.2. Multi-level goals

### 17.2.1. Three levels

Goals operują na 3 poziomach:

```
PROJECT-LEVEL goals
   ↓
PHASE-LEVEL goals (per phase 23-41)
   ↓
MODULE-LEVEL goals (per module w masterplanie)
```

W fazie 17 operator definiuje **project-level** goals. Phase i module
goals derivują się później.

### 17.2.2. Project-level goals struktura

```yaml
project_goals:
  primary_goals:
    - id: pg_1
      title: "Funkcjonalny CRM dla Customer Y"
      description: "System pozwala Customer Y zarządzać 50 klientami ich
                    kancelarii z modułem płatności"
      success_indicator: "Customer Y używa systemu w produkcji"
      priority: P0  # must-have
      estimated_value: high
      
    - id: pg_2
      title: "KSeF compliance dla Polish invoicing"
      description: "Wszystkie faktury generated i submitowane do KSeF"
      success_indicator: "0 KSeF rejection po test period"
      priority: P0
      estimated_value: high
      
    - id: pg_3
      title: "Stripe payment integration"
      description: "Klienci kancelarii mogą płacić online via Stripe"
      success_indicator: "Successful end-to-end payment test"
      priority: P0
      estimated_value: high
  
  secondary_goals:
    - id: sg_1
      title: "Multi-language UI (PL + EN)"
      priority: P1  # should-have
    
    - id: sg_2
      title: "Mobile-responsive design"
      priority: P1
    
    - id: sg_3
      title: "Customer-facing analytics dashboard"
      priority: P2  # nice-to-have
    
    - id: sg_4
      title: "Email notifications"
      priority: P1
    
    - id: sg_5
      title: "Custom branding (Customer Y colors/logo)"
      priority: P1
  
  non_goals:  # explicitly NOT in scope
    - "Mobile native apps (iOS/Android)"
    - "Multi-tenant architecture"
    - "Real-time collaboration features"
    - "AI-powered insights"
```

---

## 17.3. SMART goals framework

### 17.3.1. SMART formatting

System pomaga formattować goals w SMART format:

```
S — Specific (konkretne)
M — Measurable (mierzalne)
A — Achievable (osiągalne w kontekście budgetu/czasu)
R — Relevant (relewantne dla project)
T — Time-bound (z deadline)
```

### 17.3.2. SMART validation UI

```
┌──────────────────────────────────────────────────────────────┐
│  Goal SMART Validation                                       │
│                                                              │
│  Original: "System ma działać dobrze"                        │
│                                                              │
│  SMART analysis:                                             │
│   S - Specific:    ✗ "działać dobrze" jest vague             │
│   M - Measurable:  ✗ no metric defined                       │
│   A - Achievable:  ? cannot evaluate without specifics       │
│   R - Relevant:    ✓ relates do project                      │
│   T - Time-bound:  ✗ no deadline                             │
│                                                              │
│  Suggested rewrite:                                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  "Customer Y może wygenerować faktury KSeF dla 100%    │ │
│  │  swoich klientów w ≤30 sekund per faktura, z 0%        │ │
│  │  rejection rate od KSeF system, w terminie do          │ │
│  │  2026-06-30."                                          │ │
│  │                                                        │ │
│  │  S - Specific:    ✓ KSeF invoicing dla 100% klientów   │ │
│  │  M - Measurable:  ✓ ≤30s, 0% rejection                 │ │
│  │  A - Achievable:  ✓ KSeF API supports this             │ │
│  │  R - Relevant:    ✓ core project goal                  │ │
│  │  T - Time-bound:  ✓ 2026-06-30                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  [Accept rewrite]  [Edit manually]  [Skip SMART validation]  │
└──────────────────────────────────────────────────────────────┘
```

### 17.3.3. SMART warnings

```
Warnings dla non-SMART goals:

  Vague: "Better UX" → ask for specific metrics
  Unmeasurable: "Customer happy" → define satisfaction metric
  Unachievable: "10x performance in 1 day" → reality check
  Irrelevant: "Build mobile app" gdy project is web SaaS
  No deadline: "Eventually..." → set explicit timeframe
```

---

## 17.4. Acceptance criteria definition

### 17.4.1. Per goal acceptance criteria

```
┌──────────────────────────────────────────────────────────────┐
│  Acceptance Criteria — pg_2 KSeF compliance                  │
│                                                              │
│  Goal: "Wszystkie faktury generated i submitowane do KSeF"   │
│                                                              │
│  Acceptance criteria (must ALL be true dla goal achieved):   │
│                                                              │
│  ☑ AC-2.1: Invoice format compliance                         │
│      System generates FA(2) format invoices                  │
│      KSeF schema validation passes 100%                      │
│      Test: generate 100 sample invoices, all valid           │
│                                                              │
│  ☑ AC-2.2: Submission to KSeF                                │
│      System submits invoices do KSeF API                     │
│      Submission success rate ≥99%                            │
│      Test: submit 50 test invoices, ≥49 succeed              │
│                                                              │
│  ☑ AC-2.3: Signature/timestamp                               │
│      Invoices podpisane qualified signature                  │
│      Timestamp z trusted time source                          │
│      Test: verify signature na 10 sample invoices             │
│                                                              │
│  ☑ AC-2.4: Archive retention                                 │
│      Invoices archived for 5+ years per Polish law            │
│      Archive encryption at-rest                              │
│      Test: archive structure verification                    │
│                                                              │
│  ☑ AC-2.5: Error handling                                    │
│      KSeF API errors gracefully handled                      │
│      Operator notified about failed submissions              │
│      Test: simulate KSeF errors, verify recovery             │
│                                                              │
│  ☑ AC-2.6: Documentation                                     │
│      Customer Y documentation w PL                            │
│      Operator runbook                                        │
│      Test: documentation review                              │
│                                                              │
│  Goal achieved when: ALL 6 acceptance criteria met            │
│                                                              │
│  [Add more criteria]  [Save]                                 │
└──────────────────────────────────────────────────────────────┘
```

### 17.4.2. Acceptance criteria types

```
Functional AC:
  • Feature works as described
  • Edge cases handled
  • Error scenarios graceful
  
Performance AC:
  • Latency within bounds
  • Throughput meets target
  • Resource usage acceptable
  
Quality AC:
  • Test coverage above target
  • No critical security findings
  • Code complexity within limits
  
Compliance AC:
  • Regulatory requirements met
  • Audit trail complete
  • Documentation present
  
Operational AC:
  • Monitoring instrumented
  • Logging complete
  • Runbook documented
  
Customer-specific AC:
  • Customer-defined requirements
  • Customer training delivered
  • Customer sign-off obtained
```

---

## 17.5. Success metrics

### 17.5.1. Beyond acceptance criteria — long-term metrics

Acceptance criteria = "did we deliver?". Success metrics = "is it working?
months/years later".

```
┌──────────────────────────────────────────────────────────────┐
│  Success Metrics — Customer Y CRM                            │
│                                                              │
│  Short-term (first 30 dni po deployment):                    │
│   • Customer adoption: ≥10 employees actively use            │
│   • Invoice generation: ≥50 invoices/week                    │
│   • Bug reports: <5 critical issues                          │
│   • Customer satisfaction: ≥4/5                              │
│                                                              │
│  Mid-term (3 months):                                        │
│   • Customer renewal/extension                                │
│   • Feature requests addressed                                │
│   • System reliability: 99.5% uptime                         │
│   • Cost stability: within 10% of projected                  │
│                                                              │
│  Long-term (1 year):                                         │
│   • Customer Y becomes reference dla similar customers       │
│   • Pattern reusable dla future operator's projects          │
│   • Total ROI vs operator's time investment                  │
│                                                              │
│  Tracking:                                                   │
│   ☑ Customer-side metrics (anonymous telemetry)              │
│   ☑ Operator-side metrics (project closure report)           │
│   ☐ Customer satisfaction surveys (operator + customer setup)│
│                                                              │
│  Calibration data:                                           │
│   This project's metrics → improve future predictions        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 17.6. Stakeholder mapping

### 17.6.1. Per project stakeholders

```
┌──────────────────────────────────────────────────────────────┐
│  Stakeholders — Customer Y CRM                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PRIMARY STAKEHOLDERS                                        │
│                                                              │
│  Customer Y (decyduje + płaci):                              │
│   • Contact: Anna Kowalska (CTO Customer Y)                  │
│   • Decision authority: project scope, accept criteria        │
│   • Communication: weekly status, hard gate approvals        │
│   • Goals: efficient invoicing, GDPR compliance              │
│                                                              │
│  Operator (Robert):                                          │
│   • Decision authority: technical implementation, tools      │
│   • Hands-on: Council, builds, deployments                   │
│   • Goals: deliver on time + budget, learn patterns           │
│                                                              │
│  END USERS (Customer Y employees):                           │
│   • 10-50 employees (kancelaria staff)                       │
│   • Daily users of CRM + invoicing                           │
│   • Goals: easy to use, fast, in Polish                      │
│   • Voice: indirect (via Customer Y Anna)                    │
│                                                              │
│  CUSTOMER Y'S CLIENTS (indirect):                            │
│   • End consumers paying invoices                             │
│   • Use payment portal                                        │
│   • Goals: simple payment flow, security                      │
│                                                              │
│  REGULATORS (compliance authorities):                         │
│   • KSeF (Krajowy System e-Faktur)                           │
│   • UODO (GDPR enforcement)                                  │
│   • Goals: compliance ze regulations                         │
│                                                              │
│  Stakeholder needs matrix:                                   │
│  [Show needs vs goals coverage]                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 17.6.2. Stakeholder needs validation

```
System validates że all stakeholders' needs są reflected w goals:

  Customer Y needs:
   ✓ Efficient invoicing → pg_1 + pg_2
   ✓ GDPR compliance → covered by templates + Security Guard
   ⚠ Multi-user roles → not explicit w goals (gap?)
  
  End users needs:
   ✓ Easy to use → sg_2 (responsive design)
   ✓ Fast → covered by performance AC
   ⚠ Polish UI (mandatory for staff) → covered? sg_1 has PL+EN
  
  Customer Y's clients needs:
   ✓ Simple payment → pg_3 (Stripe)
   ⚠ Mobile payment → secondary (sg_2 mobile responsive)
  
  Recommendations:
   [Add explicit goal: multi-user roles]
   [Confirm Polish UI is primary (operator decision)]
```

---

## 17.7. Edge Cases — Goal Definition (18 cases)

### Kategoria A — SMART validation (4 cases)

**EC-A1**: Operator refuses SMART formatting
- "Just trust me, no need for measurable" → warning, audit log, accept

**EC-A2**: Goal too ambitious (not achievable)
- AEIS detects "10x performance in 1 day" → suggest reality check

**EC-A3**: Goals conflict z each other
- "Maximum quality" + "Minimum cost" + "Fast delivery" → trade-offs explicit

**EC-A4**: Multiple goals z same priority
- 5 goals all P0 → operator must prioritize, max 3 P0

### Kategoria B — Acceptance criteria gaps (4 cases)

**EC-B1**: Goal bez clear AC
- "Make it good" → cannot define AC, prompt for specifics

**EC-B2**: AC too detailed (over-specified)
- 50 criteria for one goal → suggest grouping, focus on essentials

**EC-B3**: AC unverifiable
- "Customer satisfied" → how measure? Add specific metric

**EC-B4**: AC missing dla critical goal
- P0 goal z 0 AC → require min 3 AC dla P0 goals

### Kategoria C — Stakeholder issues (4 cases)

**EC-C1**: Customer not available
- Cannot validate customer needs → stub stakeholder, validate later

**EC-C2**: Conflicting stakeholder needs
- Customer wants X, end users want Y → operator mediation, document

**EC-C3**: Hidden stakeholders missed
- Regulator overlooked (KSeF) → AEIS Compliance role catches w fazie 23

**EC-C4**: Stakeholder change mid-project
- New decision maker at customer → re-validation needed

### Kategoria D — Goal scope issues (3 cases)

**EC-D1**: Scope creep starts here
- Operator adds "and also...and also..." → redirect to scope phase 18

**EC-D2**: Goals not aligned z templates
- Goals require feature templates don't support → modify templates lub goals

**EC-D3**: Goals exceed budget
- Realistic cost dla goals > project budget → reduce scope or budget

### Kategoria E — Recovery (3 cases)

**EC-E1**: Goals lost (file corruption)
- Restore z backup or re-articulate

**EC-E2**: Operator changes mind (significant)
- Re-do faza 17, audit log shift, downstream re-validation

**EC-E3**: Customer disputes goals after agreement
- Negotiate, mediate, modify goals z customer sign-off

---

## 17.8. Acceptance + transition do fazy 18

```bash
$ aeis-cli phase17-acceptance-test --project proj_customer_y_crm

[1/7] Primary goals defined (1-3)                     ✓ PASS (3 goals)
[2/7] Secondary goals defined                          ✓ PASS (5 goals)
[3/7] Non-goals explicitly stated                      ✓ PASS
[4/7] Acceptance criteria per goal                     ✓ PASS (6 AC each P0)
[5/7] Success metrics defined                          ✓ PASS
[6/7] Stakeholders mapped                              ✓ PASS (5 groups)
[7/7] Audit chain entry goals_defined                  ✓ PASS

DoD: 7/7 ✓
Phase 17 ACCEPTED. Ready dla Phase 18 (Scope Definition).
```

---

# FAZA 18 — Scope Definition

> **Spis sekcji**:
> - 18.1 — Sense fazy + scope vs goals
> - 18.2 — In-scope / out-of-scope explicit listing
> - 18.3 — Constraints definition (technical, business, regulatory)
> - 18.4 — Risk identification (initial)
> - 18.5 — Scope vs budget reconciliation
> - 18.6 — Edge cases (15) + transition do fazy 19

---

## 18.1. Sense fazy

### 18.1.1. Scope vs Goals

```
GOALS (faza 17):  CO osiągniemy
SCOPE (faza 18):  CO konkretnie zbudujemy + CZEGO NIE

  Goal: "Functional CRM dla Customer Y"
  Scope:
    IN: customer management, invoice generation, payment integration
    OUT: marketing automation, social media integration, mobile app
```

Goals są **abstract intent**. Scope jest **concrete deliverables**.

### 18.1.2. Wynik fazy 18 (DoD)

```
✓ In-scope features explicit (numbered list)
✓ Out-of-scope features explicit (anti-scope)
✓ Technical constraints documented
✓ Business constraints documented  
✓ Regulatory constraints documented
✓ Initial risks identified
✓ Scope-budget reconciliation done
✓ Audit chain entry: scope_defined
✓ Project state: READY_FOR_COUNCIL_CONFIG
```

---

## 18.2. In-scope / out-of-scope

### 18.2.1. Scope artifact

```
┌──────────────────────────────────────────────────────────────┐
│  Scope Definition — Customer Y CRM                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  IN SCOPE (delivered w project)                              │
│                                                              │
│  Customer Management:                                        │
│   ✓ Add/edit/delete customer records                         │
│   ✓ Customer search/filter                                   │
│   ✓ Customer history (interactions, invoices)                │
│   ✓ Customer notes (internal)                                │
│   ✓ Bulk import customers (CSV)                              │
│   ✓ Customer export (GDPR Art. 15 compliance)                │
│                                                              │
│  Invoicing:                                                  │
│   ✓ Generate FA(2) format invoices                            │
│   ✓ KSeF submission                                          │
│   ✓ KSeF status tracking                                     │
│   ✓ Invoice templates customization                          │
│   ✓ Invoice PDF download                                     │
│   ✓ Invoice email to customer                                 │
│   ✓ Invoice archive (5+ years)                                │
│                                                              │
│  Payment Integration:                                        │
│   ✓ Stripe payment intent creation                           │
│   ✓ Payment links per invoice                                │
│   ✓ Payment status webhooks                                  │
│   ✓ Refund processing                                        │
│                                                              │
│  Authentication & Authorization:                             │
│   ✓ Email + password login                                    │
│   ✓ Password reset flow                                      │
│   ✓ Multi-user support (roles: admin, user)                  │
│   ✓ Audit log dla user actions                               │
│                                                              │
│  Internationalization:                                        │
│   ✓ Polish UI (primary)                                       │
│   ✓ English UI (secondary)                                   │
│   ✓ Currency formatting per locale (PLN, EUR)                │
│                                                              │
│  Operations:                                                 │
│   ✓ Customer-facing analytics dashboard                       │
│   ✓ Email notifications (invoice issued, paid)               │
│   ✓ System monitoring + alerting                             │
│   ✓ Daily backups                                             │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  OUT OF SCOPE (NOT delivered, may be future phases)          │
│                                                              │
│  Explicitly excluded:                                        │
│   ✗ Mobile native apps (iOS/Android)                          │
│   ✗ Real-time collaboration features                         │
│   ✗ AI-powered insights / recommendations                     │
│   ✗ Multi-tenant architecture (single-tenant only)           │
│   ✗ White-label / customer branding (only basic colors)      │
│   ✗ Multi-currency w single invoice (single currency only)   │
│   ✗ Subscription billing (only one-time invoices)             │
│   ✗ Marketing automation                                      │
│   ✗ Social media integration                                  │
│   ✗ Bulk email campaigns                                      │
│   ✗ Custom reporting builder (only built-in reports)         │
│   ✗ Third-party CRM integration (Salesforce, HubSpot)        │
│                                                              │
│  Out-of-scope reasoning logged dla future reference          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 18.2.2. Scope vs goal mapping

```
Scope items mapped do goals:

  Goal pg_1 "Functional CRM" → covers:
    Customer Management (all 6 items)
    Authentication (all 4 items)
  
  Goal pg_2 "KSeF compliance" → covers:
    Invoicing (all 7 items)
  
  Goal pg_3 "Stripe integration" → covers:
    Payment Integration (all 4 items)
  
  Secondary goals:
   sg_1 "Multi-language" → Internationalization (all 3 items)
   sg_4 "Email notifications" → Operations (email notifications)
   ...

Coverage check: ✓ all goals have scope items
Gap check: ✓ no scope items without goal mapping
```

---

## 18.3. Constraints definition

### 18.3.1. Three constraint categories

```
┌──────────────────────────────────────────────────────────────┐
│  Constraints — Customer Y CRM                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TECHNICAL CONSTRAINTS                                        │
│                                                              │
│   Technology stack:                                          │
│    • Backend: Python (operator's expertise)                  │
│    • Frontend: React + TypeScript                            │
│    • Database: PostgreSQL                                    │
│    • Cloud: Hetzner (Polish data center mandatory)           │
│                                                              │
│   Integrations:                                              │
│    • Stripe API (payment)                                     │
│    • KSeF API (invoicing)                                    │
│    • SendGrid (email)                                         │
│                                                              │
│   Performance:                                               │
│    • Page load: <2 sec                                       │
│    • API latency: P95 <500ms                                  │
│    • Concurrent users: 50                                    │
│                                                              │
│  BUSINESS CONSTRAINTS                                         │
│                                                              │
│   Budget:                                                    │
│    • Hard cap: $250 (operator)                                │
│    • Customer cap: €500                                      │
│                                                              │
│   Timeline:                                                  │
│    • Customer deadline: 2026-06-30                           │
│    • Soft milestones: design 2026-05-15, MVP 2026-06-15       │
│                                                              │
│   Resources:                                                 │
│    • Operator only (no team)                                  │
│    • Customer dostępny weekly (Wed 10:00)                    │
│                                                              │
│  REGULATORY CONSTRAINTS                                       │
│                                                              │
│   Compliance frameworks:                                      │
│    • GDPR (EU general)                                        │
│    • KSeF (Polish e-invoicing)                                │
│    • PCI DSS (payment card data)                              │
│                                                              │
│   Data residency:                                            │
│    • Customer data EU only (Polish data center preferred)    │
│    • No US-based services dla customer PII                    │
│                                                              │
│   Documentation:                                             │
│    • DPIA (Data Protection Impact Assessment)                │
│    • Privacy Policy w PL + EN                                │
│    • Terms of Service                                         │
│    • DPA z customer Y                                         │
│                                                              │
│   Audit:                                                     │
│    • 5-year invoice retention                                 │
│    • Audit chain integrity                                   │
│    • GDPR Art. 30 records                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 18.3.2. Constraint impact analysis

```
System analyzuje constraints i flaguje conflicts:

  Technical: Hetzner only
  Regulatory: EU data residency required
  → ✓ Compatible (Hetzner has EU data centers)
  
  Performance: 50 concurrent users
  Technical: Hetzner CX31
  → ✓ Sufficient capacity
  
  Budget: $250
  Scope: 28 in-scope features
  → ⚠ Tight — average $9 per feature
  → Reality check needed (z previous similar projects)
  
  Timeline: 2026-06-30 (8 weeks from now)
  Scope: 28 features + integrations
  → ⚠ Aggressive — typical 30+ features need 6-10 weeks
  → Recommend: prioritize, defer P2 features, MVP first
```

---

## 18.4. Initial risk identification

### 18.4.1. Risk register

```
┌──────────────────────────────────────────────────────────────┐
│  Risk Register — Customer Y CRM                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CRITICAL RISKS (must mitigate)                              │
│                                                              │
│  R1: KSeF API integration complexity                          │
│   Likelihood: Medium                                         │
│   Impact: High (blocks core feature)                         │
│   Mitigation:                                                │
│    • Test API w research phase                                │
│    • Have fallback (manual KSeF submission)                  │
│    • KSeF specialist w Council                                │
│                                                              │
│  R2: Stripe compliance dla Polish market                     │
│   Likelihood: Low (Stripe well-documented)                   │
│   Impact: High                                               │
│   Mitigation:                                                │
│    • Use Stripe's Polish-specific features                    │
│    • PCI DSS specialist w Council                             │
│                                                              │
│  HIGH RISKS                                                  │
│                                                              │
│  R3: Customer scope creep                                    │
│   Likelihood: High (customer-funded projects often)          │
│   Impact: Medium (cost overrun)                              │
│   Mitigation:                                                │
│    • Explicit out-of-scope list                               │
│    • Customer sign-off na scope                               │
│    • Change request process                                   │
│                                                              │
│  R4: Customer availability                                    │
│   Likelihood: Medium (busy schedule)                         │
│   Impact: Medium (delays)                                    │
│   Mitigation:                                                │
│    • Async approval flows (mobile companion)                 │
│    • Pre-approved decision frameworks                         │
│                                                              │
│  MEDIUM RISKS                                                │
│                                                              │
│  R5: Performance under load                                   │
│   Likelihood: Low (50 users not heavy)                       │
│   Impact: Medium                                              │
│   Mitigation: L4 performance tests pre-prod                  │
│                                                              │
│  R6: Multilanguage maintenance                                │
│   Likelihood: Medium                                          │
│   Impact: Low                                                 │
│   Mitigation: Coherence Guard cross-language checks           │
│                                                              │
│  LOW RISKS                                                   │
│                                                              │
│  R7: Email deliverability (SendGrid)                          │
│  R8: SSL certificate management                               │
│  R9: Backup restoration testing                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 18.4.2. Risk monitoring

```
Risk register linked do other AEIS systems:

  Risks dla Council deliberation (faza 23):
   Risk Assessor role addresses each risk
   Decisions documented per risk
  
  Risks dla Coherence Guard (faza 6):
   Custom checks dla risk areas
   Continuous monitoring
  
  Risks dla Quality Guard (faza 9):
   Test scenarios cover risk mitigations
  
  Risks dla Security Guard (faza 8):
   Active monitoring dla risk indicators
  
  Risks dla Cost Guard (faza 7):
   Budget alerts dla cost-impacting risks
  
  Risks dla Provenance (faza 10):
   Audit trail dla risk decisions
```

---

## 18.5. Scope vs budget reconciliation

### 18.5.1. Cost estimation refinement

```
┌──────────────────────────────────────────────────────────────┐
│  Scope-Budget Reconciliation                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Budget: $250 (effective cap)                                │
│                                                              │
│  Estimated cost based on scope:                              │
│   • 28 in-scope features                                     │
│   • Estimated avg cost per feature: $11                      │
│   • Subtotal: $308                                           │
│   • Council deliberation: $20                                │
│   • Quality gates: $35                                       │
│   • Deployment: $25                                          │
│   • Total estimated: $388                                    │
│                                                              │
│  ⚠ ESTIMATE EXCEEDS BUDGET BY $138 (55%)                     │
│                                                              │
│  Reconciliation options:                                      │
│                                                              │
│  Option A — Reduce scope                                     │
│   Defer P2 features:                                          │
│    • Customer-facing analytics dashboard                      │
│    • Custom reporting                                         │
│   Estimated savings: $30-50                                  │
│   Still over budget by ~$80                                  │
│                                                              │
│  Option B — Increase budget                                  │
│   Operator absorbs $80                                        │
│   OR: customer approves overrun                               │
│                                                              │
│  Option C — Reduce quality                                    │
│   Use lighter test strategy (skip L4 performance)             │
│   Use simpler deploy template                                │
│   Estimated savings: $40-70                                  │
│   Risk: lower quality dla customer                           │
│                                                              │
│  Option D — Combine A + B + C                                │
│   Reduce P2 scope (-$40)                                     │
│   Use Standard test instead of Comprehensive (-$30)          │
│   Operator absorbs $68                                        │
│                                                              │
│  Recommendation: Option D (balanced)                          │
│                                                              │
│  [Apply Option D]  [Choose other]  [Negotiate with customer] │
└──────────────────────────────────────────────────────────────┘
```

### 18.5.2. Customer approval (jeśli customer-funded)

```
ℹ Customer notification needed

  Project: Customer Y CRM
  Customer: Customer Y (€500 budget)
  Issue: Estimate $388 exceeds operator's hard cap $250
  
  Options dla Customer Y:
   [Operator absorbs overrun] → no customer impact
   [Customer approves additional €130 (~$140)]
       New cap: €640
       Per customer policy z faza 15
   [Reduce scope (operator suggests P2 cuts)]
       Customer approves reduced scope
   [Defer project (scope/budget reset)]
   
  Notification ready dla customer.
  [Send to customer]  [Defer]
```

---

## 18.6. Edge Cases — Scope Definition (15 cases)

### Kategoria A — Scope conflicts (4)

**EC-A1**: In-scope conflicts z out-of-scope
- e.g., "mobile responsive" IN, "mobile features" OUT — clarify

**EC-A2**: Scope item nie covered by goals
- Orphan scope item — add goal lub remove from scope

**EC-A3**: Goal nie covered by scope
- Goal without implementation plan — add scope items

**EC-A4**: Customer adds features mid-scope
- Document, treat as scope creep, negotiate

### Kategoria B — Constraints conflicts (4)

**EC-B1**: Technical vs business constraint conflict
- e.g., performance target requires more cloud resources than budget allows

**EC-B2**: Regulatory conflict z scope
- e.g., scope includes feature illegal w jurisdiction

**EC-B3**: Customer constraints conflict z operator policy
- e.g., customer wants US-hosted, operator policy EU-only

**EC-B4**: Constraint stale (changes during project)
- Regulation updated, technology deprecated — adjust scope

### Kategoria C — Risk issues (4)

**EC-C1**: Critical risk has no mitigation
- High likelihood + high impact + no plan — block proceed

**EC-C2**: Risk overlooked at this stage
- Found w faza 23 Council — re-do scope review

**EC-C3**: Risk materializes mid-project
- Activate mitigation, escalate, re-plan

**EC-C4**: Customer accepts risk operator wouldn't
- Customer signs risk waiver, audit log

### Kategoria D — Budget reconciliation (3)

**EC-D1**: Over budget z no acceptable cuts
- Escalate, negotiate, defer

**EC-D2**: Customer disputes estimate
- Detailed breakdown, calibration data, customer negotiation

**EC-D3**: Estimate too uncertain
- Phased delivery, milestone-based budgeting

---

## 18.7. Acceptance + transition do fazy 19

```bash
$ aeis-cli phase18-acceptance-test --project proj_customer_y_crm

[1/8] In-scope features explicit                       ✓ PASS (28 features)
[2/8] Out-of-scope explicit                            ✓ PASS (12 items)
[3/8] Constraints documented                           ✓ PASS (3 categories)
[4/8] Risks identified                                 ✓ PASS (9 risks)
[5/8] Risk mitigation plans                            ✓ PASS (all critical)
[6/8] Scope-budget reconciled                          ✓ PASS (Option D applied)
[7/8] Customer notified (if needed)                    ✓ PASS
[8/8] Audit chain entry scope_defined                  ✓ PASS

DoD: 8/8 ✓
Phase 18 ACCEPTED. Ready dla Phase 19 (Council Configuration).
```

---

# FAZA 19 — Initial Council Configuration

> **Spis sekcji**:
> - 19.1 — Sense fazy + final Council selection przed deliberation
> - 19.2 — Council customization per project
> - 19.3 — Knowledge bases attachment
> - 19.4 — Council briefing materials preparation
> - 19.5 — Council readiness check
> - 19.6 — Edge cases (15) + transition do fazy 20

---

## 19.1. Sens fazy

### 19.1.1. Final Council setup

W fazie 16 system wybrał Council template. Faza 19 to **final
customization** — operator może edytować Council konkretnie dla tego
projektu, dodać knowledge bases, briefing materials.

```
┌──────────────────────────────────────────────────────────────┐
│  Faza 19 vs poprzednie fazy Council                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Faza 4:  Default Council per goal (operator-wide)           │
│  Faza 12: Council templates library (operator-wide)          │
│  Faza 16: Council template assigned do project (auto)        │
│  Faza 19: Council customized DLA TEGO PROJEKTU (final)       │
│           ↓                                                  │
│  Faza 20: Council convening (start deliberation)             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 19.1.2. Wynik fazy 19 (DoD)

```
✓ Council finalized (roles, models, voting)
✓ Knowledge bases attached
✓ Briefing materials prepared
✓ Pre-council checks passed
✓ Operator approved Council readiness
✓ Audit chain entry: council_configured
✓ Project state: READY_FOR_COUNCIL_CONVENING
```

---

## 19.2. Council customization per project

### 19.2.1. Inherited Council z template

```
┌──────────────────────────────────────────────────────────────┐
│  Council — Customer Y CRM                                    │
│                                                              │
│  Inherited template: "Public SaaS z payment" (z faza 16)     │
│                                                              │
│  Roles (12 inherited):                                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ⠿  Council Chair          claude-opus     1.0  [Edit] │ │
│  │  ⠿  Planner                claude-sonnet   1.0  [Edit] │ │
│  │  ⠿  Critic                 gpt-5           1.5  [Edit] │ │
│  │  ⠿  Security               claude-opus     1.0  [Edit] │ │
│  │  ⠿  Payment Specialist     claude-opus     1.0  [Edit] │ │
│  │  ⠿  UX Designer            claude-sonnet   0.8  [Edit] │ │
│  │  ⠿  Compliance (GDPR)      bielik-11b      1.0  [Edit] │ │
│  │  ⠿  Compliance (PCI)       gpt-5           1.0  [Edit] │ │
│  │  ⠿  QA Lead                gpt-5           0.8  [Edit] │ │
│  │  ⠿  i18n Specialist        claude-sonnet   0.5  [Edit] │ │
│  │  ⠿  Risk Assessor          claude-opus     1.0  [Edit] │ │
│  │  ⠿  Compliance (KSeF)      bielik-11b      1.0  [Edit] │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Project-specific customizations:                            │
│   ☑ Add KSeF Compliance role (Polish-specific, not in tpl)   │
│   ☑ Pin Bielik dla all Polish-language tasks                  │
│   ☐ Remove role (operator decides)                            │
│   [+ Add custom role for this project]                       │
│                                                              │
│  Voting:                                                     │
│   Threshold: Supermajority 66% (z template, no change)       │
│   Quorum:    8 of 12 minimum                                 │
│   Critic veto: ✓                                             │
│   Specialist override: ✓                                     │
│                                                              │
│  Estimated:                                                  │
│   Cost per round: $3.20                                      │
│   Total cost (3 rounds): $9.60                               │
│   Time per round: 5-8 min                                    │
│                                                              │
│  [Save customization]  [Reset to template]                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 19.3. Knowledge bases attachment

### 19.3.1. Knowledge bases dla Council

Each Council role może mieć dedicated knowledge base — Council member uses
RAG do retrieve relevant info during deliberation.

```
┌──────────────────────────────────────────────────────────────┐
│  Knowledge Bases — Customer Y CRM Council                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per-role knowledge bases:                                   │
│                                                              │
│  Compliance (GDPR):                                          │
│   ☑ EU GDPR full text (2016 directive)                       │
│   ☑ EDPB guidelines (latest)                                 │
│   ☑ Polish UODO guidelines                                   │
│   ☑ Operator's previous GDPR docs                             │
│   ☐ Customer Y's privacy policy (operator provides)          │
│                                                              │
│  Compliance (PCI):                                           │
│   ☑ PCI DSS v4.0 standard                                    │
│   ☑ Stripe PCI compliance docs                                │
│   ☑ Polish payment regulations                                │
│                                                              │
│  Compliance (KSeF):                                          │
│   ☑ KSeF technical specifications                            │
│   ☑ FA(2) format spec                                         │
│   ☑ KSeF API documentation                                    │
│   ☑ Polish e-invoicing law                                   │
│                                                              │
│  Payment Specialist:                                          │
│   ☑ Stripe API docs (current)                                │
│   ☑ Stripe best practices                                     │
│   ☑ Polish payment market specifics                           │
│                                                              │
│  Security:                                                   │
│   ☑ OWASP Top 10                                             │
│   ☑ NIST cybersecurity framework                              │
│   ☑ Operator's security playbook                              │
│                                                              │
│  UX Designer:                                                │
│   ☑ Polish UX best practices                                  │
│   ☑ B2B SaaS design patterns                                  │
│   ☑ WCAG 2.1 accessibility                                    │
│   ☐ Customer Y branding guidelines (operator uploads)        │
│                                                              │
│  Project-specific (operator uploads):                         │
│   [+ Upload customer requirements doc]                       │
│   [+ Upload customer brand guidelines]                       │
│   [+ Upload similar reference projects (operator's archives)]│
│                                                              │
│  Cost dla loading knowledge bases:                            │
│   Per Council session: ~$0.50 (RAG retrieval)                │
│   First time embedding: ~$5 (one-time)                       │
│                                                              │
│  [Confirm knowledge bases]  [Customize per role]             │
└──────────────────────────────────────────────────────────────┘
```

---

## 19.4. Council briefing materials

### 19.4.1. Briefing package dla Council

Przed deliberation, Council otrzymuje **briefing package** — context
materials Council reads before discussion:

```
Council Briefing Package — Customer Y CRM

Documents:
  1. Project description (z faza 16)
     • Operator's idea
     • D-level: D4
     • Templates assigned

  2. Goals document (z faza 17)
     • 3 primary goals + 5 secondary
     • Acceptance criteria per goal
     • Stakeholders mapped

  3. Scope document (z faza 18)
     • In-scope (28 items)
     • Out-of-scope (12 items)
     • Constraints (technical/business/regulatory)
     • Risk register (9 risks)
     • Budget reconciliation result

  4. Customer context
     • Customer Y profile
     • Customer policy (z faza 15)
     • Customer history (jeśli previous projects)

  5. Technical context
     • Available environments (z faza 3)
     • Available providers (z faza 2)
     • Operator's tech preferences

  6. Operator preferences (z fazy 1, 4)
     • Autonomy preset: Production
     • Test strategy: Comprehensive
     • Deployment: Canary

Format: structured JSON + markdown summaries
Cost dla Council to ingest: ~$1 (one-time per project)
```

### 19.4.2. Operator can add custom briefing

```
┌──────────────────────────────────────────────────────────────┐
│  Add Custom Briefing Materials                               │
│                                                              │
│  Optional materials operator wants Council do consider:      │
│                                                              │
│  ☑ Operator's notes:                                         │
│     [_____________________________________________________]  │
│     [_____________________________________________________]  │
│                                                              │
│  ☑ Reference materials:                                      │
│     ☑ Similar project: Sylion Tailor v3 (Council Book)       │
│     ☐ External article: ...                                  │
│     ☐ Customer interview notes                                │
│     ☐ Competitor analysis                                    │
│                                                              │
│  ☑ Hot topics dla Council to address:                        │
│     1. KSeF API rate limits (operator concerned)              │
│     2. Customer's existing tech stack (legacy ERP)            │
│     3. Polish accessibility WCAG dla gov-funded customer      │
│                                                              │
│  ☑ Off-limits topics (operator preference):                   │
│     1. Don't suggest mobile apps (out of scope)               │
│     2. Don't suggest microservices (overkill dla scale)       │
│                                                              │
│  [Save briefing additions]                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 19.5. Council readiness check

### 19.5.1. Pre-convening checks

```
┌──────────────────────────────────────────────────────────────┐
│  Council Readiness Check                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Setup:                                                      │
│   ✓ All 12 roles assigned models                              │
│   ✓ Voting rules configured                                   │
│   ✓ Speaking order set                                        │
│                                                              │
│  Models availability:                                        │
│   ✓ claude-opus available (4 roles use)                       │
│   ✓ claude-sonnet available (3 roles use)                     │
│   ✓ gpt-5 available (3 roles use)                             │
│   ✓ bielik-11b available (lokalne, 2 roles)                   │
│   ⠋ Health check: all providers HEALTHY                       │
│                                                              │
│  Knowledge bases:                                            │
│   ✓ All required KBs loaded                                   │
│   ✓ Embeddings up-to-date                                     │
│   ✓ RAG retrieval tested                                      │
│                                                              │
│  Budget:                                                     │
│   ✓ Estimated cost ($9.60) within reserved budget            │
│   ✓ Cost Guard active                                         │
│                                                              │
│  Briefing:                                                   │
│   ✓ All briefing docs prepared                                │
│   ✓ Operator's custom additions saved                         │
│   ✓ Format validated                                         │
│                                                              │
│  Hard gates:                                                 │
│   ✓ Council finalization hard gate enabled (D4)               │
│   ✓ Operator notification configured                         │
│                                                              │
│  Audit:                                                      │
│   ✓ Provenance Guard ready                                   │
│   ✓ Audit chain entry will be created                        │
│                                                              │
│  All checks passed. Council ready dla deliberation.          │
│                                                              │
│  [Proceed to Phase 20 (Council Convening)]                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 19.6. Edge Cases — Council Configuration (15 cases)

### Kategoria A — Council customization (4)

**EC-A1**: Removed mandatory role
- e.g., remove Security from D4 project — block, force re-add

**EC-A2**: Added too many roles
- e.g., 18 roles dla simple project — warn cost overhead

**EC-A3**: Model assignment incompatible
- e.g., assigned model nie obsługuje long context dla complex role

**EC-A4**: Voting rules dla 12 roles too strict
- 100% unanimity dla 12 roles — likely deadlock, warn

### Kategoria B — Knowledge bases (4)

**EC-B1**: KB nie dostępne
- Required KB (e.g., KSeF spec) nie zaindeksowane

**EC-B2**: KB outdated
- GDPR docs z 2020 — load latest

**EC-B3**: Custom KB upload too large
- Operator uploads 500 MB doc — chunk, embed gradually

**EC-B4**: KB conflict (sprzeczne info)
- Two KBs say different things — Council notified, operator decides

### Kategoria C — Briefing issues (3)

**EC-C1**: Briefing too long
- Tokens exceed Council context window — summarize

**EC-C2**: Briefing missing critical info
- Operator forgot do add customer requirements doc

**EC-C3**: Off-limits topics still raised
- Council brings up "mobile app" mimo off-limits — instruction reinforcement

### Kategoria D — Recovery (4)

**EC-D1**: Provider down right before convening
- Switch to fallback model dla affected roles

**EC-D2**: Budget exhausted before Council starts
- Re-budget or defer Council

**EC-D3**: Operator changes mind o Council composition
- Re-do faza 19, may need to redo briefing

**EC-D4**: Council config corrupted
- Restore z template defaults

---

## 19.7. Acceptance + transition do fazy 20

```bash
$ aeis-cli phase19-acceptance-test --project proj_customer_y_crm

[1/7] Council finalized (12 roles)                     ✓ PASS
[2/7] Models assigned + available                      ✓ PASS
[3/7] Knowledge bases loaded                           ✓ PASS (8 KBs)
[4/7] Briefing materials ready                         ✓ PASS
[5/7] Pre-convening checks passed                      ✓ PASS
[6/7] Operator approved readiness                      ✓ PASS
[7/7] Audit chain entry council_configured             ✓ PASS

DoD: 7/7 ✓
Phase 19 ACCEPTED. Ready dla Phase 20 (Council Convening).

═══ GROUP B (Project Start) COMPLETE ═══
Ready dla Phase 20 (Council Deliberation start, Group C).
```

---

# Status faz 16-19

🟢 **Wszystkie 4 fazy complete**

**Zawiera**:
- ✓ Faza 16 — Project Inception (3 ścieżki tworzenia, D-level prediction, workspace allocation, project shell, 18 edge cases)
- ✓ Faza 17 — Goal Definition (multi-level goals, SMART validation, acceptance criteria, success metrics, stakeholder mapping, 18 edge cases)
- ✓ Faza 18 — Scope Definition (in/out scope explicit, 3 constraint categories, risk register, scope-budget reconciliation, 15 edge cases)
- ✓ Faza 19 — Council Configuration (final customization, knowledge bases, briefing materials, readiness check, 15 edge cases)

**Total edge cases w pliku**: 66 (18+18+15+15)

**Grupa B (Start projektu) COMPLETE**: 4 fazy
**Łącznie 19 z 41 faz frozen**

⏳ **Po Twojej akceptacji** → **soft freeze faz 16-19** + przejście do **Faza 20 — Council Convening** (start grupy C "Deliberacja → Księga").

⚠ **Następna grupa C jest sercem AEIS lifecycle**: 6 faz Council
deliberation (20-25). To gdzie magia się dzieje — multi-role AI debate
prowadzi do projektu's Księga (formal documentation). Estymuję 150-200KB
dla całej grupy C w jednym pliku.
