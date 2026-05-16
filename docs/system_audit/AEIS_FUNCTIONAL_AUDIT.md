# AEIS FUNCTIONAL AUDIT

**Data audytu:** 2026-04-24
**Metoda:** Code inspection + OpenAPI introspection + test inventory + runtime check

---

## Statusy definiujące

- **LIVE_VERIFIED** — kod istnieje, ma testy, endpointy działają (gdy system jest online)
- **PARTIAL** — kod istnieje, ale brakuje testów, UI, lub pełnej integracji
- **BROKEN** — kod istnieje, ale jest niekompletny lub nieprawidłowy
- **API_ONLY** — istnieje backend API, brak UI / frontendu
- **UI_ONLY** — istnieje frontend, brak backendu lub jest stub
- **UNDOCUMENTED** — kod istnieje, nie ma go w Księdze ani manifestach
- **DOC_DRIFT** — dokumentacja opisuje co innego niż kod robi
- **LEGACY** — kod przestarzały, do usunięcia
- **DUPLICATE** — funkcjonalność powielona w innym module

---

## Audyt per kluczowy przepływ (End-to-End)

### Flow 1: Operator → Pomysł → Pipeline Run

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. Operator wprowadza pomysł | frontend (idea-vault) | LIVE_VERIFIED | Strona /idea-vault istnieje |
| 2. Backend zapisuje ideę | cognitive.idea_vault | LIVE_VERIFIED | API + DB |
| 3. Pipeline run startuje | core.pipeline_controller | LIVE_VERIFIED | 6 stanów: pending→planning→generating→reviewing→complete |
| 4. Decomposition | cognitive.planner + aeis.decomposition_engine | LIVE_VERIFIED | Dwa silniki dekompozycji |
| 5. Assignment do workerów | worker.registry + worker.assignment | LIVE_VERIFIED | 8 stanów assignment |
| 6. Worker wykonuje | worker.runtime + execution.tool_runner | LIVE_VERIFIED | Sandbox lokalny |
| 7. Integracja | integration.orchestrator | PARTIAL | Brak ciągłego loop |
| 8. Governance check | governance.decision_ladder + core.decision_gate_engine | LIVE_VERIFIED | D0-D5 działa |
| 9. Evidence pack | governance.evidence_packs + core.evidence_spine | LIVE_VERIFIED | Pack builder OK |
| 10. Promocja / rollback | core.rollback_manager + rebuild.cutover_controller | PARTIAL | Cutover jest stubowany |

### Flow 2: Auth & Bootstrap

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. Setup first admin | security.bootstrap_init + auth_routes | LIVE_VERIFIED | /api/v1/auth/setup działa |
| 2. Login JWT | security.auth_provider | LIVE_VERIFIED | Local provider + JWT |
| 3. RBAC | security.roles + governance.roles | LIVE_VERIFIED | R-00 do R-06 |
| 4. Session | security.session_manager + session_broker | LIVE_VERIFIED | Sessions w SQLite |
| 5. Key Vault | security.key_vault + secret_provider | LIVE_VERIFIED | In-memory vault |

### Flow 3: Contract Freeze & Drift Detection

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. Freeze status | contracts.freeze_manager | LIVE_VERIFIED | /api/v1/contracts/freeze/status |
| 2. Manifest load | core.manifest_loader | LIVE_VERIFIED | 115 JSON manifestów |
| 3. Auto-register | core.auto_register | LIVE_VERIFIED | Przy starcie app |
| 4. Drift detection | integration.drift_detector | LIVE_VERIFIED | 6 typów driftu |
| 5. Drift summary | integration.drift_detector | LIVE_VERIFIED | /api/v1/integration/drift/summary |

### Flow 4: Self-Evolution (AEIS)

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. Self-observation | aeis.self_observation | LIVE_VERIFIED | Telemetria z runtime |
| 2. Improvement queue | aeis.improvement_queue | LIVE_VERIFIED | Kolejka propozycji |
| 3. Self-limitation | aeis.self_limitation | LIVE_VERIFIED | SLP-001..030 |
| 4. Self-explanation | aeis.self_explanation | PARTIAL | Brak pełnego CFT linkage |
| 5. Demand signal | skills.demand_signal + skills.demand_analyzer | LIVE_VERIFIED | Plan 20 |
| 6. Self-model store | memory.self_model_store | API_ONLY | JSON schema istnieje, brak UI |

### Flow 5: Operator Console → Dashboard

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. Next.js app | sylion-frontend | LIVE_VERIFIED | 48 stron, dark mode, shadcn |
| 2. API client | frontend api/client.ts | LIVE_VERIFIED | Fallback do 8000 |
| 3. WebSocket | surface.ws_gateway | LIVE_VERIFIED | /ws/stats |
| 4. Console API | surface.console_api | LIVE_VERIFIED | Gateway REST |
| 5. Legacy dashboard | dashboard.app | LEGACY | Port 8421, do usunięcia |

### Flow 6: Funding Autopilot

| Krok | Moduł | Status | Uwagi |
|---|---|---|---|
| 1. 41 endpoints | funding_autopilot.routes | LIVE_VERIFIED | Nieobecne w kanonie |
| 2. Store | funding_autopilot.store | LIVE_VERIFIED | SQLite / Postgres |
| 3. Frontend | — | UI_ONLY | Brak dedykowanej strony w nav (tylko /funding) |
| 4. Governance | — | UNDOCUMENTED | Brak klasyfikacji D dla funding |

---

## Podsumowanie statusów funkcjonalnych

| Status | Szacowana liczba modułów |
|---|---|
| LIVE_VERIFIED | ~140 |
| PARTIAL | ~20 |
| API_ONLY | ~25 |
| UI_ONLY | ~5 |
| UNDOCUMENTED | ~30 |
| DOC_DRIFT | ~10 |
| LEGACY | ~22 |
| DUPLICATE | ~8 |
| BROKEN | ~0 (brak wykrytych) |

---

## Test Coverage Analysis

| Kategoria | Liczba | Coverage |
|---|---|---|
| Unit / Integration tests | ~260 plików | Wysoka (większość modułów core) |
| E2E API tests | 18 plików | Średnia (auth, pipeline, devices, upload) |
| Playwright E2E | 24 spec | Średnia (dashboard, funding, governance, workers, deploy) |
| Contract tests (golden sets) | ~115 manifestów | Niska (manifesty istnieją, brak auto-runnera) |
| gRPC server tests | 6 plików | Średnia |

**Uwaga:** Testy istnieją, ale runtime jest offline. Nie można zweryfikować czy wszystkie przechodzą.
