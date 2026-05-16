# AEIS REPAIR BACKLOG

**Data audytu:** 2026-04-24
**Status:** Finalny backlog po ETAP 1-5
**Podstawa:** 16 drifts z [REPORT_ETAP_4_DRIFT.md](REPORT_ETAP_4_DRIFT.md) + konsolidacja security z [05_SECURITY_DEDUP.md](05_SECURITY_DEDUP.md)

## Podsumowanie skali

| Priorytet | Drifts | FIX-y | Effort |
|---|---|---|---|
| P0 CRITICAL | 12 | 28 | 174h |
| P1 HIGH | 3 | 8 | 20h |
| P2 MEDIUM | 1 | 4 | 12h |
| Security dedup | — | 5 clusters | 26h |
| **RAZEM** | **16 drifts** | **45 fixów** | **232h** |

~6 tygodni 1 dev / ~3 tygodnie zespół 3-os.

## Sprint 1 — Fundamenty (19h)

| FIX | Opis | Plik | Effort |
|---|---|---|---|
| FIX-005a | pipeline_run_id non-nullable w decision_snapshot | `governance/decision_snapshot.py` | 1h |
| FIX-015 | Gate namespace per-run `pipeline_step_{run_id}_{N}` | `core/pipeline.state_machine.py` | 2h |
| FIX-003 | Bootstrap: manifest_loader → contract_registry | `bootstrap/init.py` | 3h |
| FIX-004 | execution_guard OFF→strict dla L4 | manifesty L4 | 2h |
| FIX-002 | Unifikacja decision_gate_engine | `core/` vs `governance/` | 4h |
| FIX-019 | Classifier czyta treść idei (D0→Dn) | `governance/decision_gate_engine.py` | 6h |
| FIX-018 | model_id required w step result | `core/pipeline_controller.py` | 1h |

## Sprint 2 — Human Gate + Recovery (59h)

| FIX | Opis | Plik | Effort |
|---|---|---|---|
| FIX-001 | Pipeline wywołuje human_gate.create_request() dla D3+ | `core/pipeline_controller.py:198-389` | 4h |
| FIX-007 | API pipeline_routes sprawdza pending approvals | `api/pipeline_routes.py:140-148` | 2h |
| FIX-008 | Integration test: pipeline blokuje D4+ bez approval | nowy test | 3h |
| FIX-005 | Governance dla rebuild.cutover/self_healing | L2 modules | 6h |
| FIX-006 | improvement_queue jako backend HG | wiring | 4h |
| FIX-024 | plan.source: "llm"\|"stub" w response | planner | 2h |
| FIX-025 | Multi-pass planner dla długich idei | planner | 8h |
| FIX-026 | Warning gdy <7 kroków dla multi-domain | planner | 3h |
| FIX-036 | Self-healing router + endpoints | api/ | 6h |
| FIX-037 | governance/rollback endpoint | api/ | 8h |
| FIX-038 | Step failure → incident + HG request | pipeline | 10h |
| FIX-039 | Chaos testing mode | pipeline | 6h |
| FIX-040 | Persystencja output kroku jako artifact | pipeline | 8h |

## Sprint 3 — Adaptive Model A1-A7 (110h)

| FIX | Opis | Effort |
|---|---|---|
| — | Warstwa Skills — katalog kompetencji + API | 40h |
| FIX-029 | /memory/search endpoint (text query) | 4h |
| FIX-030 | Similarity index (embeddings) | 16h |
| FIX-031 | Planner few-shot z similar runs | 8h |
| FIX-032 | Evidence pack z similar_runs + reused_skills | 4h |
| FIX-033 | Automatyczny fetch gdy idea cytuje run_id | 2h |
| FIX-034 | improvement_queue: sygnał z każdego runu | 6h |
| FIX-027 | Team decomposition engine | 16h |
| FIX-028 | Parallel execution niezależnych kroków | 12h |
| FIX-020 | impact_radius heurystyka | 3h |

## Sprint 4 — LLM Quality + Security Dedup (38h)

| FIX | Opis | Effort |
|---|---|---|
| FIX-016 | Prompt constraint injection | 4h |
| FIX-017 | Output validator (tech stack compliance) | 6h |
| FIX-023 | LLM prompt z kontekstem security z idei | 2h |
| SEC-A | Konsolidacja audit (4→1): audit_sink + audit_query + security_audit + hardened_audit → audit_trail_aggregator | 8h |
| SEC-B | Konsolidacja profiles (3→1): usuń STUB, merge profile_swap | 4h |
| SEC-C | Konsolidacja bootstrap (2→1): merge bootstrap_flow → bootstrap_init | 4h |
| SEC-D | Konsolidacja key storage (2→1): key_vault → secret_provider | 6h |
| SEC-E | evidence_signer → core.evidence_spine | 4h |

## Dead Code (natychmiast, 0h)

| Akcja | Moduł | LoC |
|---|---|---|
| Usuń STUB | security.profiles | 67 |
| Zbadać | aeis.integration_controller (nigdzie niewywoływany) | 446 |
| Zbadać | core.worker (79 testów, 0 LoC implementacji — ghost) | 0 |

## Kategoryzacja decyzji wg D-ladder

| Cluster | Decision class | Uzasadnienie |
|---|---|---|
| Sprint 1 (fundamenty) | D2-D3 | Zmiany infrastrukturalne, nie user-facing |
| Sprint 2 (HG integration) | **D4** | Zmiana kontraktu pipeline, wymaga Council approval |
| Sprint 3 (Skills+Memory) | **D4-D5** | Nowa warstwa architektury, greenfield |
| Sprint 4 (cleanup) | D1-D2 | Refactor bez zmiany behavior |

## Co NIE robimy w tym backlogu

- **15 LAB modułów** — celowo zachowane (cellular/sdr/vps/container/devices.artifact_deployer)
- **v5 Dashboard V5 greenfield** — osobny projekt, patrz [02_DASHBOARD_V5_VS_CURRENT.md](02_DASHBOARD_V5_VS_CURRENT.md)
- **Mobile Operator** — backlog po zakończeniu Sprint 1-2, patrz ETAP 7

## Zgodność z modelem AEIS po sprincie

| Sprint | Pokrycie Human Gate 12 osi | Pokrycie Adaptive A1-A7 |
|---|---|---|
| Przed | 0/12 | 0/7 |
| Po Sprint 1 | 2/12 (Q1, Q9) | 0/7 |
| Po Sprint 2 | 8/12 (Q1-Q3, Q7, Q9-Q12) | 1/7 (A7) |
| Po Sprint 3 | 11/12 (brak Q6 cost) | 7/7 |
| Po Sprint 4 | 12/12 | 7/7 |

**Pełna zgodność z kanonem po ~232h pracy.**
