# Surface: Project Lifecycle Dashboard (`/projects/[projectId]/lifecycle`)
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Per-projekt dashboard prezentujący 16 hooków cyklu życia (H01–H16), aktywne karty doradcy, status każdej fazy oraz nawigację typu „j/k” pomiędzy fazami. Jeden z głównych ekranów decyzyjnych operatora.

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
| Route | `/projects/[projectId]/lifecycle` |
| Plik strony | `src/sylion-frontend/src/app/(app)/projects/[projectId]/lifecycle/page.tsx` |
| Components folder | `src/sylion-frontend/src/app/(app)/projects/[projectId]/lifecycle/_components/` |
| Persona docelowa | Operator (deep-dive na pojedynczym projekcie); auditor (do podglądu approved phases) |
| Backend hook | `useProjectLifecycle(projectId)` z polling 12 s |
| Liczba hooków faz | 16 (H01–H16) |

**Co operator robi na tej stronie:**

- Patrzy na timeline 16 faz cyklu życia projektu — kolorowane wg statusu (`approved` zielony, `in_progress` niebieski, `blocked` czerwony, `pending` szary).
- Klika fazę → otwiera `PhaseDetailModal` z aktywnymi kartami z `DecisionCardCard` w wariancie compact.
- Filtruje fazy przez search (`H08`, `sot`, `deploy`, ...).
- Używa skrótów klawiszowych `j` / `k` żeby przejść do następnej / poprzedniej fazy (LifecycleQuickActions).
- Widzi panel `ActiveCardsPanel` z kartami obecnie aktywnymi w tym projekcie (filtr `project_id`).
- Otwiera Flow Chart (alternatywna wizualizacja) gdy chce zobaczyć topologię eventów.

---

## 2. Komponenty UI

### 2.1 Hierarchia

```
ProjectLifecyclePage (page.tsx)
├── MockBanner                 -> banner offline
├── LifecycleHeader            -> nagłówek: project_id, project_type, project_domain, badges
├── LifecycleQuickActions      -> kontrolki nawigacyjne (Prev/Next/Search) + skróty j/k
├── 4× StatusTile              -> liczniki Approved / In progress / Blocked / Pending
├── Card "16-phase timeline"
│   ├── Search input            -> filtrowanie po hook_id lub event_type
│   └── PhaseTimeline (komponent globalny advisor) -> linia kafelków z 16 fazami
├── LifecycleFlowChart         -> graf eventów (alternatywa do timeline)
├── grid lg:grid-cols-2
│   ├── ActiveCardsPanel       -> aktywne karty doradcy filtrowane po project_id
│   └── Card "Selected phase"  -> podsumowanie wybranej fazy + button Open detail modal
├── PhaseDetailModal           -> modal z DecisionCardCard (variant compact) per faza
└── EmptyState (gdy lifecycle.phases.length === 0)
```

### 2.2 Tabela komponentów

| Komponent | Plik | Rola |
|-----------|------|------|
| `LifecycleHeader` | `_components/LifecycleHeader.tsx` | Nagłówek z badge dla project_type, project_domain |
| `LifecycleQuickActions` | `_components/LifecycleQuickActions.tsx` | Buttons + keyboard hints (j/k) + Search focus |
| `LifecycleFlowChart` | `_components/LifecycleFlowChart.tsx` | Wizualizacja grafu eventów AEIS (16 hooków + cross-links) |
| `PhaseStatusCard` | `_components/PhaseStatusCard.tsx` | Pojedyncza karta fazy (alt rendering) |
| `ActiveCardsPanel` | `_components/ActiveCardsPanel.tsx` | Lista aktywnych Advisor Cards (DecisionCardCard variant compact) per project |
| `EmptyState` | `_components/EmptyState.tsx` | Gdy projekt nie ma jeszcze żadnej fazy |
| `PhaseDetailModal` | `_components/PhaseDetailModal.tsx` | Modal: nagłówek H?? + kafelek statusu + lista kart fazy |
| `PhaseTimeline` | `components/advisor/PhaseTimeline.tsx` | Globalny komponent — kafelki H01–H16, podświetlony selected |
| `DecisionCardCard` | `components/advisor/DecisionCardCard.tsx` | Pełne body karty (akcje, evidence link) |

