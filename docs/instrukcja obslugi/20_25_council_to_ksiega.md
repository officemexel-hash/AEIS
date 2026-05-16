# FAZY 20-25 — Deliberacja → Księga (Grupa C)

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: C — Deliberacja → Księga (1-6 z 6) — cała grupa C
> **Zależności**: Fazy 1-19 zakończone (operator setup + project entity + Council ready)
> **Następnik**: Faza 26 (Model Selection — start grupy D Planowanie)
>
> **⚠ Krytyczna grupa**:
> Ta grupa to **serce AEIS lifecycle**. Multi-role AI Council debate
> transformuje operator's pomysł w formal project documentation (Księga).
> Wszystko po grupie C (planowanie / wykonanie / testowanie / wdrożenie)
> bazuje na Księdze.
>
> **Filozofia Council deliberation**:
> - Multi-perspective: różne role widzą problem inaczej
> - Adversarial: Critic challenges, Specialists override
> - Iterative: rounds aż do consensus lub timeout
> - Auditable: każdy verdict signed, traceable
> - Operator-supervised: hard gate na finalization (per D-level)
>
> **Wspólna struktura każdej fazy w grupie C**:
> - Sense + miejsce w council deliberation flow
> - Inputs (z poprzedniej fazy)
> - Workflow (mechanics deliberation)
> - Outputs (concrete artifacts)
> - Decision points (Council vs operator)
> - Edge cases (15-22)
> - Acceptance + transition

---

# FAZA 20 — Council Convening

> **Spis sekcji**:
> - 20.1 — Sense fazy + start deliberation
> - 20.2 — Council awakening sequence
> - 20.3 — Briefing distribution + ingestion
> - 20.4 — Question formulation (key debate questions)
> - 20.5 — Council readiness verification
> - 20.6 — Edge cases (16) + transition do fazy 21

---

## 20.1. Sens fazy + start deliberation

### 20.1.1. Co Faza 20 robi

Faza 19 przygotowała Council (roles, knowledge bases, briefing).
Faza 20 to **uruchomienie Council** — actual start deliberation.

```
┌──────────────────────────────────────────────────────────────┐
│  Council Convening — od config do first thinking              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z fazy 19):                                          │
│   • Council configured (12 roles, models, KBs)               │
│   • Briefing package prepared                                 │
│   • Project context complete                                  │
│                                                              │
│  PROCESSING (system + Council):                              │
│   • Awakening sequence (load each role z context)            │
│   • Briefing distribution (each role reads relevant docs)    │
│   • Question formulation (Chair generates key questions)     │
│   • Initial readiness verification                           │
│                                                              │
│  OUTPUT (Council ready dla deliberation):                    │
│   • All roles "loaded" (context + KBs in memory)             │
│   • Each role has its briefing summary                       │
│   • Key questions queue established                          │
│   • Audit chain entry: council_convened (signed)             │
│   • Project state: READY_FOR_INITIAL_VERDICTS                │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 20.1.2. Czas trwania + cost

```
Convening time:        2-4 min (briefing ingestion is fast)
Convening cost:        ~$1-2 (briefing processing per role)
Operator interaction:  minimal (just observe + approve start)
```

### 20.1.3. Wynik fazy 20 (DoD)

```
✓ All Council roles awakened (loaded z context)
✓ Briefing distributed + ingested
✓ Key questions formulated
✓ Readiness verified
✓ Operator approved start (hard gate jeśli D4+)
✓ Audit chain entry: council_convened
✓ Project state: READY_FOR_INITIAL_VERDICTS
```

---

## 20.2. Council awakening sequence

### 20.2.1. Per-role awakening

```
┌──────────────────────────────────────────────────────────────┐
│  Council Awakening — Customer Y CRM                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Awakening sequence (parallel for efficiency):               │
│                                                              │
│  ⠋ Council Chair                  loading...    (claude-opus)│
│  ⠋ Planner                        loading...    (claude-son.)│
│  ⠋ Critic                         loading...    (gpt-5)      │
│  ⠋ Security                       loading...    (claude-opus)│
│  ⠋ Payment Specialist             loading...    (claude-opus)│
│  ⠋ UX Designer                    loading...    (claude-son.)│
│  ⠋ Compliance (GDPR)              loading...    (bielik-11b) │
│  ⠋ Compliance (PCI)               loading...    (gpt-5)      │
│  ⠋ Compliance (KSeF)              loading...    (bielik-11b) │
│  ⠋ QA Lead                        loading...    (gpt-5)      │
│  ⠋ i18n Specialist                loading...    (claude-son.)│
│  ⠋ Risk Assessor                  loading...    (claude-opus)│
│                                                              │
│  Per-role load:                                              │
│   1. Role definition (system prompt)                         │
│   2. Project context (briefing summary)                      │
│   3. Knowledge base context (RAG-relevant chunks)            │
│   4. Operator's notes for this role                          │
│   5. Voting weight + ordering position                       │
│                                                              │
│  After loading:                                              │
│   ✓ All 12 roles ready                                       │
│   ✓ Total context: ~85K tokens (within Opus 200K limit)     │
│   ✓ Knowledge base RAG indices active                         │
│   Estimated processing: 2 min (parallel)                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 20.2.2. Role-specific context

Każda rola dostaje **same project briefing + role-specific augmentation**:

```yaml
# Council Chair context
role_chair:
  system_prompt: |
    You are Council Chair for AEIS deliberation.
    Your job: moderate, synthesize, ensure all voices heard.
    You don't have strong opinions on technical details —
    you orchestrate the discussion.
  
  briefing: <full project briefing>
  
  knowledge_base: <none specific, general AEIS process docs>
  
  voting_weight: 1.0
  speaking_position: 1 (opens session)

# Critic context
role_critic:
  system_prompt: |
    You are Critic. Your job: challenge plans, surface risks,
    play devil's advocate. Be rigorous, not adversarial.
    If plan is good, say so. If not, say why specifically.
  
  briefing: <full project briefing>
  
  knowledge_base: <general best practices, common failure patterns>
  
  voting_weight: 1.5  # stronger vote
  speaking_position: 3 (after Planner)
  veto_power: true (jeśli identifies critical security/legal issue)

# Compliance (KSeF) context
role_compliance_ksef:
  system_prompt: |
    You are Polish e-invoicing compliance expert (KSeF).
    Your job: ensure project meets Polish e-invoicing law.
    You cite specific KSeF specifications, focus on practical
    compliance not theoretical.
  
  briefing: <full project briefing>
  
  knowledge_base: <KSeF specs, FA(2) format, KSeF API docs,
                   Polish e-invoicing law>
  
  voting_weight: 1.0
  speaking_position: 9 (compliance round)
  specialist_override: true (jeśli KSeF non-compliance critical)
```

### 20.2.3. Awakening failures

```
⚠ Awakening Issues

  Critic (gpt-5):
   ✗ Failed to load (model timeout)
   Akcje:
    [Retry z fallback model (gpt-4o)]
    [Skip role temporarily (quorum: 11/12, still meets)]
    [Pause Council convening, investigate]

  Compliance (KSeF) (bielik-11b):
   ⚠ Slow loading (lokalne, GPU shared z Council Chair)
   Akcje:
    [Wait 30s additional]
    [Switch to API model (claude-haiku)]
   
  i18n Specialist:
   ✓ Loaded successfully
```

---

## 20.3. Briefing distribution + ingestion

### 20.3.1. Briefing format per role

Same project briefing, ale różnie reformatted per role's focus:

```
┌──────────────────────────────────────────────────────────────┐
│  Briefing Distribution — Per-Role Customization              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Role: Council Chair                                         │
│  Focus: full overview, no specialty depth                    │
│  Briefing length: ~5K tokens                                 │
│                                                              │
│  Role: Planner                                               │
│  Focus: technical architecture, implementation paths         │
│  Briefing length: ~8K tokens (z technical context expanded) │
│                                                              │
│  Role: Critic                                                │
│  Focus: same as Planner (mirroring) + risk angles            │
│  Briefing length: ~8K tokens                                 │
│                                                              │
│  Role: Security                                              │
│  Focus: security/compliance angles                           │
│  Briefing length: ~6K tokens (security context expanded)     │
│                                                              │
│  Role: Compliance (KSeF)                                     │
│  Focus: invoicing-specific, Polish regulations               │
│  Briefing length: ~4K tokens (only KSeF-relevant context)    │
│                                                              │
│  ... per each role                                           │
│                                                              │
│  Cost dla all distributions: ~$0.80 (per-role processing)    │
└──────────────────────────────────────────────────────────────┘
```

### 20.3.2. Per-role briefing summary

Po ingestion, każda rola produces krótki "I've understood" summary:

```
Example — Compliance (KSeF) acknowledgment:

  "I've reviewed the project briefing. Key understanding:
   
   • Customer Y CRM with KSeF e-invoicing
   • FA(2) format mandatory
   • 5-year archive retention
   • Polish jurisdiction
   • Customer-funded, deadline 2026-06-30
   
   My focus: ensure KSeF compliance from day 1.
   Primary concerns I'll raise:
   1. KSeF API rate limits (operator already flagged)
   2. Invoice signature workflow
   3. Archive integrity over 5 years
   4. Edge cases dla draft invoices
   
   Ready to participate."

Cost per acknowledgment: ~$0.05
```

---

## 20.4. Question formulation

### 20.4.1. Chair generates key questions

Po briefing ingestion, Chair formuluje **key debate questions**:

```
┌──────────────────────────────────────────────────────────────┐
│  Key Debate Questions — Customer Y CRM                       │
│  Generated by Council Chair                                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ARCHITECTURAL                                               │
│   1. Monolithic vs services architecture (small scale 50    │
│      users — keep simple)                                    │
│   2. Database choice (PostgreSQL given operator preference)  │
│   3. Frontend framework (React + TypeScript)                 │
│                                                              │
│  COMPLIANCE                                                  │
│   4. KSeF integration timing (early vs late integration)     │
│   5. GDPR data flow (where data lives, who processes)        │
│   6. PCI scope minimization (Stripe handles vs operator)     │
│                                                              │
│  PAYMENT FLOW                                                │
│   7. Stripe integration depth (Checkout vs Elements)         │
│   8. Refund handling (manual vs automated)                   │
│   9. Subscription support (out of scope, but verify)         │
│                                                              │
│  INTERNATIONALIZATION                                         │
│   10. PL primary, EN fallback (translation strategy)          │
│   11. Currency display (PLN primary, EUR for EU customers)    │
│                                                              │
│  TECHNICAL CONCERNS (z operator notes)                       │
│   12. KSeF API rate limits                                   │
│   13. Customer's legacy ERP (no integration in scope, verify)│
│   14. Polish accessibility WCAG (gov-funded customer)        │
│                                                              │
│  DELIVERY                                                    │
│   15. MVP scope (8 weeks deadline very tight)                │
│   16. Phasing strategy (phase 1 must-have, phase 2 P1)       │
│   17. Customer training/handoff                              │
│                                                              │
│  RISKS (z faza 18 risk register)                             │
│   18. Mitigation plans verification                          │
│                                                              │
│  Total: 18 key questions                                     │
│  Estimated rounds needed: 3 (z early consensus check)        │
│                                                              │
│  [Approve question set]  [Add questions]  [Remove]           │
└──────────────────────────────────────────────────────────────┘
```

