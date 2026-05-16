# FAZA 6 — Coherence Guard

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (6 z 11) — Guards Setup (1 z 5)
> **Typ**: jednorazowa konfiguracja, ciągłe działanie w tle
> **Czas wykonania**: 5 min (akceptacja defaults) / 30-45 min (full custom checks)
> **D-level**: D2 — Guard działa na sensitive artifacts (Księgi, masterplan, code)
> **Zależności**: Faza 4 (workspace defaults), Faza 5 (autonomy preset, hard gates)
> **Następnik**: Faza 7 (Cost Guard — drugi z 5 Guards)
>
> **Spis sekcji**:
> - 6.1 — Sense fazy + Coherence Guard w architekturze AEIS
> - 6.2 — Scope (docs+code+tests+deployment + optional cross-project)
> - 6.3 — Triggers (hybrid: phase boundaries + continuous + on-demand)
> - 6.4 — Severity levels (5: info / warning / error / critical / blocker)
> - 6.5 — Detection mechanisms (rules + LLM hybrid)
> - 6.6 — Baseline 15 checks + custom checks (3 mechanisms)
> - 6.7 — Findings handling (adaptive per autonomy)
> - 6.8 — Performance (separate worker, tiered cost, smart caching)
> - 6.9 — Aggregated Guards panel + per-Guard autonomy override
> - 6.10 — Edge cases (22) + inheritance + DoD

---

## 6.1. Sens fazy i Coherence Guard w architekturze AEIS

### 6.1.1. Czym jest Coherence Guard

**Coherence Guard** to **subsystem** który ciągle czyta artifacts AEIS i
flaguje **niespójności** — miejsca gdzie różne źródła "mówią coś innego".

Przykłady niespójności które Guard wykrywa:

```
Przykład 1 — Internal coherence dokumentów:
  Księga §3 mówi: "Aplikacja wspiera EUR + PLN + GBP"
  Masterplan §6 mówi: "Currency module: EUR + PLN"
  ⚠ Coherence Guard: brak GBP w masterplanie (Księga ↔ masterplan)

Przykład 2 — Cross-time:
  Faza 23 Council decision: "Use Stripe dla payments"
  Faza 33 build: operator override → "Use Adyen instead"
  ⚠ Coherence Guard: deviation z Council decision bez explicit ownership

Przykład 3 — Cross-language:
  PL: "Wymaga zatwierdzenia administratora"
  EN: "Requires admin approval"
  DE: "Erfordert Genehmigung" (missing "admin")
  ⚠ Coherence Guard: semantic mismatch między PL/EN i DE

Przykład 4 — Cross-module:
  Frontend API call: POST /api/v2/orders { items: [...] }
  Backend route: POST /api/v2/orders { products: [...] }
  ⚠ Coherence Guard: API contract mismatch (items vs products)

Przykład 5 — Cross-time (operator overrides):
  Faza 17 override: "DIM-3 Cost = L4 dla tego projektu"
  Faza 22 round override: "DIM-3 = L1 dla tej rundy"
  Faza 25: round complete, ale L1 override zostaje active
  ⚠ Coherence Guard: ghost override z zakończonej rundy
```

### 6.1.2. Coherence Guard vs inne mechanizmy

W AEIS są inne mechanizmy quality:
- **Council deliberation** — pre-execution validation (czy plan jest dobry)
- **Quality Guard** (faza 9) — testowanie kodu i deploymentu (czy build działa)
- **Provenance Guard** (faza 10) — czy każdy artifact ma audit trail

**Coherence Guard zajmuje unikalny middle ground**: sprawdza czy **różne
artifacts są zgodne ze sobą**. Nie pyta "czy to działa" (Quality Guard) ani
"czy ma evidence" (Provenance Guard) — pyta "czy są spójne".

### 6.1.3. Wynik fazy 6 (DoD)

Po fazie 6, operator ma:
- ✓ Coherence Guard skonfigurowany (scope, triggers, severity thresholds)
- ✓ Baseline 15 checks aktywne lub świadomie wyłączone
- ✓ Custom checks zdefiniowane (jeśli potrzebne)
- ✓ Findings handling pattern ustanowiony (per autonomy)
- ✓ Per-Guard autonomy override (jeśli różny niż faza 5)

---

## 6.2. Scope Coherence Guard (P6.1=c + opcja d)

### 6.2.1. Standard scope (default)

Standardowy scope obejmuje **4 kategorie artifacts**:

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Guard — Standard Scope                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ DOCUMENTS                                                 │
│      • Księga (project ontology)                             │
│      • Masterplan (build plan)                               │
│      • Test Plan                                             │
│      • Council Book (deliberation outcomes)                  │
│      • Deployment manifest                                   │
│      • Acceptance criteria                                   │
│                                                              │
│  ☑ CODE                                                      │
│      • Generated code (frontend, backend, workers)           │
│      • Configuration files (env, yaml, json)                 │
│      • Database migrations                                   │
│      • API definitions (OpenAPI, GraphQL schemas)            │
│                                                              │
│  ☑ TESTS                                                     │
│      • Unit test definitions                                 │
│      • Integration test scenarios                            │
│      • E2E test scripts                                      │
│      • Human-like UI test scenarios                          │
│      • Test gold standards (sample data)                     │
│                                                              │
│  ☑ DEPLOYMENT                                                │
│      • Environment configurations                            │
│      • Deploy manifests                                      │
│      • Rollback scripts                                      │
│      • Monitoring/alerting configs                           │
│      • Infrastructure-as-code (Terraform, etc.)              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.2.2. Cross-project scope (opcjonalnie, opt-in)

Operator może rozszerzyć scope o **cross-project coherence**:

```
┌──────────────────────────────────────────────────────────────┐
│  Cross-Project Coherence (advanced, opt-in)                  │
│                                                              │
│  ☐ Cross-project pattern check                               │
│      Wykrywa gdy nowy projekt łamie patterns z poprzednich   │
│      Examples:                                                │
│       • Stack changes (React → Vue bez explicit reason)      │
│       • Auth pattern changes (OAuth → session bez powodu)    │
│       • DB schema patterns (snake_case → camelCase mix)      │
│                                                              │
│  ☐ Cross-project naming consistency                          │
│      Wykrywa naming differences (Customer vs Client vs User) │
│                                                              │
│  ☐ Cross-project library version drift                       │
│      Flagi gdy projekt używa stale library versions          │
│                                                              │
│  ☐ Customer-side coherence                                    │
│      Dla customer projektów: wykryj że customer A i customer │
│      B z similar industry mają divergent solutions           │
│                                                              │
│  ☐ Lessons-learned propagation                                │
│      Lessons z fazy 41 Closure z poprzednich projektów —    │
│      sprawdź czy są applied w nowych                         │
│                                                              │
│  ⚠ Cross-project costs więcej (analiza wszystkich projektów). │
│    Recommended: enable po 5+ projektach gdy wzorce widoczne. │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Konsekwencje cross-project enable**:
- Guard cost: +50-100% (więcej artifacts do analizy)
- Performance: dłuższe checks (szczególnie continuous mode)
- Value: wykrywanie organizational drift, naming inconsistencies, repeating
  mistakes

**Recommendation**: zacznij OFF, włącz po 5-10 projektach gdy operator widzi
wzorce.

### 6.2.3. Scope per-project override

Operator może zmienić scope per projekt w fazie 17:

```
Project: Sylion Tailor v3 → Coherence Guard Scope

  Inherited from Phase 6: Standard (4 categories)
  Override:
   ☑ Documents
   ☑ Code
   ☑ Tests
   ☐ Deployment  ← disabled (operator handles deploy manually)
   ☑ Cross-project (enabled dla tego projektu only)
       Compare with: [Sylion Tailor v1, Sylion Tailor v2]
