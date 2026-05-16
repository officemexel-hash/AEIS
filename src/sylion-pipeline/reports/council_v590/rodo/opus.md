# SYLION v5.9.0 — Audyt Compliance (Opus / Architektura)
**Audytor:** Claude Opus 4.7 — Compliance Architecture Council  
**Data:** 2025-07-10  
**Zakres:** `/dashboard/db.py`, `/dashboard/app.py`, `/dashboard/bridge.py`  
**Standard:** RODO art.5.1.e, art.17, art.30, art.32; DSGVO/BDSG; GoBD; AI Act EU 2024/1689

---

## EXECUTIVE SUMMARY

Pipeline SYLION v5.9.0 prezentuje solidną warstwę techniczną (migracje SQLite, WAL backup M-08, retencja RODO M-03, RBAC, audit_log). Kluczowe braki dotyczą dokumentacji art.30, braku formalnego przepływu DSR art.17 dla podmiotów danych niebędących użytkownikami systemu, oraz hardkodowanych kluczy API w kodzie źródłowym — CRITICAL.

---

## FINDINGS

### CRITICAL

#### C-01 — API Keys Hardcoded w Kodzie Źródłowym (RODO art.32 / DSGVO §64 BDSG)
**Lokalizacja:** `db.py:_DEFAULT_API_KEYS` (linie ~43-47)  
**Opis:** Klucze API (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `GOOGLE_API_KEY`) są dosłownie wklejone jako stringi w kod źródłowy Python. Choć są oznaczone `secret=1` w DB (co chroni UI), klucze te są eksponowane w:
- repozytorium git (jeśli commitowane),
- logach budowania,
- procesach inspekcji kodu,
- backupach SQLite (plaintext w tabeli config).

**Wpływ:** Naruszenie art.32 RODO (brak odpowiednich środków technicznych). Potencjalne przejęcie konta API → eksfiltracja danych przetwarzanych przez te API.  
**Rekomendacja:** Usunąć `_DEFAULT_API_KEYS` z kodu; wczytywać wyłącznie z zmiennych środowiskowych (`os.environ`), Vault lub `.env` ignorowanego przez git. Zmienna sekretu w DB powinna być szyfrowana at-rest.  
**Severity:** CRITICAL

---

#### C-02 — Brak Dokumentacji RoPA (RODO art.30)
**Lokalizacja:** Cały projekt — brak `docs/RODO_COMPLIANCE.md`  
**Opis:** Art.30 nakłada obowiązek prowadzenia Rejestru Czynności Przetwarzania (RoPA) na każdego Administratora. System przetwarza dane użytkowników (loginy, sesje, audit_log z IP/username), dane konfiguracyjne API, wyniki agentów. Brak dokumentacji tej czynności stanowi bezpośrednie naruszenie.  
**Rekomendacja:** Wygenerować `docs/RODO_COMPLIANCE.md` (patrz osobny output tego audytu).  
**Severity:** CRITICAL

---

### HIGH

#### H-01 — Brak Formalnego Mechanizmu DSR art.17 dla Podmiotów Zewnętrznych
**Lokalizacja:** `app.py:delete_user()` (linia ~23759)  
**Opis:** Istniejący endpoint `DELETE /api/users/{user_id}` obsługuje kasowanie kont **operatorów** (wyłącznie przez `owner`). System nie posiada:
- publicznego punktu kontaktu DSR (Data Subject Request),
- procedury weryfikacji tożsamości wnioskodawcy,
- mechanizmu kasowania śladów użytkownika z `audit_log` (kasowanie konta nie usuwa wpisów audit_log zawierających `actor=username`),
- SLA odpowiedzi (30 dni zgodnie z RODO art.12.3).

**Uwaga pozytywna:** `delete_user` kasuje `sessions` i `users` — podstawa istnieje.  
**Rekomendacja:** Dodać endpoint DSR `/api/dsr/erasure` z: weryfikacją tożsamości, anonimizacją `audit_log.actor` (nie kasowaniem — dla bezpieczeństwa), procedurą dokumentowaną w RoPA.  
**Severity:** HIGH

---

#### H-02 — AUDIT_LOG_RETENTION_DAYS=365 — Adekwatność dla art.5.1.e
**Lokalizacja:** `db.py:_AUDIT_LOG_RETENTION_DEFAULT = 365`  
**Opis:** 365 dni to wartość rozsądna dla audit_log z punktu widzenia RODO art.5.1.e (storage limitation). Jednakże:
- Jeśli audit_log zawiera dane osobowe (username, IP, zdarzenia sesji), administrator musi udowodnić, że 365 dni jest **niezbędne** dla celów bezpieczeństwa/audytu.
- Brak formalnego uzasadnienia w dokumentacji (DPIA lub notatka bezpieczeństwa).
- Konfigurowalność przez UI (brak dolnego limitu — można ustawić na 0) ryzyko przypadkowego wyzerowania przez admina.

**Rekomendacja:** Dodać dolny limit (np. min 7 dni) w `_get_retention_days`. Dokumentować uzasadnienie 365 dni w RoPA (cel: bezpieczeństwo, detekcja anomalii, forensics).  
**Severity:** HIGH

---

