# ADR-0024: Whitelist zapytań SQL i modeli Ollama

**Status:** Accepted
**Data:** 2026-04-19
**Autor:** council re-audit v5.9.0 / security

## Kontekst

Audyt bezpieczeństwa v5.9.0 wykazał dwa wektory ataku związane z dynamicznym wykonywaniem kodu:

1. **SQL injection via dashboard API**: endpoint `/api/query` przyjmował surowe fragmenty SQL budowane przez f-string bez parametryzacji. Atakujący z dostępem do panelu mógł wykonać `DROP TABLE agents` lub odczytać klucze API.

2. **Ollama model injection**: endpoint `/api/council/run` pozwalał na podanie dowolnego nazwy modelu (`model_name`). Atakujący mógł wskazać złośliwy model lub spowodować nieautoryzowane połączenia sieciowe do zewnętrznych instancji Ollama.

Rozważane podejścia:
- **S1** — Parametryzacja wszystkich zapytań SQL + whitelist modeli Ollama (wybrana)
- **S2** — Tylko parametryzacja SQL; modele bez ograniczeń (zbyt wąskie)
- **S3** — ORM (SQLAlchemy) zamiast surowego SQL
- **S4** — Sandboxing zapytań SQL w osobnym procesie z ograniczonymi uprawnieniami

## Decyzja

**S1**: Wszystkie zapytania do SQLite przechodzą przez parametryzowane `cursor.execute(sql, params)` (eliminacja f-string SQL). Dozwolone modele Ollama są zdefiniowane w stałej `ALLOWED_OLLAMA_MODELS` w `db.py` — każda próba użycia modelu spoza listy zwraca HTTP 400 z komunikatem o niedozwolonym modelu.

## Konsekwencje

### Pozytywne
- Eliminacja SQL injection (OWASP A03:2021)
- Kontrolowany zakres modeli Ollama — zapobieganie przypadkowym połączeniom do niezaufanych endpointów
- Whitelist modeli jest konfigurowalna przez plik `config.yaml` bez kodu (deployment flexibility)

### Negatywne
- Whitelist modeli wymaga ręcznej aktualizacji przy każdym dodaniu nowego modelu Ollama — dodatkowy krok w procesie wydania
- ORM (S3) odrzucony — rezygnacja z pełniejszej abstrakcji SQL za cenę mniejszej zależności

### Neutralne
- Zmiany kompatybilne wstecznie dla klientów API — `model_name` nadal akceptowany, ale walidowany

## Alternatywy odrzucone

- **SQLAlchemy ORM (S3)**: znaczący refaktor istniejącego kodu `db.py` (~2000 linii); odłożone do v6.0
- **Sandboxing (S4)**: nadmiarowa złożoność dla lokalnej aplikacji jednouszkodnikowej

## Referencje

- `dashboard/db.py` — `ALLOWED_OLLAMA_MODELS`, parametryzowane zapytania
- `dashboard/app.py` — `/api/query`, `/api/council/run`
- OWASP Top 10 2021 — A03 Injection
- `docs/SECURITY_REAUDIT_v5.9.0.md`
