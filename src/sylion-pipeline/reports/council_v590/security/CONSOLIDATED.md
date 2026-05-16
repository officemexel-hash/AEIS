# SYLION v5.9.0 — SKONSOLIDOWANY RAPORT BEZPIECZEŃSTWA
**Security Audit Council | Data: 2026-04-19**  
**Audytorzy:** Opus (OWASP A01/A03/A07), Sonnet (OWASP A02/A04/A06), GPT-5.4 (OWASP A03/A08/A09), Gemini (OWASP A01/A08/A10)  
**Zakres:** SYLION v5.9.0 — `db.py`, `app.py`, `start.py`  
**Kontekst:** Lokalna aplikacja pipeline single-user. `_DEFAULT_API_KEYS` (db.py:1039) — świadoma decyzja dewelopera (C-006), wyłączone z audytu.

---

## TABELA SKONSOLIDOWANYCH FINDINGS

| ID | Severity | CVSS | Tytuł | Plik:Linia | Proponowany Fix | Reviewers |
|----|----------|------|-------|-----------|-----------------|-----------|
| **SEC-001** | CRITICAL | 9.8 | Brak rate limiting na `/api/auth/login` — nieograniczony brute-force | `app.py:370` | Progressive lockout per IP/username; max 10 prób/5min | Opus, Sonnet, GPT-5.4 (3/4) |
| **SEC-002** | CRITICAL | 8.1 | SHA-256 fallback dla password hashing — broken crypto | `db.py:1207` | Hard-fail jeśli argon2-cffi niedostępny; nie akceptuj SHA-256 | Sonnet, GPT-5.4, Gemini (3/4) |
| **SEC-003** | CRITICAL | 7.5 | DoS via Argon2 bez limitu długości hasła (hash-bomb) | `app.py:520, db.py:1230` | Max 128 znaków hasła we wszystkich endpointach przyjmujących password | Sonnet, GPT-5.4 (2/4) |
| **SEC-004** | CRITICAL | 9.1 | SQL f-string injection via `PRAGMA user_version = {version}` | `db.py:817` | Explicit int cast + range assert przed interpolacją | Opus, GPT-5.4 (2/4) |
| **SEC-005** | CRITICAL | 8.4 | Command injection potencjał w `_batch_imports_ok` — brak walidacji nazw importów | `start.py:93` | Regex allowlista `^[a-zA-Z_][a-zA-Z0-9_.]*$` przed budowaniem script | GPT-5.4, Opus (2/4) |
| **SEC-006** | HIGH | 7.5 | SQL injection via dynamiczne WHERE (`where_sql` f-string) w ollama shadow/insights | `app.py:5697,5814` | Jawna allowlista kolumn; zawsze `col = ?` + params | Opus, GPT-5.4, Gemini (3/4) |
| **SEC-007** | HIGH | 7.4 | `SESSION_COOKIE_SECURE` domyślnie `False` — cookie bez Secure flag | `app.py:153` | Domyślnie `True`; wyłączaj tylko dla localhost dev | Sonnet, Gemini (2/4) |
| **SEC-008** | HIGH | 7.2 | Dynamic UPDATE via f-string w wielu endpointach bez allowlisty kolumn | `app.py:664,997,1397,1440,1884,2919,3209,3675,4008,4480` | Jawna allowlista kolumn przed append do `updates` | Opus, GPT-5.4 (2/4) |
| **SEC-009** | HIGH | 7.2 | SSRF/RCE via `sys.path.insert` + dynamic import `health_check` | `app.py:303,353` | `importlib.util.spec_from_file_location` z absolutną hardkodowaną ścieżką | Gemini, GPT-5.4 (2/4) |
| **SEC-010** | HIGH | 7.3 | Słaba polityka haseł — minimum 8 znaków, brak complexity, brak max length | `app.py:520` | Min 12, max 128; complexity check lub NIST blacklist | Opus, Sonnet (2/4) |
| **SEC-011** | HIGH | 7.2 | Path traversal w `_backup_db_before_migration`: `mkdir` przed guard `resolve()` | `db.py:756-762` | `resolve()` przed `mkdir()` i sprawdzenie `is_relative_to` | GPT-5.4 (1/4) |
| **SEC-012** | HIGH | 6.8 | Brak walidacji MIME type przy baseline upload — content-type spoofing | `app.py:1207` | `python-magic` weryfikacja magic bytes po odczycie | Sonnet (1/4) |
| **SEC-013** | HIGH | 6.5 | Privilege escalation: `delete_user` może usunąć ostatniego właściciela → lockout | `app.py:672` | Sprawdzaj licznik ownerów przed usunięciem/degradacją | Gemini (1/4) |
| **SEC-014** | HIGH | 6.5 | Insecure deserialization: `json.loads(bound_agents)` bez limitu rozmiaru/schematu | `app.py:922,971` | Limit 100 elementów; walidacja agent_id regex w Pydantic | Gemini (1/4) |
| **SEC-015** | HIGH | 6.5 | DoS via unbounded `limit` parameter w list endpoints | `app.py:5693` | Ujednolicony `MAX_PAGE_SIZE = 1000` we wszystkich endpointach listujących | Gemini (1/4) |
| **SEC-016** | MEDIUM | 6.5 | Nieudane próby logowania nie są logowane w audit_log (OWASP A09) | `app.py:380` | Loguj `auth.login_failed` przed `raise HTTPException(401)` | GPT-5.4, Opus (2/4) |
| **SEC-017** | MEDIUM | 6.5 | Setup token ujawniany w API response w plaintext | `app.py:485` | Rozważ potwierdzenie PIN z konsoli zamiast ekspozycji przez API | Opus (1/4) |
| **SEC-018** | MEDIUM | 5.9 | Race condition w `prune_audit_log`/`prune_sessions` (TOCTOU między batch commits) | `db.py:984,1016` | `BEGIN EXCLUSIVE` obejmujący całą pętlę prune lub akceptacja "best-effort" z dokumentacją | Opus, Gemini (2/4) |
| **SEC-019** | MEDIUM | 5.9 | Brak weryfikacji integralności lockfile przed `pip install` (supply chain) | `start.py:140` | `pip install --require-hashes` z hashami per pakiet | Opus (1/4) |
| **SEC-020** | MEDIUM | 5.9 | Token sesji: `uuid.uuid4()` zamiast `secrets.token_hex(32)` (sub-CSPRNG entropia) | `app.py:392` | `import secrets; token = secrets.token_hex(32)` | Sonnet, GPT-5.4 (2/4) |
| **SEC-021** | MEDIUM | 5.4 | Brak walidacji `AgentSpec.model` — SSRF przez litellm custom endpoint | `db.py:923` | Allowlista prefiksów modeli w `field_validator` | Sonnet, GPT-5.4 (2/4) |
| **SEC-022** | MEDIUM | 5.3 | `prune_sessions` logika: usuwa po `expires_at + retention_days`, nie `created_at + retention` | `db.py:1016` | Dodaj pruning sesji dla wyłączonych kont; dokumentuj semantykę | GPT-5.4, Gemini (2/4) |
| **SEC-023** | MEDIUM | 5.3 | Brak walidacji górnego limitu `_get_retention_days` — arbitralnie duże wartości | `db.py:959` | `MAX_RETENTION_DAYS = 3650`; odrzucaj wartości > max | GPT-5.4 (1/4) |
| **SEC-024** | MEDIUM | 5.9 | Brak integrity check backupu SQLite przed migracją (`PRAGMA integrity_check`) | `db.py:768` | Po `source_conn.backup(dest_conn)` wykonaj `PRAGMA integrity_check` na dest | GPT-5.4 (1/4) |
| **SEC-025** | MEDIUM | 5.3 | Audit log podatny na wyczyszczenie przez admina (retention = 1 dzień dozwolone) | `db.py:970` | Minimalna retencja 30 dni dla severity='critical'/'high' | Sonnet, GPT-5.4 (2/4) |
| **SEC-026** | MEDIUM | 5.9 | TOCTOU w `_validate_zip_safe`: walidacja i ekstrakcja to dwie osobne operacje na tym samym ZipFile | `app.py:2413` | Buforuj zawartość ZipFile w pamięci podczas walidacji | Gemini (1/4) |
| **SEC-027** | MEDIUM | 4.3 | `_periodic_prune` bez timeout per operację — może zawiesić się na nieskończoność | `app.py:76` | `asyncio.wait_for(asyncio.to_thread(fn), timeout=300.0)` | Gemini (1/4) |
| **SEC-028** | LOW | 3.7 | Informacja o wersji w `/api/version` bez auth — fingerprinting | `app.py:272` | Wymagaj auth lub minimalizuj eksponowane dane | Opus, Sonnet (2/4) |
| **SEC-029** | LOW | 3.7 | Brak security headers (CSP, X-Frame-Options, X-Content-Type-Options) | `app.py:136` | Middleware dodający security headers do wszystkich odpowiedzi | Sonnet, Gemini (2/4) |
| **SEC-030** | LOW | 3.1 | CORS: `allow_methods=["*"]`, `allow_headers=["*"]` — zbyt szerokie | `app.py:142` | Jawna lista dozwolonych methods i headers | Gemini (1/4) |
| **SEC-031** | LOW | 2.9 | Session record ID: `uuid4().hex[:16]` (64-bit) — ryzyko kolizji przy milionach sesji | `app.py:397` | Użyj pełnego `uuid4().hex` lub `secrets.token_hex(16)` | GPT-5.4 (1/4) |
| **SEC-032** | LOW | 2.5 | Log injection via niezabezpieczone exception strings w logger (z agents.yaml) | `db.py:729` | `str(exc).replace('\n', ' ')` przed logowaniem | GPT-5.4 (1/4) |
| **SEC-033** | LOW | 2.1 | Hardkodowana wersja `"v5.8.9"` w nazwie pliku backupu (powinno być v5.9.0) | `db.py:754` | Importuj i używaj `SYLION_VERSION` lub stałej wersji | Opus (1/4) |
| **SEC-034** | LOW | 2.6 | Brak sliding window dla sesji — aktywny user wylogowany po 7 dniach od logowania | `app.py:152` | Odśwież `expires_at` przy każdym aktywnym użyciu sesji | Gemini (1/4) |
| **SEC-035** | LOW | 3.1 | Absoluta ścieżka dyskowa ujawniana w upload API response (`disk_path`) | `app.py:2516` | Usuń `disk_path` z response lub zwróć względną ścieżkę | Sonnet (1/4) |

