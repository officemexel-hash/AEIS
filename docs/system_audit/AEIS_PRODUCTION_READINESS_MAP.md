# AEIS PRODUCTION READINESS MAP

**Data:** 2026-04-24
**Verdict:** 🔴 **NOT PRODUCTION READY**

## Scoring

| Kategoria | Score | Target | Gap |
|---|---|---|---|
| Human Gate 12 osi (pipeline) | 0/72 (6 runów × 12) | 72/72 | 100% |
| Adaptive A1-A7 | 0/42 (6 × 7) | 42/42 | 100% |
| Decision classifier | D0 zawsze | Risk-based D0-D5 | Broken |
| Pipeline artifacts | 0/6 runów | 6/6 | 100% |
| Recovery endpoints | 1/4 istnieje | 4/4 | 75% |
| Memory reuse | 0% | >50% similarity boost | 100% |
| Evidence integrity | Orphan snapshots | 100% linked | Data integrity bug |
| Gate namespace | Cross-run pollution | Per-run isolated | Critical bug |
| Bootstrap | 0/119 manifests loaded | 119/119 | 100% |
| L4 execution_guard | 0/8 strict | 8/8 | 100% |

## Blockery produkcji (12 CRITICAL drifts)

Każdy z tych drifts ([REPORT_ETAP_4_DRIFT.md](REPORT_ETAP_4_DRIFT.md)) jest SAM W SOBIE wystarczający do wstrzymania produkcji:

- D-01 Pipeline omija Human Gate
- D-02 Classifier zawsze D0
- D-03 Bootstrap Canon broken
- D-04 Gate namespace collision
- D-05 Orphan decision snapshots
- D-06 Silent fallback planner
- D-08 execution_guard OFF
- D-09 Memory 0%
- D-10 Brak skills
- D-11 Brak doboru topologii
- D-15 Recovery endpoints brak
- D-16 Artefakty none mimo complete=true

## Scenariusze S1-S6 — verdict per scenariusz

| Scenariusz | Produkcja? | Uzasadnienie |
|---|---|---|
| S1 Hello World | NIE | Brak artefaktów mimo success |
| S2 CRUD | NIE | Gate namespace collision + wrong tech |
| **S3 Auth deploy** | **KATASTROFA** | D0 dla PII+payment, snapshot kłamie |
| S4 Multi-team | NIE | Silent fallback stub, kłamie o planie |
| S5 Memory reuse | NIE | 0% reuse, plan gorszy od oryginału |
| S6 Recovery | NIE | Nie wykrywa awarii |

**6/6 scenariuszy NIE nadaje się do produkcji.**

## Komponenty które BŁYSZCZĄ (mimo drift)

- **core.evidence_spine** — 11/12 HG (najlepszy w systemie)
- **governance.human_gate** — 10.5/12 (świetny moduł, nigdy niewołany)
- **governance.council_workflow** — 10/12
- **governance.decision_ladder** — 9/12

**Problem:** te moduły istnieją w izolacji. Pipeline ich nie używa.

## Minimalne warunki READY (Sprint 1+2)

Aby AEIS był "technicznie deployable" (nie "production-ready", tylko "internal alpha"):

1. Sprint 1 ukończony (19h) — data integrity fixed
2. Sprint 2 ukończony (59h) — HG wired
3. S3 test powtórzony z D4 classification + approval required
4. 0 orphan snapshots, 0 gate collision, 100% bootstrap

**Minimum = 78h pracy.**

## Warunki READY for external users (Sprint 1-4)

Wszystkie 4 sprinty ukończone. **232h.**

## Co mówi operator po zaufaniu obecnemu systemowi

Gdyby wdrożyć AEIS jutro z S3 jako reprezentatywnym scenariuszem:
- Auth service z PII wdrożony BEZ human approval
- Decision snapshot mówi "approved D0, local impact" — fałsz
- Brak rollback przy awarii
- Audyt compliance po step_id da mylne dane
- Ryzyko RODO: ogromne

**Rekomendacja:** nie używać AEIS do produkcji bez Sprint 1+2.

## Zielone światło kryteria

Przed przejściem do "ready":
- [ ] 100% manifestów w contract_registry przy starcie
- [ ] Classifier poprawnie D3+ dla idei z "prod/deploy/PII/credentials"
- [ ] Pipeline blokuje D4+ do approval (integration test green)
- [ ] 0 orphan decision snapshots w 24h traffic
- [ ] 0 gate namespace collisions w 100 runach
- [ ] Recovery: wymuszone failure → incident + HG request
- [ ] artifacts non-null dla 100% success runów
- [ ] Adaptive plan.source obserwowalne (llm vs stub) w API
