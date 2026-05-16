# FAZY 11-15 — Skills Library + 4 Templates

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupy**:
>   - Faza 11: A — Przygotowanie Operatora (11 z 11) — ostatnia w grupie A
>   - Fazy 12-15: A2 — Templates (1-4 z 4) — cała grupa A2
> **Zależności**: Fazy 1-10 zakończone (wszystkie Guards skonfigurowane)
> **Następnik**: Faza 16 (Project Inception — grupa B)
>
> **Decyzja architektoniczna**: 5 faz w jednym pliku ponieważ:
> - Skills Library + 4 Templates są **conceptually grouped** — wszystkie
>   są "operator's reusable building blocks" przed startem projektów
> - Każda jest mniejsza niż Guards (mniej kompleksowych mechanizmów)
> - Operator widzi je jako jedną fazę "Templates Setup"
>
> **Wspólna struktura każdej fazy**:
> - Sense + relacja do poprzednich faz
> - Lista templates / skills baseline
> - Edytowanie + custom workflow
> - Inheritance pattern do projektów
> - Edge cases (15-22)
> - DoD + acceptance test

---

# FAZA 11 — Skills Library Bootstrap

> **Spis sekcji**:
> - 11.1 — Sense fazy + czym są skills w AEIS
> - 11.2 — 4 typy skills (System / Project / Personal / Imported)
> - 11.3 — Baseline 25 system skills
> - 11.4 — Skill creation workflow (4 mechanisms)
> - 11.5 — Skill discovery (when AEIS auto-suggests new skill)
> - 11.6 — Skill versioning + deprecation
> - 11.7 — Skill marketplace (community)
> - 11.8 — Edge cases (20) + inheritance + DoD

---

## 11.1. Sense fazy + czym są skills

### 11.1.1. Definicja skill w AEIS

**Skill** to **reusable capability** którą AEIS może invoke podczas
projektów. Każdy skill ma:

- **Trigger** — kiedy skill ma być użyty
- **Implementation** — jak skill robi swoją pracę
- **Cost profile** — ile kosztuje wywołanie
- **Quality metrics** — jak dobrze działa

```
┌──────────────────────────────────────────────────────────────┐
│  Skill examples w AEIS                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  • "Generate FastAPI route z OpenAPI spec"                    │
│  • "Convert SQL schema do SQLAlchemy ORM models"             │
│  • "Create Playwright E2E test from user story"              │
│  • "Validate Polish PESEL/NIP/REGON numbers"                 │
│  • "Generate Stripe webhook handler"                          │
│  • "Translate marketing copy z PL → EN → DE"                 │
│  • "Optimize Docker image size"                              │
│  • "Generate Terraform manifest dla AWS deploy"              │
│  • "Audit Polish KSeF invoice format"                        │
│  • "Generate i18n strings z marketing brief"                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 11.1.2. Skills vs ad-hoc LLM calls

```
┌──────────────────────────────────────────────────────────────┐
│  Skill vs Ad-hoc LLM call                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  AD-HOC LLM CALL                                             │
│   • Operator/Council formuluje prompt każdym razem            │
│   • No reuse między projektami                                │
│   • Quality variable                                          │
│   • Cost variable                                             │
│   • Brak knowledge accumulation                               │
│                                                              │
│  SKILL                                                        │
│   • Pre-defined prompt + logic                                │
│   • Reused across projects                                    │
│   • Calibrated quality (improves z każdym użyciem)           │
│   • Predictable cost                                          │
│   • Knowledge accumulation (skill uczy się)                   │
│   • Versioned (rollback if regression)                        │
│   • Auditable (provenance per skill invocation)              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 11.1.3. Skills enable scale

Bez skills, każdy nowy projekt = re-invent. Z skills, operator buduje na
existing capabilities. Skills są dlatego foundational dla **operator scale
beyond first 10 projects**.

### 11.1.4. Wynik fazy 11 (DoD)

```
✓ Skills Library initialized (25 baseline + custom)
✓ Skill creation workflow configured
✓ Discovery mechanisms enabled
✓ Versioning policy set
✓ Marketplace settings configured (opt-in)
✓ Audit chain entry: phase_11.complete
```

---

## 11.2. 4 typy skills

### 11.2.1. Typ 1 — System skills

**System skills** to baseline 25 (lista w 11.3) — predefiniowane przez AEIS,
działają z box.

```
Properties:
 • Maintained by AEIS team
 • Auto-updated z AEIS releases
 • Cannot be deleted (only disabled)
 • Available immediately po fazie 11
 • Quality calibrated based on aggregate usage
```

### 11.2.2. Typ 2 — Project skills

**Project skills** powstają w trakcie konkretnego projektu — Council
tworzy skill dla specific need.

```
Properties:
 • Created mid-project (faza 27 Skill Synthesis)
 • Initially scoped do project
 • Mogą być promoted do Personal skills (operator decyduje)
 • Versioned per project
 • Cleanup po project closure (jeśli not promoted)
```

### 11.2.3. Typ 3 — Personal skills

**Personal skills** to operator's library — promoted z projects lub
created standalone.

```
Properties:
 • Operator-owned
 • Reusable across all operator's projects
 • Versioned (operator manages)
 • Can be exported/shared
 • Calibrated based on operator's usage
```

### 11.2.4. Typ 4 — Imported skills

**Imported skills** pochodzą z marketplace lub other operators.

```
Properties:
 • Source: AEIS marketplace, community, other operators
 • Trust levels (verified / community / self-signed)
 • Operator może modify (creates fork)
 • Original author credited
 • Auto-update opcjonalne (security patches)
```

### 11.2.5. Skill type matrix

```
┌──────────────────────────────────────────────────────────────┐
│  Skill Type Properties                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Property        System    Project   Personal  Imported     │
│  ─────────────── ───────  ───────   ────────  ──────────   │
│  Source          AEIS     Council   Operator  Marketplace  │
│  Persistence     Forever  Project   Forever   Forever       │
│  Editable        No       Limited   Yes       Yes (fork)    │
│  Scope           Global   Project   Workspace Workspace     │
│  Updates         Auto     Manual    Manual    Manual/Auto   │
│  Calibration     Aggregate Project  Operator  Source        │
│  Trust           Verified Verified  Verified  Variable      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11.3. Baseline 25 system skills

### 11.3.1. Pełna lista

```
┌──────────────────────────────────────────────────────────────┐
│  System Skills Baseline (25)                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CODE GENERATION (6)                                         │
│   1.  Generate FastAPI route z OpenAPI spec                   │
│   2.  Generate React component z props spec                  │
│   3.  Convert SQL schema do SQLAlchemy ORM                   │
│   4.  Generate database migration z schema diff              │
│   5.  Generate REST API client z OpenAPI                     │
│   6.  Generate Docker container z application                │
│                                                              │
│  TESTING (5)                                                 │
│   7.  Generate pytest unit tests z function signature         │
│   8.  Generate Playwright E2E z user story                    │
│   9.  Generate test fixtures z schema                         │
│   10. Generate human-like UI scenario z Księga                │
│   11. Generate load test z user behavior model               │
│                                                              │
│  POLISH/EU SPECIFIC (4)                                      │
│   12. Validate Polish identifiers (PESEL/NIP/REGON)          │
│   13. Generate KSeF-compliant invoice                         │
│   14. Validate GDPR data flow                                 │
│   15. Translate między PL/EN/DE/FR/UK                        │
│                                                              │
│  DEPLOYMENT (4)                                              │
│   16. Generate Terraform manifest dla cloud                   │
│   17. Generate Kubernetes manifests                          │
│   18. Generate CI/CD pipeline (GitHub Actions/GitLab CI)     │
│   19. Generate monitoring/alerting config                    │
│                                                              │
│  INTEGRATION (3)                                             │
│   20. Generate Stripe payment integration                    │
│   21. Generate OAuth2 authentication flow                    │
│   22. Generate webhook handler z security                    │
│                                                              │
│  DOCUMENTATION (3)                                           │
│   23. Generate API documentation z code                      │
│   24. Generate user-facing changelog z commits               │
│   25. Generate operator runbook z architecture               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 11.3.2. Skill detail example

