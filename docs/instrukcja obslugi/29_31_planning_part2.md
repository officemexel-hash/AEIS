# FAZY 29-31 — Planowanie część 2 (Grupa D)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: D — Planowanie (4-6 z 6) — druga połowa
> **Zależności**: Fazy 1-28 zakończone (Masterplan z resource profile selected)
> **Następnik**: Faza 32 (Build Initialization — start grupy E Wykonanie)
>
> **⚡ Kontynuacja z fazy 28**:
> Faza 28 wprowadziła **resource profile selection** (5 profiles z Solo
> budget do Enterprise parallel). Fazy 29-31 są **profile-aware**:
>   • Faza 29 (Test Plan): same dla wszystkich profiles ale per-profile
>     wallclock different (parallel test generation)
>   • Faza 30 (Pre-Flight Cost): comprehensive breakdown per profile,
>     reconciliation z chosen profile cost
>   • Faza 31 (Dry Run): scope adjustments per profile (jeśli more
>     workers, dry run testuje multi-worker orchestration)
>
> **Charakter fazy 29-31**:
> Końcowe verification przed actual build. Operator po fazie 31 ma
> definitive GO lub NO-GO z high confidence (85%+).

---

# FAZA 29 — Test Plan Synthesis

> **Spis sekcji**:
> - 29.1 — Sense fazy + test plan z Księga acceptance criteria
> - 29.2 — Test scenarios per acceptance criterion
> - 29.3 — Per-test-level coverage
> - 29.4 — Mandatory human-like UI scenarios
> - 29.5 — Profile-aware test generation timing
> - 29.6 — Edge cases (15) + transition do fazy 30

---

## 29.1. Sens fazy

### 29.1.1. Test plan derivation

```
KSIĘGA Part IV (Implementation Guide):
  • 28 features w scope
  • Per feature: acceptance criteria (typically 3-7 AC)
  • Total AC: ~150 across all features

TEST PLAN (faza 29):
  • Test scenarios derived from AC
  • Per scenario: test level (L1-L5)
  • Coverage map (AC → tests)
  • Implementation strategy (frameworks, tools)
  • Profile-aware execution timing
```

### 29.1.2. Wynik fazy 29 (DoD)

```
✓ Test plan generated z all AC covered
✓ Per-AC test scenarios mapped
✓ L1-L5 distribution balanced
✓ Mandatory L5 human-like scenarios included
✓ Coverage map complete
✓ Profile-aware test execution timing
✓ Audit chain entry: test_plan_finalized
✓ Project state: READY_FOR_PREFLIGHT_COST
```

---

## 29.2. Test scenarios per AC

### 29.2.1. AC → test scenario mapping

```
┌──────────────────────────────────────────────────────────────┐
│  Test Plan Coverage Map                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Goal pg_2 KSeF compliance:                                  │
│                                                              │
│  AC-2.1: Invoice format compliance                           │
│   Test scenarios:                                             │
│    • L1: validate FA(2) schema unit tests (5 cases)           │
│    • L2: invoice generation integration test                  │
│    • L3: end-to-end invoice creation E2E                      │
│    • L5: human-like UI invoice creation flow (operator       │
│           creates invoice via UI, observes formatting)        │
│   Coverage: 100%                                             │
│                                                              │
│  AC-2.2: Submission do KSeF                                  │
│   Test scenarios:                                             │
│    • L2: KSeF submission integration test                    │
│    • L2: KSeF response parsing test                          │
│    • L3: submission flow E2E                                  │
│    • L5: human-like submission z error handling test          │
│   Coverage: 100%                                             │
│                                                              │
│  AC-2.3: Signature/timestamp                                 │
│   Test scenarios:                                             │
│    • L1: signature verification unit test                    │
│    • L1: timestamp validation unit test                      │
│    • L2: signed invoice generation integration                │
│   Coverage: 100%                                             │
│                                                              │
│  AC-2.4: Archive retention                                   │
│   Test scenarios:                                             │
│    • L2: archive write/read tests                            │
│    • L1: encryption tests                                     │
│    • L3: archive search E2E                                   │
│    • L4: archive performance over 5-year scenario            │
│   Coverage: 100%                                             │
│                                                              │
│  AC-2.5: Error handling                                      │
│   Test scenarios:                                             │
│    • L2: KSeF API error simulations (10 scenarios)            │
│    • L3: error recovery flows E2E                             │
│    • L5: operator notified about failed submissions           │
│   Coverage: 100%                                             │
│                                                              │
│  AC-2.6: Documentation                                       │
│   Test scenarios:                                             │
│    • L2: docs generation tests                                │
│    • L3: docs accessibility tests                             │
│    • Review-based: documentation completeness                 │
│   Coverage: 100%                                             │
│                                                              │
│  Goal pg_2 total: 6 AC, 27 test scenarios                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 29.2.2. Per-AC scenario count guidance

```
AC types and typical scenario counts:
  
  Functional AC:
    L1: 3-8 unit tests
    L2: 1-3 integration tests
    L3: 1-2 E2E tests
    L5: 1 human-like scenario
    Total: 6-14 scenarios per AC
  
  Performance AC:
    L1: 1-2 unit tests
    L4: 1-3 performance tests
    Total: 2-5 scenarios per AC
  
  Compliance AC:
    L1: 2-5 unit tests
    L2: 1-3 integration tests
    Review-based: 1 audit
    Total: 4-9 scenarios per AC
  
  UX AC:
    L3: 1-2 E2E tests
    L5: 2-3 human-like scenarios
    Total: 3-5 scenarios per AC
```

---

## 29.3. Per-test-level coverage

### 29.3.1. Coverage matrix

```
┌──────────────────────────────────────────────────────────────┐
│  Test Coverage Matrix — Customer Y CRM                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per test level:                                             │
│                                                              │
│  L1 Unit:                                                    │
│   Total tests: 187                                           │
│   Coverage: 87% (target 85%)                                 │
│   Cost dla L1 run: ~$0.40 per build                           │
│                                                              │
│  L2 Integration:                                             │
│   Total tests: 67                                            │
│   Coverage: API contracts + DB integration                   │
│   Cost dla L2 run: ~$1.80 per build                           │
│                                                              │
│  L3 E2E:                                                     │
│   Total tests: 23                                            │
│   Coverage: critical user journeys                           │
│   Cost dla L3 run: ~$2.40 per build                           │
│                                                              │
│  L4 Performance:                                             │
│   Total tests: 12                                            │
│   Coverage: latency + throughput targets                     │
│   Cost dla L4 run: ~$5.20 (pre-prod only)                     │
│                                                              │
│  L5 Human-like UI (MANDATORY):                               │
│   Total scenarios: 32                                        │
│   Coverage:                                                  │
│    • All forms (8 scenarios)                                  │
│    • All buttons (5 scenarios)                                │
│    • Navigation flows (6 scenarios)                           │
│    • Error scenarios (5 scenarios)                            │
│    • Multi-language switching (3 scenarios)                   │
│    • Accessibility (3 scenarios)                              │
│    • Mobile responsive (2 scenarios)                          │
│   Cost dla L5 run: ~$12.80 per build                          │
│                                                              │
│  Total per build cost: ~$22.60                                │
│  Test runs estimated: ~6 (during build phase)                 │
│  Total testing cost: ~$135 (within Quality Gates budget)      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 29.4. Mandatory human-like UI scenarios

