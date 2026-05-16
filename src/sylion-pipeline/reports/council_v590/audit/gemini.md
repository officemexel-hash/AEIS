# SYLION v5.9.0 — Audit: Test Coverage Gaps
**Reviewer:** Gemini 3.1 Pro (brakujące testy, funkcje krytyczne bez pokrycia, property-based testing)  
**Date:** 2026-04-19  
**Scope:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/` — wszystkie *.py, `tests/`

---

## COV-001 — CRITICAL | `BudgetGuard.record_cost()` — brak testów dla codziennego cap i rotacji dnia

**Severity:** CRITICAL  
**Plik:linia:** `budget_guard.py:145–200` (`record_cost`, `_rotate_day`, `_on_budget_exceeded`)  
**Opis:**  
`BudgetGuard` jest krytycznym komponentem bezpieczeństwa finansowego — blokuje pipeline gdy dzienny koszt przekracza limit. Brak jakichkolwiek testów dla:
- `record_cost()` — dodanie kosztu i sprawdzenie czy cap jest egzekwowany
- `_rotate_day()` — czy dane z poprzedniego dnia są poprawnie archiwizowane
- `_on_budget_exceeded()` — czy Human Gate jest wywoływany z correct GateLevel.CRITICAL
- Atomowości zapisu stanu dziennego (`_save_daily_state()`)
- Race condition przy concurrent `record_cost()` z wielu wątków

**Property-based opportunity:**  
`hypothesis`: dla dowolnych sekwencji kosztów sumujących się do >cap, `record_cost()` musi zawsze wywołać `_on_budget_exceeded()` dokładnie raz i powinien być idempotentny przy kolejnych wywołaniach.  
**Fix proposal:**  
```python
# test_budget_guard.py
def test_daily_cap_triggers_halt():
    bg = BudgetGuard(daily_cap=10.0, ...)
    bg.record_cost(CostEntry("agent1", "stage2", 6.0, 10))
    bg.record_cost(CostEntry("agent2", "stage2", 5.0, 10))  # exceeds cap
    assert bg.is_exceeded() is True
    assert mock_human_gate.request_approval.called

@given(costs=st.lists(st.floats(min_value=0.01, max_value=100.0)))
def test_total_cost_monotonically_increases(costs):
    bg = BudgetGuard(daily_cap=float("inf"), ...)
    prev = 0.0
    for c in costs:
        bg.record_cost(CostEntry("a", "s", c, 1))
        assert bg.pipeline_cost >= prev
        prev = bg.pipeline_cost
```

---

## COV-002 — CRITICAL | `FileVerificationLayer` + `HallucinationGuard` — brak testów dla 6 typów halucynacji

**Severity:** CRITICAL  
**Plik:linia:** `file_verification.py:1–100` (Part 1), `HallucinationType` enum  
**Opis:**  
`file_verification.py` zawiera wbudowane testy (Part 3 — 17 testów), ale są one uruchamiane tylko przez `python file_verification.py --unit`, nie przez `pytest tests/`. W `tests/` brak dedykowanego pliku testowego dla file_verification. Krytyczne cases bez pokrycia w pytest:
- `NO_ACTUAL_CHANGE` — agent twierdzi że zmodyfikował plik, ale SHA jest identyczne
- `PHANTOM_FILE` — agent referuje plik który nie istnieje
- `UNEXPECTED_DELETION` — plik zniknął bez deklaracji `ClaimAction.DELETED`
- `UNEXPECTED_CREATION` — plik pojawił się bez deklaracji `ClaimAction.CREATED`
- `FILE_NOT_IN_SNAPSHOT` — plik modyfikowany poza deklarowanym scope

**Fix proposal:**  
Przenieść/zintegrować 17 wbudowanych testów do `tests/test_file_verification_v590.py` jako pytest cases. Dodać:
```python
def test_hallucination_no_actual_change(tmp_path):
    layer = FileVerificationLayer(repo_root=tmp_path)
    f = tmp_path / "target.py"
    f.write_text("original")
    snap = layer.snapshot([str(f)])
    # No modification
    claims = [AgentClaim(file="target.py", action=ClaimAction.MODIFIED)]
    result = layer.verify(snap, claims)
    assert result.verdict == Verdict.HALLUCINATION
    assert HallucinationType.NO_ACTUAL_CHANGE in result.hallucination_types