### 2.3 Mapa fazy → tytuł

```typescript
// _components/PhaseDetailModal.tsx:11-28
const PHASE_TITLES: Record<string, string> = {
  H01: "Model setup",
  H02: "API providers",
  H03: "Budget configuration",
  H04: "Idea intake",
  H05: "Source-of-Truth model",
  H06: "Council formation",
  H07: "Autonomy policy",
  H08: "Source-of-Truth drafting",
  H09: "Masterplan",
  H10: "Runtime topology",
  H11: "VPS scaling",
  H12: "Skill selection",
  H13: "Production deploy",
  H14: "Testing",
  H15: "Human Gate",
  H16: "Final approval",
};
```

### 2.4 Mapa eventów (z mock data)

| hook_id | hook_event_type | Faza |
|---------|-----------------|------|
| H01 | `aeis.system.model_setup_requested` | Model setup |
| H02 | `aeis.system.api_provider_setup_requested` | API providers |
| H03 | `aeis.system.budget_config_requested` | Budget |
| H04 | `aeis.idea.intake.completed` | Idea intake |
| H05 | `aeis.idea.sot_model_selection_requested` | SoT model |
| H06 | `aeis.council.formation_requested` | Council |
| H07 | `aeis.system.autonomy_policy_change_requested` | Autonomy |
| H08 | `aeis.idea.sot_drafted` | SoT drafting |
| H09 | `aeis.masterplan.created` | Masterplan |
| H10 | `aeis.system.runtime_topology_change_requested` | Runtime topology |
| H11 | `aeis.system.vps_scaling_requested` | VPS scaling |
| H12 | `aeis.system.skill_selection_requested` | Skill selection |
| H13 | `aeis.production.deploy_requested` | Production deploy |
| H14 | `aeis.testing.started` | Testing |
| H15 | `aeis.human_gate.ticket_pending` | Human Gate |
| H16 | `aeis.final_approval.requested` | Final approval |

---

## 3. Wszystkie controls + interactions

### 3.1 LifecycleHeader

| Control | Akcja |
|---------|-------|
| Badge `project_type` | informacyjny (np. `production` / `research` / `experiment`) |
| Badge `project_domain` | informacyjny (`software`, `funding`, etc.) |
| Title `project_id` | informacyjny (truncate jeśli długi) |

### 3.2 LifecycleQuickActions

| Control | Test ID | Akcja | State change |
|---------|---------|-------|--------------|
| Przycisk `Prev phase` | `lifecycle-prev` | przesuwa `selectedHookId` o jedną fazę wstecz | `setSelectedHookId(phases[idx-1].hook_id)` |
| Przycisk `Next phase` | `lifecycle-next` | przesuwa o jedną w przód | `setSelectedHookId(phases[idx+1].hook_id)` |
| Przycisk `Focus search` | `lifecycle-focus-search` | focus na input search | `searchRef.current?.focus()` |
| Skrót klawiszowy `j` | (global w stronie) | = `Next phase` | identyczny |
| Skrót klawiszowy `k` | (global w stronie) | = `Prev phase` | identyczny |
| Skrót klawiszowy `/` | (lub `s`) | focus search | identyczny |

### 3.3 Search input

| Control | Test ID | Akcja | API call |
|---------|---------|-------|----------|
| Input search | `lifecycle-search` | filtruje `phases` po `hook_id.includes(q)` lub `hook_event_type.includes(q)` | brak (filtr klientowy) |
| Wyczyść (X) | brak | reset `setSearch("")` | brak |

### 3.4 PhaseTimeline (16 kafelków)

| Control | Akcja | API call | State change |
|---------|-------|----------|--------------|
| Klik w kafelek `H01..H16` | `handlePhaseClick(hookId)` | brak | `setSelectedHookId(hookId)`, `setModalOpen(true)` |
| Hover na kafelku | tooltip z `hook_event_type` | brak | brak |

### 3.5 PhaseDetailModal

