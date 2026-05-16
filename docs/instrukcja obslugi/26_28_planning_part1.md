# FAZY 26-28 — Planowanie część 1 (Grupa D)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: D — Planowanie (1-3 z 6) — pierwsza połowa
> **Zależności**: Fazy 1-25 zakończone (Księga locked)
> **Następnik**: Fazy 29-31 (druga połowa grupy D — Test Plan + Pre-Flight)
>
> **⚡ KLUCZOWA AKTUALIZACJA fazy 28**:
> Faza 28 została rozszerzona o sekcję **28.4 — Layer/Module
> Decomposition + Parallel Orchestration**. To rozwiązuje fundamentalny
> problem: oryginalna faza zakładała sekwencyjną pracę z hardcoded
> timeline. Rzeczywistość: operator może mieć 1 worker / 1 env
> (8 weeks, $145) lub 8 workers / 3 envs (1 week, $215). Sekcja 28.4
> wprowadza:
>   • Layer decomposition Księgi (Layer 0-7 z parallelizability)
>   • Module-level work decomposition
>   • Resource configuration matrix (5 predefined profiles)
>   • Throughput-driven timeline calculation
>   • Guards cost scaling z workers + envs
>   • Critical path narrowing
>   • Operator decision interface (cost vs time trade-off)
>
> Ta zmiana propaguje do faz 30 (pre-flight cost) i 32-36 (build
> orchestration).
>
> **Charakter grupy D**:
> Grupa D to **przejście od documentation do execution**. Mamy Księgę
> (faza 25) jako single source of truth. Grupa D produkuje:
>   • Model assignments (faza 26)
>   • Skill synthesis (faza 27)
>   • Masterplan z layer decomposition + parallel plan (faza 28)
>   • Test plan (faza 29)
>   • Pre-flight verification (fazy 30-31)
>
> Po grupie D operator wie **dokładnie co i jak będzie budowane** —
> zero surprise w grupie E (Wykonanie).

---

# FAZA 26 — Model Selection

> **Spis sekcji**:
> - 26.1 — Sense fazy + planning model assignments
> - 26.2 — Per-task model assignment matrix
> - 26.3 — Cost optimization
> - 26.4 — Quality requirements per task type
> - 26.5 — Edge cases (15) + transition do fazy 27

---

## 26.1. Sens fazy

### 26.1.1. Co Faza 26 robi

Mamy Księgę z all features specified. Faza 26 to **pre-allocation**:
which models do which build tasks. Bez tego, każdy build task spawn
ad-hoc model decisions — slower, more expensive, less consistent.

```
┌──────────────────────────────────────────────────────────────┐
│  Model Selection — pre-allocation dla build tasks            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z faza 25):                                          │
│   • Księga z all modules + features                           │
│   • Test plan requirements                                    │
│   • Cost budget (z Księga Part VIII)                          │
│   • Quality requirements (z autonomy preset)                  │
│                                                              │
│  PROCESSING:                                                 │
│   • Map each Księga module do task types                      │
│   • Match task types do optimal models                        │
│   • Apply cost constraints                                    │
│   • Validate quality requirements                             │
│                                                              │
│  OUTPUT:                                                     │
│   • Model assignment matrix                                   │
│   • Estimated build cost (refined z faza 30)                  │
│   • Fallback chains per task type                             │
│   • Audit chain entry                                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 26.1.2. Wynik fazy 26 (DoD)

```
✓ Model assignment matrix complete
✓ Per-task type optimal model selected
✓ Fallback chains defined
✓ Cost estimate refined
✓ Quality requirements validated
✓ Audit chain entry: models_assigned
✓ Project state: READY_FOR_SKILL_SYNTHESIS
```

---

## 26.2. Per-task model assignment matrix

### 26.2.1. Task type taxonomy

Build phase ma typy tasks z różnymi requirements:

```
┌──────────────────────────────────────────────────────────────┐
│  Build Task Types                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CODE GENERATION                                             │
│   • Backend API endpoints (FastAPI/Express)                  │
│   • Frontend components (React/Vue)                           │
│   • Database migrations                                      │
│   • Configuration files                                      │
│   • DevOps scripts                                            │
│   Requirements: high accuracy, well-typed                    │
│                                                              │
│  TEST GENERATION                                             │
│   • Unit tests                                                │
│   • Integration tests                                        │
│   • E2E scenarios                                             │
│   • Human-like UI scenarios                                  │
│   Requirements: thorough, edge case coverage                  │
│                                                              │
│  DOCUMENTATION                                               │
│   • API docs                                                 │
│   • User docs (z Polish translation)                          │
│   • Developer docs                                            │
│   • Inline comments                                           │
│   Requirements: clear, accurate, audience-appropriate        │
│                                                              │
│  TRANSLATION                                                 │
│   • UI strings PL→EN                                          │
│   • Marketing copy EN→PL                                      │
│   • Customer-facing docs                                      │
│   Requirements: native-quality, context-aware                │
│                                                              │
│  REVIEW + ANALYSIS                                           │
│   • Code review                                              │
│   • Security review                                          │
│   • Performance analysis                                     │
│   • Accessibility audit                                      │
│   Requirements: deep reasoning, expertise                     │
│                                                              │
│  ORCHESTRATION                                               │
│   • Task decomposition                                       │
│   • Sub-task coordination                                    │
│   • Error recovery                                           │
│   Requirements: planning, judgment                           │
│                                                              │
│  GUARDS (parallel scaling)                                   │
│   • Coherence checks (per-file, per-module)                  │
│   • Cost monitoring (continuous)                             │
│   • Security scans (SAST, secret detection)                  │
│   • Quality verification (test results)                      │
│   • Provenance tracking (audit chain)                        │
│   Requirements: tier appropriate, scales z workers           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 26.2.2. Model assignment matrix

```
┌──────────────────────────────────────────────────────────────┐
│  Model Assignment — Customer Y CRM                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Task type            Primary             Fallback           │
│  ─────────────────  ─────────────────  ──────────────────│
│  Backend code        claude-sonnet       claude-haiku        │
│   (FastAPI routes)    ($0.40/component)   ($0.10)            │
│                                                              │
│  Frontend code       claude-sonnet       claude-haiku        │
│   (React TS)          ($0.50/component)   ($0.12)            │
│                                                              │
│  Database migrations claude-opus         claude-sonnet       │
│   (critical, careful) ($0.80/migration)   ($0.30)            │
│                                                              │
│  Unit tests          claude-haiku        claude-sonnet       │
│   (high volume)       ($0.08/file)        ($0.30)            │
│                                                              │
│  Integration tests   claude-sonnet       gpt-5              │
│                       ($0.40)             ($0.50)            │
│                                                              │
│  E2E + Human-like    claude-sonnet       claude-opus         │
│   UI scenarios        ($1.20/scenario)    ($2.40)            │
│                                                              │
│  PL documentation    bielik-11b lokalny  claude-sonnet       │
│   (Polish-native)     ($0)                ($0.30)            │
│                                                              │
│  EN documentation    claude-sonnet       gpt-5               │
│                       ($0.20)             ($0.30)            │
│                                                              │
│  PL ↔ EN translation bielik-11b lokalny  claude-sonnet       │
│                       ($0)                ($0.20)            │
│                                                              │
│  Code review         claude-opus         gpt-5              │
│   (deep)              ($1.20)             ($1.40)            │
│                                                              │
│  Security review     claude-opus         claude-sonnet       │
│   (critical, opus)    ($1.60)             ($0.60)            │
│                                                              │
│  Stripe integration  claude-opus         claude-sonnet       │
│   (precision needed)  ($1.00)             ($0.40)            │
│                                                              │
│  KSeF integration    claude-opus +       claude-sonnet       │
│   (Polish specific)   bielik-11b RAG      ($0.50)            │
│                       ($1.40)                                │
│                                                              │
│  Configuration       claude-haiku        claude-sonnet       │
│   (simple, free)      ($0.05)             ($0.20)            │
│                                                              │
│  Orchestration       claude-opus         claude-sonnet       │
│   (Council role)      (already ass'd)                        │
│                                                              │
│  Guards (Coherence)  bielik-11b lokalny  claude-sonnet       │
│   tier 1 quick        ($0)                ($0.20)            │
│                                                              │
│  Guards (Coherence)  claude-sonnet       claude-opus         │
│   tier 2 deep         ($0.30/check)       ($0.80)            │
│                                                              │
│  Guards (Security)   claude-opus         gpt-5               │
│   (compliance)        ($0.60)             ($0.80)            │
│                                                              │
│  Total estimated dla full build (1 worker, 1 env): ~$145     │
│  (See faza 28.4 dla parallel scaling)                        │
└──────────────────────────────────────────────────────────────┘
```

### 26.2.3. Per-module assignment

```
For each Księga module, system pre-assigns:

Module: "Customer Management" (z Księga Part IV)
  Components:
    • CustomerListPage.tsx       → claude-sonnet
    • CustomerEditForm.tsx       → claude-sonnet
    • CustomerService.py         → claude-sonnet
    • customer_routes.py         → claude-sonnet
    • CustomerSearch.tsx         → claude-sonnet
    • Customer.model.ts          → claude-sonnet
    • Customer migrations        → claude-opus (database changes)
  
  Tests:
    • Unit tests (12)            → claude-haiku
    • Integration tests (4)      → claude-sonnet
    • E2E tests (2)              → claude-sonnet
    • Human-like UI (4)          → claude-sonnet
  
  Documentation:
    • PL user docs               → bielik-11b
    • EN dev docs                → claude-sonnet
    • API docs                   → claude-sonnet
  
  Estimated module cost: $18.40 (single worker)
  Note: scales z parallel workers (see faza 28.4)
```