### 20.4.2. Operator review of questions

Operator może edytować question list przed deliberation:

```
Settings → Council Convening → Questions

  AEIS-generated questions:
   18 questions formulated by Chair
  
  Operator additions:
   ☑ "Should we use Bielik dla customer-facing PL content?"
   ☑ "How to handle customer's existing customer database
       migration (CSV import scope)?"
  
  Operator removals:
   ☐ Remove question 17 (training/handoff)
       Reason: out of scope, operator handles separately
  
  Question prioritization:
   P0 (must address): 1, 4, 5, 6, 12, 15
   P1 (should):       2, 3, 7, 8, 10, 11, 13
   P2 (if time):      14, 16, 18, +operator's 2
  
  [Approve final question set]
```

---

## 20.5. Council readiness verification

### 20.5.1. Pre-deliberation checks

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Deliberation Verification                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Roles:                                                      │
│   ✓ All 12 roles awakened                                    │
│   ✓ Each role acknowledged briefing                          │
│   ✓ No role failed loading                                    │
│                                                              │
│  Knowledge bases:                                            │
│   ✓ All required KBs accessible                              │
│   ✓ RAG retrieval tested per role                            │
│                                                              │
│  Questions:                                                  │
│   ✓ Question set finalized (20 questions, prioritized)       │
│   ✓ Operator approved                                        │
│                                                              │
│  Hard gates:                                                 │
│   ✓ Council finalization gate (D4) registered                │
│   ✓ Operator notification configured                         │
│                                                              │
│  Budget tracking:                                            │
│   ✓ Cost Guard active                                         │
│   ✓ Budget reservation $9.60 (3 rounds estimated)            │
│   ✓ Alerts configured (50%, 80%, 100% thresholds)            │
│                                                              │
│  Audit chain:                                                │
│   ✓ Provenance Guard ready                                   │
│   ✓ Will record every verdict, vote, decision                │
│                                                              │
│  Operator availability:                                      │
│   ✓ Operator online                                          │
│   ✓ Mobile companion paired (faza 4.5)                       │
│   ⚠ Operator quiet hours: 22:00-07:00 (current 14:32, OK)    │
│                                                              │
│  All checks passed.                                          │
│  Ready dla Phase 21 (Initial Verdicts).                      │
│                                                              │
│  [Start deliberation]  [Pause + review]                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 20.6. Edge Cases — Council Convening (16)

### Kategoria A — Awakening issues (4)

**EC-A1**: Role model unavailable
- Critical role's model down → fallback (lower-tier same family) lub pause Council

**EC-A2**: Context window exhausted
- Briefing too large dla role's model → reduce briefing scope, switch model

**EC-A3**: Knowledge base loading slow
- RAG indexing 5+ min dla one role → background load, role joins late

**EC-A4**: Awakening cost spike
- Per-role cost 5x estimated → investigate (likely briefing too verbose)

### Kategoria B — Briefing issues (4)

**EC-B1**: Briefing summary contradicts project
- Role's "I understood" doesn't match operator's intent → re-brief role

**EC-B2**: Knowledge base z stale info
- Compliance role uses old GDPR docs → update KB before continue

**EC-B3**: Briefing missing key context
- Role asks question that should be in briefing → add to briefing, restart role

**EC-B4**: Briefing leaks sensitive info
- Customer-private data accidentally w briefing → redact, restart Council

### Kategoria C — Question formulation issues (4)

**EC-C1**: Chair misses key question
- Operator notices gap → add question, regenerate priority

**EC-C2**: Question redundant z existing
- Multiple questions on same topic → consolidate

**EC-C3**: Question scope wrong (out of scope)
- Question about "mobile app" (out of scope per faza 18) → remove

**EC-C4**: Operator wants different question framing
- Edit question wording per operator's preference

### Kategoria D — Operator interaction (4)

**EC-D1**: Operator absent dla approval
- Hard gate timeout per Production preset (∞) → wait

**EC-D2**: Operator approves but reservations
- Comment added to audit chain, Council notified

**EC-D3**: Operator wants pause early
- Pre-deliberation pause → save state, resume later

**EC-D4**: Multiple operators (team)
- Team approval flow → first-clicks-wins, audit logs both

---

## 20.7. Acceptance + transition do fazy 21

```bash
$ aeis-cli phase20-acceptance-test --project proj_customer_y_crm

[1/7] All Council roles awakened                       ✓ PASS (12/12)
[2/7] Briefing distributed + ingested                  ✓ PASS
[3/7] Key questions formulated                         ✓ PASS (20 questions)
[4/7] Operator approved questions                      ✓ PASS
[5/7] Pre-deliberation checks                          ✓ PASS
[6/7] Hard gates registered                            ✓ PASS
[7/7] Audit chain entry council_convened               ✓ PASS

DoD: 7/7 ✓
Phase 20 ACCEPTED. Council ready dla Phase 21 (Initial Verdicts).
```

---

# FAZA 21 — Initial Verdicts

> **Spis sekcji**:
> - 21.1 — Sense fazy + parallel verdict generation
> - 21.2 — Per-role independent verdict
> - 21.3 — Verdict structure
> - 21.4 — Aggregation + first analysis
> - 21.5 — Edge cases (15) + transition do fazy 22

---

## 21.1. Sens fazy + parallel verdicts

### 21.1.1. Co Faza 21 robi

Każdy Council member produces **initial verdict independently** —
without seeing others' opinions yet. To zapewnia że każda role thinks
through problem niezależnie, bez group-think.

```
┌──────────────────────────────────────────────────────────────┐
│  Initial Verdicts — independent thinking                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CRITICAL DESIGN PRINCIPLE:                                  │
│  Each role responds to questions WITHOUT seeing other        │
│  roles' answers. This produces:                              │
│                                                              │
│   ✓ Diverse opinions (no anchoring effect)                   │
│   ✓ Independent risk assessments                             │
│   ✓ Multiple solution proposals                              │
│   ✓ Clear minority opinions surface                          │
│                                                              │
│  Aggregation happens AFTER all verdicts collected.           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 21.1.2. Wynik fazy 21 (DoD)

```
✓ All 12 roles produced initial verdict
✓ Verdicts collected w structured format
✓ Aggregation analysis done
✓ Areas of consensus identified
✓ Areas of disagreement identified
✓ Audit chain entry: initial_verdicts (signed per role)
✓ Project state: READY_FOR_DELIBERATION_ROUNDS
```

---

## 21.2. Per-role independent verdict

### 21.2.1. Verdict generation workflow

```
For each role (parallel):
  1. Receive question set + briefing context
  2. Think through each question
  3. Form opinion based on role's perspective + KB
  4. Articulate verdict w structured format
  5. Submit verdict (sealed until all collected)
```

### 21.2.2. Per-role verdict prompt

```yaml
verdict_generation:
  system_prompt: |
    You are {role_name}. Review the question set below and
    provide your initial verdict on each.
    
    For EACH question, provide:
    - Your stance (agree/disagree/uncertain)
    - Reasoning (z perspective of your role)
    - Specific concerns (if any)
    - Suggested approach (if applicable)
    
    Do NOT see or consider other roles' opinions.
    Be direct, specific, technical.
    Reference your knowledge base when relevant.
  
  questions: <full question set z faza 20>
  
  output_format: structured JSON
  
  max_tokens_per_verdict: 2000
  estimated_cost: $0.30-0.80 per role (zależne od model + length)
```

### 21.2.3. Verdict examples

```
Example — Critic verdict on Q4 (KSeF integration timing):

{
  "question_id": "Q4",
  "stance": "concern",
  "reasoning": "Operator notes flag KSeF rate limits as risk R1.
                Late integration creates compounding risk: late
                discovery of API quirks, no time dla fallback.
                Early integration (week 1-2) catches issues when
                buffer exists.",
  "specific_concerns": [
    "KSeF documentation incomplete dla edge cases (drafts, voids)",
    "Rate limits unclear — risk dla bulk operations",
    "Test environment may differ from production"
  ],
  "suggested_approach": "Phase 1 (week 1-2): KSeF integration POC.
                          Phase 2: full implementation with learnings.
                          Maintains buffer dla unknowns.",
  "confidence": 0.85,
  "veto_consideration": false
}

Example — Compliance (KSeF) verdict on Q4:

{
  "question_id": "Q4",
  "stance": "agree_with_modification",
  "reasoning": "Early integration absolutely critical. KSeF systems
                Polish-specific quirks (e.g., NIP UE handling, foreign
                currency invoicing edge cases). Late discovery =
                project derailment.",
  "specific_concerns": [
    "FA(2) schema validation strict — discovery testing essential",
    "Customer Y likely has existing customer NIPs needing migration",
    "Archive structure must be correct from Day 1 (5-year retention)"
  ],
  "suggested_approach": "Pre-week 1: integration test z KSeF sandbox.
                          Week 1: validate operator's NIP handling.
                          Week 2-3: full FA(2) flow.
                          Buffer week 7 dla edge case fixes.",
  "confidence": 0.95,
  "specialist_override": false  // not yet — depends on consensus
}

Example — Risk Assessor verdict on Q5 (GDPR data flow):

{
  "question_id": "Q5",
  "stance": "high_priority",
  "reasoning": "Multi-vendor data flow (Stripe, SendGrid, KSeF, our DB)
                creates complex GDPR landscape. Each transfer must be
                documented (Art. 30), DPAs signed, data minimized.",
  "specific_concerns": [
    "Stripe is US-based — adequacy decision applies but DPA needed",
    "SendGrid US-based — same issue",
    "Customer Y is data controller, operator is processor",
    "Customer's clients are data subjects — their rights apply",
    "Cross-border flow requires explicit consent flow"
  ],
  "suggested_approach": "Faza 23 dedicated GDPR data flow design.
                          DPA templates ready w faza 24.
                          DPIA dla high-risk processing (payment +
                          health data jeśli any).",
  "confidence": 0.90,
  "veto_consideration": false
}
```

### 21.2.4. Verdict generation parallel execution

```
┌──────────────────────────────────────────────────────────────┐
│  Initial Verdicts — Parallel Generation                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Status:                                                     │
│   ⠋ Council Chair                generating...   45%         │
│   ✓ Planner                      complete (3.2 min, $0.42)   │
│   ⠋ Critic                       generating...   78%         │
│   ⠋ Security                     generating...   62%         │
│   ✓ Payment Specialist           complete (2.8 min, $0.38)   │
│   ⠋ UX Designer                  generating...   55%         │
│   ⠋ Compliance (GDPR)            generating...   71%         │
│   ⠋ Compliance (PCI)             generating...   68%         │
│   ⠋ Compliance (KSeF)            generating...   82%         │
│   ⠋ QA Lead                      generating...   59%         │
│   ⠋ i18n Specialist              generating...   65%         │
│   ⠋ Risk Assessor                generating...   74%         │
│                                                              │
│  Parallel execution: yes (12 simultaneous)                   │
│  Estimated completion: 2 min remaining                       │
│  Total estimated cost: $5.20                                 │
│  Current spent: $3.10                                        │
│                                                              │
│  [Pause]  [Cancel]  [View live progress]                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 21.3. Verdict structure

