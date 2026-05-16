# SYLION v5.9.0 — Audit: Bugs & Edge Cases
**Reviewer:** Claude Sonnet 4.6 (bugs, off-by-one, None handling, exception swallowing, race conditions)  
**Date:** 2026-04-19  
**Scope:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/` — wszystkie *.py

---

## BUG-001 — CRITICAL | tests/test_m07_h04_v590.py: Test M07 FAILS — 13 forków zamiast 1

**Severity:** CRITICAL  
**Plik:linia:** `dashboard/start.py:123` + `tests/test_m07_h04_v590.py:90–106`  
**Opis:**  
Test `test_ensure_dependencies_single_fork_on_success` oczekuje, że na ścieżce happy-path (wszystkie paczki dostępne via `find_spec`) `_ensure_dependencies()` wywoła `subprocess.run` dokładnie **1 raz** (batch). W rzeczywistości wywoływany jest **13 razy** (jeden per pakiet). Root cause: monkeypatch `importlib.util.find_spec` jest ustawiany na module-level string `"importlib.util.find_spec"`, ale `start.py` importuje `importlib.util` bezpośrednio i wywołuje `importlib.util.find_spec(...)` — monkeypatch nie trafia do lokalnego namespace `_spec_ok()`. Dodatkowo `_batch_imports_ok()` nie jest mockowana — wykonuje rzeczywiste forki.  
**Fix proposal:**  
W `start.py` zmienić `importlib.util.find_spec(import_name)` na alias lokalny `_find_spec = importlib.util.find_spec` na górze pliku, lub w testach użyć `monkeypatch.setattr(start_mod, "_spec_ok", lambda name: True)` zamiast patchowania stdlib. Alternatywnie: wyodrębnić `_spec_ok` i `_batch_imports_ok` jako moduł-level funkcje (`start_mod._spec_ok`) dostępne do bezpośredniego patchowania.

---

## BUG-002 — CRITICAL | tests/test_m02_m08_v590.py: Test M08 FAILS — monkeypatch na immutable type

**Severity:** CRITICAL  
**Plik:linia:** `tests/test_m02_m08_v590.py:472`  
**Opis:**  
Test `test_backup_failure_does_not_corrupt_main_db` wywołuje `monkeypatch.setattr(sqlite3.Connection, "backup", _failing_backup)`. Powoduje błąd: `TypeError: cannot set 'backup' attribute of immutable type 'sqlite3.Connection'` — `sqlite3.Connection` jest typem C i nie wspiera monkey-patchowania. Test jest niemożliwy do uruchomienia w aktualnej formie. Produkuje ERROR w teardown (nie tylko FAILED).  
**Fix proposal:**  
Zamiast patchować `sqlite3.Connection.backup` bezpośrednio — opakować wywołanie backup w `_backup_db_before_migration()` do testable helper, np. `_do_backup(source_conn, dest_conn)`, który można patchować: `monkeypatch.setattr(db_module, "_do_backup", lambda s, d: (_ for _ in ()).throw(OSError("disk full")))`. Alternatywnie: użyć `unittest.mock.patch.object` na konkretnej instancji `conn` (patch na obiekcie, nie na typie).

---

## BUG-003 — CRITICAL | tests/test_m07_h04_v590.py: Test H04 FAILS — cursor attribute read-only

**Severity:** CRITICAL  
**Plik:linia:** `tests/test_m07_h04_v590.py:285`, `tests/test_m07_h04_v590.py:351`  
**Opis:**  
Testy `test_seed_agents_unknown_tag_on_first_iteration_failure` i `test_seed_agents_agent_id_reset_between_iterations` wykonują `conn.cursor = patched_cursor` na `sqlite3.Connection` — ta sama klasa C, ten sam problem co BUG-002. `AttributeError: 'sqlite3.Connection' object attribute 'cursor' is read-only`. Testy były projektowane dla CPython <3.12 gdzie sqlite3 implementacja była bardziej elastyczna.  
**Fix proposal:**  
Użyć wrapper/adaptera: `class _ConnWrapper: def __init__(self, real): self._real = real; def cursor(self): ...`. Przekazać wrapper do funkcji testowanej zamiast prawdziwego `sqlite3.Connection`. `_seed_agents()` powinno akceptować `conn` jako argument (dependency injection) zamiast tworzyć nowe połączenie wewnętrznie.

---

## BUG-004 — HIGH | ai_review.py:203 — `except Exception: continue` ukrywa błędy odczytu pliku

**Severity:** HIGH  
**Plik:linia:** `ai_review.py:203–205`  
**Opis:**  
```python
try:
    content = fpath.read_text(encoding="utf-8", errors="replace")