#### H-03 — Brak Szyfrowania Danych w Spoczynku (at-rest encryption)
**Lokalizacja:** `db.py:DB_PATH` = SQLite plaintext  
**Opis:** Baza SQLite przechowuje: hasła (hash argon2/bcrypt — OK), klucze API (plaintext — CRITICAL C-01), sesje, audit_log. Brak szyfrowania na poziomie pliku bazy danych (np. SQLCipher). Na środowiskach z ograniczonym dostępem fizycznym (dev) jest to akceptowalne, ale wymaga formalnego potwierdzenia w art.32 DSGVO.  
**Rekomendacja:** Produkcja: rozważyć SQLCipher lub szyfrowanie tablespace. Dev: akceptowalne z adnotacją w RoPA.  
**Severity:** HIGH (dla produkcji), MEDIUM (dla dev-only)

---

### MEDIUM

#### M-01 — SESSIONS_RETENTION_DAYS=30 — Poprawność Implementacji
**Lokalizacja:** `db.py:prune_sessions()` linie ~1004-1027  
**Opis:** Funkcja kasuje wygasłe sesje RBAC starsze niż 30 dni. Implementacja POPRAWNA: używa `_get_retention_days` z fallback do domyślnej, batched delete (1000 rows/tx), WAL-safe. 30 dni jest adekwatne dla sesji uwierzytelnienia.  
**Uwaga:** Sesje aktywne (nigdy nie wygasłe) NIE są objęte pruningiem — sprawdzić czy istnieje mechanizm timeout sesji.  
**Severity:** MEDIUM

---

#### M-02 — M-08 Backup — Brak Weryfikacji Integralności
**Lokalizacja:** `db.py:_backup_db_before_migration()` linie ~744-777  
**Opis:** Backup WAL-safe działa poprawnie (sqlite3 online backup API). Zawiera guard F-04 (path traversal). Brak:
- weryfikacji checksum backupu,
- automatycznego testu restore,
- szyfrowania backupu.

**Rekomendacja:** Dodać SHA-256 backupu do logu, rozważyć szyfrowanie backupu.  
**Severity:** MEDIUM

---

#### M-03 — AI Act art.14 — Human Oversight (human_gate)
**Lokalizacja:** `db.py:human_gate` table schema (linia ~202), `app.py` pending_gates  
**Opis:** Tabela `human_gate` z polami `mode`, `deferred_until`, `escalated_to`, `auto_approve_key`, `category`, `priority` wskazuje na zaawansowany mechanizm human-in-the-loop. Multi-agent pipeline z human-gate SPEŁNIA art.14 AI Act (human oversight) o ile:
- decyzje automatyczne są możliwe do uchylenia przez człowieka,
- istnieje dokumentacja systemu AI (art.11 AI Act).

**Rekomendacja:** Udokumentować human-gate w kontekście AI Act art.13 (transparentność) i art.14 (human oversight).  
**Severity:** MEDIUM

---

#### M-04 — Event Stream Retention (7 dni) vs. Audit Log (365 dni)
**Lokalizacja:** `db.py:EVENT_STREAM_RETENTION_DAYS = 7`  
**Opis:** Event stream retencja 7 dni — OK dla danych operacyjnych. Jednak jeśli event_stream zawiera dane osobowe (np. treści promptów z danymi użytkowników), 7 dni to poprawna minimalizacja. Wymaga weryfikacji kategorii danych.  
**Severity:** MEDIUM

---

### LOW

#### L-01 — Brak DPO (Data Protection Officer) Designation
**Opis:** Jeśli SYLION będzie produktem komercyjnym lub przetwarza dane na dużą skalę, może być wymagany DPO (art.37 RODO). W kontekście dev pipeline — brak obowiązku, ale warto zaadresować w RoPA.  
**Severity:** LOW

#### L-02 — Brak Privacy Notice dla Użytkowników Dashboardu
**Opis:** Brak widocznej informacji o przetwarzaniu danych (art.13 RODO) dla operatorów logujących się do dashboardu.  
**Rekomendacja:** Dodać footer/modal z informacją o przetwarzaniu.  
**Severity:** LOW

#### L-03 — `prune_audit_log` — Brak Dolnego Limitu Retencji
**Lokalizacja:** `db.py:_get_retention_days()` — brak min guard  
**Opis:** Administrator może ustawić `AUDIT_LOG_RETENTION_DAYS=1` co narusza cel bezpieczeństwa.  
**Rekomendacja:** `max(days, MIN_RETENTION_DAYS)` gdzie `MIN_RETENTION_DAYS = 7`.  
**Severity:** LOW

---

## PODSUMOWANIE

| Severity | Liczba | Kluczowe Findings |
|----------|--------|-------------------|
| CRITICAL | 2 | API Keys hardcoded, Brak RoPA |
| HIGH | 3 | DSR art.17 niekompletny, Retencja bez DPIA, Brak at-rest encryption |
| MEDIUM | 4 | Session timeout, Backup integrity, AI Act doc, Event stream |
| LOW | 3 | DPO, Privacy notice, Min retention guard |

**Ogólna ocena:** System ma solidne fundamenty (WAL backup, RBAC, retention pruning, audit_log). Dwa CRITICAL wymagają natychmiastowej akcji przed produkcją.
