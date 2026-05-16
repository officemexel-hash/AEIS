# SYLION AEIS v2 — Główne zadanie sesji

> Status: **AKTYWNE GŁÓWNE ZADANIE** (przyjęte 2026-04-27)
>
> Źródło: `Downloads/SYLION v2 KOMPLETNY OBRAZ.pdf` (17 stron, ekstrakcja w
> `docs/v2/_pdf_source/SYLION_v2_KOMPLETNY_OBRAZ_extracted.txt`)

## Co Robert powiedział

> Przeanalizuj dokument PDF względem kodu. Przeanalizuj go dokładnie a
> następnie zacznij wdrażać. Ważne! Podziel zadania na mniejsze taski i
> rozdziel prace na innych subagentów — kimi, codex, ollama, claude, z.ai —
> masz do nich dostęp przez powłokę i możesz je uruchamiać i nadzorować.
> **Zapamiętaj ten prompt — to jest od teraz twoje najważniejsze zadanie.**

## Skala (z PDF)

- **W15** Ontology Runtime Plane (D5, 16-19 tyg solo) — generic data model
  przez YAML manifesty, PostgreSQL hybrid columns + JSONB, OSDK auto-gen,
  action types, lineage, branches.
- **W16** Operational Apps Builder (D4, 16-20 tyg) — apps przez YAML
  manifest, Next.js runtime, 20-30 widgets, forms, dashboards, workflows,
  automations, builder UI.
- **W17** Deployment Plane (D5, 16-20 tyg) — multi-instance management,
  hybrid local+central, blue-green, rollback < 60s, policy-as-code.
- **W18** Operator Terminal (D4, 10-14 tyg) — interaktywny terminal, live
  activity stream, session threading, command palette, replay.
- **W11** rozszerzenia (3-4 tyg) — OpenRouter, Together.ai, Replicate,
  Fireworks, LM Studio, vLLM, llama.cpp + capability tagging.
- **W7** rozszerzenia (2 tyg) — 30+ kreatywnych ról (Role Catalog).
- **W13** rozszerzenia (4-5 tyg) — Task-to-Role Suggester.

Razem: ~12-15 mies. solo / ~5-8 mies. z zespołem.

## Strategia wdrożenia

PDF rekomenduje Ścieżkę C (Pause & Reflect). Robert wybrał: **wdrażać
od razu, dispatchując do subagentów**. Idziemy ścieżką B z modyfikacją:

1. **Phase 0 (TERAZ, ta sesja)** — fundament + Pre-W15 inventory + szkielety
   wszystkich nowych warstw. Cel: w jednej sesji mieć wszystkie warstwy
   *zacumowane w kodzie* (struktury katalogów, charters, manifesty,
   pierwsze action stubs), żeby w następnych sesjach móc tylko pogłębiać.

2. **Phase 1 (kolejne sesje)** — W15 G1-G2 (schema compiler MVP, OSDK,
   migracja W14 → W15).

3. **Phase 2** — W11 + W7 + W13 rozszerzenia jako equity wins (nie blokują
   W15-W18, niski koszt).

4. **Phase 3** — W16 G1-G4.

5. **Phase 4** — W17 G1-G4.

6. **Phase 5** — W18 G1-G4 + ewaluacja Policy plane (W19 z zespołem).

## Aktywne subagenty CLI (sprawdzone 2026-04-27)

| Agent | Ścieżka | Use case |
|---|---|---|
| `claude` (Agent tool) | wewnętrznie | dokumentacja, code-gen wymagający context, review |
| `codex` | `npm/codex` v0.124.0 | implementacja rdzenia, refactor, schemas |
| `kimi` | `~/.local/bin/kimi` v1.38.0 | adversarial review, edge cases, alternative impl |
| `ollama` | `Programs/Ollama` (4 modele lokalne) | boilerplate, low-stakes parallel work |
| `z.ai` | brak CLI — przez `/api/v1/ai-providers/test/zai` | tylko jako provider w runtime |

Modele Ollama lokalnie:
- `qwen2.5:0.5b` (397 MB) — smoke tests
- `qwen2.5:7b-instruct` (4.7 GB) — boilerplate, validation
- `qwen3.5:latest` (6.6 GB) — code review
- `gpt-oss:20b` (13 GB) — heavy thinking, długie prompty

## Stan obecny v1 (snapshot 2026-04-27)

- **35 top-level subsystems** w `sylion/`, **110 SQLite tables**
- Backend FastAPI live na :8000 (PID 32336), tryb dev (RBAC bypass)
- Frontend Next.js live na :3000 (PID 21296)
- **W14 ontology** istnieje w `sylion/aeis/testing/ontology/` (objects.py,
  store.py, validators) — *ten ma być lifted to W15* per PDF §2.2
- Brak istniejących chartów W15-W18 (mimo że PDF wspomina pliki w katalogu
  wyjściowym — to było z innej rozmowy, ich tu nie ma)

## Wave plan (ta sesja)

### Wave 1 — fundament (paralel, ~4 bg agenty + foreground)

