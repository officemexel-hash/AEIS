# FAZA 5 — Autonomy Configuration

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (5 z 11)
> **Typ**: jednorazowa (z opcją powrotu po doświadczeniu z projektami)
> **Czas wykonania**: 5 min (akceptacja preset z fazy 4) / 30-60 min (full per-dimension customization) / 2h (advanced + custom hard gates)
> **D-level**: D2 — autonomy decyzje wpływają na wszystkie przyszłe projekty
> **Zależności**: Faza 4 (presets autonomy ustanowione)
> **Następnik**: Faza 6 (Coherence Guard — pierwszy z 5 Guards)
>
> **Spis sekcji**:
> - 5.1 — Sense fazy + relacja do fazy 4
> - 5.2 — 10 wymiarów autonomy — pełna definicja
> - 5.3 — Levels L0-L5 — semantyka i konsekwencje
> - 5.4 — Wizard adaptive (sliders / steps / matrix)
> - 5.5 — Per-dimension deep config
> - 5.6 — Hard gates — baseline 18 + operator-extensible
> - 5.7 — Multi-color inheritance map (visualization)
> - 5.8 — Time-bounded overrides + per-dimension cascade
> - 5.9 — Edge cases (22 cases) + inheritance + DoD
> - 5.10 — Acceptance criteria + automated test

---

## 5.1. Sens fazy i relacja do fazy 4

### 5.1.1. Faza 4 vs Faza 5 — granica

**Faza 4 (Workspace Defaults)** ustanowiła:
- 5 autonomy presetów (Conservative / Balanced / Aggressive / Research / Production)
- Goal-driven mapping (które goal → który preset)
- Default budgety, notification matrix, etc.

**Faza 5 (Autonomy Configuration)** zajmuje się:
- Pełnym definiowaniem 10 wymiarów per L0-L5
- Customization presetów per dimension
- Hard gates definition (które akcje zawsze wymagają operator)
- Per-dimension override patterns
- Inheritance management

### 5.1.2. Operator może pominąć fazę 5

Operator który zaakceptował presety w fazie 4 **nie musi** robić fazy 5
deep config. Presety z fazy 4 są kompletne — wszystkie 10 wymiarów ustawione
zgodnie z preset wartościami.

**Faza 5 jest dla operatorów którzy chcą**:
- Tweakować preset per dimension (np. Production preset, ale Research-style cost decisions)
- Dodawać własne hard gates (poza standardową listą 18)
- Tworzyć custom autonomy preset
- Zrozumieć w detalu co znaczy każdy level

**Recommended path**:
- Pierwszy raz operator → skip fazę 5, używaj presetów z fazy 4
- Po 5-10 projektach → wraca do fazy 5, dostosowuje based on doświadczenie
- Power user → faza 5 od razu po fazie 4

### 5.1.3. Wynik fazy 5 (DoD)

**Minimum**:
- ✓ Operator zrozumiał co znaczy każdy z 10 wymiarów
- ✓ Operator zrozumiał semantykę L0-L5
- ✓ Hard gates baseline akceptowane (lub modyfikowane)

**Pełne**:
- ✓ Custom autonomy preset utworzony (jeśli operator chce poza 5 standard)
- ✓ Per-dimension overrides skonfigurowane
- ✓ Hard gates extension (operator-defined gates dodane)
- ✓ Inheritance behavior rozumiany
- ✓ Time-bounded override patterns ustanowione

---

## 5.2. 10 wymiarów autonomy — pełna definicja (P5.1=a)

### 5.2.1. Lista 10 wymiarów

```
┌──────────────────────────────────────────────────────────────┐
│  AEIS Autonomy Dimensions (10)                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  DIM-1   Council Formation                                   │
│  DIM-2   Council Voting Threshold                            │
│  DIM-3   Cost Decisions                                      │
│  DIM-4   Model Selection                                     │
│  DIM-5   Environment Selection                               │
│  DIM-6   Skill Creation                                      │
│  DIM-7   Quality Verdicts                                    │
│  DIM-8   Deploy Authorization                                │
│  DIM-9   Mid-flight Overrides                                │
│  DIM-10  Cascade Re-evaluation                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2.2. DIM-1: Council Formation

**Co reguluje**: kto siedzi w Council per projekt — które role są
includowane, ile modeli per rola.

**Decision points**:
- Standard set vs custom Council per projekt
- Add/remove roles per projekt
- Multi-model voting per rola (1 model vs ensemble of 3)
- Cross-project role pinning (operator chce ten sam Critic wszędzie)

**Levels**:
```
L0 — Always manual: operator wybiera Council per każdy projekt
L1 — Notify: system proponuje, operator zatwierdza lub zmienia
L2 — Balanced: system uses faza 4 default, operator może override przed start
L3 — Auto with audit: system formuje Council automatycznie, operator review po
L4 — Auto with sampling: system formuje, operator review co 5-ty projekt
L5 — Fully autonomous: system zarządza Council bez operator
```

**Risk profile**: niskie (Council formation rzadko jest critical — pattern
is well-defined). L4-L5 jest acceptable dla większości operatorów.

### 5.2.3. DIM-2: Council Voting Threshold

**Co reguluje**: ile głosów Council musi zgadzać się żeby decyzja przeszła.

**Decision points**:
- Simple majority (50%+1) vs supermajority (66%) vs unanimity
- Critic veto power (Critic może blokować nawet jeśli majority)
- Tie-breaking (operator decyduje czy Chair tie-breaks)
- Quorum requirements (min ile Council members musi participować)

**Levels**:
```
L0 — Always manual: operator definiuje threshold per Council session
L1 — Notify: system proponuje, operator confirms
L2 — Balanced: system uses faza 12 template threshold
L3 — Auto with audit: system zarządza, operator review jeśli unanimous fail
L4 — Auto with sampling: review jeśli threshold close (50/50 splits)
L5 — Fully autonomous: system zarządza wszystkim
```

### 5.2.4. DIM-3: Cost Decisions (P5.6=d full cost autonomy)

**Co reguluje**: zarządzanie kosztami — auto-approval spike, model
switching for cost optimization, budget reservation, continuous
re-balancing.

**Decision points**:
- Auto-approve cost spikes (single call > limit)
- Switch do cheaper model jeśli koszt rośnie (adaptive fallback)
- Continuous re-balancing (system constantly optimizes)
- Per-project budget reservation upfront (lock budget before start)

**Levels**:
```
L0 — Always manual:
  • Operator approves każdy spike
  • Operator wybiera model przy każdej decyzji
  • Brak auto-switching
  • Operator manualnie monitoruje cost

L1 — Notify:
  • System wykrywa spikes, pokazuje notification
  • Operator approves po notification (no time pressure)
  • Brak auto-switching

L2 — Balanced (default dla większości):
  • Auto-approve spikes < $1
  • Spikes > $1 wymagają operator (within timeout)
  • Auto-switch do cheaper model gdy budget > 70%
  • Notify operator o switch

L3 — Auto with audit:
  • Auto-approve spikes < $5
  • Auto-switch agresywnie (threshold 50%)
  • Operator review w post-build raport
  • Można rollback decyzji

L4 — Auto with sampling:
  • Auto-approve wszystko (do project budget cap)
  • Continuous re-balancing aktywny
  • Operator review co 5-ty projekt cost decisions

L5 — Fully autonomous:
  • Operator nie reaguje on cost decisions
  • System optimizes całkowicie
  • Audit chain dostępny ale brak active review
  • Used dla: high-volume projektów, mature operatorów
```

**Use case**: research labs często wybierają L4-L5 dla DIM-3 bo szybkość
iteracji ważniejsza niż cost optimization per call.

### 5.2.5. DIM-4: Model Selection

**Co reguluje**: który model dla której roli/zadania.

**Decision points**:
- Preferred model per Council role
- Fallback chain depth (jak głęboko system może iść w fallback)
- Model upgrade decisions (gdy nowy model published)
- Local vs API preference (cost vs quality trade-off)

**Levels**:
```
L0 — Always manual: operator wybiera model per call
L1 — Notify: system proponuje, operator confirms przed call
L2 — Balanced: system uses chain z fazy 2.9, operator override możliwy
L3 — Auto with audit: system free to choose, operator review post-fact
L4 — Auto with sampling: review co N-ty decision
L5 — Fully autonomous: system completes wszystko bez intervention
```

### 5.2.6. DIM-5: Environment Selection

**Co reguluje**: gdzie kod jest budowany/testowany/deployowany.

**Decision points**:
- Auto-route do appropriate environment (dev for prototyping, prod for release)
- Multi-environment parallel (build na 2 env równolegle dla comparison)
- Environment switching mid-build (np. dev → staging po milestone)
- Sovereign routing (auto-detect i route do EU sovereign jeśli PII)

**Levels**:
```
L0 — Manual: operator wybiera env dla każdego deploy
L1 — Notify: system proponuje, operator confirms
L2 — Balanced: system uses defaults, deploy do prod wymaga operator
L3 — Auto z audit: system routes wszystko, prod też (z audit chain)
L4 — Auto z sampling: review co N-ty
L5 — Fully autonomous
```

**Note**: Hard gate "deploy do production" zawsze może override DIM-5
nawet przy L5 (zobacz sekcja 5.6 hard gates).

### 5.2.7. DIM-6: Skill Creation

**Co reguluje**: czy AEIS może auto-create new skills (capabilities) na
fly, czy operator approve.

**Decision points**:
- Auto-create skills based on Council recommendation
- Skill modifications (existing skill enhancement)
- Skill deletion (cleanup unused)
- Cross-project skill sharing

**Levels**:
```
L0 — Manual: operator definiuje każdy skill
L1 — Notify: system proponuje skills, operator approves
L2 — Balanced: simple skills auto, complex wymagają operator
L3 — Auto z audit: wszystkie skills auto, operator review periodically
L4-L5 — fully autonomous
```

### 5.2.8. DIM-7: Quality Verdicts (P5.7=d configurable threshold)

**Co reguluje**: czy operator MUSI review quality gate results.

**Decision points**:
- Configurable threshold (operator definiuje "auto-accept jeśli...")
- Pre-conditions (coverage > X% AND failed < Y AND security findings = 0)
- Per-test-level (L1 unit auto-accept, L4 performance always operator)
- Per-D-level overrides

**Levels**:
```
L0 — Manual: operator review każdy test result
L1 — Notify: system shows verdict, operator może override
L2 — Balanced (configurable):
  Default threshold: auto-accept if:
    • L1 coverage > 80%
    • L1 + L2 failed < 5
    • Security findings = 0 (P0/P1)
    • Visual regression < 5% changes
  Else: operator review