```

---

## 6.3. Triggers — kiedy Guard działa (P6.2=d hybrid)

### 6.3.1. Trzy mechanizmy triggerów

**Trigger 1 — Phase boundaries (auto)**:

Guard runs przy końcu critical fazy:

```
Phase boundaries dla Coherence Guard runs:
  
  Faza 25 (Book Finalization)     → check: Księga internal coherence
  Faza 28 (Masterplan Synthesis)  → check: Księga ↔ masterplan
  Faza 29 (Test Plan Synthesis)   → check: masterplan ↔ test plan
  Faza 35 (Build Orchestration)   → check: code ↔ tests ↔ docs
  Faza 37 (Quality Gates)         → check: tests results ↔ acceptance
  Faza 39 (Deployment Config)     → check: deployment ↔ environment
  Faza 41 (Closure)               → final check: artifacts coherence
```

Per phase boundary, Guard run trwa ~30 sek - 5 min zależnie od scope.

**Trigger 2 — Continuous (background)**:

Guard ciągle monitoruje workspace:

```
Continuous monitoring:
  
  • File system watcher: gdy plik artifact się zmienia
  • Edit detection: operator edits Księgę / masterplan / kod
  • Sync events: workspace import / restore / migration
  • Dependency changes: package.json / requirements.txt updates
  
  Throttling: max 1 check per file per minute
  Batching: collect changes for 5 sek, then run check
```

**Trigger 3 — On-demand (manual)**:

Operator klika "Run coherence check" w dowolnej chwili:

```
┌────────────────────────────────────────────────────────┐
│  Run Coherence Check                                   │
│                                                        │
│  Scope: [Current project ▼]                            │
│  Depth: [● Standard]  [○ Quick]  [○ Deep]              │
│  Cost estimate: ~$0.40                                 │
│                                                        │
│  Or specific:                                          │
│   ☑ Documents (Księga ↔ masterplan ↔ tests)            │
│   ☐ Code coherence                                     │
│   ☐ Cross-language i18n                                │
│   ☐ Deployment configs                                 │
│   ☐ Cross-project patterns                             │
│                                                        │
│  [Run check]  [Cancel]                                 │
└────────────────────────────────────────────────────────┘
```

### 6.3.2. Triggers configuration

```
Settings → Coherence Guard → Triggers

  ☑ Phase boundaries (recommended ON)
     Critical phases: [25, 28, 29, 35, 37, 39, 41]
     Skip phases: [_____________]
  
  ☑ Continuous monitoring
     Throttle: [1 check/file/min ▼]
     Batch window: [5 sek ▼]
     ☑ File system events
     ☑ Edit detection
     ☐ Sync events (rare, può cause noise)
  
  ☑ On-demand always available
     Default depth: [Standard ▼]
  
  Performance:
   ☐ Reduce continuous monitoring during builds (recommended dla low RAM)
   ☐ Pause Guard when on battery (laptop)
```

---

## 6.4. Severity levels (P6.3=c — 5 levels)

### 6.4.1. Pełna definicja levels

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Severity Levels                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INFO                                                        │
│  └─ Notification: subtle (in-app status bar)                 │
│     Examples:                                                 │
│      • Naming variant detected (Customer vs Client)          │
│      • Optional field documented but not used                │
│      • Translation length differs significantly              │
│     Action: just log, operator może ignore                   │
│                                                              │
│  WARNING                                                     │
│  └─ Notification: standard (in-app modal lub badge)          │
│     Examples:                                                 │
│      • Documented feature not in masterplan                  │
│      • Test gold standard outdated                           │
│      • Translation missing for 1 string                      │
│     Action: operator review w post-phase report              │
│                                                              │
│  ERROR                                                       │
│  └─ Notification: prominent (modal + email jeśli configured) │
│     Examples:                                                 │
│      • API contract mismatch (frontend ↔ backend)            │
│      • Database schema vs ORM models diverge                 │
│      • Multiple translations missing                         │
│     Action: operator should fix przed continue               │
│                                                              │
│  CRITICAL                                                    │
│  └─ Notification: urgent (in-app + mobile + email + Slack)   │
│     Examples:                                                 │
│      • Security claim w docs not implemented in code         │
│      • Compliance requirement (GDPR) missing in deployment   │
│      • Breaking change w API bez version bump                │
│     Action: operator must address pre-deploy                 │
│                                                              │
│  BLOCKER                                                     │
│  └─ Notification: hard gate (pipeline pauses)                │
│     Examples:                                                 │
│      • Production deploy z config different than tested      │
│      • Payment integration documented ale not implemented    │
│      • Customer data handling inconsistent (GDPR risk)       │
│     Action: PIPELINE BLOCKED until resolved                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.4.2. Severity assignment per check type

Per built-in check, severity jest pre-assigned (operator może override):

```
Check type                              Default severity
──────────────────────────────────────  ────────────────
Naming inconsistency                    INFO
Optional field unused                   INFO
Translation length variance             INFO

Documented feature missing in masterplan WARNING
Test missing for documented requirement WARNING
Translation missing (1-2 strings)       WARNING

API contract mismatch                   ERROR
DB schema ↔ ORM divergence              ERROR
Translation missing (>5 strings)        ERROR
Cross-time decision deviation           ERROR

Security claim not implemented          CRITICAL
GDPR requirement missing                CRITICAL
Breaking API change without version     CRITICAL
Payment claim not implemented           CRITICAL

Production deploy ↔ tested config diff  BLOCKER
Customer data handling inconsistency    BLOCKER
Compliance gap pre-prod-deploy          BLOCKER
```

### 6.4.3. Per-project severity tuning

Operator może adjust severities per project:

```
Project: Customer Acme Pilot → Coherence Severities

  Default behavior: standard severities
  
  Project-specific overrides:
   • Translation missing — bump WARNING → ERROR
     (Customer Acme requires multilanguage from day 1)
   • Naming inconsistency — bump INFO → WARNING
     (operator reviewing naming patterns dla brand)
   • API contract mismatch — keep ERROR
   • Cross-time deviation — bump ERROR → CRITICAL
     (operator wants strict process)
  
  [Save project-level overrides]
