# 02 — Analiza Dwóch Generacji Proto Kontraktów gRPC

**Audyt**: SYLION AEIS v3.5 — Contracts Layer
**Data**: 2026-04-24
**Status**: Read-only inventory + jakość + rekomendacja

---

## 0. TL;DR

| Wymiar                        | Legacy (`src/sylion-pipeline/proto/`) | Kanon (`sylion/contracts/proto/`)      |
|-------------------------------|---------------------------------------|----------------------------------------|
| Liczba plików `.proto`        | 6                                     | 16 (15 domen + `common`)               |
| Liczba services               | **12**                                | **86**                                 |
| Liczba RPC                    | **53**                                | **483**                                |
| Zasięg domenowy               | Core + 5 domen                        | **15 domen** (A-O klasy)               |
| Versioning w pakiecie         | brak (`package sylion;`)              | **`sylion.<domain>.v1;`** (pełne)      |
| Dedykowany `common.proto`     | `sylion_common.proto`                 | `common.proto` (pakiet `sylion.common.v1`) |
| Generator stubów              | `sylion/contracts/generate_stubs.py`  | `buf.gen.yaml` (buf v2, managed mode)  |
| Katalog wyjściowy stubów      | `sylion/grpc_stubs/`                  | `sylion/contracts/generated/`          |
| **Używane runtime'owo**       | **TAK — `core_server.py` + 5 innych** | **NIE — tylko testy pomocnicze**       |
| Rekomendacja                  | Zamrozić, zmigrować                   | **WYBRAĆ** (z planem migracji)         |

**Werdykt**: `sylion/contracts/proto/` (kanon) jest dojrzały, skalowalny i pokrywa ~85 serwisów dla 119 modułów (A-O). Legacy pokrywa tylko 12 serwisów (core domain) i jest uruchamiany w produkcji. Kanon nie jest jeszcze podłączony do `sylion.grpc.*` servicerów — istnieje dryf contract-vs-runtime.

---

## 1. Inwentaryzacja — Legacy (`src/sylion-pipeline/proto/`)

Ścieżka: `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\proto\`

| Plik                       | Bytes | Services | RPCs | Uwagi                                 |
|----------------------------|-------|----------|------|---------------------------------------|
| `sylion_common.proto`      | 2 832 | 0        | 0    | Shared types (ModuleId, Decision...)  |
| `sylion_core.proto`        | 5 197 | 3        | 12   | ModuleRegistry, EvidenceSpine, EventBus (**2× stream**) |
| `sylion_cognitive.proto`   | 5 234 | 2        | 8    | ModelRouter, Plan                     |
| `sylion_execution.proto`   | 6 230 | 2        | 10   | Workflow, Job                         |
| `sylion_governance.proto`  | 4 999 | 2        | 10   | Governance, Council                   |
| `sylion_aeis.proto`        | 8 001 | 3        | 13   | Autonomy, Explanation, Improvement    |
| **SUMA**                   | ~32 KB| **12**   | **53** | 6 plików, 1 pakiet (`sylion`)       |

Cechy:
- `package sylion;` — **wszystkie pliki w tym samym namespace**, brak segregacji wersji/domen.
- Import `google/protobuf/empty.proto` + `google/protobuf/timestamp.proto` — używa well-known types.
- Używa **typowanych enumów** (`DecisionClass`, `ProposalStatus`, `Vote`, `SessionStatus` itd.).
- Docstringi `/** ... */` nad każdym service/message/enum — udokumentowane.
- 2 streaming RPC (`SubscribeEvents`, `ReplayEvents` w `sylion_core.proto`).

## 2. Inwentaryzacja — Kanon (`sylion/contracts/proto/`)

Ścieżka: `C:\Users\razor\Desktop\pipeline_glm\src\sylion-pipeline\sylion\contracts\proto\`

| Plik                  | Bytes  | Services | RPCs | Domena / klasy modułów             |
|-----------------------|--------|----------|------|------------------------------------|
| `common.proto`        | 1 536  | 0        | 0    | Shared primitives, pagination      |
| `core_v1.proto`       | 12 053 | 8        | 32   | Klasa A (Core)                     |
| `cognitive_v1.proto`  | 10 842 | 7        | 36   | Klasa B (Cognitive)                |
| `execution_v1.proto`  | 10 605 | 6        | 34   | Klasa C (Execution)                |
| `memory_v1.proto`     | 10 412 | 7        | 35   | Klasa D (Memory)                   |
| `governance_v1.proto` | 16 983 | 7        | 45   | Klasa E (Governance)               |
| `security_v1.proto`   | 11 683 | 8        | 44   | Klasa F (Security)                 |
| `efficiency_v1.proto` |  6 765 | 4        | 25   | Klasa G (Efficiency)               |
| `aeis_v1.proto`       |  8 672 | 5        | 31   | Klasa H (AEIS core)                |
| `skills_v1.proto`     |  4 711 | 3        | 17   | Klasa I (Skills)                   |
| `surface_v1.proto`    | 17 102 | 8        | 62   | Klasa J (Console/Panels)           |
| `rebuild_v1.proto`    |  6 903 | 4        | 23   | Klasa K (Self-Rebuild)             |
| `quality_v1.proto`    |  5 827 | 3        | 20   | Klasa L (Quality)                  |
| `devices_v1.proto`    |  5 902 | 4        | 19   | Klasa M (Devices Addon)            |
| `sdr_v1.proto`        |  8 114 | 5        | 26   | Klasa N (SDR/Radio)                |
| `cellular_v1.proto`   |  9 472 | 7        | 34   | Klasa O (Cellular)                 |
| **SUMA**              | ~148 KB| **86**   | **483** | 16 plików, 15 pakietów `sylion.<d>.v1` |

Cechy:
- Pakiety per-domena: `sylion.common.v1`, `sylion.core.v1`, ..., `sylion.cellular.v1`.
- `option go_package` + `option java_package` — **multi-target ready**.
- Każdy plik nagłówek "Contract Freeze 1.0.0" + lista modułów w komentarzu.
- Brak `reserved` — (pliki świeżo "zamrożone", brak ewolucji w wersjonowanych numerach).
- 1 streaming RPC (`core_v1.proto`).
- Typy prymitywne zamiast enumów (`string status`, `string severity` z komentarzami `// draft|build|...`) — **ad-hoc, nie typosafe**.
- Konsekwentny import `import "common.proto";` we wszystkich 15 plikach domenowych.

