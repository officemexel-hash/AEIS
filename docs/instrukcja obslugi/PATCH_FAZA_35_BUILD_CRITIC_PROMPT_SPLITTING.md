# PATCH FAZA 35 — Build Critic + Prompt Splitting

> **Source**: cherry-pick z MECHA (M2, M3) + Agent of Empires
> **Target**: `34_36_execution_part2.md` sekcja 35 (Build Orchestration)
> **Severity**: HIGH (jakość build + bug detection)
> **Apply**: dodać dwie nowe sekcje 35.X i 35.Y

---

## Problem

Faza 35 dziś:
- **Workers każdy generuje pojedynczą implementację** (single perspective)
- **Brak continuous review** — bugi łapane dopiero w faza 37 (10x cost)
- **NF4 sigma-style errors** mogą przejść przez wszystkie warstwy

## Add new section 35.X — Build Critic Continuous Agent (M3)

```
## 35.X. Build Critic — Continuous Adversarial Review (M3)

### Co to jest

W3 Council Hybrid ma "Critic" rolę dla decyzji architektonicznych (faza 22).
Build Critic jest **rozszerzeniem** dla runtime build phase:
  - Spawned at faza 35 start
  - Continuous review of worker commits
  - Catches errors before quality gates (faza 37)

### Spec

```yaml
build_critic:
  role: continuous adversarial reviewer w faza 35
  spawn: at faza 35 start (after Build Initialization)
  lifetime: throughout build phases
  
  model: claude-opus-4-7 (premium dla deep reasoning)
  cost_tier: subscription preferred (continuous = high call volume)
  budget: $50/build hard cap (Cost Guard)
  
  responsibilities:
    1. Review każdy commit od workers w runtime
    2. Cross-check z Księga (W5 SoT) dla drift
    3. Validate hyper-parameters (NF4 sigma-style errors)
    4. Detect groupthink (gdy wszyscy workers zgadzają się szybko)
    5. Challenge architectural decisions mid-build
    6. Identify scope creep attempts
    7. Domain-specific checks (KSeF, GDPR, security)
  
  authority:
    - CANNOT block builds (advisory power)
    - CAN escalate do operator (hard gate)
    - CAN trigger faza 34 reconvene
    - CAN emit AdvisorCards (W13)
```

### Continuous workflow

```
Every 5 minutes:
  1. Pull recent commits z all worker worktrees
  2. Diff analysis (what changed)
  3. Reasoning (LLM call): "Is this correct? Any concerns?"
  4. Output:
     PASS: log finding, continue
     WARNING: emit AdvisorCard
     CONCERN: emit AdvisorCard z hard gate flag
     BLOCKER: emit AdvisorCard + escalation

Every 30 minutes:
  Holistic review: are workers heading right direction?
  Drift detection: still aligned z Księga?
  Synthesis: any patterns emerging that worry?
  Operator dashboard update

Per worker commit:
  Targeted analysis: this specific code change
  Domain-specific checks (z faza 18 risks register)
  Cross-reference z similar past projects (calibration)
  Output: line-level findings (jeśli applicable)
```

### Domain-specific checks

```
Stripe-specific:
  - Webhook signature verification present?
  - PCI scope minimization respected?
  - Idempotency keys used?
  - Error handling robust?

KSeF-specific:
  - Polish identifier validation?
  - XML format compliance?
  - Signature handling correct?
  - Sandbox vs production endpoint switch?

GDPR:
  - PII handling correct?
  - Data minimization respected?
  - Audit logs avoid PII?

Security:
  - Auth/authz on every endpoint?
  - SQL injection guards?
  - XSS prevention?
  - Secret management (no hardcoded keys)?

Performance:
  - N+1 queries avoided?
  - Caching where appropriate?
  - Resource cleanup correct?

Polish localization:
  - All user-facing strings i18n-ed?
  - Polish character handling correct?
  - Date/currency formats Polish?