```

---

## 6.5. Detection mechanisms (P6.4=c hybrid rules + LLM)

### 6.5.1. Two-tier detection architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Detection — Two-Tier Architecture                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TIER 1 — Rule-based (fast, deterministic)                   │
│  ──────────────────────────────────────────                  │
│  Used dla:                                                   │
│   • Schema validation (JSON schema, OpenAPI)                 │
│   • Format checking (date formats, currency codes)           │
│   • Existence checks (does file X exist)                     │
│   • Basic completeness (all fields present)                  │
│   • Simple cross-references (Council decision X mentioned    │
│     in masterplan)                                           │
│                                                              │
│  Cost: $0 (lokalne computation)                              │
│  Speed: ~1-100 ms per check                                  │
│  Accuracy: 100% (within rule definition)                     │
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  TIER 2 — LLM-based (slower, semantic)                       │
│  ──────────────────────────────────────────                  │
│  Used dla:                                                   │
│   • Semantic equivalence (PL ↔ EN ↔ DE meaning)              │
│   • Intent matching (Council intent ↔ implementation)        │
│   • Subtle inconsistencies (described vs done)               │
│   • Cross-document narrative coherence                       │
│   • Pattern recognition (this looks similar to old projects) │
│                                                              │
│  Cost: $0.05-0.50 per check (zależnie od depth)              │
│  Speed: ~2-15 sek per check                                  │
│  Accuracy: ~90-95% (z calibrated prompts)                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.5.2. Tier 1 — przykład rule

```python
# Rule: every Council decision must appear in masterplan
class CouncilDecisionInMasterplanRule:
    severity = "WARNING"
    cost_tier = "TIER_1"
    
    def check(self, council_book, masterplan):
        decisions = council_book.extract_decisions()
        masterplan_text = masterplan.full_text()
        
        findings = []
        for decision in decisions:
            if not self._mentions(masterplan_text, decision):
                findings.append({
                    "severity": self.severity,
                    "decision": decision.id,
                    "title": decision.title,
                    "message": f"Council decision '{decision.title}' "
                               f"not found in masterplan"
                })
        
        return findings
    
    def _mentions(self, text, decision):
        # Check if decision keywords appear in text
        keywords = decision.extract_keywords()
        return any(kw.lower() in text.lower() for kw in keywords)
```

### 6.5.3. Tier 2 — przykład LLM check

```python
# LLM check: semantic equivalence multi-language
class SemanticEquivalenceCheck:
    severity = "WARNING"
    cost_tier = "TIER_2"
    model = "claude-sonnet-4-6"  # configurable
    
    def check(self, translations):
        """Check if PL/EN/DE versions are semantically equivalent."""
        prompt = f"""
        You are checking semantic equivalence between language versions.
        
        Polish:   {translations.pl}
        English:  {translations.en}
        German:   {translations.de}
        
        Are these semantically equivalent? Consider:
        - Same meaning conveyed
        - Same level of formality
        - Same nuances (urgency, certainty, etc.)
        
        Reply JSON:
        {{
          "equivalent": true|false,
          "issues": ["list of specific differences if any"],
          "severity": "INFO" | "WARNING" | "ERROR",
          "fix_suggestion": "how to fix if not equivalent"
        }}
        """
        
        result = self.model.complete(prompt)
        return self._parse(result)
```

### 6.5.4. Per-check mechanism selection

Operator może wybrać per check type który mechanism użyć:

```
Settings → Coherence Guard → Detection Mechanisms

  Per-check configuration:
  
  Check                              Tier   Override
  ────────────────────────────────  ─────  ──────────
  Schema validation                  Tier 1 [Use Tier 1 ▼]
  Cross-document references          Tier 1 [Use Tier 1 ▼]
  Council decision tracking          Tier 1 [Use Tier 1 ▼]
  Translation completeness           Tier 1 [Use Tier 1 ▼]
  Semantic equivalence (i18n)        Tier 2 [Use Tier 2 ▼]
  Intent matching (Council ↔ code)   Tier 2 [Use Tier 2 ▼]
  Pattern drift (cross-project)      Tier 2 [Use Tier 2 ▼]
  
  Bulk:
   [Use Tier 1 wszędzie (free, less accurate)]
   [Use Tier 2 wszędzie (expensive, more accurate)]
   [Smart hybrid (default)]
