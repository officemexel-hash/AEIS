# 02 · MAPA ARCHITEKTURY RZECZYWISTEJ vs KANON

**Data:** 2026-04-24
**Zakres:** porównanie planowanych warstw Księgi v3.5 + Distributed Build z rzeczywistymi granicami kodu
**Źródło prawdy:** struktura pakietów Python (`sylion/`), 84 route files, 57 stron frontendu, 119 manifestów

---

## 1. Trzy modele warstw w kanonie (z baseline)

### Model A — Dokumentacja v3.5 §0.4 (6 warstw AEIS)
`Cognitive • Execution • Security • Memory • Self-Evolution • Governance`

### Model B — Distributed Build (7 warstw)
`Canon → Planning → Coordination → Worker → Integration → Governance → Operator`

### Model C — Masterplan R0.6 (Kernel + 12 klas A-L)
- **Kernel** (core.*)
- **A** Kernel Foundation (8)
- **B** Cognitive (7)
- **C** Execution (6)
- **D** Memory (7)
- **E** Governance (7)
- **F** Security (8)
- **G** Efficiency (4)
- **H** AEIS Self-* (5)
- **I** Skills (3)
- **J** Surface (3)
- **K** Rebuild (4)
- **L** Quality (3)
- **TOTAL**: Kernel + 65 modułów

---

## 2. Rzeczywiste granice kodu (co widać w drzewie)

### 2.1 Pakiety Python `src/sylion-pipeline/sylion/` (33 top-level)

| Pakiet | Rola rzeczywista | Czy w Modelu C (A-L)? |
|---|---|---|
| `aeis` | Self-Evolution (H) — 7 modułów | ✅ H |
| `api` | Routery FastAPI — **warstwa transport** | ⚠️ brak w kanonie, infrastrukturalna |
| `cellular` | **LAB** — RAN/5G attack vectors | ❌ poza kanonem |
| `cognitive` | Cognitive (B) — 13 modułów (+6 nad Księgę) | ✅ B |
| `container` | **LAB** — docker orkiestracja | ❌ poza kanonem |
| `contracts` | Contract registry + manifests + proto | ✅ Kernel |
| `core` | Kernel (A) + podstawy | ✅ A |
| `db` | Persistence layer — SQLite/Postgres adapters | ⚠️ infrastrukturalne |
| `devices` | Device registry + discovery + test_harness + artifact_deployer | ⚠️ 3 w kanonie (Devices Addon), 1 LAB |
| `efficiency` | Efficiency (G) | ✅ G |
| `execution` | Execution (C) — 8 (+2 nad Księgę) | ✅ C |
| `funding_autopilot` | **Nowy moduł produkcyjny** — funding/dotacje | ❌ poza kanonem |
| `governance` | Governance (E) — 10 (+3) + **Human Gate fragment** | ✅ E |
| `grpc` + `grpc_stubs` | gRPC transport layer | ⚠️ infrastrukturalne |
| `infra` | Infrastruktura (1 manifest: topology_templates) | ⚠️ infra |
| `integration` | `core.integration` — drift detector itp. | ✅ A |
| `memory` | Memory (D) — 7 | ✅ D |
| `monitoring` | Monitoring — 4 moduły | ⚠️ częściowo G (efficiency)/E (governance) |
| `observability` | Tracing, logs, metrics | ⚠️ rozszerzenie poza kanonem |
| `pipeline` | Pipeline state machine | ✅ A? C? |
| `project_mode` | Zarządzanie trybem projektu | ❌ poza kanonem |
| `quality` | Quality (L) — 4 (+1) | ✅ L |
| `rebuild` | Rebuild (K) — 4 | ✅ K |
| `sdr` | **LAB** — Software Defined Radio | ❌ poza kanonem |
| `security` | Security (F) — 18 (+10!) | ✅ F — duża ekspansja |
| `skills` | Skills (I) — 3 | ✅ I |
| `surface` | Surface (J) — 3 | ✅ J |
| `vps` | **LAB** — orkiestracja Hetzner VPS | ❌ poza kanonem |
| `worker` | `core.worker` — registry + monitor | ✅ A |
| `server.py` | Entry point | — |

### 2.2 Warstwa transport/API (`sylion/api/`)

- **84 pliki route** (`*_routes.py` + `router.py`)
- **1433 obiekty tras**, 1170 unikalnych ścieżek OpenAPI 3.1
- Centralna rejestracja w `app.py` przez `sylion/contracts/manifests` auto-discovery

### 2.3 Frontend Operator Console (`src/sylion-frontend/src/app/(app)/`)

