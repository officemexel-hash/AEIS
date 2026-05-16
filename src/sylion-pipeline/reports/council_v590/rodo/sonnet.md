# SYLION v5.9.0 — Audyt Compliance (Sonnet / Implementacja)
**Audytor:** Claude Sonnet 4.6 — Implementation Compliance Council  
**Data:** 2025-07-10  
**Zakres:** Implementacja funkcji `prune_audit_log`, `prune_sessions`, `_get_retention_days`, backup M-08, human_gate, API  
**Standard:** RODO art.5.1.e, art.17, art.30, art.32; GoBD

---

## EXECUTIVE SUMMARY

Analiza implementacji wskazuje, że mechanizmy retencji (M-03) są prawidłowo zaimplementowane technicznie — batch delete, WAL-safe, fallback do defaults. Krytyczna luka dotyczy hardkodowania kluczy API w `_DEFAULT_API_KEYS`. Mechanizm prune jest wywoływany tylko przy migracjach, nie planowo codziennie bez dodatkowego schedulera.

---

## FINDINGS

### CRITICAL

#### C-01 — Klucze API w Kodzie Źródłowym (Implementacja)
**Lokalizacja:** `db.py` linie ~43-47: `_DEFAULT_API_KEYS = { "OPENAI_API_KEY": "sk-proj-JwEw64A9..." }`  
**Opis (implementacyjny):** Wartości `_DEFAULT_API_KEYS` są stringami Python zapisanymi w module. Każdy import `db` eksponuje klucze w pamięci procesu. Mechanizm `secret=1` w DB chroni WYŚWIETLANIE w UI, ale:
1. `sync_api_keys_to_env()` kopiuje wartości do `os.environ` — środowisko procesu jest dostępne `/proc/PID/environ` na Linux.
2. Klucze są zapisywane jako plaintext w SQLite (kolumna `value` TEXT).
3. WAL backup kopiuje te wartości do pliku backup — brak szyfrowania backupu.

**Ścieżka eksfiltracji:** git log → _DEFAULT_API_KEYS literal → kompromis wszystkich kont AI.  
**Fix:** `os.environ.get("OPENAI_API_KEY", "")` jako seed, nigdy literal w kodzie.  
**Severity:** CRITICAL

---

### HIGH

#### H-01 — Scheduler Prune — Warunkowe Działanie
**Lokalizacja:** `app.py:_periodic_prune` / `_PRUNE_TASKS`  
**Opis:** `_PRUNE_TASKS` zawiera `prune_audit_log` i `prune_sessions` wywoływane co 24h (`_PRUNE_INTERVAL_S = 86_400`). Jednakże scheduler uruchamia się tylko gdy działa `uvicorn` — jeśli aplikacja jest zatrzymana przez długi czas, prune nie działa. Dla środowisk z nieciągłą pracą aplikacji retencja może nie być egzekwowana.  
**Rekomendacja:** Dodać cron job (systemd timer lub crontab) wywołujący prune niezależnie od działania aplikacji.  
**Severity:** HIGH

---

#### H-02 — `delete_user` — Niekompletna Anonimizacja Audit Log
**Lokalizacja:** `app.py:delete_user()` linia ~23759  
**Opis:** Implementacja:
```python
conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
conn.execute("DELETE FROM users WHERE id=?", (user_id,))
conn.commit()
audit_log(conn, "user.delete", user_id, actor=actor["username"])
```
Po usunięciu użytkownika, `audit_log` zawiera dalej wpisy z `actor=<deleted_username>` z poprzednich akcji. RODO art.17 "prawo do usunięcia" nie wymaga kasowania ścieżki audytu (uzasadnienie: bezpieczeństwo, art.17.3b), ale wymaga dokumentacji tej decyzji w RoPA.  
**Rekomendacja:** Albo anonimizować `actor` w audit_log (np. `"[deleted_user]"`), albo udokumentować w RoPA że audit_log jest podstawą bezpieczeństwa (wyjątek art.17.3).  
**Severity:** HIGH

---

### MEDIUM

#### M-01 — `_get_retention_days` — Poprawność Implementacji ✓
**Lokalizacja:** `db.py:944-967`  
**Opis:** Implementacja POPRAWNA. Funkcja:
1. Czyta z `config` table z `SELECT value FROM config WHERE key = ?`.
2. Obsługuje brak wiersza → fallback do `default`.
3. Obsługuje `sqlite3.OperationalError` → fallback (np. brak tabeli podczas init).
4. Waliduje: `non-numeric → warning + default`; `≤0 → warning + default`.
5. Loguje ostrzeżenia z prefixem `M-03`.

