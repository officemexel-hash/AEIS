# ADR-0031: DB init race condition fix dla fresh installs

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/db_init_bug  

---

## Kontekst

Audyt mega_audit/db_init_bug wykazał race condition w `dashboard/db.py` przy pierwszym uruchomieniu SYLION (fresh install):

**Scenariusz błędu:**  
1. `start.py` wywołuje `init_db()` asynchronicznie przez `asyncio.create_task()`
2. Równolegle `start.py` rejestruje endpointy FastAPI i uvicorn zaczyna przyjmować żądania
3. Pierwsze żądanie HTTP (np. GET `/`) trafia do handlera zanim `init_db()` ukończy `CREATE TABLE IF NOT EXISTS agents`
4. Handler wywołuje `get_db_conn()` → `conn.execute("SELECT * FROM agents")` → `OperationalError: no such table: agents`

Problem pojawia się wyłącznie na fresh installs (brak istniejącego pliku `.db`) lub po `rm sylion.db`. Na instalacjach z istniejącą bazą — brak problemu (tabele już istnieją).

Audyt mega_audit/db_init wykazał historyczne podejście: `init_db()` była wywoływana synchronicznie w `@app.on_event("startup")` (FastAPI), co gwarantowało zakończenie przed przyjęciem żądań. Refaktor do `asyncio.create_task()` (PR bez review) zepsuł gwarancję kolejności.

Rozważane warianty:
- **R1** — Przywrócenie synchronicznego `init_db()` w `@app.on_event("startup")` (wybrana)
- **R2** — Middleware sprawdzające gotowość bazy przed każdym żądaniem (`db_ready: Event`)
- **R3** — `asyncio.Lock` w `get_db_conn()` z oczekiwaniem na `db_initialized: asyncio.Event`
- **R4** — Eager initialization przed `uvicorn.run()` (blokujące, w głównym wątku)

## Decyzja

Wdrożenie **R1** z elementem **R3** jako safety net:

1. **Primary fix**: `init_db()` wywołana w `@app.lifespan` (FastAPI ≥ 0.93) zamiast `asyncio.create_task()`. `lifespan` context manager gwarantuje zakończenie `startup` przed przyjęciem pierwszego żądania.
2. **Safety net**: `asyncio.Event` `_DB_READY` ustawiany po zakończeniu `init_db()`. `get_db_conn()` sprawdza `_DB_READY.is_set()` i raise `SYL-2003` (db not initialized) jeśli fałszywy — zamiast `OperationalError`.
3. **Idempotentność**: `init_db()` może być bezpiecznie wywołana wielokrotnie (`CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE`).

## Konsekwencje

### Pozytywne
- Eliminacja race condition na fresh install — potwierdzone testami `test_fresh_install_*`
- `SYL-2003` zamiast stack trace `OperationalError` — czytelny komunikat błędu dla SRE
- `@app.lifespan` (vs deprecated `@app.on_event`) — zgodność z FastAPI ≥ 0.93 i Starlette best practices

### Negatywne
- `@app.lifespan` wymaga refaktoru z `@app.on_event("startup")` / `@app.on_event("shutdown")` — zmiana w `start.py` i testach
- Synchroniczne `init_db()` w `lifespan` opóźnia start uvicorn o czas inicjalizacji bazy (~50-200ms na SSD) — akceptowalne

### Neutralne
- `_DB_READY` Event jako moduł-level variable — prosty mechanizm bez dodatkowych zależności
- Testy fresh-install dodane do `tests/test_db_init.py`

## Alternatywy odrzucone

- **R2 (middleware)**: overhead na każdym żądaniu po inicjalizacji — niepotrzebny koszt — odrzucone
- **R4 (przed uvicorn.run)**: blokuje event loop — problem przy przyszłym multi-worker (ADR-0035 planowane)

## Referencje

- `mega_audit/db_init_bug/` — analiza race condition z reprodukcją
- `mega_audit/db_init/` — historyczny audyt mechanizmu init_db
- `dashboard/db.py` — `init_db()`, `get_db_conn()`, `_DB_READY`
- `dashboard/start.py` — `@app.lifespan` context manager
- `tests/test_db_init.py` — testy fresh install
- FastAPI lifespan docs: https://fastapi.tiangolo.com/advanced/events/
- ADR-0023 (agent-id-reset) — powiązane zmiany w `init_db()`
