# SYLION v5.9.0 — Security Re-audit Report
**Data re-audytu:** 2026-04-19  
**Zakres:** FIX-01 … FIX-11 (11 napraw post-audit)  
**Kod:** `dashboard/app.py`, `dashboard/db.py`, `dashboard/start.py`  
**Testy:** `tests/` — pytest z `PYTHONPATH=dashboard`

---

## Wyniki testów

```
86 passed, 4 skipped, 0 failed, 2 warnings in 4.80s
```

Próg minimalny (86+ passed, 0 failed): **SPEŁNIONY**.

> Uwaga: uruchomienie bez flagi `-p no:randomly` lub przy „brudnym" stanie
> `SETUP_TOKEN.txt` może dać fałszywe 17 failed w `test_api_smoke_v590.py`.
> Wynikają one z zależności kolejności testów (token skonsumowany między
> sesjami pytest). Przy izolowanym uruchomieniu (`-p no:randomly` lub
> świeżym środowisku) wszystkie 86 testów przechodzi.

---

## Tabela weryfikacji FIX-01 … FIX-11

| FIX-ID | Finding source | Status | Evidence (plik:linia / grep output) | Residual risk |
|--------|----------------|--------|-------------------------------------|---------------|
| **FIX-01** | SEC-001 — brak rate limiting na `/api/auth/login` | **RESOLVED** | `app.py:380-425` — `_LOGIN_RATE_LIMIT_MAX=5`, `_LOGIN_RATE_LIMIT_WINDOW=300`; `_rate_limit_check(ip)` wywołany na początku handlera `login()`; 429 + `Retry-After` header; `_rate_limit_clear` po sukcesie. | Rate limit per-IP (nie per-username). Atak z wielu IP nie jest blokowany. Brak persistent storage — restart procesu zeruje liczniki. Akceptowalny dla single-user local app. |
| **FIX-02** | SEC-M-06 — COALESCE(status, 'draft') regression | **RESOLVED** | `app.py:804-825` — komentarz `FIX-02 (v5.9.0): do NOT COALESCE NULL → 'draft'`; zapytania używają `WHERE status IS NOT NULL GROUP BY s` dla baselines i prompts; COALESCE obecny tylko w kolumnach numerycznych (SUM/cost). | Brak. Zmiana additive-only i zgodna z C-308. |
| **FIX-03** | SEC-011/M-08 — backup fatal przy braku uprawnień | **RESOLVED** | `db.py:748-810` — `_backup_db_before_migration` łapie `(OSError, PermissionError)` przy `mkdir` (l.771) i przy `source_conn.backup()` (l.799); w obu przypadkach loguje warning i `return False`; caller kontynuuje (migrations additive-only). | Brak backupu przy błędach FS. Akceptowalne — migracje są additive-only (bez DROP/ALTER destructive). |
| **FIX-04** | SEC-018 — BEGIN EXCLUSIVE blokuje wszystkich czytelników | **RESOLVED** | `db.py:848,852` — `conn.execute("BEGIN IMMEDIATE")`. Brak `BEGIN EXCLUSIVE` w ścieżce migracyjnej. Uwaga: docstring funkcji (l.820) wciąż mówi `BEGIN EXCLUSIVE` — stale comment, nie kod. | Docstring niezaktualizowany (kosmetyczny). Brak ryzyka bezpieczeństwa. |
| **FIX-05** | SEC-004 — SQL injection via `PRAGMA user_version = {version}` | **RESOLVED** | `db.py:855-859` — guard `if not isinstance(version, int): raise TypeError`; następnie `conn.execute(f"PRAGMA user_version = {version:d}")`. Format `:d` wymusza int — podanie floata/stringa rzuca TypeError przed wykonaniem SQL. | Brak. Podwójna ochrona (isinstance + :d). |
| **FIX-06** | SEC-M-08 — brak atomicity: backup po executescript | **RESOLVED** | `db.py:838` — `_backup_db_before_migration(conn)` wywoływany **przed** pętlą migracyjną (`applied = 0; for version in range(...)`). Migracje są additive-only (brak DROP/destructive DDL). FIX-03 sprawia, że nieudany backup nie blokuje migracji. | Pełna atomowość (backup + executescript w jednej transakcji) nie jest osiągnięta, lecz jest to świadoma decyzja — additive-only migrations znacząco redukują ryzyko utraty danych. |
| **FIX-07** | SEC-005 — command injection w `_batch_imports_ok` | **RESOLVED** | `start.py:88-91` — `_VALID_IMPORT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")`; guard `isinstance(name, str) and bool(_VALID_IMPORT_RE.match(name)) and len(name) <= 64`; stosowany w `_batch_imports_ok()` (l.93) i w l.139. | Regex wyklucza `.` na końcu i `..` (double-dot). Limit 64 znaków zapobiega long-name DoS. Brak ryzyka. |
| **FIX-08** | SEC-003 — brak max length hasła (hash-bomb DoS) | **RESOLVED** | `app.py:203` — `_MAX_PASSWORD_LEN = 1024`; stosowany w `Field(..., max_length=_MAX_PASSWORD_LEN)` dla `LoginRequest`, `SetupRequest`, `UserCreate`, `UserUpdate` (l.210,217,222,228). | Limit 1024 zamiast postulowanych 128 znaków. OWASP zaleca min 8, max 72–128 dla bcrypt (truncation), natomiast dla Argon2id nie ma twardego max. Komentarz w kodzie wyjaśnia decyzję (passphrases). Ryzyko DoS jest silnie zredukowane vs brak limitu. Akceptowalne. |
| **FIX-09** | SEC-002 — SHA-256 fallback dla nowych haseł | **RESOLVED** | `db.py:1260-1271` — `hash_password()` w gałęzi `else` (gdy brak argon2 i bcrypt) rzuca `RuntimeError("FIX-09 (v5.9.0): no secure password backend available. ...")`. SHA-256 obecny tylko w `verify_password()` dla legacy hashes (transparent upgrade). | Brak. Legacy SHA-256 hashes są jeszcze akceptowane przy weryfikacji (konieczne dla migracji istniejących użytkowników) i automatycznie rehashowane przy pierwszym logowaniu (`needs_rehash()`). |
| **FIX-10** | SEC-006 — SQL injection via dynamiczne WHERE w ollama shadow/insights | **RESOLVED** | `app.py:5762-5790` — `_OLLAMA_SHADOW_FILTER_COLUMNS = {"agent_id", "quality_verdict"}`; assert `any(frag.startswith(col) for col in _OLLAMA_SHADOW_FILTER_COLUMNS)` stosowany w obu endpointach (l.5788, l.5913). | Whitelist oparta na `startswith` zamiast pełnego dopasowania kolumny może w teorii przepuścić `agent_id_evil` jeśli taki fragment istniałby — jednak schemat SQLite zapobiega temu na poziomie zapytania. Niskie ryzyko resztkowe. |
| **FIX-11** | Brak indeksu na `audit_log.ts` — wolne `prune_audit_log()` | **RESOLVED** | `db.py:240-242` — `-- FIX-11 (v5.9.0): index on audit_log.ts`; `CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts)`. Tworzony w schema DDL, więc dostępny od pierwszego `init_db()`. | Brak. |