### 29.4.1. L5 scenario template

Each L5 scenario:

```yaml
human_like_scenario:
  id: hu_l5_invoice_creation
  name: "Operator creates KSeF invoice end-to-end"
  
  applicable_to:
    - AC-2.1: Invoice format compliance
    - AC-2.2: Submission do KSeF
    - AC-2.5: Error handling
  
  preconditions:
    • User logged in (admin role)
    • At least 1 customer exists
    • KSeF sandbox configured
  
  test_steps:
    1. Navigate do Invoices section
    2. Click "Create new invoice"
    3. Select customer from dropdown
    4. Add invoice line items (3 items, varied amounts)
    5. Apply 23% VAT
    6. Add discount 10%
    7. Click "Generate"
    8. Verify invoice preview shows correct format (FA(2))
    9. Click "Submit do KSeF"
    10. Wait dla KSeF response (max 30 sek)
    11. Verify success message + KSeF ID assigned
    12. Verify invoice appears w archive
    13. Verify invoice email sent do customer
  
  observations_during_test:
    • Console errors: should be 0
    • Network errors: should be 0
    • Visual regressions: should match baseline
    • Animation issues: smooth UI
    • Loading states: appropriate spinners
  
  expected_outcome: invoice successfully created + submitted
  
  failure_handling:
    • Test framework reports specific failure
    • Auto-fix iterations attempt repair
    • Operator notified jeśli 5 iterations fail
  
  cost_per_run: ~$1.20
```

### 29.4.2. Customer-specific scenarios

```
Beyond standard scenarios, project-specific:
  
  • Customer Y branding visibility
   "Test że Customer Y logo visible on all pages"
  
  • Polish language switching
   "Switch UI z PL → EN → DE i back, verify translations"
  
  • Polish identifier validation
   "Try invalid PESEL/NIP, verify error messages w PL"
  
  • Customer-Y specific edge cases
   "Test cases derived from customer's previous bug reports"
   (jeśli available)
```

---

## 29.5. Profile-aware test generation timing ⚡ NEW

### 29.5.1. Why profile matters dla test generation

Test generation samo w sobie skaluje się z workers (z faza 28.4):

```
┌──────────────────────────────────────────────────────────────┐
│  Test Generation Time per Profile                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Total test scenarios: 321                                   │
│  Total generation work: ~32 hours (claude-haiku dla L1,      │
│                                     claude-sonnet dla L2-5)  │
│                                                              │
│  Per profile generation timing:                              │
│                                                              │
│  Profile 1 (1 worker):                                        │
│   Wallclock: 32 hours                                         │
│   Time spread: 4 days @ 8h/day                                │
│   Cost: $107 (no parallel overhead)                          │
│                                                              │
│  Profile 2 (2 workers):                                       │
│   Wallclock: 17.6 hours (z coordination overhead 10%)        │
│   Time spread: 2.2 days                                       │
│   Cost: $107 (same, parallel doesn't add significant cost)   │
│                                                              │
│  Profile 3 (4 workers):                                       │
│   Wallclock: 9.2 hours                                        │
│   Time spread: 1.2 days                                       │
│   Cost: $109 (small parallel overhead +2%)                    │
│                                                              │
│  Profile 4 (8 workers):                                       │
│   Wallclock: 5.6 hours                                        │
│   Time spread: <1 day                                         │
│   Cost: $113 (more coord overhead +6%)                        │
│                                                              │
│  Profile 5 (16 workers):                                      │
│   Wallclock: 3.2 hours                                        │
│   Time spread: <0.5 day                                       │
│   Cost: $122 (premium models +14%)                            │
│                                                              │
│  Note: test generation jest highly parallelizable,            │
│  jeden z najlepszych speed-up w całym projekcie.              │
└──────────────────────────────────────────────────────────────┘
```

### 29.5.2. Test execution timing per profile

Test EXECUTION (po generation) jest inny case:

```
┌──────────────────────────────────────────────────────────────┐
│  Test Execution Time per Profile                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per build run (assumes 6 builds during project):             │
│                                                              │
│  Profile 1:                                                   │
│   Per build: 22 min wallclock                                 │
│   6 builds: 132 min total                                     │
│                                                              │
│  Profile 2:                                                   │
│   Per build: 14 min (some parallel L2/L3)                    │
│   6 builds: 84 min total                                      │
│                                                              │
│  Profile 3:                                                   │
│   Per build: 9 min                                            │
│   6 builds: 54 min                                            │
│                                                              │
│  Profile 4:                                                   │
│   Per build: 6 min                                            │
│   6 builds: 36 min                                            │
│                                                              │
│  Profile 5:                                                   │
│   Per build: 4 min (limited by L6 integration tests)          │
│   6 builds: 24 min                                            │
│                                                              │
│  ⚠ Layer 6 (integration tests) ma low_parallel —              │
│   nie skaluje liniowo z workers. Always ~5-8 min minimum.    │
└──────────────────────────────────────────────────────────────┘
```

### 29.5.3. Profile-specific test plan adjustments

```
Customer Y CRM (Profile 2 selected):
  
  Test plan adjustments:
   • Test generation w Layer 5 (faza 28.4): 17.6h
   • Test execution per build: 14 min
   • Total testing time over project: ~17.6h gen + 84 min runs
                                     = ~19h
   
  Coverage validation: enabled per build
  Auto-fix iterations: max 3 (z autonomy preset Production)
  
  Profile-specific notes:
   • 2 workers means tests execute somewhat parallel
   • L6 integration tests bottleneck (always sequential)
   • L5 human-like scenarios still costly (~$12.80 per run)
```

---

## 29.6. Edge Cases — Test Plan (15)

### Kategoria A — Coverage issues (5)

**EC-A1**: AC has no testable scenarios
- Trigger: AC unmeasurable (e.g., "feels good")
- Akcje: refine AC z faza 17, define metric

**EC-A2**: AC over-tested (50 scenarios)
- Excessive scenarios, cost overrun
- Akcje: consolidate, remove redundant

**EC-A3**: Coverage drops below target
- L1 coverage 75% target 85%
- Akcje: add tests, lower target z reasoning

**EC-A4**: Critical paths under-tested
- Auth/payment paths low coverage
- Akcje: per-module targets, prioritize

