# AEIS DEPENDENCY GRAPH

**Data audytu:** 2026-04-24
**Metoda:** Import analysis + manifest inspection + API prefix grouping

---

## Zależności wysokopoziomowe (warstwy)

`
Operator Console (Next.js) → Console API (FastAPI) → Surface → Core / Cognitive / Execution
                                        ↓
                              Auth / Security (RBAC, JWT, Session)
                                        ↓
                              Memory (SQLite / PostgreSQL)
                                        ↓
                              Event Bus (lokalny / NATS)
                                        ↓
                              Worker / Integration / Governance
`

## Zależności między warstwami backendu

`
Cognitive (planner, reasoner, code_agent)
    ↓
Execution (tool_runner, workflow_engine, job_runner)
    ↓
Worker (runtime, sandbox, assignment)  ←  Autoscaler
    ↓
Integration (orchestrator, drift_detector)
    ↓
Governance (decision_ladder, council_workflow, evidence_packs)
    ↓
Core (pipeline_controller, build_state, registry, event_bus)
    ↓
Memory (evidence_store, kanon_access, retrieval, self_model_store)
    ↓
DB (SQLite / PostgreSQL pool + migrations)
`

## Zależności Security

`
Every API request → Auth Middleware (app.py)
    ↓
Auth Provider (local) OR Session Broker
    ↓
RBAC Roles (R-00 .. R-06) → Policy Engine → Execution Guard
    ↓
Key Vault (in-memory) / Secret Provider
    ↓
Audit Sink (append-only) → Evidence Spine
`

## Cross-module drift (problematic deps)

| Źródło | Cel | Typ | Problem |
|---|---|---|---|
| governance.decision_gate_engine | core.decision_gate_engine | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| governance.evidence_spine | core.evidence_spine | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| governance.rollback_manager | core.rollback_manager | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| governance.policy_engine | security.policy_engine | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| efficiency.circuit_breaker | monitoring.circuit_breaker | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| root.circuit_breaker | efficiency.circuit_breaker | DUPLICATE | Ten sam kontrakt w dwóch miejscach |
| cognitive.model_performance | monitoring.model_performance | OVERLAP | Metryki modeli w dwóch warstwach |
| aeis.self_healing_orchestrator | monitoring.self_healing | OVERLAP | Self-healing w dwóch warstwach |
| surface.console_api | api.app | TIGHT-COUPLING | Console API jest częścią monolitu |
| funding_autopilot.routes | api.app | TIGHT-COUPLING | Funding jest wpięty w główny router |
| dashboard.app | api.app | TIGHT-COUPLING | Legacy dashboard łączy się z głównym API |
| openhands.sdk.llm | cognitive.llm_adapter | ALTERNATIVE | Dwa adaptery LLM |
| project_mode.engine | cognitive.planner | OVERLAP | Planowanie w dwóch miejscach |

## Cykle (loops) — czy są bezpieczne?

| Pętla | Składniki | Ocena |
|---|---|---|
| Self-Evolution Loop | aeis.self_observation → improvement_queue → self_explanation → governance | ⚠️ Brak zabezpieczenia przed nieskończoną pętlą |
| Monitoring Loop | monitoring.anomaly_detector → monitoring.self_healing → worker.runtime | ✅ Loop guard istnieje |
| Drift Detection Loop | integration.drift_detector → governance.conflict_detector → core.build_state | ✅ Finite state |
| Autoscaler Loop | worker.autoscaler → worker.monitor → worker.registry | ✅ Finite state |