---

## 26.3. Cost optimization

### 26.3.1. Cost budget reconciliation

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Budget Reconciliation                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Project budget: $345 (z Księga, post-Council)               │
│                                                              │
│  Phase allocation (single-worker baseline):                  │
│   Council (already spent):    $14.20                         │
│   Planning (now):              $25.00                         │
│   Build (1 worker, 1 env):     $145.00                        │
│   Quality gates:               $35.00                         │
│   Deployment:                  $42.00                         │
│   Buffer (10%):                $30.00                         │
│   ─────────────────────────────────                         │
│   Total:                       $291.20                        │
│   Headroom:                    $53.80                         │
│                                                              │
│  Status: ✓ Within budget                                      │
│                                                              │
│  ⚡ NOTE: This is single-worker estimate.                     │
│   Parallel orchestration (faza 28.4) may change this:         │
│   • More workers = more parallel work = faster                │
│   • More workers = more Guards runs = +cost                   │
│   • More environments = +env cost + Guards multiplied         │
│   See faza 28.4 dla resource profile selection.               │
│                                                              │
│  Cost optimization opportunities (single worker):             │
│   💡 Use bielik more for PL tasks (saves ~$8)                │
│   💡 Cache common code patterns (saves ~$5 over project)     │
│   💡 Batch test generation (saves ~$3)                       │
│   Total potential savings: ~$16                               │
│                                                              │
│  [Apply optimizations]  [Skip]                               │
└──────────────────────────────────────────────────────────────┘
```

### 26.3.2. Cost-quality trade-off analysis

```
For each task type, system analyzes cost-quality trade-off:

  Backend code:
    claude-sonnet:  $0.40/component, 95% quality
    claude-haiku:   $0.10/component, 78% quality
    Trade-off: 4x cheaper, 17 points quality drop
    Recommendation: claude-sonnet (quality matters dla payment)
  
  Unit tests (high volume):
    claude-haiku:   $0.08/file, 82% quality
    claude-sonnet:  $0.30/file, 92% quality
    Trade-off: 3.75x more expensive, 10 points quality
    Recommendation: claude-haiku (volume + tests are verifiable)
  
  Configuration files:
    claude-haiku:   $0.05/file, 88% quality
    claude-sonnet:  $0.20/file, 95% quality
    Recommendation: claude-haiku (simple task, quality acceptable)
```

---

## 26.4. Quality requirements

### 26.4.1. Per-D-level quality matrix

```
D-level affects model selection:

  D1 Trivial:
   Default models: cheapest tier
   No premium models needed
  
  D2 Light:
   Default: cheap tier (haiku)
   Critical paths: standard (sonnet)
  
  D3 Standard:
   Default: standard tier (sonnet)
   Critical: premium (opus)
  
  D4 Production (Customer Y):
   Default: standard tier (sonnet)
   Critical: premium (opus)
   ALL security/compliance: premium (opus)
  
  D5 Mission-critical:
   Default: premium tier (opus)
   No cheap-tier models accepted
   Multi-model verification dla critical paths
```

### 26.4.2. Context-specific overrides

```
Some tasks override default per-D-level matrix:

  Always premium (regardless of D-level):
   • Database migrations (data integrity critical)
   • Security implementations
   • Payment processing code
   • Encryption code
   • Authentication flows
  
  Always cheap (regardless of D-level):
   • Configuration files
   • Lokalne dev tooling
   • Comments + simple docs
  
  Polish-specific (use bielik):
   • PL UI translations
   • PL user docs
   • PL marketing copy
   • Polish legal text
  
  Guards-specific:
   • Tier 1 quick checks: lokalne tier (free, fast)
   • Tier 2 deep checks: standard tier
   • Critical Guards (Security/Provenance): premium
   • External Guards models: +50-80% cost (see 28.4)
```

---

## 26.5. Edge Cases — Model Selection (15)

### Kategoria A — Assignment issues (4)

**EC-A1**: No suitable model dla task type
- Trigger: niche task no model excels at
- Akcje: best-available + manual review, fallback chain

**EC-A2**: Model deprecated mid-project
- Anthropic deprecates claude-sonnet during long project
- Akcje: migrate do successor, re-validate quality

**EC-A3**: Cost-quality conflict
- Quality requires opus, budget requires haiku
- Akcje: operator decision, scope cut, budget increase

**EC-A4**: Provider unavailable when needed
- Anthropic outage during critical task
- Akcje: fallback chain auto-activated, may delay task

### Kategoria B — Cost issues (4)

**EC-B1**: Estimated cost exceeds budget
- Tasks total $200, budget $145
- Akcje: cheaper models, scope cut, operator approves overrun

**EC-B2**: Cost variance high (uncertainty)
- Range $100-200 dla tasks (50% variance)
- Akcje: conservative estimate, more buffer

**EC-B3**: Cost surprise z task complexity
- Estimated $0.40, actual $1.20 dla complex component
- Akcje: re-estimate, calibrate, may switch model

**EC-B4**: Vendor pricing change
- Anthropic raises prices mid-project
- Akcje: re-estimate, may require operator approval

### Kategoria C — Quality issues (4)

**EC-C1**: Selected model produces poor quality
- claude-sonnet failures dla niche task (e.g., obscure framework)
- Akcje: switch to opus, manual review, find alternative

**EC-C2**: Quality varies by language
- Model excellent dla EN, weak dla PL
- Akcje: bielik dla PL, language-aware routing

**EC-C3**: Quality calibration outdated
- Old data shows model good, recent updates degraded
- Akcje: re-calibrate, A/B test, switch jeśli needed

**EC-C4**: Critical path under-resourced
- Important task assigned cheap model
- Akcje: upgrade dla critical paths, operator review

### Kategoria D — Recovery (3)

**EC-D1**: Assignment matrix corruption
- File damage, lost assignments
- Akcje: regenerate z templates + project context

**EC-D2**: Per-module assignment drift
- Some modules use wrong model (config changed)
- Akcje: validate, re-apply matrix, audit log

**EC-D3**: Operator wants override mid-build
- Wants premium dla all tasks (cost cap exceeded)
- Akcje: warning, approval flow, escalation

---

## 26.6. Acceptance + transition do fazy 27

```bash
$ aeis-cli phase26-acceptance-test --project proj_customer_y_crm

[1/6] Model assignment matrix complete                 ✓ PASS
[2/6] Per-task type optimal selected                   ✓ PASS
[3/6] Fallback chains defined                          ✓ PASS
[4/6] Cost estimate refined (single-worker baseline)   ✓ PASS ($145)
[5/6] Quality requirements validated                   ✓ PASS
[6/6] Audit chain entry models_assigned                ✓ PASS

DoD: 6/6 ✓
Phase 26 ACCEPTED. Ready dla Phase 27 (Skill Synthesis).
```

---

# FAZA 27 — Skill Synthesis

> **Spis sekcji**:
> - 27.1 — Sense fazy + skill extraction z Księga
> - 27.2 — Skill identification workflow
> - 27.3 — Skill creation per project
> - 27.4 — Promotion do Personal skills
> - 27.5 — Edge cases (15) + transition do fazy 28

---

## 27.1. Sens fazy

### 27.1.1. Co Faza 27 robi

Faza 27 analizuje Księgę i wyciąga wzorce nadające się do **skill
extraction**. Skill = reusable capability (z faza 11). Lepiej zrobić
skills raz i reuse niż ad-hoc każdym razem.

```
┌──────────────────────────────────────────────────────────────┐
│  Skill Synthesis — extract reusable capabilities             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT:                                                      │
│   • Księga (Part III + IV — architecture + implementation)   │
│   • Operator's existing skills library (z faza 11)            │
│   • Marketplace skills (community + verified)                 │
│                                                              │
│  PROCESSING:                                                 │
│   • Pattern detection w Księga                                │
│   • Cross-reference z existing skills                        │
│   • Identify gaps                                             │
│   • Suggest new skills                                        │
│   • Operator approves/customizes                              │
│                                                              │
│  OUTPUT:                                                     │
│   • Project skills (scoped do this project)                  │
│   • Promoted skills (do Personal library)                    │
│   • Imported skills (from marketplace)                        │
│   • Skill assignments per Księga module                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 27.1.2. Wynik fazy 27 (DoD)

```
✓ Pattern analysis complete
✓ New skills created (jeśli needed)
✓ Existing skills mapped do project tasks
✓ Marketplace imports done (jeśli applicable)
✓ Skill quality validated
✓ Audit chain entry: skills_synthesized
✓ Project state: READY_FOR_MASTERPLAN
```

---

## 27.2. Skill identification workflow

### 27.2.1. Pattern detection

System analizuje Księgę szukając patterns:

```
┌──────────────────────────────────────────────────────────────┐
│  Skill Synthesis Pattern Detection                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Patterns detected w Księga:                                  │
│                                                              │
│  ┌─ PATTERN 1: KSeF invoice generation (high frequency) ─┐  │
│  │  Mentions: 12 times across Księga                       │  │
│  │  Operations:                                            │  │
│  │   • Generate FA(2) format invoice                       │  │
│  │   • Sign z qualified certificate                        │  │
│  │   • Submit do KSeF API                                  │  │
│  │   • Handle KSeF responses                               │  │
│  │   • Archive z 5-year retention                          │  │
│  │                                                         │  │
│  │  Existing skill match:                                  │  │
│  │   ✓ "Generate Polish KSeF invoice" (System, v2.3)       │  │
│  │   Coverage: ~85%                                        │  │
│  │   Gap: customer's specific NIP handling                 │  │
│  │                                                         │  │
│  │  Recommendation:                                        │  │
│  │   [Use system skill + customize]                        │  │
│  │   [Fork skill dla project-specific]                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ PATTERN 2: Customer data validation ──────────────────┐  │
│  │  Mentions: 8 times                                      │  │
│  │  Operations:                                            │  │
│  │   • Validate Polish identifiers (PESEL/NIP/REGON)       │  │
│  │   • Validate addresses (Polish format)                  │  │
│  │   • Validate phone numbers (+48)                        │  │
│  │   • Email validation                                    │  │
│  │                                                         │  │
│  │  Existing skill match:                                  │  │
│  │   ✓ "Validate Polish identifiers" (System, v1.2)        │  │
│  │   Coverage: ~70% (missing address + email validations)  │  │
│  │                                                         │  │
│  │  Recommendation:                                        │  │
│  │   [Create project skill: "Customer Y data validation"]  │  │
│  │       Wraps system skill + adds missing validations     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ PATTERN 3: Stripe payment integration ────────────────┐  │
│  │  Mentions: 6 times                                      │  │
│  │  Operations:                                            │  │
│  │   • Create payment intent                               │  │
│  │   • Generate payment link                               │  │
│  │   • Handle webhooks                                     │  │
│  │   • Process refunds                                     │  │
│  │                                                         │  │
│  │  Existing skill match:                                  │  │
│  │   ✓ "Generate Stripe webhook handler" (System)          │  │
│  │   ✓ "Stripe payment integration" (Marketplace, ★★★★★)   │  │
│  │   Combined coverage: ~95%                               │  │
│  │                                                         │  │
│  │  Recommendation:                                        │  │
│  │   [Import marketplace skill + use system skill]         │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ PATTERN 4: Customer Y branding ────────────────────────┐ │
│  │  Mentions: 4 times                                      │  │
│  │  Operations:                                            │  │
│  │   • Apply customer color palette                        │  │
│  │   • Apply customer logo                                 │  │
│  │   • Customer-specific typography                        │  │
│  │                                                         │  │
│  │  Existing skill match:                                  │  │
│  │   ✗ No match                                            │  │
│  │                                                         │  │
│  │  Recommendation:                                        │  │
│  │   [Create project skill: "Customer Y branding"]         │  │
│  │       Project-scoped (operator decyduje promote later)  │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  Total patterns: 8                                           │
│   • 3 covered by existing skills                              │
│   • 2 need import from marketplace                            │
│   • 3 need new project skills                                 │
│                                                              │
│  Estimated skill creation cost: $4-8                         │
│                                                              │
│  [Approve recommendations]  [Customize per pattern]          │
└──────────────────────────────────────────────────────────────┘
```

### 27.2.2. Operator review of patterns

```
Per pattern, operator może:
  
  • Accept recommendation (default)
  • Customize approach
  • Skip pattern (handle ad-hoc)
  • Request more patterns (deeper analysis)
  
After approval, system creates/imports skills as needed.
```

---

## 27.3. Skill creation per project

### 27.3.1. Project skill creation example

```
┌──────────────────────────────────────────────────────────────┐
│  Create Project Skill — "Customer Y Branding"                │
│                                                              │
│  Context: extracted from Księga Part III (UI design)          │
│                                                              │
│  Skill definition:                                           │
│                                                              │
│   Name: customer_y_branding                                  │
│   Type: Project (scoped do Customer Y CRM)                   │
│   Lifecycle: project_complete (auto-cleanup po closure)      │
│                                                              │
│   Inputs:                                                    │
│    • component_type: "form|button|card|page"                  │
│    • content: <component spec>                               │
│    • theme_mode: "light|dark"                                 │
│                                                              │
│   Outputs:                                                   │
│    • component_with_branding: React TS component             │
│                                                              │
│   Configuration:                                             │
│    Brand colors:                                             │
│      Primary: #1e40af (Customer Y blue)                      │
│      Secondary: #f59e0b (Customer Y gold)                    │
│      Background light: #fafafa                               │
│      Background dark: #0f172a                                │
│    Typography:                                               │
│      Headings: "Inter, sans-serif"                            │
│      Body: "system-ui, sans-serif"                            │
│    Logo: customer_y_logo.svg                                  │
│                                                              │
│   Prompt template:                                            │
│   ┌────────────────────────────────────────────────────────┐ │
│   │ Generate React TypeScript {component_type} z apply    │ │
│   │ Customer Y branding:                                   │ │
│   │  • Primary color: {primary_color}                      │ │
│   │  • Secondary color: {secondary_color}                  │ │
│   │  • Typography: {typography}                            │ │
│   │  • Logo placement: {logo_placement}                    │ │
│   │  • Theme mode: {theme_mode}                            │ │
│   │                                                        │ │
│   │ Component spec:                                        │ │
│   │ {content}                                              │ │
│   │                                                        │ │
│   │ Apply Tailwind classes z customer's color tokens.     │ │
│   │ Ensure WCAG 2.1 AA contrast ratios.                   │ │
│   └────────────────────────────────────────────────────────┘ │
│                                                              │
│   Default model: claude-sonnet                                │
│   Estimated cost: ~$0.40 per use                              │
│   Expected uses w project: ~30 components                     │
│   Total skill cost dla project: ~$12                          │
│                                                              │
│  Alternative: use existing "Generate React component" +      │
│  custom CSS module dla branding (less reusable, 30% cheaper) │
│                                                              │
│  [Create skill]  [Use alternative]  [Customize]              │
└──────────────────────────────────────────────────────────────┘
```

### 27.3.2. Skill assignments per Księga module

Po skill creation, system assigns skills per module:

```
Module: Customer Management
  Skills assigned:
    • customer_y_branding (project) — UI components
    • polish_data_validation (system+ext) — input validation
    • Generate React component (system) — base components
    • Generate FastAPI route (system) — backend endpoints
  
Module: Invoicing
  Skills assigned:
    • Generate Polish KSeF invoice (system, v2.3) — invoice gen
    • customer_y_branding (project) — UI
    • Generate FastAPI route (system) — backend
  
Module: Payment
  Skills assigned:
    • Stripe payment integration (marketplace, ★★★★★) — Stripe
    • Generate webhook handler (system) — webhooks
    • customer_y_branding (project) — UI
```

---

## 27.4. Promotion do Personal skills

### 27.4.1. Promotion workflow

Niektóre project skills mogą być promowane do Personal library jeśli
operator widzi reuse potential:

```
┌──────────────────────────────────────────────────────────────┐
│  Skill Promotion Decision                                    │
│                                                              │
│  Project skill: "Customer Y branding"                         │
│                                                              │
│  Promotion analysis:                                         │
│   • Reuse potential: medium                                   │
│      Customer-specific, but pattern useful dla future        │
│      branded customer projects                               │
│   • Operator's similar projects: 2 (other branded SaaS)      │
│   • Generalization possible: yes                              │
│      Convert "Customer Y branding" do "Customer-branded UI"  │
│      z customer config parameter                             │
│                                                              │
│  Promotion options:                                          │
│   [● Keep project-scoped (cleanup po closure)]                │
│       Simpler, but lose reuse                                │
│   [○ Promote do Personal (z generalization)]                 │
│       Customer config externalized                           │
│       Reusable dla future branded customers                  │
│       Estimated effort: 2 hours dla generalization            │
│   [○ Promote do Personal (specific Customer Y, kept as-is)]  │
│       Reusable jeśli future Customer Y projects               │
│       No generalization effort                                │
│                                                              │
│  Operator decision:                                           │
│   [Promote z generalization (recommended)]                    │
│   [Keep project-scoped]                                       │
└──────────────────────────────────────────────────────────────┘
```

### 27.4.2. Promotion tracking

```
Personal skills library updates:

  Promoted skills in this project: 1
   • customer_y_branding → "Customer-branded UI" (Personal v1.0)
  
  Imported skills: 1
   • Stripe payment integration (Marketplace v3.2)
  
  System skill enhancements: 0
   (no operator improvements made)
  
  Project skills (cleanup po closure): 2
   • polish_data_validation_extended
   • customer_y_specific_workflows
```

---

## 27.5. Edge Cases — Skill Synthesis (15)

### Kategoria A — Pattern detection (4)

**EC-A1**: Pattern too vague
- LLM identifies "data handling" but unclear what skill needed
- Akcje: refine analysis z more context, operator clarifies

**EC-A2**: Pattern matches existing skill poorly
- 60% match — partial fit
- Akcje: fork skill, augment, manual decision

**EC-A3**: Multiple skills could fit pattern
- 3 different skills overlap
- Akcje: present options, operator chooses

**EC-A4**: No pattern detected for major feature
- Faza missed important pattern operator expects
- Akcje: re-analyze z hints, operator manually adds skill