**EC-A5**: Test scenarios missing dla mandatory L5
- Some features lack human-like scenarios
- Akcje: enforce, add automatically

### Kategoria B — Generation issues (4)

**EC-B1**: Test plan generation cost overrun
- Generation $25 vs $10 estimate
- Akcje: cheaper model, batch generation

**EC-B2**: Generated tests low quality
- Tests don't actually verify behavior
- Akcje: re-prompt, mutation testing

**EC-B3**: Test plan inconsistent z Księga
- Some AC covered, some missed
- Akcje: Coherence Guard catches, regenerate

**EC-B4**: Tests use wrong frameworks
- Operator uses pytest, plan uses unittest
- Akcje: respect operator preferences w prompts

### Kategoria C — Profile awareness (3 — NEW)

**EC-C1**: Test generation timeout zmienia się z profile
- Profile 1 generation 4 days, profile change mid-plan
- Akcje: re-estimate, adjust masterplan

**EC-C2**: Test execution bottleneck w high parallel
- Profile 4 fast generation but L6 still slow
- Akcje: communicate dependency, accept

**EC-C3**: Profile change po test plan generated
- Operator switches Profile 2 → Profile 4
- Akcje: re-estimate timing, no test changes needed

### Kategoria D — Recovery (3)

**EC-D1**: Test plan corruption
- File damage
- Akcje: regenerate, restore z backup

**EC-D2**: Test plan-Księga drift
- Księga revised, plan stale
- Akcje: re-generate affected sections

**EC-D3**: Per-AC scenarios deleted accidentally
- Operator removed scenarios mistake
- Akcje: rollback, audit log

---

## 29.7. Acceptance + transition do fazy 30

```bash
$ aeis-cli phase29-acceptance-test --project proj_customer_y_crm

[1/8] Test plan generated                              ✓ PASS
[2/8] All Księga AC covered                            ✓ PASS (150/150)
[3/8] L1-L5 distribution balanced                      ✓ PASS
[4/8] Mandatory L5 scenarios included                  ✓ PASS (32 scenarios)
[5/8] Coverage map complete                            ✓ PASS
[6/8] Profile-aware execution timing                   ✓ PASS (Profile 2)
[7/8] Operator reviewed                                ✓ PASS
[8/8] Audit chain entry test_plan_finalized            ✓ PASS

DoD: 8/8 ✓
Phase 29 ACCEPTED. Ready dla Phase 30 (Pre-Flight Cost Preview).
```

---

# FAZA 30 — Pre-Flight Cost Preview

> **Spis sekcji**:
> - 30.1 — Sense fazy + final cost reconciliation przed build
> - 30.2 — Profile-aware comprehensive cost breakdown
> - 30.3 — Risk-adjusted estimates per profile
> - 30.4 — Customer notification z profile choice
> - 30.5 — Operator final go/no-go
> - 30.6 — Edge cases (15) + transition do fazy 31

---

## 30.1. Sens fazy

### 30.1.1. Final reconciliation z profile awareness

Przed actual build (faza 32+), operator powinien zobaczyć **definitive
cost preview** based on **chosen resource profile** (z faza 28):

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Flight Cost Preview — Profile-Aware                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z faz 26-29):                                        │
│   • Model assignments (faza 26)                              │
│   • Skill assignments + cost per skill (faza 27)              │
│   • Masterplan tasks z layer decomposition (faza 28)          │
│   • Resource profile selected (faza 28.5)                     │
│   • Test plan z testing costs (faza 29)                       │
│   • Risk register z mitigation costs                          │
│                                                              │
│  PROCESSING:                                                 │
│   • Aggregate all costs WITH profile multipliers              │
│   • Apply variance ranges per profile                         │
│   • Risk-adjust dla critical paths                           │
│   • Compare z budget                                         │
│   • Show alternatives (other profiles cost-time matrix)       │
│   • Identify reduction options                                │
│                                                              │
│  OUTPUT:                                                     │
│   • Definitive cost estimate per chosen profile               │
│   • P10/P50/P90 confidence intervals per profile              │
│   • Per-phase breakdown z profile multipliers                 │
│   • Final go/no-go decision                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 30.1.2. Wynik fazy 30 (DoD)

```
✓ Comprehensive cost breakdown (chosen profile)
✓ Variance ranges established (per profile)
✓ Risk-adjusted estimate
✓ Customer notification (jeśli customer-funded)
✓ Operator go/no-go decision
✓ Profile lock-in confirmed (lub mid-build switching reserved)
✓ Audit chain entry: preflight_cost_approved
✓ Project state: READY_FOR_DRY_RUN
```

---

## 30.2. Profile-aware comprehensive cost breakdown