```

---

## 6.6. Baseline 15 checks + custom checks (P6.5=a+d, P6.6=d)

### 6.6.1. Baseline 15 checks

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Baseline Checks (15)                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CROSS-DOCUMENT (4 checks)                                   │
│   1. Każda feature w Księdze ma module w masterplanie         │
│      Tier 1 · Default WARNING                                │
│                                                              │
│   2. Każdy moduł w masterplanie ma test cases w test plan    │
│      Tier 1 · Default WARNING                                │
│                                                              │
│   3. Każdy claim w Council Book ma evidence w build artifacts│
│      Tier 2 · Default ERROR                                  │
│                                                              │
│   4. Acceptance criteria w Księdze są verifiable w testach   │
│      Tier 2 · Default WARNING                                │
│                                                              │
│  CROSS-TIME (3 checks)                                       │
│   5. Decyzje Council nie są łamane w mid-build interventions │
│      Tier 1 · Default ERROR                                  │
│                                                              │
│   6. Hard gate approvals są honored w deploy phase           │
│      Tier 1 · Default CRITICAL                               │
│                                                              │
│   7. Operator overrides expire on schedule (no ghost)        │
│      Tier 1 · Default WARNING                                │
│                                                              │
│  CROSS-LANGUAGE (3 checks, jeśli i18n)                       │
│   8. Translation coverage (każdy string ma wszystkie locales)│
│      Tier 1 · Default WARNING                                │
│                                                              │
│   9. Semantic equivalence (PL/EN/DE mean the same)            │
│      Tier 2 · Default WARNING                                │
│                                                              │
│   10. Date/currency formats per locale correct                │
│       Tier 1 · Default WARNING                               │
│                                                              │
│  CROSS-MODULE (3 checks)                                     │
│   11. API contracts między frontend i backend match           │
│       Tier 1 · Default ERROR                                 │
│                                                              │
│   12. Database schema vs ORM models match                    │
│       Tier 1 · Default ERROR                                 │
│                                                              │
│   13. Deployment configs spójne między environments          │
│       Tier 1 · Default ERROR                                 │
│                                                              │
│  OPERATIONAL (2 checks)                                      │
│   14. Cost tracking matches actual spend                     │
│       Tier 1 · Default WARNING                               │
│                                                              │
│   15. Audit chain hash chain valid                           │
│       Tier 1 · Default CRITICAL                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.6.2. Per-check configuration

Operator może edytować każdy check:

```
┌──────────────────────────────────────────────────────────────┐
│  Edit Check #5: Decyzje Council vs mid-build interventions   │
│                                                              │
│  Status:        [● Enabled]  [○ Disabled]                    │
│  Severity:      [ERROR ▼]                                    │
│  Tier:          [Tier 1 ▼]                                   │
│                                                              │
│  When to run:                                                │
│   ☑ Phase boundaries (faza 33-35)                            │
│   ☑ Continuous (file changes)                                │
│   ☑ On-demand                                                │
│                                                              │
│  Scope:                                                      │
│   ☑ Apply to all projects                                    │
│   ☐ Skip dla certain project types                           │
│                                                              │
│  Findings handling:                                          │
│   ☑ Show in aggregated panel                                 │
│   ☑ Auto-suggest fix (if Tier 2 mechanism enabled)           │
│   ☐ Auto-fix simple cases                                    │
│   ☐ Block pipeline if found                                  │
│                                                              │
│  Custom rule details:                                        │
│   Rule logic: built-in (Council decision tracking)           │
│   [View source]  [Override with custom rule]                 │
│                                                              │
│  [Save]  [Reset to default]  [Disable check]                 │
└──────────────────────────────────────────────────────────────┘
```

### 6.6.3. Custom checks — 3 mechanisms

Operator może budować własne checks na 3 sposoby:

#### Mechanism 1 — Predefined templates

```
┌──────────────────────────────────────────────────────────────┐
│  New Custom Check — From Template                            │
│                                                              │
│  Choose template:                                            │
│   [○ All database tables must have created_at column]        │
│   [○ All API endpoints must have rate limiting documented]   │
│   [○ All forms must have CSRF tokens]                        │
│   [○ All migrations must have rollback]                      │
│   [● All public APIs must have OpenAPI documentation]        │
│   [○ All sensitive operations must be audit-logged]          │
│   [○ All third-party libraries must be in approved list]     │
│   [○ All env variables must be documented]                   │
│   [○ Custom: define from scratch]                            │
│                                                              │
│  Configuration:                                              │
│   Severity:        [ERROR ▼]                                 │
│   Tier:            [Tier 1 ▼]                                │
│   Apply to:        [Public API endpoints]                    │
│                                                              │
│  Test on current project:                                    │
│   [Run dry-test]                                             │
│                                                              │
│  [Cancel]  [Save check]                                      │
└──────────────────────────────────────────────────────────────┘
```

#### Mechanism 2 — Rule-based DSL

```
┌──────────────────────────────────────────────────────────────┐
│  New Custom Check — Rule DSL                                 │
│                                                              │
│  Check name: [ Customer email always before phone        ]   │
│  Description:                                                │
│  [ Operator's UX decyzja: w wszystkich formach klientów,    │
│    email field musi być przed phone field                  ] │
│                                                              │
│  Rule (DSL):                                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ FOR every form IN frontend.forms                       │ │
│  │   IF form.contains_field("email")                      │ │
│  │      AND form.contains_field("phone")                  │ │
│  │      AND form.field_position("email") >                │ │
│  │          form.field_position("phone")                  │ │
│  │   THEN flag(severity="WARNING",                        │ │
│  │            message="Email should appear before phone") │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Apply to scope:                                             │
│   ☑ Frontend code                                            │
│   ☐ Backend code                                             │
│   ☐ Tests                                                    │
│                                                              │
│  Severity: [WARNING ▼]                                       │
│  Tier:     [Tier 1 ▼]                                        │
│                                                              │
│  Test:                                                       │
│   [Validate DSL syntax]  [Run on current project]            │
│                                                              │
│  [Cancel]  [Save check]                                      │
└──────────────────────────────────────────────────────────────┘
```

#### Mechanism 3 — LLM prompts

```
┌──────────────────────────────────────────────────────────────┐
│  New Custom Check — LLM Prompt                               │
│                                                              │
│  Check name: [ Verify business logic matches Księga      ]   │
│  Description:                                                │
│  [ Use Claude to verify że business rules implemented w     │
│    code match opisy w Księdze §5 (Business Logic)         ]  │
│                                                              │
│  LLM prompt:                                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ You are reviewing business logic implementation.       │ │
│  │                                                        │ │
│  │ Księga §5 (Business Rules):                            │ │
│  │ {ksiega_section_5}                                     │ │
│  │                                                        │ │
│  │ Implementation files:                                  │ │
│  │ {implementation_files}                                 │ │
│  │                                                        │ │
│  │ Check:                                                 │ │
│  │ 1. Each business rule documented in §5 has code impl   │ │
│  │ 2. Code doesn't implement undocumented rules           │ │
│  │ 3. Edge cases mentioned in §5 are handled in code      │ │
│  │                                                        │ │
│  │ Reply JSON:                                            │ │
│  │ {                                                      │ │
│  │   "issues": [                                          │ │
│  │     {                                                  │ │
│  │       "rule": "rule name",                             │ │
│  │       "type": "missing|extra|edge_case_unhandled",     │ │
│  │       "severity": "WARNING|ERROR|CRITICAL",            │ │
│  │       "fix_suggestion": "..."                          │ │
│  │     }                                                  │ │
│  │   ]                                                    │ │
│  │ }                                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Model:        [claude-sonnet-4-6 ▼]                         │
│  Max cost/run: [$0.50 ▼]                                     │
│  Run frequency: [On phase boundary 35 ▼]                     │
│                                                              │
│  Test on current project:                                    │
│   [Run dry-test (estimated cost: $0.32)]                     │
│                                                              │
│  [Cancel]  [Save check]                                      │
└──────────────────────────────────────────────────────────────┘
```

### 6.6.4. Custom checks management

```
┌──────────────────────────────────────────────────────────────┐
│  Custom Coherence Checks                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Active custom checks: 4                                     │
│                                                              │
│  ☑ All public APIs documented (template)                     │
│      Severity: ERROR · Tier: 1 · Cost: $0                    │
│      Last run: 2h ago · Findings: 0                          │
│      [Edit]  [Disable]  [Run now]                            │
│                                                              │
│  ☑ Customer email before phone (DSL)                         │
│      Severity: WARNING · Tier: 1 · Cost: $0                  │
│      Last run: 25 min ago · Findings: 2                      │
│      [Edit]  [Disable]  [View findings]                      │
│                                                              │
│  ☑ Business logic matches Księga (LLM)                       │
│      Severity: ERROR · Tier: 2 · Cost: ~$0.30/run            │
│      Last run: 1h ago · Findings: 1 (high confidence)        │
│      [Edit]  [Disable]  [View findings]                      │
│                                                              │
│  ☑ HIPAA compliance check (LLM)                              │
│      Severity: BLOCKER · Tier: 2 · Cost: ~$0.80/run          │
│      Last run: 4h ago · Findings: 0                          │
│      [Edit]  [Disable]  [Run now]                            │
│                                                              │
│  Total custom check cost (this month): $4.20                 │
│                                                              │
│  [+ Add custom check]  [Import from library]                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 6.7. Findings handling (P6.7=d adaptive per autonomy)

### 6.7.1. Adaptive behavior matrix

Per autonomy preset, Coherence Guard handles findings differently:

```
┌──────────────────────────────────────────────────────────────┐
│  Findings Behavior per Autonomy Preset                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Preset: Conservative                                        │
│   Behavior: NOTIFY ONLY (no auto-fix, no auto-suggestions)   │
│   Operator must:                                             │
│    • Review every finding manually                           │
│    • Decide fix approach                                     │
│    • Apply fix manually                                      │
│   Why: high-stakes projekt, operator wants control           │
│                                                              │
│  Preset: Balanced (default)                                  │
│   Behavior: NOTIFY + SUGGEST FIX                             │
│   System suggests konkretne fixes per finding                │
│   Operator approves każdy fix przed apply                    │
│   Why: balanced — operator visibility z time savings         │
│                                                              │
│  Preset: Aggressive                                          │
│   Behavior: AUTO-FIX SIMPLE + SUGGEST COMPLEX                │
│   Auto-fixed: typos, naming consistency, formatting          │
│   Suggested: semantic issues, architecture                   │
│   Notified: post-fact w batch summary                        │
│   Why: speed prioritized                                     │
│                                                              │
│  Preset: Production                                          │
│   Behavior: NOTIFY EVERYTHING (no auto-anything)             │
│   Operator review wszystkie findings przed deploy            │
│   Special: BLOCKER findings → hard gate dla deploy           │
│   Why: production safety > speed                             │
│                                                              │
│  Preset: Research                                            │
│   Behavior: AUTO-FIX EVERYTHING (max speed)                  │
│   Operator review tylko BLOCKER findings                     │
│   Why: research velocity > polish                            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.7.2. Auto-fix types (jeśli włączone)

```
Auto-fix capabilities (per Aggressive/Research presets):
  
  TIER 1 auto-fixes (safe, deterministic):
   ✓ Typo corrections (spelling)
   ✓ Naming consistency (Customer vs Client → Customer)
   ✓ Formatting (date format, currency code)
   ✓ Translation length normalization
   ✓ Optional field additions (z reasonable defaults)
   ✓ Schema validation fixes
  
  TIER 2 auto-fixes (semantic, LLM-driven):
   ⚠ Code refactor for naming consistency
   ⚠ Translation regeneration (jeśli semantic mismatch)
   ⚠ API contract synchronization
   ⚠ Test gold standard regeneration
   ⚠ Documentation update from code (lub vice versa)
  
  NEVER auto-fixed (always operator):
   ✗ Security claims (operator MUST review)
   ✗ GDPR/compliance changes
   ✗ Database migrations
   ✗ Production deployment configs
   ✗ Hard gate approvals
   ✗ Master password changes
   ✗ Provider key rotations