| Control | Test ID | Akcja |
|---------|---------|-------|
| Klik X (zamknij) | brak | `onOpenChange(false)` |
| Outside click / ESC | brak (nie disabled) | zamyka modal |
| Lista `cards[]` per faza | renderuje `DecisionCardCard variant="compact"` | każda karta ma swoje akcje (POST /actions) |

### 3.6 Selected phase summary card (right panel)

| Control | Test ID | Akcja |
|---------|---------|-------|
| Przycisk `Open detail modal` | `open-phase-modal` | `setModalOpen(true)` |
| Tekst hookId | `phase-summary-card` | informacyjny |
| Liczba kart `Cards: N` | informacyjna | brak |

### 3.7 ActiveCardsPanel

Renderuje karty z `useAdvisorFeed({ project_id })`. Każda karta otwiera akcje POST jak w `/advisor`.

### 3.8 LifecycleFlowChart

Alternatywna wizualizacja (graf z framer-motion). Klik w węzeł = `handlePhaseClick(hookId)` → ten sam state change co w timeline.

### 3.9 4× StatusTile

| Tile | Pole | Wzór |
|------|------|------|
| `Approved` | `status.approved` | `phases.filter(p => p.status === "approved").length` |
| `In progress` | `status.in_progress` | analogicznie |
| `Blocked` | `status.blocked` | analogicznie |
| `Pending` | `status.pending` | analogicznie |

Tile jest informacyjny; klik nie wywołuje akcji.

---

## 4. State management

### 4.1 Lokalny state strony

```typescript
const params = useParams<{ projectId: string }>();
const projectId = String(params?.projectId ?? "");

const { lifecycle, source, loading } = useProjectLifecycle(projectId || null);

const [selectedHookId, setSelectedHookId] = useState<string | null>(null);
const [modalOpen, setModalOpen] = useState(false);
const [search, setSearch] = useState("");
const searchRef = useRef<HTMLInputElement | null>(null);

const phases: ProjectLifecyclePhase[] = useMemo(() => lifecycle?.phases ?? [], [lifecycle]);
```

- `selectedHookId` — sterowany klikiem w timeline lub przyciskiem Prev/Next.
- `modalOpen` — niezależny od `selectedHookId` (można zamknąć modal i pozostawić zaznaczoną fazę w summary card).
- `search` — query filtra; aktualizowany onChange.
- `searchRef` — ref do focus przez button `Focus search`.

### 4.2 Hook `useProjectLifecycle`

```typescript
export function useProjectLifecycle(projectId: string | null) {
  const fetcher = useCallback(
    async (): Promise<ProjectLifecycleState | null> =>
      projectId ? advisorApi.getProjectLifecycle(projectId) : null,
    [projectId],
  );
  const fallback = projectId ? advisorMocks.projectLifecycle(projectId) : null;
  const { data, loading, error, source, refresh } = useFetch<ProjectLifecycleState | null>(fetcher, fallback, 12000);
  return { lifecycle: data, loading, error, source, refresh };
}
```

- Polling: **12 sekund** (rzadszy niż `useAdvisorFeed` 6 s, bo zmiany faz są wolniejsze).
- Fallback: `advisorMocks.projectLifecycle(projectId)` zwraca 16 mock phases (H13 jako `blocked`, H14–H16 `pending`, reszta `approved`).
- TTL reachability: 15 s (wspólne z innymi hookami advisor).

### 4.3 Useffect — auto-clean modal

```typescript
useEffect(() => {
  if (modalCard) {
    const stillPresent = cards.find((c) => c.header.card_id === modalCard.header.card_id);
    if (!stillPresent) {
      setModalCard(null);
      return;
    }
  }
  // ... auto-pickup logic
}, [cards, sorted, modalCard]);
```

Analogiczny pattern do `/advisor` — gdy karta znika z feedu (zaakceptowana), modal automatycznie się zamyka.

### 4.4 Cache invalidation

| Wydarzenie | Inwalidacja |
|------------|-------------|
| Polling 12 s | re-fetch całego `lifecycle` |
| Klik Refresh (jeśli istnieje) | `useFetch.run()` |
| Akcja na karcie wewnątrz `PhaseDetailModal` | brak natychmiastowej; kolejny tick aktualizuje `phase.cards` |