```
┌──────────────────────────────────────────────────────────────┐
│  Skill: Generate FastAPI route z OpenAPI spec                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ID: skill.codegen.fastapi_route_from_openapi                │
│  Type: System                                                │
│  Version: 2.3.1                                              │
│  Maintainer: AEIS team                                       │
│                                                              │
│  Inputs:                                                     │
│   • OpenAPI 3.0+ spec (YAML or JSON)                         │
│   • Target module path                                       │
│   • Authentication scheme (optional)                          │
│                                                              │
│  Outputs:                                                    │
│   • FastAPI router file                                      │
│   • Pydantic models                                          │
│   • Tests (basic happy-path)                                 │
│                                                              │
│  Quality metrics:                                            │
│   • Code passes linter: 99.2%                                │
│   • Generated tests pass: 94.7%                              │
│   • Type hints correct: 98.5%                                │
│   Based on: 1247 invocations w aggregate                     │
│                                                              │
│  Cost profile:                                               │
│   Average cost: $0.42                                        │
│   Range: $0.20-$1.20 (zależnie od spec complexity)           │
│   Recommended model: claude-sonnet                            │
│                                                              │
│  Time profile:                                               │
│   Average: 12 sek                                             │
│   Range: 5-45 sek                                             │
│                                                              │
│  Dependencies:                                               │
│   • Python 3.10+                                             │
│   • FastAPI 0.100+                                           │
│   • Pydantic 2.x                                             │
│                                                              │
│  Usage:                                                      │
│   Used w 23 projektach (operator's history)                  │
│   Last used: 4 dni temu                                      │
│   Operator rating: ★★★★☆ (4.2/5)                             │
│                                                              │
│  [View prompt]  [Test skill]  [Disable]  [Customize/fork]    │
└──────────────────────────────────────────────────────────────┘
```

### 11.3.3. Configuration per skill

```
Skill Settings → fastapi_route_from_openapi

  Status:        [● Enabled]  [○ Disabled]
  
  Default model: [claude-sonnet ▼]
  Max cost:      [$1.50 ▼]
  Timeout:       [60 sec ▼]
  
  Quality threshold:
   ☑ Reject output if linter fails
   ☑ Reject if generated tests fail
   ☐ Reject if type coverage < 95%
  
  Auto-improve:
   ☑ Track usage outcomes
   ☑ Refine prompt based on common issues
   ☐ A/B test new prompt versions (advanced)
  
  Personal calibration:
   • Prefer: type-strict mode
   • Avoid: deprecated FastAPI patterns
   • Custom: include Polish error messages
   [Edit operator preferences]
  
  [Save]  [Reset to AEIS defaults]
```

---

## 11.4. Skill creation workflow (4 mechanisms)

### 11.4.1. Mechanism 1 — From scratch

```
┌──────────────────────────────────────────────────────────────┐
│  Create Custom Skill — From Scratch                          │
│                                                              │
│  Skill name:    [ Generate Polish formal letter        ]     │
│  Skill type:    [Personal ▼]                                 │
│  Category:      [Documentation ▼]                            │
│                                                              │
│  Description:                                                │
│  [ Generuje formalne pismo po polsku z given context i      ]│
│  [ recipient. Wykorzystuje proper grzecznościowe forms.    ]│
│                                                              │
│  Inputs:                                                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  + recipient_name (string)                             │ │
│  │  + recipient_title (string, optional)                  │ │
│  │  + sender_name (string)                                │ │
│  │  + subject (string)                                    │ │
│  │  + main_content (string, multi-line)                   │ │
│  │  + tone (enum: bardzo_formalne | formalne | neutralne) │ │
│  │  + closing (string, default: "Z poważaniem")           │ │
│  │  [+ Add input]                                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Outputs:                                                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  + letter (string, formatted Polish letter)            │ │
│  │  + word_count (int)                                    │ │
│  │  [+ Add output]                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Implementation:                                             │
│  [● LLM prompt]  [○ Code template]  [○ Pipeline]              │
│                                                              │
│  LLM prompt:                                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Jesteś expertem w formal Polish business writing.    │ │
│  │  Wygeneruj formalne pismo:                             │ │
│  │                                                        │ │
│  │  Do: {recipient_name}, {recipient_title}              │ │
│  │  Od: {sender_name}                                     │ │
│  │  Temat: {subject}                                      │ │
│  │  Ton: {tone}                                           │ │
│  │  Zakończenie: {closing}                                │ │
│  │                                                        │ │
│  │  Treść:                                                │ │
│  │  {main_content}                                        │ │
│  │                                                        │ │
│  │  Zwróć JSON z polami: letter, word_count               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Default model: [bielik-11b lokalny ▼] (best dla Polish)    │
│  Estimated cost: $0 (lokalne)                                │
│                                                              │
│  Quality validation:                                         │
│   ☑ Validate JSON output                                     │
│   ☑ Min length 100 słów                                      │
│   ☑ Includes formal forms (Pan/Pani)                         │
│   ☐ Custom validation function                               │
│                                                              │
│  Test:                                                       │
│   [Run sample input]                                          │
│   Result: [preview generated letter]                         │
│                                                              │
│  [Save skill]  [Cancel]                                      │
└──────────────────────────────────────────────────────────────┘
```

### 11.4.2. Mechanism 2 — From existing skill (fork)

```
┌──────────────────────────────────────────────────────────────┐
│  Fork Existing Skill                                         │
│                                                              │
│  Original: Generate React component (System)                 │
│  Fork name: [ Generate React component z SYLION style    ]   │
│                                                              │
│  Modifications:                                              │
│   ☑ Add SYLION design system imports                         │
│   ☑ Use TypeScript strict mode                               │
│   ☑ Include Tailwind classes z custom palette                │
│   ☑ Add Polish accessibility labels                          │
│   ☐ Other modifications                                      │
│                                                              │
│  Diff preview:                                               │
│   [Show what changes from original]                          │
│                                                              │
│  Trust:                                                      │
│   ✓ Operator-modified (fork wymaga operator approval         │
│      przed użyciem)                                          │
│                                                              │
│  Update strategy:                                            │
│   ☑ Notify when original updated                             │
│   ☐ Auto-merge non-conflicting changes                       │
│                                                              │
│  [Save fork]                                                 │
└──────────────────────────────────────────────────────────────┘
```

### 11.4.3. Mechanism 3 — From mid-project (Skill Synthesis)

W trakcie projektu, Council może zauważyć że jakaś capability była użyta
multiple times. System sugeruje extracting do reusable skill.

```
┌──────────────────────────────────────────────────────────────┐
│  💡  Skill Synthesis Suggestion                              │
│                                                              │
│  Faza 27 detected pattern:                                   │
│                                                              │
│  W projekcie Sylion Tailor, Council wygenerował 5 podobnych  │
│  prompts dla "validate Polish customer data":                │
│   • PESEL validation                                          │
│   • NIP validation                                            │
│   • REGON validation                                          │
│   • Address validation (Polish format)                        │
│   • Phone validation (+48 format)                             │
│                                                              │
│  Combined common pattern detected.                           │
│                                                              │
│  Recommendation:                                             │
│   Create new skill: "Validate Polish customer data"          │
│   Type: Personal (reusable across projects)                  │
│                                                              │
│  Estimated savings:                                          │
│   Future projects: skill reuse vs ad-hoc prompts              │
│   Per-project savings: ~$2-5 + better quality                │
│                                                              │
│  Akcje:                                                      │
│   [● Create skill (recommended)]                             │
│       AEIS extracts pattern automatically                    │
│       Operator reviews + approves                            │
│   [○ Skip — keep as ad-hoc]                                  │
│   [○ Mark "no skill needed dla similar"]                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 11.4.4. Mechanism 4 — From marketplace import

```
┌──────────────────────────────────────────────────────────────┐
│  Import Skill — Marketplace                                  │
│                                                              │
│  Search: [polish_invoice___________]                         │
│                                                              │
│  Results:                                                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ✓ "Generate Polish KSeF invoice (FA(2))"              │ │
│  │     Author: AEIS team                                   │ │
│  │     Trust: Verified ✓                                   │ │
│  │     Used: 1247 operators                                │ │
│  │     Rating: ★★★★★ (4.8/5)                               │ │
│  │     Last update: 2 weeks ago                            │ │
│  │     [Import]                                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ⚠ "Polish invoice generator (community)"              │ │
│  │     Author: pkozak                                      │ │
│  │     Trust: Community                                    │ │
│  │     Used: 23 operators                                  │ │
│  │     Rating: ★★★☆☆ (3.4/5)                               │ │
│  │     Last update: 6 months ago                           │ │
│  │     [Import (z disclaimer)]                             │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ✓ "Polish proforma invoice"                           │ │
│  │     Author: AEIS team                                   │ │
│  │     Trust: Verified ✓                                   │ │
│  │     Used: 489 operators                                 │ │
│  │     Rating: ★★★★☆ (4.5/5)                               │ │
│  │     [Import]                                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11.5. Skill discovery (when AEIS auto-suggests)

### 11.5.1. Discovery triggers

System ciągle obserwuje patterns i sugeruje new skills:

```
Trigger 1 — Repeated pattern w jednym projekcie:
  3+ similar prompts dla same kind of task
  → Suggest: "Create skill dla this task"

Trigger 2 — Cross-project pattern:
  Same/similar prompts w 3+ projects
  → Suggest: "Promote do Personal skill"

Trigger 3 — High-cost ad-hoc:
  Single ad-hoc prompt costs > $5
  → Suggest: "Create skill dla potential cost optimization"

Trigger 4 — Low-quality ad-hoc:
  Ad-hoc prompts have low quality scores
  → Suggest: "Use calibrated skill instead"

Trigger 5 — Marketplace match:
  Operator's pattern matches existing marketplace skill
  → Suggest: "Import existing skill (saves time)"

Trigger 6 — Skill template fill:
  Common gaps w operator's library
  → Suggest: "Most operators have skill X, you don't"
```

