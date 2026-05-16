# 01 — Inventory Periphery (SYLION AEIS v3.5)

Data: 2026-04-24
Zakres: Skills, Proto contracts, Plans 01–20, Infrastructure, Tests, Dashboard V5 Package, Devices Addon, Baseline AEIS, Runtime artifacts.
Notatka: wyniki wykluczają `.claude/worktrees/` (kopie robocze gałęzi) — brane pod uwagę są tylko ścieżki kanoniczne.

---

## 1. Skills

Lokalizacja: `src/sylion-pipeline/sylion/skills/` — implementacja **runtime Skills** (nie pliki `skill.yaml` — same manifesty skill yaml NIE istnieją w repo jako katalog katalogowy, skille są zdefiniowane jako moduły Python + rekordy w SQLite przez `registry.py` / `catalog.py`).

| Plik | Rola | Cel | Status |
|------|------|-----|--------|
| `__init__.py` | package | Export agregujący | LIVE |
| `registry.py` (14.5 KB) | Skills Registry (Plan 18) | CRUD skilli, lifecycle DRAFT → PUBLISHED → DEPRECATED | LIVE |
| `catalog.py` (13.9 KB) | Skills Catalog | Kategoria/domena/tags, browse, search, recommend, track_usage; tabela `catalog_entries`; event topics `skill.catalog.*` | LIVE |
| `executor.py` (13.1 KB) | Skills Executor (Plan 18) | Sandbox, timeout, result capture | LIVE (update 2026-04-24) |
| `runtime.py` (16.9 KB) | Skills Runtime | Wykonanie skilli w pętli, integracja z event busem | LIVE |
| `demand_signal.py` (14 KB) | Demand Signal collector (Plan 20) | Kolekcja sygnałów zapotrzebowania | LIVE |
| `demand_analyzer.py` (16.2 KB) | Demand Signal Analyzer (Plan 20) | Klastrowanie, predykcja brakujących skilli | LIVE |

Uwagi:
- **Nie znaleziono** plików `skill.yaml` / katalogu `.claude/skills/` w korzeniu repo (poza addonami). Skille są rekordami w SQLite (`sylion_aeis.db`), nie plikami yaml.
- Katalog dostępnych „Claude skills” (np. `skill-registry-implementer`, `proto-contract-designer`, `dashboard-implementation`, …) to skille Claude Code (bundle), nie moduły runtime SYLION.
- Dashboard V5 i Devices Addon dostarczają własne zestawy skilli (patrz sekcje 6 i 7).

Wniosek: warstwa Skills w runtime jest kompletna (Registry + Executor + Catalog + Runtime + Demand Signal/Analyzer = 6 komponentów domeny). Brak kanonicznego źródła plików `skill.yaml` → skille rejestrowane API-owo/seedem.

---

## 2. Proto contracts

Lokalizacje:
- **Główne (v1)**: `src/sylion-pipeline/sylion/contracts/proto/` — 16 plików `.proto` (kanon).
- **Legacy/niekontraktowe**: `src/sylion-pipeline/proto/` — 6 plików (sylion_core/cognitive/execution/aeis/governance/common).

### 2.1. Kontrakty kanoniczne `contracts/proto/*.proto`

