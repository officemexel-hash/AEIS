# SYLION v5.9.1 — Security Audit OWASP Top 10 2021

**Data audytu:** 2026-04-19  
**Wersja:** 5.9.1 (Breakthrough — 18 Skills Audit)  
**Audytor:** mega_audit / security_audit subagent  
**Pliki przeanalizowane:**
- `dashboard/app.py` (7 373 linii)
- `dashboard/db.py` (2 859 linii)
- `orchestrator.py` (3 539 linii)
- `device_harness.py`, `config.py`, `requirements-lock.txt`, `CHECKSUMS.sha256`, `.env.example`

---

## EXECUTIVE SUMMARY

| Metryka | Wartość |
|---------|---------|
| Findings ogółem | **18** |
| CRITICAL (CVSS ≥ 9.0) | **1** |
| HIGH (CVSS 7.0–8.9) | **6** |
| MEDIUM (CVSS 4.0–6.9) | **8** |
| LOW (CVSS < 4.0) | **3** |
| **Overall Security Score** | **42 / 100** |

---

## FINDINGS TABLE — WSZYSTKIE 18

| ID | OWASP | Severity | CVSS 3.1 | CWE | Plik:linia | Tytuł |
|----|-------|----------|----------|-----|------------|-------|
| F-01 | A02 | **CRITICAL** | 9.1 | CWE-798 | db.py:1144–1148 | Hardcoded API keys w kodzie źródłowym |
| F-02 | A01 | **HIGH** | 8.1 | CWE-352 | app.py:1828 | CSRF walidowany tylko w 1 z ~50 mutujących endpointów |
| F-03 | A06 | **HIGH** | 7.5 | CWE-1395 | requirements-lock.txt | aiohttp 3.13.3 — 10 CVE HIGH (transitive, nieprzypięta) |
| F-04 | A08 | **HIGH** | 7.5 | CWE-345 | CHECKSUMS.sha256 | 8 plików ze statusem FAILED (SHA256SUMS.txt), CHECKSUMS.sha256 nie pokrywa 58 zmodyfikowanych plików |
| F-05 | A10 | **HIGH** | 7.2 | CWE-918 | app.py:4558–4572 | SSRF: brak walidacji base_url przy zapisie do DB (`PUT /api/models/{id}`) |
| F-06 | A03 | **HIGH** | 7.5 | CWE-78 | app.py:3162 | Niebezpieczny `git clone` — brak walidacji parametru `branch`, błąd stderr ujawniony w odpowiedzi |
| F-07 | A02 | **HIGH** | 7.3 | CWE-312 | app.py:155–194 | Nieszyfrowane backupy SQLite z plaintekstowymi kluczami API |
| F-08 | A04 | **MEDIUM** | 6.5 | CWE-807 | app.py:698 | Rate limiter bazuje na `request.client.host` — nieskuteczny za reverse proxy |
| F-09 | A01 | **MEDIUM** | 6.5 | CWE-352 | app.py:1828 | CSRF warunek `if expected_csrf` — omijany gdy `_csrf_tokens` jest pusty (po restarcie) |
| F-10 | A05 | **MEDIUM** | 6.3 | CWE-200 | app.py:3167–3168 | `git clone failed: {e.stderr.decode()[:200]}` — stderr ujawniony klientowi |
| F-11 | A09 | **MEDIUM** | 6.1 | CWE-778 | app.py (global) | Brak correlation ID / X-Request-ID w logach i odpowiedziach API |
| F-12 | A02 | **MEDIUM** | 5.9 | CWE-614 | app.py:786, 811 | `delete_cookie` bez atrybutów `secure`/`httponly`/`samesite` — cookie może nie zostać usunięte |
| F-13 | A05 | **MEDIUM** | 5.5 | CWE-200 | app.py:628 | `issues: [], error: str(exc)` — wewnętrzny wyjątek ujawniany w health endpoint |
| F-14 | A02 | **MEDIUM** | 5.5 | CWE-312 | app.py:4708 | Google API Key w URL query string zamiast nagłówka Authorization |
| F-15 | A02 | **MEDIUM** | 5.3 | CWE-916 | db.py:1413–1416 | SHA-256 legacy hashes nadal akceptowane — brak wymuszonego upgradu na starcie |
| F-16 | A07 | **LOW** | 3.7 | CWE-613 | app.py:327 | Sesja 7-dniowa bez mechanizmu idle timeout / absolute timeout |
| F-17 | A07 | **LOW** | 3.5 | app.py:336 | CWE-613 | `_csrf_tokens` in-memory — utrata po restarcie serwera, edge-case bypass |
| F-18 | A09 | **LOW** | 3.1 | CWE-223 | db.py:66 | Audit log retencja 365 dni — brak alertów na anomalie; brak monitoringu |

