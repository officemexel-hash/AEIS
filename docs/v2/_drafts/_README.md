# SYLION v2 cron-mode drafts

> Staging area dla outputów multi-backend dispatch pipeline.
> NIE jest to kod produkcyjny — tylko pre-review drafty od Ollama / Kimi / Codex / Claude.

---

## Czym jest cron-mode

W ramach sprintów 2-4 (28.04.2026) operator zadziałał w **cron-mode** —
ciągłym, równoległym dispatching zadań na 4 backendy na zmianę,
z dispatch'em co 30 minut (rundy 47:30 → 56:00, 19 rund).

Każda runda dzieli pracę między:

| Backend | Jak | Co produkuje |
|---------|-----|--------------|
| **Ollama gpt-oss:20b** | `ollama run` (subprocess) | PL design docs, plans, ADR drafts (free, local GPU, biggest share) |
| **Kimi -p** | `kimi -p "..."` (cloud Moonshot) | EN adversarial reviews, security findings |
| **Codex exec** | `codex exec --skip-git-repo-check --color never` (cloud OpenAI) | Small Python helper functions |
| **Claude (cron orchestrator)** | foreground tool calls | Atomic implementation commits z testami |

---

## Layout

```
_drafts/
├── _README.md                          # ten plik
├── ollama_batch/
│   ├── batch_AA / AB / ...            # historyczne (sprint 1)
│   ├── batch_CC / CD / ...            # sprint 2 day 4-5
│   ├── batch_CL / CM / ...            # sprint 3 day 1-3
│   └── batch_CT / CU / ...            # sprint 4
├── kimi_batch/
│   └── round_47_30 / 48_00 / ...      # per-round folders
├── codex_batch/
│   └── round_47_30 / 48_00 / ...      # per-round folders
└── codex_root_dump_20260428/          # one-off cleanup z prior chaos
└── codex_tests_dump_20260428/         # one-off cleanup z prior chaos
```

---

## Naming conventions

### Ollama batches

```
batch_<LETTERS>/<task_letter><N>_<topic_slug>.md

# Przykłady:
batch_CC/cc1_w19_integration_tests.md
batch_CD/cd2_gdpr_dsr_skeleton.md
batch_CT/ct1_w19_federation_wire_design.md
```

Każda runda ma swój `batch_*` folder i ~10 zadań ponumerowanych
`<batch_letter><N>` gdzie N = 1..10.

### Kimi reviews

```
kimi_batch/round_<HH>_<MM>/k<N>_<topic>.md
```

Każda runda ma 5 reviews (k1..k5).

### Codex helpers

```
codex_batch/round_<HH>_<MM>/h<N>_<helper_name>.py
```

Każda runda ma 5 helpers (h1..h5). Codex często emituje też towarzyszące
test files (`test_h<N>_*.py`) obok helpera.

---

## Dispatch script pattern

Każda runda ma własny `scripts/v2/dispatch_round_<HH>_<MM>.sh`.

Kontur:

```bash
#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/../.." || exit 1

OL_DIR="docs/v2/_drafts/ollama_batch/batch_XX"
KIMI_DIR="docs/v2/_drafts/kimi_batch/round_HH_MM"
CODEX_DIR="docs/v2/_drafts/codex_batch/round_HH_MM"
mkdir -p "$OL_DIR" "$KIMI_DIR" "$CODEX_DIR"

ollama_task() { ollama run gpt-oss:20b "$2" > "$OL_DIR/$1.md" 2>&1 & }
kimi_task() { kimi -p "$2" > "$KIMI_DIR/$1.md" 2>&1 & }
codex_task() {
  ( codex exec --skip-git-repo-check --color never "$2" \
    > "$CODEX_DIR/$1.py" 2>&1 ) &
}

# 10 ollama tasks
ollama_task "xx1_topic_a" "Po polsku zaprojektuj ..."
# ...

# 5 kimi reviews
kimi_task "k1_topic_a_review" "Adversarial review of ..."
# ...

# 5 codex helpers
codex_task "h1_helper_name" "Write a Python helper ..."
# ...

sleep 1
echo "Round HH:MM dispatch fired"
```