| Plik | Domena | Services (count) | Services |
|------|--------|------------------|----------|
| `common.proto` | wspólne typy | — | (tylko messages/enums) |
| `core_v1.proto` | Kernel / Core | 7 | ModuleRegistry, EventBus, EvidenceSpine, DecisionGateEngine, ContractRegistry, BundleAssembler, ManifestLoader, EnvironmentOrchestrator |
| `cognitive_v1.proto` | Cognitive | 7 | Planner, Evaluator, Reasoner, ContextBuilder, ModelRouter, LLMAdapter, CodeAgent |
| `execution_v1.proto` | Execution | 6 | JobRunner, ToolRunner, ConnectorFramework, WorkflowEngine, AdapterBus, RetryOrchestrator |
| `memory_v1.proto` | Memory | 7 | KanonAccess, CompactLayer, EvidenceStore, Indexer, Retrieval, SelfModelStore, KBAdapter |
| `security_v1.proto` | Security | 8 | AuthProvider, BootstrapInit, SessionBroker, PolicyEngine, ExecutionGuard, SecretProvider, AuditSink, PhantomWrapper |
| `governance_v1.proto` | Governance | 7 | DecisionLadder, CouncilWorkflow, Roles, GatesRegistry, EvidenceWorkflow, PolicyRegistry, SelfExplanationValidator |
| `aeis_v1.proto` | AEIS (Self-Evolution) | 5 | SelfObservation, ImprovementQueue, SelfExplanation, SelfLimitation, SelfPreservation |
| `skills_v1.proto` | Skills (Plan 18/20) | 3 | SkillsRegistry, SkillsExecutor, DemandSignalAnalyzer |
| `surface_v1.proto` | Surface / Dashboard | 8 | ConsoleAPI, ConsoleUI, WSGateway, CommandBus, EventSourcingStore, ArtifactControl, ProcessCanvas, ReadinessEngine |
| `efficiency_v1.proto` | Efficiency | 4 | CodeBloatTracker, RuntimePerfTracker, MemoryFootprintTracker, CostEnvelopeTracker |
| `quality_v1.proto` | Quality | 3 | GoldenSetRegistry, TestRunner, RegressionDetector |
| `rebuild_v1.proto` | Rebuild | 4 | RebuildOrchestrator, LPWManager, CutoverController, CFTRunner |
| `devices_v1.proto` | Devices (addon) | 4 | DeviceDiscovery, DeviceRegistry, ArtifactDeployer, OnDeviceTestHarness |
| `sdr_v1.proto` | SDR (addon) | 5 | SDRGateway, CaptureOrchestrator, SignalAnalyzer, ProtocolDecoder, RFSafetyGovernor |
| `cellular_v1.proto` | Cellular Lab (addon) | 7 | RANLab, CoreNetwork, UEEmulator, RFIsolation, AttackVector, ControlPlane, CellularEvidence |

Łącznie `contracts/proto/*.proto`: **15 plików z usługami** (+ `common.proto`), **~85 services**, **~483 rpc methods** (surowe liczniki per file: surface 62, security 44, governance 45, cognitive 36, memory 35, execution 34, cellular 34, core 32, aeis 31, sdr 26, efficiency 25, quality 20, devices 19, skills 17, rebuild 23).

### 2.2. Proto legacy `proto/sylion_*.proto`

| Plik | Services |
|------|----------|
| `sylion_core.proto` | ModuleRegistryService, EventBusService, EvidenceSpineService |
| `sylion_cognitive.proto` | ModelRouterService, PlanService |
| `sylion_execution.proto` | WorkflowService, JobService |
| `sylion_governance.proto` | GovernanceService, CouncilService |
| `sylion_aeis.proto` | AutonomyService, ExplanationService, ImprovementService |
| `sylion_common.proto` | wspólne |

Wniosek: dwie generacje kontraktów. `contracts/proto/*.proto` = kanon v1.0 (freeze), `proto/sylion_*.proto` = starszy/szkieletowy. Ryzyko drift — wymagany audyt zgodności i/lub deprecacja legacy.

---

## 3. Plans 01–20 Coverage

Brak plików kanonicznych `PLAN_01.md` … `PLAN_20.md` w repo. Masterplan jako PDF: `SYLION_AEIS_Masterplan_v3_5.pdf` (root). Numery planów są **referencyjne** (używane w audytach i baseline) — implementacje są rozsiane po modułach `sylion-pipeline/sylion/*`.

Mapowanie plan → domena → artefakty (wg `docs/system_audit/AEIS_MODULE_INVENTORY.md`, `00_BASELINE_KANON.md`, `AEIS_ARCHITECTURE_REALITY.md`):

