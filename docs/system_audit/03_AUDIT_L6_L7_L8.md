# 03 · AUDYT L6 / L7 / L8 — Governance, Human Gate, Operator Console

**Data:** 2026-04-24
**Zakres:** L6 Governance (8 modułów) + L7 Human Gate (1 moduł) + L8 Operator Console (3 moduły)
**Metoda:** statyczna analiza kodu + live API probing (token z `.audit_token`)

---

## 🔴 Krytyczne ustalenie

**Lokalizacja:** `src/sylion-pipeline/sylion/core/pipeline_controller.py` (198–389)

**Defekt:** `pipeline.execute()` całkowicie omija Human Gate dla decyzji D3–D5.

**Dowody:**
- `execute_run()` orkiestruje pełne wykonanie pipeline
- Linie 308–339: ewaluowane są TYLKO decision gates
- Linie 296–306: kod wykonuje się BEZPOŚREDNIO bez approval
- **Zero wywołań `HumanGate.create_request()` w całej ścieżce wykonania**
- Evidence spine wypełniany PO wykonaniu, nie PRZED approval (334–349)

**Impakt:** każda decyzja D4/D5 (critical/greenfield) może być wykonana bez zatwierdzenia przez człowieka poprzez wywołanie `/api/v1/pipeline/runs/{run_id}/execute`.

---

## Podsumowanie zgodności per warstwa

| Warstwa | Moduły | Śr. compliance | Status | Ryzyko |
|---|---|---|---|---|
| L6 Governance | 8 | 59% (7.1/12) | PARTIAL | HIGH |
| L7 Human Gate | 1 | 87.5% (10.5/12) | FULL (modułowo) | MEDIUM |
| L8 Operator Console | 3 | 14% (1.67/12) | STUB | CRITICAL |

---

## L6 Governance (8 modułów)

| Moduł | Status | Testy | UI | 12-HG |
|---|---|---|---|---|
| governance.roles | PARTIAL | 8 | `/app/roles` | 5/12 |
| governance.policy_registry | PARTIAL | route tests | `/app/governance` | 4/12 |
| governance.decision_ladder | FULL | 8 | `/app/decisions` | 9/12 |
| governance.council_workflow | FULL | many | `/app/governance` | **10/12** |
| governance.gates_registry | FULL | 40 | `/app/gates` | 5/12 |
| governance.evidence_workflow | FULL | route tests | `/app/evidence` | 8/12 |
| core.evidence_spine | FULL | yes | `/app/evidence-spine` | **11/12** |
| governance.decision_snapshot | FULL | route tests | `/app/decisions` | 9/12 |

**Główne luki L6:**
- Q6 (Cost): brak integracji cost_envelope (0/8)
- Q12 (Override policy): nieudokumentowane/niewymuszane (1/8)
- Q10 (Approval quorum): tylko council_workflow (3/8)
- Q11 (Escalation path): niepełne (3/8)

---

## L7 Human Gate (1 moduł)

**Moduł:** `governance.human_gate`
**Status:** ✅ FULL IMPLEMENTATION (10.5/12)
**Testy:** 47 cases w `test_human_gate.py`
**API:** 8 endpointów `/api/v1/gates/human/*`

**Działa:**
- Request creation dla D4+
- Reviewer decisions (approve/reject/needs_info)
- Escalation mechanism
- Review history + stats
- Thread-safe SQLite backend
- EventBus integration

**Braki:**
- ❌ **BRAK INTEGRACJI Z PIPELINE EXECUTION**
- ❌ Brak quorum enforcement (single reviewer)
- ❌ Brak deadline/timeout enforcement
- ❌ Brak cost validation w kontekście

**Critical:** moduł dobrze zaprojektowany, ale siedzi w izolacji — nigdy nie wołany z pipeline.

---

## L8 Operator Console (3 moduły)

| Moduł | Status | 12-HG |
|---|---|---|
| surface.console_api | PARTIAL | 2/12 |
| surface.console_ui | PARTIAL | 1/12 |
| surface.ws_gateway | FULL (messaging) | 2/12 |

