# 03 · AUDIT L0–L2 — CANON, KERNEL RUNTIME, MEMORY & SELF-EVOLUTION

**Data:** 2026-04-24
**Framework:** `02_HUMAN_GATE_FRAMEWORK.md` (5 ról, 12 osi, 12 pytań)
**Kontekst odkrycia S1:** pipeline `execute` leci bez Human Gate — wszystkie moduły L0-L2 były audytowane w tym świetle.

Legenda:
- Stan impl.: **LIVE_VERIFIED** (endpoint odpowiada realnymi danymi), **PARTIAL** (część funkcji), **BROKEN** (niezgrzyn lub błąd), **API_ONLY** (router jest, UI brak), **UI_ONLY** (widok jest, backend brak/stub), **UNDOCUMENTED**, **DOC_DRIFT** (manifest vs kod rozjechane).
- Human Gate: **GOOD / PARTIAL / MISSING / N/A**.

Spot-check live API (token `.audit_token`):
- `GET /api/v1/core/modules` → 119 modułów, 200 OK
- `GET /api/v1/contracts` → `{"contracts": []}` (pusto — rozbieżność: 119 manifestów na dysku, 0 w API)
- `GET /api/v1/decision-snapshots` → działa (snapshoty z `gate-pipeline_step_*` outcome=`approved` confidence=1.0 **auto-approve, bez operatora**)
- `GET /api/v1/aeis/improvements` → `[]`
- `GET /api/v1/rebuild/orchestrator` → 404 (prefix `/api/v1/rebuild` istnieje ale sub-path inny)
- `GET /api/v1/memory/search` → 404 (nieznaleziony endpoint)

Status bazowy: **silnik Human Gate (`sylion/governance/human_gate.py`) istnieje ale NIE jest wpięty w `pipeline/state_machine.py` ani `core/pipeline_controller.py`.** `grep human_gate|approval|gate_check` w obu plikach = 0 trafień. To jest drift o którym mówi S1 — potwierdzony na poziomie źródła.

---

## 1 · L0 · CANON (źródło prawdy kontraktów)

**Intro.** L0 to podstawa: rejestry kontraktów, loader manifestów, wersjonowanie, protobufy. 119 manifestów `*.json` + 16 plików `.proto` + 3 silniki (contract_registry, manifest_loader, version_manager) + freeze_manager. Na poziomie artefaktów — kompletne; na poziomie **live API** — contracts list zwraca pusty zbiór, co oznacza brak wypełnienia SQLite/store z plików manifest przy bootstrapie. Human Gate **N/A** dla warstwy czystego kanonu (manifesty same z siebie decyzji nie podejmują), z wyjątkiem freeze (zamrożenie = decyzja operacyjna).

### core.contract_registry
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/core/contract_registry.py`
- **Ścieżka routera**: `src/sylion-pipeline/sylion/api/contract_routes.py`
- **API prefix**: `/api/v1/contracts` + `/api/v1/manifests`
- **Cel**: Rejestr deklarowanych kontraktów modułów + ich wersji i kompatybilności.
- **Stan impl.**: **PARTIAL** — kod + router + manifest istnieją, `GET /api/v1/contracts` zwraca jednak pustą listę, podczas gdy 119 manifestów leży na dysku. Bootstrap nie populuje store.
- **Testy**: `tests/test_contract_registry.py` (56), `test_contracts.py` — unit + integration, poziom dobry.
- **UI obecność**: `src/sylion-frontend/src/app/(app)/contracts/` — strona istnieje.
- **Human Gate**:
  1. Brak decyzji generowanych w runtime (tylko rejestr). 2. N/A. 3. N/A. 4. N/A. 5. N/A. 6. Zmiana manifestu powinna być audytowana — brak linku do evidence_spine. 7. N/A. 8. OK — nie blokuje. 9. Brak. 10. N/A. 11. N/A. 12. Brak wpięcia.
- **Ocena Human Gate**: **N/A** (warstwa deklaracyjna).
- **Luki do naprawy**: bootstrap musi ładować manifesty z dysku do store; delta manifestów (add/remove contract) powinna trafić do evidence_spine.

### core.manifest_loader
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/core/manifest_loader.py`
- **Ścieżka routera**: BRAK (expose via `contract_routes`/`manifests_router`)
- **API prefix**: `/api/v1/manifests`
- **Cel**: Ładowanie `*.json` z `contracts/manifests/` do struktury runtime.
- **Stan impl.**: **PARTIAL** — loader działa (test 9 testów), ale skoro `/contracts` jest pusty, bootstrap go nie wywołuje.
- **Testy**: `test_manifest_loader.py` (9) — unit.
- **UI obecność**: subsection strony `contracts`.
- **Human Gate**: N/A (deklaracyjne).
- **Ocena**: **N/A**.
- **Luki**: wywołaj loader przy starcie backendu; udokumentuj kolejność bootstrap.

