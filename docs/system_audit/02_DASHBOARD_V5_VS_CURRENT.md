# 02 — DASHBOARD V5 vs CURRENT FRONTEND — analiza i rekomendacja PRO + SIMPLE

**Audyt:** ETAP 2 / Dashboard strategy
**Data:** 2026-04-24
**Autor:** Claude (UX + architektura frontendu)
**Tryb:** read-only, bez modyfikacji kodu
**Cel:** zarekomendować strategię dla **dwóch dashboardów — PRO i SIMPLE, z przełącznikiem**.

**Źródła:**
- A) Obecny frontend: `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\` (Next 16.2.4, React 19.2.4, 56 stron, 39 komponentów, 164 hooki, 3 layouty)
- B) Paczka V5: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\` (4 markdown-spec + 1 skill + README, 0 kodu)
- C) Baseline AEIS: `C:\Users\razor\Desktop\pipeline_glm\baseline aeis\` (3 PDF + 1 HTML)
- Referencje: `01_INVENTORY_FRONTEND.md`, `02_HUMAN_GATE_FRAMEWORK.md`

---

## 1. Co proponuje Dashboard V5 — rozkład na czynniki

### 1.1 Struktura paczki (LoC)

| Dokument | LoC | Waga |
|---|---:|---|
| `DASHBOARD_FUNCTIONAL_SPEC.md` | 213 | spec funkcjonalny (14 sekcji) |
| `DASHBOARD_TECHNICAL_SPEC.md` | 627 | spec techniczny (20 sekcji) |
| `DASHBOARD_V5_MERGE_NOTES.md` | 62 | delta vs v4 |
| `DASHBOARD_WORKPLAN_V5.md` | 34 | freeze list + 10 sprintów |
| `SKILL.md` | 156 | reguły implementacyjne |
| **Razem** | **~1092 LoC** | pełnoprawny plan architektury |

### 1.2 Kluczowe koncepty V5 (frozen decisions)

1. **Dashboard = event-sourced control plane** — nie panel metryk, tylko cockpit operacyjny + governance.
2. **Klasa J (Surface) + 7 rozszerzeń** (8 modułów, porty 5801–5807):
   - `console_api` (5801), `console_ui`, `ws_gateway` (5802), `command_bus` (5803),
     `event_sourcing_store` (5804), `artifact_control` (5805), `process_canvas` (5806), `readiness_engine` (5807).
3. **5 trybów pracy**: `INITIAL_SETUP`, `NORMAL`, `INCIDENT`, `REBUILD`, `DEVICE_LAB` (overlay).
4. **Command Bus TWO_PHASE default**, `IMMEDIATE` tylko dla D0–D1 przez policy rule. Każda akcja UI to **intent**, nie naked call.
5. **Process Canvas = Yjs + tldraw**, hybrydowy model (semantic DAG + freeform), **Yjs = source of truth**, SQL = projection only.
6. **Browser upload** = `InitiateUpload` → **signed HTTP / resumable multipart** → `FinalizeUpload` (nigdy gRPC-Web client streaming).
7. **Readiness Engine** — 7 etapów (`IDEA → SCOPE → SKILLS_ASSETS → CANON_GOVERNANCE → TEST_SANDBOX → SHADOW_CUTOVER_READY → ACTIVE_MONITORED`) + deterministic primary + ML advisory.
8. **Event sourcing rigor** — append-only stream, snapshots co 1000 events / 24h, projection rebuild, dead-letter queue, replay na timestamp, read-only historical dashboard.
9. **Static-first UI in prod** (brak SSR dependency) — runtime data tylko przez gRPC-Web / REST shim / WebSocket.
10. **Secrets never enter** event store / Yjs / replay export / evidence payload — tylko `secret_ref`, `masked_preview`, `hash`, `version_id`.
11. **Artifact Control** — 10 rodzajów (PROMPT, SKILL, CANON_PROPOSAL/ACTIVE, POLICY_PACK, EVIDENCE, PROVIDER_MANIFEST, DEVICE_CONFIG, LAB_CAPTURE…), 4 modele mutowalności (IMMUTABLE / VERSIONED_IMMUTABLE / MUTABLE_DRAFT / APPEND_ONLY).
12. **RBAC 12 ról** (viewer, operator, admin, code_optimizer, performance_engineer, memory_auditor, cost_optimizer, external_reviewer, infra_operator, governance_compliance, ai_steward, autonomy_auditor).
13. **Tokenless first setup** localhost-bound, rebind po utworzeniu admina.
14. **Realtime granularity** — presence, projection lag/version, voting states, action lifecycle, cursors Yjs.

### 1.3 Zakres UI proponowany przez V5

13 paneli + 3 workspaces:

| Panele operacyjne | Workspaces |
|---|---|
| Home / Overview | Artifact Control |
| Decision Ladder | Process Canvas |
| Code Health | Initiatives / Readiness |
| Performance | |
| Memory | |
| Cost | |
| Evidence & Governance | |
| Rebuild & Cutover | |
| AEIS Health | |
| Skills & Knowledge | |
| Devices / SDR / Cellular | |
| Integrations & Settings | |
| VPS Providers & Environments | |

Shell: TopBar + Sidebar + Context Drawer + Notification Center + **Command Palette** + Global Search + Mode Indicator + Realtime Health Indicator.

---

## 2. Ocena bieżącego frontendu jako dashboard

### 2.1 Co działa dziś (baseline)

- **56 stron** w `(app)/`, wspólny shell (`AppSidebar`, `TopCommandBar`, `ApiOfflineBanner`).
- **164 hooki** + ~400 metod REST w `client.ts` → bardzo szerokie pokrycie 119 manifestów backendu (1:1 z modułami AEIS).
- **Polling 5–30 s** w większości widoków + jeden WS endpoint (`/ws/workspace`) dla notyfikacji i pipeline runs.
- **Dark console desktop-first**, shadcn/ui + Tailwind 4 + framer-motion + recharts + sonner (toasts).
- `HumanGatePanel` w `/workspace` — jedno miejsce z głęboką logiką: drzewo decyzji, undo/rollback, kickoff projektu, auto-refresh 5 s.

### 2.2 Słabe punkty (UX i arch.)

1. **Brak route'ów dynamicznych** (`/funding/proposals/[id]`). Wszystko to płaskie listy + drawer/modal. → Brak deep-linkowalnych detali, trudne pokazanie "podróży" przez zasób.
2. **Brak `error.tsx` / `loading.tsx` / `global-error.tsx`** — Next 16 fallbacki nie istnieją.
3. **Brak Command Palette** (jest tylko `TopCommandBar` — nie confirm). Globalne wyszukiwanie niezrealizowane.
4. **Brak trybów instancji** (`INITIAL_SETUP` / `INCIDENT` / `REBUILD`) — UI wygląda tak samo niezależnie od kontekstu.
5. **Brak Process Canvas** (Yjs/tldraw nie ma w `package.json`) — brak wizualnej orkiestracji.
6. **Brak event-replay UI** — `SnapshotDiffViewer` to mały diff, nie time-travel dashboard.
7. **Single-phase governance** — `gates/page.tsx` robi `submitHumanReview` jako jeden request, nie two-phase intent lifecycle.
8. **Brak resumable upload** — brak `tus`, `chunked`, `resumable` w repo.
9. **Brak presence / cursors / projection-lag UI** — realtime zatrzymuje się na notyfikacjach.
10. **Human Gate pokrycie = ~15%** spec Orchestrator, 0% Operator Mobile (ref. `01_INVENTORY_HUMAN_GATE.md`).

### 2.3 Mapowanie obecnych stron na tier SIMPLE vs PRO

**SIMPLE tier** — codzienny monitoring + approval flow (powinny zostać prawie w obecnej formie, ewentualnie tylko uproszczone):

| Strona | Dlaczego SIMPLE |
|---|---|
| `/overview` | dashboard startowy, wysokopoziomowe KPI |
| `/idea-vault` | prosta lista pomysłów + submit |
| `/health` | zielone/czerwone światełka modułów |
| `/notifications` | inbox dla operatora |
| `/gates` | zatwierdź/odrzuć — ma tylko pokazywać kluczowe pending items z CTA "Approve/Reject" |
| `/workspace` (skrócony) | pipeline run + Human Gate choice |
| `/evidence` | tylko ostatnie evidence packs, bez deep dive |
| `/costs` / `/budget` | miesięczne wykresy, alerty |
| `/skills` | lista skills + run |
| `/book` | golden sets + simple run |
| `/performance` | sparklines + topowy leaderboard |

**PRO tier** — głęboki widok, event replay, debug, governance, infra:

| Strona | Dlaczego PRO |
|---|---|
| `/pipeline`, `/workspace` (full) | multi-model discussion, variant selection, source of truth |
| `/governance`, `/decisions`, `/gates` (full) | cascade, D0–D5, council voting, policy edit |
| `/evidence-spine`, `/audit` | full chain, tamper-check, verify |
| `/modules`, `/contracts`, `/bundles` | proto-contracts, freeze, diff |
| `/observability`, `/events`, `/anomalies`, `/drift` | logi/metrics/traces/event backbone |
| `/rebuild`, `/lifecycle`, `/build-state`, `/builds` | shadow/cutover/rollback + LPW |
| `/deploy`, `/environments`, `/workers`, `/autoscaler`, `/capacity` | infra orchestration |
| `/sdr`, `/cellular`, `/devices` | Device Lab (safety gates) |
| `/secrets`, `/security-scan`, `/roles`, `/auth`, `/auth providers` | security surface |
| `/evaluator`, `/quality`, `/golden-tests`, `/regressions` | quality deep dive |
| `/autonomy`, `/risk`, `/sla`, `/healing`, `/circuits` | autonomy policy engine |
| `/funding`, `/projects` | portfolio / finanse (PRO dla finance role) |
| `/connectors`, `/integrations`, `/settings` (full) | integration edit |

---

## 3. Ocena Dashboard V5 spec

### 3.1 Spójność

**TAK, spójny.** V5 eliminuje sprzeczności v4 (static export vs middleware vs SSR — teraz static-first tylko). Merge notes (§3–§5) jawnie wskazują co było zepsute i jak naprawione. Kontrakty między 8 modułami zdefiniowane przez porty, event subjects, envelope fields.

### 3.2 Czy uwzględnia Human Gate?

**Częściowo — na poziomie mechaniki (Command Bus TWO_PHASE), NIE na poziomie UX/kolejek.** V5 zamraża intent lifecycle (`submitted → classified → pending_verdict → approved/rejected → applying → applied/failed/rolled_back`) i wymaga review dla D2+, Council dla D3+, ale **nie opisuje**:

- kolejek P0–P4 (spec Human Gate Orchestrator moduł 04),
- Batch Approval Engine (moduł 05),
- Delegation Engine (moduł 06),
- Decision SLA / countdown (moduł 11),
- Risk-Based Auto Approval UI (moduł 09),
- Decision Learning (moduł 13).

**Brakuje też Operator Mobile** — V5 zakłada desktop static-first. Spec `AEIS_Global_Operator_Mobile_Human_Gate_Prompt` nie jest zaadresowany.

### 3.3 Ścieżka "pomysł → dyskusja modeli → wybór wariantu → source of truth"

**Częściowo.** V5 opisuje:
- Artifact Control z modelami mutowalności (`MUTABLE_DRAFT` → publish → `VERSIONED_IMMUTABLE` / `IMMUTABLE`) — ok dla prompts/skills.
- Readiness lifecycle `IDEA → SCOPE → … → ACTIVE_MONITORED` — ok dla inicjatyw.
- Canon flow (proposal → D5 + Council 4/4 → CANON_ACTIVE) — ok dla kanonu.

**Nie opisuje** explicite multi-model discussion UI (Council voting z chat-em? porównanie wariantów side-by-side? diff sugestii?). To istnieje w bieżącym kodzie (`components/workspace/CouncilPanel.tsx`, `AI Workspace`) i paradoksalnie obecny front ma więcej w tym wątku niż V5 spec.

### 3.4 12 osi polityk Human Gate

V5 **adresuje pośrednio**:

| Oś | V5 adresuje? |
|---|---|
| 1. Ryzyko (D0–D5) | TAK — `decision_class` w envelope |
| 2. Typ działania | TAK — `action_type`, `target_type` |
| 3. Środowisko | TAK — `instance_id` + dev-light/staging/prod profile |
| 4. Moduł | TAK — `target_type` |
| 5. Operator | TAK — `actor_id`, `actor_role` (12 ról RBAC) |
| 6. Koszt | CZĘŚCIOWO — brak progów $$$ w envelope |
| 7. Liczba zasobów | NIE — brak thresholds na Docker/VPS/API |
| 8. Tryb wykonania | CZĘŚCIOWO — `execution_policy` (IMMEDIATE/TWO_PHASE) tylko |
| 9. Etap procesu | TAK — Readiness stages |
| 10. Blocking | CZĘŚCIOWO — implicit w saga, brak flagi |
| 11. Grupowanie | NIE — brak batch approval w V5 |
| 12. Timeout / Eskalacja | CZĘŚCIOWO — `expires_at`, brak escalation chain |

**Wynik: ~7/12 osi explicite, 5/12 trzeba dodać na górze V5.**

### 3.5 Czy V5 jest ładny / przyjazny czy zbyt inżynieryjny?

**Zbyt inżynieryjny.** V5 to spec "jak zbudować cockpit event-sourced", nie brief UX. Brakuje:
- makiet / wireframe,
- information architecture (nawigacja per rola),
- persona journeys,
- stylingu / tokenów,
- empty states, onboarding,
- error patterns,
- mobile / responsive adaptation,
- A11y (WCAG).

Spec jest świetny jako **blueprint backendu surface** i kontrakt z implementerami, ale **nie zastąpi Figmy ani design systemu**. Kierowany do dewelopera-architekta, nie do operatora-użytkownika.

---

## 4. Porównanie w tabeli

| Funkcjonalność | Current (kod na żywo) | V5 (spec) | Zwycięzca |
|---|---|---|---|
| Szerokość pokrycia backendu | **56 stron, 164 hooki, ~400 REST calls**, ~95% modułów | 13 paneli + 3 workspaces (abstrakcyjnie, bez listy per-moduł) | **Current** (realnie działa) |
| Human Gate frontend | `HumanGatePanel` (~800 LoC) — drzewo, undo, rollback, kickoff; `/gates` płaska lista; **~15% pokrycia** spec Orchestrator | Intent lifecycle + TWO_PHASE + Council, bez kolejek P0–P4 / batch / delegation / SLA | **Tie** — oba niepełne, razem się uzupełniają |
| Event replay / time-travel | `SnapshotDiffViewer` (diff snapshotu decyzji), brak replay | Pełny event sourcing, snapshots, projection rebuild, read-only historical dashboard, dead-letter | **V5** |
| Real-time collaboration | `useWorkspaceWS` (1 endpoint), poll+WS dla notyfikacji; brak presence/cursors | WS Gateway, Yjs CRDT dla canvasu, presence, cursors, projection lag/version | **V5** |
| Process Canvas (wizualna orkiestracja) | **brak** (Yjs/tldraw nie istnieją) | Yjs + tldraw, DAG + freeform, 11 node kinds, 8 edge kinds, validation, export do BPMN/Temporal | **V5** (jedyny ma) |
| Command Bus (intents) | **single-phase** `submitHumanReview`, bezpośrednie REST calls | TWO_PHASE default, envelope 18 pól, idempotency, outbox, compensating commands | **V5** |
| Artifact Control (upload wszędzie) | Uploady ad-hoc per endpoint (np. `storeAPIKey`), brak unified flow | Unified `InitiateUpload → multipart → Finalize → Publish przez Command Bus`, 10 artifact kinds, 4 mutability models | **V5** |
| Modułowość / skalowalność (1170 ścieżek, 119 manifestów) | 1:1 route-per-moduł, płaskie listy, trudno skalować do 200+ modułów | 13 paneli abstrakcyjnych, które **nie mapują 1:1** na 119 manifestów → problem scaleowania w drugą stronę | **Current** (już unosi skalę), ale V5 wygodniejszy konceptualnie |
| UX simplicity (codzienna praca) | 56 stron w sidebarze = "wall of links"; dla operatora przytłaczające | 13 paneli = bardziej skoncentrowany, ale wymaga sub-navigacji wewnątrz | **V5** (dla SIMPLE), **Current** (dla PRO-operator) |
| Tryby instancji (INITIAL_SETUP / INCIDENT / REBUILD / DEVICE_LAB) | brak | 5 trybów z overlay i mode-aware rendering | **V5** |
| First setup wizard | brak tokenless bootstrap z UI flow | tokenless + localhost-bound + wizard 6-krokowy | **V5** |
| Secrets hygiene | częściowe (store/list, bez hard guarantees) | Twarda reguła: secrets nigdy do event store / Yjs / replay / evidence | **V5** |
| Mobile / PWA | **0%** (no manifest, no SW, no RN) | niespecyfikowany — desktop-first | **Tie** (brak obydwu) |
| Design system / styling | shadcn/ui + Tailwind 4, spójne dark theme, animacje | brak warstwy design (nie specyfikuje tokenów) | **Current** |
| Koszt wdrożenia od zera | 0 (już jest) | 20 sprintów (workplan V5) = ~40 tyg. = **~10 miesięcy** | **Current** |
| Dokumentacja / spec | rozproszona w kodzie, 1400-linijkowy `client.ts` | 1092 LoC spec + 10 freeze decisions + sprint plan | **V5** |

**Sumarycznie:** V5 wygrywa 9 kategorii, Current 3, Tie 2. **Ale** "zwycięskie" kategorie V5 to głównie *potencjał na papierze*, "zwycięskie" Current to *działa teraz*.

---

## 5. REKOMENDACJA — Dashboard PRO + SIMPLE

### 5.1 Podział funkcjonalności

#### SIMPLE (codzienny użytek, operator + owner, 80% czasu)

**Cel:** odpowiedzieć na 5 pytań operatora w < 30 s:
1. Czy system żyje? (health summary)
2. Co na mnie czeka? (inbox P0/P1)
3. Ile kosztuje? (dziś / miesiąc)
4. Co ostatnio poszło? (recent decisions)
5. Co zatwierdzam? (approve/reject CTA)

**Ekrany SIMPLE (max 8):**
1. **Home** — zagregowany overview (health dot + top 5 incidents + inbox count + cost today + active runs)
2. **Inbox** — scentralizowana kolejka approvali P0–P4 (zastępuje rozproszone `/gates`, `/notifications`, `/human-gate`)
3. **Pipeline & Ideas** — uproszczony `/workspace` — nowy pomysł + obecny run + Human Gate choice
4. **Costs** — tylko alerty + miesięczne podsumowanie (bez edycji budżetów)
5. **Skills & Books** — uruchom / przeglądaj
6. **Evidence (read-only)** — ostatnie 20 ewidencji
7. **Settings (minimal)** — konto, powiadomienia, przełącznik SIMPLE/PRO
8. **Search / Command Palette** (Cmd-K) — jedno pole do wszystkiego

**Zasady UX SIMPLE:**
- brak boczniaka z 56 linkami — max 8 pozycji + "More in PRO…"
- duże CTA (Approve / Reject / Run / Undo)
- brak technicznego żargonu (projection lag, CRDT, Yjs → ukryte)
- jasny / light theme dopuszczalny (Current jest hardcoded dark)
- mobile-responsive (w przeciwieństwie do PRO)

#### PRO (pełna moc, admin / governance / infra, 20% czasu)

**Wszystko z SIMPLE +** 48 pozostałych stron z Current, reorganizowanych w **V5 panele (13)**:

1. Home/Overview (full telemetry)
2. Decision Ladder (obecny `/decisions` + cascade + D0–D5 filter)
3. Code Health (`/modules`, `/contracts`, `/bundles`, `/drift`)
4. Performance (`/performance`, `/observability`, `/anomalies`, `/circuits`)
5. Memory (`/evidence`, `/evidence-spine`, `/audit`, canon sections)
6. Cost (`/costs`, `/budget`, `/capacity`)
7. Evidence & Governance (`/governance`, `/gates` full, `/evidence-spine`)
8. Rebuild & Cutover (`/rebuild`, `/lifecycle`, `/build-state`, `/builds`)
9. AEIS Health (`/health`, `/healing`, `/sla`, `/risk`)
10. Skills & Knowledge (`/skills`, `/book`, `/golden-tests`, `/quality`, `/evaluator`)
11. Devices / SDR / Cellular (overlay DEVICE_LAB)
12. Integrations & Settings (`/integrations`, `/connectors`, `/secrets`, `/auth`, `/roles`)
13. VPS Providers & Environments (`/environments`, `/deploy`, `/workers`, `/autoscaler`)

**Plus 3 workspaces (z V5):**
- Artifact Control (upload + version + publish + deprecate, unified)
- **Process Canvas (Yjs + tldraw)** — nowy moduł
- Initiatives / Readiness (portfolio board + stage timeline)

**Plus Mode Indicator** (INITIAL_SETUP / NORMAL / INCIDENT / REBUILD / DEVICE_LAB), Command Palette, Replay UI, Presence.

### 5.2 Czy V5 to dobry szablon dla PRO?

**TAK, ale tylko jako architektoniczny blueprint.** V5 zamraża dobrze:
- event sourcing + replay (pod PRO debug / audit),
- Command Bus TWO_PHASE (pod governance-heavy PRO),
- Process Canvas (unikalna wartość, której Current nie ma),
- Artifact Control (unified upload),
- tryby instancji (INCIDENT / REBUILD).

**Czego V5 NIE wystarczy jako szablon PRO:**
- kolejki P0–P4 + SLA + batch approval → **dokleić z Human Gate Orchestrator spec**,
- design tokens / component library → **zostawić z Current** (shadcn + Tailwind 4),
- 12 osi polityk → **5/12 trzeba dolepić** (koszt, zasoby, blocking, grouping, escalation).

### 5.3 Czy obecny frontend to dobra baza dla SIMPLE?

**TAK, pod warunkiem ostrej kuracji.** Obecny front:
- ma gotowy shell, shadcn/ui, hooki — fundament,
- ma już `useHealth`, `useProposals`, `useCostSummary`, `useWorkspaceWS` → idealnie pod SIMPLE Home,
- ma `HumanGatePanel` — z którego można wyjąć "choice" flow do SIMPLE Inbox.

**Ale trzeba:**
- usunąć 48 stron z sidebara SIMPLE (zostawić w PRO),
- dodać światły motyw (optional),
- dodać Command Palette (Cmd-K),
- dodać centralny Inbox (agreguje gates + notifications + human-gate),
- dodać route grupę `(simple)/` obok istniejącej `(app)/`.

### 5.4 Projektowanie przełącznika SIMPLE ↔ PRO

**Rekomendacja: hybryda trzech mechanizmów, z jasnym priorytetem.**

| Warstwa | Zasada | Persistence |
|---|---|---|
| 1. **Default per rola RBAC** | `viewer`, `operator` → SIMPLE; `admin`, `code_optimizer`, `performance_engineer`, `memory_auditor`, `cost_optimizer`, `external_reviewer`, `infra_operator`, `governance_compliance`, `ai_steward`, `autonomy_auditor` → PRO | backend-side (role claim) |
| 2. **User override** | przełącznik w profile settings — operator może wymusić PRO, admin może wymusić SIMPLE | `localStorage` + `user_preferences` table |
| 3. **Per-session mode** | podczas `INCIDENT` mode — wymuś PRO (nawet dla SIMPLE usera) i pokaż banner "Incident mode active, all tools unlocked" | auto, not persisted |

**Przełącznik UI:**
- w TopBar, prawy róg, ikona `Zap` (PRO) / `Circle` (SIMPLE) z tooltipem,
- `Cmd+Shift+P` → toggle,
- zmiana trybu = soft reload (nie twardy refresh) — routing zachowuje best-effort (mapowanie URL SIMPLE↔PRO).

**Route architecture:**
```
src/app/
  (app)/              ← PRO (obecne 56 stron)
  (simple)/           ← NEW: 8 ekranów, własny layout
  (marketing)/        ← landing, bez zmian
  (setup)/            ← NEW: INITIAL_SETUP wizard
  layout.tsx
