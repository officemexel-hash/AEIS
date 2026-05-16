# ADR-004: In-memory rate limiting dla endpointu logowania

| Pole          | Wartość                                                          |
|---------------|------------------------------------------------------------------|
| **ID**        | ADR-004                                                          |
| **Tytuł**     | In-memory sliding window rate limiter dla /api/auth/login        |
| **Status**    | Zaakceptowany                                                    |
| **Data**      | 2026-04-19                                                       |
| **Wersja**    | SYLION v5.9.0                                                    |
| **Zmiany**    | FIX-01                                                           |
| **Standard**  | OWASP ASVS V2.2.1, OWASP Top-10 A07:2021 (Identification Failures) |
| **CVSS**      | 9.8 (Critical) — rozwiązano                                      |
| **Autorzy**   | security-audit-council, pr-reviewer                              |
| **Powiązane** | ADR-005, CHANGELOG_v5.9.0.md §Bezpieczeństwo                    |

---

## Status

**Zaakceptowany** — zatwierdzone przez security-audit-council i pr-reviewer (bloker B-01
oznaczony jako naprawiony). Implementacja zweryfikowana przez 18 testów jednostkowych
(`tests/test_rate_limiter.py`) i e2e Playwright test `auth-brute-force`.

Decyzja jest świadomie ograniczona do **single-process, local deployment** SYLION.
Podlega rewizji jeśli SYLION uzyska tryb multi-worker lub distributed deployment.

---

## Kontekst

### Podatność (CVSS 9.8 — Critical)

Audyt bezpieczeństwa (security-audit-council, znalezisko SEC-001) wykazał brak jakiegokolwiek
mechanizmu ograniczenia prób logowania na endpoint `/api/auth/login`. Endpoint akceptował
nieograniczoną liczbę żądań POST z dowolnymi kombinacjami `username`/`password`.

**Wektory ataku:**
- **Credential stuffing** — automatyczne wypróbowanie tysięcy par `login:hasło` z wycieków
  baz danych. Przy braku rate limitingu: pełna szybkość sieci, brak detekcji.
- **Brute-force online** — systematyczne próbowanie haseł dla znanych loginów.
  Argon2 spowalnia weryfikację (~100 ms/próbę), ale atakujący może używać
  wielu równoległych połączeń.
- **Distributed brute-force** — wiele źródłowych IP sprawia, że limity per-IP (np. nginx)
  są niewystarczające bez dodatkowej logiki aplikacyjnej per-użytkownik.

**Ocena ryzyka:**
- CVSS v3.1 Base Score: **9.8 (Critical)** — Attack Vector: Network, Attack Complexity: Low,
  Privileges Required: None, User Interaction: None, Scope: Changed,
  Confidentiality: High, Integrity: High, Availability: High.
- OWASP Top-10 2021: A07 — Identification and Authentication Failures.

### Środowisko docelowe

SYLION w v5.9.0 jest aplikacją **single-process** uruchamianą jako:
- Lokalny serwer deweloperski (1 worker)
- Kontener Docker z 1 instancją
- K8s Deployment z 1 repliką (typowa konfiguracja lokalna)

Brak load balancera z wieloma procesami Python za tym samym endpointem. Dane o próbach
logowania nie muszą być współdzielone między procesami.

---

## Decyzja

Implementujemy **in-memory sliding window rate limiter** w warstwie aplikacyjnej (middleware
lub dekorator funkcji widoku) z następującymi parametrami:

### Parametry

| Parametr           | Wartość            | Uzasadnienie                                      |
|--------------------|--------------------|---------------------------------------------------|
| Klucz              | `username` (string) | Ograniczenie per-konto, niezależne od IP          |
| Okno czasowe       | 5 minut (300 s)    | OWASP ASVS V2.2.1 minimum                         |
| Limit prób         | 5 prób / okno      | Wystarczający dla literówek; skuteczny przeciw BF |
| Czas blokady       | 10 minut (600 s)   | Ponad okno — zapobiega rotation attacks           |
| Reakcja HTTP       | 429 Too Many Requests | Z nagłówkiem `Retry-After`                    |
| Reset              | Automatyczny po TTL blokady | Bez ingerencji administratora            |

### Algorytm (sliding window)

```python
_login_attempts: dict[str, list[float]] = {}  # username → lista timestampów prób
_lockouts: dict[str, float] = {}              # username → timestamp zwolnienia blokady

WINDOW_SECONDS = 300   # 5 min
MAX_ATTEMPTS   = 5
LOCKOUT_SECONDS = 600  # 10 min

def check_rate_limit(username: str) -> None:
    now = time.monotonic()

    # Sprawdź aktywną blokadę
    if username in _lockouts:
        if now < _lockouts[username]:
            retry_after = int(_lockouts[username] - now)
            raise RateLimitExceeded(retry_after=retry_after)
        else:
            del _lockouts[username]

    # Przesuń okno — usuń próby starsze niż WINDOW_SECONDS
    attempts = _login_attempts.get(username, [])
    attempts = [t for t in attempts if now - t < WINDOW_SECONDS]

    if len(attempts) >= MAX_ATTEMPTS:
        _lockouts[username] = now + LOCKOUT_SECONDS
        _login_attempts[username] = []
        raise RateLimitExceeded(retry_after=LOCKOUT_SECONDS)

    attempts.append(now)
    _login_attempts[username] = attempts
```