```

### Customer Y CRM example

```
Day 12, Worker 1 commits Stripe webhook:

Build Critic review (5 min later):
  Diff analyzed: src/webhooks/stripe.py (47 lines)
  
  Findings:
    ❌ BLOCKER: Webhook signature verification missing
       Line 12-15: payload accepted without verification
       Risk: Anyone can spoof Stripe events
       OWASP A02 violation
       Fix needed before merge to main
    
    ⚠️ WARNING: No idempotency key handling
       Stripe may send duplicate events
       Fix: deduplicate via stripe_event_id
    
    ✓ Good: Error logging structured
    ✓ Good: GDPR-compliant (no PII w logs)
  
  AdvisorCard emit (W13):
    Type: build_critic_finding
    Severity: BLOCKER
    Hard gate: true
    
    Options:
      [Auto-fix worker 1] (cost: $0.50, time: 10 min)
      [Pause Worker 1, manual review]
      [Continue z risk acceptance (NIE recommend)]
  
  Operator chooses auto-fix.
  Worker 1 fixes signature verification.
  Build Critic re-reviews → PASS.
  Audit chain: build_critic_finding_resolved
```

### Audit chain

```yaml
# New audit chain: build_critic_findings.jsonl

events:
  build_critic_spawned: timestamp, project_id, faza
  build_critic_review: timestamp, commit, worker_id, findings_count
  build_critic_finding: timestamp, severity, description, recommendation
  build_critic_advisor_card: timestamp, card_id, hard_gate
  build_critic_resolved: timestamp, finding_id, resolution_action
```
```

## Add new section 35.Y — Prompt Splitting Capability (M2)

```
## 35.Y. Prompt Splitting — Multi-perspective Task Generation (M2)

### Co to jest

Standard mode: 1 worker = 1 implementation per task (single perspective)
Prompt splitting mode: 1 task → N variants z różnymi cognitive angles
                       → synthesizer picks best lub merges

### Activation

Operator config (per task lub per faza):
  Standard mode (default): 1 implementation per task
  Prompt splitting mode: 5-15 variants per task
  Burst mode (z Profile 6): 30-60 variants per task

Auto-suggest by AdvisorCard:
  When task complexity > threshold:
    "Task X is complex (D4 + 3 compliance areas).
     Recommend prompt splitting (8 variants, $3.20)?
     Estimated quality boost: 30%."

### Cognitive angles available

```
DEFENSIVE: paranoid error handling, fail safely
FUNCTIONAL: pure functional style, no side effects
EVENT_SOURCING: append-only event log pattern
LITERATURE_REVIEW: survey top 10 industry approaches 2026
EDGE_CASES: enumerate 50+ failure modes
SECURITY: OWASP Top 10 perspective, CVE-grade scrutiny
TESTING_STRATEGY: comprehensive test plan
PERFORMANCE: optimize dla throughput
UX_PERSPECTIVE: user experience implications
ACCESSIBILITY: WCAG 2.1 AA implications
POLISH_LOCALIZATION: Polish-specific concerns
KSEF_COMPLIANCE: KSeF integration impact
GDPR_PRIVACY: data privacy implications
CRITIC: adversarial — challenge wszystkie założenia
SYNTHESIZER: best of all approaches, integrate strengths
```

### Workflow

```
For complex task (e.g., "Implement Stripe webhook"):
  
  Operator decision: prompt splitting mode (8 variants)
  
  Spawn 8 variants z prompt_splitter skill:
    Variant 1 (DEFENSIVE): paranoid checks
    Variant 2 (SECURITY): OWASP A02 focus
    Variant 3 (EDGE_CASES): 35 failure modes
    Variant 4 (KSEF_COMPLIANCE): Polish KSeF integration
    Variant 5 (GDPR_PRIVACY): minimal PII logging
    Variant 6 (PERFORMANCE): async, batching
    Variant 7 (TESTING_STRATEGY): comprehensive tests
    Variant 8 (CRITIC): reviews variants 1-7
  
  Parallel execution (Profile 2 = 2 workers handle 4 variants each):
    Time: 12 min
    Cost: 8 × $0.40 = $3.20 (subscription tier preferred)
  
  Synthesizer phase:
    Synthesizer (claude-opus) reviews wszystkie 8
    Combines:
      Variant 1 defensive structure
      Variant 2 security checks
      Variant 3 edge cases
      Variant 4 KSeF integration
      Variant 5 GDPR practices
      Variant 6 async pattern
      Variant 7 testing approach
    Addresses Variant 8 concerns
    
  Final implementation: comprehensive, multi-faceted
  Quality: 92%+ (vs 70% standard)
  Edge cases caught: ~85% (vs 30% standard)
