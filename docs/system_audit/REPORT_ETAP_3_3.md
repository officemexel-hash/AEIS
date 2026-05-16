# REPORT ETAP 3.3 — Audyt warstw L0-L8 z checklistą Human Gate

**Data:** 2026-04-24
**Zakres:** wszystkie 9 warstw, 84+ moduły audytowane statycznie i live API
**Metoda:** 3 równoległe subagenty (L0-L2, L3-L5, L6-L8), checklist 12 pytań Human Gate

## Wyniki per warstwa

| Warstwa | Moduły | Compliance | Status | Risk |
|---|---|---|---|---|
| L0 Canon | 6 + 119 manifestów | PARTIAL (bootstrap broken) | PARTIAL | MEDIUM |
| L1 Kernel | 13 | PARTIAL (duplikat decision_gate_engine) | PARTIAL | HIGH |
| L2 Memory/AEIS/Rebuild | 18 | PARTIAL (0 governance na cutover/healing) | PARTIAL | HIGH |
| **L3 Cognitive** | 13 | **0/12 osi** (all NONE) | STUB-HG | **CRITICAL** |
| **L4 Execution** | 8 | **0/12, guard=OFF dla wszystkich** | STUB-HG | **CRITICAL** |
| L5 Security | 18 | 0.67/12 avg (policy_engine 5/12) | PARTIAL | MEDIUM |
| L6 Governance | 8 | 7.1/12 (59%) | PARTIAL | HIGH |
| **L7 Human Gate** | 1 | 10.5/12 (87%) — **W IZOLACJI** | FULL_ISOLATED | MEDIUM |
| **L8 Operator Console** | 3 | 1.67/12 (14%) | **STUB** | **CRITICAL** |

## 3 fundamentalne drifts (potwierdzone)

### DRIFT 1 — Pipeline omija Human Gate
**Lokalizacja:** `core/pipeline_controller.py:198-389`, `core/pipeline.state_machine.py`
- 0 wywołań `HumanGate.create_request()` w execution path
- Decision snapshots zapisują `outcome=approved confidence=1.0` bez operatora
- `/api/v1/pipeline/runs/{run_id}/execute` pozwala wykonać D4/D5 bez approval
- L7 human_gate to świetny moduł (47 testów, 10.5/12) — ale nikt go nie woła
- **Brak integration testów** weryfikujących blokadę D4+ bez approval

### DRIFT 2 — Stały schemat wykonania vs adaptive multi-team
**S1 dowód:** pipeline zwrócił identyczny plan 6-krokowy niezależnie od projektu
- Brak mechanizmu doboru liczby zespołów (A1)
- Brak pamięci podobnych projektów (A2)
- Brak katalogu skills + mechanizmu wyboru (A3)
- Brak reuse skutecznych konfiguracji (A4)
- Brak doboru topologii local/hybrid/VPS (A6)

### DRIFT 3 — Bootstrap Canon broken
**Ustalenie L0:** 119 manifestów na dysku, `/api/v1/contracts` zwraca `[]`
- manifest_loader nie wpina się w contract_registry przy starcie
- Runtime ignoruje `decision_cls=D3` zadeklarowany w manifestach
- Konsekwencja: L6/L7 nie mogą egzekwować polityk bo nie znają Canon

## Braki systemowe (8 komponentów)

| Komponent | Status | Warstwy docelowe |
|---|---|---|
| Risk Assessment Engine | MISSING | L3-L4 (Q1) |
| Reversibility Analyzer | MISSING | L3-L4 (Q2) |
| Blast Radius Calculator | PARTIAL | L3-L4 (Q3) |
| Data Classification Engine | MISSING | L3-L4-L5 (Q4) |
| Cost Estimator | MISSING | L4 (Q6) |
| Time Sensitivity Checker | MISSING | L4 (Q7) |
| Escalation Coordinator | MISSING | L3-L4 (Q11) |
| Autonomy Level Enforcer | MISSING | L3 (Q8) |

## Konsolidowany P0 Backlog

| ID | Opis | Plik | Effort |
|---|---|---|---|
| FIX-001 | Wpiąć human_gate w state_machine (stan awaiting_approval) dla D3+ | `pipeline/state_machine.py` | 4h |
| FIX-002 | Unifikacja 2× `decision_gate_engine` (core/ vs governance/) | ww. | 4h |
| FIX-003 | Bootstrap: manifest_loader → contract_registry | `bootstrap/init.py` | 3h |
| FIX-004 | execution_guard: OFF→strict dla wszystkich L4 | L4 manifesty | 2h |
| FIX-005 | Governance dla rebuild.cutover/orchestrator, self_healing | L2 | 6h |
| FIX-006 | improvement_queue jako backend Human Gate (reuse zamiast nowej kolejki) | L2/L7 wiring | 4h |
| FIX-007 | API blocking: pipeline_routes:140-148 sprawdza pending approvals | `api/pipeline_routes.py` | 2h |
| FIX-008 | Integration test: pipeline.execute blokuje D4+ bez approval | nowy test | 3h |

**Łącznie P0:** ~28h (~3.5 dnia jednego dev)

## P1 Backlog

- FIX-009 Autonomy Level Registry (DecisionClass → AutonomyLevel) — 6h
- FIX-010 L8 Console policy validation per endpoint — 8h
- FIX-011 Escalation workflow end-to-end — 4h
- FIX-012 Cost evaluation gate (D2+) — 6h
- FIX-013 Override policy dokumentacja + audit — 5h
- FIX-014 L8 UI dla Human Gate real-time — 12h

## Statystyka zgodności

- **Moduły audytowane:** ~84
- **FULL Human Gate compliance (>10/12):** 3 (evidence_spine, human_gate, council_workflow)
- **PARTIAL (5-9/12):** 6
- **STUB/NONE (<5/12):** 75+ (~89%)

## Co to znaczy dla mapy drift

ETAP 4 (drift analysis) dostaje potwierdzone 3 największe drifts + 8 brakujących komponentów + 14 konkretnych FIX-ów (P0+P1, ~85h) — pierwszy raz konkretna mapa naprawy z numerami linii.

## Co dalej

1. **ETAP 3.4** — scenariusze S2-S6 z checklistą 12 HG + A1-A7 (adaptive multi-team)
2. **ETAP 4** — zintegrowana drift analysis per warstwa
3. **ETAP 5** — kategoryzacja + security dedup
4. **ETAP 6** — 10 map
5. **ETAP 7** — AEIS_SYSTEM_BOOK_2026.md

## Pliki źródłowe

- [03_AUDIT_L0_L1_L2.md](03_AUDIT_L0_L1_L2.md)
- [03_AUDIT_L3_L4_L5.md](03_AUDIT_L3_L4_L5.md)
- [03_AUDIT_L6_L7_L8.md](03_AUDIT_L6_L7_L8.md)
- [03_S1_SMOKE_TEST.md](03_S1_SMOKE_TEST.md)
- [02_AEIS_EXTENDED_MODEL.md](02_AEIS_EXTENDED_MODEL.md)
