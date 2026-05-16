# W18 Charter — Operator Terminal Plane

> Status: **DRAFT** (2026-04-27)
> D-level: **D4** (proponowana)
> Estymacja solo: **10-14 tygodni**
> Depends on: **W15 G2 (HARD)** dla OSDK persistence; **W14 E12 Agent
> Theater Aggregator** (rozszerzenie); **W11 Adapter Bus** (event emission);
> `sylion.core.event_bus`. **Soft**: W17 G2 dla Federation Map panelu.

## 1. Cel

W18 to **interaktywny terminal-cockpit** dla SYLION — pierwszorzędne UI
operatora, które pokazuje **na żywo co się dzieje w całej federacji
agentów**, z możliwością interwencji w każdym momencie. Mission Control
metafora: każdy agent na każdym hoście emituje linie do live activity
stream, operator widzi wszystko jak xterm + ma command palette typu
slash commands jak w nowoczesnych chat apps + Slack.

Dziś AEIS v1 ma fragmentaryczne UI: `/agent-theater` pokazuje topology
graf, `/test-center` pokazuje guardiany, ale brak unified live stream
gdzie *każda akcja* każdego modelu na każdym hoście jest widoczna w
jednej linii w real-time. Robert wielokrotnie w rozmowach mówił o
"chcę widzieć na żywo co qwen2.5 robi na laptopie i co kimi-k2 robi na
VPS i co claude rozważa lokalnie". W18 to dostarcza.

PDF §7.1: "Pełen interaktywny terminal jako pierwszorzędne UI dla
Roberta — pokazuje na żywo co się dzieje w całej federacji agentów, z
możliwością interwencji w każdym momencie. Cockpit/Mission Control dla
SYLION-a." Format linii (PDF §7.2):

```
14:32:01  W15·OntologyMigrator  qwen2.5:72b@laptop      Reading manifest customer.yaml ✓
14:32:03  W14·FindingClassifier kimi-k2@vps-warsaw      Classified F-127 → D3 (cost $0.04)
14:32:05  W6·PipelineExec       claude-opus-4-7@local   HG REQUIRED: critic review F-127 ⚠
```

W18 oznaczony **D4** (proponowana, PDF §7): user-facing UI, niereversibilne
audit log, ale brak data corruption risk (oddzielony od ontology). Crash
W18 nie powala AEIS — brak terminala = degraded UX, nie outage. Może
startować równolegle z W17 (PDF §7.6).

## 2. Scope IN

- **Live Activity Stream** — main window, każda akcja każdego agenta na
  każdym hoście jako linia.
  - Format linii: `HH:MM:SS  Wxx·Module  model@host  message`
    (PDF §7.2 dosłownie).
  - Streaming: Server-Sent Events (SSE) z backend, xterm.js renderer
    frontend.
  - Coloring: severity (info=white, warn=yellow, error=red), HG required
    (orange highlight), success ticks (green check).
  - Auto-scroll on new line z pause-on-scroll-up zachowanie (jak Chrome
    DevTools console).
  - Buffer: ostatnie 10k linii w pamięci, pełen append-only log w PG
    via W15 OSDK.

- **Filters & Focus** — narrow the firehose.
  - Filter UI: top bar z chip selectors:
    - **Layer**: W1, W2, ..., W18 (multi-select).
    - **Host**: laptop, vps-warsaw, factory-customer-A (multi-select).
    - **Model**: claude, qwen2.5, kimi-k2, gpt-oss (multi-select).
    - **Severity**: info / warn / error / hg-required.
    - **Search**: free text (matches message content).
  - Drill-down per agent: kliknięcie linii → sidebar pokazuje pełen
    context (request payload, response, lineage, kontrakt z W15).
  - Filter persistence: każdy filter set jest URL-shareable
    (`?layer=W14,W15&host=laptop`).
  - Focus mode: `/focus W14·FindingClassifier` zwęża stream do tej jednej
    encji, reszta hidden ale logowana w background.

