# SYLION AEIS v3.5 — Pełna Specyfikacja 20 Planów Wykonawczych (P01–P20)

Źródło: `pdf_extract_2.txt` (Masterplan v3.5, rozdział R6 "Execution Checklists per Plan", linie 7640–8541) oraz `pdf_extract_3.txt` (Dokumentacja zintegrowana, mapa planów 161–204).

Uwaga strukturalna: W Masterplanie plany są nazywane **P01–P20** (w Dokumentacji: Plan 01–20). Każdy plan ma: Milestone target (M0–M5), Strategy (Greenfield lub rozszerzenie), Owner Team, listę modułów, kontrakty .proto, tabele Postgres, endpointy gRPC, golden set, bramy Entry/Exit.

Pełen katalog modułów liczy ~65 klocków w 12 klasach (A–L). Każdy moduł ma owner_plan wskazujący plan wykonawczy.

---

## Plan 01 — Pipeline Core & Architektura (ACP)
- **Cel**: Zbudować nieruchome jądro SYLION — 8 modułów Kernel stanowiących kość pacierzową systemu. Bez P01 nic innego nie wystartuje.
- **Milestone**: M0 · Strategia: Greenfield · Owner: Kernel Team
- **Moduły** (klasa A — Core Kernel, 8):
  - `sylion.core.module_registry`
  - `sylion.core.manifest_loader`
  - `sylion.core.contract_registry`
  - `sylion.core.event_bus` (NATS JetStream wrapper)
  - `sylion.core.environment_orchestrator`
  - `sylion.core.bundle_assembler`
  - (+ `decision_gate_engine` rozbudowywany w P04/P12, `evidence_spine` rozbudowywany w P06)
- **Kontrakty .proto**: ModuleRegistry, ContractRegistry, EventBus, EnvironmentOrchestrator, BundleAssembler (wszystkie v1.0.0)
- **Postgres (sylion_core)**: modules, module_versions, contracts, contract_versions, events_published, environments, bundles
- **Golden set**: 100 rejestracji modułów (6 klas), 50 publikacji kontraktów SemVer, 10 pełnych bundle assembly
- **Bramy**:
  - Entry: **Contract Freeze** (7 artefaktów: manifest schema, contract registry, event taxonomy, module lifecycle, dependency rules, decision boundaries, security profile abstraction)
  - Exit: **G-KERNEL-01** — Module Registry live, Contract Registry live, Event Bus live; 8 modułów Kernel w stanie `validate`
- **Zależności**: brak (jest fundamentem); blokuje P02–P20
- **Human Gate touchpoints**: zmiana kontraktów Kernel = **D3+** (Council 4/4); zmiana mechaniki = D4/D5

---

## Plan 02 — Księga Operacyjna (KB / Kanon Access)
- **Cel**: Access Layer do Księgi Kanonicznej — jedynego źródła prawdy dla intencji, meta-zasad i Aneksów A–R. Odczyt dla D0+, zapis wyłącznie dla Council (D3+).
- **Milestone**: M1 · Strategia: Greenfield · Owner: Memory Team
- **Moduły** (klasa D — Memory):
  - `sylion.memory.kanon_access`
  - `sylion.cognitive.context_builder`
  - `sylion.memory.indexer` (pgvector)
  - `sylion.memory.retrieval` (BM25 + vector)
- **Kontrakty .proto**: KanonAccess, ContextBuilder, Retrieval (wszystkie v1.0.0). ReadDocument=D0+; WriteDocument=D3+ only
- **Postgres (sylion_memory)**: kanon_documents, kanon_versions, kanon_embeddings (vector(1536)), context_queries
- **Golden set**: 200 odczytów (Aneksy A–R), 50 prób zapisu z weryfikacją D3+, 100 wyszukiwań wektorowych, precyzja top-5 ≥ 80%
- **Bramy**:
  - Entry: evidence_spine live (P06)
  - Exit: **G-KANON-01** — Księga immutable z boku non-Council; WriteDocument odrzuca <D3+; VectorSearch p99 < 200ms
- **Zależności**: P06 (Evidence), P01 (Kernel)
- **Human Gate touchpoints**: zapis Księgi wymaga **D3+ Council 4/4**

---

## Plan 03 — MZ 3.5.5 Baseline
- **Cel**: Mechanizm przechowywania i swap aktywnego baseline'u MZ 3.5.5 (Meta-Zasady). Kluczowa reguła: "Baseline swap" bez zmiany architektury; dokładnie jeden aktywny wskaźnik.
- **Milestone**: M0→M1 · Strategia: Greenfield · Owner: Cognitive/Memory Team
- **Moduły**:
  - `sylion.memory.self_model_store`
- **Kontrakty .proto**: BaselineStore v1.0.0 — GetBaseline (D0+), ProposeNewBaseline (D2+), SwapBaseline (D4+, Council 4/4), ListBaselineVersions
- **Postgres (sylion_memory)**: mz_baselines, mz_versions, mz_active_pointer (singleton id=1)
- **Golden set**: 10 baseline swapów w sandboxie (propozycja→vote→swap→weryfikacja), 100% w Evidence Spine
- **Bramy**:
  - Entry: module_registry live, Evidence Spine dostępny
  - Exit: **G-MZ-01** — swap mechanism live; SwapBaseline wymaga Council 4/4; dokładnie jeden aktywny wskaźnik
- **Zależności**: P01, P06
- **Human Gate touchpoints**: SwapBaseline = **D4+ Council 4/4**

---