---

## A01 — BROKEN ACCESS CONTROL

**Ocena: MEDIUM-HIGH (score: 55/100)**

Implementacja RBAC (role: `owner`, `operator`, `security`, `readonly`) jest spójna. Wszystkie endpointy `/api/users/*` wymagają roli `owner`. `require_role()` i `require_auth()` są stosowane konsekwentnie. Nie stwierdzono IDOR ani pominięcia autoryzacji w ścieżkach produkcyjnych.

**Problemy:**

### F-02 — CSRF walidowany tylko w 1 endpoincie (HIGH, CVSS 8.1)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | 8.1 (AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N) |
| **CWE** | CWE-352 Cross-Site Request Forgery |
| **Plik:linia** | `dashboard/app.py:1821–1828` |

**Opis:** CSRF token (double-submit pattern) implementowany jest wyłącznie w `POST /api/baselines/upload` (linia 1828). Pozostałe ~50 endpointów mutujących (`/api/config/{key}`, `/api/users`, `/api/agents`, `/api/human-gate`, `/api/models`, `/api/prompts` itd.) **nie walidują X-CSRF-Token**.

Warunek `if expected_csrf and not hmac.compare_digest(...)` powoduje, że gdy `_csrf_tokens.get(session_token)` zwróci `None` (restart serwera + aktywne cookie), walidacja jest **pominięta** — atak CSRF jest możliwy.

**PoC:** Formularz HTML `POST /api/config/OPENAI_API_KEY` z autosubmit — bez CSRF header żądanie akceptowane na ~50 endpointach mutujących.

**Remediacja:** Wydzielić `_require_csrf(request)` (fail-closed: brak tokenu = 403) i wywołać we wszystkich POST/PUT/DELETE handlerach. Usuć warunek `if expected_csrf and ...` → zawsze walidować.

---

### F-09 — CSRF bypass po restarcie (MEDIUM, CVSS 6.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 6.5 (AV:N/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:N) |
| **CWE** | CWE-352 |
| **Plik:linia** | `dashboard/app.py:336, 1155–1159` |

**Opis:** `_csrf_tokens` to in-memory dict (`app.py:336`). Po restarcie serwera jest pusty — istniejące sesje cookie nie mają wpisu → `expected_csrf = None` → warunek `if expected_csrf and not ...` = False → CSRF walidacja pominięta.

**Remediacja:** Przenieść `_csrf_tokens` z in-memory dict do kolumny `csrf_token` w tabeli `sessions` SQLite.

---

## A02 — CRYPTOGRAPHIC FAILURES

**Ocena: MEDIUM (score: 50/100)**

Pozytywne: argon2id zaimplementowany prawidłowo (memory_cost=65536, time_cost=3), SHA-256 tylko jako legacy read-only z automatycznym rehashingiem. Cookiesy: `httponly=True`, `secure=SESSION_COOKIE_SECURE`, `samesite="strict"`. HSTS i TLS obsługiwane przez reverse proxy (poza zakresem kodu).

**Problemy:**

### F-07 — Nieszyfrowane backupy SQLite z kluczami API (HIGH, CVSS 7.3)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | 7.3 (AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N) |
| **CWE** | CWE-312 Cleartext Storage of Sensitive Information |
| **Plik:linia** | `dashboard/app.py:156–194` |

**Opis:** Codzienny backup SQLite zapisywany do `~/sylion/sylion.db.daily.YYYY-MM-DD.sqlite3` bez szyfrowania. Baza zawiera plaintekstowe klucze API (tabela `config`, `secret=1`), tokeny sesji i dane RODO.

