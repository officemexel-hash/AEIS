# SYLION v5.9.0 — Audit: Type Safety
**Reviewer:** GPT-5.4 (type hints coverage, Pydantic models, missing Optional markers, Any abuses)  
**Date:** 2026-04-19  
**Scope:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/` — wszystkie *.py

---

## TYPE-001 — HIGH | orchestrator.py: 20+ globalnych singletonów typowanych jako `X | None` bez runtime guard

**Severity:** HIGH  
**Plik:linia:** `orchestrator.py:122–145`  
**Opis:**  
Wszystkie globalne singletony (`agent_mgr: AgentManager | None = None`, `supervisor: SupervisorAgent | None = None`, itp.) są typowane jako `T | None` ale są używane w wielu miejscach bez `if X is None: raise` guard. Przykład: `is_agent_enabled(name)` (linia 524) zawiera `if agent_mgr is None: return False` — to poprawne. Ale wiele wywołań w `run_single_agent`, `stage_2_audit` itp. używa `agent_mgr.agents[...]` bezpośrednio bez sprawdzenia None-ness. Mypy wykryłby te jako `error: Item "None" of "AgentManager | None" has no attribute "agents"`.  
**Fix proposal:**  
Zdefiniować helper `_require(x: T | None, name: str) -> T: if x is None: raise RuntimeError(f"{name} not initialized"); return x`. Używać: `mgr = _require(agent_mgr, "agent_mgr")`. Alternatywnie: zastosować `assert agent_mgr is not None` na początku każdej funkcji, co type-checker zrozumie jako type narrowing.

---

## TYPE-002 — HIGH | agent_manager.py: `AgentConfig.params: dict[str, Any]` — Any abuse w kluczowym modelu

**Severity:** HIGH  
**Plik:linia:** `agent_manager.py:97` (`params: dict[str, Any] = field(default_factory=dict)`)  
**Opis:**  
`params` jest typowane jako `dict[str, Any]`, co eliminuje wszelką type safety dla parametrów agentów. Parametry takie jak `bts_mode`, `faraday_required`, `human_gate.timeout`, `human_gate.auto_approve_safe` są odczytywane przez `params.get("bts_mode", "zmq")` itp. — bez gwarancji typu. Typo w kluczu lub zły typ wartości nie będzie wykryty przez type checker. `multi_verify: dict[str, Any] | None` i `online_search: dict[str, Any] | None` mają ten sam problem.  
**Fix proposal:**  
Zdefiniować typed Pydantic/dataclass modele dla znanych grup parametrów:
```python
@dataclass
class HumanGateParams:
    timeout: int = 300
    auto_approve_safe: bool = False

@dataclass  
class RFRedTeamParams:
    bts_mode: Literal["zmq", "rf"] = "zmq"
    faraday_required: bool = True
```
Zmienić `params: dict[str, Any]` na `params: AgentParams` gdzie `AgentParams` jest Union typed lub TypedDict.

---

## TYPE-003 — HIGH | ai_review.py: `ReviewReport.findings: list` bez parametru typu

**Severity:** HIGH  
**Plik:linia:** `ai_review.py:188` (`findings: list = field(default_factory=list)`)  
**Opis:**  
`findings` jest typowany jako raw `list` bez parametru generycznego. Powinno być `list[Finding]`. W konsekwencji `for f in report.findings:` w `synthesize_reviews()` nie ma type safety — mypy nie sprawdza, czy elementy mają atrybuty `.severity`, `.file`, `.title` etc. `ReviewSynthesis.reports: list`, `agreed_findings: list`, `disputed_findings: list`, `auto_patches: list`, `human_gate_items: list` — wszystkie bez typów.  
**Fix proposal:**  
```python
findings: list[Finding] = field(default_factory=list)
# ReviewSynthesis:
reports: list[ReviewReport] = field(...)
agreed_findings: list[Finding] = field(...)
disputed_findings: list[Finding] = field(...)
auto_patches: list[dict[str, Any]] = field(...)
human_gate_items: list[dict[str, Any]] = field(...)
```

---

## TYPE-004 — HIGH | models.py: `MODEL_REGISTRY: dict[str, ModelDef]` — brak Pydantic walidacji przy rejestracji

**Severity:** HIGH  
**Plik:linia:** `models.py:90`, `models.py:100` (`_register()`)  
**Opis:**  
`ModelDef` jest zwykłym `@dataclass` bez walidacji. Pola takie jak `cost_per_1m_input: float = 0.0`, `rate_limit_rpm: int = 60` mogą otrzymać wartości ujemne lub None bez żadnego błędu. `_register()` po prostu przypisuje do dict. Brak sprawdzenia unikalności `id`, brak walidacji `api_key_env` (czy to sensowna nazwa zmiennej env). `ModelDef.capabilities: list[Capability]` może być pustą listą co może prowadzić do błędów w `get_model_for_capability()`.  
**Fix proposal:**  
Przekonwertować `ModelDef` na Pydantic `BaseModel` z walidatorami:
```python
class ModelDef(BaseModel):
    cost_per_1m_input: float = Field(ge=0.0)
    rate_limit_rpm: int = Field(gt=0)
    capabilities: list[Capability] = Field(min_length=1)
    
    @field_validator("api_key_env")
    @classmethod
    def validate_env_var(cls, v: str) -> str:
        if not v.isupper() or not v.replace("_", "").isalnum():
            raise ValueError(f"api_key_env must be UPPER_SNAKE_CASE: {v!r}")
        return v
