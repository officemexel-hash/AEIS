---
name: aeis-governance-council-auditor
description: Use when auditing AEIS Human Gate, governance, decision ladder, council workflows, autonomy policies, model-role assignment, and end-to-end approval integration. Focus on whether these systems are merely implemented as modules or actually govern the runtime pipeline.
---

# AEIS Governance Council Auditor

Use this skill for the hardest part of the audit: proving whether AEIS governance is decorative or operative.

## Focus Areas

- Human Gate requests, reviews, queues, escalation, and audit trail
- council workflow, sessions, voting, quorum, and result handling
- decision ladder and decision-class propagation
- policy engines and autonomy controls
- where governance is injected into real project/workspace flows
- whether model-council logic is used to shape planning and execution

## Workflow

1. Read the implementation modules:
   - `sylion/governance/*`
   - `sylion/aeis/*autonomy*`
   - workspace/governance API routes
2. Trace where these modules are called from:
   - API routes
   - project kickoff
   - execution flows
   - deployment flows
   - funding or operator flows
3. Separate three states:
   - module exists
   - route exists
   - end-to-end policy is enforced
4. Compare the enforcement path against the canon:
   - risk-based Human Gate
   - model council before major changes
   - approval on costly/production/external actions
   - continuation of independent work

## Questions To Answer

- Does Human Gate classify risk or only store reviews?
- Does council voting affect runtime or only exist as an isolated feature?
- Are autonomy stages enforced or only defined?
- Are model roles/ranks/weights persisted and actually consulted?
- Where does the pipeline skip governance entirely?

## Output Targets

- `CODEX_AEIS_CANON_VS_REALITY.md`
- `CODEX_AEIS_FUNCTIONAL_AUDIT.md`
- `CODEX_AEIS_REPAIR_BACKLOG.md`

## Red Flags

- classifier always returns the same class
- votes exist but are never required
- Human Gate exists but is absent from project kickoff/execution
- autonomy policy exists but never blocks anything
- model council exists only as a workspace tool, not as project governance