**PoC:** `sqlite3 ~/sylion/sylion.db.daily.2026-04-19.sqlite3 "SELECT key,value FROM config WHERE secret=1"`

**Remediacja:**
```bash
# Backup z szyfrowaniem GPG:
gpg --symmetric --cipher-algo AES256 -o backup.sqlite3.gpg backup.sqlite3
shred -u backup.sqlite3  # Usuń nieszyfrowaną kopię
```

---

### F-12 — `delete_cookie` bez secure/httponly (MEDIUM, CVSS 5.9)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 5.9 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N) |
| **CWE** | CWE-614 Sensitive Cookie in HTTPS Session Without Secure Attribute |
| **Plik:linia** | `dashboard/app.py:786, 811` |

**Opis:** `resp.delete_cookie("sylion_session")` bez parametrów. Starlette wysyła `Set-Cookie: sylion_session=; Max-Age=0` bez flagi `Secure`, co w Firefox ≤ 109 nie kasuje poprawnie cookie ustawionego z `Secure=True`.

**Remediacja:** `resp.delete_cookie("sylion_session", httponly=True, secure=SESSION_COOKIE_SECURE, samesite="strict", path="/")` (2 miejsca: linie 786, 811).

---

### F-14 — Google API Key w URL query string (MEDIUM, CVSS 5.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 5.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N) |
| **CWE** | CWE-312 |
| **Plik:linia** | `dashboard/app.py:4708` |

**Opis:** `httpx.post(f"...googleapis.com/v1beta/models/...?key={key}", ...)`. Klucz API pojawia się w URL, logach proxy/CDN, access logach serwera, headerze `Referer`.

**Remediacja:** Użyć nagłówka `x-goog-api-key: {key}` zamiast `?key={key}` w URL.

---

### F-15 — SHA-256 legacy hashes bez wymuszonego upgradu (MEDIUM, CVSS 5.3)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 5.3 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N) |
| **CWE** | CWE-916 Use of Password Hash With Insufficient Computational Effort |
| **Plik:linia** | `dashboard/db.py:1413–1416` |

**Opis:** `verify_password()` akceptuje SHA-256 (bez soli, bez key stretching). Rehash następuje dopiero przy logowaniu — użytkownicy nielogujący się przez długi czas mają słabe hashe w DB. Brak log ostrzegawczego przy wykryciu SHA-256 hash.

**Remediacja:** Dodać migrację DB wymuszającą ustawienie `must_change_password=1` dla wszystkich kont z SHA-256 hashem. Logować `WARNING` przy każdym logowaniu z SHA-256.

---

## A03 — INJECTION

**Ocena: MEDIUM-LOW (score: 65/100)**

SQL injection: **brak** — parametryzowane zapytania (`?`) stosowane konsekwentnie. Dynamiczne SQL (`f"UPDATE users SET {', '.join(updates)} WHERE id=?"`) budowane wyłącznie z hardcoded literałów, nie z input użytkownika. SafeCommandRunner w `device_harness.py` stosuje shlex.quote + allowlist.

**Problemy:**

### F-06 — `git clone` bez walidacji parametru `branch` + stderr leak (HIGH, CVSS 7.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | 7.5 (AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N) |
| **CWE** | CWE-78 OS Command Injection (partial), CWE-200 Information Exposure |
| **Plik:linia** | `dashboard/app.py:3134–3168` |

**Opis:** `GitUploadRequest.branch: str = "main"` bez regex/allowlist — trafia bezpośrednio do `["git", "clone", "--branch", req.branch, ...]`. Złośliwa wartość np. `--upload-pack=<cmd>` jest interpretowana przez git jako opcja CLI (git option injection, CVE-class). Ponadto `e.stderr.decode()[:200]` jest zwracany klientowi, ujawniając ścieżki systemowe i wersję git.

**PoC:** `{"branch": "--upload-pack=touch /tmp/pwned"}` → git przetwarza `--upload-pack` jako option.

**Remediacja:** Walidacja: `re.match(r'^[a-zA-Z0-9._/\-]{1,100}$', req.branch)` else 400. Zastąpić `e.stderr.decode()[:200]` generycznym komunikatem.

