# SYLION v5.9.0 — Security Audit Report: GPT-5.4 Perspective
**Focus: Injection (OWASP A03) + Security Logging & Monitoring Failures (OWASP A09) + Software & Data Integrity (OWASP A08)**
**Date: 2026-04-19 | Reviewer: GPT-5.4**

---

## CRITICAL

### F-GPT-001 — Command Injection Potencjał w _batch_imports_ok via import_names
**Severity:** CRITICAL  
**CVSS:** 8.4 (AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:H)  
**File:Linia:** `start.py:83-101`

**Opis:**
```python
def _batch_imports_ok(import_names):
    script = "; ".join(f"import {n}" for n in import_names)
    r = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=_BATCH_TIMEOUT,
    )
```
Zmienna `script` jest budowana przez konkatenację nazw importów. Komentarz w kodzie twierdzi: _"safe because names come from our hardcoded `_CRITICAL_DEPS` dict (security3 F-03)"_. To jest prawdą w normalnym wykonaniu — `_CRITICAL_DEPS` jest hardkodowany. Jednakże:

1. `_batch_imports_ok` jest publiczną (nieprefixowaną `__`) funkcją dostępną z zewnątrz modułu.
2. Jeśli testy jednostkowe lub zewnętrzny kod wywołają `_batch_imports_ok(["os; os.system('rm -rf /')"])`, nastąpi command injection przez `-c "import os; os.system('rm -rf /')"`.
3. V5.9.0 M-07 eksponuje `import subprocess` na poziomie modułu "so unit tests can monkey-patch" — to świadomie rozszerza powierzchnię ataku testów.

**Ryzyko:** Wysoki jeśli `_batch_imports_ok` jest wywoływane z zewnętrznych danych; Niski w obecnym flow (tylko `_CRITICAL_DEPS`).

**Proponowany fix:**
```python
# Walidacja allowlisty PRZED budowaniem scriptu
IMPORT_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_.]*$')

def _batch_imports_ok(import_names):
    for n in import_names:
        if not IMPORT_NAME_RE.match(n):
            raise ValueError(f"Unsafe import name: {n!r}")
    script = "; ".join(f"import {n}" for n in import_names)
    ...
```

---

