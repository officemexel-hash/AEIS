# 01 — INVENTORY_FRONTEND — SYLION AEIS Operator Console

**Audyt:** ETAP 1 / Inwentaryzacja frontendu
**Data:** 2026-04-24
**Źródło:** `C:\Users\razor\Desktop\pipeline_glm\src\sylion-frontend\src\`
**Stack:** Next.js `16.2.4`, React `19.2.4`, Tailwind 4, shadcn/ui, framer-motion 12, recharts 3, sonner 2 (toasts), base-ui 1.4, lucide-react.
**Backend API:** `NEXT_PUBLIC_API_URL` → fallback `http://127.0.0.1:8000` (resolvowane w `lib/api/client.ts::resolveApiBase`).

---

## Statystyki ogólne

| Kategoria | Liczba |
|---|---|
| Strony (`page.tsx`) | **56** |
| Layouty (`layout.tsx`) | **3** |
| Komponenty React (`*.tsx` w `src/components/`) | **39** |
| Hooks API (`export const/function use*` w `lib/api/hooks.ts`) | **164** |
| Methods API client (`lib/api/client.ts`) | ~400 (file ~1400 linii) |
| Biblioteki klienckie (`src/lib/`) | 5 plików (client, hooks, mock, types, utils) |

Grupy nawigacji (wg `AppSidebar.tsx`): Overview, Idea Vault, Skills Hub, Pipeline, AI Workspace, Settings, Book, Projects, Funding, Agents, Modules, Workers, Auto-Scaler, Build Factory, Event Backbone, Build State, Observability, Deploy, Governance, Evidence, Decisions, …

---

## Katalog stron Next.js App Router

Wszystkie strony siedzą w dwóch route-group: `(app)/*` (konsola, shared layout z sidebar/top-bar) oraz `(marketing)/*` (publiczny landing).