### core.version_manager
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/core/version_manager.py`
- **Ścieżka routera**: `sylion/api/version_routes.py`
- **API prefix**: `/api/v1/versions`
- **Cel**: Zarządzanie wersjami semantycznymi modułów + compat check.
- **Stan impl.**: **LIVE_VERIFIED** (testy przechodzą) ale bez dowodu z API — endpoint nie sprawdzany.
- **Testy**: `test_version_manager.py` (55), `test_version_tracker.py` — unit + integration.
- **UI obecność**: brak dedykowanej strony, używane pośrednio w `modules`.
- **Human Gate**:
  1. Bump major/breaking change = decyzja D3+. 2. Brak klasyfikacji — samo API. 3. Brak blockingu. 4. N/A. 5. Brak autoapproval policy. 6. Brak audit trail per-bump. 7. Brak. 8. OK. 9. Brak UI polityk. 10. Brak. 11. Brak. 12. Niezwiązane z decision_gate_engine.
- **Ocena**: **MISSING**.
- **Luki**: major-bump powinien triggerować decision_gate; emit event `version.bump.major` → evidence_spine.

### core.freeze_manager
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/contracts/freeze_manager.py`
- **Ścieżka routera**: `sylion/api/freeze_routes.py`
- **API prefix**: `/api/v1` (sub-paths `/freeze/*`)
- **Cel**: Zamrażanie/odmrażanie kontraktów/modułów w określonej wersji (ochrona przed hot-swap).
- **Stan impl.**: **API_ONLY** — router jest, brak UI dedykowanego, live niezweryfikowany.
- **Testy**: brak dedykowanego (brak `test_freeze_manager.py`).
- **UI obecność**: brak osobnej strony.
- **Human Gate**:
  1. Freeze/unfreeze = decyzja operacyjna high-risk. 2. Brak klasyfikacji. 3. Brak blockingu. 4. N/A. 5. Brak. 6. Brak. 7. Brak. 8. OK. 9. Brak. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: freeze/unfreeze musi wejść w governance Human Gate (high-risk, audit trail, signature).

### core.event_bus (definicje kanonu)
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/core/event_bus.py` + `event_bus_factory.py` + `nats_event_bus.py`
- **Ścieżka routera**: `sylion/api/event_backbone_routes.py`
- **API prefix**: `/api/v1/event-backbone`
- **Cel**: Definicja magistrali zdarzeń (wersja L0 = taksonomia w `events.yaml`).
- **Stan impl.**: **LIVE_VERIFIED** (testy, NATS adapter, factory).
- **Testy**: `test_event_bus.py` (33), `test_event_bus_factory.py`, `test_nats_event_bus.py`.
- **UI obecność**: `events/` + `observability/`.
- **Human Gate**: N/A (bus kanonu).
- **Ocena**: **N/A**.
- **Luki**: brak — ale bus powinien mieć kanonicznie event `governance.human_gate.decision.*` (jest w events.yaml do weryfikacji).

### 119 manifestów `*.json`
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/contracts/manifests/*.json`
- **Ścieżka routera**: `/api/v1/manifests`
- **API prefix**: `/api/v1/manifests`
- **Cel**: Deklaracja każdego modułu (module_id, kind, decision_cls, sec_profile, depends_on).
- **Stan impl.**: **DOC_DRIFT** — 119 plików na dysku, 119 modułów w `/core/modules`, ale `/contracts` pusty. Również: w manifestach `decision_cls=D3` wskazuje że systemowo te moduły **powinny** mieć Human Gate, ale w runtime tego nie mają.
- **Testy**: `test_generate_manifests.py`.
- **UI obecność**: `modules/`, `contracts/`.
- **Human Gate**: **MISSING globally** — manifest deklaruje `decision_cls`, runtime to ignoruje.
- **Ocena**: **MISSING** (systemowo).
- **Luki**: silnik który przy akcji modułu `M` z `decision_cls=D3` wymusza przejście przez governance.