---

## A04 — INSECURE DESIGN

**Ocena: MEDIUM (score: 58/100)**

Pozytywne: setup_token jest jednorazowy (DELETE z DB po użyciu), przechowywany jako SHA-256 hash, generowany przez `secrets.token_urlsafe(32)`. Admin bootstrap flow — prawidłowy (BEGIN IMMEDIATE + threading.Lock).

**Problemy:**

### F-08 — Rate limiter nieefektywny za reverse proxy (MEDIUM, CVSS 6.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 6.5 (AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:N) |
| **CWE** | CWE-807 Reliance on Untrusted Inputs in a Security Decision |
| **Plik:linia** | `dashboard/app.py:698` |

**Opis:** Rate limiter logowania (`FIX-01`) bazuje na `request.client.host` — bezpośrednim IP TCP. Przy wdrożeniu za nginx/Caddy, `request.client.host = 127.0.0.1` (IP proxy) dla WSZYSTKICH klientów. Lockout 5 prób / 5 minut jest nieefektywny — atakujący może wykonać nieograniczony brute force haseł.

**PoC:** 1000 równoległych requestów przez proxy — każdy widoczny jako 127.0.0.1, lockout nigdy nie jest aktywowany.

**Remediacja:** `uvicorn.run(..., proxy_headers=True, forwarded_allow_ips="127.0.0.1")` w `start.py`. W login handler: `ip = request.headers.get("X-Real-IP") or request.client.host`.

---

## A05 — SECURITY MISCONFIGURATION

**Ocena: MEDIUM (score: 52/100)**

Pozytywne: brak domyślnego hasła admina, sesja wymaga setup_token. Global exception handler (`P-ERR-4`) loguje pełny traceback do pliku, zwraca generyczne `"Internal server error"` klientowi.

**Problemy:**

### F-10 — stderr git clone ujawniony klientowi (MEDIUM, CVSS 6.3)

Patrz F-06 — stderr `e.stderr.decode()[:200]` zwracany w `HTTPException(400, ...)` ujawnia wewnętrzne ścieżki systemowe, wersję git, konfigurację.

---

### F-13 — Wyjątek ujawniony w health endpoint (MEDIUM, CVSS 5.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 5.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **CWE** | CWE-200 Exposure of Sensitive Information |
| **Plik:linia** | `dashboard/app.py:628` |

**Opis:** Endpoint `/api/health` (dostępny bez auth) zwraca `{"issues": [], "error": str(exc)}` przy błędzie health check. `str(exc)` może zawierać stack trace, ścieżki do plików, konfigurację SQLite.

**Remediacja:** Zwrócić generyczny komunikat: `{"ok": False, "error": "Health check failed — see server logs"}`.

**Brak security headers:** Żadne security headers nie są ustawiane przez middleware: brak `X-Frame-Options`, `X-Content-Type-Options`, `Content-Security-Policy`, `Referrer-Policy`. Dodać przez middleware FastAPI.

---

## A06 — VULNERABLE AND OUTDATED COMPONENTS

**Ocena: HIGH (score: 45/100)**

Patched w v5.9.1: starlette (CVE-2025-62727), python-multipart (CVE-2026-24486), pypdf (22 CVE), litellm (CVE-2026-35030 CRITICAL). Wynik pip-audit na requirements-lock.txt: `No known vulnerabilities found`.

**Problemy:**

### F-03 — aiohttp 3.13.3 — 10 CVE HIGH, transitive, nieprzypięta (HIGH, CVSS 7.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | do 9.1 per CVE (łączna CVSS finding: 7.5) |
| **CWE** | CWE-1395 Dependency on Vulnerable Third-Party Component |
| **Plik:linia** | `requirements-lock.txt` (brak wpisu aiohttp), `.venv: aiohttp==3.13.3` |

**Opis:** `aiohttp` jest zależnością przechodnią `litellm==1.83.0`, zainstalowaną jako `3.13.3`. **Nie jest przypięta** w `requirements-lock.txt`. Wersja 3.13.3 zawiera 10 CVE HIGH (CVE-2026-34513 do CVE-2026-34525), obejmujących request smuggling, SSRF oraz DoS przez litellm HTTP client.