- **Session Threading** — wiele sesji jednocześnie.
  - Każde "co robisz" to **session** z `id`, `title`, `started_at`,
    `progress` (0-100), `tasks` (list of W6 Execution Pipeline state).
  - UI: lewa kolumna z listą active sessions (lista w 1-click switcher),
    main window stream filtered do aktywnej sesji.
  - Session lifecycle: `created` → `running` → `paused` → `completed`
    / `cancelled` / `failed`.
  - Persistence: każda sesja jako W15 type `OperatorSession`. Append-only
    event log per session w PG.
  - Multi-session view: split mode pokazujący 2-3 sesje obok siebie
    (xterm panes).

- **Task List per Session** — todo list bieżącej sesji.
  - Source: integration z W6 Execution Pipeline state machine.
  - UI: prawa kolumna z task tree, każdy task `pending / running /
    done / failed / skipped`, click expand → step details.
  - Task can be: spawned by agent automatically, dodany przez operatora
    (`/task add "verify W14 SoT"`), inherited from charter.
  - Real-time updates: state changes propagated z `event_bus` → SSE.

- **Interactive Interventions** — pierwszorzędna funkcja.
  - **Pause**: `/pause` — current session frozen mid-execution. Resume
    z `/resume`. Backend: send pause signal do active agent loops via
    `command_bus`.
  - **Cancel**: `/cancel` — abort current task (graceful, allow rollback).
  - **Override model**: `/model claude` — switch active model w locie
    dla bieżącej task (np. zauważyłeś że qwen się zaciął, Robert chce
    ekspresową claude review).
  - **Inject HG**: `/hg required: critic review` — force injection HG
    do current step nawet jeśli D-level by tego nie wymagał. Operator
    interwencja dla precaution.
  - **Rollback**: `/rollback {step_id}` — cofnięcie do snapshot
    pre-step. Integration z W14 SimulationBranch / W15 branches.

- **Command Palette** — pełen zestaw slash commands.
  - **Status / Info**:
    - `/status` — overall AEIS health (z W17 health aggregator).
    - `/cost` — kumulowany cost session / dziennie / miesięcznie.
    - `/agents` — lista active agents z model + host + current task.
    - `/budget` — daily / monthly budget remaining (W11 cost data).
    - `/help` — quick reference.
  - **Focus / Navigation**:
    - `/focus {entity}` — narrow stream do jednego agenta / modułu.
    - `/host {name}` — drill into specific host (PDF §7.2).
    - `/model {name}` — drill into specific model usage (PDF §7.2).
    - `/explain {entity}` — show context, recent activity, dependencies.
  - **Findings / Diff**:
    - `/findings` — open findings list (W14 E7).
    - `/diff` — diff bieżącej zmiany (jeśli session edituje pliki).
    - `/diff sessions {id1} {id2}` — port. sesji (PDF §7.2).
  - **Control**:
    - `/skip` — skip current task.
    - `/retry` — retry current task.
    - `/priority {high|normal|low}` — re-priorytyzacja queue.
  - **History / Replay**:
    - `/replay {session_id}` — odtworzenie historycznej sesji jak film
      (PDF §7.2).
    - `/export {session_id} {format}` — export do markdown / json.
    - `/report` — wygeneruj raport sesji.
  - Auto-completion: command palette pokazuje suggestions po `/`
    z fuzzy match.

- **History & Replay** — sesje persisted, replay step-by-step.
  - Persistence: każda linia stream + każda akcja zapisana w PG via W15
    OSDK jako append-only `TerminalEvent` z `prev_hash` chain.
  - Replay UI: timeline scrubber u dołu, play/pause/speed (1x, 2x, 5x, 10x).
  - Step-by-step: `→` jeden event do przodu, `←` cofnij (visualnie tylko,
    nie cofa state).
  - Replay-as-film: czas przyspieszony, animacja przejść między eventami.
  - Hash-chained: tamper detection przy `/verify-replay {session_id}`.