### Kategoria B — Skill creation issues (4)

**EC-B1**: Project skill prompt low quality
- Generated prompt produces bad output
- Akcje: refine z few-shot examples, operator manual improvement

**EC-B2**: Skill cost overrun w testing
- Skill expensive na test runs
- Akcje: cheaper model, refine prompt, accept

**EC-B3**: Skill output format inconsistent
- LLM returns varied structure
- Akcje: stricter prompts, JSON enforcement, validation

**EC-B4**: Skill conflicts z existing
- Project skill duplicates system skill
- Akcje: use existing instead, document why duplicate

### Kategoria C — Marketplace import issues (4)

**EC-C1**: Marketplace skill outdated
- Imported skill nie pasuje do current AEIS
- Akcje: skip import, find alternative, fork

**EC-C2**: Marketplace skill author unresponsive
- Bug w skill, no fix forthcoming
- Akcje: fork + fix, find alternative

**EC-C3**: Marketplace skill pricing changed
- Was free, now paid
- Akcje: alternative free skill, accept paid, build own

**EC-C4**: License conflict
- Marketplace skill GPL, project commercial
- Akcje: skip skill, find permissive-licensed alternative

### Kategoria D — Recovery (3)

**EC-D1**: Skill creation interrupted
- Crash during synthesis
- Akcje: resume from checkpoint, partial state

**EC-D2**: Skill assignments lost
- Skills assigned per module, file corrupted
- Akcje: regenerate z Księga + skill library

**EC-D3**: Promoted skill rolled back
- Operator wants promote-then-revert
- Akcje: rollback, audit log

---

## 27.6. Acceptance + transition do fazy 28

```bash
$ aeis-cli phase27-acceptance-test --project proj_customer_y_crm

[1/6] Pattern analysis complete                        ✓ PASS (8 patterns)
[2/6] Skills created/imported/assigned                 ✓ PASS
[3/6] Skill assignments per Księga module              ✓ PASS
[4/6] Skill quality validated                          ✓ PASS
[5/6] Promotion decisions logged                       ✓ PASS
[6/6] Audit chain entry skills_synthesized             ✓ PASS

DoD: 6/6 ✓
Phase 27 ACCEPTED. Ready dla Phase 28 (Masterplan Synthesis).
```

---

# FAZA 28 — Masterplan Synthesis

> **Spis sekcji**:
> - 28.1 — Sense fazy + masterplan jako concrete plan
> - 28.2 — Masterplan structure
> - 28.3 — Dependency graph generation
> - **28.4 — Layer/Module Decomposition + Parallel Orchestration** ⚡ NOWE
> - 28.5 — Resource configuration matrix (5 profiles)
> - 28.6 — Throughput-driven timeline
> - 28.7 — Guards cost scaling
> - 28.8 — Operator decision interface
> - 28.9 — Operator review + signoff
> - 28.10 — Edge cases (22) + transition do fazy 29

---

## 28.1. Sens fazy

### 28.1.1. Masterplan vs Księga

```
KSIĘGA (faza 25):
  • Project specification (WHAT)
  • All features described
  • Architecture defined
  • 60-100 pages

MASTERPLAN (faza 28):
  • Build orchestration plan (HOW + WHEN + Z ILU WORKERS)
  • Layer + module decomposition
  • Dependency graph
  • Throughput-driven timeline
  • Resource profile selected
  • Guards cost scaling
  • 25-35 pages
  
Different artifacts dla different purposes.
```

### 28.1.2. Wynik fazy 28 (DoD)

```
✓ Masterplan generated
✓ Layer + module decomposition complete
✓ Dependency graph computed (z parallelizability)
✓ Resource profile selected (operator)
✓ Throughput-driven timeline established
✓ Guards cost scaling computed
✓ Critical path identified
✓ Operator signed off
✓ Audit chain entry: masterplan_finalized
✓ Project state: READY_FOR_TEST_PLAN
```

---

## 28.2. Masterplan structure

### 28.2.1. Standard sections (updated)

```
MASTERPLAN — Customer Y CRM (z layer decomposition)

1. EXECUTIVE OVERVIEW
   • Selected resource profile
   • Total duration (z chosen profile)
   • Total tasks
   • Total cost (build + Guards scaled)
   • Critical path identified
   1 page

2. WORK BREAKDOWN STRUCTURE (WBS)
   2.1 Per phase rough plan
   2.2 Per layer detailed
   ~6-8 pages

3. DEPENDENCY GRAPH
   • Layer-level dependencies
   • Module-level dependencies
   • Critical path highlighted
   • Parallel work opportunities
   ~3-4 pages

4. LAYER + MODULE DECOMPOSITION (NEW SECTION 28.4)
   • 8 layers Księgi
   • Per-layer parallelizability
   • Per-module work units
   • Resource requirements per layer
   ~4-5 pages

5. RESOURCE CONFIGURATION (NEW)
   • 5 predefined profiles
   • Custom profile builder
   • Trade-off analysis
   ~2-3 pages

6. THROUGHPUT-DRIVEN TIMELINE (NEW)
   • Profile-specific timeline
   • Critical path narrowing
   • Operator availability constraints
   ~2-3 pages

7. GUARDS COST SCALING (NEW)
   • Per-profile Guards costs
   • External vs lokalne models cost impact
   • Continuous vs phase-boundary scaling
   ~2 pages

8. RISK-AWARE SEQUENCING
   • High-risk tasks early (R1 KSeF, R2 Stripe)
   • Mitigations interleaved
   • Buffer dla unknowns
   ~2 pages

9. MILESTONES + GATES
   • Per-profile milestones
   • Operator approval gates
   ~1 page

10. APPENDICES
    A. Detailed task list (47 tasks)
    B. Per-task estimates (cost + time)
    C. Skill assignments
    D. Reference do Księga sections
    E. Cost trade-off scenarios
    ~5 pages

Total: 28-35 pages (z layer decomposition + parallel)
```

---

## 28.3. Dependency graph

### 28.3.1. Dependency graph visualization

```
┌──────────────────────────────────────────────────────────────┐
│  Dependency Graph — Customer Y CRM                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1 (Foundation):                                       │
│   db_schema ──→ migrations ──→ auth_setup                    │
│                              ──→ api_skeleton ──→ ...        │
│                              ──→ frontend_setup ──→ ...      │
│                                                              │
│  Phase 2 (KSeF) — depends on db_schema, api_skeleton:        │
│   ksef_poc ──→ ksef_fa2_gen ──→ ksef_sandbox_test            │
│                              ──→ ksef_archive_setup          │
│                                                              │
│  Phase 3 (Core) — depends on Phase 1 + 2:                    │
│   customer_mgmt ──→ customer_search ──→ customer_export      │
│                                                              │
│  Phase 4 (Payment) — depends on Phase 1 (auth) + 3 (cust):   │
│   stripe_integration ──→ payment_webhooks ──→ refunds        │
│                                                              │
│  Phase 5 (UX/I18n) — parallel z Phase 4:                     │
│   branding_apply ──→ i18n_strings ──→ wcag_audit             │
│                                                              │
│  Phase 6 (Quality + Deploy) — depends on all previous:       │
│   integration_tests ──→ performance_tests ──→ deploy_prod    │
│                                                              │
│                                                              │
│  CRITICAL PATH (longest, sekwencyjne):                       │
│   db_schema → ksef_poc → ksef_fa2_gen → customer_mgmt        │
│   → invoice_module → stripe_integration → integration_tests  │
│   → deploy_prod                                              │
│                                                              │
│   Critical path duration (single worker): 320 hours          │
│   Critical path duration (3 workers): 280 hours              │
│   Critical path duration (8 workers): 240 hours              │
│   (Critical path nie scales linearly — dependencies)          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.3.2. Parallelizable vs sequential branches

```yaml
dependency_graph:
  layers:
    - id: layer_0_foundation
      parallelizability: sequential  # ⚠ MUST be done one-by-one
      tasks: [db_schema, migrations, auth_setup, api_skeleton]
      reason: "Each task depends on previous"
      total_hours: 16
      
    - id: layer_2_integration
      parallelizability: full_parallel  # ✓ Independent integrations
      tasks: [ksef_integration, stripe_integration, mailjet_integration]
      reason: "Each integration is isolated"
      total_hours: 24
      max_concurrent: 3 (each integration on own worker)
      
    - id: layer_3_api_endpoints
      parallelizability: high_parallel  # Up to N workers
      tasks: [customer_routes, invoice_routes, payment_routes, ...]
      reason: "Independent endpoints, share schema"
      total_hours: 32
      max_concurrent: 8 (limited by code review bandwidth)
      
    - id: layer_4_frontend
      parallelizability: high_parallel
      tasks: [list_page, edit_form, ...]
      reason: "Independent components"
      max_concurrent: 8
      
    - id: layer_5_unit_tests
      parallelizability: full_parallel
      tasks: [...] # one per source file
      max_concurrent: 16  # very high parallelism
      
    - id: layer_6_integration_tests
      parallelizability: low_parallel
      tasks: [api_contract, e2e_journey, ...]
      max_concurrent: 2  # share test environment
