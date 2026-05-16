# FAZA 4 — Workspace Defaults

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (4 z 11)
> **Typ**: jednorazowa (z opcją powrotu po doświadczeniu z projektami)
> **Czas wykonania**: 5-10 min (smart defaults accept) / 30-60 min (full customization)
> **D-level**: D1 — settings, brak operacji finansowych w trakcie fazy
> **Zależności**: Faza 1 (workspace + goals); Fazy 2-3 zalecane (providers + środowiska dla pełnego kontekstu)
> **Następnik**: Faza 5 (Autonomy Configuration)
>
> **Spis sekcji**:
> - 4.1 — Sense fazy i smart defaults philosophy
> - 4.2 — Wizard krok-po-kroku z advisor
> - 4.3 — Default budgets per projekt (templates + cost estimation z Księgi)
> - 4.4 — Default autonomy preset (5 presetów + goal-driven)
> - 4.5 — Notification matrix + mobile companion app
> - 4.6 — Default cleanup periods per environment type
> - 4.7 — UI customization (full power-user level)
> - 4.8 — Shortcuts (predefined + custom + adaptive learning)
> - 4.9 — Workspace navigation (favorites + recent + groups)
> - 4.10 — Approval workflow + escalation (autonomy-driven timeouts)
> - 4.11 — Default test strategy (minimal + mandatory human-like UI testing)
> - 4.12 — Default Council templates (per-goal sets)
> - 4.13 — Edge cases (25 cases) + inheritance + DoD

---

## 4.1. Sense fazy i smart defaults philosophy

### 4.1.1. Po co faza 4

Po fazach 1-3 operator ma:
- ✓ Workspace skonfigurowany (faza 1)
- ✓ Providery LLM dostępne (faza 2)
- ✓ Środowiska deploy gotowe (faza 3)

Co operator **nie ma**: zdefiniowanych **default behaviors** dla nowych
projektów. Bez fazy 4 każdy nowy projekt wymagałby od operatora ustanowienia
budgetów, autonomy, notifications, cleanup, test strategy, Council
templates — **za każdym razem od zera**.

Faza 4 ustanawia **defaults** które nowe projekty dziedziczą. Operator może
zawsze override per projekt (faza 17), ale nie musi za każdym razem
zaczynać od zera.

### 4.1.2. Smart defaults philosophy (P4.1=c)

Faza 4 NIE wymaga że operator ustanawia każdy setting ręcznie. Zamiast
tego, system **proponuje smart defaults** based on:

```
Sources for smart defaults:
  ├── Goals z fazy 1 (public_products / cybersecurity / research / ...)
  ├── Providery dostępne z fazy 2 (mix lokalne/API)
  ├── Środowiska z fazy 3 (cloud/local/edge mix)
  ├── Operator role z fazy 1 (Solo / Team Lead / Klient)
  ├── Hardware capabilities (GPU, RAM)
  └── Industry best practices (SYLION operator profile)
```

System pre-fills wartości, operator widzi **dlaczego** każda wartość była
wybrana, akceptuje lub modyfikuje:

```
┌──────────────────────────────────────────────────────────────┐
│  Default Budget per Project                                  │
│                                                              │
│  Suggested: $50/project                                      │
│                                                              │
│  Why this value:                                             │
│   • Goal "public_products" → typical SaaS spend $30-100/proj │
│   • You have premium API providers (Claude, GPT-5)          │
│   • Hardware capable of significant local offload (RTX 4090) │
│   • Operator profile: solo (lower scale than teams)          │
│   • Industry typical for SYLION operators: $40-60            │
│                                                              │
│  [Accept $50]  [Customize]  [Use template ▼]                 │
└──────────────────────────────────────────────────────────────┘
```

### 4.1.3. Operator's role in faza 4

Faza 4 jest **konwersacyjna** — system proponuje, operator decyduje:

```
System: "Based on your goals, I suggest these defaults..."
Operator: "Accept" / "Customize" / "Tell me more"
```

Operator może też **pominąć** completely i polegać na pure system defaults
(generic, mniej dostosowane). Ale rekomendowana ścieżka to **30-60 min
customization** (P4.3=c).

### 4.1.4. Wynik fazy (DoD)

Po fazie 4, operator ma:

**Minimum (P4.3 minimum path)**:
- ✓ Default budget zatwierdzone (jakaś wartość, nawet domyślna)
- ✓ Default notification settings funkcjonują
- ✓ Default cleanup defaults established
- ✓ System ready do create new projects bez dodatkowych config

**Pełne (P4.3=c full path)**:
- ✓ Budget templates per project size
- ✓ Autonomy preset selected
- ✓ Notification matrix customized + mobile app paired
- ✓ Cleanup policies per environment type
- ✓ UI customizations applied
- ✓ Shortcuts configured
- ✓ Approval workflows zdefiniowane
- ✓ Test strategy default + human-like testing enabled
- ✓ Council templates per-goal selected

---

## 4.2. Wizard krok-po-kroku z advisor (P4.2 = b krok po kroku + advisor)

### 4.2.1. Wizard struktura

Faza 4 prowadzi operatora przez 9 kroków, każdy z embedded **AEIS Advisor**
który daje kontekst i rekomendacje.

```
┌─────────────────────────────────────────────────────────┐
│  Krok 1/9 — Welcome do Phase 4                          │
│  Krok 2/9 — Default Budgets per Project                 │
│  Krok 3/9 — Default Autonomy Preset                     │
│  Krok 4/9 — Notification Matrix + Mobile App            │
│  Krok 5/9 — Default Cleanup Periods                     │
│  Krok 6/9 — UI Customization                            │
│  Krok 7/9 — Shortcuts & Navigation                      │
│  Krok 8/9 — Approval & Escalation                       │
│  Krok 9/9 — Test Strategy + Council Defaults            │
└─────────────────────────────────────────────────────────┘
```

Operator może w każdej chwili:
- **[Skip step]** — używa system defaults dla tego stepu
- **[Save and continue]** — saves to step
- **[Save and exit]** — pause faza 4, wraca później
- **[Restart wizard]** — od nowa

### 4.2.2. AEIS Advisor pattern

Każdy krok ma **embedded advisor** w prawym pane:

```
┌─────────────────────────────────────────────────────────────┐
│  KROK 2/9 — Default Budgets             ✕ Hide advisor      │
├─────────────────────────────────────────────┬───────────────┤
│                                             │               │
│  Budget templates:                          │  💡 ADVISOR    │
│                                             │               │
│  ┌─ SMALL ────────────────────────┐        │  Why budgets   │
│  │ Budget cap: $20                │        │  matter:        │
│  │ For: D1-D2 projects, prototypes│        │                 │
│  │ Auto-applied when: D-level<=2  │        │  • Cost shocks  │
│  └────────────────────────────────┘        │    can stop     │
│                                             │    progress     │
│  ┌─ MEDIUM ───────────────────────┐        │                 │
│  │ Budget cap: $80                │        │  • Without caps,│
│  │ For: D3 projects, real apps    │        │    operator     │
│  │ Auto-applied when: D-level=3   │        │    surprised by │
│  └────────────────────────────────┘        │    bills        │
│                                             │                 │
│  ┌─ LARGE ────────────────────────┐        │  • SYLION-style │
│  │ Budget cap: $250               │        │    operators    │
│  │ For: D4-D5, customer-facing    │        │    spend $40-200│
│  │ Auto-applied when: D-level>=4  │        │    per project  │
│  └────────────────────────────────┘        │                 │
│                                             │  • Cost auto-   │
│  ┌─ ENTERPRISE ───────────────────┐        │    estimation   │
│  │ Budget cap: $1,000             │        │    z Księgi/    │
│  │ For: critical, government      │        │    masterplanu  │
│  │ Auto-applied when: critical=Y  │        │    może zmienić │
│  └────────────────────────────────┘        │    template per │
│                                             │    project      │
│  + Add custom template                      │                 │
│                                             │  Recommended    │
│  Cost estimation z Księgi:                  │  for you:       │
│   ☑ Enable auto-estimate per projekt        │   Use 4-tier    │
│      System sczyta Księgę + masterplan      │   template      │
│      i powie czy budget template wystarczy  │   approach      │
│                                             │                 │
│  [Skip]  [Save defaults]  [Continue]       │  [Why?]         │
└─────────────────────────────────────────────┴───────────────┘
```

### 4.2.3. Advisor depth modes

Operator może wybrać jak głęboki ma być advisor:

```
Settings → Wizard Behavior

  Advisor depth:
   [● Standard (recommendations + brief why)]
   [○ Verbose (recommendations + deep why + alternatives)]
   [○ Minimal (recommendations only, no why)]
   [○ Off (skip advisor, just settings)]
  
  Show advisor:
   [● Always visible (right pane)]
   [○ Collapsible (operator opens on demand)]
   [○ Modal (only when stuck)]
  
  Personalization:
   ☑ Use my goals to tailor recommendations
   ☑ Use my hardware capabilities
   ☑ Use my role profile
   ☐ Compare to anonymized SYLION operator stats
```

### 4.2.4. Wizard navigation

```
─────────────────────────────────────────────────────────────
  ◀ Krok 2/9                                  Krok 4/9 ▶
   Default Budgets               Notifications + Mobile

  [Save & previous]              [Save & next]
  [Save & exit wizard]           [Save & jump to step ▼]
─────────────────────────────────────────────────────────────
```

---

## 4.3. Default budgets per projekt (P4.4=d templates + cost estimation z Księgi)

### 4.3.1. Budget templates concept

Operator definiuje **templates** które nowe projekty dziedziczą based on
characteristics. Templates są **zmienialne per projekt** (faza 17).

**4 default templates** (operator może dodać więcej):

```yaml
budget_templates:
  small:
    cap_usd: 20
    auto_apply_when:
      d_level_max: 2
      project_type: [prototype, internal_tool, research]
    description: "Quick prototypes, internal tools, research experiments"
    typical_breakdown:
      llm_calls: 60%
      cloud_resources: 30%
      buffer: 10%
  
  medium:
    cap_usd: 80
    auto_apply_when:
      d_level: 3
      project_type: [internal_app, small_saas]
    description: "Real apps, internal SaaS, customer demos"
    typical_breakdown:
      llm_calls: 50%
      cloud_resources: 35%
      buffer: 15%
  
  large:
    cap_usd: 250
    auto_apply_when:
      d_level_min: 4
      project_type: [customer_facing_saas, payment_required]
    description: "Public products, customer-facing apps z real money"
    typical_breakdown:
      llm_calls: 40%
      cloud_resources: 45%
      buffer: 15%
  
  enterprise:
    cap_usd: 1000
    auto_apply_when:
      d_level: 5
      project_type: [critical_infrastructure, government, financial]
    description: "Government, financial, critical national infrastructure"
    typical_breakdown:
      llm_calls: 30%
      cloud_resources: 50%
      compliance_audit: 10%
      buffer: 10%
```

