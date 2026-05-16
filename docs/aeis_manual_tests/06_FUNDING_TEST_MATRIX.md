# AEIS Funding Test Matrix

Status: P2 restart4 pass

## Funding Pass Rule

Funding passes only as a local, gated flow. No real external submission is allowed in this phase.

## Matrix

| Criterion | Expected Behavior | Evidence | Status |
|---|---|---|---|
| Funding sources | Sources load or are explicitly marked local/test | P2R4 generated `/programs`; local grant catalog present | PASS |
| Company intake | Required fields validate | Generated `OrganizationIn` and matching path tested by backend smoke | PASS |
| Deadline validation | Invalid/missing deadline blocks scoring | P2R4 generated `/match` marks expired program `deadline_expired` and score 0; generated backend pytest covers it | PASS |
| Provenance | Missing source blocks scoring/claims | P2R4 generated `/match` marks missing-source program `missing_source`; Council/Ksiega scan clean | PASS |
| Scoring | Scoring runs only with required data | `/match` scores only eligible programs above blocked programs | PASS |
| Documents | Required documents block submission until present | Generated backend checklist blocks missing documents | PASS |
| Draft | Draft can be saved locally | `/applications` creates local draft | PASS |
| Approval request | Approval event/ticket is created | `/applications/{id}/human-gate` stores local approval evidence | PASS |
| Final submit approval | Submit blocked without approval | Generated backend smoke covers blocked path before HumanGate | PASS |
| Legal confirmation | Submit blocked without legal confirmation | P2R4 generated `/prepare-submission` returns `legal_confirmation_required` before local rehearsal | PASS |
| Budget confirmation | Submit blocked without budget confirmation | P2R4 generated `/prepare-submission` returns `budget_confirmation_required` before local rehearsal | PASS |
| Document confirmation | Submit blocked without document confirmation | P2R4 generated `/prepare-submission` returns `document_confirmation_required` before local rehearsal | PASS |
| External submit | No real external submit occurs | Artifact scan clean; product returns local rehearsal only | PASS |
| Audit trail | Funding decisions and blocks are recorded | Council/Ksiega and generated app status trail present | PASS |
| Product UX | Product explains what is blocked and why | P2R4 generated frontend displays missing confirmations and disables final local submission until documents/legal/budget/HumanGate are complete | PASS |
