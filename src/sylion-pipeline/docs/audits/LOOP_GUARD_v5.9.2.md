# SYLION v5.9.1 — Audit: loop_guard.py
**Data audytu:** 2025-07-07  
**Audytor:** Automated Security Review  
**Plik:** `sylion-pipeline/loop_guard.py` (1511 linii, ~62 kB)  
**Snapshot:** `snapshot_0052` vs `latest` — **IDENTYCZNE** (brak zmian diff)

---

## 1. Architektura — 3 komponenty

`loop_guard.py` zawiera trzy klasy w jednym pliku:

| Klasa                | Odpowiedzialność                                                  |
|----------------------|-------------------------------------------------------------------|
| `LoopGuard`          | Wykrywanie pętli, limity hard iteration, eskalacja do człowieka  |
| `ContextPersistence` | Zapis patch summaries, stage summaries, okno kontekstu (20 wpisów) |
| `IterationTracker`   | Pełny stan pętli korekcji per-plik; persistence do JSON          |

---

## 2. Cztery wzorce pętli (4 loop patterns)

Kod implementuje **3 jawne wzorce** wykrywane przez scoring, plus **1 implicit**:

### Wzorzec 1: Same-fix (identyczna łatka)
Wykrywany przez `_calculate_patch_overlap_score()` — `SequenceMatcher.ratio() >= 0.85` → `patch_score = 1.0`.  
Agent aplikuje tę samą zmianę wielokrotnie bez efektu.

### Wzorzec 2: Variant-fix (podobna łatka)
`SequenceMatcher.ratio() >= 0.60` → `patch_score = ratio` (liniowa interpolacja).  
Agent modyfikuje tę samą sekcję kodu w nieznacznie różny sposób.

### Wzorzec 3: Regression-bounce (oscylacja)
Agent A → patch diff1, Agent A → patch diff2 (cofający diff1), Agent A → diff1...  
Wykrywany przez porównanie ostatniej łatki ze WSZYSTKIMI poprzednimi: jeśli podobieństwo do wcześniejszej ≥ 0.85 → `oscillation_detected = True`, rekomendacja: nowy model lub interwencja.

### Wzorzec 4: Version-inflation (semantic loop)
`_calculate_finding_similarity_score()` — to samo `finding_id` pojawia się 3+ razy → `finding_score = 1.0`.  
To samo znalezisko jest raportowane wielokrotnie bez rozwiązania — agent nie postępuje.

---

## 3. Progi interwencji

### Loop Score (0.0–1.0) — kompozytowy

```
score = 0.35 × iteration_score + 0.40 × finding_score + 0.25 × patch_score
```

| Próg              | Wartość | Status               |
|-------------------|---------|----------------------|
| WARNING_THRESHOLD | 0.45    | `LoopStatus.WARNING` |
| LOOP_THRESHOLD    | 0.70    | `LoopStatus.LOOP_DETECTED` |

### Hard limit iterations
`max_iterations` (default: **5**) → gdy `count >= max_iterations`: `LoopStatus.HARD_LIMIT` (pomijany scoring).

### Per-agent cost limits (konfigurowane w konstruktorze)
- `max_cost_usd_per_agent`: $5.00
- `max_cost_usd_per_file`: $2.00
- `max_time_sec_per_file`: 300s

**Uwaga:** `max_cost_usd_per_agent` i `max_cost_usd_per_file` są zadeklarowane w konstruktorze (L.351–353) i `_agent_stats`, ale **NIE są sprawdzane w `check_loop()`** — brak logiki egzekwowania tych limitów (patrz Finding L-002).

---

## 4. HumanGate escalation

Metoda `escalate_to_human()` (L.636–675) przy wykryciu `LOOP_DETECTED` lub `HARD_LIMIT`:

1. Generuje `LoopReport` z loop_score, oscillation_detected, semantic_loop_detected, repeated_findings
2. Wyświetla kolorowany prompt CLI (`_print_escalation_prompt`)
3. Czyta input użytkownika (`_read_human_choice`)
4. Obsługuje 4 opcje:

| Opcja | EscalationChoice     | Efekt                                           |
|-------|----------------------|-------------------------------------------------|
| a)    | `FORCE_CONTINUE`     | Dodaje (agent_id, file_path) do `_overridden` set |
| b)    | `SKIP`               | Pipeline pomija plik/znalezisko                  |
| c)    | `MANUAL_INTERVENE`   | Agent wstrzymany, człowiek naprawia ręcznie      |
| d)    | `ASSIGN_NEW_MODEL`   | Zadanie do nowego modelu                         |