### 30.2.1. Hierarchical breakdown z chosen profile

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Flight Cost Breakdown — Customer Y CRM                  │
│  Selected Profile: 2 (Solo balanced)                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASES OVERVIEW                                             │
│   Already spent (Phases 1-29):                               │
│    • Council deliberation:    $14.20                         │
│    • Council Book + Księga:   $42.40                         │
│    • Planning (faz 26-29):     $32.10                         │
│    • Subtotal already:         $88.70                         │
│                                                              │
│   To be spent (Phases 30-41) z Profile 2:                    │
│    • Pre-flight (this phase):  $0.10                         │
│    • Dry run (faza 31):        $5.00                         │
│    • Build (fazy 32-36):       $148.00 (z Profile 2)          │
│    • Guards continuous:        $25.00 (z Profile 2 scaling)   │
│    • Testing (fazy 37-38):     $35.00                         │
│    • Environments (staging):   $16.00 (3 weeks Hetzner CX21)  │
│    • Deployment (fazy 39-40):  $42.00                         │
│    • Closure (faza 41):        $5.00                         │
│    • Subtotal remaining:       $276.10                        │
│                                                              │
│   TOTAL PROJECT (Profile 2):    $364.80                       │
│   Budget:                       $345.00                        │
│   ⚠ OVERRUN:                    $19.80 (5.7%)                 │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  ALTERNATIVE PROFILES (cost vs time):                         │
│                                                              │
│  Profile 1 (Solo budget):                                     │
│   Build:   $145, Guards: $5, Envs: $0                         │
│   Total: $321 (within budget, headroom $24)                   │
│   Timeline: 8.5 weeks (deadline tight)                        │
│   Risk: schedule slippage z 1 worker                           │
│                                                              │
│  Profile 2 (Solo balanced) — current selection:               │
│   Build:   $148, Guards: $25, Envs: $16                       │
│   Total: $364 (5.7% overrun)                                  │
│   Timeline: 5 weeks (3 weeks buffer)                          │
│   Risk: low-medium                                           │
│                                                              │
│  Profile 3 (Burst parallel):                                  │
│   Build:   $152, Guards: $50, Envs: $30                       │
│   Total: $407 (18% overrun)                                   │
│   Timeline: 2-3 weeks (5 weeks buffer)                        │
│   Risk: medium (more coordination)                           │
│                                                              │
│  Profile 4 (Maximum parallel):                                │
│   Build:   $158, Guards: $103, Envs: $50                      │
│   Total: $476 (38% overrun)                                   │
│   Timeline: 1-1.5 weeks (huge buffer)                         │
│   Risk: medium-high                                          │
│                                                              │
│  Profile 5 (Enterprise):                                      │
│   Build:   $175, Guards: $200, Envs: $80                      │
│   Total: $620 (80% overrun)                                   │
│   Timeline: 4-6 days                                         │
│   Risk: high                                                 │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  PER-PHASE DETAILED (Profile 2)                              │
│                                                              │
│  Build phase (faza 32-36):                                    │
│   Backend code generation:                                    │
│    • 35 components × $0.40 avg = $14.00                       │
│    • Variance: ±20% → ($11.20 - $16.80)                      │
│   Frontend code generation:                                   │
│    • 28 components × $0.50 avg = $14.00                       │
│    • Variance: ±15% → ($11.90 - $16.10)                      │
│   Database migrations:                                       │
│    • 8 migrations × $0.80 = $6.40                            │
│    • Variance: ±10% → ($5.76 - $7.04)                        │
│   Test generation (parallel z Profile 2):                     │
│    • 187 unit × $0.08 = $14.96                                │
│    • 67 integration × $0.40 = $26.80                          │
│    • 23 E2E × $1.20 = $27.60                                  │
│    • 32 L5 × $1.20 = $38.40                                   │
│    • Subtotal: $107.76                                        │
│   PL documentation: $5 (lokalne bielik)                       │
│   EN documentation: $4                                        │
│   Translations: $3                                            │
│   Reviews + analysis: $8                                      │
│   Stripe + KSeF specific: $12                                 │
│   ────────────────────────────                              │
│   Build subtotal: $174.16 (single-worker baseline)           │
│   Profile 2 multiplier: 0.85 (parallel efficiency)           │
│   Profile 2 build cost: $148.00                              │
│                                                              │
│  Guards phase (continuous z Profile 2):                      │
│   Coherence Guard: $12 (T1 lokalne + T2 sonnet)              │
│   Cost Guard: $0 (built-in)                                  │
│   Security Guard: $5 (per phase boundary)                     │
│   Quality Guard: $3 (per test run)                            │
│   Provenance Guard: $2 (audit chain)                          │
│   Cross-worker checks: $3                                     │
│   ────────────────────────────                              │
│   Guards subtotal: $25                                        │
│                                                              │
│  Testing phase (faza 37-38):                                  │
│   • L1 runs (~6 builds): $2.40                                │
│   • L2 runs (~6 builds): $10.80                               │
│   • L3 runs (~6 builds): $14.40                               │
│   • L4 (pre-prod only): $5.20                                 │
│   • L5 (mandatory, ~6 runs): $76.80                           │
│   ────────────────────────────                              │
│   Testing subtotal: $109.60                                   │
│                                                              │
│  ⚠ Testing $110 SIGNIFICANTLY EXCEEDS allocated $35           │
│                                                              │
│  Environments (Profile 2 = staging only):                    │
│   Hetzner CX21 staging: €4.20/mo × 3 weeks = ~$16             │
│                                                              │
│  Deployment phase (faza 39-40):                               │
│   • Pre-deploy validation: $3                                 │
│   • Deploy execution: $8 (canary stages)                      │
│   • Cloud resources: $25 (Hetzner first month)                │
│   • Customer training prep: $5                                │
│   • Monitoring setup: $4                                      │
│   ────────────────────────────                              │
│   Deployment subtotal: $45                                    │
│                                                              │
│  ─────────────────────────────────────                       │
│                                                              │
│  RECONCILIATION                                              │
│                                                              │
│   Original Council estimate:   $345                           │
│   Pre-flight refined (Prof 2):  $364                           │
│   OVERRUN:                      $19 (5.7%)                    │
│                                                              │
│  ⚠ MINOR OVERRUN — easier to handle than $131 (z 1-worker)    │
│                                                              │
│  Root cause analysis:                                         │
│   • Test plan generated more scenarios than estimated         │
│   • Guards costs higher z Profile 2 multiplier (still rea-   │
│     sonable vs Profile 4 $103)                                │
│   • Environment cost added (Profile 2 has staging)            │
│                                                              │
│  Options:                                                     │
│   [● Customer approves €18 overrun (~$20)]                    │
│       Customer Y has €100 unused dla overrun                  │
│       Likely auto-approve                                    │
│   [○ Switch to Profile 1 (saves $43 but +3.5 weeks)]          │
│   [○ Operator absorbs $20]                                    │
│   [○ Reduce L5 scenarios (cut 2 non-essential, save $2.40)]   │
│   [○ Use cheaper test generation (haiku for L2, save ~$15)]   │
│   [○ Combination of above]                                    │
│                                                              │
│  [Proceed z reconciliation]  [Detailed analysis]             │
└──────────────────────────────────────────────────────────────┘
```

---

## 30.3. Risk-adjusted estimates per profile

### 30.3.1. Confidence intervals per profile

```
Cost confidence intervals dla each profile:

Profile 1 (Solo budget):
  P10 (best case):    $282
  P50 (likely):       $321
  P90 (worst case):   $402

Profile 2 (Solo balanced):
  P10 (best case):    $310
  P50 (likely):       $364
  P90 (worst case):   $448

Profile 3 (Burst parallel):
  P10 (best case):    $345
  P50 (likely):       $407
  P90 (worst case):   $512

Profile 4 (Maximum parallel):
  P10 (best case):    $402
  P50 (likely):       $476
  P90 (worst case):   $612

Profile 5 (Enterprise):
  P10 (best case):    $520
  P50 (likely):       $620
  P90 (worst case):   $810
  
Operator should plan dla P50 budget z P90 contingency.
Customer Y CRM with Profile 2:
  P50 = $364 (5.7% overrun, manageable)
  P90 = $448 (29% overrun, customer approval needed)
```

### 30.3.2. Risk mitigation costs

```
If risks materialize:
  
  R1 (KSeF integration complexity):
   Mitigation cost: $20-40
   Already partially budgeted (early integration)
   Profile-independent (cost similar across profiles)
  
  R2 (Stripe Polish compliance):
   Mitigation cost: $10-20
   Low likelihood
  
  R3 (Customer scope creep):
   Mitigation: scope discipline (no extra cost jeśli avoided)
   If happens: $30-100
  
  R4 (Customer availability):
   Mitigation: async approvals (already designed)
   Profile-specific impact:
    Profile 1-2: minimal (operator-driven)
    Profile 3-4: medium (more decisions to await)
    Profile 5: high (rapid iterations need fast approvals)
