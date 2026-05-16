# 03 · S2 SCENARIUSZ — "TODO CRUD webapp" przez AEIS

**Data:** 2026-04-24
**Cel:** sprawdzić czy pipeline adaptuje plan do multi-domain (FE+BE+DB+tests+docker) oraz czy uruchamia mechanizmy Human Gate, doboru topologii i skills

## Wykonane

1. `POST /api/v1/pipeline/ideas` → `run_id=4ca263e9e99e486fb8d1a7e5ca947385`, `status=pending`
2. `POST /api/v1/pipeline/runs/{run_id}/execute` → `status=complete` po ~30s

## Wynik

- **11 kroków planu** (vs 6 w S1) — planner SKALUJE po złożoności projektu
- Wszystkie kroki `status=complete`, każdy z op_id/input_hash/output_hash
- **`artifacts: None`** — znowu brak realnych plików
- `model_id: ""` — pusty dla wszystkich kroków
- 0 wywołań Human Gate

## ✅ Co działa

- Planner rozpoznaje że "CRUD fullstack" ≠ "hello world" → 11 vs 6 kroków
- Plan ma sensowny DAG: req→API spec→DB→arch→env→BE+FE→tests→audit→refactor→deploy
- Dependencies OK (step 8 `depends_on=[6,7]` prawidłowe)
- Priorities (high/medium/low) przypisane

## 🔴 Co NIE działa

### DRIFT A — LLM generuje kod niezgodny z wymaganiami
- Idea: **FastAPI + SQLite + React**
- Step 1 ("Analyze Requirements") → zwraca **Python class** zamiast listy wymagań
- Step 2 ("Define API Specifications") → zwraca kod **Flask + in-memory dict** (nie FastAPI, nie SQLite)
- LLM ignoruje constraints projektu, generuje najbardziej "oczywisty" kod

### DRIFT B — Cross-run data leak w gate_registry 🔴 CRITICAL
Steps 1-6 dostały gate_name Z POPRZEDNIEGO RUNU (S1 "hello world"):

| Step ID | Rzeczywista nazwa kroku | Gate name (z S1!) |
|---|---|---|
| 1 | Analyze Requirements | Analyze Requirements ✅ (przypadek) |
| 2 | Define API Specifications | **Design Application Structure** ❌ |
| 3 | Design Database Schema | **Implement FastAPI Application** ❌ |
| 4 | Design Application Architecture | **Test Endpoint Functionality** ❌ |
| 5 | Setup Development Environment | **Review Code and Documentation** ❌ |
| 6 | Implement FastAPI Backend | **Deploy Application** ❌ |
| 7 | Implement React Frontend | Implement React Frontend ✅ |
| 8-11 | — | OK (step_id >6, brak konfliktu z S1) |

**Root cause:** `gates_registry` keyuje gate po `f"pipeline_step_{step_id}"` globalnie zamiast `f"run_{run_id}_step_{step_id}"`. Nowe runy NADPISUJĄ cudze gate lub odczytują cudze.

**Konsekwencja:** evidence spine / audit log wskazują fałszywe pary step→gate. Jeśli ktoś zrobi compliance review po step_id, dostanie mylące dane.

### DRIFT C — Zero adaptive topologii (potwierdzone)

Pipeline NIE robi żadnego z:
- A1: doboru liczby zespołów — jeden wykonawca, zawsze sekwencyjnie
- A2: pamięci podobnych projektów — S1 i S2 startują "na czystym biurku"
- A3: doboru skills — brak skill jak "frontend-react", "backend-fastapi", "db-sqlite"
- A4: reuse — S1 już robił "Implement FastAPI" (błędnie zresztą), ale nic z tego nie wraca
- A6: doboru topologii local/VPS/hybrid — żaden wybór
- A7: Human Gate systemowy — zero

### DRIFT D — Wszystkie gates = pass (auto-approve)

Każdy z 11 kroków: `gate.result=pass`, `blocks="pipeline execution"`. Ale nikt nic nie blokuje — decision_gate_engine tylko klasyfikuje i puszcza dalej. Brak D3/D4/D5 classification, brak awaiting_approval.

## Compliance 12-HG per krok pipeline

Każdy krok tego runu: **0/12** osi Human Gate (Q1-Q12 wszystkie NONE).
Każdy krok 12-A: **0/7** adaptacyjnych (A1-A7 wszystkie NONE).

## Nowe znaleziska (nie pokryte S1)

1. ✅ Planner JEST skalowalny — S1=6 steps, S2=11 steps
2. 🔴 Cross-run gate namespace collision (data integrity bug)
3. 🔴 LLM ignoruje constraints (FastAPI→Flask, SQLite→in-memory)
4. ⚠️ Brak walidacji że output kroku spełnia description

## Repair backlog (new)

| ID | Opis | Effort |
|---|---|---|
| FIX-015 | Gate namespace per-run: `pipeline_step_{run_id}_{step_id}` | 2h |
| FIX-016 | LLM prompt constraint injection (kiedy idea mówi "FastAPI", nie pozwól na Flask) | 4h |
| FIX-017 | Output validator: czy wygenerowany kod używa zadeklarowanych bibliotek | 6h |
| FIX-018 | model_id nigdy nie pusty — required w API response | 1h |

## Dalej

S3 — wprowadzimy element ryzyka (np. deployment na VPS) aby wywołać hipotetyczne D4+ i zobaczyć czy Human Gate w ogóle się aktywuje.