- **HG Integration** — interrupt-first.
  - HG (Human Gate) request od agent → modal pop-up z urgent banner +
    żółta linia w stream.
  - Modal pokazuje: context, decision options (Approve / Reject / Modify),
    cost estimate, evidence pack link.
  - Decision propagated back via `command_bus` z audit (W15 lineage event).
  - Timeout default 5 min — jeśli no response, default action z manifestu
    (zwykle `pause`).
  - Browser notification + optional email/Slack ping (post-G3).

- **Federation Map** — opcjonalny panel (depends on W17 G2).
  - Topology view: hosty jako nodes, model availability per host, current
    load.
  - Live metrics overlay: CPU, RAM, GPU, requests/sec.
  - Interactive: kliknięcie host → drill-down do tego host w stream.
  - Brak Federation Map = W18 nadal działa (single-host mode), tylko
    multi-host view niedostępny.

## 3. Scope OUT

- **Nie zastępuje istniejących frontend surfaces** (PDF §7.3) — `/funding`,
  `/idea-vault`, `/test-center` zostają. W18 to operator-centric layer,
  jeden z surfaces, nie super-app.
- **Nie jest IDE** (PDF §7.3) — brak edytora kodu, brak debuggera, brak
  file tree. W18 fokus = obserwacja + intervention.
- **Nie hostuje modeli** (PDF §7.3) — modele runtime są w W11, W18 tylko
  consumer event'ów.
- **Nie podejmuje decyzji za Roberta** (PDF §7.3) — auto-routing
  jest w W13 Advisor. W18 surface dla manual intervention.
- **Multi-user collaborative editing** sesji — single-user model (PDF §2.3).
- **Custom shell commands** (jak prawdziwy bash) — slash commands tylko,
  brak arbitrary code execution z UI.
- **Mobile-first design** — desktop-first (xterm.js działa głównie na
  desktop). Mobile może podejrzeć read-only stream.

## 4. Exit gates

### G1 — SSE Backend + Skeleton (week 3)
- **Deliverables**:
  - `sylion/aeis_v2/terminal/sse_backend.py` — SSE endpoint
    `GET /api/v2/terminal/stream` z subscription model.
  - `sylion/aeis_v2/terminal/event_consumer.py` — subscribes do
    `sylion.core.event_bus`, normalizes events do terminal format.
  - `sylion/api/terminal_routes.py` — REST endpoints (sessions, replay,
    interventions).
  - `sylion-frontend/src/app/(app)/terminal/page.tsx` — xterm.js skeleton
    z połączeniem SSE.
  - 5 commands działa: `/help`, `/status`, `/agents`, `/clear`, `/cost`.
  - 30+ pytest, 5 frontend integration tests.
- **Success criteria**:
  - Real-time stream pokazuje events z aktualnego AEIS workflow
    (W14 testing run obecny).
  - Backend handle 100 events/sec z brakiem dropped events.
  - Front buffer 10k linii bez performance issues.
- **HG required**: NO (foundational).

### G2 — Sessions + Filters + Replay (week 6)
- **Deliverables**:
  - `sylion/aeis_v2/terminal/session_manager.py` — session lifecycle,
    persistence via W15.
  - `sylion/aeis_v2/terminal/replay_engine.py` — replay z hash chain
    verification.
  - W15 ontology types: `OperatorSession`, `TerminalEvent` (manifest
    + auto-gen).
  - Frontend: filter UI (chip selectors), session switcher, replay timeline.
  - Hash chain verify: `make w18-verify-replay` zielony.
  - Wszystkie filters działa, URL-shareable.
- **Success criteria**:
  - 5.1 SC F-W18-01..F-W18-04 zielone.
  - Replay z 1000-event session z prędkością 5x w < 30s.
  - Session creation overhead < 50ms.
- **HG required**: NO (no D4 trigger jeszcze).

