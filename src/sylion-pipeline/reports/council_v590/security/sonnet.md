# SYLION v5.9.0 — Security Audit Report: Sonnet Perspective
**Focus: Cryptographic Failures (OWASP A02) + Vulnerable Components (OWASP A06) + Insecure Design (OWASP A04)**
**Date: 2026-04-19 | Reviewer: Sonnet**

---

## CRITICAL

### F-SON-001 — DoS via Argon2 bez limitu długości hasła (ReDoS/Hash-Bomb)
**Severity:** CRITICAL  
**CVSS:** 7.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H)  
**File:Linia:** `app.py:520, db.py:1230`

**Opis:**
Endpoint `/api/auth/login` i `/api/auth/setup` walidują hasło z minimalną długością 8 znaków, ale **nie narzucają górnego limitu długości**. Funkcja `hash_password` przekazuje surowy `password` do Argon2:
```python
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
return ph.hash(password)
```
Argon2 przetwarza cały input — megabajtowe hasło zablokuje 64MB RAM + 3 iteracje per request. Przy `parallelism=4` atak 10 równoległych requestów z 1MB hasłem = 640MB RAM + pełne CPU wykorzystanie. Single-worker FastAPI oznacza kompletny DoS serwera.

**PoC:**
```python
import requests
payload = {"username": "admin", "password": "A" * 1_000_000}
requests.post("http://localhost:8421/api/auth/login", json=payload)
```

**Proponowany fix:**
```python
MAX_PASSWORD_LEN = 128
if len(body.password) > MAX_PASSWORD_LEN:
    raise HTTPException(400, f"Hasło zbyt długie (max {MAX_PASSWORD_LEN})")
```
Dodać do wszystkich endpointów przyjmujących hasło: `/api/auth/login`, `/api/auth/setup`, `POST /api/users`, `PUT /api/users/{id}`.

---

### F-SON-002 — SHA-256 Fallback dla Password Hashing (Broken Crypto)
**Severity:** CRITICAL  
**CVSS:** 8.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `db.py:1207-1237`

**Opis:**
Gdy ani argon2-cffi ani bcrypt nie są zainstalowane, system fall-backuje do SHA-256:
```python
_HASH_BACKEND = "sha256"  # last resort — legacy only
# ...
return "sha256:" + hashlib.sha256(password.encode()).hexdigest()
```
SHA-256 bez soli to kryptograficznie złamany algorytm dla haseł: podatny na rainbow table attacks i GPU brute-force (miliard prób/sekundę na consumer GPU). Choć argon2-cffi jest na liście `_CRITICAL_DEPS`, plik `start.py` nie wywoła `sys.exit()` jeśli argon2 jest zepsute — tylko jeśli fastapi/uvicorn/pydantic/litellm/python-multipart są niedostępne.

**Ryzyko:** Jeśli argon2-cffi ulegnie kompromitacji lub "broken distribution" i system przejdzie na SHA-256, wszystkie hasła w bazie są praktycznie w plaintext.

**Proponowany fix:**
```python
if _HASH_BACKEND == "sha256":
    raise RuntimeError(
        "FATAL: argon2-cffi not available. Cannot hash passwords securely. "
        "Install: pip install argon2-cffi"
    )
```
Traktuj brak argon2 jako hard-fail, analogicznie do brakującego fastapi.

---

## HIGH

### F-SON-003 — Insecure Cookie: SESSION_COOKIE_SECURE domyślnie False
**Severity:** HIGH  
**CVSS:** 7.4 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `app.py:153, 414-415, 567-568`

**Opis:**
```python
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"  # True only behind HTTPS proxy
```
Domyślnie `SESSION_COOKIE_SECURE = False`, więc cookie `sylion_session` jest wysyłane bez flagi `Secure`. Oznacza to, że cookie może być przesyłane przez niezaszyfrowane HTTP, podatne na MitM/sniffing. Aplikacja opisana jest jako "lokalna" (127.0.0.1), ale `--host 0.0.0.0` jest obsługiwaną opcją w `start.py:206`, co czyni ją dostępną przez sieć LAN bez TLS.

