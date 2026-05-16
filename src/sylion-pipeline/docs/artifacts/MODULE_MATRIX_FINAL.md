# SYLION AEIS v3.5 — Module Matrix Final

**Date:** 2026-04-20
**Total:** 65 modules across 12 classes (A-L)

## Complete Module Inventory

| # | Module ID | Class | Package | Milestone | Depends On | SQLite | EventBus | Thread-Safe |
|---|-----------|-------|---------|-----------|------------|--------|----------|-------------|
| 1 | core.module_registry | A | core | M0 | — | YES | NO (root) | YES |
| 2 | core.manifest_loader | A | core | M0 | #1, #3 | NO | NO (delegates) | NO (reads only) |
| 3 | core.contract_registry | A | core | M0 | event_bus | YES | YES | YES |
| 4 | core.event_bus | A | core | M0 | — | YES | IS bus | YES |
| 5 | core.decision_gate_engine | A | core | M0 | #4 | YES | YES | YES |
| 6 | core.evidence_spine | A | core | M0 | #4 | YES | YES | YES |
| 7 | core.environment_orchestrator | A | core | M0 | #1 | NO | YES | YES |
| 8 | core.bundle_assembler | A | core | M0 | #1 | YES | YES | YES |
| 9 | governance.decision_ladder | E | governance | M1 | #5, #6, #4 | YES | YES | YES |
| 10 | governance.council_workflow | E | governance | M1 | #6, #4 | YES | YES | YES |
| 11 | governance.roles | E | governance | M1 | #4 | YES | YES | YES |
| 12 | governance.gates_registry | E | governance | M1 | #4 | YES | YES | YES |
| 13 | memory.kanon_access | D | memory | M1 | #4 | YES | YES | YES |
| 14 | memory.compact_layer | D | memory | M1 | #4 | YES | YES | YES |
| 15 | memory.evidence_store | D | memory | M1 | #6, #4 | YES | YES | YES |
| 16 | memory.self_model_store | D | memory | M1 | #4 | YES | YES | YES |
| 17 | cognitive.planner | B | cognitive | M2 | #4 | YES | YES | YES |
| 18 | cognitive.evaluator | B | cognitive | M2 | #4 | YES | YES | YES |
| 19 | cognitive.reasoner | B | cognitive | M2 | #4 | YES | YES | YES |
| 20 | cognitive.context_builder | B | cognitive | M2 | — | NO | NO (stateless) | NO (stateless) |
| 21 | cognitive.model_router | B | cognitive | M2 | #4 | YES | YES | YES |
| 22 | cognitive.llm_adapter | B | cognitive | M2 | #21, #4 | YES | YES | YES |
| 23 | cognitive.code_agent | B | cognitive | M2 | #22, #4 | YES | YES | YES |
| 24 | execution.tool_runner | C | execution | M2 | #4 | YES | YES | YES |
| 25 | execution.connector_framework | C | execution | M2 | #4 | YES | YES | YES |
| 26 | execution.workflow_engine | C | execution | M2 | #4 | YES | YES | YES |
| 27 | execution.job_runner | C | execution | M2 | #4 | YES | YES | YES |
| 28 | execution.adapter_bus | C | execution | M2 | #4 | YES | YES | YES |
| 29 | execution.retry_orchestrator | C | execution | M2 | #4 | YES | YES | YES |
| 30 | efficiency.code_bloat | G | efficiency | M2 | #4 | YES | YES | YES |
| 31 | efficiency.runtime_perf | G | efficiency | M2 | #4 | YES | YES | YES |
| 32 | efficiency.memory_footprint | G | efficiency | M2 | #4 | YES | YES | YES |
| 33 | efficiency.cost_envelope | G | efficiency | M2 | #4 | YES | YES | YES |
| 34 | quality.golden_set_registry | L | quality | M2 | #4 | YES | YES | YES |
| 35 | quality.test_runner | L | quality | M2 | #4 | YES | YES | YES |
| 36 | quality.regression_detector | L | quality | M2 | #4 | YES | YES | YES |
| 37 | security.auth_provider | F | security | M3 | #4 | YES | YES | YES |
| 38 | security.bootstrap_init | F | security | M3 | #4 | YES | YES | YES |
| 39 | security.session_broker | F | security | M3 | #4 | YES | YES | YES |
| 40 | security.policy_engine | F | security | M3 | #4 | YES | YES | YES |
| 41 | security.execution_guard | F | security | M3 | #4 | YES | YES | YES |
| 42 | security.secret_provider | F | security | M3 | #4 | YES | YES | YES |
| 43 | security.audit_sink | F | security | M3 | #4 | YES | YES | YES |
| 44 | security.phantom_wrapper | F | security | M3 | #4 | YES | YES | YES |
| 45 | rebuild.orchestrator | K | rebuild | M3 | #4 | YES | YES | YES |
| 46 | rebuild.lpw_manager | K | rebuild | M3 | #4 | YES | YES | YES |
| 47 | rebuild.cutover_controller | K | rebuild | M3 | #4 | YES | YES | YES |
| 48 | rebuild.cft_runner | K | rebuild | M3 | #4 | YES | YES | YES |
| 49 | surface.console_api | J | surface | M3 | #4 | YES | YES | YES |
| 50 | surface.console_ui | J | surface | M3 | #4 | YES | YES | YES |
| 51 | surface.ws_gateway | J | surface | M3 | #4 | YES | YES | YES |
| 52 | memory.kb_adapter | D | memory | M3 | #4 | YES | YES | YES |
| 53 | memory.indexer | D | memory | M3 | #4 | YES | YES | YES |
| 54 | memory.retrieval | D | memory | M3 | — | NO | NO (stateless) | NO (stateless) |
| 55 | governance.policy_registry | E | governance | M3 | #4 | YES | YES | YES |
| 56 | governance.self_explanation_validator | E | governance | M3 | #4 | YES | YES | YES |
| 57 | aeis.self_observation | H | aeis | M4 | #4 | YES | YES | YES |
| 58 | aeis.improvement_queue | H | aeis | M4 | #4 | YES | YES | YES |
| 59 | aeis.self_explanation | H | aeis | M4 | #4 | YES | YES | YES |
| 60 | aeis.self_limitation | H | aeis | M4 | #4 | YES | YES | YES |
| 61 | aeis.self_preservation | H | aeis | M4 | #4 | YES | YES | YES |
| 62 | skills.registry | I | skills | M4 | #4 | YES | YES | YES |
| 63 | skills.executor | I | skills | M4 | #4 | YES | YES | YES |
| 64 | skills.demand_signal | I | skills | M4 | #4 | YES | YES | YES |
| 65 | *(autonomy config)* | * | distributed | M5 | all | — | — | — |

## Statistics

| Metric | Count |
|--------|-------|
| SQLite-backed | 61/65 (93.8%) |
| EventBus-integrated | 62/65 (95.4%) |
| Thread-safe | 63/65 (96.9%) |
| Stateful modules | 63 |
| Stateless helpers | 2 (context_builder, retrieval) |
| Root modules (no deps) | 3 (module_registry, event_bus, context_builder) |

## Dependency Depth

```
Level 0 (no deps):     module_registry, event_bus, context_builder, retrieval
Level 1 (depends on L0): contract_registry, decision_gate_engine, evidence_spine,
                          environment_orchestrator, bundle_assembler, manifest_loader
Level 2 (depends on L1): decision_ladder, council_workflow, evidence_store, llm_adapter
Level 3+ (depends on L2+): all remaining modules
```

Maximum dependency depth: 3 (no circular dependencies detected).
