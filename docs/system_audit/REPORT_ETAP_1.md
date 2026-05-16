# RAPORT ETAP 1 — Pełna inwentaryzacja SYLION AEIS

**Data:** 2026-04-24
**Zakres:** backend, frontend, skills, proto, plans, infra, tests, Human Gate, mobile, addony
**Źródła prawdy:** kod, manifesty, routery, testy (nie dokumentacja)

---

## 1. Liczby systemu

| Obszar | Stan |
|---|---|
| Manifestów modułów (`sylion/contracts/manifests/*.json`) | **119** |
| Top-level pakietów Python (`sylion/`) | 33 |
| Plików route FastAPI (`*_routes.py`) | ~80 |
| Obiektów tras (`app.routes`) | **1433** |
| Unikalnych szablonów ścieżek OpenAPI | **1170** |
| Schematów komponentów OpenAPI | 250 |
| Stron Next.js (`page.tsx`) | **57** |
| Layoutów frontend | 3 |
| Komponentów React | 39 |
| Hooków API (`lib/api/hooks.ts`) | **164** |
| Plików proto (kanon `contracts/proto/`) | 15 (~85 services, ~483 rpc) |
| Plików proto (legacy `proto/`) | 6 (drift) |
| Testy backendu (`tests/`) | **292 pliki** (płasko, bez kategorii) |
| Testy infra (`tests/` root) | 7 |

## 2. Pokrycie kanonu (Księga v3.5)

| Metryka | Wartość |
|---|---|
| Moduły planowane w Księdze | 65 |
| Zaimplementowane na backendzie | **64/65** (98%) |
| Brak 1 modułu kanonicznego | `skills.demand_signal` w Księdze figuruje jako `aeis.demand_signal` — nazwa domeny przesunięta, kod jest |
| Moduły POZA Księgą (nowe) | **55** |
| W tym laboratoryjne (nie ruszać) | 15 (`cellular.* ×7`, `sdr.* ×5`, `vps ×1`, `container ×1`, `devices.artifact_deployer ×1`) |
| Netto rozszerzeń produkcyjnych | **40** |
| Devices Addon (klasy M/N/O) | +16 planowanych, niezmergowane, 10 deklarowanych skilli |

## 3. Największe drifty (najbardziej krytyczne odkrycia)

### 🔴 DRIFT #1 — Human Gate Orchestrator (największa luka systemu)

Specyfikacja (z `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`):
- Orchestrator: **13 submodułów** (Intake, Classifier, Autonomy Policy Engine, Decision Queue P0-P4, Batch Approval, Delegation, Execution Continuity, Decision Dependency Graph, Notification Routing, Audit Trail, Risk-Based Auto, SLA, Learning)
- Operator Mobile: **12 submodułów** (push, deep link, biometria, device binding, approval tokens, offline)
- Pixel Live Test Mode: **15 testów ADB**

Rzeczywistość:
- **Orchestrator**: 0 IMPLEMENTED / 5 PARTIAL / 8 MISSING
- **Operator Mobile**: 0 IMPLEMENTED / 3 PARTIAL (web-only) / 9 MISSING
- **Pixel Live Test**: 0/15
- Priorytety P0-P4: nieimplementowane (kolumna `priority TEXT 'normal'` — martwa)
- Autonomy Levels 0-5: istnieje INNY model (5-stage rollout observe/propose/sandbox/limited/full — Masterplan R7), semantycznie niezgodny ze spec
- Secure Approval Layer (biometria, device binding, signatures): MISSING
- Aplikacja mobilna (Android/iOS/RN): **0% implementacji**

Istnieje tylko:
- `sylion/governance/human_gate.py` (367 linii — create/submit/escalate/list/stats) — solidna baza do rozszerzenia
- `HumanGatePanel.tsx` (802 linie) — ale obsługuje **Canon Book kickoff decision tree**, nie approve/reject/defer/delegate

### 🟡 ZNALEZISKO KRYTYCZNE — istnieje niezmergowany worktree

W `.claude/worktrees/serene-mccarthy-6bb664/` istnieją **cząstkowe implementacje**:
- `sylion/decision_orchestrator/` — batch_compiler, delegation_service, timeout_handler, dependency_graph, notification_router
- `sylion/operator_mobile/` — biometric_challenge, emergency_alerts, pixel_live_test, operator_digest

**NIE SĄ na głównej gałęzi.** To jest decyzja do podjęcia:
- **A)** merge do main (zbadać jakość, uzupełnić, zintegrować)
- **B)** rebuild od nowa (użyć jako referencji)
- **C)** porzucić i zacząć świeżo wg spec

### 🔴 DRIFT #2 — Mobile AEIS (kompletny brak)

Brak: `manifest.json`, service worker, `next-pwa`, komponenty Mobile*, ścieżki `/m/`, kod Android/iOS/RN/Expo/Capacitor.
Wynik wyszukiwania "Mobile" we frontendzie = 3 dopasowania, wszystkie to hamburger menu na landing page.

**"AEIS Operator Mobile" + "Pixel Live Test Mode" = 0% implementacji.**

### 🔴 DRIFT #3 — Dashboard V5 Package niezintegrowany

`SYLION_Dashboard_V5_ClaudeCode_Package/` to paczka specyfikacji (4 spec MD + 1 skill manifest + README) — **0 kodu zintegrowanego**.
Kluczowe wymagania **nie są zaimplementowane**:
- Event-sourced architecture
- Command Bus TWO_PHASE commit
- Process Canvas Yjs + tldraw
- Resumable multipart upload
- Event replay UI

Bieżący frontend: brak `yjs`, `tldraw`, `y-websocket` w `package.json`. `/gates` używa single-phase POST, `SnapshotDiffViewer` = prosty diff, nie full replay.