**Proponowany fix:**
```python
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "1") == "1"
# + dokumentacja: ustaw 0 tylko dla lokalnego developmentu
```
Lub warunkowo:
```python
secure_flag = True if os.getenv("DASHBOARD_HOST", "127.0.0.1") != "127.0.0.1" else SESSION_COOKIE_SECURE
```

---

### F-SON-004 — Brak Walidacji MIME Type przy Baseline Upload (Content-Type Spoofing)
**Severity:** HIGH  
**CVSS:** 6.8 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:L/A:N)  
**File:Linia:** `app.py:1207-1348`

**Opis:**
Endpoint `/api/baselines/upload` sprawdza rozszerzenie pliku, ale nie weryfikuje rzeczywistego Content-Type ani magic bytes pliku:
```python
raw_bytes = await file.read()
ext = Path(file.filename or "").suffix.lower()
if ext not in ALLOWED_EXTS:
    raise HTTPException(...)
```
Atakujący może wgrać plik `.exe` lub `.php` z rozszerzeniem `.pdf` i będzie zaakceptowany. Pliki są zapisywane na dysk w `workspace_uploads/ksiega/` i ich zawartość trafia do bazy danych (`content` field). Jeśli pipeline przetwarza pliki bazując na rozszerzeniu bez weryfikacji rzeczywistego formatu, możliwa eskalacja do RCE.

**Proponowany fix:**
```python
import magic  # python-magic
mime = magic.from_buffer(raw_bytes[:8192], mime=True)
ALLOWED_MIMES = {"application/pdf", "text/plain", "application/vnd.openxmlformats..."}
if mime not in ALLOWED_MIMES:
    raise HTTPException(400, f"Niedozwolony typ pliku: {mime}")
```

---

### F-SON-005 — Niepełna Walidacja Compression Ratio w _validate_zip_safe (Zip Bomb)
**Severity:** HIGH  
**CVSS:** 6.5 (AV:N/AC:L/PR:L/UI:N/S:U/C:N/I:N/A:H)  
**File:Linia:** `app.py:2310-2336`

**Opis:**
```python
if member.compress_size > 0 and member.file_size / member.compress_size > MAX_ZIP_RATIO:
    raise HTTPException(...)
```
Walidacja sprawdza `member.compress_size > 0` — jeśli `compress_size == 0` (np. stored mode, bez kompresji), warunek jest pomijany i ratio nie jest sprawdzane. Plik ZIP ze `compress_size=0` i `file_size=0` (puste pliki) przejdzie bez problemu. Ponadto, `member.file_size` pochodzi z nagłówka ZIP i może być sfałszowane (tzw. "quine ZIP", "recursive ZIP"). Ekstrakcja poprzez `zf.extract(member, str(extract_tmp))` bez sprawdzenia rzeczywistego rozmiaru po ekstrakcji pozwala na zip bomb z pofałszowanymi nagłówkami.

**Proponowany fix:**
Sprawdzaj rzeczywisty rozmiar po ekstrakcji każdego pliku, nie tylko nagłówkowy `file_size`. Użyj `member.file_size` jako górne ograniczenie z marginesem, ale również sprawdzaj `os.path.getsize` po zapisie.

---

## MEDIUM

### F-SON-006 — Token Sesji 64 hex znaki (UUID hex) — Niewystarczająca Entropia dla Long-lived Sessions
**Severity:** MEDIUM  
**CVSS:** 5.9 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N)  
**File:Linia:** `app.py:392`

**Opis:**
```python
token = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char token
```
64 hex znaków = 256 bitów entropii z `uuid.uuid4()`. Entropia UUID4 wynosi faktycznie 122 bity (6 bitów jest stałych w formacie UUID). Przy `SESSION_DURATION = 86400 * 7` (7 dni), long-lived tokeny z 122-bitową entropią są wystarczające. Jednakże UUID4 może być przewidywalny jeśli RNG systemu jest słaby (historyczne błędy w Xen VM, Docker). `secrets.token_hex(32)` zapewnia pełne 256 bitów z kryptograficznie bezpiecznego PRNG.

**Proponowany fix:**
```python
import secrets
token = secrets.token_hex(32)  # 256 bits CSPRNG
```

---

### F-SON-007 — Audit Log nie jest Immutable — możliwe prune zbyt agresywne
**Severity:** MEDIUM  
**CVSS:** 5.3 (AV:N/AC:L/PR:H/UI:N/S:U/C:N/I:H/A:N)  
**File:Linia:** `db.py:970-1001`

