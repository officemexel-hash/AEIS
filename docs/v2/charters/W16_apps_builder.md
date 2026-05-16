# W16 Charter — Operational Apps Builder Plane

> Status: **DRAFT** (2026-04-27)
> D-level: **D4**
> Estymacja solo: **16-20 tygodni**
> Depends on: **W15 G2 (HARD)**, AEIS v1 frontend baseline (sylion-frontend
> Next.js 16 + React 19 + shadcn/ui), `sylion.surface.command_bus`.

## 1. Cel

W16 to **builder aplikacji operacyjnych** dla SYLION — odpowiednik Palantir
Workshop / Slate. Cel: pełny system operacyjny (formularze + dashboardy +
workflow + automatyzacje) zbudowany przez **manifest YAML** z widgetów
high-level, używających obiektów z W15 OSDK. **Nowa app w 4 godziny zamiast
2 tygodni.**

Dziś AEIS v1 ma 13 frontend surfaces (`/funding`, `/idea-vault`,
`/test-center`, `/agent-theater`, …). Każdy to 5-15 stron napisanych
ręcznie w Next.js: hook do API, formularz, lista, szczegóły, dashboard,
RBAC checks. Per surface: ~3000-8000 LOC, 2-4 tyg pracy. **W16 redukuje to
do 100-300 linii YAML i `make build-app`** — rendering, routing, data
binding, RBAC są powered by runtime engine.

W16 oznaczony **D4** (high impact, ale reversible — manifest można cofnąć,
hand-coded surface może wrócić). PDF §4 jasno mówi: depends on **W15 G2**
(OSDK + Action Types muszą być stabilne zanim widgets je używają).
Kluczowa decyzja PDF §2.5: **własny React-based builder**, nie Budibase /
ToolJet — re-use Next.js / shadcn/ui infra które AEIS już ma, brak iframe
overhead, RBAC reuse. Workflow engine: Python `transitions` library
(`sylion.pipeline.state_machine` rozszerzenie), nie Temporal. **Custom
code escape hatch** od początku jako first-class citizen — niewszystkie
apps wpasują się w manifest, własny React + Python validator hook musi
być wspierany cleanly.

## 2. Scope IN

- **App Manifest Format** — `apps/{name}/app.yaml`.
  - Top-level: `name`, `version`, `display_name`, `route_prefix`,
    `rbac` (role: viewer/operator/admin/auditor), `ontology_types`
    (lista typów z W15 jakie app używa).
  - Sections: `pages`, `dashboards`, `forms`, `workflows`, `automations`.
  - Każda section to lista entries z `id`, `widget` / `state_machine` /
    `trigger`, `bindings` (do W15 OSDK queries).
  - Wsparcie includes/templating: `extends: base_crud_app.yaml`,
    `include: shared_kpi_panel.yaml`.

- **App Runtime Engine** — Next.js dynamic loader.
  - Build step: `make build-apps` czyta wszystkie `apps/*/app.yaml`,
    generuje Next.js routes pod `/apps/{name}/...`, kompiluje per-app
    bundle (lazy-loaded).
  - Dev mode: file watcher na manifestach, hot-reload < 2s na change
    (incremental).
  - Dynamic routing: `[...slug].tsx` catch-all per app, dispatcher renderuje
    widget na podstawie manifest entry.
  - SSR/SSG decyzja per page (default SSG dla static dashboards, SSR dla
    forms).

- **Component Library** — 20-30 high-level widgets (zgrupowane).
  - **Data Display** (8): `ObjectListView`, `ObjectDetailView`,
    `ObjectGridView`, `KpiCard`, `MetricChart`, `TimeSeriesChart`,
    `LineageTreeView`, `DataTable`.
  - **Data Entry** (6): `ObjectFormEditor`, `ObjectInlineEditor`,
    `BulkActionBar`, `WizardForm`, `FileUploadField`, `RichTextField`.
  - **Workflow** (4): `WorkflowStateView`, `KanbanBoard`,
    `ApprovalQueue`, `TimelineView`.
  - **Insights** (5): `AdvisorCardFeed`, `RecommendationsList`,
    `AnomalyDetector`, `CostMonitor`, `HealthDashboard`.
  - **Layout & Nav** (5): `GridLayout`, `TabContainer`, `Sidebar`,
    `BreadcrumbBar`, `CommandPalette`.
  - Każdy widget ma `widget.yaml` schema (props), Storybook entry, 5+
    pytest-react testów.

