# FAZA 7 — Cost Guard

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (7 z 11) — Guards Setup (2 z 5)
> **Typ**: jednorazowa konfiguracja, ciągłe działanie w tle
> **Czas wykonania**: 5-15 min (akceptacja defaults z faz 3-5) / 30-60 min (full anomaly tuning)
> **D-level**: D2 — Guard wpływa na all spending decisions
> **Zależności**: Faza 3 (cost dashboards 3-level), Faza 4 (budget templates + cost estimation), Faza 5 (DIM-3 autonomy), Faza 6 (aggregated Guards panel)
> **Następnik**: Faza 8 (Security Guard)
>
> **Spis sekcji**:
> - 7.1 — Sense fazy + relacja do faz 3-5
> - 7.2 — Scope (LLM + cloud + vendor pass-through)
> - 7.3 — Aggregation granularity (4 levels z toggle)
> - 7.4 — Time windows (project + period + real-time)
> - 7.5 — Anomaly detection (4-tier)
> - 7.6 — Detection mechanisms (rules + statistical + ML hybrid)
> - 7.7 — Baseline learning (multi-dim)
> - 7.8 — Auto-actions (all with autonomy control)
> - 7.9 — Predictive actions (adaptive per autonomy)
> - 7.10 — Hard stops vs soft stops (configurable)
> - 7.11 — Reporting (daily/weekly/monthly/closure/on-demand)
> - 7.12 — Real-time optimization recommendations
> - 7.13 — Edge cases (22) + inheritance + DoD

---

## 7.1. Sense fazy i relacja do faz 3-5

### 7.1.1. Co Cost Guard robi (i czego NIE robi)

Cost Guard NIE wymyśla cost monitoring od zera. Bazuje na infrastrukturze:

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Infrastructure stack                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Faza 3:  Cost dashboards 3-level (provider/env/resource)    │
│           Per-environment cost limits                         │
│           Cost forecasting                                    │
│                                                              │
│  Faza 4:  Budget templates (small/medium/large/enterprise)   │
│           Cost estimation z Księgi/masterplanu               │
│           Cost calibration history                            │
│                                                              │
│  Faza 5:  DIM-3 Cost Decisions L0-L5                          │
│           Hard gate "Cost spike" approval                     │
│           Multi-color inheritance map                         │
│                                                              │
│  Faza 6:  Aggregated Guards panel (gdzie Cost findings appear)│
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  Faza 7 (Cost Guard) ENFORCES + DODAJE:                       │
│   • Real-time per-minute monitoring                          │
│   • Anomaly detection (4-tier)                                │
│   • Predictive alerts (przed budget hit)                     │
│   • Auto-actions (model switch, throttle, pause)             │
│   • Cross-source aggregation (LLM + cloud + vendor)          │
│   • Optimization recommendations                              │
│   • Closure cost reports                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.1.2. Cost Guard vs Coherence Guard architecture

Identyczna **structural architecture** jak Coherence Guard (faza 6):
- Separate worker process
- Aggregated panel integration (faza 6.9)
- Per-Guard autonomy override capability
- 5 severity levels (INFO/WARNING/ERROR/CRITICAL/BLOCKER)

Różnica: scope (cost vs coherence) i detection mechanisms (statistical/ML
vs rules/LLM). Reszta wzorców jest identyczna — **operator nie uczy się
nowego UX**.

### 7.1.3. Wynik fazy 7 (DoD)

Po fazie 7 operator ma:
- ✓ Cost Guard scope skonfigurowany (LLM + cloud + vendor)
- ✓ Aggregation levels wybrane (per call/phase/role/project)
- ✓ Anomaly detection tier ustanowiony
- ✓ Auto-actions sconfigurowane per autonomy
- ✓ Optimization recommendations enabled
- ✓ Reporting cadence wybrane

---

## 7.2. Scope (P7.1=c — LLM + cloud + vendor pass-through)