| URL | page.tsx | Główny backend moduł / endpointy | Layout |
|---|---|---|---|
| `/` (landing) | `app/(marketing)/page.tsx` | brak (statyczny landing) | `(marketing)/layout.tsx` |
| `/overview` | `app/(app)/overview/page.tsx` | `api.listPipelineRuns`, `api.getDecisionTimeline`, `api.ideaStats`; `useHealth`, `useProposals` | `(app)/layout.tsx` |
| `/idea-vault` | `app/(app)/idea-vault/page.tsx` | `api.listIdeas`, `api.ideaStats`, `api.listPipelineRuns` | `(app)/layout.tsx` |
| `/skills` | `app/(app)/skills/page.tsx` | `api.createSkill`; `useSkills`, `useSkillExecutions`, `useDemandSignals` | `(app)/layout.tsx` |
| `/pipeline` | `app/(app)/pipeline/page.tsx` | `api.listRuns`, `api.getRuntimeLLMConfig`, `api.submitPipelineIdea`, … | `(app)/layout.tsx` |
| `/workspace` | `app/(app)/workspace/page.tsx` | `api.submitPipelineRun`, `api.getPipelineRun`, `api.getPipelineRunSteps` (+ Workspace WS, HumanGate, Council, Chat, Books, Prompts — via komponenty `workspace/*`) | `(app)/layout.tsx` |
| `/settings` | `app/(app)/settings/page.tsx` | `api.listAPIKeys`, `api.storeAPIKey`, … (runtime LLM config) | `(app)/layout.tsx` |
| `/book` | `app/(app)/book/page.tsx` | `api.createGoldenSet`, `api.runGoldenSet`, … | `(app)/layout.tsx` |
| `/projects` | `app/(app)/projects/page.tsx` | Projekty kanoniczne (`useHealth`, project APIs) | `(app)/layout.tsx` |
| `/funding` | `app/(app)/funding/page.tsx` | `api.getFundingMatchingResults`, `api.getFundingScoring`, `api.analyzeFundingConsortium` | `(app)/layout.tsx` |
| `/agents` | `app/(app)/agents/page.tsx` | `useHealth` + agent registry | `(app)/layout.tsx` |
| `/modules` | `app/(app)/modules/page.tsx` | `useModules`, `useContracts` | `(app)/layout.tsx` |
| `/workers` | `app/(app)/workers/page.tsx` | `api.registerWorker`, `api.heartbeatWorker`, `api.deleteWorker`; `useWorkers` | `(app)/layout.tsx` |
| `/autoscaler` | `app/(app)/autoscaler/page.tsx` | `api.evaluateAutoscaler`, `api.executeAutoscaler`, `api.updateAutoscalerPolicy` | `(app)/layout.tsx` |
| `/builds` | `app/(app)/builds/page.tsx` | `api.createCandidateBuild`, `api.validateCandidateBuild`, `api.promoteCandidateBuild`; `useCandidateBuilds` | `(app)/layout.tsx` |
| `/events` | `app/(app)/events/page.tsx` | `useBackboneHealth`, `useBackboneCatalog`, `useBackboneEvents` | `(app)/layout.tsx` |
| `/build-state` | `app/(app)/build-state/page.tsx` | `useBuildState` | `(app)/layout.tsx` |
| `/observability` | `app/(app)/observability/page.tsx` | `useObservabilitySnapshot`, `useLogs`, `useMetrics`, `useTraces` | `(app)/layout.tsx` |
| `/deploy` | `app/(app)/deploy/page.tsx` | `api.generateDeployTopology`; `useDeploySummary`, `useDeployTopologies` | `(app)/layout.tsx` |
| `/governance` | `app/(app)/governance/page.tsx` | `api.checkCompliance`, `api.listComplianceRules`, `api.voteProposal`; `useProposals`, `usePolicies`, `useGates` | `(app)/layout.tsx` |
| `/evidence` | `app/(app)/evidence/page.tsx` | `useEvidence`, `useEvidenceStore` | `(app)/layout.tsx` |
| `/decisions` | `app/(app)/decisions/page.tsx` | `api.listDecisionSnapshots`, `api.listCascadeEvents`, `api.evaluateGate`; `useDecisionAuditLog` | `(app)/layout.tsx` |
| `/gates` | `app/(app)/gates/page.tsx` | `api.submitHumanReview`; `useGovernanceGates`, `useHumanGateRequests` | `(app)/layout.tsx` |
| `/evidence-spine` | `app/(app)/evidence-spine/page.tsx` | `api.getSpineEntries`, `api.getSpineStats`, `api.verifySpineChain` | `(app)/layout.tsx` |
| `/evaluator` | `app/(app)/evaluator/page.tsx` | `api.listEvaluations`; `useEvaluatorEvaluations`, `useEvaluationCriteria` | `(app)/layout.tsx` |
| `/anomalies` | `app/(app)/anomalies/page.tsx` | `api.resolveAnomaly`; `useAnomalies`, `useAnomalyBaselines` | `(app)/layout.tsx` |
| `/audit` | `app/(app)/audit/page.tsx` | `api.verifyAuditChain`, `api.tamperCheck`; `useAuditEvents`, `useAuditSummary` | `(app)/layout.tsx` |
| `/auth` | `app/(app)/auth/page.tsx` | `api.getAuthStatus`, `api.listAuthProviders`, `api.listAuthSessions` | `(app)/layout.tsx` |
| `/autonomy` | `app/(app)/autonomy/page.tsx` | `useAutonomyStatus`, `useAutonomyStages`, `useSelfObservation` | `(app)/layout.tsx` |
| `/budget` | `app/(app)/budget/page.tsx` | `api.configureModelBudget`, `api.resetModelBudget`; `useCostAlerts`, `useBudgetAlerts`, `useModelBudgetEntries` | `(app)/layout.tsx` |
| `/bundles` | `app/(app)/bundles/page.tsx` | `api.getBundle`, `api.listBundleVersions`; `useBundles` | `(app)/layout.tsx` |
| `/capacity` | `app/(app)/capacity/page.tsx` | `useCapacityResources`, `useCapacityRecommendations` | `(app)/layout.tsx` |
| `/cellular` | `app/(app)/cellular/page.tsx` | `api.analyzeControlPlane`, `api.detectControlPlaneAnomalies`; `useRANStacks`, `useCoreNetworks`, `useUEDevices`, etc. | `(app)/layout.tsx` |
| `/circuits` | `app/(app)/circuits/page.tsx` | `useCircuitBreakers` | `(app)/layout.tsx` |
| `/connectors` | `app/(app)/connectors/page.tsx` | `api.listConnectors`; `useConnectors`, `useAdapters` | `(app)/layout.tsx` |
| `/contracts` | `app/(app)/contracts/page.tsx` | `useContracts`, `useContractsList`, `useFreezeStatus` | `(app)/layout.tsx` |
| `/costs` | `app/(app)/costs/page.tsx` | `api.configureModelBudget`, `api.resetModelBudget`; `useCostRecords`, `useDailySpend`, `useMonthlySpend`, `useCostSummary` | `(app)/layout.tsx` |
| `/devices` | `app/(app)/devices/page.tsx` | `api.scanDevices`, `api.registerDevice`, `api.runDeviceTest`; `useDiscoveredDevices`, `useRegisteredDevices` | `(app)/layout.tsx` |
| `/drift` | `app/(app)/drift/page.tsx` | `api.detectDrift`, `api.resolveDrift`; `useDrifts`, `useDriftSummary`, `useConfigDrifts` | `(app)/layout.tsx` |
| `/environments` | `app/(app)/environments/page.tsx` | `api.listDeployments`, `api.listWorkers` | `(app)/layout.tsx` |
| `/golden-tests` | `app/(app)/golden-tests/page.tsx` | `useGoldenSets`, `useGoldenSetsList` | `(app)/layout.tsx` |
| `/healing` | `app/(app)/healing/page.tsx` | `api.updateHealingRule`, `api.createHealingRule`; `useHealingRules`, `useHealingActions` | `(app)/layout.tsx` |
| `/health` | `app/(app)/health/page.tsx` | `useHealth` (+ trend) | `(app)/layout.tsx` |
| `/integrations` | `app/(app)/integrations/page.tsx` | `api.listIntegrations`; `useIntegrations` | `(app)/layout.tsx` |
| `/lifecycle` | `app/(app)/lifecycle/page.tsx` | `useLifecycleStages`, `useLifecycleEntries` | `(app)/layout.tsx` |
| `/notifications` | `app/(app)/notifications/page.tsx` | `api.markNotificationRead`, `api.markNotificationUnread`, `api.ackNotification`; `useNotificationsList`, `useNotificationCountWS` | `(app)/layout.tsx` |
| `/performance` | `app/(app)/performance/page.tsx` | `api.getModelTrend`, `api.detectAnomalies`; `useModelSummaries`, `useModelLeaderboard` | `(app)/layout.tsx` |
| `/quality` | `app/(app)/quality/page.tsx` | Golden sets + regressions (`useRegressions`, `useGoldenSets`) | `(app)/layout.tsx` |
| `/rebuild` | `app/(app)/rebuild/page.tsx` | `api.createCFTSuite`, `api.snapshotLPW`; `useRebuildPlans`, `useCutoverPlans`, `useLPW` | `(app)/layout.tsx` |
| `/risk` | `app/(app)/risk/page.tsx` | `useRiskScores`, `useChangeProposals` | `(app)/layout.tsx` |
| `/roles` | `app/(app)/roles/page.tsx` | `useRoles`, `useExecutionPolicies`, `useDecisionBoundaries` | `(app)/layout.tsx` |
| `/sdr` | `app/(app)/sdr/page.tsx` | `useSDRDevices`, `useCaptures`, `useAnalyses`, `useRFPolicies` | `(app)/layout.tsx` |
| `/secrets` | `app/(app)/secrets/page.tsx` | `api.listSecrets`; `useSecrets` | `(app)/layout.tsx` |
| `/security-scan` | `app/(app)/security-scan/page.tsx` | `api.listSecurityFindings`, `api.listSecurityScans`; `useSecurityFindings`, `useSecurityScans` | `(app)/layout.tsx` |
| `/sla` | `app/(app)/sla/page.tsx` | `useSlaPolicies`, `useMetricSummary` | `(app)/layout.tsx` |

