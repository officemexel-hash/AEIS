# 00 — PATCHES FAZ — Naprawy spójności z architekturą W1-W19

> **Status**: 🟢 Active draft (uzupełnienie 41-fazowego manuala)
> **Cel**: explicit patche do fazy 5, 7, 20-25 + Customer Y CRM recalculation
> **Pozycja**: Czytaj **PO** `00_ARCHITEKTURA_W1_W19.md` i `00_ADVISOR_LAYER.md`
>
> **Kontekst**: Po porównaniu 41-fazowego manuala z faktyczną architekturą
> AEIS (W1-W19), zidentyfikowano **5 konkretnych niezgodności** które
> wymagają naprawy w istniejących plikach. Ten dokument je dokumentuje.

---

# Lista niezgodności do naprawy

| # | Faza | Plik | Problem | Severity |
|---|---|---|---|---|
| 1 | 5 | `05_autonomy_configuration.md` | D-ladder ma D1-D5, powinno D0-D5 | HIGH |
| 2 | 7 | `07_cost_guard.md` | Brak Subscription waterfall (W11) | CRITICAL |
| 3 | 20-25 | `20_25_council_to_ksiega.md` | Council 12 ról zamiast 9, brak 5 rang, brak critic signature | CRITICAL |
| 4 | 30 | `29_31_planning_part2.md` | Pre-Flight Cost nie używa Subscription Advisor (W13) | HIGH |
| 5 | Customer Y CRM | wszystkie | Cost calculation $358.50 zakłada 100% PAYG | CRITICAL |

---

# PATCH #1 — Faza 5 — D-ladder D0-D5

## Problem

Oryginalny manual (faza 5) używa D-ladder z 5 klas D1-D5. Realny AEIS (W4) ma **6 klas D0-D5** z **D0 Informational**.

## Fix

W pliku `05_autonomy_configuration.md`, zastąpić sekcję "D-level definitions":

**OLD (incorrect)**:
```
D1 Trivial — quick decisions
D2 Light — moderate review
D3 Standard — Council 4/4
D4 Critical — Council + Human
D5 Mission-critical — full process
```

**NEW (correct, z W4)**:
```
D-ladder — 6 klas decyzji (D0-D5):

| Klasa | Nazwa | Gate | Human | Rollback | Efficiency |
|---|---|---|---|---|---|
| D0 | Informational | auto | nie | — | — |
| D1 | Trivial | 1 agent | nie | — | — |
| D2 | Standard | 2 agents + Review | nie | opcjonalny | opcjonalny |
| D3 | Significant | Full Board Council 4/4 | opcjonalny | WYMAGANY | WYMAGANY |
| D4 | Critical | Council 4/4 + Human | tak + Code Optimizer veto | WYMAGANY + LPW | WYMAGANY + benchmark |
| D5 | Greenfield/Systemic | Council 4/4 + Human + External Review | tak + zewnętrzny | WYMAGANY + LPW + CFT pass | WYMAGANY + perf/cost sign-off |

Reguły eskalacji U1-U6:
- U1 cost magnitude: >$100/$1k/$10k → +1/+2/+3 D-level
- U2 blast radius: multi-project / prod → +1
- U3 reversibility: rollback >1d → +1, data loss → min D4
- U4 hard preferences: blocked_providers/cost_ceilings → min D3
- U5 autonomy: autonomy_level=manual → wszystko ≥D3
- U6 max: cap na D5
```

## Wpływ

- D0 dodane jako "informational auto" — system loguje ale nie pyta operatora
- Przykłady D0: "Selecting cheapest model dla L1 unit test gen", "Auto-rotation of audit chain", "Skill version bump z patch release"
- Reguły U1-U6 explicit (nie były w oryginalnym manualu)
- **Customer Y CRM (D4) classification potwierdzona** — payment flow + customer-facing + production

## Audit chain entry

```json
{
  "patch_id": "patch_phase_5_d0_d5",
  "applied_to": "05_autonomy_configuration.md",
  "section": "D-level definitions",
  "old_value": "D1-D5 (5 classes)",
  "new_value": "D0-D5 (6 classes) + U1-U6 rules",
  "source": "AEIS_W1_to_W19_kompletny_opis.md W4",
  "signature": "ed25519:..."
}
```

---

# PATCH #2 — Faza 7 — Subscription waterfall (CRITICAL)

## Problem

