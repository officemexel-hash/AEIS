# AEIS DOCUMENTATION DRIFT MAP

**Data audytu:** 2026-04-24
**Porównanie:** Kod + runtime vs Księga v3.5 vs Masterplan v3.5 vs Distributed Build Architecture

---

## Drift 1: Liczba modułów (65 → 119+)

**Księga / Masterplan:** ~65 modułów w 12 klasach (A-L)

**Rzeczywistość:** 119+ zidentyfikowanych komponentów w ~26 warstwach/domenach

**Wpływ:** Dokumentacja nie nadąża za kodem. Niektóre moduły nie mają manifestów (mimo 115 JSON).

---

## Drift 2: Distributed Build Architecture — implementacja częściowa

| Wymaganie architektoniczne | Stan docelowy | Stan rzeczywisty | Drift |
|---|---|---|---|
| Canon Layer jako osobny runtime | Osobny serwer | Brak — kanon to pliki PDF/MD | BRAK |
| Planning Layer (Decomposition Engine) | Osobny serwer | Moduł w core + aeis.decomposition_engine | PARTIAL |
| Coordination Layer (Assignment Orchestrator) | Osobny serwer | Moduł worker.assignment w monolicie | PARTIAL |
| Worker Runtime na osobnych hostach | 4-5 worker servers | Lokalny SQLite mode, 1 proces | BRAK |
| Integration jako ciągły loop | Osobny serwer integracyjny | Trigger manualny / API-only | BRAK |
| Governance Engine osobno | Osobny serwer | Wbudowany w FastAPI app | PARTIAL |
| Operator Console (Pro) | Dashboard Pro z fleet view | Next.js + legacy dashboard | PARTIAL |
| Event Bus (NATS JetStream) | Rozproszony event bus | SQLite mode default, NATS opcjonalny | BRAK |
| Contract Freeze przed równoległą pracą | Ceremony M0 | Brak formalnej ceremonii | BRAK |
| Postgres 16 + pgvector | Single storage | SQLite default, PG opcjonalne | PARTIAL |

---

## Drift 3: Meta-zasady — zgodność

| Meta-zasada | Stan w kodzie | Ocena |
|---|---|---|
| Rebuildability over Lineage | Rebuild modules istnieją (rebuild/, cutover, CFT) | Zgodne |
| Reversibility & Fidelity | Rollback manager, LPW, CFT runner istnieją | Zgodne |
| Efficiency by Default | 4 moduły efficiency istnieją, ale brak pre-bundle gates G-EFF | Częściowe |
| Autonomy under Canon | Self-evolution modules istnieją, ale brak 5-etapowego rollout | Częściowe |
| Modularity by Contract | 115 manifestów, 22 proto, ale brak buf breaking CI | Częściowe |
| Contract Freeze | freeze_manager istnieje, ale brak formalnego M0 ceremony | Brak |
| Security Profile Abstraction | Profiles dev-light/prod-strict istnieją, ale brak swap M5 | Częściowe |
| Human Gate D4/D5 | human_gate istnieje, ale brak external review integration | Częściowe |

---

## Drift 4: Plan 17 — Operator Console

**Kanon:** 8 paneli operacyjnych, 7 widoków RBAC, kontrakty WebSocket, mockupy ASCII, WCAG AA

**Rzeczywistość:**
- 48 stron Next.js z dark mode
- Komponenty: MetricCard, TelemetryChart, CascadeTree, DecisionTimeline, SnapshotDiffViewer
- Panele workspace: BookGeneratorPanel, ChatPanel, CouncilPanel, HumanGatePanel, PipelineVisualization
- Brak: dedykowanego panelu fleet view z topologią workerów (jest tylko lista)
- Brak: dedykowanego panelu build topology view z wizualizacją grafu
- Brak: mockupów ASCII w UI (są w kodzie jako komentarze / dokumentacja)

---

## Drift 5: Plan 19/20 — Self-Evolution & Demand

**Kanon:** 5 modułów self-*, 3 moduły skills/demand, 5 etapów Autonomy Rollout

**Rzeczywistość:**
- 15 modułów w aeis/ (3x więcej niż kanon)
- Brak formalnego 5-etapowego rollout (observe→propose→sandbox→limited-prod→full-governed)
- Demand signal działa, ale brak G-AEIS-SKILL-01 jako formalnej bramy
- Self-Model Store istnieje w kodzie, brak UI do przeglądania

---

## Drift 6: Niekanoniczne moduły bez dokumentacji

| Moduł | Źródło | Decyzja |
|---|---|---|
| cellular/* | Eksperyment bezpieczeństwa 5G | Do zatwierdzenia przez Council (D3) |
| sdr/* | Eksperyment RF | Do zatwierdzenia przez Council (D3) |
| funding_autopilot/* | Autopilot grantów UE | Do zatwierdzenia przez Council (D3) |
| openhands/* | Integracja zewnętrzna | Do usunięcia lub zatwierdzenia |
| project_mode/* | Tryb projektowy | Do zatwierdzenia przez Council (D2) |
| media/* (audio, stream, webrtc) | Streaming media | Do zatwierdzenia przez Council (D3) |
| infrastructure provisioning (pixel, router, wireguard) | Provisioning | Do zatwierdzenia przez Council (D3) |

---

## Drift 7: API Drift

| Wymaganie kanoniczne | Rzeczywistość | Drift |
|---|---|---|
| gRPC jako główny protokół międzymodułowy | REST API 1170 paths, gRPC jest stub/secondary | REST zdominował gRPC |
| Contract Registry z buf breaking | 22 proto, 40+ stubs, brak CI buf | Brak CI enforcement |
| Event Taxonomy zamrożona | 115 manifestów, ale event taxonomy jest rozproszona | Częściowe |
| Module Lifecycle draft→build→validate→shadow→dual→cutover→stable→deprecated | W kodzie lifecycle_gates, ale brak UI do zarządzania | Częściowe |

---

## Drift 8: Test & Quality Drift

| Wymaganie | Kanon | Rzeczywistość |
|---|---|---|
| Golden set per contract | Wymagane | ~115 manifestów, ale brak auto-golden-set runnera |
| CFT przed każdym bundle | Wymagane | CFT runner istnieje, nie jest uruchamiany automatycznie |
| Pre-bundle gates G-EFF/G-PERF/G-MEM/G-COST | Wymagane v3.3 | Moduły istnieją, brak integracji z bundle assembler |
| Code Optimizer hard veto | Wymagane v3.3 | Moduł code_bloat istnieje, brak veto w bundle flow |
| Performance benchmark D4+ | Wymagane | runtime_perf istnieje, brak integracji z decision gate |
| Cost envelope D4+ | Wymagane | cost_envelope istnieje, brak integracji z decision gate |