### G3 — Interventions + Command Palette Full (week 9)
- **Deliverables**:
  - Wszystkie interventions: pause, cancel, override model, inject HG,
    rollback.
  - Wszystkie 18+ slash commands.
  - HG modal flow z full context display + 3 decision options + audit.
  - Command auto-completion z fuzzy match.
  - 6+ E2E scenariuszy z realnymi interventions.
- **Success criteria**:
  - 5.1 SC F-W18-05..F-W18-08 zielone.
  - Pause-resume z queue preservation działa.
  - Override model: w trakcie task, switch model, kontynuacja z
    następnego step bez data loss.
- **HG required**: YES (D4 milestone, Council vote).

### G4 — Federation Map + Production (week 12-14)
- **Deliverables**:
  - Federation Map panel (jeśli W17 G2 done — soft dep).
  - Multi-session split view (2-3 panes).
  - Notifications (browser + optional email/Slack).
  - Performance: 1000 events/sec sustained bez UI lag (P-W18-01).
  - Documentation: command reference, replay guide, troubleshooting.
  - 4-week soak: Robert używa W18 codziennie jako default surface.
- **Success criteria**:
  - Wszystkie 20 SC zielone.
  - Robert deklaruje W18 jako "default home page" w SYLION.
- **HG required**: YES (production promotion D4).

## 5. Success criteria

### 5.1 Functional (8)
1. **F-W18-01**: Live stream pokazuje events z 5 modułów (W11, W13, W14,
   W15, W16) w real-time, format zgodny z PDF §7.2.
2. **F-W18-02**: Filter z 3 dimensjami (layer + host + severity)
   współdziała, multi-select, URL-shareable.
3. **F-W18-03**: Session create / switch / archive działa, każda sesja
   ma własny context, replay-able.
4. **F-W18-04**: Replay z timeline scrubber, play/pause/speed (1x..10x),
   step-by-step `→` `←`.
5. **F-W18-05**: Pause / resume kontynuuje sesję bez utraty queue, brak
   data loss.
6. **F-W18-06**: Override model w trakcie task: poprzedni model abandons,
   nowy model resumes z następnego step.
7. **F-W18-07**: Inject HG: arbitrary force HG do step, blokuje propagation
   do approval.
8. **F-W18-08**: 18+ slash commands działa: `/help`, `/status`, `/cost`,
   `/agents`, `/skip`, `/focus`, `/explain`, `/findings`, `/retry`, `/diff`,
   `/budget`, `/priority`, `/export`, `/report`, `/host`, `/model`,
   `/replay`, `/diff sessions`.

### 5.2 Performance (4)
1. **P-W18-01**: 1000 events/sec sustained przez 10 min bez dropped events,
   bez UI lag (frame time < 16ms p95).
2. **P-W18-02**: Filter change → stream update < 200ms (re-subscribe na
   backend, frontend re-render).
3. **P-W18-03**: Session switch (1k events buffer) < 100ms.
4. **P-W18-04**: Replay scrubbing 5x speed → frame rate >= 30 FPS.

### 5.3 Reliability (4)
1. **R-W18-01**: SSE reconnect po network drop: < 3s auto-reconnect, brak
   utraty events (replay z last seen offset).
2. **R-W18-02**: Backend crash → frontend pokazuje status banner, retry.
   Po backend recovery, stream resumes z buffer.
3. **R-W18-03**: Hash chain integrity weryfikowalny daily, zero break w
   normal operation.
4. **R-W18-04**: Sesja persistowana w PG przed UI confirms — brak utraty
   przy crash mid-create.

### 5.4 Developer Experience (4)
1. **DX-W18-01**: Robert otwiera W18 w 1 click z navigation, default landing
   stan to "all events, last 10 min".
2. **DX-W18-02**: Slash command auto-completion fuzzy: `/foc` → `/focus`
   suggestion, `Tab` accept.
3. **DX-W18-03**: Command reference (`/help`) inline w terminal jako
   markdown render, plus standalone docs page.
