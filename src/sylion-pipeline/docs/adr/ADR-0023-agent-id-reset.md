# ADR-0023: Reset numeracji agent_id po migracji schematu

**Status:** Accepted
**Data:** 2026-04-19
**Autor:** council re-audit v5.9.0

## Kontekst

Po migracji schematu bazy danych w v5.9.0 (nowe kolumny w tabeli `agents`: `agent_type`, `council_role`, `skill_tags`) wystąpił problem z auto-increment `agent_id` w SQLite. Istniejące bazy mogły zawierać przerwane sekwencje ID po:
- Usunięciu i ponownym seedowaniu agentów
- Ręcznej ingerencji w bazę
- Przerwanej inicjalizacji (`init_db()` zakończonej błędem przed commitem)

Skutek: `agent_id` w nowej bazie zaczynało od wartości ~480 zamiast 1, co powodowało błędy w UI (paginacja, lookup po ID).

Rozważane podejścia:
- **A1** — `DELETE FROM sqlite_sequence WHERE name='agents'; INSERT OR REPLACE ...` przy każdym seedzie (wybrana)
- **A2** — Użycie UUID zamiast INTEGER PRIMARY KEY dla `agent_id`
- **A3** — Zachowanie istniejącej numeracji; UI adaptuje się dynamicznie
- **A4** — Pełne DROP + CREATE TABLE przy migracji (destruktywne)

## Decyzja

Przy każdym wywołaniu `init_db()` na świeżej bazie: reset sekwencji `sqlite_sequence` dla tabeli `agents`. Na istniejącej bazie: migracja addytywna bez naruszania istniejących ID (A1 z warunkiem `IF NOT EXISTS` dla nowych kolumn).

## Konsekwencje

### Pozytywne
- Spójna numeracja agentów od 1 w nowych instalacjach
- Brak destruktywnego DROP TABLE — istniejące dane zachowane
- Bezpieczna idempotentność `init_db()` (wielokrotne wywołanie nie psuje danych)

### Negatywne
- SQLite `sqlite_sequence` reset nie jest transakcyjnie atomowy z INSERT — w przypadku błędu mid-seed możliwa niespójność
- Rezygnacja z UUID (A2) oznacza że `agent_id` nie jest unikalny globalnie między instalacjami (istotne przy przyszłym federation feature)

### Neutralne
- Decyzja o UUID odkładana do v5.10 (breaking change API)

## Alternatywy odrzucone

- **UUID (A2)**: breaking change dla API `/api/agents/{id}` — odłożone do v5.10 z versioned endpoint
- **DROP TABLE (A4)**: nieakceptowalne dla istniejących użytkowników z danymi produkcyjnymi

## Referencje

- `dashboard/db.py` — `init_db()`, `_seed_agents()`
- `docs/MIGRATION_GUIDE.md` — sekcja migracji v5.8.x → v5.9.0