- **Forms** — auto-gen z W15 manifest + customization.
  - Z W15 type spec (5 properties) auto-gen full CRUD form (5 inputs,
    validation, error display, optimistic submit).
  - Customization layer: `form_customization.yaml` — override field order,
    add helper text, custom validators (Python lambda lub external module),
    conditional visibility (jsonpath rules).
  - Submit dispatches W15 Action Type (z auto HG injection na D3+).

- **Dashboards** — grid layout z widgets, data binding do OSDK.
  - 12-column responsive grid (recharts + react-grid-layout).
  - Dashboard manifest definiuje widgets + ich `binding`:
    `{type: list, ontology_type: customer, filter: {status: ACTIVE},
     limit: 10}`.
  - Refresh policy per widget: `manual`, `30s`, `5m`, `realtime` (SSE).
  - Drill-down: kliknięcie row w `ObjectListView` nawiguje do
    `/apps/{name}/{type}/{id}` (jeśli detail page exists).

- **Workflows** — state machines + UI per state.
  - Manifest: lista `states`, `transitions` z `guard` (warunek na property),
    `action` (W15 Action Type wywołane przy transition), `ui_per_state`
    (page do wyświetlenia gdy obiekt jest w danym stanie).
  - Backend: Python `transitions` library, integracja z
    `sylion.pipeline.state_machine` jako extension.
  - Wbudowane patterns: `ApprovalFlow`, `ReviewCycle`, `ProcurementFlow`,
    `IncidentResponseFlow` (4 templated workflows).
  - Audit: każda state transition produkuje W15 LineageEvent.

- **Automations** — event-driven + cron.
  - Trigger types: `on_ontology_event` (event z W15 lineage), `cron`
    (czas), `on_external_webhook`, `on_threshold_breach` (metric).
  - Action: dispatch W15 Action Type, send notification, trigger inny
    automation (chained).
  - Backend: APScheduler + integracja z `sylion.core.event_bus` consumer.
  - Manifest spec: `triggers`, `conditions`, `actions`, `error_handling`
    (retry policy + dead-letter).

- **Builder UI** — drag-drop, live preview, hot-reload.
  - In-browser editor: lewa kolumna widget palette, środek live preview,
    prawa property panel.
  - Save → write `app.yaml`, build → hot-reload bundle, view → render.
  - Visual mode + YAML mode (oba synchronized via OT-like merge).
  - Undo/redo, version history, draft saves.
  - **NIE jest pixel-perfect WYSIWYG** — Robert deklaruje strukturę,
    style są shadcn/ui defaults (możliwość theme override per app).

- **Custom Code Escape Hatch** — własne React + Python validators.
  - W manifeście: `widget: custom`, `module: ./custom_panel.tsx`,
    `props: {...}`. Custom plik leży w `apps/{name}/custom/`.
  - Python validator escape: `validator: ./validators.check_dependency`.
  - Audit: Guardian liczy use frequency. Cel: < 10% widgets per app.
  - Custom code traktowany jak normal Next.js code (TypeScript, lint,
    test wymagane).

## 3. Scope OUT

- **Multi-user collaborative editing** (operational transforms, presence,
  conflict resolution) — single-user assumption (PDF §2.3).
- **Complex BPMN workflows** (parallel branches, sub-processes, escalation
  chains z calendar awareness, BPMN 2.0 import) — `transitions` linear FSM
  wystarczy. Power users mogą custom escape.
- **iOS/Android native app generation** — web-only, mobile = responsive
  layout. PWA "add to home screen" wystarczy.
