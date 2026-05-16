# ADR-003: Framework migracji schematu bazy danych (PRAGMA user_version)

| Pole          | Wartość                                                  |
|---------------|----------------------------------------------------------|
| **ID**        | ADR-003                                                  |
| **Tytuł**     | Framework migracji schematu SQLite oparty na PRAGMA user_version |
| **Status**    | Zaakceptowany                                            |
| **Data**      | 2026-04-19                                               |
| **Wersja**    | SYLION v5.9.0                                            |
| **Zmiany M**  | M-02, M-08, FIX-04, FIX-05, FIX-06                      |
| **Autorzy**   | Rada Migracji SYLION (migration-council)                 |
| **Powiązane** | ADR-006, CHANGELOG_v5.9.0.md, MIGRATION_GUIDE.md        |

---

## Status

**Zaakceptowany** — decyzja zatwierdzona przez migration-council (wynik: GO-WITH-WARNINGS,
wszystkie ostrzeżenia zaadresowane przez FIX-04, FIX-05, FIX-06). Decyzja obowiązuje
od v5.9.0. Podlega rewizji przed v6.0.0 w kontekście ewentualnego przejścia na
PostgreSQL lub SQLite z rozszerzeniem FTS5.

---

## Kontekst

### Problem

Do v5.8.x SYLION nie posiadał mechanizmu wersjonowania schematu bazy danych. Migracje
były wykonywane ręcznie przez administratora przed wdrożeniem nowej wersji. Skutki:

1. **Brak automatyzacji** — każde wdrożenie wymagało ręcznej interwencji DBA, co zwiększało
   ryzyko błędu ludzkiego i wydłużało okno serwisowe.
2. **Brak idempotentności** — ponowne uruchomienie skryptu migracyjnego mogło powodować
   błędy `table already exists` lub duplikaty danych.
3. **Brak historii** — nie było mechanizmu sprawdzenia, jaka wersja schematu jest aktualnie
   zainstalowana w instancji produkcyjnej.
4. **Ryzyko desynchronizacji** — wersja kodu mogła wyprzedzić wersję schematu lub odwrotnie,
   co prowadziło do trudnych do debugowania błędów runtime.

### Ograniczenia techniczne

- SYLION v5.9.0 używa **SQLite** jako głównego magazynu danych (single-file, embedded).
- Środowisko: lokalne instalacje, kontenery Docker, K8s (PVC), GrapheneOS. Brak stałego
  dostępu do narzędzi zewnętrznych (Alembic, Flyway, Liquibase).
- SQLite dostarcza wbudowaną zmienną `PRAGMA user_version` (32-bitowa liczba całkowita),
  która przeżywa restart i jest atomowo zapisywana wraz z transakcją DDL.
- Rozmiar zespołu i skala projektu: framework musi być prosty, zrozumiały bez zewnętrznych
  zależności i możliwy do wdrożenia w środowiskach offline.

### Wyniki audytu (migration-council)

- Audyt zidentyfikował brak wersjonowania schematu jako ryzyko HIGH.
- Rekomendacja: wbudowany framework oparty na `PRAGMA user_version` jako minimalne,
  wystarczające rozwiązanie dla aktualnej skali projektu.

---

## Decyzja

Implementujemy wbudowany framework migracji SQLite z następującymi elementami:

### Komponenty

```python
# Stała wersji docelowej
_DB_TARGET_VERSION: int = 1

# Słownik migracji: numer wersji → lista instrukcji DDL
_MIGRATIONS: dict[int, list[str]] = {
    1: [
        "CREATE TABLE IF NOT EXISTS ...",
        "CREATE INDEX IF NOT EXISTS ...",
        # wyłącznie addytywne DDL
    ],
}

# Funkcja wykonująca migracje
def _run_migrations(conn: sqlite3.Connection) -> None: ...
```

### Algorytm

1. Odczytaj `PRAGMA user_version` z otwartego połączenia.
2. Dla każdej wersji `v` w zakresie `(current_version, _DB_TARGET_VERSION]` (rosnąco):
   a. Pobierz listę instrukcji DDL z `_MIGRATIONS[v]`.
   b. Wykonaj kopię zapasową (non-fatal — patrz ADR-006).
   c. W transakcji `BEGIN IMMEDIATE`: wykonaj DDL, ustaw `PRAGMA user_version = {v:d}`.
3. Zatrzymaj się gdy `PRAGMA user_version == _DB_TARGET_VERSION`.

### Zasady projektowe (niezmienne)

- **Wyłącznie addytywne** — migracje mogą tylko dodawać tabele, kolumny, indeksy.
  Nigdy nie usuwają ani nie modyfikują istniejących obiektów.
- **Idempotentne** — każda instrukcja DDL używa `IF NOT EXISTS` / `IF EXISTS`.
- **Atomowe** — każda migracja wykonywana w oddzielnej transakcji `BEGIN IMMEDIATE`.
- **Monotoniczne** — numer wersji rośnie wyłącznie o 1; skoki wersji są zabronione.
- **Bez danych** — migracje DDL nie modyfikują danych; transformacje danych wykonywane
  są osobno w logice aplikacyjnej po zakończeniu migracji schematu.