---

## 3. Runtime Usage — kto używa czego

### 3.1 Live gRPC server (`sylion.server` → `sylion.grpc.core_server.create_grpc_server`)

Plik: `src/sylion-pipeline/sylion/grpc/core_server.py` (linie 30-35, 206-260)

```python
from sylion.grpc_stubs import sylion_core_pb2, sylion_core_pb2_grpc, sylion_common_pb2
from sylion.grpc_stubs import sylion_execution_pb2_grpc
from sylion.grpc_stubs import sylion_cognitive_pb2_grpc
from sylion.grpc_stubs import sylion_governance_pb2_grpc
from sylion.grpc_stubs import sylion_aeis_pb2_grpc
```

**Wszystkie runtime'owe servicery rejestrują LEGACY stuby**:
- `ModuleRegistryService`, `EvidenceSpineService`, `EventBusService` (core)
- `WorkflowService`, `JobService` (execution)
- `ModelRouterService`, `PlanService` (cognitive)
- `GovernanceService`, `CouncilService` (governance)
- `AutonomyService`, `ExplanationService`, `ImprovementService` (aeis)

**12/12 rejestracji z legacy**. Zero rejestracji z kanonu.

### 3.2 Pliki importujące LEGACY stuby

```
sylion/grpc_stubs/sylion_{aeis,cognitive,common,core,execution,governance}_pb2[_grpc].py
sylion/grpc/core_server.py
sylion/grpc/aeis_server.py
sylion/grpc/cognitive_server.py
sylion/grpc/execution_server.py
sylion/grpc/governance_server.py
sylion/grpc/eventbus_server.py
sylion/api/health_routes.py     (import tylko do health-check flagi)
sylion/server.py                 (entrypoint)
tests/test_grpc_*.py             (6 plików testów serwerów)
tests/test_server_integration.py
```

Razem: **6 servicerów + 1 entrypoint + 7 testów**.

### 3.3 Pliki importujące KANON (`contracts/generated/*_v1_pb2`)

`grep -r "from sylion.contracts.generated"` → **0 dopasowań w kodzie runtime'owym**.

Jedyne referencje:
- `tests/test_stub_manager.py` — **tylko jako stringi w testach** generatora stubów (linie 78-79, 100-101, 245-265, 309-310). Nie importuje pakietów.
- `sylion/contracts/generated/*.py` — generated code (self-import).

**Kanoniczne stuby są generowane, ale NIE używane przez żaden servicer ani router.**

### 3.4 FastAPI (`sylion/api/app.py`)