| Plan | Tytuł / Domena (wg Kanonu) | Artefakty w kodzie | Status |
|------|----------------------------|--------------------|--------|
| 01 | Kanon & Freeze | `contracts/proto/*` + docs/system_audit | PRESENT |
| 02 | Cognitive Routing + VPS bootstrap | `sylion/cognitive/*`, `sylion/vps/provider_manager` | PRESENT |
| 03 | Cognitive Planner / Reasoner | `sylion/cognitive/planner`, `reasoner` | PRESENT |
| 04 | Execution core | `sylion/execution/*` | PRESENT |
| 05 | Execution connectors / adapter bus | `execution/adapter_bus`, connectors | PRESENT |
| 06 | Security skeleton | `sylion/security/*` (auth, policy, guard) | PRESENT |
| 07 | (nie udokumentowany w zebranych evidence) | — | UNCLEAR |
| 08 | Memory / Kanon / Księga | `sylion/memory/*`, `kanon_access`, `evidence_store` | PRESENT |
| 09 | (nie udokumentowany) | — | UNCLEAR |
| 10 | (nie udokumentowany) | — | UNCLEAR |
| 11 | Execution workflow + retry | `execution/workflow_engine`, `retry_orchestrator` | PRESENT |
| 12 | Security PHANTOM / Efficiency gates | `security/phantom`, `efficiency/*` | PRESENT |
| 13 | Governance gates + CUT/COMP/CFT | `governance/*`, `rebuild/*` | PRESENT |
| 14 | Council workflow + Roles | `governance/council_workflow`, `roles` | PRESENT |
| 15 | Evidence workflow + Policy registry | `governance/evidence_workflow`, `policy_registry` | PRESENT |
| 16 | Compaction & Memory Protocol | `memory/compact_layer`, `indexer` | PRESENT |
| 17 | Operator Console (Surface) | `surface/*` (console_api, console_ui, ws_gateway) — patrz drift w `AEIS_DOCUMENTATION_DRIFT_MAP.md` | PARTIAL |
| 18 | Skills (Registry / Executor) | `skills/registry`, `skills/executor` | LIVE |
| 19 | Self-Evolution / Autonomy | `aeis/self_observation`, `improvement_queue`, `self_explanation`, `self_limitation`, `self_preservation` | LIVE |
| 20 | Demand Signal Analyzer | `skills/demand_signal`, `skills/demand_analyzer` | LIVE_VERIFIED |

Wniosek: brak kanonicznych dokumentów `PLAN_XX.md` per plan; jedyne źródło prawdy to PDF Masterplan + `docs/system_audit/` audyty. Plany 07/09/10 nie mają eksplicytnych odniesień w dostępnych evidence — wymaga zweryfikowania przeciw PDF.

---

## 4. Infrastructure

### 4.1. `infra/` (root)
| Plik | Rola |
|------|------|
| `hetzner_host_b.json` | Metadata instancji Hetzner (cx23, Ubuntu 24.04, ipv4 46.224.3.35, Fsn1, label `purpose=sylion-distributed`, `role=host-b`) |

Wniosek: katalog `infra/` **jest praktycznie pusty** (1 plik JSON). Cała realna infrastruktura jest w `src/sylion-pipeline/deploy/` (nie w `/infra/`).

### 4.2. `src/sylion-pipeline/` — realna infrastruktura

| Plik | Cel |
|------|-----|
| `docker-compose.yml` | baseline compose |
| `docker-compose.dev.yml` | dev stack |
| `docker-compose.full.yml` | pełny stack |
| `docker-compose.pg.yml` | Postgres override |
| `Dockerfile` | główny obraz |
| `Dockerfile.api` | obraz API |

### 4.3. `src/sylion-pipeline/deploy/`
| Plik | Cel |
|------|-----|
| `Caddyfile`, `Caddyfile.compose`, `Caddyfile.dev` | Reverse proxy Caddy (produkcja + compose + dev) |
| `grafana/` | dashboardy Grafana |
| `monitoring/prometheus.yml` | scrape config Prometheus |
| `monitoring/prometheus_alerts.yml` | reguły alertów |
| `monitoring/alertmanager.yml` | Alertmanager |
| `prometheus.yml` | (duplikat — do zgłoszenia) |
| `sylion-backup.service` / `.timer` | systemd backup |
| `sylion-dashboard.service` | systemd dashboard |

