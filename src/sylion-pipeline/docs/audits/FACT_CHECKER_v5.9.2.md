# SYLION v5.9.1 — Audit: fact_checker.py
**Data audytu:** 2025-07-07  
**Audytor:** Automated Security Review  
**Plik:** `sylion-pipeline/fact_checker.py` (491 linii, ~19 kB)  
**Snapshot:** `snapshot_0052` vs `latest`

---

## 1. Co weryfikuje

`FactCheckerAgent` to Warstwa 5 Anti-Hallucination — niezależny agent LLM uruchamiany przed Stage 6 (Deploy). Weryfikuje:

1. Czy cytowana ścieżka pliku i numer linii zawierają opisany kod  
2. Czy opisana podatność/problem faktycznie istnieje w danym miejscu  
3. Czy proponowany fix rzeczywiście rozwiązuje problem  
4. Czy ocena severity (CRITICAL/HIGH/MEDIUM/LOW) jest uzasadniona  
5. Detekcja halucynacji — przypadki gdy audytor sfabrykował kod, numery linii lub problemy  

**Weryfikuje:** claims agentów (opisy znalezisk + patche) vs rzeczywisty kod źródłowy z repozytorium. Nie weryfikuje dokumentów — tylko pliki Go z workspace.

---

## 2. Threshold dla „fact"

Brak jawnego liczbowego progu akceptacji — decyzja jest jakościowa (enum `FactCheckVerdict`):

| Verdict       | Znaczenie                                             |
|---------------|-------------------------------------------------------|
| `CONFIRMED`   | Znalezisko i fix zweryfikowane przez niezależny LLM   |
| `DISPUTED`    | LLM uważa znalezisko lub fix za nieprawidłowe         |
| `HALLUCINATION` | LLM wykrył sfabrykowane treści                      |
| `INCONCLUSIVE` | LLM nie może ustalić poprawności                    |
| `SKIPPED`     | Pominięto (brak LLM, budget, timeout)                 |
| `ERROR`       | Błąd wewnętrzny                                       |

`confidence` (0.0–1.0) pochodzi z odpowiedzi LLM — nie ma progu który automatycznie zmienia verdict. `FactCheckReport.to_dict()` oblicza `confirmation_rate` i `hallucination_rate`, ale orchestrator nie blokuje pipeline po przekroczeniu żadnego z nich.

**Integracja z orchstratorem:** Wymagana ręczna decyzja — raport jest zapisywany, lecz nie ma zdefiniowanej polityki blokowania (patrz Finding F-001).

---

## 3. Integracja z orchestratorem

- Instancja tworzona w orchestratorze przez: `FactCheckerAgent(workspace=..., llm_caller=..., model_id=...)`
- Po każdym wywołaniu LLM koszty są rejestrowane do `cost_tracker` (v5.9.1 Cluster R, nowość vs snapshot)
- Model domyślny: `anthropic/claude-sonnet-4-6` (zmieniony z `claude-sonnet-4-5-20250929` w snapshot)
- Model konfigurowalny przez env var `FACT_CHECKER_MODEL_ID` (nowość vs snapshot)
- Log zapisywany do `log_dir/fact_check_report.json`
- Brak asynchronicznego przetwarzania — `check_all` działa sekwencyjnie

---

## 4. Testy w test_*.py

Plik: `test_anti_hallucination.py` — klasa `TestFactCheckerAgent` (9 testów):

| Test                           | Co pokrywa                                      |
|--------------------------------|-------------------------------------------------|
| `test_skipped_when_no_llm`     | SKIPPED verdict bez LLM callera                 |
| `test_confirmed_with_mock_llm` | CONFIRMED + confidence z mock LLM               |
| `test_hallucination_detected`  | HALLUCINATION verdict                           |
| `test_check_all_report`        | Agregacja raportu (total_items, errors)         |
| `test_file_not_found_context`  | Obsługa brakującego pliku                       |
| `test_line_oob_context`        | Obsługa numeru linii poza zakresem              |
| `test_parse_markdown_json`     | Parser JSON w blokach markdown                  |
| `test_max_items_enforcement`   | Limit `max_items_per_run`                       |
| `test_result_serialization`    | JSON-serializowalność FactCheckResult           |