Wszystkie zadania run **w paralel** (`&` na końcu każdej komendy).
Ollama jest free (lokalny GPU), więc 10x parallelism nie generuje kosztu;
Kimi/Codex są cloud, ale tanie i dobrze skalują.

---

## Lifecycle draftu

```
1. cron orchestrator pisze dispatch script + odpala bg
2. Backend pisze plik do _drafts/<backend>_batch/<round>/
3. Cron orchestrator (Claude) sweeps drafts
4. Drafts WYSOKIEJ wartości: integrowane przez Claude'a w atomic commit
5. Drafts niskiej wartości: zostają w _drafts/ jako historyczna ścieżka decyzyjna
```

Drafty NIE są commitowane — gitignore powinien je wykluczać dla
niewielkiej historii git. Jednak obecnie SĄ w repo (na potrzeby
audytu cron-mode'u i rekonstrukcji decyzji w sprint 4 retro).

---

## Multi-backend rationale

Per directive operatora 2026-04-27:
> "wykorzystuj maksymalnie lokalne modele bo są tanie"

Stąd Ollama dostaje **biggest share** (10 zadań/runda, ~280 drafts
łącznie przez sprint 2-4), a Kimi i Codex po 5 zadań/runda.

Per ADR-002 ([decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md](../decisions/ADR-002-multi-model-routing-matrix-2026-04-27.md)):

| Typ pracy | Backend |
|-----------|---------|
| PL design docs | Ollama (free, dobra w polskim) |
| EN adversarial review | Kimi (cloud, dobra w EN security) |
| Single-function Python helpers | Codex (cloud, najsilniejsza w API) |
| Atomic implementation z testami | Claude (atomic-commit, full context) |

---

## Dispatch rounds inventory

Per `docs/v2/_cron_log.md`:

| Runda | Batch letter | Topics | Drafts dostarczone |
|-------|--------------|--------|---------------------|
| 47:30 | CC | sprint 2 day 4 fan-out (W19 tests, ADR-MERGE, embeddings PG, Council wedge, GDPR DSR, replay-fork, security checklist, ADR conflict matrix, success criteria) | 10 + 5 + 5 |
| 48:00 | CD | sprint 2 day 4-5 (cache integration, GDPR PG, replay module, nightly merge, council telemetry, W15 ext G2, cost_ledger PG, kimi wrapper, audit JSONL rotator, day5 plan) | 10 + 5 + 5 |
| 48:30 | CE | sprint 2 day 5 deeper (W16 G1 metrics, replay audit schema, GDPR audit immutability, council chaos, cache eviction, W19 council signoff, PG idempotent migrations, cost_ledger partitioning, divergence_score, sprint2 dashboard) | 10 + 5 + 5 |
| 49:00 | CF | sprint 2 day 5 fan-out (SessionSnapshot, PgUserDataStore, W19 integration, Council real models, dashboard audit, cost metrics, W16 G2, divergence impl, smoke E2E, day5 summary) | 10 + 5 + 5 |
| 49:30 | CG | sprint 2 day 6 deeper (hard_purge, telemetry impl, replay React widget, W19 signoff endpoint, embedding eviction runner, session protocol, dashboard overview, audit chain integrity, replay routes, day 6 plan) | 10 + 5 + 5 |
| 50:00 | CH | sprint 2 day 6/7 (chain migration, metrics router, audit chain CLI, council role adapters, replay W18 capture, W15 ext G3, idea lifecycle, adapter_bus metrics, smoke E2E chained, post-mortem) | 10 + 5 + 5 |
| 50:30 | CI | sprint 2 day 7 (metrics design, council real models strategy, replay dashboard, W16 G2 LLM gen, audit chain index, cost partitions, dashboard violations, replay W18 endpoints, health endpoint, day 7 plan) | 10 + 5 + 5 |
| 51:00 | CJ | sprint 3 day 1 (W14 PG store, dashboard React, replay widget, council widget, council adapters real, W15 G3 workflow, idea lifecycle, audit chain monitor, smoke E2E, sprint3 status) | 10 + 5 + 5 |
| 51:30 | CK | sprint 3 backlog (PgUserDataStore, replay W18 routes, admin dashboard, W19 staged rollout, chaos tests, PG policy registry, council signoff endpoint, kimi reviews, codex helpers) | 10 + 5 + 5 |
| 52:00 | CL | sprint 3 day 2 (PgEmbedding, replay routes full, admin overview React, W16 G2 LLM, council OllamaRoleAdapter, DPO runbook, session lifecycle, cost_ledger PG, kimi normalizer, day 2 status) | 10 + 5 + 5 |
| 52:30 | CM | sprint 3 day 2 finish (PgUserDataStore v2, PgEmbeddingCache v2, dashboard v3, DPO runbook full, cost_ledger PG migration, replay diff visualizer, W15 workflow rules, council audit view, idea lifecycle SM, day 3 status) | 10 + 5 + 5 |
| 53:00 | CN | sprint 3 day 3 (W17 cost migration full, admin overview React, replay dashboard, council audit view, council role adapters real, W15 workflow, idea lifecycle, audit chain monitor, smoke E2E, completion report) | 10 + 5 + 5 |
| 53:30 | CO | sprint 3 day 3 prep (council role prompts, idea lifecycle SM, W15 workflow engine, admin overview KPI, replay dashboard, cost_ledger PG queries, DPO dashboard, audit chain monitor cron, smoke E2E full, day 3 plan) | 10 + 5 + 5 |
| 54:00 | CP | sprint 3 day 4 (admin overview v3, W15 workflow full, replay dashboard, council widget, DPO audit dashboard, idea lifecycle dashboard, audit alert dispatch, smoke E2E full, W7 catalog ext, day 3 status) | 10 + 5 + 5 |
| 54:30 | CQ | sprint 3 day 4 prep (W15 workflow full, W7 catalog v2, admin dashboard FINAL, v2 metrics extra, event bus chained, workflow dashboard, replay W18 SessionLifecycle, idea lifecycle dashboard, integration smoke, day 3 progress) | 10 + 5 + 5 |
| 55:00 | CR | sprint 3 close + sprint 4 prep (W19 council vote, federation routing, staged rollout, chaos tests, PG policy registry, admin overview v3, W11 metrics, event bus, integration smoke, sprint3 close) | 10 + 5 + 5 |
| 55:30 | CS | sprint 4 prep (W14+W15+W17 pipeline, W19 council vote run, admin overview, W19 staged rollout impl, W19 chaos tests, event bus, idea dashboard, replay dashboard, DPO audit, sprint3 close status) | 10 + 5 + 5 |
| 56:00 | CT | sprint 4 production wire-in (W19 federation wire design, W19 chaos test suite, W19 PG policy full, admin dashboard full, W19 production runbook, event bus, W19 metrics extra, replay dashboard, council signoff audit, sprint 4 day 1 progress) | 10 + 5 + 5 |

**Razem**: ~190 ollama drafts + ~95 kimi reviews + ~95 codex helpers = **~380 drafts** dla 40 atomic commits.

---

## Konsumpcja draftów

Drafty są **inputem dla Claude'a**, nie dla operatora. Cron orchestrator
robi sweep + integruje wartościowe pomysły w atomic commitach z testami.

Operator może czytać drafty by:
- zrozumieć decyzje retroaktywnie (kto zaproponował co)
- zobaczyć Kimi findings które zostały zaadresowane
- audytować Codex helpers które wpadły do produkcji

---

## Retencja

Drafty NIE są retencyjne — mogą być purgowane bez utraty produkcyjnej
wartości (cała wartość "produkcyjna" siedzi w atomic commitach).
Jednak `_cron_log.md` referencjuje batch IDs więc kasowanie zerwałoby
referencjalność audytu.

**Rekomendacja sprint 5**: archive `_drafts/` do `_drafts.archive.tar.gz`
po sprint review i pokazanie operatorowi.