L3 — Auto z audit: system accepts wszystkie verdicts, operator review post
L4 — Auto z sampling: 1 z 10 verdicts manual review
L5 — Fully autonomous
```

**Configurable threshold UI**:

```
DIM-7 Quality Verdicts → Configure threshold

  Auto-accept if ALL of these are true:
   ☑ L1 unit tests coverage >= [80% ▼]
   ☑ L1 + L2 failed tests < [5 ▼]
   ☑ Security findings P0/P1 = 0
   ☐ Performance tests pass (jeśli L4 enabled)
   ☑ Visual regression < [5%] changes
   ☑ Accessibility checks pass
   ☑ Human-like UI testing pass
   ☑ Lint errors = 0
   ☐ Code complexity < threshold
  
  Else require operator review.
  
  D-level overrides:
   ☑ D5 always require operator (skip auto-accept)
   ☑ D4 require operator if any test failed
   ☐ D1-D2 use looser thresholds
```

### 5.2.9. DIM-8: Deploy Authorization

**Co reguluje**: kto autoryzuje deploys.

**Decision points**:
- Auto-deploy do dev/staging vs always operator
- Production deploy (zawsze operator? auto z monitoring?)
- Rollback authorization
- Multi-stage deploy (canary → percentage → full)

**Levels**:
```
L0 — Manual: operator approves każdy deploy do każdego env
L1 — Notify: system proposes deploy, operator approves przed start
L2 — Balanced:
  • Dev: auto
  • Staging: auto (z healthcheck)
  • Production: operator approves (hard gate)
L3 — Auto z audit:
  • Dev/staging auto
  • Production: auto z multi-stage canary, operator notified
L4 — Auto z sampling: review jeśli failure rate > threshold
L5 — Fully autonomous
```

**Note**: Production deploy ZAWSZE może być hard gate (sekcja 5.6) nawet
przy L5.

### 5.2.10. DIM-9: Mid-flight Overrides (P5.8=d adaptive per preset)

**Co reguluje**: co operator może override mid-build (gdy pipeline runs).

**Adaptive per preset**:

```
Conservative preset:
  Operator może:
   • Pause/resume pipeline
   • Cancel current phase
   • Modify Council composition
   • Skip phase
   • Edit Księgę mid-flight
   • Change masterplan
   • Switch models mid-build
   • Edit any artifact mid-build
   • Modify autonomy levels in real-time

Balanced preset:
  Operator może:
   • Pause/resume pipeline
   • Cancel current phase
   • Modify Council composition (next Council session, not current)
   • Skip phase
   • Switch models (next call, not current)
   • Modify autonomy levels (effective next phase)

Aggressive preset:
  Operator może:
   • Pause/resume pipeline
   • Cancel project (final cancellation)
   • Nothing else mid-flight (operator interferes minimum)

Production preset:
  Operator może:
   • Emergency pause
   • Emergency cancel
   • Trigger DR procedure
   • Edit hard gate response timeout

Research preset:
  Operator może:
   • All Conservative options
   • Plus: experimental real-time prompt injection
   • Plus: model swap mid-call (advanced!)
```

**Levels** map preset choices:
```
L0-L1 — Conservative-style (full control)
L2 — Balanced
L3-L4 — Aggressive (limited interference)
L5 — Fully autonomous (operator nie interferuje)
```

### 5.2.11. DIM-10: Cascade Re-evaluation

**Co reguluje**: czy system auto-replanuje po incident/failure, czy
operator decyduje.

**Decision points**:
- Test failure → auto-replan how to fix vs operator decides
- Cost overrun → auto-cut scope vs operator decides
- Provider down → auto-failover vs operator decides
- Security finding → auto-mitigate vs operator decides

**Levels**:
```
L0 — Manual: każda re-evaluation wymaga operator decision
L1 — Notify: system proposuje plan, operator approves
L2 — Balanced: routine cascades auto, complex (>3 phases affected) operator
L3 — Auto z audit: system replans, operator review post
L4 — Auto z sampling
L5 — Fully autonomous
```

**Note**: Security incidents zawsze są hard gate w Conservative/Production
presets, nawet przy L5.

### 5.2.12. Wymiar selection summary

```
┌──────────────────────────────────────────────────────────────┐
│  Dimension              Default   Most operators set         │
│  ──────────────────  ───────   ─────────────────────────  │
│  DIM-1  Council form    L2       L2-L3 (rarely critical)     │
│  DIM-2  Voting          L2       L2 (preset handles)         │
│  DIM-3  Cost            L2       L1-L4 (most variable)       │
│  DIM-4  Model selection L2       L2-L3                       │
│  DIM-5  Environment     L2       L1-L2 (production matters)  │
│  DIM-6  Skill creation  L2       L3-L5 (rarely critical)     │
│  DIM-7  Quality verdicts L2      L0-L2 (operator review)     │
│  DIM-8  Deploy auth     L1       L0-L2 (always cautious)     │
│  DIM-9  Mid-flight      L2       Per preset (rarely changed) │
│  DIM-10 Cascade re-eval L2       L1-L3                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 5.3. Levels L0-L5 — semantyka i konsekwencje (P5.2=a)

### 5.3.1. Pełna definicja per level