**55 katalogów stron** (+1 marketing):
```
agents, anomalies, audit, auth, autonomy, autoscaler, book, budget, build-state,
builds, bundles, capacity, cellular, circuits, connectors, contracts, costs,
decisions, deploy, devices, drift, environments, evaluator, events, evidence,
evidence-spine, funding, gates, golden-tests, governance, healing, health,
idea-vault, integrations, lifecycle, modules, notifications, observability,
overview, performance, pipeline, projects, quality, rebuild, risk, roles, sdr,
secrets, security-scan, settings, skills, sla, workers, workspace
```

---

## 3. Rzeczywista mapa warstw AEIS (stan 2026-04-24)

Wnioski z inwentaryzacji — system **ma 7 warstw rzeczywistych**:

### 🟦 WARSTWA 1 — CANON (źródło prawdy kontraktów)
**Rola:** manifesty, kontrakty gRPC, wersjonowanie, freeze
**Pakiety:** `contracts/` (manifests + proto 15 plików), `core/contract_registry`, `core/manifest_loader`, `core/version_manager`, `core/event_bus` definitions
**Frontend:** `/contracts`, `/modules`, `/book` (Canon Book)
**Stan:** ✅ dojrzałe (119 manifestów auto-loading), ⚠️ 2 generacje proto (drift)

### 🟩 WARSTWA 2 — KERNEL (fundamenty runtime)
**Rola:** lifecycle, snapshots, rollback, hot swap, decision gate engine, evidence spine
**Pakiety:** `core/` (15 modułów), `pipeline/`, `integration/`
**Frontend:** `/lifecycle`, `/snapshot`, `/rollback`, `/hot-swap`, `/decisions`
**Stan:** ✅ dojrzałe — największa domena kanonu poza Security

### 🟨 WARSTWA 3 — COGNITIVE & PLANNING
**Rola:** agent runtime, planner, reasoner, chat, code agent, LLM adapter, model router, idea vault, knowledge, feedback, evaluator
**Pakiety:** `cognitive/` (13 modułów)
**Frontend:** `/workspace`, `/agents`, `/idea-vault`, `/evaluator`, `/skills` (częściowo)
**Stan:** ✅ dojrzałe + rozrost o +6 modułów nad plan

### 🟧 WARSTWA 4 — EXECUTION & WORKER (Distributed Build)
**Rola:** workerzy, assignments, build topology, bundle assembler, environment orchestrator, pipeline controller, execution guard
**Pakiety:** `worker/`, `execution/`, `pipeline/`, `core/bundle_assembler`, `core/environment_orchestrator`
**Frontend:** `/workers`, `/builds`, `/bundles`, `/build-state`, `/pipeline`, `/environments`, `/capacity`, `/autoscaler`
**Stan:** ✅ dojrzałe, ścisłe zgodne z Distributed Build spec

### 🟥 WARSTWA 5 — GOVERNANCE & HUMAN GATE
**Rola:** decision ladder D0-D5, decision gate engine, evidence spine/pack, human gate, autonomy controller, audit trail, compliance
**Pakiety:** `governance/` (10 modułów), `aeis/autonomy_controller`, `core/decision_gate_engine`, `core/evidence_spine`
**Frontend:** `/gates`, `/governance`, `/decisions`, `/autonomy`, `/evidence`, `/evidence-spine`, `/audit`, `/roles`, `/risk`
**Stan:** 🔴 **KRYTYCZNY DRIFT** — Human Gate Orchestrator jako 5-rolowy system nie istnieje, jest tylko fragment `governance/human_gate.py` (367 LoC). Implementacja obecna obsługuje D0-D5 (inny typ governance), nie risk-based policy engine z 12 osiami konfiguracji.

### 🟪 WARSTWA 6 — SECURITY (F + rozszerzenia)
**Rola:** auth, JWT, vault, RBAC, audit signing, bootstrap, secrets, circuit breaker
**Pakiety:** `security/` (18 modułów = 8 kanon + 10 rozszerzeń)
**Frontend:** `/auth`, `/secrets`, `/security-scan`, `/circuits`, `/roles`
**Stan:** ✅ dojrzałe + duża ekspansja (+10). Zgodnie z decyzją użytkownika: do weryfikacji i ew. deduplikacji w ETAP 5 **JAKO OSTATNI ELEMENT PRZED WDROŻENIEM** (żeby testy nie były spowalniane).

### 🟫 WARSTWA 7 — OPERATOR CONSOLE & SURFACE
**Rola:** UI, dashboard, WebSocket real-time, notification engine
**Pakiety:** `surface/` (3 manifesty), `api/workspace_ws_routes`, `api/notification_routes`, cały frontend
**Frontend:** wszystkie 57 stron + HumanGatePanel
**Stan:** ⚠️ PARTIAL — frontend bogaty (55 ścieżek), ale:
- Brak dynamicznych route'ów po ID (wszystko drawer/modal)
- Brak Event Replay, Command Bus TWO_PHASE, Yjs canvas (spec V5 = 0% zintegrowany)
- Mobile = 0%
- Human Gate UI to Canon Book flow, nie risk-based approval queue