middleware.ts          ← cienki: czyta user_pref + role, redirect /overview → /simple/home albo /pro/overview
```

### 5.5 Którą ścieżkę wybrać — A / B / C?

#### Opcja A — rozbuduj obecny (PRO+SIMPLE jako nakładki na Current)

- **Koszt:** 3–5 sprintów (SIMPLE: ~2 sprinty, Process Canvas: +2 sprinty, Command Bus refactor: +1)
- **Ryzyko:** niskie — fundament działa, iteracyjne dodawanie
- **Ograniczenie:** architektura pozostaje polling-first, nie event-sourced. Event replay i TWO_PHASE będą dolepione, nie natywne.

#### Opcja B — V5 jako PRO + Current jako SIMPLE (koegzystencja)

- **Koszt:** 10–15 sprintów (V5 PRO: 15 sprintów wg workplan, można zrównoleglić SIMPLE z Current w 3 sprintach)
- **Ryzyko:** średnie — dwa deploymenty, dwa URL, dwie codebase tymczasowo. Migracja stopniowa modułu po module.
- **Plus:** V5 powstaje na czysto, bez kompromisów; SIMPLE działa od razu dla 80% user stories.
- **Minus:** dryf — 119 manifestów trzeba zmapować w V5 (13 paneli nie wystarczy), 1170 ścieżek REST trzeba opakować w Command Bus.

#### Opcja C — rebuild obu od nowa wspólnym design systemem

- **Koszt:** 20+ sprintów = **~10 miesięcy**
- **Ryzyko:** wysokie — porzucenie 56 działających stron, regresje, długi time-to-market
- **Plus:** najczystsze, wspólne tokens, jedna codebase
- **Minus:** w tym czasie system AEIS rośnie — specyfikacja dryftuje, wymaga ciągłej re-synchronizacji

#### REKOMENDACJA: **Hybryda A + B — "Progressive V5 on Current foundation"**

**Uzasadnienie:**

1. **Zachowujemy 100% obecnego frontu** jako warstwę PRO — 56 stron dalej żyje pod `(app)/`. Koszt utrzymania zerowy (już jest). To **de-risk**: nawet jeśli V5 się opóźni, operatorzy mają co robić.
2. **Dobudowujemy SIMPLE** jako nową route group `(simple)/` — **2 sprinty**. Niski koszt, wysoka wartość (codzienny użytek 80% czasu).
3. **Wprowadzamy Command Bus + Event Store jako backend** (V5 moduły 5803+5804) — **3–4 sprinty backend**. Frontend Current może *opcjonalnie* przełączać pojedyncze akcje na intent submission (np. `gates/submitHumanReview` → Command Bus wrapper). Backward-compat.
4. **Process Canvas + Artifact Control + Readiness Engine** — **dokładnie wg V5 spec** jako **nowe panele PRO**, nie refaktor istniejących — **4–6 sprintów**.
5. **Replay UI + Presence** — **2 sprinty** po gotowym event store.
6. **12 osi polityk Human Gate + kolejki P0–P4 + SLA** — **dokleić na górze V5 Command Bus** jako osobny panel Inbox (dzielony przez SIMPLE i PRO) — **2 sprinty**.

**Razem: 13–16 sprintów** (vs. 20 dla czystego V5 od zera), z działającą SIMPLE po **2 sprintach** i pierwszymi PRO bonusami (Canvas, Replay) po **6–8 sprintach**.

**Harmonogram:**

| Sprint | Deliverable |
|---|---|
| 1–2 | SIMPLE shell + Home + Inbox + Costs + Pipeline (routing `(simple)/`, przełącznik, Command Palette) |
| 3–4 | Command Bus backend + Event Store backend (V5 moduły 5803+5804) |
| 5–6 | Wrapowanie istniejących akcji w intenty (gates, governance, human-gate) |
| 7–8 | Artifact Control (unified upload) — nowy panel PRO |
| 9–10 | Process Canvas (Yjs + tldraw) — nowy workspace PRO |
| 11–12 | Readiness Engine + Initiatives workspace PRO |
| 13–14 | Replay UI + Presence + Projection-lag indicator PRO |
| 15–16 | Human Gate 12 osi + P0–P4 queues + SLA + batch approval |

---

## 6. Screenshots-friendly ekrany (ETAP 7 — Księga)

Dla przyszłej Księgi AEIS rekomenduję screenshoty tych ekranów jako **najbardziej reprezentatywne**:

**Z SIMPLE (po wdrożeniu):**
1. `/simple/home` — agregat 5 odpowiedzi + dot status
2. `/simple/inbox` — pending approvals z P0–P4
3. `/simple/pipeline` — Human Gate choice dialog

**Z Current (PRO, już działają):**
4. `/workspace` — `HumanGatePanel` z drzewem decyzji (najbogatszy UI w repo)
5. `/overview` — pipeline runs + decision timeline
6. `/governance` — compliance + policies + proposals (3-column layout)
7. `/decisions` — `CascadeTree` + `DecisionTimeline` + `SnapshotDiffViewer` (unikalne UI)
8. `/evidence-spine` — verify chain + spine entries
9. `/audit` — `verifyAuditChain` + tamper check
10. `/rebuild` — shadow/cutover/rollback (klasa Rebuildability)
11. `/observability` — logs + metrics + traces (3 tabs)
12. `/modules` — 119 manifestów w jednej liście z detail drawer
13. `/cellular` — RAN + Core + UE (klasa O, unikalne)
14. `/sdr` — captures + analyses (klasa N, unikalne)
15. `/autonomy` — stages + self-observation (filar Autonomia pod Kanonem)

**Z przyszłego PRO V5:**
16. Process Canvas (Yjs) — hybryda DAG + freeform z presence
17. Replay UI — slider timestamp + snapshot render
18. Readiness portfolio board — 7 etapów × N inicjatyw

**Uwagi do robienia screenshotów:**
- Current front to dark console — wymaga backendu pod `127.0.0.1:8000`. Jeśli backend down → pojawi się `ApiOfflineBanner` + mock data (są zaimplementowane w `lib/data/mock.ts`).
- Brak `loading.tsx` → pierwsze renderowanie może pokazać pusty stan. Zaplanować wait dla hooks.
- Najpiękniejsze wizualnie: `/overview`, `/decisions` (dzięki `framer-motion` + `recharts`), `/workspace` (bogata zawartość).

---

## 7. Podsumowanie decyzji

| Pytanie | Odpowiedź |
|---|---|
| Czy V5 to dobry szablon dla PRO? | **TAK jako blueprint architektury backendu surface + nowych paneli (Canvas, Artifact Control, Replay)**. Nie dla całego UI — 56 obecnych stron mapuje się 1:1 na 119 manifestów i trzeba je zachować. |
| Czy obecny front to dobra baza dla SIMPLE? | **TAK po kuracji** — użyć hooków `useHealth`, `useProposals`, `useCostSummary`, `HumanGatePanel` w nowej route group `(simple)/`. |
| Przełącznik? | **3-warstwowy**: default per rola → user override → INCIDENT auto-lock na PRO. Toggle `Cmd+Shift+P` w TopBar. |
| Ścieżka? | **Hybryda A+B** — zachować Current PRO, dobudować SIMPLE (2 sprinty), progressively dolepiać V5 moduły (Command Bus, Event Store, Canvas, Replay) przez 13–16 sprintów. |
| Główne ryzyko? | V5 ma 7/12 osi Human Gate — trzeba dolepić kolejki P0–P4, batch, delegation, SLA, escalation z spec `AEIS_Global_Operator_Mobile_Human_Gate_Prompt`. Mobile = oddzielny track. |
| Koszt? | ~13–16 sprintów (~6–8 miesięcy) vs. 20 sprintów dla czystego V5 od zera. SIMPLE użyteczne po **2 sprintach**. |

**Finalny werdykt:** Nie burzyć tego co działa, nie wdrażać V5 1:1 jako zamiennika. Traktować V5 jako **architektoniczny spec 8 modułów klasy J+**, a UX jako **dwuwarstwowy system (SIMPLE = 8 ekranów nowych, PRO = 56 obecnych + 3 workspaces V5 + Mode Indicator)**. Przełącznik per-rola + per-user override + incident auto-lock.

---

**Pliki referencyjne (absolute paths):**
- Spec V5 funkcjonalny: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\.claude\docs\DASHBOARD_FUNCTIONAL_SPEC.md`
- Spec V5 techniczny: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\.claude\docs\DASHBOARD_TECHNICAL_SPEC.md`
- V5 merge notes: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\.claude\docs\DASHBOARD_V5_MERGE_NOTES.md`
- V5 workplan: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\.claude\docs\DASHBOARD_WORKPLAN_V5.md`
- V5 skill: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\.claude\skills\dashboard-implementation\SKILL.md`
- Frontend inwentarz: `C:\Users\razor\Desktop\pipeline_glm\docs\system_audit\01_INVENTORY_FRONTEND.md`
- Human Gate framework: `C:\Users\razor\Desktop\pipeline_glm\docs\system_audit\02_HUMAN_GATE_FRAMEWORK.md`
- Frontend root: `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\`
- AppSidebar (nawigacja): `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\components\AppSidebar.tsx`
- HumanGatePanel (najbogatszy UI): `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\components\workspace\HumanGatePanel.tsx`
- API client (~1400 LoC): `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\lib\api\client.ts`