```
┌──────────────────────────────────────────────────────────────┐
│  L0 — Always Manual                                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • Operator klika za każdym razem                           │
│   • System nigdy nie podejmuje decyzji autonomicznie         │
│   • Operator pisemnie aprobuje każdą akcję                   │
│                                                              │
│  Pros:                                                       │
│   • Maksymalna kontrola                                      │
│   • Maksymalna safety                                        │
│   • Operator wie wszystko co się dzieje                      │
│                                                              │
│  Cons:                                                       │
│   • Bardzo wolno (operator latency = bottleneck)             │
│   • Operator burnout (zbyt dużo prompts)                     │
│   • Pipeline często paused waiting na operator               │
│                                                              │
│  Best for:                                                   │
│   • Government / classified projects                         │
│   • Critical financial systems                               │
│   • New operator (still learning)                            │
│   • High-stakes deployment                                   │
│                                                              │
│  Operator interactions per project: 50-150                   │
│  Hands-on time per project: 2-8 hours                        │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  L1 — Notify Only                                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • System podejmuje decyzję                                 │
│   • Operator widzi notification natychmiast                  │
│   • Operator może override w trakcie/post                    │
│   • Decyzja "stoi" dopóki operator nie zmieni                │
│                                                              │
│  Pros:                                                       │
│   • Szybko (system nie czeka)                                │
│   • Operator visibility (wie co się dzieje)                  │
│   • Możliwość override                                       │
│                                                              │
│  Cons:                                                       │
│   • Notification noise (wiele alerts)                        │
│   • Operator może przegapić niektóre                         │
│   • Override za późno (decyzja already executed)             │
│                                                              │
│  Best for:                                                   │
│   • Operator który chce visibility ale nie kontrolę          │
│   • Mature operator który ufa systemowi ale chce wiedzieć    │
│   • Audit-heavy environments                                 │
│                                                              │
│  Operator interactions per project: 30-80 (notifications)    │
│  Hands-on time: 30-60 min                                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  L2 — Balanced (default)                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • Operator approves dla risky decisions                    │
│   • System auto dla routine decisions                        │
│   • Defined risk thresholds (per dimension)                  │
│                                                              │
│  Pros:                                                       │
│   • Balance speed vs control                                 │
│   • Operator focus na important decyzje                      │
│   • System handles boring stuff                              │
│                                                              │
│  Cons:                                                       │
│   • Definicja "risky" jest subjective                        │
│   • Może wymagać tuning thresholds                           │
│                                                              │
│  Best for:                                                   │
│   • Standard production work                                 │
│   • Most SYLION operators                                    │
│   • Default dla większości presetów                          │
│                                                              │
│  Operator interactions per project: 8-15                     │
│  Hands-on time: 25-45 min                                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  L3 — Auto with Audit                                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • System podejmuje wszystkie decyzje                       │
│   • Pełen audit chain dla każdej decyzji                     │
│   • Operator review post-fact (np. po build)                 │
│   • Operator może rollback decyzji ale ostro                 │
│                                                              │
│  Pros:                                                       │
│   • Bardzo szybko                                            │
│   • Operator wciąż w pętli (post-review)                     │
│   • Pełna traceability                                       │
│                                                              │
│  Cons:                                                       │
│   • Decyzje już "done" before operator review                │
│   • Rollback może być expensive (re-build)                   │
│                                                              │
│  Best for:                                                   │
│   • Mature operator z proven autonomy presets                │
│   • Volume work (wiele projektów)                            │
│                                                              │
│  Operator interactions per project: 3-8 (post-review)        │
│  Hands-on time: 15-30 min                                    │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  L4 — Auto with Sampling                                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • System podejmuje wszystkie decyzje                       │
│   • Operator review tylko sample (1 z N)                     │
│   • Default sample rate: 1/10                                │
│   • System może flag suspicious cases for extra review       │
│                                                              │
│  Pros:                                                       │
│   • Bardzo wysokie throughput                                │
│   • Operator focus tylko na anomalies                        │
│                                                              │
│  Cons:                                                       │
│   • Risk: missed bad decisions                               │
│   • Wymaga trustworthy autonomy                              │
│                                                              │
│  Best for:                                                   │
│   • Research workloads (volume)                              │
│   • Internal tooling (low stakes)                            │
│   • Operator z 100+ projektów experience                     │
│                                                              │
│  Operator interactions per project: 0-2                      │
│  Hands-on time: 5-15 min                                     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  L5 — Fully Autonomous                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Behavior:                                                   │
│   • System operates bez operator intervention                │
│   • Audit chain always present (forensic)                    │
│   • Operator może reset/disable autonomous mode              │
│   • Hard gates STILL apply (fundamentale)                    │
│                                                              │
│  Pros:                                                       │
│   • Maksymalna prędkość                                      │
│   • Operator może focus na meta (strategy, planning)         │
│   • Allows AEIS to scale                                     │
│                                                              │
│  Cons:                                                       │
│   • Maximum risk (system errors not caught)                  │
│   • Operator może lose touch z what's happening              │
│   • Wymaga bardzo dojrzałego setup                           │
│                                                              │
│  Best for:                                                   │
│   • Production CI/CD pipelines                               │
│   • Research labs z volume requirements                      │
│   • Operator po long-term proven setup                       │
│                                                              │
│  Operator interactions per project: 0 (poza hard gates)      │
│  Hands-on time: 0-5 min                                      │
│                                                              │
│  ⚠ NOT RECOMMENDED dla customer-facing production            │
│    bez extensive validation                                  │
└──────────────────────────────────────────────────────────────┘
```

### 5.3.2. Risk multiplier per level

System pokazuje "risk multiplier" relative do L0 baseline:

```
Level   Speed multiplier   Risk multiplier   Cost variance
─────   ─────────────────  ────────────────  ──────────────
L0      1.0x  (baseline)   1.0x              ±0% (controlled)
L1      2.0x               1.1x              ±5%
L2      4.0x               1.3x              ±10%
L3      8.0x               1.8x              ±20%
L4      15x                2.5x              ±35%
L5      30x                4.0x              ±60%

Speed:  estimated wallclock time relative to L0 manual
Risk:   probability of suboptimal decisions
Cost:   variance from estimated cost (auto-decisions less optimal)
```

---

## 5.4. Wizard adaptive (P5.4=d)

### 5.4.1. Wizard mode selection

Operator po wejściu w fazę 5 widzi:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Phase 5 — Autonomy Configuration                         │
│                                                              │
│  Your faza 4 preset: Production (z public_products goal)     │
│                                                              │
│  Wybierz tryb konfiguracji:                                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [● Quick (5 min)]                                   │    │
│  │     Akceptuj preset z fazy 4                         │    │
│  │     Skip per-dimension config                        │    │
│  │     Recommended dla pierwszych projektów             │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○ Sliders (15-30 min)]                             │    │
│  │     10 sliders na single screen                      │    │
│  │     Power-user mode                                  │    │
│  │     Real-time preview                                │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○ Wizard (30-60 min)]                              │    │
│  │     10 steps, 1 dimension per step                   │    │
│  │     Detailed explanations                            │    │
│  │     Recommended dla beginners                        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○ Matrix (advanced)]                               │    │
│  │     10 dims × 5 presets visualization                │    │
│  │     Compare presets side-by-side                     │    │
│  │     Build custom preset                              │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  [○ Hard gates focus]                                │    │
│  │     Skip per-dimension                               │    │
│  │     Focus tylko na hard gates configuration          │    │
│  │     For operators z specific compliance needs        │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│                              [Continue]                      │
└──────────────────────────────────────────────────────────────┘
```

### 5.4.2. Sliders mode (power-user)

Single screen z 10 sliders, real-time preview:

```
┌──────────────────────────────────────────────────────────────┐
│  Autonomy Sliders                          [Reset to preset] │
│                                                              │
│  Dimension                Slider               Level         │
│  ─────────────────────  ─────────────────────  ──────────  │
│  DIM-1 Council Form     [○──────●─────] L2     Balanced     │
│  DIM-2 Voting Threshold [○────●───────] L2     Balanced     │
│  DIM-3 Cost Decisions   [○──●─────────] L1     Notify       │
│  DIM-4 Model Selection  [○──────●─────] L2     Balanced     │
│  DIM-5 Environment      [●─────────────] L0    Manual       │
│  DIM-6 Skill Creation   [○──────────●─] L4     Auto+Sample  │
│  DIM-7 Quality Verdicts [○──●─────────] L1     Notify       │
│  DIM-8 Deploy Auth      [●─────────────] L0    Manual       │
│  DIM-9 Mid-flight       [○────●───────] L2     Balanced     │
│  DIM-10 Cascade         [○────●───────] L2     Balanced     │
│                                                              │
│  Preview impact:                                             │
│   • Operator interactions: ~12 per project                   │
│   • Speed multiplier: 3.2x                                   │
│   • Risk multiplier: 1.4x                                    │
│   • Cost variance: ±12%                                      │
│   • Compared to Production preset: -40% interactions         │
│                                                              │
│  Hard gates active: 18 (default baseline)                   │
│  [Edit hard gates →]                                         │
│                                                              │
│  Save options:                                               │
│  [Save as override of Production]                            │
│  [Save as new custom preset]                                 │
│  [Apply to all goals (overrides goal-mapping)]               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.4.3. Wizard mode (beginner-friendly)

10 kroków, jeden wymiar per krok:

```
┌──────────────────────────────────────────────────────────────┐
│  Step 3/10 — DIM-3 Cost Decisions                            │
│                                                              │
│  Co kontroluje DIM-3:                                        │
│   • Auto-approval cost spikes                                │
│   • Model switching dla cost optimization                    │
│   • Continuous re-balancing                                  │
│                                                              │
│  ┌─ EXPLANATION ────────────────────────────────────────┐   │
│  │  Cost decisions to wymiar gdzie warto być ostrożnym. │   │
│  │  Surprise bills są frustrating, ale za-restryktywne  │   │
│  │  setup zatrzymuje pipeline często.                   │   │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Wybierz level:                                              │
│                                                              │
│  ┌─ L0 ──────────────────────────────────────────────┐      │
│  │  Operator approves każdy cost spike                │      │
│  │  Najsafe, najwolniej                               │      │
│  │  Recommended: government / financial               │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌─ L1 (selected by Production preset) ───────────────┐      │
│  │  ● System notifies, operator może override          │      │
│  │  Recommended dla większości production              │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌─ L2 ──────────────────────────────────────────────┐      │
│  │  Auto-approve <$1, operator dla >$1                │      │
│  │  Recommended dla balanced workflows                │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  ┌─ L3-L5 ───────────────────────────────────────────┐      │
│  │  More aggressive automation                        │      │
│  │  [Show advanced options]                           │      │
│  └────────────────────────────────────────────────────┘      │
│                                                              │
│  Your selection: L1 (preset default)                        │
│                                                              │
│  Impact:                                                     │
│   • Operator action per spike: notification (no time press) │
│   • Pipeline never blocked by cost decisions                 │
│   • Operator must monitor cost dashboard daily               │
│                                                              │
│  [← Previous]  [Skip step]  [Save & next]                    │
└──────────────────────────────────────────────────────────────┘
```

### 5.4.4. Matrix mode (advanced compare)