Uwagi:
- Wszystkie strony w `(app)` dzielą wspólny shell (sidebar + top-bar + `ApiOfflineBanner`). Shell jest **client-side** (`"use client"`).
- Większość list-views używa hooków `useApi(...)` z auto-refresh (polling 5–30s).
- Real-time jest dostępne przez `useWorkspaceWS` (`/ws/workspace`) — używane przez `usePipelineRunsWithWS` i `useNotificationCountWS`.
- **Brak jakichkolwiek route'ów dynamicznych** typu `/funding/proposals/[id]` — wszystkie strony to listy/dashboardy bez detalówek po ID w URL. Szczegóły wybranych zasobów są otwierane jako stan lokalny komponentu (drawer/modal), nie przez routing.

---

## Layouty

| Plik | Typ | Rola |
|---|---|---|
| `app/layout.tsx` | Root | HTML `<html lang="en" class="dark">`, font Inter, globalny `<Toaster>` (sonner). Server component (brak `"use client"`). |
| `app/(app)/layout.tsx` | Route-group shell | `"use client"`. Dostarcza `SidebarProvider`, renderuje `<AppSidebar/>`, `<TopCommandBar/>`, `<ApiOfflineBanner/>` i `<main>` z marginesem pod sidebar. Wszystkie strony konsoli żyją tutaj. |
| `app/(marketing)/layout.tsx` | Landing shell | `"use client"`. Fixed nav, hamburger menu, link "Launch Console → /overview". |

