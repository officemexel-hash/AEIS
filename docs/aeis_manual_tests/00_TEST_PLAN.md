# AEIS Manual + Self-Test Plan

Status: draft approved for planning baseline

## Core Rule

AEIS passes only when all five local project simulations pass, their generated products are tested, AEIS Test Center is tested, guards are proven as real blockers, and AEIS later runs a second self-test against its own system.

No VPS deploy is allowed in this test phase. Local execution is allowed. Hetzner API key checks are allowed only as read-only checks unless separately approved.

## API Key And Budget Safety

When a test reaches the point of connecting AEIS to external model providers or Hetzner, the operator must be notified before any key is entered. The operator will enter temporary, minimal-budget, disposable keys for the test.

The assistant must not ask the operator to paste permanent secrets into chat. Secrets should be entered by the operator directly into the local UI, local `.env`, local secret store, or provider settings surface used by AEIS.

Provider usage priority:

1. Use subscription/included quota first, where available.
2. Prefer configured model providers with existing subscription limits, such as Claude, ChatGPT/OpenAI, Gemini, or equivalent provider quota.
3. Use paid budget only after subscription quota is unavailable, exhausted, or explicitly insufficient.
4. Any paid-budget mode requires visible cost cap, Human Gate approval, and audit evidence.
5. Any external infrastructure action remains blocked unless separately approved.

Required evidence for model/provider tests:

- provider configured,
- key presence verified without exposing the key,
- quota/subscription mode identified when possible,
- cost cap recorded,
- Human Gate approval recorded for any paid-budget path,
- audit trail recorded,
- no secret printed in logs, screenshots, reports, or chat.

## Stop-Fix-Restart

If a test detects a mock, stub, fallback masking failure, dead button, false success, placeholder artifact, broken API, bypassed Human Gate, fake council result, non-working skill, non-persistent memory, ineffective guard, or critical runtime/UI error:

1. Stop the current simulation.
2. Record a BLOCKER in `09_FINDINGS.md`.
3. Repair the issue.
4. Run focused technical verification.
5. Restart backend/frontend when required.
6. Restart the same simulation from the beginning.
7. Record the retest result in `10_REPAIR_LOG.md`.

No exceptions.

## Five Project Simulations

| ID | Project | Complexity | Local Product | Key Surfaces |
|---|---|---:|---|---|
| P1 | Mini CRM Local | Low | CRM app with customers, notes, statuses | Idea, Human Gate, Council, Book, Masterplan, artifact |
| P2 | Funding Assistant | Medium | Grant assistant with scoring and blocked submit | Funding, guards, documents, approval, audit |
| P3 | Mobile Approval Queue | Medium | Local approval queue with desktop/mobile states | Operator Mobile, Human Gate, queue, audit |
| P4 | Local Automation Runtime | High | Local task runtime with workers, retry, logs | Workers, runtime config, observability, guards |
| P5 | Complex Multi-Domain AEIS | Very high | Project platform with CRM, funding, mobile, runtime, governance | Full AEIS spine |

## Required Test Layers

- Dashboard inventory.
- UI to API to module mapping.
- Manual project simulations.
- Product tests for generated artifacts.
- AEIS Test Center tests.
- Funding criteria.
- Guards criteria.
- Skills adaptivity.
- Council analysis and discussion.
- Human Gate blocking and audit.
- Memory write, retrieval, and reuse.
- Cost/time/resource adaptivity.
- Final AEIS self-test run.

## Final Pass Criteria

AEIS passes when:

- P1-P5 pass after any required Stop-Fix-Restart cycles.
- Every generated product is tested locally.
- Funding passes local end-to-end criteria without external submit.
- Guards block real risk conditions and produce audit evidence.
- Human Gate cannot be bypassed on core decisions.
- Council produces real analyses, discussion, consolidation, and critic/adversarial critic evidence.
- Skills are selected, executed, and tested for adaptive creation/reuse.
- Memory stores and retrieves decisions, books, masterplans, artifacts, and test results.
- Test Center can test products and block release on failures.
- AEIS self-test produces a report comparable to the manual report.
- No `BLOCKER_OPEN` remains on the core path.
