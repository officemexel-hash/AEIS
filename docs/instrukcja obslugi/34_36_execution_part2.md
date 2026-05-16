# FAZY 34-36 — Wykonanie część 2 (Grupa E)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: E — Wykonanie (3-5 z 5) — druga połowa
> **Zależności**: Fazy 1-33 zakończone (build active, sequential phase execution)
> **Następnik**: Fazy 37-38 (Grupa F — Testowanie)
>
> **⚡ Charakter faz 34-36**:
> - **Faza 34** = exception flow (mid-build problem → Council reconvening)
> - **Faza 35** = inner loop (parallel orchestration WITHIN each phase)
> - **Faza 36** = completion (build done, prep dla testing)
>
> **Critical: faza 35 jest "always-on" inside każda faza 33 phase**.
> Faza 33 = sequential outer loop. Faza 35 = parallel inner mechanics.
> Faza 34 wywołuje się tylko jeśli major issue (rzadko).

---

# FAZA 34 — Mid-Build Council Reconvening

> **Spis sekcji**:
> - 34.1 — Sense fazy + when Council reconvenes
> - 34.2 — Trigger conditions
> - 34.3 — Mini-deliberation workflow
> - 34.4 — Decision integration back into build
> - 34.5 — Edge cases (15) + return do faza 33

---

## 34.1. Sens fazy

### 34.1.1. Co Faza 34 robi

Faza 34 to **exception handler** dla mid-build issues które wymagają
multi-perspective deliberation. Większość build issues jest handled
inline (przez Guards, auto-fix, operator). Ale niektóre issues są
**na tyle major** że wymagają Council input.

```
┌──────────────────────────────────────────────────────────────┐
│  Mid-Build Council Reconvening — exception flow              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  WHY this faza exists:                                       │
│   Council był convened w fazach 20-25 dla initial decisions. │
│   Build (faza 33-35) wykonuje plan. Czasem trafia się issue  │
│   której:                                                    │
│    • Pojedynczy operator nie powinien decydować sam           │
│    • Wymaga multi-perspective analysis                        │
│    • Wpływa na fundamental project decisions (Księga)         │
│    • Może wymagać scope change                                │
│                                                              │
│  Faza 34 to mini-version fazy 22 (deliberation rounds):      │
│   • Same Council members reconvene                            │
│   • Smaller scope (focused on issue)                          │
│   • Faster (1-2 rounds typowo)                                │
│   • Cheaper ($3-8 vs $16 dla full deliberation)               │
│                                                              │
│  AFTER faza 34:                                               │
│   • Council decision documented                               │
│   • Może modify build plan, masterplan, lub Księga revision  │
│   • Faza 33 resumes z updated context                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 34.1.2. Kiedy NIE używać fazy 34

Większość issues NIE wymaga Council:

```
HANDLE INLINE (NOT faza 34):
  ✗ Generated code fails Coherence Guard
    → Coherence Guard auto-fix lub Worker regenerates
  ✗ Test failure
    → Quality Guard auto-fix iterations
  ✗ Cost spike z anomaly
    → Cost Guard auto-action lub operator approval
  ✗ Provider outage
    → Fallback chain auto-activates
  ✗ Security finding (low severity)
    → Operator quick-fix
  ✗ Customer asks for clarification
    → Operator responds directly

USE FAZA 34 (Council reconvening):
  ✓ Critical security vulnerability requires architectural change
  ✓ Customer wants major scope change (>20% scope)
  ✓ Performance regression requires re-architecture
  ✓ KSeF API changed unexpectedly (regulatory)
  ✓ Compliance issue discovered (GDPR, PCI)
  ✓ Multi-system integration failure (3+ areas affected)
  ✓ Operator explicitly requests "Council input"
```

### 34.1.3. Wynik fazy 34 (DoD)

```
✓ Council reconvened (same members + relevant new specialists)
✓ Mini-deliberation complete (1-2 rounds typowo)
✓ Decision documented z reasoning
✓ Build plan / masterplan / Księga updates applied
✓ Audit chain entry: mid_build_council_decision
✓ Faza 33 resumed z updated context
```

---

## 34.2. Trigger conditions

### 34.2.1. Auto-triggers

System może auto-trigger fazę 34 na podstawie pattern detection:

```
┌──────────────────────────────────────────────────────────────┐
│  Auto-Trigger Conditions                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CRITICAL SECURITY FINDING                                    │
│   Trigger: Security Guard reports CRITICAL/BLOCKER            │
│            requiring architectural change                     │
│   Example: SQL injection w core auth, requires refactoring   │
│            authentication module                              │
│   Auto-action: pause build, trigger faza 34                   │
│                                                              │
│  CUSTOMER MAJOR SCOPE CHANGE                                  │
│   Trigger: customer request that adds/removes >20% scope      │
│   Example: customer wants add subscription billing            │
│            (was out of scope)                                 │
│   Auto-action: trigger faza 34 (Council evaluates impact)     │
│                                                              │
│  PERFORMANCE REGRESSION                                       │
│   Trigger: P95 latency > 2x target dla critical path         │
│   Example: invoice generation 5s vs 1s target                 │
│   Auto-action: trigger faza 34 jeśli architectural fix needed│
│                                                              │
│  REGULATORY CHANGE                                            │
│   Trigger: KSeF/PCI/GDPR docs updated z breaking change      │
│   Example: KSeF API v2 announced 6 months from now           │
│   Auto-action: trigger faza 34 dla impact analysis            │
│                                                              │
│  MULTI-SYSTEM INTEGRATION FAILURE                             │
│   Trigger: failure spans 3+ Council perspectives              │
│   Example: Stripe webhook fails, KSeF rejects, customer       │
│            data corrupt — all related                         │
│   Auto-action: trigger faza 34                                │
│                                                              │
│  COST OVERRUN MAJOR                                           │
│   Trigger: actual cost trends 50%+ over budget                │
│   Example: Phase 3 costs $30 vs $15 estimate                  │
│   Auto-action: trigger faza 34 (need scope decisions)         │
│                                                              │
│  COMPLIANCE GAP                                               │
│   Trigger: Compliance specialist Guard finds gap              │
│   Example: GDPR DPA needed dla unexpected sub-processor       │
│   Auto-action: trigger faza 34                                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 34.2.2. Operator-triggered

Operator może manualnie trigger fazę 34:

```
┌──────────────────────────────────────────────────────────────┐
│  Operator-Triggered Faza 34                                   │
│                                                              │
│  Operator może wywołać Council mid-build dla:                 │
│                                                              │
│   ☑ "Need architectural decision"                             │
│      Operator zauważył design issue                           │
│   ☑ "Customer changed mind, need scope review"                │
│      Customer wants major change                              │
│   ☑ "Discovered new risk"                                     │
│      Operator widzi risk nie w faza 18 register              │
│   ☑ "Performance concerns, need plan"                         │
│      Realizing approach won't scale                           │
│   ☑ "Scope creep happening, need discipline"                  │
│      Many small additions accumulate                          │
│   ☑ "Strategic decision needed"                               │
│      Operator wants Council input on direction               │
│                                                              │
│  [Trigger Council reconvening]                                │
└──────────────────────────────────────────────────────────────┘
```

### 34.2.3. Trigger frequency expectation

```
W typical D4 project (Customer Y CRM):
  Expected faza 34 invocations: 0-2 over entire build
  
  Most common reason: customer scope change (45% of cases)
  Second: technical risk discovered (30%)
  Third: performance issue (15%)
  Other: 10%

W D5 project:
  Expected: 2-5 invocations
  More complex = more decision points

W D2-D3 project:
  Expected: 0-1
  Rarely justified

Operator may set "invocation budget" w faza 5 autonomy:
  • Conservative: many invocations OK
  • Production: 2-3 budget
  • Aggressive: 1 budget
```

---

## 34.3. Mini-deliberation workflow

### 34.3.1. Faza 34 jest faster than faza 22

```
Faza 22 (initial deliberation):
  • Full briefing z Council Book
  • All 12 roles mandatory
  • 3-5 rounds typowo
  • Cost: $16
  • Time: 1-2h
  • Scope: 20+ questions

Faza 34 (mid-build):
  • Focused briefing on specific issue
  • Relevant roles only (5-8 typowo)
  • 1-2 rounds typowo
  • Cost: $3-8
  • Time: 20-45 min
  • Scope: 1-3 focused questions
```

### 34.3.2. Mini-deliberation steps