```
┌──────────────────────────────────────────────────────────────┐
│  Autonomy Matrix — Compare Presets                           │
│                                                              │
│  Dim       Conserv  Balanced  Aggress  Research  Production  │
│  ───────  ──────── ────────  ────────  ────────  ──────────│
│  DIM-1    L0       L2        L4       L4         L2          │
│  DIM-2    L0       L2        L4       L4         L2          │
│  DIM-3    L0       L2        L5       L5         L1          │
│  DIM-4    L0       L2        L4       L5         L2          │
│  DIM-5    L0       L2        L4       L4         L2          │
│  DIM-6    L0       L2        L4       L4         L2          │
│  DIM-7    L0       L2        L4       L1         L2          │
│  DIM-8    L0       L2        L4       L0         L0          │
│  DIM-9    L0       L2        L4       L0         L1          │
│  DIM-10   L0       L2        L4       L4         L0          │
│                                                              │
│  Operator interactions per project:                          │
│   Conservative: ~150                                         │
│   Balanced:     ~30                                          │
│   Aggressive:   ~5                                           │
│   Research:     ~8                                           │
│   Production:   ~15                                          │
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  Build custom preset:                                        │
│  Start from: [Production ▼]                                  │
│                                                              │
│   DIM-1  Council        [L2 ▼]                               │
│   DIM-2  Voting         [L2 ▼]                               │
│   DIM-3  Cost           [L1 ▼]   ← inherited                 │
│   DIM-4  Model          [L3 ▼]   ← override                  │
│   DIM-5  Environment    [L2 ▼]                               │
│   ...                                                        │
│                                                              │
│  Custom name: [My Production Variant            ]            │
│  Description: [Production + faster model selection]          │
│                                                              │
│  [Save as new preset]                                        │
└──────────────────────────────────────────────────────────────┘
```

---

## 5.5. Per-dimension deep config

### 5.5.1. Per-dimension settings panel

Per wymiar, operator widzi:

```
┌──────────────────────────────────────────────────────────────┐
│  DIM-3 — Cost Decisions                                       │
│  ────────────────────────────────────────────────────────────│
│                                                              │
│  Current level: L2 (Balanced)                                │
│  Inherited from: Production preset (faza 4)                  │
│                                                              │
│  ┌─ LEVEL OVERRIDE ─────────────────────────────────────┐    │
│  │  Default for this preset: L1                         │    │
│  │  Your override:           L2                         │    │
│  │  [Reset to preset default]                           │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ L2 BEHAVIOR DETAILS ────────────────────────────────┐    │
│  │                                                      │    │
│  │  Auto-approve cost spikes:                           │    │
│  │   ☑ Per-call < $1.00 (auto)                          │    │
│  │   ☐ Per-call < $5.00 (auto z notification)           │    │
│  │   ☑ Per-call >= $5.00 (require operator)             │    │
│  │                                                      │    │
│  │  Auto-switch do cheaper model:                       │    │
│  │   ☑ When project budget > 70% used                   │    │
│  │      Switch threshold: [70% ▼]                       │    │
│  │   ☐ When per-call cost > limit                       │    │
│  │   ☑ Notify operator when switch happens              │    │
│  │                                                      │    │
│  │  Continuous re-balancing:                            │    │
│  │   ☑ Active                                           │    │
│  │      Optimization frequency: [Per call ▼]            │    │
│  │      Aggressiveness: [Balanced ▼]                    │    │
│  │   ☐ Disabled                                         │    │
│  │                                                      │    │
│  │  Per-project budget reservation:                     │    │
│  │   ☑ Lock estimated budget upfront                    │    │
│  │      Buffer: [10%]                                   │    │
│  │   ☐ Soft tracking (no upfront lock)                  │    │
│  │                                                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─ TIME-BOUNDED OVERRIDE ──────────────────────────────┐    │
│  │  This dimension can be overridden per:               │    │
│  │   ☑ Per project (faza 17)                            │    │
│  │   ☑ Per Council session (faza 22)                    │    │
│  │   ☑ Per build phase (faza 33)                        │    │
│  │   ☑ Per single decision (real-time)                  │    │
│  │                                                      │    │
│  │  Override expiration:                                │    │
│  │   ☑ Override expires after build complete            │    │
│  │   ☐ Override permanent (until manually changed)      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                              │
│  [Save changes]  [Reset]  [Configure another dim →]         │
└──────────────────────────────────────────────────────────────┘
```

### 5.5.2. Per-D-level overrides per dimension

Każdy wymiar może mieć **różne** levels per D-level projektu:

```
DIM-7 Quality Verdicts → Per D-level override

  D1 (trivial):     L4 (auto with sampling)
  D2 (light):       L3 (auto with audit)
  D3 (standard):    L2 (balanced)
  D4 (production):  L1 (notify, operator review failures)
  D5 (critical):    L0 (manual review wszystkich)
  
  Override pattern:
   ☑ Use D-level adaptive levels
   ☐ Same level dla wszystkich D-levels (current: L2)
  
  Smart defaults per D:
   Higher D = more cautious (lower L number)
   Operator może adjust per row
```

---

## 5.6. Hard gates — baseline 18 + operator-extensible (P5.3=d, P5.9=a + extensible)

### 5.6.1. Czym są hard gates

**Hard gates** to akcje które ZAWSZE wymagają operator approval, niezależnie
od autonomy level:

- Nawet L5 fully autonomous nie może bypass hard gate
- Operator must explicitly approve każdy hard gate
- Hard gates są ostatnia linia obrony przed nieodwracalnymi błędami
- Hard gates mają dedykowany approval flow (sekcja 4.10 + 5.6.4)

### 5.6.2. Baseline 18 hard gates

System ma **18 predefined hard gates**. Operator może każdy edytować,
disable, lub dodać własne.

