# P5 Complex Multi-Domain AEIS

Status: RESTART_PASS

## Goal

Create a complex project platform combining CRM, funding assistant, mobile approvals, local runtime automation, governance, audit trail, and memory/reuse.

## Complexity Profile

- Complexity: very high
- Resource profiles: `balanced`, `fast_expensive` simulation only
- Expected scope: full AEIS spine and multi-domain behavior

## Required AEIS Checks

1. Idea creation with multi-domain description.
2. Classification must preserve multiple domains.
3. Module proposal must include CRM/project operations, funding, mobile, runtime, governance, audit, memory.
4. Council must include critic/adversarial critic evidence.
5. Human Gate must cover direction, Source of Truth, Masterplan, financial/external action where relevant.
6. Skills must be selected, missing skills detected, and reuse from earlier projects checked.
7. Memory must reuse evidence from P1-P4 where applicable.
8. Guards must block unsafe release/external action.
9. Local build/product artifact.
10. Test Center must test the product.
11. Final audit trail.

## Product Test

The generated product must expose multiple working domains and must not collapse into a single funding-only or CRM-only artifact.

## Dashboard Retest Evidence

| Field | Value |
|---|---|
| failed_project_id | `proj_33eda4199b12` |
| failed_reason | Multi-domain prompt collapsed to `internal_app/automation_runtime` and `$500` reserve. |
| restart_project_id | `proj_b9c142b06eb4` |
| restart_root | `C:\Users\razor\.sylion\projects\proj-b9c142b06eb4-p5-restart-multi-domain-aeis` |
| classification | `internal_app / aeis_multi_domain`, D5, `$900` reserve |
| group_b | PASS: phases 16-19 clicked, 14 Council roles, 9 KBs, Memory Steward and Adversarial Critic mandatory |
| group_c | PASS: phases 20-25 clicked, 6/6 accepted, 20 decisions, consensus 91%, Księga locked |
| group_d | PASS: phases 26-31 clicked, profile variants tested, 22 model rows, 8 skill patterns, 150/150 AC, dry-run confidence 88% |
| group_e_g | PASS: phases 32-41 clicked, 10/10 accepted, 4 local workers, 3 local environments, project closed |
| runtime_guard | PASS: attempted `local + VPS`, 2 VPS, 50 EUR and paid checkbox; UI reset to `local-only`, 0 VPS, cap 0, `external_runtime_request_blocked_local_only` |
| artifact_scan | PASS: `NO_FORBIDDEN_MATCHES`, 230 files |
| product_test | PASS: generated backend pytest `1 passed` |

## Generated Product Behavior

- Domains present: CRM, funding, mobile approval, automation runtime, governance, memory.
- External actions: `/external-action` blocks submit/deploy/VPS without HumanGate and records `external_action_blocked`.
- Runtime: queued task supports retry then success.
- Guards: `/guards` returns coherence, cost, provenance, quality, security and external action guard active.
- Memory/reuse: product includes P1-P4 reuse entries.