4. **DX-W18-04**: Replay z tutorial mode pokazującym 1-week-old session
   z annotations "to jest pause", "to jest HG injection" jako onboarding.

## 6. Top ryzyka

### R1: SSE scaling przy 20 hostów × 5 modeli × 10 actions/sec = 1000 events/sec
- **Probability**: H
- **Impact**: H (główne ryzyko, PDF §7.5)
- **Mitigation**:
  - **Subscription model**: backend filtruje events server-side per
    subscriber, klient otrzymuje tylko events spełniające jego filter.
    Single subscriber widzi maksymalnie ~50 events/sec (typowy filter).
  - **Filtering on backend**: layer filter, host filter, severity filter
    aplikowane przed SSE write — minimalizuje bandwidth.
  - **Throttling**: gdy filter set wide (np. all events), backend
    aggregates pod 50ms windows, sends batched chunks.
  - **Buffer + drop policy**: jeśli klient slow, backend dropuje oldest
    events z buffer (drop policy = `oldest_first`), znaczy linią `[N
    events dropped]`.
  - **Backpressure**: SSE response stream uses `await` semantics —
    backend nie blokuje globalnie, slow client tylko sam się limituje.
  - Performance test G2/G4: 1000 events/sec generated, verify P-W18-01 SC.
- **Trigger to escalate**: Test pokazuje dropped events > 1% lub UI lag
  > 100ms — switch do WebSocket (binary frame protocol) lub Redis Streams
  jako pub/sub buffer (HG D4).

### R2: HG modal pop-up jest disruptive jeśli zbyt częsty
- **Probability**: M
- **Impact**: M
- **Mitigation**: HG threshold tuning: D3+ wymaga HG, D2 może bypass
  (audit-only). Robert ma `/hg-mode {strict|standard|relaxed}` polecenie
  zmieniające threshold. Strict = wszystkie HG, standard = D3+, relaxed
  = D4+. Default `standard`. Notifications bypass UI: jeśli W18 nie
  open, push notification + email — Robert nie musi mieć terminala
  open 24/7.
- **Trigger to escalate**: Robert deklaruje "HG modal alert fatigue"
  → re-eval threshold, simplify modal, batch HG requests w queue
  zamiast modal-per-request.

### R3: Replay state drift od live state
- **Probability**: M
- **Impact**: M
- **Mitigation**: Replay jest **read-only** przez design — wizualizacja
  historycznych events bez wpływu na live state. UI clear separation:
  replay mode banner "REPLAY: 2026-04-25 14:32" w czerwonym z lock icon.
  Backend: replay endpoint zwraca events z PG, brak `event_bus`
  re-publish. Operator clicked actions w replay mode disabled (no
  interventions, no commands except `/exit-replay`). Hash chain verify
  przed replay starts — broken chain → warning + audit alert.
- **Trigger to escalate**: User report "thought I clicked in replay
  but action happened in live" → audit incident, harden UI separation.

### R4: Audit log explosion (1000 events/sec × 86400s × 365 = 31B events/year)
- **Probability**: H
- **Impact**: H
- **Mitigation**: **Tiered retention**:
  - Live buffer: in-memory ring buffer 10k events.
  - Hot storage: PG W15 type `TerminalEvent` for last 30 dni
    (~2.6B events × ~200B = ~520GB) → compressed JSONB rows.
  - Cold storage: parquet archive po 30 dni do `/archive/` (S3 lub local)
    z metadata in PG (`hash`, `timestamp`, `archive_url`).
  - Hash chain crosses tiers (events w archive nadal podpisane).
  - Audit log entries dla replay-related ops — minimalne (1 entry per
    replay session, nie per scrubbed event).
  - Retention policy configurable: 30/90/365 dni hot, infinite cold.
- **Trigger to escalate**: PG storage > 80% capacity → emergency archive
  + retention policy reduction (HG D4).