```
┌──────────────────────────────────────────────────────────────┐
│  Mini-Deliberation Workflow                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  STEP 1 — Issue framing (~5 min, $0.50)                       │
│   Council Chair frames the issue:                             │
│    • What happened?                                           │
│    • What's the impact?                                       │
│    • What decisions are needed?                                │
│   Operator + relevant roles only invited                      │
│                                                              │
│  STEP 2 — Quick verdicts (~15 min, $2-3)                      │
│   Each invited role gives focused verdict on issue           │
│   Format: stance + reasoning + suggested approach            │
│   Parallel execution                                         │
│                                                              │
│  STEP 3 — Discussion round (~10 min, $1-2)                    │
│   Roles see each other's verdicts                             │
│   Updates lub doubles down                                    │
│   Critic challenges weakest reasoning                         │
│                                                              │
│  STEP 4 — Consolidation (~10 min, $1)                         │
│   Chair synthesizes                                          │
│   Operator approves OR makes final call                       │
│   Decision documented                                         │
│                                                              │
│  STEP 5 — Build plan update (~5 min, $0.50)                   │
│   Build state updated w new decision                          │
│   Affected tasks re-queued lub modified                       │
│   Audit chain entry                                           │
│   Faza 33 resumes                                             │
│                                                              │
│  Total faza 34 time: 30-60 min                                │
│  Total faza 34 cost: $3-8                                     │
└──────────────────────────────────────────────────────────────┘
```

### 34.3.3. Example invocation — customer scope change

```
┌──────────────────────────────────────────────────────────────┐
│  Faza 34 Invocation Example                                   │
│  Customer Y CRM, mid-Phase 3                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  TRIGGER:                                                    │
│   Customer Y Anna emailed:                                    │
│   "Po przemyśleniu, chcielibyśmy dodać moduł rezerwacji      │
│    spotkań dla naszych klientów. Czy to możliwe w obecnym   │
│    projekcie?"                                                │
│                                                              │
│  Operator triggered faza 34: "Customer scope change"          │
│                                                              │
│  COUNCIL CONVENED (focused, 6 roles):                         │
│   • Council Chair (orchestration)                             │
│   • Planner (technical feasibility)                           │
│   • Critic (challenge)                                        │
│   • Compliance (GDPR — booking data)                          │
│   • UX Designer (user flow impact)                            │
│   • Risk Assessor (timeline/budget impact)                    │
│                                                              │
│  STEP 1 — Issue framing:                                      │
│   "Customer wants add appointment booking module.             │
│    Was OUT OF SCOPE (faza 18 explicit non-goal).              │
│    Estimated effort: 1-2 weeks added.                         │
│    Cost: ~$60-100 added.                                      │
│    Customer impact: significant feature.                       │
│    Decisions needed:                                          │
│     1. Accept scope addition lub deny?                        │
│     2. Jeśli accept: integrate w current build lub Phase 2?   │
│     3. Jeśli accept: cost/timeline reconciliation z customer  │
│     4. Compliance impact (booking data = additional PII)?"    │
│                                                              │
│  STEP 2 — Quick verdicts (parallel):                          │
│                                                              │
│   Planner:                                                    │
│   "Technically feasible. Best done as separate module after  │
│    main project. Mid-build addition risks scope creep         │
│    cascade. Recommend: defer to Phase 2."                     │
│                                                              │
│   Critic:                                                     │
│   "Strong concern: classic scope creep pattern. Customer       │
│    initially didn't want this. Likely more 'small' additions │
│    coming. Recommend: deny + propose Phase 2 contract."       │
│                                                              │
│   Compliance:                                                 │
│   "Booking data adds new PII categories. Requires DPIA        │
│    update, customer notification (data subjects), DPA         │
│    amendment. Adds 2-3 days of compliance work."              │
│                                                              │
│   UX Designer:                                                │
│   "Booking module significantly changes UX flow. Customer     │
│    list now needs booking integration UI. Multi-page          │
│    impact. Estimate 8-12 components."                         │
│                                                              │
│   Risk Assessor:                                              │
│   "Adding mid-build:                                          │
│    + Cost: $80 added (50% over current Phase 3 budget)       │
│    + Timeline: 2 weeks added (deadline tight)                 │
│    + Risk: introduces R5 'scope cascade'                      │
│    Adding as Phase 2 contract:                                │
│    + Cost: $80 + $20 setup overhead = $100                    │
│    + Timeline: separate (no current impact)                   │
│    + Risk: contract negotiation overhead, but isolated"       │
│                                                              │
│   Council Chair:                                              │
│   "Strong consensus emerging dla 'defer to Phase 2 contract'.│
│    Need operator decision on customer communication."        │
│                                                              │
│  STEP 3 — Discussion (1 round):                               │
│   Critic doubles down: "Don't add anything mid-build."        │
│   Compliance flags: "If accept now, need DPIA fast."          │
│   No specialist override invoked.                             │
│                                                              │
│  STEP 4 — Consolidation:                                      │
│   Operator decision needed.                                   │
│                                                              │
│   Council recommendation: defer + propose Phase 2 contract    │
│   Confidence: 92%                                             │
│                                                              │
│   Operator options:                                           │
│    [● Accept Council recommendation: defer + Phase 2]         │
│    [○ Override: accept mid-build (riski cascade)]             │
│    [○ Decline customer's request entirely]                    │
│    [○ Custom decision z own reasoning]                        │
│                                                              │
│  Operator chose: defer + propose Phase 2 contract             │
│                                                              │
│  STEP 5 — Build plan update:                                  │
│   ✓ No changes to current build                               │
│   ✓ Customer notification template generated:                 │
│     "Doceniamy Państwa propozycję rezerwacji spotkań.         │
│      Po analizie technicznej z naszej strony, najlepiej      │
│      będzie dodać ten moduł jako Fazę 2 projektu — po         │
│      stabilnym wdrożeniu obecnego CRM. Pozwoli to na          │
│      dedicated focus i lepszą jakość. Czy możemy przedyskuto-│
│      wać Phase 2 contract w połowie czerwca?"                 │
│   ✓ Audit chain entry: scope_change_deferred                  │
│   ✓ Faza 33 resumes z normal flow                             │
│                                                              │
│  Faza 34 totals:                                              │
│   Duration: 38 min                                            │
│   Cost: $4.20                                                 │
│   Council decision: documented                                │
│   Build impact: zero (deferred)                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 34.4. Decision integration back into build

### 34.4.1. 4 types of build impact

Po faza 34 decision, impact może być w 4 categories:

```
┌──────────────────────────────────────────────────────────────┐
│  Build Impact Categories                                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  IMPACT 1 — No change                                         │
│   Council confirms current approach OK                        │
│   Build resumes z no modification                             │
│   Example: customer asked, but Council says current plan OK   │
│                                                              │
│  IMPACT 2 — Build plan tweaks                                 │
│   Specific tasks modified, added, removed                     │
│   Affected workers re-queued                                  │
│   Masterplan updated (in-place revision)                      │
│   Example: switch model dla one task, refactor approach       │
│                                                              │
│  IMPACT 3 — Phase reorg                                       │
│   Significant changes to remaining build phases               │
│   Re-do faza 28.4 dla affected phases                         │
│   May change resource profile mid-build                       │
│   Example: add 2 weeks of work, may switch Profile 2 → 3      │
│                                                              │
│  IMPACT 4 — Księga revision                                   │
│   Fundamental project changes                                 │
│   Triggers formal "Księga revision" process                   │
│   May require customer signoff                                │
│   Major build halt + replan                                   │
│   Example: scope grows 50%, change architecture               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 34.4.2. Build state transitions per impact

```
Per impact category, build state transitions:

  Impact 1 (no change):
    Build state: was BUILDING → BUILDING (resume)
    No artifacts modified
    Faza 33 continues z next task
  
  Impact 2 (tweaks):
    Build state: was BUILDING → BUILDING (resume z modifications)
    Affected tasks re-queued
    Some completed work may be discarded
    Faza 33 continues
  
  Impact 3 (phase reorg):
    Build state: BUILDING → REPLANNING_PHASE (~30 min)
    Re-do affected portions of faza 28
    Re-validate via mini faza 31 (focused dry run)
    Build state: REPLANNING_PHASE → BUILDING
    Faza 33 continues z updated plan
  
  Impact 4 (Księga revision):
    Build state: BUILDING → REVISION (~hours/days)
    Halt all build work
    Trigger formal Księga revision (mini-Council w fazie 25)
    Customer signoff required
    Re-do fazy 26-31 (planning) z new Księga
    Re-validate całkowicie
    Build state: REVISION → BUILDING (resume z fresh plan)
```

### 34.4.3. Worker state during faza 34

```
W trakcie faza 34, workers:

  Active tasks (in-progress):
    • Allowed to complete current task (don't waste work)
    • New tasks queued but NOT consumed
    • State preserved
  
  Workers communicate "paused" via shared state:
    • Idle workers wait dla decision
    • Active workers finish current then idle
    • No new task assignments
  
  Resource hold:
    • Environments stay provisioned
    • LLM quotas preserved
    • Cost tracking continues (paused state cost = 0)
  
  After faza 34 decision:
    • Workers receive updated context
    • New task queue loaded
    • Modified skill assignments (jeśli any)
    • Resume normal operation
```