### 11.5.2. Discovery notification

```
┌──────────────────────────────────────────────────────────────┐
│  💡  Skill Discovery                                          │
│                                                              │
│  Pattern detected: Council generates similar prompts         │
│  3 projects (Sylion Tailor v1/v2/v3) używały:                │
│   "Generate Stripe webhook handler" (variants)               │
│                                                              │
│  Acknowledged options:                                       │
│   [● Create personal skill (extract pattern)]                │
│   [○ Import marketplace skill (similar exists)]              │
│   [○ Skip — continue ad-hoc]                                 │
│   [○ Suppress similar suggestions for 30 dni]                │
│                                                              │
│  Estimated benefit:                                          │
│   Future projects: -$3 per project + 2x faster                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11.6. Skill versioning + deprecation

### 11.6.1. Versioning model

```
SemVer-like versioning:

  MAJOR.MINOR.PATCH (e.g., 2.3.1)
  
  MAJOR: breaking change (input/output schema)
  MINOR: new features, backwards compatible
  PATCH: bug fixes, prompt refinements

Example skill history:
  • v1.0.0 (2025-01) — initial release
  • v1.0.1 (2025-02) — fix Polish character handling
  • v1.1.0 (2025-04) — added optional auth parameter
  • v2.0.0 (2025-08) — breaking: changed input schema
  • v2.1.0 (2026-01) — added GraphQL support
  • v2.3.1 (2026-04) — current
```

### 11.6.2. Auto-update vs pinned

```
Settings → Skills → Update Behavior

  System skills:
   [● Auto-update PATCH (security/bug fixes)]
   [○ Auto-update MINOR (new features)]
   [○ Pin to current version (no auto-updates)]
  
  Imported skills:
   [● Notify on updates (operator decyduje)]
   [○ Auto-update (jeśli verified author)]
   [○ Manual only]
  
  Personal skills:
   [Operator manages versions]
  
  Project skills:
   [Locked to creation version (project-scoped)]
```

### 11.6.3. Deprecation workflow

```
┌──────────────────────────────────────────────────────────────┐
│  Skill Deprecation Notice                                    │
│                                                              │
│  Skill: "Generate React component (legacy class-based)"      │
│  Status: DEPRECATED 2026-04-01                               │
│  EOL: 2026-10-01                                             │
│                                                              │
│  Replacement: "Generate React component (functional)"        │
│   • Modern React patterns (hooks, FC)                        │
│   • Better TypeScript support                                │
│   • Improved performance                                     │
│                                                              │
│  Your usage:                                                 │
│   • 5 projects use this skill                                │
│   • 23 invocations w ostatnim miesiącu                       │
│                                                              │
│  Migration path:                                             │
│   [Auto-migrate (system rewrites)]                           │
│       Updates references, may need code adjustments          │
│   [Manual migration]                                         │
│       Operator updates each project                          │
│   [Continue using deprecated]                                │
│       Until EOL date, then forced migration                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11.7. Skill marketplace (community)

### 11.7.1. Marketplace structure