- **Pixel-perfect WYSIWYG editor** (Webflow style) — manifest-driven, structured.
- **Drag-drop database designer** — ontology przez W15 manifesty (YAML), nie
  GUI. PDF §4.3.

## 4. Exit gates

### G1 — Foundation (week 4)
- **Deliverables**:
  - `sylion/aeis_v2/apps/compiler.py` — manifest reader + Next.js route gen.
  - 5 core widgets implemented z Storybook + tests:
    `ObjectListView`, `ObjectFormEditor`, `KpiCard`, `MetricChart`,
    `AdvisorCardFeed`.
  - 1 example app: `apps/customer_crm/app.yaml` (3 pages, 1 dashboard,
    1 form) działa end-to-end.
  - Hot-reload w dev < 5s.
  - 50+ pytest + 20+ React tests.
- **Success criteria**:
  - Manifest 50 linii produkuje działającą app z list + detail + form.
  - Manifest validation error messages z line + field path.
- **HG required**: NO (foundational).

### G2 — Component Library (week 8)
- **Deliverables**:
  - 20+ widgets (wszystkie 8 Data Display + 6 Data Entry + 4 Workflow +
    selected Insights).
  - 3 example apps:
    - `apps/customer_crm` — CRUD + dashboard + 1 workflow.
    - `apps/funding_dashboard` — read-only KPI + drill-down.
    - `apps/inspection_tracker` — Kanban board + form + automations.
  - Storybook publicly browsable na `/internal/storybook`.
  - Form auto-gen z W15 manifest działa: tworzysz typ w W15, automatycznie
    masz form widget bez dodatkowej konfiguracji.
- **Success criteria**:
  - 5.1 SC F-W16-01..F-W16-04 zielone.
  - 5.4 SC DX-W16-01 (nowa app < 4h) zwerfikowane na rzeczywistej app.
- **HG required**: YES (D4 milestone, Council vote).

### G3 — Workflows + Automations (week 12)
- **Deliverables**:
  - Workflow engine action: `sylion/aeis_v2/apps/workflow_engine.py`.
  - Wszystkie 4 templated workflows.
  - Automation engine: `sylion/aeis_v2/apps/automation_engine.py`.
  - APScheduler integracja, deduplication, dead-letter queue.
  - 4 więcej example apps z workflows / automations.
  - Workflow audit: każda transition w W15 lineage.
- **Success criteria**:
  - 5.1 SC F-W16-05..F-W16-08 zielone.
  - Reliability SC R-W16-01..R-W16-04.
- **HG required**: NO (incremental on G2).

### G4 — Builder UI + Production (week 16-20)
- **Deliverables**:
  - Builder UI z drag-drop, live preview, version history.
  - Visual mode ↔ YAML mode bi-directional.
  - Production hardening: error boundaries per widget, fallback UI, log
    aggregation.
  - 7+ example apps total (W14 demo projects 6 zmigrowane do W16 jako
    acceptance test).
  - Documentation: widget reference, manifest cookbook, "build first app
    in 10 minutes" tutorial.
  - 4-week soak run na realnym workload (Robert używa W16 codziennie).
- **Success criteria**:
  - Wszystkie 20 SC zielone.
  - Custom code escape hatch < 10% średnio per app.
- **HG required**: YES (production promotion D4).

## 5. Success criteria

### 5.1 Functional (8)
1. **F-W16-01**: Manifest YAML 50 linii produkuje running app z list +
   detail + form (3 pages) bez custom code.
2. **F-W16-02**: Form widget auto-gen z W15 manifest pokrywa wszystkie 5
   property types (string, int, float, bool, datetime) z validation.
3. **F-W16-03**: Dashboard z 4 KPI cards + 2 charts + 1 list rendered, data
   binding live, refresh policy działa.
4. **F-W16-04**: 20+ widgets dostępnych, każdy z Storybook entry + 5+ testów.
5. **F-W16-05**: Workflow z 5 stanami, 6 transitions, 3 z guards działa,
   audit w W15 lineage.
6. **F-W16-06**: Automation `cron: "0 9 * * MON"` triggeruje action (np.
   send weekly report), execution audited.
