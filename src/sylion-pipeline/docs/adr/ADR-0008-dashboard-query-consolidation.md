# ADR-008: Konsolidacja zapytań dashboardu (15 COUNT → 5 GROUP BY)

| Pole          | Wartość                                                          |
|---------------|------------------------------------------------------------------|
| **ID**        | ADR-008                                                          |
| **Tytuł**     | Konsolidacja zapytań COUNT dashboardu i naprawa regresji NULL    |
| **Status**    | Zaakceptowany                                                    |
| **Data**      | 2026-04-19                                                       |
| **Wersja**    | SYLION v5.9.0                                                    |
| **Zmiany**    | M-06, FIX-02                                                     |
| **Metryki**   | 15 round-tripów → 5 round-tripów (−67% DB round-trips)          |
| **Autorzy**   | performance-profiler, code-auditor, pr-reviewer                  |
| **Powiązane** | CHANGELOG_v5.9.0.md §Zmieniono (M-06, FIX-02), ADR-003          |

---

## Status

**Zaakceptowany** — zatwierdzone przez performance-profiler (no regressions, czas odpowiedzi
dashboardu w normie po optymalizacji) i pr-reviewer (bloker B-04: regresja FIX-02
potwierdzona jako naprawiona, C-308 OK, JSON shape preserved).

---

## Kontekst

### Problem wydajnościowy (M-06)

Panel administracyjny SYLION (`/api/admin/dashboard`) prezentował statystyki podzielone
według statusu dla kilku encji (sesje, zadania agentów, logi audytowe, importy, błędy).
Oryginalna implementacja w `dashboard.py` wykonywała jedno zapytanie `COUNT(*)` per
kombinacja (encja, status):

```python
# Poprzednia implementacja (v5.8.x) — przykład dla 3 statusów × 5 encji = 15 zapytań
sessions_active   = db.execute("SELECT COUNT(*) FROM sessions WHERE status = 'active'").fetchone()[0]
sessions_expired  = db.execute("SELECT COUNT(*) FROM sessions WHERE status = 'expired'").fetchone()[0]
sessions_revoked  = db.execute("SELECT COUNT(*) FROM sessions WHERE status = 'revoked'").fetchone()[0]
# ... × 5 encji = 15 zapytań
```

**Profil performance-profiler:**
- 15 oddzielnych round-tripów do SQLite per żądanie dashboardu
- Każdy round-trip: ~2-5 ms (mutex + query planning + I/O)
- Łącznie: ~30-75 ms tylko na zapytania COUNT, przy braku indeksów na `status`

### Refaktoryzacja M-06

Zastąpienie 15 zapytań jednokolumnowych przez 5 zapytań z `GROUP BY status`:

```sql
-- Jedno zapytanie zamiast trzech
SELECT status, COUNT(*) as count
FROM sessions
GROUP BY status
-- Wynik: [('active', 142), ('expired', 38), ('revoked', 5)]
```

**Oryginalna implementacja M-06 (z regresją):**

```python
# Błąd: COALESCE zmienia zachowanie dla NULL statusów
result = db.execute(
    "SELECT COALESCE(status, 'unknown') as status, COUNT(*) "
    "FROM sessions GROUP BY COALESCE(status, 'unknown')"
).fetchall()
```

### Regresja M-06 — FIX-02

`COALESCE(status, 'unknown')` spowodowało regresję w kształcie odpowiedzi JSON:

**Przed M-06 (v5.8.x):**
```json
{"active": 142, "expired": 38, "revoked": 5}
```

**Po M-06 (z COALESCE):**
```json
{"active": 142, "expired": 38, "revoked": 5, "unknown": 3}
```

Klucz `"unknown"` pojawił się w odpowiedzi (dla wierszy z `status IS NULL`), co złamało
kontrakt API — kontrakty klientów frontendowych (C-308) oczekiwały określonego zestawu kluczy.

**Źródło wierszy NULL:** Wiersze z `status IS NULL` nie powinny wchodzić do agregatów
dashboardu — są to rekordy w trakcie tworzenia (w transakcji) lub historyczne rekordy
z błędnej migracji. Oryginalne zapytania `WHERE status = 'active'` etc. z natury je pomijały.

---

## Decyzja

### FIX-02: `WHERE status IS NOT NULL` zamiast COALESCE

Poprawiona implementacja zachowuje optymalizację M-06 (5 zapytań GROUP BY) i przywraca
oryginalne zachowanie (pomijanie NULL statusów):

```python
# Poprawna implementacja (v5.9.0)
_DASHBOARD_QUERIES: dict[str, str] = {
    "sessions": """
        SELECT status, COUNT(*) as count
        FROM sessions
        WHERE status IS NOT NULL
        GROUP BY status
    """,
    "agent_tasks": """
        SELECT status, COUNT(*) as count
        FROM agent_tasks
        WHERE status IS NOT NULL
        GROUP BY status
    """,
    "audit_log_actions": """
        SELECT action, COUNT(*) as count
        FROM audit_log
        WHERE action IS NOT NULL
        GROUP BY action
    """,
    "imports": """
        SELECT status, COUNT(*) as count
        FROM imports
        WHERE status IS NOT NULL
        GROUP BY status
    """,
    "errors": """
        SELECT severity, COUNT(*) as count
        FROM error_log
        WHERE severity IS NOT NULL
        GROUP BY severity
    """,
}

def _execute_dashboard_query(name: str) -> dict[str, int]:
    rows = db.execute(_DASHBOARD_QUERIES[name]).fetchall()
    return {row[0]: row[1] for row in rows}
```