Brakuje: **`error.tsx`**, **`loading.tsx`**, **`global-error.tsx`** — nie znalezione w App Routerze (brak fallbacków Next 15/16 dla błędów i shell-skeleton).

---

## Biblioteki klienckie (`src/lib/`)

| Plik | Rozmiar | Co robi |
|---|---|---|
| `lib/api/client.ts` | ~1400 linii | **Serce integracji z backendem.** Definiuje `resolveApiBase()` (env + fallback 127.0.0.1:8000), `request<T>()` z nagłówkami `X-Auth-Token` / `X-User-ID` / `X-Session-ID` (z `localStorage`). Eksportuje wielki obiekt `api` z ~400 metodami REST pokrywającymi: Core/Modules/Contracts, Governance (compliance, proposals, gates, decision snapshots, cascade), Cognitive (models, evaluations), Execution (workflows, jobs, retry), Security (audit, sessions, users, profiles, scans, auth, bootstrap), Skills, Memory (kanon sections, self-models, evidence store), Devices / SDR / Cellular (klasy M/N/O), Quality (golden sets), Rebuild/LPW/CFT, Cost/Budget/Alerts, Worker Fleet, Integration Orchestrator, Drift, Event Backbone, Deploy/Topology, Auto-Scaler, Observability, Pipeline, AI Workspace (Chat, Council, Settings, Prompts, Books), **HumanGate (sessions, tree, history, choices, undo, rollback, present)**, Guided Project Kickoff, Canonical Project Mode, Funding Autopilot, Idea Vault, Evidence Spine, Model Performance, Decision Audit, Notifications, Hallucination Detector, Code Snapshots, Cascade Analyzer, Conflict Detector, Compliance Checker, Session Manager, Capacity/Risk/SLA/Anomaly, Roles/Boundaries, Hardened Audit, Evaluator, Connectors/Adapters/Secrets, Auth Providers/Sessions, Profile Swaps, Worker Monitor, Contract Freeze, Build State. Obsługuje auth storage (`sylion_auth_token`, `sylion_auth_user`, `sylion_auth_session`). |
| `lib/api/hooks.ts` | ~530 linii | 164 hooki (`useHealth`, `useProposals`, `useModules`, …). Bazowy `useApi<T>(fetcher, fallback, refreshMs?)` + dedykowane hooki dla wszystkich encji. Dodatkowo: **`useWorkspaceWS(topics?)`** — WebSocket do `/ws/workspace` z subskrypcją topic-ów, `usePipelineRunsWithWS()` i `useNotificationCountWS(userId)` łączące poll+WS z fallback degraded. |
| `lib/data/mock.ts` | mock fallback | Mock data dla trybu offline / brak backendu. |
| `lib/types/index.ts` | typy | Współdzielone typy TS (m.in. `ApprovalStatus`). |
| `lib/utils.ts` | util | `cn()` (clsx + tailwind-merge). |