```

---

## TYPE-005 — MEDIUM | agent_manager.py: `AgentConfig` — brak `Optional` dla pól z `None` default

**Severity:** MEDIUM  
**Plik:linia:** `agent_manager.py:68–100` (dataclass `AgentConfig`)  
**Opis:**  
`AgentConfig` używa nowoczesnej składni `X | None` dla niektórych pól (np. `group: str | None = None`), ale inne pola z `None` default jak `declared_files: list[str] | None = None`, `fallback_model: str | None = None`, `multi_verify: dict[str, Any] | None = None` mają poprawne adnotacje. Jednak `started_at: str | None = None`, `completed_at: str | None = None`, `error: str | None = None`, `result_path: str | None = None` — te pola runtime-state mogłyby być silniej typowane (np. `started_at: datetime | None = None` zamiast stringa). Używanie `str` dla datetime obniża type safety.  
**Fix proposal:**  
Zmienić `started_at: str | None` → `started_at: datetime | None`. Analogicznie dla `completed_at`. Zapis do JSON używa `.isoformat()` — to nadal proste.

---

## TYPE-006 — MEDIUM | dashboard/app.py: Pydantic modele bez pełnej walidacji — brak `Field` constraints

**Severity:** MEDIUM  
**Plik:linia:** `dashboard/app.py:180+` (klasy Pydantic `ConfigUpdate`, `LoginRequest`, itp.)  
**Opis:**  
`ConfigUpdate(BaseModel)` zawiera jedynie `value: str` bez żadnych ograniczeń długości, formatu czy zawartości. Endpoint `PUT /api/config/{key}` przyjmuje dowolnie długą wartość. `LoginRequest` — `password: str` bez `min_length`. Brak walidacji `Field(min_length=..., max_length=...)` na polach wejściowych. Potencjalne wektory DoS przez duże payloady.  
**Fix proposal:**  
```python
class ConfigUpdate(BaseModel):
    value: str = Field(max_length=4096)

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)
```

---

## TYPE-007 — MEDIUM | config.py: `get_enabled_models_from_db() -> list[dict] | None` — nieprecyzyjny typ zwracany

**Severity:** MEDIUM  
**Plik:linia:** `config.py:84` (`get_enabled_models_from_db()`)  
**Opis:**  
Funkcja zwraca `list[dict] | None`. Użytkownicy muszą sprawdzać `if result is not None` i następnie iterować po `dict` z nieznanymi kluczami. Brak `TypedDict` dla struktury row z DB (`provider`, `priority`, `enabled`, itp.). Każde miejsce używające tej funkcji musi zgadywać klucze słownika.  
**Fix proposal:**  
```python
class ModelRegistryRow(TypedDict):
    id: str
    provider: str
    priority: int
    enabled: int
    model_id: str
    api_key_env: str

def get_enabled_models_from_db() -> list[ModelRegistryRow] | None: ...
```

---

## TYPE-008 — MEDIUM | loop_guard.py: `IterationRecord.finding_id: str | None` — Optional ale używany jako str

**Severity:** MEDIUM  
**Plik:linia:** `loop_guard.py:69` (`finding_id: str | None`)  
**Opis:**  
`finding_id` jest `str | None`, ale w `LoopReport.repeated_findings: list[str]` i w `check_loop()` (gdzie finding_ids są porównywane) używany jest jakby zawsze był `str`. Bez type narrowing przed użyciem może dojść do `TypeError: '<' not supported between instances of 'NoneType' and 'str'` przy sortowaniu lub `set()` operacjach.  
**Fix proposal:**  
Dodać guard: `if record.finding_id is not None: repeated_findings.append(record.finding_id)`. Lub zdefiniować `finding_id: str = ""` jako pusty string zamiast None, jeśli puste ID jest semantycznie akceptowalne.

---

## TYPE-009 — LOW | claim_provenance.py: `ProvenanceClaim.keywords: list[str]` — brak walidacji pustej listy

**Severity:** LOW  
**Plik:linia:** `claim_provenance.py:75` + `verify_claim:130`  
**Opis:**  
`verify_claim()` sprawdza `if not claim.keywords: return NO_EVIDENCE`. Ale nic nie zabrania przekazania `keywords=[""]` (lista z pustym stringiem), co przejdzie przez guard i spróbuje dopasować pusty pattern w `context_text`. `re.search("", text)` zawsze zwraca truthy — prowadząc do fałszywego `VERIFIED` z `match_ratio=1.0`.  
**Fix proposal:**  
```python
clean_keywords = [k.strip() for k in claim.keywords if k.strip()]
if not clean_keywords:
    result.verdict = ProvenanceVerdict.NO_EVIDENCE
    return result
```

---

## TYPE-010 — LOW | agent_manager.py: `apply_profile` — `_set_nested` niepotrzebnie rekurencyjne, niejasny typ

**Severity:** LOW  
**Plik:linia:** `agent_manager.py:305–314` (`apply_profile` + `_set_nested`)  
**Opis:**  
`apply_profile()` parsuje `key.split(".")` i wywołuje `_set_nested(self.global_config, parts[1:] + [attr], value)` — ale logika jest niespójna: dla `len(parts) == 2` i `parts[0] == "global"` wywołuje `_set_nested(self.global_config, parts[1:] + [attr], value)` co dodaje `attr` dwa razy do ścieżki. Typ zwracany `_set_nested` to `None` ale jest używany jak by coś zwracał. `d: dict` bez parametru generycznego.  
**Fix proposal:**  
Przepisać `apply_profile` z jasną logiką parsowania klucza i dodać testy jednostkowe dla różnych formatów kluczy. Typować: `def _set_nested(d: dict[str, Any], keys: list[str], value: Any) -> None:`.

---

*Zgłosił: GPT-5.4 (type safety)*