---

## 34.5. Edge Cases — Mid-Build Council (15)

### Kategoria A — Trigger issues (4)

**EC-A1**: False trigger
- Auto-trigger fires unnecessarily (e.g., minor security finding misclassified)
- Akcje: dismiss, no Council needed, log false trigger

**EC-A2**: Trigger missed (should have fired)
- Operator notices issue, system didn't auto-trigger
- Akcje: manual trigger, investigate detection gap

**EC-A3**: Multiple simultaneous triggers
- 3 different issues trigger concurrently
- Akcje: consolidate into single Council session, or sequential

**EC-A4**: Trigger during operator absence
- Critical issue, operator unavailable
- Akcje: pause build, escalation channels, await operator

### Kategoria B — Council mechanics (4)

**EC-B1**: Council members unavailable mid-deliberation
- Provider outage during faza 34
- Akcje: pause, retry, fallback models

**EC-B2**: Mini-deliberation can't reach consensus
- Council split, 1 round insufficient
- Akcje: 2nd round, operator decision, full faza 22 reconvening

**EC-B3**: Specialist override conflict
- 2 specialists disagree on critical aspect
- Akcje: operator mediation, escalate to full Council

**EC-B4**: Mini-deliberation cost overrun
- $15 vs $5 estimate
- Akcje: investigate, accept, may indicate complex issue needing full Council

### Kategoria C — Decision integration (4)

**EC-C1**: Impact category wrong
- Marked Impact 2, actually Impact 3
- Akcje: re-categorize, may re-do partial replanning

**EC-C2**: Worker state corruption during pause
- Worker can't resume cleanly
- Akcje: restart worker, restore from snapshot

**EC-C3**: Decision conflicts z previous Council
- Faza 34 decision contradicts faza 23 decision
- Akcje: explicit override z reasoning, audit log

**EC-C4**: Customer rejects post-Council decision
- Customer was supposed to be on board, isn't
- Akcje: re-trigger faza 34 z customer feedback, may halt project

### Kategoria D — Recovery (3)

**EC-D1**: Faza 34 itself fails
- Crash mid-mini-deliberation
- Akcje: resume from last step, may need restart

**EC-D2**: Multiple faza 34 invocations w short period
- 3 invocations w 1 week (warning sign)
- Akcje: investigate root cause, may indicate plan instability

**EC-D3**: Operator overrides Council recommendation
- Council says X, operator chooses Y z weak reasoning
- Akcje: log override, may indicate operator-Council misalignment

---

## 34.6. Acceptance + return do faza 33

```bash
$ aeis-cli phase34-status --project proj_customer_y_crm

Faza 34 (Mid-Build Council) status:

  Trigger: customer scope change request
  Council session ID: mc_abc123
  
  Mini-deliberation:
   ✓ 6 roles convened
   ✓ 1 round of verdicts
   ✓ Consensus reached (92% confidence)
   ✓ Operator approved Council recommendation
  
  Decision: defer scope addition do Phase 2 contract
  Build impact: Impact 1 (no change to current build)
  
  Faza 34 totals:
   Duration: 38 min
   Cost: $4.20
   Audit entries: 12
  
  ✓ Build state: BUILDING (resumed)
  ✓ Workers: re-activated
  ✓ Faza 33 continues z next task

Phase 34 ACCEPTED. Build resumed.
```

---

# FAZA 35 — Build Orchestration

> **Spis sekcji**:
> - 35.1 — Sense fazy + parallel orchestration WITHIN każda phase
> - 35.2 — Worker coordination mechanics
> - 35.3 — Cross-worker Coherence Guard checks
> - 35.4 — Layer parallelism within phase
> - 35.5 — Error recovery cascades
> - 35.6 — Mid-build profile switching
> - 35.7 — Live orchestration dashboard
> - 35.8 — Edge cases (22) + transition

---

## 35.1. Sens fazy

### 35.1.1. Co Faza 35 robi

Faza 35 to **inner loop dla faza 33**. Faza 33 sequentially iteruje
przez phases. Faza 35 obsługuje **wszystkie parallel mechanics WITHIN
phase**:

```
┌──────────────────────────────────────────────────────────────┐
│  Build Orchestration — parallel mechanics WITHIN phase       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Faza 33 control flow:                                        │
│   for phase in masterplan.phases:                             │
│     await execute_phase(phase)  ← delegated to faza 35        │
│                                                              │
│  Faza 35 inside execute_phase():                              │
│   • Decompose phase into layer-tasks                          │
│   • Assign tasks to workers (per profile)                     │
│   • Manage parallel execution                                 │
│   • Coordinate cross-worker work                              │
│   • Run cross-worker Coherence Guard                          │
│   • Handle worker failures, retries                           │
│   • Track parallel progress                                   │
│   • Allow mid-phase profile switching                         │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.1.2. Why faza 35 jest separate from faza 33

Faza 35 was put separately because:
1. **Reusable** — same orchestration mechanics dla different phases
2. **Testable** — orchestration logic isolated
3. **Profile-dependent** — different profiles = different orchestration
4. **Complex** — parallel coordination wymaga dedicated mental model

### 35.1.3. Wynik fazy 35 (DoD per phase)

Faza 35 nie ma DoD — jest **embedded inside faza 33's per-phase loop**:

```
Per phase invocation of faza 35:
  ✓ All phase tasks scheduled
  ✓ Workers assigned per profile
  ✓ Parallel execution managed
  ✓ Cross-worker Coherence checks done
  ✓ Errors handled (recovered or escalated)
  ✓ Phase artifacts integrated
  ✓ Phase milestone ready dla faza 33's transition
  ✓ Audit chain entries per task
```

---

## 35.2. Worker coordination mechanics

### 35.2.1. Coordination primitives

Workers coordinują przez 3 primitives:

```
┌──────────────────────────────────────────────────────────────┐
│  Worker Coordination Primitives                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SHARED TASK QUEUE                                         │
│   File: coordination/task_queue.jsonl                         │
│   Format: append-only JSON lines                              │
│   Operations:                                                │
│    • enqueue(task) — orchestrator adds task                   │
│    • dequeue() — worker takes next task                       │
│    • peek() — preview without taking                          │
│    • update_status(task_id, status)                           │
│                                                              │
│   Worker selection:                                           │
│    • Skill match (worker has required skill)                  │
│    • Specialization (Backend vs Frontend worker)              │
│    • Load balance (least busy)                                │
│                                                              │
│  2. FILE-LEVEL LOCKS                                          │
│   File: coordination/locks.json                               │
│   Format: lock_path → worker_id                               │
│   Operations:                                                │
│    • acquire(file_path) — exclusive lock                      │
│    • release(file_path) — release                             │
│    • check(file_path) — see who holds                         │
│   Timeout: 30 min default (auto-release)                      │
│                                                              │
│  3. SHARED STATE                                              │
│   File: coordination/shared_state.json                        │
│   Format: key-value store                                     │
│   Operations:                                                │
│    • get(key) — read                                          │
│    • set(key, value) — write z optimistic concurrency         │
│    • subscribe(key) — notification on change                  │
│                                                              │
│   Used dla:                                                   │
│    • Cross-worker config (e.g., "current_phase")              │
│    • Inter-worker messages                                    │
│    • Coordination flags                                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.2.2. Task assignment algorithm

```python
def assign_next_task(worker):
    """Assign next appropriate task from queue do worker."""
    
    # Get all queued tasks
    queue = load_task_queue()
    
    candidates = []
    for task in queue:
        if task.status != "queued":
            continue
            
        # Check skill match
        if task.required_skill not in worker.skills:
            continue
            
        # Check specialization
        if task.specialization and task.specialization != worker.specialization:
            continue
            
        # Check dependencies
        if not all(dep in completed_tasks for dep in task.depends_on):
            continue
            
        # Check resource availability
        if not worker.has_capacity(task.estimated_cost, task.estimated_time):
            continue
        
        candidates.append(task)
    
    if not candidates:
        return None  # No suitable task
    
    # Prioritize:
    #   1. Critical path tasks (z masterplan)
    #   2. Tasks with most dependents (unblock other work)
    #   3. Largest tasks (parallel efficiency)
    selected = max(candidates, key=lambda t: (
        t.is_critical_path * 1000 +
        t.dependent_count * 100 +
        t.estimated_time
    ))
    
    # Mark as taken
    selected.status = "in_progress"
    selected.assigned_worker = worker.id
    save_task_queue()
    
    return selected
```

### 35.2.3. Coordination overhead measurement

```
W trakcie buildu, system mierzy actual coordination overhead:

  Measurements per minute:
   • Time spent in coordination operations (lock acquire, queue ops)
   • Time spent waiting (lock contention, queue empty)
   • Productive task work
  
  Overhead % = (coordination + waiting) / total_time
  
  Profile budgets:
   Profile 1: 0% (no coordination needed)
   Profile 2: 11% budget
   Profile 3: 18% budget
   Profile 4: 25% budget
   Profile 5: 35% budget
  
  Live tracking dashboard:
   Current overhead: 8% ✓ (budget 11%)
   Trending: stable
  
  Alerts:
   ⚠ If overhead > budget × 1.2: investigate
   ⚠ If overhead > budget × 1.5: profile may not fit project
```