**W środowisku nieinteraktywnym** (EOFError/KeyboardInterrupt) → domyślnie `SKIP`.

**Integracja z supervisor.py:** `escalate_to_human()` w LoopGuard jest *CLI-only* — nie wywołuje `supervisor.GateRequest`. `BudgetGuard` korzysta z `GateRequest`, ale `LoopGuard` nie (patrz Finding L-003).

---

## 5. Integracja z debug-loop-breaker skill

Brak bezpośredniego importu lub referencji do `debug-loop-breaker` w kodzie.  
`ContextPersistence.get_context_for_agent()` (L.967–1010) generuje kontekst wstrzykiwany do promptu agenta (patch history + stage summary), co jest mechanizmem wspierającym debug-loop-breaking, ale bez formalnej integracji z skill API. Orchestrator musi wywołać `get_context_for_agent()` ręcznie przed każdym wywołaniem agenta.

---

## 6. Nowości vs snapshot_0052

**BRAK różnic** — `diff snapshot_0052 latest` dla `loop_guard.py` zwraca pustą odpowiedź. Obie wersje są identyczne. Plik nie otrzymał żadnych zmian w ramach v5.9.1 Cluster R FinOps.

---

## 7. Findings

### L-001 — CRITICAL: `escalate_to_human()` blokuje na stdin — deadlock w CI/CD

**Severity:** CRITICAL  
**Lokalizacja:** `_read_human_choice()` L.703–720; `input()` call L.713

**Problem:** `escalate_to_human()` wywołuje `input()` — blokuje indefinitely w środowiskach bez terminala (CI/CD, Docker bez TTY, k8s pods). Fallback na `SKIP` przy EOFError jest poprawny dla nieinteraktywnych sesji, ale w środowiskach które wysyłają EOF natychmiast, *każda* eskalacja jest automatycznie pomijana bez wiedzy operatora. Audit pipeline może milcząco pominąć krytyczne pętle.

**Rekomendacja:** Dodać `non_interactive_default: EscalationChoice` parametr do `__init__` i `escalate_to_human()`. Logować jako WARNING gdy fallback jest używany. Integrować z supervisor `GateRequest` zamiast raw stdin.

**Patch sketch:**
```python
def __init__(self, ..., non_interactive_default: EscalationChoice = EscalationChoice.SKIP):
    self.non_interactive_default = non_interactive_default

def _read_human_choice(self) -> EscalationChoice:
    try:
        raw = input(...)
        ...
    except (EOFError, KeyboardInterrupt):
        logger.warning(
            "Non-interactive env — auto-selecting default: %s",
            self.non_interactive_default.value
        )
        return self.non_interactive_default
```

---

### L-002 — HIGH: max_cost_usd_per_agent i max_cost_usd_per_file nie są egzekwowane

**Severity:** HIGH  
**Lokalizacja:** Konstruktor L.351–353; `check_loop()` L.435–478

**Problem:** Pola `max_cost_usd_per_agent` ($5.00) i `max_cost_usd_per_file` ($2.00) są przechowywane ale **nigdy sprawdzane** w `check_loop()` ani `record_iteration()`. Jedynym mechanizmem kosztu jest `BudgetGuard` (globalny dzienny limit). Per-agent i per-file limity są martwym kodem — agent może wydać $100 na jeden plik bez interwencji LoopGuard.

**Rekomendacja:** Dodać sprawdzenie cost limits w `check_loop()`:
```python
# W check_loop():
agent_cost = self._agent_stats.get(agent_id, {}).get("total_cost_usd", 0.0)
if agent_cost >= self.max_cost_usd_per_agent:
    logger.warning("AGENT COST LIMIT — agent=%s cost=$%.4f", agent_id, agent_cost)
    return LoopStatus.HARD_LIMIT

file_cost = sum(r.cost_usd for r in records)
if file_cost >= self.max_cost_usd_per_file:
    return LoopStatus.HARD_LIMIT
```

---

### L-003 — HIGH: Eskalacja LoopGuard nie używa supervisor.GateRequest

**Severity:** HIGH  
**Lokalizacja:** `escalate_to_human()` L.636–675

**Problem:** `BudgetGuard._on_budget_exceeded()` poprawnie tworzy `supervisor.GateRequest` z `GateLevel.CRITICAL`. Natomiast `LoopGuard.escalate_to_human()` używa surowego `input()` zamiast `GateRequest`. Dwie safety layers używają różnych mechanizmów eskalacji — brak spójności. W środowisku produkcyjnym (bez terminala) HumanGate LoopGuard jest nieosiągalne.