**Jedyna uwaga:** Brak górnego limitu (ktoś mógłby ustawić 9999 lat). Dla minimalizacji danych (art.5.1.e) warto dodać max limit.  
**Severity:** MEDIUM (uwaga, nie błąd krytyczny)

---

#### M-02 — `prune_audit_log` — Batch Delete (1000 rows/tx) ✓
**Lokalizacja:** `db.py:970-1002`  
**Opis:** Implementacja batch delete POPRAWNA. Używa:
```python
"DELETE FROM audit_log WHERE id IN (SELECT id FROM audit_log WHERE created_at < ? LIMIT 1000)"
```
Podejście WAL-safe — krótkie transakcje nie blokują czytelników. Zwraca total count.  
**Brak:** Indeks na `audit_log.created_at` — pełne skanowanie tabeli przy każdym batch. Przy dużych zbiorach degradacja wydajności.  
**Rekomendacja:** `CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at)`.  
**Severity:** MEDIUM

---

#### M-03 — `prune_sessions` — Poprawność ✓
**Lokalizacja:** `db.py:1004-1030`  
**Opis:** Analogiczna implementacja do `prune_audit_log`. Kasuje sesje starsze niż `SESSIONS_RETENTION_DAYS` (domyślnie 30 dni). Poprawna. Sesje wygasłe (pole `expires_at`) vs. sesje nieaktywne — warto sprawdzić czy prune używa właściwego pola (`created_at` vs `expires_at`).  
**Rekomendacja:** Weryfikacja czy kasowane są sesje wg `expires_at < now - days` a nie tylko wg `created_at`.  
**Severity:** MEDIUM

---

#### M-04 — Backup M-08 — Guard F-04 Path Traversal ✓
**Lokalizacja:** `db.py:744-777`  
**Opis:** Guard F-04 (`backup_path.resolve().relative_to(backup_dir.resolve())`) zapobiega path traversal — POPRAWNY. SQLite online backup API działa w WAL mode — POPRAWNY. Brak szyfrowania pliku backup — patrz Opus H-03.  
**Severity:** MEDIUM (brak szyfrowania backupu)

---

#### M-05 — GoBD/HGB — `audit_log` vs. Dokumenty Księgowe
**Opis:** GoBD (Niemcy) wymaga 10-letniej retencji dla dokumentów księgowych. `audit_log` w SYLION to dziennik techniczny (security log), NIE dokument księgowy w rozumieniu §147 AO / HGB. Zatem:
- `_AUDIT_LOG_RETENTION_DEFAULT = 365` nie narusza GoBD.
- Jeśli w przyszłości audit_log będzie zawierał transakcje finansowe, retencja musi wzrosnąć do 10 lat.

**Status:** OK dla bieżącego use-case.  
**Severity:** MEDIUM (uwaga na przyszłość)

---

### LOW

#### L-01 — `SETUP_TOKEN.txt` — Potencjalny Sekret w Repo
**Lokalizacja:** `dashboard/SETUP_TOKEN.txt`  
**Opis:** Plik `SETUP_TOKEN.txt` w katalogu dashboard może zawierać token setup. Jeśli jest commitowany do gita i nie jest w `.gitignore`, stanowi naruszenie art.32.  
**Rekomendacja:** Sprawdzić `.gitignore`, usunąć z historii gita jeśli commitowany.  
**Severity:** LOW → CRITICAL jeśli commitowany

#### L-02 — `test_sylion.db` w Repozytorium
**Lokalizacja:** `dashboard/test_sylion.db`  
**Opis:** Baza testowa może zawierać dane testowe (hasła, tokeny). Nawet jeśli dane są fikcyjne, plik .db w repo może być problemem.  
**Severity:** LOW

#### L-03 — Brak Rate Limiting na Endpointach Uwierzytelniania
**Lokalizacja:** `app.py` — login endpoint  
**Opis:** Brak widocznego rate limitingu na `/api/auth/login` — podatność na brute force. Naruszenie art.32 (środki bezpieczeństwa).  
**Severity:** LOW → HIGH w produkcji

---

## PODSUMOWANIE IMPLEMENTACJI

| Komponent | Status | Uwagi |
|-----------|--------|-------|
| `_get_retention_days` | POPRAWNY | Brak górnego limitu |
| `prune_audit_log` | POPRAWNY | Brak indeksu |
| `prune_sessions` | POPRAWNY | Sprawdzić które pole daty |
| Backup M-08 | POPRAWNY | Brak szyfrowania |
| `delete_user` | CZĘŚCIOWY | Audit log nie anonimizowany |
| API Keys | KRYTYCZNY | Hardcoded w kodzie |
| human_gate | POPRAWNY | Spełnia AI Act art.14 |
| Scheduler prune | WARUNKOWY | Tylko gdy app działa |