---

## 5. API integration

### 5.1 Endpointy

| Metoda | Endpoint | Wywołujący | Typ odpowiedzi |
|--------|----------|------------|----------------|
| GET | `/api/v1/advisor/projects/{projectId}/lifecycle` | `useProjectLifecycle` | `ProjectLifecycleState` |
| GET | `/api/v1/advisor/cards?operator_id={uuid}&project_id={projectId}&limit=50` | `useAdvisorFeed({ project_id })` (w ActiveCardsPanel) | `{ cards: AdvisorCardEnvelope[] }` |
| POST | `/api/v1/advisor/cards/{cardId}/actions` | DecisionCardCard wewnątrz modala | `HandleActionResponse` |
| GET | `/api/v1/advisor/evidence/{packId}` | gdy operator otworzy Evidence Pack z karty | `EvidencePack` |

### 5.2 TypeScript schema

```typescript
export interface ProjectLifecyclePhase {
  hook_id: string;                // "H01".."H16"
  hook_event_type: string;        // np. "aeis.production.deploy_requested"
  status: "pending" | "in_progress" | "approved" | "blocked";
  cards: AdvisorCardEnvelope[];   // karty obecnie aktywne dla tej fazy
  last_event_at?: number;         // unix seconds
}

export interface ProjectLifecycleState {
  project_id: string;
  project_type: string;
  project_domain: string;
  phases: ProjectLifecyclePhase[];  // dokładnie 16 elementów
}
```

### 5.3 Przykład odpowiedzi

```json
{
  "project_id": "proj-abc-001",
  "project_type": "production",
  "project_domain": "software",
  "phases": [
    {
      "hook_id": "H01",
      "hook_event_type": "aeis.system.model_setup_requested",
      "status": "approved",
      "cards": [],
      "last_event_at": 1745000000
    },
    {
      "hook_id": "H08",
      "hook_event_type": "aeis.idea.sot_drafted",
      "status": "in_progress",
      "cards": [{ "envelope_version": "1.0.0", "header": {...}, "body": {...} }],
      "last_event_at": 1745625100
    },
    {
      "hook_id": "H13",
      "hook_event_type": "aeis.production.deploy_requested",
      "status": "blocked",
      "cards": [{ "envelope_version": "1.0.0", "header": {"risk_level": "critical", ...}, ... }]
    }
  ]
}
```

---

## 6. Persistence (localStorage, cookies, sessionStorage)

| Mechanizm | Co | TTL |
|-----------|-----|-----|
| `_reachable`/`_checkedAt` (module-level) | TTL backend reachability | 15 s |
| `selectedHookId`, `search`, `modalOpen` | wyłącznie React state | sesja, reset po reload |

**Strona nie używa localStorage / cookies.** Po reload `selectedHookId` resetuje się do `null`, search do pustego.

---

## 7. Modes / variants

### 7.1 Tryby źródła danych

Identycznie jak `/advisor`: `live` / `mock` / `loading`. `MockBanner` u góry.

### 7.2 Empty state

Gdy `!loading && (!lifecycle || phases.length === 0)`:

```tsx
<EmptyState projectId={projectId} />
```

Renderuje komunikat „Projekt {projectId} nie ma jeszcze faz cyklu życia. Hooki H01–H16 zostaną zarejestrowane gdy projekt rozpocznie pracę.”

### 7.3 Loading state

`loading === true && !lifecycle`: cała sekcja po nagłówku jest pusta (Skeleton TODO). Aktualnie pokazuje header + status tiles z zerami.

### 7.4 Variant: filtered timeline

Gdy `search.trim().length > 0`:

- `filteredPhases` → tylko fazy zawierające query.
- Jeśli `filteredPhases.length === 0` → tekst „No phases match `<query>`” pod timeline.
- `PhaseTimeline` renderuje tylko widoczne fazy (mniejszy timeline).

### 7.5 Variant: PhaseDetailModal