Oryginalna faza 7 Cost Guard zna tylko PAYG spending. Nie uwzględnia **Subscription tier waterfall** który jest fundamentalny dla W11 Adapter Bus.

## Fix

W pliku `07_cost_guard.md`, dodać nową sekcję 7.X "Subscription Waterfall (W11)":

```
## 7.X. Subscription Waterfall — kluczowa logika kosztu (W11)

### Decision priority

Każdy LLM call idzie przez 3-stage waterfall:

┌──────────────────────────────────────────────────────────────┐
│  STAGE 1 — Subscription tier (FREE within quota)             │
│   Anthropic Pro: $20/mo z $30 free quota                     │
│   OpenAI Plus: $20/mo z $20 free quota                        │
│   Etc.                                                        │
│  ↓ exhausted gdy quota_used >= quota_limit                    │
│                                                              │
│  STAGE 2 — PAYG (paid per-token)                             │
│   $0.003-$0.015 per 1k tokens dla Anthropic                  │
│   $0.005-$0.020 per 1k tokens dla OpenAI                     │
│  ↓ approaches gdy spent >= cap × 0.8                          │
│                                                              │
│  STAGE 3 — Hard cap (blocks request)                         │
│   $5 per test environment (Robert's testing setup)           │
│   $200 per project (typical D4)                              │
│   Custom per operator preferences                             │
└──────────────────────────────────────────────────────────────┘

### Cost Guard tracking (per provider)

{
  "subscription_tier": {
    "anthropic_pro": {
      "monthly_cost": "$20",
      "monthly_quota_dollars": "$30",
      "consumed_this_period": "$12.40",
      "remaining": "$17.60",
      "reset_date": "2026-06-01",
      "rate_limit_remaining": "high"
    }
  },
  "payg": {
    "anthropic": {
      "spent_this_month": "$2.40",
      "hard_cap": "$5.00",
      "soft_alerts": [50%, 80%, 95%],
      "remaining_budget": "$2.60",
      "anomaly_detected": false
    }
  },
  "decision_logic": {
    "next_call": "use_subscription",
    "reason": "Pro tier has $17.60 remaining quota",
    "fallback_if_exhausted": "switch_to_payg",
    "fallback_if_capped": "queue_or_block"
  }
}

### Subscription Advisor (W13) integration

Cost Guard **NIE decyduje sam** o switching tier — eskaluje do
Subscription Advisor (W13) gdy:
- PAYG spending > 80% cap dla 5+ days (sustainable)
- Subscription tier exhausted ale workload continues
- Predictable workload pattern detected (3+ similar projects)

Subscription Advisor emit AdvisorCard z:
- ROI analysis (savings vs subscription cost)
- 30-day spending history
- Workload forecast
- Hard gate: operator MUST decide
```

## Customer Y CRM przykład Cost Guard live

```
Phase 4 (Payment Integration), Day 12:

Cost Guard live state:
  
  Anthropic Pro subscription:
    quota_remaining: $4.20 / $30 (86% consumed)
    estimated_exhaustion: 2 dni przy current rate
  
  Anthropic PAYG:
    spent: $0 (subscription tier still active)
    hard_cap: $5.00
    
  Decision dla next call:
    → use_subscription (still has quota)
    → after exhaustion: switch to PAYG
    → if PAYG approaches 80%: trigger Subscription Advisor
  
  Anomaly check:
    Average daily spend last 7 days: $0.85
    Today's spend so far: $1.20 (1.4x average)
    Anomaly: ⚠ MILD (within tolerance)
    Action: log, monitor, no alert yet

Day 14 (Phase 5, Subscription exhausted):
  
  Subscription quota: $0 / $30 (100% consumed)
  Switch to PAYG: automatic
  PAYG spent: $0 → $0.85 first day on PAYG
  Subscription Advisor: monitoring trend
  
Day 18 (Phase 5, sustained PAYG spending):
  PAYG spent: $4.10 / $5.00 (82%)
  Subscription Advisor TRIGGERED:
    Pattern: sustainable $0.85/day
    Forecast: PAYG cap exhausted in 1.5 days
    
    Options dla operator:
    [1. Upgrade Pro tier ($20 buys $30 quota — saves $10/mo)]
    [2. Increase PAYG cap z reasoning]
    [3. Defer (continue current pattern, will block)]
```

---

# PATCH #3 — Fazy 20-25 — Council Hybrid (CRITICAL)

## Problem