7. **F-W16-07**: Custom widget escape hatch: `widget: custom` + `.tsx` file
   renders inline w app, props passed correctly.
8. **F-W16-08**: Builder UI: open existing app, drag widget na grid, save,
   widget pojawia się w live app po reload.

### 5.2 Performance (4)
1. **P-W16-01**: App build cold start (manifest → Next.js bundle compiled)
   < 30s dla 5-page app.
2. **P-W16-02**: Hot-reload incremental change (1 widget property edit)
   visible < 5s.
3. **P-W16-03**: Dashboard render z 10 widgets (4 list, 4 chart, 2 KPI)
   FCP < 1.5s, TTI < 3s na 3G throttled.
4. **P-W16-04**: Form submit (5 fields) end-to-end (validate + W15 OSDK
   call + UI feedback) < 500ms p95.

### 5.3 Reliability (4)
1. **R-W16-01**: Widget crash w jednym slot dashboard nie powala całej
   strony (error boundary izoluje).
2. **R-W16-02**: Manifest z błędem validation (broken FK reference)
   blokuje build, NIE deployuje broken app.
3. **R-W16-03**: Workflow restart po crash kontynuuje od ostatniego
   committed state (idempotent transitions).
4. **R-W16-04**: Automation z `error_handling: retry` retry'uje 3x z
   exponential backoff, potem dead-letter queue + Guardian alert.

### 5.4 Developer Experience (4)
1. **DX-W16-01**: Robert buduje nową app (3 pages, 1 form, 1 dashboard) w
   < 4h od pustego folderu do running localhost.
2. **DX-W16-02**: Manifest validation errors zawierają line + field path
   + suggested fix, render w terminal AND w Builder UI banner.
3. **DX-W16-03**: Storybook ma wszystkie 20+ widgety z 3+ states each
   (default, loading, error). Browsable w 1 klik.
4. **DX-W16-04**: "Build first app in 10 minutes" tutorial works dla
   programisty znającego Next.js basics, weryfikowane z 3 zewnętrznymi
   reviewerami.

## 6. Top ryzyka

### R1: Component library za mała dla typical apps
- **Probability**: H
- **Impact**: H
- **Mitigation**: Pre-G1 phase: audit 13 frontend surfaces v1 + 6 demo
  projects W14, lista wszystkich UI patterns które się powtarzają.
  Identifikuje minimum viable widget set (target: 20 widgets pokrywa 80%
  obserwowanych use cases). Reszta przez `widget: custom`. G2 review:
  jeśli >2 widgets do dodania na app, sygnał że library za mała → expand
  scope (HG D3) zanim G3.
- **Trigger to escalate**: Średnio >30% widgets per app to `custom`
  → freeze G2, dodaj 5+ widgetów, retest.

### R2: Custom code escape hatch nadużywany
- **Probability**: H
- **Impact**: M
- **Mitigation**: Guardian `EscapeHatchUsageGuardian` (W14 pattern E5)
  liczy usage frequency per app + globally. Alert na >15% per app, alert
  na >10% średnio. Każdy `widget: custom` wymaga komentarza z reason
  ("widget X niewystarczający bo Y"). Periodic review: które custom widgets
  pojawiają się 3+ razy → kandydat na "promote to library widget" (PDF §4.5).
- **Trigger to escalate**: Apps średnio >25% custom → re-design widget API
  (HG D4).

### R3: Builder UI sam jest skomplikowanym appem do utrzymania
- **Probability**: H
- **Impact**: M
- **Mitigation**: Builder UI buduje się na *własnym* W16 framework jak tylko
  G2 stable — eat own dogfood, jeśli W16 framework dla Buildera niewystar-
  czający, sygnał że framework nie gotowy. Builder UI w G4 ma być cienki:
  drag-drop layout + property editor + YAML view. Brak inline JS evaluation,
  brak custom rendering — wszystko routes back to standard W16 runtime.
  Estymacja G4: 4-6 tyg z 16-20 total — większość już w runtime engine.