```

### 6.7.3. Per-finding workflow

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Finding #237                                      │
│                                                              │
│  Type:     Cross-language semantic mismatch                  │
│  Severity: WARNING                                           │
│  Detected: 2 min ago                                         │
│  Source:   i18n strings table                                │
│                                                              │
│  Finding:                                                    │
│   String key:      "checkout.confirm_button"                 │
│   PL: "Potwierdź zakup"      (Confirm purchase)              │
│   EN: "Place order"          (Place order)                   │
│   DE: "Bestellen"            (Order)                         │
│                                                              │
│  Issue: PL i EN have different meanings                      │
│   PL implies "confirm"                                       │
│   EN implies "place" (different action)                      │
│   DE matches EN                                              │
│                                                              │
│  Suggested fix (LLM):                                        │
│   Option A: Standardize do "Confirm purchase"                │
│             PL: "Potwierdź zakup" (no change)                │
│             EN: "Confirm purchase" (changed)                 │
│             DE: "Kauf bestätigen" (changed)                  │
│                                                              │
│   Option B: Standardize do "Place order"                     │
│             PL: "Złóż zamówienie" (changed)                  │
│             EN: "Place order" (no change)                    │
│             DE: "Bestellen" (no change)                      │
│                                                              │
│  Auto-fix recommendation: Option B (matches majority)        │
│                                                              │
│  Akcje:                                                      │
│   [Apply Option A]                                           │
│   [Apply Option B]                                           │
│   [Custom fix (operator manual)]                             │
│   [Mark as intentional (suppress)]                           │
│   [Snooze 7 dni]                                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.7.4. Blocking behavior (P6.8=d per severity + autonomy)

```
┌──────────────────────────────────────────────────────────────┐
│  Pipeline Blocking Matrix                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Severity   Conservative  Balanced   Aggressive  Production  │
│  ─────────  ────────────  ─────────  ─────────── ─────────── │
│  INFO       no block      no block   no block    no block    │
│  WARNING    no block      no block   no block    no block    │
│  ERROR      block         no block   no block    block       │
│  CRITICAL   block         block      no block    block       │
│  BLOCKER    block         block      block       block       │
│                                                              │
│  Notification per severity (always sent):                    │
│  INFO       in-app        in-app     batch       in-app+ema  │
│  WARNING    in-app+email  in-app     batch       in-app+ema  │
│  ERROR      modal+email   modal      batch       modal+ema   │
│  CRITICAL   urgent        urgent     in-app      urgent      │
│  BLOCKER    hard gate     hard gate  hard gate   hard gate   │
│                                                              │
│  Override:                                                   │
│   Operator can override blocking dla projects via faza 17    │
│   Hard gate "force-continue with blocker" wymaga approval    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 6.8. Performance — separate worker, tiered cost, smart caching

### 6.8.1. Separate worker architecture (P6.10=a)

```
┌──────────────────────────────────────────────────────────────┐
│  AEIS Process Architecture                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Main pipeline (UI + Council + Build)                  │  │
│  │   • Operator-facing                                    │  │
│  │   • Heavy processing (LLM calls)                       │  │
│  │   • Cannot be blocked by Guards                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Coherence Guard worker (separate process/thread)      │  │
│  │   • Background priority                                │  │
│  │   • Throttled (1 check per file per minute)            │  │
│  │   • Can be paused on low memory                        │  │
│  │   • Doesn't impact UI responsiveness                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Other Guards (Cost, Security, Quality, Provenance)    │  │
│  │   • Each w own worker                                  │  │
│  │   • Coordinated via shared event bus                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Communication:                                              │
│   • Main → Workers: phase events (faza completed, etc.)      │
│   • Workers → Main: findings (via aggregated queue)           │
│   • Workers ↔ Workers: minimal (mostly independent)          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.8.2. Tiered cost strategy (P6.9=b)

```
Cost strategy:
  
  Quick checks (Tier 1):
   Model: lokalne (free)
   Frequency: continuous, w trakcie pracy
   Cost: $0
   Examples: schema validation, format checking
  
  Medium checks (Tier 2 — cheap LLM):
   Model: bielik-11b lokalny / claude-haiku
   Frequency: phase boundaries
   Cost: $0-$0.10 per check
   Examples: simple semantic checks, naming consistency
  
  Critical checks (Tier 2 — premium LLM):
   Model: claude-sonnet / claude-opus
   Frequency: phase boundaries dla critical phases
   Cost: $0.20-$1.50 per check
   Examples: business logic verification, security claims
  
  Batch optimization:
   Multiple checks combined w single LLM call (cheaper per check)
   Continuous checks batched in 5-min windows
```

### 6.8.3. Cost budget per Guard

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Guard Cost Budget                                 │
│                                                              │
│  Per project budget allocation:                              │
│   Default: 5% of project budget                              │
│   Override: [10%] dla quality-critical projects              │
│                                                              │
│  Per workspace monthly cap:                                   │
│   Default: $30/month                                         │
│   Current usage: $12.40 (this month)                         │
│   Trend: -8% vs last month                                   │
│                                                              │
│  When cap approached:                                        │
│   At 80%: notify, suggest reducing Tier 2 checks             │
│   At 95%: pause Tier 2 checks (Tier 1 continues, free)       │
│   At 100%: pause all LLM-based checks until next month       │
│                                                              │
│  [Adjust budget]  [View detailed cost breakdown]             │
└──────────────────────────────────────────────────────────────┘
```

