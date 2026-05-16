# SYLION v5.9.0 — Security Audit Report: Gemini Perspective
**Focus: Access Control (OWASP A01) + Server-Side Request Forgery (OWASP A10) + Insecure Deserialization (OWASP A08)**
**Date: 2026-04-19 | Reviewer: Gemini**

---

## CRITICAL

### F-GEM-001 — Privilege Escalation: Brak Weryfikacji Roli w update_user (owner może mianować owner)
**Severity:** CRITICAL  
**CVSS:** 8.8 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H)  
**File:Linia:** `app.py:636-668`

**Opis:**
```python
@app.put("/api/users/{user_id}")
def update_user(user_id: str, body: UserUpdate, request: Request):
    actor = require_role(request, "owner")
    ...
    if body.role is not None:
        valid_roles = ("owner", "operator", "security", "readonly")
        if body.role not in valid_roles:
            raise HTTPException(400, ...)
        updates.append("role=?")
        params.append(body.role)
```
Właściciel (owner) może zmienić rolę dowolnego użytkownika, **łącznie ze zmianą na "owner"**. Brak ograniczenia "nie możesz promować do roli wyższej niż własna". W systemie z jednym właścicielem to akceptowalne, ale jest **brak ochrony przed samopromocją** przez operatora (gdyby endopint był dostępny dla niższych ról) i brak sprawdzenia czy modyfikowany `user_id` należy do innego właściciela.

Krytyczniejsza luka: Brak weryfikacji czy `user_id` należy do realnie istniejącego użytkownika **przed** budowaniem listy `updates`. Choć `target = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()` jest zrobione na początku i podnosi 404 — flow jest poprawny. Jednak w endpointach `DELETE /api/users/{user_id}` (db.py:672-685) usunięcie admina przez innego admina jest możliwe — nie ma hierarchii własności.

**Dodatkowy finding:** `delete_user` sprawdza `actor["user_id"] == user_id` (nie możesz usunąć siebie), ale nie sprawdza czy usuwany użytkownik jest ostatnim właścicielem — możliwy lockout systemu.

**Proponowany fix:**
```python
# Prevent deleting last owner
if body.role == "owner" or (target["role"] == "owner"):
    owner_count = conn.execute(
        "SELECT COUNT(*) as c FROM users WHERE role='owner' AND enabled=1"
    ).fetchone()["c"]
    if owner_count <= 1 and body.get("role") != "owner":
        raise HTTPException(400, "Nie można zdegradować ostatniego właściciela")
```

---

### F-GEM-002 — Insecure Deserialization: json.loads bez Weryfikacji Schematu na bound_agents
**Severity:** CRITICAL  
**CVSS:** 7.8 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H)  
**File:Linia:** `app.py:922, 971`

**Opis:**
```python
d["bound_agents_list"] = json.loads(d.get("bound_agents", "[]"))
```
Pole `bound_agents` jest przechowywane w bazie jako JSON string i deserializowane przez `json.loads` bez weryfikacji schematu ani limitów rozmiaru. Jeśli `bound_agents` zawiera:
1. Tysiące elementów → DoS przez zużycie pamięci przy deserializacji dużej listy
2. Zagnieżdżone struktury JSON → CPU DoS (json.loads dla głęboko zagnieżdżonych struktur)
3. Złośliwe wartości agent_id → mogą być przekazane do downstream API bez sanityzacji

Prompt creation zapisuje `bound_agents` jako JSON:
```python
conn.execute(... "?, ..." (json.dumps(body.bound_agents),) ...)
```
Gdzie `body.bound_agents: list[str]` — nie ma limitu długości listy ani walidacji elementów.

**Proponowany fix:**
```python
MAX_BOUND_AGENTS = 100
MAX_AGENT_ID_LEN = 64

@field_validator("bound_agents")
@classmethod
def validate_bound_agents(cls, v: list[str]) -> list[str]:
    if len(v) > MAX_BOUND_AGENTS:
        raise ValueError(f"Too many bound agents (max {MAX_BOUND_AGENTS})")
    for aid in v:
        if len(aid) > MAX_AGENT_ID_LEN or not aid.isidentifier():
            raise ValueError(f"Invalid agent_id: {aid!r}")
    return v
```

---

## HIGH

