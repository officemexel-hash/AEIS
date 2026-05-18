"""
SYLION API -- Main router aggregating all sub-routers.

Mount this on a FastAPI application to enable all SYLION REST endpoints.
"""

from fastapi import APIRouter

from sylion.api.core_routes import router as core_router
from sylion.api.governance_routes import router as governance_router
from sylion.api.cognitive_routes import router as cognitive_router
from sylion.api.execution_routes import router as execution_router
from sylion.api.security_routes import router as security_router
from sylion.api.monitoring_routes import router as monitoring_router
from sylion.api.memory_routes import router as memory_router
from sylion.api.efficiency_routes import router as efficiency_router
from sylion.api.quality_routes import router as quality_router
from sylion.api.aeis_routes import router as aeis_router
from sylion.api.skills_routes import router as skills_router
from sylion.api.rebuild_routes import router as rebuild_router
from sylion.api.surface_routes import router as surface_router
from sylion.api.device_routes import router as device_router
from sylion.api.sdr_routes import router as sdr_router
from sylion.api.cellular_routes import router as cellular_router
from sylion.api.contract_routes import (
    manifest_router,
    router as contract_router,
)
from sylion.api.health_routes import router as health_router
from sylion.api.ws_routes import router as ws_router
from sylion.api.hot_swap_routes import router as hot_swap_router
from sylion.api.pipeline_routes import router as pipeline_router
from sylion.api.ai_workspace_routes import router as ai_workspace_router
from sylion.api.workspace_ws_routes import router as workspace_ws_router
from sylion.api.monitoring_budget_routes import router as monitoring_budget_router
from sylion.api.snapshot_routes import router as snapshot_router
from sylion.api.quality_gate_routes import router as quality_gate_router
from sylion.api.deployment_routes import router as deployment_router
from sylion.api.audit_routes import router as audit_router
from sylion.api.self_healing_routes import router as self_healing_router
from sylion.api.evidence_timeline_routes import router as evidence_timeline_router
from sylion.api.capacity_routes import router as capacity_router
from sylion.api.decision_boundaries_routes import router as decision_boundaries_router
from sylion.api.decision_snapshot_routes import router as decision_snapshot_router
from sylion.api.self_explanation_routes import router as self_explanation_router
from sylion.api.roles_routes import router as roles_router
from sylion.api.security_ext_routes import router as security_ext_router
from sylion.api.execution_guard_routes import router as execution_guard_router
from sylion.api.phantom_routes import router as phantom_router
from sylion.api.hardened_audit_routes import router as hardened_audit_router
from sylion.api.bundle_routes import router as bundle_router
from sylion.api.notification_routes import router as notification_router
from sylion.api.circuit_breaker_routes import router as circuit_breaker_router
from sylion.api.golden_set_routes import router as golden_set_router
from sylion.api.gates_routes import router as gates_router
from sylion.api.idea_routes import router as idea_router
from sylion.api.evaluator_routes import router as evaluator_router
from sylion.api.integration_routes import router as integration_router
from sylion.api.healing_engine_routes import router as healing_engine_router
from sylion.api.model_budget_routes import router as model_budget_router
from sylion.api.model_control_plane_routes import router as model_control_plane_router
from sylion.api.production_deploy_routes import router as production_deploy_router
from sylion.api.audit_sink_routes import router as audit_sink_router
from sylion.api.audit_query_routes import router as audit_query_router
from sylion.api.connector_routes import router as connector_router
from sylion.api.cloud_connectors_routes import router as cloud_connectors_router
from sylion.api.adapter_bus_routes import router as adapter_bus_router
from sylion.api.secret_routes import router as secret_router
from sylion.api.bootstrap_routes import router as bootstrap_router
from sylion.api.security_profiles_routes import router as security_profiles_router
from sylion.api.profile_swap_routes import router as profile_swap_router
from sylion.api.security_audit_routes import router as security_audit_router
from sylion.api.auth_routes import router as auth_router
from sylion.api.knowledge_routes import router as knowledge_router
from sylion.api.feedback_routes import router as feedback_router
from sylion.api.model_registry_routes import router as model_registry_router, alias_router as registry_alias_router
from sylion.api.regression_routes import router as regression_router
from sylion.api.version_routes import router as version_router
from sylion.api.lifecycle_routes import router as lifecycle_router
from sylion.api.rollback_routes import router as rollback_router
from sylion.api.agent_runtime_routes import router as agent_runtime_router
from sylion.api.vps_routes import router as vps_router
from sylion.api.vault_routes import router as vault_router
from sylion.api.risk_routes import router as risk_router
from sylion.api.container_routes import router as container_router
from sylion.api.worker_routes import router as worker_router
from sylion.api.integration_orchestrator_routes import router as integration_orchestrator_router
from sylion.api.event_backbone_routes import router as event_backbone_router
from sylion.api.deploy_routes import router as deploy_router
from sylion.api.worker_monitor_routes import router as worker_monitor_router
from sylion.api.freeze_routes import router as freeze_router
from sylion.api.build_state_routes import router as build_state_router
from sylion.api.autoscaler_routes import router as autoscaler_router
from sylion.api.observability_routes import router as observability_router
from sylion.api.ai_providers_routes import router as ai_providers_router
from sylion.api.provider_catalog_routes import router as provider_catalog_router
from sylion.api.environment_catalog_routes import router as environment_catalog_router
from sylion.api.workspace_defaults_routes import router as workspace_defaults_router
from sylion.api.coherence_guard_routes import router as coherence_guard_router
from sylion.api.guard_suite_routes import router as guard_suite_router
from sylion.api.templates_setup_routes import router as templates_setup_router
from sylion.api.project_start_routes import router as project_start_router
from sylion.api.council_to_ksiega_routes import router as council_to_ksiega_router
from sylion.api.planning_routes import router as planning_router
from sylion.api.execution_start_routes import router as execution_start_router
from sylion.api.decomposition_routes import router as decomposition_router
from sylion.api.architecture_layers_routes import router as architecture_layers_router
from sylion.api.runtime_truth_routes import router as runtime_truth_router

