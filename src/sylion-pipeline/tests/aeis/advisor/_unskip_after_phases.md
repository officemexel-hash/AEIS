# Integration Test Unskip Checklist

**File**: `tests/aeis/advisor/{role_resolver,variants,subscription,scaling}/test_integration_{module}.py`  
**Total scaffolds**: 16 test functions (all `@pytest.mark.skip`)  
**Status**: Awaiting Codex Phase 2 + Claude engine commits

---

## role_resolver (4 tests)

| # | Test function | Depends on | Unskip condition |
|---|---|---|---|
| 1 | ~~`test_resolve_with_real_preferences_blocked_provider_excluded`~~ ✅ | Codex preferences resolver | Commit `[advisor][codex][phase2][preferences]` landed AND `sylion.aeis.advisor.preferences.resolver` import works |
| 2 | ~~`test_resolve_with_real_pricing_cost_ceiling_enforced`~~ ✅ | Codex pricing estimator | Commit `[advisor][codex][phase2][pricing]` landed AND `sylion.aeis.advisor.pricing.estimator` import works |
| 3 | ~~`test_resolve_falls_back_to_local_when_external_blocked`~~ ✅ | Codex preferences resolver | Same as #1 |
| 4 | `test_routing_decision_audit_trail_persisted` | Claude engine audit subscriber | Commit `[advisor][claude][engine]` landed AND `sylion.aeis.advisor.events.audit_subscriber` import works |

## variants (4 tests)

| # | Test function | Depends on | Unskip condition |
|---|---|---|---|
| 5 | ~~`test_generate_with_real_pricing_estimates_costs`~~ ✅ | Codex pricing estimator | Commit `[advisor][codex][phase2][pricing]` landed |
| 6 | `test_aggressive_variant_uses_real_council_size_preference` | Codex preferences resolver | Commit `[advisor][codex][phase2][preferences]` landed |
| 7 | `test_cost_saving_variant_respects_blocked_providers` | Codex preferences resolver | Same as #6 |
| 8 | `test_variant_recommendations_within_budget_threshold_preference` | Codex preferences resolver | Same as #6 |

## subscription (4 tests)

| # | Test function | Depends on | Unskip condition |
|---|---|---|---|
| 9 | ~~`test_record_usage_via_real_pricing_correctly_calculates_cost`~~ ✅ | Codex pricing estimator | Commit `[advisor][codex][phase2][pricing]` landed |
| 10 | ~~`test_roi_calculator_with_real_30day_usage_metrics`~~ ✅ | Codex pricing estimator | Same as #9 (cost values must be real, not stub) |
| 11 | `test_purchase_card_human_gate_required_via_real_actions_module` | Codex/Claude actions service | Commit `[advisor][codex][phase2][actions]` OR `[advisor][claude][actions]` landed |
| 12 | `test_evidence_pack_id_present_when_actions_handles_purchase_card` | Codex/Claude actions service | Same as #11 |

## scaling (4 tests)

| # | Test function | Depends on | Unskip condition |
|---|---|---|---|
| 13 | ~~`test_topology_recommendation_uses_real_pricing_for_vps_cost`~~ ✅ | Codex pricing estimator | Commit `[advisor][codex][phase2][pricing]` landed |
| 14 | `test_staging_plan_respects_operator_preference_runtime_strategy` | Codex preferences resolver | Commit `[advisor][codex][phase2][preferences]` landed |
| 15 | `test_multi_vps_d3_evidence_pack_via_real_engine_creator` | Claude engine creator | Commit `[advisor][claude][engine] creator wired` landed |
| 16 | `test_env_inventory_persisted_with_real_pg_connection_pool` | Codex PG migration | Commit `[advisor][codex][phase1][pg_migration]` landed AND `sylion.aeis.advisor._db.get_pool` returns real `psycopg_pool.ConnectionPool` |

---

## How to bulk-unskip

When a phase lands, remove the relevant `@pytest.mark.skip(...)` decorators from the corresponding test functions.

Example (after preferences Phase 2):
```python
# BEFORE
@pytest.mark.skip(reason="awaiting Codex Phase 2 + Claude engine")
def test_resolve_with_real_preferences_blocked_provider_excluded():
    ...

# AFTER
def test_resolve_with_real_preferences_blocked_provider_excluded():
    ...
```

Or use `pytest.mark.skipif` for conditional skipping based on import availability:
```python
_HAS_PREFS = importlib.util.find_spec("sylion.aeis.advisor.preferences.resolver") is not None

@pytest.mark.skipif(not _HAS_PREFS, reason="preferences not yet available")
def test_resolve_with_real_preferences_blocked_provider_excluded():
    ...
```

---

## Cross-reference: import migration

When unskipping, also execute the import migration checklist from:
`docs/claude_parallel/aeis_advisor/_handoff/kimi_final_report.md` §5.2
