# ADR-0026: CSRF pełne pokrycie wszystkich mutujących endpointów

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/csrf_71_endpoints  

---

## Kontekst

Audyt mega_audit/csrf_71_endpoints wykazał, że spośród 71 endpointów mutujących dane (POST/PUT/PATCH/DELETE) w `dashboard/app.py` i `dashboard/router_provision.py`, tylko 23 były objęte weryfikacją tokenu CSRF. Pozostałe 48 endpointów przyjmowało żądania bez walidacji `X-CSRF-Token` lub cookie `csrf_token`, co stanowi wektor ataku CSRF (OWASP A01:2021 — Broken Access Control).

Znane podatne endpointy (próbka):
- `POST /api/agents/create` — tworzenie agentów bez CSRF
- `POST /api/user/password` — zmiana hasła bez CSRF (CVSS 8.8)
- `DELETE /api/sessions/{id}` — unieważnienie sesji bez CSRF
- `POST /api/pipeline/run` — uruchomienie pipeline bez CSRF
- `PUT /api/config` — zapis konfiguracji systemu bez CSRF

Implementacja CSRF bazuje na double-submit cookie pattern (ADR-0009: secure cookies). Token generowany przy `GET /` i przechowywany w `HttpOnly=False, SameSite=Strict` cookie `csrf_token`. Middleware `verify_csrf()` porównuje cookie z nagłówkiem `X-CSRF-Token`.

Rozważane warianty:
- **C1** — Ręczne dodanie `verify_csrf()` do każdego handlera (status quo — niekompletne)
- **C2** — FastAPI middleware globalny z wykluczeniami dla GET/HEAD/OPTIONS + endpointów publicznych (wybrana)
- **C3** — Synchronous dependency `Depends(verify_csrf)` wstrzykiwana do każdego routera
- **C4** — Porzucenie double-submit na rzecz SameSite=Strict-only (niewystarczające dla starszych przeglądarek)

## Decyzja

Wdrożenie **C2**: globalny `CSRFMiddleware` w `dashboard/app.py` działający jako Starlette middleware, który automatycznie odrzuca żądania mutujące (metody: POST, PUT, PATCH, DELETE) bez ważnego tokenu CSRF. Wyjątki (publiczne endpointy nie wymagające auth: `/api/setup`, `/api/health`) konfigurowane w liście `CSRF_EXEMPT_PATHS` w `config.yaml`.

Tokeny CSRF rotowane przy każdym logowaniu (`POST /api/auth/login`) i unieważniane przy wylogowaniu.

## Konsekwencje

### Pozytywne
- Pełne pokrycie 71/71 mutujących endpointów (z 23/71 przed zmianą)
- Eliminacja CSRF jako klasy błędów w projekcie SYLION
- Centralna konfiguracja ścieżek exempt — bez rozproszenia logiki CSRF po handlerach
- Zgodność z OWASP ASVS L2 (4.2.2)

### Negatywne
- Frontend (dashboard JS) musi dołączać nagłówek `X-CSRF-Token` do każdego żądania mutującego — wymaga aktualizacji `dashboard/static/js/api.js`
- Klienci API (curl, narzędzia zewnętrzne) muszą pobierać token z `GET /api/csrf-token` przed każdą mutacją — breaking change dla skryptów automatycznych

### Neutralne
- Middleware nie wpływa na wydajność GET/HEAD/OPTIONS
- Token przechowywany w `LocalStorage` po stronie klienta — kompromis między UX a security (akceptowalny przy `SameSite=Strict`)

## Alternatywy odrzucone

- **C1 (ręczne `Depends`)**: 48 plików do zmiany, ryzyko pominięcia nowych endpointów — odrzucone na rzecz centralnego middleware
- **C4 (SameSite-only)**: Firefox < 60 i Safari iOS < 12 nie respektują `SameSite=Strict` — odrzucone dla kompatybilności

## Referencje

- `mega_audit/csrf_71_endpoints/` — pełna lista 71 endpointów i status pokrycia
- ADR-0009 (secure-cookie-default) — podstawa double-submit cookie pattern
- `dashboard/app.py` — `CSRFMiddleware`, `CSRF_EXEMPT_PATHS`
- `dashboard/static/js/api.js` — klient JS (wymaga aktualizacji)
- OWASP ASVS 4.2.2, OWASP Top 10 2021 A01
