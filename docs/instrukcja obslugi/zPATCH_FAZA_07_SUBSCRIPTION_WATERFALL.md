# PATCH FAZA 07 — Subscription Waterfall (W11)

> **Source**: AEIS_W1_to_W19_kompletny_opis.md, sekcje W11 + W13
> **Target**: `07_cost_guard.md`
> **Severity**: CRITICAL
> **Apply**: Czytaj razem z phase 7 file

---

## Problem

Phase 7 Cost Guard zna tylko PAYG spending. **Brakuje 3-stage subscription waterfall** który jest fundamentem W11 Adapter Bus, oraz integracji z Subscription Advisor (W13).

## Add new section 7.X

W `07_cost_guard.md`, dodać po sekcji "Cost tracking" nową sekcję:

```
## 7.X. Subscription Waterfall — kluczowa logika kosztu (W11)

### 7.X.1. 3-stage waterfall

Każdy LLM call **MUSI** iść przez waterfall:

┌──────────────────────────────────────────────────────────────┐
│  STAGE 1 — Subscription tier (FREE within quota)             │
│   Anthropic Pro: $20/mo z $30/mo free quota                  │
│   OpenAI Plus: $20/mo z $20/mo free quota                     │
│   Anthropic Build: $0/mo (rate-limited free)                 │
│   Google AI Studio: $0/mo (rate-limited free)                │
│  ↓ EXHAUSTED gdy used >= quota_limit                          │
│                                                              │
│  STAGE 2 — PAYG (Pay-as-you-go, paid per token)              │
│   Anthropic: $0.003-$0.015 per 1k tokens                     │
│   OpenAI: $0.005-$0.020 per 1k tokens                        │
│   Cost Guard tracks against per-key hard cap                  │
│  ↓ APPROACHES gdy spent >= cap × 0.8                          │
│                                                              │
│  STAGE 3 — Hard cap (BLOCKS request)                         │
│   Per-key cap: $5 (test environment)                         │
│   Per-project cap: $200-500 (typical D4)                     │
│   Per-month cap: configurable                                │
│   No bypass without operator override (D3+ Evidence Pack)    │
└──────────────────────────────────────────────────────────────┘

### 7.X.2. Cost Guard state tracking

Cost Guard tracks 3 separate budgets per provider:

{
  "providers": {
    "anthropic": {
      "subscription_tier": {
        "tier_name": "Anthropic Pro",
        "monthly_cost": "$20.00",
        "monthly_quota_dollars": "$30.00",
        "consumed_this_period": "$12.40",
        "quota_remaining": "$17.60",
        "period_reset_date": "2026-06-01",
        "rate_limit_status": "high",
        "last_used": "2026-05-15T14:23:00Z"
      },
      "payg": {
        "spent_this_month": "$2.40",
        "hard_cap": "$5.00",
        "soft_alerts": [50, 80, 95],
        "remaining_budget": "$2.60",
        "anomaly_detected": false,
        "trending": "stable"
      },
      "decision_logic": {
        "next_call_uses": "subscription",
        "reason": "Pro tier has $17.60 remaining",
        "fallback_after_exhaustion": "switch_to_payg",
        "fallback_after_payg_cap": "queue_or_block_or_advisor"
      }
    },
    "openai": { ... },
    "bielik_lokalny": {
      "type": "local",
      "cost": "$0",
      "rate_limit": "GPU constrained"
    }
  }
}

### 7.X.3. Decision algorithm

For each LLM call request:

1. CHECK SUBSCRIPTION TIER
   if subscription.quota_remaining > estimated_cost:
     use subscription (free)
     deduct from quota_remaining
     log to subscription_usage_chain.jsonl
     return
   
2. CHECK PAYG BUDGET
   if payg.remaining_budget > estimated_cost:
     use payg
     deduct from remaining_budget
     check anomaly (statistical)
     if approaching cap (80%+):
       trigger Subscription Advisor (W13)
     log to cost_ledger.jsonl
     return
   
3. HARD CAP REACHED
   options:
     - queue request (wait dla period reset)
     - block (return error)
     - emit AdvisorCard (operator decision)
     - escalate to D3 (Evidence Pack required)
   
   Default per autonomy:
     Conservative: block + AdvisorCard
     Production: AdvisorCard + queue
     Aggressive: extend cap z reasoning
     Research: queue silently

### 7.X.4. Anomaly detection (statistical)

Cost Guard runs continuously:

  Statistical baseline (last 7 days):
    avg_daily_spend = mean(daily_spend[-7:])
    std_daily_spend = std(daily_spend[-7:])
  
  Anomaly thresholds:
    MILD: today_spend > avg + 1.5×std
    MODERATE: today_spend > avg + 2.5×std
    SEVERE: today_spend > avg + 3.5×std
  
  Actions:
    MILD: log + dashboard indicator
    MODERATE: notification + investigate
    SEVERE: pause workers + AdvisorCard hard gate
```

## Add new section 7.Y — Subscription Advisor integration (W13)