# Phase 2 — D-INTEGRATE: agent A/B/K route mounts
from sylion.api.council_routes import router as council_router
from sylion.api.autonomy_routes import router as autonomy_router
from sylion.api.autonomy_configuration_routes import router as autonomy_configuration_router
from sylion.api.operator_mobile_routes import (
    legacy_router as operator_mobile_legacy_router,
    router as operator_mobile_router,
)
from sylion.api.metrics_routes import router as metrics_router
from sylion.funding_autopilot.routes import router as funding_router
from sylion.api.projects_routes import router as projects_router
from sylion.api.projects_freeze_routes import router as projects_freeze_router
from sylion.api.advisor_routes import router as advisor_router
from sylion.api.teams_routes import router as teams_router

router = APIRouter()

router.include_router(core_router)
router.include_router(governance_router)
router.include_router(cognitive_router)
router.include_router(execution_router)
router.include_router(security_router)
router.include_router(monitoring_router)
router.include_router(memory_router)
router.include_router(efficiency_router)
router.include_router(quality_router)
router.include_router(aeis_router)
router.include_router(skills_router)
router.include_router(rebuild_router)
router.include_router(surface_router)
router.include_router(device_router)
router.include_router(sdr_router)
router.include_router(cellular_router)
router.include_router(contract_router)
router.include_router(manifest_router)
router.include_router(health_router)
router.include_router(ws_router)
router.include_router(hot_swap_router)
router.include_router(pipeline_router)
router.include_router(ai_workspace_router)
router.include_router(workspace_ws_router)
router.include_router(monitoring_budget_router)
router.include_router(snapshot_router)
router.include_router(quality_gate_router)
router.include_router(deployment_router)
router.include_router(audit_router)
router.include_router(self_healing_router)
router.include_router(evidence_timeline_router)
router.include_router(capacity_router)
router.include_router(decision_boundaries_router)
router.include_router(decision_snapshot_router)
router.include_router(self_explanation_router)
router.include_router(roles_router)
router.include_router(security_ext_router)
router.include_router(execution_guard_router)
router.include_router(phantom_router)
router.include_router(hardened_audit_router)
router.include_router(bundle_router)
router.include_router(notification_router)
router.include_router(circuit_breaker_router)
router.include_router(golden_set_router)
router.include_router(gates_router)
router.include_router(idea_router)
router.include_router(evaluator_router)
router.include_router(integration_router)
router.include_router(healing_engine_router)
router.include_router(model_budget_router)
router.include_router(model_control_plane_router)
router.include_router(production_deploy_router)
router.include_router(audit_sink_router)
router.include_router(audit_query_router)
router.include_router(connector_router)
router.include_router(cloud_connectors_router)
router.include_router(adapter_bus_router)
router.include_router(secret_router)
router.include_router(bootstrap_router)
router.include_router(security_profiles_router)
router.include_router(profile_swap_router)
router.include_router(security_audit_router)
router.include_router(auth_router)
router.include_router(knowledge_router)
router.include_router(feedback_router)
router.include_router(model_registry_router)
router.include_router(registry_alias_router)
router.include_router(regression_router)
router.include_router(version_router)
router.include_router(lifecycle_router)
router.include_router(rollback_router)
router.include_router(agent_runtime_router)
router.include_router(vps_router)
router.include_router(vault_router)
router.include_router(risk_router)
router.include_router(container_router)
router.include_router(worker_router)
router.include_router(integration_orchestrator_router)
router.include_router(event_backbone_router)
router.include_router(deploy_router)
router.include_router(worker_monitor_router)
router.include_router(freeze_router)
router.include_router(build_state_router)
router.include_router(autoscaler_router)
router.include_router(observability_router)
router.include_router(ai_providers_router)
router.include_router(provider_catalog_router)
router.include_router(environment_catalog_router)
router.include_router(workspace_defaults_router)
router.include_router(coherence_guard_router)
router.include_router(guard_suite_router)
router.include_router(templates_setup_router)
router.include_router(project_start_router)
router.include_router(council_to_ksiega_router)
router.include_router(planning_router)
router.include_router(execution_start_router)
router.include_router(decomposition_router)
router.include_router(architecture_layers_router)
router.include_router(runtime_truth_router)

# Phase 2 — D-INTEGRATE: A/B/K mounts
router.include_router(council_router)
router.include_router(autonomy_configuration_router)
router.include_router(autonomy_router)
router.include_router(operator_mobile_router)
router.include_router(operator_mobile_legacy_router)
router.include_router(metrics_router)
router.include_router(funding_router)
router.include_router(projects_router)
# W14 round_meta BE-1/BE-2/BE-3: static /freeze + /authorize endpoints.
router.include_router(projects_freeze_router)

# AEIS Advisor Layer (Etap 1) — REST bridge to engine/preferences/actions/funding
router.include_router(advisor_router)
router.include_router(teams_router)

# Section J — Meta-Orchestration controls (J1-J9)
from sylion.api.orchestration_routes import router as orchestration_router
router.include_router(orchestration_router)