---

## PODSUMOWANIE STATYSTYCZNE

| Severity | Liczba Findings | % Całości |
|----------|----------------|-----------|
| CRITICAL | 5 | 14.3% |
| HIGH | 10 | 28.6% |
| MEDIUM | 12 | 34.3% |
| LOW | 8 | 22.9% |
| **TOTAL** | **35** | **100%** |

### Findings wg kategorii OWASP Top 10

| OWASP Kategoria | Findings |
|----------------|---------|
| A01 — Broken Access Control | SEC-013, SEC-014 |
| A02 — Cryptographic Failures | SEC-002, SEC-003, SEC-010, SEC-020 |
| A03 — Injection (SQL/Command) | SEC-004, SEC-005, SEC-006, SEC-008, SEC-032 |
| A04 — Insecure Design | SEC-016, SEC-019, SEC-025 |
| A05 — Security Misconfiguration | SEC-007, SEC-028, SEC-029, SEC-030 |
| A06 — Vulnerable Components | SEC-002, SEC-019 |
| A07 — Broken Auth | SEC-001, SEC-020, SEC-031, SEC-034 |
| A08 — Software/Data Integrity | SEC-011, SEC-024, SEC-026 |
| A09 — Logging & Monitoring | SEC-016, SEC-017, SEC-033 |
| A10 — SSRF/RCE | SEC-009, SEC-021 |

