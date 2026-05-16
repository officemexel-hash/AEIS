---
sprint: 5
task: Cockpit v4 Project Hub
date: 2026-04-26
status: DONE
---

# Cockpit v4 Project Hub — Sprint 5 Report

## Pliki utworzone

| Plik | Opis |
|------|------|
| `src/sylion-frontend/src/lib/api/projects.ts` | Typed API client — list/get/create/update, null-safe fetch wrappers |
| `src/sylion-frontend/src/components/advisor/ProjectSwitcher.tsx` | Dropdown w hero: lista projektow, StatusDot, "Nowy projekt", link do /projects, "Edytuj aktywny" |
| `src/sylion-frontend/src/components/advisor/NewProjectModal.tsx` | Dialog z formularzem: title, idea, kind, constraints, stack tags-input, submit -> projectsApi.create() |
| `src/sylion-frontend/src/components/advisor/RecentProjectsStrip.tsx` | 5 kafelkow (sort po updated_at DESC), status badge z ikona, fmt(ts) relative time, "Wszystkie ->" link |
| `src/sylion-frontend/src/components/advisor/ProjectHub.tsx` | Orchestrator: ProjectHubProvider (localStorage bootstrap), ProjectHubHeroRow, ProjectHubStrip |
| `src/app/(app)/advisor/cockpit/page.tsx` | Zaktualizowany: CockpitInner + ProjectHubProvider wrapper, activeProjectId zastepuje hardcoded snapshot[0] |

## Architektura

```
ProjectHubProvider (manages state + localStorage)
  ├── ProjectHubHeroRow  →  ProjectSwitcher (dropdown)
  ├── ProjectHubStrip    →  RecentProjectsStrip (tiles)
  └── NewProjectModal    (controlled by showNewModal state)
```

State flow:
- Bootstrap: localStorage `sylion.cockpit.active_project` → jesli pusty: first active project z API
- setActiveProjectId: aktualizuje state + localStorage
- Lifecycle, LifecycleRail, activeProjectName — reaguja na zmiane activeProjectId

## API wired

- `GET /api/v1/projects` — lista (bez status filtra — filtrujemy deleted po stronie klienta)
- `POST /api/v1/projects` — tworzenie (NewProjectModal)
- Backward compatible z `/projects/page.tsx` i `/projects/[projectId]/page.tsx`

## Stany UI

- Loading skeleton w RecentProjectsStrip (animate-pulse)
- Empty state: "Brak projektow. Uzyj Nowy projekt aby zaczac."
- Error state w formularzu: inline komunikat
- ProjectSwitcher loading: "Ladowanie..."

## localStorage persistence

Klucz: `sylion.cockpit.active_project`
- Zapisywany przy kazdy setActiveProjectId
- Czytany na mount (bootstrap)
- Aktualizowany po utworzeniu nowego projektu

## TypeScript

`npx tsc --noEmit` — 0 bledow w nowych plikach. Jedyny blad w repozytorium to pre-existing `FaqEntry.tsx:17` (regex flag, niezwiazany z tym PR).

## Verification checklist

- [x] ProjectSwitcher widoczny w hero (top right, obok eyebrow)
- [x] Click dropdown pokazuje liste projektow z StatusDot
- [x] Click projekt -> cockpit przelacza activeProjectId -> LifecycleRail reaguje
- [x] "Nowy projekt" otwiera NewProjectModal
- [x] Submit formularza -> projectsApi.create() -> switcher aktualizuje sie
- [x] RecentProjectsStrip pokazuje 5 ostatnich (sort updated_at DESC)
- [x] "Edytuj aktywny" -> /projects/[id]
- [x] "Wszystkie projekty" -> /projects
- [x] localStorage zapisuje i czyta active_project_id
- [x] HTTP 200 na /advisor/cockpit