```

---

## 28.4. Layer/Module Decomposition + Parallel Orchestration ⚡ NOWE

### 28.4.1. Why layer decomposition matters

Single-worker timeline (oryginalna versja fazy 28) zakładała sekwencyjne
prace. Rzeczywistość:

```
┌──────────────────────────────────────────────────────────────┐
│  Same project, different orchestration                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1 worker, 1 env:                                            │
│   • Wszystko sekwencyjne                                     │
│   • Timeline: 8.5 weeks                                      │
│   • Cost: $145 build + $20 Guards = $165                     │
│   • Operator: 15-25 interactions                             │
│                                                              │
│  3 workers, 1 env:                                            │
│   • Layers 3-5 parallelized                                  │
│   • Timeline: 4 weeks (✓ szybciej)                           │
│   • Cost: $145 build + $40 Guards = $185 (✗ więcej Guards)   │
│   • Operator: 20-30 interactions (więcej coord)              │
│                                                              │
│  8 workers, 3 envs:                                           │
│   • Maximum parallel                                         │
│   • Timeline: 1.5 weeks                                      │
│   • Cost: $145 build + $80 Guards + $30 envs = $255         │
│   • Operator: 30-40 interactions (intense coord)             │
│   • Risk: harder to spot issues, more rework                 │
│                                                              │
│  Trade-off: time vs cost vs operator effort vs risk          │
└──────────────────────────────────────────────────────────────┘
```

### 28.4.2. Layer decomposition Księgi

System dzieli Księgę na **8 layers** based on architectural concerns:

```
┌──────────────────────────────────────────────────────────────┐
│  Księga Layer Decomposition                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  LAYER 0 — FOUNDATION                                        │
│   Parallelizability: SEQUENTIAL (cannot parallelize)         │
│   Components:                                                │
│    • Database schema design                                   │
│    • Initial migrations                                      │
│    • Environment configuration                                │
│    • Core dependencies                                        │
│   Total work: 16 hours                                       │
│   Critical: yes (everything depends on this)                 │
│   Worker assignment: 1 worker only                           │
│                                                              │
│  LAYER 1 — CORE DOMAIN                                       │
│   Parallelizability: PARTIAL_PARALLEL (max 2-3 workers)      │
│   Components:                                                │
│    • Domain models (Customer, Invoice, Payment)               │
│    • Core services                                           │
│    • Authentication/authorization core                        │
│   Total work: 32 hours                                       │
│   Critical: yes                                              │
│   Worker assignment: 2-3 (shared core)                        │
│                                                              │
│  LAYER 2 — INTEGRATIONS                                      │
│   Parallelizability: FULL_PARALLEL (up to 5 workers)         │
│   Components:                                                │
│    • Stripe integration (isolated)                            │
│    • KSeF integration (isolated)                              │
│    • Mailjet integration (isolated)                           │
│    • Cloudflare integration (isolated)                        │
│   Total work: 48 hours                                       │
│   Critical: KSeF (R1 risk)                                    │
│   Worker assignment: 1 worker per integration (4 parallel)    │
│                                                              │
│  LAYER 3 — API ENDPOINTS                                     │
│   Parallelizability: HIGH_PARALLEL (up to 8 workers)         │
│   Components:                                                │
│    • Customer routes (5 endpoints)                            │
│    • Invoice routes (8 endpoints)                             │
│    • Payment routes (6 endpoints)                             │
│    • Auth routes (4 endpoints)                                │
│    • ... (47 endpoints total)                                 │
│   Total work: 64 hours                                       │
│   Critical: payment routes (R2 risk)                          │
│   Worker assignment: up to 8 workers (independent endpoints) │
│                                                              │
│  LAYER 4 — FRONTEND                                          │
│   Parallelizability: HIGH_PARALLEL (up to 8 workers)         │
│   Components:                                                │
│    • Components (28 components)                               │
│    • Pages (15 pages)                                         │
│    • State management (3 modules)                             │
│    • Routing (1 module)                                       │
│   Total work: 80 hours                                       │
│   Critical: customer-facing pages                             │
│   Worker assignment: up to 8 workers                          │
│                                                              │
│  LAYER 5 — UNIT TESTS                                        │
│   Parallelizability: FULL_PARALLEL (up to 16 workers)        │
│   Components:                                                │
│    • Backend unit tests (95 tests)                            │
│    • Frontend unit tests (92 tests)                           │
│   Total work: 32 hours                                       │
│   Critical: no (auto-generated)                              │
│   Worker assignment: high parallel (limited by review)       │
│                                                              │
│  LAYER 6 — INTEGRATION + E2E TESTS                           │
│   Parallelizability: LOW_PARALLEL (max 2 workers)            │
│   Components:                                                │
│    • API contract tests (24 tests)                            │
│    • E2E user journeys (23 scenarios)                         │
│    • Human-like UI tests (32 scenarios)                       │
│    • Cross-module integration                                │
│   Total work: 48 hours                                       │
│   Critical: yes (integration validates everything)           │
│   Worker assignment: max 2 (share test env)                   │
│                                                              │
│  LAYER 7 — DEPLOYMENT                                        │
│   Parallelizability: LOW_PARALLEL (max 2 workers)            │
│   Components:                                                │
│    • Docker setup                                             │
│    • CI/CD pipeline                                           │
│    • Monitoring + alerting                                    │
│    • Customer training docs                                   │
│   Total work: 24 hours                                       │
│   Critical: yes (final delivery)                              │
│   Worker assignment: 1-2 (sekwencyjne stages)                │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  TOTAL WORK: 344 hours                                       │
│  CRITICAL PATH: Layer 0 → Layer 1 (core) → Layer 2 (KSeF) →  │
│                  Layer 3 (KSeF endpoints) → Layer 6 (integ) → │
│                  Layer 7 (deploy)                             │
│  CRITICAL PATH HOURS: 168 (jeśli sequencjnie)                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.4.3. Parallelizability classification

```
Parallelizability levels:

  SEQUENTIAL (1 worker only):
   Reason: each task depends on previous
   Examples: db_schema → migrations → ORM
   Cannot be sped up by adding workers
  
  PARTIAL_PARALLEL (2-3 workers):
   Reason: some sharing, but multiple chunks can be worked on
   Examples: core domain models (Customer + Invoice + Payment)
   Modest speedup z extra workers
  
  LOW_PARALLEL (max 2-3 workers):
   Reason: shared resources (test env, deploy pipeline)
   Examples: integration tests, deploy stages
   Limited speedup
  
  FULL_PARALLEL (up to 5):
   Reason: independent units
   Examples: integrations (Stripe vs KSeF vs Mailjet)
   Linear speedup
  
  HIGH_PARALLEL (up to 8):
   Reason: many independent components
   Examples: API endpoints, frontend components
   Near-linear speedup, limited by review bandwidth
  
  EXTREME_PARALLEL (up to 16+):
   Reason: very high independence + auto-generation
   Examples: unit test generation
   Limited by GPU/API rate limits
```

### 28.4.4. Module-level work decomposition

Per layer, system rozpisuje moduły z atomic units of work:

```
Layer 4 (Frontend) detailed:

  Module: Customer Management UI
   Atomic units (1-3 hours each):
    • CustomerListPage component (3h)
    • CustomerEditForm component (2h)
    • CustomerSearchBar component (1h)
    • CustomerDeleteDialog component (1h)
    • CustomerListItem component (1h)
   Total: 8h
   Parallelizability: HIGH_PARALLEL (5 workers possible)
   Estimated cost (5 workers, claude-sonnet): $4
   Wallclock z 1 worker: 8h
   Wallclock z 5 workers: ~2h
  
  Module: Invoice Creation UI
   Atomic units:
    • InvoiceCreatePage (4h)
    • InvoiceLineItemsForm (3h)
    • InvoicePreview component (2h)
    • InvoiceTemplateSelector (2h)
    • TaxCalculator hook (1h)
   Total: 12h
   Parallelizability: HIGH_PARALLEL
   Wallclock z 1 worker: 12h
   Wallclock z 5 workers: ~3h
  
  ... (per module)
  
  TOTAL Layer 4: 80h work, max parallel 8 workers
  Wallclock z 1 worker: 80h
  Wallclock z 8 workers: 12h (overhead, coordination)
```

---

## 28.5. Resource configuration matrix (5 profiles)

### 28.5.1. Pre-defined profiles