### R5: Slash command surface area
- **Probability**: M
- **Impact**: L
- **Mitigation**: 18+ commands w G3 — discoverability problem. Mitigation:
  - `/help` jako command reference inline + organized po grupach.
  - Auto-completion fuzzy match — `/c` → `cost`, `cancel`, `clear`.
  - Command groups: `/help status`, `/help control` filtruje doc.
  - W docs: cookbook z 20 typowych operations + matching commands.
  - Telemetry (post-G3): zliczamy command usage, top 5 = featured w
    quickbar UI (jeśli pojawi się need).
- **Trigger to escalate**: User research pokazuje commands rarely used
  (>5 commands < 5% usage) → simplify, drop / merge commands.

## 7. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| Frontend renderer | xterm.js v5 + custom React panels | PDF §7.4; mature terminal emulator, accessible, theme-able. |
| Real-time | Server-Sent Events (SSE) | PDF §7.4; HTTP-friendly, auto-reconnect, lighter than WS dla unidirectional. |
| Backend | FastAPI subscribing to event bus | PDF §7.4; spójność. |
| Storage | PostgreSQL przez W15 OSDK | PDF §7.4; persistence sessions + events. |
| Replay | Append-only event log w PG, hash-chained | Spójność z evidence_spine wzorzec. |
| State (frontend) | Zustand + react-query | Spójność z v1 frontend stack. |
| Command parser | Custom (~200 LOC) z fuzzy match (fuse.js) | Lekkie, customowe matching dla slash commands. |
| Filters | Backend SQL filter (W15 OSDK queries) + frontend chip UI | Filter logic na backend, UI display only. |
| Notifications | Browser Notification API + optional Slack/email webhook | Native, minimal. |
| Topology graph | react-flow (re-use z W14 E12 Theater) | Konsystencja z `/agent-theater`. |
| Replay timeline | recharts (timeline mode) | Konsystencja z dashboards. |
| Testing | pytest + Vitest + Playwright | Spójność. |

## 8. Dependencies

- **Hard**:
  - **W15 G2** — OSDK dla `OperatorSession`, `TerminalEvent` types z
    hash chain.
  - **W14 E12 Agent Theater Aggregator** — extension: aggregator
    publishes events do `event_bus` w terminal-friendly format. W18
    consumes jako event source.
  - **W11 Adapter Bus** — emits events per LLM call (model, host,
    cost, latency). W18 consumes.
  - `sylion.core.event_bus` — backbone.
  - `sylion.surface.command_bus` — interventions dispatch.
- **Soft**:
  - **W17 G2** — Federation Map panel needs deploy ontology (Node, deploy
    state). Bez W17, panel hidden, reszta W18 działa.
  - W14 W6 Execution Pipeline — task list source.
  - W14 E5 Guardians — alert injection do stream.
  - W13 Advisor — AdvisorCard events streamowane do W18.
- **Parallel-able**:
  - PDF §7.6: "Może startować równolegle z W17." Hard dep tylko na W15
    G2 + W14 E12 (oba existing).

## 9. Modules created

- `sylion/aeis_v2/terminal/__init__.py` — public API.
- `sylion/aeis_v2/terminal/sse_backend.py` — SSE endpoint, subscription
  model, throttling.
- `sylion/aeis_v2/terminal/event_consumer.py` — `event_bus` consumer,
  normalizer do terminal line format.
- `sylion/aeis_v2/terminal/session_manager.py` — session lifecycle, W15
  persistence.
- `sylion/aeis_v2/terminal/replay_engine.py` — replay z hash verify,
  speed control.
- `sylion/aeis_v2/terminal/command_dispatcher.py` — slash command parser,
  intervention executor.
- `sylion/aeis_v2/terminal/intervention_handler.py` — pause / cancel /
  override / inject HG / rollback executors.
- `sylion/aeis_v2/terminal/hg_modal_service.py` — HG request lifecycle,
  notification routing.
- `sylion/aeis_v2/terminal/federation_map.py` — panel data provider
  (depends on W17).