```

---

## COV-003 — HIGH | `LoopGuard.check_loop()` — brak testów dla wykrywania pętli semantycznych

**Severity:** HIGH  
**Plik:linia:** `loop_guard.py` (klasa `LoopGuard`, metoda `check_loop()`)  
**Opis:**  
`LoopGuard` wykrywa nieskończone pętle korekcji (agent łata → audytor odrzuca → agent łata ponownie). Brak testów dla:
- Wykrywania oscylacji (agent alternuje między dwoma wersjami pliku)
- Wykrywania semantic loop (agenci zgłaszają te same findings w kółko)
- `HARD_LIMIT` — co się stanie po przekroczeniu max_iterations
- `EscalationChoice` — czy prawidłowe opcje są prezentowane operatorowi
- Persystencji stanu między sesjami (`ContextPersistence`)

**Property-based opportunity:**  
`hypothesis`: dla N>max_iterations wywołań `record_iteration()` z identycznym `patch_diff` — `check_loop()` musi zawsze zwrócić `LoopStatus.LOOP_DETECTED`.  
**Fix proposal:**  
```python
def test_oscillation_detection():
    guard = LoopGuard(max_iterations=5)
    diff_a = "- old_code\n+ new_code"
    diff_b = "- new_code\n+ old_code"
    for i in range(3):
        guard.record_iteration(IterationRecord(..., patch_diff=diff_a if i%2==0 else diff_b))
    status = guard.check_loop("agent", "file.py")
    assert status.status in (LoopStatus.LOOP_DETECTED, LoopStatus.WARNING)
```

---

## COV-004 — HIGH | `ClaimProvenance.verify_claim()` — brak testów dla granicznych przypadków

**Severity:** HIGH  
**Plik:linia:** `claim_provenance.py:90–190` (`verify_claim`)  
**Opis:**  
Brak testów pytest (tylko inline examples w docstringu) dla:
- `FILE_MISSING` — plik nie istnieje
- `LINE_OOB` — numer linii poza zakresem (off-by-one: linia 0, linia > len)
- `VERIFIED` — wszystkie keywords znajdowane
- `WEAK` — plik istnieje ale keywords nie pasują
- `NO_EVIDENCE` — pusta lista keywords
- Case-sensitive vs case-insensitive matching
- Context window przy pierwszej i ostatniej linii (edge of file)

**Property-based opportunity:**  
`hypothesis`: dla dowolnego `line_number` poza `[1, len(lines)]`, wynik musi być zawsze `LINE_OOB`, nigdy crash.  
**Fix proposal:**  
```python
@given(line_number=st.integers())
def test_verify_claim_never_crashes_on_any_line(tmp_path, line_number):
    f = tmp_path / "code.py"
    f.write_text("line1\nline2\nline3\n")
    cp = ClaimProvenance(workspace=tmp_path)
    claim = ProvenanceClaim("id1", "agent", "code.py", line_number, ["line"])
    result = cp.verify_claim(claim)
    assert result.verdict in ProvenanceVerdict  # never crashes, always returns valid verdict
```

---

## COV-005 — HIGH | `AgentManager.validate_metadata()` — brak testów dla reguł walidacji §9.5

**Severity:** HIGH  
**Plik:linia:** `agent_manager.py:360–430` (`validate_metadata()`)  
**Opis:**  
Metoda `validate_metadata()` implementuje reguły bezpieczeństwa z §9.5 (overlapping allowed/forbidden actions, streaming agents bez book_refs, high-security bez human_gate). Brak dedykowanych testów dla każdej reguły. `tests/test_regressions_v588.py` nie pokrywa validate_metadata w ogóle.  
**Fix proposal:**  
```python
def test_validate_metadata_overlap_actions():
    mgr = AgentManager.__new__(AgentManager)
    mgr.agents = {"test_agent": AgentConfig(
        name="test_agent",
        allowed_actions=["deploy", "backup"],
        forbidden_actions=["deploy"],  # overlap!
        security_impact="high",
    )}
    issues = mgr.validate_metadata()
    assert any("overlapping" in i for i in issues)

def test_validate_metadata_streaming_without_book_refs():
    mgr = AgentManager.__new__(AgentManager)
    mgr.agents = {"stream_agent": AgentConfig(name="stream_agent", group="streaming", book_refs=[])}
    issues = mgr.validate_metadata()
    assert any("book_refs" in i for i in issues)
```

---

## COV-006 — HIGH | `ABRController` — brak testów dla state machine transitions

**Severity:** HIGH  
**Plik:linia:** `abr_controller.py:232+` (klasa `ABRController`)  
**Opis:**  
`ABRController` zarządza state machine (IDLE→RAMPING_UP→STABLE→CONGESTED→RAMPING_DOWN→THROTTLED). Brak jakichkolwiek testów dla przejść stanów, progów bitrate, czy reakcji na sygnały REMB/PLI/NACK. Kod jest krytyczny dla jakości streamingu (Pion D).  
**Property-based opportunity:**  
`hypothesis`: dla dowolnych wartości bandwidth w [min_bitrate, max_bitrate], `select_rung()` powinno zawsze zwracać indeks z zakresu `[0, len(ladder)-1]`.  
**Fix proposal:**  
```python
@given(bandwidth=st.floats(min_value=0, max_value=100_000))
def test_abr_select_rung_always_valid(bandwidth):
    ctrl = ABRController()
    estimate = NetworkEstimate(available_kbps=bandwidth, ...)
    decision = ctrl.update(estimate)
    assert 0 <= decision.new_rung < len(ctrl.ladder)