| # | Agent | Task | Output |
|---|---|---|---|
| 1 | Claude bg | Pre-W15 Module Inventory | `docs/v2/migration/MODULE_INVENTORY_CLASSIFICATION.csv` + report |
| 2 | Claude bg | Pełne charters W15-W18 (13 sekcji każdy) | `docs/v2/charters/W{15..18}_*.md` |
| 3 | Claude bg | W11 Provider extensions + capability tagging | `sylion/providers/{lmstudio,vllm,llamacpp}.py` + tagging |
| 4 | Claude bg | W7 Role Catalog (30+ YAML manifestów) | `sylion/skills/roles/*.yaml` + loader |
| 5 | Codex CLI | W15 sample object manifests + DDL preview | `sylion/aeis_v2/ontology/manifests/*.yaml` |
| 6 | Foreground | W15 schema compiler MVP (manifest reader, DDL gen, REST auto-gen) | `sylion/aeis_v2/ontology/{compiler,registry,osdk}.py` |
| 7 | Foreground | W18 Terminal SSE backend + xterm.js page | `sylion/api/terminal_routes.py` + `app/(app)/terminal/page.tsx` |
| 8 | Foreground | W13 Task-to-Role Suggester heuristic + endpoint | `sylion/aeis/advisor/role_suggester.py` |

### Wave 2 — integracja (po Wave 1)

- Migracja W14 ontology → W15 (side-by-side test)
- AdvisorCard integration dla Task-to-Role Suggester
- Frontend page dla Role Catalog
- Operator Terminal command palette + replay

### Wave 3 — Apps Builder szkielet

- W16 manifest format spec
- 5 widget components (ObjectListView, ObjectFormEditor, KpiCard,
  ChartWidget, AdvisorCardFeed)

## Zasady pracy

1. **In-place upgrade** (decyzja PDF §2.1) — żadnego forka repo.
2. **Backward compat** — `/api/v1/*` stable, internal Python API może się
   zmieniać z deprecation warnings.
3. **Każda warstwa ma exit gates G1-G4** (charter convention z PDF).
4. **Każdy commit ma F-### prefix** + crossreferencja do warstwy.
5. **Subagenty bg** zawsze dostają samodzielny brief (file paths, tone,
   constraints) — bez zakładania kontekstu z tej rozmowy.
6. **Nie usuwam istniejącego kodu** v1 dopóki v2 nie ma side-by-side test
   passing przez tydzień (PDF §6.3).

## Postęp wave 1

(uzupełniam na bieżąco gdy agenty kończą)

## Cron progress snapshot (auto-generated 2026-04-27)

- Commits: 38 (`[v2 cron]` prefix)
- V2 gate: 194 passed (pytest src/sylion-pipeline/tests/aeis_v2/ -q)
- W15 compiler: 0/3 P0 + 10/10 P1 closed
- W15 applier: 3/4 P0 + 0/4 P1 closed
- W17 federation: 5/6 P0 + 2/7 P1 closed
- W18 terminal: 1/1 P0 + 2/4 P1 closed
- Open reservoir (still-open P0/P1):
  - W15 compiler: P0-1 (enum SQL injection), P0-2 (hash-chain race), P0-3 (silent schema drift)
  - W15 applier: P0-4 (Exception swallow), P1-1 (PG unreachable cache), P1-2 (dry_run leakage), P1-3 (empty DDL), P1-4 (shared bootstrap orphans)
  - W17 federation: P0-2 (hostile node cost-default), P1-1 (unbounded available_models), P1-3 (sort tie-breaker), P1-5 (no audit), P1-6 (no rate limit), P1-7 (PREFER_LOCAL dead code)
  - W18 terminal: P1-2 (locale-dependent .lower()), P1-4 (ctx mutation foot-gun)
- **ADR-001 (2026-04-27)**: 5 architectural decisions resolved (extension validation, idea→app studio cascade, cost-ledger event-sourced, policy DSL parked, task-role hybrid matching) — see `docs/v2/decisions/ADR-001-five-architectural-decisions-2026-04-27.md`. W19 evaluator + Release Rail enforcement PARKED until W15/W16/W17/W18 + W7/W11/W13 feature-complete.
- **ADR-002 (2026-04-27)**: multi-model routing matrix; ollama for simple PL tasks, Claude bg for atomic-commit work, codex for single-function gen, kimi for short EN reviews — see `docs/v2/decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md`.
- **ADR-003 (2026-04-28, sprint 2 PROPOSED)**: W19 evaluator unblock decision point — three options (A: KEEP PARKED, B: jinja2 sandbox + 1% staged rollout, C: OPA Rego sidecar) with trade-offs matrix and per-option consequences. **Recommendation: Option B** (jinja2 SandboxedEnvironment + `SYLION_W19_EVALUATOR_DISABLED` feature flag + audit JSONL + Council Hybrid review of first 10 rule sets). Awaiting operator sign-off + Council Hybrid (W3) vote. Supersedes ADR-001 Decision #4 PARKED directive *conditionally* (only on B/C acceptance). See `docs/v2/decisions/ADR-003-W19-evaluator-unblock-2026-04-28.md` and `CHARTER_OPEN_QUESTIONS_DELTA.md` Q-NEW-W19-UNBLOCK §8.
- See `docs/v2/_cron_log.md` for round-by-round trail.