**PoC (SSRF via aiohttp CVE-2026-34519):**
Exploitacja przez LLM API proxy call — aiohttp przetwarza odpowiedź zawierającą spreparowane nagłówki HTTP, przekierowując żądanie do wewnętrznego IP.

**Remediacja:**
```
# Dodać do requirements-lock.txt:
aiohttp==3.13.4  # Security fix: 10 CVE HIGH in 3.13.3
```

---

## A07 — IDENTIFICATION AND AUTHENTICATION FAILURES

**Ocena: MEDIUM (score: 55/100)**

Pozytywne: rate limit 5 prób / 5 min (lockout 10 min), argon2id, session invalidation po zmianie hasła (`DELETE FROM sessions WHERE user_id=?`), opaque 256-bit session tokens. Brak domyślnych credentials. Setup token jednorazowy.

**Problemy:**

### F-01 — Hardcoded API keys w kodzie źródłowym (CRITICAL, CVSS 9.1)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | **CRITICAL** |
| **CVSS 3.1** | 9.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N) |
| **CWE** | CWE-798 Use of Hard-coded Credentials |
| **Plik:linia** | `dashboard/db.py:1144–1148` |

**Opis:** Słownik `_DEFAULT_API_KEYS` zawiera aktywne klucze produkcyjne czterech providerów AI:
- `OPENAI_API_KEY`: `sk-proj-JwEw64A9...` (pełna wartość, format poprawny)
- `ANTHROPIC_API_KEY`: `sk-ant-api03-rV-H9Ch...` (pełna wartość)
- `PERPLEXITY_API_KEY`: `pplx-o2ZYm41s...` (pełna wartość)
- `GOOGLE_API_KEY`: `AQ.Ab8RN6...` (pełna wartość)

Klucze są seedowane do tabeli `config` przy każdym `init_db()` przez `_seed_defaults()`. Każda nowa instalacja lub test dostaje te klucze automatycznie. Każdy z dostępem do repozytorium Git lub deploymentu ma dostęp do kluczy produkcyjnych.

**PoC:**
```bash
# Wystarczy otworzyć plik:
cat dashboard/db.py | grep -A5 "_DEFAULT_API_KEYS"
# → Pełne klucze API
```

**Remediacja (wymaga akcji użytkownika — rotacja kluczy PRZED wdrożeniem):**
1. Revoke wszystkie 4 klucze w panelach OpenAI / Anthropic / Perplexity / Google AI Studio
2. Zastąpić w kodzie:
```python
_DEFAULT_API_KEYS = {
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
    "PERPLEXITY_API_KEY": "",
    "GOOGLE_API_KEY": "",
}
```
3. Wymagać konfiguracji przez UI lub `.env`

---

### F-16 — Session 7-dniowy bez idle timeout (LOW, CVSS 3.7)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | LOW |
| **CVSS 3.1** | 3.7 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **CWE** | CWE-613 Insufficient Session Expiration |
| **Plik:linia** | `dashboard/app.py:327` |

**Opis:** `SESSION_DURATION = 86400 * 7` — stały 7-dniowy TTL bez idle timeout. Porzucona sesja pozostaje aktywna przez tydzień.

**Remediacja:** Dodać kolumnę `last_active_at` w tabeli `sessions`, unieważniać sesje nieaktywne przez np. 8h.

---

### F-17 — `_csrf_tokens` in-memory — utrata po restarcie (LOW, CVSS 3.5)

Patrz F-09 — pełny opis. Severity LOW (wymaga aktywnej sesji cookie + restartu serwera).

---

## A08 — SOFTWARE AND DATA INTEGRITY FAILURES

**Ocena: LOW (score: 35/100)**

Brak podpisywania pakietów (`pip-compile` bez `--generate-hashes`). CI/CD sprawdza manifest, ale nie weryfikuje sum kontrolnych przy każdym deployu.

**Problemy:**

### F-04 — CHECKSUMS.sha256 — 8 FAILs w SHA256SUMS.txt (HIGH, CVSS 7.5)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | 7.5 (AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:N) |
| **CWE** | CWE-345 Insufficient Verification of Data Authenticity |
| **Plik:linia** | `SHA256SUMS.txt` (root), `CHECKSUMS.sha256` (sylion-pipeline/) |

