# Rejestr zmian — SYLION

Wszystkie istotne zmiany w projekcie SYLION są dokumentowane w tym pliku.

Format oparty na [Keep a Changelog v1.1.0](https://keepachangelog.com/pl/1.1.0/),
projekt stosuje [Semantic Versioning 2.0.0](https://semver.org/lang/pl/).

---

## [Nieudostępnione] — plan v6.0.0

### Planowane
- Refaktoryzacja orkiestratora: ekstrakcja `AgentOrchestrator` do osobnego modułu z interfejsem `OrchestratorProtocol`
- Migracja sygnatur parametrów agentów z `dict[str, Any]` na `TypedDict` (pełne bezpieczeństwo typów)
- Zestaw testów `BudgetGuard` pokrywający limity tokenów i logikę przerwania pętli agenta
- Rejestr umiejętności oparty na wtyczkach (`SkillRegistry`) — dynamiczne ładowanie bez restartu procesu
- Eksport OpenTelemetry dla śledzenia rozproszonych zapytań agentów

---

## [5.9.0] — 2026-04-19 — „Breakthrough — 18 Skills Audit"

> Wydanie przełomowe: pełny audyt 18 umiejętności (13 rad × 4 modele = 52 subagentów). Wydanie zawiera
> wyłącznie zmiany addytywne — brak zmian łamiących kompatybilność wsteczną z v5.8.x.
> Baseline produkcyjny: v5.8.8.1.
>
> Wynik audytu: security-audit-council 35 znalezisk (5 CRITICAL, 10 HIGH, 12 MEDIUM, 8 LOW),
> rodo-compliance 3 CRITICAL, code-auditor 42 znaleziska, pr-reviewer REQUEST-CHANGES → wszystkie
> 5 blokerów naprawione, predeploy NO-GO → GO po FIX-01..FIX-11, testgen 86 passed / 4 skipped /
> 0 failed, e2e-playwright 40/40 smoke tests pass, migration-council GO-WITH-WARNINGS (additive-only),
> finops ~80% estymowane oszczędności przy pełnej optymalizacji.
>
> Szczegółowa mapa napraw: [FIX_MAP.md](./FIX_MAP_v5.9.0.md)

---

### Dodano

#### Walidacja agentów — M-01
- **Walidacja `AgentSpec` przez Pydantic w `_seed_agents`** (M-01): każda specyfikacja agenta jest
  walidowana przy starcie, co wyklucza uruchomienie z nieprawidłową konfiguracją. Błędy są jawne
  i opisowe zamiast powodować nieprzewidywalne awarie w trakcie działania.

#### Framework migracji bazy danych — M-02
- **`PRAGMA user_version` jako wersja schematu** (M-02): nowy mechanizm migracji oparty na
  `_DB_TARGET_VERSION = 1`, słowniku `_MIGRATIONS` (klucz: numer wersji int → wartość: lista
  instrukcji DDL) oraz funkcji `_run_migrations`. Każda migracja jest zapisana transakcyjnie;
  powrót do poprzedniej wersji możliwy przez przywrócenie kopii zapasowej.
  Szczegóły: [ADR-003](./adr/ADR-0003-migration-framework.md).

#### Retencja danych (RODO) — M-03
- **Automatyczna retencja `audit_log` (365 dni) i `sessions` (30 dni)** (M-03): implementacja
  art. 5 ust. 1 lit. e) RODO (zasada ograniczenia przechowywania). Harmonogram czyszczenia
  uruchamiany przy starcie serwera; progi retencji konfigurowalne przez zmienne środowiskowe
  `SYLION_AUDIT_RETENTION_DAYS` i `SYLION_SESSION_RETENTION_DAYS`.

#### Zarządzanie zależnościami — M-04
- **`requirements.in` + `pip-compile` lockfile** (M-04): wersje zależności są teraz przypinane
  deterministycznie. `requirements.txt` generowany przez `pip-compile` z automatycznym
  fallbackiem do ręcznej instalacji gdy `pip-compile` jest niedostępny w środowisku CI.

#### Kopie zapasowe przed migracją — M-08
- **WAL-safe backup przed każdą migracją schematu** (M-08): plik `~/sylion/sylion.db.bak.v5.9.0.YYYY-MM-DD.sqlite3`
  tworzony automatycznie przed uruchomieniem migracji. Operacja nie blokuje równoczesnych odczytów
  w trybie WAL. Backup jest non-fatal na systemach plików tylko do odczytu (kontenery, K8s,
  GrapheneOS) — szczegóły: [ADR-006](./adr/ADR-0006-backup-non-fatal.md).

#### Resetowanie stanu agenta — H-04
- **`agent_id = None` na początku każdej iteracji `_seed_agents`** (H-04): naprawa hot-fix
  eliminująca wyścig stanów, w którym poprzedni `agent_id` był widoczny przez kolejną iterację
  pętli w przypadku wyjątku częściowego zapisu.

#### Rate limiting — FIX-01
- **In-memory rate limiter dla `/api/auth/login`** (FIX-01): sliding window 5 prób / 5 min,
  blokada konta na 10 minut po wyczerpaniu limitu. Zgodne z OWASP ASVS V2.2.1. Rozwiązuje
  CVSS 9.8 (brak ograniczenia prób logowania). Szczegóły: [ADR-004](./adr/ADR-0004-rate-limiting.md).

#### Ochrona przed wstrzyknięciem poleceń — FIX-07
- **Wyrażenie regularne `_VALID_IMPORT_RE`** (FIX-07): defence-in-depth w `start.py`
  `_batch_imports_ok` — nazwy modułów importowanych w procesie wsadowym są weryfikowane
  względem białej listy wzorców przed przekazaniem do interpretera. Zapobiega wstrzyknięciu
  poleceń powłoki.

#### Indeksy bazy danych — FIX-11
- **Indeksy `idx_audit_log_ts` i `idx_audit_log_actor`** (FIX-11): nowe indeksy na kolumnach
  `timestamp` i `actor` w tabeli `audit_log`. Znaczące przyspieszenie zapytań filtrujących
  po czasie i użytkowniku (np. raporty RODO, panel administratora).

#### Nowe pliki testów
- `tests/test_rate_limiter.py` — 18 przypadków testowych dla FIX-01 (sliding window, lockout,
  reset po TTL, współbieżność)
- `tests/test_migration_framework.py` — 24 przypadki testowe dla M-02 (upgrade, idempotentność,
  wycofanie, obsługa błędów)
- `tests/test_password_hashing.py` — 12 przypadków testowych dla FIX-09 (argon2 ok, bcrypt ok,
  brak backend → RuntimeError, max_length enforcement)

---

### Zmieniono

#### Tryb transakcji SQLite
- **`BEGIN EXCLUSIVE` → `BEGIN IMMEDIATE`** (FIX-04): poprzedni tryb ekskluzywny blokował
  równoległe odczyty podczas migracji. Tryb `IMMEDIATE` nabywa blokadę zapisu niezwłocznie,
  ale pozwala na równoległe odczyty w WAL — właściwe zachowanie dla SQLite w trybie WAL.
  Zmiana jest transparentna dla aplikacji i nie wymaga modyfikacji klienta.

#### Usunięcie awaryjnego haszowania SHA-256
- **Fallback SHA-256 usunięty z `hash_password`** (FIX-09): poprzednia implementacja
  po cichu degradowała się do SHA-256 gdy brakowało argon2 lub bcrypt. Nowe zachowanie:
  `RuntimeError` z czytelnym komunikatem. Nie ma żadnej ścieżki do kodu produkcyjnego
  korzystającej z kryptograficznie słabego SHA-256. Rozwiązuje CVSS 8.1.
  Szczegóły: [ADR-005](./adr/ADR-0005-password-hashing.md).

#### Filtr zapytań dashboardu
- **`COALESCE(status, 'unknown') = ...` → `WHERE status IS NOT NULL`** (FIX-02): regresja
  wprowadzona przez M-06 powodowała zmianę kształtu JSON w odpowiedzi API. Nowy filtr
  `WHERE status IS NOT NULL` zachowuje oryginalne zachowanie (C-308 OK) i eliminuje
  pomijanie wierszy z `NULL` statusem, które powinny być uwzględniane w agregatach.

#### Konsolidacja zapytań dashboardu — M-06
- **15 zapytań `COUNT` → 5 zapytań z `GROUP BY`** (M-06): refaktoryzacja warstwy dostępu
  do danych panelu administracyjnego. Czas renderowania dashboardu skrócony o ~67% liczby
  round-tripów bazy danych. Wynik performance-profiler: brak regresji, czas odpowiedzi
  w normie. Szczegóły: [ADR-008](./adr/ADR-0008-dashboard-query-consolidation.md).

#### Wsadowy import — M-07
- **13 wywołań `subprocess.run` → 1 wywołanie** (M-07): `_batch_imports_ok` w `start.py`
  przebudowany tak, by wykonywać import wszystkich modułów w jednym procesie potomnym
  zamiast wywoływać nowy proces dla każdego modułu. Czas startu: 2,62 s → 1,80 s
  (oszczędność 820 ms, przyśpieszenie 1,46×). Szczegóły: [ADR-007](./adr/ADR-0007-batch-imports.md).

#### Zabezpieczenie formatowania SQL — FIX-05
- **`PRAGMA user_version = {version:d}` + guard `isinstance`** (FIX-05): parametr wersji
  jest teraz jawnie rzutowany do formatu dziesiętnego (`:d`) i weryfikowany przez `isinstance(version, int)`
  przed interpolacją do łańcucha PRAGMA. Eliminuje możliwość wstrzyknięcia przez spreparowany
  obiekt implementujący `__format__`.

#### Filtr WHERE w zapytaniach Ollama — FIX-10
- **Biała lista filtrów WHERE dla zapytań Ollama** (FIX-10): defence-in-depth — dozwolone
  nazwy kolumn w dynamicznie budowanych klauzulach WHERE są weryfikowane względem białej
  listy przed interpolacją. Rozwiązuje CVSS 7.5 (potencjalne wstrzyknięcie SQL przez
  niezaufaną nazwę kolumny).

#### Ograniczenie długości hasła — FIX-08
- **`max_length=1024` dla pól `password` w `LoginRequest` i `SetupRequest`** (FIX-08):
  Argon2 jest kosztowny obliczeniowo dla bardzo długich haseł. Poprzednia implementacja
  akceptowała hasła o nieograniczonej długości, co umożliwiało atak DoS. Limit 1024 bajtów
  eliminuje ryzyko (CVSS 7.5) przy zachowaniu praktycznego marginesu dla rzeczywistych haseł.

---

### Naprawiono

Pełna mapa napraw: [FIX_MAP.md](./FIX_MAP_v5.9.0.md)

| ID      | Komponent                     | Opis                                                                        | CVSS  | Status     |
|---------|-------------------------------|-----------------------------------------------------------------------------|-------|------------|
| FIX-01  | `auth.py`                     | Brak ograniczenia prób logowania — in-memory rate limiter (OWASP ASVS V2.2.1) | 9.8   | Naprawiono |
| FIX-02  | `dashboard.py`                | Regresja NULL w M-06 — `COALESCE` → `WHERE status IS NOT NULL`             | —     | Naprawiono |
| FIX-03  | `db.py` `_backup_db_before_migration` | Błąd krytyczny na FS tylko do odczytu → non-fatal z ostrzeżeniem   | —     | Naprawiono |
| FIX-04  | `db.py`                       | `BEGIN EXCLUSIVE` blokował odczyty WAL → `BEGIN IMMEDIATE`                 | —     | Naprawiono |
| FIX-05  | `db.py`                       | Brak ochrony formatu w `PRAGMA user_version` → `:d` + `isinstance`         | —     | Naprawiono |
| FIX-06  | `db.py` backup + migration    | Atomowość M-08 — migracje addytywne, backup non-fatal                      | —     | Naprawiono |
| FIX-07  | `start.py` `_batch_imports_ok`| Command injection — `_VALID_IMPORT_RE` defence-in-depth                    | —     | Naprawiono |
| FIX-08  | `models.py` `LoginRequest`    | DoS przez długie hasło Argon2 → `max_length=1024`                          | 7.5   | Naprawiono |
| FIX-09  | `security.py` `hash_password` | Cichy fallback do SHA-256 → `RuntimeError` bez bezpiecznego backendu       | 8.1   | Naprawiono |
| FIX-10  | `ollama.py`                   | SQL injection w filtrach WHERE → biała lista kolumn                        | 7.5   | Naprawiono |
| FIX-11  | Schema SQLite                 | Brak indeksów `audit_log` → `idx_audit_log_ts`, `idx_audit_log_actor`      | —     | Naprawiono |

---

### Bezpieczeństwo

> Sekcja eksponuje naprawy o najwyższym priorytecie bezpieczeństwa wykryte przez
> security-audit-council (35 znalezisk) i rodo-compliance (9 krytycznych/wysokich).

#### KRYTYCZNE — FIX-01: Brak rate limitingu logowania (CVSS 9.8)
- **Podatność:** Endpoint `/api/auth/login` nie ograniczał liczby prób uwierzytelnienia,
  umożliwiając atak brute-force na hasła użytkowników.
- **Naprawa:** In-memory sliding window (5 prób / 5 min → blokada 10 min). Zgodne z
  OWASP ASVS V2.2.1. Szczegóły implementacji i wyboru architektury: [ADR-004](./adr/ADR-0004-rate-limiting.md).
- **Weryfikacja:** 18 testów jednostkowych w `tests/test_rate_limiter.py`, e2e Playwright
  test `auth-brute-force` (40/40 pass).

#### WYSOKIE — FIX-08: DoS przez długie hasło (CVSS 7.5)
- **Podatność:** Argon2 skaluje złożoność z długością wejścia. Hasło o nieograniczonej
  długości mogło spowodować wyczerpanie CPU serwera.
- **Naprawa:** `max_length=1024` w walidatorze Pydantic `LoginRequest` i `SetupRequest`.
  Odrzucenie następuje przed jakimkolwiek kosztem obliczeniowym (HTTP 422).

#### WYSOKIE — FIX-09: Cichy fallback SHA-256 (CVSS 8.1)
- **Podatność:** `hash_password` w `security.py` stosowała SHA-256 jako awaryjny algorytm
  gdy argon2 i bcrypt były niedostępne. SHA-256 bez soli jest kryptograficznie nieadekwatny
  dla przechowywania haseł.
- **Naprawa:** Jawny `RuntimeError` — brak drogi do produkcji bez bezpiecznego backendu.
  Eliminuje całą klasę ciągłej degradacji bezpieczeństwa. Szczegóły: [ADR-005](./adr/ADR-0005-password-hashing.md).

---

### Usunięto

Brak. Wydanie v5.9.0 jest wyłącznie addytywne — żadna publiczna funkcja API, tabela bazy
danych ani plik konfiguracyjny nie został usunięty ani zmieniony w sposób niezgodny wstecznie.

---

## [5.8.8.1] — Baseline produkcyjny (poprzednie stabilne)

> Wersja bazowa. Szczegółowy rejestr zmian v5.8.x zachowany w `CHANGELOG_v5.8.x.md`.

---

<!-- Linki porównawcze -->
[Nieudostępnione]: https://github.com/sylion/sylion-pipeline/compare/v5.9.0...HEAD
[5.9.0]: https://github.com/sylion/sylion-pipeline/compare/v5.8.8.1...v5.9.0
[5.8.8.1]: https://github.com/sylion/sylion-pipeline/releases/tag/v5.8.8.1