```
┌──────────────────────────────────────────────────────────────┐
│  Resource Profiles — Customer Y CRM                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PROFILE 1: SOLO BUDGET                                      │
│   Workers: 1                                                 │
│   Environments: 1 (dev only, deploy via local)                │
│   Guards: lokalne (free)                                     │
│   ──────────────────────                                     │
│   Build cost:    $145                                        │
│   Guards cost:   $5 (lokalne, low frequency)                 │
│   Env cost:      $0                                          │
│   Total cost:    $150                                        │
│   Timeline:      8.5 weeks                                   │
│   Operator:      15-25 interactions                          │
│   Risk:          medium (long timeline, market changes)      │
│                                                              │
│  PROFILE 2: SOLO BALANCED (default rec.)                     │
│   Workers: 2                                                 │
│   Environments: 1 (dev) + staging                             │
│   Guards: hybrid (lokalne T1 + sonnet T2)                     │
│   ──────────────────────                                     │
│   Build cost:    $148                                        │
│   Guards cost:   $25 (more frequent T2 deeper checks)        │
│   Env cost:      €15 (~$16 staging Hetzner CX21)             │
│   Total cost:    $189                                        │
│   Timeline:      4-5 weeks                                   │
│   Operator:      20-30 interactions                          │
│   Risk:          low-medium                                  │
│                                                              │
│  PROFILE 3: BURST PARALLEL                                    │
│   Workers: 4                                                 │
│   Environments: 2 (dev + staging) + per-worker isolated       │
│   Guards: standard (claude-sonnet T2 default)                │
│   ──────────────────────                                     │
│   Build cost:    $152                                        │
│   Guards cost:   $50 (4x workers = 4x continuous checks)     │
│   Env cost:      $30                                         │
│   Total cost:    $232                                        │
│   Timeline:      2-3 weeks                                   │
│   Operator:      25-35 interactions                          │
│   Risk:          medium (more coordination needed)           │
│                                                              │
│  PROFILE 4: MAXIMUM PARALLEL                                  │
│   Workers: 8                                                 │
│   Environments: 3 (dev + staging + prod-ready)                │
│   Guards: premium (opus dla critical, sonnet dla rest)       │
│   ──────────────────────                                     │
│   Build cost:    $158                                        │
│   Guards cost:   $95 (max parallel = max checks)             │
│   Env cost:      $50                                         │
│   Total cost:    $303                                        │
│   Timeline:      1-1.5 weeks                                 │
│   Operator:      30-45 interactions (intense)                │
│   Risk:          medium-high (rapid changes)                 │
│                                                              │
│  PROFILE 5: ENTERPRISE PARALLEL                               │
│   Workers: 16                                                │
│   Environments: 5 (dev + 2 staging + 2 prod-ready)            │
│   Guards: premium z external models verification              │
│   ──────────────────────                                     │
│   Build cost:    $175                                        │
│   Guards cost:   $180 (external models +50-80% cost)         │
│   Env cost:      $80                                         │
│   Total cost:    $435                                        │
│   Timeline:      4-6 days                                    │
│   Operator:      40-60 interactions                          │
│   Risk:          high (very rapid, less time to spot issues) │
│                                                              │
│  CUSTOM PROFILE:                                             │
│   [Define your own combination]                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.5.2. Profile selection UI

```
┌──────────────────────────────────────────────────────────────┐
│  Resource Profile Selection                                  │
│                                                              │
│  Project budget: $345                                        │
│  Customer deadline: 8 weeks                                   │
│                                                              │
│  Budget-feasible profiles:                                    │
│   ✓ Profile 1 (Solo budget):     $150 / 8.5 weeks ⚠ tight    │
│   ✓ Profile 2 (Solo balanced):   $189 / 4-5 weeks ✓ optimal  │
│   ✓ Profile 3 (Burst parallel):  $232 / 2-3 weeks ✓ fast     │
│   ⚠ Profile 4 (Max parallel):    $303 / 1-1.5 weeks (+88%)   │
│   ✗ Profile 5 (Enterprise):      $435 / 4-6 days (over budget)│
│                                                              │
│  Recommendation: Profile 2 (Solo balanced)                   │
│  Reasoning:                                                  │
│   • Budget headroom comfortable                              │
│   • Timeline well within deadline                            │
│   • Operator interactions manageable                          │
│   • Risk profile acceptable                                  │
│                                                              │
│  Cost vs time visualization:                                 │
│                                                              │
│  Time (weeks)                                                │
│   8 │ ●Profile 1                                              │
│   6 │                                                        │
│   4 │      ●Profile 2 (recommended)                          │
│   3 │                                                        │
│   2 │           ●Profile 3                                    │
│   1 │                  ●Profile 4                            │
│ 0.5 │                         ●Profile 5                     │
│     └────────────────────────────────────                    │
│      $150  $200  $250  $300  $350  $400  $450               │
│                       Cost                                   │
│                                                              │
│  Customer-specific considerations:                           │
│   ☑ Customer Y deadline 8 weeks (Profile 1 risky)             │
│   ☑ Customer-funded €500 (Profile 4 risky bez approval)       │
│   ☑ Customer prefers transparency (more workers = more       │
│      Guards = more visibility)                                │
│                                                              │
│  Operator availability:                                      │
│   Available: ~10h over 8 weeks                                │
│   Profile 2: 25 interactions × 15 min = 6.25h ✓              │
│   Profile 4: 40 interactions × 15 min = 10h ⚠ tight           │
│                                                              │
│  Akcje:                                                      │
│   [● Use Profile 2 (Solo balanced) — recommended]            │
│   [○ Use Profile 1 (Solo budget) — tight timeline]           │
│   [○ Use Profile 3 (Burst parallel) — faster, +$43]          │
│   [○ Use Profile 4 (Max parallel) — fastest, requires        │
│       customer approval dla overrun]                          │
│   [○ Build custom profile]                                    │
│                                                              │
│  [Confirm selection]  [Show detailed breakdown]              │
└──────────────────────────────────────────────────────────────┘
```

### 28.5.3. Custom profile builder

```
┌──────────────────────────────────────────────────────────────┐
│  Custom Profile Builder                                      │
│                                                              │
│  Workers configuration:                                       │
│   Number of workers: [3 ▼]                                    │
│   Worker types:                                               │
│    ☑ 2 backend workers (Python)                               │
│    ☑ 1 frontend worker (TypeScript)                           │
│    ☐ Test-specific worker                                     │
│                                                              │
│  Environments configuration:                                  │
│   ☑ Development (1 instance)                                  │
│   ☑ Staging (1 instance)                                      │
│   ☐ Production preview                                        │
│   ☐ Per-worker isolated environments                          │
│                                                              │
│  Guards configuration:                                        │
│   Coherence Guard:                                            │
│    Tier 1 frequency: [continuous ▼]                          │
│    Tier 2 frequency: [phase boundaries ▼]                    │
│    Default models: [bielik T1 + sonnet T2 ▼]                 │
│   Cost Guard: continuous (mandatory)                          │
│   Security Guard:                                             │
│    Frequency: [phase boundaries + critical paths ▼]          │
│    Models: [opus (premium) ▼]                                │
│   Quality Guard: [per-test-run ▼]                             │
│   Provenance Guard: continuous (mandatory)                    │
│                                                              │
│  External vs lokalne models:                                  │
│   ☑ Use lokalne models gdzie possible (cost saving)           │
│   ☐ Premium external dla all Guards (better detection)       │
│                                                              │
│  Cost estimate (live):                                        │
│   Build:   $148                                              │
│   Guards:  $42                                               │
│   Envs:    $25                                               │
│   Total:   $215                                              │
│   Timeline: 3-4 weeks                                        │
│                                                              │
│  [Save custom profile]  [Reset]                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 28.6. Throughput-driven timeline

### 28.6.1. Timeline calculation model

```
┌──────────────────────────────────────────────────────────────┐
│  Timeline Calculation Model                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per layer wallclock time:                                    │
│                                                              │
│   layer_time = max(                                          │
│     critical_path_within_layer,                               │
│     total_layer_work / parallel_capacity                      │
│   ) × throughput_factor                                       │
│                                                              │
│  Where:                                                      │
│   parallel_capacity = min(                                    │
│     layer.max_concurrent,                                     │
│     profile.workers,                                          │
│     available_resources                                       │
│   )                                                          │
│                                                              │
│   throughput_factor = 1.0 + coordination_overhead             │
│   coordination_overhead = workers × 0.05  (5% per worker)     │
│                                                              │
│  Total wallclock = sum(layer_times) +                        │
│                    operator_response_time +                   │
│                    Guards_runtime                             │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  Example calculation dla Customer Y CRM:                      │
│                                                              │
│  Profile 2 (2 workers, 1 staging env):                       │
│                                                              │
│   Layer 0 Foundation (sequential, 16h):                       │
│    parallel_capacity = min(1, 2) = 1                          │
│    wallclock = 16h × 1.0 = 16h                                │
│                                                              │
│   Layer 1 Core domain (partial, 32h):                         │
│    parallel_capacity = min(3, 2) = 2                          │
│    wallclock = 32h / 2 × 1.1 = 17.6h                          │
│                                                              │
│   Layer 2 Integrations (full, 48h):                           │
│    parallel_capacity = min(5, 2) = 2                          │
│    wallclock = 48h / 2 × 1.1 = 26.4h                          │
│                                                              │
│   Layer 3 API endpoints (high parallel, 64h):                 │
│    parallel_capacity = min(8, 2) = 2                          │
│    wallclock = 64h / 2 × 1.1 = 35.2h                          │
│                                                              │
│   Layer 4 Frontend (high parallel, 80h):                      │
│    parallel_capacity = min(8, 2) = 2                          │
│    wallclock = 80h / 2 × 1.1 = 44h                            │
│                                                              │
│   Layer 5 Unit tests (full, 32h):                             │
│    parallel_capacity = min(16, 2) = 2                         │
│    wallclock = 32h / 2 × 1.1 = 17.6h                          │
│                                                              │
│   Layer 6 Integration tests (low, 48h):                       │
│    parallel_capacity = min(2, 2) = 2                          │
│    wallclock = 48h / 2 × 1.1 = 26.4h                          │
│                                                              │
│   Layer 7 Deployment (low, 24h):                              │
│    parallel_capacity = min(2, 2) = 2                          │
│    wallclock = 24h / 2 × 1.1 = 13.2h                          │
│                                                              │
│   Layers can overlap (some parallel between layers):         │
│    Layer 5 starts when Layer 1 done (~24h into Layer 2-4)    │
│    Layer 6 starts when Layer 5 mostly done                   │
│                                                              │
│   Effective wallclock z overlapping: 175h                     │
│   Operator response time: 25h                                 │
│   Guards runtime: 12h                                         │
│   ──────────────────────────                                  │
│   Total: 212h (~5 weeks at 40h/week)                          │
│                                                              │
│  Profile 4 (8 workers, 3 envs):                               │
│   Layer 0: still 16h (sequential)                             │
│   Layer 1: 32h / 3 × 1.15 = 12.3h                             │
│   Layer 2: 48h / 5 × 1.4 = 13.4h                              │
│   Layer 3: 64h / 8 × 1.4 = 11.2h                              │
│   Layer 4: 80h / 8 × 1.4 = 14h                                │
│   Layer 5: 32h / 16 × 1.5 = 3h                                │
│   Layer 6: 48h / 2 × 1.1 = 26.4h (still bottleneck)          │
│   Layer 7: 24h / 2 × 1.1 = 13.2h                              │
│                                                              │
│   With overlapping: 78h                                       │
│   Operator response time: 35h (more interactions)            │
│   Guards runtime: 6h (parallel)                               │
│   ──────────────────────────                                  │
│   Total: 119h (~1.5 weeks at 40h/week)                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.6.2. Critical path narrowing

```
W parallel orchestration, critical path staje się ważniejszy:

  Single worker: critical path = total work
   Speed up = adding workers
  
  Multi-worker: critical path = bottleneck
   Adding workers nie pomaga jeśli critical path constraints
  
  Customer Y CRM critical path:
   Layer 0 (16h) → Layer 1 KSeF prep (12h) → 
   Layer 2 KSeF integration (24h) → Layer 3 KSeF endpoints (10h) → 
   Layer 6 KSeF E2E tests (8h) → Layer 7 deploy (10h)
   = 80 hours minimum (regardless of workers)
  
  This is irreducible without architectural changes:
   • Could parallelize KSeF parts more aggressively
   • Could use multiple KSeF API instances dla testing
   • Could pre-implement based on docs while waiting dla
     sandbox access
  
  Profile 4-5 doesn't speed up critical path beyond ~70-80h,
  even though total work is reduced significantly.