```
## 7.Y. Subscription Advisor (W13) integration

Cost Guard **NIE decyduje sam** o subscription tier — eskaluje do
Subscription Advisor.

### 7.Y.1. Trigger conditions

Subscription Advisor jest invoked gdy:

  1. SUSTAINED PAYG SPENDING
     PAYG > 80% cap dla 5+ dni z trending "sustained"
     Implication: predictable workload, subscription może być cheaper

  2. SUBSCRIPTION EXHAUSTED MID-PROJECT
     Subscription quota = 0 ale workload continues
     Implication: tier upgrade lub continue PAYG decision

  3. PROVIDER PRICING CHANGE
     Provider announces price change
     Implication: re-evaluate subscription vs PAYG ratio

  4. WORKLOAD PATTERN CHANGE
     3+ projects z similar provider use
     Implication: aggregate justifies subscription

### 7.Y.2. ROI Analysis (Advisor performs)

ROI = (PAYG_cost_30_day_forecast - subscription_monthly_cost) / subscription_monthly_cost

Inputs:
  - Last 30 days actual spend
  - Active projects forecast
  - Subscription tier benefits (quota + rate limits)
  - Operator preferences (z W13 Adaptive Preferences)

Output:
  ROI > 30%: STRONG recommend subscription
  ROI 10-30%: WEAK recommend (operator decides)
  ROI < 10%: STAY WITH PAYG
  ROI < -20%: SUBSCRIPTION NOT JUSTIFIED

### 7.Y.3. Hard gate emission

Gdy ROI > 30%, Subscription Advisor emit AdvisorCard:

{
  "type": "subscription_advisor",
  "decision_class": "D3",
  "hard_gate": true,
  "trigger": "PAYG approaching cap z sustainable trend",
  "rationale": {
    "30_day_history": [...],
    "forecast_next_30_days": "...",
    "subscription_tier_proposal": "Anthropic Pro",
    "monthly_savings": "$15-30",
    "roi_calculation": "..."
  },
  "options": [
    {"id": "upgrade", "action": "Subscribe to Pro tier"},
    {"id": "increase_payg", "action": "Increase PAYG cap z reasoning"},
    {"id": "switch_provider", "action": "Use cheaper alternative"},
    {"id": "defer", "action": "Continue PAYG monitoring"}
  ],
  "evidence_pack": "evidence_packs/subscription_advisor_2026_05_27.json",
  "rollback_plan": "Cancel subscription within 7-day grace period"
}

Operator MUST decide (hard gate). Decision logged w advisor_subscription_chain.jsonl
```

## Customer Y CRM przykład (Cost Guard live z subscription waterfall)

```
Customer Y CRM lifecycle Cost Guard activity:

Day 1-15 (Setup, faza 1-15):
  Subscription tier: Anthropic Build (free, $0/mo) — operator default
  Bielik lokalny: free
  PAYG used: $0
  
Day 16-25 (Council deliberation):
  Robert dodał Anthropic Pro ($20/mo) per Subscription Advisor recommendation
    (Funding Advisor flagged 3-month commitment justified)
  Subscription quota: $0 → $30 dostępne
  
  Council deliberation:
    8 invocations × ~$3.50 = $28 wartości
    Subscription quota consumed: $28/$30
  
Day 26-31 (Planning):
  Subscription quota: $2/$30 remaining
  Most planning calls: subscription (still has buffer)
  Last 2 calls: switch to PAYG (auto)
  PAYG spent: $0.85
  
Day 32 (Build start, Phase 1):
  Subscription quota: $0 (exhausted dla May)
  PAYG: $0.85 → consuming
  
Day 32-40 (Build phases 1-3):
  PAYG cumulative: $0.85 → $32 (rapid build phase consumption)
  
  Day 38: PAYG hit $20 / $200 cap (10%)
  Day 40: PAYG hit $32 / $200 cap (16%)
  
  No anomalies, anomaly detector: stable
  Subscription Advisor: NOT triggered (ROI nie justifies upgrade
    bo current Pro tier subscription is active for next month)
  
Day 41 (June 1, period reset):
  Subscription quota: $30 reset
  
Day 42-50 (Build phases 4-6):
  Mix: 40% subscription + 60% PAYG (subscription used first per call)
  PAYG approached $50 / $200 cap (25%)
  
Day 51-65 (Testing + Pre-deploy):
  June subscription consumed $25/$30
  PAYG: $90 / $200 (45%)
  
Day 66-78 (Deploy + Closure):
  July period started
  Subscription used: $30/$30 (full month)
  PAYG final: $142 / $200 (71%)
  
FINAL Customer Y CRM cost reconciliation:
  
  Subscription tier total (3 months × $20): $60
  Subscription quota consumed (free wartość): $90 
  PAYG total (after subscription exhaustion): $297
  
  ACTUAL OPERATOR SPEND: $60 + $297 = $357
  WARTOŚĆ Z SUBSCRIPTION: $90 free quota saved $90 PAYG
  
  Hipotetycznie PAYG-only: $387 (without subscription)
  Net savings z subscription: $30
```

## Audit chain entries

```json
[
  {
    "patch_id": "patch_phase_7_subscription_waterfall_v1",
    "applied_to": "07_cost_guard.md",
    "added_sections": ["7.X Subscription Waterfall", "7.Y Subscription Advisor"],
    "source_layers": ["W11 (Adapter Bus)", "W13 (Advisor Layer)"],
    "verified_against": "Customer Y CRM lifecycle",
    "signature": "ed25519:..."
  }
]
```

## Co operator rozumie po patchu

1. **Cost decisions NIE są monolityczne** — 3 stages (subscription → PAYG → cap)
2. **Subscription tier ma matematycznie znaczenie** — tracked osobno z period reset
3. **Subscription Advisor (W13) jest hard gate** — operator MUST decide gdy ROI > 30%
4. **Customer Y CRM cost** = $60 sub + $297 PAYG = $357 (NIE $358 PAYG-only)
5. **Per-key testowy budget** ($5 cap) ma sens dla testów ale NIE dla production projects (subscription needed)