- **Trigger to escalate**: G4 work overflow > 6 tyg → freeze Builder UI
  scope at "YAML editor + live preview, no drag-drop", ship G4 bez visual
  mode (downgrade D4 → D3 dla tego komponentu).

### R4: W15 OSDK churn breaks W16 widgets
- **Probability**: M
- **Impact**: H
- **Mitigation**: W16 deklaruje `osdk_compat: ">=2.0,<3.0"` w każdym
  manifest. Build step weryfikuje. W16 widgets używają OSDK przez stabilną
  abstraction layer (`sylion/aeis_v2/apps/osdk_adapter.py`) — schema bumps
  W15 1.x → 1.y dotykają tylko adapter, widgets niewidoczne dla zmian.
  CI: weekly OSDK regen smoke run wszystkie example apps.
- **Trigger to escalate**: OSDK breaking change wymaga widget rewrite
  → koordynacja z W15 (HG D4 koordynacja warstw).

### R5: SSR / SSG / dynamic routing edge cases
- **Probability**: M
- **Impact**: M
- **Mitigation**: Standardowy Next.js patterns, dokumentowane mode per
  page w manifest (`render_mode: ssr | ssg | csr`). Domyślnie `ssg`,
  forms forcują `ssr` automatycznie. Edge cases (interactive dashboard
  z auth) testowane w 3 example apps z różnymi modes. Logging na unhandled
  routing edge cases.
- **Trigger to escalate**: SEO / shareability requirements pojawią się
  → w v1 deferred (single-user, low priority), v2 plan re-evaluate.

## 7. Tech stack

| Component | Choice | Rationale |
|---|---|---|
| Framework | Next.js 16 + React 19 | PDF §2.5; kontynuacja v1 stack; App Router native. |
| UI Components | shadcn/ui + Radix primitives | Już używane w v1; styled, accessible, customizable. |
| Charts | Recharts | Active maintenance, declarative, używane w `/agent-theater`. |
| Grid layout | react-grid-layout | Battle-tested, drag/resize, responsive. |
| Forms | react-hook-form + zod | Performance, type-safe; już w v1. |
| Tables | TanStack Table v8 | Headless, perf na 10k rows, pagination/sort built-in. |
| Workflow engine | python-transitions | PDF §2.5; mature, simple FSM, integration z W6 pipeline. |
| Automations | APScheduler + own consumer | Cron + interval triggers; własny event consumer dla `on_event`. |
| Build | Next.js native + custom prebuild step | `make build-apps` wstrzykuje generated routes przed `next build`. |
| Hot-reload | chokidar + Next.js Fast Refresh | Watcher na YAML, force re-build app entry. |
| Storybook | Storybook 8 | Widget docs + visual regression (Chromatic optional). |
| Testing | Vitest + Testing Library + Playwright | Vitest dla unit, Playwright dla E2E. |
| Manifest val | pydantic v2 + jsonschema | Spójność z W15. |

## 8. Dependencies

- **Hard**:
  - **W15 G2** — OSDK musi być stabilne (bez breaking changes). Forms
    auto-gen, list bindings, action dispatch — wszystko przez W15.
  - `sylion.surface.command_bus` (action dispatch z UI).
  - `sylion-frontend` baseline (Next.js 16, shadcn, lib/api).
  - `sylion.security.rbac` (per-app role enforcement).
- **Soft**:
  - W18 Operator Terminal Plane (W16 może emit terminal events dla
    "user clicked / form submitted").
  - W14 E11 Demo Projects — 6 demo projects są acceptance test dla G4.
- **Development order**:
  - Pre-G1: audit 13 v1 surfaces + 6 W14 demos → widget shortlist.
  - G1-G4 zgodnie z 4-gate plan.

## 9. Modules created

- `sylion/aeis_v2/apps/__init__.py` — public API.
- `sylion/aeis_v2/apps/compiler.py` — Manifest → Next.js routes + bundle
  config gen.
- `sylion/aeis_v2/apps/registry.py` — App discovery, lifecycle (registered,
  active, deprecated).