### 21.3.1. Standardized verdict format

Każdy verdict ma identyczną strukturę dla aggregation:

```json
{
  "verdict_id": "v_xyz123",
  "role": "compliance_ksef",
  "model": "bielik-11b",
  "round": 1,
  "round_type": "initial_verdicts",
  "questions_addressed": [Q1, Q2, ..., Q20],
  
  "per_question_verdicts": {
    "Q4": {
      "stance": "agree_with_modification",
      "reasoning": "...",
      "specific_concerns": [...],
      "suggested_approach": "...",
      "confidence": 0.95,
      "specialist_override": false
    },
    ...
  },
  
  "overall_assessment": {
    "project_viability": "high",
    "operator_approach_alignment": "strong",
    "primary_concerns_summary": "KSeF complexity, payment compliance",
    "recommendations": [
      "Early KSeF integration",
      "Dedicated PCI scope minimization session"
    ]
  },
  
  "metadata": {
    "ts": "2026-05-01T15:32:18Z",
    "tokens_in": 8420,
    "tokens_out": 1840,
    "cost_usd": 0.32,
    "duration_sec": 184
  },
  
  "signature": "ed25519:..."
}
```

### 21.3.2. Verdict storage

```
~/.sylion/<op>/projects/customer_y_crm/council/round_1_verdicts/
├── v_chair_xyz123.json
├── v_planner_abc456.json
├── v_critic_def789.json
├── v_security_ghi012.json
├── v_payment_jkl345.json
├── v_ux_mno678.json
├── v_gdpr_pqr901.json
├── v_pci_stu234.json
├── v_ksef_vwx567.json
├── v_qa_yza890.json
├── v_i18n_bcd123.json
└── v_risk_efg456.json

Each file:
  • Append-only
  • Signed by operator's Ed25519 key
  • Linked w audit chain
  • Cannot be modified post-write
```

---

## 21.4. Aggregation + first analysis

### 21.4.1. Aggregation algorithm

Po wszystkich verdictach, system aggreguje:

```python
def aggregate_verdicts(round_verdicts):
    aggregation = {}
    
    for question in question_set:
        per_question_stances = []
        for role_verdict in round_verdicts:
            stance = role_verdict.per_question_verdicts[question.id]
            per_question_stances.append(stance)
        
        aggregation[question.id] = {
            "consensus_level": calculate_consensus(per_question_stances),
            "majority_stance": majority_vote(per_question_stances),
            "minority_stances": minority_opinions(per_question_stances),
            "concerns_raised": all_concerns(per_question_stances),
            "approaches_suggested": all_approaches(per_question_stances),
            "specialist_overrides": specialist_opinions(per_question_stances)
        }
    
    return aggregation
```

### 21.4.2. Consensus visualization

```
┌──────────────────────────────────────────────────────────────┐
│  Initial Verdicts — Aggregation Analysis                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  CONSENSUS ANALYSIS (per question)                           │
│                                                              │
│  Question                              Consensus Level       │
│  ──────────────────────────────────  ─────────────────  │
│  Q1 (architecture)                     ████████████ 92% ✓    │
│  Q2 (database)                         ████████████ 100% ✓   │
│  Q3 (frontend)                         ████████████ 100% ✓   │
│  Q4 (KSeF timing)                      ███████░░░░░ 58% ⚠    │
│  Q5 (GDPR data flow)                   ████████░░░░ 75% ✓    │
│  Q6 (PCI scope)                        ████████░░░░ 75% ✓    │
│  Q7 (Stripe integration)               █████░░░░░░░ 42% ⚠    │
│  Q8 (refund handling)                  ████████░░░░ 75% ✓    │
│  Q9 (subscriptions)                    ████████████ 100% ✓   │
│  Q10 (translation strategy)            ████████░░░░ 75% ✓    │
│  Q11 (currency display)                ████████████ 92% ✓    │
│  Q12 (KSeF rate limits)                ███████░░░░░ 67% ⚠    │
│  Q13 (legacy ERP)                      ████████████ 100% ✓   │
│  Q14 (Polish accessibility WCAG)       ████████░░░░ 75% ⚠    │
│  Q15 (MVP scope)                       █████░░░░░░░ 42% ⚠    │
│  Q16 (phasing strategy)                ███████░░░░░ 67% ⚠    │
│  Q17 (training/handoff)                ████████████ 100% ✓   │
│  Q18 (risk mitigations)                ████████░░░░ 75% ✓    │
│  Q19 (Bielik dla PL content)           ███████░░░░░ 58% ⚠    │
│  Q20 (CSV migration)                   ████████░░░░ 75% ✓    │
│                                                              │
│  Strong consensus (>=85%): 5 questions                       │
│  Moderate consensus (70-85%): 8 questions                    │
│  Weak consensus (50-70%): 5 questions ⚠                      │
│  No consensus (<50%): 2 questions ⚠⚠                         │
│                                                              │
│  Areas needing deliberation rounds:                          │
│   • Q4 (KSeF timing) — 5 different timelines proposed        │
│   • Q7 (Stripe integration) — Checkout vs Elements split     │
│   • Q12 (rate limits) — 2 mitigation strategies              │
│   • Q14 (WCAG) — full vs partial compliance                  │
│   • Q15 (MVP scope) — significant disagreement               │
│   • Q16 (phasing) — phasing logic differs                    │
│   • Q19 (Bielik usage) — quality vs cost trade-off           │
│                                                              │
│  Specialist overrides flagged: 0                             │
│  (No role used override w initial round)                     │
│                                                              │
│  Estimated rounds needed:                                    │
│   • Strong consensus questions: 0 additional rounds          │
│   • Moderate: probably 1 round to align                      │
│   • Weak: 2 rounds dla resolution                            │
│   • No consensus: 2-3 rounds + possibly operator decision    │
│                                                              │
│  [View per-question detailed verdicts]                       │
│  [Proceed to Phase 22 (Deliberation Rounds)]                 │
└──────────────────────────────────────────────────────────────┘
```

### 21.4.3. Operator preview

Operator może zobaczyć detailed verdicts przed Phase 22:

```
Per-question detail view:

Q4 (KSeF integration timing):
  Stances:
    • Compliance (KSeF):     Early integration (week 1-2)  ← strong
    • Critic:                Early integration             ← agree
    • Risk Assessor:         Early integration             ← agree
    • Security:              Early-medium                  ← align
    • Planner:               Medium (week 3-4)             ← concern
    • Council Chair:         Defer to specialists           ← neutral
    • Other 6 roles:         Defer to specialists           ← neutral
  
  Majority: Early integration (5 specific votes)
  Concerns:
    • Discovery testing dla edge cases
    • Buffer dla unknowns
    • Customer NIP migration timing
  
  Suggested approach:
    Pre-week 1: KSeF sandbox POC
    Week 1-2: full integration
    Buffer: week 7 dla fixes
```

---

## 21.5. Edge Cases — Initial Verdicts (15)

### Kategoria A — Generation issues (4)

**EC-A1**: Role timeout dla verdict
- Model takes >10 min, exceeds timeout
- Akcje: extend, switch model, skip role (lower quorum)

**EC-A2**: Role produces invalid format
- LLM returns prose instead of JSON
- Akcje: retry z stricter prompt, parse manually, mark role partial

**EC-A3**: Cost overrun dla generation
- Round costs 2x estimate ($10 vs $5)
- Akcje: investigate, switch cheaper models, operator approves

**EC-A4**: Role refuses to verdict
- Role says "insufficient context" → re-brief, augment KB

### Kategoria B — Verdict quality (4)

**EC-B1**: Verdict shallow (one-liner answers)
- Role gave low-effort verdict → re-prompt z deeper requirement

**EC-B2**: Verdict contradicts briefing
- Role mentions "mobile app" (out of scope) → re-prompt, fix briefing

**EC-B3**: Verdict references wrong KB
- Role uses outdated KSeF info → update KB, regenerate

**EC-B4**: Verdict shows hallucination
- Role cites fabricated regulation → verify, regenerate, flag KB issue

### Kategoria C — Aggregation issues (4)

**EC-C1**: Aggregation algorithm fails
- Mismatched question IDs across verdicts → manual reconciliation

**EC-C2**: Consensus calculation wrong
- Algorithm bug shows false consensus → verify, fix

**EC-C3**: Operator disagrees z aggregation
- "I see consensus differently" → operator override z reasoning

**EC-C4**: Specialist override missed
- Role marked override but algorithm missed → manual flag, treat as override

### Kategoria D — Operator interaction (3)

**EC-D1**: Operator wants pause for review
- Pause Council, save state, resume Phase 22 later

**EC-D2**: Operator wants direct intervention
- Add own opinion as 13th "verdict" → Council considers w Phase 22

**EC-D3**: Operator skeptical of verdicts
- Operator wants regenerate verdicts → cost-aware, max 1 regen

---

## 21.6. Acceptance + transition do fazy 22

```bash
$ aeis-cli phase21-acceptance-test --project proj_customer_y_crm

[1/6] All Council roles produced verdict               ✓ PASS (12/12)
[2/6] Verdicts in valid structured format              ✓ PASS
[3/6] Aggregation analysis done                        ✓ PASS
[4/6] Consensus levels calculated                      ✓ PASS
[5/6] Specialist overrides identified                  ✓ PASS (0)
[6/6] Audit chain entry initial_verdicts               ✓ PASS

DoD: 6/6 ✓
Phase 21 ACCEPTED. Ready dla Phase 22 (Deliberation Rounds).
```

---

# FAZA 22 — Deliberation Rounds

> **Spis sekcji**:
> - 22.1 — Sense fazy + iterative deliberation
> - 22.2 — Round structure (turn-taking, addressing disagreements)
> - 22.3 — Adversarial mechanics (Critic challenges, Specialist overrides)
> - 22.4 — Consensus measurement
> - 22.5 — Round budget + termination conditions
> - 22.6 — Operator mid-deliberation interventions
> - 22.7 — Edge cases (22) + transition do fazy 23

