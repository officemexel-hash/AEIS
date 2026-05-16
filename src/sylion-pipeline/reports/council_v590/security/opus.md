# SYLION v5.9.0 — Security Audit Report: Opus Perspective
**Focus: Injection (OWASP A03) + Broken Auth (OWASP A07) + Security Misconfiguration (OWASP A05)**
**Date: 2026-04-19 | Reviewer: Opus**

---

## CRITICAL

### F-OPS-001 — SQL Injection via Dynamic PRAGMA user_version in _run_migrations
**Severity:** CRITICAL  
**CVSS:** 9.1 (AV:L/AC:L/PR:H/UI:N/S:C/C:H/I:H/A:H)  
**File:Linia:** `db.py:817`

**Opis:**
```python
conn.execute(f"PRAGMA user_version = {version}")
```
Zmienna `version` pochodzi z iteracji `range(current + 1, target + 1)`. Wartość `current` jest odczytywana z bazy danych:
```python
current = conn.execute("PRAGMA user_version").fetchone()[0]
```
Jeśli atakujący może zmodyfikować plik `.db` (np. przez dostęp do systemu plików), może wstrzyknąć dowolną wartość do `PRAGMA user_version`. Choć SQLite ogranicza PRAGMA do liczb całkowitych, to `version` pochodzi z zewnętrznego pliku DB i nie jest castowane jawnie przed interpolacją. Wartość nieoczekiwana (np. negatywna, bardzo duża) może powodować nieprzewidywalne zachowanie migracji lub obejście warunku `current > target`.

**Dodatkowy kontekst:** Podobny wzorzec widoczny w `_migration_0_to_1`:
```python
conn.execute(f"ALTER TABLE model_registry ADD COLUMN {col} {typedef}")
```
Tutaj `col` i `typedef` pochodzą z hardkodowanej listy Python, co jest bezpieczne — ale wzorzec f-string w execute() pozostaje ryzykowny jako precedens.

**Proponowany fix:**
```python
# Rzutuj jawnie na int i zweryfikuj zakres przed interpolacją
version_int = int(version)
assert 1 <= version_int <= 9999, "version out of range"
conn.execute(f"PRAGMA user_version = {version_int}")
```
Lub użyj parametryzowanego zapytania jeśli SQLite to wspiera dla PRAGMA (niestety nie wspiera — stąd konieczność jawnego cast + walidacji).

---

### F-OPS-002 — Broken Authentication: Brak Rate Limiting na /api/auth/login
**Severity:** CRITICAL  
**CVSS:** 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)  
**File:Linia:** `app.py:370-418`

**Opis:**
Endpoint `/api/auth/login` nie implementuje żadnego rate limiting ani lockout po nieudanych próbach. Atakujący może wykonać nieograniczoną liczbę prób brute-force haseł. Brak mechanizmu: progressive delays, account lockout po N nieudanych próbach, CAPTCHA, ani IP-based throttling. Jedyna ochrona to Argon2id (kosztowne haszowanie), ale Argon2 z parametrami `time_cost=3, memory_cost=65536` daje ~100ms/próbę — przy 10 równoległych żądaniach to ~1000 prób/s (ograniczone latencją serwera, ale realnie wykonalne dla słabych haseł).

**Proponowany fix:**
```python
# Implementuj licznik nieudanych prób per username/IP w tabeli sessions lub osobnej tabeli
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_MAX_ATTEMPTS = 10
_WINDOW_SECS = 300  # 5 min

def _check_rate_limit(key: str):
    now = time.time()
    attempts = [t for t in _LOGIN_ATTEMPTS.get(key, []) if now - t < _WINDOW_SECS]
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(429, "Zbyt wiele prób logowania. Poczekaj 5 minut.")
    attempts.append(now)
    _LOGIN_ATTEMPTS[key] = attempts
```

---

## HIGH

### F-OPS-003 — SQL Injection via Dynamic WHERE Clause w list_ollama_shadow_log / list_ollama_insights
**Severity:** HIGH  
**CVSS:** 7.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N)  
**File:Linia:** `app.py:5697-5703, 5814-5820`

