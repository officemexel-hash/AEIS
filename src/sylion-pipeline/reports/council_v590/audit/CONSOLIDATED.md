# SYLION v5.9.0 — CONSOLIDATED AUDIT REPORT
**Wersja:** 5.9.0 (Breakthrough — 18 Skills Audit)  
**Data audytu:** 2026-04-19  
**Scope:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/` — wszystkie *.py  
**Recenzenci:** Claude Opus 4.7 (architektura) · Claude Sonnet 4.6 (bugs) · GPT-5.4 (type safety) · Gemini 3.1 Pro (testy)

---

## Wyniki testów

```
6 failed, 30 passed, 2 warnings, 5 errors in 2.76s
```

**Passed:** 30  
**Failed:** 6  
**Errors:** 5 (w tym 1 teardown error pokrywający się z FAILED)

### Szczegółowe failures:
| Test | Błąd |
|------|------|
| `test_m02_m08_v590::TestM08Backup::test_backup_failure_does_not_corrupt_main_db` | `TypeError: cannot set 'backup' attribute of immutable type 'sqlite3.Connection'` |
| `test_m07_h04_v590::TestEnsureDependenciesM07::test_ensure_dependencies_single_fork_on_success` | `AssertionError: oczekiwano 1 wywołania subprocess.run (batch), dostano 13` |
| `test_m07_h04_v590::TestEnsureDependenciesM07::test_ensure_dependencies_fallback_per_package_on_failure` | Monkeypatch nie trafia do lokalnego namespace start.py |
| `test_m07_h04_v590::TestEnsureDependenciesM07::test_ensure_dependencies_timeout_handled` | j.w. |
| `test_m07_h04_v590::TestSeedAgentsH04::test_seed_agents_unknown_tag_on_first_iteration_failure` | `AttributeError: 'sqlite3.Connection' object attribute 'cursor' is read-only` |
| `test_m07_h04_v590::TestSeedAgentsH04::test_seed_agents_agent_id_reset_between_iterations` | j.w. |

### ERRORS (5, w tym nakładające się):
| Error | Typ |
|-------|-----|
| `test_m02_m08_v590::TestM08Backup::test_backup_failure_does_not_corrupt_main_db` | ERROR in teardown (monkeypatch.undo na immutable type) |
| `test_m03_m06_v590::TestDashboardM06` (4 testy) | SKIPPED — fastapi nie importuje się, testy oznaczone skipem, ale pytest raportuje jako ERROR |

---

## Podsumowanie findings

| ID | Severity | Obszar | Plik:linia | Zgłosił |
|----|----------|--------|-----------|---------|
| ARC-001 | CRITICAL | Architektura | orchestrator.py:122 | Opus |
| ARC-002 | HIGH | Architektura | orchestrator.py:118 | Opus |
| ARC-003 | HIGH | Architektura | orchestrator.py:67 | Opus |
| ARC-004 | HIGH | Architektura | agent_manager.py:35 | Opus |
| ARC-005 | HIGH | Dead code | ai_review.py:700 | Opus |
| ARC-006 | MEDIUM | Architektura | config.py:44 | Opus |
| ARC-007 | MEDIUM | Architektura | dashboard/bridge.py:16 | Opus |
| ARC-008 | MEDIUM | Architektura | orchestrator.py:770 | Opus |
| ARC-009 | LOW | DRY | loop_guard.py:23 | Opus |
| ARC-010 | LOW | Architektura | models.py:90 | Opus |
| BUG-001 | CRITICAL | Test failure | dashboard/start.py:123 | Sonnet |
| BUG-002 | CRITICAL | Test failure | tests/test_m02_m08_v590.py:472 | Sonnet |
| BUG-003 | CRITICAL | Test failure | tests/test_m07_h04_v590.py:285 | Sonnet |
| BUG-004 | HIGH | Exception swallowing | ai_review.py:203 | Sonnet |
| BUG-005 | HIGH | Exception swallowing | config.py:44 | Sonnet |
| BUG-006 | HIGH | Race condition | agent_manager.py:220 | Sonnet |
| BUG-007 | HIGH | Regex bug | ai_review.py:640 | Sonnet |
| BUG-008 | MEDIUM | Exception swallowing | budget_guard.py:251 | Sonnet |
| BUG-009 | MEDIUM | Performance | dashboard/bridge.py:95 | Sonnet |
| BUG-010 | MEDIUM | Async/threading | orchestrator.py:118 | Sonnet |
| BUG-011 | MEDIUM | Logic bug | ai_review.py:751 | Sonnet |
| BUG-012 | LOW | Off-by-one | claim_provenance.py:155 | Sonnet |
| TYPE-001 | HIGH | Type safety | orchestrator.py:122 | GPT-5.4 |
| TYPE-002 | HIGH | Any abuse | agent_manager.py:97 | GPT-5.4 |
| TYPE-003 | HIGH | Missing generics | ai_review.py:188 | GPT-5.4 |
| TYPE-004 | HIGH | Missing Pydantic | models.py:90 | GPT-5.4 |
| TYPE-005 | MEDIUM | Optional markers | agent_manager.py:68 | GPT-5.4 |
| TYPE-006 | MEDIUM | Pydantic validation | dashboard/app.py:180 | GPT-5.4 |
| TYPE-007 | MEDIUM | Return type | config.py:84 | GPT-5.4 |
| TYPE-008 | MEDIUM | Optional usage | loop_guard.py:69 | GPT-5.4 |
| TYPE-009 | LOW | Input validation | claim_provenance.py:75 | GPT-5.4 |
| TYPE-010 | LOW | Type annotation | agent_manager.py:305 | GPT-5.4 |
| COV-001 | CRITICAL | Test coverage | budget_guard.py:145 | Gemini |
| COV-002 | CRITICAL | Test coverage | file_verification.py:1 | Gemini |
| COV-003 | HIGH | Test coverage | loop_guard.py | Gemini |
| COV-004 | HIGH | Test coverage | claim_provenance.py:90 | Gemini |
| COV-005 | HIGH | Test coverage | agent_manager.py:360 | Gemini |
| COV-006 | HIGH | Test coverage | abr_controller.py:232 | Gemini |
| COV-007 | MEDIUM | Test coverage | supervisor.py:170 | Gemini |
| COV-008 | MEDIUM | Test coverage | dashboard/bridge.py | Gemini |
| COV-009 | MEDIUM | Test coverage | dashboard/db.py:785 | Gemini |
| COV-010 | LOW | Test coverage | fact_checker.py | Gemini |

---

## Statystyki

| Severity | Liczba |
|----------|--------|
| CRITICAL | 7 |
| HIGH | 17 |
| MEDIUM | 12 |
| LOW | 6 |
| **RAZEM** | **42** |

---

## Priorytety naprawy

### Blokery (natychmiastowe — testy nie przechodzą)

1. **BUG-002 / BUG-003** — `sqlite3.Connection` nie jest monkey-patchowalny w Pythonie 3.12. Testy M08 i H04 muszą używać wrapperów zamiast bezpośredniego patchowania C-extension. Root cause: testy projektowane dla Python <3.12 API.

2. **BUG-001** — Test M07 (`test_ensure_dependencies_single_fork_on_success`) oczekuje 1 forka subprocess, ale `_ensure_dependencies()` wywołuje 13. Monkeypatch `importlib.util.find_spec` nie działa przez zamknięcie lokalnej funkcji `_spec_ok()`. Wymaga refactoru `start.py` by `_spec_ok` był patchowalny.

### Krytyczne design issues

3. **ARC-001** — `orchestrator.py` jako god object (30+ globalnych singletonów, 3300+ linii). Priorytet refactoru dla maintainability.

4. **COV-001 + COV-002** — `BudgetGuard` i `FileVerificationLayer` to krytyczne komponenty bezpieczeństwa bez pokrycia pytest. `file_verification.py` ma wbudowane testy (17 sztuk) ale nie są dostępne przez `pytest tests/`.

### Wysokie ryzyko runtime

5. **BUG-006** — race condition w `AgentManager.save()` przy równoległych operacjach enable/disable.

6. **BUG-010** — `threading.Lock` używany w async context może blokować event loop.

7. **TYPE-002** — `params: dict[str, Any]` w `AgentConfig` eliminuje type safety dla kluczowych parametrów agentów.

---

## Wzorce powtarzające się (cross-reviewer)

| Pattern | Instances | Recenzenci |
|---------|-----------|-----------|
| Exception swallowing bez logowania | BUG-004, BUG-005, BUG-008, ARC-006 | Sonnet, Opus |
| `Any` typ w kluczowych strukturach | TYPE-002, TYPE-003, TYPE-004, ARC-010 | GPT-5.4, Opus |
| Brak testów dla security components | COV-001, COV-002, COV-003, COV-007 | Gemini |
| Mutable global state | ARC-001, ARC-002, BUG-006 | Opus, Sonnet |
| Monkey-patch na stdlib C-types | BUG-002, BUG-003 | Sonnet |

---

## Pliki z najwyższą koncentracją problemów

| Plik | Findings | Max Severity |
|------|----------|-------------|
| `orchestrator.py` | ARC-001, ARC-002, ARC-003, ARC-008, BUG-010, TYPE-001 | CRITICAL |
| `ai_review.py` | ARC-005, BUG-004, BUG-007, BUG-011, TYPE-003 | HIGH |
| `agent_manager.py` | ARC-004, BUG-006, TYPE-002, TYPE-005, COV-005 | HIGH |
| `dashboard/start.py` | BUG-001 | CRITICAL |
| `config.py` | ARC-006, BUG-005, TYPE-007 | HIGH |
| `tests/test_m07_h04_v590.py` | BUG-001, BUG-003 | CRITICAL |
| `tests/test_m02_m08_v590.py` | BUG-002 | CRITICAL |

---

*Raport skonsolidowany przez orchestrator multi-ai-audyt. Szczegóły: `opus.md`, `sonnet.md`, `gpt54.md`, `gemini.md`. Wyniki testów: `test-run.txt`.*