Wniosek: stos monitoringu kompletny (Prometheus + Alerts + Alertmanager + Grafana + Caddy + systemd). Katalog `infra/` w roocie jest szczątkowy — sugeruje konsolidację lub porzucenie tego folderu.

---

## 5. Tests

### 5.1. `tests/` (root repo)
7 plików, wyłącznie testy infrastrukturalne:

| Plik | Domena |
|------|--------|
| `test_autoscaler.py` | Autoscaler |
| `test_build_state.py` | Build state |
| `test_contract_freeze.py` | Contract freeze |
| `test_deploy_routes.py` | Deploy routes |
| `test_infra_topology.py` | Infra topology |
| `test_observability.py` | Observability |
| `test_worker_monitor.py` | Worker monitor |

Żadnych podkatalogów (brak `unit/` `integration/` `e2e/` `contract/` `golden/` w root `tests/`).

### 5.2. `src/sylion-pipeline/tests/`
**292 plików `test_*.py`** (płaska struktura, bez podziału na kategorie). Pokrycie po nazwach pokrywa wszystkie klasy modułów:
- Cognitive (planner, reasoner, evaluator, context_builder, model_router, llm_adapter, code_agent)
- Execution (adapter_bus, workflow_engine, retry_orchestrator, job_runner, tool_runner, connector_framework)
- Memory (kanon_access, compact_layer, evidence_store, indexer, retrieval, self_model_store, kb_adapter)
- Security (auth_provider, session_broker, policy_engine, execution_guard, secret_provider, audit_sink, phantom_wrapper, bootstrap_init)
- Governance (decision_ladder, council_workflow, roles, gates_registry, evidence_workflow, policy_registry, self_explanation_validator)
- AEIS (self_observation, improvement_queue, self_explanation, self_limitation, self_preservation, autonomy_controller, autonomy_stages)
- Surface (console_api, console_ui, ws_gateway, command_bus, event_sourcing_store, artifact_control, process_canvas, readiness_engine, ai_workspace_routes)
- Skills (registry, executor, catalog, demand_signal, demand_analyzer)
- Quality (golden_set_registry, test_runner, regression_detector)
- Efficiency (code_bloat_tracker, runtime_perf_tracker, memory_footprint_tracker, cost_envelope_tracker)
- Rebuild (rebuild_orchestrator, lpw_manager, cutover_controller, cft_runner)
- Devices/SDR/Cellular (artifact_deployer, attack_vectors, capture_orchestrator, …)
- E2E/API (test_api_all_routes, test_api_integration, test_api_smoke_v590, test_api_keys_ui_v591)

Wniosek: 292 testów w jednej płaskiej przestrzeni — brak standaryzacji kategorii. 7 testów w `tests/` root to wydzielona warstwa infra. Golden/contract testy nie są osobno wyselekcjonowane katalogowo (są wewnątrz `tests/` pipeline).

---

## 6. Dashboard V5 Package

Lokalizacja: `SYLION_Dashboard_V5_ClaudeCode_Package/` (osobna paczka w roocie, **nie zintegrowana** z `src/sylion-pipeline`).

| Zawartość | Opis |
|-----------|------|
| `README.md` | Opis overlay bundle dla Claude Code |
| `CLAUDE.md_SNIPPET.md` | Fragment do wklejenia do głównego `CLAUDE.md` |
| `PACKAGE_MANIFEST.json` | `version 5.0.0`, 7 plików, timestamp 2026-04-20 |
| `.claude/docs/DASHBOARD_FUNCTIONAL_SPEC.md` | Spec funkcjonalny v5 |
| `.claude/docs/DASHBOARD_TECHNICAL_SPEC.md` | Scalony spec techniczny v5 |
| `.claude/docs/DASHBOARD_V5_MERGE_NOTES.md` | Diff vs v4 |
| `.claude/docs/DASHBOARD_WORKPLAN_V5.md` | Plan wdrożenia + freeze list |
| `.claude/skills/dashboard-implementation/SKILL.md` | Zaktualizowany skill |