### Integracja

Rate limiter wywoływany **przed** weryfikacją hasła (Argon2) — nie ma kosztu obliczeniowego
po przekroczeniu limitu. Błąd 429 zwracany ze stałym czasem odpowiedzi (constant-time)
niezależnie od istnienia konta (ochrona przed user enumeration).

### Parametry konfigurowalne

Wartości `WINDOW_SECONDS`, `MAX_ATTEMPTS`, `LOCKOUT_SECONDS` eksponowane przez zmienne
środowiskowe `SYLION_RATELIMIT_WINDOW`, `SYLION_RATELIMIT_MAX_ATTEMPTS`,
`SYLION_RATELIMIT_LOCKOUT` — umożliwia dostrajanie bez ponownej kompilacji.

---

## Konsekwencje

### Pozytywne

- **Eliminacja CVSS 9.8** — zredukowanie ryzyka brute-force i credential stuffing do poziomu
  akceptowalnego dla środowiska lokalnego/deweloperskiego.
- **OWASP ASVS V2.2.1** — implementacja spełnia wymaganie „rate limit or lockout after N failed
  attempts within defined time window".
- **Zerowe zależności zewnętrzne** — implementacja używa wyłącznie stdlib Python (`time`,
  `dict`). Brak Redisa, Memcached ani żadnego zewnętrznego store.
- **Prostota** — implementacja mieści się w < 50 LOC; w pełni pokryta testami jednostkowymi.
- **Stały czas odpowiedzi** — zabezpieczenie przed timing attack i user enumeration.

### Negatywne

- **Brak persystencji** — dane rate limiter są w pamięci procesu. Restart serwera resetuje
  liczniki. Atakujący może obejść blokadę przez wymuszenie restartu (np. jeśli ma dostęp
  do wywołania restart serwisu). Ryzyko akceptowalne dla single-process local deployment.
- **Brak współdzielenia między procesami** — jeśli SYLION zostanie uruchomiony z wieloma
  workerami (gunicorn `-w 4`), każdy worker ma niezależny licznik; atakujący może wysłać
  5 × N_WORKERS prób przed blokowaniem. Wymaga migracji do zewnętrznego store (Redis)
  przy skalowaniu.
- **Podatność na DoS per-konto** — legitymizowany użytkownik może zostać zablokowany przez
  atakującego który celowo przeprowadza failed attempts na jego konto. Mitigacja: limit 5 prób
  jest wystarczająco wysoki dla przypadkowych literówek; blokada trwa 10 min, nie permanentnie.
- **Brak alertów** — przekroczenie limitu nie generuje zdarzenia w `audit_log`. Planowane
  w v5.9.1.

### Neutralne

- Implementacja jest transparentna dla klienta API (standardowe HTTP 429 z `Retry-After`).
- Parametry domyślne (5/5min/10min) mogą być zbyt restrykcyjne dla środowisk z wieloma
  użytkownikami za NAT — dostrajalne przez zmienne środowiskowe.

---

## Alternatywy rozważane

### Opcja A: Rate limiting na poziomie nginx/reverse proxy

**Częściowo odrzucona.** Nginx `limit_req_zone` działa per-IP — niewystarczające dla
distributed brute-force z różnych IP. Dodatkowo SYLION w v5.9.0 może być uruchamiany
bezpośrednio (bez nginx), więc warstwa proxy nie może być jedyną ochroną. Komplementarne,
nie wystarczające samo w sobie.

### Opcja B: Redis jako store dla liczników (Token Bucket / Sliding Window)

**Odrzucona dla v5.9.0.** Redis wprowadza zewnętrzną zależność operacyjną. Dla lokalnego,
single-process deployment jest to over-engineering. Zmiana w rekomendowanym kierunku
przy skalowaniu do multi-worker lub distributed deployment.

### Opcja C: Blokada konta w bazie danych (persistent lockout)

**Odrzucona.** Wymaga dodania kolumny `locked_until` do tabeli `users` (migracja schematu)
i dodatkowego zapytania do bazy danych przy każdej próbie logowania. Komplikuje reset konta
(wymaga akcji administratora lub endpointu reset). In-memory jest wystarczające dla zagrożeń
w scope v5.9.0.

### Opcja D: CAPTCHA po N nieudanych próbach

**Odrzucona dla v5.9.0.** CAPTCHA wymaga integracji zewnętrznego serwisu (reCAPTCHA,
hCaptcha), co jest niezgodne z zasadą offline-first i prywatnościową polityką SYLION.
Może być rozważona w przyszłości jako warstwa dodatkowa.

### Opcja E: Slow-down (exponential backoff zamiast hard lockout)

**Rozważona, odrzucona.** Stopniowe zwiększanie czasu odpowiedzi (sleep) blokuje wątki
serwera i może być użyte jako amplifier DoS. Hard lockout z HTTP 429 jest efektywniejszy
i nie zużywa zasobów serwera.
