# PROD R2 Human Gate Resolution Policy PASS1/PASS2

Date: 2026-05-18
Roadmap items: `B.1 Unified Human Gate`, `B.2 Unified ticket lifecycle`, `B.4 Mobile approve/reject`
Decision pack: `results/decisions/PROD-D4-HUMAN-GATE-RESOLUTION-POLICY_evidence_pack.json`
Status: `FROZEN_2X` for D3-D5 resolution policy and cross-plane Human Gate regression

## Scope

This freeze covers:

- D3-D5 terminal decisions (`approved`, `rejected`) require a non-empty operator reason in the canonical `TicketStore`.
- `escalated` tickets remain reviewable and can transition to a terminal state.
- `fetch_pending()` returns pending and escalated reviewable tickets.
- Legacy `/api/v1/gates/human/reviews` maps missing D3+ rationale to `422` instead of silently drifting.
- Mobile `/api/v1/mobile/queue/{ticket_id}/decision` maps missing D3+ rationale to `422`.
- Governance `/api/v1/governance/tickets/{ticket_id}/resolve` keeps the same public `422` contract while the backend store now also enforces it.
- Funding, deploy, round-meta and skills approval flows still resolve after the stricter Human Gate policy.

## Files Changed

- `src/sylion-pipeline/sylion/governance/ticket.py`
- `src/sylion-pipeline/sylion/governance/human_gate.py`
- `src/sylion-pipeline/sylion/api/governance_routes.py`
- `src/sylion-pipeline/sylion/api/gates_routes.py`
- `src/sylion-pipeline/sylion/api/operator_mobile_routes.py`
- `src/sylion-pipeline/sylion/funding_autopilot/governance_bridge.py`
- `src/sylion-pipeline/sylion/project_mode/round_meta_hooks.py`
- targeted governance, mobile, funding, deploy and round-meta tests

## Verification PASS1

```text
python -m pytest <combined Human Gate/funding/deploy regression suite> -q
139 passed, 6 warnings
```

Suite contents:

- `tests/governance/test_ticket_store.py`
- `tests/governance/test_human_gate_mirror.py`
- `tests/governance/test_human_gate_resolution_policy.py`
- `tests/operator_mobile/test_routes.py`
- `tests/aeis_v2/test_round_meta_post_approval.py`
- `tests/aeis_v2/test_be8_backend_extensions.py`
- `tests/funding/test_governance_bridge.py`
- `tests/funding/test_browser_automation.py`
- `tests/test_deploy_routes.py`
- `tests/test_funding_autopilot_routes.py`
- `tests/integration/test_unified_truth.py`
- `tests/integration/scenarios/test_S4_execution_with_gates.py`
- `tests/integration/scenarios/test_S7_funding_flow.py`
- `tests/skills/test_hg_required_skill.py`

## Verification PASS2

```text
python -m pytest <same combined Human Gate/funding/deploy regression suite> -q
139 passed, 6 warnings
```

Additional checks:

```text
python -m compileall -q src\sylion-pipeline\sylion\governance src\sylion-pipeline\sylion\api src\sylion-pipeline\sylion\funding_autopilot src\sylion-pipeline\sylion\project_mode
PASS

git diff --check
PASS
```

## Stop-Fix-Retest Notes

During this slice, the first wider run exposed and closed three failures:

- BE8 round-meta tests expected stale phase/status values after the execution/audit side effect; tests now accept the canonical `build_authorization` phase and audit-blocked outcomes.
- Funding browser tests assumed Playwright was absent; tests now explicitly simulate Playwright absence instead of depending on the host environment.
- Deploy and funding route suites depended on global post-resolve hooks that previous suites could clear; fixtures now explicitly register the required round-meta and funding hooks.

After those fixes, the full combined suite passed twice without further code changes.

## Boundary

This freeze does not yet complete the whole Human Gate consolidation roadmap:

- the canonical table is still named `governance_tickets`, not the final `human_gate_tickets`;
- ticket `owner` is still represented by `requested_by` / reviewer fields;
- mobile device identity and push non-repudiation remain a later slice;
- council quorum enforcement and full model-control-plane integration are outside this freeze.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-HUMAN-GATE-RESOLUTION-POLICY_evidence_pack.json
```

Expected rollback time: 30 minutes.
Data loss risk: `NONE`.