---

## 22.1. Sens fazy + iterative deliberation

### 22.1.1. Co fazy 22 robi

Po initial verdicts (faza 21), Council ma areas of disagreement.
Faza 22 to **iterative deliberation rounds** — Council debates aż do
consensus lub timeout.

```
┌──────────────────────────────────────────────────────────────┐
│  Deliberation Rounds — iterative consensus building          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z fazy 21):                                          │
│   • All 12 initial verdicts                                  │
│   • Aggregation analysis                                     │
│   • Areas of disagreement identified                         │
│                                                              │
│  PROCESSING (multi-round):                                   │
│   Round N:                                                    │
│    1. Chair presents disagreement areas                      │
│    2. Each role responds (z visibility do other verdicts)    │
│    3. Adversarial: Critic challenges, Specialists override   │
│    4. Consensus measurement                                  │
│    5. If consensus or budget exhausted → exit                │
│    6. Else → next round                                       │
│                                                              │
│  OUTPUT (round-by-round):                                    │
│   • Round 2 verdicts (updated, informed by round 1)          │
│   • Round 3 verdicts (jeśli needed)                          │
│   • Final round verdicts                                     │
│   • Consensus reached or operator decision                   │
│   • Audit chain entries per round                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 22.1.2. Wynik fazy 22 (DoD)

```
✓ Disagreement areas addressed
✓ Consensus achieved on most questions (>= 85% target)
✓ Specialist overrides invoked w cases of safety/compliance
✓ Operator decision dla unresolved disagreements (jeśli any)
✓ Round budget respected (max 5 rounds typical)
✓ Audit chain entries per round (signed)
✓ Project state: READY_FOR_CONSOLIDATION
```

---

## 22.2. Round structure

### 22.2.1. Per-round mechanics

```
Round N structure:
  
  1. CHAIR FRAMING (1 min)
     Chair presents:
      • Areas of disagreement from previous round
      • Specific questions to address
      • Deliberation goals dla this round
  
  2. PER-ROLE RESPONSE (parallel, 2-5 min each)
     Each role:
      • Sees other roles' verdicts from previous round
      • Considers others' reasoning
      • May change stance lub double down
      • Provides updated reasoning
      • May invoke specialist override (if applicable)
  
  3. CRITIC ROUND (1-2 min)
     Critic challenges:
      • Identifies weakest reasoning
      • Probes assumptions
      • Surfaces missed considerations
      • Optionally invokes veto (jeśli critical issue)
  
  4. SPECIALIST OVERRIDE PHASE (jeśli triggered)
     Domain specialists (Security, Compliance, Payment) may:
      • Veto unsafe approaches
      • Mandate specific compliance approaches
      • Block decisions w their domain
  
  5. CHAIR SYNTHESIS (1-2 min)
     Chair:
      • Summarizes round outcomes
      • Highlights remaining disagreements
      • Decides next round focus
  
  6. CONSENSUS MEASUREMENT
     System:
      • Calculates consensus per question
      • Decides: continue, exit z consensus, or operator
        decision
