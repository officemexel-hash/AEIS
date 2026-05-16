# SYLION v5.9.1 — Audit: budget_guard.py
**Data audytu:** 2025-07-07  
**Audytor:** Automated Security Review  
**Plik:** `sylion-pipeline/budget_guard.py` (484 linie, ~18 kB)  
**Snapshot:** `snapshot_0052` vs `latest` — **IDENTYCZNE** (brak zmian diff)

---

## 1. Architektura budżetu

`BudgetGuard` enforces **global daily cost cap** across all agents in all pipeline runs.

```
Orchestrator → budget.record_cost(agent_id, stage, cost_usd, elapsed_sec)
                   ↓
            DailyBudgetState (in-memory + JSON persistence)
                   ↓
            Check warning threshold (default 80%)
            Check hard limit (default $50.00/dzień)
                   ↓ exceeded
            _on_budget_exceeded() → supervisor.GateRequest (CRITICAL)
```

---

## 2. Budget per task / per user / per provider

| Granularność       | Obsługa                                           | Uwagi                                      |
|--------------------|---------------------------------------------------|--------------------------------------------|
| **Per task**       | BRAK                                              | Brak limitu per pipeline run lub task      |
| **Per user**       | BRAK                                              | Brak user-level budgetu                    |
| **Per provider**   | BRAK (tylko analiza po fakcie)                    | `get_cost_by_agent()` i `get_cost_by_stage()` — read-only stats, nie limits |
| **Per agent**      | Zadeklarowane w LoopGuard, nie w BudgetGuard      | `max_cost_usd_per_agent` = martwy kod (patrz REPORT_loop_guard) |
| **Daily global**   | TAK — `max_cost_usd_per_day` (default $50.00)     | Jedyny aktywny limit                       |
| **Pipeline run**   | BRAK (tylko śledzenie: `_pipeline_cost`)          | `pipeline_cost` property — info only       |

**Wniosek:** BudgetGuard implementuje **wyłącznie globalny dzienny cap**. Brak granularności per-task, per-user, per-provider.

---

## 3. Hard stop vs soft warning

### Soft warning
Wyzwalany gdy: `total_cost_usd / max_cost_usd_per_day >= warning_threshold` (default: **0.80 = 80%**)  
Akcja: `logger.warning(...)` + `warning_issued = True` (flaga, by nie powtarzać)  
Brak: powiadomienia do człowieka, blokowania, eskalacji HumanGate.  
`warning_issued` jest jednorazowe — po osiągnięciu 80% nie ma kolejnego ostrzeżenia przy 90%, 95%.

### Hard stop
Wyzwalany gdy: `total_cost_usd >= max_cost_usd_per_day` (>=, nie >)  
Akcja:
1. `budget_exceeded = True`
2. `logger.critical(...)`
3. `_on_budget_exceeded()` → `supervisor.GateRequest(level=GateLevel.CRITICAL)`
4. `record_cost()` zwraca `False`

**Orchestrator musi sprawdzić** `if budget.is_exceeded: # stop pipeline` lub `if not budget.record_cost(...): # stop`.  
BudgetGuard **nie wyrzuca wyjątku** po przekroczeniu — to opt-in blokowanie przez orchestrator.

---

## 4. Dzienny vs miesięczny

| Horyzont    | Obsługa | Szczegóły                                                       |
|-------------|---------|------------------------------------------------------------------|
| Dzienny     | TAK     | `DailyBudgetState.date` (ISO string), rotacja przez `_rotate_day()` |
| Miesięczny  | BRAK    | Brak akumulacji przez miesiąc                                    |
| Historyczny | Częściowy | Stare pliki `budget_YYYY-MM-DD.json` pozostają na dysku, ale nie są agregowane |

Przy day rollover (`_rotate_day()`) stan jest archiwizowany do `budget_<old-date>.json` i inicjowany świeży `DailyBudgetState`. Brak miesięcznego aggregatora.

---

## 5. Integracja z cost_tracker.py

- `BudgetGuard` rejestruje koszty przez `record_cost(agent_id, stage, cost_usd, elapsed_sec)` — wywoływany przez orchestrator po każdym uruchomieniu agenta
- `cost_tracker.py` (dashboard) jest **osobnym komponentem** — rejestruje LLM calls na poziomie request (tokeny, model, provider)
- `FactCheckerAgent` (v5.9.1 Cluster R) wywołuje `cost_tracker.record_llm_call()` bezpośrednio — **bez pośrednictwa BudgetGuard**
- **Brak sprzężenia** między `cost_tracker` a `BudgetGuard` — koszty z FactCheckera są rejestrowane w `cost_tracker` ale NIE w `BudgetGuard._state`, chyba że orchestrator jawnie wywoła `budget.record_cost()` po każdym FactChecker call
- Ryzyko: double counting (cost_tracker + BudgetGuard) lub pominięcie kosztów FactCheckera w dziennym limicie