- `sylion/api/terminal_routes.py` — REST endpoints.
- `sylion-frontend/src/app/(app)/terminal/page.tsx` — main terminal page.
- `sylion-frontend/src/components/terminal/*` — xterm wrapper, filter
  bar, session switcher, replay timeline, HG modal, federation map.
- W15 manifests: `OperatorSession`, `TerminalEvent`,
  `InterventionEvent`.

## 10. Migration from v1

| Step | What | Rollback |
|---|---|---|
| 1 | **Audit existing event sources**: 35 subsystem v1, list event_bus topics, czy każdy emituje sufficient context. Output: `docs/v2/migration/V1_EVENT_SOURCES_INVENTORY.md`. | Audit-only. |
| 2 | **Event format normalization**: extend event_bus envelope dla terminal needs (`layer`, `host`, `model`, `severity` jeśli missing). Backward-compat — old subscribers ignore new fields. | Revert envelope, lose terminal context (degraded). |
| 3 | **Pilot SSE backend** w dev mode: deploy SSE endpoint, subscribe do 1 layer (W14), verify events arrive. | Disable SSE endpoint. |
| 4 | **Frontend skeleton on `/terminal`**: xterm.js, basic stream. Robert uses obok existing surfaces. | Remove `/terminal` route. |
| 5 | **Wave 1**: full filters + 5 commands. | Per-feature flags w UI. |
| 6 | **Wave 2 (G2)**: sessions + replay + W15 persistence. | Sessions feature flag. |
| 7 | **Wave 3 (G3)**: interventions + full command palette. | Interventions disabled, observation-only mode. |
| 8 | **Cleanup**: legacy `/agent-theater` może deprekować Topology View jeśli W18 Federation Map robi to lepiej. Decision punkt G4. | `/agent-theater` zostaje, oba surfaces dostępne. |

W18 nie zastępuje (PDF §7.3): istniejące surfaces zostają. W18 to nowy
operator-centric layer. Migration jest *dodawaniem*, nie *replacement*.

## 11. D-level rationale

**D4** (proponowana, PDF §7):
- User-facing UI z significant impact na operator experience.
- **Niereversibilne audit log** w PG (interventions, replays są audit-tracked
  z hash chain), tampering = compliance issue.
- **Interventions changing live state** (pause, cancel, override model)
  mogą mieć cascading effect na running tasks.
- HG injection per intervention — RBAC implications dla zespołu 10 os.
- BUT: brak data corruption risk (oddzielony od ontology), crash W18 nie
  powala AEIS, fallback do existing surfaces.

Dlaczego nie D5: D5 zarezerwowane dla data-corruption-risk warstw (W15)
lub deploy-lifecycle blast radius (W17). W18 jest UI/observability layer
— jeśli się zepsuje, AEIS dalej działa, Robert wraca do legacy surfaces.

Dlaczego nie D3: Affects production daily workflow (Robert deklaruje W18
jako default home page po G4). Interventions modify live state. Audit log
compliance. Standard D4 sygnał = high impact, reversible.

## 12. Test plan

- **Unit** (pytest):
  - `tests/aeis_v2/terminal/test_sse_backend.py` — subscription model,
    throttling, drop policy, reconnect.
  - `tests/aeis_v2/terminal/test_event_consumer.py` — normalization,
    edge cases (missing fields, malformed envelope).
  - `tests/aeis_v2/terminal/test_session_manager.py` — lifecycle,
    persistence, crash recovery.
  - `tests/aeis_v2/terminal/test_replay_engine.py` — hash verify, speed,
    step-by-step.
  - `tests/aeis_v2/terminal/test_command_dispatcher.py` — parsing, fuzzy
    match, all 18 commands.
  - `tests/aeis_v2/terminal/test_intervention_handler.py` — each
    intervention idempotent, audit logged.