```

### 22.2.2. Per-round artifacts

```
~/.sylion/<op>/projects/customer_y_crm/council/round_2_deliberation/
├── chair_framing.json
├── verdicts/
│   ├── v_chair_round2.json
│   ├── v_planner_round2.json
│   ├── ... (12 verdicts)
├── critic_challenges.json
├── specialist_overrides/
│   └── (any overrides invoked)
├── chair_synthesis.json
├── consensus_analysis.json
└── round_outcome.json
```

---

## 22.3. Adversarial mechanics

### 22.3.1. Critic challenges

Critic ma special role — challenge plans aggressively:

```
Example Critic challenge — Round 2:

  Topic: Q15 (MVP scope)
  Background: Round 1 split — Planner suggested aggressive 28
              features w 8 weeks, others worried.
  
  Critic challenge:
   "Planner's MVP plan assumes:
    1. No KSeF API issues (R1 risk says otherwise)
    2. Customer Y customer data clean (no migration challenges)
    3. Stripe integration trivial (it's not, dla Polish customers)
    4. 100% operator availability (Production preset implies
       interrupted work)
    
    Even on best case, this is 10-12 week scope, not 8.
    
    Recommendation: aggressive scope cut to 18 features
    (P0 only) lub deadline extension.
    
    Status: NOT vetoing, but strongly disagree."

Cost dla Critic challenge: ~$0.50 (claude-opus deep analysis)
```

### 22.3.2. Specialist overrides

Specialist override = domain expert may block decisions w their domain:

```
Example Specialist override — Round 3:

  Topic: Q5 (GDPR data flow)
  Background: Most roles converged on plan that includes
              SendGrid (US-based) dla email.
  
  Compliance (GDPR) override:
   "I'm invoking specialist override on Q5.
    
    Reasoning:
    1. Customer Y is gov-funded entity → Polish data sovereignty
       implications strong
    2. SendGrid US-based — adequacy decision OK ale operator's
       customer policy mandates EU-only providers
    3. Polish UODO recently fined operator dla US-based mailing
       (precedent)
    
    Mandate: switch to Mailjet (EU-based, similar features)
    OR Polish Mailchimp competitor.
    
    This override blocks finalization until addressed.
    Estimated cost impact: +$15 dla Mailjet vs SendGrid
    (acceptable trade-off dla compliance)."

System effects:
  ✓ Override logged w audit chain
  ✓ Other roles cannot vote-down override
  ✓ Operator can override the override (z risk acknowledgment)
  ✓ Decision: Mailjet substitution
```

### 22.3.3. Override conflict resolution

Co jeśli dwa specialists invoke conflicting overrides?

```
Example conflict:

  Compliance (GDPR): mandates EU-only providers
  Payment Specialist: mandates Stripe (best Polish payment, US-based)
  
  Conflict: GDPR → no US, Payment → US-based Stripe
  
  Resolution algorithm:
   1. Check if GDPR adequacy applies do specific case
      (Stripe ma adequacy decision dla payments)
   2. If yes → both can be satisfied
   3. If no → escalate do operator
   
  Resolution dla this case:
   ✓ Stripe ma EU adequacy + DPA template
   ✓ Compliance accepts Stripe specifically (banking carve-out)
   ✗ Compliance still rejects SendGrid (no banking equivalent)
  
  Result: Stripe accepted, SendGrid replaced z Mailjet
```

---

## 22.4. Consensus measurement

### 22.4.1. Consensus algorithm

```python
def measure_consensus(round_verdicts):
    consensus_per_question = {}
    
    for question in question_set:
        stances = [v.per_question_verdicts[question.id]
                   for v in round_verdicts]
        
        # Calculate weighted consensus
        weighted_stances = weight_by_voting_power(stances)
        majority_stance = get_majority(weighted_stances)
        
        consensus_pct = sum(
            v.voting_weight for v in round_verdicts
            if matches_stance(v, majority_stance)
        ) / sum(v.voting_weight for v in round_verdicts)
        
        consensus_per_question[question.id] = {
            "level": consensus_pct,
            "majority_stance": majority_stance,
            "minority_count": count_minority(stances),
            "specialist_overrides_active": has_active_overrides(stances)
        }
    
    overall_consensus = mean(c.level for c in consensus_per_question.values())
    
    return {
        "per_question": consensus_per_question,
        "overall_consensus": overall_consensus,
        "ready_dla_consolidation": overall_consensus >= 0.85
    }
```

### 22.4.2. Consensus visualization across rounds

```
┌──────────────────────────────────────────────────────────────┐
│  Consensus Evolution Across Rounds                           │
│  Customer Y CRM                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Question              Round 1    Round 2    Round 3    Δ   │
│  ──────────────────  ────────  ────────  ────────  ──── │
│  Q1 architecture        92%       95%        —        ✓ +3   │
│  Q2 database           100%      100%        —        =      │
│  Q3 frontend           100%      100%        —        =      │
│  Q4 KSeF timing         58%       82%       92%       ✓ +34  │
│  Q5 GDPR flow           75%       70%       95%       ✓ +20  │
│  Q6 PCI scope           75%       88%        —        ✓ +13  │
│  Q7 Stripe integration  42%       58%       85%       ✓ +43  │
│  Q8 refunds             75%       92%        —        ✓ +17  │
│  Q9 subscriptions      100%      100%        —        =      │
│  Q10 translation        75%       88%        —        ✓ +13  │
│  Q11 currency           92%       95%        —        ✓ +3   │
│  Q12 rate limits        67%       82%       95%       ✓ +28  │
│  Q13 legacy ERP        100%      100%        —        =      │
│  Q14 WCAG               75%       72%       70%       ⚠ -5   │
│  Q15 MVP scope          42%       62%       82%       ✓ +40  │
│  Q16 phasing            67%       82%        —        ✓ +15  │
│  Q17 training/handoff  100%      100%        —        =      │
│  Q18 risk mitigations   75%       95%        —        ✓ +20  │
│  Q19 Bielik usage       58%       72%       85%       ✓ +27  │
│  Q20 CSV migration      75%       92%        —        ✓ +17  │
│                                                              │
│  Overall:                                                    │
│   Round 1: 76% average                                       │
│   Round 2: 88% average ✓ approaching 85% threshold            │
│   Round 3: 91% average ✓ EXCEEDED threshold (5 questions)    │
│                                                              │
│  Status:                                                     │
│   ✓ 18 questions z >=85% consensus                           │
│   ⚠ 1 question (Q14 WCAG) declining — operator decision      │
│   ✓ Specialist overrides resolved (3 invoked, all addressed) │
│                                                              │
│  Ready dla consolidation: YES (with operator decision na Q14)│
│                                                              │
│  [Operator decides Q14]  [Continue to consolidation]         │
└──────────────────────────────────────────────────────────────┘
```

---

## 22.5. Round budget + termination

### 22.5.1. Termination conditions

```
Round terminates when ANY of:

  1. CONSENSUS REACHED
     Overall >= 85% consensus
     0 active specialist overrides
     Exit cleanly to consolidation

  2. ROUND BUDGET EXHAUSTED
     Max rounds reached (default 5)
     Remaining disagreements → operator decision
     
  3. COST BUDGET EXHAUSTED
     Cost Guard triggers stop
     Pause for operator decision

  4. STUCK (no progress)
     Round N consensus same as Round N-1
     Diminishing returns detected
     Force operator decision

  5. OPERATOR INTERVENTION
     Operator pauses lub finalizes early

  6. SPECIALIST DEADLOCK
     Two specialists w opposing overrides
     Operator must resolve
```

### 22.5.2. Round budget per autonomy

```
Round budget per autonomy preset:

  Conservative:    max 5 rounds, $25 budget
  Balanced:        max 4 rounds, $15 budget
  Aggressive:      max 3 rounds, $10 budget
  Production:      max 5 rounds, $25 budget (D4+ projects)
  Research:        max 2 rounds, $5 budget (research velocity)

Estimated dla typical D4 project:
  Round 1: $5.20 (initial verdicts)
  Round 2: $4.80 (most disagreements addressed)
  Round 3: $3.40 (residual issues)
  Round 4: $2.80 (mostly polishing)
  Total: ~$16
```

### 22.5.3. Diminishing returns detection

System wykrywa kiedy more rounds nie pomagają:

```
Diminishing returns detection:

  Round 4 analysis:
   Round 3 consensus: 88%
   Round 4 consensus: 89%
   Improvement: +1% (below threshold of +5%)
   
  Cost spent: $11
  Estimated cost dla round 5: $3
  Estimated improvement: +0.5%
  
  Recommendation: STOP, operator decides remaining issues
  
  Akcje:
   [● Stop deliberation, operator decides Q14]
   [○ One more round (cost $3 dla potentially no improvement)]
```

---

## 22.6. Operator mid-deliberation interventions

### 22.6.1. Operator może (per autonomy DIM-9):

```
Conservative preset:
  ✓ Pause/resume deliberation
  ✓ Cancel current round
  ✓ Modify Council composition (next round, not current)
  ✓ Skip phase
  ✓ Edit Council briefing materials
  ✓ Switch models mid-deliberation (next call)
  ✓ Add own verdict as 13th opinion
  ✓ Force consensus decision

Production preset:
  ✓ Emergency pause
  ✓ Emergency cancel
  ✓ DR procedure trigger
  ✗ Most other interventions (w deliberation)
```

### 22.6.2. Mid-deliberation operator interface

```
┌──────────────────────────────────────────────────────────────┐
│  Council Deliberation — Round 2 in progress                  │
│                                                              │
│  Status: Round 2, 60% complete                                │
│  Spent: $4.80 / $15 budget                                   │
│  Estimated finish: 2 min                                     │
│                                                              │
│  Live operator controls:                                     │
│   [⏸ Pause]     [✗ Cancel round]     [⏭ Force exit]        │
│                                                              │
│  Operator notes:                                             │
│   ☐ "Council seems to be over-thinking Q15 (MVP scope)"      │
│   ☐ "Add own opinion: prefer ambitious scope, accept risk"  │
│                                                              │
│  Quick actions:                                              │
│   [Add operator verdict]                                      │
│   [Switch a role's model (next round)]                       │
│   [Inject focus topic]                                        │
│                                                              │
│  Live verdict updates:                                       │
│   ✓ Council Chair (round 2 verdict received)                 │
│   ✓ Planner (round 2 verdict received)                       │
│   ⠋ Critic (still generating...)                             │
│   ✓ ... 9 more received                                      │
│                                                              │
│  [Live cost overlay]  [View round 1 verdicts]                │
└──────────────────────────────────────────────────────────────┘
```

---

## 22.7. Edge Cases — Deliberation Rounds (22)

### Kategoria A — Round mechanics (5)

**EC-A1**: Round runs forever (Council can't agree)
- Trigger consensus stuck < 80% across rounds
- Akcje: operator decision, force exit, escalation

**EC-A2**: Critic over-aggressive
- Critic vetoes everything, blocks progress
- Akcje: temporarily reduce Critic veto power, operator review

**EC-A3**: Specialist deadlock
- Two specialists block each other
- Akcje: escalate do operator, mediation

**EC-A4**: Round consensus measurement disagrees
- Algorithm says 86%, operator sees 75% intuitively
- Akcje: detailed breakdown, operator override

**EC-A5**: Round produces no useful new info
- Verdicts identical do previous round
- Akcje: skip round, operator decides

### Kategoria B — Cost issues (4)

**EC-B1**: Round cost spike
- Round 3 cost 3x estimate
- Akcje: investigate, switch models, operator approves

**EC-B2**: Cost budget exhausted mid-round
- Cost Guard triggers stop
- Akcje: pause, operator approves continue, finalize z partial data

**EC-B3**: Per-role cost imbalance
- Critic spends $4, others $0.50 each
- Akcje: limit Critic verbosity, switch model

**EC-B4**: Total deliberation cost > 25% project budget
- Eating into build budget
- Akcje: force termination, operator decides

### Kategoria C — Operator interaction (5)

**EC-C1**: Operator absent for hard gate timeout
- Production preset = ∞, deliberation pauses
- Akcje: wait, escalation channels, fallback contact

**EC-C2**: Operator wants pause for thought
- Pause mid-round, save state
- Akcje: state preservation, resume mechanic

**EC-C3**: Operator changes mind on Council
- Mid-deliberation, wants different role models
- Akcje: queue change for next round, full restart

**EC-C4**: Operator wants veto override
- Specialist veto invoked, operator wants ignore
- Akcje: explicit override z reason, audit log, accept risk

**EC-C5**: Operator's own verdict conflicts z Council
- Operator added 13th verdict, disagrees z 11/12
- Akcje: operator decides, audit log, override warning

### Kategoria D — Quality issues (4)

**EC-D1**: Roles parrot each other
- Group-think detected after seeing other verdicts
- Akcje: independence reminder, force diverse views

**EC-D2**: Hallucinated regulations
- Compliance role cites fabricated law
- Akcje: KB verification, regenerate verdict, fix KB

**EC-D3**: Verdicts shallow w late rounds
- Roles tired, low-effort responses
- Akcje: re-prompt, switch model, accept current state

**EC-D4**: Hidden disagreement
- Algorithm shows consensus but actual answers differ
- Akcje: deep semantic check, operator review

### Kategoria E — Recovery (4)

**EC-E1**: Provider outage mid-round
- Critical role's model down
- Akcje: fallback model, skip role temporarily, pause

**EC-E2**: Audit chain corruption
- Round verdicts not properly signed
- Akcje: forensic, regenerate signed, fail-fast

**EC-E3**: Round restart needed (data corruption)
- Verdicts lost
- Akcje: restart from previous round, reuse cache where possible

**EC-E4**: Mid-round AEIS update
- AEIS auto-updates affected behavior
- Akcje: defer update, complete deliberation, restart

---

## 22.8. Acceptance + transition do fazy 23

```bash
$ aeis-cli phase22-acceptance-test --project proj_customer_y_crm

[1/8] Disagreement areas addressed                     ✓ PASS
[2/8] Consensus achieved (>=85% on most questions)     ✓ PASS (18/20)
[3/8] Specialist overrides invoked + resolved          ✓ PASS (3/3)
[4/8] Operator decisions on unresolved (Q14)           ✓ PASS
[5/8] Round budget respected                           ✓ PASS (3 rounds)
[6/8] Cost within budget                               ✓ PASS ($16/$15 borderline)
[7/8] Audit chain entries per round                    ✓ PASS
[8/8] Project state: READY_FOR_CONSOLIDATION           ✓ PASS

DoD: 8/8 ✓
Phase 22 ACCEPTED. Ready dla Phase 23 (Consolidation).
```

---

# FAZA 23 — Consolidation

> **Spis sekcji**:
> - 23.1 — Sense fazy + ze deliberation do single source
> - 23.2 — Conflict resolution dla outstanding disagreements
> - 23.3 — Operator hard-gate na finalization (D4+ projects)
> - 23.4 — Pre-consolidation review
> - 23.5 — Edge cases (15) + transition do fazy 24

---

## 23.1. Sens fazy

### 23.1.1. Co Faza 23 robi

Po deliberation rounds (faza 22), Council ma consensus w większości
spraw. Faza 23 to **finalization** — operator + Council finalize
remaining decisions, lock in verdicts, signal end of deliberation.

```
┌──────────────────────────────────────────────────────────────┐
│  Consolidation — finalize Council decisions                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT (z fazy 22):                                          │
│   • Final round verdicts                                     │
│   • Consensus metrics                                        │
│   • Outstanding disagreements (jeśli any)                    │
│   • Specialist overrides applied                             │
│                                                              │
│  PROCESSING (operator + Council Chair):                      │
│   • Resolve outstanding disagreements                        │
│   • Operator hard-gate review (D4+ projects)                 │
│   • Lock in finalizations                                    │
│   • Generate "Council Decision Summary"                      │
│                                                              │
│  OUTPUT:                                                     │
│   • Decision summary document (one per question)             │
│   • Operator's signoff                                       │
│   • Audit chain entry: council_finalized (signed)            │
│   • Project state: READY_FOR_BOOK_GENERATION                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 23.1.2. Wynik fazy 23 (DoD)

```
✓ All Council decisions finalized
✓ Outstanding disagreements resolved
✓ Operator hard-gate approved (D4+ projects)
✓ Decision summary generated
✓ Audit chain entry: council_finalized
✓ Project state: READY_FOR_BOOK_GENERATION
```

---

## 23.2. Conflict resolution

### 23.2.1. Outstanding disagreements

Po fazie 22, mogą zostać:
- Questions z weak consensus (<85%)
- Specialist overrides not yet operator-approved
- Operator-disputed Council recommendations

Faza 23 finalizuje these.

### 23.2.2. Conflict resolution UI

```
┌──────────────────────────────────────────────────────────────┐
│  Outstanding Disagreements — Customer Y CRM                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Question Q14 — Polish accessibility WCAG                    │
│   Status: Weak consensus (70%) declining across rounds       │
│                                                              │
│  Council positions:                                          │
│  • Compliance (GDPR): full WCAG 2.1 AA mandatory             │
│  • UX Designer: full AA recommended                          │
│  • Planner: WCAG 2.1 A baseline + AA dla critical paths      │
│  • Critic: AA mandatory dla gov-funded customer              │
│  • Cost Specialist (Cost Guard): AA adds $40, A is $15       │
│  • i18n Specialist: AA includes RTL/screen-reader Polish      │
│  • Other 6: defer                                             │
│                                                              │
│  Trade-offs:                                                 │
│   Option A: Full WCAG 2.1 AA                                 │
│    • Cost: +$40                                               │
│    • Time: +1.5 weeks                                         │
│    • Compliance: gov-funded customer expects                  │
│    • Quality: best                                            │
│                                                              │
│   Option B: WCAG 2.1 A baseline + AA critical                │
│    • Cost: +$25                                               │
│    • Time: +1 week                                            │
│    • Compliance: meets minimum, may be insufficient           │
│    • Quality: good                                            │
│                                                              │
│   Option C: WCAG 2.1 A only                                  │
│    • Cost: +$15                                               │
│    • Time: +0.5 weeks                                         │
│    • Compliance: ⚠ may not meet customer expectations         │
│    • Quality: acceptable                                      │
│                                                              │
│  Operator decision needed:                                   │
│   [● Option A — Full AA (recommended dla gov-funded)]         │
│   [○ Option B — A baseline + AA critical]                    │
│   [○ Option C — A only]                                      │
│   [○ Defer to customer (they pay)]                           │
│   [○ Custom decision]                                         │
│                                                              │
│  Operator reasoning (logged):                                │
│   [_____________________________________________________]    │
│                                                              │
│  [Confirm decision]                                          │
└──────────────────────────────────────────────────────────────┘
```

### 23.2.3. Operator decision propagates

```
After operator decides Q14 (Option A):
  ✓ Council Chair adds operator's decision do verdicts
  ✓ All affected questions updated (cost, timeline, scope)
  ✓ Audit chain entry: operator_decision_q14
  ✓ Risk register updated (R4 customer availability)
  ✓ Cost estimate recalculated (+$40)
  ✓ Timeline adjusted (+1.5 weeks dla AA implementation)
```

---

## 23.3. Operator hard-gate

### 23.3.1. Hard-gate na finalization (D4+)

Per autonomy preset Production, finalization wymaga hard-gate dla D4+
projects:

```
┌──────────────────────────────────────────────────────────────┐
│  🚨  Hard Gate — Council Finalization                        │
│                                                              │
│  Project: Customer Y CRM (D4)                                │
│  Status: Council deliberation complete                       │
│                                                              │
│  Summary of decisions:                                       │
│   • 20 questions deliberated                                 │
│   • 19 reached consensus (>=85%)                             │
│   • 1 (Q14 WCAG) operator-decided                            │
│   • 3 specialist overrides applied                           │
│   • 0 unresolved                                             │
│                                                              │
│  Key decisions to confirm:                                   │
│   ✓ Architecture: monolithic, PostgreSQL, React+TS           │
│   ✓ KSeF: early integration (week 1-2)                       │
│   ✓ GDPR: EU-only providers (SendGrid → Mailjet)             │
│   ✓ Stripe: standard integration                              │
│   ✓ MVP scope: 18 features (down from 28)                    │
│   ✓ Phasing: P0 features first, P1 after                     │
│   ✓ Bielik dla PL content (consensus reached)                │
│   ✓ WCAG 2.1 AA full (operator decision)                     │
│   ✓ Risk mitigation plans approved                            │
│                                                              │
│  Estimated impact:                                           │
│   Cost: $345 (down from initial $388 estimate)               │
│   Timeline: 8.5 weeks (slightly over deadline 8 weeks)       │
│   Risk profile: medium                                       │
│                                                              │
│  Customer Y notification:                                    │
│   Will be notified post-finalization (z book ready)          │
│                                                              │
│  Operator approval required:                                 │
│   [● Approve finalization]                                    │
│   [○ Request additional Council round]                        │
│   [○ Reject (operator decides solution)]                      │
│   [○ Pause project (defer decision)]                          │
│                                                              │
│  ⚠ This action locks Council decisions.                      │
│     Future changes will require explicit re-deliberation.    │
│                                                              │
│  [Confirm approval]                                          │
└──────────────────────────────────────────────────────────────┘
```

### 23.3.2. Operator's optional notes

```
Approval may include operator notes:

  "Approved with reservations:
   - Timeline 8.5 weeks slightly over customer's 8-week deadline.
     Will discuss z customer for 0.5 week extension or scope cut.
   - WCAG AA decision driven by customer being gov-funded.
     If customer flexes on this, may revisit.
   - KSeF early integration adds risk if API issues found late.
     Will monitor closely.
   
   Otherwise, plan looks solid."

These notes:
  ✓ Logged w audit chain
  ✓ Visible w Council Book
  ✓ Inform downstream phases (planning, build)
  ✓ Surface again at relevant decision points
```

---

## 23.4. Pre-consolidation review

### 23.4.1. Decision quality check

```
┌──────────────────────────────────────────────────────────────┐
│  Pre-Finalization Decision Quality Review                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Decision quality metrics:                                    │
│                                                              │
│  Consensus distribution:                                      │
│   100% consensus:    5 questions  ✓                          │
│   >=85% consensus:   13 questions ✓                          │
│   85-95% range:      —                                       │
│   Operator decisions: 1 question                              │
│   Total: 19 + 1 = 20 ✓                                       │
│                                                              │
│  Specialist participation:                                    │
│   • Compliance (GDPR): 2 overrides invoked, 2 accepted       │
│   • Compliance (KSeF): 1 override invoked, 1 accepted        │
│   • Compliance (PCI): 0 overrides                            │
│   • Security: 0 overrides                                    │
│   • Payment: 0 overrides                                     │
│                                                              │
│  Critic engagement:                                          │
│   Round 1: 8 challenges raised                               │
│   Round 2: 4 follow-ups                                      │
│   Round 3: 2 deep-dives                                      │
│   No vetoes invoked (good — no critical issues)              │
│                                                              │
│  Coherence check:                                            │
│   ✓ Decisions internally consistent                          │
│   ✓ Cost estimates align (was $388, now $345)                │
│   ✓ Timeline align (was 8 weeks, now 8.5 weeks)              │
│   ✓ All goals (z faza 17) covered by decisions                │
│   ✓ All scope items (z faza 18) addressed                     │
│   ✓ Risk register updated                                    │
│                                                              │
│  Compliance verification:                                    │
│   ✓ GDPR: data flow design accepted                          │
│   ✓ KSeF: integration plan accepted                          │
│   ✓ PCI: minimization approach accepted                      │
│   ✓ Polish accessibility: AA confirmed (operator)            │
│                                                              │
│  Audit trail:                                                │
│   ✓ All round verdicts signed                                │
│   ✓ All operator decisions signed                             │
│   ✓ Specialist overrides logged                               │
│   ✓ Cost tracking complete                                   │
│                                                              │
│  Status: Ready dla finalization                              │
│                                                              │
│  [Proceed do finalization]  [Request more deliberation]      │
└──────────────────────────────────────────────────────────────┘
```

---

## 23.5. Edge Cases — Consolidation (15)

### Kategoria A — Conflict resolution issues (4)

**EC-A1**: Operator decision changes everything
- Operator picks contrarian option, requires re-evaluation
- Akcje: cascade implications, may require new Council round

**EC-A2**: Operator unable to decide
- Genuine equipoise, can't choose
- Akcje: customer consultation, defer, escalate

**EC-A3**: Operator's decision violates compliance
- Operator picks unsafe option, Compliance role re-flags
- Akcje: hard-block w operator override, customer disclosure

**EC-A4**: Late-discovered conflict
- New conflict noticed during finalization review
- Akcje: regression to fazy 22, focused mini-round

### Kategoria B — Operator approval issues (4)

**EC-B1**: Hard gate timeout
- Operator absent, gate doesn't auto-resolve
- Akcje: notification escalation, defer, fallback

**EC-B2**: Operator approves but later regrets
- Already finalized, customer notified
- Akcje: reverse via faza 22 reconvening, audit reasoning

**EC-B3**: Operator notes contradict Council decisions
- "Approved" + reservations that conflict
- Akcje: clarify intent, may be operator-conditional

**EC-B4**: Mobile approval z biometric fail
- Operator on mobile, biometric fails repeatedly
- Akcje: switch to desktop, master password fallback

### Kategoria C — Quality issues (4)

**EC-C1**: Decision summary inaccurate
- Auto-summary misses important details
- Akcje: operator review, manual edit, regenerate

**EC-C2**: Coherence check fails
- Decisions internally contradict
- Akcje: detailed analysis, focused re-deliberation

**EC-C3**: Cost reconciliation discrepancy
- Decisions cost differs significantly z initial estimate
- Akcje: detailed breakdown, customer notification jeśli needed

**EC-C4**: Timeline reconciliation problem
- Decisions push beyond customer deadline
- Akcje: scope cut option, deadline extension request

### Kategoria D — Recovery (3)

**EC-D1**: Mid-finalization crash
- AEIS crashes, partial state
- Akcje: restore from checkpoint, verify integrity

**EC-D2**: Audit chain integrity issue
- Some signatures don't verify
- Akcje: forensic, may require deliberation re-do

**EC-D3**: Customer changes mind during finalization
- Customer revises requirements
- Akcje: pause, scope renegotiation, may require Phase 17 re-do

---

## 23.6. Acceptance + transition do fazy 24

```bash
$ aeis-cli phase23-acceptance-test --project proj_customer_y_crm

[1/6] All decisions finalized                          ✓ PASS
[2/6] Outstanding disagreements resolved               ✓ PASS
[3/6] Operator hard-gate approved (D4)                 ✓ PASS
[4/6] Decision summary generated                       ✓ PASS
[5/6] Coherence check passed                           ✓ PASS
[6/6] Audit chain entry council_finalized              ✓ PASS

DoD: 6/6 ✓
Phase 23 ACCEPTED. Ready dla Phase 24 (Council Book).
```

---

# FAZA 24 — Council Book Generation

> **Spis sekcji**:
> - 24.1 — Sense fazy + Council Book jako artifact
> - 24.2 — Book structure
> - 24.3 — Generation workflow
> - 24.4 — Operator review + signoff
> - 24.5 — Edge cases (15) + transition do fazy 25

---

## 24.1. Sens fazy

### 24.1.1. Council Book = formal record

```
┌──────────────────────────────────────────────────────────────┐
│  Council Book — formal record of deliberation                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Council Book contains:                                      │
│   • Project context (z fazy 16-19)                            │
│   • All Council deliberation records                          │
│   • All decisions z reasoning                                 │
│   • Risk register z mitigations                               │
│   • Specialist overrides documented                           │
│   • Operator interventions logged                             │
│   • Final decision summary                                    │
│                                                              │
│  Purpose:                                                    │
│   • Source dla Księga generation (faza 25)                    │
│   • Customer-facing decision documentation                    │
│   • Audit trail dla compliance                                │
│   • Reference dla future similar projects                     │
│   • Legal record dla customer relationship                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 24.1.2. Wynik fazy 24 (DoD)

```
✓ Council Book generated (markdown + PDF)
✓ All sections complete
✓ Operator reviewed + signed off
✓ Customer-facing version ready (jeśli applicable)
✓ Audit chain entry: council_book_generated
✓ Project state: READY_FOR_KSIEGA_GENERATION
```

---

## 24.2. Council Book structure

### 24.2.1. Standard sections

```
COUNCIL BOOK — Customer Y CRM

1. EXECUTIVE SUMMARY
   • Project overview
   • Key decisions made
   • Estimated cost + timeline
   • Customer key takeaways
   1-2 pages

2. PROJECT CONTEXT
   2.1 Operator's idea
   2.2 Goals (z faza 17)
   2.3 Scope (z faza 18)
   2.4 Constraints + risks
   2.5 Stakeholders
   ~3-5 pages

3. COUNCIL CONFIGURATION
   3.1 Roles + models
   3.2 Knowledge bases used
   3.3 Voting rules
   ~1-2 pages

4. DELIBERATION RECORD
   4.1 Initial verdicts (round 1) summary
   4.2 Round-by-round consensus evolution
   4.3 Critical challenges raised
   4.4 Specialist overrides invoked
   4.5 Operator decisions
   ~5-10 pages

5. KEY DECISIONS Z REASONING
   For each major decision (typically 15-20):
   • Decision title
   • Final stance
   • Supporting reasoning
   • Dissenting opinions
   • Alternatives considered
   • Implementation approach
   ~10-20 pages

6. RISKS + MITIGATIONS
   • Updated risk register
   • Mitigation plans approved
   • Monitoring plan
   ~2-3 pages

7. COMPLIANCE
   • GDPR design summary
   • KSeF integration plan
   • PCI scope minimization
   • Polish accessibility approach
   ~3-5 pages

8. APPENDICES
   8.1 Detailed verdicts (per round)
   8.2 Audit chain references
   8.3 Cost breakdown
   8.4 Timeline projection
   8.5 Operator's notes throughout

Total: 30-50 pages typical
```

### 24.2.2. Customer-facing version

```
COUNCIL BOOK — Customer-Facing Edition

Differences z full version:
  • Internal AEIS terminology removed (no "Council role X")
  • Reasoning simplified
  • Audit IDs hidden
  • Cost details aggregated (no per-call $)
  • Operator notes filtered (only relevant)
  • Visual elements (charts, diagrams) added
  • Polish version generated (jeśli customer requests)

Length: ~10-20 pages (vs 30-50 internal)
Format: PDF, signed
```

---

## 24.3. Generation workflow

### 24.3.1. LLM-driven generation

```
Generation steps:

  1. STRUCTURE PHASE
     System creates outline z standard structure
     Operator approves outline
     Cost: ~$0.50

  2. SECTION GENERATION (parallel where possible)
     Each section generated by appropriate model:
     - Executive summary: Council Chair's perspective ($0.80)
     - Decision narratives: collaborative across roles ($2.40)
     - Compliance section: respective specialists ($1.20)
     - Risk section: Risk Assessor ($0.40)
     Total: ~$8

  3. INTEGRATION PHASE
     System combines sections into coherent document
     Coherence Guard validates internal consistency
     Cost: ~$0.50

  4. POLISH PHASE
     Editorial pass dla readability
     Format consistency
     Reference resolution
     Cost: ~$1.20

Total generation cost: ~$10
Total generation time: ~5-10 min
```

### 24.3.2. Customer-facing transformation

```
After full version ready:
  ↓
Customer-facing transformation:
  • Filter sections (operator selects)
  • Simplify language (LLM rewrite)
  • Remove internal terminology
  • Generate Polish translation (jeśli requested)
  • Add visual elements
  Cost: ~$3-5
```

---

## 24.4. Operator review + signoff

### 24.4.1. Review interface

```
┌──────────────────────────────────────────────────────────────┐
│  Council Book Review                                         │
│  Customer Y CRM                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Generated Council Book:                                      │
│   File: ~/.sylion/.../council/council_book.md                 │
│   Length: 38 pages                                           │
│   Word count: ~12,500                                        │
│                                                              │
│  Sections:                                                   │
│   ✓ Executive Summary (1.2 pages)                            │
│   ✓ Project Context (4 pages)                                │
│   ✓ Council Configuration (1.5 pages)                        │
│   ✓ Deliberation Record (8 pages)                            │
│   ✓ Key Decisions z Reasoning (15 pages)                     │
│   ✓ Risks + Mitigations (2.5 pages)                          │
│   ✓ Compliance (4 pages)                                     │
│   ✓ Appendices (2 pages)                                     │
│                                                              │
│  Quality checks:                                             │
│   ✓ Coherence Guard: no inconsistencies found                │
│   ✓ All Council decisions captured                           │
│   ✓ All operator decisions reflected                         │
│   ✓ Risk register up-to-date                                 │
│   ✓ Audit chain references valid                             │
│                                                              │
│  Operator review:                                            │
│   [● Read full Book (open in editor)]                        │
│   [○ Read Executive Summary only]                            │
│   [○ Review specific section]                                │
│   [○ Skip to signoff]                                        │
│                                                              │
│  Operator notes:                                             │
│   [_____________________________________________________]    │
│                                                              │
│  Customer-facing version:                                    │
│   ☑ Generate customer-facing version                         │
│   ☑ Translate to Polish                                       │
│   ☐ Send to customer immediately (manual after Księga)       │
│                                                              │
│  [Sign off Book]  [Request edits]  [Cancel]                  │
└──────────────────────────────────────────────────────────────┘
```

### 24.4.2. Operator signoff implications

Po signoff:
- Council Book staje się **immutable** (any changes require re-deliberation)
- Cryptographic signature applied (operator's Ed25519)
- Audit chain entry: council_book_signed
- Customer-facing version generated
- Council Book staje się base dla Księga (faza 25)

---

## 24.5. Edge Cases — Council Book (15)

### Kategoria A — Generation issues (4)

**EC-A1**: Generation fails mid-section
- Network issue, model timeout
- Akcje: retry, smaller model, partial generation

**EC-A2**: Generated content shallow
- LLM produces low-quality output
- Akcje: better prompts, premium model, manual augmentation

**EC-A3**: Generation cost overrun
- $25 instead of $10
- Akcje: investigate, cap further generation, accept

**EC-A4**: Generation hallucinations
- Book mentions decisions Council didn't make
- Akcje: cross-check z audit chain, regenerate, manual fix

### Kategoria B — Quality issues (4)

**EC-B1**: Internal contradictions w Book
- Coherence Guard catches contradictions
- Akcje: focused re-generation of conflicting sections

**EC-B2**: Missing key decisions
- Book skips important decisions
- Akcje: review checklist, augment manually, regenerate

**EC-B3**: Polish translation issues
- Auto-translation incorrect
- Akcje: bielik refinement, native speaker review (operator)

**EC-B4**: Format issues
- Markdown rendering broken
- Akcje: reformat, manual cleanup, alternative format

### Kategoria C — Operator review (4)

**EC-C1**: Operator wants major edits
- Many sections wrong
- Akcje: regenerate affected sections, may need re-deliberation

**EC-C2**: Operator nie ma time dla full review
- Book 38 pages, operator busy
- Akcje: executive summary only, defer detailed review

**EC-C3**: Customer wants Book early
- Customer pressuring for Book before signoff
- Akcje: defer, send draft z disclaimer, escalate

**EC-C4**: Operator finds error post-signoff
- Already locked Book
- Akcje: addendum mechanism, audit log correction

### Kategoria D — Recovery (3)

**EC-D1**: Book file corruption
- Generated Book corrupted
- Akcje: restore z backup, regenerate

**EC-D2**: Audit chain doesn't match Book
- Decisions w Book don't match chain
- Akcje: forensic, regenerate, may indicate tampering

**EC-D3**: Customer-facing version leaks internal info
- Filter failed, internal terminology exposed
- Akcje: regenerate customer version, additional filter

---

## 24.6. Acceptance + transition do fazy 25

```bash
$ aeis-cli phase24-acceptance-test --project proj_customer_y_crm

[1/6] Council Book generated                           ✓ PASS (38 pages)
[2/6] All sections complete                            ✓ PASS
[3/6] Operator reviewed + signed                       ✓ PASS
[4/6] Customer-facing version ready                    ✓ PASS
[5/6] Coherence Guard validation                       ✓ PASS
[6/6] Audit chain entry council_book_generated         ✓ PASS

DoD: 6/6 ✓
Phase 24 ACCEPTED. Ready dla Phase 25 (Księga Generation).
```

---

# FAZA 25 — Księga Finalization

> **Spis sekcji**:
> - 25.1 — Sense fazy + Księga jako project's bible
> - 25.2 — Księga structure (vs Council Book)
> - 25.3 — Generation z Council Book + augmentation
> - 25.4 — Operator review + lock
> - 25.5 — Edge cases (15) + transition do fazy 26

---

## 25.1. Sens fazy

### 25.1.1. Księga vs Council Book

```
┌──────────────────────────────────────────────────────────────┐
│  Księga vs Council Book                                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  COUNCIL BOOK (faza 24)                                      │
│   • Process documentation (HOW we decided)                   │
│   • Deliberation records                                     │
│   • Multiple perspectives preserved                           │
│   • Audit/compliance focus                                    │
│   • 30-50 pages typical                                      │
│                                                              │
│  KSIĘGA (faza 25)                                            │
│   • Project specification (WHAT we'll build)                 │
│   • Single coherent vision                                    │
│   • Implementation-oriented                                   │
│   • Build/deploy focus                                        │
│   • 60-100 pages typical                                     │
│                                                              │
│  Księga uses Council Book jako foundation, ALE adds:         │
│   • Detailed feature specifications                           │
│   • Technical architecture details                            │
│   • Data models                                               │
│   • API specifications                                        │
│   • Test strategies elaboration                               │
│   • Deployment plans                                          │
│   • Customer-facing language                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 25.1.2. Księga jako single source of truth

```
W AEIS lifecycle:
  
  Goals (faza 17)         → captured w Księga
  Scope (faza 18)         → captured w Księga
  Council decisions (24)  → resolved w Księga
  
  ↓ Księga staje się source dla:
  
  Masterplan (faza 28)     → derived z Księga
  Test plan (faza 29)      → derived z Księga
  Build (faza 35)          → guided by Księga
  Deployment (faza 39)     → planned per Księga
  Closure (faza 41)        → measured against Księga
  
  ALL downstream phases reference Księga jako truth.
```

### 25.1.3. Wynik fazy 25 (DoD)

```
✓ Księga generated (markdown + PDF + structured data)
✓ All sections elaborated z Council Book
✓ Coherence Guard validation passed
✓ Customer-facing version ready
✓ Operator reviewed + locked Księga
✓ Audit chain entry: ksiega_finalized (signed)
✓ Project state: READY_FOR_PLANNING (Phase 26)
```

---

## 25.2. Księga structure

### 25.2.1. Standard sections

```
KSIĘGA — Customer Y CRM

PART I — VISION
1. Executive overview
2. Goals statement
3. Stakeholders
4. Success metrics
5. Customer context
~5-8 pages

PART II — SCOPE + CONSTRAINTS
6. In-scope features (detailed)
7. Out-of-scope (justifications)
8. Technical constraints
9. Business constraints
10. Regulatory constraints
~10-15 pages

PART III — ARCHITECTURE
11. System architecture overview
12. Module decomposition
13. Data architecture
14. API architecture
15. Frontend architecture
16. Integration architecture (Stripe, KSeF, Mailjet)
17. Security architecture
18. Deployment architecture
~15-25 pages

PART IV — IMPLEMENTATION GUIDE
19. Module specifications (detailed per module)
20. Data models
21. API specifications
22. UI/UX specifications
23. Testing strategy
24. Performance targets
25. Internationalization specifications
~20-30 pages

PART V — OPERATIONAL
26. Deployment plan
27. Monitoring + alerting
28. Runbooks
29. Customer training/handoff
30. Maintenance plan
~5-10 pages

PART VI — COMPLIANCE
31. GDPR compliance plan
32. KSeF compliance plan
33. PCI scope + compliance
34. Accessibility (WCAG 2.1 AA)
35. Polish regulations specifics
~5-10 pages

PART VII — RISKS + MITIGATIONS
36. Risk register (updated)
37. Mitigation plans
38. Monitoring plan
~3-5 pages

PART VIII — TIMELINE + COSTS
39. Project timeline (week-by-week)
40. Cost breakdown
41. Resource allocation
42. Milestones
~3-5 pages

APPENDICES
A. Council Book reference
B. Detailed audit chain
C. Glossary
D. References
~5-10 pages

Total: 60-100 pages typical
```

---

## 25.3. Generation workflow

### 25.3.1. Z Council Book do Księga

```
Generation pipeline:

  1. INHERITANCE PHASE
     Inherit z Council Book:
      • All decisions (Part I-II)
      • Compliance approaches (Part VI)
      • Risk register (Part VII)
     Cost: ~$0.50 (parsing/restructuring)

  2. ARCHITECTURAL ELABORATION
     Architecture role + Planner generate:
      • System architecture
      • Module decomposition
      • Data architecture
      • API design
     Cost: ~$5-8 (deep technical)

  3. IMPLEMENTATION SPECIFICATION
     For each in-scope module:
      • Detailed specs
      • Data models
      • API specs
      • UI specs
     Cost: ~$10-15 (28 modules × ~$0.50)

  4. OPERATIONAL PLANNING
     Generate:
      • Deployment plan (z deploy template)
      • Monitoring plan
      • Runbooks
     Cost: ~$2

  5. COMPLIANCE ELABORATION
     Compliance specialists detail:
      • GDPR plan
      • KSeF plan
      • PCI plan
     Cost: ~$3

  6. TIMELINE + COSTS
     Synthesize:
      • Week-by-week timeline
      • Cost breakdown
      • Resource allocation
     Cost: ~$1

  7. INTEGRATION + POLISH
     Combine into single document
     Coherence Guard validates
     Cost: ~$2

Total generation cost: ~$25-35
Total time: ~15-25 min
```

### 25.3.2. Quality checks

```
Coherence Guard validates:
  ✓ Księga consistent z Council Book
  ✓ All goals (faza 17) covered
  ✓ All scope items (faza 18) addressed
  ✓ All risks (faza 18) mitigated
  ✓ All Council decisions (faza 23) implemented
  ✓ All operator notes (faza 23) reflected
  ✓ Internal consistency (no contradictions)
  ✓ Cost estimates align z budget
  ✓ Timeline align z deadline
```

---

## 25.4. Operator review + lock

### 25.4.1. Review interface

```
┌──────────────────────────────────────────────────────────────┐
│  Księga Review                                               │
│  Customer Y CRM                                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Generated Księga:                                           │
│   File: ~/.sylion/.../ksiega/ksiega_v1.md                     │
│   Length: 78 pages                                           │
│   Word count: ~28,500                                        │
│   Generation cost: $32.40                                    │
│                                                              │
│  Sections:                                                   │
│   ✓ Part I (Vision) — 6 pages                                │
│   ✓ Part II (Scope + Constraints) — 12 pages                 │
│   ✓ Part III (Architecture) — 18 pages                       │
│   ✓ Part IV (Implementation Guide) — 25 pages                │
│   ✓ Part V (Operational) — 7 pages                           │
│   ✓ Part VI (Compliance) — 5 pages                           │
│   ✓ Part VII (Risks) — 3 pages                               │
│   ✓ Part VIII (Timeline + Costs) — 4 pages                   │
│   ✓ Appendices — 6 pages                                     │
│                                                              │
│  Quality checks:                                             │
│   ✓ Coherence Guard: passed                                  │
│   ✓ All Council decisions implemented                        │
│   ✓ All goals covered                                        │
│   ✓ All scope items addressed                                │
│   ✓ Compliance plans complete                                │
│   ✓ Cost estimates: $345 (matches Council)                   │
│   ✓ Timeline: 8.5 weeks (matches Council)                    │
│                                                              │
│  Operator review options:                                    │
│   [● Read full Księga]                                        │
│   [○ Read by Part]                                            │
│   [○ Review architecture only]                                │
│   [○ Review compliance only]                                  │
│   [○ Skip do lock]                                            │
│                                                              │
│  ⚠ This Księga becomes IMMUTABLE after lock.                  │
│     Future changes require explicit "Księga revision"        │
│     phase, signed audit entry, and may require                │
│     re-deliberation.                                          │
│                                                              │
│  [Lock Księga]  [Request edits]  [Reject + redo Council]     │
└──────────────────────────────────────────────────────────────┘
```

### 25.4.2. Lock implications

```
After Księga locked:
  ✓ Cryptographic signature (operator's Ed25519)
  ✓ Hash recorded w audit chain
  ✓ Customer-facing version finalized
  ✓ Project state advances do PLANNING
  ✓ Group C complete

Future changes:
  • Minor (typos, clarifications): inline addendum
  • Material (architecture, scope): formal "Księga revision"
    process — re-Council deliberation required
  • Customer-driven changes: change request workflow
```

### 25.4.3. Customer notification

```
Po Księga locked:
  
  ☑ Generate customer notification:
     Subject: "Customer Y CRM — Project Plan Ready dla Review"
     Attachment: customer-facing Księga (PDF, Polish)
     Content:
       "Plan projektu został przygotowany. 
        Załączamy szczegółowy plan obejmujący:
         - Cele projektu
         - Zakres prac
         - Architektura systemu
         - Plan zgodności z RODO i KSeF
         - Harmonogram realizacji
         - Wycenę kosztów
        
        Prosimy o przegląd i potwierdzenie do dnia X."
  
  ☑ Customer review window: 5 business days
  ☑ Customer changes can trigger Księga revision
  ☑ Customer signoff required przed Phase 26 (Planning)
  
  [Send to customer]  [Defer (operator handles)]
```

---

## 25.5. Edge Cases — Księga (15)

### Kategoria A — Generation issues (4)

**EC-A1**: Generation timeout dla complex project
- 78-page generation takes >30 min
- Akcje: progressive generation, accept partial, batch sections

**EC-A2**: Cost overrun
- Generation $50 vs $30 estimate
- Akcje: investigate, cheaper model dla less critical sections

**EC-A3**: Architecture section incomplete
- Architecture role hits context limits
- Akcje: split into multiple sub-sections, smaller chunks

**EC-A4**: Cross-section contradictions
- Architecture vs Implementation specs differ
- Akcje: focused regeneration, manual reconciliation

### Kategoria B — Quality issues (4)

**EC-B1**: Operator finds errors w detailed specs
- Architecture section technically wrong
- Akcje: regenerate section z augmented context

**EC-B2**: Customer disagrees post-Księga
- Customer wants changes after seeing Księga
- Akcje: change request process, scope renegotiation

**EC-B3**: Compliance gaps discovered
- Compliance role missed something w Księga
- Akcje: addendum lub revision cycle

**EC-B4**: Polish translation quality issues
- Customer-facing Polish version awkward
- Akcje: bielik refinement, native speaker fallback

### Kategoria C — Lock workflow (4)

**EC-C1**: Operator delays lock indefinitely
- Want's "perfect" Księga, never satisfied
- Akcje: time-box review, customer pressure surface

**EC-C2**: Customer wants pre-lock review
- Wants to influence Księga before lock
- Akcje: pre-lock customer review process

**EC-C3**: Pre-lock scope creep
- Operator wants add features before lock
- Akcje: defer to revision, scope discipline

**EC-C4**: Lock during operator absence
- Auto-lock w timeout
- Akcje: defer, escalation, skip auto-lock

### Kategoria D — Recovery (3)

**EC-D1**: Księga file corruption
- Generated file damaged
- Akcje: regenerate, restore z backup

**EC-D2**: Audit chain mismatch z Księga
- Decisions w Księga don't match chain
- Akcje: forensic, regenerate, may indicate issue

**EC-D3**: Customer signoff withdrawn
- Customer rescinds approval
- Akcje: pause project, renegotiation, possibly cancel

---

## 25.6. Acceptance + transition do fazy 26

```bash
$ aeis-cli phase25-acceptance-test --project proj_customer_y_crm

[1/8] Księga generated (78 pages)                      ✓ PASS
[2/8] All sections complete                            ✓ PASS
[3/8] Council Book inheritance verified                ✓ PASS
[4/8] Coherence Guard passed                           ✓ PASS
[5/8] Customer-facing version ready                    ✓ PASS
[6/8] Operator reviewed                                ✓ PASS
[7/8] Księga locked (signed)                           ✓ PASS
[8/8] Audit chain entry ksiega_finalized               ✓ PASS

DoD: 8/8 ✓
Phase 25 ACCEPTED. Ready dla Phase 26 (Model Selection).

═══ GROUP C (Deliberacja → Księga) COMPLETE ═══
Ready dla Phase 26 (Planning, Group D).
```

---

# Status faz 20-25

🟢 **Wszystkie 6 faz complete**

**Zawiera**:
- ✓ Faza 20 — Council Convening (awakening sequence, briefing distribution, question formulation, 16 edge cases)
- ✓ Faza 21 — Initial Verdicts (parallel verdict generation, structured format, aggregation analysis, 15 edge cases)
- ✓ Faza 22 — Deliberation Rounds (iterative consensus building, adversarial mechanics, specialist overrides, round budget, operator interventions, 22 edge cases)
- ✓ Faza 23 — Consolidation (conflict resolution, operator hard-gate D4+, decision quality review, 15 edge cases)
- ✓ Faza 24 — Council Book Generation (formal record, generation workflow, customer-facing version, 15 edge cases)
- ✓ Faza 25 — Księga Finalization (project bible, generation z Council Book, lock workflow, customer notification, 15 edge cases)

**Total edge cases w pliku**: 98 cases (16+15+22+15+15+15)

**Grupa C (Deliberacja → Księga) COMPLETE**: 6 faz
**Łącznie 25 z 41 faz frozen**

⏳ **Po Twojej akceptacji** → **soft freeze faz 20-25** + przejście do **Faza 26 — Model Selection** (start grupy D "Planowanie").

🎯 **Milestone**: serce AEIS lifecycle gotowe. Operator ma teraz **Księga**
— single source of truth dla projektu. Wszystko po grupie C (planowanie /
wykonanie / testowanie / wdrożenie) bazuje na niej.