---

## 35.3. Cross-worker Coherence Guard checks

### 35.3.1. Why cross-worker checks needed

Single-worker projects: Coherence Guard checks single output stream.
Multi-worker projects: outputs from different workers must be **mutually
coherent**.

```
Examples of cross-worker incoherence:

  • Worker 1 generates User schema z field "first_name"
    Worker 2 generates UserProfile component using "firstName"
    → Mismatch (snake_case vs camelCase across boundary)
  
  • Worker 1 generates API endpoint POST /api/customers
    Worker 2 generates frontend calling POST /api/customer (typo)
    → Frontend will fail
  
  • Worker 1 implements auth middleware z JWT
    Worker 2 implements UI z session-based auth
    → Architecture mismatch
  
  • Worker 1 creates DB migration adding column 'email_verified'
    Worker 2 references 'email_confirmed' w code
    → Mismatch
```

### 35.3.2. Cross-worker check tier

Coherence Guard ma additional **Tier 3** dla cross-worker:

```
┌──────────────────────────────────────────────────────────────┐
│  Coherence Guard Tier 3 — Cross-Worker                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Tier 1 (lokalne, per-file):                                  │
│   Single file consistency                                     │
│   Free                                                       │
│                                                              │
│  Tier 2 (sonnet, per-module):                                 │
│   Within-worker module coherence                              │
│   ~$0.30 per check                                            │
│                                                              │
│  Tier 3 (sonnet, cross-worker):  ← NEW dla parallel          │
│   Verifies outputs from different workers consistent          │
│   Trigger: when 2+ workers complete tasks dla same module     │
│   Cost: ~$0.50 per check                                      │
│   Frequency: per phase boundary + after worker syncs          │
│                                                              │
│  Tier 4 (opus, cross-system):                                 │
│   Verifies cross-module integration                          │
│   Trigger: end of build phases that touch multiple modules    │
│   Cost: ~$1.50 per check                                      │
│   Frequency: 1-2 per major phase                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.3.3. Cross-worker check workflow

```
Trigger: Worker 1 finishes "user_schema.sql"
          Worker 2 finishes "UserForm.tsx"
          Both touch User entity
          
Cross-worker check:
  1. Detect related outputs (file dependency analysis)
  2. Send do Tier 3 (claude-sonnet)
  3. Prompt: "Compare these outputs from different workers.
              Identify any inconsistencies (naming, types,
              behavior expectations)."
  4. Output: list of issues z severity
  5. Per issue:
     • INFO: log only
     • WARNING: notify operator, optionally auto-fix
     • ERROR: pause both workers, require resolution
     • CRITICAL: rollback affected work, force re-coordination

Example output:
  ⚠ Worker 1 used 'email_address' field
     Worker 2 used 'email' (shorter)
     Severity: WARNING
     Recommendation: standardize on 'email'
     Auto-fix: Worker 1 will rename in next batch
```

### 35.3.4. Cross-worker check cost scaling

```
Cross-worker check cost grows z workers:

  2 workers: ~5 checks/phase × $0.50 = $2.50/phase
  4 workers: ~12 checks/phase × $0.50 = $6.00/phase
  8 workers: ~28 checks/phase × $0.50 = $14.00/phase
  16 workers: ~60 checks/phase × $0.50 = $30.00/phase
  
  Scaling: O(N²) where N = workers (each pair may need check)
  
  Mitigations:
   • Smart pairing (only related work)
   • Skip if same module (no cross-worker)
   • Batch checks (multiple files at once)
```

---

## 35.4. Layer parallelism within phase

### 35.4.1. Per-phase parallel patterns

Different phases have different parallel patterns based on layer:

```
┌──────────────────────────────────────────────────────────────┐
│  Per-Phase Parallel Patterns                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Phase 1 (Foundation, Layer 0 sequential):                    │
│   Pattern: SEQUENTIAL                                         │
│   Workers: 1 effective (others wait dla Worker 1)             │
│   Critical path: full layer time                              │
│   Profile 2 wallclock: 13h                                    │
│                                                              │
│  Phase 2 (KSeF, Layer 2 partial parallel):                    │
│   Pattern: PARTIAL_PARALLEL                                   │
│   Workers: 2 effective (Worker 1 KSeF + Worker 2 mock data)   │
│   Critical path: Worker 1 chain                               │
│   Profile 2 wallclock: 18h                                    │
│                                                              │
│  Phase 3 (Core Features):                                     │
│   Pattern: HIGH_PARALLEL                                      │
│   Workers: 2 (max dla Profile 2)                              │
│   Critical path: customer + invoice modules                   │
│   Profile 2 wallclock: 22h                                    │
│                                                              │
│  Phase 4 (Payment Integration):                               │
│   Pattern: PARTIAL_PARALLEL                                   │
│   Workers: 2 (Worker 1 backend, Worker 2 frontend payment UI) │
│   Critical path: backend integration                          │
│   Profile 2 wallclock: 16h                                    │
│                                                              │
│  Phase 5 (UX/I18n):                                           │
│   Pattern: HIGH_PARALLEL                                      │
│   Workers: 2 (mostly Worker 2)                                │
│   Critical path: branding apply                               │
│   Profile 2 wallclock: 18h                                    │
│                                                              │
│  Phase 6 (Quality + Deploy):                                  │
│   Pattern: SEQUENTIAL stages                                  │
│   Workers: 1-2 (sequencing constraints)                       │
│   Critical path: integration tests → deploy                   │
│   Profile 2 wallclock: 24h                                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.4.2. Within-phase task scheduling

Per phase, faza 35 schedules tasks:

```
Example: Phase 4 (Payment Integration) scheduling

Tasks queued:
  T1: Stripe service module (Worker 1, claude-opus, $1.20, 4h)
  T2: Stripe webhook handler (Worker 1, claude-opus, $1.00, 3h)
  T3: Payment API endpoint (Worker 1, claude-sonnet, $0.40, 2h)
  T4: PaymentForm component (Worker 2, claude-sonnet, $0.50, 2h)
  T5: Payment success page (Worker 2, claude-sonnet, $0.30, 1h)
  T6: Payment failure handling (Worker 2, claude-sonnet, $0.40, 2h)
  T7: Refund flow (Worker 1, claude-sonnet, $0.40, 2h)

Dependencies:
  T2 depends on T1 (webhook needs service)
  T3 depends on T1 (endpoint uses service)
  T4 depends on T3 (frontend calls endpoint)
  T5 depends on T4 (success after form)
  T6 depends on T4
  T7 depends on T1, T2, T3 (refund full stack)

Scheduling:
  Time 0: Worker 1 starts T1, Worker 2 idle (waiting dla T3)
  Time 2h: Worker 2 starts T4 mock (assumes API spec ready)
            (parallel z Worker 1 still on T1)
  Time 4h: T1 done. Worker 1 starts T2 + T3 (both can start)
            T3 priority because T4 depends on it
  Time 6h: T3 done. Worker 2's T4 mock replaced z real call.
            T4 continues (now z real backend)
  Time 7h: T2 done. Worker 1 starts T7 (refund needs T1+T2)
  Time 8h: T4 done. Worker 2 starts T5 + T6 (parallel)
  Time 9h: T7 done. Worker 1 done (helps Worker 2 jeśli needed)
  Time 10h: T5 done.
  Time 11h: T6 done.
  
Phase 4 wallclock: 11h (vs 16h sequential, 31% speedup)
Profile 2 estimate was 16h — actual 11h (under budget ✓)
```

### 35.4.3. Dynamic task generation

Some tasks generate sub-tasks dynamically:

```
Example: Backend Stripe service generates needs:

  Worker 1 generates Stripe service:
    Output: stripe_service.py
    Detected sub-tasks needed:
      • Generate stripe_types.py (type definitions)
      • Generate stripe_errors.py (error classes)
      • Generate test_stripe_service.py (unit tests)
    
  Auto-queued sub-tasks:
    • stripe_types.py → Worker 1 (already context)
    • stripe_errors.py → Worker 1
    • test_stripe_service.py → Worker 2 (test specialist)
    
  Original task remains "in progress" until all sub-tasks done
```

---

## 35.5. Error recovery cascades

### 35.5.1. Error categories