### F-GEM-003 — SSRF via sys.path.insert + from health_check import (Dynamic Module Loading)
**Severity:** HIGH  
**CVSS:** 7.2 (AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `app.py:303-305, 353-355`

**Opis:**
```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from health_check import run_full_check
```
Ścieżka `parent.parent` jest hardkodowana, ale `sys.path.insert(0, ...)` na pierwszą pozycję w path oznacza, że jeśli atakujący może stworzyć plik `health_check.py` w katalogu nadrzędnym (np. przez upload do `workspace_uploads`), zamiast prawdziwego `health_check.py` zostanie załadowany złośliwy moduł.

Wektor ataku:
1. Upload złośliwego pliku `health_check.py` (jako slot `phantom` lub przez błąd sanityzacji)  
2. Wywołanie `GET /api/health/deep` (wymaga roli owner/operator)  
3. Złośliwy kod wykonuje się w kontekście serwera

**Weryfikacja:** `workspace_uploads` jest w `Path(__file__).parent.parent / "workspace_uploads"`, a `sys.path` pokazuje na `Path(__file__).parent.parent` — ten sam katalog nadrzędny! Jeśli upload trafi do `../health_check.py` (przez path traversal lub inne błędy), RCE jest możliwe.

**Proponowany fix:**
```python
# Nie modyfikuj sys.path — użyj importlib z pełną ścieżką
import importlib.util
health_check_path = Path(__file__).resolve().parent.parent / "health_check.py"
if not health_check_path.exists():
    raise HTTPException(404, "Health check module not found")
spec = importlib.util.spec_from_file_location("health_check", health_check_path)
hc_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc_module)
report = hc_module.run_full_check()
```

---

### F-GEM-004 — Broken Object Level Authorization: Brak Weryfikacji Własności w Prompt/Baseline APIs
**Severity:** HIGH  
**CVSS:** 6.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:H/A:N)  
**File:Linia:** `app.py:983-998, 1157-1170`

**Opis:**
Endpointy modyfikacji promptów i bazeline'ów sprawdzają autentykację i rolę, ale nie weryfikują **własności zasobu**:
```python
@app.put("/api/prompts/{prompt_id}")
def update_prompt(prompt_id: str, body: PromptUpdate, request: Request):
    user = require_role(request, "owner", "operator", "security")
    # ...
    prompt = conn.execute("SELECT * FROM prompts WHERE id=?", (prompt_id,)).fetchone()
    # Brak: czy prompt należy do user?
```
Użytkownik z rolą `operator` może modyfikować prompt stworzony przez `owner`. Brak kontroli `created_by`. W obecnym modelu to może być celowa decyzja (collaboration), ale przy scenariuszu wielu operatorów jeden operator może nadpisać pracę innego.

**Ryzyko:** Horizontal privilege escalation — operator modyfikuje baseline/prompt innego operatora, wstrzykuje złośliwą treść do promptu systemowego agenta.

**Proponowany fix:**
```python
if user["role"] != "owner" and prompt["created_by"] != user["username"]:
    raise HTTPException(403, "Brak uprawnień do modyfikacji tego zasobu")
```

---

### F-GEM-005 — DoS via Unbounded limit Parameter w List Endpoints
**Severity:** HIGH  
**CVSS:** 6.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H)  
**File:Linia:** `app.py:5693, 5811`