**Opis:**
```python
where_sql = f"WHERE {' AND '.join(where)}" if where else ""
total = conn.execute(
    f"SELECT COUNT(*) AS c FROM ollama_shadow_log {where_sql}",
    tuple(params),
).fetchone()["c"]
```
Zapytania filtrujące budują fragment WHERE poprzez `.join(where)` — gdzie `where` jest listą stringów takich jak `"agent_id = ?"` lub `"quality_verdict = ?"`. Wartości są poprawnie parametryzowane przez `?`. Jednakże, gdy lista `where` jest pusta i budowany jest `where_sql = ""`, całe zapytanie jest interpolowane przez f-string, tworząc potencjalny precedens. Ryzyko bezpośredniej SQLi jest tu niskie (wartości są w `params`), jednak wzorzec dynamicznej konstrukcji SQL przez f-string jest inherentnie niebezpieczny i podatny na regresję — przyszły developer może dołączyć do `where` wartość nieoczyszczoną.

**Rzeczywiste ryzyko:** Jeśli ktokolwiek kiedykolwiek doda `where.append(user_controlled_value)` zamiast `where.append("col = ?")` + `params.append(value)`, natychmiastowa SQLi.

**Proponowany fix:**
Użyj allowlisty kolumn do filtrowania i zawsze buduj WHERE z `?` placeholderami:
```python
ALLOWED_FILTERS = {"agent_id", "quality_verdict", "status"}
where = []
params = []
for col, val in [("agent_id", agent_id), ("quality_verdict", quality)]:
    if val and col in ALLOWED_FILTERS:
        where.append(f"{col} = ?")
        params.append(val)
```

---

### F-OPS-004 — Dynamic UPDATE via f-string w wielu endpointach (update_user, update_prompt, update_baseline, etc.)
**Severity:** HIGH  
**CVSS:** 7.2 (AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `app.py:664, 997, 1397, 1440, 1884, 2919, 3209, 3675, 4008, 4480`

**Opis:**
Wzorzec:
```python
conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", params)
```
`updates` jest listą stringów jak `"display_name=?"`, `"role=?"`. Wartości są w `params`. Na pierwszy rzut oka bezpieczne — lecz lista `updates` jest budowana z warunków `if body.field is not None:` bez allowlisty nazw kolumn. Jeśli Pydantic przepuści nieoczekiwane pole (np. przez `extra="allow"` — w tym przypadku model ma `extra="ignore"`, więc ryzyko mniejsze) lub deweloper doda pole bez walidacji, kolumna SQL może być kontrolowana przez użytkownika.

**Proponowany fix:**
Jawna allowlista kolumn:
```python
ALLOWED_COLUMNS = {"display_name", "role", "password_hash", "enabled"}
for field_name, col, val in candidates:
    assert col in ALLOWED_COLUMNS, f"Unexpected column: {col}"
    updates.append(f"{col}=?")
    params.append(val)
```

---

### F-OPS-005 — Weak Password Policy (minimum 8 znaków, brak złożoności)
**Severity:** HIGH  
**CVSS:** 7.3 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `app.py:520`

**Opis:**
```python
if len(body.password) < 8:
    raise HTTPException(400, "Hasło musi mieć minimum 8 znaków")
```
Jedyne kryterium walidacji hasła to długość >= 8. Brak weryfikacji złożoności, brak blacklisty popularnych haseł (`password`, `12345678`), brak górnego limitu długości (potencjalny DoS przez bardzo długi password w Argon2). Przy Argon2 z `memory_cost=65536` (64MB) próba zhashowania 1MB+ hasła może zablokować serwer.

**Proponowany fix:**
```python
if len(body.password) < 12:
    raise HTTPException(400, "Hasło musi mieć minimum 12 znaków")
if len(body.password) > 128:
    raise HTTPException(400, "Hasło zbyt długie (max 128)")
# Opcjonalnie: weryfikacja entropii lub zbioru znaków
```

---

## MEDIUM

### F-OPS-006 — Race Condition w prune_audit_log / prune_sessions (TOCTOU)
**Severity:** MEDIUM  
**CVSS:** 5.3 (AV:L/AC:H/PR:L/UI:N/S:U/C:N/I:L/A:L)  
**File:Linia:** `db.py:984-994, 1016-1025`

**Opis:**
```python
while True:
    cur = conn.execute(
        "DELETE FROM audit_log WHERE id IN "
        "(SELECT id FROM audit_log WHERE ts < ? LIMIT 1000)",
        (cutoff,),
    )
    conn.commit()
    deleted = cur.rowcount or 0
    total += deleted
    if deleted < 1000:
        break
```
Brak eksplicytnej transakcji obejmującej cały proces pruningu. Każdy batch jest commitowany osobno, więc współbieżne inserty między commitami mogą powodować niespójność w zliczaniu. Przy SQLite WAL i single-worker to ryzyko niskie, ale przy wywołaniu `prune_audit_log()` z zewnątrz (np. test fixture) może dojść do race. Dodatkowo, funkcja jest wywoływana zarówno w lifespan startup, jak i w `_periodic_prune` (asyncio.to_thread) — jeśli serwer restartuje podczas pruningu, może zostać przerwany w połowie.

**Proponowany fix:** Dodaj `BEGIN EXCLUSIVE` lub `BEGIN IMMEDIATE` przed pętlą pruningu i `COMMIT` po zakończeniu całego procesu (lub zaakceptuj obecną semantykę "best-effort batched" z dokumentacją).

---

### F-OPS-007 — Setup Token Ujawniany w API Response (wartość plaintext)
**Severity:** MEDIUM  
**CVSS:** 6.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)  
**File:Linia:** `app.py:485-488`