**Opis:** Weryfikacja sumy kontrolnej zwraca 8 plików FAILED:
```
./sylion-pipeline/.hypothesis/unicode_data/15.0.0/codec-utf-8.json.gz: FAILED
./sylion-pipeline/.pytest_cache/v/cache/nodeids: FAILED
./sylion-pipeline/docs/adr/ADR-0020-pydantic-migration.md: FAILED
./sylion-pipeline/docs/adr/ADR-0021-rodo-retention.md: FAILED
./sylion-pipeline/docs/adr/ADR-0022-pip-compile.md: FAILED
./sylion-pipeline/docs/adr/ADR-0023-agent-id-reset.md: FAILED
./sylion-pipeline/docs/adr/ADR-0024-sql-ollama-whitelist.md: FAILED
./sylion-pipeline/results/hallucinations.jsonl: FAILED
```

`CHECKSUMS.sha256` (wewnętrzny) nie pokrywa plików zmodyfikowanych w v5.9.1, w tym krytycznych `app.py`, `db.py`. Mechanizm integralności jest faktycznie **niefunkcjonalny** dla bieżącej wersji.

**PoC:** Backdoor wprowadzony do `dashboard/app.py` nie zostałby wykryty przez `sha256sum -c CHECKSUMS.sha256`.

**Remediacja:** Po freeze v5.9.1: `cd sylion-pipeline && sha256sum $(git ls-files) > CHECKSUMS.sha256`. Dodać krok weryfikacji checksums do CI/CD jako gate blokujący deploy.

---

## A09 — SECURITY LOGGING AND MONITORING FAILURES

**Ocena: MEDIUM (score: 55/100)**

Pozytywne: `audit_log()` rejestruje kluczowe zdarzenia (login, logout, user.create, config.update, rodo.erasure). Rotujący file handler dostępny (`SYLION_LOG_FILE=1`). Retencja audit_log: 365 dni (konfigurowalny). Structured JSON logging dostępny (`SYLION_LOG_JSON=1`).

**Problemy:**

### F-11 — Brak correlation ID / X-Request-ID (MEDIUM, CVSS 6.1)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | MEDIUM |
| **CVSS 3.1** | 6.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H) - wpływ na obserwowalność |
| **CWE** | CWE-778 Insufficient Logging |
| **Plik:linia** | `dashboard/app.py` (middleware, brak implementacji) |

**Opis:** Żądania HTTP nie mają przypisywanego correlation ID. Logi z różnych middleware (latency, audit, error) nie są powiązane w jednym request trace. Przy incydencie bezpieczeństwa niemożliwa jest korelacja logów: które żądanie HTTP wywołało który wpis audit_log?

**Remediacja:**
```python
@app.middleware("http")
async def inject_request_id(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    # Dodać do każdego logu: extra={"request_id": req_id}
    return response
```

---

### F-18 — Brak alertów na anomalie w audit logu (LOW, CVSS 3.1)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | LOW |
| **CVSS 3.1** | 3.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N) |
| **CWE** | CWE-223 Omission of Security-relevant Information |
| **Plik:linia** | `dashboard/db.py:66` |

**Opis:** Audit log działa (retencja 365d), ale brak mechanizmów alertowania na anomalie: masowe próby logowania z różnych IP, wielokrotne `config.update` dla API keys, masowe `user.delete`. Brak metryki `login_failure_rate`.

**Remediacja:** Dodać `GET /api/security/anomalies` agregujący audit_log pod kątem podejrzanych wzorców. Zintegrować z Prometheus (ekspozycja przez istniejący `GET /api/metrics`).

---

## A10 — SERVER-SIDE REQUEST FORGERY (SSRF)

**Ocena: MEDIUM (score: 58/100)**

`_probe_ollama()` ma SSRF protection (`ipaddress.ip_address` + allowlist localhost/private). Połączenia orchestratora do dashboardu: hardcoded `http://127.0.0.1:{port}` — bezpieczne.

**Problemy:**

### F-05 — SSRF: brak walidacji `base_url` przy zapisie do DB (HIGH, CVSS 7.2)