| Stan | Renderowanie |
|------|--------------|
| `phase === null` | `<DialogTitle>—</DialogTitle>` + meta dashes |
| `phase.cards.length === 0` | „Brak aktywnych kart dla tej fazy.” |
| `phase.cards.length > 0` | `<DecisionCardCard variant="compact" />` per karta |

---

## 8. Accessibility

### 8.1 ARIA

- `<h1>` z tytułem projektu w `LifecycleHeader`.
- `<h2>` „16-phase timeline” w sekcji timeline.
- `Search input` używa `<label className="relative">` zamiast jawnego `aria-label` — TODO: dodać `aria-label="Filter phases"`.
- `PhaseDetailModal` używa `Dialog` z Radix → `role="dialog" aria-modal="true"` automatycznie.

### 8.2 Keyboard navigation

| Klawisz | Akcja |
|---------|-------|
| `j` | next phase |
| `k` | prev phase |
| `/` lub `s` | focus search |
| `Tab` | navigacja przez timeline kafelki, status tiles, summary card |
| `Enter` na kafelku | otwiera `PhaseDetailModal` |
| `Esc` w modalu | zamyka modal |

### 8.3 Color contrast

- Statusy:
  - `approved` — `text-sylion-green` (WCAG AA na ciemnym tle)
  - `in_progress` — `text-sylion-blue`
  - `blocked` — `text-sylion-red`
  - `pending` — `text-muted-foreground` (kontrast >4.5:1)
- Każdy status ma także ikonę (CheckCircle / Activity / X / Clock) — informacja nie polega tylko na kolorze.

---

## 9. Przykładowe operator flows (step-by-step)

### 9.1 Happy path: Operator weryfikuje deploy production

1. Operator klika kafelek projektu w `/dashboard/operator-monitor` → router push `/projects/proj-abc-001/lifecycle`.
2. `ProjectLifecyclePage` montuje się; `useProjectLifecycle("proj-abc-001")` startuje.
3. `GET /api/v1/advisor/projects/proj-abc-001/lifecycle` zwraca state z 16 fazami: H01–H12 approved, H13 blocked (critical), H14–H16 pending.
4. UI renderuje:
   - `LifecycleHeader`: project_type=`production`, project_domain=`software`.
   - `LifecycleQuickActions`: hint klawiszy „press j/k to navigate”.
   - 4× `StatusTile`: Approved=12, In progress=0, Blocked=1, Pending=3.
   - `PhaseTimeline` z 16 kafelkami; H13 podświetlony czerwono.
   - `LifecycleFlowChart`: graf z czerwoną krawędzią między H12 a H13.
   - `ActiveCardsPanel`: jedna karta critical (z H13).
5. Operator klika kafelek H13 w timeline.
6. `handlePhaseClick("H13")` → `setSelectedHookId("H13")`, `setModalOpen(true)`.
7. `PhaseDetailModal` otwiera się: tytuł „H13 — Production deploy”, status badge `blocked` (czerwony), event_type `aeis.production.deploy_requested`.
8. Modal pokazuje listę kart: jedna `DecisionCardCard variant="compact"`: „BLOCK production deploy — SoT not approved”.
9. Operator klika `Open Evidence Pack` na karcie.
10. `GET /api/v1/advisor/evidence/{packId}` zwraca pełen D5 pack.
11. Operator weryfikuje rollback plan, zamyka Evidence dialog.
12. Wraca do PhaseDetailModal. Klika `Convert to Human Gate` na karcie.
13. `POST /api/v1/advisor/cards/{cardId}/actions` z `{ "action": "convert_to_human_gate" }`.
14. Backend zwraca `{ created_human_gate_ticket_id: "hg-tkt-44", ... }`.
15. Po następnym ticku polling-u (12 s) `useProjectLifecycle` zwraca zaktualizowany state — H13 nadal `blocked` (do czasu approval SoT), ale karta zniknęła (przeniesiona do Human Gate).
16. Operator zamyka modal (Esc), pokazuje się summary card po prawej z H13 + `0 cards`.

### 9.2 Path: Nawigacja klawiszowa j/k

