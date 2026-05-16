# PATCH FAZA 28 — Profile 6 Burst Mode

> **Source**: cherry-pick z MECHA (60 agents subscription tier exploitation)
> **Target**: `26_28_planning_part1.md` sekcja 28.4 (Layer Decomposition)
> **Severity**: HIGH (nowy resource profile)
> **Apply**: dodać po 5 istniejących profiles

---

## Problem

Faza 28.4 ma **5 resource profiles** (Solo budget → Enterprise parallel). Brakuje **6-tego profilu dla burst-mode scenarios** wykorzystującego subscription tier exploitation.

## Add new section 28.4.6

W pliku `26_28_planning_part1.md`, po sekcji "5 Resource Profiles" dodać:

```
## 28.4.6. Profile 6 — Burst Mode (NEW)

### Co to jest

Profile 6 jest **różny od Profiles 1-5**: nie jest dla całego projektu, ale 
**dla specific phases które mogą być burst-paralleled**.

  Profile 1-5: dla całego build (faza 32-36)
  Profile 6: dla single faza burst (faza 22 deliberation, 
             faza 31 dry run, faza 35 specific layers)

### Spec

| Cecha | Wartość |
|---|---|
| Workers | **60 simultaneous** |
| Envs | 1 shared sandbox (Docker isolated) |
| Cost model | **Subscription tier exclusive** (~$0 marginal) |
| Duration limit | **30 minutes hard timeout** |
| Daily limit | 2 bursts/dzień max (60 min total/day) |
| Use case | Research, exploration, parallelizable phases |

### Prerequisites

```yaml
required:
  subscription:
    - Anthropic Max 20x ($200/mo)
    - OR ChatGPT Teams equivalent
    - OR aggregate of multiple subscriptions
  
  technical:
    - Tmux Persistent Sessions (A1) ✓
    - Git Worktrees (A2) ✓  
    - Docker Sandboxing (A3) ✓
    - Prompt Splitting skill (M2) recommended
  
  operator:
    - Confirm understanding "30-min hard limit"
    - Subscription Advisor (W13) verified ROI
    - Project D-level allows (NIE dla customer-facing prod builds)
```

### Use cases — gdzie aktywować

```
✅ FAZA 22 deliberation (per-question swarm):
  Standard: 12 agentów × 19 questions × ~12 min = 3.8h
  Burst Mode: 60 agentów × 19 questions × ~5 min (parallel) = 60-90 min
  Quality: HIGHER (60 perspectives per question vs 12)

✅ FAZA 31 dry run (scaled simulation):
  Standard: 8 tasks symulowanych × 5 min = 40 min
  Burst Mode: 60 tasks symulowanych × 5 min (parallel) = 5 min
  Confidence: dramatycznie wyższa

✅ FAZA 35 specific layers (parallel work):
  Layer 5 unit tests:
    Standard Profile 2: 16 workers × 48h = 48h wallclock
    Burst Mode: 60 agents × ~5h = 5h wallclock
    Time saved: 43h
  
  Layer 2 integrations (parallelizable):
    Standard: 24h sequential
    Burst Mode: 60 agents × ~2h = 2h
    Time saved: 22h

✅ Research / exploration mode (poza standard lifecycle):
  Quick prototype testing
  Complex debugging (60 agents szukają root cause)
  Architecture exploration

❌ NIE używać Burst Mode dla:
  - Customer-facing production builds (audit/compliance overhead)
  - Sequential phases (Layer 0 Foundation, Layer 7 Polish)
  - Tasks wymagające deep coherence between iterations
```

### Workflow

```
Trigger:
  Operator presses Ctrl+Shift+B w faza 22 / 31 / 35
  
Pre-flight check (15 sec):
  ✓ Anthropic Max 20x active
  ✓ Quota remaining > $50 (safety margin)
  ✓ No active burst (only 2x/day max)
  ✓ Docker available (z A3)
  ✓ Tmux server running (z A1)
  ✓ Disk space dla 60 worktrees (z A2)
  ✓ Project allows Burst Mode (D-level, customer policy)
  
  If all green: Burst Mode activated
  Else: AdvisorCard z reason

