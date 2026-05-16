# AEIS v2 — Adaptive Enterprise Intelligence System

> Pakiet `sylion.aeis_v2` — nowa generacja warstw architektonicznych SYLION
> (PDF "Kompletny Obraz", 2026-04-27). In-place upgrade obok v1 — bez forka.

---

## Czym jest v2

AEIS v2 to **Palantir-inspired ontology runtime** dla SYLION: wszystkie typy
obiektów dziedzinowych są deklarowane w **YAML manifestach**, z których
kompilator auto-generuje DDL PostgreSQL (hybrid storage: dedicated columns +
JSONB), kontrakty REST, klientów OSDK (Python + TypeScript) oraz adaptery
audytowe. Lokalne modele LLM (ollama, kimi via `model_router`) są obywatelem
pierwszej klasy: routing matrix per task-type, cost ledger event-sourced,
intervention queue z replay-as-film. W19 (policy plane) jest świadomie
**PARKED** — patrz ADR-001 #4.

Decyzje architektoniczne: [`ADR-001`](../../../docs/aeis_v2/ADR-001.md),
[`ADR-002`](../../../docs/aeis_v2/ADR-002.md). Karty modułów (charters):
`docs/aeis_v2/charters/W{15,16,17,18}_charter.md`.

---

## Moduly (10 sub-modules)

| Modul | Zakres | Phase | Kluczowe pliki |
|---|---|---|---|
| `ontology/` | W15 — manifest+compiler+applier+migration+OSDK | **G2 ready** + extension validator | `manifest.py`, `compiler.py`, `applier.py`, `migration.py`, `osdk_gen.py`, `osdk_ts_gen.py`, `extension_validator.py`, `registry.py` |
| `deployment/` | W17 — federation+nodes+cost-ledger | **G1 feature-complete** (P0+P1 closed); cost-ledger Phase 0 + G2 step 1+2+3 | `federation.py`, `nodes.py`, `registry.py`, `agent.py`, `cost_ledger.py`, `cost_ledger_pg.py`, `cost_ledger_refresher.py` |
| `terminal/` | W18 — stream+sessions+commands+intervention+replay | **G1 + G3 step 1** | `stream.py`, `sessions.py`, `commands.py`, `replay.py` |
| `adapter_bus_v2/` | W11 — retry+breaker+wrapper | **Phase 0** (feature-complete) | `retry.py`, `circuit_breaker.py`, `bus_wrapper.py` |
| `role_match/` | W13 — hybrid task-role match | **Phase 0** (embeddings przez abstrakcję) | `hybrid.py` |
| `apps_v2/` | W16 — apps cascade Phase 0 | **Phase 0** (skeleton + wizard) | `__init__.py` |
| `embeddings/` | W13/W16 G1 — provider abstraction | **Phase 0** | `provider.py` |
| `audit/` | W15-W18 — daily-rotated JSONL | **Phase 0** (stable) | `rotated_writer.py` |
| `db/` | W15 G2 — v2 PostgreSQL pool | **Phase 0** (stable) | `pool_v2.py` |
| `simulation/` | W14 sim L0-L4 | **L0 + L1 only** | `levels.py`, `demo_data.py` |

---

## Status per warstwa W7-W19 (per ADR-001)

- **W7** (role catalog): backend OK + frontend OK
- **W11** (adapter bus): retry OK + breaker OK + wrapper OK
- **W13** (task-role match): hybrid OK + embeddings consumer OK
- **W15** (ontology):
  - G1 OK
  - G2 OSDK Python + TypeScript OK
  - G3 step 1 (W14 migration) OK
  - G2 v2 pool OK
  - extension validator OK
- **W16** (apps builder): Phase 0 OK + wizard OK
- **W17** (deployment):
  - 6/6 P0 OK
  - 7/7 P1 OK
  - cost ledger Phase 0 + G2 OK
  - cost-cap policy OK
  - cost-cap REST runtime control (in flight)
- **W18** (terminal): SSE + sessions + commands + intervention OK + replay-as-film backend + frontend OK
- **W19** (policy plane): MVP catalog OK + **PARKED do końca**: evaluator, Release Rail enforcement (per ADR-001 #4)

---

## ADRs (decyzje)

- **ADR-001** — pięć decyzji architektonicznych:
  1. Extension validation (hybrid syntactic + runtime)
  2. Idea → app cascade (sklejka W16↔W7↔W13)
  3. Cost-ledger event-sourced (append-only + materialized view refresh)
  4. **W19 PARKED** (catalog only, evaluator deferred)
  5. Task-role hybrid (similarity + skills + workload)
- **ADR-002** — multi-model routing matrix: Claude (architecture, audyt) +
  codex (code-gen, refactor) + ollama (lokal batch) + kimi (review),
  per task type.

---

## Quick start

```bash
cd C:/Users/razor/Desktop/pipeline_glm/src/sylion-pipeline
python -m pytest tests/aeis_v2/ -q       # 487+ tests
bash ../../scripts/v2/smoke_e2e.sh       # 75+ HTTP assertions
```

---

## Audit logs

Każdy strumień v2 leci do daily-rotated JSONL pod
`logs/v2/<name>/YYYY-MM-DD.jsonl`. Bieżąca lista nazw:

- `apply_audit` (W15 ontology applier)
- `routing_audit` (W17 federation routing)
- `intervention_audit` (W18 terminal intervention queue)
- `migration_audit` (W15 G3 W14 migration)
- `cost_ledger` (W17 deployment cost stream)
- `terminal_replay` (W18 replay-as-film events)
- `cost_ledger_refresh` (W17 materialized view refresh)

---

## Frontend strony (sidebar AEIS v2)

- `/ontology` — **W15** read-only manifest + DDL preview
- `/apps-builder` + `/apps-builder/wizard` — **W16** apps catalog +
  idea→app studio
- `/terminal` + `/terminal/replay` — **W18** live SSE + replay-as-film
- `/role-catalog` + Studio Doboru Roli — **W7 → W13**
- `/federation` — **W17** node registry + routing audit
- `/policy` — **W19** read-only catalog (evaluator PARKED)

---

## Continuous integration

- `_cron_log.md` — round-by-round trail (60+ commits w cron-mode)
- `_drafts/` — local-model output staging (ollama batches A-T,
  codex rounds, kimi reviews)
- Konwencja commitów: `[v2 cron] <type>: <module> — <change>`

---

> **Heads-up**: warstwa v1 (`sylion.*` legacy) działa side-by-side i jest
> nietykalna w cron-mode. Każda zmiana v2 musi być atomic per submodule
> i przechodzić zielone testy v2 przed self-commitem.
