# AEIS MODULE INVENTORY

**Data audytu:** 2026-04-24
**Źródło prawdy:** kod + runtime + OpenAPI introspection

---

## Podsumowanie liczbowe

| Metryka | Wartość |
|---|---|
| Wszystkie zidentyfikowane komponenty | ~280 |
| Moduły backend Python (sylion/) | ~383 pliki |
| Pliki API routes | 87 |
| Manifesty JSON | 115 |
| Proto definitions | 22 |
| Strony frontend (Next.js) | 48+ |
| Testy jednostkowe / integracyjne | ~260 |
| Testy E2E API | 18 |
| Testy Playwright | 24 |
| Skille (.claude + .agents) | 42 (21x2) |
| Kanon przewidywał (Masterplan) | ~65 modułów |
| Rzeczywista liczba modułów | ~119+ |

---

## Warstwy kanoniczne vs rzeczywiste

| Warstwa kanoniczna | Modułów w kanonie | Modułów w kodzie | Status |
|---|---|---|---|
| A. Core Kernel | 8 | 21+ | ROZSZERZONA |
| B. Cognitive | 7 | 17+ | ROZSZERZONA |
| C. Execution | 6 | 11 | ROZSZERZONA |
| D. Memory | 7 | 8 | ROZSZERZONA |
| E. Governance | 7 | 27 | ROZSZERZONA + DUPLIKATY |
| F. Security | 8 | 21 | ROZSZERZONA |
| G. Efficiency | 4 | 8 | ROZSZERZONA + DUPLIKATY |
| H. Self-Evolution | 5 | 15 | ROZSZERZONA |
| I. Skills/Demand | 3 | 6 | ROZSZERZONA |
| J. Surface | 3 | 8 | ROZSZERZONA |
| K. Rebuildability | 4 | 8 | ROZSZERZONA |
| L. Quality | 3 | 5 | ROZSZERZONA |
| M. Monitoring | 0 (w innych) | 12 | NOWA KLASA |
| N. Worker/Coordination | 0 (Distributed Build) | 7 | NOWA KLASA |
| O. Integration | 0 (Distributed Build) | 2 | NOWA KLASA |
| P. Cellular/5G | 0 | 7 | EKSPERYMENTALNA |
| Q. SDR/RF | 0 | 5 | EKSPERYMENTALNA |
| R. Devices | 0 (addon) | 4 | ROZSZERZENIE |
| S. Funding Autopilot | 0 | 6 | EKSPERYMENTALNA |
| T. Project Mode | 0 | 2 | EKSPERYMENTALNA |
| U. VPS | 1 (Plan 02) | 1 | ZGODNA |
| V. Container | 0 | 1 | ROZSZERZENIE |
| W. Infra Templates | 0 | 1 | ROZSZERZENIE |
| X. DB Layer | 0 (infra) | 4 | ZGODNA |
| Y. Pipeline State Machine | 0 (w core) | 1 | ZGODNA |
| Z. Contracts/Proto | 0 (w core) | 8 | ZGODNA |
| API Routes | 0 | 87 | ZGODNA |
| Entrypoints/Root | 0 | ~35 | ROZSZERZONE |
| Legacy Dashboard | 0 | ~22 | LEGACY |
| OpenHands SDK | 0 | 6 | EKSPERYMENTALNA |
| Frontend | 3 (Surface) | ~50 | ZGODNA |
| Skills Metadata | 30+ (Aneks M) | 21 | CZĘŚCIOWA |

---

## Anomalie inwentaryzacyjne

1. **Duplikaty funkcjonalne:**
   - circuit_breaker występuje w: root, efficiency, monitoring
   - 
ollback_manager występuje w: core, governance
   - policy_engine występuje w: security, governance
   - evidence_spine występuje w: core, governance
   - decision_gate_engine występuje w: core, governance
   - security_profiles vs profiles w security

2. **Legacy:** Dashboard (port 8421) istnieje równolegle z nowym frontendem Next.js (port 3000)

3. **Eksperymentalne poza kanonem:** cellular/, sdr/, funding_autopilot/, openhands/, project_mode/

4. **Media/Stream:** abr_controller, audio_pipeline, signaling_server, stream_monitor, stream_security — nieobecne w kanonie v3.5

5. **Infrastructure provisioning:** pixel_provision, router_provision, wireguard_provision — nieobecne w kanonie