Oryginalne fazy 20-25 mają Council z **12 rolami** (Planner, Critic, Security, Legal, Finance, Governance, QA, Red Team, Council Chair, Compliance, UX, Risk Assessor + i18n Specialist + ...). Realny AEIS (W3) ma **9 ról × 5 rang × 4 fazy + mandatory critic signature**.

## Fix

W pliku `20_25_council_to_ksiega.md`, naprawić Council architecture:

### 3.1. 9 ról (kanoniczne, NIE 12)

**OLD (incorrect, 12 ról)**:
```
1. Planner
2. Critic
3. Security
4. Legal
5. Finance
6. Governance
7. QA
8. Red Team
9. Council Chair
10. Compliance Specialist
11. UX Designer
12. Risk Assessor
```

**NEW (correct, 9 ról kanoniczne z W3)**:
```
1. Planner — proponuje rozwiązanie
2. Critic — kwestionuje propozycje (mandatory signature D3+)
3. Security — wykrywa luki bezpieczeństwa
4. Legal — compliance, zgodność z prawem
5. Finance — koszt, ROI, budget
6. Governance — proces, lifecycle, audit
7. QA — testowalność, edge cases
8. Red Team — adversarial perspective
9. Council Chair — moderator, agregator
```

**Co z 3 dodatkowymi rolami z oryginału?**

Compliance Specialist, UX Designer, Risk Assessor **mogą być invited as
specialists** dla konkretnych decyzji, ale **nie są stałymi członkami Council**.

Per W3, są **5 rang** (waga × rola), więc role mogą być invited z:
- `primary` (waga 1.0) — gdy konkretna ekspertyza jest core
- `support` (waga 0.7) — gdy rola wspiera
- `observer` (waga 0.4) — gdy rola obserwuje, zaleca

Przykład Customer Y CRM:
- 9 stałych ról Council (full board)
- + Polish Tax Specialist invited as primary (KSeF compliance critical)
- + UX Designer invited as support (customer-facing)
- + Compliance invited as observer (GDPR/PCI baseline)

### 3.2. 5 rang per rola

Każda rola ma rangę z wagą głosu:

| Rang | Waga | Cel | Kiedy używana |
|---|---|---|---|
| `primary` | 1.0 | główna decyzja | core ekspertyza dla decyzji |
| `support` | 0.7 | wsparcie głosu | secondary expertise |
| `observer` | 0.4 | obserwuje, zaleca | baseline awareness |
| `cost_sentinel` | 0.35 | może zablokować na cost | przy każdym Council |
| `security_sentinel` | 0.35 | może zablokować na security | przy każdym Council |

**Sentinele** są specjalnym typem — niski waga głosu **ale veto power**. Mogą zablokować Council decision niezależnie od wyniku głosowania.

### 3.3. 4 fazy deliberacji (kanoniczne)

**OLD (mój manual miał 5 faz: convene → verdicts → discussion → consolidation → book generation)**

**NEW (correct, 4 fazy z W3)**:

```
Phase 1 — Parallel verdicts (independent, no anchoring)
  Wszystkie role głosują niezależnie.
  9 verdykty + opcjonalnie sentinel verdykty.
  
Phase 2 — Discussion (1-2 rundy)
  Verdicts ujawnione.
  Role mogą argumentować, zmieniać verdyk.
  Rounds aż consensus lub diminishing returns.
  
Phase 3 — Consolidated vote
  Final weighted voting:
    Sum(role_verdict × role_weight) per option
    Highest sum wins, sentinele mogą veto
  
Phase 4 — Critic signature (MANDATORY D3+)
  Critic role MUSI podpisać final decision.
  Bez podpisu Critic — decision invalidated.
  Critic signature = "I have considered this z adversarial perspective
                     and find rationale acceptable, despite concerns X, Y, Z"
```

**Customer Y CRM example** (re-done z patch):