### F-GPT-002 — Path Traversal w _backup_db_before_migration: backup_dir nie jest rozwiązane przed mkdir
**Severity:** CRITICAL  
**CVSS:** 7.5 (AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `db.py:756-762`

**Opis:**
```python
backup_dir = Path.home() / "sylion"
backup_dir.mkdir(parents=True, exist_ok=True)
backup_path = backup_dir / f"sylion.db.bak.{version_tag}.{date_str}.sqlite3"

try:
    backup_path.resolve().relative_to(backup_dir.resolve())
except ValueError:
    raise RuntimeError(...)
```
Guard F-04 sprawdza czy `backup_path.resolve()` jest w `backup_dir.resolve()`. Jednak `backup_dir.mkdir()` jest wywołane **przed** sprawdzeniem. Jeśli `Path.home()` zwraca wartość kontrolowaną przez środowisko (`HOME=/tmp/../../etc`), backup_dir jest tworzony poza oczekiwaną lokalizacją **zanim** guard to wykryje.

Konkretnie: `Path.home()` czyta `HOME` env var. Jeśli `HOME=/tmp/attack_dir` gdzie `attack_dir` zawiera symlink do `/etc`, to `backup_dir.mkdir()` tworzy katalog przez symlink **zanim** guard sprawdzi `relative_to`. Guard używa `resolve()` co rozwiązuje symlinki — więc wykryje naruszenie — ale katalog już został stworzony.

**Proponowany fix:**
```python
backup_dir = Path.home() / "sylion"
# Resolve BEFORE mkdir
resolved_home = Path.home().resolve()
if not (resolved_home / "sylion").is_relative_to(resolved_home):
    raise RuntimeError("HOME directory resolved to unexpected path")
backup_dir.mkdir(parents=True, exist_ok=True)
```

---

## HIGH

### F-GPT-003 — Niezabezpieczone _get_retention_days: SQL Integer Overflow / Negative Values DoS
**Severity:** HIGH  
**CVSS:** 6.5 (AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:N/A:H)  
**File:Linia:** `db.py:959-966`

**Opis:**
```python
n = int(str(raw).strip())
if n <= 0:
    logger.warning("M-03: retention %s=%d ≤ 0, using default %d", key, n, default)
    return default
return n
```
Walidacja odrzuca `n <= 0`, ale akceptuje arbitralnie duże wartości. Administrator może ustawić `AUDIT_LOG_RETENTION_DAYS = 99999999` (273971 lat), co powoduje:
```python
cutoff = time.time() - 99999999 * 86400  # = timestamp ~270K lat temu
```
`cutoff` staje się bardzo dużą ujemną liczbą — SQLite z kolumną `ts REAL` zachowa się poprawnie (nie usunie nic), ale: przy bardzo małej wartości (np. `1` dzień), prune wyczyści prawie cały audit log. Nie ma górnego limitu walidacji.

**Proponowany fix:**
```python
MAX_RETENTION_DAYS = 3650  # 10 lat maksimum
if n > MAX_RETENTION_DAYS:
    logger.warning("M-03: retention %s=%d > max %d, using max", key, n, MAX_RETENTION_DAYS)
    return MAX_RETENTION_DAYS
```

---

### F-GPT-004 — _migration_0_to_1 wykonuje ALTER TABLE bez Transakcji Ochronnej
**Severity:** HIGH  
**CVSS:** 6.5 (AV:L/AC:H/PR:H/UI:N/S:U/C:N/I:H/A:H)  
**File:Linia:** `db.py:828-905`

**Opis:**
```python
def _migration_0_to_1(conn: sqlite3.Connection):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(prompts)").fetchall()}
    if "scope" not in cols:
        conn.execute("ALTER TABLE prompts ADD COLUMN scope TEXT NOT NULL DEFAULT 'global'")
    ...
```
Migracja jest wywoływana w kontekście `conn.execute("BEGIN EXCLUSIVE")` z `_run_migrations`, ale sama `_migration_0_to_1` nie sprawdza stanu transakcji. W SQLite, `PRAGMA table_info` jest bezpieczne w transakcji, ale `ALTER TABLE ADD COLUMN` może być problematyczne jeśli wiele transakcji jest zagnieżdżonych. Jeśli migracja zawiedzie po połowie alteracji, rollback cofnie `PRAGMA user_version = {version}`, ale część `ALTER TABLE` może być nieodwracalna (SQLite nie obsługuje `DROP COLUMN` w starszych wersjach).

Brak mechanizmu sprawdzenia "czy migracja jest w połowie wykonana" przy następnym restarcie — może prowadzić do "dirty migration state".

**Proponowany fix:** Dodaj weryfikację stanu po każdej `ALTER TABLE`, loguj każdy krok z timestamps. Rozważ "migration idempotency check" przed każdym ALTER.

---

### F-GPT-005 — Brak Sanityzacji w AgentSpec.id: możliwe SQL Injection przez agent_id
**Severity:** HIGH  
**CVSS:** 7.2 (AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `db.py:927-931, app.py passim`

**Opis:**
```python
@field_validator("id")
@classmethod
def id_must_be_nonempty(cls, v: str) -> str:
    if not v or not v.strip():
        raise ValueError("agent id must be a non-empty string")
    return v
```
Walidator `id_must_be_nonempty` sprawdza tylko czy id nie jest puste. Nie ogranicza dozwolonych znaków. Agent `id` jest następnie używany w wielu zapytaniach SQL jako parametr `?` (co jest bezpieczne), ale również w:
- Audit log `target` fields
- Dynamicznych WHERE przy filtrach
- Potencjalnie w nazewnictwie plików

Jeśli `agent_id` zawiera `'`, `"`, `;`, `\n` lub specjalne znaki, może to powodować problemy w logowaniu, exportach (CSV injection) lub audycie.

**Proponowany fix:**
```python
AGENT_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')

@field_validator("id")
@classmethod
def id_must_be_valid(cls, v: str) -> str:
    if not AGENT_ID_RE.match(v.strip()):
        raise ValueError(f"agent id must match pattern [a-zA-Z0-9_-]{{1,64}}, got: {v!r}")
    return v.strip()
```

---

## MEDIUM

### F-GPT-006 — prune_sessions Używa cutoff Opartego na expires_at, nie created_at — Logika Błędna
**Severity:** MEDIUM  
**CVSS:** 5.3 (AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N)  
**File:Linia:** `db.py:1016-1024`

**Opis:**
```python
days = _get_retention_days(conn, "SESSIONS_RETENTION_DAYS", _SESSIONS_RETENTION_DEFAULT)
cutoff = time.time() - days * 86400
cur = conn.execute(
    "DELETE FROM sessions WHERE token IN "
    "(SELECT token FROM sessions WHERE expires_at < ? LIMIT 1000)",
    (cutoff,),
)
```
`cutoff` jest odejmowany od `time.time()` i porównywany z `expires_at`. Logika: "usuń sesje które wygasły więcej niż `SESSIONS_RETENTION_DAYS` temu". To jest semantycznie poprawne (usuwa tylko faktycznie wygasłe sesje), ALE: sesja z `expires_at = time.time() + 86400 * 365` (rok) nigdy nie zostanie usunięta przez prune dopóki nie minie rok od wygaśnięcia. Jeśli `SESSIONS_RETENTION_DAYS = 30`, a sesja trwa 7 dni, to sesja jest usuwana `30 + 7 = 37` dni po stworzeniu — nie 30.

**Dodatkowe ryzyko:** Brak pruning aktywnych sesji z nieaktywnych kont — jeśli user zostaje wyłączony (`enabled=0`), ich sesja pozostaje w tabeli do naturalnego wygaśnięcia.

**Proponowany fix:** Dodaj również pruning sesji dla wyłączonych kont: `DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE enabled=0)`.

---

### F-GPT-007 — Audit Log Pomija Nieudane Próby Logowania
**Severity:** MEDIUM  
**CVSS:** 5.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N)  
**File:Linia:** `app.py:370-418`

**Opis:**
Udane logowanie jest logowane w `audit_log` (`auth.login`), ale **nieudane próby logowania nie są logowane**. Brak widoczności brute-force ataków, credential stuffing ani reconnaissance w audit logu. OWASP A09 (Security Logging and Monitoring Failures) wymaga logowania nieudanych prób uwierzytelnienia.

**Proponowany fix:**
```python
if not user or not verify_password(body.password, user["password_hash"]):
    # Log failed attempt BEFORE raising
    with get_conn() as c:
        audit_log(c, "auth.login_failed", body.username, 
                  f"Failed login attempt from {ip}", severity="warning")
    raise HTTPException(401, "Nieprawidłowe dane logowania")
```
Uwaga: loguj `body.username` (może nie istnieć w bazie), NIE hasło.

---

### F-GPT-008 — Brak Integrity Check na Backup File przed Migracją
**Severity:** MEDIUM  
**CVSS:** 4.9 (AV:L/AC:L/PR:H/UI:N/S:U/C:H/I:N/A:N)  
**File:Linia:** `db.py:768-778`

**Opis:**
Po stworzeniu backupu SQLite przez `source_conn.backup(dest_conn)`, nie ma weryfikacji integralności kopii:
```python
source_conn.backup(dest_conn)
# Brak weryfikacji: PRAGMA integrity_check na dest_conn
```
Jeśli backup jest niekompletny (przerwany I/O, pełny dysk), migracja kontynuuje. Wadliwy backup jest bezużyteczny w razie rollback potrzeby.

**Proponowany fix:**
```python
dest_conn = sqlite3.connect(str(backup_path))
try:
    source_conn.backup(dest_conn)
    # Weryfikuj backup
    result = dest_conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise sqlite3.DatabaseError(f"Backup integrity check failed: {result}")
finally:
    dest_conn.close()
```

---

## LOW

### F-GPT-009 — Session ID Kolizja: uuid4().hex[:16] (64-bit przestrzeń)
**Severity:** LOW  
**CVSS:** 2.9 (AV:L/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)  
**File:Linia:** `app.py:397`

**Opis:**
```python
(uuid.uuid4().hex[:16], user["id"], token, now, now + SESSION_DURATION, ip)
```
Session record `id` to pierwsze 16 znaków hex UUID4 = 64-bit. Przy milionach sesji teoretyczna kolizja jest mała (birthday paradox: ~50% po 2^32 = 4 miliardach), ale `INSERT` SQLite zwróci `UNIQUE constraint failed` przy kolizji, powodując błąd dla użytkownika. Niegroźne bezpieczeństwo, ale błąd logiki.

**Proponowany fix:** Użyj pełnego `uuid.uuid4().hex` (128 bitów) lub `secrets.token_hex(16)`.

---

### F-GPT-010 — Log Injection via Niezabezpieczone f-string w logger.info
**Severity:** LOW  
**CVSS:** 2.5 (AV:L/AC:H/PR:L/UI:N/S:U/C:N/I:L/A:N)  
**File:Linia:** `db.py:812-813, 820`

**Opis:**
```python
logger.info("M-02: applying migration → user_version=%d (%s)",
            version, migration.__name__)
```
Tu bezpiecznie (parametryzowane). Ale w `_seed_agents`:
```python
logger.warning("_parse_agents_yaml(%s) failed: %s — using fallback", AGENTS_YAML_PATH, exc)
```
Jeśli `exc` zawiera znaki sterujące (np. `\n`, ANSI escape sequences) z pliku YAML, może to "zatruć" logi. Log injection jest możliwy gdy atakujący może kontrolować treść `agents.yaml` lub wyjątek generowany przez jej parsowanie.

**Proponowany fix:**
```python
safe_exc = str(exc).replace('\n', ' ').replace('\r', '')
logger.warning("_parse_agents_yaml(%s) failed: %s — using fallback", AGENTS_YAML_PATH, safe_exc)
```

---

*Raport: GPT-5.4 | SYLION v5.9.0 | 10 findings (2 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW)*