```
┌──────────────────────────────────────────────────────────────┐
│  Build Error Categories                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  WORKER ERRORS                                                │
│   • Worker timeout (model not responding)                     │
│   • Worker crash (process died)                               │
│   • Worker resource exhaustion (out of GPU memory)            │
│   • Worker quota exceeded (LLM tokens depleted)               │
│                                                              │
│  TASK ERRORS                                                  │
│   • Generated output invalid (parse fails)                    │
│   • Generated output Coherence-failed                         │
│   • Generated output Security-flagged (CRITICAL)              │
│   • Test failures (Quality Guard)                             │
│   • Missing dependency (skill not loaded)                     │
│                                                              │
│  COORDINATION ERRORS                                          │
│   • Lock timeout (worker held lock too long)                  │
│   • Shared state corruption                                   │
│   • Cross-worker check failure                                │
│   • Deadlock detection                                        │
│                                                              │
│  EXTERNAL ERRORS                                              │
│   • Provider outage (Anthropic, OpenAI down)                  │
│   • Cloud env unreachable                                     │
│   • Rate limits hit                                           │
│   • API key invalid                                           │
│                                                              │
│  SYSTEMIC ERRORS                                              │
│   • Disk full                                                 │
│   • Network partition                                         │
│   • AEIS bug (unhandled exception)                            │
│   • Audit chain integrity issue                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.5.2. Recovery strategies

```
Per error category, recovery cascade:

  WORKER ERRORS:
   1st attempt: retry z same worker, same model
   2nd attempt: switch to fallback model
   3rd attempt: switch to different worker (jeśli specialization allows)
   4th attempt: notify operator, may need manual intervention
   5th attempt: pause phase, escalate
  
  TASK ERRORS (output invalid):
   1st attempt: regenerate z stricter prompt
   2nd attempt: switch to premium model
   3rd attempt: split task into smaller parts
   4th attempt: notify operator dla manual completion
  
  TASK ERRORS (Coherence-failed):
   1st attempt: include neighboring context, regenerate
   2nd attempt: cross-worker check + alignment
   3rd attempt: operator review + manual fix
  
  COORDINATION ERRORS:
   1st attempt: release lock + retry
   2nd attempt: restart coordination layer
   3rd attempt: sequential fallback (single worker)
   4th attempt: escalate
  
  EXTERNAL ERRORS:
   1st attempt: wait 30 sec + retry
   2nd attempt: switch provider via fallback chain
   3rd attempt: pause workers, wait recovery
   4th attempt: notify operator, defer affected tasks
  
  SYSTEMIC ERRORS:
   1st attempt: log + continue (jeśli non-critical)
   2nd attempt: restart affected component
   3rd attempt: full pause + operator escalation
```

### 35.5.3. Cascade example

```
Scenario: Worker 1 generates Stripe webhook handler

  Attempt 1: claude-sonnet
   Output: invalid JSON schema (parse fails)
   → Retry z stricter prompt
   
  Attempt 2: claude-sonnet (stricter)
   Output: valid but Coherence-failed (uses wrong API version)
   → Switch to premium model
   
  Attempt 3: claude-opus
   Output: valid + Coherence OK
   → Security Guard scan
   Result: CRITICAL — uses deprecated webhook signing method
   → Cross-worker check + alignment
   
  Attempt 4: claude-opus z augmented context
   Includes Stripe latest signing docs
   Output: valid + Coherence OK + Security OK
   ✓ Task complete
  
Cost: $4.20 (vs $1 expected) — 4x overrun dla this task
Time: 35 min (vs 10 min expected)

Cost Guard flags: spike anomaly
Operator notified: 1 task had 4x cost overrun
Operator decision: accept (Stripe complexity), continue
```

### 35.5.4. Worker failure isolation

```
Co jeśli worker totally fails (crash):

  1. Detection: heartbeat missed for 30 sec
  2. Auto-isolation:
     • Mark worker as failed
     • Release all worker's locks
     • Re-queue worker's in-progress task
     • Other workers notified
  3. Recovery attempt:
     • Restart worker process
     • Reload state from snapshot
     • Resume from last checkpoint
  4. If recovery fails:
     • Single-worker fallback (other workers continue)
     • Notify operator
     • May trigger faza 34 (Council) jeśli systemic
```

---

## 35.6. Mid-build profile switching

### 35.6.1. Why mid-build switching

Operator może chcieć switch profile mid-build z różnych powodów (z faza 30):

```
Triggers dla mid-build profile switching:
  
  • Customer dorzuca pieniądze na speed-up
  • Critical deadline pressure (need to compress)
  • Quality issues (need slow down + more attention)
  • Budget overrun (need to cut)
  • Operator unavailable (need higher autonomy)
  • Better progress than expected (can scale down)
```

### 35.6.2. Profile switching workflow

```
┌──────────────────────────────────────────────────────────────┐
│  Mid-Build Profile Switch                                     │
│  Customer Y CRM, mid-Phase 4                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Current: Profile 2 (2 workers, 1 staging)                    │
│  Requested: Profile 3 (4 workers, 2 envs)                     │
│                                                              │
│  Reason: customer wants faster delivery, approved $43 added   │
│                                                              │
│  Switch impact analysis:                                      │
│   Time saved: ~2 weeks                                        │
│   Cost added: $43                                             │
│   Switch overhead: $15 (env provision, worker spawn)          │
│   Net additional: $58                                         │
│   New estimated total: $407                                   │
│                                                              │
│  Switch process:                                              │
│   1. ✓ Drain current workers (finish in-progress tasks)       │
│   2. ⠋ Provision new staging environment                      │
│   3. ⏸ Spawn 2 additional workers                             │
│   4. ⏸ Reassign skills + models                               │
│   5. ⏸ Re-balance task queue                                  │
│   6. ⏸ Update Guards configuration (cross-worker checks now   │
│         more frequent)                                        │
│   7. ⏸ Resume build z 4 workers                               │
│   Estimated switch time: 12 min                               │
│                                                              │
│  ⚠ Cannot switch w middle of:                                  │
│   • Critical path tasks (defer until done)                    │
│   • Hard gate workflows                                        │
│   • Coordination-heavy phases                                 │
│                                                              │
│  Akcje:                                                      │
│   [● Confirm switch (12 min downtime)]                        │
│   [○ Schedule switch dla next phase boundary]                 │
│   [○ Cancel switch]                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 35.6.3. Switch scenarios

```
Profile DOWN (e.g., 4 workers → 2 workers):
  • Drain 2 workers
  • Re-balance their pending tasks to remaining
  • Decommission unused environment
  • Lower Guards frequency
  • Switch overhead: ~$5
  • Time savings preservation: depends on already-done work
  
Profile UP (e.g., 2 workers → 4 workers):
  • Provision new envs
  • Spawn new workers
  • Re-assign skills (load on new workers)
  • Higher Guards frequency
  • Switch overhead: ~$15
  • Speed up: 30-50% dla remaining work
  
Profile change mid-phase:
  • Risky (work-in-progress disruption)
  • Recommended: wait dla phase boundary
  
Profile change mid-task:
  • NOT supported
  • Always wait dla current task completion
```

---

## 35.7. Live orchestration dashboard

### 35.7.1. Comprehensive live view

```
┌──────────────────────────────────────────────────────────────┐
│  Build Orchestration Dashboard — Customer Y CRM              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Overall: Phase 4 of 6, 67% complete                          │
│  Profile: 2 (Solo balanced)                                   │
│  Total cost: $87.40 / $148                                    │
│                                                              │
│  ─────── WORKERS ───────                                      │
│                                                              │
│  Worker 1 (Backend):                                          │
│   Status: ⠋ ACTIVE                                            │
│   Current task: T7 Refund flow                                │
│   Model: claude-sonnet                                        │
│   Progress: ▓▓▓▓▓▓▓▓░░ 78%                                    │
│   Time on task: 1h 34min / est 2h                             │
│   Cost on task: $0.32 / est $0.40                             │
│   Lifetime cost: $58.20                                       │
│                                                              │
│  Worker 2 (Frontend):                                         │
│   Status: ⠋ ACTIVE                                            │
│   Current task: T6 Payment failure handling                   │
│   Model: claude-sonnet                                        │
│   Progress: ▓▓▓▓░░░░░░ 42%                                    │
│   Time on task: 50min / est 2h                                │
│   Cost on task: $0.18 / est $0.40                             │
│   Lifetime cost: $29.20                                       │
│                                                              │
│  ─────── COORDINATION ───────                                 │
│                                                              │
│  Active locks:                                                │
│   stripe_service.py → Worker 1 (refund changes)               │
│   PaymentForm.tsx → Worker 2 (none)                           │
│   shared_state → Worker 1 (config update)                     │
│                                                              │
│  Coordination overhead: 9% (budget 11% ✓)                     │
│  Lock contention events: 2 (last 30 min)                      │
│  Cross-worker checks: 3 done w Phase 4 (all PASS)             │
│                                                              │
│  ─────── TASK QUEUE ───────                                   │
│                                                              │
│  Phase 4 progress:                                            │
│   ✓ T1: Stripe service module                                 │
│   ✓ T2: Stripe webhook handler                                │
│   ✓ T3: Payment API endpoint                                  │
│   ✓ T4: PaymentForm component                                 │
│   ✓ T5: Payment success page                                  │
│   ⠋ T6: Payment failure handling (Worker 2, 42%)              │
│   ⠋ T7: Refund flow (Worker 1, 78%)                           │
│                                                              │
│  Phase 4 wallclock: 8h elapsed of est 11h                     │
│  On track ✓                                                   │
│                                                              │
│  ─────── GUARDS ───────                                       │
│                                                              │
│  Coherence: ✓ 0 issues w Phase 4                              │
│  Cost: ⚠ T7 cost variance high (investigated)                 │
│  Security: ✓ all critical paths clean                         │
│  Quality: pending tests                                       │
│  Provenance: 142 entries w Phase 4                            │
│                                                              │
│  ─────── ALERTS ───────                                       │
│                                                              │
│  No active alerts                                             │
│                                                              │
│  ─────── ACTIONS ───────                                      │
│                                                              │
│  [Pause build]  [Switch profile]  [Trigger Council]           │
│  [View task detail]  [View live cost]                         │
│  [Mobile sync]                                               │
└──────────────────────────────────────────────────────────────┘
```