**Opis:**
```python
return JSONResponse(
    {"token": stripped, "hint": "Token wczytany z SETUP_TOKEN.txt"},
    headers={"Cache-Control": "no-store, private", "Pragma": "no-cache"},
)
```
Endpoint `/api/auth/setup-token-hint` zwraca plaintext setup token przez sieć (nawet jeśli tylko z loopback). Token jest jednorazowy i chroniony ograniczeniem do 127.0.0.1/::1, ale plik `SETUP_TOKEN.txt` zawiera token w plaintext, a endpoint go udostępnia w JSON. Logi HTTP (np. nginx access log) mogą zapisać URL odpowiedzi bez body, lecz tokeny w query strings i nagłówkach są logowane.

**Ryzyko:** Lokalny atakujący z dostępem do logów może przechwycić token.

**Proponowany fix:** Rozważ wymaganie potwierdzenia (np. PIN wygenerowany na konsoli) zamiast ekspozycji tokena przez API.

---

### F-OPS-008 — Brak Weryfikacji Integralności Lockfile w _ensure_dependencies
**Severity:** MEDIUM  
**CVSS:** 5.9 (AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:H/A:N)  
**File:Linia:** `start.py:137-160`

**Opis:**
```python
if _LOCK.exists():
    r = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "-r", str(_LOCK)],
        ...
    )
```
Plik lockfile `requirements-lock.txt` jest instalowany bez weryfikacji podpisu kryptograficznego ani hasha. Jeśli atakujący może zmodyfikować ten plik (np. przez kompromitację repozytorium lub systemu plików), może wykonać dowolny kod Python przez złośliwą zależność. Supply chain attack vector.

**Proponowany fix:** Weryfikuj SHA-256 lockfile przed instalacją z hardkodowanym hashem, lub używaj `pip install --require-hashes` (hash per pakiet w lockfile).

---

## LOW

### F-OPS-009 — Informacja o Wersji w /api/version (bez auth)
**Severity:** LOW  
**CVSS:** 3.7 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)  
**File:Linia:** `app.py:272-285`

**Opis:**
Endpoint `/api/version` nie wymaga uwierzytelnienia i ujawnia pełną wersję systemu (`5.9.0`), datę buildu (`2026-04-19`) i wersje komponentów. Ułatwia to fingerprinting i identyfikację podatnych wersji.

**Proponowany fix:** Ogranicz dostęp do `/api/version` do uwierzytelnionych użytkowników, lub zwracaj minimalny zakres informacji anonimowo.

---

### F-OPS-010 — Backup Filename zawiera Hardkodowaną Wersję (v5.8.9 zamiast aktualnej)
**Severity:** LOW  
**CVSS:** 2.1 (AV:L/AC:L/PR:H/UI:N/S:U/C:N/I:L/A:N)  
**File:Linia:** `db.py:754`

**Opis:**
```python
version_tag = "v5.8.9"
backup_path = backup_dir / f"sylion.db.bak.{version_tag}.{date_str}.sqlite3"
```
Funkcja `_backup_db_before_migration` hardkoduje `version_tag = "v5.8.9"` mimo że jest wykonywana w wersji v5.9.0. Powoduje to mylący naming backupów i trudności w audycie — backupy z v5.9.0 będą oznaczone jako v5.8.9.

**Proponowany fix:** Importuj i używaj `SYLION_VERSION` z `app.py` lub zdefiniuj wspólną stałą wersji w `db.py`.

---

*Raport: Opus | SYLION v5.9.0 | 10 findings (2 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW)*