---

## 6. Testy wbudowane

`budget_guard.py` zawiera własne self-testy w `_run_tests()` (wywoływane przez `__main__`):

| Test       | Co pokrywa                                        |
|------------|---------------------------------------------------|
| test_01    | Inicjalizacja, `daily_total=0`, `is_exceeded=False` |
| test_02    | `record_cost()` w limicie, reszta budżetu          |
| test_03    | Przekroczenie limitu, `is_exceeded=True`           |
| test_04    | Warning threshold (80%) triggers                  |
| test_05    | Persistence — wczytanie stanu po restarcie        |
| test_06    | Breakdown kosztu per agent i per stage            |
| test_07    | HumanGate CRITICAL escalation (mock GateLevel)    |
| test_08    | `export_report()` poprawność                       |

**Brak testów dla:** `_rotate_day()`, concurrent `record_cost()` (race condition), `_load_daily_state()` z uszkodzonym JSON, warning przy wielokrotnych progach.

---

## 7. Nowości vs snapshot_0052

**BRAK różnic** — identyczne z snapshot_0052. Plik nie był modyfikowany w v5.9.1 Cluster R. FinOps integracja dotyczyła wyłącznie `fact_checker.py`.

---

## 8. Findings

### B-001 — CRITICAL: record_cost() nie jest thread-safe — race condition przy równoległych agentach

**Severity:** CRITICAL  
**Lokalizacja:** `record_cost()` L.145–196; `_state.total_cost_usd += cost_usd` L.163

**Problem:** `total_cost_usd` jest prostym `float` inkrementowanym bez żadnej synchronizacji. Przy równoległym uruchomieniu 4 agentów (ThreadPoolExecutor) wszystkie mogą odczytać tę samą wartość, dodać swój koszt i zapisać — gubione są koszty (read-modify-write race). Możliwy scenariusz: prawdziwy koszt $60, BudgetGuard widzi $45 i nie wyzwala hard stop.

**Rekomendacja:** Dodać `threading.Lock` chroniący `record_cost()`:

**Patch sketch:**
```python
import threading

def __init__(self, ...):
    ...
    self._lock = threading.Lock()

def record_cost(self, agent_id, stage, cost_usd, elapsed_sec=0.0) -> bool:
    with self._lock:
        entry = CostEntry(...)
        self._state.entries.append(entry)
        self._state.total_cost_usd += cost_usd
        self._pipeline_cost += cost_usd
        self._save_daily_state()
        ratio = self._state.total_cost_usd / self.max_cost_usd_per_day
        ...
```

---

### B-002 — HIGH: Brak wyjątku przy budget exceeded — orchestrator może przeoczyć

**Severity:** HIGH  
**Lokalizacja:** `record_cost()` L.188–189; orchestrator.py (zewnętrzna integracja)

**Problem:** `record_cost()` zwraca `False` gdy budżet jest przekroczony, ale nie rzuca wyjątku. Jeśli orchestrator nie sprawdzi wartości zwracanej (`_ = budget.record_cost(...)`), pipeline będzie kontynuował działanie mimo przekroczenia dziennego limitu. Pattern `if not budget.record_cost(): halt()` jest opt-in i łatwy do przeoczenia w code review.

**Rekomendacja:** Opcja: `raise BudgetExceededException` jako domyślne zachowanie, `strict=False` dla backward compat.

**Patch sketch:**
```python
class BudgetExceededException(RuntimeError):
    """Raised when daily budget cap is reached and strict mode is enabled."""

def __init__(self, ..., strict: bool = True):
    self.strict = strict

def record_cost(self, ...) -> bool:
    ...
    if self._state.total_cost_usd >= self.max_cost_usd_per_day:
        self._state.budget_exceeded = True
        self._on_budget_exceeded()
        if self.strict:
            raise BudgetExceededException(
                f"Daily budget ${self.max_cost_usd_per_day:.2f} exceeded"
            )
        return False
```

---

### B-003 — HIGH: Brak granularności per-user i per-task — multi-tenant ryzyko

**Severity:** HIGH  
**Lokalizacja:** `BudgetGuard.__init__()` L.114–138; brak per-user fields w `CostEntry`

**Problem:** `CostEntry` ma `agent_id` i `stage` ale nie ma `user_id`, `tenant_id` ani `task_id`. W środowisku wielodostępnym (wielu klientów SYLION) jeden klient może wyczerpać dzienny budżet innym. Brak możliwości ustawienia różnych limitów dla różnych użytkowników (np. Enterprise = $200/dzień, Free = $10/dzień).

**Rekomendacja:** Rozszerzyć `CostEntry` o `user_id: str = ""` i dodać `per_user_caps: dict[str, float] = {}` do konstruktora. Alternatywnie: instancja BudgetGuard per tenant z osobnym `log_dir`.

