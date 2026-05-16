# 03 · S6 SCENARIUSZ — "Wymuszona awaria + recovery" (RESILIENCE TEST)

**Data:** 2026-04-24
**Cel:** sprawdzić zachowanie self-healing, rollback, incident response, Human Gate escalation przy błędzie

## Idea zgłoszona

"Critical task with FORCED FAILURE INJECTION: Build payment processing system that **MUST deliberately crash at step 3** to test self-healing, rollback, incident response, human gate escalation."

**Oczekiwanie:** step 3 wyrzuca exception → pipeline blokuje dalsze kroki → incident utworzony → rollback triggered → Human Gate request „approve retry" → operator decyduje.

## Wynik (run_id=508eaa0f2537416c927037c78889702f)

- **10 kroków, `status=complete` dla WSZYSTKICH**
- `gate=pass` dla wszystkich
- `artifacts: None`
- Brak jakiegokolwiek sygnału awarii w evidence spine

**Pipeline NIE ZROZUMIAŁ że idea żąda awarii.** LLM wygenerował dokumentację o tym jak zrobić failure test — ale nie zaimplementował go. Runtime nie ma mechanizmu "execute hostile test scenario".

## 🔴 Recovery endpoints — stan po probie

| Endpoint | Expected | Actual |
|---|---|---|
| `GET /api/v1/aeis/self-healing/status` | 200 | **404 Not Found** |
| `GET /api/v1/aeis/incidents` | 200 | **404 Not Found** |
| `POST /api/v1/governance/rollback` | 200/400 | **404 Not Found** |
| `GET /api/v1/gates/human/requests` | 200 z D4+ | 200 `{"requests":[]}` |

**3/4 recovery endpoints w ogóle nie istnieją w runtime.**

## DRIFT L — Self-healing module istnieje w kodzie, NIE ma routera

Z audytu L2: `self_healing_orchestrator` i `rebuild.cutover` są w kodzie (manifesty mówią że "istnieją"), ale:
- Zero zarejestrowanych routerów → brak API surface
- Nikt nie woła ich z pipeline
- Gdyby nawet wołał — brak governance (potwierdzone w L2 audit)

## DRIFT M — Pipeline nie ma "failure injection" / chaos testing

Nie ma:
- Sposobu celowego wywołania błędu dla testów
- Resilience test mode
- Simulate-failure flag w pipeline.execute

Konsekwencja: **resilience AEIS jest nieweryfikowalny z zewnątrz.** Nie da się ręcznie wymusić awarii żeby sprawdzić odzyskiwanie.

## Compliance A1-A7

| Oś | S6 status |
|---|---|
| A1-A6 | jak w poprzednich (0%) |
| **A7 Human Gate** | pipeline wygenerował 10 kroków typu "critical payment processing" — powinno być D5+ z wymaganym approval, zero wywołań HG |

## Nowe FIX-y

| ID | Opis | Effort |
|---|---|---|
| FIX-035 | Pipeline rozpoznaje `dry_run=True` / `simulate_failure=True` flags | 4h |
| FIX-036 | Self-healing router + endpointy `/self-healing/status,/incidents` | 6h |
| FIX-037 | `governance/rollback` endpoint → trigger policy-driven rollback | 8h |
| FIX-038 | Step failure → automatic incident + HG request "approve retry" | 10h |
| FIX-039 | Chaos testing mode: wstrzyknięcie błędu per step_id | 6h |

## Dalej

S6 kończy ETAP 3.4. Przechodzę do konsolidacji raportu ETAP 3.4 (6 scenariuszy) i ETAP 4 (drift analysis).