```

---

## COV-007 — MEDIUM | `HumanGate` — brak testów dla auto-approval i timeout behavior

**Severity:** MEDIUM  
**Plik:linia:** `supervisor.py:170+` (`HumanGate.request_approval()`)  
**Opis:**  
`HumanGate` jest jedyną warstwą bezpieczeństwa przed wykonaniem destruktywnych akcji. Brak testów dla:
- `auto_approve_info=True` — czy INFO level jest auto-approvowany bez interakcji
- CRITICAL level — czy `"YES"` jest wymagane, a jakikolwiek inny input jest odrzucany
- `timeout_seconds > 0` — czy timeout powoduje REJECTED
- `KeyboardInterrupt` handling — czy przerywa do REJECTED

**Fix proposal:**  
```python
def test_human_gate_auto_approves_info():
    gate = HumanGate(auto_approve_info=True)
    req = GateRequest(level=GateLevel.INFO, ...)
    result = gate.request_approval(req)
    assert result.decision == GateDecision.APPROVED
    assert "auto-approved" in result.human_notes

def test_human_gate_critical_requires_YES(monkeypatch):
    gate = HumanGate()
    monkeypatch.setattr("builtins.input", lambda _: "no")  # first NO
    req = GateRequest(level=GateLevel.CRITICAL, ...)
    # Should loop asking for YES/NO, not accept "no" as rejection on CRITICAL
```

---

## COV-008 — MEDIUM | `DashboardBridge` — brak integracyjnych testów dla fire-and-forget behavior

**Severity:** MEDIUM  
**Plik:linia:** `dashboard/bridge.py` (cała klasa `DashboardBridge`)  
**Opis:**  
`DashboardBridge` jest krytycznym łącznikiem pipeline ↔ dashboard. Brak testów sprawdzających:
- Czy metody rzeczywiście nie propagują wyjątków gdy DB jest down (`conn = None`)
- Czy `push_gate_request()` zwraca `None` gdy DB niedostępna (nie crasha pipeline)
- Czy `get_gate_decision()` poprawnie polluje i timeout

**Fix proposal:**  
```python
def test_bridge_fire_and_forget_on_db_unavailable():
    bridge = DashboardBridge()
    with patch("dashboard.bridge._get_conn", return_value=None):
        result = bridge.push_gate_request("action", "title")
        assert result is None  # nie crashuje

def test_bridge_update_agent_returns_gracefully_on_error():
    bridge = DashboardBridge()
    with patch("dashboard.bridge._get_conn") as mock_conn:
        mock_conn.return_value.execute.side_effect = sqlite3.Error("disk full")
        bridge.update_agent_status("agent1", "running")  # nie propaguje wyjątku
```

---

## COV-009 — MEDIUM | `init_db()` / `_migrate_columns()` — brak testów dla migracji schematu v0→v1

**Severity:** MEDIUM  
**Plik:linia:** `dashboard/db.py:785+` (`_run_migrations`, `_MIGRATIONS`)  
**Opis:**  
`tests/test_m02_m08_v590.py` testuje ogólny framework M-02, ale nie testuje konkretnej migracji v0→v1 (`_migrate_columns`). Brak testów dla:
- Bazy z `user_version=0` — czy migracja jest stosowana
- Bazy z `user_version=1` — czy migracja jest pomijana (idempotentność)
- Backupu przed migracją (M-08, ale ten test jest broken — BUG-002)
- Downgrade scenario — czy błąd jest zgłaszany

**Fix proposal:**  
Dodać testy integracyjne z prawdziwą bazą w pamięci sprawdzające PRAGMA user_version przed i po `init_db()`.

---

## COV-010 — LOW | `FactCheckerAgent` — brak jakichkolwiek testów

**Severity:** LOW  
**Plik:linia:** `fact_checker.py` (cały plik)  
**Opis:**  
`FactCheckerAgent` (Layer 5 anti-hallucination) nie ma ani jednego testu pytest. Plik `fact_checker.py` definiuje `FactCheckerAgent`, `FactCheckItem`, `FactCheckResult`, `FactCheckReport`. Brak mockowania odpowiedzi LLM, brak testów dla parsowania JSON verdict, brak testów dla `HALLUCINATION` vs `CONFIRMED` ścieżek.  
**Property-based opportunity:**  
`hypothesis`: parsowanie JSON response powinno nigdy nie crashować dla dowolnego stringa (nawet niepoprawnego JSON).  
**Fix proposal:**  
```python
@given(text=st.text())
def test_fact_checker_parse_never_crashes(text):
    agent = FactCheckerAgent(llm=MockLLM(response=text))
    result = agent._parse_verdict(text)
    assert result.verdict in FactCheckVerdict
```

---

*Zgłosił: Gemini 3.1 Pro (test coverage gaps)*