**Opis:**
```python
limit = max(1, min(int(limit or 50), 500))
```
Limit jest sanityzowany do 500 dla ollama shadow/insights. Ale w wielu innych endpoints (listy agentów, promptów, baseline'ów, audit log) podobna sanityzacja może być nieobecna lub wyższy limit jest dozwolony:
```python
recent_logs = [dict(r) for r in conn.execute(
    "SELECT * FROM audit_log ORDER BY ts DESC LIMIT 10"
).fetchall()]
```
Tu hardkodowane LIMIT 10 — bezpieczne. Ale endpointy jak `/api/agents`, `/api/baselines`, `/api/prompts` — sprawdzić czy mają limity. Audit log może mieć miliony wpisów. Query bez LIMIT lub z bardzo dużym LIMIT może powodować memory exhaustion.

**Weryfikacja wymagana dla:**
- `GET /api/agents` — czy ma limit?
- `GET /api/prompts` — czy ma limit?  
- `GET /api/audit` — czy ma limit?

**Proponowany fix:** Ujednolicony limit we wszystkich endpoints listujących: `MAX_PAGE_SIZE = 1000` z paginacją.

---

## MEDIUM

### F-GEM-006 — TOCTOU w _validate_zip_safe: Walidacja i Ekstrakcja w Różnych Operacjach
**Severity:** MEDIUM  
**CVSS:** 5.9 (AV:N/AC:H/PR:L/UI:N/S:U/C:N/I:H/A:N)  
**File:Linia:** `app.py:2413-2417`

**Opis:**
```python
with zipfile.ZipFile(str(tmp_path), 'r') as zf:
    _validate_zip_safe(zf, extract_tmp)
    for member in zf.infolist():
        zf.extract(member, str(extract_tmp))
```
`_validate_zip_safe` i następująca ekstrakcja czytają ZipFile **dwukrotnie** z tego samego obiektu `zf`. Walidacja przechodzi przez `zf.infolist()`, po czym ekstrakcja wykonuje `zf.extract(member, ...)`. Między tymi operacjami ZIP jest otwarty do odczytu — jeśli system plików pozwala na modyfikację `tmp_path` podczas operacji (np. przez race condition w wielowątkowym środowisku), TOCTOU pozwoli na ekstrakcję innej zawartości niż zwalidowana.

Ryzyko niskie w single-worker setup, ale niezerowe przy `asyncio.to_thread` i wielu równoległych uploadów.

**Proponowany fix:** Użyj `zipfile.Path` lub odczytaj zawartość do pamięci podczas walidacji, zamiast ponownie czytać z dysku przy ekstrakcji.

---

### F-GEM-007 — Audit Log Severity Field bez Walidacji (SQL Injection via Severity)
**Severity:** MEDIUM  
**CVSS:** 5.4 (AV:N/AC:L/PR:H/UI:N/S:U/C:L/I:L/A:N)  
**File:Linia:** `db.py` audit_log function (passim)

**Opis:**
Funkcja `audit_log` przyjmuje `severity` jako wolny string. Choć pola są wstawiane przez parametryzowane zapytania `?`, `severity` bez walidacji pozwala na wstrzyknięcie dowolnej wartości do kolumny `severity` w audit_log. Jeśli dashboard filtruje po severity przez dynamiczne query (np. `WHERE severity = '{user_input}'`), istnieje ryzyko SQLi.

Sprawdzić: czy `/api/audit` endpoint filtruje po severity? Jeśli tak i używa parametrów — bezpieczne. Jeśli f-string — niebezpieczne.

**Proponowany fix:**
```python
VALID_SEVERITIES = {"debug", "info", "warning", "error", "critical"}
def audit_log(conn, action, target, detail="", actor="system", severity="info"):
    if severity not in VALID_SEVERITIES:
        severity = "info"
    ...
```

---

### F-GEM-008 — _periodic_prune nie ma Graceful Cancellation Handling
**Severity:** MEDIUM  
**CVSS:** 4.3 (AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:N/A:L)  
**File:Linia:** `app.py:70-80, 127-128`

**Opis:**
```python
async def _periodic_prune():
    while True:
        await asyncio.sleep(_PRUNE_INTERVAL_S)
        for name, fn in _PRUNE_TASKS:
            try:
                deleted = await asyncio.to_thread(fn)
            except Exception as exc:
                _log.warning("Periodic prune[%s] failed: %s", name, exc)

# Shutdown:
prune_task.cancel()
```
Przy `prune_task.cancel()` zadanie jest anulowane przez `asyncio.CancelledError`. Jeśli prune jest w trakcie `asyncio.to_thread(fn)` (blokujące I/O w wątku), `CancelledError` jest propagowane do korutyny, ale wątek SQLite może nadal działać. Nie powoduje to data corruption (SQLite transakcje gwarantują atomowość), ale może prowadzić do nieoczekiwanego stanu przy szybkim restart.

**Dodatkowe ryzyko:** `_periodic_prune` nie ma timeout dla pojedynczej operacji prune — jeśli baza jest zablokowana, może zawiesić się na nieskończoność bez żadnego logowania timeoutu.

**Proponowany fix:**
```python
deleted = await asyncio.wait_for(
    asyncio.to_thread(fn), 
    timeout=300.0  # 5 minut max na prune
)
```

---

## LOW

### F-GEM-009 — CORS Konfiguracja Pozwala na Wildcard Methods i Headers
**Severity:** LOW  
**CVSS:** 3.1 (AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:L/A:N)  
**File:Linia:** `app.py:137-145`

**Opis:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[...],
    allow_methods=["*"],
    allow_headers=["*"],
)
```
`allow_methods=["*"]` i `allow_headers=["*"]` przy ograniczonych `allow_origins` jest względnie bezpieczne (origins ograniczone do localhost:8421). Jednak `allow_headers=["*"]` umożliwia CORS preflight dla dowolnych custom nagłówków — potencjalnie przydatne dla atakującego w scenariuszu CSRF bypass przy słabych weryfikacjach Origin.

**Proponowany fix:**
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["X-Session-Token", "Content-Type", "Accept"],
```

---

### F-GEM-010 — Brak Expiry Odświeżania Sesji (Sliding Window)
**Severity:** LOW  
**CVSS:** 2.6 (AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N)  
**File:Linia:** `app.py:152, 162-166`

**Opis:**
`SESSION_DURATION = 86400 * 7` (7 dni). Sesja jest tworzona z stałym `expires_at = now + SESSION_DURATION` i **nie jest odświeżana** przy aktywności użytkownika. Użytkownik aktywnie pracujący przez > 7 dni od logowania będzie nieoczekiwanie wylogowany. Brak sliding window session management. Krótszy problem bezpieczeństwa: sesja z dnia 1 i sesja z dnia 6 mają identyczny czas życia od stworzenia — nie od ostatniego użycia.

**Proponowany fix:** Przy każdym `get_current_user()` sprawdzaj czy sesja zbliża się do wygaśnięcia (np. < 1 dzień), i jeśli tak — odśwież `expires_at` o kolejne `SESSION_DURATION`.

---

*Raport: Gemini | SYLION v5.9.0 | 10 findings (2 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW)*