### 4.3.2. Cost estimation z Księgi (KEY FEATURE)

System może **auto-estimate** czy budget template wystarczy dla konkretnego
projektu, bazując na **Księdze i masterplanie wdrożeniowym**.

Workflow (uruchamia się w fazie 25 po Księga finalizacji + faza 28 po
masterplan):

```
┌──────────────────────────────────────────────────────────────┐
│  📊  Cost Estimation Report — Sylion Tailor                  │
│                                                              │
│  Source documents analyzed:                                  │
│   ✓ Księga: 47 pages, 15 sections, 8 acceptance criteria    │
│   ✓ Masterplan: 12 phases, 47 modules                       │
│   ✓ Test plan: 87 tests across L1-L4                        │
│                                                              │
│  Auto-detected project characteristics:                      │
│   • D-level:                D4 (customer-facing + payment)   │
│   • Suggested template:     LARGE ($250 cap)                 │
│   • Estimated complexity:   medium-high                      │
│   • Council depth needed:   3 rounds, 8 roles                │
│   • Build phases:           ~25 hours equivalent             │
│                                                              │
│  Estimated cost breakdown:                                   │
│                                                              │
│   ┌─ COUNCIL DELIBERATION ─────────────────────────────┐    │
│   │  Round 1 (parallel verdicts):       $4.20          │    │
│   │  Round 2 (discussion):              $5.80          │    │
│   │  Round 3 (consolidation):           $3.40          │    │
│   │  Critic signature:                  $1.20          │    │
│   │  Subtotal:                          $14.60         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─ PLANNING + MASTERPLAN ───────────────────────────┐     │
│   │  Model selection rounds 1-3:        $2.10          │    │
│   │  Skill synthesis 1-3:               $1.80          │    │
│   │  Masterplan synthesis:              $4.20          │    │
│   │  Test plan synthesis:               $2.80          │    │
│   │  Pre-flight + dry run:              $3.50          │    │
│   │  Subtotal:                          $14.40         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─ BUILD ORCHESTRATION ─────────────────────────────┐     │
│   │  Frontend builders:                 $35.20         │    │
│   │  Backend builders:                  $42.80         │    │
│   │  Stripe integration:                $8.40          │    │
│   │  i18n PL/EN/DE:                     $12.10         │    │
│   │  Test writing:                      $18.60         │    │
│   │  Mid-build interventions (est. 3):  $4.50          │    │
│   │  Subtotal:                          $121.60        │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─ QUALITY GATES + REPAIR ──────────────────────────┐     │
│   │  L1-L4 test runs:                   $8.20          │    │
│   │  Auto-repair iterations (est. 5):   $14.20         │    │
│   │  External review (mock):            $6.40          │    │
│   │  Subtotal:                          $28.80         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─ DEPLOYMENT ──────────────────────────────────────┐     │
│   │  Pre-deploy validation:             $2.40          │    │
│   │  Deploy execution:                  $3.20          │    │
│   │  Post-deploy verification:          $1.80          │    │
│   │  Cloud resources first month:       $42.00         │    │
│   │  Subtotal:                          $49.40         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ┌─ HUMAN-LIKE TESTING (mandatory) ──────────────────┐     │
│   │  Browser automation runs:           $8.40          │    │
│   │  UI scenario tests (15-20):         $12.40         │    │
│   │  Bug detection + fix iterations:    $6.20          │    │
│   │  Subtotal:                          $27.00         │    │
│   └────────────────────────────────────────────────────┘    │
│                                                              │
│   ───────────────────────────────────────────────────       │
│   TOTAL ESTIMATED:                      $255.80              │
│   Buffer (10%):                         $25.58               │
│   ───────────────────────────────────────────────────       │
│   RECOMMENDED BUDGET:                   $282                 │
│                                                              │
│  ⚠ Template "LARGE" ($250) jest za małe                       │
│                                                              │
│  Recommendations:                                            │
│   [● Use $282 for this project (one-time override)]          │
│   [○ Upgrade do template "ENTERPRISE" ($1000)]               │
│   [○ Reduce scope (system suggests cuts):                    │
│        - Skip dry-run (-$3.50)                               │
│        - Reduce mid-build interventions (-$4.50)             │
│        - Use cheaper models for build (-$25)                 │
│        - Total savings: $33 → fits $250 cap]                 │
│   [○ Accept template, proceed (warning: may exceed)]         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.3.3. Cost estimation accuracy

System uczy się z każdego projektu:

```
Settings → Cost Estimation → Calibration

  Calibration data:
   • 47 projects completed (post-build)
   • Average estimate accuracy: 87% (range 65-110%)
   • Tendency: +12% under-estimate (system zwykle za optymistyczny)
  
  Auto-adjustment:
   ☑ Apply +12% buffer to estimates (auto-calibrated)
   ☑ Per-D-level calibration:
        D1-D2: -3% over-estimate (system precise)
        D3:    +8% under
        D4:    +18% under
        D5:    +25% under (complex projects, uncertainty)
   ☐ Per-goal calibration (jeszcze nie wystarczająco data)
  
  Estimation factors (operator może dostroić):
   Base call cost weight:     [1.0]
   Repair iterations weight:  [1.5] ← typically more than estimated
   Mid-build interventions:   [1.3]
   Buffer percentage:         [10%]
  
  [View detailed calibration data]  [Reset calibration]
```

### 4.3.4. Custom budget templates

Operator może budować własne templates:

```
┌──────────────────────────────────────────────────────────────┐
│  Custom Budget Template                                      │
│                                                              │
│  Template name:    [ Customer pilot                ]         │
│  Cap (USD):        [ 150                           ]         │
│  Description:      [ For 1-month customer pilot           ] │
│                    [ projects with limited scope          ]  │
│                                                              │
│  Auto-apply when (rules):                                    │
│   ☑ Project type: [pilot ▼]                                  │
│   ☑ Goal includes: [customer_demo ▼]                         │
│   ☐ D-level range: [2 to 3 ▼]                                │
│   ☑ Tag includes: [pilot ▼]                                  │
│                                                              │
│  Cost breakdown structure:                                    │
│   LLM calls:           [40%] ← will warn jeśli przekroczone  │
│   Cloud resources:     [40%]                                 │
│   Customer-specific:   [10%] ← np. domain, custom DNS        │
│   Buffer:              [10%]                                 │
│                                                              │
│  Behavior at thresholds:                                      │
│   At 50% spent:    [Notify only ▼]                           │
│   At 80% spent:    [Email + slack ▼]                         │
│   At 95% spent:    [Pause + require approval ▼]              │
│   At 100% spent:   [Hard stop ▼]                             │
│                                                              │
│  [Cancel]  [Save template]                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.4. Default autonomy preset (P4.5=d goal-driven)

### 4.4.1. Goal-driven preset selection

Operator wybrał **goal-driven defaults**. System wybiera preset based on
project goals at creation time, ale wszystkie 5 presetów są zdefiniowane
w fazie 4 jako reference.

**5 presetów** (operator może edytować + tworzyć custom w fazie 5):

```yaml
autonomy_presets:
  conservative:
    name: "Conservative"
    description: "Operator approves everything, slow but safe"
    suggested_for: [security_critical, government, financial]
    dimensions_default: L0  # Wszystkie 10 wymiarów = L0 (manual)
  
  balanced:
    name: "Balanced"
    description: "Standard mode — system handles routine, operator handles risky"
    suggested_for: [public_products, apps_internal]
    dimensions_default: L2  # Wszystkie wymiary = L2
  
  aggressive:
    name: "Aggressive"
    description: "System auto-handles wherever possible"
    suggested_for: [research, prototypes, internal_experiments]
    dimensions_default: L4  # Wszystkie wymiary = L4
  
  research:  # NEW — additional preset
    name: "Research"
    description: "Aggressive on cost decisions, conservative on quality"
    suggested_for: [research, ml_experiments]
    dimensions_overrides:
      cost_decisions: L5      # Aggressive (research może wymagać experiments)
      model_selection: L5     # Try anything
      quality_verdicts: L1    # Manual review (research integrity)
      deploy_authorization: L0  # Manual (research nie wymaga deploy)
  
  production:  # NEW — additional preset
    name: "Production"
    description: "Balanced + extra strict on production-related decisions"
    suggested_for: [public_products, customer_facing]
    dimensions_overrides:
      deploy_authorization: L0  # Always manual
      security_decisions: L0    # Always manual
      cost_decisions: L1        # Notify (don't auto)
      cascade_re_evaluation: L0 # Manual review po incidents
```

### 4.4.2. Goal → preset mapping

```
┌──────────────────────────────────────────────────────────────┐
│  Default Autonomy per Goal (auto-applied at project create)  │
│                                                              │
│  Operator goals (z fazy 1):  public_products + cybersecurity │
│                                                              │
│  Auto-mapping:                                               │
│   • public_products  → Production preset                     │
│   • cybersecurity    → Conservative preset                   │
│                                                              │
│  When project has multiple goals — system uses MOST          │
│  CONSERVATIVE preset (security wins over public).            │
│                                                              │
│  Override per project (faza 17):                             │
│   ☑ Allow operator to override preset per project            │
│   ☑ Show inheritance chain ("inherited from goals")          │
│                                                              │
│  Override per phase (fazy 23, 32, etc.):                     │
│   ☑ Allow per-phase override                                 │
│                                                              │
│  Mapping table:                                              │
│   Goal                  Default preset                       │
│   ─────────────────  ──────────────                          │
│   public_products      Production                             │
│   cybersecurity        Conservative                          │
│   research             Research                              │
│   apps_internal        Balanced                              │
│   mixed/explore        Balanced                              │
│                                                              │
│  [Save mapping]  [Edit preset details]                       │
└──────────────────────────────────────────────────────────────┘
```

### 4.4.3. Preset preview

Operator może zobaczyć preview każdego presetu przed wyborem:

```
┌──────────────────────────────────────────────────────────────┐
│  Preset Preview: Production                                  │
│                                                              │
│  10 dimensions of autonomy (L0-L5):                          │
│                                                              │
│   DIM-1  Council formation:        L2 (Balanced)             │
│   DIM-2  Council voting threshold: L2 (Balanced)             │
│   DIM-3  Cost decisions:           L1 (Notify, don't auto)  │
│   DIM-4  Model selection:          L2 (Balanced)             │
│   DIM-5  Environment selection:    L2 (Balanced)             │
│   DIM-6  Skill creation:           L2 (Balanced)             │
│   DIM-7  Quality verdicts:         L2 (Balanced)             │
│   DIM-8  Deploy authorization:     L0 (Always manual) ⚠      │
│   DIM-9  Mid-flight overrides:     L1 (Notify)              │
│   DIM-10 Cascade re-evaluation:    L0 (Manual review) ⚠      │
│                                                              │
│  ⚠ Manual gates (cannot be bypassed):                        │
│     • Deploy authorization (D-level >= 4)                    │
│     • Cascade re-evaluation after incidents                  │
│                                                              │
│  Typical operator interactions per project:                  │
│   • 8-15 approval prompts (vs ~3-5 in Aggressive)            │
│   • 25-45 min hands-on operator time per project             │
│   • Risk profile: low (production-safe)                      │
│                                                              │
│  Best for:                                                   │
│   ✓ Customer-facing applications                             │
│   ✓ Real money flows                                         │
│   ✓ Compliance-required projects                             │
│                                                              │
│  Consider Conservative if:                                   │
│   • Government / classified workloads                        │
│   • Regulatory audit requirements                            │
│   • New operator (lower confidence)                          │
│                                                              │
│  [Use Production]  [Customize]  [Compare with...]           │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.5. Notification matrix + mobile companion app (P4.6=d operator-defined + P4.11=a in-app + mobile)

### 4.5.1. AEIS Mobile companion app

Faza 4 wprowadza **AEIS Mobile** jako companion app. Scope:

**What mobile DOES**:
- Receive notifications (push notifications)
- Quick approve/reject hard gates
- View project status (read-only)
- View cost dashboards
- Acknowledge alerts
- View audit chain entries

**What mobile DOES NOT**:
- Edit projects
- Modify settings
- Run Council deliberations
- Trigger builds
- Modify environments
- Change credentials

To jest **companion**, nie pełen client. Heavy actions wymagają desktop.

### 4.5.2. Mobile pairing setup

```
┌──────────────────────────────────────────────────────────────┐
│  ●  AEIS Mobile Pairing                                      │
│                                                              │
│  AEIS Mobile pozwala otrzymywać notifications + quick        │
│  approvals na telefonie. Heavy actions zostają na desktop.   │
│                                                              │
│  Setup:                                                      │
│   1. Pobierz AEIS Mobile:                                    │
│      [App Store (iOS)]  [Google Play (Android)]              │
│                                                              │
│   2. Zeskanuj QR code w aplikacji:                           │
│                                                              │
│        ┌───────────────────────┐                             │
│        │ ▓▓ ▓▓ ▓▓▓ ▓ ▓▓▓ ▓▓ ▓▓│                             │
│        │ ▓▓▓ ▓ ▓ ▓▓ ▓▓ ▓▓▓ ▓ ▓│                             │
│        │ ▓ ▓▓ ▓▓▓ ▓ ▓▓▓ ▓▓ ▓▓▓│                             │
│        │ ▓▓ ▓ ▓ ▓ ▓▓ ▓▓▓ ▓ ▓ ▓│                             │
│        │ ▓ ▓▓▓ ▓▓ ▓▓ ▓ ▓▓ ▓▓▓ │                             │
│        │ ▓▓ ▓ ▓ ▓▓▓ ▓▓ ▓ ▓ ▓▓ │                             │
│        └───────────────────────┘                             │
│                                                              │
│   3. Mobile generuje pairing code, wpisz tutaj:              │
│      Pairing code: [ ______ ]                                │
│                                                              │
│   4. Setup mobile auth:                                      │
│      [○ Use master password (every time)]                    │
│      [● Mobile-specific PIN (faster)]                        │
│      [○ Biometric (Face ID / Touch ID)]                      │
│      [○ Combination: PIN + biometric]                        │
│                                                              │
│   5. Permissions (co mobile może):                           │
│      ☑ Receive notifications                                 │
│      ☑ View project status                                   │
│      ☑ Approve hard gates                                    │
│      ☑ Approve cost overruns (z confirmation)                │
│      ☐ Approve security incidents (recommend desktop only)   │
│      ☐ Modify settings (always desktop)                      │
│                                                              │
│  [Skip mobile setup]  [Verify pairing]                       │
└──────────────────────────────────────────────────────────────┘
```

### 4.5.3. Notification matrix (operator-defined per event)

Operator wybiera per event type które kanały są aktywne:

```
┌──────────────────────────────────────────────────────────────┐
│  Notification Matrix                                         │
│                                                              │
│  Per event type, wybierz kanały:                             │
│                                                              │
│   Event                  In-app  Mobile  Email  Slack  SMS  │
│   ──────────────────  ──────  ──────  ─────  ─────  ─── │
│   Council finalize        ✓      ✓       ☐      ☐     ☐   │
│   Hard gate required      ✓      ✓       ✓      ☐     ☐   │
│   Build complete          ✓      ✓       ☐      ☐     ☐   │
│   Build failure           ✓      ✓       ✓      ☐     ☐   │
│   Cost 50% threshold      ✓      ☐       ☐      ☐     ☐   │
│   Cost 80% threshold      ✓      ✓       ✓      ☐     ☐   │
│   Cost 95% threshold      ✓      ✓       ✓      ✓     ☐   │
│   Cost 100% exceeded      ✓      ✓       ✓      ✓     ✓   │
│   Deploy success          ✓      ✓       ☐      ☐     ☐   │
│   Deploy failure          ✓      ✓       ✓      ✓     ☐   │
│   Security incident       ✓      ✓       ✓      ✓     ✓   │
│   Quota approaching       ✓      ☐       ✓      ☐     ☐   │
│   Provider down           ✓      ✓       ✓      ☐     ☐   │
│   Customer-side outage    ✓      ✓       ✓      ✓     ☐   │
│                                                              │
│  Bulk actions:                                               │
│   [Mark all events: In-app + Mobile (recommended baseline)]  │
│   [Critical events: also Email + Slack]                     │
│   [Reset to AEIS defaults]                                   │
│                                                              │
│  Email recipient: robert@sylion.dev                          │
│  Slack workspace: SYLION dev (configured ✓)                  │
│  SMS phone:       +48-xxx-xxx-xxx (configured ✓)             │
│                                                              │
│  Quiet hours (no mobile notifications):                      │
│   ☑ Active 22:00 - 07:00 (operator timezone)                 │
│   ☐ Weekends                                                 │
│   ☐ Mark critical events as exception                        │
│                                                              │
│  [Save matrix]  [Test notification]                          │
└──────────────────────────────────────────────────────────────┘
```

### 4.5.4. Mobile notification flow

```
EXAMPLE — Hard gate approval na mobile:

┌─────────────────────────────────┐
│  AEIS — Hard Gate Required      │
│  ──────────────────────────────  │
│                                 │
│  Project: Sylion Tailor          │
│  Phase: Production Deploy        │
│  D-level: D4                     │
│                                 │
│  Action required:               │
│  Approve deploy do hetzner-     │
│  warsaw-1 z artifactsami        │
│  build_id:abc123                │
│                                 │
│  Verifications passed:          │
│   ✓ All tests (84% coverage)    │
│   ✓ Security scan clean         │
│   ✓ Cost within budget ($42)    │
│   ✓ DNS ready                   │
│                                 │
│  Operator approval needed for:  │
│   • Production deploy           │
│   • DNS cutover                 │
│   • Auto-scaling enable         │
│                                 │
│  [📱 Approve from mobile]        │
│  [💻 Switch to desktop]          │
│  [⏸ Snooze 15 min]              │
│  [✗ Reject]                     │
│                                 │
└─────────────────────────────────┘

Tap [Approve] →
  Biometric prompt (Face ID / Touch ID)
  Approval sent
  Desktop AEIS notified
  Pipeline continues
```

---

## 4.6. Default cleanup periods (P4.7=d smart defaults z notification)

### 4.6.1. Smart defaults per environment type

Faza 3 ustawiła cleanup policy. Faza 4 ustawia **defaults dla nowych
environments** based on type:

```
┌──────────────────────────────────────────────────────────────┐
│  Default Cleanup Periods (per environment type)              │
│                                                              │
│  Environment type      Default policy                        │
│  ──────────────────  ────────────────────────────────────  │
│  Production           Manual decommission                    │
│  Staging              Schedule (nights + weekends hibernate) │
│  Development          Schedule (nights only hibernate)       │
│  Testing              Auto cleanup po 24 hours               │
│  Demo                 Conditional (cleanup po 7d unused)     │
│  CI/CD ephemeral      Auto cleanup po 4 hours                │
│  PR previews          Conditional (cleanup po 3d unused)     │
│  Edge devices         Manual (customer property)             │
│  Sovereign            Manual (compliance audit)              │
│  Air-gapped           Manual (external control)              │
│                                                              │
│  Smart notification:                                         │
│   ☑ Notify operator BEFORE każdy cleanup (override option)   │
│   ☑ Notify operator po cleanup z summary                     │
│   ☐ Silent cleanup (no notifications)                        │
│                                                              │
│  Notification timing:                                        │
│   24h cleanup:    notify 1h before                           │
│   7d cleanup:     notify 24h before                          │
│   Schedule:       notify 30 min before                       │
│   Manual:         no auto-notify                             │
│                                                              │
│  [Edit per type]  [Save defaults]  [Reset to AEIS recommend] │
└──────────────────────────────────────────────────────────────┘
```

### 4.6.2. Cleanup overrides

```
Settings → Cleanup → Per-environment overrides

  Operator może override per environment w fazie 3.
  W fazie 4 ustanawia tylko defaults dla NOWYCH environments.
  
  Override behavior:
   ☑ Show override option przed każdy cleanup
   ☑ Allow "Extend by 24h" w mobile notification
   ☑ Allow "Convert to permanent" (manual approve)
   ☑ Allow "Decommission now" (skip wait)
  
  Audit trail:
   ☑ Log cleanup decisions (manual approve / auto / override)
   ☑ Log restore operations (po decommission)
   ☑ Log "Convert to permanent" decisions z reason