```
Faza 22 — Deliberation Rounds (Phase 2 W3):

  Question: Q15 "MVP scope vs comprehensive — co priorytet?"
  
  Round 1 verdicts (Phase 1, parallel):
    Planner (primary, 1.0): comprehensive (rationale: differentiation)
    Critic (primary, 1.0): MVP (challenge: scope creep risk)
    Security (support, 0.7): MVP (less attack surface)
    Legal (observer, 0.4): MVP (less compliance complexity)
    Finance (primary, 1.0): MVP (budget tight)
    Governance (support, 0.7): comprehensive (audit easier)
    QA (primary, 1.0): MVP (testability)
    Red Team (support, 0.7): MVP (threat surface)
    Council Chair (observer, 0.4): comprehensive (synthesis)
    + cost_sentinel: support MVP (no veto)
    + security_sentinel: support MVP (no veto)
    + Polish Tax Specialist invited (primary, 1.0): MVP (KSeF first)
  
  Weighted sum:
    MVP: 1.0+0.7+0.4+1.0+1.0+0.7+0.35+0.35+1.0 = 6.5
    Comprehensive: 1.0+0.7+0.4 = 2.1
    
  Round 2 (discussion):
    Planner argues: "differentiation matters"
    Critic counter: "MVP first, comprehensive Phase 2"
    Most stay z MVP.
    
  Phase 3 — Consolidated vote:
    MVP: 6.5 (vs comprehensive: 2.1) — MVP wins
    No sentinel veto
    
  Phase 4 — Critic signature:
    "I sign as Critic. MVP decision is sound. My remaining concern:
     ensure Phase 2 contract has clear scope."
    ✓ Signed (mandatory dla D4)
    
  Audit chain: council_wedge.jsonl entry
```

### 3.4. Audit chain rozdzielone

**OLD (incorrect, jeden chain "1247 entries")**:
- Wszystko w `audit/chain.jsonl`

**NEW (correct, 17 separate chains z W10)**:

Per Council deliberation, entry idzie do **specific chain**:
- `council_wedge.jsonl` — Council decisions (Phase 1-4)
- `adr_signoff.jsonl` — ADR sign-off (Critic signature step)
- Plus general chains (rbac_v2, workflow_engine, etc.)

---

# PATCH #4 — Faza 30 — Pre-Flight Cost z Subscription Advisor (W13)

## Problem

Faza 30 robi cost preview ale **nie używa Subscription Advisor** (W13). Powinna eskalować do hard gate gdy subscription tier upgrade jest justified.

## Fix

W pliku `29_31_planning_part2.md`, dodać do faza 30:

```
## 30.X. Subscription Advisor Integration (W13)

Po hierarchical breakdown z chosen profile, Subscription Advisor
analizuje workload forecast:

INPUT do Subscription Advisor:
  - Total project cost forecast (z chosen profile)
  - Per-provider spending forecast
  - Subscription tiers status (z W11 Adapter Bus)
  - Operator history (similar projects, monthly aggregate)
  - Cost ceiling preferences (z W13 Adaptive Preferences)

ANALYSIS:
  Per provider, evaluate:
    PAYG forecast vs subscription monthly cost
    Free quota wykorzystanie (subscription benefit)
    ROI = (PAYG_total - subscription_total) / subscription_total
    Confidence (z W13 advisor_history)

OUTPUT (gdy ROI > threshold):
  AdvisorCard z hard gate decyzją:
    [1. Upgrade subscription tier]
    [2. Continue PAYG z monitoring]
    [3. Mixed strategy (subscription dla high-quota providers)]

Customer Y CRM example:

  Faza 30 ($358 total forecast Profile 2):
  
  Subscription Advisor analyzes:
    Anthropic spending forecast: $190 dla projektu (53%)
    Anthropic Pro tier: $20/mo × 3 mo = $60 + $30/mo free quota = $90
    PAYG without subscription: $190
    PAYG z subscription: $190 - $90 = $100
    Total: $60 subscription + $100 PAYG = $160 (saves $30)
  
  ROI: ($190 - $160) / $60 = 50%
  Confidence: 0.91
  
  Hard gate emit:
    [● Upgrade Anthropic Pro] (saves $30, predictable cost)
    [○ Continue PAYG] (more variable, no upfront)
    
  Operator decision: upgrade ✓
```

---

# PATCH #5 — Customer Y CRM cost recalculation (CRITICAL)

## Problem

Wszystkie pliki manuala referencujące Customer Y CRM mają cost $358.50 zakładając **100% PAYG**. To jest **niepoprawne** — z subscription waterfall, faktyczne paid spending jest niższe.

## Fix

Ujednolicić wszystkie referencje Customer Y CRM cost:

### Old (incorrect): $358.50 PAYG only

### New (correct, z W11 subscription waterfall):