## Plan 04 — Drabina D0–D5 (Decision Ladder)
- **Cel**: Silnik klasyfikacji decyzji D0–D5 — fundament governance. Każda decyzja klasyfikowana i przeprowadzana przez odpowiednią bramę. ClassifyDecision i EvaluateGate są wywoływane przez wszystkie inne moduły → krytyczna ścieżka.
- **Milestone**: M1 · Strategia: Greenfield · Owner: Governance Team
- **Moduły**:
  - `sylion.governance.decision_ladder`
  - `sylion.core.decision_gate_engine`
- **Kontrakty .proto**: DecisionLadder v1.0.0 — ClassifyDecision, EvaluateGate, RegisterGate, ListGates, GetDecisionHistory
- **Postgres (sylion_governance)**: decisions, decision_classifications, gate_evaluations
- **Golden set**: 100 decyzji klasyfikowanych z dokładnością ≥ 95%; min. 10 przypadków per klasa D0–D5; D4/D5 zawsze wymaga Council 4/4
- **Bramy**:
  - Entry: event_bus live, module_registry live
  - Exit: **G-GOV-01** — drabina D0–D5 end-to-end; ClassifyDecision ≥ 95% accuracy
- **Zależności**: P01
- **Human Gate touchpoints**: **cała drabina jest mechanizmem Human Gate** — D3+ wymaga Council, D4/D5 wymaga Human; security_profile jako field manifestu i gate evaluator param (R0.7 propozycja #3)

---

## Plan 05 — Council 4/4
- **Cel**: Mechanizm 4-osobowego gremium decyzyjnego dla wszystkich decyzji D3+. Cykl: propose → vote → quorum → finalize z pełnym audytem.
- **Milestone**: M1 · Strategia: Greenfield · Owner: Governance Team
- **Moduły**:
  - `sylion.governance.council_workflow`
  - `sylion.governance.roles`
- **Kontrakty .proto**: CouncilWorkflow, Roles (v1.0.0)
- **Postgres**: councils, council_members, council_sessions, votes, quorum_records
- **Golden set**: 20 end-to-end Council flows, 10 odrzuceń przy braku kworum, **10 przypadków D4+ z weryfikacją Human Gate**
- **Bramy**:
  - Entry: G-GOV-01 zdane
  - Exit: **G-COUNCIL-01** — Council 4/4 workflow live; kworum weryfikowane przed finalizacją D3+
- **Zależności**: P04
- **Human Gate touchpoints**: **bezpośrednio** — Council 4/4 to główny mechanizm Human Gate dla D3+; D4+ wymaga weryfikacji Human

---

## Plan 06 — Evidence Pack / Evidence Spine
- **Cel**: Append-only log Ed25519 z replay. Każda decyzja, zmiana modułu i przejście przez bramę zostawia dowód. Audytowalność jest warunkiem autonomii AEIS (P19).
- **Milestone**: M1 · Strategia: Greenfield · Owner: Governance/Memory Team
- **Moduły**:
  - `sylion.governance.evidence_workflow`
  - `sylion.memory.evidence_store`
  - `sylion.core.evidence_spine`
- **Kontrakty .proto**: EvidenceWorkflow, EvidenceStore (v1.0.0); DeletePack tylko D5
- **Postgres**: evidence_packs, evidence_events, signatures (Ed25519)
- **Golden set**: 100 decyzji z kompletem evidence packs, 100% replay, odrzucenie paczek bez podpisu
- **Bramy**:
  - Entry: G-COUNCIL-01 zdane, audit_sink live
  - Exit: **G-EVIDENCE-01** — Evidence Spine live; każda D2+ ma pack; 100% replay; podpisy weryfikowalne
- **Zależności**: P05, P09 (audit_sink)
- **Human Gate touchpoints**: DeletePack = **D5 only** (fundament)

---

## Plan 07 — Workflowy 7 Działów (Execution) ⚠️ GŁĘBOKA ANALIZA
- **Cel**: Warstwa wykonawcza SYLION — silnik workflow, runner narzędzi, framework konektorów, adapter bus. 7 działów operacyjnych (DevOps, Analytics, Product, Security, Finance, Legal, Customer Success) otrzymuje dedykowane workflowy. Retry Orchestrator zapewnia odporność.
- **Milestone**: M2 · Strategia: Greenfield · Owner: Execution Team
- **Moduły** (klasa C — Execution, 6 modułów, wszystkie owner_plan=P07):
  - `sylion.execution.workflow_engine` — DAG-based definicja i wykonanie przepływów
  - `sylion.execution.tool_runner` — uruchamianie narzędzi z izolacją i audytem
  - `sylion.execution.connector_framework` — rejestracja i wywołanie external konektorów
  - `sylion.execution.job_runner` — zadania batch i cron
  - `sylion.execution.adapter_bus` — magistrala adapterów dla integracji zewnętrznych
  - `sylion.execution.retry_orchestrator` — at-least-once + exponential backoff + dead-letter
- **Kontrakty .proto do napisania** (3 minimalne):
  1. `WorkflowEngine.proto v1.0.0` — DefineWorkflow, StartWorkflow, GetWorkflowStatus, CompleteStep, AbortWorkflow
  2. `ToolRunner.proto v1.0.0` — RegisterTool, InvokeTool, GetToolResult, ListTools
  3. `ConnectorFramework.proto v1.0.0` — RegisterConnector, CallConnector, GetConnectorHealth, ListConnectors
  - (Spec wymienia tylko 3 proto; kontrakty dla job_runner, adapter_bus, retry_orchestrator nie mają jawnych .proto — prawdopodobnie dziedziczą z WorkflowEngine / ToolRunner lub są wewnętrzne)
- **Postgres (sylion_execution)**: workflows, workflow_instances, tool_invocations, connector_registrations
- **Kluczowe endpointy gRPC**: WorkflowEngine.StartWorkflow, WorkflowEngine.CompleteStep, ToolRunner.InvokeTool, ConnectorFramework.RegisterConnector
- **Golden set**: 100 instancji workflow (min 10 per dział), end-to-end testy dla 7 przepływów działowych, weryfikacja retry przy symulowanym błędzie konektora
- **Bramy**:
  - Entry: G-EVIDENCE-01 zdane, event_bus live
  - Exit: **G-EXEC-01** — silnik workflow live; 7 przepływów działowych end-to-end zdane; ToolRunner emituje do Evidence Spine
- **Zależności**: P01 (event_bus), P06 (evidence). P07 blokuje P08 (Cognitive), P10 (Efficiency), P15 (Multi-team adapter).
- **Rozszerzenia**: P15 dodaje do workflow_engine task routing per rola efficiency (P07 + P15)
- **Estymacja**: M2 = sprint 5-8, miesiąc 3-5 (milestone M2 obejmuje Cognitive + Execution + Efficiency + Quality równolegle — patrz R5.3)
- **Human Gate touchpoints**: każde wywołanie zewnętrzne przez konektor **przechodzi przez Execution Guard** (R0.6 — klasa C definicja); zmiany konektorów = D2 (peryferyjne)

---

## Plan 08 — Multi-Agent Coordination (Cognitive)
- **Cel**: Warstwa kognitywna — planer, ewaluator, reasoner, code agent, Model Router (LiteLLM) dla wymienialności LLM.
- **Milestone**: M2 · Strategia: Greenfield · Owner: Cognitive Team
- **Moduły** (klasa B, 7):
  - `sylion.cognitive.planner`
  - `sylion.cognitive.evaluator`
  - `sylion.cognitive.reasoner` (CoT + ToT)
  - `sylion.cognitive.code_agent`
  - `sylion.cognitive.model_router`
  - `sylion.cognitive.llm_adapter`
  - (+ context_builder z P02)
- **Kontrakty .proto**: Planner, Evaluator, Reasoner, ModelRouter (v1.0.0)
- **Postgres (sylion_cognitive)**: plans, plan_steps, reasoning_traces, model_invocations, llm_costs
- **Golden set**: 100 end-to-end egzekucji, 5 typów zadań (code, analysis, planning, summarization, reasoning), weryfikacja fallback Model Router
- **Bramy**:
  - Entry: G-EXEC-01 zdane, fake LLM adapter dostępny
  - Exit: **G-COG-01** — Planner + Evaluator + Reasoner + Model Router w `stable`; ślady w Evidence; koszty LLM rejestrowane
- **Zależności**: P07, P01, P06
- **Human Gate touchpoints**: warstwa Cognitive stubowana na fake-LLM adapter do czasu gotowości Model Routera (R0.6)

---

## Plan 09 — Security Skeleton + Red/Blue Team ⚠️ GŁĘBOKA ANALIZA
- **Cel**: Wdrożenie **wszystkich 8 modułów security od dnia 1** w profilu dev-light. Kluczowa obserwacja: ten sam kontrakt .proto obowiązuje we wszystkich profilach — podmiana implementacji (dev-light → prod-strict) **nie zmienia architektury**. M5 kończy hardening: Keycloak OIDC, PHANTOM + gVisor, HashiCorp Vault, Ed25519 audit chain.
- **Milestone**: M0 (skeleton) + M5 (full hardening) · Strategia: Greenfield · Owner: Security Team
- **Moduły** (klasa F — Security, 8; wszystkie owner_plan=P09):
  1. `sylion.security.auth_provider` — M0: local token bootstrap → M5: Keycloak OIDC
  2. `sylion.security.bootstrap_init` — M0: plaintext admin init → M5: secure seed + hardware token (**oddzielny moduł wg R0.7 propozycja #4**, nie część app shell)
  3. `sylion.security.session_broker` — M0: in-memory → M5: Redis + JWT + refresh token rotation
  4. `sylion.security.policy_engine` — M0: allow-list basic → M5: OPA + fine-grained
  5. `sylion.security.execution_guard` — M0: subprocess isolation → M5: PHANTOM + gVisor/Firecracker
  6. `sylion.security.secret_provider` — M0: .env + local file → M5: HashiCorp Vault
  7. `sylion.security.audit_sink` — M0: append log → M5: Ed25519 signed chain (integracja z P06 w M6)
  8. `sylion.security.phantom_wrapper` — M0: skeleton (light sandbox) → M5: full PHANTOM strict
- **Kontrakty .proto do napisania** (8 — jeden per moduł):
  1. `AuthProvider.proto v1.0.0` — Authenticate, ValidateToken, RevokeToken, RefreshToken
  2. `BootstrapInit.proto v1.0.0` — InitializeSystem, GetBootstrapStatus, ResetBootstrap (D5)
  3. `SessionBroker.proto v1.0.0` — CreateSession, GetSession, InvalidateSession, ListActiveSessions
  4. `PolicyEngine.proto v1.0.0` — EnforcePolicy, AddPolicy, RemovePolicy (Council), ListPolicies
  5. `ExecutionGuard.proto v1.0.0` — GuardExecution, GetGuardStatus, SetGuardProfile
  6. `SecretProvider.proto v1.0.0` — GetSecret, SetSecret (D3+), RotateSecret, ListSecretIds
  7. `AuditSink.proto v1.0.0` — AppendAudit, QueryAuditLog, VerifyAuditChain
  8. `PhantomWrapper.proto v1.0.0` — RunInPhantom, GetPhantomResult, AbortPhantom
- **Postgres (sylion_security)**: auth_tokens, sessions, policies, secrets, audit_log (UUIDv7, sig_hex), phantom_runs
- **Kluczowe endpointy gRPC**: Authenticate, CreateSession, EnforcePolicy, GuardExecution, GetSecret, AppendAudit, RunInPhantom
- **Golden set**:
  - M0: 100 bootstrap flows (zimny start + reinit), 1000 walidacji tokenów z 0% false positive
  - M5: 100 OIDC flows (Keycloak), 1000 egzekucji PHANTOM, **pen-test: 0 krytycznych podatności**
- **Bramy**:
  - Entry: Contract Freeze (7 artefaktów)
  - Exit M0: **G-SEC-SKELETON-01** — 8 modułów dev-light `validate`; bootstrap flow operacyjny
  - Exit M5: **G-SEC-FULL-01 + G-PENTEST-01** — wszystkie moduły prod-strict; pen-test bez krytycznych podatności
- **Zależności**: Contract Freeze (M0), P06 (w M5 audit_sink integruje się z Evidence Spine)
- **Rozszerzenia**: P06+P09 (audit_sink + evidence_spine integration)
- **Estymacja**: rozciągnięta M0→M5 (9+ miesięcy); profile: dev-light → test-light → staging-strict → prod-strict
- **Human Gate touchpoints**:
  - `RemovePolicy` = **Council** (D3+)
  - `SetSecret` = **D3+**
  - `ResetBootstrap` = **D5 only**
  - R0.7 propozycja #3: security_profile jako parametr gate evaluatora
  - R8.4: **Autonomy wymaga Security** — żaden etap Autonomy Rollout > 1 bez prod-strict

---

## Plan 10 — Cztery Wymiary Efficiency ⚠️ GŁĘBOKA ANALIZA
- **Cel**: Implementacja meta-zasady **"Efficiency by Default"** (v3.3) przez 4 dedykowane moduły pomiarowe. Każdy bundle musi zmieścić się w budżecie zanim trafi na produkcję. Bramy G-EFF-01..04 **blokują deployment** poza budżetem.
- **Milestone**: M2 · Strategia: Greenfield · Owner: Efficiency Team
- **Moduły** (klasa G, 4 moduły, wszystkie owner_plan=P10):
  1. `sylion.efficiency.code_bloat` — analiza rozrostu kodu, dependency graph, dead code detection
  2. `sylion.efficiency.runtime_perf` — latencja i throughput per RPC; SLO tracking (p50/p95/p99)
  3. `sylion.efficiency.memory_footprint` — heap, GC pressure, RSS per moduł
  4. `sylion.efficiency.cost_envelope` — budżet tokenów + kosztów API (USD)
- **Kontrakty .proto do napisania** (4):
  1. `CodeBloatMeter.proto v1.0.0` — MeasureBloat, GetBloatReport, SetBloatBudget, AlertOnBloat
  2. `RuntimePerfMeter.proto v1.0.0` — MeasureRuntime, GetPerfReport, SetSLO, CheckSLOBreach
  3. `MemoryFootprintMeter.proto v1.0.0` — MeasureMemory, GetMemoryReport, SetMemoryBudget
  4. `CostEnvelopeMeter.proto v1.0.0` — MeasureCost, GetCostReport, SetCostBudget, CheckBudget
- **Postgres (sylion_efficiency)**: code_metrics, runtime_metrics, memory_metrics, cost_metrics, efficiency_budgets
- **Kluczowe endpointy gRPC**: MeasureBloat, MeasureRuntime, MeasureMemory, MeasureCost, CheckBudget
- **Golden set**: 500 bundle'ów zmierzonych w 4 wymiarach; **100% enforcement budżetów** — żaden bundle poza budżetem nie deployuje; pokrycie każdej klasy A–K
- **Bramy**:
  - Entry: G-COG-01 zdane, evidence_spine live
  - Exit: **G-EFF-01** (code bloat) + **G-EFF-02** (runtime) + **G-EFF-03** (memory) + **G-EFF-04** (cost) — 4 bramy aktywne; deployment pipeline blokowany przy przekroczeniu budżetu
- **Zależności**: P08 (Cognitive — żeby mierzyć LLM cost), P06 (Evidence), P01 (Bundle assembler)
- **Artefakty docelowe dodatkowo**: Aneks L (Code Efficiency Report — JSON schema + golden anti-patterns LLM bloat), Aneks N (Performance/Memory/Cost baselines)
- **Estymacja**: M2 — sprint 5-8
- **Human Gate touchpoints**: każdy bundle przekraczający budżet **blokowany w pipeline**; override wymaga Council (w P12 przez `OverrideGate` D3+)

---

## Plan 11 — Testowanie Kanoniczne + Golden Set
- **Cel**: Infrastruktura testów kanonicznych — złoty zestaw jako źródło prawdy dla regresji. Test Runner egzekwuje w CI; Regression Detector triggeruje auto-rollback.
- **Milestone**: M2 · Strategia: Greenfield · Owner: Quality Team
- **Moduły** (klasa L, 3):
  - `sylion.quality.golden_set_registry`
  - `sylion.quality.test_runner`
  - `sylion.quality.regression_detector`
- **Kontrakty .proto**: GoldenSet, TestRunner, RegressionDetector (v1.0.0); UpdateGoldenSet=D2+
- **Postgres (sylion_quality)**: golden_sets, test_cases, test_runs, regression_alerts
- **Golden set (meta)**: 500 test cases pokrywających wszystkie moduły M2; auto-rollback test
- **Bramy**:
  - Entry: G-EFF-01..04 zdane
  - Exit: **G-QUALITY-01** — Registry ≥ 500 cases; Test Runner w CI/CD; Regression Detector aktywny
- **Zależności**: P10, P06
- **Human Gate touchpoints**: UpdateGoldenSet = D2+

---

## Plan 12 — Bramy G-* (Gates Registry)
- **Cel**: Pełny rejestr bram G-* + rozszerzenie Decision Gate Engine (P04) o rejestrację/ewaluację dowolnych bram. Bramy blokują pipeline, deployment, milestone transitions.
- **Milestone**: M2 · Strategia: Greenfield · Owner: Governance Team
- **Moduły**:
  - `sylion.governance.gates_registry`
  - `sylion.core.decision_gate_engine` (rozszerzenie P04+P12)
- **Kontrakty .proto**: GatesRegistry v1.0.0 — RegisterGate, EvaluateAllGates, GetGateStatus, GetGateHistory, **OverrideGate (Council 4/4)**
- **Postgres**: gates, gate_evaluations, gate_history, gate_overrides
- **Golden set**: 30 bram (G-KERNEL/GOV/SEC/EFF/PERF/MEM/COST), 1000 ewaluacji, 10 override'ów z Council 4/4
- **Bramy**:
  - Entry: G-QUALITY-01 zdane, P04 live
  - Exit: G-EFF-01..04 + G-PERF-01 + G-MEM-01 + G-COST-01 aktywne
- **Zależności**: P04, P11
- **Human Gate touchpoints**: **OverrideGate = Council 4/4** (D3+)

---

## Plan 13 — Rejestr Bram + Audit
- **Cel**: Rozszerzenie P12 o pełny audit trail każdej ewaluacji bramy. Każde EvaluateGate → zdarzenie w Evidence Spine. Możliwość rekonstrukcji historii decyzji bramowych.
- **Milestone**: M2 · Strategia: Greenfield (rozszerzenie P12) · Owner: Governance Team
- **Moduły**:
  - `sylion.governance.gates_registry` (P12+P13)
  - `sylion.core.evidence_spine` (integracja zdarzeń bramowych)
- **Kontrakty**: osadzenie w istniejących proto — `gate_event_class` w event taxonomy
- **Postgres**: gate_audit_log (UUIDv7, full_context_jsonb, evidence_pack_id)
- **Golden set**: 1000 ewaluacji w gate_audit_log; każde zdarzenie ma evidence pack; replay 100 losowych
- **Bramy**:
  - Entry: G-EFF-01..04, G-EVIDENCE-01
  - Exit: **G-GATE-AUDIT-01** — 100% ewaluacji audytowanych
- **Zależności**: P12, P06
- **Human Gate touchpoints**: via P12 (OverrideGate Council)

---

## Plan 14 — Greenfield Rebuild Orchestration
- **Cel**: Implementacja meta-zasady **"Rebuildability over Lineage"** (v3.0). Orchestrator zarządza shadow → dual → cutover; LPW Manager chroni legacy 7 dni; CFT Runner weryfikuje fidelity.
- **Milestone**: M3 · Strategia: Greenfield · Owner: Rebuildability Team
- **Moduły** (klasa K, 4):
  - `sylion.rebuild.orchestrator`
  - `sylion.rebuild.lpw_manager` (Legacy Preservation Window 7 dni)
  - `sylion.rebuild.cutover_controller` (state machine)
  - `sylion.rebuild.cft_runner` (Compact Fidelity Test — współdzielony z P16)
- **Kontrakty .proto**: RebuildOrchestrator, LPWManager (ExtendLPW=Council D4), CutoverController, CFTRunner
- **Postgres (sylion_rebuild)**: rebuild_jobs, lpw_records, cutover_states, cft_runs, cft_results
- **Golden set**: 10 rebuildów end-to-end z CFT fidelity ≥ 99%; 5 testów rollback; LPW 7 dni
- **Bramy**:
  - Entry: G-GATE-AUDIT-01, G-QUALITY-01
  - Exit: **G-REBUILD-01**
- **Zależności**: P13, P11
- **Artefakty dodatkowe**: Aneks G (Artefakty rebuild JSON/YAML), Aneks H (Reversibility Protocol), Aneks I (Compact Fidelity Test schemat)
- **Human Gate touchpoints**: `ExtendLPW = Council D4`; cutover transitions mogą wymagać Human zatwierdzenia w strict profilu

---

## Plan 15 — Multi-Team + 4 Role Efficiency
- **Cel**: Rozszerzenie Roles (P05) o 4 role efficiency (Code, Runtime, Memory, Cost) z precyzyjnymi uprawnieniami per wymiar. Workflow Engine dostaje adapter do task routing per rola.
- **Milestone**: M2 · Strategia: Greenfield (rozszerzenie P05) · Owner: Governance Team
- **Moduły**:
  - `sylion.governance.roles` (P05+P15)
  - `sylion.execution.workflow_engine` (P07+P15) — task routing per rola
- **Kontrakty .proto**: Roles.proto v1.0.0 rozszerzenie
- **Postgres**: roles, role_assignments, role_efficiency_actions
- **Golden set**: 4 role × 10 akcji = 40 audytowanych; każda rola dostęp tylko do swojego wymiaru
- **Bramy**:
  - Entry: G-EXEC-01, G-COG-01, P05 live
  - Exit: **G-ROLES-01**
- **Zależności**: P05, P07, P10
- **Human Gate touchpoints**: role są bazą uprawnień do D-akcji; każda akcja audytowana

---

## Plan 16 — Compaction & Memory Protocol
- **Cel**: Warstwa kompakcji kontekstu — redukcja rozmiaru przy zachowaniu fidelity (meta-zasada Reversibility & Fidelity v3.1). Kluczowa miara: **fidelity score ≥ 0.99**.
- **Milestone**: M3 · Strategia: Greenfield · Owner: Memory Team
- **Moduły**:
  - `sylion.memory.compact_layer`
  - `sylion.rebuild.cft_runner` (współdzielony z P14)
- **Kontrakty .proto**: CompactLayer — CompactContext, DecompactContext, VerifyFidelity, GetCompactionStatus, ListCompactions
- **Postgres**: compactions, compaction_versions, cft_verifications
- **Golden set**: 100 kompakcji z CFT 100% pass (fidelity ≥ 0.99); 3 algorytmy; DecompactContext bez utraty artefaktów semantycznych
- **Bramy**:
  - Entry: G-REBUILD-01, CFT Runner live (P14)
  - Exit: **G-COMPACT-01** (fidelity ≥ 99%) + **G-CFT-01**
- **Zależności**: P14
- **Artefakty dodatkowe**: canon_compact.md, triggery 24h + pre-D3 + pre-bundle, dwupoziomowy compact (agent + operator)
- **Human Gate touchpoints**: triggery pre-D3 (przed eskalacją decyzji wysokiej klasy)

---

## Plan 17 — Operator Console Enterprise (UI/UX)
- **Cel**: Enterprise interface dla operatorów SYLION. Next.js 14 + tRPC + shadcn/ui. Console API = gRPC-web/tRPC gateway; WS Gateway = real-time push.
- **Milestone**: M3 · Strategia: Greenfield · Owner: Surface Team
- **Moduły** (klasa J, 3):
  - `sylion.surface.console_api`
  - `sylion.surface.console_ui`
  - `sylion.surface.ws_gateway`
- **Kontrakty .proto**: ConsoleAPI (GetDashboard, ListDecisions, GetModuleStatus, ListActiveGates, **CastVote proxy**, GetAuditLog), WSGateway (Subscribe, Unsubscribe, PushEvent)
- **Postgres (sylion_surface)**: console_sessions, console_actions, ws_subscriptions
- **Golden set**: 1000 akcji UI, 100 concurrent WS klientów bez degradacji, e2e: operator widzi decyzję Council i głosuje
- **Bramy**:
  - Entry: G-REBUILD-01, G-COUNCIL-01
  - Exit: **G-SURFACE-01**
- **Zależności**: P14, P05, P17 scope obejmuje 8 paneli operacyjnych
- **Artefakty dodatkowe**: Aneks K (Design tokens + WebSocket schemas), Design system, RBAC × widoki, mockupy ASCII, accessibility WCAG AA
- **Human Gate touchpoints**: **Console to UI dla Human Gate** — CastVote proxy jest kluczowym touchpointem; operator widzi pending D3+ decisions

---

## Plan 18 — Skills & Knowledge Pipeline
- **Cel**: Rejestr skills — lifecycle DRAFT→PUBLISHED→DEPRECATED. Skills jako pierwszoklasowy artefakt z wersjonowaniem.
- **Milestone**: M4 · Strategia: Greenfield · Owner: Skills Team
- **Moduły**:
  - `sylion.skills.registry`
  - `sylion.skills.executor`
  - `sylion.memory.kb_adapter`
- **Kontrakty .proto**: SkillsRegistry (DeprecateSkill=D2+), SkillExecutor
- **Postgres (sylion_skills)**: skills, skill_versions, skill_executions, skill_metrics
- **Golden set**: 30+ skills (min 5/dział), 100 egzekucji, pełny lifecycle per skill
- **Bramy**:
  - Entry: G-COG-01, Kanon live (P02)
  - Exit: **G-SKILLS-01**
- **Zależności**: P08, P02
- **Artefakty dodatkowe**: Aneks M (Skills Catalog 30+ standardowych skilli), schemat skill.yaml, versioning
- **Human Gate touchpoints**: DeprecateSkill = **D2+**; publish skill = D2+

---

## Plan 19 — AEIS Self-Evolution Engine ⭐
- **Cel**: **Serce SYLION AEIS** — mechanizm samoewolucji pod nadzorem Kanonu. 5 modułów: Self-Observation (D0 — pomiar bez wpływu), Improvement Queue (Council triage, Human zatwierdza D2+), Self-Explanation, Self-Limitation, Self-Preservation. **Zasada: autonomia wyłącznie w granicach Kanonu**.
- **Milestone**: M4 · Strategia: Greenfield · Owner: AEIS Team
- **Moduły** (klasa H, 5):
  - `sylion.aeis.self_observation` — 100% runtime; raporty hourly; **ZERO modyfikacji (D0)**
  - `sylion.aeis.improvement_queue` — Council triażuje; Human zatwierdza D2+
  - `sylion.aeis.self_explanation` — uzasadnienia zmian zgodne z Kanonem
  - `sylion.aeis.self_limitation` — polityki ograniczające autonomię
  - `sylion.aeis.self_preservation` — detekcja zagrożeń misji; eskalacja do Council
- **Kontrakty .proto** (5): SelfObservation, ImprovementQueue, SelfExplanation, SelfLimitation, SelfPreservation
- **Postgres (sylion_aeis)**: observations, improvements, self_explanations, self_limitations, preservation_events
- **Golden set**: 1000 obserwacji (A–K), 100 improvements z Council triage, 50 self-explanacji z walidacją Kanonu, 30 polityk ograniczeń, **0 naruszeń misji**
- **Bramy**:
  - Entry: G-SKILLS-01, G-COUNCIL-01, Evidence Spine live
  - Exit: **G-AEIS-01..05** (wszystkie 5 bram)
- **Zależności**: P18, P05, P06
- **Artefakty dodatkowe**: Aneks O (AEIS Self-Model JSON Schema), Aneks Q (Self-Limitation Policies SLP-001..030), Aneks R (Self-Explanation Templates)
- **Human Gate touchpoints**: **cały plan jest framework Human Gate dla autonomii** — Architektura pełna od dnia 1; aktywność stopniowa przez **5 etapów Autonomy Rollout** (R7.1–R7.5: Observe-only → Propose-only → Sandbox → Limited prod → Full governed). Każdy improvement D2+ wymaga Human; D3+ Council 4/4

---

## Plan 20 — Skill Demand Engine
- **Cel**: Domykanie pętli samoewolucji: Demand Signal zbiera sygnały z 4 źródeł (workflow gaps, failed tool invocations, operator requests, AEIS observations), klastruje, proponuje nowe skills do Skills Registry (P18). **Ostatnie ogniwo Autonomy Rollout Stage 2 (Propose-only)**.
- **Milestone**: M4 · Strategia: Greenfield · Owner: AEIS/Skills Team
- **Moduły**:
  - `sylion.aeis.demand_signal`
  - `sylion.skills.registry` (integracja z P18)
- **Kontrakty .proto**: DemandSignal — RecordSignal, ClusterSignals, ProposeSkill, GetClusterReport, ListSignals
- **Postgres**: demand_signals, demand_clusters (centroid_embedding), skill_proposals
- **Golden set**: 4 × 100 = 400 sygnałów; 10 klastrów ≥ 80% precyzja; 5 propozycji skill z evidence pack
- **Bramy**:
  - Entry: G-AEIS-01..05, G-SKILLS-01
  - Exit: **G-AEIS-SKILL-01** — pętla Observation→Signal→Cluster→Propose end-to-end zamknięta
- **Zależności**: P19, P18
- **Artefakty dodatkowe**: Aneks P (Skill Demand Signals — schematy + protokoły generacji)
- **Human Gate touchpoints**: ProposeSkill składa propozycję do Council; każda propozycja ma evidence pack

---

## Analiza spec vs kod — P07, P09, P10

Źródła kodu sprawdzone:
- `src/sylion-pipeline/sylion/execution/` → P07
- `src/sylion-pipeline/sylion/security/` → P09
- `src/sylion-pipeline/sylion/efficiency/` → P10
- `docs/artifacts/` (01_ARCHITECTURE_SUMMARY.md, 02_MODULE_MAP.md, ...)
- `evidence/` (faza0..fazaF, smoke_e2e.txt, windows_test)

### P07 — Execution (spec = 6 modułów)

| Spec moduł | Plik w kodzie | Status |
|---|---|---|
| `execution.workflow_engine` | `workflow_engine.py` | ✅ obecny |
| `execution.tool_runner` | `tool_runner.py` | ✅ obecny |
| `execution.connector_framework` | `connector_framework.py` | ✅ obecny |
| `execution.job_runner` | `job_runner.py` | ✅ obecny |
| `execution.adapter_bus` | `adapter_bus.py` | ✅ obecny |
| `execution.retry_orchestrator` | `retry_orchestrator.py` | ✅ obecny |
| — (poza spec) | `capacity_planner.py` | ➕ dodatkowe |
| — (poza spec) | `deployment_orchestrator.py` | ➕ dodatkowe (nachodzi na Kernel `environment_orchestrator`) |
| — (poza spec) | `execution_planner.py` | ➕ dodatkowe |
| — (poza spec) | `tool_registry.py` | ➕ dodatkowe (może być artefaktem ToolRunner.RegisterTool) |

**Wniosek P07**: Wszystkie 6 modułów spec są obecne. Kod zawiera **4 dodatkowe moduły** niewymienione w P07 masterplanu. Teza użytkownika "nie znaleziono artefaktów" jest **niepoprawna** — artefakty istnieją, problem raczej w mapowaniu nazewniczym (`tool_registry` vs spec `tool_runner.RegisterTool` endpoint). Rekomendacja: sprawdzić czy `deployment_orchestrator.py` nie duplikuje funkcjonalności z `core.environment_orchestrator` (P01).

### P09 — Security (spec = 8 modułów)

| Spec moduł | Plik w kodzie | Status |
|---|---|---|
| `security.auth_provider` | `auth_provider.py` | ✅ |
| `security.bootstrap_init` | `bootstrap_init.py` + `bootstrap_flow.py` | ✅ (rozszerzone) |
| `security.session_broker` | `session_broker.py` + `session_manager.py` | ✅ (rozszerzone) |
| `security.policy_engine` | `policy_engine.py` | ✅ |
| `security.execution_guard` | `execution_guard.py` | ✅ |
| `security.secret_provider` | `secret_provider.py` + `key_vault.py` | ✅ (rozszerzone) |
| `security.audit_sink` | `audit_sink.py` + `audit_query.py` + `audit_trail_aggregator.py` + `hardened_audit.py` | ✅ (silnie rozszerzone) |
| `security.phantom_wrapper` | `phantom_wrapper.py` | ✅ |
| — (poza spec) | `evidence_signer.py`, `evidence_signer_v2.py` | ➕ (Ed25519 signing — z roadmapy M5) |
| — (poza spec) | `profile_manager.py`, `profile_swap.py`, `profiles.py`, `security_profiles.py` | ➕ (implementuje security_profile dev-light/test-light/staging-strict/prod-strict z R0.7 #3) |
| — (poza spec) | `security_audit.py` | ➕ |

**Wniosek P09**: Wszystkie 8 modułów spec są obecne i rozszerzone. Dodatkowo zaimplementowano **profile management** (zgodne z R0.7 propozycja #3 i R8.2 — 4 profile security w praktyce) oraz **Ed25519 evidence signer** (docelowy element M5). Teza użytkownika o braku artefaktów jest **błędna** — P09 ma ~20 plików implementacji.

### P10 — Efficiency (spec = 4 moduły)

| Spec moduł | Plik w kodzie | Status |
|---|---|---|
| `efficiency.code_bloat` | `code_bloat.py` | ✅ |
| `efficiency.runtime_perf` | `runtime_perf.py` | ✅ |
| `efficiency.memory_footprint` | `memory_footprint.py` | ✅ |
| `efficiency.cost_envelope` | `cost_envelope.py` | ✅ |
| — (poza spec) | `circuit_breaker.py` | ➕ dodatkowe |
| — (poza spec) | `config_drift.py` | ➕ dodatkowe |
| — (poza spec) | `cost_monitor.py` | ➕ dodatkowe (uzupełnia cost_envelope) |
| — (poza spec) | `performance_budget.py` | ➕ dodatkowe (uzupełnia runtime_perf) |

**Wniosek P10**: Wszystkie 4 moduły spec obecne + 4 dodatkowe (rozbudowujące enforcement budgets). Bramy G-EFF-01..04 wymagają bloków "deployment blocked on budget breach" — należy zweryfikować czy obecny `performance_budget.py` + `cost_monitor.py` realizują ten enforcement w pipeline.

### Ogólny werdykt dla P07/P09/P10
**Artefakty istnieją i są ponadwymiarowe względem spec.** Problem użytkownika najprawdopodobniej wynika z jednego z:
1. Oczekiwania, że moduły będą ponazywane dokładnie według nazewnictwa ze spec (`sylion.execution.tool_runner` jako katalog, nie plik)
2. Oczekiwania obecności `.proto` plików — tylko `src/sylion-pipeline/sylion/contracts/` może zawierać proto (nie sprawdzono)
3. Oczekiwania bram G-EFF-01..04, G-SEC-SKELETON-01, G-EXEC-01 zarejestrowanych w Gates Registry (P12) — to jest inna warstwa niż pliki modułów

Rekomendacja: drugi audit powinien sprawdzić `src/sylion-pipeline/sylion/contracts/` (proto) oraz manifesty (`manifest.yaml` per moduł), a także rejestrację w `core.module_registry`.

---

## Podsumowanie

### Plany z **jawnie zdefiniowanym Human Gate / Autonomy**
Wszystkie 20 planów dotyka drabiny D0–D5, ale bezpośrednie wspomnienie Human Gate / autonomy / Council 4/4 / risk-based jest w:

| Plan | Charakter Human Gate |
|---|---|
| **P02** | WriteDocument Księgi = D3+ only |
| **P03** | SwapBaseline = D4+ Council 4/4 |
| **P04** | Drabina D0–D5 = sam silnik Human Gate; security_profile param w gate evaluatorze |
| **P05** | **Council 4/4 = główny mechanizm Human Gate dla D3+**; golden set zawiera "10 D4+ z weryfikacją Human Gate" |
| **P06** | DeletePack = D5 only |
| **P09** | RemovePolicy/SecretProvider=D3+; ResetBootstrap=D5; **Autonomy wymaga Security (R8.4)** |
| **P10** | Budget breach blokuje deployment; override = Council |
| **P11** | UpdateGoldenSet = D2+ |
| **P12** | **OverrideGate = Council 4/4** (explicit) |
| **P14** | ExtendLPW = Council D4 |
| **P17** | **Console UI = UI dla Human Gate** (CastVote proxy, ListDecisions) |
| **P18** | DeprecateSkill = D2+ |
| **P19** | **Całość = framework Human Gate dla autonomii**; 5 etapów Autonomy Rollout (R7); D2+ Human, D3+ Council |
| **P20** | ProposeSkill składa do Council z evidence pack |

### Plany priorytetowe (critical path)
- **M0 blockers (sprint 1-2)**: P01 (Kernel), P09 skeleton (Security), P03 baseline
- **M1 blockers (sprint 3-4)**: P04, P05, P06, P02
- **M2 equal-priority**: P07, P08, P10, P11, P12, P13, P15
- **M3**: P14, P16, P17
- **M4**: P18, P19, P20
- **M5**: P09 full hardening

### Krytyczne zależności (critical path kolejności)
```
Contract Freeze → P01 (Kernel) → P06 (Evidence) + P04 (Ladder) + P05 (Council)
                      ↓
             P02 (Kanon) + P09 skeleton
                      ↓
             P07 (Execution) → P08 (Cognitive) → P10 (Efficiency) + P11 (Quality)
                                           ↓
             P12 (Gates) → P13 (Gate Audit) → P14 (Rebuild) → P16 (Compact) + P17 (Console)
                                                               ↓
             P18 (Skills) → P19 (AEIS Self-*) → P20 (Demand Engine)
                                                               ↓
             P09 full hardening (M5) ⇒ Autonomy Stage 3+ unlocked
```

### Blokery "bez których nic nie ruszy"
1. **Contract Freeze** — 7 artefaktów (patrz R2): manifest schema, contract registry, event taxonomy, module lifecycle, dependency rules, decision boundaries, security profile abstraction
2. **P01 Kernel** — blokuje 65 modułów
3. **P04 + P06** — każdy moduł woła ClassifyDecision i loguje do Evidence
4. **P09 skeleton** — bez security-skeleton nie da się uruchomić żadnego workflow

### Uwagi końcowe
- Masterplan nie zawiera oddzielnych sekcji "Plan 01", "Plan 02" — zamiast tego plany są zdefiniowane jako **checklisty wykonawcze** w rozdziale R6 (linie 7640–8541). Dodatkowe specyfikacje wykonawcze per plan znajdują się wg komentarza w R6.0 w plikach `v35_plan_NN.py` (nie sprawdzono obecności w repo).
- Każdy plan ma precyzyjnie zdefiniowane: moduły, kontrakty .proto (łącznie ~50+ proto files), tabele Postgres (łącznie ~60+ tabel), endpointy gRPC, golden set, Entry/Exit gates.
- Dla P07/P09/P10 kod **istnieje** w `src/sylion-pipeline/sylion/{execution,security,efficiency}/` — pierwotna teza użytkownika o braku artefaktów jest nieuzasadniona.