```

### ROI per complex task

```
Standard mode:
  Cost: $0.40
  Quality: 70%
  Edge cases caught: ~30%
  
Prompt splitting mode:
  Cost: $3.70 (8 × $0.40 + $0.50 synthesizer)
  Quality: 92%+
  Edge cases caught: ~85%
  
Cost-benefit per task:
  +$3.30 cost
  -2-3h re-work prevention (z faza 37)
  -2-3 customer-facing bugs prevented
  Operator's value: $200-300 saved per complex task
  
Net ROI per complex task: +$200-300
```

### Audit chain

```yaml
# Extended audit chain: workflow_engine.jsonl

events:
  prompt_splitting_initiated:
    timestamp, base_task_id, num_variants, angles_used
  
  variant_spawned: timestamp, variant_id, angle, worker_id
  variant_completed: timestamp, variant_id, output, quality_score
  
  synthesizer_run:
    timestamp, num_inputs, synthesis_strategy, output_size
  
  prompt_splitting_completed:
    timestamp, total_cost, total_time, final_quality_score
```
```

## Customer Y CRM Pro Edition — z faza 35 enhancements

```
Standard faza 35 (current AEIS):
  4.2 weeks build
  $142 cost
  ~10 bugs caught w faza 37 (re-work needed)

Z Build Critic + Prompt Splitting (Pro Edition):
  
  Build Critic (continuous):
    Catches 8 of 10 bugs przed faza 37
    Re-work prevented: ~16h
    Cost: $30 (Build Critic continuous calls)
  
  Prompt Splitting dla complex tasks:
    ~10 complex tasks z 8 variants each
    Cost: 10 × $3.70 = $37
    Quality boost: 70% → 92% on those tasks
    Re-work prevented: ~10h
  
  Total faza 35:
    Time: 4.2 weeks → 3.5 weeks (-17%)
    Cost: $142 → $209 (+$67)
    Quality: dramatically higher
    Bugs caught early: 8 vs 0
  
  Faza 37 impact:
    Standard: 7 auto-fixes needed
    Pro Edition: 1-2 auto-fixes needed
    Saved time: ~2h operator review
  
  Net ROI: +$67 cost, save ~26h re-work × $80 = $2080 saved
  Net value per project: +$2000
```

## Audit chain integration

Łączny audit chain dla faza 35 (z patches):
  workflow_engine.jsonl: orchestration events
  build_critic_findings.jsonl: per-finding events
  build_critic_advisor_cards.jsonl: emitted cards
  prompt_splitting.jsonl: variant generation events

## Co operator rozumie po patchu

1. **Build Critic = continuous safety net** — bugi łapane przed faza 37
2. **Prompt Splitting = quality multiplier** — dla complex tasks (D4 + compliance)
3. **Costs są wyższe ale ROI massive** — $67 więcej, $2000 saved
4. **Auto-suggest mechanism** — AEIS sam proponuje Prompt Splitting dla complex
5. **Subscription tier exploitation** — Build Critic + Prompt Splitting używają subscription (lub Burst Mode)
6. **NF4 sigma-style errors caught** — Build Critic łapie hyper-parameter mistakes