### 7.2.1. Trzy kategorie cost sources

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Guard Tracking Scope                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ☑ LLM PROVIDERS (z fazy 2)                                  │
│      • Anthropic (Claude family)                             │
│      • OpenAI (GPT family)                                   │
│      • OpenRouter (multi-vendor)                             │
│      • Google (Gemini family)                                │
│      • Mistral                                               │
│      • Lokalne modele ($0, monitoring tylko utilization)     │
│                                                              │
│      Tracking: per-call cost + tokens in/out                 │
│      Source: API responses, model registry                   │
│      Real-time: yes                                          │
│                                                              │
│  ☑ CLOUD RESOURCES (z fazy 3)                                │
│      • AWS (EC2, S3, RDS, Lambda, etc.)                      │
│      • Hetzner Cloud                                         │
│      • DigitalOcean                                          │
│      • Linode, OVH, Scaleway, IONOS                          │
│      • Edge devices: $0 (monitoring tylko power/uptime)      │
│                                                              │
│      Tracking: per-resource hourly/daily cost                │
│      Source: Cloud Pricing APIs (z fazy 3.4.2 templates)     │
│      Real-time: yes (estimated, true cost via vendor billing)│
│                                                              │
│  ☑ VENDOR PASS-THROUGH (z fazy 4 EC-D5)                       │
│      Operator's project może używać external services:       │
│      • Stripe (payment processing fees)                      │
│      • ElevenLabs (TTS API)                                  │
│      • SendGrid / Twilio (email/SMS)                         │
│      • Cloudflare premium features                           │
│      • Custom APIs operator integruje                        │
│                                                              │
│      Tracking: tylko jeśli operator credentials provided     │
│      Source: vendor billing APIs (gdzie dostępne)            │
│      Real-time: opóźnienia (vendor-side billing aggregation) │
│                                                              │
│  ☐ OPERATOR TIME (opt-in, jeśli operator self-bills)         │
│      Tracking: time spent w AEIS UI per project              │
│      Hourly rate: configurable                               │
│      Cost: notional (operator's own time value)              │
│      Used dla: client billing, time tracking                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.2.2. Vendor pass-through configuration

```
Settings → Cost Guard → Vendor Pass-Through

  Track these vendor services:
  
  ☑ Stripe (payment fees)
     API key: configured ✓
     Fee structure: 1.4% + €0.25 per transaction (auto-detected)
     Refresh: daily
  
  ☑ ElevenLabs (TTS)
     API key: configured ✓
     Pricing: $0.18 per 1000 chars
     Refresh: per call
  
  ☐ SendGrid (email)
     [Configure]
  
  ☐ Twilio (SMS)
     [Configure]
  
  ☑ Cloudflare (CDN, premium features)
     Account: configured ✓
     Refresh: hourly
  
  Custom vendors:
   [+ Add custom vendor]
   
  Track unknown vendor calls:
   ☑ Detect API calls do non-tracked vendors
       Alert operator: "New external API detected, track?"
```

### 7.2.3. Cost source unification

Different sources have different timing:

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Source Timing                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Source           Real-time   Daily reconcile  Vendor truth  │
│  ──────────────  ──────────  ───────────────  ───────────── │
│  Anthropic       ✓ (per call) ✓               vendor billing │
│  OpenAI          ✓ (per call) ✓               vendor billing │
│  AWS estimated   ~minute      ✓               billing API    │
│  Hetzner         ~minute      ✓               billing API    │
│  Stripe          ~minute      ✓ (fees)        Dashboard      │
│  Vendor pass-thr varies        ✓ (delayed)    Vendor billing │
│                                                              │
│  Reconciliation strategy:                                    │
│   • Real-time: best estimate dla immediate decisions         │
│   • Daily: vendor billing data syncs (correction)            │
│   • Discrepancy alert: jeśli estimate != actual w 10%        │
│                                                              │
│  Operator dashboard shows:                                   │
│   • Live estimate (real-time, may differ z final)            │
│   • Yesterday confirmed (vendor truth)                       │
│   • Variance indicator (estimate accuracy)                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 7.3. Aggregation granularity (P7.2=d — wszystkie levels z toggle)

### 7.3.1. 4 levels granularity

Identyczny pattern jak cost dashboards z fazy 3.10 (operator zna UX):

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Guard — Aggregation Levels                             │
│  Toggle view: [● Provider] [○ Project] [○ Phase] [○ Role]    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  LEVEL 1 — Per source (provider/cloud/vendor)                │
│   Anthropic            $54.20 (61%)                          │
│   OpenAI               $18.50 (21%)                          │
│   Hetzner              €34.20 (37%)                          │
│   Stripe (fees)        €8.40                                 │
│   ...                                                        │
│                                                              │
│  LEVEL 2 — Per project                                       │
│   Sylion Tailor v3     $89.40 (43%)                          │
│   Customer Acme Pilot  $42.10 (20%)                          │
│   Internal Dashboard   $25.20 (12%)                          │
│   ...                                                        │
│                                                              │
│  LEVEL 3 — Per phase (within project)                        │
│   Sylion Tailor v3:                                          │
│     Council deliberation (faza 23)    $14.60 (16%)           │
│     Planning + masterplan             $14.40 (16%)           │
│     Build orchestration               $42.80 (48%)           │
│     Quality gates                     $8.20 (9%)             │
│     Deployment                        $9.40 (11%)            │
│                                                              │
│  LEVEL 4 — Per role (Council)                                │
│   Sylion Tailor v3 → Council:                                │
│     Council Chair (claude-opus)       $4.20                  │
│     Planner (claude-sonnet)           $3.80                  │
│     Critic (gpt-5)                    $3.10                  │
│     Security (claude-opus)            $1.50                  │
│     ...                                                      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.3.2. Cross-level pivot

Operator może combine levels (np. "show me OpenAI cost per project per
phase"):

```
┌──────────────────────────────────────────────────────────────┐
│  Cross-Level Pivot                                           │
│                                                              │
│  Rows: [Provider ▼]   Cols: [Phase ▼]   Filter: [Project ▼]  │
│                                                              │
│           Council  Planning  Build   Quality  Deploy  Total  │
│  ──────  ───────  ───────── ──────  ──────── ────── ────── │
│  Anthropic $5.20   $7.40     $32.10  $4.20    $5.30  $54.20 │
│  OpenAI    $4.10   $3.80     $7.20   $1.80    $1.60  $18.50 │
│  Hetzner   $0      $0        $25.40  $4.10    $4.70  €34.20 │
│  Stripe    $0      $0        $0      $0       $8.40  €8.40  │
│  ──────  ───────  ───────── ──────  ──────── ────── ────── │
│  Total    $9.30    $11.20    $64.70  $10.10   $19.90 $115.30│
│                                                              │
│  [Export CSV]  [Save as default view]                        │
└──────────────────────────────────────────────────────────────┘
```

### 7.3.3. Persistent vs ad-hoc views

```
Settings → Cost Guard → Default Views

  Saved views:
   • "Daily standup" — provider × today
   • "Project closure" — phase × per project
   • "Council costs" — role × per project (deep)
   • "Vendor costs" — vendor pass-through × monthly
  
  Default view dla each context:
   • Workspace overview:  [Daily standup ▼]
   • Project page:         [Phase × per project ▼]
   • Council page:         [Council costs ▼]
   • Closure report:       [Per phase + recommendations ▼]
  
  [+ Save current view as default]
```

---

## 7.4. Time windows (P7.3=c — project + period + real-time per-minute)

### 7.4.1. Three time scales

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Time Windows                                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  REAL-TIME (per-minute)                                      │
│   Use: monitoring active builds, spike detection             │
│   Refresh: every 30-60 sec                                    │
│   Example: "Cost ostatniej minuty: $0.42"                    │
│   UI: Live ticker w sidebar (gdy active project)             │
│                                                              │
│  PERIOD (hour/day/week/month)                                │
│   Use: trend analysis, budget planning                        │
│   Refresh: hourly aggregation                                 │
│   Example: "Spend ostatnich 24h: $14.50"                     │
│   UI: Charts on dashboards                                   │
│                                                              │
│  PROJECT LIFETIME                                            │
│   Use: total project cost, vs estimate accuracy              │
│   Refresh: per project event (build, deploy, etc.)           │
│   Example: "Total dla Sylion Tailor v3: $89.40"              │
│   UI: Project header + closure report                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.4.2. Real-time live ticker

```
┌────────────────────────────────────────────────┐
│  Live Cost Ticker — Sylion Tailor v3           │
│                                                │
│  Last minute:    $0.42                         │
│  Last 5 min:     $1.85                         │
│  Last hour:      $14.20                        │
│                                                │
│  Active spend rate: $14.20/h                   │
│  Project budget:    $250                       │
│  Spent so far:      $89.40 (36%)               │
│  Estimated finish:  in 11h (within budget)     │
│                                                │
│  ⚠ Spend rate up 18% w ostatnich 5 min        │
│     [Investigate]                              │
└────────────────────────────────────────────────┘
```

Ticker visible:
- W sidebar dashboard gdy active project running
- W mobile companion app (z fazy 4.5)
- Optional always-on overlay (per UI customization z fazy 4.7)

### 7.4.3. Period aggregation

```
┌──────────────────────────────────────────────────────────────┐
│  Monthly Cost Trends — Workspace                             │
│  Period: [This month] [Last 30 days] [Custom]                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  This month: $215 / $500 budget (43%)                        │
│                                                              │
│  Daily breakdown:                                            │
│  ▁▂▃▅▂▁▂▄▆▇▅▃▁▂▃▄▅▆▇█▆▅▄▃▂▁▁▂▃▄                            │
│  1                  10                  20         29        │
│                                                              │
│  Weekly summary:                                             │
│   Week 1: $42  (●●○○○ avg)                                   │
│   Week 2: $58  (●●●○○ above avg)                             │
│   Week 3: $79  (●●●●○ high)                                  │
│   Week 4: $36  (●●○○○ below avg, partial week)               │
│                                                              │
│  Comparison:                                                 │
│   Last month: $187 (+15%)                                    │
│   3-mo trend: ↗ slowly increasing                            │
│                                                              │
│  Per-day forecast:                                           │
│   Today: ~$8 (current rate)                                  │
│   Tomorrow: ~$12 (Sylion Tailor v3 build planned)            │
│   This week remaining: ~$45                                  │
│   Month-end projection: $295 (within budget)                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 7.5. Anomaly detection 4-tier (P7.4=d)

### 7.5.1. Four tiers of anomaly

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Guard — Anomaly Detection Tiers                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TIER 1 — Per-call spike                                     │
│   Detection: single call cost > threshold                    │
│   Threshold sources:                                         │
│    • Per-call hard cap (faza 5 hard gate)                    │
│    • Per-call soft cap (operator-defined)                    │
│    • Project-relative (>5% of project budget)                │
│   Speed: instant (during call)                                │
│   False positive rate: very low (deterministic)               │
│                                                              │
│  TIER 2 — Statistical anomaly                                │
│   Detection: spend deviation > N sigma vs baseline           │
│   Examples:                                                   │
│    • Hourly spend 3σ above normal pattern                    │
│    • Daily spend 2σ above operator's average                 │
│    • Per-project cost 2σ above similar projects              │
│   Speed: ~5-30 sec (after data collection)                    │
│   False positive rate: medium (calibrated by P7.6)           │
│                                                              │
│  TIER 3 — Pattern anomaly                                    │
│   Detection: unusual sequences/patterns                      │
│   Examples:                                                   │
│    • 10+ calls/sec sustained (potential runaway loop)        │
│    • Same prompt sent 100x w hour (cache miss?)              │
│    • Unusual model selection (gpt-5 dla simple task)         │
│    • Sudden vendor switch mid-build                          │
│   Speed: ~1-5 min (pattern aggregation)                       │
│   False positive rate: medium-high (requires tuning)          │
│                                                               │
│  TIER 4 — Predictive (looking ahead)                         │
│   Detection: trend extrapolation suggests problem             │
│   Examples:                                                   │
│    • Predicted budget exhaustion w 5h                        │
│    • Predicted month-end overrun (current rate)              │
│    • Predicted closure cost +50% vs estimate                 │
│   Speed: continuous (predictions updated w time)              │
│   False positive rate: variable (predictions may not happen)  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.5.2. Per-tier severity assignment

```
Tier 1 — Per-call spike:
  Single call > $5:    WARNING
  Single call > $10:   ERROR
  Single call > $50:   CRITICAL (likely bug or attack)
  Single call > $100:  BLOCKER (almost certainly wrong)

Tier 2 — Statistical:
  Hourly spike 2σ:     INFO
  Hourly spike 3σ:     WARNING
  Daily anomaly:       WARNING
  Weekly anomaly:      ERROR

Tier 3 — Pattern:
  Sustained high rate:  WARNING
  Unusual sequence:     ERROR (potential bug)
  Resource leak (cloud):CRITICAL

Tier 4 — Predictive:
  Project budget hit predicted: WARNING
  Workspace budget hit predicted: ERROR
  Closure cost +50% predicted: CRITICAL
```

---

## 7.6. Detection mechanisms (P7.5=d hybrid)

### 7.6.1. Three mechanism types

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Detection Mechanisms                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  RULE-BASED (Tier 1)                                         │
│   How: hard-coded thresholds, deterministic                  │
│   Cost: $0                                                   │
│   Examples:                                                   │
│    • Per-call cap                                             │
│    • Per-hour cap                                             │
│    • Per-day cap                                              │
│    • Per-project cap                                          │
│   Best for: simple thresholds, deterministic limits          │
│                                                              │
│  STATISTICAL (Tier 2)                                        │
│   How: moving averages, standard deviations, percentiles     │
│   Cost: $0 (lokalne computation)                             │
│   Examples:                                                   │
│    • 30-day moving average baseline                          │
│    • Z-score detection (>3σ)                                  │
│    • Percentile-based (>95th percentile)                      │
│    • Seasonal adjustment (weekday vs weekend)                │
│   Best for: numeric anomalies, baseline-relative              │
│                                                              │
│  ML-BASED (Tier 3-4)                                         │
│   How: trained model recognizes patterns                     │
│   Cost: $0 (after training, lokalne inference)                │
│   Examples:                                                   │
│    • Time-series forecasting (Prophet, ARIMA)                │
│    • Anomaly detection (isolation forest)                     │
│    • Pattern recognition (LSTM, transformer-light)            │
│   Best for: complex patterns, predictions                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.6.2. Mechanism selection per check

```
Settings → Cost Guard → Detection Mechanisms

  Per-check configuration:
  
  Check                              Tier   Mechanism
  ────────────────────────────────  ─────  ──────────
  Per-call spike                     T1     Rule-based
  Per-hour spike                     T1     Rule-based
  Per-day spike                      T1     Rule-based
  Hourly statistical anomaly         T2     Statistical
  Daily statistical anomaly          T2     Statistical
  Weekly trend anomaly               T2     Statistical
  Sustained high rate                T3     Pattern (rules)
  Resource leak detection            T3     Pattern (rules)
  Unusual model selection            T3     ML-based (if available)
  Budget exhaustion prediction       T4     ML-based
  Closure cost prediction            T4     ML-based
  Seasonal pattern detection         T4     ML-based
  
  ML availability:
   ☑ Train ML models on operator's data
   ☐ Use generic SYLION operator models (anonymized)
   ☐ Disable ML (rules + statistical only)
   
  Training data needed:
   • Minimum 5 completed projects dla projekt-level patterns
   • Minimum 30 days of activity dla daily patterns
   • Minimum 90 days dla seasonal patterns
   
  Current training status:
   ✓ Project-level patterns (47 projects)
   ✓ Daily patterns (>30 days)
   ⠋ Seasonal patterns (training, 78 days collected)
```

---

## 7.7. Baseline learning (P7.6=d multi-dim)

### 7.7.1. Multi-dimensional baselines

System uczy się baselines per multiple dimensions:

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Baselines — Multi-Dimensional                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Per workspace (operator-wide):                              │
│   Average daily spend:        $5.40 (last 90 days)           │
│   Average project cost:       $42 (n=47)                     │
│   Spend variance:             ±35% normal                    │
│                                                              │
│  Per operator (cross-workspace):                             │
│   N/A jeśli single workspace                                 │
│   Used dla multi-workspace operators                          │
│                                                              │
│  Per project type (z goals):                                 │
│   public_products:  avg $145 per project (n=12)              │
│   cybersecurity:    avg $89 per project (n=8)                │
│   research:         avg $32 per project (n=15)               │
│   apps_internal:    avg $22 per project (n=12)               │
│                                                               │
│  Per D-level:                                                │
│   D1: avg $12 (n=8)                                          │
│   D2: avg $24 (n=15)                                         │
│   D3: avg $58 (n=12)                                         │
│   D4: avg $142 (n=10)                                        │
│   D5: avg $387 (n=2)                                         │
│                                                              │
│  Per phase:                                                  │
│   Council:          avg $14 (16% of total)                   │
│   Planning:         avg $14 (16%)                            │
│   Build:            avg $42 (48%)                            │
│   Quality:          avg $8 (9%)                              │
│   Deployment:       avg $10 (11%)                            │
│                                                              │
│  Per Council role:                                           │
│   Council Chair:    avg $4.20                                │
│   Planner:          avg $3.80                                │
│   Critic:           avg $3.10                                │
│   ...                                                        │
│                                                              │
│  Per provider:                                               │
│   Anthropic:        avg 60% of total spend                   │
│   OpenAI:           avg 22%                                  │
│   Cloud:            avg 14%                                  │
│   Vendor:           avg 4%                                   │
│                                                              │
│  Seasonal:                                                   │
│   Weekday spend:    1.4x weekend                             │
│   Morning peak:     09:00-12:00                              │
│   Quiet hours:      22:00-06:00                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.7.2. Anomaly detection wykorzystuje baselines

```
Example anomaly check (Tier 2):
  
  Current event: project Sylion Tailor v3 hit $200 spend
  
  Baseline checks:
   • vs project type (public_products avg $145): +38% above ⚠
   • vs D-level (D4 avg $142): +41% above ⚠
   • vs operator's calibrated estimate ($180): +11% above (within
     normal variance ±35%)
   • vs daily spend trend: not unusual
  
  Verdict: WARNING (above project type and D-level averages)
  
  Operator notification:
  ⚠ "Sylion Tailor v3 spend ($200) is 38% above similar
      projects average. Build phase still in progress."
```

### 7.7.3. Baseline calibration

Baselines update automatycznie:

```
Settings → Cost Guard → Baseline Calibration

  Auto-update baselines:
   ☑ After each project closure (faza 41)
   ☑ Weekly recalculation (Sundays)
   ☐ Daily recalculation (more responsive, but noisy)
  
  Outlier handling:
   ☑ Exclude top/bottom 5% (trim outliers from baseline)
   ☐ Include all data points
  
  Manual baseline reset:
   [Reset all baselines (start fresh learning)]
   [Reset specific dimension]
   [Adjust manually (operator override)]
  
  Confidence intervals:
   ☑ Show baseline confidence (more data = tighter intervals)
   Example: "D4 avg $142 ±$28 (n=10, 80% confidence)"
```

---

## 7.8. Auto-actions (P7.7=e — all + autonomy control)

### 7.8.1. Five auto-action categories

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Guard Auto-Actions (5 categories)                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. NOTIFY                                                   │
│     Always available. Operator sees finding.                 │
│     No actual action taken.                                  │
│     Channels: in-app, mobile, email, Slack (per faza 4)      │
│                                                              │
│  2. MODEL SWITCH                                             │
│     Auto-switch do cheaper model w fallback chain            │
│     Trigger: budget approaching threshold                    │
│     Implementation: dynamic per next call                    │
│     Reversal: when budget headroom restored                  │
│                                                              │
│  3. THROTTLING                                               │
│     Slow down request rate                                   │
│     Trigger: sustained high spend rate                       │
│     Implementation: queue calls z rate limit                 │
│     Effect: longer wallclock time, ale not stop              │
│                                                              │
│  4. PAUSING                                                  │
│     Pause non-critical workloads                             │
│     Trigger: budget critically close                         │
│     What pauses: research projects, optional tests, etc.     │
│     What continues: critical production, security gates      │
│                                                              │
│  5. HARD STOP                                                │
│     Pipeline blocks, requires operator approval              │
│     Trigger: budget exceeded (lub critical anomaly)          │
│     What stops: everything except read-only operations        │
│     Resume: operator approves OR raises budget                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.8.2. Autonomy-driven action matrix

Per autonomy preset, które actions auto vs manual:

```
┌──────────────────────────────────────────────────────────────┐
│  Auto-Action Matrix per Autonomy Preset                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Action          Conserv  Balanced  Aggress  Production  Res │
│  ──────────────  ───────  ────────  ───────  ─────────── ─── │
│  Notify          ✓        ✓         ✓        ✓           ✓   │
│  Model switch    M        A 70%     A 50%    M           A   │
│  Throttling      M        A         A        A           A   │
│  Pause           M        M         A        M           A   │
│  Hard stop       M        M         M        M           M   │
│                                                              │
│  Legend:                                                     │
│   A = Auto (system działa)                                   │
│   A 70% = Auto powyżej 70% budget threshold                  │
│   M = Manual (operator approves)                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Per-action override**:

```
Settings → Cost Guard → Auto-Actions

  Inherited from Phase 5: Production preset
  
  Per-action customization:
   Model switch:    [Inherit (Manual) ▼]  [Override: Auto 70% ▼]
   Throttling:      [Inherit (Auto) ▼]
   Pausing:         [Inherit (Manual) ▼]
   Hard stop:       [Inherit (Manual) ▼]  ← cannot be auto (safety)
  
  Custom thresholds dla auto-actions:
   Model switch trigger:    [● 70% budget] [○ 50%] [○ 90%]
   Throttling trigger:      [● 80% budget]
   Pausing trigger:         [● 95% budget]
```

### 7.8.3. Model switching workflow

```
Scenario: Sylion Tailor v3 budget at 75% ($188 / $250)

Cost Guard decision (Production preset, override Auto 70%):
  → Trigger: 70% threshold reached
  → Action: model switch dla next non-critical roles
  
Specific switches:
  Council Chair:  claude-opus → claude-sonnet (saves ~70%)
  Planner:        claude-sonnet → claude-haiku (saves ~80%)
  Critic:         gpt-5 → unchanged (operator marked as critical)
  Quality:        claude-sonnet → bielik-11b (lokalne, $0)
  
Notification:
  ⚠ "Cost Guard auto-switched models dla budget protection.
      Estimated savings dla remaining build: $42.
      [View details] [Revert to original]"
  
Audit chain entry:
  cost_guard_action: "model_switch"
  trigger: "75% budget threshold"
  switches: [list above]
  expected_savings: $42
```

### 7.8.4. Throttling workflow

```
Scenario: sustained 80% budget spend rate

Cost Guard decision:
  → Trigger: spend rate suggests budget hit w <2h
  → Action: throttle non-critical calls
  
Throttling rules:
  Council deliberation:    no change (deliberation needs flow)
  Build orchestration:     max 1 call/sec (was burst-able)
  Test execution:          max 5 parallel (was 20)
  Background tasks:        deferred (run after critical)
  
Effect:
  Wall-clock time: +30-60% (slower)
  Cost: -20% (less burst)
  Throughput: maintained dla critical work
  
Operator visibility:
  Live ticker shows "🐌 Throttling active (cost protection)"
  Estimated finish time updated
```

---

## 7.9. Predictive actions (P7.8=d adaptive per autonomy)

### 7.9.1. Prediction types

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Predictions                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Project budget exhaustion:                                  │
│   "Current spend rate suggests budget hit in 5h"             │
│   Confidence: 78%                                            │
│   Based on: last 1h spend × estimated remaining time         │
│                                                              │
│  Workspace monthly budget:                                   │
│   "Month-end projection: $487 / $500 budget (97%)"           │
│   Confidence: 85%                                            │
│   Based on: current daily rate × days remaining              │
│                                                              │
│  Closure cost vs estimate:                                   │
│   "Project will likely close at $215 vs estimated $180 (+19%)│
│   Confidence: 72%                                            │
│   Based on: current phase + remaining work + historical       │
│                                                              │
│  Per-phase predictions:                                       │
│   "Build phase will cost ~$45 (estimated $35, +29%)"          │
│   Confidence: 80%                                            │
│   Based on: progress so far + historical phase patterns      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.9.2. Adaptive predictive actions per autonomy

```
┌──────────────────────────────────────────────────────────────┐
│  Predictive Action per Autonomy Preset                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Conservative:                                                │
│   Just notify operator                                       │
│   "Budget exhaustion predicted in 5h. Plan accordingly."     │
│   Operator decyduje action                                   │
│                                                              │
│  Balanced:                                                    │
│   Notify + suggest scope reduction                           │
│   "Predicted overrun. System suggests:                       │
│    • Skip dry-run (-$3.50)                                    │
│    • Reduce mid-build interventions (-$4.50)                 │
│    Total potential savings: $8                                │
│    [Apply suggestions]  [Operator decyduje per item]"         │
│                                                              │
│  Aggressive:                                                  │
│   Auto-switch defaults pre-emptively                          │
│   System silently optimizes:                                  │
│    • Switch to cheaper models for non-critical roles          │
│    • Reduce sample frequency (testing)                       │
│    • Defer optional reports                                  │
│   Notification: "Auto-optimized dla budget. Saved estimated $X"│
│                                                              │
│  Production:                                                  │
│   Conservative-style (just notify)                            │
│   Production projects need predictability — operator decyduje│
│                                                              │
│  Research:                                                    │
│   Aggressive-style (auto-optimize)                            │
│   Research velocity > polish                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.9.3. Predictive horizon

```
Settings → Cost Guard → Predictions

  Prediction horizons:
   ☑ 1-hour ahead (real-time monitoring)
   ☑ 4-hour ahead (project finish estimate)
   ☑ 24-hour ahead (daily budget check)
   ☑ 7-day ahead (weekly trend)
   ☑ 30-day ahead (monthly budget projection)
   ☐ 90-day ahead (quarterly planning)
  
  Confidence thresholds:
   Show predictions z confidence >= [70% ▼]
   Trigger actions z confidence >= [85% ▼]
   
   Lower threshold = more predictions but more false alarms
   Higher threshold = fewer predictions but more reliable
```

---

## 7.10. Hard stops vs soft stops (P7.9=d configurable)

### 7.10.1. Tiered stops architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Limit Tiers (per project)                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Budget: $250                                                │
│                                                              │
│  Tier 1 — INFO (50% = $125):                                 │
│   • Notification: in-app                                      │
│   • No action                                                │
│   • Operator awareness                                       │
│                                                              │
│  Tier 2 — WARNING (80% = $200):                              │
│   • Notification: in-app + email + mobile                    │
│   • Action: model switch enabled (per autonomy)              │
│   • Suggest scope reduction                                  │
│                                                              │
│  Tier 3 — SOFT STOP (95% = $237.50):                         │
│   • Notification: urgent (all channels)                       │
│   • Action: pause non-critical workloads                     │
│   • Critical operations continue (Council, hard gates)       │
│   • Operator can over-ride non-critical pause                 │
│                                                              │
│  Tier 4 — HARD STOP (100% = $250):                           │
│   • Notification: hard gate                                   │
│   • Action: ALL operations blocked                            │
│   • Operator must approve continue                            │
│   • Audit chain entry: budget_exceeded_hard_stop              │
│                                                              │
│  Tier 5 — KILL SWITCH (130% = $325):                         │
│   • Notification: emergency                                   │
│   • Action: workspace-wide pause (all projects)               │
│   • Suggests: investigate (likely bug or compromise)          │
│   • Wymaga master password do continue                        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.10.2. Per-project configuration

```
Project: Sylion Tailor v3 → Cost Limits

  Inherited from Phase 4 (LARGE template): $250
  
  Per-tier behavior:
   50% — INFO:        ☑ Notify
   80% — WARNING:     ☑ Notify  ☑ Auto model switch  ☑ Suggest cuts
   95% — SOFT STOP:   ☑ Pause non-critical  ☐ Operator can override
   100% — HARD STOP:  ☑ Block all  ☑ Require approval  ☑ Audit log
   130% — KILL SWITCH: ☑ Emergency stop  ☑ Master password required
  
  Per-tier overrides:
   ☐ Allow operator to skip 95% soft stop
       (some projects have firm deadlines, hard work continues)
   ☐ Allow team approval (jeśli Team Lead profile)
       (don't always wait for solo operator)
   
  Customer-specific:
   ☐ Send customer notification at hard stop
       (transparent: "Project paused due to budget cap")
```

### 7.10.3. Override workflow

```
Scenario: project hits 100% hard stop, operator wants continue

┌──────────────────────────────────────────────────────────────┐
│  ⚠  Hard Stop — Project Budget Exceeded                      │
│                                                              │
│  Project: Sylion Tailor v3                                   │
│  Spent: $251.40 / $250 budget (100.6%)                       │
│  Phase: Build (60% complete)                                 │
│  Estimated cost to complete: $48                             │
│  Total projected: $299                                       │
│                                                              │
│  Reasons to continue:                                        │
│   • Phase already 60% complete (sunk cost)                   │
│   • Customer deadline tomorrow                                │
│   • Ditching project costs more (re-do later)                │
│                                                              │
│  Reasons to pause:                                           │
│   • Investigate why over-budget                              │
│   • May indicate inefficient approach                        │
│   • Customer should approve cost overrun                     │
│                                                              │
│  Approval options:                                           │
│   [● Approve $50 increase ($300 new cap)]                    │
│       Continue with realistic buffer                         │
│   [○ Approve $100 increase ($350 new cap)]                   │
│       Generous buffer                                        │
│   [○ Approve unlimited (operator-managed)]                   │
│       Cost Guard tracks but doesn't enforce dla this project │
│   [○ Pause project (manual review)]                          │
│       Stop, investigate, decide later                        │
│                                                              │
│  Audit chain entry will record:                              │
│   action: budget_override                                    │
│   amount: increase $50 → $300                                │
│   reason: "Customer deadline, phase 60% complete"            │
│   approver: robert.k                                         │
│                                                              │
│  [Confirm $50 increase]  [Cancel]                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 7.11. Reporting (P7.10=d all + on-demand)

### 7.11.1. Standard reports

```
┌──────────────────────────────────────────────────────────────┐
│  Cost Guard Reports                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  DAILY SUMMARY                                               │
│   Schedule: every morning 09:00 (operator timezone)          │
│   Channel: email + in-app                                    │
│   Content:                                                    │
│    • Yesterday total spend                                    │
│    • Today's projection                                       │
│    • Active alerts                                            │
│    • Top 3 spend events                                       │
│   Length: 1-page summary                                      │
│                                                              │
│  WEEKLY REPORT                                               │
│   Schedule: Mondays 09:00                                    │
│   Channel: email                                             │
│   Content:                                                    │
│    • Last week total + comparison                             │
│    • Per-project breakdown                                    │
│    • Trend analysis (4-week)                                  │
│    • Anomalies detected                                       │
│    • Optimization opportunities                               │
│   Length: 2-3 pages                                          │
│                                                              │
│  MONTHLY REPORT                                              │
│   Schedule: 1st of month                                     │
│   Channel: email + downloadable PDF                          │
│   Content:                                                    │
│    • Month total + budget utilization                         │
│    • Per-provider/project/phase breakdown                     │
│    • Year-to-date trend                                       │
│    • Forecast next month                                      │
│    • Top savings opportunities                                │
│   Length: 5-8 pages                                          │
│                                                              │
│  PROJECT CLOSURE REPORT                                      │
│   Trigger: project transition do faza 41 (closure)            │
│   Channel: in-app + downloadable                             │
│   Content:                                                    │
│    • Total cost vs estimate                                   │
│    • Per-phase breakdown                                      │
│    • Cost drivers (top spends)                                │
│    • Savings vs baseline                                      │
│    • Calibration data added                                   │
│    • Recommendations dla future similar projects              │
│   Length: 3-5 pages                                          │
│                                                              │
│  ON-DEMAND REPORT                                            │
│   Trigger: operator manual                                    │
│   Customizable: time period, breakdown, filters              │
│   Format: PDF / CSV / JSON                                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.11.2. Daily summary example

```
┌──────────────────────────────────────────────────────────────┐
│  📊  Cost Daily Summary — 2026-04-29                         │
│                                                              │
│  Yesterday:                                                  │
│   Total spend: $14.20                                        │
│   vs avg: -8% (good)                                         │
│   Top spend: Sylion Tailor build ($9.40)                     │
│                                                              │
│  Today's projection:                                         │
│   $12-18 (based on planned activities)                       │
│   Active: Sylion Tailor (Faza 35 build), Customer Acme (23)  │
│                                                              │
│  Month progress:                                             │
│   Spent: $215 / $500 budget (43%)                            │
│   Days elapsed: 29 / 30 (97%)                                │
│   Status: ✓ Under budget                                     │
│                                                              │
│  Active alerts: 0 critical, 1 warning                        │
│   ⚠ Customer Acme Pilot 80% budget                           │
│                                                              │
│  Optimization opportunity:                                    │
│   💡 Switch Council Critic to claude-haiku saves $5/week     │
│   [Apply suggestion]                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 7.11.3. Project closure report

```
┌──────────────────────────────────────────────────────────────┐
│  📊  Project Closure Cost Report — Sylion Tailor v3          │
│                                                              │
│  Final cost: $215.40                                         │
│  Estimate (z fazy 4): $180                                   │
│  Variance: +19.7%                                            │
│                                                              │
│  Per-phase breakdown:                                        │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Phase             Estimate  Actual   Var              │ │
│  │  ─────────────── ─────────  ──────── ─────             │ │
│  │  Council         $14.60    $14.20   -3%                │ │
│  │  Planning        $14.40    $15.80   +10%               │ │
│  │  Build           $121.60   $145.30  +19%  ⚠            │ │
│  │  Quality         $28.80    $28.10   -2%                │ │
│  │  Deployment      $49.40    $42.40   -14%               │ │
│  │  Testing (HUI)   $27.00    $23.40   -13%               │ │
│  │  ───────────────────────────────────────              │ │
│  │  Total           $255.80   $269.20  +5%                │ │
│  │                                                       │ │
│  │  (Note: actual w table sums to $269 because vendor    │ │
│  │  pass-through is shown separately as $-53.80 savings  │ │
│  │  because we used cheaper alternatives mid-build)       │ │
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Variance analysis:                                          │
│   • Build phase 19% over: 5 mid-flight interventions vs 3   │
│     estimated. Operator could pre-plan more thoroughly.     │
│   • Deployment 14% under: lokalne routing saved cloud cost. │
│                                                              │
│  Cost drivers (top 5):                                       │
│   1. Claude Opus calls (Council Chair):  $42.10              │
│   2. Hetzner CX31 deploy environment:    $35.80              │
│   3. GPT-5 calls (Critic):               $24.50              │
│   4. Build worker iterations (R0+R3):    $18.20              │
│   5. Stripe fees (test transactions):    $8.40               │
│                                                              │
│  Calibration data added:                                     │
│   ✓ public_products D4 baseline updated                      │
│   ✓ Build phase variance pattern recorded                    │
│   ✓ Operator intervention factor: 1.4x (vs 1.0 estimated)   │
│                                                              │
│  Recommendations dla similar future projects:                │
│   • Use estimate $215 (calibrated) instead of $180           │
│   • Plan dla 5+ mid-build interventions w D4 projects        │
│   • Consider switching Critic do gpt-5-mini (saves ~30%)     │
│                                                              │
│  [Download PDF]  [Export raw data]  [Share with customer]    │
└──────────────────────────────────────────────────────────────┘
```

### 7.11.4. Report customization

```
Settings → Cost Guard → Reports

  Daily summary:
   ☑ Enabled
   Schedule: [09:00 operator timezone ▼]
   Channels: [☑ Email] [☑ In-app] [☐ Mobile push]
   Content level: [Standard ▼]
  
  Weekly report:
   ☑ Enabled
   Day: [Monday ▼]
   Time: [09:00 ▼]
   Channels: [☑ Email]
   Content: [Standard ▼]  [○ Detailed] [○ Custom]
  
  Monthly report:
   ☑ Enabled
   Format: [PDF ▼] [CSV available]
   Include: [☑ All projects] [☐ By customer] [☐ By type]
  
  Closure reports:
   ☑ Auto-generate dla każdy closed project
   ☑ Share opcja z customer (dla customer projects)
  
  On-demand reports:
   Available formats: PDF / CSV / JSON / interactive dashboard
   Saved templates: 4 templates available
  
  Notifications about reports:
   ☑ "Daily report sent" notification
   ☐ "Weekly report ready" notification (set if you forget)
```

---

## 7.12. Real-time optimization recommendations (P7.11=c)

### 7.12.1. Recommendation engine

System ciągle analizuje cost patterns i sugeruje optymalizacje **w trakcie
projektu** (nie tylko post-fact).

```
┌──────────────────────────────────────────────────────────────┐
│  💡  Cost Optimization Recommendations                       │
│  Updated: 30 sek temu                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ACTIVE PROJECT — Sylion Tailor v3                          │
│                                                              │
│  ┌─ HIGH IMPACT ────────────────────────────────────────┐    │
│  │  💡 Switch Council Critic do gpt-5-mini              │   │
│  │     Current: gpt-5 ($0.42 per call)                  │   │
│  │     Suggested: gpt-5-mini ($0.08 per call)           │   │
│  │     Quality impact: minimal (Critic role tolerates)  │   │
│  │     Savings: ~$8 dla remaining build                 │   │
│  │     Confidence: 90%                                  │   │
│  │     [Apply]  [Dismiss]                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ MEDIUM IMPACT ──────────────────────────────────────┐   │
│  │  💡 Skip dry-run dla phase 30                         │   │
│  │     Estimated value: $3.50 saved                     │   │
│  │     Risk: medium (skipping pre-flight checks)        │   │
│  │     Recommended: only if confident in masterplan     │   │
│  │     [Apply]  [Dismiss]                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌─ LOW IMPACT ─────────────────────────────────────────┐   │
│  │  💡 Use lokalny embeddings (nomic-embed-text)        │   │
│  │     Current: OpenAI text-embedding-3 ($0.02)         │   │
│  │     Suggested: nomic-embed-text lokalny ($0)         │   │
│  │     Quality impact: -5% (slightly less accurate)     │   │
│  │     Savings: ~$2 per project                         │   │
│  │     [Apply]  [Dismiss]                               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  WORKSPACE-WIDE (all projects)                               │
│                                                              │
│  ┌─ STRATEGIC ──────────────────────────────────────────┐    │
│  │  💡 Reserved instances for Hetzner production        │   │
│  │     Current monthly: €34/month (on-demand)           │   │
│  │     Annual prepay: €326 (save ~€82, 25%)             │   │
│  │     Caveat: 1-year commitment                        │   │
│  │     Recommended if: stable production usage          │   │
│  │     [Learn more]  [Apply]  [Dismiss]                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Total potential savings: $13.50 (this project) +€82 annual  │
│                                                              │
│  [Show all recommendations]  [Settings]                      │
└──────────────────────────────────────────────────────────────┘
```

### 7.12.2. Recommendation generation

```
Settings → Cost Guard → Recommendations Engine

  Recommendation triggers:
   ☑ During active project (real-time)
   ☑ Project completion (post-fact analysis)
   ☑ Weekly review (workspace-wide)
   ☑ Monthly strategic review
  
  Recommendation types:
   ☑ Model substitutions (cheaper alternatives)
   ☑ Phase optimizations (skip optional steps)
   ☑ Provider switches (cost-effective vendors)
   ☑ Reserved capacity (cloud RIs)
   ☑ Architecture suggestions (caching, CDN, etc.)
   ☑ Workflow optimizations (batch vs streaming)
   ☐ Aggressive cuts (operator-flagged as risky)
  
  Confidence threshold:
   Show recommendations z confidence >= [70% ▼]
   
  Notification:
   ☐ Show top recommendation w live ticker
   ☑ Daily digest of new recommendations
   ☑ Weekly summary of accepted vs ignored
  
  Learning:
   ☑ Track which recommendations operator applied
   ☑ Adjust suggestions based on operator's preferences
   ☑ Don't suggest twice if dismissed
```

### 7.12.3. Recommendation lifecycle

```
Per recommendation tracking:
  
  Created: 2026-04-29 14:32
  Type: Model substitution
  Status: PENDING (operator hasn't acted)
  
  If applied:
   ✓ Applied: 2026-04-29 14:45
   Actual savings (measured): $7.80 (vs estimated $8)
   Quality impact: none observed
   Audit chain: applied
  
  If dismissed:
   ✗ Dismissed: 2026-04-29 14:35
   Reason (optional): "Need maximum quality dla critical demo"
   Future: don't suggest again dla similar context
  
  If snoozed:
   ⏸ Snoozed: until project complete
   Re-evaluate: when project closes
  
  Recommendation library:
   • Operator dismissed recommendations: 47
   • Operator applied: 23
   • Currently pending: 8
   • Total saved (estimated): $187
   • Total saved (measured): $164
```

---

## 7.13. Edge Cases (P7.12=b — 22 cases)

22 cases w 5 kategoriach.

### Kategoria A — Detection issues (5 cases)

#### EC-A1: False positive — operator-intentional spike

**Trigger**: Operator manually triggered expensive call (using opus dla
critical decision). Cost Guard flags as anomaly.

```
ℹ Anomaly detected — operator action

  Event: Single call $4.20 (3.2σ above baseline)
  Context: Operator manually selected claude-opus dla complex
           legal review
  
  Operator response:
   [Mark as intentional]
       Suppress similar spikes z same context
   [Add to "operator-approved exceptions"]
       Cost Guard learns: "operator legal review = expected high"
   [Take notification, just confirming]
       No suppression
```

#### EC-A2: Baseline contamination

**Trigger**: Operator's first 5 projects were all small ($20). Then big
$200 project. Statistical baseline ($20 ±$3) flags $200 as 60σ anomaly.

```
ℹ Baseline calibration issue

  Project: Customer Acme Pilot ($200)
  Baseline: $20 ±$3 (z 5 small projects)
  Z-score: 60σ (extreme!)
  
  Issue: baseline not yet representative (only 5 data points)
  
  Akcje:
   [Use project type baseline instead]
       public_products avg $145, this $200 = +38% (normal range)
   [Increase baseline tolerance]
       Wait until 20+ projects dla statistical reliability
   [Suppress dla this anomaly only]
   
  Auto-correction:
   System will widen tolerance jako more data collected
```

#### EC-A3: ML model overfitting

**Trigger**: ML-based anomaly detection trained on 30 dni. Operator's pattern
recently changed (started new business, more projects). ML flags new patterns
as anomalies.

```
⚠ ML model needs retraining

  ML model trained: 90 days ago
  Recent pattern shift: operator activity +200% w ostatnich 14 dni
  
  Effect: ML flags new patterns as anomalies (false positives)
  False positive rate: 65% (vs 8% normally)
  
  Akcje:
   [Retrain ML model now]
       Use recent data, ~15 min processing
   [Disable ML temporarily]
       Use rules + statistical only
   [Adjust pattern tolerance]
       Wider acceptable patterns
   [Schedule monthly auto-retraining]
       Avoid future drift
```

#### EC-A4: Multiple anomalies same root cause

**Trigger**: Provider degradation causes Tier 1 (per-call latency), Tier 2
(hourly spend up), Tier 3 (retry pattern), Tier 4 (project budget warning).
4 alerts za jeden problem.

```
⚠ Aggregated anomaly — single root cause

  4 anomaly findings, likely same root cause:
   ⚠ Per-call cost up 40% (claude-sonnet)
   ⚠ Hourly spend +35% baseline
   ⚠ Pattern: many retries detected
   ⚠ Predicted: budget hit w 8h
  
  Root cause: Anthropic API degraded (high latency causing retries)
  
  Aggregation:
  Cost Guard merges these into single notification:
   "Anthropic API degraded → 4 cost anomalies. Root cause:
    vendor-side issue. Recommended: switch to OpenRouter fallback."
   
  Akcje:
   [Apply suggested fix (use OpenRouter fallback)]
   [Wait for vendor recovery]
   [Pause project until resolved]
```

#### EC-A5: Cost source missing data

**Trigger**: Stripe API down dla 2h. Cost Guard nie ma billing data.
Reports show "$0 vendor cost", actually it was $5.

```
ℹ Cost data incomplete

  Source: Stripe billing API
  Status: ✗ Down (last successful sync: 2h ago)
  
  Estimated missing data: $4-8 (last 2h transactions)
  
  Display:
   • Reports show "Stripe: $X (estimated, vendor sync pending)"
   • Daily summary marked z "incomplete data"
  
  Akcje:
   [Wait for Stripe recovery (auto-sync)]
   [Manually enter estimated cost]
   [Exclude Stripe z reports until sync]
   
  When Stripe recovers:
   ✓ Backfill missing 2h
   ✓ Reconcile estimates vs actual
   ✓ Adjust reports retroactively
```

### Kategoria B — Auto-action issues (5 cases)

#### EC-B1: Model switch backfires

**Trigger**: Cost Guard auto-switched Council Critic od claude-sonnet do
claude-haiku. Critic now produces wrong analyses, build fails. Total cost
higher (rebuild needed).

```
✗ Auto-switch caused regression

  Auto-switch: Council Critic claude-sonnet → claude-haiku
  Trigger: 75% budget threshold
  
  Result:
   • Critic missed important issue
   • Build failed (didn't catch security vulnerability)
   • Rebuild required
   • Net cost: $25 more (rebuild + new Council)
  
  Lessons learned:
   ☑ Mark Critic role as "no auto-switch" (operator-critical)
   ☑ Add quality regression detection po auto-switch
   ☐ Disable auto-switch globally (too risky)
   
  Recovery:
   [Revert to claude-sonnet]
   [Restart build z proper Critic]
```

#### EC-B2: Throttling causes cascading delays

**Trigger**: Throttling activated. Build slows. Tests timeout. Test failures.
Operator notification storm.

```
⚠ Throttling cascade effect

  Throttling: max 1 call/sec
  Effect on tests:
   • Test timeout: 5 tests failed (timeout, not actual failure)
   • Operator notified każdym failure (5 notifications)
   • Build pipeline confused (failed tests trigger investigations)
  
  Akcje:
   [Increase throttle (max 5 calls/sec)]
   [Disable throttling temporarily]
   [Rerun failed tests manually]
   [Adjust test timeouts dla throttled mode]
   
  Future prevention:
   ☑ Detect cascading effects from throttling
   ☑ Adjust dependent timeouts when throttling active
```

#### EC-B3: Pause non-critical pauses critical

**Trigger**: Cost Guard paused "non-critical" workloads. One was actually
critical (operator forgot to mark it). Customer experience degrades.

```
⚠ Pause incorrectly affected critical workload

  Paused: "Customer Acme weekly report generation"
  Marked as: non-critical
  Actually: critical (customer expects every Monday)
  
  Customer impact:
   ⚠ Customer didn't receive Monday report
   ⚠ Customer service ticket opened
  
  Akcje:
   [Resume paused workload immediately]
   [Mark workload as critical (don't pause again)]
   [Notify customer + apology]
   [Generate report manually now]
   
  Process improvement:
   ☑ Periodic review of "non-critical" tagged workloads
   ☑ Customer-facing workloads default critical
```

#### EC-B4: Hard stop blocks production deploy

**Trigger**: Hard stop triggered mid-deploy do production. Half-deployed
state. Customer-facing partial outage.

```
🚨 CRITICAL — Hard stop during production deploy

  Project: Sylion Tailor v3
  Action: Production deploy 60% complete
  Cost Guard hard stop: budget exceeded (101%)
  
  Current state:
   ✓ New version deployed do prod (4 z 6 services updated)
   ✗ 2 services still on old version
   ⚠ Mixed-version state (UNSAFE)
  
  Akcje (urgent):
   [● Override hard stop, complete deploy]
       Approve $20 budget increase, finish deploy
       Estimated: 2 min to complete
   [○ Rollback partial deploy]
       Restore old version on all 6 services
       Customer downtime: ~3 min
   [○ Manual deploy completion]
       Operator manually deploys remaining services
   
  ⚠ DO NOT leave half-deployed (mixed versions = bad)
  
  Future prevention:
   ☑ Never hard-stop mid-critical-action (deploy, migration)
   ☑ Reserve buffer dla critical operations
   ☑ Alert before deploy: "estimated $X, budget remaining $Y"
```

#### EC-B5: Auto-action loop

**Trigger**: Cost Guard switches model → quality drops → tests fail → retry
needed → more cost → switch again → more failures → infinite loop.

```
⚠ Auto-action feedback loop detected

  Pattern detected:
   1. Cost approaching threshold
   2. Switch to cheaper model
   3. Quality drops, tests fail
   4. Retry needed (more cost)
   5. Threshold hit again
   6. Switch again, more failures
   7. (loop continues)
  
  Emergency action: PAUSE all auto-actions
  
  Operator review needed:
   [Disable auto-switching dla this project]
   [Investigate test failures]
   [Increase budget to break loop]
   [Restart with operator-approved model selection]
   
  Future prevention:
   ☑ Detect loops (same auto-action 3+ times w hour)
   ☑ Auto-disable after loop detected
   ☑ Notify operator z loop detection
```

### Kategoria C — Reporting issues (4 cases)

#### EC-C1: Report contains stale data

**Trigger**: Daily report generated. Vendor (Stripe) data delayed by 6h.
Report missing recent costs.

```
⚠ Report shows incomplete data

  Daily summary 2026-04-29:
   Marked: "Stripe data 6h delayed"
   Estimated missing: $3-5
   Reports shows: $14.20 actual + ~$3-5 estimated = $17-19 likely
  
  Operator awareness:
   [Mark report as preliminary]
   [Wait for full data, regenerate]
   [Accept estimates (no regen needed)]
```

#### EC-C2: Closure report estimate accuracy poor

**Trigger**: Project closure report shows estimate was 45% off (actual much
higher). Operator wants to investigate.

```
⚠ Cost estimate accuracy issue

  Project: Customer Acme Pilot
  Estimated: $80
  Actual: $145
  Variance: +81%
  
  Investigation findings:
   • 2 mid-flight scope additions (operator-approved)
   • 4 extra mid-build interventions (vs 2 estimated)
   • Customer requested last-minute language addition (DE)
  
  Recommendation:
   [Adjust calibration dla "Customer pilot" type]
       New baseline: 1.5x z scope adjustments
   [Document scope creep w project notes]
   [Improve estimate accuracy dla future]
```

#### EC-C3: Report sent do wrong recipient

**Trigger**: Daily report sent do operator's old email (cached). Operator
moved emails. Reports not seen for 2 weeks.

```
⚠ Reports not being read

  Daily reports sent: 14
  Reports opened (estimated): 0
  Email recipient: robert@old-company.com
  
  Possible:
   • Email bounce (account closed)
   • Spam folder
   • Operator changed email
  
  Akcje:
   [Update recipient email]
   [Verify email delivery]
   [Switch primary channel do in-app]
   [Switch to mobile push notifications]
```

#### EC-C4: Report generation cost too high

**Trigger**: Monthly report uses LLM dla insights. Generation costs $5.
Operator decides to disable.

```
ℹ Report generation cost analysis

  Monthly report cost: $4.80 (LLM-generated insights)
  Yearly: ~$58
  
  Operator's options:
   [Use LLM-generated insights (current)]
       Best quality, $58/yr
   [Use template-based reports (no LLM)]
       Lower quality but free
   [Hybrid: LLM dla closure reports only]
       Save ~$40/yr, lose monthly insights
   [Disable LLM-generated reports]
       Use raw data tables only
```

### Kategoria D — Recommendations issues (4 cases)

#### EC-D1: Recommendation backfires

**Trigger**: Operator applied recommendation "switch Critic do gpt-5-mini".
Saved $5. But mini missed bug → cost $25 to fix.

```
⚠ Recommendation backfired

  Recommendation: Switch Critic gpt-5 → gpt-5-mini
  Saved: $5 (LLM cost)
  Hidden cost: $25 (rebuild after Critic missed bug)
  Net: -$20
  
  Lessons learned:
   ☑ Track recommendation ROI (savings - hidden costs)
   ☑ Adjust confidence dla similar recommendations
   ☑ Consider Critic role może wymagać premium model
   
  Akcje:
   [Revert recommendation (use gpt-5 again)]
   [Mark recommendation as "operator vetoed"]
       Don't suggest similar dla 30 dni
   [Accept loss as learning experience]
```

#### EC-D2: Recommendations spam (too many)

**Trigger**: System generates 47 recommendations w jeden tydzień. Operator
overwhelmed, ignores all.

```
⚠ Recommendations overload

  Recommendations generated: 47 (last 7 days)
  Operator engagement: 2 applied, 0 dismissed, 45 ignored
  
  Recommendations:
   [Increase confidence threshold (90% instead of 70%)]
       Fewer recommendations, higher quality
   [Batch into weekly digest (vs real-time)]
       1 summary instead of 47 alerts
   [Disable low-impact recommendations]
       Show only $10+ savings opportunities
   [Operator overrides: pause recommendations entirely]
```

#### EC-D3: Recommendation conflicts z operator preference

**Trigger**: Recommendation: "Use lokalne models more". Operator has goal
"public_products" requiring API quality. Conflict.

```
ℹ Recommendation conflicts z operator profile

  Recommendation: Switch więcej calls do lokalnych models
  Operator goal: public_products (requires high quality)
  Operator profile: prefers API quality > cost savings
  
  System learning:
   ☑ Note operator's preference (don't repeat similar)
   ☑ Adjust future recommendations to favor quality
   ☑ Suggest cost optimization w other dimensions
       (e.g., cloud resources, vendor pass-through)
```

#### EC-D4: Recommendation requires operator action

**Trigger**: Recommendation "Apply Hetzner reserved instance". Requires
operator to commit to 1-year prepay. Operator nie wie czy ma cash flow.

```
ℹ Recommendation requires operator decision

  Recommendation: Hetzner Reserved Instance (1-year prepay)
  Savings: €82/year
  Cash flow impact: -€326 upfront
  
  Operator considerations:
   • Cash flow availability
   • Project pipeline stability (1 year commitment)
   • Risk of provider change
  
  Akcje:
   [Approve and apply]
   [Defer 30 days (re-evaluate)]
   [Cancel — won't apply]
   [Schedule reminder]
```

### Kategoria E — Recovery / migration (4 cases)

#### EC-E1: Cost data corruption

**Trigger**: SQLite corruption affecting cost data table.

```
⚠ Cost data corruption

  Affected: last 7 days of cost records (~12 GB lost)
  
  Recovery:
   [Restore z backup (yesterday)]
       Lose 24h of records
   [Reconstruct from vendor billing APIs]
       Slow (~30 min) but accurate
   [Combine: restore + vendor reconcile]
       Best result, ~15 min
```

#### EC-E2: Workspace import — cost history

**Trigger**: Operator imports workspace from another machine. Cost history
incomplete.

```
ℹ Cost history import

  Imported: 6 months of cost data
  Reconciliation needed:
   • Vendor billing data may be different timezone
   • Cost calibration may not match new machine baseline
   • Recommendations may need recalibration
  
  Akcje:
   [Auto-reconcile (default)]
   [Manual review per anomaly]
   [Reset cost baselines, learn from scratch]
```

#### EC-E3: AEIS update changes cost calculations

**Trigger**: AEIS update changed how cost is calculated. Old data
incomparable.

```
ℹ AEIS update — cost calculation changed

  Old: pre-tax LLM cost
  New: includes fees, tax adjustments
  
  Impact:
   • Historical comparisons may show artificial increases
   • Reports include disclaimer
   • Calibration models adjusted
  
  Akcje:
   [Apply new calculation method (default)]
   [Mark transition w cost timeline]
   [Recalibrate ML models z new data]
```

#### EC-E4: Vendor API change breaks tracking

**Trigger**: Stripe changed API format. Cost Guard can't parse new format.

```
✗ Vendor API integration broken

  Vendor: Stripe
  Last successful sync: 4 dni temu
  Reason: Stripe API v2024-06 → v2025-01 (breaking)
  
  Akcje:
   [Update Stripe integration (system update)]
       AEIS team push update
   [Manual cost entry w meantime]
   [Disable Stripe tracking temporarily]
   [Use estimated costs (z transaction count × avg fee)]
```

---

## 7.14. Inheritance + Acceptance Criteria + DoD

### 7.14.1. Inheritance pattern

```
Phase 4: Budget templates established
   ↓
Phase 5: DIM-3 Cost Decisions L0-L5
   ↓
Phase 6: Aggregated Guards panel
   ↓
Phase 7 (Cost Guard) — combines all of above:
   • Inherits budget templates jako enforcement targets
   • Inherits DIM-3 levels jako auto-action permissions
   • Reports findings do faza 6 aggregated panel
   • Per-Guard autonomy override possible
```

### 7.14.2. DoD

#### Wspólne (zawsze wymagane)

```
✓ Cost Guard scope configured
✓ Anomaly detection thresholds reviewed
✓ Auto-actions authorized per autonomy preset
✓ Reports cadence ustanowione
✓ Audit chain entry: phase_7.complete
```

#### Recommended

```
✓ Vendor pass-through tracked (jeśli applicable)
✓ Predictive horizons enabled (1h, 24h, 30d minimum)
✓ Recommendations engine active
✓ ML baseline learning enabled (po 30 dni data)
✓ Closure reports auto-generated
```

### 7.14.3. Soft warnings vs hard blocks

**Hard blocks**:
- All anomaly detection disabled (Guard useless)
- Auto-actions all disabled bez manual oversight (defeats purpose)
- No cost limits configured (no enforcement possible)

**Soft warnings**:
- ML disabled bez data (acceptable, fallback to statistical)
- Vendor pass-through not tracked (operator handles externally)
- Predictive disabled (operator handles via reports)
- Recommendations disabled (operator handles externally)

### 7.14.4. Acceptance test

```bash
$ aeis-cli phase7-acceptance-test

Running Phase 7 acceptance test...

[Common requirements]
[1/5] Scope configured (LLM + cloud + vendor)        ✓ PASS
[2/5] Anomaly detection thresholds                   ✓ PASS
[3/5] Auto-actions authorized                        ✓ PASS
[4/5] Reports cadence                                ✓ PASS
[5/5] Audit chain entry phase_7.complete             ✓ PASS

[Optional features]
[6/9] Vendor pass-through                            ✓ PASS (Stripe, ElevenLabs)
[7/9] Predictive horizons                            ✓ PASS (4 horizons)
[8/9] Recommendations engine                         ✓ PASS (active)
[9/9] ML baseline learning                           ⠋ PROGRESS (78 days collected, need 90)

[Integration]
[10/12] Aggregated Guards panel integration          ✓ PASS
[11/12] Per-Guard autonomy override                  ✓ PASS
[12/12] Cost limits enforcement                      ✓ PASS

DoD: 11/12 ✓ + 1 ⠋
Hard blocks: 0
Soft warnings: 0

Phase 7 ACCEPTED. Ready to proceed to Phase 8 (Security Guard).

ML training will complete w 12 dni (auto).
```

---

## Status fazy 7

🟢 **Wszystkie sekcje 7.1-7.14 complete**

**Zawiera**:
- ✓ Sense + relacja do faz 3-5 (7.1)
- ✓ Scope: LLM + cloud + vendor pass-through (7.2)
- ✓ Aggregation: 4 levels z toggle + cross-level pivot (7.3)
- ✓ Time windows: real-time + period + project lifetime (7.4)
- ✓ Anomaly detection: 4 tiers (per-call/statistical/pattern/predictive) (7.5)
- ✓ Detection mechanisms: rules + statistical + ML hybrid (7.6)
- ✓ Baseline learning: multi-dim (workspace/operator/type/D-level/phase/role) (7.7)
- ✓ Auto-actions: 5 categories z autonomy control (7.8)
- ✓ Predictive actions: adaptive per autonomy preset (7.9)
- ✓ Hard/soft stops: 5-tier configurable (7.10)
- ✓ Reporting: daily/weekly/monthly/closure/on-demand (7.11)
- ✓ Real-time recommendations z lifecycle tracking (7.12)
- ✓ Edge cases: 22 cases w 5 kategoriach (7.13)
- ✓ Inheritance + DoD + acceptance test (7.14)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 7** + przejście do **Faza 8 — Security Guard** (trzeci z 5 Guards).
