# AEIS ARCHITECTURE REALITY

**Data audytu:** 2026-04-24
**Porównanie:** Rzeczywiste warstwy vs Kanon v3.5 vs Distributed Build Architecture

---

## Warstwy kanoniczne (Księga v3.5)

Kanon przewiduje 6 warstw AEIS + 7 warstw Distributed Build:

| Warstwa kanoniczna AEIS | Powiązany plan |
|---|---|
| Cognitive | Plan 02, 03, 17 |
| Execution | Plan 04, 05, 11 |
| Security | Plan 06, 12 |
| Memory | Plan 08, 16 |
| Self-Evolution | Plan 19, 20 |
| Governance | Plan 13, 14, 15 |

| Warstwa Distributed Build | Komponenty |
|---|---|
| A. Canon Layer | Canon Manager, Księga Store, Policy Store |
| B. Planning & Decomposition | Decomposition Engine, Dependency Analyzer, Contract Freeze |
| C. Coordination | Assignment Orchestrator, Global Build State, Compact Generator |
| D. Worker | Build Worker Runtime, sandbox, patch builder |
| E. Integration & Validation | Integration Orchestrator, contract tests, drift detector |
| F. Governance | Decision Classifier, Approval Engine, Evidence Pack Builder |
| G. Operator / Control Plane | Dashboard Simple, Dashboard Pro, fleet view |

---

## Rzeczywiste warstwy systemu

### 1. Entrypoint & Bootstrap
- server.py, 
un_server.py, dashboard_server.py
- config.py, models.py
- **Rozjazd:** Brak wyraźnej separacji Canon Layer jako osobnego runtime. Config jest globalnym singletonem.

### 2. API Surface (FastAPI)
- 87 plików routes, 1170 unikalnych ścieżek OpenAPI, 250 schematów
- **Rozjazd:** Jeden monolityczny FastAPI app zamiast gateway/gRPC-web jako główny entrypoint. Console API jest częścią tego samego procesu.

### 3. Kernel / Core
- 21+ modułów w sylion/core/
- Zawiera: registry, manifest loader, contract registry, event bus (lokalny + NATS), decision gates, evidence spine, pipeline controller, build state
- **Rozjazd:** Kanon przewidywał 8 modułów Kernel — mamy 21+. decision_gate_engine, evidence_spine, 
ollback_manager zduplikowane w governance.

### 4. Cognitive Layer
- 17+ modułów w sylion/cognitive/
- **Rozjazd:** Kanon 7 modułów — mamy 17+. Dodatkowe: chat_engine, agent_runtime, hallucination_detector, idea_vault, knowledge_distiller, model_registry, feedback_collector.

### 5. Execution Layer
- 11 modułów w sylion/execution/
- **Rozjazd:** Kanon 6 modułów — mamy 11. Dodatkowe: task_scheduler, deployment_orchestrator, capacity_planner, execution_planner, tool_registry.

### 6. Security Layer
- 21 modułów w sylion/security/ + duplikaty w governance
- **Rozjazd:** Kanon 8 modułów — mamy 21. Dodatkowe: bootstrap_flow, session_manager, audit_query, audit_trail_aggregator, evidence_signer_v2, hardened_audit, profile_manager, profile_swap, security_audit.

### 7. Memory Layer
- 8 modułów w sylion/memory/
- **Rozjazd:** Kanon 7 modułów — zbliżone. Dodatkowy: book_generator. Brak wyraźnego self_model_store jako osobnego deployable.

### 8. Governance Layer
- 27 modułów w sylion/governance/
- **Rozjazd:** Kanon 7 modułów — mamy 27. Duplikaty core/governance. Dużo modułów eksperymentalnych (cascade_analyzer, conflict_resolver, council_hybrid).

### 9. Self-Evolution Layer
- 15 modułów w sylion/aeis/
- **Rozjazd:** Kanon 5 modułów — mamy 15. Dodatkowe: adaptation_engine, autonomy_controller, autonomy_stages, decomposition_engine, evidence_pack, evolution_tracker, explanation_engine, integration_controller, self_healing_orchestrator.

### 10. Worker / Coordination Layer
- 7 modułów w sylion/worker/
- **Status:** Zgodne z Distributed Build Architecture. Brak rozproszonej topologii — obecnie lokalny sqlite mode.

### 11. Integration Layer
- 2 moduły w sylion/integration/
- **Rozjazd:** Distributed Build przewidywał Integration Orchestrator + contract tests + drift — mamy tylko orchestrator i drift_detector. Brak ciągłego runnera contract tests w loop.

### 12. Operator Console / Surface
- Nowy frontend Next.js (48 stron, 30+ komponentów)
- Legacy dashboard (port 8421)
- **Rozjazd:** Dwa równoległe systemy UI. Legacy dashboard powinien być usunięty.

### 13. Eksperymentalne warstwy spoza kanonu
- **Cellular/5G Lab** (8 modułów)
- **SDR/RF Lab** (5 modułów)
- **Funding Autopilot** (6 modułów, 41 endpointów)
- **OpenHands SDK** (6 modułów)
- **Project Mode** (2 moduły)
- **Media/Stream** (5 modułów w root)

---

## Mapa rozjazdów (Drift Map)

| # | Rozjazd | Waga | Konsekwencja |
|---|---|---|---|
| 1 | Brak osobnego Canon Layer runtime | Średnia | Kanon jest plikiem PDF, nie usługą |
| 2 | Monolityczny FastAPI zamiast gateway | Średnia | Wszystkie routy w jednym procesie, brak izolacji |
| 3 | Zduplikowane moduły core/governance | Wysoka | Dryf kontraktów, niejednoznaczna odpowiedzialność |
| 4 | 2x UI (legacy + Next.js) | Wysoka | Podwójna praca utrzymaniowa, dezorientacja |
| 5 | Brak ciągłego Integration Orchestrator loop | Wysoka | Integracja jest manualna, nie ciągła |
| 6 | Worker layer lokalny (SQLite), nie rozproszony | Średnia | Nie realizuje pełnej wizji Distributed Build |
| 7 | Eksperymentalne moduły bez governance | Średnia | cellular, sdr, funding bez jasnego lifecycle |
| 8 | 719 dirty files w git | Krytyczna | Brak stabilnej linii bazowej |
| 9 | Runtime offline (martwe PID) | Krytyczna | System nie działa |
| 10 | Brak gRPC-web / tRPC gateway | Niska | REST API pełni rolę Surface API |