Routery HTTP (np. `cellular_routes.py`, `sdr_routes.py`, `adapter_bus_routes.py`) używają **klas Python (sylion.cellular.control_plane, sylion.sdr.*, sylion.cellular.*), NIE proto**. REST-na-proto bridge nie istnieje — proto są konsumowane wyłącznie przez gRPC server, a ten używa legacy.

---

## 4. Jakość i skalowalność — porównanie

| Kryterium                         | Legacy                             | Kanon                                 | Lepszy |
|-----------------------------------|------------------------------------|---------------------------------------|--------|
| **Organizacja (domeny)**          | 1 pakiet (`sylion`), 6 plików      | 15 pakietów per-domena, 16 plików     | Kanon  |
| **Skalowalność (119 modułów)**    | pokrywa ~12 core services         | pokrywa ~85 services, 15 klas A-O     | Kanon  |
| **Versioning**                    | brak (`package sylion;`)           | `sylion.<domain>.v1;` — `v2` możliwe obok `v1` | Kanon |
| **Multi-language targets**        | brak option'ów                     | `go_package` + `java_package` w każdym pliku | Kanon |
| **Shared messages**               | `sylion_common.proto` (8 typów)    | `common.proto` (11 typów, pagination) | Kanon  |
| **Typy wiadomości — enumy**       | **Typowane enumy** (DecisionClass, Vote, Status) | `string` + komentarz `// a\|b\|c` — stringly-typed | **Legacy** |
| **Well-known types**              | `google.protobuf.Timestamp/Empty`  | `double epoch_seconds`, własny `Empty`| **Legacy** |
| **Streaming RPC**                 | 2 (EventBus: Subscribe, Replay)    | 1 (Core)                              | **Legacy** |
| **Komentarze / docstringi**       | `/** ... */` na services, enums, messages | Nagłówki sekcji `// E1: ...`, bez opisu pól | **Legacy** |
| **Pola `reserved`**               | 0                                  | 0                                     | remis  |
| **Konsekwencja nazewnictwa**      | PascalCase+snake\_case, spójne     | PascalCase+snake\_case, spójne        | remis  |
| **Generator**                     | ad-hoc `grpc_tools` script         | `buf.gen.yaml` (buf v2, managed, remote plugins) | Kanon |
| **Rozszerzenia** (Devices+16, HG+13, OP+12) | brak pokrycia               | `devices_v1`, `sdr_v1`, `cellular_v1`, `surface_v1` — **pokryte** | Kanon |
| **Decision Gates / Evidence**     | `Decision`, `Contract` top-level   | Pełne `DecisionLadderService` + `EvidenceWorkflowService` (6+6 RPC) | Kanon |
| **Reużywalne typy z common**      | `ModuleId`, `EvidenceEntry`        | `ModuleId`, `LifecycleStage`, `DecisionClass`, `ContentHash`, `PageRequest/Info`, `OperationResult` | Kanon |

### 4.1 Kluczowe wady KANONU (do naprawy)

1. **Stringly-typed enumeracje** — `status`, `severity`, `check_type` itd. jako `string` zamiast `enum` → gubi typosafety, psuje klientów, utrudnia breaking-change detection przez buf.
2. **Własny `Timestamp` (`double epoch_seconds`)** — brak `google.protobuf.Timestamp` → niespójność z ekosystemem gRPC.
3. **Brak docstringów na polach** — komentarze sekcyjne, ale pola bez opisów.
4. **Zero `reserved` tags** — przy pierwszej kompatybilnej zmianie ryzyko re-użycia numerów pól.
5. **Brak wersji `v2`** — `_v1` w nazwie pliku ale żadnego przygotowania do ewolucji.

### 4.2 Kluczowe wady LEGACY

1. **Pokrywa tylko 12/86 serwisów** (~14%).
2. **Brak klas J (Surface), K (Rebuild), L (Quality), M (Devices), N (SDR), O (Cellular), F (Security), D (Memory), G (Efficiency), I (Skills)** — czyli 10 z 15 klas modułów.
3. **1 pakiet dla wszystkiego** — `package sylion;` → kolizje typów, brak izolacji wersji.
4. **Brak option'ów multi-language** — utrudnia klientów Go/Java/TypeScript.
5. **Brak buf/managed mode** — CI nie detekuje breaking changes.

---

## 5. Drift Analysis — unikalne / zduplikowane services

### 5.1 Services obecne w OBU generacjach (duplikacja / dryf)

