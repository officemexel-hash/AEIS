# SYLION v5.9.0 — Audit: Architektura & Design Patterns
**Reviewer:** Claude Opus 4.7 (architecture, SOLID, circular imports, god objects)  
**Date:** 2026-04-19  
**Scope:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/` — wszystkie *.py

---

## ARC-001 — CRITICAL | orchestrator.py: God Object (3000+ linii, 30+ globalnych singletonów)

**Severity:** CRITICAL  
**Plik:linia:** `orchestrator.py:122–145`  
**Opis:**  
`orchestrator.py` zawiera ponad **3 300 linii** i definiuje **30 modułowych singletonów** jako moduł-level globals (`agent_mgr`, `supervisor`, `human_gate`, `safe_runner`, `loop_guard`, `ctx_persistence`, `iteration_tracker`, `gate_ux`, `consequence_desc`, `halluc_guard`, `file_layer`, `book_guardian`, `budget_guard`, `build_verifier`, `claim_prover`, `semantic_deduper`, `fact_checker`, `signaling_srv`, `device_harness`, `metrics_collector`, `abr_controller`, `input_protocol`, `audio_pipeline`, `stream_security`, `benchmark_harness`, `stream_monitor_inst`, `e2e_controller`, `dashboard_srv`). To naruszenie SRP (Single Responsibility Principle) i OCP (Open/Closed Principle). Plik jednocześnie inicjalizuje pipeline, orkiestruje 12 etapów, zarządza stanem, obsługuje błędy i raportuje wyniki.  
**Fix proposal:**  
Podzielić na co najmniej 4 moduły: `pipeline_init.py` (inicjalizacja globalnych singletonów), `pipeline_stages.py` (stage_1–stage_9), `pipeline_runner.py` (run_pipeline, main), `pipeline_cost.py` (cost reporting). Singletony przenieść do `PipelineContext` dataclass przekazywanej przez dependency injection zamiast mutable globals.

---

## ARC-002 — HIGH | orchestrator.py: Mutable Global State bez pełnej synchronizacji

**Severity:** HIGH  
**Plik:linia:** `orchestrator.py:118` (`_globals_lock = threading.Lock()`) + linie 122–145  
**Opis:**  
`_globals_lock` istnieje, ale większość funkcji korzysta z globalnych singletonów bez jego akwizycji. `is_agent_enabled()` (linia 524), `is_stage_enabled()` (linia 532) i `_report_cost_to_dashboard()` (linia 595) czytają `agent_mgr` i `budget_guard` bez locka. `run_in_executor` threads wywołują `save_signal()` bez synchronizacji. Przy równoległym uruchamianiu stage'ów (asyncio + executor) może dojść do data race.  
**Fix proposal:**  
Zamiast `_globals_lock` ochrony na poziomie modułu — enkapsulacja całego stanu w `PipelineContext` z `asyncio.Lock` (nie `threading.Lock`) per-kontekst. Alternatywnie: wszystkie funkcje pomocnicze powinny otrzymywać kontekst jako argument, nie sięgać do globals.

---

## ARC-003 — HIGH | Circular Import Risk: orchestrator ↔ supervisor ↔ human_gate_ux

**Severity:** HIGH  
**Plik:linia:** `orchestrator.py:67–97`, `supervisor.py`, `human_gate_ux.py`  
**Opis:**  
`orchestrator.py` importuje z 20+ modułów na poziomie modułu (w tym `supervisor`, `loop_guard`, `human_gate_ux`, `file_verification`, `book_guardian`, `budget_guard`). Żaden z tych modułów nie importuje bezpośrednio z `orchestrator`, ale współdzielą typy (np. `GateRequest`, `GateLevel`) z `supervisor.py` importowanym przez wiele innych modułów. Jeśli ktoś doda choćby jeden `from orchestrator import X` w dowolnym z tych modułów — nastąpi import cycle crash.  
**Fix proposal:**  
Wyodrębnić typy wspólne (`GateRequest`, `GateLevel`, `GateDecision`, `LoopStatus` itp.) do dedykowanego modułu `types.py` / `pipeline_types.py`. Orchestrator importowałby z `types.py`, a wszystkie implementacje (supervisor, loop_guard) też. To standardowy wzorzec zapobiegający cyklom w dużych Pythonowych projektach.

---

## ARC-004 — HIGH | AgentManager: SRP Violation (zarządzanie konfiguracją + runtime + display + validation)

**Severity:** HIGH  
**Plik:linia:** `agent_manager.py:35` (klasa `AgentManager`)  
**Opis:**  
`AgentManager` (klasa) odpowiada za: (1) ładowanie i zapis YAML, (2) runtime state (mark_running/mark_completed/mark_failed), (3) grupowanie i filtrowanie agentów, (4) walidację konfiguracji + metadanych, (5) pośrednie zapewnienie formatowania (kolor, ikon) przez `print_status`. Klasa ma 35 metod. Łamie SRP — zmiana reprezentacji stanu runtime zmusza do modyfikacji tej samej klasy co logika walidacji.  
**Fix proposal:**  
Rozbić na: `AgentConfigLoader` (YAML I/O), `AgentStateTracker` (mark_running/completed/failed/save_state), `AgentRegistry` (queries: get_enabled_agents, get_groups), `AgentConfigValidator` (validate, validate_metadata). `AgentManager` pozostaje fasadą delegującą.

---

## ARC-005 — HIGH | ai_review.py: Dead Code — `apply_auto_patches` zawsze ustawia MANUAL_REQUIRED

**Severity:** HIGH  
**Plik:linia:** `ai_review.py:700–735` (funkcja `apply_auto_patches`)  
**Opis:**  
Funkcja `apply_auto_patches()` w komentarzu deklaruje, że auto-patch jest wyłączony i zawsze ustawia `status = "MANUAL_REQUIRED"`. Mimo to, w `run_review()` (linia ~780) wywoływana jest ta funkcja, a wywołujące code paths zachowują się jakby patche były aplikowane (logują "Applied N auto-patches"). Jest to mylące — interfejs sugeruje działanie, które w rzeczywistości nie zachodzi. `auto_fixable` w `Finding` jest nigdy nie truthy bo `_verify_private_attrs` jawnie ustawia `f.auto_fixable = False` dla wszystkich znalezionych bugów.  
**Fix proposal:**  
Usunąć `apply_auto_patches()` lub jawnie nazwać ją `report_pending_patches()`. Usunąć pole `auto_fixable` z `Finding` jeśli nie jest używane, lub całkowicie wdrożyć mechanizm auto-patch (z odpowiednimi testami) albo definitywnie wyłączyć przez usunięcie dead code.

---

## ARC-006 — MEDIUM | config.py: _read_db_config exception swallowing maskuje błędy DB

**Severity:** MEDIUM  
**Plik:linia:** `config.py:44`, `config.py:69`, `config.py:84`, `config.py:118`  
**Opis:**  
Cztery funkcje (`_read_db_config`, `_read_db_api_key`, `get_enabled_models_from_db`, i inne) łapią `except Exception: return default` bez jakiegokolwiek logowania. Jeśli baza danych jest uszkodzona lub nieosiągalna z innego powodu niż "nie istnieje", błąd jest milcząco ignorowany. Konfiguracja wraca do wartości domyślnych (pustych kluczy API), co może być trudne do debugowania.  
**Fix proposal:**  
Zmienić na `except Exception as e: logger.debug("DB config unavailable: %s", e); return default`. Dodać minimum jeden `logger = logging.getLogger("config")` na poziomie modułu.

---

## ARC-007 — MEDIUM | Brak fasady — DashboardBridge importuje bezpośrednio z dashboard.db naruszając warstwowość

**Severity:** MEDIUM  
**Plik:linia:** `dashboard/bridge.py:16` (`from dashboard.db import get_conn, init_db`)  
**Opis:**  
`DashboardBridge` w pipeline-side code importuje bezpośrednio z `dashboard.db` (warstwę storage). Brak interfejsu/fasady. To tworzy bezpośrednie coupling między pipeline a implementacją storage, utrudniając testy (muszą inicjalizować całą DB), podmianę backendu (np. PostgreSQL) i izolację. `_get_conn()` w bridge.py zarządza własnym stanem `_db_initialized` powielając logikę z `db.py:_db_init_lock`.  
**Fix proposal:**  
Zdefiniować protokół/interfejs `DashboardStore(Protocol)` z metodami `push_gate_request`, `get_gate_decision`, `update_agent_status` itp. `DashboardBridge` powinien przyjmować tę abstrakcję w konstruktorze (dependency injection), zamiast tworzyć połączenia SQL bezpośrednio.

---

## ARC-008 — MEDIUM | orchestrator.py: `run_single_agent` (770 linii od linii 770) — naruszenie SRP w funkcji

**Severity:** MEDIUM  
**Plik:linia:** `orchestrator.py:770` (funkcja `run_single_agent`)  
**Opis:**  
Funkcja `run_single_agent` jest de facto mini-orkiestratorem zawierającym: inicjalizację agenta, wykonanie z retry, obsługę Human Gate, weryfikację plików (HallucinationGuard), zapis kosztów do BudgetGuard i LoopGuard, raportowanie do dashboard. Szacunkowo 200+ linii w jednej funkcji. Narusza SRP — zmiana w jednym aspekcie (np. retry policy) wymaga edycji tej samej funkcji co logika cost reporting.  
**Fix proposal:**  
Rozbić na: `_prepare_agent_context(...)`, `_execute_with_gate(...)`, `_verify_agent_output(...)`, `_record_agent_metrics(...)`. `run_single_agent` pozostaje cienką fasadą wywołującą te kroki sekwencyjnie.

---

## ARC-009 — LOW | loop_guard.py i supervisor.py definiują identyczną klasę `C` (ANSI colors)

**Severity:** LOW  
**Plik:linia:** `loop_guard.py:23–36`, `supervisor.py:14–27`  
**Opis:**  
Klasa `C` z ANSI color constants jest duplikowana w co najmniej 2 plikach (loop_guard.py, supervisor.py, agent_manager.py — prawdopodobnie więcej). Narusza DRY (Don't Repeat Yourself). Dodanie nowego koloru wymaga zmiany w N plikach.  
**Fix proposal:**  
Przenieść `class C` do `utils/colors.py` i importować `from utils.colors import C` wszędzie.

---

## ARC-010 — LOW | models.py: MODEL_REGISTRY jako mutable module-level dict — brak enkapsulacji

**Severity:** LOW  
**Plik:linia:** `models.py:90` (`MODEL_REGISTRY: dict[str, ModelDef] = {}`)  
**Opis:**  
`MODEL_REGISTRY` jest publicznym mutable dict na poziomie modułu. Każdy może mutować go przez `MODEL_REGISTRY["x"] = ...` lub `del MODEL_REGISTRY["x"]` bez żadnej ochrony. W wielowątkowym środowisku (uvicorn, executor threads) może dojść do partial reads podczas modyfikacji. Funkcja `_register()` nie jest thread-safe (brak locka).  
**Fix proposal:**  
Enkapsulować w klasie `ModelRegistry` z metodami `register()`, `get()`, `list_all()` chroniącymi dostęp `threading.RLock`. Eksponować singleton `REGISTRY` jako obiekt niemodyfikowalny z zewnątrz.

---

*Zgłosił: Claude Opus 4.7 (architektura i design patterns)*