```

### 30.3.3. Profile change cost projection

```
Co jeśli operator chce switch profile mid-build:

  Profile 2 → Profile 3 mid-build:
   Switch cost: ~$15 (provision new env, scale workers)
   New estimated: $407 - already_spent
   Net additional: ~$30-40
   Time saved: 2-3 weeks
  
  Profile 2 → Profile 1 mid-build:
   Switch cost: ~$5 (drain workers, decommission staging)
   New estimated: $321 - already_spent
   Net savings: ~$30-40
   Time added: 3.5 weeks
  
  Profile 3 → Profile 4 mid-build:
   Switch cost: ~$25 (more workers, more envs, retrain Guards)
   New estimated: $476 - already_spent
   Net additional: ~$70
   Time saved: 1-2 weeks
  
  Switch decisions can be made:
   • Po faza 32 (build init) — easy switch
   • Po faza 33 (sequential phase 1 done) — moderate switch
   • Po faza 35 (build orchestration mid) — hard switch (preserve work)
   • Po faza 36 (build complete) — too late
```

---

## 30.4. Customer notification z profile choice

### 30.4.1. Customer-facing summary

```
┌──────────────────────────────────────────────────────────────┐
│  Customer Y Notification                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Subject:                                                    │
│   "Customer Y CRM — Final Cost & Timeline Estimate"           │
│                                                              │
│  Customer-facing PDF attached                                 │
│                                                              │
│  Body (Polish, customer-facing):                              │
│  ────────────────────────────────                            │
│                                                              │
│  Szanowna Pani Anna,                                         │
│                                                              │
│  Po zakończeniu fazy planowania, mamy ostateczne estymaty    │
│  dla projektu Customer Y CRM.                                │
│                                                              │
│  WYBRANY PLAN REALIZACJI:                                    │
│   Profil: Solo Balanced (2 workers, środowisko staging)      │
│                                                              │
│  KOSZT:                                                       │
│   Estymowany: $364 (z VAT i opłatami)                         │
│   Pierwotnie planowany: $345                                  │
│   Przekroczenie: $19 (5.7%)                                   │
│   Mieści się w Państwa policy €100 buffer.                    │
│                                                              │
│  HARMONOGRAM:                                                │
│   Czas realizacji: 5 tygodni                                  │
│   Termin Państwa: 8 tygodni (3 tygodnie buffer)              │
│   Status: ✓ W terminie                                        │
│                                                              │
│  ALTERNATYWY (jeśli Państwo preferują):                       │
│   • Plan ekonomiczny: $321 / 8.5 tygodni (cisza w terminie)   │
│   • Plan szybki: $407 / 2-3 tygodnie (znacznie szybciej)      │
│   • Plan ekspresowy: $476 / 1-1.5 tygodni (najszybciej)       │
│                                                              │
│  CO POKRYWA $364:                                             │
│   • Pełna implementacja systemu CRM                           │
│   • Integracja z KSeF (faktury elektroniczne)                 │
│   • Integracja Stripe (płatności online)                      │
│   • UI po polsku i angielsku                                  │
│   • Pełna zgodność z RODO i WCAG 2.1 AA                       │
│   • Testy i deployment do produkcji                           │
│   • Dokumentacja użytkownika i administratora                  │
│   • Tygodniowe statusy + finalne szkolenie                    │
│                                                              │
│  CO WYMAGA AKCEPTACJI:                                        │
│   1. Akceptacja $19 przekroczenia budżetu                     │
│   2. Wybór planu realizacji (lub akceptacja Solo Balanced)    │
│                                                              │
│  PROSIMY O ODPOWIEDŹ DO 2026-05-08.                           │
│  Po akceptacji rozpoczynamy budowę.                           │
│                                                              │
│  Z poważaniem,                                                │
│  Robert                                                      │
│  ────────────────────────────────                            │
│                                                              │
│  Operator review przed wysłaniem:                             │
│   ☑ Polish translation reviewed                               │
│   ☑ Customer-friendly language                                │
│   ☑ Internal AEIS terminology removed                         │
│   ☑ Cost transparency without intimidation                    │
│                                                              │
│  [Send to customer]  [Edit message]  [Defer sending]          │
└──────────────────────────────────────────────────────────────┘
```

---

## 30.5. Operator final go/no-go

### 30.5.1. Decision interface

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Flight Final Decision — Customer Y CRM                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Selected: Profile 2 (Solo balanced)                          │
│                                                              │
│  Customer status:                                             │
│   ✓ Notification sent                                         │
│   ⠋ Awaiting customer response (1 day elapsed of 3)           │
│                                                              │
│  Reconciliation strategy:                                     │
│   Customer approves $19 overrun (default expected)            │
│   New estimate: $364 within €100 customer buffer              │
│                                                              │
│  Timeline reconciliation:                                     │
│   Estimated: 5 weeks                                          │
│   Risk-adjusted (P50): 5 weeks                                │
│   Risk-adjusted (P90): 6.5 weeks                              │
│   Customer deadline: 8 weeks                                  │
│   Buffer: 1.5 weeks (P90)                                     │
│   Status: ✓ Comfortable                                        │
│                                                              │
│  Profile lock-in decision:                                    │
│   [● Lock Profile 2 dla entire build]                         │
│       Most predictable                                        │
│       Switching disabled w fazy 32-36                         │
│   [○ Lock Profile 2 z option to switch]                       │
│       Allows mid-build profile change                         │
│       Switch costs apply (~$15 dla up, ~$5 dla down)          │
│   [○ Profile 2 dla phase 1, decide po                         │
│       phase 1 milestone]                                      │
│       Adaptive planning                                       │
│                                                              │
│  Operator decision:                                          │
│   [● Confirm Profile 2 + send to customer (await approval)]   │
│   [○ Operator approves bez customer (absorb overrun)]         │
│   [○ Switch to Profile 1 (within budget, slower)]             │
│   [○ Switch to Profile 3 (faster, +overrun)]                  │
│   [○ Pause project pending revision]                          │
│   [○ Cancel project]                                          │
│                                                              │
│  ⚠ This is final go/no-go before build starts.                │
│  ⚠ After confirming, dry run (faza 31) executes.              │
│  ⚠ After dry run GO, faza 32 starts actual build.             │
│                                                              │
│  [Confirm decision]                                          │
└──────────────────────────────────────────────────────────────┘
```

### 30.5.2. Customer response handling

```
Po customer responds:
  
  Scenario 1 — Customer approves z reservations:
   Customer accepts $19 overrun.
   May request specific updates (e.g., weekly status reports).
   Akcje:
    • Acknowledge customer
    • Document updates w project notes
    • Proceed do faza 31
  
  Scenario 2 — Customer wants different profile:
   Customer prefers Profile 1 (cheaper, longer)
   Akcje:
    • Re-do faza 28.8 z new profile
    • Re-do faza 30 z new estimates
    • Acknowledge customer
    • Re-send confirmation
    • Proceed do faza 31
  
  Scenario 3 — Customer rejects/disputes:
   Customer thinks too expensive
   Akcje:
    • Negotiate scope cut
    • Switch to Profile 1
    • Defer project
    • Cancel
  
  Scenario 4 — Customer doesn't respond (timeout):
   3 days elapsed, no response
   Akcje:
    • Reminder sent
    • Operator decision: proceed lub defer
    • Audit log
```