| Atrybut | Wartość |
|---------|---------|
| **Severity** | HIGH |
| **CVSS 3.1** | 7.2 (AV:N/AC:H/PR:H/UI:N/S:C/C:H/I:L/A:N) |
| **CWE** | CWE-918 Server-Side Request Forgery |
| **Plik:linia** | `dashboard/app.py:4558–4572` (`PUT /api/models/{id}`) |

**Opis:** Operator (`operator` role) może ustawić `base_url` dla modelu Ollama przez `PUT /api/models/{id}`. Przy zapisie sprawdzane jest tylko `scheme in (http, https)` i `hostname != None` — brak ograniczenia do localhost/sieci prywatnych. Wartość jest następnie użyta przez `_probe_ollama()` i `httpx.post()`.

`_probe_ollama()` ma wbudowaną ochronę SSRF, ale inne ścieżki kodu (linie 7200–7285) wywołują `httpx.post` na `base_url` odczytanym z DB **bez przejścia przez `_probe_ollama`**, przy zapytaniach LLM.

**PoC:**
```json
PUT /api/models/ollama-1
{"base_url": "http://192.168.8.1:80"}
```
Kolejne wywołanie LLM przez orchestrator wyśle żądanie HTTP do routera wewnętrznego (192.168.8.1 jest seedowany jako DEVICE_ROUTER_HOST).

**Remediacja:**
```python
def _validate_base_url_for_model(url: str) -> None:
    from urllib.parse import urlparse
    import ipaddress
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "Invalid scheme")
    host = parsed.hostname
    try:
        addr = ipaddress.ip_address(host)
        if not (addr.is_private or addr.is_loopback):
            raise HTTPException(400, "Only private/localhost URLs allowed for model base_url")
    except ValueError:
        ALLOWED_HOSTS = {"localhost", "127.0.0.1", "::1"}
        if host not in ALLOWED_HOSTS:
            raise HTTPException(400, f"Host {host!r} not in allowed list")
```

---

## PODSUMOWANIE PER KATEGORIA OWASP

| Kategoria | Score | Najpoważniejszy Finding | Status |
|-----------|-------|------------------------|--------|
| A01 Broken Access Control | 55/100 | F-02 CSRF ~50 endpointów | OPEN |
| A02 Cryptographic Failures | 50/100 | F-07 Nieszyfrowane backupy | OPEN |
| A03 Injection | 65/100 | F-06 Git branch injection | OPEN |
| A04 Insecure Design | 58/100 | F-08 Rate limit bypass przez proxy | OPEN |
| A05 Security Misconfiguration | 52/100 | F-10 stderr leak, brak security headers | OPEN |
| A06 Vulnerable Components | 45/100 | F-03 aiohttp 10 CVE HIGH | OPEN |
| A07 Auth Failures | 55/100 | F-01 Hardcoded API keys CRITICAL | OPEN |
| A08 Software Integrity | 35/100 | F-04 CHECKSUMS 8 FAILED | OPEN |
| A09 Logging/Monitoring | 55/100 | F-11 Brak correlation ID | OPEN |
| A10 SSRF | 58/100 | F-05 SSRF via model base_url | OPEN |

**Overall Security Score: 42/100**

---

## TOP 5 PRIORYTETÓW (ACTION ITEMS)

### P0 — NATYCHMIASTOWE (dziś)

**1. Rotacja i usunięcie hardcoded API keys (F-01, CRITICAL)**  
Pliki: `db.py:1144–1148`  
Akcja: Revoke kluczy w panelach OpenAI/Anthropic/Perplexity/Google → wyzerować `_DEFAULT_API_KEYS` → commit → deploy.  
Ryzyko zwłoki: Każda godzina = potencjalny nieautoryzowany koszt LLM API.

**2. Pinning aiohttp ≥ 3.13.4 (F-03, HIGH)**  
Pliki: `requirements-lock.txt`  
Akcja: Dodać `aiohttp==3.13.4` do lock file → `pip install -r requirements-lock.txt` → restart.  
Ryzyko zwłoki: 10 CVE HIGH w aktywnej transitive dependency.