```

---

## 4.7. UI customization (P4.8=d power user level)

### 4.7.1. Customization scope

Operator wybrał **power user level**. Co operator może customize:

**Theme & visual**:
- Theme mode (auto/light/dark)
- Accent color (8 presets + custom hex)
- Density (compact/standard/comfortable)
- Font family (system/Inter/JetBrains Mono/custom)
- Font size base (12-20px)
- Animations (enabled/reduced/disabled)
- High contrast mode
- Custom CSS injection (advanced!)

**Layout**:
- Sidebar position (left/right/top)
- Sidebar collapsed state
- Visible panels per phase (operator wybiera co widzi)
- Panel sizes (resizable splits)
- Multi-window layout (Tauri supports)

**Per-phase customizations**:
- Faza 23 (Council): Show book panel persistent / collapsed
- Faza 28 (Masterplan): Show diagram view default / table view
- Faza 35 (Build): Live activity stream verbose / minimal

**Custom dashboards**:
- Operator może budować własne dashboards (drag & drop widgets)
- Cost / health / progress / custom metrics

### 4.7.2. UI customization wizard

```
┌──────────────────────────────────────────────────────────────┐
│  ●  UI Customization                                         │
│                                                              │
│  Theme:                                                      │
│   ┌─ PREVIEW ──────────────────────────────────────┐        │
│   │  [Compact] [Standard] [Comfortable]            │        │
│   │                                                │        │
│   │   ╔═══════════════════════════════════╗      │        │
│   │   ║ AEIS Header                       ║      │        │
│   │   ╠═══════════════════════════════════╣      │        │
│   │   ║ Sidebar │ Main Content            ║      │        │
│   │   ║         │                         ║      │        │
│   │   ║         │  ●  Sample button       ║      │        │
│   │   ║         │  ┌─────────────────┐    ║      │        │
│   │   ║         │  │ Sample text     │    ║      │        │
│   │   ║         │  └─────────────────┘    ║      │        │
│   │   ╚═══════════════════════════════════╝      │        │
│   │                                                │        │
│   │  Theme:    [Dark ▼]                            │        │
│   │  Accent:   [● Green] [○ Blue] [○ Purple] ...   │        │
│   │  Density:  [Standard ▼]                        │        │
│   │  Font:     [JetBrains Mono ▼]                  │        │
│   │  Base size: [14px ▼]                           │        │
│   └────────────────────────────────────────────────┘        │
│                                                              │
│  Layout:                                                     │
│   Sidebar position:   [● Left] [○ Right] [○ Top]             │
│   Sidebar default:    [● Expanded] [○ Collapsed] [○ Hidden]  │
│   Multi-window:       [● Allow] [○ Single window only]       │
│                                                              │
│  Per-phase visibility:                                       │
│   ☑ Council Book panel (faza 23)                             │
│   ☑ Masterplan diagram (faza 28)                             │
│   ☑ Live build stream (faza 35)                              │
│   ☐ Cost overlay (always-visible cost meter)                 │
│   ☐ Audit chain inspector                                    │
│                                                              │
│  Advanced:                                                   │
│   ☐ Allow custom CSS injection (power-user!)                 │
│      Path: ~/.sylion/<op>/custom.css                         │
│   ☐ Enable plugin system (community extensions)              │
│   ☐ Developer mode (show internal IDs, audit JSON, etc.)     │
│                                                              │
│  [Apply changes]  [Save preset]  [Reset to AEIS default]    │
└──────────────────────────────────────────────────────────────┘
```

### 4.7.3. UI presets

Operator może zachować **named presets**:

```
Saved presets:
  • "Workday focus"   — minimal sidebar, no notifications, large font
  • "Demo mode"       — clean UI, no developer info, large fonts dla
                        prezentacji
  • "Power user"      — compact density, all panels visible, dev mode on
  • "Mobile-paired"   — large click targets, reduce visual noise
  
Switch with hotkey:
  Cmd+1 / Ctrl+1: Workday focus
  Cmd+2 / Ctrl+2: Demo mode
  Cmd+3 / Ctrl+3: Power user