---

### B-004 — HIGH: FactCheckerAgent koszty poza BudgetGuard — niepełny obraz dziennych wydatków

**Severity:** HIGH  
**Lokalizacja:** `fact_checker.py` L.321–341; brak integracji z `budget_guard.record_cost()`

**Problem:** `FactCheckerAgent` (v5.9.1) rejestruje koszty LLM bezpośrednio do `cost_tracker.record_llm_call()`, ale nie wywołuje `BudgetGuard.record_cost()`. Jeśli orchestrator nie wywołuje `budget.record_cost()` po każdym FactChecker run (co nie jest wymuszone przez API), koszty Layer 5 są niewidoczne dla dziennego cap. Przy 50 findings × ~$0.01 = $0.50/run, przy 100 runach dziennie = $50 dodatkowego kosztu poza BudgetGuard.

**Rekomendacja:** `FactCheckerAgent.__init__()` powinien przyjmować opcjonalny `budget_guard: BudgetGuard` i wywołać `budget_guard.record_cost("fact_checker", "fact_check", cost_usd)` po każdym `_check_one()`.

---

### B-005 — MEDIUM: Jednokrotne ostrzeżenie przy 80% — brak eskalacji przy 90%, 95%

**Severity:** MEDIUM  
**Lokalizacja:** `record_cost()` L.170–178; `warning_issued: bool` L.77

**Problem:** Flaga `warning_issued` jest ustawiana po pierwszym przekroczeniu `warning_threshold` (80%) i nigdy resetowana. Operator dostaje jeden log warning przy $40/$50, a następne $5 wydatku (90%) przechodzi bez dodatkowego sygnału aż do hard stop. W systemach z wieloma pipeline'ami uruchamianymi równolegle, jeden operator może przeoczyć jedyne ostrzeżenie.

**Rekomendacja:** Implementacja multi-level warnings:
```python
WARNING_LEVELS = [0.80, 0.90, 0.95]
_warned_levels: set[float] = field(default_factory=set)

# W record_cost():
for level in WARNING_LEVELS:
    if ratio >= level and level not in self._state._warned_levels:
        self._state._warned_levels.add(level)
        logger.warning("Budget at %.0f%%: $%.4f / $%.2f", level*100, ...)
        if level >= 0.90:
            self._notify_human_gate(level)  # Soft gate dla 90%+
```

---

### B-006 — LOW: `_save_daily_state()` wywołana przy każdym record_cost() — I/O overhead

**Severity:** LOW  
**Lokalizacja:** `record_cost()` L.167; `_save_daily_state()` L.320–328

**Problem:** Każde wywołanie `record_cost()` zapisuje cały plik JSON na dysk (wszystkie entries). Przy intensywnym pipeline (1000 agent calls/godz), oznacza to 1000 disk writes/godz z rosnącym plikiem. Przy 50 000 entries plik może mieć kilka MB — zapis synchroniczny w critical path powoduje dodatkowe latency.

**Rekomendacja:** Debounce zapisu — flush co N calls lub co T sekund:
```python
def _save_daily_state(self) -> None:
    self._dirty_count = getattr(self, "_dirty_count", 0) + 1
    if self._dirty_count % 10 == 0:  # Flush co 10 calls
        self._flush_to_disk()
```
Alternatywnie: asynchroniczny zapis w tle (asyncio lub threading).

---

## 9. Podsumowanie

| ID    | Severity | Obszar                                          | Status |
|-------|----------|-------------------------------------------------|--------|
| B-001 | CRITICAL | Race condition w record_cost() — brak thread-safety | OPEN |
| B-002 | HIGH     | Brak wyjątku przy budget exceeded — opt-in check | OPEN  |
| B-003 | HIGH     | Brak per-user/per-task granularności            | OPEN   |
| B-004 | HIGH     | FactChecker koszty poza BudgetGuard             | OPEN   |
| B-005 | MEDIUM   | Jednokrotne warning — brak multi-level alerts   | OPEN   |
| B-006 | LOW      | I/O overhead — zapis JSON przy każdym record    | OPEN   |

**Granularność budżetu:** Wyłącznie globalny dzienny cap ($50.00 domyślnie). Brak per-task, per-user, per-provider, miesięcznego. `get_cost_by_agent()` i `get_cost_by_stage()` dostarczają breakdown tylko do celów raportowania.

**Hard stop:** `record_cost()` zwraca `False` + `GateLevel.CRITICAL` escalation. Nie rzuca wyjątku — orchestrator musi aktywnie sprawdzać wartość zwracaną lub `is_exceeded` property.

**Integracja z cost_tracker:** Luźna i niesymetryczna — cost_tracker rejestruje na poziomie LLM calls (tokeny), BudgetGuard na poziomie agent runs (USD). Brak automatycznej synchronizacji między nimi.