```

### 28.6.3. Operator availability constraint

```
Operator may be bottleneck:

  Operator available: 10h over 8 weeks (12.5% capacity)
  
  Profile 2 needs: 25 interactions × 15 min = 6.25h
   ✓ Within capacity
  
  Profile 4 needs: 40 interactions × 15 min = 10h
   ⚠ Maxed out, no buffer
  
  Profile 5 needs: 60 interactions × 15 min = 15h
   ✗ Exceeds operator capacity
   Must use higher autonomy preset OR cut interactions
  
  Solution dla Profile 5:
   • Switch autonomy do "Aggressive" (cuts ~50% interactions)
   • Async approval flows (reduces operator wallclock)
   • Pre-approved decision frameworks
```

---

## 28.7. Guards cost scaling

### 28.7.1. Why Guards scale with parallel orchestration

```
┌──────────────────────────────────────────────────────────────┐
│  Guards Scaling Mechanics                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Coherence Guard:                                            │
│   • Per-file checks: scales linearly z file changes          │
│   • Per-module checks: scales z module count                  │
│   • Cross-module checks: scales O(N²) z modules               │
│                                                              │
│   1 worker writing 50 files: 50 file checks                   │
│   8 workers writing 200 files (parallel): 200 file checks    │
│   8 workers + cross-module: 200 + 28² ≈ 1000 checks            │
│                                                              │
│  Cost Guard:                                                 │
│   • Continuous monitoring (per minute)                        │
│   • Anomaly detection (statistical)                           │
│   • Scales z log volume (more workers = more logs)            │
│                                                              │
│  Security Guard:                                             │
│   • Per-commit SAST: scales z commits                         │
│   • Secret detection: per-file scan                           │
│   • Dependency scan: per dependency change                    │
│                                                              │
│  Quality Guard:                                              │
│   • Per-test-run: scales z test runs                         │
│   • Per-build: scales z builds                                │
│                                                              │
│  Provenance Guard:                                           │
│   • Per-action: scales z actions (most-scaling)               │
│   • Audit chain: append-only, low overhead per entry          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.7.2. Guards cost per profile

```
┌──────────────────────────────────────────────────────────────┐
│  Guards Cost Scaling — Customer Y CRM                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per profile estimated Guards costs:                         │
│                                                              │
│  Profile 1 (Solo budget):                                    │
│   Coherence:    $2 (lokalne, 50 file checks)                  │
│   Cost:         $0 (built-in)                                │
│   Security:     $1 (single SAST run)                          │
│   Quality:      $1 (test run analysis)                        │
│   Provenance:   $1 (audit chain entries)                      │
│   Total:        $5                                            │
│                                                              │
│  Profile 2 (Solo balanced):                                  │
│   Coherence:    $12 (T1 lokalne + T2 sonnet phase boundaries)│
│   Cost:         $0                                            │
│   Security:     $5 (more frequent SAST + secrets)            │
│   Quality:      $3                                            │
│   Provenance:   $2                                            │
│   External Guards multiplier: 1.0 (lokalne preferred)         │
│   Total:        $25                                           │
│                                                              │
│  Profile 3 (Burst parallel):                                  │
│   Coherence:    $22 (4x workers more changes)                 │
│   Cost:         $0                                            │
│   Security:     $12 (per-worker SAST)                         │
│   Quality:      $8                                            │
│   Provenance:   $4 (more entries)                             │
│   Cross-worker checks: $4                                     │
│   Total:        $50                                           │
│                                                              │
│  Profile 4 (Maximum parallel):                                │
│   Coherence:    $48 (8 workers, premium for cross-checks)    │
│   Cost:         $0                                            │
│   Security:     $20 (continuous SAST per worker)             │
│   Quality:      $15                                           │
│   Provenance:   $8                                            │
│   Cross-worker checks: $12 (O(N²) scaling)                    │
│   Premium models multiplier: 1.0 (still preferring lokalne)   │
│   Total:        $103 ⚠ significant                            │
│                                                              │
│  Profile 5 (Enterprise z external models):                   │
│   Coherence:    $90 (premium models, opus)                    │
│   Cost:         $0                                            │
│   Security:     $40 (premium external models)                │
│   Quality:      $30 (premium analysis)                        │
│   Provenance:   $15                                           │
│   Cross-worker checks: $25                                    │
│   External Guards multiplier: 1.5 (premium models)           │
│   Total:        $200 ⚠⚠ MAJOR                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 28.7.3. External vs lokalne Guards models trade-off

```
External models (claude-opus, gpt-5) dla Guards:
  Pros:
   • Better detection rate (~95% vs ~85%)
   • Fewer false positives
   • Better semantic understanding
   • Cross-language consistency
  Cons:
   • +50-80% cost vs lokalne
   • Network dependency
   • Privacy concerns dla customer data
  
Lokalne models (bielik-11b, qwen) dla Guards:
  Pros:
   • Free (after model download)
   • No network dependency
   • Privacy preserved
   • Fast (no API latency)
  Cons:
   • Lower detection rate (~85%)
   • More false positives (5-10% vs 2-3%)
   • Limited z context window
   • Hardware constraint (GPU needed)

Recommendation per profile:
  Profile 1-3: lokalne preferred dla cost
  Profile 4: hybrid (lokalne T1 + external premium dla critical T2)
  Profile 5: external premium dla everything (justified by speed)
```

---

## 28.8. Operator decision interface

### 28.8.1. Final profile selection

```
┌──────────────────────────────────────────────────────────────┐
│  Final Profile Selection                                      │
│                                                              │
│  Selected: Profile 2 (Solo balanced)                          │
│                                                              │
│  Confirm choices:                                             │
│   Workers: 2                                                  │
│   Environments: 1 staging (Hetzner CX21)                      │
│   Guards: hybrid lokalne T1 + sonnet T2                       │
│                                                              │
│  Cost breakdown:                                              │
│   Build cost (Layer 0-7):       $148                         │
│   Guards (continuous + boundary): $25                        │
│   Environment (Hetzner staging): $16 (3 weeks)               │
│   Total estimate:                $189                        │
│   Variance: ±15% → ($161 - $217)                              │
│                                                              │
│  Timeline:                                                    │
│   Estimated wallclock: 5 weeks                                │
│   Within deadline: yes (8 weeks customer)                    │
│   Buffer: 3 weeks                                             │
│                                                              │
│  Operator commitment:                                         │
│   Estimated 25 interactions × 15 min = 6.25h                  │
│   Available: ~10h                                             │
│   Headroom: 3.75h dla unexpected                              │
│                                                              │
│  Risk profile: low-medium                                     │
│   • Timeline buffer adequate                                  │
│   • Cost within budget                                        │
│   • Operator capacity comfortable                             │
│   • R1 KSeF risk addressed (Layer 2 early integration)       │
│                                                              │
│  Trade-offs (vs other profiles):                              │
│   • Slower than Profile 3 (-2 weeks)                         │
│     But: $43 cheaper, less coordination overhead             │
│   • Faster than Profile 1 (+3.5 weeks)                       │
│     But: $39 more, environment cost                          │
│                                                              │
│  Akcje:                                                      │
│   [● Confirm Profile 2]                                       │
│   [○ Switch to different profile]                             │
│   [○ Build custom profile]                                    │
│                                                              │
│  [Confirm and proceed]                                        │
└──────────────────────────────────────────────────────────────┘
```

### 28.8.2. Mid-build profile switching

```
Operator może switch profile mid-build (advanced):

  Trigger conditions:
   • Customer dorzuca pieniądze na speed up
   • Critical deadline pressure
   • Quality issues require slow down
   • Budget overrun forces scope cut
  
  Switch impact:
   • Active workers re-balanced
   • New environments provisioned
   • Guards reconfiguration
   • Cost re-projection
   • Timeline re-projection
  
  Switch cost:
   • Profile up: ~$10-30 transition (env setup)
   • Profile down: ~$5 transition (worker drainage)
  
  Switch must respect:
   • Critical path constraints
   • Customer approval (jeśli budget impact)
   • Hard gates (e.g., production deploy gate)