```

---

## 4.8. Shortcuts (P4.9=c+d full customization + adaptive learning)

### 4.8.1. Predefined shortcuts (fully customizable)

```
┌──────────────────────────────────────────────────────────────┐
│  Keyboard Shortcuts                                          │
│  Filter: [All categories ▼]   [+ Add custom]                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  GLOBAL                                                      │
│   Cmd+K           Quick search (projects, phases, settings)  │
│   Cmd+,           Open settings                              │
│   Cmd+/           Show shortcuts                             │
│   Cmd+Shift+P     Command palette                            │
│   Cmd+B           Toggle sidebar                             │
│   Cmd+J           Toggle terminal                            │
│   Cmd+L           Lock workspace                             │
│   Esc             Cancel / close modal                       │
│                                                              │
│  NAVIGATION                                                  │
│   Cmd+1-9         Switch to project 1-9                      │
│   Cmd+Tab         Last active project                        │
│   Cmd+P           Project picker                             │
│   Cmd+Up/Down     Phase prev/next                            │
│   Cmd+Shift+H     Home (workspace overview)                  │
│                                                              │
│  PROJECT                                                     │
│   Cmd+N           New project (faza 16)                      │
│   Cmd+Shift+N     New project from template                  │
│   Cmd+S           Save / freeze current state                │
│   Cmd+Shift+A     Archive project                            │
│   Cmd+Z           Undo last action (where applicable)        │
│   Cmd+Shift+Z     Redo                                       │
│                                                              │
│  COUNCIL (Faza 23)                                           │
│   Cmd+Enter       Approve current decision                   │
│   Cmd+Shift+Enter Approve all pending                        │
│   Cmd+R           Reject current                             │
│   1/2/3/4         Quick select option A/B/C/D                │
│   Space           Pause council                              │
│                                                              │
│  CUSTOM (operator-defined)                                   │
│   Cmd+Shift+T     [Open today's project — auto-suggested]    │
│   Cmd+Shift+L     [Toggle live cost overlay]                 │
│   Cmd+Shift+B     [Build current project]                    │
│   [+ Add custom]                                             │
│                                                              │
│  [Edit any]  [Reset all to defaults]                         │
└──────────────────────────────────────────────────────────────┘
```

### 4.8.2. Adaptive shortcut learning (P4.9=d)

System uczy się ze wzorców operator i sugeruje shortcuts:

```
┌──────────────────────────────────────────────────────────────┐
│  💡  Shortcut Learning                                       │
│                                                              │
│  System wykrył wzorce:                                       │
│                                                              │
│  Pattern 1: "Open project Sylion Tailor + Faza 23"           │
│   Częstotliwość: 14 razy w ostatnich 7 dniach                │
│   Typowy czas: 8 sekund manual (search + click + click)      │
│                                                              │
│   Sugestia shortcut:                                         │
│   ┌────────────────────────────────────────────────┐        │
│   │  Cmd+Shift+T  → Sylion Tailor / Council        │        │
│   │  Estimated time saved: 7 sek per use           │        │
│   │  Total per week: 98 sek                        │        │
│   └────────────────────────────────────────────────┘        │
│                                                              │
│   [Accept shortcut]  [Decline]  [Customize key]              │
│                                                              │
│                                                              │
│  Pattern 2: "Cancel Council + check costs"                   │
│   Częstotliwość: 8 razy ostatnio                             │
│   Suggestion: Cmd+Shift+C → Council pause + cost overlay     │
│   [Accept]  [Decline]                                        │
│                                                              │
│                                                              │
│  Pattern 3: "Decommission test environments po build"        │
│   Częstotliwość: 5 razy                                      │
│   Suggestion: Bulk action — system automatically po success  │
│   [Enable auto-cleanup]  [Manual approve]  [Decline]         │
│                                                              │
│                                                              │
│  Settings:                                                   │
│   ☑ Suggest shortcuts based on patterns                      │
│   ☑ Suggest auto-actions based on patterns                   │
│   ☐ Auto-apply suggested shortcuts (no approval)             │
│   Suggestion frequency: [Weekly ▼]                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.8.3. Shortcut conflicts

System wykrywa konflikty z OS shortcuts:

```
⚠ Shortcut conflict detected

  Cmd+Shift+T conflicts with:
   • macOS: Open last closed tab in browser
   • Tauri (AEIS): undefined
  
  AEIS will use Cmd+Shift+T globally w tej app, ale browser
  context może być confusing.
  
  Suggestion: use Cmd+Shift+Y instead (less conflicts)
  
  [Use Cmd+Shift+T anyway]  [Use Cmd+Shift+Y]  [Cancel]
```

---

## 4.9. Workspace navigation (P4.10=d projects grouped by status)

### 4.9.1. Project organization

Operator wybrał **projects grouped by status** — natural workspace
organization.

```
┌──────────────────────────────────────────────────────────────┐
│  Workspace Sidebar                                           │
│  Search: [_______________]  Cmd+K                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ▼ FAVORITES                                                 │
│      ★ Sylion Tailor                  Faza 35 (build)        │
│      ★ Lokalny CRM                    Faza 41 (closure)      │
│                                                              │
│  ▼ ACTIVE (3)                                                │
│      ● Sylion Tailor                  Faza 35 (build)        │
│      ● Customer Acme Pilot            Faza 23 (council)      │
│      ● Internal Dashboard             Faza 28 (planning)     │
│                                                              │
│  ▼ IN PROGRESS, paused (2)                                   │
│      ⏸ Old PKB v1                     Faza 33 (paused)       │
│      ⏸ Customer Beta Pilot            Faza 22 (paused)       │
│                                                              │
│  ▼ COMPLETED RECENT (5)                                      │
│      ✓ Lokalny CRM                    Closed 2 dni temu      │
│      ✓ Sylion Tailor v1               Closed 7 dni temu      │
│      ✓ Atelier MVP                    Closed 14 dni temu     │
│      ✓ ... (2 more)                                           │
│                                                              │
│  ▼ ARCHIVED (12)                                             │
│      [Show all archived]                                     │
│                                                              │
│  ▼ DRAFTS / IDEAS (4)                                        │
│      ◌ Sylion Tailor v3 idea          Captured 3 dni temu    │
│      ◌ Music school CRM               Captured 1 dzień temu  │
│      ...                                                     │
│                                                              │
│  ─────────────────────────────────────                      │
│                                                              │
│  [+ New project]  [+ New idea]  [+ Folder]                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.9.2. Quick search (Cmd+K)

```
┌──────────────────────────────────────────────────────────────┐
│  🔍  Search                                                  │
│                                                              │
│  [ syl____________________ ]                                 │
│                                                              │
│  PROJECTS                                                    │
│   ★ Sylion Tailor              Active · Faza 35              │
│   ✓ Sylion Tailor v1           Closed                        │
│   ✓ Sylion Atelier MVP         Closed                        │
│                                                              │
│  PHASES                                                      │
│   • Sylion Tailor / Faza 23 (Council)                        │
│   • Sylion Tailor / Faza 35 (Build)                          │
│   • Sylion Tailor / Faza 41 (Closure) — pending              │
│                                                              │
│  COMMANDS                                                    │
│   /sylion-tailor build           Build Sylion Tailor         │
│   /sylion-tailor cost            Show cost dashboard          │
│                                                              │
│  RECENT FILES                                                │
│   • sylion-tailor/ksiega.md (modified 2h ago)                │
│   • sylion-tailor/masterplan.md (modified 1d ago)            │
│                                                              │
│  Esc: cancel · Tab: navigate · Enter: select                 │
└──────────────────────────────────────────────────────────────┘
```

### 4.9.3. Workspace overview

```
┌──────────────────────────────────────────────────────────────┐
│  Workspace Overview                          Press H to home │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ⚡  ACTIVE PROJECTS                                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Sylion Tailor                Faza 35 (Build)         │ │
│  │  Progress: ████████░░░░ 65%   $42 / $250 budget       │ │
│  │  Last activity: 2 min ago     Estimated complete: 8h  │ │
│  │  [View live]  [Pause]  [Cost]  [Logs]                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Customer Acme Pilot          Faza 23 (Council)       │ │
│  │  Progress: ████░░░░░░░░ 25%   $8 / $150 budget        │ │
│  │  Last activity: 25 min ago    Awaiting decision       │ │
│  │  ⚠ Operator action needed: hard gate approval         │ │
│  │  [Review now]  [Snooze 30 min]                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  📊  COSTS THIS MONTH                                        │
│   Total: $87.50 / $500 budget (18%)                          │
│   By provider: Anthropic $54, OpenAI $18, Cloud $9           │
│                                                              │
│  📈  PROVIDERS HEALTH                                         │
│   ✓ All providers healthy                                     │
│   ⚠ OpenAI degraded (latency 1.4s, normal 380ms)             │
│                                                              │
│  🌍  ENVIRONMENTS                                            │
│   4 active, 1 alert (rpi-fabryka-2 offline)                  │
│                                                              │
│  📅  UPCOMING                                                │
│   • Customer Acme Pilot review meeting tomorrow              │
│   • Monthly cost report due Friday                           │
│   • RPi fleet update window weekend                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.10. Approval workflow + escalation (P4.11=a + P4.12=c autonomy-driven)

### 4.10.1. Approval channels

Operator wybrał **in-app + mobile** jako primary. Other channels available
ale wymagają explicit configuration:

```
┌──────────────────────────────────────────────────────────────┐
│  Approval Workflow Configuration                             │
│                                                              │
│  Default approval channels (per event):                      │
│                                                              │
│   Event type                Primary       Fallback           │
│   ─────────────────────  ─────────────  ───────────         │
│   Hard gate                In-app+Mobile  Email po 30min     │
│   Cost overrun (95%)       In-app+Mobile  Email po 15min     │
│   Cost overrun (100%)      In-app+Mobile  Email+SMS po 10min │
│   Security incident        In-app+Mobile  Email+SMS+Slack    │
│                                                              │
│  Approval modal behavior:                                    │
│   ☑ Show critical context (what's being approved)            │
│   ☑ Show consequences (what happens after approve)           │
│   ☑ Show alternatives (reject paths)                         │
│   ☑ Require explicit click (no auto-confirm)                 │
│   ☑ Mobile: require biometric (Face ID/Touch ID)             │
│                                                              │
│  Concurrent approval prevention:                             │
│   ☑ If approved on mobile, desktop modal auto-dismisses      │
│   ☑ Same vice-versa                                          │
│   ☑ Audit chain logs WHICH device approved                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.10.2. Escalation timeouts (autonomy-driven)

Operator wybrał **autonomy-driven escalation**. Timeouts dziedziczone z
autonomy preset projektu:

```
┌──────────────────────────────────────────────────────────────┐
│  Escalation Timeouts per Autonomy Preset                     │
│                                                              │
│  Preset: Conservative                                        │
│   Hard gate timeout:           60 min before escalation      │
│   Cost overrun timeout:        30 min                        │
│   Security incident timeout:   5 min (always urgent)         │
│   Auto-action po timeout:      Pause + notify ALL channels   │
│                                                              │
│  Preset: Balanced                                            │
│   Hard gate timeout:           30 min                        │
│   Cost overrun timeout:        15 min                        │
│   Security incident timeout:   5 min                         │
│   Auto-action po timeout:      Pause + email                 │
│                                                              │
│  Preset: Aggressive                                          │
│   Hard gate timeout:           10 min                        │
│   Cost overrun timeout:        5 min                         │
│   Security incident timeout:   2 min                         │
│   Auto-action po timeout:      Auto-deny (safety) + notify   │
│                                                              │
│  Preset: Production                                          │
│   Hard gate timeout:           ∞ (wait indefinitely)         │
│   Cost overrun timeout:        ∞                             │
│   Security incident timeout:   2 min                         │
│   Auto-action po timeout:      Pause indefinitely            │
│                                                              │
│  Preset: Research                                            │
│   Hard gate timeout:           120 min (relaxed)             │
│   Cost overrun timeout:        60 min                        │
│   Security incident timeout:   10 min                        │
│   Auto-action po timeout:      Auto-deny + log               │
│                                                              │
│  Per-event override:                                         │
│   ☑ Allow per-event customization w faza 17                  │
│   ☑ Operator can extend timeout w real-time (mobile +15 min) │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.10.3. Escalation flow example

```
EXAMPLE — Hard gate dla deploy:

T+0:00:  Hard gate created
         → In-app modal pokazane
         → Mobile push notification sent
         
T+5:00:  Operator nie reagował
         → Mobile reminder push notification

T+15:00: Operator nadal brak reakcji
         → Email sent: "Hard gate awaiting approval"
         
T+30:00: (Balanced preset timeout)
         → Pipeline pauzowany
         → Notification: "Pipeline paused due to no operator response"
         → Slack notification (jeśli skonfigurowany)
         
T+60:00: Operator wraca, klika Approve
         → Pipeline resumes
         → Audit entry: gate_approved_late z reason "operator returned"
```

---

## 4.11. Default test strategy (P4.13=a + mandatory human-like UI testing)

### 4.11.1. Test strategy default + human-like mandatory

Operator wybrał **standard L1+L2+L3 jako default** ALE **human-like UI/UX
testing zawsze włączone** (mandatory dla wszystkich projektów).

```yaml
default_test_strategy:
  level_1_unit:
    enabled: true
    coverage_target: 80%
    framework: pytest / vitest / jest
    runs: per build
  
  level_2_integration:
    enabled: true
    coverage: API contracts, DB integration
    framework: pytest with fixtures
    runs: per build
  
  level_3_e2e:
    enabled: true
    coverage: critical user journeys
    framework: Playwright
    runs: per build
  
  level_4_performance:
    enabled: false  # default off, enable per project
    framework: k6 / locust
    runs: pre-prod only
  
  human_like_ui_testing:  # MANDATORY — always on, P4.13 explicit
    enabled: true  # ZAWSZE — operator nie może wyłączyć w defaults
    framework: Playwright + AEIS observation engine
    scope:
      - All forms (data entry validation)
      - All buttons (click + observe response)
      - All navigation paths
      - Error scenarios (network failure, invalid input)
      - Multi-language switching (jeśli i18n)
      - Mobile viewport (jeśli responsive)
      - Accessibility (keyboard navigation, screen reader)
    behavior:
      - Click each element
      - Enter realistic data (não dummy "test123")
      - Observe page response
      - Check console errors
      - Check network errors
      - Take screenshots na key states
      - Log animations / unexpected behaviors
    fix_during_test:
      - Detect visual regression
      - Detect functional regression
      - Auto-suggest fix (LLM-driven)
      - Apply fix if autonomy permits
      - Re-run after fix
      - Loop until stable lub manual review
```

### 4.11.2. Human-like testing detailed

```
┌──────────────────────────────────────────────────────────────┐
│  Human-Like UI Testing (mandatory)                           │
│                                                              │
│  AEIS uruchamia browser automation która zachowuje się jak   │
│  prawdziwy user. NIE jest to "test123 + assert" — to:        │
│                                                              │
│  Workflow per test scenario:                                 │
│                                                              │
│  1. Plan scenario:                                           │
│     "User wchodzi na stronę → klika Login → wpisuje dane     │
│      → submituje → spodziewa się dashboard"                  │
│                                                              │
│  2. Execute step-by-step:                                    │
│     a. Navigate do URL                                       │
│     b. Wait for page load (visual + network idle)            │
│     c. Find Login element (by accessible label, not selector)│
│     d. Click → wait for transition                           │
│     e. Find email input → type realistic email               │
│     f. Find password input → type realistic password         │
│     g. Find submit → click                                   │
│     h. Wait for redirect / response                          │
│     i. Verify dashboard elements visible                     │
│                                                              │
│  3. Observation w trakcie:                                   │
│     - Screenshot przed/po każdym step                        │
│     - Console error log                                      │
│     - Network request log                                    │
│     - Visual diff vs expected (jeśli have baseline)          │
│     - Animation detection (czy UI responsive)                │
│     - Layout shift detection (CLS)                           │
│                                                              │
│  4. Issue detection:                                         │
│     - Element nie znaleziony → "form structure broken"       │
│     - Type slow vs fast → "input handling issue"             │
│     - Click bez response → "button handler missing"          │
│     - Console errors → "JavaScript error w X"                │
│     - 500 response → "backend bug"                           │
│     - Visual regression → "CSS broken"                       │
│                                                              │
│  5. Auto-fix (jeśli autonomy permits):                       │
│     - LLM analizuje issue + code                             │
│     - Proponuje fix                                          │
│     - Apply fix                                              │
│     - Re-run scenario                                        │
│     - Loop max 3-5 iterations                                │
│                                                              │
│  6. Report:                                                  │
│     - Total scenarios: 24                                    │
│     - Passed: 22                                             │
│     - Auto-fixed: 1 (CSS regression in mobile view)          │
│     - Manual review: 1 (semantic issue, LLM not confident)   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 4.11.3. Human-like testing default scenarios

System ma **biblioteki scenariuszy** które są auto-generated dla projektu:

```
Standard scenarios (auto-applied):
  
  Authentication:
   • Sign up flow (email + password)
   • Sign up flow (OAuth jeśli dostępne)
   • Login successful
   • Login failure (wrong password)
   • Password reset flow
   • Logout
  
  Forms:
   • Submit empty form (validation expected)
   • Submit with invalid data (validation expected)
   • Submit with valid data (success expected)
   • Submit with edge cases (long strings, special chars, unicode)
   • Browser back po submit (state persistence?)
  
  Navigation:
   • Click each menu item
   • Use browser back button (history works?)
   • Refresh page (state lost? OK?)
   • Open w new tab (sharable URLs?)
  
  Errors:
   • Network down during submit
   • Server 500 response
   • Slow network (3G simulation)
   • Malformed response
  
  Multi-language (jeśli i18n):
   • Switch to PL → all texts changed
   • Switch to EN → all texts changed
   • Switch to DE → all texts changed
   • Verify date/currency format
  
  Accessibility:
   • Tab navigation through all interactive elements
   • Keyboard-only operation (no mouse)
   • Screen reader announcements (axe-core checks)
   • High contrast mode rendering
  
  Mobile responsive (jeśli applicable):
   • iPhone viewport
   • iPad viewport
   • Android viewport
   • Touch interactions
   • Orientation change

Project-specific scenarios (z masterplanu):
  • Generated z user stories w Księdze
  • Generated z acceptance criteria
  • Generated z edge cases identified by Council
  
Operator can add custom scenarios w fazie 13 (Test Strategy Templates).
```

### 4.11.4. Human-like testing settings

```
Settings → Test Strategy → Human-like UI

  Mandatory scope (always on):
   ✓ Authentication scenarios (8)
   ✓ Form scenarios (15-25 per form)
   ✓ Navigation scenarios (per route)
   ✓ Error scenarios (10)
   ✓ Multi-language (jeśli i18n: per locale)
   ✓ Accessibility (15 checks)
  
  Optional scope:
   ☑ Mobile responsive testing
   ☑ Slow network simulation
   ☐ Long-running stress (5+ min sessions)
   ☐ Concurrent multi-user (advanced)
  
  Auto-fix behavior (autonomy-driven):
   Conservative: detect → ask operator → apply fix
   Balanced:     detect → auto-fix simple → ask for complex
   Aggressive:   detect → auto-fix all → ask only for risky
  
  Cost considerations:
   Browser automation cost: ~$0.40 per scenario
   Average project: 20-40 scenarios
   Cost: $8-16 per build
   ☑ Include w project budget (recommended)
   ☐ Run only on PR builds (save cost)
   ☑ Run all scenarios pre-prod always
```

---

## 4.12. Default Council templates (P4.14=d per-goal sets)

### 4.12.1. Per-goal Council sets

Operator wybrał **operator-defined per goal**. Operator buduje own sets
dla each goal kombinacja.

```
┌──────────────────────────────────────────────────────────────┐
│  Default Council Templates per Goal                          │
│                                                              │
│  Goal: public_products                                       │
│  Default Council set:                                        │
│   1. Council Chair        (claude-opus)                      │
│   2. Planner              (claude-sonnet)                    │
│   3. Critic               (gpt-5)                            │
│   4. Security             (claude-opus)                      │
│   5. UX Designer          (claude-sonnet)                    │
│   6. QA Lead              (gpt-5)                            │
│   7. Compliance           (bielik-11b lokalny)               │
│   [+ Add role]                                               │
│                                                              │
│  Goal: cybersecurity                                         │
│  Default Council set:                                        │
│   1. Council Chair        (claude-opus)                      │
│   2. Planner              (claude-opus)                      │
│   3. Critic               (claude-opus)                      │
│   4. Security             (claude-opus + RAG security docs)  │
│   5. Compliance           (bielik-11b + KRI knowledge base)  │
│   6. Risk Assessor        (claude-opus)                      │
│   7. Encryption Auditor   (gpt-5)                            │
│   [+ Add role]                                               │
│                                                              │
│  Goal: research                                              │
│  Default Council set:                                        │
│   1. Council Chair        (claude-opus)                      │
│   2. Researcher           (claude-opus)                      │
│   3. Critic               (gpt-5)                            │
│   [+ Add role]                                               │
│                                                              │
│  Goal: apps_internal                                         │
│  Default Council set:                                        │
│   1. Planner              (claude-sonnet)                    │
│   2. Critic               (gpt-5)                            │
│   [+ Add role]                                               │
│                                                              │
│  Multi-goal projects (np. public_products + cybersecurity):  │
│  Strategy: [● Union of role sets]                            │
│            [○ Use larger set]                                │
│            [○ Operator defines separate set]                 │
│                                                              │
│  Per-D-level adjustments:                                    │
│   D1-D2: skip optional roles (Compliance, UX może)           │
│   D3:    standard set                                        │
│   D4:    add External Reviewer mock                          │
│   D5:    full board + government compliance role             │
│                                                              │
│  [Save templates]  [Edit per goal]  [Test on sample project] │
└──────────────────────────────────────────────────────────────┘
```

### 4.12.2. Council role library

Operator może wybrać z rich library predefined ról:

```
Standard roles (always available):
  • Council Chair         — moderator deliberation
  • Planner              — proposes solution
  • Critic               — challenges plan
  • Security             — security implications
  • Compliance           — regulatory requirements
  • UX Designer          — user experience
  • QA Lead              — testability
  • Risk Assessor        — overall risk
  • Researcher           — for research projects
  • Encryption Auditor   — crypto-specific
  • External Reviewer    — mock external audit
  
Industry-specific roles:
  • Polish Legal         — KSeF, RODO, Polish law
  • EU Compliance        — GDPR, NIS2, DORA
  • Financial Auditor    — financial regulation
  • Government TLP       — classification awareness
  • Healthcare HIPAA     — medical data
  • Payment PCI          — payment card industry
  • Accessibility WCAG   — a11y compliance
  
Domain-specific roles:
  • Code Architect       — software architecture
  • DBA                  — database design
  • DevOps               — deployment, ops
  • Mobile Specialist    — mobile UI/UX
  • Real-time Specialist — real-time systems
  • ML Engineer          — ML model design
  
Operator-defined custom roles:
  [+ Create custom role with prompt]
```

### 4.12.3. Council composition wizard

Operator może uruchomić **wizard** który pomaga zbudować Council dla
specific project type:

```
┌──────────────────────────────────────────────────────────────┐
│  Council Composition Wizard                                  │
│                                                              │
│  What kind of project?                                       │
│   [○ Web app (SaaS, internal tool)]                          │
│   [○ Mobile app]                                             │
│   [● Web app + payment integration]                          │
│   [○ ML/AI project]                                          │
│   [○ Government / classified]                                │
│   [○ Custom]                                                 │
│                                                              │
│  Industry:                                                   │
│   [○ E-commerce]                                             │
│   [○ Financial / banking]                                    │
│   [○ Healthcare]                                             │
│   [● Fashion / atelier]                                      │
│   [○ Government]                                             │
│   [○ Other]                                                  │
│                                                              │
│  Compliance required:                                        │
│   ☑ GDPR                                                     │
│   ☑ PCI DSS (jeśli credit cards)                             │
│   ☐ HIPAA                                                    │
│   ☐ KRI-PL                                                   │
│                                                              │
│  Languages supported:                                        │
│   ☑ Polski                                                   │
│   ☑ English                                                  │
│   ☑ Deutsch                                                  │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  AEIS recommends Council:                                    │
│                                                              │
│   Council Chair        claude-opus                            │
│   Planner              claude-sonnet                          │
│   Critic               gpt-5                                  │
│   Security             claude-opus                            │
│   Payment Specialist   claude-opus + RAG PCI docs            │
│   UX Designer          claude-sonnet                          │
│   Compliance (GDPR)    bielik-11b                             │
│   Compliance (PCI)     gpt-5                                  │
│   QA Lead              gpt-5                                  │
│   i18n Specialist      claude-sonnet                          │
│                                                              │
│  Total: 10 roles                                             │
│  Estimated cost per round: $2.40                             │
│  Estimated time per round: 4-6 min                           │
│                                                              │
│  [Customize]  [Save as template]  [Use for this project]    │
└──────────────────────────────────────────────────────────────┘
```

---

## 4.13. Edge Cases (P4.15=c — 25 cases)

25 cases w 5 kategoriach (faza 4 ma mniej external integration).

### Kategoria A — Configuration conflicts (5 cases)

#### EC-A1: Smart defaults conflict z user preferences

**Trigger**: AEIS proponuje "Conservative preset" dla cybersecurity goal.
Operator chce Aggressive (np. dla rapid research wewnątrz security
domain).

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠ Suggested vs preferred autonomy mismatch                  │
│                                                              │
│  Goal: cybersecurity                                         │
│  AEIS suggests: Conservative preset                          │
│  Operator preference: Aggressive                             │
│                                                              │
│  Conflict reason:                                            │
│   AEIS uważa że cybersecurity wymaga ostrożności (manual     │
│   approval dla wszystkich decisions). Operator może chcieć   │
│   Aggressive dla research-style cybersec experiments.        │
│                                                              │
│  Akcje:                                                      │
│  [● Use Aggressive (operator's preference)]                  │
│      Note: AEIS będzie sometime warn że "to risky dla        │
│      cybersec" — możesz dismiss                              │
│  [○ Use Conservative (AEIS recommendation)]                  │
│      Safer default                                           │
│  [○ Custom — modify preset per dimension w fazie 5]          │
│      Aggressive na cost decisions, Conservative na security  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### EC-A2: Budget template doesn't fit estimated project cost

**Trigger**: Operator wybrał "small" template ($20). Cost estimation z
Księgi mówi $80 needed.

```
⚠ Budget template too small for estimated project cost

  Selected: SMALL ($20)
  Estimated need: $80 (z Księgi/masterplan analysis)
  
  Options:
   [Switch to MEDIUM template ($80)]  ← recommended
   [Reduce project scope (system suggests)]
   [Override: use $20, accept risk of overrun]
   [Increase SMALL template cap]
```

#### EC-A3: Notification matrix conflicts with quiet hours

**Trigger**: Critical security alert at 02:00 AM. Operator has quiet hours
22:00-07:00.

```
⚠ Critical alert during quiet hours

  Event: Security incident — possible data leak
  Time: 02:14 AM operator timezone
  Quiet hours: 22:00-07:00
  
  Default behavior:
   ☑ Critical events override quiet hours (configured)
   ☑ Send mobile push regardless
   ☑ Email + Slack regardless
   ☑ SMS dla critical
  
  Result: All notifications sent. Operator wakes up.
  
  Settings option:
   ☐ Make quiet hours STRICT (even critical events wait til morning)
      ⚠ NOT RECOMMENDED dla security
```

#### EC-A4: Mobile pairing fails

**Trigger**: QR code scanned but pairing handshake fails (network issue,
firewall, etc.).

```
✗ Mobile pairing failed

  Reason: Cannot reach AEIS desktop from mobile
  Possible causes:
   • Mobile not on same network as desktop
   • Firewall blocking AEIS port (default 8127)
   • VPN interference
  
  Akcje:
   [Use external relay (Tailscale-style)]
       Mobile + desktop both connect to relay server
       Works through NAT/firewall
   [Manually configure]
       Operator wpisuje desktop IP + port
   [Skip mobile setup]
       Continue desktop-only
```

#### EC-A5: UI customization breaks workspace

**Trigger**: Operator dodał custom CSS z bug który ukrywa critical UI
elements (np. cost dashboard, save button).

```
⚠ UI customization issue detected

  Symptoms:
   • "Save" button niewidoczny (z-index issue?)
   • Cost overlay nie renderuje się
   • Console errors related to .aeis-* classes
  
  Custom CSS source: ~/.sylion/<op>/custom.css
  Last modified: 5 min ago
  
  Akcje:
   [Disable custom CSS (revert to standard)]
       Quick fix, operator naprawia w isolation
   [Open CSS file in editor]
       Operator manual debugging
   [Show CSS conflicts]
       AEIS shows które reguły coliduj z core styles
```

### Kategoria B — Mobile companion issues (5 cases)

#### EC-B1: Mobile app outdated, backend updated

**Trigger**: Operator updated AEIS desktop do v3.1, ale mobile is v3.0.
Some new features incompatible.

```
ℹ Mobile app version mismatch

  Desktop AEIS: v3.1.0
  Mobile AEIS: v3.0.5
  
  Compatibility:
   ✓ Notifications work (basic)
   ✓ Approve/reject works (basic)
   ✗ New "cost predictions" view nie działa
   ✗ "Mobile dashboard widgets" nie work
  
  Akcje:
   [Update mobile app]
       Open App Store / Play Store
   [Continue z degraded mobile features]
       Notifications + approvals OK
   [Pin desktop do v3.0 (rollback)]
       Wait until mobile updated
```

#### EC-B2: Mobile lost connection during approval

**Trigger**: Operator widzi approval modal na mobile, klika Approve, ale
phone loses signal mid-submit.

```
⚠ Approval submission failed (network)

  Action: Hard gate approve dla deploy
  Status: NOT submitted (network error)
  
  AEIS desktop status: still waiting for approval
  
  Akcje:
   [Retry submission (when connected)]
       Mobile queues, sends gdy back online
   [Switch to desktop]
       Cancel mobile attempt, approve from desktop
   [Cancel approval]
       No action taken
```

#### EC-B3: Mobile + desktop concurrent approval

**Trigger**: Operator zaczął approval na mobile, simultaneously partner
otworzył approval na desktop (shared workspace).

```
⚠ Concurrent approval detected

  Hard gate: Deploy to production
  Mobile: Robert (przyjmuje approval)
  Desktop: Anna (przyjmuje approval, started 2s later)
  
  Resolution: First-click-wins
  Winner: Robert (mobile, 2s earlier)
  
  Audit chain entry:
   ts: 2026-04-29 14:32:08
   approved_by: robert.k
   device: mobile
   second_attempt_by: anna.k (rejected, race lost)
```

#### EC-B4: Mobile app deleted, no notifications received

**Trigger**: Operator deleted mobile app accidentally. Critical
notifications nie dotaerły. Discovered po 8h delay.

```
⚠ Mobile push notifications failing (no acknowledgment)

  Last successful push delivery: 8h ago
  Total failed deliveries: 47
  
  Possible causes:
   • App deleted/uninstalled
   • Push notifications disabled w OS
   • Phone offline / battery dead
   • Push token expired
  
  AEIS recommends:
   [Verify mobile app still installed]
       Send test push (operator confirms receipt)
   [Disable mobile temporarily]
       Use desktop + email until issue resolved
   [Reset push token]
       Re-pair mobile
```

#### EC-B5: Mobile auth method compromised

**Trigger**: Operator's phone stolen. Mobile has biometric auth → thief
może bypass z own face/finger jeśli spoof.

```
🚨 EMERGENCY — Mobile device compromised

  Operator action: "My phone was stolen"
  
  Immediate actions:
   ✓ Revoke mobile pairing (disable mobile access)
   ✓ Audit recent mobile actions (review last 24h)
   ✓ Notify operator security email
  
  Audit shows:
   Last 24h mobile actions: 12 (operator's normal pattern)
   No suspicious approvals
   No data access
  
  Recommendations:
   [● Revoke mobile pairing now]
   [Re-pair from new device]
       Wymaga master password from desktop
   [Audit all activities last 7d]
       Detailed report dla incident response
   [Optional: change master password]
       Just to be safe
```

### Kategoria C — Wizard / setup issues (5 cases)

#### EC-C1: Operator skips wizard but later regrets

**Trigger**: Operator skipped fazę 4. Po 3 projektach realizes że every
project requires manual setup. Wraca do fazy 4.

```
ℹ Welcome back to Phase 4

  You skipped Phase 4 setup 3 weeks ago.
  Since then:
   • You created 3 projects
   • Average setup time per project: 12 min (manual config)
   • Total time spent: 36 min that could be saved
  
  Apply defaults retroactively?
   [Yes — use new defaults dla future projekty]
       Existing 3 projects unchanged
   [Yes — also update existing projects to new defaults]
       Existing projects re-checked, settings updated
       Operator review changes per project
   [No — just save defaults dla future]
```

#### EC-C2: Wizard bugfix mid-setup

**Trigger**: Operator jest w wizard step 6, AEIS gets crash. Recovery?

```
ℹ Wizard interrupted (crash detected)

  Phase 4 setup w step 6/9 (UI Customization)
  Last save: step 5 (Cleanup periods)
  
  Recovery options:
   [Resume from step 6]
       Re-enter UI customization choices
   [Restart wizard from beginning]
       Lose all progress
   [Skip remaining steps]
       Use system defaults dla 4-9
```

#### EC-C3: Cost estimation wrong (project cost much higher)

**Trigger**: AEIS estimated $80, project actually cost $250 (3x estimate).

```
ℹ Cost estimation accuracy review

  Project: Customer Acme Pilot
  Estimated cost: $80
  Actual cost: $251 (3.1x over estimate)
  
  Calibration:
   ☑ Add this project to calibration data
   ☑ Adjust future estimates dla similar projects
  
  Why estimate was wrong:
   • Council deliberation 4 rounds vs estimated 2 (operator
     debating)
   • Build phase R3+R5 repair iterations vs estimated R0+R1
   • Mid-build interventions: 8 vs estimated 3
   • Customer requested last-minute scope additions
  
  Future estimates dla "Customer pilot" type:
   Old multiplier: 1.0
   New multiplier: 1.5 (auto-calibrated)
   
  Operator can manually adjust:
   [Increase pilot budget template do $150]
   [Add risk buffer 50% dla pilots]
   [Keep $80, accept overrun risk]
```

#### EC-C4: Settings inheritance unclear

**Trigger**: Operator zmieniła Conservative w fazie 4, ale projekt nadal
używa Aggressive z fazy 17. Nie wie skąd.

```
ℹ Settings inheritance trace

  Project: Sylion Tailor v2
  Current autonomy preset: Aggressive
  
  Inheritance chain:
   Phase 4 default:    Production (z public_products goal)
   Phase 17 override:  Aggressive ← THIS APPLIES
   Phase 22 override:  none (inherits from 17)
   Phase 23 override:  none (inherits from 17)
  
  Why Aggressive:
   Operator decyzja w faza 17 podczas project setup.
   Date: 2026-04-15 14:32
   Reason logged: "Quick prototype, accept risk"
  
  Akcje:
   [Revert to Phase 4 default (Production)]
       Project autonomy → Production
   [Keep Aggressive]
       No change
   [Customize per dimension]
       Open faza 5 deep config
```

#### EC-C5: Multiple goals create conflicting defaults

**Trigger**: Operator goals = public_products + research. public_products
maps to Production, research maps to Research preset.

```
⚠ Multi-goal default conflict

  Goals: public_products + research
  
  Goal mappings:
   • public_products → Production preset
   • research        → Research preset
  
  Conflict:
   Production wymusza manual deploy authorization
   Research relaxed na cost decisions
  
  Resolution strategies:
   [● Most conservative wins (Production)]
       Safest but slower
   [○ Most aggressive wins (Research)]
       Faster but riskier
   [○ Per-dimension merge]
       Conservative na security/deploy, Aggressive na cost/research
   [○ Operator chooses per project]
       Show prompt every new project
```

### Kategoria D — Smart defaults edge cases (5 cases)

#### EC-D1: Smart defaults out of date (vendor changes)

**Trigger**: AEIS suggests "use Anthropic Claude Sonnet" jako default
Council Chair. Anthropic changes pricing/availability — sugestia stale.

```
ℹ Default needs refresh

  Default Council Chair: claude-sonnet-4-6
  Status: Still available, but:
   • Newer model claude-sonnet-5 available (better performance, +5%)
   • Pricing change: -20% lower cost
   • Operator hasn't reviewed this default in 6 months
  
  Recommend update:
   [Switch default to claude-sonnet-5]
   [Keep claude-sonnet-4-6]
   [Show comparison]
```

#### EC-D2: Operator profile changed (Solo → Team Lead)

**Trigger**: Operator changes profile from Solo do Team Lead. Some
defaults nie pasują już (e.g., approval flows).

```
ℹ Profile changed: Solo → Team Lead

  Affected defaults:
   • Approval workflow: dotychczas tylko operator approves.
     Team Lead może chcieć team approval.
   • Notification matrix: dodać team email distribution?
   • UI: pokazać team dashboard widgets?
   • Project templates: dodać "team review" gates?
  
  Update defaults teraz?
   [Smart update (auto-suggest changes)]
   [Manual review per default]
   [Keep current (no changes)]
```

#### EC-D3: Industry-specific defaults missing

**Trigger**: Operator w fazie 1 zaznaczył "healthcare" jako goal, ale
faza 4 nie ma healthcare-specific defaults.

```
ℹ Healthcare goal — no specific template

  Your goals include: healthcare
  AEIS templates: nie są jeszcze dostosowane dla healthcare
  
  Manual setup needed:
   • HIPAA compliance role w Council (manually add)
   • PHI data handling rules
   • Encryption requirements (always strong)
   • Audit chain extra strict
   • Data retention extra strict
  
  Akcje:
   [Use generic Conservative + manually add HIPAA role]
   [Request healthcare template]
       AEIS team może dodać healthcare-specific template
   [Use community-contributed healthcare template]
       From AEIS marketplace
```

#### EC-D4: Hardware degradation affects defaults

**Trigger**: Operator's GPU starts failing. AEIS detect degraded
performance. Should adjust defaults?

```
⚠ Hardware capability changed

  Detected: GPU thermal throttling, performance -30%
  
  Affected defaults:
   • Default "use local models when possible" — local jest now slow
   • Tutorial mode estimates — Quick może take longer
   • Auto-benchmark results stale
  
  Adjust defaults?
   [● Auto-adjust (prefer API providers more)]
       Higher cost but reliable performance
   [○ Keep current (operator handles per project)]
   [○ Run hardware diagnostic]
       Check if GPU needs cleaning, repair
```

#### EC-D5: Cost estimation includes services not in budget

**Trigger**: Cost estimation z Księgi includes "Stripe processing fees"
($0.30/transaction). To NIE jest w AEIS budget — to vendor cost.

```
ℹ Cost estimation note

  Estimated cost includes:
   ✓ AEIS direct costs: LLM calls, cloud resources
   ⚠ Vendor pass-through costs: Stripe fees, SMS costs, etc.
  
  Budget should cover:
   AEIS-controlled: $42 (LLM + cloud)
   Vendor pass-through: $8.40 (Stripe, ElevenLabs, etc.)
   Total: $50.40
  
  Akcje:
   [Include vendor costs w budget]
       Budget = $50, alerts include Stripe fees
   [Track vendor costs separately]
       Two budgets: AEIS = $42, Vendor = $10
   [Note in audit only]
       Operator manages vendor costs externally
```

### Kategoria E — Recovery / data integrity (5 cases)

#### EC-E1: Phase 4 settings corrupted

**Trigger**: SQLite corruption affects faza 4 settings table.

```
⚠ Phase 4 settings corruption

  Corrupted:
   ✗ Budget templates (3 of 4 unreadable)
   ✗ Notification matrix
   ✓ Autonomy presets (intact)
   ✗ Cleanup defaults
   ✓ UI customization (intact)
  
  Recovery options:
   [Restore z backup (yesterday)]
       Lose 24h of settings changes
   [Re-create from scratch]
       Phase 4 wizard restart
   [Restore z exported settings file]
       Operator's manual export available
```

#### EC-E2: Settings export/import for new machine

**Trigger**: Operator buys new laptop, wants transfer Phase 4 settings.

```
┌──────────────────────────────────────────────────────────────┐
│  Export Phase 4 Settings                                     │
│                                                              │
│  Settings to export:                                         │
│   ☑ Budget templates                                         │
│   ☑ Autonomy presets                                         │
│   ☑ Notification matrix                                      │
│   ☑ Cleanup defaults                                         │
│   ☐ UI customization (laptop-specific)                       │
│   ☐ Shortcuts (laptop-specific)                              │
│   ☑ Council templates                                        │
│   ☑ Test strategy defaults                                   │
│                                                              │
│  Format: [JSON ▼]                                            │
│  Encryption: [Use master password]                           │
│                                                              │
│  Output: ~/.sylion/exports/phase4-2026-04-29.json            │
│  Size: ~12 KB (encrypted)                                    │
│                                                              │
│  [Export]  [Cancel]                                          │
└──────────────────────────────────────────────────────────────┘
```

#### EC-E3: Default updates from AEIS team

**Trigger**: AEIS publishes new "best practices" defaults. Operator should
review.

```
ℹ AEIS Best Practices Update

  Published: 2026-04-25
  Changes since your last review (90 dni temu):
   • Notification matrix: added "AI hallucination detected" event
   • Budget templates: added "MICRO" template ($5) dla quick tests
   • Council templates: updated security role z RAG knowledge
   • Cleanup defaults: tightened CI ephemeral cleanup
  
  Apply updates?
   [Auto-apply (no breaking changes)]
   [Review each change manually]
   [Skip — keep my current defaults]
```

#### EC-E4: Sync conflict (multi-machine operator)

**Trigger**: Operator works on laptop + desktop. Different defaults
configured on each. Sync detects conflict.

```
⚠ Settings sync conflict

  Conflict source:
   Laptop:   Default budget = $80, last edit 2h ago
   Desktop:  Default budget = $50, last edit 6h ago
  
  Resolution:
   [● Use laptop value ($80) — newer]
   [○ Use desktop value ($50)]
   [○ Merge manually]
       Show full diff per setting
   [○ Per-machine settings (don't sync this one)]
```

#### EC-E5: Backup restore creates inconsistency

**Trigger**: Operator restores backup from 30 days ago. Defaults z backup
różnią się od faz 5-10 settings (newer).

```
⚠ Restore creates inconsistency

  Restored Phase 4 (from backup 30 dni temu):
   • Default autonomy preset: Balanced
  
  But Phases 5-10 settings (current):
   • Custom autonomy z 10 dimensions L1-L4 mix
  
  Inheritance chain broken:
   Phase 4 says: "Use Balanced preset"
   Phase 5 has: "Custom 10-dim autonomy" (no longer references preset)
  
  Resolution:
   [Re-create Phase 5 custom autonomy from backup]
       Restore both 4 and 5 from same backup point
   [Keep current Phase 5, reconnect inheritance]
       Phase 4 preset ignored, custom Phase 5 wins
   [Skip restore]
       Continue z current state, ignore backup
```

---

## 4.14. Inheritance + Acceptance Criteria + DoD

### 4.14.1. Inheritance pattern

Faza 4 sets **defaults** które dziedziczone przez wszystkie nowe projekty.
3 konkretne przykłady:

**Przykład 1 — Budget template propagation**:

```
Faza 4 sets:    Budget template "MEDIUM" ($80) dla D3 projects
   ↓
Faza 16 (Project Inception): nowy projekt klasyfikowany jako D3
   → Auto-applied: budget MEDIUM ($80)
   ↓
Faza 17 (Project Configuration): operator widzi inherited budget
   → Operator może override: "this project = $150"
   ↓
Faza 25 (Book Finalization): cost estimation z Księgi
   → Estimated $120
   → Within $150 (override) but exceeds $80 (default)
   → Show warning: "Project exceeds default template, you've already
                    overridden to $150 — OK"
   ↓
Faza 30 (Pre-Flight Cost Preview): final approval
   → Show $120 estimated, $150 cap, $30 buffer
```

**Przykład 2 — Notification matrix per event**:

```
Faza 4 sets:    "Cost 80% threshold" → In-app + Mobile + Email
   ↓
Faza 17 (per-project): override dla customer-facing project
   → Add Slack channel
   → Add SMS dla operator + customer success team
   ↓
Mid-project, cost reaches 80%:
   → Notifications fire on ALL channels
   → Mobile app shows quick-action: "Increase budget" / "Pause project"
```

**Przykład 3 — Test strategy human-like mandatory**:

```
Faza 4 sets:    Human-like UI testing = MANDATORY (always on)
   ↓
Faza 13 (Test Strategy Templates): operator może NIE wyłączyć
   → Human-like sekcja jest read-only, marked "mandatory"
   ↓
Faza 17 (per-project): operator próbuje disable
   → Block: "Cannot disable mandatory testing"
   → Może modify scope (specific scenarios)
   ↓
Faza 28 (Masterplan Synthesis): masterplan includes testing phase
   → 25-40 human-like scenarios auto-added
   ↓
Faza 35 (Build Orchestration): testing runs automatically po build
   → Cost: ~$8-16
   → Time: 15-30 min
   → Auto-fix iterations zgodnie z autonomy preset
```

### 4.14.2. Acceptance Criteria — DoD

#### Wspólne (zawsze wymagane)

```
✓ At least 1 budget template configured (default OK)
✓ Default autonomy preset selected (lub goal-driven mapping active)
✓ Notification matrix configured (in-app minimum)
✓ Default cleanup periods set
✓ Audit chain entry: phase_4.complete
```

#### Goal-specific dodatkowe

**Jeśli mobile app paired**:
```
✓ Mobile pairing verified (test push successful)
✓ Mobile permissions configured (which actions allowed)
✓ Mobile auth method set (PIN / biometric)
```

**Jeśli operator z goal "public_products"**:
```
✓ Production-tier budget template (LARGE/ENTERPRISE)
✓ Notification matrix includes critical events to all channels
✓ Approval workflow z mobile confirmation
✓ Council template includes UX + Compliance roles
```

**Jeśli operator z goal "cybersecurity"**:
```
✓ Conservative autonomy preset selected (lub equivalent custom)
✓ Council template includes Security + Compliance + Risk Assessor
✓ Audit chain extra-strict configuration
✓ Mobile approval restricted dla security incidents (desktop only)
```

### 4.14.3. Soft warnings vs hard blocks

**Hard blocks**:
- 0 budget templates configured (cannot create projects)
- No notification channel active (operator wouldn't see alerts)
- Default autonomy preset undefined (cannot determine project autonomy)

**Soft warnings**:
- Single notification channel only (no fallback if email down)
- All goals mapped to Aggressive (might be unsafe dla production)
- Cost estimation disabled (no early warning system)
- Mobile not paired (operator misses notifications when away from desktop)
- Human-like testing scope reduced (recommended full)

### 4.14.4. Acceptance test (automated)

```bash
$ aeis-cli phase4-acceptance-test

Running Phase 4 acceptance test...

[Common requirements]
[1/5] Budget templates configured                   ✓ PASS (4 templates)
[2/5] Default autonomy preset                       ✓ PASS (goal-driven)
[3/5] Notification matrix                           ✓ PASS (5 channels)
[4/5] Default cleanup periods                       ✓ PASS (10 types)
[5/5] Audit chain entry phase_4.complete            ✓ PASS

[Optional features]
[6/8] Mobile companion paired                       ✓ PASS (verified push)
[7/8] Cost estimation enabled                       ✓ PASS (calibrated)
[8/8] Custom shortcuts configured                   ⚠ WARN (only defaults)

[Goal-specific: public_products]
[9/12] Production budget template available          ✓ PASS (LARGE)
[10/12] Critical notifications multi-channel        ✓ PASS
[11/12] Mobile approval workflow                    ✓ PASS
[12/12] Council includes UX + Compliance            ✓ PASS

DoD: 11/12 ✓ + 1 ⚠
Soft warnings: 1 (no custom shortcuts)
Hard blocks: 0

Phase 4 ACCEPTED. Ready to proceed to Phase 5 (Autonomy Configuration).

Recommended pre-Phase-5 actions:
  • Configure 2-3 custom shortcuts dla frequent actions
  • Test mobile notifications with sample event
```

---

## Status fazy 4

🟢 **Wszystkie sekcje 4.1-4.14 complete**

**Zawiera**:
- ✓ Smart defaults philosophy + advisor pattern (4.1, 4.2)
- ✓ Budget templates + cost estimation z Księgi/masterplanu (4.3)
- ✓ 5 autonomy presets + goal-driven mapping (4.4)
- ✓ Notification matrix + AEIS Mobile companion app + pairing (4.5)
- ✓ Cleanup defaults per environment type (4.6)
- ✓ UI customization (power user level z custom CSS) (4.7)
- ✓ Shortcuts (predefined + custom + adaptive learning) (4.8)
- ✓ Workspace navigation (groups by status, search, overview) (4.9)
- ✓ Approval workflow + autonomy-driven escalation timeouts (4.10)
- ✓ Test strategy default + mandatory human-like UI testing (4.11)
- ✓ Council templates per-goal sets + composition wizard (4.12)
- ✓ Edge cases — 25 cases w 5 kategoriach (4.13)
- ✓ Inheritance + DoD + acceptance test (4.14)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 4** + przejście do **Faza 5 — Autonomy Configuration**.