---

## 4. Warstwy DODATKOWE (poza 7-warstwowym kanonem)

### ⬛ WARSTWA LAB (eksperymentalna, nie ruszać)
**Pakiety:** `cellular/` (7), `sdr/` (5), `vps/` (1), `container/` (1), `devices/artifact_deployer`
**Status:** świadome rozszerzenie, opisać funkcjonalność, nie ruszać. Używa własnych routerów (`cellular_routes.py`, `sdr_routes.py`, `vps_routes.py`, `container_routes.py`).

### ⬜ WARSTWA FUNDING (nowa produkcyjna)
**Pakiety:** `funding_autopilot/` (config, permissions, routes, schemas, service, store)
**Frontend:** `/funding`, `/projects`
**Status:** w pełni funkcjonalny — dotyczy pozyskiwania dotacji/grantów. Nie był w Księdze 65, ale aktywny i używany.

### ⬜ WARSTWA OBSERVABILITY (rozszerzenie)
**Pakiety:** `observability/`, `monitoring/` (4)
**Frontend:** `/observability`, `/health`, `/anomalies`, `/performance`, `/sla`, `/events`
**Status:** cross-cutting concern poza oryginalnymi 6/7 warstwami.

### ⬜ WARSTWA INFRA (transport/adaptery)
**Pakiety:** `db/`, `grpc/`, `grpc_stubs/`, `api/` (transport layer)
**Status:** infrastruktura nie mapuje się na żadną warstwę biznesową.

---

## 5. Mapowanie 7 warstw DISTRIBUTED BUILD na stan rzeczywisty

| Warstwa DB | Realizacja w kodzie | Stan |
|---|---|---|
| **Canon** | `contracts/` + `core/contract_registry` + `core/manifest_loader` | ✅ dojrzały |
| **Planning** | `cognitive/planner`, `cognitive/reasoner`, `cognitive/idea_vault`, `pipeline/state_machine` | ✅ dojrzały |
| **Coordination** | `worker/registry`, `execution/*`, `pipeline/controller` | ✅ dojrzały |
| **Worker** | `worker/` (registry, monitor, assignments, topology, build) | ✅ dojrzały |
| **Integration** | `integration/drift_detector`, `core/integration`, `core/bundle_assembler` | ✅ dojrzały |
| **Governance** | `governance/*`, `core/decision_gate_engine`, `core/evidence_spine` | ⚠️ **drift do Human Gate**: obecne D0-D5 ≠ risk-based policy engine 12 osi |
| **Operator** | frontend + `surface/*` + `api/workspace_ws_routes` | ⚠️ PARTIAL: brak Event Replay, brak Mobile, brak PRO/SIMPLE switch |

---

## 6. Krytyczne rozjazdy (architektoniczne)

### R1. Warstwa Operator jest niedorozwinięta
- UX = płaskie listy + drawery (brak głębokich widoków detali)
- Brak `[id]` route'ów dynamicznych
- Brak live collaboration (Yjs)
- Brak event replay
- Brak Command Bus TWO_PHASE
- Mobile = 0%
- **Implikacja:** AEIS nie ma jeszcze prawdziwej "wieży kontroli" — to duży strumień pracy

### R2. Warstwa Governance ma 2 równoległe implementacje
- **A)** D0-D5 Decision Ladder + Evidence Pack (rozwinięte, działa, audit-ready)
- **B)** Human Gate wg spec (5 ról, 12 osi, risk-based, policy engine) — **praktycznie nie istnieje**

Nie są alternatywami — są komplementarne. **Decision Ladder D0-D5 jest WEWNĄTRZ Human Gate** (jako jeden z mechanizmów klasyfikacji). Ale architektura obecna myli je — `governance/human_gate.py` to odcinek D3+ approval, nie risk-based orchestrator.

### R3. Klasyfikacja modułów — domena vs warstwa vs klasa Księgi
Manifesty używają prefixu domeny (np. `security.*`). Warstwy wg Księgi to klasy A-L. Pakiety Python to trzecie cięcie. **Trzy różne taksonomie** — kandydat do ujednolicenia w nowej Księdze (ETAP 7).

### R4. Monitoring + Observability — rozmyta granica
`monitoring/` (4 manifesty) vs `observability/` (bez manifestów, kod w pakiecie) — nakładające się odpowiedzialności. Kandydat do konsolidacji.