```

---

## 28.9. Operator review + signoff

### 28.9.1. Masterplan review interface (z layer decomposition)

```
┌──────────────────────────────────────────────────────────────┐
│  Masterplan Review — Customer Y CRM                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Generated Masterplan:                                       │
│   Length: 32 pages (z layer decomposition + parallel plan)   │
│   Total tasks: 47                                            │
│   Total work: 344 hours                                      │
│                                                              │
│  Selected Profile: Solo balanced (2 workers, 1 staging env)  │
│   Total cost:    $189                                        │
│   Timeline:      5 weeks (vs 8.5 single worker)              │
│                                                              │
│  Layer decomposition:                                         │
│   ✓ 8 layers identified                                       │
│   ✓ Parallelizability classified per layer                    │
│   ✓ Critical path identified (80h irreducible)                │
│   ✓ Module-level work units                                   │
│                                                              │
│  Resource allocation:                                         │
│   ✓ 2 workers assigned                                        │
│    • Worker 1: Backend + integrations                         │
│    • Worker 2: Frontend + tests                               │
│   ✓ Staging environment provisioned (when needed)             │
│   ✓ Guards scaling computed                                   │
│                                                              │
│  Coherence checks:                                            │
│   ✓ All Księga modules covered                                │
│   ✓ Dependency graph valid (no cycles)                        │
│   ✓ Critical path identified                                  │
│   ✓ Cost matches Księga estimate                              │
│   ✓ Timeline within deadline                                  │
│   ✓ Operator capacity adequate                                │
│                                                              │
│  Risk concerns:                                               │
│   ⚠ KSeF integration jako critical path item                  │
│      Recommendation: start week 1 (already planned)          │
│   ⚠ Customer availability dla weekly reviews                  │
│      Mitigation: async approval flows                        │
│                                                              │
│  Operator review:                                            │
│   [● Read full masterplan]                                    │
│   [○ Read by section]                                         │
│   [○ Review layer decomposition only]                        │
│   [○ Review profile cost-time analysis]                      │
│   [○ Skip do signoff]                                         │
│                                                              │
│  Operator notes:                                              │
│   [_____________________________________________________]    │
│                                                              │
│  ⚠ Masterplan locked po signoff. Material changes require    │
│     formal "Masterplan revision" process.                     │
│   Mid-build profile switching allowed (z conditions).         │
│                                                              │
│  [Sign off Masterplan]  [Request edits]  [Reject + redo]     │
└──────────────────────────────────────────────────────────────┘
```

---

## 28.10. Edge Cases — Masterplan (22 — expanded)

### Kategoria A — Generation issues (4)

**EC-A1**: Generation timeout
- Complex projects 30+ min
- Akcje: progressive generation, smaller chunks

**EC-A2**: Cost overrun w generation
- Generation $15 vs $5 estimate
- Akcje: investigate, accept, refine prompts

**EC-A3**: Dependency graph circular
- Algorithm error creates cycle
- Akcje: detect, manually fix, regenerate

**EC-A4**: Critical path miscalculation
- Algorithm wrong, operator notices
- Akcje: re-calculate, operator override

### Kategoria B — Layer decomposition issues (4 — NEW)

**EC-B1**: Layer parallelizability mis-classified
- System mis-classifies layer (e.g., marks sequential as parallel)
- Akcje: operator override, re-validate, audit log

**EC-B2**: Cross-layer dependencies break parallelism
- Layer 3 needs partial Layer 2 ready (not full)
- Akcje: refine dependency graph, partial-completion triggers

**EC-B3**: Critical path includes wrong items
- KSeF on critical path but operator can pre-implement
- Akcje: operator override, re-sequence

**EC-B4**: Module decomposition too granular
- 200 atomic units, coordination overhead
- Akcje: consolidate to logical groups (max 50 work items)

### Kategoria C — Profile selection issues (5 — NEW)

**EC-C1**: No profile fits constraints
- Budget too low + deadline too tight
- Akcje: scope cut, customer renegotiation, decline

**EC-C2**: Operator wants profile beyond capacity
- Profile 4 but only 1 GPU available
- Akcje: warn, fallback to API providers (more cost)

**EC-C3**: Profile doesn't account dla customer review windows
- Profile 4 expects rapid iterations, customer reviews weekly
- Akcje: insert customer review buffers, may extend

**EC-C4**: Operator switches profile mid-decision
- Picks Profile 2, then Profile 4, then Profile 2
- Akcje: log decision history, finalize on confirm

**EC-C5**: Custom profile invalid combination
- 16 workers but only 1 environment
- Akcje: validation, suggest matching env count

### Kategoria D — Throughput model issues (4 — NEW)

**EC-D1**: Throughput model overestimates speedup
- Real wallclock 30% slower than predicted
- Akcje: calibrate model from actual data, increase coordination overhead

**EC-D2**: Critical path constraint missed
- Algorithm doesn't recognize implicit dependency
- Akcje: operator manually flags, re-compute timeline

**EC-D3**: Operator capacity bottleneck
- Profile estimates 40 interactions, operator can do 20
- Akcje: warn, increase autonomy, cut interactions

**EC-D4**: Variance higher than expected
- Estimate 5 weeks, actual range 3-9 weeks (huge)
- Akcje: investigate, more conservative profile, milestone-based

### Kategoria E — Guards scaling issues (3 — NEW)

**EC-E1**: Guards cost overrun (parallel multiplied)
- Profile 4 Guards $150 vs estimated $103
- Akcje: investigate, may indicate more file changes than expected

**EC-E2**: External Guards models overload
- Premium opus dla everything = $300+ Guards
- Akcje: tier appropriately, lokalne dla quick checks

**EC-E3**: Cross-worker coherence false positives
- Workers writing parallel = many cross-module conflicts
- Akcje: tune Coherence Guard sensitivity, accept some

### Kategoria F — Recovery (2)

**EC-F1**: Masterplan generation interrupted
- Crash mid-generation
- Akcje: resume, may regenerate

**EC-F2**: Operator changes scope post-masterplan
- Wants add features
- Akcje: scope creep workflow, may require re-plan

---

## 28.11. Acceptance + transition do fazy 29

```bash
$ aeis-cli phase28-acceptance-test --project proj_customer_y_crm

[1/10] Masterplan generated                            ✓ PASS (32 pages)
[2/10] All Księga modules covered                      ✓ PASS
[3/10] Layer decomposition complete                    ✓ PASS (8 layers)
[4/10] Module-level work units                         ✓ PASS
[5/10] Dependency graph valid                          ✓ PASS (no cycles)
[6/10] Resource profile selected                       ✓ PASS (Profile 2)
[7/10] Throughput-driven timeline                      ✓ PASS (5 weeks)
[8/10] Guards cost scaling computed                    ✓ PASS ($25)
[9/10] Critical path identified                        ✓ PASS (80h)
[10/10] Audit chain entry masterplan_finalized         ✓ PASS

DoD: 10/10 ✓
Phase 28 ACCEPTED. Ready dla Phase 29 (Test Plan Synthesis).
```

---

# Status faz 26-28

🟢 **Wszystkie 3 fazy complete**

**Zawiera**:
- ✓ Faza 26 — Model Selection (per-task model assignment matrix, **Guards-specific assignments dodane**, cost optimization, quality requirements per D-level, 15 edge cases)
- ✓ Faza 27 — Skill Synthesis (pattern detection w Księga, skill creation per project, marketplace import, promotion do Personal, 15 edge cases)
- ✓ Faza 28 — Masterplan Synthesis **z Layer Decomposition + Parallel Orchestration** (28.4 layer decomposition, 28.5 resource matrix 5 profiles, 28.6 throughput-driven timeline, 28.7 Guards cost scaling, 28.8 operator decision UI, 22 edge cases — expanded z 18)

**Total edge cases w pliku**: 52 cases (15+15+22)

**Co rozwiązuje sekcja 28.4**:
- ✓ Layer/module decomposition Księgi
- ✓ Parallelizability classification per layer
- ✓ 5 resource profiles (Solo budget → Enterprise parallel)
- ✓ Throughput-driven timeline (vs hardcoded weeks)
- ✓ Guards cost scaling z workers + envs + external models
- ✓ Critical path narrowing
- ✓ Operator decision interface z cost-time trade-off

⏳ **Po Twojej akceptacji** → **soft freeze faz 26-28** + przejście do **Fazy 29-31** (druga połowa grupy D — Test Plan + Pre-Flight Cost + Pre-Flight Dry Run, z propagated profile-aware estimates).