### Dlaczego `WHERE status IS NOT NULL`, nie `COALESCE`

| Kryteria                    | `COALESCE(status, 'unknown')` | `WHERE status IS NOT NULL` |
|-----------------------------|-------------------------------|----------------------------|
| Pomija wiersze NULL          | Nie (agreguje jako 'unknown') | Tak (wiersze pomijane)     |
| JSON shape zgodny z v5.8.x  | Nie (dodaje klucz 'unknown')  | Tak                        |
| Kontrakt C-308 zachowany    | Nie                           | Tak                        |
| Semantycznie poprawne        | Częściowo                     | Tak                        |
| Wydajność (indeks na status) | Porównywalna                  | Lepsza (IS NOT NULL szybsze niż COALESCE na indeksie) |

### Indeksy wspierające zapytania (FIX-11 + M-06)

Nowe indeksy z FIX-11 (`idx_audit_log_ts`, `idx_audit_log_actor`) uzupełniają
optymalizację M-06 dla tabeli `audit_log`. Planuje się dodanie `idx_sessions_status`
i `idx_agent_tasks_status` w v5.9.1 po analizie query planner.

---

## Konsekwencje

### Pozytywne

- **Redukcja round-tripów o 67%** — 15 → 5 zapytań per żądanie dashboardu.
- **Mniejsze zużycie zasobów SQLite** — mniejsza rywalizacja o mutex bazy danych;
  ważne przy jednoczesnym obciążeniu agentów w tle.
- **JSON shape preserved** — kontrakt API C-308 zachowany; zero breaking changes
  dla klientów frontendowych.
- **Czytelność kodu** — `_DASHBOARD_QUERIES` jako słownik deklaratywny ułatwia
  dodawanie nowych metryk i code review.
- **Testowalność** — zapytania SQL jako stałe łańcuchy są łatwe do testowania
  jednostkowego z bazą in-memory SQLite.

### Negatywne

- **Zmiana granularności danych** — wiersze z `status IS NULL` są wykluczone z agregatów.
  Jest to zachowanie celowe (zgodne z v5.8.x), ale wymaga świadomości przy dodawaniu
  nowych statusów — nowe wartości muszą być jawnie zapisywane (nie NULL) by pojawiły się
  w dashboardzie.
- **Brak agregatu dla 'unknown'** — jeśli monitoring danych jakościowych wymaga zliczania
  rekordów z NULL statusem, konieczne jest dodanie oddzielnego zapytania diagnostycznego.
  Nie jest to wymaganie v5.9.0.

### Neutralne

- Zmiana jest transparentna dla API — endpoint `/api/admin/dashboard` zwraca identyczny
  kształt JSON jak w v5.8.x.
- Performance-profiler potwierdził: brak regresji czasowych w pozostałych endpointach
  po wprowadzeniu M-06 + FIX-02.
- `_DASHBOARD_QUERIES` jako module-level constant umożliwia przyszłą refaktoryzację
  do SQLAlchemy Core bez zmiany logiki biznesowej.

---

## Alternatywy rozważane

### Opcja A: Utrzymanie 15 zapytań (status quo v5.8.x)

**Odrzucona.** Performance-profiler zidentyfikował ten wzorzec jako najważniejsze
źródło opóźnień w panelu administracyjnym. Refaktoryzacja jest prosta, bezpieczna
i daje mierzalne korzyści bez zmiany semantyki.

### Opcja B: `COALESCE(status, 'unknown')` (oryginalna implementacja M-06)

**Odrzucona (FIX-02).** Zmiana kształtu JSON (dodanie klucza 'unknown') złamała
kontrakt C-308. Zachowanie oryginalne jest pożądane: NULL statusy są pomijane.

### Opcja C: Widoki materializowane / tabela cache dla statystyk dashboardu

**Rozważona, odłożona.** SQLite nie wspiera widoków materializowanych. Tabela cache
aktualizowana triggerem lub harmonogramem byłaby skalowalnym rozwiązaniem dla dużych
zbiorów danych, ale jest over-engineering dla aktualnej skali (~10K rekordów).
Zaplanowane do oceny gdy liczba wierszy przekroczy 100K.

### Opcja D: Agregacja w warstwie aplikacyjnej (Python) po pobraniu wszystkich wierszy

**Odrzucona.** Transfer wszystkich wierszy do pamięci Python w celu zliczenia jest
wielokrotnie gorszy niż `GROUP BY` w SQLite. Brak korzyści; znacznie większe zużycie
pamięci i czasu transferu.

### Opcja E: Osobny endpoint `/api/admin/dashboard/stats` z cachingiem HTTP (Cache-Control)

**Rozważona, odłożona.** Cache HTTP (ETags, Cache-Control: max-age=60) mógłby eliminować
zbędne zapytania dla szybko zmieniających się statystyk. Wymaga refaktoryzacji warstwy
HTTP i nie jest priorytetem v5.9.0.