1. Operator chce szybko przejrzeć wszystkie fazy.
2. Naciska `j` (focus globalny na stronie). `LifecycleQuickActions` wywołuje `handleNextPhase()`.
3. `phases.findIndex(...) === -1` (selectedHookId jest null) → `nextIndex = 0` → `setSelectedHookId("H01")`.
4. Summary card po prawej pokazuje: „H01 — Model setup, status approved, cards 0”.
5. Operator naciska `j` ponownie. `nextIndex = min(0+1, 15) = 1` → H02.
6. Powtarza `j` 11 razy → dochodzi do H13. Summary pokazuje status `blocked`, cards `1`.
7. Klika `Open detail modal` lub naciska `Enter` na summary → modal otwiera się z H13.
8. Po inspekcji naciska `k` (prev phase) → wraca do H12 approved.

### 9.3 Path: Search „sot”

1. Operator chce zobaczyć wszystkie fazy SoT (Source-of-Truth).
2. Naciska `/` → focus search (lub klik w przycisk `Focus search`).
3. Wpisuje `sot` w search input.
4. `filteredPhases = phases.filter(p => p.hook_id.toLowerCase().includes("sot") || p.hook_event_type.toLowerCase().includes("sot"))`.
5. Wynik: H05 (`aeis.idea.sot_model_selection_requested`) + H08 (`aeis.idea.sot_drafted`).
6. PhaseTimeline renderuje tylko 2 kafelki.
7. Operator klika H08 → modal otwiera się.

### 9.4 Error path: Backend offline

1. Operator otwiera `/projects/proj-xyz-002/lifecycle`. Backend nieosiągalny.
2. `useProjectLifecycle` → `source = "mock"`, `lifecycle = advisorMocks.projectLifecycle("proj-xyz-002")`.
3. `MockBanner` u góry: „Backend offline — wyświetlam dane demonstracyjne”.
4. Mock state: 16 faz, H13 jako `blocked`, H14–H16 `pending`.
5. Operator może klikać kafelki, otwierać modale — ale akcje na kartach (POST) zwrócą stub.
6. Po wstaniu backendu, kolejny tick polling-u (12 s) zaciągnie real data.

---

## 10. Cross-references

### 10.1 Backend modules

| Moduł | Plik | Rola |
|-------|------|------|
| Lifecycle hooks engine | `src/sylion-pipeline/sylion/aeis/advisor/lifecycle_hooks/` | Re-emisja eventów AEIS jako `aeis.advisor.hook.<HID>.fired` |
| Project state aggregator | `sylion.aeis.advisor.lifecycle.aggregator` | Buduje `ProjectLifecycleState` z eventów |
| Mobile gateway routes | `sylion.aeis.advisor.mobile_gateway` | Endpoint `/projects/{id}/lifecycle` |

### 10.2 Architecture docs

- `docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks.md` — pełna specyfikacja 16 hooków, eventów wejściowych/wyjściowych, statusów.
- `docs/claude_parallel/aeis_advisor/00_architecture/04_lifecycle_hooks_audit_results.md` — wyniki audytu 16 hooków (which fire, which fail).
- `docs/claude_parallel/aeis_advisor/00_architecture/07_event_taxonomy.md` — taksonomia eventów `aeis.*`.

### 10.3 Pokrewne surfaces

| Surface | Powód |
|---------|-------|
| `/dashboard/operator-monitor` | Multi-project view; klik w projekt przenosi tu |
| `/advisor` | Globalny feed; karty z tego projektu pojawiają się w `ActiveCardsPanel` |
| `/projects/[projectId]` | Project overview (nie-lifecycle, generic project page) |
| `/governance` | Council vote dla decyzji w fazie H06 lub H16 |
| `/audit` | Każde zdarzenie cyklu życia jest zapisane w audit trail |

### 10.4 Powiązana dokumentacja

- [`01_modul_aeis_advisor.md`](../01_modul_aeis_advisor.md)
- [`02_operational_manual.md`](../02_operational_manual.md) — runbook „odblokowanie zablokowanej fazy H13”
- [`03_governance_audit_compliance.md`](../03_governance_audit_compliance.md)