**Rekomendacja:** Ujednolicić eskalację — `LoopGuard.escalate_to_human()` powinien tworzyć `GateRequest` (jak BudgetGuard) gdy dostępny supervisor, fallback do stdin.

---

### L-004 — HIGH: `_overridden` set nie jest persisted — utrata stanu po restarcie

**Severity:** HIGH  
**Lokalizacja:** `_overridden: set[tuple[str, str]]` L.372; brak serializacji

**Problem:** Po decyzji człowieka `FORCE_CONTINUE`, para `(agent_id, file_path)` jest dodawana do `_overridden` — ale ten set jest in-memory only. Po restarcie procesu (crash, deploy) LoopGuard ponownie eskaluje te same pary do człowieka, ignorując wcześniejsze decyzje. W długich pipeline'ach z wieloma restartami prowadzi to do wielokrotnych zbędnych eskalacji.

**Rekomendacja:** Persisted `_overridden` do JSON analogicznie jak `_records` (przez `_write_json`). Ładować przy inicjalizacji.

---

### L-005 — MEDIUM: Waga `finding_score` (0.40) wyższa niż `iteration_score` (0.35) — ryzyko false positives przy podobnych ID

**Severity:** MEDIUM  
**Lokalizacja:** `_calculate_loop_score()` L.508–512; `_calculate_finding_similarity_score()` L.515–545

**Problem:** Finding IDs porównywane są przez `SequenceMatcher` jako teksty — jeśli ID mają format `FIND-SEC-001`, `FIND-SEC-002`, similarity ratio wyniesie ~0.85 (tylko ostatnia cyfra różna). Dwa różne znaleziska mogą zostać sklasyfikowane jako "powtarzające się" przez fuzzy matching, generując false positive `LOOP_DETECTED` po zaledwie 2 iteracjach.

**Rekomendacja:** Fuzzy matching na finding ID powinien być wyłączony lub używać tylko exact matching. Semantic similarity powinna operować na `description`/`title`, nie na `finding_id`.

**Patch sketch:**
```python
# Zmiana w _calculate_finding_similarity_score():
# Usuń sekcję fuzzy matching (L.534-544)
# Zostaw tylko exact duplicate detection
if max_repeat >= 3:
    return 1.0
if max_repeat == 2:
    repeated_count = sum(1 for v in counts.values() if v >= 2)
    return min(0.6 + 0.1 * repeated_count, 1.0)
return 0.0  # Brak fuzzy matching dla ID
```

---

### L-006 — LOW: Brak maksymalnego rozmiaru `_records` — memory leak przy długich pipeline'ach

**Severity:** LOW  
**Lokalizacja:** `_records: dict[tuple[str, str], list[IterationRecord]]` L.363

**Problem:** `_records` i `_agent_stats` rosną nieograniczenie przez cały czas życia procesu. Przy pipeline obejmującym 10 000 plików i 5 iteracjach każdy = 50 000 `IterationRecord` w pamięci. Każdy rekord zawiera pełny `patch_diff` (może być kilka kB) → potencjalny OOM po kilku godzinach pracy.

**Rekomendacja:** Dodać opcjonalny `max_records_per_key: int = 20` — po przekroczeniu usuwaj najstarsze rekordy (sliding window). Alternatywnie: persisted storage z lazy loading.

---

## 8. Podsumowanie

| ID    | Severity | Obszar                                          | Status |
|-------|----------|-------------------------------------------------|--------|
| L-001 | CRITICAL | stdin deadlock w CI/CD przy escalate_to_human   | OPEN   |
| L-002 | HIGH     | Per-agent/per-file cost limits — martwy kod     | OPEN   |
| L-003 | HIGH     | Eskalacja bez GateRequest — niespójność         | OPEN   |
| L-004 | HIGH     | `_overridden` set nie persisted — utrata stanu  | OPEN   |
| L-005 | MEDIUM   | Fuzzy finding ID similarity — false positives   | OPEN   |
| L-006 | LOW      | Nieograniczony wzrost `_records` — memory leak  | OPEN   |

**Integracja z debug-loop-breaker:** Formalna integracja nieobecna — `ContextPersistence.get_context_for_agent()` dostarcza mechanizm, ale wymaga ręcznego wywołania przez orchestrator. Zalecane stworzenie adaptera łączącego skill API z `ContextPersistence`.

**Próg interwencji:** Po **5 iteracjach** (hard limit) lub gdy loop score ≥ 0.70. WARNING przy ≥ 0.45. Progi są konfigurowalne przez konstruktor, ale nie przez config.py ani env vars.