### 6.8.4. Smart caching (P6.11=d)

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Cache Architecture                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Cache layers:                                               │
│                                                              │
│  L1 — Per-file checksum cache                                │
│   When file unchanged → skip ALL checks                      │
│   Storage: ~/.sylion/<op>/coherence/cache/checksums.db       │
│   Retention: 30 days                                          │
│                                                              │
│  L2 — Per-check result cache                                 │
│   Cache key: file_hash + check_id + dependencies_hashes      │
│   When sources unchanged → return cached result               │
│   Storage: ~/.sylion/<op>/coherence/cache/results.db         │
│   Retention: 7 days                                           │
│                                                              │
│  L3 — Cross-document relationship graph                       │
│   Tracks: which files affect which checks                    │
│   Used for: incremental invalidation                         │
│   When file X changes, invalidate only checks że depend on X │
│                                                              │
│  Diff-based incremental:                                     │
│   For text files: diff between versions                      │
│   Re-check tylko diff regions                                │
│   Saves ~80% LLM costs dla incremental updates               │
│                                                              │
│  Cache invalidation triggers:                                │
│   ✓ File modified (mtime + checksum change)                  │
│   ✓ Dependency changed (per relationship graph)              │
│   ✓ Check definition modified (operator edit)                │
│   ✓ Manual cache invalidation                                │
│   ✓ AEIS version update (cache schema may change)            │
│                                                              │
│  Manual controls:                                            │
│   [Clear all coherence cache]                                │
│   [Show cache stats]                                         │
│      Hit rate: 78% (good)                                    │
│      Storage: 124 MB                                         │
│      Saved cost: $89 (estimated bez cache)                   │
└──────────────────────────────────────────────────────────────┘
```

---

## 6.9. Aggregated Guards panel + per-Guard autonomy override

### 6.9.1. Aggregated Guards panel (P6.12=d)

Wszystkie 5 Guards (Coherence, Cost, Security, Quality, Provenance)
publishują findings do shared panel:

```
┌──────────────────────────────────────────────────────────────┐
│  Guards — Aggregated Findings                                │
│  Filter: [All ▼]  Sort: [Severity ↓]                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Project: Sylion Tailor v3                                   │
│  Total findings: 23  ·  Active: 18  ·  Resolved: 5           │
│                                                              │
│  CRITICAL (2)                                                │
│  ⚠ Coherence: Security claim "OAuth2" not implemented        │
│      Source: Council Book §4 ↔ auth.py                       │
│      [Details]  [Suggested fix]  [Override]                  │
│                                                              │
│  ⚠ Security: Hardcoded credential detected w config          │
│      Source: backend/config.yaml line 23                     │
│      [Details]  [Suggested fix]  [Override]                  │
│                                                              │
│  ERROR (5)                                                   │
│  ✗ Coherence: API contract mismatch (frontend ↔ backend)     │
│  ✗ Quality: 2 unit tests failing (auth module)              │
│  ✗ Provenance: 3 build artifacts bez signed manifest        │
│  ✗ Coherence: Deploy config różne między staging i prod      │
│  ✗ Cost: Single call exceeded $5 cap (manual approval pend.) │
│                                                              │
│  WARNING (8)                                                 │
│  ⚠ Coherence: 3 translation strings missing dla DE locale   │
│  ⚠ Quality: Code coverage 78% (target 80%)                  │
│  ⚠ Coherence: Naming variant w 4 files (Customer vs Client) │
│  ... (5 more)                                                │
│                                                              │
│  INFO (3)                                                    │
│  ℹ Coherence: Translation length variance > 30% (PL vs DE)  │
│  ℹ Cost: Build phase cost 15% above estimate                │
│  ℹ Provenance: 2 artifacts pending verification (low prio)  │
│                                                              │
│  ─────────────────────────────────────────────                │
│                                                              │
│  Conflicting findings:                                       │
│   ⚠ Coherence says "API contract mismatch"                   │
│      Quality says "API tests pass"                           │
│      Resolution: tests use wrong endpoint, both right        │
│      [Operator review needed]                                │
│                                                              │
│  Bulk actions:                                               │
│   [Apply all auto-fixable]  [Snooze all info]                │
│   [Export findings report]                                   │
└──────────────────────────────────────────────────────────────┘
```

### 6.9.2. Per-Guard autonomy override (P6.14=c)

Każdy Guard inherits global autonomy (z fazy 5), ale operator może override
per-Guard:

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Guard — Autonomy Override                         │
│                                                              │
│  Inherited from Phase 5: Production preset                   │
│   Default behavior: NOTIFY EVERYTHING                        │
│                                                              │
│  Coherence-specific override:                                │
│                                                              │
│   ☑ Override: use Balanced behavior dla Coherence            │
│      Rationale: Coherence findings są łatwiejsze do auto-fix │
│      niż security or production decisions                    │
│                                                              │
│   Effective:                                                 │
│    INFO/WARNING:  notify only                                │
│    ERROR:         notify + suggest fix                       │
│    CRITICAL:      notify + suggest fix                       │
│    BLOCKER:       hard gate (cannot bypass)                  │
│                                                              │
│   Auto-fix:                                                  │
│    ☑ Tier 1 fixes auto (typos, naming)                       │
│    ☐ Tier 2 fixes auto (no — operator approves)              │
│                                                              │
│  Per-check override:                                         │
│   ☑ Allow per-check autonomy customization                   │
│      e.g., "Translation completeness can auto-fix"           │
│      e.g., "Security claim verification always manual"       │
│                                                              │
│  [Save override]  [Reset to Phase 5 inherit]                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 6.10. Edge Cases (P6.13=b — 22 cases)

22 cases w 5 kategoriach.

### Kategoria A — False positives (5 cases)

#### EC-A1: Naming variant intentional

**Trigger**: Coherence Guard flags "Customer" vs "Client" jako
inconsistency. Operator intentionally uses Customer (b2b) and Client
(b2c).

```
ℹ Coherence Finding — Naming variant detected

  Severity: INFO
  Files: 12 files use "Customer", 8 files use "Client"
  
  Operator response:
  [Mark as intentional (suppress future)]
   → Add note: "Customer = B2B, Client = B2C"
   → Future variants suppressed
   
  [Apply auto-fix (standardize do one)]
   → Operator picks which to use
   
  [Investigate per file]
   → Show context dla each variant
```

#### EC-A2: LLM check hallucination

**Trigger**: LLM check (Tier 2) reports false finding (hallucinated).
Operator sees finding ale weryfikuje że nie ma issue.

```
⚠ False positive detected

  Finding: "Business rule X w Księga §5 nie jest w code"
  
  Operator verification:
  Code DOES implement rule X (just w different file).
  LLM didn't find it w expected location.
  
  Akcje:
   [Mark false positive — improve LLM context]
       Operator's note added to check definition
       Future runs include hint about rule X location
   [Refine LLM prompt]
       Operator edytuje check prompt do być more specific
   [Suppress this finding (one-time)]
```

#### EC-A3: Intentional deviation z Council decision

**Trigger**: Council decided "use Stripe". Operator mid-build switched do
Adyen z good reason. Coherence Guard flags as deviation.

```
⚠ Coherence Finding — Cross-time deviation

  Council decision (Faza 23): "Use Stripe dla payments"
  Implementation: Adyen integration
  
  Operator response:
   [Mark intentional — provide reason]
       Add note: "Adyen support PL local methods better than Stripe"
       Update Księga §6 z revised payment provider
       Coherence regenerates check based on updated Księga
   
   [Revert do Stripe]
       Implementation rollback, restore Council decision
   
   [Update Council decision retroactively]
       Mark Council decision z "amended on date X by operator"
```

#### EC-A4: Translation length variance OK dla some languages

**Trigger**: German typically longer than English. Guard flags variance >30%
ale to normalne dla DE.

```
ℹ Translation length variance — DE expected

  String: "checkout.confirm_button"
  PL: 18 chars  EN: 14 chars  DE: 28 chars (+100% vs EN)
  
  Default check: WARNING jeśli variance > 30%
  
  German typically longer — adjust threshold:
   [Increase DE threshold do 50% (DE-aware)]
   [Suppress check dla string]
   [Per-language thresholds: PL/EN +30%, DE +50%]
```

#### EC-A5: Test gold standard outdated po major refactor

**Trigger**: Operator refactored UI po feedback. Test gold standards
(screenshots) outdated. Guard flags coherence issues (test ↔ implementation).

```
⚠ Test gold standards outdated

  Outdated: 14 visual gold standards (Playwright screenshots)
  Reason: UI refactor 2 dni temu (operator approved)
  
  Akcje:
   [Regenerate all gold standards]
       Run tests, save current screenshots as new baseline
       Operator manually verifies każdy
   [Skip visual regression dla affected tests]
       Tests pass on functional, ignore visual
   [Per-test approval]
       Operator reviews each new screenshot