```
Customer Y CRM — Cost reconciliation (full):

Subscription tier (W11):
  Anthropic Pro: $20/mo × 3 mo = $60
    Z $30/mo free quota × 3 = $90 wartości free
  
PAYG spending (after subscription quota consumed):
  Phase 1-15: ~$0 (Bielik lokalne free, minimal cloud LLM)
  Phase 16-25: ~$26 (Council deliberation z subscription quota largely)
  Phase 26-31: ~$2 (planning, mostly subscription)
  Phase 32-36: ~$142 (build, subscription exhausted, all PAYG)
  Phase 37-41: ~$127 (testing + deploy + closure)
  
TOTAL paid:
  Subscription: $60 (predictable monthly)
  PAYG: ~$297
  
TOTAL all-in: ~$357

CUSTOMER PERSPECTIVE:
  Customer Y paid: €450 (within €500 cap)
  Operator gross: $450 (~€) - $357 (cost) = $93 profit
  
PER-KEY ANALYSIS (dla Robert's testing setup):
  Każdy of 9 testowy keys ma $5 cap
  Customer Y CRM total: $357
  
  Per provider:
    Anthropic: ~$190 = przekracza $5 cap × 38 keys
    OpenAI fallback: ~$5
    Bielik lokalny: $0
    Inne: $5-15
  
  WNIOSEK: Customer Y CRM jako proof-of-concept WYMAGA:
    - Subscription tier (Anthropic Pro $20/mo)
    - Lub większe per-key caps
    - Lub mniejsza scope (smaller D-level, mniej phases)
```

### Pliki do update

Następujące pliki wymagają update Customer Y CRM cost reference:

1. `26_28_planning_part1.md` — sekcja "Cost reconciliation" w fazie 28
2. `29_31_planning_part2.md` — pre-flight cost preview tabele
3. `34_36_execution_part2.md` — build completion cost summary
4. `37_39_testing_predeploy.md` — test phase cost ($45.60)
5. `40_41_deploy_closure.md` — final operator + customer reports
6. `PODSUMOWANIE_KOMPLETNE.md` — final stats

---

# CZĘŚĆ VI — Plan testowy 9 throwaway keys — naprawiony

## Original (incorrect) plan

- 9 keys × $50-100 = $450-900 budget
- Wszystko jako PAYG

## Corrected plan

```
Test environment plan (correct):

PER-PROVIDER CONFIGURATION:
  
  9 modeli total, dystrybucja:
    1. Anthropic claude-opus (premium)
    2. Anthropic claude-sonnet (balanced)
    3. Anthropic claude-haiku (cheap)
    4. OpenAI GPT-5 (alternative reasoning)
    5. OpenAI GPT-4o (alternative balanced)
    6. Google Gemini 2.5 Pro (long-context)
    7. Mistral Large (alternative)
    8. Bielik 11B (lokalny, $0)
    9. OpenRouter fallback (varied)
  
  Per-key budget:
    $5 cap per key (hard limit)
    10 testów planowanych = $0.50 per test budget
    
  TOTAL TEST BUDGET: $45 (8 paid + 1 free Bielik)

SUBSCRIPTION CONSIDERATION:
  
  Anthropic Pro tier ($20/mo z $30 quota):
    NIE potrzebne dla testów ($5 cap is below subscription benefit)
    Use PAYG dla controlled blast radius
    
  OpenAI Plus tier ($20/mo z $20 quota):
    Same — use PAYG dla testowy budget control

TEST SCENARIO MAPPING:
  
  Test 1-2: Faza 1-15 (operator setup) — minimal LLM use
    Estimated cost: $1 across all 9 keys
    Subscription not needed
  
  Test 3-5: Faza 16-25 (Council deliberation light)
    Estimated cost: $5-10 across all 9 keys
    Heaviest: Anthropic claude-opus (~$3)
    Within per-key caps
  
  Test 6-8: Faza 26-36 (planning + build, scope cut)
    Estimated cost: $10-15 across all 9 keys
    Within per-key caps
  
  Test 9-10: Faza 37-41 (testing + deploy)
    Estimated cost: $5-8 across all 9 keys
    Final reconciliation

TOTAL ACROSS 10 TESTS: $25-35 (well within $45 budget)

PER-KEY USAGE (final):
  Anthropic claude-opus: ~$5 (max key usage)
  Anthropic claude-sonnet: ~$3
  Anthropic claude-haiku: ~$1
  OpenAI GPT-5: ~$3
  OpenAI GPT-4o: ~$2
  Google Gemini: ~$3
  Mistral Large: ~$2
  Bielik 11B: $0 (lokalny)
  OpenRouter: ~$2
  
  TOTAL: ~$21 dla all 10 test runs
  HEADROOM: $24 dla unexpected scenarios

POST-TEST CLEANUP:
  All 9 keys deleted
  Audit chain entries preserved
  Calibration data extracted dla future operator setups
  No persistent cost exposure
```