except Exception:
    continue
```
Wyjątek przy odczycie pliku (np. `PermissionError`, `IsADirectoryError`, `FileNotFoundError`) jest milcząco pomijany. Scanner przechodzi do następnego pliku bez ostrzeżenia operatora. Może ukryć realne problemy z uprawnieniami lub stanem systemu plików.  
**Fix proposal:**  
`except OSError as e: log.warning("Static scan: cannot read %s: %s", fpath, e); continue`.

---

## BUG-005 — HIGH | config.py:44,69,84,118 — Exception swallowing w 4 funkcjach DB access

**Severity:** HIGH  
**Plik:linia:** `config.py:44`, `:69`, `:84`, `:118`  
**Opis:**  
Wszystkie funkcje odczytu konfiguracji DB łapią `except Exception: return default` bez logowania. Jeśli baza jest uszkodzona (np. po niekompletnym zapisie), aplikacja startuje ze skonfigurowanymi wartościami domyślnymi (puste klucze API), ale nie ma żadnego śladu w logach co ułatwiałoby diagnozę.  
**Fix proposal:**  
`except Exception as e: logging.getLogger("config").debug("DB config read failed: %s", e); return default`.

---

## BUG-006 — HIGH | agent_manager.py: save() + enable()/disable() — race condition przy YAML write

**Severity:** HIGH  
**Plik:linia:** `agent_manager.py:220–237` (`save()`), `agent_manager.py:242` (`enable()`)  
**Opis:**  
`enable(name)` akwiruje `self._lock`, modyfikuje `self.agents[name].enabled`, następnie wywołuje `self.save()` już **poza** lockiem (`self._lock` jest zwolniony przez `with self._lock:` blok). `save()` otwiera plik YAML, czyta go, modyfikuje i zapisuje bez żadnej synchronizacji. Jeśli dwa wątki wywołają `enable()` i `disable()` równolegle — oba dokonają read→modify→write na tym samym pliku i jeden nadpisze drugiego.  
**Fix proposal:**  
Przenieść `self.save()` do bloku `with self._lock:` lub użyć `fcntl.flock()` na pliku YAML podczas zapisu. Alternatywnie: zamiast read-modify-write pliku, utrzymywać in-memory state jako jedyne źródło prawdy i zapisywać go atomowo.

---

## BUG-007 — HIGH | ai_review.py `_parse_llm_findings`: regex `\[[\s\S]*?\]` — lazy match może ominąć tablicę

**Severity:** HIGH  
**Plik:linia:** `ai_review.py:640–660`  
**Opis:**  
`re.search(r"\[[\s\S]*?\]", text)` z lazy quantifier `*?` znajdzie **najkrótsze** dopasowanie `[...]`, co w przypadku JSON jak `[{"id": ..., "description": "see [1]"}, ...]` może zatrzymać się na `[1]` zamiast całej tablicy. Prowadzi to do `json.loads` failure i cichego pominięcia wszystkich findings z odpowiedzi LLM.  
**Fix proposal:**  
Użyć greedy: `r"\[[\s\S]*\]"` lub lepiej parsować za pomocą `json.JSONDecoder().raw_decode(text, text.index("["))`. Dodać fallback logowanie gdy JSON parse fails: `log.debug("LLM JSON parse failed for %s: %s", reviewer, e)`.

---

## BUG-008 — MEDIUM | budget_guard.py:251 — Exception swallowing w `record_cost()`

**Severity:** MEDIUM  
**Plik:linia:** `budget_guard.py:251`  
**Opis:**  
`record_cost()` w `except Exception as e: logger.error("BudgetGuard record_cost failed: %s", e)` — błąd jest logowany, ale nie propagowany. Gdy `_save_daily_state()` rzuci wyjątek (np. brak miejsca na dysku), operacja jest traktowana jako sukces. Koszt agenta nie zostaje zapisany, ale pipeline kontynuuje — prowadząc do niedoszacowania dziennego budżetu.  
**Fix proposal:**  
Przy `OSError` (brak miejsca) propagować wyjątek lub co najmniej inkrementować counter `_save_failures` i po N failures eskalować do Human Gate.

---

## BUG-009 — MEDIUM | bridge.py: `get_gate_decision()` polling bez exponential backoff

**Severity:** MEDIUM  
**Plik:linia:** `dashboard/bridge.py:95–115` (`get_gate_decision()`)  
**Opis:**  
Metoda `get_gate_decision(timeout_s=60)` polluje bazę co sekundę `time.sleep(1)` w pętli. Przy długich timeout'ach (np. 300s dla critical decisions) tworzy 300 zapytań SQL. Brak exponential backoff ani jitter. W sytuacji gdy dashboard DB jest niedostępna — każda iteracja tworzy nowe połączenie, które failuje, a exception jest łapana i ignorowana (linia 111: `log.error(...)`), po czym pętla kontynuuje.  
**Fix proposal:**  
Dodać exponential backoff: `sleep = min(1 * 2**attempt, 30)`, lub użyć `asyncio.wait_for()` z SQLite NOTIFY (via polling na `updated_at` timestamp). Opcjonalnie: WebSocket event zamiast pollingu.

---

## BUG-010 — MEDIUM | orchestrator.py: `_globals_lock` (threading.Lock) używany z asyncio

**Severity:** MEDIUM  
**Plik:linia:** `orchestrator.py:118` + użycia w `init_supervisor` i `run_pipeline`  
**Opis:**  
`_globals_lock = threading.Lock()` jest używany w funkcjach async (`init_supervisor` jest sync, ale wywoływane z async context). Jeśli `_globals_lock` jest akwirowany wewnątrz `asyncio.to_thread()` i równolegle jakiś coroutine próbuje go akwirować w event loop thread — dojdzie do deadlock lub zablokowania event loop. `threading.Lock()` blokuje cały wątek, nie yield do event loop.  
**Fix proposal:**  
Użyć `asyncio.Lock()` dla coroutines i `threading.Lock()` tylko dla synchronicznych funkcji w executorze. Lub przenieść całą inicjalizację do synchronicznej fazy startup przed startem event loop.

---

## BUG-011 — MEDIUM | ai_review.py: `synthesize_reviews` — threshold błędny przy 2 recenzentach (1/1 majority)

**Severity:** MEDIUM  
**Plik:linia:** `ai_review.py:751` (`threshold = max(2, len(active_reports) // 2 + 1)`)  
**Opis:**  
Przy 2 aktywnych reviewerach: `threshold = max(2, 2//2 + 1) = max(2, 2) = 2`. Finding musi być zgłoszone przez obu reviewerów, by trafić do `agreed`. Przy 1 aktywnym (Ollama down, Claude skip): `threshold = max(2, 1) = 2` — żaden finding nie trafi do agreed, nawet CRITICAL z jedynego dostępnego reviewera. To prowadzi do fałszywego "no agreed findings" przy degradacji systemu.  
**Fix proposal:**  
`threshold = max(1, len(active_reports) // 2 + 1)` — przy 1 recenzencie wystarczy 1/1. Dodać ostrzeżenie gdy liczba aktywnych recenzentów < 2: `log.warning("Only %d active reviewer(s) — findings may be incomplete", len(active_reports))`.

---

## BUG-012 — LOW | claim_provenance.py: `verify_claim` — off-by-one w context window przy line_number=1

**Severity:** LOW  
**Plik:linia:** `claim_provenance.py:155–160`  
**Opis:**  
`start = max(0, claim.line_number - 1 - self.context_window)` — przy `line_number=1` i `context_window=10`: `start = max(0, 1 - 1 - 10) = max(0, -10) = 0`. Poprawnie. Ale `end = min(len(lines), claim.line_number + self.context_window)` — przy `line_number=1`: `end = min(N, 11)`. Context zawiera linie 0–11 (12 linii) zamiast 21 (`-10..+10`). Asymetryczne okno kontekstowe przy pierwszych liniach pliku — może obniżyć `match_ratio` dla keywords które faktycznie są w pliku ale poniżej linii 11.  
**Fix proposal:**  
Dokumentować asymetrię okna przy edge of file jako expected behavior, lub wyrównać: `actual_window = min(self.context_window, claim.line_number - 1)`.

---

*Zgłosił: Claude Sonnet 4.6 (bugs i edge cases)*