### 35.7.2. Operator interventions live

Operator może w runtime:

```
Quick interventions (no build pause):
  • Approve hard gate
  • Acknowledge notification
  • Switch single role's model dla next task
  • Adjust Guards sensitivity

Medium interventions (brief pause):
  • Switch profile (drain workers, reconfig)
  • Add task manually
  • Skip task (mark as N/A)
  • Force Coherence check

Major interventions (significant pause):
  • Trigger faza 34 (Council reconvening)
  • Modify masterplan
  • Cancel project
  • Customer scope change negotiation
```

---

## 35.8. Edge Cases — Build Orchestration (22)

### Kategoria A — Worker coordination (5)

**EC-A1**: Lock deadlock
- Worker 1 holds lock A, waits dla B; Worker 2 holds B, waits dla A
- Akcje: deadlock detection, abort one worker, retry

**EC-A2**: Lock starvation
- Worker keeps acquiring locks first, others wait
- Akcje: priority queue, fair scheduling

**EC-A3**: Shared state corruption
- Concurrent writes corrupt shared_state.json
- Akcje: optimistic concurrency, restore from backup

**EC-A4**: Worker overloaded (too many tasks queued)
- Backend worker has 50 tasks waiting
- Akcje: rebalance, may need profile change

**EC-A5**: Coordination overhead exceeds budget
- 25% overhead vs 11% budget (Profile 2)
- Akcje: investigate, reduce parallelism, profile down

### Kategoria B — Cross-worker checks (4)

**EC-B1**: Cross-worker check finds CRITICAL mismatch
- Workers' outputs incompatible
- Akcje: pause both workers, regenerate one, manual fix

**EC-B2**: Cross-worker check cost overrun
- Many checks needed, $30 vs $5 budget
- Akcje: smarter pairing, batch checks, accept

**EC-B3**: Cross-worker check false positive
- Flag mismatch that's actually OK
- Akcje: tune sensitivity, suppress, accept

**EC-B4**: Cross-worker check missed actual issue
- Mismatch slipped through
- Akcje: improve check rules, manual review, integration tests catch

### Kategoria C — Layer parallelism issues (4)

**EC-C1**: Task scheduling produces sub-optimal order
- Workers finish at different times, idle workers
- Akcje: improve scheduling algorithm, manual reorder

**EC-C2**: Dynamic task generation explodes
- Sub-tasks generate sub-tasks recursively
- Akcje: depth limit, manual review, cap tasks

**EC-C3**: Dependency chain longer than expected
- T2 depends on T1, T1 takes longer than estimate
- Akcje: parallel work on independent chains, accept

**EC-C4**: Critical path discovered mid-phase
- Algorithm didn't recognize implicit dependency
- Akcje: re-prioritize, may need replanning

### Kategoria D — Error recovery (5)

**EC-D1**: Worker repeatedly fails task
- 5 retries all fail
- Akcje: operator manual, may need different approach

**EC-D2**: Cascade failure (one worker fails, others compensate fail)
- Worker 1 down, Worker 2 takes its tasks but overloaded
- Akcje: fall back to single-worker, escalate

**EC-D3**: Provider outage during critical task
- Anthropic down mid-Stripe integration
- Akcje: fallback model, wait, may delay phase

**EC-D4**: Disk full during build
- Workspace fills up z artifacts
- Akcje: cleanup snapshots, expand storage, pause build

**EC-D5**: Audit chain corruption mid-build
- Provenance Guard reports issue
- Akcje: forensic, restore, may need to re-do work

### Kategoria E — Profile switching (4)

**EC-E1**: Switch fails (provisioning error)
- New env can't be provisioned
- Akcje: rollback switch, stay z current profile

**EC-E2**: Switch loses work
- In-progress task abandoned during switch
- Akcje: ensure drain completion, cancel switch jeśli risk

**EC-E3**: Switch makes things worse
- More workers but coordination overhead spikes
- Akcje: switch back, accept lesson learned

**EC-E4**: Customer-funded switch not pre-approved
- Operator switches without customer agreement
- Akcje: customer notification, may require negotiation

---

## 35.9. Acceptance + transition

```bash
$ aeis-cli phase35-status --project proj_customer_y_crm

Faza 35 (Build Orchestration) status:

  Active: yes (handles each phase 33 invocation)
  Profile: 2 (Solo balanced)
  Coordination overhead: 9% (within budget 11%)
  
  Per-phase orchestration:
   ✓ Phase 1: orchestrated successfully (sequential pattern)
   ✓ Phase 2: orchestrated successfully (partial parallel)
   ✓ Phase 3: orchestrated successfully (high parallel)
   ⠋ Phase 4: in progress (partial parallel)
   ⏸ Phase 5: queued
   ⏸ Phase 6: queued
  
  Lifetime stats:
   Tasks orchestrated: 47
   Tasks completed: 31 (66%)
   Cross-worker checks: 14 (all passed)
   Lock contentions: 8 (resolved)
   Worker failures: 1 (recovered)
   Profile switches: 0
   Faza 34 invocations triggered: 1 (resolved)

Faza 35 jest embedded inside faza 33 — no standalone DoD.
Continues automatically until all phases complete.
Po wszystkich phases → transition do Faza 36 (Build Completion).
```

---

# FAZA 36 — Build Completion

> **Spis sekcji**:
> - 36.1 — Sense fazy + post-build verification
> - 36.2 — Build completion checklist
> - 36.3 — Final coherence validation
> - 36.4 — Artifacts inventory
> - 36.5 — Worker decommissioning
> - 36.6 — Edge cases (15) + transition do faza 37

---

## 36.1. Sens fazy

### 36.1.1. Co Faza 36 robi

Po wszystkich build phases (faza 33 → fazy 35), faza 36 to **completion
checkpoint** before transitioning do testing (grupa F).