6. **Root-level modules:** ~35 plików poza sylion/ (media, infra, finance, devops) — poza strukturą klas kanonicznych

---

## Pełna lista modułów per status

### LIVE_VERIFIED (~140 modułów)
Moduły które mają kod, testy i działające API (gdy system jest online).
Zaliczamy tu: całe Core, Cognitive, Execution, Memory, Security, Skills, Surface, Worker, Integration, Quality, Rebuild, Efficiency, Monitoring, DB, Contracts, API routes, Frontend.

### PARTIAL (~20 modułów)
- sylion.core.nats_event_bus — wymaga NATS (opcjonalne)
- sylion.core.nats_adapter — wymaga NATS
- sylion.core.nats_health — wymaga NATS
- sylion.core.environment_orchestrator — stubowany
- sylion.core.bundle_assembler — stubowany
- sylion.core.dependency_mapper — stubowany
- sylion.core.hot_swap — stubowany
- sylion.core.code_snapshot — stubowany
- sylion.cognitive.evaluation_framework — brak pełnej integracji
- sylion.cognitive.knowledge_distiller — API-only
- sylion.execution.execution_planner — częściowy
- sylion.execution.capacity_planner — API-only
- sylion.aeis.self_explanation — brak pełnego CFT linkage
- sylion.aeis.self_preservation — API-only
- sylion.aeis.explanation_engine — częściowy
- sylion.aeis.integration_controller — API-only
- sylion.governance.self_explanation_validator — częściowy
- sylion.governance.change_merger — API-only
- sylion.governance.conflict_resolver — API-only
- sylion.governance.council_hybrid — API-only
- sylion.surface.console_ui — UI-only backend
- sylion.surface.event_sourcing_store — API-only
- sylion.rebuild.cutover_automation — API-only
- sylion.memory.self_model_store — API-only

### API_ONLY (~25 modułów)
Moduły z backendem API ale bez dedykowanego UI lub frontendu.
 cellular/, sdr/, openhands/, project_mode/, funding_autopilot/ (UI minimalne), infrastructure provisioning, media/stream.

### UI_ONLY (~5 modułów)
- surface.console_ui — backend renderujący UI
- human_gate_ux — flow UX
- dashboard/* — legacy UI
- marketing/* — statyczna strona

### UNDOCUMENTED (~30 modułów)
Moduły które nie mają opisu w Księdze v3.5 ani w oficjalnych planach:
 cellular/*, sdr/*, funding_autopilot/*, openhands/*, project_mode/*, media/*, infrastructure provisioning, efficiency/config_drift, efficiency/performance_budget, efficiency/cost_monitor, quality/quality_gate_engine.

### DOC_DRIFT (~10 modułów)
- governance.decision_gate_engine — dokumentacja mówi o 1 module, kod ma 2
- governance.evidence_spine — dokumentacja mówi o core, kod ma duplikat
- governance.rollback_manager — dokumentacja mówi o core, kod ma duplikat
- security.policy_engine — dokumentacja mówi o security, governance ma duplikat
- efficiency.circuit_breaker — dokumentacja mówi o 1 module, kod ma 3

### LEGACY (~22 modułów)
- dashboard.app, dashboard.bridge, dashboard.start, dashboard.db, dashboard.jwt_auth, dashboard.rbac, dashboard.metrics, dashboard.health_check_v2, dashboard.cost_tracker, dashboard.feature_flags, dashboard.human_gate_consensus, dashboard.i18n_middleware, dashboard.rate_limit_middleware, dashboard.security_headers_middleware, dashboard.retention_cleaner, dashboard.retention_scheduler, dashboard.seed_agents, dashboard.upload_security, dashboard.correlation_id, dashboard.cascade_delete, dashboard.guards_status_runtime_patch, dashboard.book_guardian_example, dashboard.test_e2e_api
- security.evidence_signer (v1, zastąpiony przez v2)
- sylion-pipeline.dashboard_server

### DUPLICATE (~8 modułów)
- efficiency.circuit_breaker = monitoring.circuit_breaker = root circuit_breaker
- governance.decision_gate_engine = core.decision_gate_engine
- governance.evidence_spine = core.evidence_spine
- governance.rollback_manager = core.rollback_manager
- governance.policy_engine = security.policy_engine
- security.security_profiles = security.profiles