- `sylion/aeis_v2/apps/widget_registry.py` — Widget catalog: schema,
  Storybook entry, props validation.
- `sylion/aeis_v2/apps/form_engine.py` — Auto-gen form spec z W15 manifest
  + customization layer.
- `sylion/aeis_v2/apps/workflow_engine.py` — State machine runtime,
  transitions library wrapper, lineage hooks.
- `sylion/aeis_v2/apps/automation_engine.py` — Trigger evaluator, event
  consumer, retry/dead-letter logic.
- `sylion/aeis_v2/apps/osdk_adapter.py` — Stable abstraction nad W15 OSDK.
- `sylion/api/apps_routes.py` — REST endpoints dla app metadata + manifest
  query.
- `sylion-frontend/src/app/apps/[appName]/[...slug]/page.tsx` — dispatcher.
- `sylion-frontend/src/components/widgets/*` — 20+ widget React components.
- `sylion-frontend/src/components/builder/*` — Builder UI (G4).
- `apps/{example_apps}/` — 7+ example app manifestów.

## 10. Migration from v1

| Step | What | Rollback |
|---|---|---|
| 1 | **Audit + classify 13 surfaces**: które są kandydatami na W16 manifest, które stay hand-coded. Output: `docs/v2/migration/SURFACE_CLASSIFICATION.md`. | Audit-only, no code change. |
| 2 | **Pilot migracji**: 1 surface (np. `/test-center/dashboard` proste KPI) → manifest. Side-by-side z hand-coded. | Disable `/apps/test-center`, hand-coded zostaje. |
| 3 | **Pilot validation**: 1 tydzień Robert używa pilot, feedback. | n/a (pilot tylko). |
| 4 | **Wave 1**: 5 read-mostly surfaces (`/funding-dashboard`, `/idea-vault/list`, `/agent-theater/topology`, `/test-center/catalog`, `/orchestration/event-map`) → manifest. | Per-surface feature flag `USE_W16_APP=false`. |
| 5 | **Wave 2**: 5 form-heavy surfaces (po G2 form auto-gen done). | Per-surface feature flag. |
| 6 | **Wave 3**: 6 W14 demo projects → manifest (G4 acceptance). | Demo projects niezależne, niski risk. |
| 7 | **Cleanup hand-coded duplikatów**: po 30 dniach side-by-side bez issues. | Restore from git history; surfaces niewielkie. |

Każdy z 13 v1 surfaces ma classification:
- **Stay hand-coded** (np. `/operator-terminal` W18, custom UI) — out of W16 scope.
- **Migrate to manifest** (większość CRUD-heavy) — Wave 1-3.
- **Hybrid** (manifest dashboard + custom panel) — escape hatch.

PDF §6.4 jest jasny: migracja frontend surfaces *opcjonalna*, nie blokuje
v3.0. W16 może shipnąć z 5 zmigrowanymi surfaces, reszta zostaje legacy.

## 11. D-level rationale

**D4** (high impact, reversible):
- Manifest-driven framework jest reverse-able — jeśli W16 nie spełnia
  oczekiwań, hand-coded surfaces zostają. Każdy migrated surface ma
  feature flag który cofa do v1 implementacji.
- Workflow engine (transitions library) jest battle-tested, niski risk
  data corruption.
- Automations mogą być włączane/wyłączane per app, error handling
  blokuje propagation.
- Builder UI w G4 to nice-to-have — jeśli G4 fails, W16 G3 z YAML-only
  builder nadal spełnia 80% wartości.

Dlaczego nie D5: W16 nie touchuje data layer (W15 to robi), nie touchuje
deployment (W17 to robi). Crash w W16 frontend nie korumpuje danych —
forms przechodzą przez W15 actions z transactional commits. → D4.

Dlaczego nie D3: Affects user-facing produkty (Robert używa codziennie).
Workflow misfires mogą wpłynąć na business processes (np. funding
application workflow). → D4 minimum.

## 12. Test plan