### 🟡 DRIFT #4 — Proto contracts: dwie generacje

- Kanon: `src/sylion-pipeline/sylion/contracts/proto/` (15 plików, ~85 services, ~483 rpc)
- Legacy: `proto/sylion_*.proto` (6 plików) — duplikat / stary kształt

Ryzyko: kod generowany z obu źródeł może tworzyć niespójne kontrakty.

### 🟡 DRIFT #5 — Plans 01-20 częściowe pokrycie

- 17/20 planów ma artefakty kodowe
- **Plans 07, 09, 10** — brak potwierdzonych odniesień w evidence
- Brak kanonicznych plików `PLAN_XX.md` — tylko PDF Masterplan
- Brak skill.yaml dla skilli (rejestrowane w SQLite, nie w plikach)

### 🟢 DRIFT #6 — Duże rozrosty domen

| Domena | Księga | Kod | Nadmiar |
|---|---|---|---|
| security | 8 | 18 | +10 (audit_query, audit_trail_aggregator, bootstrap_flow, evidence_signer, hardened_audit, key_vault, profile_swap, profiles, security_audit, security_profiles) |
| core | 13 | 15 | +2 |
| cognitive | 7 | 13 | +6 |
| governance | 7 | 10 | +3 |
| execution | 6 | 8 | +2 |
| monitoring | ? | 4 | nowe |

## 4. Obszary dojrzałe (co działa dobrze)

- **Governance flow D0-D5**: `DecisionLadder` + `DecisionGateEngine` + `EvidenceSpine` + `DecisionAudit` — solidna implementacja, ale to jest **inny typ** governance niż spec Human Gate
- **NotificationEngine** — pełny system kanałowy (brak tylko mobile/SMS)
- **AutonomyController + SandboxExecutor + LimitedProdExecutor** — dobra infrastruktura pod execution continuity
- **Router konsolowy** — `client.ts` 1400 linii, ~400 metod REST, WebSocket na `/ws/workspace`
- **64/65 modułów Księgi obecnych** — 98% pokrycia planu

## 5. Moduły laboratoryjne (opis bez instrukcji)

Zgodnie z decyzją użytkownika — opisujemy funkcjonalność, nie ruszamy:

| Domena | Moduły | Funkcjonalność (krótko) |
|---|---|---|
| `cellular` | attack_vectors, control_plane, core_network, evidence_writer, ran_lab, rf_isolation, ue_emulator | Laboratorium RAN / core network / UE — emulacja, testy izolacji RF, wektory ataków, rejestracja dowodów |
| `sdr` | (5 modułów) | Software Defined Radio — laboratorium radia programowalnego |
| `vps` | (1 moduł) | Orkiestracja VPS Hetzner |
| `container` | docker_manager | Zarządzanie kontenerami lokalnymi |
| `devices.artifact_deployer` | — | Wdrażanie artefaktów na urządzenia fizyczne |

## 6. Wyprodukowane artefakty

- [00_RUNTIME_STARTUP.md](docs/system_audit/00_RUNTIME_STARTUP.md) — jak uruchomić stack
- [00_BASELINE_KANON.md](docs/system_audit/00_BASELINE_KANON.md) — co Księga zakładała
- [01_INVENTORY_BACKEND.md](docs/system_audit/01_INVENTORY_BACKEND.md) — 119 manifestów, tabele
- [01_INVENTORY_FRONTEND.md](docs/system_audit/01_INVENTORY_FRONTEND.md) — 57 stron, hooki, komponenty
- [01_INVENTORY_PERIPHERY.md](docs/system_audit/01_INVENTORY_PERIPHERY.md) — skills/proto/plans/infra/tests
- [01_INVENTORY_HUMAN_GATE.md](docs/system_audit/01_INVENTORY_HUMAN_GATE.md) — audyt spec vs rzeczywistość

---

## 7. Pytania do decyzji przed ETAP 2

### P1. Worktree `serene-mccarthy-6bb664/` z cząstkową implementacją Human Gate
Jak postępujemy:
- **A)** Zbadać tamten worktree, ocenić jakość, zaplanować merge
- **B)** Traktować jako niezaufany, rebuild od zera wg spec
- **C)** Zignorować w audycie (zostawić jako ślepy zaułek)

### P2. Dwie generacje proto (kanon vs legacy)
- **A)** Potwierdzić kanon i usunąć legacy
- **B)** Nie ruszać w audycie, tylko odnotować drift
- **C)** Sprawdzić co z którego jest używane runtime'owo

### P3. Domena `security` ma 18 modułów zamiast 8
10 nowych (audit_query, audit_trail_aggregator, bootstrap_flow, evidence_signer, hardened_audit, key_vault, profile_swap, profiles, security_audit, security_profiles) — czy to:
- **A)** Świadome rozszerzenia (jak cellular/sdr) — zachowaj
- **B)** Sprawdzić czy się duplikują ze sobą i z Księgą (klasyfikacja DUPLICATE w ETAP 5)

### P4. Dashboard V5 Package
- **A)** Merge do głównej branchy jako spec przyszłej ewolucji
- **B)** Traktować jako nieaktualny / porzucony
- **C)** Zaplanować wdrożenie jako duży osobny projekt po audycie

### P5. Plans 07, 09, 10 bez potwierdzonych artefaktów
Czy pamiętasz co miało być w tych planach? Mogę wyciągnąć ze spec, ale chcę potwierdzenie że to rzeczywiście luki, nie fałszywe negatywy.

---

**Gotowy do ETAP 2 (Mapa architektury rzeczywistej vs warstwy kanonu)** — potrzebuję Twoich odpowiedzi P1-P5 (szczególnie P1) żeby wiedzieć jak traktować znaleziska.