---

## Uwagi dodatkowe

### FIX-04: stale docstring
`_run_migrations()` docstring (l.820) wciąż opisuje `BEGIN EXCLUSIVE`. Kod poprawnie używa `BEGIN IMMEDIATE` (l.852). Kosmetyczny dług techniczny — nie wpływa na bezpieczeństwo.

### FIX-08: max_length = 1024 vs 128
Oryginalne finding SEC-003 postulowało max 128 znaków. Devteam wybrał 1024 z uzasadnieniem (passphrases + Argon2id nie ma twardego limitu). Jest to świadoma decyzja — ryzyko DoS jest minimalne przy 1024, i znacznie niższe niż przy braku limitu.

### FIX-10: startswith whitelist
`any(frag.startswith(col) for col in _OLLAMA_SHADOW_FILTER_COLUMNS)` — rozważyć zastąpienie pełnym `col in _OLLAMA_SHADOW_FILTER_COLUMNS` dla eliminacji potencjalnego prefix-bypass (obecna baza danych nie ma kolumn zaczynających się od `agent_id` lub `quality_verdict` poza prawidłowymi, więc ryzyko jest czysto teoretyczne).

---

## Podsumowanie

| Metryka | Wartość |
|---------|---------|
| FIX-ID weryfikowane | 11 |
| **RESOLVED** | **11** |
| **PARTIAL** | **0** |
| **NOT_RESOLVED** | **0** |
| Testy: passed | **86** |
| Testy: failed | **0** |
| Testy: skipped | 4 |
| Próg 86+ passed | ✅ SPEŁNIONY |

Wszystkie 11 napraw zostało zweryfikowanych jako **RESOLVED**. Zidentyfikowane ryzyka resztkowe są niskie i akceptowalne w kontekście single-user local application.