---

## 30.6. Edge Cases — Pre-Flight Cost (15)

### Kategoria A — Estimation issues (5)

**EC-A1**: Estimate vary widely w cycles
- Estimate keeps changing across phases
- Akcje: lock estimate now, accept variance

**EC-A2**: Estimate exceeds workspace budget cap
- $476 > $250 hard cap (z higher profile)
- Akcje: scope cut required, customer-funded only, switch profile

**EC-A3**: Customer policy doesn't cover overrun
- Customer cap €500, estimate €580
- Akcje: scope cut, customer renegotiation, decline

**EC-A4**: Risk-adjusted P90 alarming
- $612 P90 dla $345 budget (Profile 4)
- Akcje: contingency plan, scope reduction options, switch profile

**EC-A5**: Vendor pass-through unclear
- Stripe fees variable based on transactions
- Akcje: estimate range, monitor closely

### Kategoria B — Profile reconciliation issues (4 — NEW)

**EC-B1**: Chosen profile too expensive po reconciliation
- Profile 4 selected, exceeds budget by 50%
- Akcje: switch to lower profile, customer approves higher, scope cut

**EC-B2**: Profile lock conflict z mid-build switching
- Operator wants flexible but lock-in confirmed
- Akcje: change lock setting, document decision

**EC-B3**: Profile alternative shows better trade-off
- Operator picks Profile 2, Profile 3 only $43 more dla 2 weeks faster
- Akcje: re-evaluation, customer notification

**EC-B4**: Profile multiplier inaccurate
- Build cost $148 estimated, $180 actual (z Profile 2)
- Akcje: calibrate multipliers from actual data, update planning model

### Kategoria C — Customer interaction (3)

**EC-C1**: Customer doesn't respond
- Notification sent, no reply
- Akcje: timeout, escalation, defer

**EC-C2**: Customer wants different profile
- Customer prefers Profile 1 (cheaper, longer)
- Akcje: re-plan z new profile

**EC-C3**: Customer changes mind on overrun
- Initially approved, withdraws later
- Akcje: stop project, refund consideration

### Kategoria D — Operator decision (3)

**EC-D1**: Operator wants over-budget proceed
- Absorb overrun
- Akcje: confirm, audit log, monitor closely

**EC-D2**: Operator wants major scope cut
- Cut 30% scope dla budget
- Akcje: regenerate Księga (revision), re-Council

**EC-D3**: Operator cancels
- Decides not feasible
- Akcje: clean cancel, audit log, customer notify

---

## 30.7. Acceptance + transition do fazy 31

```bash
$ aeis-cli phase30-acceptance-test --project proj_customer_y_crm

[1/8] Comprehensive cost breakdown                     ✓ PASS
[2/8] Profile-aware cost estimate                      ✓ PASS (Profile 2)
[3/8] Variance ranges established                      ✓ PASS (P10/P50/P90)
[4/8] Risk-adjusted estimate                           ✓ PASS
[5/8] Customer notification (if customer-funded)       ✓ PASS
[6/8] Operator go/no-go decision                       ✓ PASS
[7/8] Reconciliation strategy applied                  ✓ PASS
[8/8] Audit chain entry preflight_cost_approved        ✓ PASS

DoD: 8/8 ✓
Phase 30 ACCEPTED. Ready dla Phase 31 (Pre-Flight Dry Run).
```

---

# FAZA 31 — Pre-Flight Dry Run

> **Spis sekcji**:
> - 31.1 — Sense fazy + simulate first build phase
> - 31.2 — Profile-specific dry run scope
> - 31.3 — Dry run execution
> - 31.4 — Issue detection + correction
> - 31.5 — Final go decision
> - 31.6 — Edge cases (16) + transition do fazy 32

---

## 31.1. Sens fazy

### 31.1.1. Dry run = simulation przed actual build

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Flight Dry Run — simulate before commit                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Why dry run:                                                │
│   • Catch issues before $148 build commit                    │
│   • Verify orchestration works (z chosen profile)             │
│   • Test model availability                                   │
│   • Test skill execution                                      │
│   • Test environment readiness                                │
│   • Test integration points                                   │
│   • Test parallel coordination (z multi-worker profiles)      │
│                                                              │
│  Cost: $5-10 (zależne od profile)                             │
│  Time: 15-45 min (zależne od profile complexity)              │
│                                                              │
│  Result:                                                     │
│   GO or NO-GO decision z high confidence                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 31.1.2. Wynik fazy 31 (DoD)

```
✓ Dry run executed (limited scope of phase 1)
✓ Profile-specific orchestration verified
✓ All systems verified working
✓ Issues detected + corrected
✓ Final go/no-go z high confidence (85%+)
✓ Audit chain entry: dry_run_complete
✓ Project state: READY_FOR_BUILD (faza 32)
```

---

## 31.2. Profile-specific dry run scope

### 31.2.1. Scope adjustments per profile

Different profiles wymagają different dry run scope dla validation:

```
┌──────────────────────────────────────────────────────────────┐
│  Dry Run Scope per Profile                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Profile 1 (Solo budget — 1 worker):                         │
│   Tasks tested: 5-7 representative                            │
│   Cost: $5                                                    │
│   Time: 15-30 min                                            │
│   Focus: model availability, skill execution                  │
│                                                              │
│  Profile 2 (Solo balanced — 2 workers):                       │
│   Tasks tested: 7-10 (z parallel verification)                │
│   Cost: $6-8                                                  │
│   Time: 20-35 min                                            │
│   Focus: + 2-worker coordination, env readiness              │
│                                                              │
│  Profile 3 (Burst parallel — 4 workers):                      │
│   Tasks tested: 12-15 (parallel batches)                      │
│   Cost: $10-12                                                │
│   Time: 25-45 min                                            │
│   Focus: + multi-worker conflicts, Guards parallel scaling   │
│                                                              │
│  Profile 4 (Maximum parallel — 8 workers):                    │
│   Tasks tested: 18-22 (full parallel test)                    │
│   Cost: $15-18                                                │
│   Time: 30-60 min                                            │
│   Focus: + cross-worker coherence, env divergence checks     │
│                                                              │
│  Profile 5 (Enterprise — 16 workers):                         │
│   Tasks tested: 25-30 (extreme parallel test)                 │
│   Cost: $25-35                                                │
│   Time: 45-90 min                                            │
│   Focus: + all above + external Guards models verification   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 31.2.2. Limited scope simulation (Profile 2)

```
┌──────────────────────────────────────────────────────────────┐
│  Dry Run Scope — Customer Y CRM (Profile 2)                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Goals:                                                      │
│   • Verify all systems work end-to-end                       │
│   • Test 2-worker coordination                                │
│   • Verify staging environment ready                          │
│   • NIE produce production-ready output                       │
│   • Catch any orchestration issues                            │
│                                                              │
│  Tasks simulated (8 representative dla Profile 2):           │
│   1. Generate single FastAPI route (claude-sonnet)            │
│   2. Generate single React component (claude-sonnet)          │
│   3. Generate database migration (claude-opus)                │
│   4. Generate unit tests (claude-haiku) — parallel z #1       │
│   5. Generate KSeF skill output (claude-opus + bielik RAG)    │
│   6. Generate Stripe skill output (marketplace skill)        │
│   7. Run Coherence Guard on outputs (T1 lokalne + T2 sonnet)  │
│   8. Test 2-worker coordination (assign tasks 1+4 parallel)   │
│                                                              │
│  Verification:                                               │
│   • Each model responds                                       │
│   • Each skill executes                                       │
│   • Outputs parseable                                         │
│   • Coherence Guard processes (z parallel-aware checks)      │
│   • Audit chain entries created                               │
│   • 2-worker coordination clean (no deadlocks)               │
│   • Staging environment provisioned correctly                 │
│   • Cost tracking accurate                                    │
│                                                              │
│  Cost budget: $7                                              │
│  Time budget: 35 min                                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 31.3. Dry run execution

### 31.3.1. Live execution view

```
┌──────────────────────────────────────────────────────────────┐
│  Dry Run Execution — Profile 2                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Status:                                                     │
│   ✓ Task 1: FastAPI route generated (Worker 1)               │
│      Cost: $0.42, Time: 15s, Quality: PASS                   │
│                                                              │
│   ✓ Task 4: Unit tests generated (Worker 2, parallel)        │
│      Cost: $0.16, Time: 12s, Quality: PASS                   │
│      (Parallel z Task 1 — clean coordination)                │
│                                                              │
│   ✓ Task 2: React component generated (Worker 1)             │
│      Cost: $0.51, Time: 18s, Quality: PASS                   │
│                                                              │
│   ✓ Task 3: Database migration generated (Worker 1)          │
│      Cost: $0.78, Time: 22s, Quality: PASS                   │
│                                                              │
│   ⠋ Task 5: KSeF skill output (Worker 2)                     │
│      Cost: $1.40, Estimated: 30-45s                           │
│                                                              │
│   ⠋ Task 6: Stripe skill output (Worker 1, parallel z #5)    │
│   ⠋ Task 7: Coherence Guard validation (continuous)          │
│   ⠋ Task 8: 2-worker coordination test                       │
│                                                              │
│  Live cost: $4.27 / $7 budget                                 │
│  Time: 14 min / 35 min                                        │
│                                                              │
│  Worker status:                                              │
│   Worker 1: Task 6 (active, GPU 35%)                          │
│   Worker 2: Task 5 (active, GPU 45%)                          │
│   Both workers communicating cleanly via shared state         │
│                                                              │
│  Environment status:                                          │
│   Staging Hetzner CX21: ✓ provisioned, healthy                │
│                                                              │
│  Guards status:                                              │
│   Coherence T1 (lokalne): 12 checks done, 0 issues            │
│   Coherence T2 (sonnet): 2 checks done, 0 issues              │
│   Cost: tracking 100% accurate                                │
│   Provenance: 24 audit entries created                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 31.4. Issue detection + correction

### 31.4.1. Common dry run issues

```
Issues that surface w dry run:

  • Model unavailable (provider issue)
   Akcje: switch model, wait for recovery
  
  • Skill prompt produces unexpected format
   Akcje: refine prompt, adjust validation
  
  • Knowledge base query returns wrong context
   Akcje: re-index KB, adjust query
  
  • Coherence Guard catches false positive
   Akcje: tune Guard, suppress per check
  
  • Cost overrun (small task expensive)
   Akcje: switch model, refine task
  
  • Performance issue (slow model)
   Akcje: parallel where possible, switch
  
  • Multi-worker coordination issue (Profile 2+):
   - Race conditions on shared state
   - Worker deadlocks
   - Coordination overhead higher than estimated
   Akcje: adjust coordination patterns, isolate state better

  • Environment provisioning issue:
   - Staging not ready
   - Network connectivity problems
   - Permissions misconfigured
   Akcje: re-provision, fix configs, fallback to local-only

  • Guards parallel scaling issue (Profile 3+):
   - Cross-worker coherence checks overload
   - Guards models hitting rate limits
   Akcje: throttle Guards, switch models, reduce frequency
```

### 31.4.2. Issue resolution interface

```
┌──────────────────────────────────────────────────────────────┐
│  Dry Run Issue Detected                                      │
│                                                              │
│  Task 5: KSeF skill output                                   │
│  Status: ✗ FAILED                                             │
│                                                              │
│  Issue: Bielik RAG returned outdated KSeF documentation       │
│          (2024 version, KSeF API updated to 2026)             │
│                                                              │
│  Impact:                                                     │
│   Generated skill output references deprecated endpoints     │
│   Would fail w actual build                                   │
│                                                              │
│  Recommendation:                                             │
│   Update KSeF knowledge base before build:                    │
│    • Re-index latest KSeF API docs                            │
│    • Verify schema versions                                   │
│    • Test skill again                                         │
│                                                              │
│  Akcje:                                                      │
│   [● Pause dry run, fix KB]                                   │
│       Update KB, re-run dry run                              │
│   [○ Continue dry run, fix later]                             │
│       Note issue, address before build                       │
│   [○ Use claude-opus only (no RAG)]                           │
│       Skip Bielik dla KSeF, use opus z latest docs            │
│                                                              │
│  [Apply fix]                                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 31.5. Final go decision

### 31.5.1. Dry run results