```
┌──────────────────────────────────────────────────────────────┐
│  Build Completion — final checkpoint                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (after fazy 33 completes wszystkie phases):           │
│   • All build phase artifacts                                 │
│   • Workers' final state                                      │
│   • Audit chain (full build history)                          │
│   • Cost tracking complete                                    │
│                                                              │
│  PROCESSING:                                                 │
│   • Final coherence validation (all artifacts together)       │
│   • Comprehensive Guards sweep                                │
│   • Artifacts inventory + integrity check                     │
│   • Cost reconciliation                                       │
│   • Worker decommissioning                                    │
│   • Build summary report                                      │
│                                                              │
│  OUTPUT:                                                     │
│   • Build complete certified                                  │
│   • Artifacts ready dla testing                               │
│   • Audit chain finalized dla build phase                     │
│   • Workers gracefully shut down                              │
│   • Project state: BUILD_COMPLETE                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 36.1.2. Wynik fazy 36 (DoD)

```
✓ All phase artifacts validated
✓ Final coherence check passed
✓ Comprehensive Guards sweep passed
✓ Artifacts inventory complete
✓ Cost reconciliation done
✓ Workers decommissioned
✓ Build summary report generated
✓ Audit chain entry: build_complete
✓ Project state: BUILD_COMPLETE (ready dla testing)
```

---

## 36.2. Build completion checklist

```
┌──────────────────────────────────────────────────────────────┐
│  Build Completion Checklist                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PHASE COMPLETIONS:                                           │
│   ✓ Phase 1 (Foundation) complete                             │
│   ✓ Phase 2 (KSeF Integration) complete                       │
│   ✓ Phase 3 (Core Features) complete                          │
│   ✓ Phase 4 (Payment Integration) complete                    │
│   ✓ Phase 5 (UX/I18n) complete                                │
│   ✓ Phase 6 (Quality + Deploy) — partial (testing pending)    │
│                                                              │
│  CODE ARTIFACTS:                                              │
│   ✓ Backend: 47 files generated                               │
│   ✓ Frontend: 68 files generated                              │
│   ✓ Migrations: 8 files                                       │
│   ✓ Configuration: 12 files                                   │
│   ✓ Documentation: 18 files                                   │
│   Total files: 153                                            │
│                                                              │
│  TEST ARTIFACTS:                                              │
│   ✓ Unit tests: 187                                           │
│   ✓ Integration tests: 67                                     │
│   ✓ E2E tests: 23                                             │
│   ✓ Human-like UI: 32                                         │
│                                                              │
│  GIT STATE:                                                   │
│   ✓ All branches up-to-date                                   │
│   ✓ build/* branches merged to develop                        │
│   ✓ develop ready dla integration testing                     │
│   ✗ main not yet updated (deployment phase)                   │
│                                                              │
│  GUARDS STATE:                                                │
│   Total findings during build:                                │
│   • Coherence: 47 INFO, 8 WARNING, 0 ERROR                    │
│   • Cost: 2 anomalies (operator-handled)                      │
│   • Security: 3 WARNING, 1 ERROR (resolved)                   │
│   • Quality: pending tests                                    │
│   • Provenance: 1247 entries created                          │
│   Net unresolved: 0 ✓                                         │
│                                                              │
│  COST RECONCILIATION:                                         │
│   Build budget: $148                                          │
│   Build actual: $142.30                                       │
│   Under budget by: $5.70 (3.9%) ✓                             │
│   Guards spent: $24.80 / $25 budget ✓                         │
│   Env spent: $14.50 / $16 budget ✓                            │
│                                                              │
│  TIMING:                                                      │
│   Build estimated: 5 weeks                                    │
│   Build actual: 4.2 weeks                                     │
│   Saved: 0.8 weeks ✓                                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 36.3. Final coherence validation

### 36.3.1. Comprehensive integration check

```
┌──────────────────────────────────────────────────────────────┐
│  Final Coherence Validation                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Validation scope: ENTIRE codebase                            │
│  Tier: 4 (opus, cross-system)                                 │
│  Cost: ~$5 (one-time deep check)                              │
│                                                              │
│  Validation checks:                                           │
│                                                              │
│  ARCHITECTURAL COHERENCE                                      │
│   ✓ Frontend ↔ Backend API contracts match                    │
│   ✓ DB schema ↔ ORM models consistent                         │
│   ✓ Authentication flow consistent across layers              │
│   ✓ Error handling patterns uniform                            │
│   ✓ Logging standards followed                                │
│                                                              │
│  KSIEGA COMPLIANCE                                            │
│   ✓ All Księga features implemented                            │
│   ✓ All AC covered by implementation                          │
│   ✓ Architecture matches Księga spec                           │
│   ✓ Naming conventions consistent z spec                       │
│                                                              │
│  CROSS-MODULE INTEGRATION                                     │
│   ✓ Customer module ↔ Invoice module                          │
│   ✓ Invoice module ↔ Payment module                           │
│   ✓ Payment module ↔ Stripe integration                       │
│   ✓ Invoice module ↔ KSeF integration                         │
│   ✓ Auth module ↔ all protected endpoints                     │
│                                                              │
│  COMPLIANCE INTEGRATION                                       │
│   ✓ GDPR data flows match design (faza 23)                    │
│   ✓ KSeF compliance end-to-end                                │
│   ✓ PCI scope minimized as planned                            │
│   ✓ WCAG 2.1 AA addressed (testing will verify)              │
│                                                              │
│  RISK MITIGATION VERIFICATION                                 │
│   ✓ R1 KSeF: integration robust, fallback present            │
│   ✓ R2 Stripe: PCI compliance verified                        │
│   ✓ R3 Customer scope: deferred decisions documented          │
│   ✓ R4 Customer availability: async approval flows present   │
│                                                              │
│  Verdict: ALL COHERENCE CHECKS PASSED                         │
│  Build is internally consistent.                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

---

## 36.4. Artifacts inventory

### 36.4.1. Comprehensive artifacts list

```
┌──────────────────────────────────────────────────────────────┐
│  Build Artifacts Inventory                                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CODE (153 files)                                             │
│   Backend:                                                    │
│    • main.py (entry point)                                    │
│    • config.py                                                │
│    • models/ (12 models)                                      │
│    • services/ (15 services)                                  │
│    • routes/ (20 endpoints)                                   │
│   Frontend:                                                   │
│    • app/ (28 components)                                     │
│    • pages/ (15 pages)                                        │
│    • hooks/ (10 hooks)                                        │
│    • i18n/ (translations PL+EN)                               │
│   Database:                                                   │
│    • 8 migration files                                        │
│   Configuration:                                              │
│    • Docker, .env templates, etc.                             │
│   Documentation:                                              │
│    • API docs, user docs (PL+EN), runbooks                    │
│                                                              │
│  TESTS (309 test files/scenarios)                             │
│   Unit: 187 tests                                             │
│   Integration: 67 tests                                       │
│   E2E: 23 scenarios                                           │
│   Human-like UI: 32 scenarios                                 │
│                                                              │
│  GIT REPOSITORY                                               │
│   Branches: 10 (main + develop + 8 build/*)                   │
│   Commits: 247                                                │
│   Authors: AEIS Worker 1, AEIS Worker 2, operator             │
│                                                              │
│  AUDIT CHAIN                                                  │
│   Entries: 1247                                               │
│   Hash chain: integrity ✓                                     │
│   Signatures: all valid                                       │
│   Size: ~12 MB                                                │
│                                                              │
│  ENVIRONMENTS                                                 │
│   Dev: lokalne (still up)                                     │
│   Staging: Hetzner CX21 (still up)                            │
│                                                              │
│  REPORTS                                                      │
│   Per-phase reports: 6                                        │
│   Cost reports: daily x 30                                    │
│   Guards summaries: per phase                                 │
│   Build progress logs: continuous                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 36.4.2. Artifact integrity verification

```
For each artifact category, verify:

  CODE:
    • All files present (no missing references)
    • Linter passes (no syntax errors)
    • Type checking passes
    • Imports valid
  
  TESTS:
    • All test files parseable
    • Test framework can discover all
    • Coverage reportable
  
  GIT:
    • All branches consistent
    • No uncommitted changes
    • Tags applied dla milestones
  
  AUDIT CHAIN:
    • Hash chain unbroken
    • Signatures valid
    • Time stamps consistent
  
  CONFIG:
    • All required env vars documented
    • No secrets w files
    • Sample configs provided
```

---

## 36.5. Worker decommissioning

### 36.5.1. Graceful shutdown

```
┌──────────────────────────────────────────────────────────────┐
│  Worker Decommissioning                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Worker 1 (Backend):                                          │
│   ⠋ Finishing current task (none, idle)                       │
│   ✓ Releasing all locks                                       │
│   ✓ Saving final state                                        │
│   ✓ Audit chain entry: worker_decommissioned                  │
│   ✓ Process terminated                                        │
│                                                              │
│  Worker 2 (Frontend):                                         │
│   ⠋ Finishing current task (none, idle)                       │
│   ✓ Releasing all locks                                       │
│   ✓ Saving final state                                        │
│   ✓ Audit chain entry: worker_decommissioned                  │
│   ✓ Process terminated                                        │
│                                                              │
│  Coordination layer:                                          │
│   ✓ Task queue archived (157 historical entries)              │
│   ✓ Locks released                                            │
│   ✓ Shared state preserved (read-only mode)                   │
│                                                              │
│  Environments:                                                │
│   ✓ Dev: still up (operator may need)                         │
│   ✓ Staging: still up (testing will use)                      │
│   ⏸ Decommission only po project closure (faza 41)            │
│                                                              │
│  Total worker resource usage:                                 │
│   Worker 1: 78h wallclock, $58.20 cost                        │
│   Worker 2: 71h wallclock, $29.20 cost                        │
│   Total: $87.40 + Guards $24.80 + Env $14.50 = $126.70        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 36.5.2. State preservation dla future revival

```
Workers decommissioned ale state preserved jeśli need revival:

  Reasons to revive workers:
   • Testing finds issues, need code fixes
   • Customer change request requires modifications
   • Production deployment needs adjustments
   
  Revival workflow:
   1. Load worker state from snapshot
   2. Reload skills
   3. Re-attach do coordination layer
   4. Resume per assigned tasks
   
  Cost dla revival: ~$2 per worker (model warm-up)
  Time: 5-10 min
```

---

## 36.6. Build summary report

### 36.6.1. Comprehensive build report

```
┌──────────────────────────────────────────────────────────────┐
│  Build Summary Report — Customer Y CRM                       │
│  Generated: 2026-06-15 14:30                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  PROJECT OVERVIEW                                            │
│   Customer: Customer Y                                        │
│   Type: SaaS CRM with payment integration                     │
│   D-level: D4                                                 │
│   Profile: Solo Balanced (2 workers, 1 staging)               │
│                                                              │
│  TIMING                                                       │
│   Build started: 2026-05-15                                   │
│   Build completed: 2026-06-15 (4.2 weeks)                     │
│   Estimated: 5 weeks                                          │
│   Saved: 0.8 weeks ✓                                          │
│                                                              │
│  COST                                                         │
│   Build cost: $142.30 (planned $148)                          │
│   Guards: $24.80 (planned $25)                                │
│   Environments: $14.50 (planned $16)                          │
│   Total faza E: $181.60 / $189 (3.9% under)                   │
│                                                              │
│   Project total so far: $338.50                               │
│   Customer Y commitment: €500                                 │
│   Remaining headroom: ~€100 dla testing + deploy              │
│                                                              │
│  DELIVERABLES                                                 │
│   Code: 153 files                                             │
│   Tests: 309 (pending execution)                              │
│   Documentation: 18 files (PL+EN)                             │
│   Migrations: 8                                               │
│                                                              │
│  QUALITY                                                      │
│   Coherence Guard: ✓ all passed                                │
│   Security Guard: ✓ no critical findings                      │
│   Cross-module integration: ✓ verified                         │
│   Compliance: ✓ GDPR + KSeF + PCI ready                        │
│                                                              │
│  WORKER UTILIZATION                                           │
│   Worker 1: 78h, 95% utilization, $58.20                      │
│   Worker 2: 71h, 88% utilization, $29.20                      │
│   Coordination overhead: 9% (budget 11%) ✓                    │
│                                                              │
│  EVENTS                                                       │
│   Faza 34 invocations: 1 (customer scope change, deferred)    │
│   Profile switches: 0                                         │
│   Worker failures: 1 (recovered cleanly)                      │
│   Provider outages: 0                                         │
│   Operator interventions: 18 (within estimate 25-30)          │
│                                                              │
│  RISK STATUS                                                  │
│   R1 KSeF complexity: ✓ mitigated (early integration)         │
│   R2 Stripe Polish: ✓ no issues                                │
│   R3 Scope creep: ✓ Council deferred 1 attempt                │
│   R4 Customer availability: ✓ async flows worked              │
│                                                              │
│  NEXT PHASE                                                   │
│   Faza 37: Quality Gates (test execution)                     │
│   Faza 38: Acceptance Testing                                 │
│   Estimated cost: $35                                         │
│   Estimated time: 1 week                                      │
│                                                              │
│  Operator review needed:                                      │
│   [● Approve build complete + proceed do testing]             │
│   [○ Request additional build work]                           │
│   [○ Pause project]                                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 36.6.2. Customer-facing build update (Polish)

```
Email do Customer Y Anna:

  Subject: Customer Y CRM — Etap budowy zakończony

  Szanowna Pani Anna,

  Z przyjemnością informuję, że etap budowy projektu został
  zakończony — 0.8 tygodnia przed terminem.

  CO ZOSTAŁO ZBUDOWANE:
   ✓ System CRM (zarządzanie klientami)
   ✓ Moduł fakturowania z integracją KSeF
   ✓ Płatności online via Stripe
   ✓ UI w języku polskim i angielskim
   ✓ Pełna zgodność z RODO
   ✓ Dostępność WCAG 2.1 AA

  KOSZT ETAPU:
   Planowany: $189
   Rzeczywisty: $182 (3.9% pod budżetem)

  CO DALEJ:
   • Etap testowania i kontroli jakości (1 tydzień)
   • Dostarczenie pre-produkcji do Państwa wglądu
   • Wdrożenie produkcyjne

  Po testach przekażę Państwu link do staging environment
  do osobistego sprawdzenia przed wdrożeniem.

  Z poważaniem,
  Robert
```

---

## 36.7. Edge Cases — Build Completion (15)

### Kategoria A — Validation issues (5)

**EC-A1**: Final coherence check fails
- Cross-module integration issue found
- Akcje: targeted fix, may revive workers, may need faza 34

**EC-A2**: Missing files detected
- Some artifacts not generated
- Akcje: regenerate, may need re-run affected phase

**EC-A3**: Compliance gap discovered
- GDPR missing element
- Akcje: address, may delay testing transition

**EC-A4**: Risk not properly mitigated
- Documented mitigation not actually implemented
- Akcje: implement, validate, audit log

**EC-A5**: Quality threshold failure
- Last-minute Guards finding
- Akcje: fix or operator override w reasoning

### Kategoria B — Resource issues (4)

**EC-B1**: Cost reconciliation discrepancy
- Tracked $142.30 vs actual $148
- Akcje: investigate, audit reconciliation, document

**EC-B2**: Workers won't shut down cleanly
- Stuck process
- Akcje: force terminate, save what state possible

**EC-B3**: Audit chain integrity broken
- Provenance Guard reports issue
- Akcje: forensic, may need to mark gap, restore

**EC-B4**: Disk space issue (snapshots filling)
- Workspace 80% full
- Akcje: archive snapshots, cleanup, expand

### Kategoria C — Reporting + transition (3)

**EC-C1**: Build summary generation fails
- LLM-based report has issues
- Akcje: regenerate, simpler format, manual fallback

**EC-C2**: Customer notification ill-timed
- Customer notified before operator review
- Akcje: hold notification, operator confirms first

**EC-C3**: Operator wants additional build before testing
- Quality concerns
- Akcje: revive workers, queue additional tasks, re-do faza 36

### Kategoria D — Recovery (3)

**EC-D1**: Build completion interrupted
- Crash during faza 36
- Akcje: resume from checkpoint, re-validate

**EC-D2**: State preservation fails
- Worker state can't be saved
- Akcje: reconstruction from logs, accept loss

**EC-D3**: Phase 36 itself takes too long
- 2 hours dla validation/reporting
- Akcje: accept, optimize dla future projects

---

## 36.8. Acceptance + transition do faza 37

```bash
$ aeis-cli phase36-acceptance-test --project proj_customer_y_crm

[1/9] All phase artifacts validated                    ✓ PASS
[2/9] Final coherence check passed                     ✓ PASS
[3/9] Comprehensive Guards sweep                       ✓ PASS
[4/9] Artifacts inventory complete                     ✓ PASS (153 files)
[5/9] Cost reconciliation done                         ✓ PASS ($142.30)
[6/9] Workers decommissioned                           ✓ PASS (2/2)
[7/9] Build summary report generated                   ✓ PASS
[8/9] Audit chain entry build_complete                 ✓ PASS
[9/9] Project state: BUILD_COMPLETE                    ✓ PASS

DoD: 9/9 ✓
Phase 36 ACCEPTED. Ready dla Phase 37 (Quality Gates Testing).

═══ GROUP E (Wykonanie) COMPLETE ═══
Ready dla Phase 37 (Testing, Group F).
```

---

# Status faz 34-36

🟢 **Wszystkie 3 fazy complete**

**Zawiera**:
- ✓ Faza 34 — Mid-Build Council Reconvening (auto-triggers, operator-triggers, mini-deliberation workflow z customer scope change example, 4 build impact categories, 15 edge cases)
- ✓ Faza 35 — Build Orchestration **z full parallel mechanics** (worker coordination primitives 3, cross-worker Coherence Guard tier 3+4, layer parallelism patterns, error recovery cascades, mid-build profile switching, 22 edge cases)
- ✓ Faza 36 — Build Completion (final coherence validation, artifacts inventory, worker decommissioning, build summary report z customer notification, 15 edge cases)

**Total edge cases w pliku**: 52 cases (15+22+15)

**Profile-aware runtime mechanics zaimplementowane**:
- ✓ Worker coordination primitives (queue, locks, shared state)
- ✓ Cross-worker Coherence Guard (Tier 3 + Tier 4)
- ✓ Cross-worker check cost scaling O(N²)
- ✓ Layer parallelism patterns per phase (sequential / partial / high parallel)
- ✓ Dynamic task generation
- ✓ Error recovery cascades z 5 categories
- ✓ Mid-build profile switching workflow
- ✓ Live orchestration dashboard

**Grupa E (Wykonanie) COMPLETE**: 5 faz (32-33 w part 1, 34-36 w part 2)
**Łącznie 36 z 41 faz frozen**

⏳ **Po Twojej akceptacji** → **soft freeze faz 34-36** + przejście do **Faza 37 — Quality Gates** (start grupy F "Testowanie").

🎯 **Build is DONE**: 153 files, 309 tests ready, $142.30 cost ($5.70 under budget), 4.2 weeks (0.8 weeks under). Workers decommissioned cleanly. Ready dla testing phase.

Pozostały **5 faz** w 2 grupach:
- **Grupa F** (2 fazy 37-38) — Quality Gates + Acceptance Testing
- **Grupa G** (3 fazy 39-41) — Pre-Deploy + Deploy + Closure
