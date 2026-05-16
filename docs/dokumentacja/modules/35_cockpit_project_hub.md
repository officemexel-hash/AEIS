# Surface: Cockpit Project Hub (`/advisor/cockpit`)
> Status dokumentacji: DONE_SYNC_P3_004 (2026-05-13)
> Runtime status: patrz `../DOCS_RUNTIME_SYNC_2026_05_13.md`. Ten plik jest dokumentem modulowym; fakty runtime maja pierwszenstwo przed starszym opisem.

> Dokumentacja modulu Project Hub w widoku Cockpit v4 AEIS Advisor.
> Zrodlo: commit `df504823` (sprint5).
> Problem operator: "nie widze w centrum dowodzenia w dashboard 'zacznij nowy projekt'
> albo wybierz z listy projektow, albo modyfikuj projekt" — rozwiazanie: Project Hub.

## Spis tresci

1. [Cel + URL](#1-cel--url)
2. [Komponenty UI](#2-komponenty-ui)
3. [Wszystkie controls + interactions](#3-wszystkie-controls--interactions)
4. [State management](#4-state-management)
5. [API integration](#5-api-integration)
6. [Persistence (localStorage)](#6-persistence-localstorage)
7. [Modes / variants](#7-modes--variants)
8. [Accessibility](#8-accessibility)
9. [Przykladowe operator flows (step-by-step)](#9-przykladowe-operator-flows-step-by-step)
10. [Cross-references](#10-cross-references)

---

## 1. Cel + URL

| Pole | Wartosc |
|------|---------|
| Route | `/advisor/cockpit` |
| Plik strony | `src/sylion-frontend/src/app/(app)/advisor/cockpit/page.tsx` |
| Glowny komponent hub | `src/sylion-frontend/src/components/advisor/ProjectHub.tsx` |
| API client | `src/sylion-frontend/src/lib/api/projects.ts` |
| Persona docelowa | Operator pracujacy z wieloma projektami jednoczesnie |
| Backend prefix | `/api/v1/projects` |

Project Hub to warstwa kontekstu projektu wbudowana w Cockpit. Odpowiada za trzy potrzeby:

1. **Wybor aktywnego projektu** — operator widzi jaki projekt jest aktywny i moze go przelaczac bez wychodzenia z Cockpit.
2. **Szybkie tworzenie nowego projektu** — modal dostepny jednym kliknieciem.
3. **Podglad ostatnich projektow** — pas 5 najnowszych projektow posortowanych po `updated_at DESC`.

`activeProjectId` propaguje sie do `LifecycleRail` i wszystkich sekcji Cockpit — zmiana aktywnego projektu odswiezza caly kontekst cockpitu bez przeladowania strony.

---

## 2. Komponenty UI

### 2.1 Hierarchia

```
cockpit/page.tsx
└── ProjectHubProvider (ProjectHub.tsx)
    ├── CockpitInner (page.tsx — renderowany przez children callback)
    │   ├── ProjectHubHeroRow
    │   │   └── ProjectSwitcher.tsx (dropdown prawy-gorny naroznik hero)
    │   ├── ProjectHubStrip
    │   │   └── RecentProjectsStrip.tsx (5 kafelkow projektow)
    │   └── ... inne sekcje Cockpit (LifecycleRail, AdvisorCore, itd.)
    └── NewProjectModal.tsx (portal dialog, montowany gdy showNewModal=true)
```

### 2.2 Tabela komponentow

| Komponent | Plik | Rola |
|-----------|------|------|
| `ProjectHubProvider` | `ProjectHub.tsx` | Context provider: `activeProjectId`, `showNewModal`, bootstrap z localStorage |
| `ProjectHubHeroRow` | `ProjectHub.tsx` | Wrapper eksportowany dla hero-row Cockpit (renderuje ProjectSwitcher) |
| `ProjectHubStrip` | `ProjectHub.tsx` | Wrapper eksportowany dla pasa projektow (renderuje RecentProjectsStrip) |
| `ProjectSwitcher` | `ProjectSwitcher.tsx` | Dropdown "aktywny projekt" w prawym gornym narozeniku hero |
| `NewProjectModal` | `NewProjectModal.tsx` | Dialog tworzenia projektu (pola: title, idea, kind, constraints, stack) |
| `RecentProjectsStrip` | `RecentProjectsStrip.tsx` | Pas 5 kafelkow ostatnich projektow |
| `useProjectHub` | `ProjectHub.tsx` | Hook do odczytu kontekstu hub we wnukach |

---

## 3. Wszystkie controls + interactions

### 3.1 ProjectSwitcher — dropdown aktywnego projektu

| Element | Akcja |
|---------|-------|
| Przycisk z nazwa aktywnego projektu + ikona `ChevronsUpDown` | Otwiera / zamyka dropdown |
| Lista projektow (max 60 wysokosc, scrollowalny) | Klikniecie projektu → `onSelectProject(id)` → `setActiveProjectId(id)` |
| Kafelek projektu | Ikona statusu (zielona = active/in_progress, szara = draft/inne) + truncated title + link-ikona edycji → `/projects/[id]` |
| Przycisk "Nowy projekt" z ikona `Plus` | `onNewProject()` → `setShowNewModal(true)` |
| Link "Wszystkie projekty" | `href="/projects"` |
| Click-outside | Zamyka dropdown |

Status dots w ProjectSwitcher:

| `project.status` | Kolor |
|-----------------|-------|
| `active` | zielony |
| `in_progress` | zielony |
| `draft` | szary |
| `blocked` | czerwony |
| `completed` | niebieski |
| inne | szary |

### 3.2 NewProjectModal — formularz nowego projektu

Komponent uzywa `@base-ui/react Dialog` (portal). Pola:

| Pole | Control | Walidacja |
|------|---------|-----------|
| Tytu projektu | `<input type="text">` | niepuste, max ~120 znakow |
| Opis / pomysl | `<textarea>` | opcjonalne |
| Rodzaj projektu | `<select>` | `application \| research \| audit \| funding \| other` |
| Ograniczenia | `<input type="text">` | opcjonalne |
| Stack (tagi) | tags-input (spacja/Enter dodaje tag) | opcjonalne |

Akcje:

| Przycisk | Akcja |
|----------|-------|
| Anuluj / X | `onClose()` → `setShowNewModal(false)` |
| Stworz projekt | `projectsApi.create(payload)` → po sukcesie: `onCreated(project)` → `setActiveProjectId(project.project_id)` + zamkniecie modalu |

### 3.3 RecentProjectsStrip — pas 5 ostatnich projektow

- 5 kafelkow (`w-52 h-20`) sortowanych po `updated_at DESC`.
- Projekty ze statusem `deleted` sa pomijane.
- Aktywny projekt: obramowanie niebieskie (`border-blue-500/40`).

| Element kafelka | Zawartosc |
|----------------|-----------|
| Ikona statusu | `CircleDot` (active), `AlertCircle` (blocked), `CheckCircle2` (completed), `Clock` (draft) |
| Badge statusu | etykieta w kolorze wg `STATUS_CONFIG` |
| Tytu projektu | truncated, max 1 linia |
| Czas | wzgledny `fmt(updated_at)`: "Xm temu" / "Xh temu" / "DD Mon" |
| Strzalka `ArrowRight` | link do `/projects/[id]/lifecycle` |
| Loading skeleton | 4 szare kwadraty `animate-pulse` podczas ladowania |
| Empty state | komunikat "Nie ma jeszcze projektow" |

Klikniecie kafelka → `onSelectProject(id)`.

---

## 4. State management

### 4.1 ProjectHubContext

```typescript
interface ProjectHubCtx {
  activeProjectId: string | null;    // ID aktualnie aktywnego projektu
  setActiveProjectId: (id: string) => void;  // zmiana + zapis do localStorage
  showNewModal: boolean;              // czy modal tworzenia jest widoczny
  setShowNewModal: (v: boolean) => void;
}
```

Dostawca: `ProjectHubProvider`. Konsument: `useProjectHub()` hook.

### 4.2 Bootstrap sequence

1. `ProjectHubProvider` montuje sie.
2. `useEffect` czyta `localStorage.getItem("sylion.cockpit.active_project")`.
3. Jesli klucz istnieje → `setActiveProjectIdState(stored)`, `bootstrapped=true`.
4. Jesli brak → `projectsApi.list()` → wybiera pierwszy projekt ze statusem `active` lub `in_progress`, lub pierwszy z listy; zapisuje do localStorage.
5. `bootstrapped=true` → Provider renderuje `children`.
6. Dopoki `!bootstrapped` → Provider zwraca `null` (blokada renderowania).

### 4.3 Callbacki

| Callback | Wywolany przez | Efekt |
|----------|---------------|-------|
| `setActiveProjectId(id)` | ProjectSwitcher, RecentProjectsStrip | `setActiveProjectIdState(id)` + `localStorage.setItem(LS_KEY, id)` |
| `handleCreated(project)` | NewProjectModal onCreated | `setActiveProjectId(project.project_id)` + `setShowNewModal(false)` |

### 4.4 Propagacja `activeProjectId` do Cockpit

`cockpit/page.tsx` renderuje `CockpitInner` przez `children` callback:

```typescript
<ProjectHubProvider>
  {(ctx) => (
    <CockpitInner
      activeProjectId={ctx.activeProjectId}
      setActiveProjectId={ctx.setActiveProjectId}
      setShowNewModal={ctx.setShowNewModal}
    />
  )}
</ProjectHubProvider>
```

`LifecycleRail` i inne sekcje Cockpit otrzymuja `projectId={activeProjectId}` jako prop — zmiana aktywnego projektu triggeruje re-render tych komponentow z nowym ID.

---

## 5. API integration

### 5.1 Client `lib/api/projects.ts`

Typed API client z null-safe fetch wrappers. Baza: `process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8010"`.

```typescript
export interface Project {
  project_id: string;
  title: string;
  idea: string;
  constraints?: string;
  owner_id?: string;
  team_id?: string;
  project_kind: "application" | "research" | "audit" | "funding" | "other";
  status: "draft" | "active" | "in_progress" | "blocked" | "completed" | "archived" | "deleted";
  phase?: string;
  approvals?: { book?: boolean; operating_model?: boolean };
  preferred_stack?: string[];
  created_at?: number;
  updated_at?: number;
}
```

### 5.2 Metody `projectsApi`

| Metoda | Endpoint | Metoda HTTP | Opis |
|--------|----------|-------------|------|
| `list(status?)` | `GET /api/v1/projects[?status=X]` | GET | Lista projektow; opcjonalny filtr statusu; zwraca `[]` przy bledzie |
| `get(id)` | `GET /api/v1/projects/{id}` | GET | Jeden projekt lub `null` przy bledzie |
| `create(payload)` | `POST /api/v1/projects` | POST | Tworzy projekt; zwraca `Project` lub `null` |
| `update(id, patch)` | `PUT /api/v1/projects/{id}` | PUT | Aktualizuje projekt; zwraca `Project` lub `null` |

Wszystkie metody uzywaja `.catch(() => null)` — brak rzucania wyjatkow do UI. Blad = `null` / pusta tablica.

### 5.3 Endpointy backendu (FastAPI)

Backend: `src/sylion-pipeline/sylion/api/projects_routes.py`.

| Endpoint | Opis |
|----------|------|
| `GET /api/v1/projects` | Lista projektow (filtruje po statusie jesli `?status=`) |
| `GET /api/v1/projects/{id}` | Jeden projekt |
| `POST /api/v1/projects` | Tworzy nowy projekt; zwraca `{ project_id, title, ... }` |
| `PUT /api/v1/projects/{id}` | Partial update projektu |

---

## 6. Persistence (localStorage)

| Klucz | Typ | Wartosc | Kiedy zapisywany |
|-------|-----|---------|------------------|
| `sylion.cockpit.active_project` | `string` | `project_id` aktywnego projektu | Pri bootstrap (brak klucza) + przy kazdej zmianie `setActiveProjectId(id)` |

Zapis przez `localStorage.setItem(LS_KEY, id)` — synchroniczny, zawsze przed aktualizacja state.

Jesli localStorage niedostepny (SSR): `typeof localStorage !== "undefined"` guard chroni przed `ReferenceError`.

---

## 7. Modes / variants

### 7.1 Brak projektow (pusta lista)

- `ProjectSwitcher`: "Brak projektow" w liscie + przycisk "Nowy projekt".
- `RecentProjectsStrip`: empty state "Nie ma jeszcze projektow".
- `activeProjectId=null` → `LifecycleRail` renderuje stan bez projektu (zalezny od implementacji LifecycleRail).

### 7.2 Loading state

- `ProjectSwitcher`: tekst "Ladowanie..." w przycisku; lista zamknieta.
- `RecentProjectsStrip`: 4 szare skeleton kwadraty `animate-pulse`.
- `ProjectHubProvider`: zwraca `null` dopoki `!bootstrapped` — brak "flash" stanu null.

### 7.3 Blad API

- Metody `projectsApi.*` zwracaja `null` / `[]` — brak rzucania.
- `ProjectSwitcher`: "Brak projektow" (lista pusta po bledzie).
- `NewProjectModal`: przycisk "Stworz" odpala `create(payload)` → `null` → modal pozostaje otwarty (operator widzi ze nie zadzialo).

### 7.4 Aktywny projekt zmieniony z zewnatrz

Zmiana przez `setActiveProjectId` jest jedynym mechanizmem — brak polling do sprawdzania czy ID nadal wazny. Przy bledzie `get(id)` zwroci `null`; `LifecycleRail` odpowiada za obslugi null project_id.

---

## 8. Accessibility

| Element | ARIA / Zachowanie |
|---------|------------------|
| Przycisk ProjectSwitcher | `data-testid="cockpit-project-switcher"` |
| Dropdown lista | Click-outside zamyka — brak `Esc` handler w MVP |
| NewProjectModal | `@base-ui/react Dialog` — wbudowany focus-trap i `aria-modal` |
| RecentProjectsStrip kafelek | `<button>` + keyboard tab-navigable |

---

## 9. Przykladowe operator flows (step-by-step)

### 9.1 Przelaczenie projektu

1. Operator na `/advisor/cockpit`. Widzi aktywny projekt "Memory Profiler" w prawym gornym narozeniku hero.
2. Klika na przycisk z nazwa — otwiera sie dropdown z lista projektow.
3. Widzi 4 projekty (all non-deleted). Klika "Grant Portal v2".
4. `onSelectProject("proj-gp2-abc")` → `setActiveProjectId("proj-gp2-abc")` → `localStorage.setItem(...)`.
5. Dropdown zamyka sie. Hero button zmienia sie na "Grant Portal v2".
6. `LifecycleRail` dostaje `projectId="proj-gp2-abc"` → odswiezenie lifecycle phases.

### 9.2 Tworzenie nowego projektu

1. Operator klika "Nowy projekt" w dropdownie ProjectSwitcher (lub klik przycisku Plus).
2. `setShowNewModal(true)` → `NewProjectModal` renderuje sie jako portal.
3. Operator wypelnia: Tytul = "KYC Pipeline", Rodzaj = `application`, Stack = `python, fastapi`.
4. Klika "Stworz projekt".
5. `projectsApi.create({ title: "KYC Pipeline", project_kind: "application", preferred_stack: ["python","fastapi"] })`.
6. Backend zwraca `{ project_id: "proj-kyc-001", ... }`.
7. `handleCreated(project)` → `setActiveProjectId("proj-kyc-001")` + `setShowNewModal(false)`.
8. Cockpit wyswietla nowy projekt jako aktywny. RecentProjectsStrip (po reload) pokaze go na pierwszym miejscu.

### 9.3 Podglad ostatnich projektow

1. Operator widzi pas 5 kafelkow pod hero.
2. Kafelek "Funding Round A" — status "W toku" (blue), `updated_at` = "3h temu".
3. Operator klika kafelek → `onSelectProject("proj-fund-a")`.
4. Aktywny projekt zmienia sie na "Funding Round A".
5. Klikniecie ikony `ArrowRight` na kafelku → nawigacja do `/projects/proj-fund-a/lifecycle`.

---

## 10. Cross-references

### 10.1 Backend modules

| Modul | Plik | Rola |
|-------|------|------|
| Projects routes | `src/sylion-pipeline/sylion/api/projects_routes.py` | CRUD projektow: GET/POST/PUT |
| IdeaVault | `modules/44_idea_vault.md` | Projekty tworzone przez Step 10 wizardu sa powiazane z idea_id |

### 10.2 Powiazane surfaces

| Surface | Powod |
|---------|-------|
| `/advisor/cockpit` | Strona-gospodyni Project Hub |
| `/projects/[id]/lifecycle` | Cel nawigacji po kliknieciu ArrowRight w kafelku |
| `/projects` | "Wszystkie projekty" link w dropdownie ProjectSwitcher |
| `modules/23_operator_monitor.md` | Operator Monitor rowniez wyswietla aktywny projekt — te dwa widoki uzywaja tego samego `project_id` ale maja osobne localStorage state |
| `modules/22_lifecycle_dashboard.md` | `LifecycleRail` konsumuje `activeProjectId` z ProjectHubContext |

### 10.3 Powiazana dokumentacja

- [`modules/21_onboarding_wizard.md §3.11`](./21_onboarding_wizard.md) — Step 10 tworzy seed projektu; ten projekt staje sie kandydatem na `activeProjectId` po onboardingu.
- `docs/claude_parallel/aeis_advisor/` — architektura Cockpit v4 i historia surface.