```
┌──────────────────────────────────────────────────────────────┐
│  Dry Run Complete — Profile 2                                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Results:                                                    │
│   ✓ Task 1: PASS (FastAPI route, Worker 1)                   │
│   ✓ Task 2: PASS (React component, branding applied)         │
│   ✓ Task 3: PASS (Database migration valid)                  │
│   ✓ Task 4: PASS (Unit tests, parallel z Task 1)             │
│   ⚠ Task 5: WARN (KB outdated, FIXED + re-tested)            │
│   ✓ Task 6: PASS (Stripe skill, marketplace working)         │
│   ✓ Task 7: PASS (Coherence Guard runs, no issues)           │
│   ✓ Task 8: PASS (2-worker coordination clean)               │
│                                                              │
│  Cost spent: $5.80 / $7 budget                                │
│  Time spent: 32 min / 35 min                                  │
│                                                              │
│  System verifications:                                        │
│   ✓ All providers reachable                                   │
│   ✓ All models responding correctly                           │
│   ✓ All skills executable                                     │
│   ✓ Knowledge bases accessible (po fix)                       │
│   ✓ Coherence Guard functional (T1 + T2)                      │
│   ✓ Audit chain logging                                       │
│   ✓ Cost tracking accurate                                    │
│   ✓ Multi-worker coordination clean                           │
│   ✓ Staging environment provisioned                           │
│                                                              │
│  Profile-specific verifications (Profile 2):                  │
│   ✓ 2-worker parallel execution working                       │
│   ✓ Worker coordination overhead 11% (within 5-15% budget)   │
│   ✓ Guards scaling z 2 workers tested                         │
│   ✓ Environment + worker integration clean                    │
│                                                              │
│  Issues found:                                               │
│   • 1 (KB outdated, FIXED)                                    │
│                                                              │
│  Confidence dla actual build: HIGH (88%+)                     │
│                                                              │
│  Profile re-evaluation:                                       │
│   Profile 2 working well. No need to switch.                  │
│   [○ Switch to Profile 3 dla faster build (extra $43)]        │
│   [○ Switch to Profile 1 dla cheaper (slower)]                │
│   [● Stay z Profile 2 (recommended)]                          │
│                                                              │
│  Final go/no-go:                                             │
│                                                              │
│  [● GO — proceed do Phase 32 (Build)]                         │
│  [○ NO-GO — investigate further]                              │
│  [○ Modify masterplan based on dry run learnings]             │
│                                                              │
│  ⚠ Final commitment to build phase ($276 remaining budget).   │
│     After GO, build starts.                                   │
│                                                              │
│  [Confirm GO]                                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 31.6. Edge Cases — Dry Run (16)

### Kategoria A — Execution issues (5)

**EC-A1**: Provider down during dry run
- Anthropic outage mid-test
- Akcje: pause, retry, fallback

**EC-A2**: Skill timeout
- Skill execution >5 min
- Akcje: investigate, optimize, accept timeout

**EC-A3**: Cost overrun w dry run
- $10 vs $7 budget (Profile 2)
- Akcje: investigate, may indicate build will exceed too

**EC-A4**: Multiple parallel issues
- Several tasks fail simultaneously
- Akcje: investigate root cause, may indicate systemic issue

**EC-A5**: Output validation fails
- Generated output unparseable
- Akcje: refine validation, switch model

### Kategoria B — Profile-specific issues (4 — NEW)

**EC-B1**: Multi-worker coordination fails
- Profile 2+ worker deadlock detected
- Akcje: simplify coordination, single-worker fallback

**EC-B2**: Guards parallel scaling fails
- Profile 3+ Guards overloaded
- Akcje: throttle Guards, use lokalne instead of external

**EC-B3**: Environment provisioning slow
- Staging takes 10 min to provision
- Akcje: pre-provision, accept delay, simpler env

**EC-B4**: Cross-worker coherence false positives
- Workers writing parallel = many cross-module conflicts
- Akcje: tune Coherence Guard sensitivity per profile

### Kategoria C — System issues (4)

**EC-C1**: Audit chain doesn't log
- Provenance Guard issue
- Akcje: investigate, fix before build

**EC-C2**: Coherence Guard not triggered
- Guard expected, didn't run
- Akcje: investigate config, fix

**EC-C3**: KB query mismatch
- Wrong knowledge retrieved
- Akcje: re-index, refine query, update KB

**EC-C4**: Skill assignments wrong
- Module gets wrong skill
- Akcje: re-do faza 27, fix assignments

### Kategoria D — Operator review + recovery (3)

**EC-D1**: Operator unsatisfied z output quality
- Outputs technically pass but operator doesn't like
- Akcje: refine prompts, switch model

**EC-D2**: Operator wants more comprehensive dry run
- 8 tasks insufficient sample (Profile 2)
- Akcje: expand scope (more tasks, higher cost)

**EC-D3**: Dry run interrupted
- Crash mid-execution
- Akcje: resume, may regenerate partial

---

## 31.7. Acceptance + transition do fazy 32

```bash
$ aeis-cli phase31-acceptance-test --project proj_customer_y_crm

[1/8] Dry run executed                                 ✓ PASS
[2/8] Profile-specific scope validated                 ✓ PASS (Profile 2)
[3/8] All systems verified                             ✓ PASS
[4/8] Multi-worker coordination tested                 ✓ PASS (2 workers)
[5/8] Issues detected + corrected                      ✓ PASS (1 fixed)
[6/8] Confidence high (88%+)                           ✓ PASS
[7/8] Final go/no-go decision                          ✓ PASS (GO)
[8/8] Audit chain entry dry_run_complete               ✓ PASS

DoD: 8/8 ✓
Phase 31 ACCEPTED. Ready dla Phase 32 (Build Initialization).

═══ GROUP D (Planning) COMPLETE ═══
Ready dla Phase 32 (Build, Group E).
```

---

# Status faz 29-31

🟢 **Wszystkie 3 fazy complete**

**Zawiera**:
- ✓ Faza 29 — Test Plan Synthesis (test scenarios per AC, L1-L5 distribution, mandatory L5 human-like, **profile-aware test generation timing dodane**, 15 edge cases)
- ✓ Faza 30 — Pre-Flight Cost Preview (**profile-aware comprehensive breakdown**, alternative profiles cost-time matrix, P10/P50/P90 confidence intervals per profile, profile change cost projections, customer notification z Polish, 15 edge cases)
- ✓ Faza 31 — Pre-Flight Dry Run (**profile-specific dry run scope**, multi-worker coordination testing, 16 edge cases — z 4 NEW profile-specific)

**Total edge cases w pliku**: 46 cases (15+15+16)

**Co rozwiązuje propagacja profile awareness z fazy 28.4**:
- ✓ Faza 29: profile-aware test generation timing (parallel scaling)
- ✓ Faza 30: comprehensive cost breakdown z profile multipliers, alternative profiles comparison
- ✓ Faza 31: profile-specific dry run scope (more workers = more validation needed)

**Grupa D (Planowanie) COMPLETE**: 6 faz (26-28 w part 1, 29-31 w part 2)
**Łącznie 31 z 41 faz frozen**

⏳ **Po Twojej akceptacji** → **soft freeze faz 29-31** + przejście do **Faza 32 — Build Initialization** (start grupy E "Wykonanie").

🎯 **Milestone**: Operator ma teraz **wszystko zaplanowane**:
- Księga (single source of truth)
- Masterplan z layer decomposition + parallel orchestration plan
- Test plan
- Skills + Models assignments
- Cost (verified per profile, customer reconciled)
- Resource profile selected (Profile 2 dla Customer Y)
- Dry run validated (88%+ confidence)

Brak surprise w grupie E.