```
┌──────────────────────────────────────────────────────────────┐
│  Hard Gates — Baseline (18) + Custom                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PREDEFINED (18):                                            │
│                                                              │
│  PRODUCTION & DEPLOY                                         │
│   1. Deploy to production environment                        │
│      Default: ENABLED dla D3+, DISABLED dla D1-D2            │
│      [Edit]  [Disable]                                       │
│                                                              │
│   2. Force-deploy z failed tests                             │
│      Default: ENABLED always                                 │
│      [Edit]  [Disable]                                       │
│                                                              │
│   3. Rollback to previous production version                 │
│      Default: ENABLED always                                 │
│                                                              │
│   4. DNS cutover (live traffic switch)                       │
│      Default: ENABLED always                                 │
│                                                              │
│  PAYMENT & FINANCIAL                                         │
│   5. Payment integration trigger (live mode, not sandbox)    │
│      Default: ENABLED always                                 │
│                                                              │
│   6. Customer credit charge / refund                         │
│      Default: ENABLED always                                 │
│                                                              │
│  DATA & PRIVACY                                              │
│   7. GDPR data delete request                                │
│      Default: ENABLED always                                 │
│                                                              │
│   8. Customer data export (GDPR Art. 15)                     │
│      Default: ENABLED always                                 │
│                                                              │
│   9. Production data backup restore                          │
│      Default: ENABLED always                                 │
│                                                              │
│  SECURITY                                                    │
│   10. Security incident response action                      │
│       Default: ENABLED always                                │
│                                                              │
│   11. Master password change                                 │
│       Default: ENABLED always                                │
│                                                              │
│   12. Provider key rotation                                  │
│       Default: ENABLED dla critical providers                │
│                                                              │
│  CLASSIFIED & COMPLIANCE                                     │
│   13. Classified data movement (TLP:RED+)                    │
│       Default: ENABLED if any TLP:RED projekt                │
│                                                              │
│   14. Council finalization for D5 projects                   │
│       Default: ENABLED for D5                                │
│                                                              │
│   15. Customer onboarding (first deploy do customer env)     │
│       Default: ENABLED always                                │
│                                                              │
│  WORKSPACE & MANAGEMENT                                      │
│   16. Schema-breaking DB migration                           │
│       Default: ENABLED always                                │
│                                                              │
│   17. API breaking change publish                            │
│       Default: ENABLED always                                │
│                                                              │
│   18. Workspace export (with secrets)                        │
│       Default: ENABLED always                                │
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  CUSTOM (operator-defined): 0                                │
│   [+ Add custom hard gate]                                   │
│                                                              │
│  Examples of custom gates Operator może dodać:               │
│   • Approval przed sending email do >100 customers           │
│   • Trigger auto-scaling above N instances                   │
│   • Cost spike > $X w 1 hour                                 │
│   • New customer signup z >€10K initial value                │
│   • Deploy do specific customer environment                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.6.3. Edytowanie hard gate

```
┌──────────────────────────────────────────────────────────────┐
│  Edit Hard Gate: Deploy to production environment            │
│                                                              │
│  Status:                                                     │
│   [● Enabled]  [○ Disabled]                                  │
│                                                              │
│  When to trigger:                                            │
│   ☑ D-level >= [3 ▼]                                         │
│   ☑ Environment type: [production ▼]                         │
│   ☐ Specific environment: [hetzner-prod-1 ▼]                 │
│   ☑ Project type: [public_products, customer_facing]         │
│                                                              │
│  Approval requirements:                                      │
│   ☑ Requires explicit click (no quick-tap)                   │
│   ☑ Requires biometric (mobile)                              │
│   ☐ Requires master password re-entry                        │
│   ☑ Show context: what's being deployed                      │
│   ☑ Show consequences: what changes after approval           │
│   ☑ Show alternatives: rejection paths                       │
│   ☑ Display estimated impact (cost, time, users affected)    │
│                                                              │
│  Approval channels:                                          │
│   ☑ In-app modal                                             │
│   ☑ Mobile push (z biometric required)                       │
│   ☑ Email z deep-link                                        │
│   ☐ Slack interactive message                                │
│   ☐ SMS confirmation code                                    │
│                                                              │
│  Timeout:                                                    │
│   ☑ Use autonomy preset timeout                              │
│   ☐ Custom timeout: [60 min ▼]                               │
│   Action po timeout: [Pause project, await operator ▼]       │
│                                                              │
│  Bypass conditions (rzadko, tylko advanced):                 │
│   ☐ Allow operator-pre-approved batch (e.g., "approve all    │
│       D3 deploys for next 4h")                               │
│   ☐ Allow team approval (jeśli Team Lead profile)            │
│                                                              │
│  Audit:                                                      │
│   ☑ Log każdą approval z full context                        │
│   ☑ Log każdą rejection z reason                             │
│   ☑ Log każdy timeout                                        │
│   ☑ Tamper-evident hash chain                                │
│                                                              │
│  [Save changes]  [Reset to default]  [Disable this gate]     │
└──────────────────────────────────────────────────────────────┘
```

### 5.6.4. Dodawanie custom hard gate

```
┌──────────────────────────────────────────────────────────────┐
│  Add Custom Hard Gate                                        │
│                                                              │
│  Gate name: [ Email blast > 100 recipients              ]    │
│                                                              │
│  Description:                                                │
│  [ Operator approval wymagany przed mass email             ] │
│  [ wysłanym do >100 customers (anti-spam protection)      ]  │
│                                                              │
│  Trigger condition:                                          │
│  [● Action-based] [○ Threshold-based] [○ Custom expression]  │
│                                                              │
│   When action: [send_email ▼]                                │
│   With parameter: recipients_count > [100 ▼]                 │
│                                                              │
│  Approval flow:                                              │
│   ☑ Show recipients preview (first 10 + count)               │
│   ☑ Show email content preview                               │
│   ☑ Require explicit "I confirm sending to X recipients"     │
│   ☑ 60-second cooldown przed approval (anti-mistake)         │
│                                                              │
│  Timeout: [30 min ▼]                                         │
│  Action po timeout: [Cancel email send ▼]                    │
│                                                              │
│  Channels: [● All channels (email blocking is critical)]     │
│                                                              │
│  D-level applicability:                                      │
│   ☑ All D-levels (this gate matters always)                  │
│                                                              │
│  Test gate:                                                  │
│   [Run dry-test (simulate trigger)]                          │
│                                                              │
│  [Cancel]  [Save custom gate]                                │
└──────────────────────────────────────────────────────────────┘
```

### 5.6.5. Hard gate UX (P5.10=d adaptive per gate type)

Każdy hard gate ma adaptive approval modal based on type:

#### Standard deploy gate (minimal-medium)

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Hard Gate — Production Deploy Approval                   │
│                                                              │
│  Project: Sylion Tailor                                      │
│  Action: Deploy build_id:abc123 to hetzner-warsaw-1          │
│                                                              │
│  Quick context:                                              │
│   ✓ All tests passed (84% coverage)                          │
│   ✓ Security scan clean                                       │
│   ✓ Cost within budget ($42 / $80)                           │
│                                                              │
│  [Approve]  [Reject]  [Snooze 15 min]                        │
└──────────────────────────────────────────────────────────────┘
```

#### Security incident gate (detailed)

```
┌──────────────────────────────────────────────────────────────┐
│  🚨  Hard Gate — Security Incident Response                  │
│                                                              │
│  Severity: HIGH                                              │
│  Detected: 14:32:08 (3 min ago)                              │
│                                                              │
│  ─── INCIDENT DETAILS ──────────────────────────────────────│
│  Type: Suspicious activity on edge device                    │
│  Device: rpi-pos-store-warsaw-1                              │
│  Customer: Retail Store (chain)                              │
│                                                              │
│  Symptoms:                                                   │
│   • Unusual outbound traffic (850 GB w 48h)                  │
│   • New process: cryptominer-style behavior                  │
│   • Outbound do mining pools                                 │
│   • SSH login attempts from unknown IP                       │
│                                                              │
│  Likely cause: Cryptojacking / device compromise             │
│                                                              │
│  ─── PROPOSED RESPONSE ─────────────────────────────────────│
│  Immediate actions (require approval):                       │
│   1. Isolate device from network                             │
│   2. Snapshot current state (forensic)                       │
│   3. Notify customer + provide incident report               │
│   4. Initiate device wipe + redeployment                     │
│                                                              │
│  Estimated downtime for customer: 2-4 hours                  │
│  Cost impact: $50-200 (replacement SD card + shipping)       │
│                                                              │
│  ─── APPROVAL OPTIONS ──────────────────────────────────────│
│                                                              │
│  [● Approve full response (recommended)]                     │
│      All 4 actions executed                                  │
│                                                              │
│  [○ Approve partial — only isolate]                          │
│      Action 1 only, decide rest after investigation          │
│                                                              │
│  [○ Reject — operator handles manually]                      │
│      No automated response, operator takes over              │
│                                                              │
│  ⚠ Timeout: 5 minutes (security urgency)                     │
│  ⚠ Auto-action po timeout: ISOLATE (safety default)          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

#### Routine cost gate (minimal)

```
┌────────────────────────────────────────────────┐
│  💰  Hard Gate — Cost Spike                    │
│                                                │
│  Single call cost: $5.20 (limit: $5.00)        │
│  Project: Sylion Tailor                        │
│  Operation: Council deliberation round 3       │
│                                                │
│  [Approve]  [Reject]                           │
└────────────────────────────────────────────────┘
```

---

## 5.7. Multi-color inheritance map (P5.5=d)

### 5.7.1. Visualization

Po skonfigurowaniu, operator widzi **multi-color map** pokazujący skąd
każdy level się pochodzi:

```
┌──────────────────────────────────────────────────────────────┐
│  Autonomy Inheritance Map                                    │
│                                                              │
│  Project: Sylion Tailor v3 (Faza 23 — Council Deliberation)  │
│                                                              │
│  Effective autonomy:                                         │
│                                                              │
│  ████ ████ ████ ████ ████ ████ ████ ████ ████ ████          │
│  L2   L2   L1   L2   L2   L4   L1   L0   L2   L2           │
│  D1   D2   D3   D4   D5   D6   D7   D8   D9   D10           │
│                                                              │
│  Inherited from:                                             │
│   ████ Phase 4 default (Production preset)  — 6 dimensions   │
│   ████ Phase 5 override (operator custom)   — 2 dimensions   │
│   ████ Phase 17 project override            — 1 dimension    │
│   ████ Phase 23 round override              — 1 dimension    │
│   ████ Hard gate (always L0)                — 1 dimension    │
│                                                              │
│  ─────────────────────────────────────────                   │
│                                                              │
│  Per-dimension breakdown:                                    │
│                                                              │
│  DIM-1 Council Form     L2  ████ Phase 4 (Production)        │
│  DIM-2 Voting           L2  ████ Phase 4 (Production)        │
│  DIM-3 Cost             L1  ████ Phase 4 (Production preset) │
│  DIM-4 Model            L2  ████ Phase 5 override (was L1)   │
│  DIM-5 Environment      L2  ████ Phase 4 (Production)        │
│  DIM-6 Skill            L4  ████ Phase 5 override (was L2)   │
│  DIM-7 Quality          L1  ████ Phase 17 project (was L2)   │
│  DIM-8 Deploy           L0  ████ Hard gate (always L0)       │
│  DIM-9 Mid-flight       L2  ████ Phase 4 (Production)        │
│  DIM-10 Cascade         L2  ████ Phase 23 round override     │
│                                                              │
│  ─────────────────────────────────────────                   │
│                                                              │
│  Override actions:                                           │
│   [Reset all to Production preset]                           │
│   [Reset specific dimension]                                 │
│   [Save current state as new preset]                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.7.2. Color legend

```
████ Phase 4 default          (most stable, hardest to lose)
████ Phase 5 override         (operator's general preference)
████ Phase 17 project override (per-project tweak)
████ Phase 22-23 session override (per-session experiment)
████ Hard gate (locked L0)    (cannot be overridden)
```

### 5.7.3. Inheritance trace

Operator może click na konkretny dimension żeby zobaczyć **full trace**:

```
┌──────────────────────────────────────────────────────────────┐
│  DIM-7 Quality Verdicts — Full Inheritance Trace             │
│                                                              │
│  Effective: L1 (Notify only)                                 │
│                                                              │
│  Trace:                                                      │
│                                                              │
│  ╔══════════════════════════════════════════════════════╗   │
│  ║ Phase 4 default        L2 (Balanced)                 ║   │
│  ║ Source: Production preset                            ║   │
│  ║ Why: Production projects need balanced quality       ║   │
│  ║ Modified: 2026-04-29 14:30                           ║   │
│  ╚══════════════════════════════════════════════════════╝   │
│                            ↓ overridden                       │
│  ╔══════════════════════════════════════════════════════╗   │
│  ║ Phase 5 override       (no override at this level)   ║   │
│  ╚══════════════════════════════════════════════════════╝   │
│                            ↓ inherits                         │
│  ╔══════════════════════════════════════════════════════╗   │
│  ║ Phase 17 project       L1 (Notify) ← OVERRIDE        ║   │
│  ║ Source: Operator decision dla Sylion Tailor v3       ║   │
│  ║ Why: "Customer uses production daily, dodatkowy      ║   │
│  ║       review test results"                           ║   │
│  ║ Set on: 2026-04-25 10:14                             ║   │
│  ║ Author: robert.k                                     ║   │
│  ╚══════════════════════════════════════════════════════╝   │
│                            ↓ no further override              │
│  ╔══════════════════════════════════════════════════════╗   │
│  ║ Effective: L1                                         ║   │
│  ╚══════════════════════════════════════════════════════╝   │
│                                                              │
│  Actions:                                                    │
│  [Revert Phase 17 override (go back to L2)]                  │
│  [Make this project-permanent]                               │
│  [Apply L1 do all similar projects]                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 5.8. Time-bounded overrides + per-dimension cascade (P5.12=d)

### 5.8.1. Override scopes

Operator może override per-dimension na różnych poziomach z różnym
czasem trwania:

```
┌──────────────────────────────────────────────────────────────┐
│  Override Scopes                                             │
│                                                              │
│  Scope               Duration              Applies to        │
│  ──────────────────  ──────────────────  ────────────────  │
│  Per-decision        Single decision      Current decision   │
│  Per-round           Council round        All decisions in   │
│                                            this round         │
│  Per-phase           Phase execution      All decisions in   │
│                                            this phase         │
│  Per-build           Build cycle          All decisions in   │
│                                            this build         │
│  Per-project         Until project closed All decisions in   │
│                                            this project       │
│  Per-workspace       Permanent (until    All projects in    │
│                       operator changes)    this workspace     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.8.2. Override creation UX

Operator can create override z dowolnego punktu:

```
─────────────────────────────────────────────────────────────
  Quick override (right-click menu na dimension)
  
  DIM-3 Cost Decisions: L1 → L4
  
  Scope:
   [● Per-decision] (default — minimum scope)
   [○ Per-round]
   [○ Per-phase]
   [○ Per-build]
   [○ Per-project (faza 17)]
   [○ Per-workspace permanent]
  
  Reason (optional, recommended dla audit):
   [Quick experiment, want to see if cheaper models work       ]
  
  Save reminder?
   ☑ Notify me at end of scope (reminder of override)
   ☑ Audit log entry z reason
  
  [Apply override]  [Cancel]
─────────────────────────────────────────────────────────────
```

### 5.8.3. Override expiration

```
Active overrides — Sylion Tailor v3

  Override                Scope            Expires
  ─────────────────────  ──────────────  ───────────────────
  DIM-3 L1 → L4           Per-build       Build complete (5h)
  DIM-7 L2 → L1           Per-project     Project closed
  DIM-6 L2 → L4           Per-decision    EXPIRED (executed)
  DIM-1 standard preset   Per-workspace   Permanent
  
  Reminders:
   ⚠ DIM-3 L4 (cheaper models) expires in 5h
     Prepare to revert to L1?
     [Extend by 24h]  [Make permanent]  [Let expire]
```

---

## 5.9. Edge Cases (P5.11=b — 22 cases)

22 cases w 5 kategoriach.

### Kategoria A — Inheritance conflicts (5 cases)

#### EC-A1: Override vs hard gate conflict

**Trigger**: Operator tries to override DIM-8 Deploy Auth z L0 do L4.
But DIM-8 jest hard-gated dla D4+ projektów.

```
✗ Cannot override — Hard gate applies

  Project D-level: D4
  Hard gate: "Deploy to production" enabled dla D3+
  
  Wymaganie: DIM-8 L0 (always manual) dla deploys do prod
  
  Even with override L4, hard gate intercepts.
  
  Options:
   [Disable hard gate (requires reason + audit)]
   [Override DIM-8 only dla non-prod environments]
   [Cancel override]
```

#### EC-A2: Multi-level override conflict

**Trigger**: Phase 5 sets DIM-3 = L2. Phase 17 override L4. Phase 22 round
override L1. Operator confused o which applies.

```
ℹ Override conflict resolution

  DIM-3 — multiple overrides active:
   Phase 4 preset:   L1
   Phase 5 override: L2  (was L1, +1)
   Phase 17 project: L4  (was L2, +2)
   Phase 22 round:   L1  (was L4, -3)
   
  Effective: L1 (most recent override)
  
  Inheritance rule: most recent override wins.
  
  [Show full trace]  [Revert to phase 5 (L2)]
```

#### EC-A3: Operator override expired mid-build

**Trigger**: Operator set DIM-3 → L4 dla per-build scope. Build completes.
Override expires. Mid-build re-deploy attempt — system uses L1 (default).
Operator confused why behavior changed.

```
ℹ Override expired

  DIM-3 override (L4) expired po build completion.
  System now using L1 (Phase 4 default).
  
  Effects on next operations:
   • Next call won't auto-switch to cheaper model
   • Operator will see notifications dla cost decisions
   • Revert to Production preset behavior
  
  Akcje:
   [Re-apply override (extend duration)]
   [Make override permanent]
   [Continue z L1 (default)]
```

#### EC-A4: Goal-driven preset conflict

**Trigger**: Operator goals = public_products + research. Different
mappings. Phase 4 z most-conservative-wins → Production preset. But
operator chce Research-style cost decisions.

```
⚠ Multi-goal mapping conflict

  Goals: public_products + research
  
  Goal mappings:
   public_products → Production (Conservative cost decisions L1)
   research        → Research (Aggressive cost decisions L5)
  
  Most-conservative wins: L1 active.
  
  Operator's intent (z conversation): wants L5 cost decisions
  
  Options:
   [Override DIM-3 do L5 (per-workspace permanent)]
       Effective: cost autonomy zachowuje się jak Research preset
   [Switch goal mapping rule do "most-aggressive wins"]
       Affects all dimensions, not just DIM-3
   [Custom preset z mixed levels]
       Define new preset matching operator's exact intent
   [Keep L1, accept slower cost decisions]
```

#### EC-A5: Inheritance broken by partial restore

**Trigger**: Operator restored fazy 4 z backup (older). Phase 5 customizations
zostały (newer). Inheritance pattern broken.

```
⚠ Inheritance state inconsistent

  Phase 4 (restored from 30d backup):
   • Production preset (default cost = L1)
  
  Phase 5 (current, newer):
   • Override DIM-3 = L2 (relative to old preset that had L1)
   • But preset values may have changed since override
  
  Resolution:
   [Re-establish overrides relative to restored preset]
       System recalculates each override
   [Reset all Phase 5 overrides]
       Use pure preset values
   [Keep current Phase 5, accept inconsistency]
       Some overrides may not behave as expected
```

### Kategoria B — Hard gate edge cases (5 cases)

#### EC-B1: Hard gate timeout during operator absence

**Trigger**: Production deploy hard gate. Operator on vacation. Mobile
notifications missed. Timeout: pipeline pauses indefinitely.

```
⚠ Hard gate timeout

  Gate: Deploy do production
  Project: Sylion Tailor v3
  Created: 2026-04-29 14:32
  Timeout: 60 min
  Now: 2026-04-29 18:14 (3.6h past timeout)
  
  Pipeline status: PAUSED
  
  Operator activity:
   • Last seen: 2026-04-25 (4 dni temu)
   • Vacation flag: NOT set
   
  Possible scenarios:
   • Operator unaware (mobile notification missed)
   • Operator ill / unable to respond
   • Mobile device dead/lost
  
  System actions:
   ✓ Notification sent every 30 min
   ✓ Email + SMS (3x)
   ⏸ Pipeline waits indefinitely (Production preset behavior)
  
  Manual actions:
   [Try alternate contact method]
   [Cancel deployment (rollback to safe state)]
   [Continue waiting]
```

#### EC-B2: Hard gate approval z mobile auth fail

**Trigger**: Operator tries to approve hard gate na mobile, but biometric
fails (Face ID nie działa, palec mokry). Falls back na master password
prompt — also fails.

```
✗ Mobile authentication failed

  Hard gate: Deploy to production
  
  Authentication attempts:
   • Face ID: 3x failed (sunlight glare)
   • Touch ID: 5x failed (wet finger)
   • Master password: 3x failed (operator typing wrong)
  
  Status: Mobile temporarily locked
  Wait: 5 min before next attempt
  
  Alternative options:
   [Switch to desktop AEIS]
       Approve from desktop (z master password tam)
   [Use recovery seed (mobile)]
       Re-establish auth z 24-word seed
   [Wait 5 min, retry biometric]
```

#### EC-B3: Hard gate approval race (mobile + desktop)

**Trigger**: Operator approves on mobile, partner approves on desktop
simultaneously (split-second). Both clicks register before sync.

```
ℹ Concurrent approval — race resolved

  Hard gate: Deploy to production
  Approvals received:
   • Mobile (robert.k): 14:32:08.234
   • Desktop (anna.k): 14:32:08.241
  
  Winner: Mobile (robert.k) — 7ms earlier
  
  Audit chain entry:
   action: "deploy_approved"
   approved_by: "robert.k"
   device: "mobile"
   concurrent_attempt: "anna.k (desktop, lost race)"
   ts: 2026-04-29 14:32:08.234
```

#### EC-B4: Custom hard gate triggers too often

**Trigger**: Operator added custom gate "approval przed >100 emails". After
running, it triggers every Marketing Council session (which sends weekly
newsletter). Operator gets gate fatigue.

```
ℹ Hard gate frequency analysis

  Custom gate: "Email blast > 100 recipients"
  
  Trigger frequency: 12 times w ostatnich 7 dniach
  Approval rate: 100% (operator always approves)
  Average response time: 2.1 min
  
  Pattern detected: gate triggers dla recurring scheduled emails
  
  Recommendations:
   [Increase threshold do 1000 recipients]
       Less frequent triggers
   [Whitelist recurring "newsletter_weekly" workflow]
       Auto-approve scheduled marketing
   [Convert to notification-only (not hard gate)]
       Operator sees but doesn't approve
   [Disable gate (operator no longer cares)]
```

#### EC-B5: Hard gate disabled accidentally

**Trigger**: Operator disabled hard gate "Deploy to production" w
debugging. Forgot to re-enable. Next prod deploy bypasses safety.

```
⚠ Hard gate disabled — production deploy proceeded without approval

  Gate: "Deploy to production"
  Status: DISABLED (since 2026-04-25)
  Disabled by: robert.k (debugging)
  
  Recent prod deploys:
   2026-04-26: Sylion Tailor v3.2 deployed (no approval) ← unsupervised
   2026-04-27: Customer Acme v1.1 deployed (no approval)
   2026-04-28: Sylion Tailor v3.3 deployed (no approval)
  
  ⚠ 3 production deploys w 4 dniach bez operator approval.
  
  Risk assessment:
   • All deploys passed automated tests ✓
   • No production incidents reported ✓
   • But: no human-in-loop verification
  
  Akcje:
   [Re-enable gate now]  ← STRONGLY RECOMMENDED
   [Audit recent deploys for issues]
   [Keep disabled (operator's call)]
       Note: requires explicit reason in audit chain
```

### Kategoria C — Per-dimension config edge cases (5 cases)

#### EC-C1: DIM-3 (Cost) misconfiguration

**Trigger**: Operator set DIM-3 L5 (fully autonomous). Forgot to set budget
caps. System spent $500 in 1 day before operator noticed.

```
🚨 CRITICAL — Cost autonomy without budget caps

  DIM-3: L5 (Fully autonomous)
  Project budget: NOT SET (defaults to template MEDIUM $80)
  Actual spend last 24h: $487
  Overrun: $407 (508%)
  
  System behavior:
   ✓ Auto-approved every cost decision (per L5)
   ✗ No budget cap enforcement (no template applied)
   ✗ No early warning notifications
  
  Root cause: Operator created project bypassing template selection
  
  Akcje:
   [● Pause all autonomous projects]
       Halt spending immediately
   [Apply emergency budget cap]
       $50 cap, project pauses
   [Investigate unauthorized usage]
       Could be misconfig OR operator legitimately needed it
   [Contact AEIS support]
   
  Preventative:
   [Force budget template selection na project creation]
   [Disable DIM-3 L5 dla projects bez explicit budget]
```

#### EC-C2: DIM-7 threshold too restrictive

**Trigger**: Operator's DIM-7 threshold: "auto-accept jeśli coverage >
95%". But 95% jest hard to achieve. Operator review required dla every
project.

```
ℹ DIM-7 threshold analysis

  Current threshold: coverage > 95% AND failed = 0
  
  Project history (last 20 projects):
   • Met threshold: 2 projects (10%)
   • Required operator review: 18 projects (90%)
  
  Operator review pattern:
   • All 18 reviews approved without changes
   • Average review time: 4 min
   • Total operator time: 72 min spent reviewing
   
  Recommendation: relax threshold
   Suggested: coverage > 80% AND failed < 3
   Estimated new auto-accept rate: 75%
   Time saved: ~50 min per 20 projects
   
  [Apply suggested threshold]
   [Keep current strict threshold]
   [Customize manually]
```

#### EC-C3: DIM-9 mid-flight override complexity

**Trigger**: Conservative preset DIM-9 = full control. Operator constantly
interferes mid-build, breaking pipeline state.

```
⚠ DIM-9 mid-flight overrides causing issues

  Preset: Conservative (L0, full control)
  
  Recent build attempts:
   ✗ Build #1: aborted by operator (changed Council mid-deliberation)
       Result: state inconsistent, restart required
   ✗ Build #2: aborted (operator edited Księgę mid-build)
       Result: workers crashed, partial state
   ✗ Build #3: completed (operator hands-off)
       Result: success
  
  Pattern: operator interventions caused 2/3 failures
  
  Recommendations:
   [Switch DIM-9 do L2 (Balanced)]
       Limits real-time interference
       Some changes require build complete
   [Add "Confirm action" prompts dla mid-flight changes]
       Operator double-checks consequences
   [Keep L0 ale add safety constraints]
       e.g., "no edit Księgi after Council finalize"
```

#### EC-C4: Cross-dimension dependency

**Trigger**: Operator set DIM-4 (Model selection) L5, ale DIM-3 (Cost)
L0. Conflict: DIM-4 L5 może wybrać expensive model, DIM-3 L0 wymaga
operator approval per call.

```
⚠ Cross-dimension dependency conflict

  DIM-3 (Cost):           L0 (Always manual)
  DIM-4 (Model selection): L5 (Fully autonomous)
  
  Conflict: System auto-selects model, ale każdy call wymaga cost approval.
  
  Effective behavior:
   • System chooses claude-opus (per DIM-4 L5)
   • Cost decision triggered (per DIM-3 L0)
   • Operator gets prompt: "Approve $0.84 dla claude-opus?"
   • Operator must approve EACH call individually
  
  Result: pipeline 50x slower than expected, operator overwhelmed
  
  Resolution options:
   [Align dimensions (both L2-L3)]
       System auto-selects + auto-approves routine costs
   [Lower DIM-4 to L2]
       System uses preferred model, skips alternates
   [Raise DIM-3 to L3]
       System auto-approves cost decisions, model selection autonomous
   [Use auto-conflict-detector]
       AEIS suggests level pairs that work together
```

#### EC-C5: Per-D-level adaptive levels confusing

**Trigger**: Operator set DIM-7 z per-D-level adaptive (D1=L4, D5=L0). New
project D3 — operator unsure what level applies.

```
ℹ Per-D-level adaptive — DIM-7

  Current configuration:
   D1: L4 (auto with sampling)
   D2: L3 (auto with audit)
   D3: L2 (balanced)  ← project's D-level
   D4: L1 (notify)
   D5: L0 (manual)
  
  Project: Sylion Tailor v3
  Project D-level: D3
  Effective level: L2
  
  Why D3 → L2:
   D3 = standard production project
   Balanced auto/manual mix appropriate
   
  [Override for this project (use L1 dla extra caution)]
   [Accept L2]  [View full table]
```

### Kategoria D — Wizard / setup issues (4 cases)

#### EC-D1: Operator picks wizard but skips most steps

**Trigger**: Operator started wizard (10 steps), skipped 8/10. Faza 5
config incomplete.

```
ℹ Phase 5 wizard incomplete

  Wizard mode: 10-step wizard
  Steps completed: 2/10
  Steps skipped: 8/10
  
  Effective autonomy:
   • Configured by you: DIM-1 (L3), DIM-2 (L2)
   • Inherited from preset: DIM-3, DIM-4, ... DIM-10
   • Hard gates: 18 baseline (no custom)
  
  Recommended:
   [Continue wizard from step 3]
       Configure remaining 8 dimensions
   [Switch to sliders mode]
       Faster overview of all 10
   [Accept current config (mostly preset)]
       Most dimensions inherited from Phase 4
```

#### EC-D2: Operator misunderstands "L4 vs L5"

**Trigger**: Operator set everything L5 thinking it means "advanced
operator". Actually means "fully autonomous". Operator wakes up po 1
projekcie z surprise.

```
⚠ Autonomy understanding check

  You set 8/10 dimensions to L5 (Fully autonomous).
  
  L5 means: AEIS operates without operator intervention.
  Hard gates still apply, but routine decisions auto.
  
  Did you intend this?
  
  Your project history suggests:
   • You typically interact 8-15 times per project (Balanced)
   • Last project: 12 operator interactions
   • L5 expects 0-2 interactions per project
  
  Risk:
   • You may miss important context
   • Decisions may not match your preferences
   • Cost overruns possible (no operator catch)
  
  Recommendations:
   [Lower most dimensions do L2-L3]
       Maintain visibility, less manual work
   [Keep L5, monitor carefully first 3 projects]
       Aggressive but observed
   [Read full L5 documentation]
       Understand consequences before continuing
```

#### EC-D3: Wizard advisor missing context

**Trigger**: Wizard advisor shows generic recommendations. Operator z
specific industry (e.g., medical) — needs HIPAA-specific guidance not
covered by advisor.

```
ℹ Industry-specific guidance not available

  Your project: Healthcare app dla clinic
  Advisor recommendations: generic (no HIPAA-specific)
  
  Manual considerations:
   • DIM-3 Cost: HIPAA budget approvals may need additional approval
   • DIM-7 Quality: PHI handling tests required (extra strict)
   • DIM-8 Deploy: HIPAA-compliant cloud only
   • Hard gates: add "PHI processing approval" custom gate
  
  Resources:
   [HIPAA compliance template (community-contributed)]
   [Healthcare best practices documentation]
   [Request AEIS team review for industry-specific template]
```

#### EC-D4: Sliders mode disorienting (too much info)

**Trigger**: Operator wybrał sliders mode. 10 sliders + dependency tracking
+ real-time preview = overwhelming. Operator wants simpler.

```
ℹ Wizard mode complexity

  You've been on sliders screen for 35 min.
  Average operator finishes in 15 min.
  
  Switch to simpler mode?
   [Switch to wizard (10 steps z explanations)]
   [Switch to matrix (compare presets)]
   [Switch to quick (use Production preset)]
   [Continue z sliders]
   [Save partial progress, take break]
```

### Kategoria E — Recovery / migration (3 cases)

#### EC-E1: Workspace import — autonomy state mismatch

**Trigger**: Operator imports workspace z previous machine. Phase 5 custom
overrides reference dimensions/levels not present w current AEIS version
(updated since export).

```
⚠ Workspace import — autonomy compatibility

  Imported workspace: AEIS v2.8 (older)
  Current AEIS:        v3.1
  
  Compatibility issues:
   ✗ DIM-7 sub-options: 3 options removed in v3.0
       Your override using removed option "test_security_findings_zero"
   ✓ Hard gates: 17/18 baseline match (1 renamed)
   ✗ Custom preset "Old Production": uses removed dimensions
  
  Resolution:
   [Auto-migrate (system maps old → new)]
       Best-effort, may not preserve exact intent
   [Reset autonomy to defaults]
       Lose all customizations, start fresh
   [Manual review per setting]
       Operator decides for each conflict
```

#### EC-E2: Backup restore breaks active overrides

**Trigger**: Operator restored Phase 5 z backup. Active per-project
overrides (Phase 17) still reference old Phase 5 state. Conflict.

```
⚠ Restore conflict — active per-project overrides

  Phase 5 (restored): different dimension levels
  Active Phase 17 overrides: 5 projects still use old Phase 5 references
  
  Affected projects:
   • Sylion Tailor v3 (DIM-3 override relative do old L1)
   • Customer Acme Pilot (DIM-7 override relative do old L2)
   • Internal Dashboard (3 dimensions)
   • Tutorial CRM (1 dimension)
   • PKB v2 (2 dimensions)
  
  Resolution per project:
   [Auto-recalculate overrides (best effort)]
   [Reset overrides do new Phase 5 defaults]
   [Manual review]
```

#### EC-E3: Custom hard gate definition lost

**Trigger**: Operator's custom hard gate defined complex condition. AEIS
update removes the function used in condition. Gate stops working.

```
⚠ Custom hard gate broken

  Gate: "Cost spike > $X w 1 hour"
  Condition: depends on `cost_spike_window` function
  
  Issue: `cost_spike_window` removed in AEIS v3.0
  Replacement: `cost_threshold_check` (different signature)
  
  Resolution:
   [Auto-migrate to new function]
       System rewrites condition with closest match
   [Manual rewrite gate condition]
       Operator updates definition
   [Disable gate temporarily]
       Operator handles manually
   [Use replacement built-in gate]
       AEIS may have similar baseline gate
```

---

## 5.10. Inheritance + Acceptance Criteria + DoD

### 5.10.1. Inheritance pattern (P5.12=d full cascade)

Per-dimension cascade z time-bounded scopes:

```
Per-dimension chain (using DIM-3 jako example):

  Phase 4 default:       L1 (Production preset)
   ↓
  Phase 5 override:      L2 (operator preference)
   ↓
  Phase 17 project:      L4 (per-project override)
   ↓
  Phase 22 round:        L1 (per-round override)
   ↓
  Real-time decision:    L0 (operator manual override dla single decision)

Each scope has:
  • Time-bound (when expires)
  • Reason (logged for audit)
  • Override count (how many times overridden in workspace)
  • Author (who set it)
```

### 5.10.2. Acceptance Criteria — DoD

#### Wspólne (zawsze wymagane)

```
✓ Operator zrozumiał 10 wymiarów (z explanation lub wizard)
✓ Operator zrozumiał semantykę L0-L5
✓ Hard gates baseline reviewed (akceptowane lub modyfikowane)
✓ Audit chain entry: phase_5.complete
```

#### Customization (jeśli operator nie skipped)

```
✓ Per-dimension levels customized (lub explicitly accepted preset)
✓ Custom hard gates added (lub operator explicit "no custom needed")
✓ Inheritance behavior tested (sample project z visible inheritance trace)
```

#### Adaptive per goal

```
Goal "public_products":
  ✓ DIM-8 (Deploy) z hard gate dla production
  ✓ DIM-7 (Quality) z notify minimum
  
Goal "cybersecurity":
  ✓ Most dimensions L0-L1 (manual)
  ✓ Custom security incident hard gate
  ✓ Audit chain extra-strict
  
Goal "research":
  ✓ Most dimensions L3-L5 (autonomous)
  ✓ Cost decisions L4-L5 (experimentation)
  ✓ Quality verdicts L1 (research integrity check)
  
Goal "apps_internal":
  ✓ Standard preset acceptable
  ✓ Custom hard gates rzadko potrzebne
```

### 5.10.3. Soft warnings vs hard blocks

**Hard blocks**:
- All dimensions set to L5 with no hard gates active
- DIM-8 Deploy at L5 dla production environments without hard gate
- Conflicting overrides z circular dependencies

**Soft warnings**:
- DIM-3 (Cost) L4-L5 bez budget cap
- All dimensions same level (operator może chcieć variation)
- No per-D-level adaptive
- No custom hard gates dla industry-specific requirements
- Sliders mode used for >30 min (suggest wizard)

### 5.10.4. Acceptance test (automated)

```bash
$ aeis-cli phase5-acceptance-test

Running Phase 5 acceptance test...

[Common requirements]
[1/4] 10 dimensions configured                       ✓ PASS
[2/4] L0-L5 semantics verified (operator quiz pass) ✓ PASS
[3/4] Hard gates baseline reviewed                  ✓ PASS (18 active)
[4/4] Audit chain entry phase_5.complete            ✓ PASS

[Customization (if applicable)]
[5/7] Per-dimension overrides count                 ℹ INFO (3 overrides)
[6/7] Custom hard gates count                       ℹ INFO (2 custom)
[7/7] Inheritance trace tested                      ✓ PASS

[Goal-specific: public_products + cybersecurity]
[8/12] Production deploy hard gate                  ✓ PASS
[9/12] Quality verdicts ≤ L2 (notify or stricter)   ✓ PASS (L1)
[10/12] Cost decisions z budget cap                 ✓ PASS
[11/12] Security incident hard gate                 ✓ PASS
[12/12] Most dimensions L0-L2 (cybersecurity)        ✓ PASS

DoD: 12/12 ✓
Soft warnings: 0
Hard blocks: 0

Phase 5 ACCEPTED. Ready to proceed to Phase 6 (Coherence Guard).

Recommended pre-Phase-6 actions:
  • None — phase 5 fully configured
```

---

## Status fazy 5

🟢 **Wszystkie sekcje 5.1-5.10 complete**

**Zawiera**:
- ✓ Sense fazy + relacja do fazy 4 (5.1)
- ✓ 10 wymiarów autonomy z full definicją (5.2)
- ✓ L0-L5 semantyka z risk multiplier (5.3)
- ✓ Wizard adaptive (4 modes: quick/sliders/wizard/matrix) (5.4)
- ✓ Per-dimension deep config + per-D-level adaptive (5.5)
- ✓ Hard gates 18 baseline + operator-extensible (5.6)
- ✓ Multi-color inheritance map z trace (5.7)
- ✓ Time-bounded overrides + per-dimension cascade (5.8)
- ✓ Edge cases — 22 cases w 5 kategoriach (5.9)
- ✓ Inheritance + DoD + acceptance test (5.10)

⏳ **Po Twojej akceptacji** → **soft freeze fazy 5** + przejście do **Faza 6 — Coherence Guard** (pierwszy z 5 Guards).