### Zabezpieczenia (FIX-05)

```python
# Ochrona przed wstrzyknięciem przez spreparowany obiekt __format__
assert isinstance(version, int), f"user_version musi być int, got {type(version)}"
conn.execute(f"PRAGMA user_version = {version:d}")
```

---

## Konsekwencje

### Pozytywne

- **Automatyzacja** — migracje wykonywane automatycznie przy starcie serwera; zero interwencji
  ręcznej przy standardowym wdrożeniu.
- **Audytowalność** — aktualny stan schematu odczytywany przez `PRAGMA user_version` w dowolnym
  momencie, bez dostępu do kodu źródłowego.
- **Brak zależności zewnętrznych** — framework wbudowany w kod aplikacji; działa w środowiskach
  offline i air-gapped.
- **Idempotentność** — wielokrotne uruchomienie jest bezpieczne; `IF NOT EXISTS` gwarantuje brak
  duplikatów.
- **Czytelność** — słownik `_MIGRATIONS` jest jedynym miejscem przechowywania historii schematu;
  łatwy do przeglądania i rewizji kodu.
- **Weryfikowalność** — 24 testy jednostkowe w `tests/test_migration_framework.py` pokrywają
  upgrade, idempotentność, obsługę błędów i scenariusze wycofania.

### Negatywne

- **Brak rollback DDL** — SQLite nie obsługuje transakcyjnego rollback dla DDL (np. `DROP TABLE`).
  Wycofanie wymaga przywrócenia kopii zapasowej. Zasada addytywności mityguje to ryzyko:
  nowe tabele/kolumny mogą istnieć bez wpływu na poprzednią wersję kodu.
- **Ograniczenia SQLite** — `ALTER TABLE` w SQLite jest ograniczony (brak `DROP COLUMN` do SQLite 3.35,
  brak `RENAME COLUMN` do SQLite 3.25). Addytywna strategia jest świadomym ograniczeniem
  wynikającym z tych limitów.
- **Brak wsparcia dla rozgałęzień** — framework zakłada liniową historię migracji. Równoległe
  gałęzie deweloperskie modyfikujące schemat wymagają ręcznej koordynacji numerów wersji.
- **Blokada jednego procesu** — `BEGIN IMMEDIATE` na SQLite pozwala tylko jednemu procesowi
  zapisywać jednocześnie. Wieloprocesowe wdrożenia (np. gunicorn multi-worker) wymagają
  koordynacji zewnętrznej (np. inicjalizacja przed forkiem).

### Neutralne

- **Zakres v5.9.0** — `_DB_TARGET_VERSION = 1` obejmuje tylko pierwszą formalną migrację.
  Framework jest zaprojektowany do liniowego rozszerzania przez kolejne wydania.
- **Kompatybilność wsteczna** — `PRAGMA user_version = 0` (wartość domyślna) interpretowane
  jest jako baza przedframeworkowa; migracja 1 jest bezpieczna dla wszystkich instancji v5.8.x.

---

## Alternatywy rozważane

### Opcja A: Alembic (SQLAlchemy)

**Odrzucona.** Alembic jest potężnym narzędziem dla PostgreSQL/MySQL, ale wprowadza ciężką
zależność (`alembic`, `sqlalchemy`) do projektu opartego wyłącznie na `sqlite3` stdlib.
Wymagałby refaktoryzacji warstwy dostępu do danych i nie jest dostosowany do środowisk offline.

### Opcja B: Flyway / Liquibase

**Odrzucona.** Narzędzia Java wymagające JVM — nieakceptowalne dla lekkiego instalatora
Python. Nadmierny overhead operacyjny dla skali projektu.

### Opcja C: Numery wersji w osobnej tabeli `schema_migrations`

**Rozważona, odrzucona.** Tabela `schema_migrations` (wzorzec Rails Active Record) jest
popularnym rozwiązaniem, ale wymaga bootstrappingu — tabela musi istnieć zanim zostanie
użyta do śledzenia wersji. `PRAGMA user_version` jest atomowo dostępny od pierwszego
otwarcia bazy danych, bez inicjalizacji. Prostsze rozwiązanie dla naszej skali.

### Opcja D: Pliki `.sql` w katalogu `migrations/` (wzorzec goose/dbmate)

**Odrzucona.** Wymaga parsowania i wykonywania zewnętrznych plików SQL przy starcie —
komplikuje distribucję (package bundling), utrudnia testowanie jednostkowe i wymaga
dodatkowych zależności systemowych. Inline DDL w słowniku `_MIGRATIONS` jest prostsze
i testowalność wyższa.

### Opcja E: Bez wersjonowania (status quo v5.8.x)

**Odrzucona.** Utrzymanie status quo zostało ocenione jako ryzyko HIGH przez migration-council.
Ręczne migracje przy każdym wdrożeniu są niemożliwe do skalowania i podatne na błąd ludzki.
