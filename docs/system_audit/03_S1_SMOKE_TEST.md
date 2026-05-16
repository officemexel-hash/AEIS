# 03 · S1 SMOKE TEST — "Hello World REST endpoint" przez AEIS

**Data:** 2026-04-24
**Status runtime:** backend :8000 + frontend :3001 + SQLite
**Cel:** zweryfikować czy system działa end-to-end z najprostszym pomysłem

---

## Wykonane kroki

1. **Bootstrap** — POST `/api/v1/auth/setup` (admin/hasło z `.env`) → token
2. **Idea** — POST `/api/v1/ideas` → `idea_id=ecea48e1...`
3. **Pipeline submit** — POST `/api/v1/pipeline/ideas` z opisem → `run_id=bafdbafe...`, status `pending`
4. **Execute** — POST `/api/v1/pipeline/runs/{run_id}/execute` → status `complete`

## Wynik

```json
{
  "run_id": "bafdbafeeb8344438531ec4a0fb3f948",
  "status": "complete",
  "plan": {
    "plan_id": "2a44e18ea96341bc85224e9036ab0408",
    "steps": [
      {"step_id": 1, "name": "Analyze Requirements"},
      {"step_id": 2, "name": "Design Application Structure"},
      {"step_id": 3, "name": "Implement FastAPI Application"},
      {"step_id": 4, "name": "Test Endpoint Functionality"},
      {"step_id": 5, "name": "Review Code and Documentation"},
      {"step_id": 6, "name": "Deploy Application"}
    ]
  },
  "steps": [... 6× operation=generate, op_id, input_hash, output_hash ...],
  "artifacts": null
}
```

## ✅ Co działa

- Bootstrap auth (setup → token)
- Idea tracking (CRUD)
- Pipeline submission
- **Planner** generuje plan z 6 krokami, dependencies, priorities
- **Executor** wykonuje każdy krok (`operation=generate`)
- **Audit trail**: każdy krok ma `op_id`, `input_hash`, `output_hash`
- Status transitions: `pending → complete`
- Plan persystowany (plan_id)

## 🔴 Co NIE działa / brakuje (vs spec kanon)

### 1. Zero Human Gate w całym flow
Pipeline `execute` leci od planowania do "complete" bez żadnej decyzji człowieka. Zgodnie ze specyfikacją Human Gate (5 ról, 12 osi):
- ❌ brak klasyfikacji decyzji
- ❌ brak batch approval
- ❌ brak policy engine (risk-based autoapproval)
- ❌ brak Council dyskusji modeli przed wyborem planu
- ❌ brak propozycji wariantów dla człowieka
- ❌ brak budowy source of truth przez dyskusję → zatwierdzenie

### 2. Brak realnych artefaktów
`artifacts: None` — status "complete" jest fałszywy. System mówi że wygenerował kod, ale plik nie powstał. Hashes input/output sugerują że LLM coś wyprodukował, ale nie jest to zapisane jako artefakt modułu.

### 3. Brak wyboru topologii wykonania
Specyfikacja wymaga: po zatwierdzeniu masterplanu człowiek wybiera **1-model / multi-model / local / hybrid / VPS-only**. W S1: żaden wybór, domyślny model, brak pytania.

### 4. Brak testów i deployu w rzeczywistości
Plan mówi "Test Endpoint Functionality" + "Deploy Application" — ale to są kroki LLM generate, nie realne uruchomienie pytest / docker build / deploy.

### 5. Idea-id nie połączone z run-id w odpowiedzi
Pipeline przyjmuje "idea" jako string w body, nie referuje do utworzonego `idea_id=ecea...`. Dwa równoległe światy: `/ideas` vs `/pipeline/ideas`.

### 6. Brak feedback loop
Nic nie pyta operatora o korektę / akceptację / iterację.

## Implikacje dla audytu

S1 potwierdza:
- **System "działa" mechanicznie** — endpointy odpowiadają, pipeline przechodzi stany
- **System NIE działa wg kanonu** — cała idea Human Gate + dyskusja modeli + source of truth + masterplan jest niezaimplementowana w runtime flow

To największa luka odkryta w ETAP 3. Wpływa na wszystkie pozostałe scenariusze S2-S6 — każdy z nich spec-wise wymaga Human Gate, więc audyt musi pokazać **co każdy etap scenariusza robi w RZECZYWISTOŚCI** vs co **powinien robić**.

## Dalsze kroki

- ETAP 3.3: audyt statyczny per warstwa z checklistą Human Gate (12 pytań)
- ETAP 3.4: S2-S6 — każdy scenariusz musi być sprawdzony: gdzie pojawia się Human Gate? gdzie powinien?
- ETAP 4 (drift): udokumentować drift "pipeline bez Human Gate" jako główny punkt naprawczy

## Ścieżka do naprawy (szkic)

W Masterplanie:
- **P05 Council** jako silnik Human Gate → musi być integralną częścią `pipeline.execute`
- **P17 Operator UI** → wprowadzić widok "pipeline paused waiting for approval"
- **P19 Autonomy Rollout** → poziom autonomii `observe → propose → sandbox → limited → full` per-moduł
- **Worktree `serene-mccarthy`** — merge `decision_orchestrator` + `operator_mobile` (decyzja P1 z ETAP 2)

Po mergu: każdy `pipeline.execute` powinien przechodzić przez `decision_orchestrator.intake() → classifier → policy_engine → queue → approval_or_auto` zanim wyśle request do LLM.