| Service (legacy name → kanon)                | Dryf                                       |
|----------------------------------------------|--------------------------------------------|
| `GovernanceService` (legacy) ↔ `DecisionLadderService` (kanon) | Podobna funkcjonalność, różne nazwy RPC (`CreateProposal` vs `Propose`), różne typy (`Proposal` proto message vs `ProposalMessage`). **Niekompatybilne wire**. |
| `CouncilService` ↔ `CouncilWorkflowService`   | `CreateSession` vs `OpenSession`, `CastVote` (kompatybilne struktury), `TallyVotes` vs `Tally`. Różne kody enum (`Vote.YES` vs `string value`). |
| `ModuleRegistryService` (core)                | Legacy: 4 RPC; Kanon: 8 RPC (dodaje `Deregister`, `UpdateLifecycle`, itd.). |
| `EvidenceSpineService` (core)                 | Legacy: `AppendEntry/VerifyChain/GetEntry/SubscribeEntries` (stream). Kanon: podobnie, ale bez streaming. |
| `EventBusService` (core)                      | Legacy: 2× stream RPC (`SubscribeEvents`, `ReplayEvents`). Kanon: present w `core_v1` ale bez stream. |
| `WorkflowService`, `JobService` (execution)   | Legacy: 5+5 RPC. Kanon: rozbudowane do 34 RPC w 6 serwisach (dodaje scheduler, idempotency, retry). |
| `ModelRouterService`, `PlanService` (cognitive) | Legacy: 4+4 RPC. Kanon: 7 serwisów, 36 RPC (dodaje memory, reasoning, prompt registry). |
| `AutonomyService`, `ExplanationService`, `ImprovementService` (aeis) | Legacy: 13 RPC. Kanon: 5 serwisów, 31 RPC. |

**Wire-level**: żaden z duplikatów nie jest kompatybilny binarnie — różne nazwy pakietów (`sylion` vs `sylion.<domain>.v1`), różne `FullyQualifiedName` serwisów.

### 5.2 Services tylko w KANONIE (brak w legacy)

Cała klasa D/F/G/I/J/K/L/M/N/O + rozszerzenia E (Governance to 7 serwisów):
- **Memory** (`memory_v1`): 7 svc (ContextStore, SemanticIndex, Reasoning, EpisodicLog, KnowledgeGraph, FactStore, RetrievalOrchestrator)
- **Security** (`security_v1`): 8 svc (Auth, Authz, Secrets, Audit, ThreatDetect, Sandbox, CryptoKMS, PolicyEnforce)
- **Efficiency** (`efficiency_v1`): 4 svc
- **Skills** (`skills_v1`): 3 svc (Registry, Executor, Demand)
- **Surface** (`surface_v1`): 8 svc, 62 RPC (Console, Panels, Chat, Council UI)
- **Rebuild** (`rebuild_v1`): 4 svc
- **Quality** (`quality_v1`): 3 svc
- **Devices** (`devices_v1`): 4 svc, 19 RPC — **wymagane dla Devices Addon (+16 modułów)**
- **SDR** (`sdr_v1`): 5 svc
- **Cellular** (`cellular_v1`): 7 svc, 34 RPC
- **Governance E2-E7**: CouncilWorkflow, Roles, GatesRegistry, EvidenceWorkflow, PolicyRegistry, SelfExplanationValidator

### 5.3 Services tylko w LEGACY

**Żaden**. Legacy to wąski podzbiór domenowo, ale wszystkie jego core-serwisy są pokryte w kanonie (z innymi nazwami / rozszerzone).

---

## 6. Rekomendacja

### Wybór: **KANON (`sylion/contracts/proto/`)** + plan migracji

**Uzasadnienie**:

1. **Pokrycie domenowe** — kanon pokrywa 15 klas modułów A-O (~85 serwisów), legacy pokrywa 5 klas (~12 serwisów). Dla 119 modułów + Devices+16 + HG+13 + OperatorMobile+12 legacy nie wystarczy ani teraz, ani w przyszłości.
2. **Versioning i ewolucja** — `sylion.<domain>.v1` pozwala na dodanie `v2` obok `v1` bez breaking-change. Legacy `package sylion;` wymagałby zmiany nazw w całości.
3. **Multi-language** — `option go_package` + `option java_package` w kanonie pozwalają wygenerować klientów Go/Java/TS (wymagane dla Operator Mobile i Console UI). Legacy nie.
4. **Buf managed** — `buf.gen.yaml` + remote plugins automatyzują CI/CD, breaking-change detection (`buf breaking`), linting (`buf lint`). Legacy ma ręczny skrypt grpcio-tools.
5. **Governance i Evidence** — kanon pokrywa pełny stack D0-D5 + EvidencePack + Gates (wymagane dla D3+ decyzji w MEMORY.md). Legacy ma ogólne `Proposal/Council`, bez Roles/Policy/SelfExplanation.