Brakuje dedykowanych plików: `lib/auth.ts`, `lib/vault.ts`, `lib/websocket.ts` — WS i auth są inlined w `client.ts` + `hooks.ts`.

---

## Human Gate UI — stan obecny

### Co jest (i gdzie siedzi w drzewie)

1. **`components/workspace/HumanGatePanel.tsx`** (~800 linii) — główny UI dla Human Gate w obrębie `/workspace`:
   - lista sesji (`api.listHumanGateSessions`);
   - tworzenie nowej sesji (`api.createHumanGateSession`) + "Project Kickoff" (`api.createProjectKickoff` — guided project);
   - wyświetlanie bieżącej decyzji (`api.getHumanGateCurrentDecision`) z choices/description/consequences;
   - custom answer (nadpisanie choice'ów tekstem);
   - drzewo decyzji (`api.getHumanGateTree` → lokalny `TreeNode`) z wizualizacją `current/visited/superseded`;
   - historia (`api.getHumanGateHistory`) z **undo last** (`api.undoHumanGateChoice`) i **rollback do węzła** (`api.rollbackHumanGateTo`);
   - sekcja "Project": approvals `book` + `operating_model` (`api.approveProjectSection`), launch pipeline (`api.launchProjectPipeline`), stage timeline, notyfikacje projektu;
   - auto-refresh co 5s gdy projekt `running/queued/ready_to_launch/blocked_on_audit`.
2. **`app/(app)/gates/page.tsx`** — strona listowa `useGovernanceGates`, `useHumanGateRequests`, z akcją `api.submitHumanReview` (forma approve/reject).
3. **`components/workspace/CouncilPanel.tsx`** + **`components/decisions/*`** (CascadeTree, DecisionTimeline, SnapshotDiffViewer) — wspierające decyzje (D3+).

### Czego brakuje vs spec `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`

Spec wymaga **13 submodułów Orchestratora** + **12 modułów Operator Mobile**. Mapowanie:

| # | Submoduł spec | UI present? | Uwagi |
|---|---|---|---|
| 01 | Decision Intake (agent/docker/VPS/pipeline/portal/deploy/security/finance/legal) | **NIE** | Obecny tylko wąski `HumanGate` per sesja kickoff + `/gates` dla governance. Brak dedykowanego widoku "centralny intake". |
| 02 | Decision Classifier (risk/financial/legal/technical/production/security/reputation/P0-P4) | **NIE** | Brak UI klasyfikacji/priorytetów P0–P4. |
| 03 | Autonomy Policy Engine (reguły autoapprove/escalate/limity $/Docker/VPS/API) | Częściowo | `/autonomy` pokazuje stage + self-observation, ale brak edytora polityk z limitami per moduł/operator/env. |
| 04 | Decision Queue (kolejki P0–P4 + blokujące/nieblokujące/zbiorcze/przeterminowane) | **NIE** | Brak filtrowanej kolejki. `/gates` to płaska lista. |
| 05 | Batch Approval Engine (grupowanie + zatwierdzanie pakietowe) | **NIE** | Brak wielozaznaczenia / batch approve. |
| 06 | Delegation Engine (owner/CTO/CFO/legal/admin/fallback) | **NIE** | Brak routing ownerów. |
| 07 | Execution Continuity Engine (work stealing, freeze zależnych tasków, fallback) | **NIE** | Brak UI widocznego continuity stanu. |
| 08 | Decision Dependency Graph (zależności decyzji/tasków/agentów) | Częściowo | `CascadeTree.tsx` pokrywa cascade decyzji, ale nie graf zależności oczekujących approvali. |
| 09 | Risk-Based Auto Approval | **NIE** | Brak UI reguł auto-approve. |
| 10 | Notification Routing (per kanał/per operator/push) | Częściowo | Jest `/notifications`, `useNotificationCountWS`, ale bez routingu kanałowego i push. |
| 11 | Decision SLA (timeout/expiry/reminder) | **NIE** | Brak SLA countdownu dla decyzji (ogólny SLA jest tylko dla metryk w `/sla`). |
| 12 | Audit Trail (kompletny) | TAK | `/audit` + `/evidence-spine` + `api.verifyAuditChain` + `api.tamperCheck`. |
| 13 | Decision Learning (heurystyki z przeszłych decyzji) | **NIE** | Brak UI. |

### Operator Mobile (12 modułów)

| # | Moduł spec | UI present? |
|---|---|---|
| 01 | Global Critical Inbox | **NIE** |
| 02 | Module Channels | **NIE** |
| 03 | Push Notification Engine | **NIE** |
| 04 | Mobile Human Gate | **NIE** |
| 05 | Secure Approval Layer (biometria, signed token) | **NIE** |
| 06 | Operator Modes (active/passive/emergency) | **NIE** |
| 07 | System Status (live) | **NIE** |
| 08 | Batch Approval mobilny | **NIE** |
| 09 | Escalation System | **NIE** |
| 10 | Voice / Chat Operator | **NIE** |
| 11 | Audit & Compliance mobile | **NIE** |
| 12 | Operator Preferences | **NIE** |

**Wniosek**: aktualny front ma ~**15% pokrycia** spec Human Gate Orchestrator (głównie moduły 08 cascade + 12 audit + ~fragment 01/03) oraz **0%** Operator Mobile.

---

## Mobile / PWA — stan

### Jednoznaczna odpowiedź: **NIE.**

**Brak natywnej aplikacji mobilnej i brak PWA.**

Dowody:
- **Brak `manifest.json` / `manifest.webmanifest`** w `src/sylion-frontend/public/` (zawartość: `file.svg`, `globe.svg`, `next.svg`, `vercel.svg`, `window.svg` — tylko domyślne asset Next.js).
- **Brak service workera** (`sw.ts`, `service-worker.js`, `workbox-*`) w repo.
- **Brak `next-pwa` / `@ducanh2912/next-pwa`** w `package.json` (zależności: next, react, recharts, framer-motion, shadcn, sonner, tailwind, lucide — żadnej PWA-zależności).
- **Brak `metadata.manifest`** w `app/layout.tsx` (tylko `title` + `description`).
- **Brak komponentów `Mobile*` / `Responsive*`** w `src/components/`. Grep dla `Mobile|Responsive|manifest|serviceWorker|PWA` zwraca tylko 3 pliki: `drift/page.tsx` (menu mobilne nav), `marketing/UseCasesSection.tsx`, `(marketing)/layout.tsx` — wszystkie to odpowiedzi **responsywne desktop-first** (hamburger menu na `md:` breakpoint), nie "natywna appka".
- **Brak ścieżek** `/m/`, `/mobile/`, `/app/mobile/`.
- **Brak natywnego kodu** (Android/iOS, React Native, Expo, Capacitor, Ionic) — żadnych `android/`, `ios/`, `App.tsx` RN, `capacitor.config.*`, `app.json` Expo, `.xcodeproj` w repo frontendu.
- Nie istnieje żaden komponent spełniający spec "AEIS Operator Mobile" (Google Pixel Live Test Mode, Face Unlock, push FCM, deep linki, offline approval tokens) — opisane w `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`.

Stan webu: **desktop-first dark console**. Landing (`/`) ma jedynie prosty hamburger responsive.

---

## Komponenty Dashboard V5

Lokalizacja: `C:\Users\razor\Desktop\pipeline_glm\SYLION_Dashboard_V5_ClaudeCode_Package\`.

Zawartość paczki (wg `PACKAGE_MANIFEST.json` v5.0.0, 2026-04-20):
```
README.md
CLAUDE.md_SNIPPET.md
.claude/docs/DASHBOARD_FUNCTIONAL_SPEC.md
.claude/docs/DASHBOARD_TECHNICAL_SPEC.md
.claude/docs/DASHBOARD_V5_MERGE_NOTES.md
.claude/docs/DASHBOARD_WORKPLAN_V5.md
.claude/skills/dashboard-implementation/SKILL.md
```

**To jest paczka dokumentacyjno-planistyczna**, nie kod. Zawiera 4 markdown-specy + 1 skill-manifest + snippet do wklejenia w `CLAUDE.md`. W paczce **nie ma żadnego kodu React / TypeScript / komponentów** — wyłącznie specyfikacje v5:
- `DASHBOARD_FUNCTIONAL_SPEC.md` — spec funkcjonalny,
- `DASHBOARD_TECHNICAL_SPEC.md` — scalony spec techniczny,
- `DASHBOARD_V5_MERGE_NOTES.md` — delta vs v4,
- `DASHBOARD_WORKPLAN_V5.md` — freeze list i plan wdrożenia,
- `SKILL.md` — skill `dashboard-implementation` (obecny też w `.claude/skills/dashboard-implementation/` projektu, agent.md widoczny w CLAUDE.md).

Kluczowe decyzje "zamrożone w v5" (z README):
- Dashboard = **event-sourced control plane**,
- Command Bus = `TWO_PHASE` default, `IMMEDIATE` tylko D0–D1 przez policy rule,
- **Process Canvas = Yjs + tldraw, hybrydowy DAG + freeform**,
- Browser upload = signed HTTP upload / resumable multipart (nie gRPC-Web streaming),
- Readiness = deterministic primary + ML advisory,
- Replay audytu = full event sourcing + snapshots + projection rebuild,
- **Secrets nigdy** do event store / Yjs / replay / evidence payload.

**Jak się ma do bieżącego frontendu:**
- **Paczka V5 jest NIEZAIMPLEMENTOWANA w kodzie.** Obecny front to zbiór ~56 klasycznych "list+drawer" dashboardów zbudowanych na hookach `useApi`/polling i REST — nie event-sourced command-bus.
- **Yjs / tldraw / Process Canvas** nie istnieją w `package.json` ani w `src/` (brak `yjs`, `@tldraw/*`, `y-websocket`). → `grep package.json` potwierdza brak zależności.
- **Command Bus TWO_PHASE** — brak UI. `gates/page.tsx` robi `api.submitHumanReview` jako pojedynczy request (single-phase).
- **Resumable multipart upload** — brak implementacji (nie znaleziono `resumable`, `tus`, `chunked upload` w repo frontendu).
- **Event sourcing replay UI** — brak dedykowanego widoku snapshot+projection rebuild; `SnapshotDiffViewer.tsx` jest prostym diff viewerem snapshotu decyzji, nie full event-replay.
- Skill `dashboard-implementation` jest załadowany w `.claude/skills/` (dostępny dla Claude Code), natomiast **żaden commit wave 22–25** (ostatnie w `git log`) nie wdraża Dashboard V5 — to dalej rozbudowa klasycznych modułów AEIS.

**Rekomendacja** (do kolejnych etapów audytu): traktować `SYLION_Dashboard_V5_ClaudeCode_Package/` jako **specyfikację wzorcową** do porównania z aktualnym frontem. V5 prawdopodobnie ma być "następną generacją" (event-sourced + canvas), co implikuje znaczącą migrację architektoniczną, nie incremental patch.

---

## Podsumowanie ETAPU 1

- Front działa w **pełnym trybie desktop-first** z `(app)` shellem i 56 stronami konsoli — bogate pokrycie modułów AEIS 1:1 z backendem (Workers, Autoscaler, Build State, Observability, Governance, Decisions, SDR, Cellular, Funding, …).
- **Human Gate istnieje jako jeden komponent** (`HumanGatePanel`) w `/workspace` + płaska lista w `/gates`. Pokrywa ~15% specyfikacji Orchestratora z `AEIS_Global_Operator_Mobile_Human_Gate_Prompt.txt`. Brakuje klasyfikatora, kolejek P0–P4, batch approval, delegation engine, SLA, policy engine UI.
- **Mobile = NIE.** Brak natywnej aplikacji, brak PWA, brak service-workera, brak manifestu, brak zależności. Spec "AEIS Operator Mobile" / "Google Pixel Live Test Mode" = **0% implementacji**.
- **Dashboard V5** to tylko paczka specyfikacji — kod nie istnieje (brak Yjs/tldraw, brak event-sourced command bus UI).