```
┌──────────────────────────────────────────────────────────────┐
│  AEIS Skill Marketplace                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Categories:                                                 │
│   • Code Generation (487 skills)                             │
│   • Testing (234 skills)                                     │
│   • Polish/EU Compliance (89 skills)                         │
│   • Deployment (156 skills)                                  │
│   • Integration (203 skills)                                 │
│   • Documentation (78 skills)                                │
│   • Analysis (123 skills)                                    │
│   • Industry-specific (67 skills)                            │
│                                                              │
│  Trust levels:                                               │
│   ✓ Verified by AEIS team — passed quality checks            │
│   ⚠ Community — operator at own risk                         │
│   ✗ Self-signed — single operator's work                     │
│                                                              │
│  Marketplace settings:                                       │
│   ☑ Allow searching marketplace                              │
│   ☑ Show ratings + usage stats                               │
│   ☐ Auto-suggest marketplace imports                         │
│   ☐ Publish my own skills do marketplace                     │
│   ☐ Anonymous usage stats sharing                            │
│                                                              │
│  Privacy:                                                    │
│   When importing, marketplace receives:                      │
│   ✗ NIE: operator's name/identity                            │
│   ✓ Anonymous usage statistics                               │
│   ✓ Anonymous quality ratings                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 11.7.2. Publishing operator's skills

```
┌──────────────────────────────────────────────────────────────┐
│  Publish Skill do Marketplace                                │
│                                                              │
│  Skill: "Generate Polish formal letter" (Personal)           │
│                                                              │
│  Pre-publication checks:                                     │
│   ✓ No hardcoded credentials                                 │
│   ✓ No personal data w prompt examples                       │
│   ✓ License compatible (MIT)                                 │
│   ⚠ Quality calibration: 23 invocations (low for marketplace)│
│      Recommended: use 100+ invocations dla statistical sig    │
│                                                              │
│  Marketplace info:                                           │
│   Display name: [Generate Polish formal letter]              │
│   Description:  [Multi-line description]                     │
│   Category:     [Documentation ▼]                            │
│   License:      [MIT ▼]                                      │
│   Author:       [ Your handle (optional) ]                   │
│                                                              │
│  Visibility:                                                 │
│   [● Public (anyone can import)]                             │
│   [○ Private (specific operators only)]                      │
│   [○ Organization (operator's team)]                         │
│                                                              │
│  [Cancel]  [Submit dla AEIS verification]                    │
│                                                              │
│  Verification process:                                       │
│   1. Auto-checks (security, format) — instant                │
│   2. AEIS team review — 3-5 dni                              │
│   3. Test installations — 1-2 dni                            │
│   4. Published z "Verified" badge                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 11.8. Edge Cases — Skills (20 cases)

### Kategoria A — Skill creation issues (4 cases)

#### EC-A1: Skill prompt too generic

**Trigger**: Operator created skill z generic prompt. Output quality
unpredictable.

```
⚠ Skill quality issue

  Skill: "Generate API endpoint"
  Issue: too generic — "Make me an API endpoint"
  Output variance: high (40% rejected by quality checks)
  
  Akcje:
   [Refine prompt z more context]
   [Add input schema strictness]
   [Use few-shot examples]
   [Mark skill as "draft" until refined]
```

#### EC-A2: Skill output schema mismatch

**Trigger**: Skill returns inconsistent JSON structure.

```
⚠ Skill output validation failed

  Expected: { letter: string, word_count: int }
  Got: { content: "...", words: 250 }
  
  Akcje:
   [Add JSON schema enforcement do prompt]
   [Use response_format=json_object (OpenAI)]
   [Refine output schema]
```

#### EC-A3: Skill cost spikes

**Trigger**: Skill normally $0.30, suddenly $2.00 per call.

```
⚠ Skill cost anomaly

  Skill: Generate FastAPI route
  Normal: $0.30
  Recent: $2.00 (6.7x)
  
  Cause: input OpenAPI spec became huge (was 100 lines, now 5000)
  
  Akcje:
   [Add input size limit do skill]
   [Switch to cheaper model dla large inputs]
   [Split spec into smaller chunks]
```

#### EC-A4: Skill conflicts z another skill

**Trigger**: Two skills both claim "FastAPI route generation". Operator
confused which to use.

```
⚠ Duplicate skill purpose

  Skills with similar purpose:
   • System: "Generate FastAPI route z OpenAPI spec"
   • Personal: "Generate FastAPI route (custom)"
   • Imported: "FastAPI route from spec"
  
  Akcje:
   [Tag skills z distinct use cases]
   [Disable redundant skills]
   [Operator chooses primary]
```

### Kategoria B — Skill discovery issues (4 cases)

#### EC-B1: Discovery noise (too many suggestions)

**Trigger**: System suggests 15 new skills w jeden tydzień.

```
⚠ Discovery overload

  Suggestions w ostatnim tygodniu: 15
  Operator dismissed: 13
  Created: 2
  
  Akcje:
   [Increase confidence threshold]
   [Batch suggestions weekly]
   [Disable discovery temporarily]
```

#### EC-B2: Discovery missing obvious patterns

**Trigger**: Operator manually noticed pattern. AEIS discovery missed.

```
ℹ Discovery gap

  Operator noticed: 5 projects all need "Polish address validation"
  AEIS discovery: didn't suggest
  
  Akcje:
   [Operator manually creates skill]
   [Provide feedback do discovery engine]
   [Lower discovery confidence threshold]
```

#### EC-B3: Discovery suggests wrong abstraction

**Trigger**: System suggests skill "Generate webhook handler". Operator's
projects had different webhook needs (Stripe vs Twilio vs custom).

```
⚠ Discovery abstraction wrong

  Suggested: "Generate webhook handler"
  Reality: 3 different webhook types z different requirements
  
  Akcje:
   [Create 3 separate skills (per type)]
   [Create parametrized skill (z webhook_type input)]
   [Reject suggestion, continue ad-hoc]
```

#### EC-B4: Marketplace skill better than auto-suggested

**Trigger**: AEIS auto-suggests creating new skill. Operator finds better
marketplace alternative.

```
ℹ Marketplace alternative exists

  Auto-suggestion: "Generate Stripe webhook handler"
  Marketplace match: "Stripe webhook handler v3.2 (verified)"
       Better quality (4.9★, 1500+ users)
  
  Akcje:
   [Import marketplace skill instead]
   [Create custom anyway (operator preferences)]
```

### Kategoria C — Versioning / updates (4 cases)

#### EC-C1: Auto-update breaks projects

**Trigger**: System skill auto-updated (PATCH). New version has subtle
behavior change. Operator's projects affected.

```
⚠ Auto-update regression

  Skill: Generate React component v2.3.0 → v2.3.1
  Change: prefer "use" hooks naming convention
  Impact: 3 projects fail tests (relied on old naming)
  
  Akcje:
   [Auto-rollback skill version]
   [Update affected projects]
   [Disable auto-updates dla this skill]
```

#### EC-C2: Pinned skill incompatible z new AEIS

**Trigger**: Operator pinned skill v1.x. AEIS update changed skill API.
Pinned version no longer works.

```
⚠ Pinned skill incompatible

  Skill: Generate API client (pinned v1.5)
  AEIS: updated v3.0 (skill API v2.0)
  Status: pinned skill nie loads
  
  Akcje:
   [Migrate to current API version]
   [Manual port skill]
   [Disable skill]
```

#### EC-C3: Deprecated skill still in use

**Trigger**: Skill deprecated 6 months ago. EOL today. Operator's project
still uses.

```
🚨 Deprecated skill EOL today

  Skill: Generate React component (class-based)
  EOL: 2026-04-30 (today)
  Status: AFTER today, skill cannot be invoked
  
  Affected projects: 2 (haven't migrated)
  
  Akcje (urgent):
   [Auto-migrate now]
   [Extend EOL by 30 dni (operator override)]
   [Manual migration]
```

#### EC-C4: Marketplace skill author abandoned

**Trigger**: Imported skill author hasn't updated w 2 lata. Bugs accumulating.

```
ℹ Marketplace skill maintenance

  Skill: "Custom OAuth flow"
  Last update: 24 months ago
  Author: not responding
  Issues filed: 12 (open)
  
  Akcje:
   [Fork skill (operator maintains)]
   [Find alternative skill]
   [Migrate do system skill]
```

### Kategoria D — Skill execution (4 cases)

#### EC-D1: Skill output validation fails

**Trigger**: Skill output doesn't match declared schema.

```
✗ Skill output invalid

  Skill: Generate database migration
  Expected schema: { migration_sql: string, rollback_sql: string }
  Got: { sql: string }
  
  Akcje:
   [Auto-retry z stricter prompt]
   [Operator manual intervention]
   [Skill needs fix]
```

#### EC-D2: Skill timeout

**Trigger**: Skill execution exceeds timeout.

```
⚠ Skill timeout

  Skill: Generate complex React app
  Timeout: 60 sek
  Actual: still running at 90 sek
  
  Akcje:
   [Increase timeout]
   [Split into smaller skills]
   [Use streaming output]
```

#### EC-D3: Skill cost over budget

**Trigger**: Skill needed but exceeds project budget cap.

```
⚠ Skill blocked by budget

  Skill: Generate complete deployment manifest (estimated $8)
  Project remaining budget: $5
  
  Akcje:
   [Use cheaper alternative skill]
   [Operator approves cost increase]
   [Manual implementation]
```

#### EC-D4: Skill output triggers Security Guard

**Trigger**: Skill generated code has security finding (Security Guard
catches).

```
⚠ Skill output security issue

  Skill: Generate API endpoint
  Output: contains hardcoded "test_secret_key"
  Security Guard: CRITICAL finding
  
  Akcje:
   [Refine skill prompt: never include hardcoded secrets]
   [Mark skill as needs review]
   [Operator fixes manually]
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Skills library lost

**Trigger**: Skills database corrupted.

```
⚠ Skills library corruption

  Lost: 47 personal/imported skills
  System skills: intact (re-downloaded)
  
  Akcje:
   [Restore z backup]
   [Re-import marketplace skills]
   [Recreate personal skills]
```

#### EC-E2: Workspace import — skills

**Trigger**: Operator imports workspace. Skills need migration.

```
ℹ Skills migration

  Imported skills: 47
  Compatible: 42
  Need version update: 3
  Incompatible (different AEIS version): 2
  
  Akcje:
   [Auto-migrate compatible]
   [Manual review incompatible]
```

#### EC-E3: Skill rollback

**Trigger**: New skill version causing issues. Operator wants rollback.

```
ℹ Skill rollback

  Skill: Generate FastAPI route
  Current: v2.3.1
  Rollback to: v2.2.5
  
  Akcje:
   [Rollback now]
   [Pin to v2.2.5]
   [Affected projects: re-evaluate]
```

#### EC-E4: Marketplace offline

**Trigger**: AEIS marketplace down. Operator can't import/update skills.

```
⚠ Marketplace unavailable

  Status: down (last 30 min)
  
  Akcje:
   [Use cached skill data]
   [Wait for recovery]
   [Skip marketplace dla now]
```

---

## 11.9. Inheritance + DoD — Skills

```bash
$ aeis-cli phase11-acceptance-test

[Common requirements]
[1/5] System skills baseline available               ✓ PASS (25 skills)
[2/5] Skill creation workflow configured             ✓ PASS
[3/5] Discovery enabled                              ✓ PASS
[4/5] Versioning policy set                          ✓ PASS
[5/5] Audit chain entry phase_11.complete            ✓ PASS

[Optional]
[6/8] Marketplace settings                           ✓ PASS (search enabled)
[7/8] Personal skills count                          ℹ INFO (3 created)
[8/8] Imported skills count                          ℹ INFO (5 imported)

DoD: 5/5 ✓
Phase 11 ACCEPTED.
```

---

# FAZA 12 — Council Templates

> **Spis sekcji**:
> - 12.1 — Sense fazy + relacja do faz 4 (default Council)
> - 12.2 — Template structure (roles, voting, ordering)
> - 12.3 — Baseline 8 templates (per goal type + project type)
> - 12.4 — Template editor + composition wizard
> - 12.5 — Per-D-level scaling
> - 12.6 — Edge cases (15) + DoD

---

## 12.1. Sens fazy

### 12.1.1. Faza 4 vs Faza 12

**Faza 4** ustanowiła **default Council per goal** — operator wybrał
basic compositions. **Faza 12** to **deep template management** — wiele
templates, fine-tuning, composition wizard.

```
Faza 4 ustawiła:
  Goal "public_products" → Default Council:
   Council Chair, Planner, Critic, Security, UX, QA, Compliance

Faza 12 expanduje na:
  • Multiple templates per goal (z różnymi project types)
  • Fine-tune voting thresholds per template
  • Order of speakers
  • Side-bar consultations (specialists)
  • Template inheritance (modify parent)
  • Per-D-level role scaling
  • Custom templates dla specific scenarios
```

### 12.1.2. Wynik fazy 12 (DoD)

```
✓ Council templates configured (8 baseline minimum)
✓ Template-to-project type mapping
✓ Voting thresholds per template
✓ Per-D-level scaling configured
✓ Custom templates created (jeśli specific potrzeby)
✓ Audit chain entry: phase_12.complete
```

---

## 12.2. Template structure

### 12.2.1. Per-template definition

```yaml
council_template:
  id: ct_public_saas_payment
  name: "Public SaaS z payment integration"
  description: "Customer-facing SaaS z Stripe/payment processing"
  
  applies_to:
    goals: [public_products]
    project_types: [saas, ecommerce]
    has_payment: true
    d_level_min: 3
    d_level_max: 5
  
  roles:
    - role: council_chair
      model_preference: claude-opus
      mandatory: true
      voting_weight: 1.0
    
    - role: planner
      model_preference: claude-sonnet
      mandatory: true
      voting_weight: 1.0
    
    - role: critic
      model_preference: gpt-5
      mandatory: true
      voting_weight: 1.5  # Critic ma stronger vote
    
    - role: security
      model_preference: claude-opus
      mandatory: true
      voting_weight: 1.0
      specialization: payment_security
    
    - role: payment_specialist
      model_preference: claude-opus
      mandatory: true (jeśli has_payment)
      voting_weight: 1.0
      knowledge_base: pci_dss_docs
    
    - role: ux_designer
      model_preference: claude-sonnet
      mandatory: true
      voting_weight: 0.8  # UX advisory
    
    - role: compliance_gdpr
      model_preference: bielik-11b
      mandatory: true
      voting_weight: 1.0
    
    - role: compliance_pci
      model_preference: gpt-5
      mandatory: true (jeśli has_payment)
      voting_weight: 1.0
    
    - role: qa_lead
      model_preference: gpt-5
      mandatory: true
      voting_weight: 0.8
    
    - role: i18n_specialist
      model_preference: claude-sonnet
      mandatory: false (only if i18n)
      voting_weight: 0.5
  
  voting:
    threshold: 0.66  # supermajority
    quorum_min: 6  # min 6 roles must vote
    chair_tiebreak: true
    critic_veto: true (jeśli security/payment veto)
  
  ordering:
    speaker_order: [chair, planner, critic, security, payment, ...]
    rounds_max: 3
    early_consensus_check: after_round_1
  
  cost_profile:
    estimated_per_round: $2.40
    estimated_total: $7.20 (3 rounds)
    
  performance:
    estimated_time: 4-8 min per round
```

### 12.2.2. Voting types

```
Voting types (operator wybiera per template):
  
  Simple majority:    50%+1 votes
  Supermajority:      66%+ votes
  Unanimity:          100% votes
  Weighted:           sum of voting weights > threshold
  Critic veto:        Critic może blokować even if majority
  Specialist override: Domain specialist (Security/Payment) może override
  
  Quorum requirement:
   Min N roles must participate dla decyzja valid
  
  Tie-breaking:
   Chair decides
   Operator decides
   Repeat round
   Default to safer option
```

### 12.2.3. Speaker ordering

```
Why ordering matters:
  Different orderings produce different deliberations.
  
  Standard order:
   Chair → Planner (proposes) → Critic (challenges) → 
   Specialists → Compliance → QA → Chair (synthesizes)
  
  Devil's advocate first:
   Critic → Planner (responds to challenges) → Specialists → ...
   Useful dla: high-stakes, want to surface risks early
  
  Round-robin:
   All speakers in rotation, equal time
   Useful dla: research, brainstorming
  
  Chair-led discussion:
   Chair asks each role specific questions
   Useful dla: interview-style validation
```

---

## 12.3. Baseline 8 templates

### 12.3.1. Template list

```
┌──────────────────────────────────────────────────────────────┐
│  Baseline Council Templates (8)                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. MINIMAL (D1-D2)                                          │
│     Roles: Planner, Critic                                   │
│     For: prototypes, internal experiments                    │
│     Cost per round: $0.40                                    │
│                                                              │
│  2. BALANCED STANDARD (D3)                                   │
│     Roles: Chair, Planner, Critic, Security, QA              │
│     For: most projects                                       │
│     Cost per round: $1.20                                    │
│                                                              │
│  3. PUBLIC SAAS (D3-D4)                                      │
│     Roles: Chair, Planner, Critic, Security, UX, QA,         │
│            Compliance (GDPR)                                 │
│     For: customer-facing SaaS                                │
│     Cost per round: $1.80                                    │
│                                                              │
│  4. PUBLIC SAAS Z PAYMENT (D4-D5)                            │
│     Roles: + Payment Specialist + Compliance (PCI)            │
│     For: SaaS z Stripe/payment processing                    │
│     Cost per round: $2.40                                    │
│                                                              │
│  5. CYBERSECURITY (D4-D5)                                    │
│     Roles: Chair, Planner, Critic, Security, Compliance,     │
│            Risk Assessor, Encryption Auditor                 │
│     For: SYLION-style projects                               │
│     Cost per round: $2.80                                    │
│                                                              │
│  6. RESEARCH (D1-D3)                                         │
│     Roles: Chair, Researcher, Critic                         │
│     For: research, ML experiments                            │
│     Cost per round: $1.00                                    │
│                                                              │
│  7. INTERNAL TOOL (D1-D2)                                    │
│     Roles: Planner, QA                                       │
│     For: internal tools, low stakes                          │
│     Cost per round: $0.30                                    │
│                                                              │
│  8. GOVERNMENT/CLASSIFIED (D5)                               │
│     Roles: Chair, Planner, Critic, Security (deep),          │
│            Compliance (KRI-PL), Risk Assessor, External      │
│            Reviewer (mock), Encryption Auditor               │
│     For: TLP:RED workloads                                   │
│     Cost per round: $4.20                                    │
│     Special: All decisions hard-gated                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 12.3.2. Template selection algorithm

```
Per project (faza 16-17):
  1. Identify project goals
  2. Identify project type (SaaS, internal, research, etc.)
  3. Identify D-level
  4. Identify special requirements (payment, classification)
  
  → Match against templates
  → Recommend best fit
  → Operator can override
  → Operator can fork template dla project-specific tweaks
```

---

## 12.4. Template editor + composition wizard

### 12.4.1. Edytor templates

```
┌──────────────────────────────────────────────────────────────┐
│  Edit Template: Public SaaS z payment                        │
│                                                              │
│  Identity:                                                   │
│   Name: [Public SaaS z payment integration]                  │
│   Description: [...]                                         │
│   ID: ct_public_saas_payment                                 │
│                                                              │
│  Applies to:                                                 │
│   Goals: [☑ public_products] [☐ apps_internal]               │
│   Project types: [☑ saas] [☑ ecommerce]                      │
│   Has payment: [● Yes (mandatory dla template)]              │
│   D-level: [3 ▼] - [5 ▼]                                     │
│                                                              │
│  Roles:                                                      │
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
│  │  + Add role                                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Voting:                                                     │
│   Threshold: [● Supermajority (66%)] [○ Simple] [○ Unanimous]│
│   Quorum:    [6 roles minimum ▼]                             │
│   Chair tie-break: [✓]                                       │
│   Critic veto: [✓]                                           │
│   Specialist override (Security/Payment): [✓]                │
│                                                              │
│  Ordering:                                                   │
│   Speaker order: [Standard ▼] [Edit custom]                  │
│   Max rounds: [3 ▼]                                          │
│   Early consensus: [After round 1 ▼]                         │
│                                                              │
│  Cost & time:                                                │
│   Estimated cost per round: $2.40                            │
│   Estimated total: $7.20 (3 rounds)                          │
│   Estimated time: 4-8 min per round                          │
│                                                              │
│  [Save template]  [Cancel]  [Test on sample project]         │
└──────────────────────────────────────────────────────────────┘
```

### 12.4.2. Composition wizard

Wizard pomaga zbudować nowy template (ulepszony z fazy 4.12.3):

```
┌──────────────────────────────────────────────────────────────┐
│  Council Composition Wizard                                  │
│                                                              │
│  Quick questions:                                            │
│                                                              │
│  Project type: [Web SaaS ▼]                                  │
│  Industry: [Fintech ▼]                                       │
│  Compliance:                                                 │
│   ☑ GDPR  ☑ PCI DSS  ☐ HIPAA  ☐ KRI-PL  ☐ SOC 2             │
│  Has payment: [Yes ▼]                                        │
│  Multilanguage: [PL + EN + DE ▼]                             │
│  D-level: [4 ▼]                                              │
│                                                              │
│  Recommended roles:                                          │
│   ✓ Council Chair                                            │
│   ✓ Planner                                                  │
│   ✓ Critic                                                   │
│   ✓ Security (mandatory dla fintech)                         │
│   ✓ Payment Specialist (mandatory dla payment)               │
│   ✓ Compliance GDPR (mandatory)                              │
│   ✓ Compliance PCI (mandatory dla payment)                   │
│   ✓ Compliance KSeF (PL fintech regulation)                  │
│   ✓ UX Designer                                              │
│   ✓ Risk Assessor (recommended dla D4)                       │
│   ✓ i18n Specialist (multilanguage)                          │
│   ✓ QA Lead                                                  │
│                                                              │
│  Total: 12 roles                                             │
│  Estimated cost per round: $3.20                             │
│  Estimated total: $9.60 (3 rounds)                           │
│                                                              │
│  [Customize]  [Save as template]  [Use for project]          │
└──────────────────────────────────────────────────────────────┘
```

---

## 12.5. Per-D-level scaling

### 12.5.1. Auto-scaling roles per D-level

Same template auto-scales:

```
Template: "Public SaaS z payment"

D1-D2 (trivial/light):
  Skip: UX, Compliance details, Risk Assessor
  Active: Chair, Planner, Critic, Security, Payment, QA
  Cost per round: $1.40

D3 (standard):
  Skip: Risk Assessor (optional)
  Active: All except Risk Assessor
  Cost per round: $2.00

D4 (production):
  Active: Wszystkie roles
  Cost per round: $2.40
  Add: External Reviewer mock

D5 (critical):
  Active: All + Encryption Auditor
  Cost per round: $3.00
  All decisions hard-gated
  Min 3 rounds (no early consensus)
```

---

## 12.6. Edge Cases — Council Templates (15 cases)

### Kategoria A — Template fit (4 cases)

#### EC-A1: No template matches project

**Trigger**: Operator's project doesn't fit any baseline template.

```
ℹ No template match

  Project: Customer-specific industrial monitoring
  Goals: cybersecurity + apps_internal (mixed)
  Industry: manufacturing (no template)
  
  Akcje:
   [Use closest template (cybersecurity) + customize]
   [Build new template via wizard]
   [Use minimal template, add roles ad-hoc]
```

#### EC-A2: Template too heavy dla project

**Trigger**: Template ma 12 roles, project simple. Cost overkill.

```
⚠ Template overhead

  Template: "Public SaaS z payment" (12 roles, $3.20/round)
  Project: simple landing page (no payment, low complexity)
  
  Mismatch: D4-tier Council dla D2 project
  
  Akcje:
   [Use simpler template (Balanced Standard, $1.20)]
   [Custom template z fewer roles]
   [Operator override (use heavy template anyway)]
```

#### EC-A3: Template missing role

**Trigger**: Project needs Polish accessibility expert. Templates don't
include.

```
ℹ Custom role needed

  Project: Public Polish gov portal
  Compliance: WCAG 2.1 AA dla public sector
  Standard templates: no Polish accessibility role
  
  Akcje:
   [Add custom role "Polish Accessibility Specialist"]
   [Import from marketplace]
   [Use generic Accessibility role z PL knowledge base]
```

#### EC-A4: Template applies but operator disagrees

**Trigger**: System recommends heavy template. Operator wants lighter.

```
ℹ Template recommendation override

  Recommended: Cybersecurity template (heavy, $2.80/round)
  Operator wants: Balanced Standard ($1.20)
  
  Reason: "Internal cybersec experiment, lower stakes than usual"
  
  Akcje:
   [Use Balanced Standard (operator's choice)]
   [Document rationale w project notes]
   [Audit chain entry: template_override z reason]
```

### Kategoria B — Voting issues (4 cases)

#### EC-B1: Quorum not met

**Trigger**: Template requires 6 roles voting. Only 4 responded (2 timed
out).

```
⚠ Quorum failure

  Required: 6/9 roles vote
  Got: 4/9 (2 timed out, 3 didn't speak)
  
  Akcje:
   [Re-run round (give more time)]
   [Lower quorum dla this round]
   [Skip non-responding roles' inputs]
   [Operator manual decision]
```

#### EC-B2: Tied vote, no tie-breaker

**Trigger**: 4 vs 4 split. Chair tie-break disabled in template.

```
⚠ Tied vote

  Result: 4 yes, 4 no, 0 abstain
  Tie-breaker: not configured
  
  Akcje:
   [Operator decides]
   [Re-run z additional round]
   [Add Chair tie-break (modify template)]
   [Default to safer option (no)]
```

#### EC-B3: Critic veto unexpected

**Trigger**: Critic vetoed despite majority approval. Operator surprised.

```
ℹ Critic veto used

  Vote: 7 yes, 1 no (Critic)
  Critic veto: enabled w template
  Result: BLOCKED
  
  Critic reasoning:
   "Identified critical security issue not addressed"
  
  Akcje:
   [Address Critic's concern]
   [Operator override veto]
   [Disable Critic veto dla future]
```

#### EC-B4: Specialist override disagreement

**Trigger**: Security specialist override z opinion że plan unsafe. Other
roles disagree.

```
⚠ Specialist override

  Plan: deploy z minor security finding
  Security specialist: OVERRIDE (refuses to allow)
  Other roles (8): disagree (consider OK)
  
  Akcje:
   [Honor specialist override (default safer)]
   [Operator decides (specialist's domain expertise)]
   [Escalate do operator z full context]
```

### Kategoria C — Template management (4 cases)

#### EC-C1: Template version conflict

**Trigger**: Project started z template v1.0. Template updated do v2.0
(breaking) mid-project.

```
ℹ Template version drift

  Project: started z template v1.0
  Current: template v2.0 (breaking changes)
  
  Akcje:
   [Project locked to v1.0 (creation version)]
       Continues z stable
   [Migrate project do v2.0]
       Possible adjustments needed
   [Fork v1.0 dla this project's needs]
```

#### EC-C2: Custom template lost po AEIS update

**Trigger**: AEIS update changed template format. Custom template incompatible.

```
⚠ Template incompatibility

  Custom template: "Custom for Customer X"
  AEIS update: changed role schema
  Status: template won't load
  
  Akcje:
   [Auto-migrate template]
   [Manual rewrite]
   [Disable template]
```

#### EC-C3: Template dependencies (skills, knowledge bases)

**Trigger**: Template references skills/KBs that don't exist.

```
⚠ Template dependencies missing

  Template: Cybersecurity
  Required: skill "OWASP Top 10 audit" (missing)
  Required: KB "PL government cybersec docs" (missing)
  
  Akcje:
   [Install missing dependencies]
       Auto-import from marketplace
   [Adapt template (use available alternatives)]
   [Skip template]
```

#### EC-C4: Template testing on sample fails

**Trigger**: Operator tests new template. Sample project deliberation
fails.

```
⚠ Template test failure

  Test project: simple landing page
  Template: Public SaaS z payment (12 roles)
  
  Issue: roles fight over irrelevant scope
   • Payment Specialist: "no payment, why am I here?"
   • Compliance PCI: "no payment, irrelevant"
  
  Akcje:
   [Don't apply template to projects without payment]
   [Make payment-specific roles conditional]
   [Use lighter template]
```

### Kategoria D — Recovery (3 cases)

#### EC-D1: Template database corruption

**Trigger**: Template definitions corrupted.

```
⚠ Templates corrupted

  Lost: 3 custom templates
  Baseline: intact
  
  Akcje:
   [Restore z backup]
   [Recreate manually]
```

#### EC-D2: Workspace import — templates

**Trigger**: Operator imports workspace. Templates need migration.

```
ℹ Templates migration

  Imported: 8 baseline + 5 custom
  Compatible: all 8 baseline
  Custom: 3 compatible, 2 need migration
  
  Akcje:
   [Auto-migrate compatible]
   [Manual review incompatible]
```

#### EC-D3: Cross-workspace template sharing

**Trigger**: Operator wants share template z another operator (team).

```
ℹ Template sharing

  Template: "Custom for Customer X"
  Recipient: another operator (team member)
  
  Akcje:
   [Export template (signed by operator)]
   [Recipient imports z trust verification]
   [Marketplace publish (alternative)]
```

---

## 12.7. Inheritance + DoD — Council Templates

```bash
$ aeis-cli phase12-acceptance-test

[Common requirements]
[1/4] Templates configured (8 baseline)              ✓ PASS
[2/4] Template-to-project mapping                    ✓ PASS
[3/4] Per-D-level scaling                            ✓ PASS
[4/4] Audit chain entry phase_12.complete            ✓ PASS

[Optional]
[5/6] Custom templates count                         ℹ INFO (3 created)
[6/6] Composition wizard tested                      ✓ PASS

DoD: 4/4 ✓
Phase 12 ACCEPTED.
```

---

# FAZA 13 — Test Strategy Templates

> **Spis sekcji**:
> - 13.1 — Sense fazy + relacja do faz 4 (default test strategy)
> - 13.2 — Test strategy structure
> - 13.3 — Baseline 5 strategies
> - 13.4 — Custom strategy builder
> - 13.5 — Edge cases (15) + DoD

---

## 13.1. Sens fazy

Faza 4 ustanowiła **mandatory human-like UI testing** + L1+L2+L3 default.
Faza 13 to **deep test strategy management** — multiple strategies per
project type.

### 13.1.1. Wynik fazy 13 (DoD)

```
✓ Test strategies configured (5 baseline)
✓ Strategy-to-project mapping
✓ Mandatory human-like preserved across all strategies
✓ Custom strategies dla specific potrzeb
✓ Audit chain entry: phase_13.complete
```

---

## 13.2. Test strategy structure

```yaml
test_strategy:
  id: ts_minimal_internal
  name: "Minimal — internal tools"
  description: "Quick tests dla low-stakes internal projects"
  
  applies_to:
    project_types: [internal_tool, prototype]
    d_level_max: 2
  
  levels:
    L1_unit:
      enabled: true
      coverage_target: 60%  # lower for internal
      framework: pytest / vitest
      cost_per_run: ~$0.05
    
    L2_integration:
      enabled: true
      scope: critical_paths_only
      framework: pytest fixtures
      cost_per_run: ~$0.10
    
    L3_e2e:
      enabled: false  # skip for internal
    
    L4_performance:
      enabled: false
    
    L5_human_like_ui:
      enabled: true  # MANDATORY
      scenarios_min: 8  # reduced for internal
      cost_per_run: ~$3.20
  
  quality_gates:
    block_deploy_if:
      - L1 coverage < 50%
      - L1 failed > 5
      - L5 critical scenarios fail
    warn_if:
      - L2 coverage < 70%
      - performance regression > 30%
  
  estimated_total:
    cost: ~$3.50 per build
    time: ~5-8 min
```

---

## 13.3. Baseline 5 strategies

```
┌──────────────────────────────────────────────────────────────┐
│  Baseline Test Strategies (5)                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. MINIMAL — internal tools                                 │
│     Levels: L1, L2, L5 (mandatory)                           │
│     Coverage: 60%                                            │
│     Cost: ~$3.50 per build                                   │
│                                                              │
│  2. STANDARD — most projects (default)                       │
│     Levels: L1, L2, L3, L5                                   │
│     Coverage: 80%                                            │
│     Cost: ~$8 per build                                      │
│                                                              │
│  3. COMPREHENSIVE — production                               │
│     Levels: L1, L2, L3, L5 + L4 pre-prod                     │
│     Coverage: 85%                                            │
│     Cost: ~$15 per build                                     │
│                                                              │
│  4. CRITICAL — D4-D5 production                              │
│     Levels: All (L1-L5)                                      │
│     Coverage: 90% + critical paths 95%                       │
│     Cost: ~$30 per build                                     │
│     Mutation testing enabled                                 │
│                                                              │
│  5. RESEARCH — research/experiments                          │
│     Levels: L1 light + L5 (mandatory)                        │
│     Coverage: 50% (research focus on functionality)          │
│     Cost: ~$5 per build                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 13.4. Custom strategy builder

```
┌──────────────────────────────────────────────────────────────┐
│  Build Custom Test Strategy                                  │
│                                                              │
│  Name: [ Strategy for Customer Y                          ]  │
│                                                              │
│  Project applies:                                            │
│   Project type: [SaaS ▼]                                     │
│   D-level: [4 ▼]                                             │
│   Customer-specific: [Customer Y]                            │
│                                                              │
│  Test levels:                                                │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  L1 Unit                                               │ │
│  │   ☑ Enabled                                            │ │
│  │   Coverage target: [85%]                               │ │
│  │   Framework: [pytest + coverage.py ▼]                  │ │
│  │                                                        │ │
│  │  L2 Integration                                        │ │
│  │   ☑ Enabled                                            │ │
│  │   Scope: [API + DB integration]                        │ │
│  │                                                        │ │
│  │  L3 E2E                                                │ │
│  │   ☑ Enabled                                            │ │
│  │   Scope: [critical user journeys (8 scenarios)]        │ │
│  │                                                        │ │
│  │  L4 Performance                                        │ │
│  │   ☑ Enabled                                            │ │
│  │   Run frequency: [pre-prod only]                       │ │
│  │   Load: [100 concurrent users]                         │ │
│  │                                                        │ │
│  │  L5 Human-like UI                                      │ │
│  │   ☑ ENABLED (MANDATORY)                                │ │
│  │   Scenarios: [25-40 (auto-generated z Księga)]         │ │
│  │   Customer-specific: ☑ "test customer's specific edge   │ │
│  │     case forms (z previous bug reports)"               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Quality gates:                                              │
│   Block deploy if:                                           │
│    ☑ Any L5 scenario fails                                   │
│    ☑ L1 coverage < 80%                                       │
│    ☑ L4 P95 latency > 500ms                                  │
│    ☑ Customer-specific tests fail                            │
│                                                              │
│  [Save strategy]                                             │
└──────────────────────────────────────────────────────────────┘
```

---

## 13.5. Edge Cases — Test Strategy (15 cases)

Kompresja: główne scenariusze, każde 2-3 zdania.

### Kategoria A — Strategy fit (3)

**EC-A1**: No strategy matches → use closest + customize
**EC-A2**: Strategy too heavy dla project → use lighter
**EC-A3**: Strategy too light dla customer requirements → upgrade

### Kategoria B — Coverage issues (4)

**EC-B1**: Coverage target unrealistic → calibrate based on data
**EC-B2**: Coverage gaming (low-quality tests) → mutation testing
**EC-B3**: Critical paths uncovered → per-module targets
**EC-B4**: Coverage tool inconsistencies → standardize tool

### Kategoria C — Test execution (4)

**EC-C1**: Flaky tests → retry policy
**EC-C2**: Test environment unavailable → degraded mode
**EC-C3**: Test data corruption → regenerate
**EC-C4**: Tests slow → parallelize + optimize

### Kategoria D — Human-like UI specific (2)

**EC-D1**: Customer-side data needed → use synthetic + flagged
**EC-D2**: Visual regression false positives → tolerance tuning

### Kategoria E — Recovery (2)

**EC-E1**: Strategy lost po update → restore z backup
**EC-E2**: Migration test history → mark transition

---

## 13.6. Inheritance + DoD — Test Strategy

```bash
$ aeis-cli phase13-acceptance-test

[1/4] Strategies configured (5 baseline)             ✓ PASS
[2/4] Mandatory human-like preserved                 ✓ PASS
[3/4] Strategy-to-project mapping                    ✓ PASS
[4/4] Audit chain entry phase_13.complete            ✓ PASS

DoD: 4/4 ✓
Phase 13 ACCEPTED.
```

---

# FAZA 14 — Deployment Templates

> **Spis sekcji**:
> - 14.1 — Sense fazy + relacja do fazy 3 (environments)
> - 14.2 — Template structure
> - 14.3 — Baseline 6 templates
> - 14.4 — Edge cases (15) + DoD

---

## 14.1. Sens fazy

Faza 3 ustawiła **environments**. Faza 14 ustawia **deployment templates**
— jak deploy do tych environments.

### 14.1.1. Wynik fazy 14 (DoD)

```
✓ Deployment templates configured (6 baseline)
✓ Per-environment deployment patterns
✓ Rollback strategies defined
✓ Hard gate "production deploy" preserved
✓ Audit chain entry: phase_14.complete
```

---

## 14.2. Template structure

```yaml
deployment_template:
  id: dt_canary_production
  name: "Canary deploy do production"
  description: "Multi-stage canary z automatic rollback"
  
  applies_to:
    environment_types: [production]
    project_types: [public_products, customer_facing]
    d_level_min: 3
  
  stages:
    - stage: pre_deploy
      actions:
        - run_full_test_suite
        - verify_no_critical_security_findings
        - verify_budget_available
        - verify_dns_ready
      gates:
        - all_tests_pass
        - security_clean
        - operator_approval (hard gate)
    
    - stage: canary_5pct
      actions:
        - deploy_to_canary
        - route_5pct_traffic
        - monitor_30_min
      gates:
        - error_rate < 0.1%
        - latency_p95 < 500ms
    
    - stage: canary_25pct
      actions:
        - increase_canary_traffic_25pct
        - monitor_30_min
      gates:
        - error_rate < 0.1%
    
    - stage: canary_50pct
      actions:
        - increase_canary_traffic_50pct
        - monitor_15_min
      gates:
        - error_rate < 0.1%
    
    - stage: full_rollout
      actions:
        - deploy_to_all_instances
        - decommission_old_version (z grace period)
      gates:
        - operator_final_approval
    
    - stage: post_deploy
      actions:
        - run_smoke_tests
        - notify_customers (if applicable)
        - update_documentation
        - audit_log
  
  rollback:
    automatic_triggers:
      - error_rate > 1%
      - latency_p95 > 2x_baseline
      - critical_alert
    manual_trigger:
      - operator command
    rollback_actions:
      - stop_canary
      - restore_previous_version
      - notify_operator
      - audit_log
  
  estimated_time:
    happy_path: 90 min (incl. monitoring)
    rollback: 5 min
  
  cost_profile:
    estimated: $5-15 per deploy
```

---

## 14.3. Baseline 6 templates

```
1. SIMPLE DEPLOY — single stage replacement
   For: dev/staging environments
   Time: 5-15 min

2. ROLLING DEPLOY — gradual instance replacement
   For: small production, no canary infrastructure
   Time: 15-45 min

3. CANARY DEPLOY — multi-stage z monitoring
   For: production z customer traffic
   Time: 90-180 min (z full monitoring)

4. BLUE-GREEN — parallel environments swap
   For: zero-downtime requirements
   Time: 30-60 min

5. AIR-GAPPED DEPLOY — package + manual transfer
   For: sovereign environments without internet
   Time: depends on operator

6. EDGE FLEET DEPLOY — bulk update do edge devices
   For: customer-side RPi/edge updates
   Time: depends on fleet size
```

---

## 14.4. Edge Cases — Deployment (15 cases)

### Kategoria A — Deploy stages (4)

**EC-A1**: Canary stage fails → automatic rollback
**EC-A2**: Pre-deploy gate timeout → operator escalation
**EC-A3**: Full rollout slow → operator monitoring
**EC-A4**: DNS propagation issue → wait + retry

### Kategoria B — Rollback (4)

**EC-B1**: Automatic rollback triggered → notify + audit
**EC-B2**: Rollback fails → manual intervention
**EC-B3**: Rollback after data migration → schema mismatch
**EC-B4**: Customer-facing impact → notification + apology

### Kategoria C — Edge fleet (3)

**EC-C1**: Mixed update results (some succeed) → per-device handling
**EC-C2**: Customer-side network issues → retry + escalation
**EC-C3**: Hardware diversity (different Pi versions) → conditional deploys

### Kategoria D — Air-gapped (2)

**EC-D1**: Manual transfer delays → status tracking
**EC-D2**: Sync conflicts → resolution workflow (z faza 3 EC-D3)

### Kategoria E — Recovery (2)

**EC-E1**: Template corruption → restore
**EC-E2**: Customer-specific deployment requirements → custom template

---

## 14.5. Inheritance + DoD — Deployment

```bash
$ aeis-cli phase14-acceptance-test

[1/5] Templates configured (6 baseline)              ✓ PASS
[2/5] Per-environment patterns                       ✓ PASS
[3/5] Rollback strategies                            ✓ PASS
[4/5] Hard gate preserved                            ✓ PASS
[5/5] Audit chain entry phase_14.complete            ✓ PASS

DoD: 5/5 ✓
Phase 14 ACCEPTED.
```

---

# FAZA 15 — Cost & Budget Policies

> **Spis sekcji**:
> - 15.1 — Sense fazy + relacja do faz 4 (budget templates) + 7 (Cost Guard)
> - 15.2 — Policy structure
> - 15.3 — Baseline 5 policies
> - 15.4 — Customer-specific cost policies
> - 15.5 — Edge cases (15) + DoD

---

## 15.1. Sens fazy

Faza 4 ustawiła **budget templates** (small/medium/large/enterprise).
Faza 7 ustawiła **Cost Guard** enforcement. Faza 15 ustawia **policies**
— compleksowe rules łączące budgets, autonomy, cost decisions.

### 15.1.1. Wynik fazy 15 (DoD)

```
✓ Cost policies configured (5 baseline)
✓ Customer-specific policies (jeśli applicable)
✓ Approval workflows defined
✓ Cost reporting integrated z policies
✓ Audit chain entry: phase_15.complete
```

---

## 15.2. Policy structure

```yaml
cost_policy:
  id: cp_strict_customer
  name: "Strict customer-funded project"
  description: "Customer pays — strict accountability"
  
  applies_to:
    project_types: [customer_funded]
    customer_specific: true
  
  budget_rules:
    template: large  # use LARGE template z fazy 4
    hard_cap: $250
    soft_cap: $200 (operator approval beyond)
    customer_visible: true  # transparency
  
  approval_workflows:
    spike_approval:
      threshold: $5
      who_approves: operator
      timeout: 30 min
    
    overrun_approval:
      threshold: 90% budget
      who_approves: operator + customer (notify)
      timeout: 2h
    
    customer_notification:
      events:
        - 50% spend (info)
        - 80% spend (warning)
        - 100% spend (require approval before continue)
  
  reporting:
    customer_facing:
      - weekly cost report
      - project closure report z full breakdown
    operator_internal:
      - daily cost monitoring
      - weekly trend analysis
  
  auto_actions:
    autonomy: Conservative  # NIE auto-action customer money
    only_notify: true
```

---

## 15.3. Baseline 5 policies

```
1. INTERNAL — operator-funded internal projects
   Hard cap: workspace budget
   Approval: operator only
   Reporting: operator-internal

2. STRICT CUSTOMER — customer pays, strict
   Hard cap: contracted amount
   Approval: operator + customer notify
   Reporting: customer-facing transparent

3. FLEXIBLE CUSTOMER — customer pays, flexible
   Hard cap: contracted amount × 1.5
   Approval: operator + customer override
   Reporting: customer-facing summary

4. RESEARCH — operator's research budget
   Hard cap: monthly research allocation
   Approval: operator only
   Reporting: monthly research summary

5. EXPERIMENTAL — small budgets dla quick tests
   Hard cap: $20 per project
   Approval: auto for spike <$2
   Reporting: aggregate weekly
```

---

## 15.4. Customer-specific cost policies

```
┌──────────────────────────────────────────────────────────────┐
│  Customer Cost Policy — Customer Acme                        │
│                                                              │
│  Contract:                                                   │
│   Total budget: €5,000 (annual)                              │
│   Per-project cap: €500                                      │
│   Overrun policy: customer approves above 110%                │
│                                                              │
│  Payment:                                                    │
│   Frequency: monthly invoice                                 │
│   Currency: EUR                                              │
│   Includes: AEIS costs + vendor pass-through                 │
│                                                              │
│  Customer visibility:                                         │
│   ☑ Real-time cost dashboard (customer login)                │
│   ☑ Weekly summary email                                     │
│   ☑ Project-by-project breakdown                             │
│   ☑ Invoice items detailed                                   │
│                                                              │
│  Approval workflows:                                          │
│   Per-call > €5: operator approves                           │
│   Per-project > 80% cap: customer notification               │
│   Per-project > 100% cap: customer approves                  │
│   Annual > 100%: contract renegotiation                      │
│                                                              │
│  Special rules:                                              │
│   ☑ Customer-private data → never use shared models          │
│   ☑ EU data residency required (z faza 3.9)                  │
│   ☑ GDPR compliance reporting (z faza 8)                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 15.5. Edge Cases — Cost Policies (15 cases)

### Kategoria A — Budget caps (4)

**EC-A1**: Hard cap reached mid-deploy → grace handling
**EC-A2**: Customer-funded overrun → customer approval workflow
**EC-A3**: Annual budget exhausted → contract renegotiation
**EC-A4**: Currency fluctuation EUR/USD → tracking adjustments

### Kategoria B — Approval workflows (4)

**EC-B1**: Customer doesn't respond → escalation
**EC-B2**: Operator absent + customer needs approval → fallback
**EC-B3**: Approval timeout during critical work → conservative default
**EC-B4**: Multi-party approvals conflict → resolution workflow

### Kategoria C — Customer-specific (4)

**EC-C1**: Customer dispute charges → audit trail evidence
**EC-C2**: Customer requests refund → policy framework
**EC-C3**: Multi-customer project → cost split rules
**EC-C4**: Customer-side credentials issues → operator covers temporarily

### Kategoria D — Reporting issues (2)

**EC-D1**: Customer report shows incorrect data → reconciliation
**EC-D2**: Vendor pass-through delayed → estimate vs actual

### Kategoria E — Recovery (1)

**EC-E1**: Policy corruption → restore + customer notify

---

## 15.6. Inheritance + DoD — Cost Policies

```bash
$ aeis-cli phase15-acceptance-test

[1/5] Policies configured (5 baseline)               ✓ PASS
[2/5] Customer-specific policies                     ✓ PASS
[3/5] Approval workflows defined                     ✓ PASS
[4/5] Reporting integration                          ✓ PASS
[5/5] Audit chain entry phase_15.complete            ✓ PASS

DoD: 5/5 ✓
Phase 15 ACCEPTED.

═══ GROUP A2 (Templates) COMPLETE ═══
Ready to proceed to Phase 16 (Project Inception, Group B).
```

---

# Status faz 11-15

🟢 **Wszystkie 5 faz complete**

**Zawiera**:
- ✓ Faza 11 — Skills Library Bootstrap (4 typy skills, 25 baseline, 4 mechanisms creation, marketplace, 20 edge cases)
- ✓ Faza 12 — Council Templates (8 baseline templates, voting structure, composition wizard, per-D-level scaling, 15 edge cases)
- ✓ Faza 13 — Test Strategy Templates (5 baseline, mandatory human-like preserved, 15 edge cases)
- ✓ Faza 14 — Deployment Templates (6 baseline incl. canary/blue-green/air-gapped/edge fleet, 15 edge cases)
- ✓ Faza 15 — Cost & Budget Policies (5 baseline + customer-specific, 15 edge cases)

**Total edge cases w pliku**: 80 (20+15+15+15+15)

**Grupa A (Przygotowanie Operatora) COMPLETE**: 11 faz
**Grupa A2 (Templates) COMPLETE**: 4 fazy
**Łącznie 15 z 41 faz frozen**

⏳ **Po Twojej akceptacji** → **soft freeze faz 11-15** + przejście do **Faza 16 — Project Inception** (start grupy B "Start projektu").

⚠ **Zmiana charakteru** od fazy 16: dotychczas konfigurowaliśmy operatora.
Od fazy 16 zaczynamy **lifecycle projektu** — operator faktycznie używa
skonfigurowanej infrastruktury żeby budować software.