Zamrożone założenia v5:
- Dashboard = event-sourced control plane
- CommandBus = TWO_PHASE (IMMEDIATE tylko D0–D1)
- Process Canvas = Yjs + tldraw (DAG + freeform)
- Browser upload = signed HTTP / resumable multipart (nie gRPC-Web streaming)
- Readiness = deterministic primary + ML advisory
- Pełny event sourcing + snapshoty + projection rebuild
- Secrets **nigdy** w event store / Yjs / evidence

Status: **specyfikacja**, nie kod. Nie zmergowana — traktowana jako overlay do dopięcia.

---

## 7. Devices Addon

Lokalizacja: `sylion_devices_addon/` (osobny addon, kompatybilny z core v1.1+).

| Plik | Rola |
|------|------|
| `CLAUDE-DEVICES.md` | Kanoniczny opis warstwy (14 sekcji, definiuje A11 agenta, klasy M/N/O, cykl urządzenia attached→identified→provisioned→active→released) |
| `MASTERPLAN-INTEGRATION.md` | Wpięcie w masterplan: +A11, +klasy M/N/O (+16 modułów → 81), +3 artefakty Contract Freeze, +5 bram, +3 sekcje Evidence Pack, +2 typy eventów |
| `README.md` | Instrukcja instalacji, disclaimer prawny, stack (srsRAN/OAI/Open5GS/UERANSIM/USRP/LimeSDR/BladeRF) |

Skille (10 w `.claude/skills/` addonu — nie zweryfikowane fizyczną listą w tej inwentaryzacji, ale zadeklarowane w README):
- device-discovery
- device-artifact-generator
- on-device-test-loop
- sdr-capture
- sdr-signal-analysis
- hardware-evidence-writer
- cellular-lab-orchestrator (klasa O)
- rf-isolation-validator (klasa O, KRYTYCZNY)
- attack-vector-catalog (klasa O)
- control-plane-analyzer (klasa O)

Zasady twarde: TX domyślnie OFF, whitelist pasm + D3, izolacja RF (klatka Faradaya / kabel + tłumiki 60+ dB), testowy PLMN 001/01 lub 999/99, testowe IMSI, kill-switch, Council+Human Gate dla każdego TX, responsible disclosure.

Kontrakty proto dla addonu są już w kanonie: `devices_v1.proto`, `sdr_v1.proto`, `cellular_v1.proto`.

---

## 8. Baseline AEIS

Lokalizacja: `baseline aeis/`

| Plik | Opis |
|------|------|
| `AEIS_Distributed_Build_Architecture.pdf` | Architektura rozproszonego builda AEIS |
| `SYLION_AEIS_Dokumentacja_v3_5.pdf` | Dokumentacja v3.5 |
| `SYLION_AEIS_Masterplan_v3_5.pdf` | Masterplan v3.5 (duplikat tego z roota) |
| `SYLION_AEIS_v3.5_Raport_Postepow.html` | Raport postępów v3.5 |

Wniosek: snapshot dokumentacji PDF w stanie baseline v3.5 — wersja referencyjna dla wszystkich audytów. Duplikaty z rootem (`SYLION_AEIS_Masterplan_v3_5.pdf`, `AEIS_Distributed_Build_Architecture.pdf`, `SYLION_AEIS_Dokumentacja_v3_5.pdf` są zarówno tu, jak i w roocie) — ryzyko rozsynchronizowania wersji.

---

## 9. Artefakty Runtime