- **Integration** (testcontainers PG + FastAPI + frontend smoke):
  - `tests/aeis_v2/integration/test_event_to_stream.py` — event_bus
    publish → SSE delivery → frontend receive.
  - `tests/aeis_v2/integration/test_session_lifecycle.py` — create →
    events → archive → replay.
  - `tests/aeis_v2/integration/test_pause_resume_w14.py` — uses live
    W14 testing flow, pause mid-test, verify state preserved.
  - `tests/aeis_v2/integration/test_override_model.py` — z W11 model
    switch live.

- **E2E** (Playwright):
  - `e2e/terminal/test_basic_flow.spec.ts` — open terminal, see events,
    apply filter, drill-down.
  - `e2e/terminal/test_session_replay.spec.ts` — record session, archive,
    replay with scrubbing.
  - `e2e/terminal/test_intervention_flow.spec.ts` — start session, pause,
    cancel, verify audit.
  - `e2e/terminal/test_hg_modal.spec.ts` — HG request fires, modal,
    decision propagates.

- **Performance benchmark**:
  - `scripts/bench_w18.py` — generates 1000 events/sec for 10 min,
    measures: dropped events count, UI frame time (via Playwright
    metrics), backend CPU/RAM.
  - Replay benchmark: 1k / 10k / 100k event sessions, scrubbing FPS.

- **Stress / chaos** (G4):
  - 10x normal load (10000 events/sec) — observe degradation pattern.
  - Network jitter / packet loss — SSE reconnect verified.
  - Backend rolling restart — clients reconnect without data loss.

- **DX validation**:
  - "First-time operator" walkthrough z 3 reviewers (kimi, codex, GLM)
    — czas-to-first-intervention, command discoverability ratings.

## 13. Open questions

- **Q1**: SSE vs WebSocket choice — PDF §7.4 deklaruje SSE. Trade-off:
  SSE lighter, native HTTP, ale uni-directional. Interventions używają
  separate `command_bus` POST endpoint (consistent w PDF). Decision:
  start z SSE. Re-eval w G4 jeśli scaling issues — switch do WS może być
  drop-in (SSE → WS adapter).

- **Q2**: Multi-session split view — 2 panes vs 3+ panes. UI complexity
  vs power user value. V1 plan: 2 panes (G4), 3+ panes future.

- **Q3**: Notifications channel selection — browser only, browser + email,
  browser + email + Slack. Robert preferences? V1 plan: browser default,
  optional Slack via webhook URL config. Email: post-G4.

- **Q4**: Slash commands user-customization — allow user to define alias
  (`/s` → `/status`) lub macro (`/morning` → executes `/status; /budget;
  /agents`). V1 plan: aliases only (G3+), macros post-G4.

- **Q5**: Replay-as-shareable-URL — bezpieczeństwo (dane w sesji mogą
  być sensitive). V1 plan: replay only logged-in użytkownik, brak public
  share. Z 10-os zespołem (PDF §9.1) → re-eval RBAC dla sessions w W19.

- **Q6**: Federation Map — depends na W17 G2. Jeśli W17 opóźniony, czy
  W18 G4 może shipnąć bez Map? Plan: yes, panel pokazuje "Wymaga W17
  G2", ale W18 G4 nie blokowany.

- **Q7**: Light theme / dark theme — terminal default dark (xterm
  convention). Light theme post-G4 jeśli request.

- **Q8**: AccessibilityMode (screen reader compat dla xterm) — xterm.js
  ma built-in `screenReaderMode`. V1 plan: enabled, audit z a11y
  reviewer post-G3.

- **Q9**: Replay storage retention — 30 dni hot + cold archive vs all-hot.
  Decision punkt G2 z Cost Sentinel. Compute budget wpływa: 1000 ev/sec
  × 30 dni = 2.6B events ~ 520GB hot.

- **Q10**: Mobile read-only view — iOS Safari + Chrome Android wsparcie
  dla `/terminal/?readonly=true`. V1 plan: post-G4 jeśli use case
  pojawi się.