```

### Kategoria B — Performance issues (5 cases)

#### EC-B1: Continuous monitoring w slow

**Trigger**: Operator's project ma 2000+ files. Continuous monitoring spowalnia
CPU.

```
⚠ Coherence Guard performance impact

  Project: Sylion Tailor v3
  Files monitored: 2143
  CPU usage (Guard worker): 18% sustained
  
  Recommendations:
   [Reduce continuous to phase boundaries only]
       Less responsive but lower CPU
   [Throttle aggressively (1 check / 5 min per file)]
       Reduce frequency
   [Exclude generated files (build artifacts)]
       Skip build/, dist/, node_modules/
   [Use Tier 1 only (no LLM)]
       Faster but less semantic depth
```

#### EC-B2: LLM cost overrun

**Trigger**: Custom LLM check runs 50x w jednej godzinie (operator was
debugging). Cost spike.

```
⚠ Coherence Guard cost spike

  Custom LLM check: "Business logic verification"
  Runs last hour: 47 (normalnie 5-10)
  Cost last hour: $14.10
  
  Likely cause: operator was testing check
  
  Akcje:
   [Pause this check temporarily]
   [Add cooldown (max 1 run per 5 min)]
   [Reduce model do cheaper (sonnet → haiku)]
   [Continue (operator was testing intentionally)]
```

#### EC-B3: Cache cold start delay

**Trigger**: Operator restarts AEIS. Cache cold. First Guard run takes
much longer.

```
ℹ Coherence Guard warming up

  Status: cache cold (last AEIS restart 2 min ago)
  
  Initial scan progress:
   ⠋ Hashing 2143 files... (1247/2143)
   Estimated time: 4 min
  
  Subsequent runs will be much faster (incremental).
  
  Skip initial scan? (uses last cache, may have stale results)
   [Skip — use cached results]  [Wait for full scan]
```

#### EC-B4: Cache corruption

**Trigger**: Cache database corrupted (filesystem issue). Guard returning
stale results.

```
⚠ Coherence cache appears corrupted

  Symptoms:
   • Findings inconsistent between runs
   • Cache hit rate suspicious (100% — too high)
   • Some files report unchanged when actually modified
  
  Akcje:
   [Rebuild cache from scratch]
       Cost: ~5 min processing time
       Recommended
   [Verify cache integrity]
       Check database consistency
   [Disable cache temporarily]
       Run all checks fresh każdym razem (slow)
```

#### EC-B5: Worker process crashed

**Trigger**: Coherence Guard worker process crashed (out of memory).
Findings stop being generated.

```
✗ Coherence Guard worker died

  Last successful check: 14 min ago
  Worker status: crashed (segfault)
  Cause: out of memory (project z 5000+ files)
  
  Akcje:
   [Restart worker (auto-recovery)]
       Worker restarts z reduced memory limit
   [Reduce worker memory (smaller working set)]
       Trade: more frequent re-checks
   [Increase system swap]
       Allow worker more virtual memory
   [Pause Coherence Guard]
       Run on-demand only do operator decyduje
```

### Kategoria C — Custom checks issues (4 cases)

#### EC-C1: DSL syntax error w custom check

**Trigger**: Operator wrote custom check w DSL z syntax error. Check fails
to parse.

```
✗ Custom check has DSL syntax error

  Check: "Customer email before phone"
  Error: Unexpected token "AND" at line 4
  
  Operator's DSL:
   FOR every form IN frontend.forms
     IF form.contains_field("email")
        AND form.contains_field("phone")     ← "AND" needs proper structure
        AND form.field_position("email") >
            form.field_position("phone")
     THEN flag(...)
  
  Fix:
   IF form.contains_field("email")
   AND form.contains_field("phone")
   AND form.field_position("email") > form.field_position("phone")
  
  [Apply fix]  [Edit manually]  [Disable check]
```

#### EC-C2: LLM custom check returns invalid JSON

**Trigger**: LLM-based check zwraca invalid JSON. System nie może
parse findings.

```
⚠ Custom LLM check parsing failed

  Check: "Business logic matches Księga"
  LLM response: not valid JSON (mid-sentence cut off)
  
  Possible causes:
   • LLM hit token limit
   • Prompt unclear about JSON format
   • Model occasionally produces text instead of JSON
  
  Akcje:
   [Increase max_tokens dla check]
       Was 1000, increase do 2000
   [Switch to model z better JSON compliance]
       Currently sonnet, switch to opus
   [Add JSON enforcement to prompt]
       "You MUST reply z valid JSON only"
   [Retry check]
```

#### EC-C3: Custom check too broad (matches everything)

**Trigger**: Operator wrote LLM check z broad criteria. Returns 50+
findings z każdego runu. Noise overload.

```
⚠ Custom check has high false positive rate

  Check: "All forms must be accessibility-compliant"
  Findings per run: 47 average
  Operator dismissed: 92% (43 z 47)
  Genuine issues: 4 (8%)
  
  Recommendations:
   [Refine check scope]
       Limit do customer-facing forms only
   [Adjust severity (currently ERROR, lower do INFO)]
   [Use specific rules instead of LLM]
       Tier 1 deterministic checks z lower false positive
   [Disable check]
```

#### EC-C4: Custom check imported from community

**Trigger**: Operator imported community check, ale nie pasuje do
operator's project. False positives.

```
ℹ Imported check needs adjustment

  Check: "HIPAA compliance check (community v1.2)"
  Imported: 1 dzień temu
  Findings: 23 dla SYLION Tailor (e-commerce, NOT healthcare)
  
  Issue: check assumes healthcare project
  
  Akcje:
   [Restrict check do healthcare projects only]
       Tag: project_goal == "healthcare"
   [Disable check]
       Not applicable dla operator's projects
   [Customize check definition]
       Edit do match operator's needs
   [Report community check issue]
       Suggest improvements do contributor
```

### Kategoria D — Findings handling issues (4 cases)

#### EC-D1: Auto-fix breaks code

**Trigger**: Aggressive preset auto-fixed naming inconsistency. Fix broke
code (dependency variable name reused).

```
✗ Auto-fix introduced regression

  Auto-fix: rename "Client" to "Customer" w 8 files
  Build status: FAILED po fix
  
  Reason: variable "Client" was used jako import name (HTTP client lib)
  Auto-fix renamed import too, breaking import statement
  
  Akcje:
   [Revert auto-fix]
       Restore previous version, manual fix instead
   [Fix the fix]
       Operator manually corrects import statement
   [Disable auto-fix dla naming consistency]
       Future findings → notify only
   [Improve auto-fix logic]
       Don't rename import statements
```

#### EC-D2: Findings panel overwhelmed (too many)

**Trigger**: 5 Guards aktywne. Multiple findings każdy. Panel pokazuje
200+ items. Operator overwhelmed.

```
⚠ Findings overload

  Total active findings: 247
  Across all 5 Guards
  
  Recommendations:
   [Auto-suppress INFO severity (only WARNING+)]
       Reduces to ~50 findings
   [Group by type]
       247 → 12 categories
   [Prioritize by D-level affected]
       Show D5 findings first
   [Run bulk auto-fix safe ones]
       Address 80% automatically, manual review rest
   [Operator workflow: address top 10]
       Set goal, ignore rest until top 10 done