- **Unit** (Vitest + pytest):
  - `tests/aeis_v2/apps/test_compiler.py` — manifest → routes determinism,
    error messages.
  - `tests/aeis_v2/apps/test_widget_registry.py` — props validation,
    schema diff detection.
  - `tests/aeis_v2/apps/test_form_engine.py` — auto-gen z W15 type, edge
    cases (nullable, default, FK).
  - `tests/aeis_v2/apps/test_workflow_engine.py` — state transitions, guards,
    audit.
  - `tests/aeis_v2/apps/test_automation_engine.py` — cron triggers, event
    triggers, retry, dead-letter.
  - `tests/widgets/*.test.tsx` — 5+ testów per widget (render, props, events).

- **Integration** (testcontainers PG + Next.js dev server):
  - `tests/aeis_v2/integration/test_app_compile_to_route.py` — E2E
    manifest → live HTTP route → response.
  - `tests/aeis_v2/integration/test_form_submit_to_lineage.py` — form
    submit → action → W15 lineage event.
  - `tests/aeis_v2/integration/test_workflow_lifecycle.py` — full
    workflow run z 5 stanami.

- **E2E** (Playwright):
  - `e2e/apps/customer_crm.spec.ts` — full CRUD flow, 1 dashboard, 1 form.
  - `e2e/apps/funding_dashboard.spec.ts` — load dashboard, drill-down.
  - `e2e/apps/inspection_tracker.spec.ts` — Kanban drag, automation trigger.
  - `e2e/builder/builder_ui.spec.ts` — open app, edit manifest, save,
    reload, verify.

- **Performance benchmark**:
  - `scripts/bench_w16.py` — build time per app, hot-reload latency,
    dashboard render time, form submit roundtrip.
  - Lighthouse CI per example app, FCP/TTI thresholds.

- **DX validation**:
  - "Build first app in 10 minutes" — 3 external reviewers (kimi, codex,
    GLM) próbują follow-along, raport timing + roadblocks.

## 13. Open questions

- **Q1**: Internationalization (i18n) — czy widgets supportują built-in
  translation, czy każda app robi own? V1: en + pl hardcoded. W16 v1:
  opt-in `i18n: true` w app manifest, używa `next-intl`. Decision G2.

- **Q2**: Theming per app — czy każda app może mieć własne CSS theme
  override, czy wszystkie SYLION-style? V1: shared theme. W16: opcja
  `theme: ./theme.css` w manifest, opcjonalnie. Decision G3.

- **Q3**: Marketplace dla widgets / apps community — czy widgets mogą
  być package'owane i shared (npm)? Z 10-os zespołem teoretycznie
  yes, ale wymaga discovery + trust mechanism. Decision: post-G4
  (v3.x territory).

- **Q4**: Mobile-specific layouts — manifest deklaruje `breakpoints`?
  V1: responsive (shadcn responsive), brak mobile-specific. W16 G2:
  basic responsive. Mobile-specific: Q5 dla v3+.

- **Q5**: Custom React widgets allowed bezpośrednio w manifest (`widget:
  ./MyWidget.tsx`) vs require registration. V1: registration required
  (security via path validation), reusability via widget library promotion.

- **Q6**: Workflow timeouts / SLA tracking — automation `if state == X for
  > 24h: notify`. W G3 wbudowane czy escape hatch? Decision G3, lean
  toward built-in (1 line YAML).

- **Q7**: Dashboard sharing — link z filtered view (`?status=ACTIVE`)
  preserved w URL, shareable. V1 default. Multi-user share-and-react z
  zespołem 10 osób → potential v3+ feature.

---

## Architectural Decision (2026-04-27)

See [ADR-001](../decisions/ADR-001-five-architectural-decisions-2026-04-27.md) — Decision #2.

**Resolved:** Idea → App Studio cascade pipeline: template matching (top-N library, ~20 templates) → embeddings retrieval if score < 0.7 → LLM generation with templates as few-shot. Every generated manifest passes through Council Hybrid (W3) before production. Threshold (0.7) is empirical — tune over 2 months.