**Opis:**
`prune_audit_log` usuwa wpisy starsze niż `AUDIT_LOG_RETENTION_DAYS` (domyślnie 365 dni), ale:
1. Wartość `AUDIT_LOG_RETENTION_DAYS` jest konfigurowalna przez administratora przez UI (`PUT /api/config/AUDIT_LOG_RETENTION_DAYS`) — właściciel może ustawić `1` dzień i wyczyścić historię bezpieczeństwa.
2. Brak walidacji minimalnej wartości retencji (tylko `n > 0` jest sprawdzane, więc `1` dzień jest dozwolone).
3. Zdarzenia bezpieczeństwa (auth failures, config changes, user creation) są usuwane razem z pozostałymi.

**Ryzyko:** Insider threat — właściciel konta może wyczyścić ślad audytu własnych działań (OWASP A09 Security Logging).

**Proponowany fix:** Wymagaj minimalnie 30 dni retencji dla wpisów z `severity='critical'` lub `severity='high'`. Opcjonalnie szyfruj/podpisuj audit log.

---

### F-SON-008 — AgentSpec Pydantic bez walidacji pola `model` (SSRF via model_name)
**Severity:** MEDIUM  
**CVSS:** 5.4 (AV:N/AC:L/PR:H/UI:N/S:U/C:L/I:L/A:N)  
**File:Linia:** `db.py:918-941`

**Opis:**
```python
class AgentSpec(BaseModel):
    id: str
    name: Opt[str] = None
    stage: Opt[str] = "0"
    role: Opt[str] = ""
    model: Opt[str] = None
    enabled: bool = True
    model_config = {"extra": "ignore"}
```
Pole `model` nie ma żadnej walidacji wartości. W pipeline wartość `model` jest przekazywana do `litellm` jako identyfikator modelu. Jeśli atakujący może zmodyfikować `agents.yaml`, może wstrzyknąć URL modelu jako `model: http://attacker.com/api` co spowoduje SSRF — litellm obsługuje niestandardowe endpointy.

**Proponowany fix:**
```python
ALLOWED_MODEL_PREFIXES = ("claude", "gpt", "gemini", "deepseek", "grok", "ollama", "perplexity")

@field_validator("model")
@classmethod
def validate_model(cls, v: str | None) -> str | None:
    if v and not any(v.startswith(p) for p in ALLOWED_MODEL_PREFIXES):
        raise ValueError(f"Unknown model prefix: {v}")
    return v
```

---

## LOW

### F-SON-009 — Disk Path Ujawniony w Upload Response
**Severity:** LOW  
**CVSS:** 3.1 (AV:N/AC:H/PR:L/UI:N/S:U/C:L/I:N/A:N)  
**File:Linia:** `app.py:2516`

**Opis:**
```python
return {
    ...
    "disk_path": str(dest_path),  # ujawnia absolutną ścieżkę dyskową
    ...
}
```
Odpowiedź na upload zawiera absolutną ścieżkę dyskową pliku (`/home/user/.../workspace_uploads/ksiega/filename.pdf`). Ujawnia strukturę katalogów systemu plików, home directory użytkownika i instalacji SYLION. Ułatwia targeted path traversal lub social engineering.

**Proponowany fix:** Usuń `disk_path` z odpowiedzi API lub zwróć względną ścieżkę w kontekście aplikacji.

---

### F-SON-010 — Brak Nagłówków Security Headers (X-Frame-Options, CSP, etc.)
**Severity:** LOW  
**CVSS:** 3.7 (AV:N/AC:H/PR:N/UI:R/S:U/C:L/I:L/A:N)  
**File:Linia:** `app.py:137-145`

**Opis:**
FastAPI nie ustawia domyślnie nagłówków bezpieczeństwa. Brak: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`, `Referrer-Policy`. Mimo że aplikacja działa lokalnie, brak CSP umożliwia XSS przez zainfekowane dane wyświetlane w dashboardzie.

**Proponowany fix:**
```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        return response

app.add_middleware(SecurityHeadersMiddleware)
```

---

*Raport: Sonnet | SYLION v5.9.0 | 10 findings (2 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW)*