## Subscription Advisor implications dla test plan

```
Subscription Advisor (W13) NIE eskaluje dla test plan:
  - Per-key cap $5 << subscription tier $20/mo
  - Throwaway keys = no monthly recurring justification
  - ROI dla test: PAYG simpler, lower commitment
  
Advisor decision: continue PAYG dla testing

ALE: real production projects (Customer Y CRM type) wymagają
subscription tier — zostało to zaznaczone w PATCH #5.
```

---

# CZĘŚĆ VII — Lista zaktualizowanych plików (post-patches)

| Plik | Status | Zmiany |
|---|---|---|
| `00_ARCHITEKTURA_W1_W19.md` | ✅ NEW | Fundament W1-W19 |
| `00_ADVISOR_LAYER.md` | ✅ NEW | W13 deep dive |
| `00_PATCHES_FAZ.md` | ✅ NEW (this) | Patches dla 5 niezgodności |
| `05_autonomy_configuration.md` | ⏳ TO PATCH | D-ladder D0-D5 + U1-U6 |
| `07_cost_guard.md` | ⏳ TO PATCH | Subscription waterfall |
| `20_25_council_to_ksiega.md` | ⏳ TO PATCH | 9 ról × 5 rang × 4 fazy + critic signature |
| `29_31_planning_part2.md` | ⏳ TO PATCH | Subscription Advisor integration |
| Customer Y CRM references | ⏳ TO UPDATE | $60 sub + $297 PAYG = $357 |

**Recommendation**: zostawić istniejące pliki phase as-is (już są frozen),
ale dodać 3 nowe foundational documents:
1. `00_ARCHITEKTURA_W1_W19.md` (created)
2. `00_ADVISOR_LAYER.md` (created)
3. `00_PATCHES_FAZ.md` (this file)

Operator czytając manual:
1. Najpierw 3 foundational docs (architecture + Advisor + patches)
2. Potem 17 phase files z świadomością niezgodności

To jest **Opcja C — Hybrid** którą wybrałeś.

---

# CZĘŚĆ VIII — Co dalej

Po przeczytaniu wszystkich 3 foundational documents:

1. ✅ Architektura W1-W19 zrozumiana (`00_ARCHITEKTURA_W1_W19.md`)
2. ✅ Advisor Layer zrozumiany (`00_ADVISOR_LAYER.md`)
3. ✅ Patches znane (`00_PATCHES_FAZ.md`)

**Operator wraca do** 41 faz manuala z świadomością:
- Każda faza działa na konkretnych warstwach (mapowanie w 00_ARCHITEKTURA_W1_W19)
- Każda faza ma Advisor hooks (w 00_ADVISOR_LAYER)
- Niezgodności są znane (w 00_PATCHES_FAZ)

**Manual jest teraz konsystentny** z realnym AEIS architecture.

🎯 **Total deliverables**:
- 17 phase files (oryginalne 41-fazowe manual)
- 3 foundational documents (architecture + Advisor + patches)
- 1 podsumowanie + 1 plik symulacji testowych
- = **22 plików**, ~1.85 MB total

---

# Załącznik — Update memory edits

```
Suggested memory updates:

1. AEIS architecture: 19 warstw W1-W19 (3 grupy: Foundation W1-W7, 
   Governance W8-W14, Lifecycle W15-W19)
2. Advisor Layer (W13) is core — 4 filary, 16 lifecycle hooks, 
   5 Specialized Advisors (Subscription/Scaling/Funding/RoleResolver/Variants)
3. Council Hybrid: 9 ról (NIE 12) × 5 rang (primary 1.0/support 0.7/
   observer 0.4/cost_sentinel 0.35/security_sentinel 0.35) × 4 fazy 
   (parallel verdicts/discussion/consolidated/critic signature mandatory D3+)
4. D-ladder D0-D5 (NIE D1-D5), z U1-U6 escalation rules
5. Subscription waterfall (W11): subscription → PAYG → cap, NIE jednolite PAYG
6. Customer Y CRM correct cost: ~$60 subscription + ~$297 PAYG = ~$357 
   (NIE $358 PAYG-only)
```