### Plan migracji (sugerowany, poza zakresem tego audytu)

**Faza 1 — Hardening kanonu** (przed cutoverem):
- Zamienić stringly-typed pola (`status`, `severity`, `check_type`, `stage`, `class_value`) na prawdziwe `enum` z sufiksami `_UNSPECIFIED = 0`.
- Zamienić `double epoch_seconds` na `google.protobuf.Timestamp`.
- Dodać `reserved` dla zarezerwowanych numerów pól (minimum 10 per message).
- Ujednolicić streaming — dodać `stream` do EvidenceSpine, EventBus, Surface (notyfikacje).
- Dodać docstringi do pól (buf lint może wymusić).

**Faza 2 — Servicery** (jeden per domena, pilotaż core):
- Napisać `sylion/grpc/v1/core_server.py` używający `from sylion.contracts.generated import core_v1_pb2, core_v1_pb2_grpc`.
- Zarejestrować równolegle z legacy (port 50051 = legacy, 50052 = v1) — **dual-run** zgodny z SYLION cutover pattern.
- Przełączyć klientów.

**Faza 3 — Deprecation legacy**:
- Oznaczyć `sylion/proto/sylion_*.proto` jako `DEPRECATED` w nagłówkach.
- Oznaczyć `sylion/grpc_stubs/*` jako deprecated w `__init__.py`.
- Po 2 releasach usunąć `sylion/proto/` i `sylion/grpc_stubs/`.

### Alternatywy — odrzucone

| Opcja    | Dlaczego NIE                                                                 |
|----------|-----------------------------------------------------------------------------|
| Legacy   | Pokrywa 14% domeny. Nie skaluje się do 119 modułów, nie wspiera Devices/Surface/Memory/Security. |
| Hybrid   | Trzymanie dwóch generacji = podwójny koszt CI, ryzyko dryfu, klient musi wybierać. |
| Rebuild  | Niepotrzebne — kanon jest dobrze zaprojektowany, wymaga tylko 5 punktów hardening (patrz Faza 1). |

---

## 7. Dowody (plik:linia)

- Live gRPC uses legacy: `src/sylion-pipeline/sylion/server.py:27` → `from sylion.grpc.core_server import create_grpc_server`
- All servicers register legacy stubs: `src/sylion-pipeline/sylion/grpc/core_server.py:30-35, 206-260`
- Kanon generator (buf v2): `src/sylion-pipeline/buf.gen.yaml`
- Kanon fallback generator: `src/sylion-pipeline/sylion/contracts/generate_stubs.py:26-43`
- Kanon proto pliki: `src/sylion-pipeline/sylion/contracts/proto/*.proto` (16 plików)
- Kanon generated stubs (unused by runtime): `src/sylion-pipeline/sylion/contracts/generated/*_pb2.py` (14 par plików)
- Legacy proto: `src/sylion-pipeline/proto/sylion_*.proto` (6 plików)
- Legacy stubs (in use): `src/sylion-pipeline/sylion/grpc_stubs/sylion_*_pb2*.py`
- Kanon nieużywany w runtime: `grep -r "from sylion.contracts.generated"` → 0 dopasowań (poza self-imports)

---

## 8. Ryzyka i flagi

1. **Contract-vs-runtime drift** — zespół pisze nowe proto w kanonie (15 plików, 86 services), ale runtime nadal działa na 6 legacy plikach. Każda zmiana w kanonie jest **niewidoczna dla klientów gRPC**.
2. **False sense of coverage** — `tests/test_stub_manager.py` testuje generator, ale nie importuje generated pb2 jako moduły — więc testy ZIELONE ≠ kanon faktycznie kompiluje się poprawnie do wire-spec.
3. **Governance ambiguity** — duplikacja `GovernanceService` (legacy) vs `DecisionLadderService` (kanon) — jeśli klient wywoła `GovernanceService.CreateProposal`, trafi do legacy servicer'a, który nie wie o `DecisionClass=D3+` flow z `EvidenceWorkflowService` (brak w legacy).
4. **Devices Addon +16** — wymaga `devices_v1.proto` (kanon). Legacy nie ma. **Bez migracji nie da się dodać Devices.**
5. **Operator Mobile +12** — wymaga `surface_v1.proto` + `go_package`/`java_package` options dla klienta mobilnego. Legacy nie wspiera.
