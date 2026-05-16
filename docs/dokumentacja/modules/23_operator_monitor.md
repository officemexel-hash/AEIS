# Surface: Operator Monitoring Dashboard (`/dashboard/operator-monitor`)
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Multi-projektowy panel KPI dla operatora — agregacja statusu wszystkich aktywnych projektów, throughput rekomendacji, zużycie budżetu, aktywność Rady oraz banery alertów. Centralny ekran codziennej pracy.

## Spis treści

1. [Cel + URL](#1-cel--url)
2. [Komponenty UI](#2-komponenty-ui)
3. [Wszystkie controls + interactions](#3-wszystkie-controls--interactions)
4. [State management](#4-state-management)
5. [API integration](#5-api-integration)
6. [Persistence (localStorage, cookies, sessionStorage)](#6-persistence-localstorage-cookies-sessionstorage)
7. [Modes / variants](#7-modes--variants)
8. [Accessibility](#8-accessibility)
9. [Przykładowe operator flows (step-by-step)](#9-przykładowe-operator-flows-step-by-step)
10. [Cross-references](#10-cross-references)

---

## 1. Cel + URL

| Pole | Wartość |
|------|---------|
| Route | `/dashboard/operator-monitor` |
| Plik strony | `src/sylion-frontend/src/app/(app)/dashboard/operator-monitor/page.tsx` |
| Components folder | `src/sylion-frontend/src/app/(app)/dashboard/operator-monitor/_components/` |
| Persona docelowa | Operator (codzienna praca, multi-project triage); admin (cross-org overview) |
| Backend hook | `useMonitoringSnapshot(30_000)` — refresh 30 sekund |
| Faza projektu (B.4) | Phase B.4 of the AEIS Advisor Layer |

**Co operator robi na tej stronie:**

- Widzi w jednym miejscu: liczbę aktywnych projektów, sumę aktywnych kart, średni accept rate, % zużycia budżetu globalnie.
- Patrzy na matrix project × phase i klika projekt → przechodzi do `/projects/{id}/lifecycle`.
- Analizuje throughput rekomendacji (emitted vs accepted vs rejected, 14 dni).
- Sprawdza cost vs budget globalnie i per-projekt (bar chart).
- Ogląda heatmapę aktywności Rady (24h × 7 dni).
- Reaguje na alerty (banner + tab `Alerts`) — klik → otwiera kartę w `/advisor/[cardId]`.
- Dostaje subscription advisor banner (jeśli system rekomenduje upgrade planu / dodatkowe moduły).

---

## 2. Komponenty UI

### 2.1 Hierarchia

```
OperatorMonitoringDashboardPage (page.tsx)
├── Header (title + auto-refresh badge + Refresh button)
├── MockBanner
├── 4× Kpi card                    -> Active projects / Active cards / Avg accept rate / Budget used
├── SubscriptionAdvisorBanner      -> renderowane warunkowo gdy są rekomendacje subscription
├── Tabs (4 zakładki)
│   ├── overview     -> ProjectsMatrix + (RecommendationThroughput | AlertsBanner)
│   ├── cost         -> CostVsBudget
│   ├── activity     -> CouncilActivityHeatmap + RecommendationThroughput
│   └── alerts       -> AlertsBanner
└── Footer card                    -> link "Need a deep-dive into a single project?" → /dashboard
```

### 2.2 Tabela komponentów

| Komponent | Plik | Linie | Rola |
|-----------|------|-------|------|
| `OperatorMonitoringDashboardPage` | `dashboard/operator-monitor/page.tsx` | 252 | Orkiestrator |
| `ProjectsMatrix` | `_components/ProjectsMatrix.tsx` | 217 | Heatmap projects × phases (rows = projekty, cols = fazy H01..H16). Klik wiersza → nawigacja do `/projects/{id}/lifecycle` |
| `RecommendationThroughput` | `_components/RecommendationThroughput.tsx` | 223 | Wykres line/area: emitted vs accepted vs rejected (14 dni) |
| `CostVsBudget` | `_components/CostVsBudget.tsx` | 208 | Globalny progress bar + bar chart per-project |
| `CouncilActivityHeatmap` | `_components/CouncilActivityHeatmap.tsx` | 155 | Heatmap głosów Rady (24h × 7 dni) |
| `SubscriptionAdvisorBanner` | `_components/SubscriptionAdvisorBanner.tsx` | 108 | Banner gdy system rekomenduje upgrade planu lub aktywację modułu |
| `AlertsBanner` | `_components/AlertsBanner.tsx` | 138 | Lista alertów z severity badge i przyciskiem `Open card` |
| `MockBanner` | `components/advisor/MockBanner.tsx` | (shared) | Pasek offline |

### 2.3 Kpi cards (inline w page.tsx)

| Kpi | Wartość | Akcent kolorystyczny | Akcessory |
|-----|---------|----------------------|-----------|
| Active projects | `snapshot.projects.length` | `text-sylion-blue` | brak |
| Active cards | `Σ projects.active_cards` | `text-sylion-amber` | brak |
| Avg accept rate | `Σ accept_rate / N · 100%` | `text-sylion-green` | brak |
| Budget used | `spend_usd / budget_usd · 100%` | `>=85% amber, >=100% red, else blue` | jeśli `criticalAlerts > 0` → `<X> critical` chip pod wartością |

---

## 3. Wszystkie controls + interactions

### 3.1 Header

| Control | Test ID | Akcja | API call |
|---------|---------|-------|----------|
| Badge `auto-refresh 30s` | brak | informacyjny | brak |
| Button `Refresh` | `aria-label="Refresh monitoring snapshot"` | wymusza `refresh()` przed kolejnym tickem | `GET /api/v1/advisor/monitoring/snapshot` |

### 3.2 Tabs

| Tab | Test ID | Renderuje |
|-----|---------|-----------|
| `overview` | `tab-overview` (inferred) | `ProjectsMatrix` + grid `RecommendationThroughput` + `AlertsBanner` |
| `cost` | `tab-cost` | `CostVsBudget` |
| `activity` | `tab-activity` | `CouncilActivityHeatmap` + `RecommendationThroughput` |
| `alerts` | `tab-alerts` | `AlertsBanner` (z licznikiem `snapshot.alerts.length` w badge) |

### 3.3 ProjectsMatrix

| Control | Akcja | API call |
|---------|-------|----------|
| Klik w wiersz projektu | `onSelectProject(id)` → `window.location.href = /projects/{id}/lifecycle` | brak (full page nav) |
| Hover na komórce | tooltip z `phase` + `cards count` | brak |

### 3.4 RecommendationThroughput

| Control | Akcja |
|---------|-------|
| Hover na punkcie wykresu | Recharts tooltip z `emitted/accepted/rejected` per timestamp |
| Toggle serii (legend) | Recharts standard — pokazuje/ukrywa linię |

### 3.5 CostVsBudget

| Control | Akcja |
|---------|-------|
| Progress bar globalny | informacyjny — kolor wg progu (zielony <70%, bursztynowy 70-90%, czerwony >90%) |
| Bar chart per-project | każdy bar pokazuje spend / budget; tooltip z dokładnymi liczbami |

### 3.6 CouncilActivityHeatmap

| Control | Akcja |
|---------|-------|
| Hover na komórce 24h × 7d | tooltip z `votes count` |
| Kolor komórki | gradient od `bg-muted` (0 votes) do `bg-sylion-blue` (max votes) |

### 3.7 SubscriptionAdvisorBanner

| Control | Akcja |
|---------|-------|
| Banner pojawia się gdy `snapshot.subscription_recommendations.length > 0` | wyświetla pierwszą rekomendację |
| Button `View details` (jeśli istnieje) | nawigacja do `/advisor/[cardId]` |
| Button `Dismiss` | ukrywa banner do następnego polling-u |

### 3.8 AlertsBanner

| Control | Akcja |
|---------|-------|
| Lista alertów | każdy ma severity badge (low/medium/high/critical) + tytuł |
| Klik w alert (jeśli ma `card_id`) | nawigacja do `/advisor/{card_id}` |
| Klik w alert bez `card_id` | informacyjny |

### 3.9 Footer card

| Control | Akcja |
|---------|-------|
| Link `Lifecycle dashboard` | `<a href="/dashboard">` (lub stary route) |

---

## 4. State management

### 4.1 Hook `useMonitoringSnapshot`

```typescript
const { snapshot, source, loading, refresh } = useMonitoringSnapshot(30_000);
```

- Polling: **30 sekund**.
- Fallback: `advisorMocks.monitoringSnapshot()` z 3 projektami, 14-dniowym throughput, 14-dniową council activity, 2 alertami.
- TTL reachability: 15 s.

### 4.2 Lokalny state

```typescript
const [tab, setTab] = useState<string>("overview");

const stats = useMemo(() => {
  const projectCount = snapshot.projects.length;
  const totalActiveCards = snapshot.projects.reduce((acc, p) => acc + p.active_cards, 0);
  const avgAcceptRate = projectCount > 0
    ? snapshot.projects.reduce((acc, p) => acc + p.accept_rate, 0) / projectCount
    : 0;
  const criticalAlerts = snapshot.alerts.filter((a) => a.severity === "critical").length;
  const usedPct = snapshot.cost_vs_budget.budget_usd > 0
    ? snapshot.cost_vs_budget.spend_usd / snapshot.cost_vs_budget.budget_usd
    : 0;
  return { projectCount, totalActiveCards, avgAcceptRate, criticalAlerts, usedPct };
}, [snapshot]);
```

### 4.3 Cache invalidation

| Wydarzenie | Inwalidacja |
|------------|-------------|
| Polling 30 s | re-fetch całego snapshot |
| Klik Refresh | natychmiastowy `refresh()` |
| Klik wiersza projektu | full nav (state znika) |

---

## 5. API integration

### 5.1 Endpoint

| Metoda | Endpoint | Wywołujący |
|--------|----------|------------|
| GET | `/api/v1/advisor/monitoring/snapshot` | `advisorApi.getMonitoringSnapshot()` |
| GET | `/api/v1/advisor/audit/recent?limit={n}` | `AuditTrailCard` w Cockpit v4 |
| GET | `/api/v1/advisor/teams/topology` | `AgentTopology` w Cockpit v4 |
| GET | `/api/v1/advisor/preferences/counts` | `ConfigurationControlCards` w Cockpit v4 |
| GET | `/api/v1/advisor/cards/{cardId}` | gdy operator klika alert z card_id (full nav do `/advisor/{cardId}`) |

Endpointy `audit/recent`, `teams/topology` i `preferences/counts` zostały dodane w sprint3
(commit 1ecdbce) jako backend gap-fill dla komponentów Cockpit v4.

#### `GET /api/v1/advisor/audit/recent`

Parametry: `limit` (int, 1–50, default 5), `user_id` (string, default `"default"`, ignorowany).

Odpowiedź: `{ "entries": [{ "id", "timestamp", "actor", "action", "target", "payload", "signature" }] }`

Źródło danych: tabela `audit_log` (sortowana `timestamp DESC LIMIT {limit}`). Przy błędzie DB — pusta lista.

#### `GET /api/v1/advisor/teams/topology`

Odpowiedź: `{ "nodes": [{ "id", "label", "active", "workers_count" }], "edges": [[from, to], ...] }`

Węzły (stała kolejność): `planner`, `workers`, `verifier`, `critic`, `council`.

Krawędzie: planner→workers, workers→verifier, verifier→critic, critic→council.

Dane `active` i `workers_count` pobierane z `get_orchestration_service().get_active_teams()`.
Klasyfikacja agentów do węzłów odbywa się przez `_classify_bucket(agent_type, current_task)` na podstawie słów kluczowych. Przy błędzie zwraca pusty graf z `active=False`.

#### `GET /api/v1/advisor/preferences/counts`

Odpowiedź: `{ "api_keys": int, "local_models": int, "routing_rules": int, "skills": int }`

Źródło: `engine_db.fetch_configuration_counts()`. Przy PG-only mode `api_keys = 0` (klucze API nadal w legacy SQLite vault poza zakresem tych tras).

### 5.2 TypeScript schema

```typescript
interface MonitoringSnapshot {
  /** Sprint3 nowe pola (1ecdbce) */
  strategy: string;             // "Balanced" | "Cost-saving" | "Aggressive" — z LLM routing preset
  active_teams: number;         // liczba aktywnych zespołów agentów
  avg_confidence: number;       // średni confidence_score 20 ostatnich rekomendacji (0..1)
  pending_hg: number;           // liczba nierozwiązanych kart human_gate_required
  hg_breakdown: string;         // JSON: [{ bucket, count }] — buckety po project_domain / card_type

  projects: Array<{
    project_id: string;
    project_name: string;
    project_type: string;        // "research" | "production" | "experiment"
    project_domain: string;
    active_phase: string;        // np. "H08 — SoT drafting"
    active_cards: number;
    accept_rate: number;         // 0..1
    spend_usd_month: number;
    budget_usd_month: number;
  }>;
  throughput: Array<{
    ts: number;
    emitted: number;
    accepted: number;
    rejected: number;
  }>;
  cost_vs_budget: {
    spend_usd: number;
    budget_usd: number;
    per_project: Record<string, { spend: number; budget: number }>;
  };
  council_activity: Array<{ ts: number; votes: number }>;
  subscription_recommendations: AdvisorCardEnvelope[];
  alerts: Array<{
    id: string;
    severity: "low" | "medium" | "high" | "critical";
    title: string;
    card_id?: string;
  }>;
}
```

### 5.3 Przykład odpowiedzi

```json
{
  "strategy": "Balanced",
  "active_teams": 2,
  "avg_confidence": 0.81,
  "pending_hg": 1,
  "hg_breakdown": "[{\"bucket\":\"software\",\"count\":1}]",
  "projects": [
    {
      "project_id": "p-1",
      "project_name": "Funding research bot",
      "project_type": "research",
      "project_domain": "funding",
      "active_phase": "H08 — SoT drafting",
      "active_cards": 3,
      "accept_rate": 0.74,
      "spend_usd_month": 38.21,
      "budget_usd_month": 120
    }
  ],
  "throughput": [
    { "ts": 1745000000, "emitted": 8, "accepted": 5, "rejected": 2 }
  ],
  "cost_vs_budget": {
    "spend_usd": 463.56,
    "budget_usd": 800,
    "per_project": {
      "p-1": { "spend": 38.21, "budget": 120 },
      "p-2": { "spend": 412.4, "budget": 600 }
    }
  },
  "council_activity": [{ "ts": 1745000000, "votes": 3 }],
  "subscription_recommendations": [],
  "alerts": [
    {
      "id": "alert-1",
      "severity": "critical",
      "title": "Production deploy blocked (mp-42)",
      "card_id": "demo-card-critical"
    }
  ]
}
```

---

## 6. Persistence

| Mechanizm | Co | TTL |
|-----------|-----|-----|
| `_reachable`/`_checkedAt` | reachability cache | 15 s |
| `tab` | aktywna zakładka, lokalny state | sesja |

**Strona nie używa localStorage / cookies.**

---

## 7. Modes / variants

### 7.1 Tryby źródła

`live` / `mock` / `loading` jak w innych advisor surfaces.

### 7.2 Empty states

| Stan | Renderowanie |
|------|--------------|
| `snapshot.projects.length === 0` | `ProjectsMatrix` pokazuje „Brak aktywnych projektów” |
| `snapshot.alerts.length === 0` | `AlertsBanner` pokazuje „Brak aktywnych alertów” |
| `snapshot.subscription_recommendations.length === 0` | `SubscriptionAdvisorBanner` w ogóle się nie renderuje (early return null) |

### 7.3 Loading

Pierwszy render: `snapshot = advisorMocks.monitoringSnapshot()` (fallback) → UI od razu pokazuje sensowne dane mock. Po pierwszym rzeczywistym fetchu się aktualizuje.

### 7.4 Variants Kpi

`Budget used` zmienia kolor:
- `<85%` → `text-sylion-blue` (default)
- `[85%, 100%)` → `text-sylion-amber`
- `>=100%` → `text-sylion-red`

Dodatkowo gdy `criticalAlerts > 0` — pod wartością Kpi `Budget used` pojawia się pomarańczowy chip „X critical”.

### 7.5 Tryb interfejsu: Operating Advisor Cockpit (sprint2, 2026-04-26)

Sprint 2 wprowadził **dwa tryby strony** sterowane przez `useAdvisorMode()`:

| Tryb | Tytuł strony | Układ |
|------|-------------|-------|
| `operator` | “Operating Advisor Cockpit” | Cockpit layout (sekcje poniżej) |
| `technical` | “Monitor operatora” | Oryginalny układ tabelaryczny (Tabs + KPI + ProjectsMatrix) |

Przełącznik widoczny w nagłówku jako ikona `LayoutDashboard` (cockpit) / `Terminal` (technical).

#### Układ Cockpit (tryb operator)

```
OperatorMonitoringDashboardPage (mode=operator)
├── Header (tytuł “Operating Advisor Cockpit” + mode toggle)
├── MockBanner (jeśli source != live)
├── CockpitHero             — hero split: opis systemu + top-priority card
├── CockpitDecisionSection  — “Co wymaga decyzji teraz” — top 3 karty
├── CockpitLifecycleStrip   — poziomy strip 16 faz lifecycle (H01–H16)
├── CockpitAgentFlow        — diagram: Planner → Workers → Verifier → Critic → Council
├── CockpitConfigStats      — siatka konfiguracji: API keys, models, routing, skills
└── CockpitFAQWidget        — accordion FAQ + link /faq
```

#### Nowe komponenty Cockpit

Folder: `src/sylion-frontend/src/components/dashboard/`

| Komponent | Plik | Opis |
|-----------|------|------|
| `CockpitHero` | `CockpitHero.tsx` | Hero split z AdvisorBubble pokazującą kartę o najwyższym `risk_level`. Status pills (strategia, Human Gates, blokady, zespoły) |
| `CockpitDecisionSection` | `CockpitDecisionSection.tsx` | Top 3 karty sortowane: `risk_level` malejąco, potem `d_level` malejąco. Link do `/advisor` gdy kart > 3 |
| `CockpitLifecycleStrip` | `CockpitLifecycleStrip.tsx` | 16 faz H01–H16 z polskimi etykietami i statusem per faza (`approved`/`in_progress`/`pending`/`blocked`) |
| `CockpitAgentFlow` | `CockpitAgentFlow.tsx` | 5-węzłowy diagram przepływu agentów (statyczny) |
| `CockpitConfigStats` | `CockpitConfigStats.tsx` | Siatka konfiguracji zdolności systemowych |
| `CockpitFAQWidget` | `CockpitFAQWidget.tsx` | Accordion FAQ entries + odsyłacz do `/faq` |

#### Fazy lifecycle w CockpitLifecycleStrip

H01 Konfiguracja modeli · H02 API providers · H03 Budzet · H04 Intake pomyslu ·
H05 Model SoT · H06 Formacja Rady · H07 Polityka autonomii · H08 Szkic SoT ·
H09 Masterplan · H10 Topologia runtime · H11 Skalowanie VPS · H12 Dobor Skills ·
H13 Deploy produkcyjny · H14 Testy · H15 Human Gate · H16 Finalna akceptacja

#### Dodatkowe hooki w trybie Cockpit

| Hook | Cel |
|------|-----|
| `useAdvisorFeed({ refreshMs: 8000 })` | Karty dla CockpitHero + CockpitDecisionSection |
| `useProjectLifecycle(featuredProjectId)` | Lifecycle pierwszego projektu dla CockpitLifecycleStrip |
| `useAdvisorMode()` | Odczyt `mode` + `toggle` dla przełącznika trybu |

---

## 8. Accessibility

### 8.1 ARIA

- `<h1>` dla nagłówka — w trybie operator: “Operating Advisor Cockpit”, w trybie technical: “Monitor operatora”.
- `Tabs` używa Radix → role/labels automatycznie.
- Każdy `Kpi` ma label nad wartością (np. „Active projects”).
- Badge auto-refresh nie jest live region (TODO: `aria-live` dla badge gdy `loading=true`).

### 8.2 Keyboard navigation

- `Tab`: header → Refresh button → tabs → tab content (interactives w środku) → footer link.
- `←/→` na tabs: przełącza zakładki (Radix).
- `Enter` na wierszu projektu w ProjectsMatrix: nav to lifecycle.

### 8.3 Color contrast

- KPI używa zarówno koloru, jak i ikony (FolderKanban, TrendingUp, CheckCircle2, CircleDollarSign).
- Heatmapa Council używa gradientu, którego skala jest pokazana w legendzie.

---

## 9. Przykładowe operator flows

### 9.1 Happy path: Operator weryfikuje status rano

1. Operator otwiera `/dashboard/operator-monitor` po przyjściu do biura.
2. `useMonitoringSnapshot(30_000)` startuje pierwszy fetch.
3. `GET /api/v1/advisor/monitoring/snapshot` zwraca: 3 projekty, throughput 14d, 2 alerty (1 critical, 1 medium).
4. UI renderuje 4 KPI: 3 / 6 / 74% / 58%.
5. Tab `overview` jest default. ProjectsMatrix pokazuje 3 wiersze z phase indicators.
6. Operator widzi czerwony alert „Production deploy blocked (mp-42)” w `AlertsBanner` po prawej.
7. Klik w alert → `card_id="demo-card-critical"` → nav do `/advisor/demo-card-critical`.
8. Operator obsługuje krytyczną decyzję, wraca do `/dashboard/operator-monitor`.
9. Po następnym ticku (30 s) alert znika, KPI „Active cards” spada do 5.

### 9.2 Happy path: Drill-down do projektu

1. Operator widzi w ProjectsMatrix że projekt `p-2 Operator console refresh` ma `active_phase = "H13 — production deploy"` w kolorze czerwonym (blocked).
2. Klika wiersz `p-2`.
3. `onSelectProject("p-2")` → `window.location.href = "/projects/p-2/lifecycle"`.
4. Pełna nawigacja do Lifecycle Dashboard projektu p-2.

### 9.3 Path: Sprawdzenie zużycia budżetu

1. Operator widzi w KPI że Budget used = 87% (kolor amber).
2. Klika tab `Cost & Budget`.
3. `CostVsBudget` renderuje:
   - Globalny progress bar 463.56 USD / 800 USD = 58%.
   - Bar chart per-project: p-1 (32%), p-2 (69%), p-3 (16%).
4. Widzi że p-2 jest najbliższy limitu (412.4 USD / 600 USD).
5. Klik w bar p-2 (jeśli interactivny) → nav do `/projects/p-2/lifecycle`.

### 9.4 Path: Activity heatmap (Council)

1. Operator klika tab `Council Activity`.
2. `CouncilActivityHeatmap` pokazuje grid 24h × 7d.
3. Operator widzi że największa aktywność Rady jest w środy 14:00-18:00 (najciemniejsze niebieskie komórki).
4. Pod heatmapą `RecommendationThroughput` z 14-dniowym wykresem — average ~10 emitted/dzień.

### 9.5 Error path: Backend offline

1. Operator otwiera dashboard. Backend offline.
2. `MockBanner` u góry: „Backend offline”.
3. UI pokazuje mock 3 projekty z mock throughput. Action buttons (Refresh) nie zmieniają stanu.
4. Po wstaniu backendu (np. 2 min później), kolejny tick (30 s) zaciągnie real data; banner zniknie.

---

## 10. Cross-references

### 10.1 Backend modules

| Moduł | Plik | Rola |
|-------|------|------|
| Monitoring snapshot aggregator | `src/sylion-pipeline/sylion/aeis/advisor/monitoring/` | Buduje snapshot z różnych źródeł (projects, cards, council, costs) |
| Cost tracker | `sylion.aeis.advisor.costs` | spend_usd_month, budget_usd_month |
| Council activity tracker | `sylion.aeis.council.activity` | votes per timestamp |
| Subscription advisor | `sylion.aeis.advisor.subscription` | recommendations dla planów / modułów |

### 10.2 Architecture docs

- `docs/claude_parallel/aeis_advisor/00_architecture/00_master_spec.md` — sekcja „Operator Monitoring B.4”.

### 10.3 Pokrewne surfaces

| Surface | Powód |
|---------|-------|
| `/projects/[id]/lifecycle` | Drill-down z kliku w ProjectsMatrix |
| `/advisor/[cardId]` | Klik w alert → szczegół karty |
| `/budget` | Pełna konfiguracja budżetu (CostVsBudget pokazuje tylko snapshot) |
| `/governance` | Council voting view (CouncilActivityHeatmap pokazuje tylko historię) |
| `/costs` | Detalna analiza kosztów per provider/model |
| `/faq` | CockpitFAQWidget linkuje do pełnego FAQ; tryb Cockpit |

### 10.4 Powiązana dokumentacja

- [`02_operational_manual.md`](../02_operational_manual.md) — runbook „daily morning check”.
- [`29_faq_runbook.md`](29_faq_runbook.md) — pełna dokumentacja FAQ surface i komponentów Cockpit.
- [`28_orchestration_panel.md`](28_orchestration_panel.md) — `CockpitConfigStats` bazuje na danych J1–J5.