### R5. Warstwa Canon nie obejmuje Kernel runtime
Kernel (`core/event_bus`, `core/hot_swap`, `core/rollback_manager`) to **runtime**, a Canon to **kontrakty** (statyczne). Obecnie są zmieszane w `core/`. W Distributed Build to 2 oddzielne warstwy.

---

## 7. Propozycja 8-warstwowej architektury dla nowej Księgi (2026)

Na podstawie obserwowanej rzeczywistości proponuję:

```
┌─────────────────────────────────────────────────────────────┐
│  L8 · OPERATOR CONSOLE (PRO + SIMPLE) + MOBILE AEIS         │
│       wieża kontroli + decyzje + konfiguracja polityk       │
├─────────────────────────────────────────────────────────────┤
│  L7 · HUMAN GATE ORCHESTRATOR (risk-based, 5 ról, 12 osi)   │
│       Decision Intake → Classifier → Policy → Queue → Batch │
│       → Delegation → Continuity → Graph → Audit → Mobile    │
├─────────────────────────────────────────────────────────────┤
│  L6 · GOVERNANCE & COMPLIANCE                                │
│       D0-D5 ladder, Evidence Spine, Audit Trail, Roles, SLO │
├─────────────────────────────────────────────────────────────┤
│  L5 · SECURITY & SECRETS                                     │
│       Auth, Vault, Circuit Breaker, Hardened Audit, RBAC    │
├─────────────────────────────────────────────────────────────┤
│  L4 · EXECUTION & WORKERS (Distributed Build)                │
│       Workers, Assignments, Topology, Bundle, Environment   │
├─────────────────────────────────────────────────────────────┤
│  L3 · COGNITIVE & PLANNING                                   │
│       Agents, Planner, Reasoner, Models, Idea Vault, Skills │
├─────────────────────────────────────────────────────────────┤
│  L2 · MEMORY & SELF-EVOLUTION                                │
│       Memory, Knowledge, AEIS Self-*, Adaptation, Rebuild   │
├─────────────────────────────────────────────────────────────┤
│  L1 · KERNEL RUNTIME                                         │
│       Event Bus, Lifecycle, Hot Swap, Rollback, Snapshot    │
├─────────────────────────────────────────────────────────────┤
│  L0 · CANON (źródło prawdy kontraktów)                      │
│       Manifests, Proto, Registry, Version Manager, Freeze   │
└─────────────────────────────────────────────────────────────┘

 Poprzeczne: OBSERVABILITY, MONITORING, QUALITY, EFFICIENCY
 Peryferyjne: LAB (cellular/sdr/vps/container), FUNDING, DEVICES
```

**Uzasadnienie:**
- **Human Gate jako L7 (własna warstwa)** — nie jest podrzędne Governance, tylko orchestruje ją
- **Canon L0 + Kernel L1** oddzielone — kontrakty statyczne vs runtime
- **Operator L8** — frontend + Mobile jako osobny layer z przełącznikiem PRO/SIMPLE
- **Memory + Self-Evolution jako L2** — są blisko danych i niżej niż Cognitive w hierarchii

---

## 8. Tabela porównawcza — Księga vs Rzeczywistość vs Propozycja

| Aspekt | Księga 65 (Model A-C) | Rzeczywistość (119) | Propozycja 2026 |
|---|---|---|---|
| Liczba warstw | 6 (A) / 7 (B) / 13 klas (C) | ~7 de facto + 4 poprzeczne | 9 (8 pionowych + 4 poprzeczne) |
| Human Gate | element Governance | fragment 367 LoC | **własna warstwa L7** |
| Canon vs Runtime | zmieszane w Kernel | zmieszane w core/ | **L0 + L1 oddzielone** |
| Mobile | Operator Mobile (12 submodułów) | 0% | **L8 (backlog)** |
| Observability | brak | rozwinięte | poprzeczne |
| Quality | klasa L | jest | poprzeczne |
| LAB (cellular/sdr) | brak | 15 modułów | peryferyjne |
| Funding | brak | pełny moduł | peryferyjne (produkcyjne) |

---

## 9. Dalsze kroki

**ETAP 2 czeka na zwrot z 4 subagentów:**
- P1: Ocena worktree `serene-mccarthy` → decyzja merge/rebuild/drop
- P2: Analiza proto → wybór generacji
- P3: *(rozwiązane decyzją użytkownika: security później, ETAP 5 dedup)*
- P4: Dashboard V5 vs current → propozycja PRO/SIMPLE
- P5: Plans 07/09/10 → wyciągnięcie specyfikacji

Po zwrocie → konsolidacja → ETAP 3 (audyt funkcjonalny z Human Gate Framework per moduł).