**Strony frontend istnieją, ale niepełne:**
- ✅ `/app/governance`, `/app/decisions`, `/app/gates`, `/app/evidence`, `/app/roles`, `/app/audit`
- ⚠️ Brak: real-time human gate request status
- ⚠️ Brak: governance policy enforcement na poziomie operatora

**API:** 19 endpointów. **Testy:** 11 plików. **Gaps:** brak compliance validation per endpoint, brak autonomy level checks.

---

## Human Gate Integration Map

### Obecny stan
```
Pipeline Execution Path:
  execute_run() → plan() → code_agent.generate()
    → decision_gate.evaluate() ← gates_registry
    → evidence_spine.append() ← audit log
    → [STEP EXECUTES] ✅ CODE RUNS
    ❌ NO HUMAN_GATE CALL

Human Gate Sitting Idle:
  /api/v1/gates/human/requests — API istnieje
  /api/v1/gates/human/reviews  — API istnieje
  ← NIGDY nie wywoływane w trakcie wykonania
```

### Wymagana integracja (szkic)
```python
# Przed wykonaniem kroku (line 296):
if decision_class in (DecisionClass.D4, DecisionClass.D5):
    hg = get_human_gate()
    request = hg.create_request(
        gate_id=gate_id,
        title=f"Human approval: {decision_class}",
        description=step_description,
        context_json=step_record,
        requested_by="pipeline_controller"
    )
    approved = wait_for_human_approval(request['request_id'], timeout=300)
    if not approved:
        step_record['status'] = 'blocked_pending_approval'
        continue
```

---

## Ranking 12-HG (Human Gate compliance)

Najlepiej zaprojektowane moduły:
- **evidence_spine** 11/12 ✅
- **human_gate** 10.5/12 ✅ (moduł, nie system)
- **council_workflow** 10/12 ✅
- **decision_ladder** 9/12 ✅
- **decision_snapshot** 9/12 ✅

Średnia L6: 7.1/12 (59%). Średnia L7: 10.5/12 (87%, modułowo). Średnia L8: 1.67/12 (14%).

---

## Priority Backlog

### P0 — CRITICAL (naprawić natychmiast)

1. **Pipeline.execute bypasses Human Gate** — 4h
   - Plik: `core/pipeline_controller.py:198-389`
   - Fix: wywołać `human_gate.create_request()` przed D4+

2. **Brak Human Gate blocking w API routes** — 2h
   - Plik: `api/pipeline_routes.py:140-148`
   - Fix: sprawdzać pending approvals przed success

### P1 — HIGH (ten sprint)

3. Autonomy level enforcement missing (6h)
4. L8 Console brak policy validation (8h)
5. Escalation workflow incomplete (4h)

### P2 — MEDIUM (następny sprint)

6. Cost evaluation gate missing (6h)
7. Override policy nieudokumentowane (5h)
8. L8 UI pages niepełne (12h)

---

## Testy

| Kategoria | Liczba | Status |
|---|---|---|
| L6 Governance tests | 8 plików | ✅ Dobre |
| L7 Human Gate tests | 47 cases | ✅ Excellent |
| L8 Surface tests | 5 plików | ⚠️ Partial |
| **Integration tests** | **0** | ❌ **MISSING** |
| **Smoke test (S1)** | istnieje | ⚠️ Potwierdza bypass |

**Critical missing:** zero testów integracyjnych weryfikujących, że `pipeline.execute()` blokuje D4+ bez human approval.

---

## Rekomendacje

1. Wsadzić Human Gate jako OBOWIĄZKOWY gate między `decision_gate` a execution
2. Zaimplementować **Autonomy Level Registry** (DecisionClass → AutonomyLevel mapping)
3. Dodać **Cost/Time Evaluation Gate** dla D2+
4. Enable **Human Gate monitoring** w L8 console (real-time updates)
5. Stworzyć integration test pełnego flow: proposal → council → human_gate → execute

---

**Status raportu:** CRITICAL FINDINGS IDENTIFIED
**Rekomendacja:** załatwić P0 przed produkcją
