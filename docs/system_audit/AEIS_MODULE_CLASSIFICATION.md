# AEIS MODULE CLASSIFICATION (119 modules)

## Summary

- **CORE**:  65 modules ( 54.6%)
- **EXT**:  29 modules ( 24.4%)
- **EXP**:   3 modules (  2.5%)
- **DUP**:   7 modules (  5.9%)
- **LAB**:  15 modules ( 12.6%)

## Detailed Classification

### CORE Category (65 modules)

**Modules required for AEIS to function — no removal without major refactor**

- `aeis.improvement_queue` [FULL]
- `aeis.self_explanation` [FULL]
- `aeis.self_limitation` [FULL]
- `aeis.self_observation` [FULL]
- `aeis.self_preservation` [FULL]
- `cognitive.code_agent` [FULL]
- `cognitive.context_builder` [PARTIAL]
- `cognitive.evaluator` [FULL]
- `cognitive.llm_adapter` [FULL]
- `cognitive.model_router` [FULL]
- `cognitive.planner` [FULL]
- `cognitive.reasoner` [FULL]
- `core.bundle_assembler` [FULL]
- `core.contract_registry` [FULL]
- `core.decision_gate_engine` [FULL]
- `core.environment_orchestrator` [FULL]
- `core.event_bus` [FULL]
- `core.evidence_spine` [PARTIAL]
- `core.manifest_loader` [STUB]
- `core.module_registry` [FULL]
- `efficiency.code_bloat` [FULL]
- `efficiency.cost_envelope` [FULL]
- `efficiency.memory_footprint` [FULL]
- `efficiency.runtime_perf` [FULL]
- `execution.adapter_bus` [FULL]
- `execution.connector_framework` [FULL]
- `execution.job_runner` [FULL]
- `execution.retry_orchestrator` [FULL]
- `execution.tool_runner` [FULL]
- `execution.workflow_engine` [FULL]
- `governance.council_workflow` [FULL]
- `governance.decision_ladder` [FULL]
- `governance.evidence_workflow` [FULL]
- `governance.gates_registry` [FULL]
- `governance.policy_registry` [FULL]
- `governance.roles` [FULL]
- `governance.self_explanation_validator` [FULL]
- `memory.compact_layer` [FULL]
- `memory.evidence_store` [FULL]
- `memory.indexer` [FULL]
- `memory.kanon_access` [FULL]
- `memory.kb_adapter` [FULL]
- `memory.retrieval` [PARTIAL]
- `memory.self_model_store` [FULL]
- `quality.golden_set_registry` [FULL]
- `quality.regression_detector` [FULL]
- `quality.test_runner` [FULL]
- `rebuild.cft_runner` [FULL]
- `rebuild.cutover_controller` [FULL]
- `rebuild.lpw_manager` [FULL]
- `rebuild.orchestrator` [FULL]
- `security.audit_sink` [FULL]
- `security.auth_provider` [FULL]
- `security.bootstrap_init` [PARTIAL]
- `security.execution_guard` [FULL]
- `security.phantom_wrapper` [FULL]
- `security.policy_engine` [FULL]
- `security.secret_provider` [FULL]
- `security.session_broker` [FULL]
- `skills.demand_signal` [FULL]
- `skills.executor` [FULL]
- `skills.registry` [FULL]
- `surface.console_api` [FULL]
- `surface.console_ui` [FULL]
- `surface.ws_gateway` [FULL]
### EXT Category (29 modules)

**Production extensions with real value — keep unless explicitly replaced**

- `aeis.self_healing_orchestrator` [FULL]
- `cognitive.agent_runtime` [FULL]
- `cognitive.chat_engine` [FULL]
- `cognitive.feedback_collector` [FULL]
- `cognitive.idea_vault` [FULL]
- `cognitive.knowledge_distiller` [FULL]
- `cognitive.model_registry` [FULL]
- `core.code_snapshot` [FULL]
- `core.hot_swap` [FULL]
- `core.lifecycle_gates` [FULL]
- `core.rollback_manager` [FULL]
- `core.version_manager` [FULL]
- `devices.device_discovery` [FULL]
- `devices.device_registry` [FULL]
- `devices.test_harness` [FULL]
- `execution.capacity_planner` [FULL]
- `execution.deployment_orchestrator` [FULL]
- `governance.decision_boundaries` [FULL]
- `governance.decision_snapshot` [FULL]
- `governance.evidence_timeline` [FULL]
- `infra.topology_templates` [FULL]
- `monitoring.circuit_breaker` [FULL]
- `monitoring.model_budget` [FULL]
- `monitoring.notification_engine` [FULL]
- `monitoring.self_healing` [FULL]
- `quality.quality_gate_engine` [FULL]
- `security.audit_trail_aggregator` [FULL]
- `security.evidence_signer` [FULL]
- `security.security_profiles` [FULL]
### EXP Category (3 modules)

**Experimental/stub quality — integrate, refactor, or remove**

- `aeis.integration_controller` [FULL]
- `core.integration` [STUB]
- `core.worker` [STUB]
### DUP Category (7 modules)

**Duplicates/overlapping functionality — consolidate or remove**

- `security.audit_query` [FULL] — consolidate with audit_trail_aggregator
- `security.bootstrap_flow` [FULL] — merge with bootstrap_init
- `security.hardened_audit` [FULL] — consolidate with audit_trail_aggregator
- `security.key_vault` [FULL] — merge with secret_provider
- `security.profile_swap` [FULL] — consolidate with security_profiles
- `security.profiles` [STUB] — consolidate with security_profiles
- `security.security_audit` [FULL] — consolidate with audit_trail_aggregator
### LAB Category (15 modules)

**Laboratory modules — DO NOT TOUCH, mark only**

- `cellular.attack_vectors` [PARTIAL]
- `cellular.control_plane` [FULL]
- `cellular.core_network` [PARTIAL]
- `cellular.evidence_writer` [PARTIAL]
- `cellular.ran_lab` [PARTIAL]
- `cellular.rf_isolation` [PARTIAL]
- `cellular.ue_emulator` [PARTIAL]
- `container.docker_manager` [FULL]
- `devices.artifact_deployer` [PARTIAL]
- `sdr.capture_orchestrator` [PARTIAL]
- `sdr.protocol_decoder` [FULL]
- `sdr.rf_safety_governor` [FULL]
- `sdr.sdr_gateway` [PARTIAL]
- `sdr.signal_analyzer` [FULL]
- `vps.provider_manager` [FULL]