### Findings wg liczby reviewerów (consensus)

| Reviewers | Findings | Severity Impact |
|-----------|---------|----------------|
| 3/4 modeli | SEC-001, SEC-002, SEC-006 | 2 CRITICAL + 1 HIGH → Najwyższy priorytet |
| 2/4 modeli | SEC-003, SEC-007, SEC-008, SEC-010, SEC-016, SEC-018, SEC-020, SEC-021, SEC-022, SEC-025, SEC-028, SEC-029 | Mix HIGH/MEDIUM |
| 1/4 modeli | Pozostałe (SEC-004, SEC-005, SEC-009, etc.) | Specjalistyczne perspektywy |

---

## PRIORYTETY NAPRAWCZE

### Natychmiastowe (przed następnym release)
1. **SEC-001** — Rate limiting na login (3/4 consensus)
2. **SEC-002** — SHA-256 hard-fail (3/4 consensus)  
3. **SEC-003** — Max 128 znaków hasła (DoS)
4. **SEC-006** — WHERE SQL allowlista (3/4 consensus)

### Krótkoterminowe (sprint)
5. **SEC-004** — PRAGMA version int cast
6. **SEC-005** — Import name regex validation
7. **SEC-007** — Cookie Secure flag domyślnie True
8. **SEC-009** — importlib zamiast sys.path.insert
9. **SEC-010** — Password policy min 12 chars

### Długoterminowe (technical debt)
- SEC-016: Audit log failed logins
- SEC-019: Supply chain hash verification
- SEC-029: Security headers middleware
- SEC-021: AgentSpec model allowlista

---

## WYŁĄCZONE Z AUDYTU

- `_DEFAULT_API_KEYS` w `db.py:1039` — świadoma decyzja developera (C-006 constraint); klucze plaintext w kodzie są akceptowalnym kompromisem dla single-user lokalnej aplikacji.

---

*SYLION v5.9.0 Security Audit Council | 4 pentesterzy | 35 findings łącznie*