| Katalog | Rola | Zawartość |
|---------|------|-----------|
| `output/playwright/` | Artefakty uruchomień Playwright (smoke human-test) | 1 sesja (`20260424_073759`) |
| `evidence/` | Dowody z faz audytów | `faza0` (session_start, grep jwt, baseline pytest), `fazaA` (circular imports, build guard), `fazaB` (JWT auto-gen, B-001–B-003), `fazaC` (shutdown, pipeline async cancel, strict JSON), `fazaD` (DNS fallback), `fazaE` (summary), `fazaF` (wersjonowanie, litellm offline, memoize), `smoke_e2e.txt`, `windows_test` |
| `evidence/faza0/` … `evidence/fazaF/` | ewidencja per faza | surowe pliki .txt + zrzuty |
| `proofs/` | **PUSTY** | — |
| `results/` | Wyniki runów RAG/evaluator | 10 katalogów `run-<hash>` + `hallucinations.jsonl` (44 linie) |
| `docs/artifacts/` | **PUSTY** | — |
| `docs/production/human-test-artifacts/` | Zrzuty e2e UI | 11 PNG (sidebar, modules budget/performance/projects, pipeline reload, api_blocked_overview, 404, browser_history) |
| `docs/production/` | Human test raport | `HUMAN_TEST_REPORT.md`, `CHANGELOG_LIVE.md`, `_inventory_scan.json` |
| `docs/system_audit/` | Audyty (osobna przestrzeń — **nie modyfikowana**) | 12 plików MD (KANON, ARCHITECTURE_REALITY, FUNCTIONAL_AUDIT, MODULE_INVENTORY, MODULE_CLASSIFICATION, DEPENDENCY_GRAPH, DOCUMENTATION_DRIFT_MAP, PRODUCTION_READINESS_MAP, REPAIR_BACKLOG, RUNTIME_STARTUP, API_UI_COVERAGE_MAP, CANON_VS_REALITY) |
| `src/results/projects/project_<id>/` | Artefakty runów Cognitive (plan + deploy) | 15 projektów, każdy z `plan/` i `deploy/PLAN.md` |

Pliki runtime w roocie (istotne jako evidence startowe):
- `sylion_aeis.db` — główna baza SQLite (rejestry + skille + evidence)
- `backend.log`, `backend.err`, `backend_audit.log`, `chat_app.log`, `final_run.json`, `openapi_dump.json` — logi uruchomień
- `pdf_extract*.txt` — ekstrakty z PDFów Masterplan/Dokumentacji

Wniosek: warstwa evidence/results/output jest aktywnie produkowana (evidence per faza A–F, 10 runów RAG, 15 projektów cognitive). Katalogi `proofs/` i `docs/artifacts/` są PUSTE — ryzyko nieużywanej konwencji nazw (albo miejsc do wypełnienia w dalszych fazach audytu).

---

## Podsumowanie ogólne

- Skills runtime kompletny (6 komponentów, bez kanonicznych plików `skill.yaml`).
- Proto contracts: **15 services-bearing + 1 common** w kanonie `contracts/proto/v1`, ~85 services, ~483 RPC + legacy generacja `proto/sylion_*.proto` (potencjalny drift).
- Plans 01–20: brak kanonicznych plików `PLAN_XX.md`; 17/20 planów ma widoczne artefakty kodowe, plany 07/09/10 nie mają potwierdzonych odniesień w zebranych evidence (do weryfikacji w PDF).
- Infra w root `/infra/` praktycznie pusta (1 JSON Hetzner). Realna infrastruktura w `src/sylion-pipeline/deploy/` (Caddy + Prometheus + Alertmanager + Grafana + systemd + 4 compose + 2 Dockerfile).
- Testy: 292 w pipeline (flat) + 7 w root tests/ (infra). Brak podziału na `unit/integration/e2e/contract/golden`.
- Dashboard V5: spec osobna paczka overlay (nie zmergowana).
- Devices Addon: osobny addon z 3 dokumentami + 10 skilli; kontrakty proto już w kanonie.
- Baseline AEIS: 4 PDF/HTML + duplikaty z rootem.
- Runtime artifacts: evidence per faza, 10 runów RAG, 15 projektów cognitive, `proofs/` i `docs/artifacts/` puste.