**Brak testów dla:** DISPUTED verdict, ERROR verdict, `_save_report`, cost_tracker integration, równoległości.

---

## 5. Nowości vs snapshot_0052

| Element                        | snapshot_0052                  | latest (v5.9.1)                        |
|--------------------------------|-------------------------------|----------------------------------------|
| Model domyślny                 | `claude-sonnet-4-5-20250929`  | `claude-sonnet-4-6`                    |
| `model_id` parametr            | Wymagany string               | Optional (`None` → env/default)        |
| Env var override               | Brak                          | `FACT_CHECKER_MODEL_ID`                |
| cost_tracker integracja        | Brak                          | Pełna (Cluster R FinOps)               |
| Rejestracja failed calls       | Brak                          | Dodana (`success=False`)               |

---

## 6. Findings

### F-001 — CRITICAL: Brak polityki blokowania pipeline po wykryciu halucynacji

**Severity:** CRITICAL  
**Lokalizacja:** `check_all()` L.224–277; orchestrator.py (integracja zewnętrzna)

**Problem:** `FactCheckReport` zawiera `hallucinations` counter oraz `hallucination_rate`, ale nie ma mechanizmu który automatycznie wstrzymuje pipeline gdy rate przekroczy próg. Orchestrator musi ręcznie sprawdzić `report.hallucinations > 0`. Jeśli developer zapomni o tym sprawdzeniu, halucynacje przechodzą do Stage 6 (Deploy).

**Rekomendacja:** Dodać metodę `should_block_pipeline(threshold: float = 0.0) -> bool` i wymusić jej wywołanie w orchestratorze.

**Patch sketch:**
```python
# W FactCheckReport:
def should_block_pipeline(self, hallucination_threshold: float = 0.0,
                          disputed_threshold: float = 0.5) -> bool:
    if self.total_items == 0:
        return False
    h_rate = self.hallucinations / self.total_items
    d_rate = self.disputed / self.total_items
    return h_rate > hallucination_threshold or d_rate > disputed_threshold

# W orchestratorze:
if report.should_block_pipeline():
    raise PipelineBlockedError("FactChecker blocked pipeline — halucynacje wykryte")
```

---

### F-002 — HIGH: Sekwencyjne wywołania LLM — brak równoległości

**Severity:** HIGH  
**Lokalizacja:** `check_all()` L.243–246 (`for item in check_items: result = self._check_one(item)`)

**Problem:** Przy `max_items_per_run=50` i średnim czasie LLM ~5s per call, całkowity czas = 250s (4+ minuty). Brak `asyncio` lub `ThreadPoolExecutor`. Dla dużych audytów z wieloma findings, FactChecker staje się wąskim gardłem.

**Rekomendacja:** Zrównoleglić `_check_one()` przez `concurrent.futures.ThreadPoolExecutor`.

**Patch sketch:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def check_all(self, items, max_workers: int = 4) -> FactCheckReport:
    check_items = items[:self.max_items_per_run]
    results = [None] * len(check_items)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(self._check_one, item): i
                   for i, item in enumerate(check_items)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    ...
```

---

### F-003 — HIGH: Brak confidence threshold — INCONCLUSIVE traktowane jak sukces

**Severity:** HIGH  
**Lokalizacja:** `_parse_response()` L.476–477; `check_all()` tallying L.249–253

**Problem:** Wynik `INCONCLUSIVE` z `confidence=0.1` i `INCONCLUSIVE` z `confidence=0.9` są liczone identycznie. `FactCheckReport.errors` sumuje `ERROR + SKIPPED` ale nie `INCONCLUSIVE`. Przypadki wątpliwe (LLM nie wie) przechodzą niezauważone — wysoka niepewność powinna eskalować lub blokować.

**Rekomendacja:** Dodać próg `min_confidence_for_inconclusive` (default 0.6) — poniżej traktować jako potencjalną halucynację.

**Patch sketch:**
```python
# W _check_one():
if result.verdict == FactCheckVerdict.INCONCLUSIVE and result.confidence < 0.6:
    log.warning("Low-confidence INCONCLUSIVE for %s — treating as suspect", item.finding_id)
    result.issues_found.append("Low confidence inconclusive — manual review recommended")