### 16 plików proto
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/contracts/proto/*.proto`
- **Cel**: Definicje gRPC dla warstw (aeis, core, cognitive, governance, memory, rebuild, …).
- **Stan impl.**: **LIVE_VERIFIED** (wygenerowane stuby w `generated/`).
- **Testy**: `test_grpc_core_server.py`, `test_grpc_aeis_server.py`.
- **UI obecność**: brak.
- **Human Gate**: N/A.
- **Ocena**: **N/A**.
- **Luki**: brak breaking-change guard wpiętego w CI (istnieje skill `buf-breaking-guardian` — nie potwierdzono użycia).

---

## 2 · L1 · KERNEL RUNTIME

**Intro.** L1 to fundament runtime: bus, lifecycle gates, hot-swap, rollback, snapshots, bundle assembler, module registry, decision gate engine, evidence spine, orchestracja środowiska, state machine pipeline'u. Testy jednostkowe mają wysokie pokrycie (15–70 testów per moduł). **Największy problem:** `decision_gate_engine` istnieje w `core/` i `governance/` jako DWIE implementacje — klasyczny drift. `pipeline/state_machine.py` i `core/pipeline_controller.py` NIE odwołują się do human_gate/approval/gate_check — potwierdzenie S1.

### core.event_bus (runtime)
- **Ścieżka kodu**: `src/sylion-pipeline/sylion/core/event_bus.py`
- **Router**: `event_backbone_routes.py`
- **Prefix**: `/api/v1/event-backbone`
- **Cel**: Publikacja/subskrypcja eventów runtime (in-memory + NATS).
- **Stan**: **LIVE_VERIFIED**.
- **Testy**: 33 unit + NATS integration.
- **UI**: `events/`, `observability/`.
- **Human Gate**: N/A (transport).
- **Ocena**: **N/A**.
- **Luki**: brak dedykowanego topic'u governance dla Human Gate potwierdzonego live.

### core.lifecycle_gates
- **Kod**: `core/lifecycle_gates.py`
- **Router**: `api/lifecycle_routes.py`
- **Prefix**: `/api/v1/lifecycle`
- **Cel**: Bramki fazowe modułów (draft → dev → stable → deprecated) z kryteriami.
- **Stan**: **LIVE_VERIFIED** (50 testów).
- **Testy**: `test_lifecycle_gates.py` (50).
- **UI**: `lifecycle/`, `gates/`.
- **Human Gate**:
  1. Przejście draft→stable = decyzja D3. 2. Brak klasyfikacji na osiach ryzyka. 3. Blocking tylko per-moduł, nie systemowo. 4. Brak batch. 5. Brak autoapproval policy. 6. Evidence spine istnieje, wpięcie niepewne. 7. Brak. 8. OK. 9. `gates/` UI jest. 10. Brak timeoutu. 11. Brak signature. 12. Nie łączy się z `governance.human_gate`.
- **Ocena**: **PARTIAL**.
- **Luki**: wpiąć gate_check w human_gate z policy risk-based; signature + timeout.

### core.hot_swap
- **Kod**: `core/hot_swap.py`
- **Router**: `api/hot_swap_routes.py`
- **Prefix**: `/api/v1/hot-swap` + alias `/api/v1/hotswap`
- **Cel**: Wymiana modułu w locie bez restartu.
- **Stan**: **LIVE_VERIFIED** (50 testów).
- **Testy**: `test_hot_swap.py` (50).
- **UI**: brak dedykowanej; prawdopodobnie w `modules/`.
- **Human Gate**:
  1. Hot-swap w prod = critical risk. 2. Brak klasyfikacji. 3. Blocking tak (swap atomowy), ale brak auto-pause na Human Gate. 4. N/A. 5. Brak. 6. Snapshot przed swap tak. 7. Brak. 8. OK. 9. Brak UI polityki. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: w prod wymagać approval; emit `core.hot_swap.requested` z ryzykiem.

### core.rollback_manager
- **Kod**: `core/rollback_manager.py`
- **Router**: `api/rollback_routes.py`
- **Prefix**: `/api/v1/rollback`
- **Cel**: Cofanie deploymentu modułu do poprzedniej wersji + snapshot.
- **Stan**: **LIVE_VERIFIED** (57 testów).
- **Testy**: `test_rollback_manager.py` (57).
- **UI**: brak dedykowanej; używane w `deploy/`.
- **Human Gate**:
  1. Rollback = decyzja high-risk (utrata stanu). 2. Brak. 3. Blocking. 4. N/A. 5. Brak. 6. Brak. 7. Brak. 8. OK. 9. Brak. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: rollback w prod musi wymagać approval + recovery window.

### core.code_snapshot
- **Kod**: `core/code_snapshot.py`
- **Router**: `api/snapshot_routes.py`
- **Prefix**: `/api/v1/snapshots`
- **Cel**: Snapshot kodu/stanu przed zmianą (używany przez rollback/hot_swap).
- **Stan**: **LIVE_VERIFIED** (67 testów).
- **Testy**: `test_code_snapshot.py` (67).
- **UI**: brak dedykowanej.
- **Human Gate**: N/A (narzędzie dla decyzji).
- **Ocena**: **N/A**.
- **Luki**: snapshot_id powinien być polem approval_token (link do evidence).

### core.bundle_assembler
- **Kod**: `core/bundle_assembler.py`
- **Router**: `api/bundle_routes.py`
- **Prefix**: `/api/v1/bundles`
- **Cel**: Składanie wielomodułowych bundli do deploymentu.
- **Stan**: **LIVE_VERIFIED** (58 testów).
- **Testy**: `test_bundle_assembler.py` (58).
- **UI**: `bundles/`.
- **Human Gate**:
  1. Złożenie bundle do prod = decyzja D3+. 2. Brak. 3. Brak. 4. Batch naturalny (bundle=batch). 5. Brak. 6. Brak. 7. Brak. 8. OK. 9. UI list tak, polityk brak. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: bundle promote → staging/prod wymaga gate.

### core.module_registry
- **Kod**: `core/module_registry.py`
- **Router**: `api/core_routes.py` (`GET /api/v1/core/modules`)
- **Prefix**: `/api/v1/core`
- **Cel**: Centralna rejestracja/odkrywanie modułów + heartbeaty.
- **Stan**: **LIVE_VERIFIED** — 119 modułów zwracanych.
- **Testy**: `test_module_registry.py` (40).
- **UI**: `modules/`.
- **Human Gate**: N/A (rejestr). Rejestracja nowego modułu mogłaby być decyzją (dev mode: off).
- **Ocena**: **N/A**.
- **Luki**: w prod — nowy moduł w registry = gate.

### core.environment_orchestrator
- **Kod**: `core/environment_orchestrator.py`
- **Router**: brak dedykowanego (wpięty w core_routes / pipeline).
- **Prefix**: `/api/v1/core` (pośrednio)
- **Cel**: Zarządzanie środowiskami (local/dev/staging/prod) i propagacją.
- **Stan**: **PARTIAL** (62 testy ale brak dedykowanego routera/UI).
- **Testy**: `test_environment_orchestrator.py` (62).
- **UI**: `environments/`.
- **Human Gate**:
  1. Promocja env staging→prod = D3+. 2. Brak. 3. Brak. 4. Brak. 5. Brak. 6. Brak. 7. Brak. 8. OK. 9. `environments/` tak. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: env-promotion gate, policy per env.

### core.decision_gate_engine
- **Kod**: `core/decision_gate_engine.py` + **druga kopia** `governance/decision_gate_engine.py` (drift)
- **Router**: `api/gates_routes.py`
- **Prefix**: `/api/v1/gates`
- **Cel**: Silnik bramek decyzyjnych (D0-D5).
- **Stan**: **BROKEN/DOC_DRIFT** — dwie implementacje w różnych warstwach, niejasne która jest aktywna; brak sygnałów `human_gate|wait_for_approval` w pipeline. Decision snapshots tworzy się **auto-approve** (`outcome=approved, confidence=1.0` bez operatora).
- **Testy**: `test_core_decision_gate_engine.py` (44), `test_decision_gate_engine.py`, `test_decision_snapshot.py`, `test_decision_snapshot_integration.py`.
- **UI**: `decisions/`, `gates/`.
- **Human Gate**:
  1. TUTAJ powinny powstawać WSZYSTKIE decyzje. 2. `decision_class` jest polem, ale brak risk/env/module axes. 3. Brak blockingu w pipeline. 4. Brak batch endpoint. 5. Auto-approve bez policy. 6. `decision-snapshots` jest, ale outcome=approved defaultowo. 7. Brak. 8. "Continuity" == bypass. 9. UI `decisions/` + `gates/` istnieje. 10. Brak. 11. Brak. 12. Nie wpięte w `pipeline/state_machine`.
- **Ocena**: **MISSING** (de facto bypass).
- **Luki**: ujednolicić do JEDNEJ implementacji; faktycznie wymuszać gate w pipeline; dodać 12 osi, batch, policy, signature, timeout.

### core.evidence_spine
- **Kod**: `core/evidence_spine.py`
- **Router**: `api/evidence_timeline_routes.py`
- **Prefix**: `/api/v1/evidence-timeline`
- **Cel**: Ciągły log dowodów decyzji/zmian (append-only).
- **Stan**: **LIVE_VERIFIED** (45 testów + dedykowany router).
- **Testy**: `test_core_evidence_spine.py` (45), `test_evidence_spine.py`, `test_evidence_timeline.py`, `test_evidence_signer.py`, `test_evidence_signer_v2.py`, `test_evidence_workflow.py`.
- **UI**: `evidence/`, `evidence-spine/`.
- **Human Gate**: to jest audit trail **dla** Human Gate — infrastruktura jest.
- **Ocena**: **PARTIAL** — kręgosłup gotowy, ale nic do niego decyzji Human Gate nie wrzuca systemowo.
- **Luki**: mandatoryjne zapisy z `human_gate` i `decision_gate` (obecnie opcjonalne).

### core.integration (+ `pipeline/state_machine.py`, `core/pipeline_controller.py`)
- **Kod**: `sylion/integration/orchestrator.py`, `integration/drift_detector.py`, `pipeline/state_machine.py`, `core/pipeline_controller.py`
- **Router**: `api/integration_routes.py`, `integration_orchestrator_routes.py`, `pipeline_routes.py`
- **Prefix**: `/api/v1/integrations`, `/api/v1/integration`, `/api/v1/pipeline`
- **Cel**: State machine pipeline'u + orkiestracja integracji zewnętrznych + drift detection.
- **Stan**: **BROKEN** (wg kanonu) — `execute` leci bez Human Gate (S1 dowód).
- **Testy**: `test_pipeline_state_machine.py` (69), `test_pipeline_controller.py` (65), `test_pipeline_e2e.py`, `test_integration_controller.py` (60), `test_integration_v2.py`, `test_integration_v3.py`, `test_integration_orchestrator_routes.py`.
- **UI**: `pipeline/`, `integrations/`, `drift/`.
- **Human Gate**: **MISSING pełne** — wszystkie 12 pytań na NIE w odniesieniu do pipeline. `state_machine.py` ma stany (`pending→running→complete`), ale brak stanu `awaiting_approval`. Żaden `await gate.wait()`.
- **Ocena**: **MISSING**.
- **Luki**: *kluczowa*. Dodać stan `awaiting_approval`, hook do `governance/human_gate.py`, classifier przy każdej zmianie stanu, policy engine, batch approval endpoint, signature, timeout+eskalacja, UI "pipeline paused". TO JEST #1 BACKLOG.

---

## 3 · L2 · MEMORY & SELF-EVOLUTION

**Intro.** 7× `memory.*`, 7× `aeis.*`, 4× `rebuild.*`. Memory — fundament wiedzy i kontekstu (SQLite/indexer/retrieval). AEIS — silniki samoobserwacji, samoograniczenia, samonaprawy, ewolucji. Rebuild — odbudowa systemu (LPW/CFT/cutover). Na poziomie testów jednostkowych — OK; na poziomie Human Gate: AEIS to **miejsce które GENERUJE najwięcej decyzji autonomii**, a żaden z tych modułów nie przechodzi przez centralne gate w runtime. `autonomy_controller.py` ma stages, ale brak dowodu wpięcia w governance.

### memory.kanon_access
- **Kod**: `memory/kanon_access.py`
- **Router**: `api/memory_routes.py`
- **Prefix**: `/api/v1/memory`
- **Cel**: Dostęp do "kanonu" (read-only do manifestów/proto z runtime).
- **Stan**: **PARTIAL** (`/memory/search` 404 w spot-check).
- **Testy**: `test_memory.py` (43).
- **UI**: `book/`, `idea-vault/`.
- **Human Gate**: N/A (read).
- **Ocena**: **N/A**.
- **Luki**: weryfikacja endpointów.

### memory.indexer
- **Kod**: `memory/indexer.py`
- **Router**: `memory_routes.py`
- **Prefix**: `/api/v1/memory`
- **Cel**: Indeksowanie treści (BM25/embeddings?) dla retrieval.
- **Stan**: **LIVE_VERIFIED** unit-poziom.
- **Testy**: `test_memory_indexer.py` (33), `test_memory_indexer_full.py`.
- **UI**: pośrednio w `book/`.
- **Human Gate**: N/A (tool).
- **Ocena**: **N/A**.
- **Luki**: indeksowanie dokumentów prawnych/kosztowych mogłoby mieć policy (uploady zewnętrzne — oś 2 ryzyka).

### memory.retrieval
- **Kod**: `memory/retrieval.py`
- **Router**: `memory_routes.py`
- **Prefix**: `/api/v1/memory`
- **Cel**: Zapytania RAG/retrieval top-k.
- **Stan**: **LIVE_VERIFIED** (testy).
- **Testy**: `test_memory_retrieval.py` (21), `test_memory_retrieval_full.py`.
- **UI**: `book/`.
- **Human Gate**: N/A.
- **Ocena**: **N/A**.
- **Luki**: brak.

### memory.evidence_store
- **Kod**: `memory/evidence_store.py`
- **Router**: `memory_routes.py` + ewentualnie `evidence_timeline_routes.py`
- **Prefix**: `/api/v1/memory` / `/api/v1/evidence-timeline`
- **Cel**: Store dowodów (evidence packs).
- **Stan**: **LIVE_VERIFIED** (65 testów).
- **Testy**: `test_memory_evidence_store.py` (65), `test_evidence_pack.py`, `test_evidence_packs.py`.
- **UI**: `evidence/`.
- **Human Gate**: store → **PARTIAL** (audit trail gotowy).
- **Ocena**: **PARTIAL**.
- **Luki**: mandatoryjne wpięcie z Human Gate decisions.

### memory.self_model_store
- **Kod**: `memory/self_model_store.py`
- **Router**: `memory_routes.py`
- **Prefix**: `/api/v1/memory`
- **Cel**: Przechowywanie modelu samoobserwacji (self-knowledge).
- **Stan**: **LIVE_VERIFIED** (29 testów).
- **Testy**: `test_self_model_store.py` (29).
- **UI**: brak dedykowanej.
- **Human Gate**:
  1. Modyfikacja self-modelu = D3 (system zmienia swoje postrzeganie siebie). 2. Brak. 3. Brak. 4. Brak. 5. Brak. 6. Brak. 7. Brak. 8. OK. 9. Brak. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: zmiana self-modelu musi być audytowana + opcjonalnie zatwierdzana (autonomy stage).

### memory.compact_layer
- **Kod**: `memory/compact_layer.py`
- **Cel**: Kompresja/zagęszczanie pamięci (old → summaries).
- **Stan**: **UNDOCUMENTED** (brak dedykowanego testu).
- **Testy**: brak osobnego `test_memory_compact_layer.py`.
- **UI**: brak.
- **Human Gate**: kompresja = nieodwracalna strata szczegółu → D3. **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: dodać testy; approval dla kompresji w prod.

### memory.kb_adapter
- **Kod**: `memory/kb_adapter.py`
- **Cel**: Adapter do zewnętrznej bazy wiedzy.
- **Stan**: **UNDOCUMENTED**.
- **Testy**: brak osobnego.
- **UI**: brak.
- **Human Gate**: integracja zewnętrzna (oś 2!) — **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: policy dla external KB calls (koszt, prywatność).

### aeis.self_observation
- **Kod**: `aeis/self_observation.py`
- **Router**: `aeis_routes.py`
- **Prefix**: `/api/v1/aeis`
- **Cel**: Samoobserwacja (telemetria zachowań systemu).
- **Stan**: **LIVE_VERIFIED** (32 testy).
- **Testy**: `test_self_observation.py` (32).
- **UI**: `autonomy/`, `overview/`.
- **Human Gate**: N/A (obserwacja pasywna).
- **Ocena**: **N/A**.
- **Luki**: brak.

### aeis.self_limitation
- **Kod**: `aeis/self_limitation.py` + `aeis/autonomy_controller.py` + `autonomy_stages.py`
- **Router**: `aeis_routes.py`
- **Prefix**: `/api/v1/aeis`
- **Cel**: Stages autonomii (observe → propose → sandbox → limited → full).
- **Stan**: **PARTIAL** — logika jest, brak wpięcia systemowego.
- **Testy**: `test_self_limitation.py` (69).
- **UI**: `autonomy/`.
- **Human Gate**: to jest **polityka autonomii** o której mówi framework! Ma potencjał GOOD, w praktyce:
  1. Stages istnieją. 2. Brak per-moduł osi w runtime. 3. Limited stage = blocking — czy egzekwowane? Do weryfikacji. 4. Brak. 5. Brak policy engine. 6. Brak. 7. Brak. 8. OK. 9. `autonomy/` jest. 10. Brak. 11. Brak. 12. Brak połączenia z pipeline.
- **Ocena**: **PARTIAL**.
- **Luki**: to jest NATURAL HOST dla Human Gate; wymaga połączenia z `decision_gate_engine` i `pipeline/state_machine`.

### aeis.self_preservation
- **Kod**: `aeis/self_preservation.py`
- **Router**: `aeis_routes.py`
- **Prefix**: `/api/v1/aeis`
- **Cel**: Ochrona krytycznych komponentów przed degradacją.
- **Stan**: **LIVE_VERIFIED** (47).
- **Testy**: `test_self_preservation.py` (47).
- **UI**: `autonomy/`.
- **Human Gate**: decyzja "zablokuj self-modyfikację" = security decision → **PARTIAL**.
- **Ocena**: **PARTIAL**.
- **Luki**: eskalacja gdy self-preservation triggers.

### aeis.self_explanation
- **Kod**: `aeis/self_explanation.py` + `aeis/explanation_engine.py`
- **Router**: `api/self_explanation_routes.py`
- **Prefix**: `/api/v1/self-explanation`
- **Cel**: Generowanie human-readable wyjaśnień decyzji.
- **Stan**: **LIVE_VERIFIED** (37+).
- **Testy**: `test_self_explanation.py` (37), `test_self_explanation_validator.py`.
- **UI**: `decisions/`, `evidence/`.
- **Human Gate**: N/A jako źródło decyzji; **wspiera** Human Gate (operator dostaje rationale).
- **Ocena**: **PARTIAL** (niezbędne dla UI Human Gate, nie zintegrowane).
- **Luki**: wynik self-explanation powinien być mandatoryjnym polem approval request.

### aeis.self_healing_orchestrator
- **Kod**: `aeis/self_healing_orchestrator.py`
- **Router**: `api/self_healing_routes.py`, `api/healing_engine_routes.py`
- **Prefix**: `/api/v1/self-healing`, `/api/v1/healing-engine`
- **Cel**: Automatyczna naprawa uszkodzonych modułów.
- **Stan**: **LIVE_VERIFIED** (76+65 testów).
- **Testy**: `test_self_healing_orchestrator.py` (76), `test_self_healing.py` (65).
- **UI**: `healing/`.
- **Human Gate**:
  1. Akcja healing w prod = D3 (system modyfikuje siebie). 2. Brak klasyfikacji ryzyka. 3. Brak blockingu. 4. Brak batch. 5. Brak policy "heal auto do severity X, powyżej approval". 6. Brak (do weryfikacji czy leci do evidence_spine). 7. Brak. 8. OK. 9. `healing/` UI. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **MISSING**.
- **Luki**: kluczowe — prod healing musi mieć policy autoapproval/eskalacji.

### aeis.improvement_queue
- **Kod**: `aeis/improvement_queue.py`
- **Router**: `aeis_routes.py`
- **Prefix**: `/api/v1/aeis`
- **Cel**: Kolejka propozycji samoulepszeń.
- **Stan**: **LIVE_VERIFIED** (endpoint zwraca `[]`).
- **Testy**: pokryte w `test_self_evolution.py` (15) + w test_self_healing orchestra.
- **UI**: `autonomy/`.
- **Human Gate**:
  1. Każda pozycja queue to kandydat do approval. 2. Brak klasyfikacji. 3. Kolejka jest blocking. 4. Batch naturalny. 5. Brak policy. 6. Brak. 7. Brak. 8. OK. 9. UI jest. 10. Brak. 11. Brak. 12. Brak.
- **Ocena**: **PARTIAL** (struktura gotowa, brak integracji).
- **Luki**: podłączyć do `human_gate` — queue POWINNA być backendem Human Gate decyzji.

### aeis.integration_controller
- **Kod**: `aeis/integration_controller.py`
- **Router**: `aeis_routes.py` (dyskoverable w `/api/v1/aeis`)
- **Prefix**: `/api/v1/aeis`
- **Cel**: Kontroler integracji zewnętrznych (wersja AEIS).
- **Stan**: **LIVE_VERIFIED** (60 testów).
- **Testy**: `test_integration_controller.py` (60).
- **UI**: `integrations/`.
- **Human Gate**: external calls = oś 2 → **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: policy na external API calls (koszty, prywatność).

### rebuild.orchestrator
- **Kod**: `rebuild/orchestrator.py`
- **Router**: `api/rebuild_routes.py`
- **Prefix**: `/api/v1/rebuild`
- **Cel**: Orkiestracja odbudowy systemu (LPW/CFT/cutover).
- **Stan**: **LIVE_VERIFIED** unit-poziom; live `/api/v1/rebuild/orchestrator` 404 (prefix istnieje, sub-path brak).
- **Testy**: `test_rebuild_orchestrator.py` (27), `test_rebuild_orchestrator_full.py`, `test_rebuild_routes.py`.
- **UI**: `rebuild/`.
- **Human Gate**: rebuild = najwyższy ryzyko. **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: rebuild MUSI mieć Human Gate (critical) + evidence.

### rebuild.lpw_manager
- **Kod**: `rebuild/lpw_manager.py` + `lpw_checkpoint.py`
- **Router**: `rebuild_routes.py`
- **Prefix**: `/api/v1/rebuild`
- **Cel**: Low-Power-Window checkpointy.
- **Stan**: **LIVE_VERIFIED**.
- **Testy**: pokryte w `test_rebuild_orchestrator*`.
- **UI**: `rebuild/`.
- **Human Gate**: checkpoint decision = **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: policy.

### rebuild.cft_runner
- **Kod**: `rebuild/cft_runner.py`
- **Router**: `rebuild_routes.py`
- **Prefix**: `/api/v1/rebuild`
- **Cel**: Continuous Fidelity Test runner.
- **Stan**: **LIVE_VERIFIED**.
- **Testy**: `test_rebuildability.py` (52), `test_rebuildability_framework.py`.
- **UI**: `rebuild/`, `golden-tests/`.
- **Human Gate**: N/A (test harness).
- **Ocena**: **N/A**.
- **Luki**: brak.

### rebuild.cutover_controller
- **Kod**: `rebuild/cutover_controller.py` + `cutover_automation.py`
- **Router**: `rebuild_routes.py`
- **Prefix**: `/api/v1/rebuild`
- **Cel**: Kontroler cutover (stara→nowa topologia).
- **Stan**: **PARTIAL** (brak dedykowanego testu).
- **Testy**: pośrednio.
- **UI**: `rebuild/`.
- **Human Gate**: cutover prod = critical → **MISSING**.
- **Ocena**: **MISSING**.
- **Luki**: mandat approval + signature + rollback window.

---

## 4 · Human Gate compliance summary

| Moduł | Ocena |
|---|---|
| core.contract_registry | N/A |
| core.manifest_loader | N/A |
| core.version_manager | MISSING |
| core.freeze_manager | MISSING |
| core.event_bus (L0) | N/A |
| manifesty (119) | MISSING (systemowo — decision_cls ignorowany) |
| proto (16) | N/A |
| core.event_bus (L1) | N/A |
| core.lifecycle_gates | PARTIAL |
| core.hot_swap | MISSING |
| core.rollback_manager | MISSING |
| core.code_snapshot | N/A |
| core.bundle_assembler | MISSING |
| core.module_registry | N/A |
| core.environment_orchestrator | MISSING |
| core.decision_gate_engine | MISSING (bypass/auto-approve) |
| core.evidence_spine | PARTIAL |
| core.integration + pipeline.state_machine | **MISSING — krytyczne** |
| memory.kanon_access | N/A |
| memory.indexer | N/A |
| memory.retrieval | N/A |
| memory.evidence_store | PARTIAL |
| memory.self_model_store | MISSING |
| memory.compact_layer | MISSING |
| memory.kb_adapter | MISSING |
| aeis.self_observation | N/A |
| aeis.self_limitation (autonomy) | PARTIAL |
| aeis.self_preservation | PARTIAL |
| aeis.self_explanation | PARTIAL |
| aeis.self_healing_orchestrator | MISSING |
| aeis.improvement_queue | PARTIAL |
| aeis.integration_controller | MISSING |
| rebuild.orchestrator | MISSING |
| rebuild.lpw_manager | MISSING |
| rebuild.cft_runner | N/A |
| rebuild.cutover_controller | MISSING |

Zbiorczo L0-L2: **0× GOOD**, 8× PARTIAL, 14× MISSING, 14× N/A.

---

## 5 · Najważniejsze drifty L0-L2

1. **Pipeline bez Human Gate (krytyczne).** `pipeline/state_machine.py` + `core/pipeline_controller.py` nie zawierają słów `human_gate|approval|gate_check`. `execute` leci do `complete` z `decision-snapshot outcome=approved confidence=1.0` wystawionym automatycznie. Potwierdza S1.

2. **Dwie implementacje `decision_gate_engine`** — `core/decision_gate_engine.py` i `governance/decision_gate_engine.py`. Klasyczny fork; nie wiadomo która jest źródłem prawdy. Manifest `core.decision_gate_engine.json` deklaruje jedną.

3. **Silnik `governance/human_gate.py` istnieje, ale nie ma konsumenta w L0-L2.** Moduł jest w kodzie, router `gates_routes.py` tylko ogólny; brak wpięcia w lifecycle/hot-swap/rollback/healing/rebuild.

4. **`/api/v1/contracts` zwraca pustą listę** mimo 119 manifestów na dysku i 119 modułów w registry. Bootstrap nie ładuje kanonu do store.

5. **Manifesty deklarują `decision_cls=D3` dla większości modułów** — runtime to ignoruje, brak zmaterializowania tej klasy w przepływie akcji.

6. **AEIS autonomy_stages istnieją** (observe/propose/sandbox/limited/full) ale stan autonomii per-moduł nie wpływa na pipeline — brak sprzężenia.

7. **`improvement_queue` jest NATURAL HOST dla Human Gate** (kolejka propozycji = kolejka decyzji), ale nie jest podłączona do approvals.

8. **Brak dedykowanych testów**: `memory.compact_layer`, `memory.kb_adapter`, `rebuild.cutover_controller` (pokryte tylko pośrednio).

9. **`evidence_spine` gotowy** — nie jest mandatoryjnym sinkiem dla governance events.

10. **`freeze_manager` bez dedykowanego testu i UI** przy wysokim wpływie operacyjnym.

11. **`version_manager` major-bump bez decision hook** — breaking changes przechodzą cicho.

12. **`rebuild.*`** — najbardziej krytyczna warstwa pod względem ryzyka (cutover, LPW) — **zero** integracji z Human Gate.

---

## 6 · Rekomendacje do backlogu naprawczego

### P0 (critical, blokuje S1 działający wg kanonu)
- **FIX-001** Wpiąć `governance/human_gate.py` w `pipeline/state_machine.py`: dodać stan `awaiting_approval`; po klasyfikacji step'u przez `decision_gate_engine` czekać na approval (lub autoapproval-policy) przed `operation=generate`.
- **FIX-002** Unifikacja `core/decision_gate_engine.py` ↔ `governance/decision_gate_engine.py` → jeden silnik, drugi DEPRECATED.
- **FIX-003** Bootstrap kanonu: przy starcie backendu `manifest_loader` musi załadować 119 manifestów do `contract_registry` store (fix `/api/v1/contracts` = []).

### P1 (high risk, systemowo istotne)
- **FIX-004** Risk-based policy engine (12 osi) + endpoint `/api/v1/governance/policies` CRUD, powiązany z UI `autonomy/`.
- **FIX-005** Hot-swap / rollback / cutover / freeze w prod → wymagają approval (policy) + signature + timeout.
- **FIX-006** `improvement_queue` ↔ Human Gate: queue=kolejka decyzji, batch approval endpoint, UI panel "pending decisions".
- **FIX-007** `self_healing_orchestrator` — policy "auto do severity X, powyżej gate".
- **FIX-008** `version_manager` — major bump triggeruje decision_gate; emit event `version.bump.major` → evidence_spine.

### P2 (quality, audit)
- **FIX-009** Mandatoryjny sink `evidence_spine` dla wszystkich decyzji governance (obecnie opcjonalnie).
- **FIX-010** Dopisać `self_explanation` jako wymagane pole approval_request (operator dostaje rationale + warianty).
- **FIX-011** Testy dedykowane: `memory.compact_layer`, `memory.kb_adapter`, `rebuild.cutover_controller`, `core.freeze_manager`.
- **FIX-012** `environment_orchestrator` — promocja env staging→prod wymaga D3+ gate.

### P3 (UI/UX Human Gate)
- **FIX-013** UI `decisions/` jako frontend Human Gate: kolejka, priorytety, batch, delegacja, audit trail, tokeny, tryby operatora (Dashboard + Mobile mirror).
- **FIX-014** Stan `awaiting_approval` widoczny w `pipeline/` — operator widzi co blokuje.
- **FIX-015** UI `autonomy/` — konfiguracja per-moduł per-oś (12 wymiarów).

### P4 (discipline)
- **FIX-016** W manifest schema egzekwować że `decision_cls >= D3` ⇒ moduł MUSI implementować `human_gate_hook` (enforced in CI).
- **FIX-017** `buf-breaking-guardian` wpięty w CI dla `contracts/proto/`.

---

**Podsumowanie końcowe.** Warstwy L0-L2 mają solidny *fundament inżynierski* (testy, moduły, routery, UI) ale **systemowo nie egzekwują Human Gate**. Infrastruktura do tego istnieje (`human_gate.py`, `decision_gate_engine`, `evidence_spine`, `autonomy_stages`, `improvement_queue`, UI `decisions/gates/autonomy/`) — brakuje **spoiwa** między `pipeline/state_machine` a governance. Najważniejsza interwencja to FIX-001 + FIX-002 + FIX-006, które razem zamieniają obecne "mechaniczne complete" w realne "awaiting approval → approved with evidence".
