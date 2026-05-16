# 01 · INVENTORY BACKEND — katalog modułów SYLION AEIS v3.5

Inwentaryzacja backendu na dzień 2026-04-24. Źródło: 119 manifestów w
`sylion/contracts/manifests/*.json` + kod w `sylion/` + routery w `sylion/api/`.

Dokument jest produktem ETAP 1 audytu — tylko inwentaryzacja, bez oceny jakości.

---

## Statystyki ogólne

- **Total manifestów**: 119
- **W Księdze (z planowanych 65)**: 64
- **Poza Księgą (nowe, rozszerzenia)**: 55
- **Moduły LABORATORYJNE (nie ruszać)**: 15
- **Manifesty bez implementacji**: 0
- **Manifesty bez routera API**: 5

### Podział na domeny

| Domena | Liczba manifestów |
|--------|-------------------|
| aeis | 7 |
| cellular | 7 |
| cognitive | 13 |
| container | 1 |
| core | 15 |
| devices | 4 |
| efficiency | 4 |
| execution | 8 |
| governance | 10 |
| infra | 1 |
| memory | 7 |
| monitoring | 4 |
| quality | 4 |
| rebuild | 4 |
| sdr | 5 |
| security | 18 |
| skills | 3 |
| surface | 3 |
| vps | 1 |
| **RAZEM** | **119** |

---

## Katalog modułów backendu

Kolumny:

- **Moduł** — `module_id` z manifestu
- **Domena** — prefix przed pierwszą kropką
- **Impl path** — ścieżka implementacji (`-` jeśli brak)
- **Router path** — ścieżka pliku routera (`-` jeśli brak)
- **API prefix** — prefiks URL z routera
- **Kanon** — ✓ jeśli w 65 planowanych, ✗ jeśli powstał później
- **Zależności** — `depends_on` z manifestu
- **Cel** — 1-liniowy opis (z `description` manifestu)