```

---

### F-004 — MEDIUM: Token count estimation błędna (1 token ≠ 4 znaki dla kodu)

**Severity:** MEDIUM  
**Lokalizacja:** `_check_one()` L.323–324

**Problem:** Szacowanie tokenów jako `len(text) // 4` jest niepoprawne dla kodu Go i JSON. Kod Go ma krótkie tokeny (słowa kluczowe, operatory), efektywny ratio to ~3 znaki/token. Błąd ~25–30% przeszacowania kosztów → `cost_tracker` raportuje zawyżone koszty.

**Rekomendacja:** Użyć biblioteki `tiktoken` lub approximation specyficznej dla modelu (`// 3` dla kodu).

**Patch sketch:**
```python
try:
    import tiktoken
    enc = tiktoken.encoding_for_model("gpt-4")
    _in = len(enc.encode(FACT_CHECK_SYSTEM_PROMPT + user_prompt))
    _out = len(enc.encode(response))
except ImportError:
    _in = max(1, (len(FACT_CHECK_SYSTEM_PROMPT) + len(user_prompt)) // 3)
    _out = max(1, len(response) // 3)
```

---

### F-005 — MEDIUM: `reasoning` truncated do 2000 znaków w `to_dict()`

**Severity:** MEDIUM  
**Lokalizacja:** `FactCheckResult.to_dict()` L.95

**Problem:** `"reasoning": self.reasoning[:2000]` — przy obszernym uzasadnieniu LLM (szczegółowy opis halucynacji) krytyczne informacje są obcinane w logach. Developer analizujący `fact_check_report.json` może nie zobaczyć pełnego uzasadnienia dla HALLUCINATION verdict.

**Rekomendacja:** Zapisywać pełne uzasadnienie w raporcie (`reasoning_full`), skróconą wersję zostawić w `reasoning` dla wyświetlania.

**Patch sketch:**
```python
def to_dict(self) -> dict[str, Any]:
    return {
        ...
        "reasoning": self.reasoning[:2000],
        "reasoning_full": self.reasoning,  # Dodane pole
        ...
    }
```

---

### F-006 — LOW: Brak testów dla DISPUTED verdict i cost_tracker integration

**Severity:** LOW  
**Lokalizacja:** `test_anti_hallucination.py` — klasa `TestFactCheckerAgent`

**Problem:** Verdict `DISPUTED` (znalezisko istnieje, ale severity niepoprawne) nie jest pokryty żadnym testem. Integracja cost_tracker z mock'iem nie jest testowana — błąd w obliczeniu kosztu nie zostanie wykryty w CI.

**Rekomendacja:** Dodać testy:
```python
def test_disputed_severity(self):
    mock_resp = json.dumps({"verdict": "DISPUTED", "confidence": 0.8,
        "reasoning": "Severity too high", "issues_found": ["Should be MEDIUM"],
        "suggested_severity": "MEDIUM"})
    ...
    assert result.verdict == FactCheckVerdict.DISPUTED
    assert result.suggested_severity == "MEDIUM"
```

---

## 7. Podsumowanie

| ID    | Severity | Obszar                              | Status    |
|-------|----------|-------------------------------------|-----------|
| F-001 | CRITICAL | Brak auto-blokowania pipeline       | OPEN      |
| F-002 | HIGH     | Brak równoległości LLM calls        | OPEN      |
| F-003 | HIGH     | INCONCLUSIVE bez confidence gate    | OPEN      |
| F-004 | MEDIUM   | Błędne szacowanie tokenów           | OPEN      |
| F-005 | MEDIUM   | Truncation reasoning w logach       | OPEN      |
| F-006 | LOW      | Niepełne pokrycie testami           | OPEN      |

**False positive/negative rate:** Niemożliwy do zmierzenia — nie ma testów z rzeczywistymi parami (znalezisko + kod), brak metryk historycznych z pipeline. Zalecane uruchomienie FactCheckera na zbiorze labeled findings i pomiar accuracy.
