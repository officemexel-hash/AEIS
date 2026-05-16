# CODEX PARALLEL COORDINATION

**Status:** draft 0.1  
**Cel:** reguly wspolpracy dla Claude Code, Codex i Kimi pracujacych jednoczesnie w tym samym katalogu

## 1. Regula nadrzedna

Jesli trzy modele pracuja jednoczesnie w tym samym katalogu, najwiekszym ryzykiem nie jest zly kod, tylko:

- konflikt write ownership
- nadpisanie wspolnych plikow
- budowa rownoleglych subsystemow

Dlatego:

- kazdy plik ma jednego wlasciciela
- shared files sa reserved albo append-only
- integration robi dopiero Agent D

## 2. Wlasciciele

### Agent A — Claude Code — ownership exclusive

- `src/sylion-pipeline/sylion/api/ai_workspace_routes.py`
- `src/sylion-pipeline/sylion/project_mode/*`
- `src/sylion-pipeline/sylion/governance/*`
- `src/sylion-pipeline/sylion/api/governance_routes.py`
- `src/sylion-pipeline/sylion/api/aeis_routes.py`
- `src/sylion-pipeline/sylion/api/model_registry_routes.py`
- `src/sylion-pipeline/sylion/cognitive/model_registry.py`
- `src/sylion-pipeline/sylion/worker/*` tam, gdzie dotyczy truth reconciliation
- `tests/governance/*`
- `tests/workspace/*`
- `tests/project_mode/*`

### Agent B — Codex — ownership exclusive

- `src/sylion-pipeline/sylion/skills/*`
- `src/sylion-pipeline/sylion/memory/*`
- `src/sylion-pipeline/sylion/api/skills_routes.py`
- `src/sylion-pipeline/sylion/api/memory_routes.py`
- nowy `src/sylion-pipeline/sylion/operator_mobile/*`
- nowy `src/sylion-frontend/src/app/(app)/operator-mobile/*`
- `src/sylion-frontend/src/app/(app)/skills/*`
- `tests/skills/*`
- `tests/memory/*`
- `tests/mobile/*`

### Agent K — Kimi — ownership exclusive

- `src/sylion-pipeline/sylion/funding_autopilot/*`
- `src/sylion-pipeline/sylion/api/funding*`
- `src/sylion-pipeline/sylion/observability/*`
- `src/sylion-pipeline/sylion/monitoring/*`
- `src/sylion-frontend/src/app/(app)/funding/*`
- `src/sylion-frontend/src/app/(app)/observability/*`
- `src/sylion-pipeline/dashboard/*` tylko w zakresie oznaczenia legacy / cleanup bridge
- `tests/funding/*`
- `tests/observability/*`

### Agent D — Claude Code final — ownership shared integration

Tylko D edytuje:

- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/sylion/api/router.py`
- `src/sylion-frontend/src/lib/api/client.ts`
- root start scripts
- wspolne shared manifests
- finalne integration tests

## 3. Shared files

### Reserved for D only

- `src/sylion-pipeline/sylion/api/app.py`
- `src/sylion-pipeline/sylion/api/router.py`
- `src/sylion-frontend/src/lib/api/client.ts`
- `requirements*.txt`
- `pyproject.toml`

### Append-only

- `docs/codex_system_audit/CODEX_PARALLEL_PROGRESS_LEDGER.md`
- `docs/codex_system_audit/CODEX_PARALLEL_REQUESTS.md`

## 4. Request protocol

Jesli A, B lub K potrzebuja zmiany w pliku, ktorego nie posiadaja:

1. nie edytuja go sami
2. dopisuja wpis do `CODEX_PARALLEL_REQUESTS.md`
3. pracuja dalej w swoim ownership scope
4. D albo wlasciciel pliku rozwiazuje request pozniej

## 5. Commit protocol

Kazdy agent:

- uzywa wlasnego prefiksu commit message
- nie dotyka shared files reserved-for-D
- przed kazdym wiekszym commitem robi `git status` i sprawdza, czy nie ruszyl cudzych plikow

Prefiksy:

- A: `[A-GOV]`
- B: `[B-ADAPT]`
- K: `[K-SURF]`
- D: `[D-INTEGRATE]`

## 6. Stop conditions

Agent musi przerwac prace i zglosic konflikt, jesli:

- odkryje, ze potrzebna zmiana wymaga wejscia w cudzy ownership scope
- wykryje, ze jego plan tworzy nowy subsystem obok juz istniejacego namespace
- wykryje masowy overlap runtime truth plane

## 7. Zasada namespace

Wszystkie naprawy maja byc robione wewnatrz realnych namespace'ow repo.

Zakazane sa greenfieldowe rownolegle top-level katalogi typu:

- `skills/` obok `src/sylion-pipeline/sylion/skills`
- `memory/search/` obok `src/sylion-pipeline/sylion/memory`
- `funding/` obok `src/sylion-pipeline/sylion/funding_autopilot`

Wyjatek:

- nowy `operator_mobile/*`, bo nie ma potwierdzonej istniejacej codebase aplikacyjnej

## 8. Handoff do D

A, B i K koncza swoj etap dopiero wtedy, gdy:

- ich testy w swoim ownership scope sa zielone
- nie maja otwartych krytycznych requestow blokujacych D
- przygotowali notatke handoff z:
  - zakresem zmian
  - znanymi ryzykami
  - rzeczami niewlaczonymi jeszcze do shared files