### P1 — KRÓTKOTERMINOWE (1 tydzień)

**3. CSRF protection na wszystkich mutujących endpointach (F-02, HIGH)**  
Pliki: `app.py` (~50 handlerów)  
Akcja: Wydzielić helper `_require_csrf()`, wywołać we wszystkich POST/PUT/DELETE. Przenieść CSRF token do SQLite.

**4. Regeneracja CHECKSUMS.sha256 + integracja CI (F-04, HIGH)**  
Pliki: `CHECKSUMS.sha256`, `SHA256SUMS.txt`, `.github/workflows/`  
Akcja: Po freeze kodu v5.9.1 → regeneracja sum → dodanie kroku weryfikacji do CI jako gate blokujący deploy.

**5. SSRF validation w `PUT /api/models/{id}` (F-05, HIGH)**  
Pliki: `app.py:4558–4572`  
Akcja: Przenieść logikę z `_probe_ollama` do walidacji przy zapisie `base_url`.

### P2 — ŚREDNIOTERMINOWE (1 miesiąc)

- F-06: Walidacja `branch` regex + generyczny komunikat błędu
- F-07: Szyfrowanie backupów GPG lub eliminacja plaintekstu z DB
- F-08: `proxy_headers=True` + `forwarded_allow_ips` w uvicorn start.py
- F-11: Middleware correlation ID / X-Request-ID
- F-12: `delete_cookie` z pełnymi atrybutami security
- F-14: Google API key w nagłówku zamiast URL

### P3 — DŁUGOTERMINOWE

- F-13: Health endpoint bez ujawniania wyjątków
- F-15: Migracja wymuszająca rehash SHA-256 → argon2id
- F-16: Idle timeout dla sesji
- F-18: Alerty anomalii w audit logu
- Security headers middleware (X-Frame-Options, X-Content-Type-Options, CSP)

---

## POZYTYWNE USTALENIA

| Obszar | Ocena |
|--------|-------|
| SQL injection | Brak — parametryzowane zapytania we wszystkich miejscach ✅ |
| SafeCommandRunner allowlist | Poprawna — shlex.quote + allowlist komend ADB/SSH ✅ |
| Setup token — one-shot | DELETE z DB po użyciu, hash SHA-256 w DB ✅ |
| Argon2id parametry | Zgodne z OWASP (memory_cost=65536, time_cost=3) ✅ |
| CVE dependencies (patched) | starlette, multipart, pypdf, litellm — wszystkie patched ✅ |
| Domyślne credentials | Brak domyślnego hasła admina ✅ |
| Session tokens | 256-bit opaque UUID4, przechowywane w DB ✅ |
| Global exception handler | `P-ERR-4` — pełny traceback do logów, generyczny 500 do klienta ✅ |
| CORS | Ograniczony do localhost:{port} ✅ |
| Session invalidation | Po zmianie hasła — DELETE wszystkich sesji ✅ |

---

## APPENDIX — CVSS SCORING SUMMARY

| ID | Score | Vector |
|----|-------|--------|
| F-01 | **9.1** | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N |
| F-02 | 8.1 | AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:N |
| F-03 | 7.5 | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:H |
| F-04 | 7.5 | AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:N |
| F-05 | 7.2 | AV:N/AC:H/PR:H/UI:N/S:C/C:H/I:L/A:N |
| F-06 | 7.5 | AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:N |
| F-07 | 7.3 | AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N |
| F-08 | 6.5 | AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:N |
| F-09 | 6.5 | AV:N/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:N |
| F-10 | 6.3 | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N |
| F-11 | 6.1 | AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H |
| F-12 | 5.9 | AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N |
| F-13 | 5.5 | AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N |
| F-14 | 5.5 | AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N |
| F-15 | 5.3 | AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N |
| F-16 | 3.7 | AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N |
| F-17 | 3.5 | AV:N/AC:H/PR:L/UI:N/S:U/C:N/I:L/A:N |
| F-18 | 3.1 | AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N |

---

*Raport wygenerowany przez security-audit subagent (mega_audit/security_audit). Metodologia: OWASP Top 10 2021, CVSS v3.1, manual code review + grep analysis. Data: 2026-04-19.*