```

#### EC-D3: Conflicting findings między Guards

**Trigger**: Coherence Guard says "API contract mismatch". Quality Guard
says "API tests pass". Conflict.

```
⚠ Inter-Guard conflict

  Coherence: "Frontend POST /api/orders { items } ↔ 
              Backend POST /api/orders { products } MISMATCH"
  
  Quality: "All API tests pass (47/47)"
  
  Investigation:
   Tests use mock server z OLD endpoint definition
   Mock server: { items }  ← matches frontend
   Real backend: { products }  ← matches Coherence finding
  
  Resolution:
   • Coherence finding is correct
   • Tests are passing because mock is wrong
   • Real production deploy would FAIL
  
  Akcje:
   [Update mock server do match real backend]
       Tests will then fail correctly, exposing real issue
   [Update real backend do match frontend]
       Frontend ↔ backend ↔ tests all align
   [Operator clarifies intended state]
```

#### EC-D4: Snoozed findings forgotten

**Trigger**: Operator snoozed many findings. Later forgets. Findings
re-surface w periodic re-check, operator confused.

```
ℹ Snoozed findings reminder

  Snoozed findings: 18 (across last 30 days)
  Snooze expiring soon (next 7 days):
   • 5 findings (re-surface auto)
  
  Recommend periodic review:
   [Review all snoozed now]
   [Extend all snooze 30 days]
   [Mark all as resolved (suppress permanent)]
   [Convert snooze do permanent suppression]
   
  Settings:
   ☑ Show snooze expiration warnings
   ☐ Auto-resolve snoozed findings po 90 dni (no action)
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Custom checks lost po AEIS update

**Trigger**: AEIS update changed DSL syntax. Operator's custom checks no
longer parse.

```
⚠ Custom checks broken after update

  AEIS: v3.0 → v3.1
  Affected custom checks: 4 z 8
  
  Backward compatibility:
   • DSL keyword "FOR every" → "FOR EACH" w v3.1
   • LLM check format unchanged
  
  Akcje:
   [Auto-migrate DSL syntax]
       System updates 4 affected checks
   [Manual review per check]
       Operator approves each migration
   [Rollback do v3.0]
       Wait dla compatible AEIS update
```

#### EC-E2: Workspace import — Guards configuration

**Trigger**: Operator imports workspace. Coherence Guard config (custom
checks, severities) needs migration.

```
ℹ Workspace import — Guards config

  Imported:
   ✓ Coherence Guard settings (15 baseline checks)
   ✓ Custom checks: 4 imported
   ⚠ Custom check "HIPAA compliance" requires LLM model
       Imported model preference: claude-opus
       Current available: claude-opus ✓ OK
   ✓ Cache rebuilt (cold start, 5 min)
  
  Conflicts: none
  Status: Ready
```

#### EC-E3: Backup restore — partial Coherence Guard state

**Trigger**: Operator restores backup. Coherence cache stale. Findings
re-generate.

```
ℹ Coherence Guard recovery

  After restore:
   • Cache: rebuilding (5 min)
   • Findings DB: restored from backup (47 findings)
   • Snoozed findings: respect previous snoozes
   • New findings since backup: will be detected on next run
  
  Manual review po restore:
   [Run full coherence check]
       Detect any new findings since backup point
```

#### EC-E4: Cross-project pattern data lost

**Trigger**: Operator enabled cross-project checks (P6.1=d option). Lost
cross-project data po workspace migration.

```
⚠ Cross-project coherence data missing

  Reason: Cross-project pattern database was machine-local
  Not exported w workspace backup (privacy default)
  
  Akcje:
   [Re-build cross-project patterns]
       AEIS scans all projects w current workspace
       ~10-20 min processing
       LLM cost: ~$5-15 (one-time)
   [Disable cross-project checks]
       Standard scope only
   [Import patterns from cloud sync]
       Jeśli operator enabled cloud pattern sync
```

---

## 6.11. Inheritance + Acceptance Criteria + DoD

### 6.11.1. Inheritance pattern

```
Phase 5 (autonomy preset) defines: how aggressive Guards są
   ↓
Phase 6 (Coherence Guard) inherits, but może override per-Guard:
   • Conservative w ogólnym → Coherence może być Balanced
   • Aggressive w ogólnym → Coherence pozostaje strict dla security checks
   ↓
Phase 17 (per-project) override:
   • Niektóre checks aggressive dla critical projects
   • Niektóre disabled dla research/prototypes
   ↓
Real-time finding handling:
   • Suppress per finding
   • Snooze per project
```

### 6.11.2. DoD

#### Wspólne (zawsze wymagane)

```
✓ Coherence Guard scope configured (standard lub custom)
✓ Triggers configured (defaults OK)
✓ Severity thresholds reviewed
✓ Baseline 15 checks reviewed (enabled or explicitly disabled)
✓ Audit chain entry: phase_6.complete
```

#### Recommended

```
✓ Custom checks defined (jeśli operator ma specific needs)
✓ Per-Guard autonomy override considered
✓ Cost budget allocated dla Guard
✓ Performance settings tuned (jeśli needed)
```

### 6.11.3. Soft warnings vs hard blocks

**Hard blocks**:
- All baseline checks disabled (Guard becomes useless)
- LLM-based checks enabled bez budget cap (cost runaway)
- Worker disabled wszystko (Guard nie działa)

**Soft warnings**:
- Cross-project checks enabled przed 5+ projects (no patterns yet)
- Aggressive auto-fix dla critical checks
- All checks Tier 2 (very expensive)
- No custom checks (operator może mieć specific needs)

### 6.11.4. Acceptance test

```bash
$ aeis-cli phase6-acceptance-test

Running Phase 6 acceptance test...

[Common requirements]
[1/5] Scope configured                              ✓ PASS
[2/5] Triggers configured                           ✓ PASS
[3/5] Severity thresholds reviewed                  ✓ PASS
[4/5] Baseline 15 checks reviewed                   ✓ PASS (15 enabled)
[5/5] Audit chain entry phase_6.complete            ✓ PASS

[Optional features]
[6/8] Custom checks defined                         ℹ INFO (4 custom)
[7/8] Per-Guard autonomy override                   ✓ PASS (override applied)
[8/8] Cost budget allocated                         ✓ PASS ($30/mo)

[Performance]
[9/11] Worker running                               ✓ PASS
[10/11] Cache initialized                           ✓ PASS (78% hit rate)
[11/11] LLM cost within budget                      ✓ PASS ($12/$30 used)

DoD: 11/11 ✓
Hard blocks: 0
Soft warnings: 0

Phase 6 ACCEPTED. Ready to proceed to Phase 7 (Cost Guard).
```

---

## Status fazy 6

🟢 **Wszystkie sekcje 6.1-6.11 complete**

**Zawiera**:
- ✓ Sense + Coherence Guard architektura (6.1)
- ✓ Scope (docs+code+tests+deployment + opcjonalne cross-project) (6.2)
- ✓ Triggers (hybrid: phase boundaries + continuous + on-demand) (6.3)
- ✓ Severity levels (5-level) z per-project tuning (6.4)
- ✓ Detection mechanisms (rules + LLM hybrid, 2-tier architecture) (6.5)
- ✓ Baseline 15 checks + custom checks (3 mechanisms) (6.6)
- ✓ Findings handling adaptive per autonomy + auto-fix (6.7)
- ✓ Performance (separate worker, tiered cost, smart caching) (6.8)
- ✓ Aggregated Guards panel + per-Guard autonomy override (6.9)
- ✓ Edge cases — 22 cases w 5 kategoriach (6.10)
- ✓ Inheritance + DoD + acceptance test (6.11)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 6** + przejście do **Faza 7 — Cost Guard** (drugi z 5 Guards).