Execution (T+0 to T+30):
  T+0:    Spawn 60 workers simultaneously (~30 sec)
          Każdy w isolated Docker container + worktree
  T+0:30 - T+30: Active processing
          60 workers process różne angles (z prompt splitting M2)
          Coordinator collects partial results continuously
  T+30: Hard timeout
          Spawn synthesizer agent (1 LLM call)
          Synthesizer aggregates 60 outputs → final result
          Cleanup (worktrees, containers, sessions)

Cost monitoring (real-time):
  Every 1 min: check Anthropic quota remaining
  Every 5 min: log do cost_ledger.jsonl
  If quota < 10%: emit AdvisorCard "approaching quota"
  If quota = 0: HARD HALT
```

### Customer Y CRM "Pro Edition" — z Burst Mode

```
Standard Profile 2 lifecycle:
  Faza 22 deliberation: 3.8h, $9.20
  Faza 31 dry run:      40 min, $0.50
  Faza 35 build:        4.2 weeks, $142.30
  Total relevant:       ~5 weeks, ~$152

Z Burst Mode (Profile 2 outer + Burst dla 22, 31, 35.L5):
  Faza 22 (Burst): 60-90 min, $0 marginal
  Faza 31 (Burst): 5 min, $0 marginal
  Faza 35 (mixed): 2.5 weeks (L5 unit tests Burst), $50
  Total relevant: ~2.7 weeks, ~$50

OUTCOME:
  Time: 5 weeks → 2.7 weeks (-46%)
  Cost: $152 → $50 (-67%)
  Subscription leveraged maximally
```

### Audit chain

```yaml
# New audit chain: burst_mode.jsonl

events:
  burst_initiated:
    timestamp, project_id, faza, num_workers, 
    predicted_duration, subscription_tier
  
  burst_quota_warning:
    timestamp, quota_remaining, action_taken
  
  burst_hard_halt:
    timestamp, reason (timeout/quota/manual), 
    partial_results_count
  
  burst_synthesizer_run:
    timestamp, num_inputs, synthesis_strategy, 
    final_output_size
  
  burst_completed:
    timestamp, duration, num_workers_succeeded, 
    total_cost, subscription_used, quality_metrics
```

### Operator decision matrix

```
Czy aktywować Burst Mode dla projektu?

Customer-funded D4 z deadline pressure:
  ☑ Burst Mode dla faza 22 (operator's time = customer waiting)
  ☑ Burst Mode dla Layer 5 unit tests (parallelizable)
  ☐ Burst Mode dla Layer 0/1/7 (sequential, nie pomaga)
  
Customer-funded D3 standard:
  ☑ Burst Mode dla faza 22 (saves operator time)
  ☐ Burst Mode dla build (Profile 2 sufficient)
  
Internal R&D project:
  ☑ Burst Mode dla wszystkich exploration phases
  ☑ Burst Mode dla rapid prototyping
  
Polish gov-funded customer:
  Operator decision: zależne od customer requirements
  Some customers prefer standard process (audit trail z 9-rolowej Council)
  Burst Mode adds 60-perspective enrichment, ale enrichments may overwhelm audit
  Recommendation: ASK customer
```

## Audit chain entry

```json
{
  "patch_id": "patch_phase_28_profile_6_burst_v1",
  "applied_to": "26_28_planning_part1.md",
  "section": "28.4 Layer Decomposition",
  "added": "Profile 6 Burst Mode subsection 28.4.6",
  "source_inspiration": "MECHA (JoePro AI) + AoE (njbrake)",
  "verified_against": "Customer Y CRM Pro Edition simulation",
  "signature": "ed25519:..."
}
```

## Co operator rozumie po patchu

1. **6 resource profiles** zamiast 5 — Profile 6 jest specjalny (per-faza, nie cały projekt)
2. **Burst Mode wykorzystuje subscription tier maximally** — ~$0 marginal cost
3. **30-min hard timeout** — nie ma sustained 60-agent operation
4. **Customer Y CRM Pro Edition example** — pokazuje real impact (10.5 → 6 tyg)
5. **Operator decision matrix** — kiedy aktywować, kiedy nie
