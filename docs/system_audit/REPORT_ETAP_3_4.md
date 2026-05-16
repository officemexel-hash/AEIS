# REPORT ETAP 3.4 — Scenariusze S1-S6 end-to-end

**Data:** 2026-04-24
**Zakres:** 6 scenariuszy o rosnącej złożoności, każdy live przeciw runtime :8000
**Metoda:** submit idea → execute → odczyt plan/steps/gates/decision_snapshots + probe memory/HG/recovery endpoints

## Tabela scenariuszy

| # | Scenariusz | Złożoność | Kroki | Status | Human Gate | Artefakty | Kluczowe drifts |
|---|---|---|---|---|---|---|---|
| S1 | Hello World REST | trivial | 6 | complete | 0 | None | brak HG integration |
| S2 | TODO CRUD fullstack | simple | 11 | complete | 0 | None | **gate namespace collision** |
| S3 | Prod deploy auth+PII | HIGH RISK | 15 | complete | 0 | None | **D0 dla D5, orphan snapshots** |
| S4 | Multi-platform SaaS 6 teams | complex | **5 STUB** | complete | 0 | None | **silent fallback planner** |
| S5 | Reuse explicit run_id | simple | 10 (generic) | complete | 0 | None | **memory=0, plan gorszy od oryginału** |
| S6 | Forced failure + recovery | resilience | 10 | complete | 0 | None | **recovery endpoints 404** |

## 13 drifts odkrytych w scenariuszach

### Od S1
1. Pipeline omija Human Gate w całej ścieżce wykonania
2. `artifacts: None` mimo `status: complete` (fałszywe complete)
3. Brak wyboru topologii wykonania
4. LLM generuje docs zamiast realnych deliverables
5. `idea_id` z `/ideas` nie linkuje do pipeline run

### Od S2
6. **Cross-run gate namespace collision** — `pipeline_step_{N}` globalnie keyed, gate names wyciekają między runami (11 z 15 kroków S3 miało nazwy bramek z S1+S2)
7. LLM ignoruje constraints (FastAPI→Flask, SQLite→in-memory)

### Od S3
8. **Decision classifier = D0 ZAWSZE** (produkcyjny deploy z PII/payment tokens dostał D0)
9. `impact_radius = local` ZAWSZE (deploy na VPS z nginx/SSL: local)
10. `pipeline_run_id = null` w decision_snapshot — **orphan records**

### Od S4
11. **Silent fallback na stub planner** dla złożonych idei — S4 (6 zespołów) dostał 5 kroków stub, a prosty S3 dostał 15 kroków. Brak obserwowalności fallbacku.

### Od S5
12. **Memory=0%** — `/memory/search` 404, `/aeis/similar` 404. Eksplicytne podanie `run_id` w idei zignorowane. Plan S5 **gorszy** od S2 mimo że S2 był w bazie.

### Od S6
13. **Recovery endpoints brak** — `/self-healing/status` 404, `/incidents` 404, `/rollback` 404. Pipeline nie potrafi wywołać awarii nawet na żądanie.

## Matrix 12 osi Human Gate × scenariusze

Wszystkie osi Q1-Q12 × scenariusze S1-S6: **0/72 osiągniętych**.

Największy cios: **S3 (produkcyjny deploy auth z PII) powinien mieć 12/12 osi, ma 0/12.**

## Matrix A1-A7 (adaptive multi-team)

| Oś | Pokryte w S1-S6 | Uwagi |
|---|---|---|
| A1 dobór zespołów | 0/6 | Zawsze 1 sekwencyjny agent |
| A2 pamięć podobnych | 0/6 | Memory endpoints 404, nawet explicit run_id zignorowany |
| A3 skills | 0/6 | Brak katalogu skills aktywnych w runtime |
| A4 reuse | 0/6 | Zero transferu wiedzy między runami |
| A5 autonomia | 0/6 | Bez polityk, stały poziom |
| A6 topologia | 0/6 | Brak wyboru local/VPS/hybrid |
| A7 HG systemowy | 0/6 | HG istnieje jako moduł, nigdy nie wołany z pipeline |

**Pokrycie adaptive model: 0/42.**

## Konsolidowany P0+P1 backlog (13 drifts → 39 fixów)

Z wszystkich trzech raportów audytu + 6 scenariuszy, skumulowana lista FIX-001 do FIX-039. Ok. **185h pracy** — ~5 tygodni 1 dev / 2 tygodnie zespołu 3-os.

**Top 10 CRITICAL (jeśli miało być wdrożenie jutro):**
1. FIX-001 Pipeline→Human Gate integracja (4h)
2. FIX-007 API blocking dla pending approvals (2h)
3. FIX-015 Gate namespace per-run (2h)
4. FIX-019 Decision classifier czyta treść idei (6h)
5. FIX-021 pipeline_run_id required w snapshot (1h)
6. FIX-024 Observability fallback planner (2h)
7. FIX-003 Bootstrap contract_registry (3h)
8. FIX-031 Planner few-shot z similar runs (8h)
9. FIX-038 Step failure→incident+HG (10h)
10. FIX-036 Self-healing router (6h)

**Razem P0:** 44h.

## Wniosek globalny

**S1-S6 dowodzą że runtime AEIS jest fasadą.** Endpointy odpowiadają, pipeline przechodzi stany, ale:
- Nie wykonuje realnych zadań (artefakty puste)
- Nie waży ryzyka (D0 zawsze)
- Nie używa pamięci
- Nie angażuje człowieka dla D4+
- Nie odzyskuje z awarii (bo ich nie wykrywa)
- Nie skaluje topologii zespołów
- Rozpada się dla złożonych inputów (silent fallback)

System "działa" w sensie HTTP 200, ale **nie realizuje deklarowanego kontraktu kanonu**. To największa luka audytu — i dokładnie to, co użytkownik podejrzewał rozpoczynając audyt.

## Dalej

- **ETAP 4** — zintegrowana drift analysis: 3 warstwowe + 13 scenariuszowych = 16 głównych drifts, każdy z plikiem+linią+effortem
- **ETAP 5** — kategoryzacja 119 modułów (CORE/EXT/EXP/DUP/LEGACY/LAB) + security dedup
- **ETAP 6** — 10 map w docs/system_audit/
- **ETAP 7** — AEIS_SYSTEM_BOOK_2026.md po polsku ze screenshotami