| # | Moduł | Domena | Impl path | Router path | API prefix | Kanon | Zależności | Cel |
|---|-------|--------|-----------|-------------|------------|-------|------------|-----|
| 1 | `aeis.improvement_queue` | aeis | `sylion/aeis/improvement_queue.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✓ | core.event_bus | Priority queue of self-improvement proposals with evidence requirements. |
| 2 | `aeis.integration_controller` | aeis | `sylion/aeis/integration_controller.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✗ | - | Integration controller for external systems and APIs. |
| 3 | `aeis.self_explanation` | aeis | `sylion/aeis/self_explanation.py` | `sylion/api/self_explanation_routes.py` | `/api/v1/self-explanation` | ✓ | core.event_bus | Generates human-readable explanations of system decisions and behavior. |
| 4 | `aeis.self_healing_orchestrator` | aeis | `sylion/aeis/self_healing_orchestrator.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✗ | - | Self-healing orchestration engine for AEIS. |
| 5 | `aeis.self_limitation` | aeis | `sylion/aeis/self_limitation.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✓ | core.event_bus | Enforces hard limits on system capabilities. Cannot be bypassed. |
| 6 | `aeis.self_observation` | aeis | `sylion/aeis/self_observation.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✓ | core.event_bus | Real-time self-observation of system state, performance, and health. |
| 7 | `aeis.self_preservation` | aeis | `sylion/aeis/self_preservation.py` | `sylion/api/aeis_routes.py` | `/api/v1/aeis` | ✓ | core.event_bus | Protects system integrity. Detects and prevents self-modification attacks. |
| 8 | `cellular.attack_vectors` | cellular | `sylion/cellular/attack_vectors.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | Library of known cellular attack vectors for security testing. |
| 9 | `cellular.control_plane` | cellular | `sylion/cellular/control_plane.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | Control plane message analysis and protocol fuzzing. |
| 10 | `cellular.core_network` | cellular | `sylion/cellular/core_network.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | Core network emulation: AMF, SMF, UPF, and subscriber management. |
| 11 | `cellular.evidence_writer` | cellular | `sylion/cellular/evidence_writer.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | Writes cellular test evidence to EvidenceSpine with structured payloads. |
| 12 | `cellular.ran_lab` | cellular | `sylion/cellular/ran_lab.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | RAN (Radio Access Network) lab emulation with gNB and UE simulation. |
| 13 | `cellular.rf_isolation` | cellular | `sylion/cellular/rf_isolation.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | RF isolation validation for lab environment safety compliance. |
| 14 | `cellular.ue_emulator` | cellular | `sylion/cellular/ue_emulator.py` | `sylion/api/cellular_routes.py` | `/api/v1/cellular` | ✗ | core.event_bus | User Equipment emulator with attach/detach and mobility simulation. |
| 15 | `cognitive.agent_runtime` | cognitive | `sylion/cognitive/agent_runtime.py` | `sylion/api/agent_runtime_routes.py` | `/api/v1/agents` | ✗ | - | Agent runtime environment for executing autonomous agents. |
| 16 | `cognitive.chat_engine` | cognitive | `sylion/cognitive/chat_engine.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✗ | - | AI workspace chat engine for operator interaction. |
| 17 | `cognitive.code_agent` | cognitive | `sylion/cognitive/code_agent.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Autonomous code generation and modification agent with sandbox execution. |
| 18 | `cognitive.context_builder` | cognitive | `sylion/cognitive/context_builder.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Builds execution context from memory, evidence, and system state. |
| 19 | `cognitive.evaluator` | cognitive | `sylion/cognitive/evaluator.py` | `sylion/api/evaluator_routes.py` | `/api/v1/evaluator` | ✓ | core.event_bus | Evaluates plan quality, feasibility, and alignment with constraints. |
| 20 | `cognitive.feedback_collector` | cognitive | `sylion/cognitive/feedback_collector.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✗ | - | Feedback collection and processing for cognitive models. |
| 21 | `cognitive.idea_vault` | cognitive | `sylion/cognitive/idea_vault.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✗ | - | Idea vault for storing and managing creative concepts. |
| 22 | `cognitive.knowledge_distiller` | cognitive | `sylion/cognitive/knowledge_distiller.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✗ | - | Knowledge distillation from pipeline runs into canonical form. |
| 23 | `cognitive.llm_adapter` | cognitive | `sylion/cognitive/llm_adapter.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Unified adapter for LLM providers (OpenAI, Anthropic, local). Token tracking. |
| 24 | `cognitive.model_registry` | cognitive | `sylion/cognitive/model_registry.py` | `sylion/api/model_registry_routes.py` | `/api/v1/model-registry` | ✗ | - | Registry of AI models with versioning and metadata. |
| 25 | `cognitive.model_router` | cognitive | `sylion/cognitive/model_router.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Routes LLM requests to optimal model based on task type and cost envelope. |
| 26 | `cognitive.planner` | cognitive | `sylion/cognitive/planner.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Multi-agent planning engine. Decomposes goals into executable task trees. |
| 27 | `cognitive.reasoner` | cognitive | `sylion/cognitive/reasoner.py` | `sylion/api/cognitive_routes.py` | `/api/v1/cognitive` | ✓ | core.event_bus | Logical reasoning engine with chain-of-thought and formal verification hooks. |
| 28 | `container.docker_manager` | container | `sylion/container/docker_manager.py` | `sylion/api/container_routes.py` | `/api/v1/container` | ✗ | - | Docker & Kubernetes container manager. Tracks containers, images, pods and deployments. |
| 29 | `core.bundle_assembler` | core | `sylion/core/bundle_assembler.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.event_bus, core.module_registry | Assemble, validate, and ship module bundles for coordinated deployment. |
| 30 | `core.code_snapshot` | core | `sylion/core/code_snapshot.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✗ | - | Code snapshot and versioning for bundle assemblies. |
| 31 | `core.contract_registry` | core | `sylion/core/contract_registry.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.event_bus | Versioned repository of inter-module contracts. Detects breaking changes. |
| 32 | `core.decision_gate_engine` | core | `sylion/core/decision_gate_engine.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.event_bus | Classifies changes D0-D5 and evaluates governance gates. Foundation of governance. |
| 33 | `core.environment_orchestrator` | core | `sylion/core/environment_orchestrator.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.event_bus, core.module_registry, core.bundle_assembler | Manage module deployment lifecycle with shadow->dual->cutover transitions. |
| 34 | `core.event_bus` | core | `sylion/core/event_bus.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | - | Pub/sub event backbone. SQLite-backed (NATS JetStream later). Event taxonomy: domain.event.action |
| 35 | `core.evidence_spine` | core | `sylion/core/evidence_spine.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.event_bus | Immutable hash-chain audit log. SHA-256 chain with tamper-evident evidence entries. |
| 36 | `core.hot_swap` | core | `sylion/core/hot_swap.py` | `sylion/api/hot_swap_routes.py` | `/api/v1/hot-swap` | ✗ | - | Hot-swap environment manager for zero-downtime deployments. |
| 37 | `core.integration` | core | `sylion/integration/__init__.py` | `sylion/api/integration_routes.py` | `/api/v1/integrations` | ✗ | core.event_bus, core.module_registry, core.worker | Candidate build orchestration, validation pipeline, and cross-module contract drift detection. |
| 38 | `core.lifecycle_gates` | core | `sylion/core/lifecycle_gates.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✗ | - | Module lifecycle gates and transition validation. |
| 39 | `core.manifest_loader` | core | `sylion/core/manifest_loader.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | core.module_registry, core.contract_registry | Parse and validate module.yaml manifests against canonical schema. |
| 40 | `core.module_registry` | core | `sylion/core/module_registry.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✓ | - | Single source of truth about living modules. Module lifecycle state machine. |
| 41 | `core.rollback_manager` | core | `sylion/core/rollback_manager.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✗ | - | Rollback manager for reversibility and recovery. |
| 42 | `core.version_manager` | core | `sylion/core/version_manager.py` | `sylion/api/core_routes.py` | `/api/v1/core` | ✗ | - | Version manager for system-wide versioning. |
| 43 | `core.worker` | core | `sylion/worker/__init__.py` | `sylion/api/worker_routes.py` | `/api/v1/workers` | ✗ | core.event_bus, core.module_registry | Distributed build worker registry, assignment orchestration, compact generation and build topology management. |
| 44 | `devices.artifact_deployer` | devices | `sylion/devices/artifact_deployer.py` | `-` | `-` | ✗ | core.event_bus | Deploys artifacts to target devices with rollback support. |
| 45 | `devices.device_discovery` | devices | `sylion/devices/device_discovery.py` | `-` | `-` | ✗ | core.event_bus | Discovers devices on the network via multiple protocols. |
| 46 | `devices.device_registry` | devices | `sylion/devices/device_registry.py` | `-` | `-` | ✗ | core.event_bus | Registry of known devices with capabilities and status tracking. |
| 47 | `devices.test_harness` | devices | `sylion/devices/test_harness.py` | `-` | `-` | ✗ | core.event_bus | On-device test execution harness with result collection. |
| 48 | `efficiency.code_bloat` | efficiency | `sylion/efficiency/code_bloat.py` | `sylion/api/efficiency_routes.py` | `/api/v1/efficiency` | ✓ | core.event_bus | Tracks code size, complexity, and duplication metrics. |
| 49 | `efficiency.cost_envelope` | efficiency | `sylion/efficiency/cost_envelope.py` | `sylion/api/efficiency_routes.py` | `/api/v1/efficiency` | ✓ | core.event_bus | LLM cost tracking with budget envelopes and per-task allocation. |
| 50 | `efficiency.memory_footprint` | efficiency | `sylion/efficiency/memory_footprint.py` | `sylion/api/efficiency_routes.py` | `/api/v1/efficiency` | ✓ | core.event_bus | Memory usage tracking and leak detection across modules. |
| 51 | `efficiency.runtime_perf` | efficiency | `sylion/efficiency/runtime_perf.py` | `sylion/api/efficiency_routes.py` | `/api/v1/efficiency` | ✓ | core.event_bus | Runtime performance monitoring with latency histograms and throughput. |
| 52 | `execution.adapter_bus` | execution | `sylion/execution/adapter_bus.py` | `sylion/api/adapter_bus_routes.py` | `/api/v1/adapters` | ✓ | core.event_bus | Message bus for inter-adapter communication with protocol translation. |
| 53 | `execution.capacity_planner` | execution | `sylion/execution/capacity_planner.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✗ | - | Capacity planning and resource allocation. |
| 54 | `execution.connector_framework` | execution | `sylion/execution/connector_framework.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✓ | core.event_bus | Plugin framework for external system connectors (REST, gRPC, DB). |
| 55 | `execution.deployment_orchestrator` | execution | `sylion/execution/deployment_orchestrator.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✗ | - | Deployment orchestration for pipelines and jobs. |
| 56 | `execution.job_runner` | execution | `sylion/execution/job_runner.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✓ | core.event_bus | Background job execution with priority queues and resource limits. |
| 57 | `execution.retry_orchestrator` | execution | `sylion/execution/retry_orchestrator.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✓ | core.event_bus | Exponential backoff retry with circuit breaker and dead-letter queue. |
| 58 | `execution.tool_runner` | execution | `sylion/execution/tool_runner.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✓ | core.event_bus | Executes registered tools with input validation and output capture. |
| 59 | `execution.workflow_engine` | execution | `sylion/execution/workflow_engine.py` | `sylion/api/execution_routes.py` | `/api/v1/execution` | ✓ | core.event_bus | DAG-based workflow orchestration with parallel execution and checkpointing. |
| 60 | `governance.council_workflow` | governance | `sylion/governance/council_workflow.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus, core.evidence_spine, core.decision_gate_e... | Council voting workflow: propose, deliberate, vote, ratify. |
| 61 | `governance.decision_boundaries` | governance | `sylion/governance/decision_boundaries.py` | `sylion/api/decision_boundaries_routes.py` | `/api/v1/decision-boundaries` | ✗ | - | Decision boundary enforcement for D0-D5 classifications. |
| 62 | `governance.decision_ladder` | governance | `sylion/governance/decision_ladder.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus, core.evidence_spine, core.decision_gate_e... | Implements the D0-D5 decision classification ladder with auto-routing. |
| 63 | `governance.decision_snapshot` | governance | `sylion/governance/decision_snapshot.py` | `sylion/api/decision_snapshot_routes.py` | `/api/v1/decision-snapshots` | ✗ | - | Decision snapshot capture and audit trail. |
| 64 | `governance.evidence_timeline` | governance | `sylion/governance/evidence_timeline.py` | `sylion/api/evidence_timeline_routes.py` | `/api/v1/evidence-timeline` | ✗ | - | Evidence timeline aggregation and visualization. |
| 65 | `governance.evidence_workflow` | governance | `sylion/governance/evidence_workflow.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus, core.evidence_spine | Evidence collection, review, and chain-of-custody workflow. |
| 66 | `governance.gates_registry` | governance | `sylion/governance/gates_registry.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus, core.decision_gate_engine | Registry of governance gates (G-xxx) with enable/disable and evaluation. |
| 67 | `governance.policy_registry` | governance | `sylion/governance/policy_registry.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus | Central policy registry with versioning and enforcement hooks. |
| 68 | `governance.roles` | governance | `sylion/governance/roles.py` | `sylion/api/roles_routes.py` | `/api/v1/roles` | ✓ | core.event_bus | Role-based access control for governance actors (Agent, Board, Council, Human). |
| 69 | `governance.self_explanation_validator` | governance | `sylion/governance/self_explanation_validator.py` | `sylion/api/governance_routes.py` | `/api/v1/governance` | ✓ | core.event_bus | Validates that system decisions include adequate self-explanations. |
| 70 | `infra.topology_templates` | infra | `sylion/infra/topology_templates.py` | `-` | `-` | ✗ | core.worker, core.module_registry | Terraform and Ansible topology template generator for distributed AEIS deployments. |
| 71 | `memory.compact_layer` | memory | `sylion/memory/compact_layer.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus | Compaction and summarization layer for long-term memory storage. |
| 72 | `memory.evidence_store` | memory | `sylion/memory/evidence_store.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus, core.evidence_spine | Structured evidence storage with link to EvidenceSpine hash chain. |
| 73 | `memory.indexer` | memory | `sylion/memory/indexer.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus | Full-text and semantic indexing for memory retrieval. |
| 74 | `memory.kanon_access` | memory | `sylion/memory/kanon_access.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus | Access layer for Ksiega (Kanon) sections. Versioned knowledge base. |
| 75 | `memory.kb_adapter` | memory | `sylion/memory/kb_adapter.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus | Adapter for external knowledge base integrations (vector DB, graph DB). |
| 76 | `memory.retrieval` | memory | `sylion/memory/retrieval.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus, memory.indexer | Unified retrieval interface combining keyword, semantic, and graph search. |
| 77 | `memory.self_model_store` | memory | `sylion/memory/self_model_store.py` | `sylion/api/memory_routes.py` | `/api/v1/memory` | ✓ | core.event_bus | Persistent store for self-model (capabilities, limits, identity). |
| 78 | `monitoring.circuit_breaker` | monitoring | `sylion/monitoring/circuit_breaker.py` | `sylion/api/circuit_breaker_routes.py` | `/api/v1/circuit-breakers` | ✗ | - | Circuit breaker for fault tolerance and resilience. |
| 79 | `monitoring.model_budget` | monitoring | `sylion/monitoring/model_budget.py` | `sylion/api/model_budget_routes.py` | `/api/v1/model-budget` | ✗ | - | Per-model budget tracking and enforcement. |
| 80 | `monitoring.notification_engine` | monitoring | `sylion/monitoring/notification_engine.py` | `sylion/api/monitoring_routes.py` | `/api/v1/monitoring` | ✗ | - | Notification engine for alerts and operator alerts. |
| 81 | `monitoring.self_healing` | monitoring | `sylion/monitoring/self_healing.py` | `sylion/api/self_healing_routes.py` | `/api/v1/self-healing` | ✗ | - | Self-healing engine for automatic remediation. |
| 82 | `quality.golden_set_registry` | quality | `sylion/quality/golden_set_registry.py` | `sylion/api/quality_routes.py` | `/api/v1/quality` | ✓ | core.event_bus | Registry of golden test sets with expected outputs and thresholds. |
| 83 | `quality.quality_gate_engine` | quality | `sylion/quality/quality_gate_engine.py` | `sylion/api/quality_routes.py` | `/api/v1/quality` | ✗ | - | Quality gate engine for entry/exit criteria validation. |
| 84 | `quality.regression_detector` | quality | `sylion/quality/regression_detector.py` | `sylion/api/quality_routes.py` | `/api/v1/quality` | ✓ | core.event_bus | Detects regressions by comparing current results against golden sets. |
| 85 | `quality.test_runner` | quality | `sylion/quality/test_runner.py` | `sylion/api/quality_routes.py` | `/api/v1/quality` | ✓ | core.event_bus | Test execution engine with golden set comparison and reporting. |
| 86 | `rebuild.cft_runner` | rebuild | `sylion/rebuild/cft_runner.py` | `sylion/api/rebuild_routes.py` | `/api/v1/rebuild` | ✓ | core.event_bus | Cross-Functional Test runner for rebuild validation. |
| 87 | `rebuild.cutover_controller` | rebuild | `sylion/rebuild/cutover_controller.py` | `sylion/api/rebuild_routes.py` | `/api/v1/rebuild` | ✓ | core.event_bus | Controls cutover from old to new module implementation. |
| 88 | `rebuild.lpw_manager` | rebuild | `sylion/rebuild/lpw_manager.py` | `sylion/api/rebuild_routes.py` | `/api/v1/rebuild` | ✓ | core.event_bus | Last-Processed-Window manager for zero-data-loss rebuild transitions. |
| 89 | `rebuild.orchestrator` | rebuild | `sylion/rebuild/orchestrator.py` | `sylion/api/rebuild_routes.py` | `/api/v1/rebuild` | ✓ | core.event_bus | Orchestrates module rebuild lifecycle: plan, execute, validate. |
| 90 | `sdr.capture_orchestrator` | sdr | `sylion/sdr/capture_orchestrator.py` | `sylion/api/sdr_routes.py` | `/api/v1/sdr` | ✗ | core.event_bus, sdr.rf_safety_governor | Orchestrates multi-channel RF capture with scheduling and coordination. |
| 91 | `sdr.protocol_decoder` | sdr | `sylion/sdr/protocol_decoder.py` | `sylion/api/sdr_routes.py` | `/api/v1/sdr` | ✗ | core.event_bus | Protocol identification and decoding for known RF protocols. |
| 92 | `sdr.rf_safety_governor` | sdr | `sylion/sdr/rf_safety_governor.py` | `sylion/api/sdr_routes.py` | `/api/v1/sdr` | ✗ | core.event_bus | RF safety governor. Enforces transmission limits and compliance. |
| 93 | `sdr.sdr_gateway` | sdr | `sylion/sdr/sdr_gateway.py` | `sylion/api/sdr_routes.py` | `/api/v1/sdr` | ✗ | core.event_bus | SDR hardware gateway. Manages radio interfaces and capture sessions. |
| 94 | `sdr.signal_analyzer` | sdr | `sylion/sdr/signal_analyzer.py` | `sylion/api/sdr_routes.py` | `/api/v1/sdr` | ✗ | core.event_bus | Signal analysis: spectral, temporal, modulation classification. |
| 95 | `security.audit_query` | security | `sylion/security/audit_query.py` | `sylion/api/audit_query_routes.py` | `/api/v1/audit-query` | ✗ | - | Audit query engine for security log analysis. |
| 96 | `security.audit_sink` | security | `sylion/security/audit_sink.py` | `sylion/api/audit_sink_routes.py` | `/api/v1/audit-sink` | ✓ | core.event_bus | Immutable audit log sink. All security events flow here. |
| 97 | `security.audit_trail_aggregator` | security | `sylion/security/audit_trail_aggregator.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✗ | - | Audit trail aggregation across all modules. |
| 98 | `security.auth_provider` | security | `sylion/security/auth_provider.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Authentication provider supporting bootstrap, session, OIDC modes. |
| 99 | `security.bootstrap_flow` | security | `sylion/security/bootstrap_flow.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✗ | - | Bootstrap flow initialization for security defaults. |
| 100 | `security.bootstrap_init` | security | `sylion/security/bootstrap_init.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Bootstrap initialization for security subsystem. First-run setup. |
| 101 | `security.evidence_signer` | security | `sylion/security/evidence_signer.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✗ | - | Cryptographic evidence signing for tamper-proof logs. |
| 102 | `security.execution_guard` | security | `sylion/security/execution_guard.py` | `sylion/api/execution_guard_routes.py` | `/api/v1/execution-guard` | ✓ | core.event_bus | Guards code execution with sandboxing and resource limits. |
| 103 | `security.hardened_audit` | security | `sylion/security/hardened_audit.py` | `sylion/api/hardened_audit_routes.py` | `/api/v1/hardened-audit` | ✗ | - | Hardened audit profiles for strict compliance. |
| 104 | `security.key_vault` | security | `sylion/security/key_vault.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✗ | - | Secure key vault for secrets and encryption keys. |
| 105 | `security.phantom_wrapper` | security | `sylion/security/phantom_wrapper.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Phantom/sandbox execution wrapper for untrusted code paths. |
| 106 | `security.policy_engine` | security | `sylion/security/policy_engine.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Policy evaluation engine. Enforces security policies at runtime. |
| 107 | `security.profile_swap` | security | `sylion/security/profile_swap.py` | `sylion/api/profile_swap_routes.py` | `/api/v1/profile-swaps` | ✗ | - | Security profile swap and transition management. |
| 108 | `security.profiles` | security | `sylion/security/profiles.py` | `sylion/api/security_profiles_routes.py` | `/api/v1/security-profiles` | ✗ | - | Security profile definitions for dev, test, staging, prod environments. |
| 109 | `security.secret_provider` | security | `sylion/security/secret_provider.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Secret management with rotation, vault integration, and access audit. |
| 110 | `security.security_audit` | security | `sylion/security/security_audit.py` | `sylion/api/security_audit_routes.py` | `/api/v1/security-audit` | ✗ | - | Security audit engine for comprehensive assessment. |
| 111 | `security.security_profiles` | security | `sylion/security/security_profiles.py` | `sylion/api/security_profiles_routes.py` | `/api/v1/security-profiles` | ✗ | - | Security profiles management with hardened configs. |
| 112 | `security.session_broker` | security | `sylion/security/session_broker.py` | `sylion/api/security_routes.py` | `/api/v1/security` | ✓ | core.event_bus | Session management with timeout, rotation, and concurrent limits. |
| 113 | `skills.demand_signal` | skills | `sylion/skills/demand_signal.py` | `sylion/api/skills_routes.py` | `/api/v1/skills` | ✗ | core.event_bus | Analyzes skill usage patterns and generates demand signals. |
| 114 | `skills.executor` | skills | `sylion/skills/executor.py` | `sylion/api/skills_routes.py` | `/api/v1/skills` | ✓ | core.event_bus | Executes skill invocations with input validation and output capture. |
| 115 | `skills.registry` | skills | `sylion/skills/registry.py` | `sylion/api/skills_routes.py` | `/api/v1/skills` | ✓ | core.event_bus | Registry of available skills with metadata and versioning. |
| 116 | `surface.console_api` | surface | `sylion/surface/console_api.py` | `sylion/api/surface_routes.py` | `/api/v1/surface` | ✓ | core.event_bus | REST API surface for console/management operations. |
| 117 | `surface.console_ui` | surface | `sylion/surface/console_ui.py` | `sylion/api/surface_routes.py` | `/api/v1/surface` | ✓ | core.event_bus | Web UI console for system monitoring and control. |
| 118 | `surface.ws_gateway` | surface | `sylion/surface/ws_gateway.py` | `sylion/api/surface_routes.py` | `/api/v1/surface` | ✓ | core.event_bus | WebSocket gateway for real-time event streaming to clients. |
| 119 | `vps.provider_manager` | vps | `sylion/vps/provider_manager.py` | `sylion/api/vps_routes.py` | `/api/v1/vps` | ✗ | - | Virtual Provider Substrate manager for compute providers. |

---

## Moduły LABORATORYJNE (nie ruszać)

Poniższe moduły to **piaskownica badawcza** — cellular stack (5G/LTE lab),
SDR (software-defined radio), VPS/container plumbing, deployer artefaktów na
urządzenia. **NIE są częścią rdzenia AEIS** i ich się w tym audycie nie rusza —
opisuję tylko funkcjonalność, bez rekomendacji i bez instrukcji obsługi.

| # | Moduł | Funkcjonalność |
|---|-------|----------------|
| 1 | `cellular.attack_vectors` | Library of known cellular attack vectors for security testing. |
| 2 | `cellular.control_plane` | Control plane message analysis and protocol fuzzing. |
| 3 | `cellular.core_network` | Core network emulation: AMF, SMF, UPF, and subscriber management. |
| 4 | `cellular.evidence_writer` | Writes cellular test evidence to EvidenceSpine with structured payloads. |
| 5 | `cellular.ran_lab` | RAN (Radio Access Network) lab emulation with gNB and UE simulation. |
| 6 | `cellular.rf_isolation` | RF isolation validation for lab environment safety compliance. |
| 7 | `cellular.ue_emulator` | User Equipment emulator with attach/detach and mobility simulation. |
| 8 | `container.docker_manager` | Docker & Kubernetes container manager. Tracks containers, images, pods and deployments. |
| 9 | `devices.artifact_deployer` | Deploys artifacts to target devices with rollback support. |
| 10 | `sdr.capture_orchestrator` | Orchestrates multi-channel RF capture with scheduling and coordination. |
| 11 | `sdr.protocol_decoder` | Protocol identification and decoding for known RF protocols. |
| 12 | `sdr.rf_safety_governor` | RF safety governor. Enforces transmission limits and compliance. |
| 13 | `sdr.sdr_gateway` | SDR hardware gateway. Manages radio interfaces and capture sessions. |
| 14 | `sdr.signal_analyzer` | Signal analysis: spectral, temporal, modulation classification. |
| 15 | `vps.provider_manager` | Virtual Provider Substrate manager for compute providers. |

Razem: **15 modułów laboratoryjnych** (cellular.* 7, sdr.* 5, vps.* 1, container.* 1, devices.artifact_deployer 1).

---

## Moduły poza Księgą (nowe)

Moduły, które **nie występują wśród 65 planowanych** w `00_BASELINE_KANON.md §2`.
Powstały jako rozszerzenia/adaptacje już po zamrożeniu kanonu lub są modułami
laboratoryjnymi (cellular/sdr/vps/container/devices), których Księga v3.5 nie opisuje.

Razem: **55 modułów poza Księgą** (z 119 wszystkich).

### aeis.*  (2)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `aeis.integration_controller` | rozszerzenie | Integration controller for external systems and APIs. |
| `aeis.self_healing_orchestrator` | rozszerzenie | Self-healing orchestration engine for AEIS. |

### cellular.*  (7)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `cellular.attack_vectors` | LAB | Library of known cellular attack vectors for security testing. |
| `cellular.control_plane` | LAB | Control plane message analysis and protocol fuzzing. |
| `cellular.core_network` | LAB | Core network emulation: AMF, SMF, UPF, and subscriber management. |
| `cellular.evidence_writer` | LAB | Writes cellular test evidence to EvidenceSpine with structured payloads. |
| `cellular.ran_lab` | LAB | RAN (Radio Access Network) lab emulation with gNB and UE simulation. |
| `cellular.rf_isolation` | LAB | RF isolation validation for lab environment safety compliance. |
| `cellular.ue_emulator` | LAB | User Equipment emulator with attach/detach and mobility simulation. |

### cognitive.*  (6)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `cognitive.agent_runtime` | rozszerzenie | Agent runtime environment for executing autonomous agents. |
| `cognitive.chat_engine` | rozszerzenie | AI workspace chat engine for operator interaction. |
| `cognitive.feedback_collector` | rozszerzenie | Feedback collection and processing for cognitive models. |
| `cognitive.idea_vault` | rozszerzenie | Idea vault for storing and managing creative concepts. |
| `cognitive.knowledge_distiller` | rozszerzenie | Knowledge distillation from pipeline runs into canonical form. |
| `cognitive.model_registry` | rozszerzenie | Registry of AI models with versioning and metadata. |

### container.*  (1)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `container.docker_manager` | LAB | Docker & Kubernetes container manager. Tracks containers, images, pods and deployments. |

### core.*  (7)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `core.code_snapshot` | rozszerzenie | Code snapshot and versioning for bundle assemblies. |
| `core.hot_swap` | rozszerzenie | Hot-swap environment manager for zero-downtime deployments. |
| `core.integration` | rozszerzenie | Candidate build orchestration, validation pipeline, and cross-module contract drift detection. |
| `core.lifecycle_gates` | rozszerzenie | Module lifecycle gates and transition validation. |
| `core.rollback_manager` | rozszerzenie | Rollback manager for reversibility and recovery. |
| `core.version_manager` | rozszerzenie | Version manager for system-wide versioning. |
| `core.worker` | rozszerzenie | Distributed build worker registry, assignment orchestration, compact generation and build topology management. |

### devices.*  (4)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `devices.artifact_deployer` | LAB | Deploys artifacts to target devices with rollback support. |
| `devices.device_discovery` | rozszerzenie | Discovers devices on the network via multiple protocols. |
| `devices.device_registry` | rozszerzenie | Registry of known devices with capabilities and status tracking. |
| `devices.test_harness` | rozszerzenie | On-device test execution harness with result collection. |

### execution.*  (2)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `execution.capacity_planner` | rozszerzenie | Capacity planning and resource allocation. |
| `execution.deployment_orchestrator` | rozszerzenie | Deployment orchestration for pipelines and jobs. |

### governance.*  (3)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `governance.decision_boundaries` | rozszerzenie | Decision boundary enforcement for D0-D5 classifications. |
| `governance.decision_snapshot` | rozszerzenie | Decision snapshot capture and audit trail. |
| `governance.evidence_timeline` | rozszerzenie | Evidence timeline aggregation and visualization. |

### infra.*  (1)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `infra.topology_templates` | rozszerzenie | Terraform and Ansible topology template generator for distributed AEIS deployments. |

### monitoring.*  (4)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `monitoring.circuit_breaker` | rozszerzenie | Circuit breaker for fault tolerance and resilience. |
| `monitoring.model_budget` | rozszerzenie | Per-model budget tracking and enforcement. |
| `monitoring.notification_engine` | rozszerzenie | Notification engine for alerts and operator alerts. |
| `monitoring.self_healing` | rozszerzenie | Self-healing engine for automatic remediation. |

### quality.*  (1)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `quality.quality_gate_engine` | rozszerzenie | Quality gate engine for entry/exit criteria validation. |

### sdr.*  (5)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `sdr.capture_orchestrator` | LAB | Orchestrates multi-channel RF capture with scheduling and coordination. |
| `sdr.protocol_decoder` | LAB | Protocol identification and decoding for known RF protocols. |
| `sdr.rf_safety_governor` | LAB | RF safety governor. Enforces transmission limits and compliance. |
| `sdr.sdr_gateway` | LAB | SDR hardware gateway. Manages radio interfaces and capture sessions. |
| `sdr.signal_analyzer` | LAB | Signal analysis: spectral, temporal, modulation classification. |

### security.*  (10)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `security.audit_query` | rozszerzenie | Audit query engine for security log analysis. |
| `security.audit_trail_aggregator` | rozszerzenie | Audit trail aggregation across all modules. |
| `security.bootstrap_flow` | rozszerzenie | Bootstrap flow initialization for security defaults. |
| `security.evidence_signer` | rozszerzenie | Cryptographic evidence signing for tamper-proof logs. |
| `security.hardened_audit` | rozszerzenie | Hardened audit profiles for strict compliance. |
| `security.key_vault` | rozszerzenie | Secure key vault for secrets and encryption keys. |
| `security.profile_swap` | rozszerzenie | Security profile swap and transition management. |
| `security.profiles` | rozszerzenie | Security profile definitions for dev, test, staging, prod environments. |
| `security.security_audit` | rozszerzenie | Security audit engine for comprehensive assessment. |
| `security.security_profiles` | rozszerzenie | Security profiles management with hardened configs. |

### skills.*  (1)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `skills.demand_signal` | rozszerzenie | Analyzes skill usage patterns and generates demand signals. |

### vps.*  (1)

| Moduł | Kategoria | Cel |
|-------|-----------|-----|
| `vps.provider_manager` | LAB | Virtual Provider Substrate manager for compute providers. |

---

## Meta

- **Wygenerowano**: 2026-04-24 (ETAP 1 audytu)
- **Łącznie manifestów**: 119
- **W Księdze (planowane)**: 64 / 65 baseline = 98% pokrycia planu
- **Poza Księgą**: 55
- **Laboratoryjne (pomijane)**: 15
- **Źródła**:
  - `src/sylion-pipeline/sylion/contracts/manifests/*.json`
  - `src/sylion-pipeline/sylion/**/*.py`
  - `src/sylion-pipeline/sylion/api/*_routes.py`
  - `docs/system_audit/00_BASELINE_KANON.md` (sekcja 2)
