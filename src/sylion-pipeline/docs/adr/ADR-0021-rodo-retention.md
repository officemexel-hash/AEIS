# ADR-0021: Polityka retencji danych osobowych (RODO Art. 5(1)(e))

**Status:** Accepted
**Data:** 2026-04-19
**Autor:** council re-audit v5.9.0 / compliance

## Kontekst

SYLION przechowuje w lokalnej bazie SQLite dane osobowe w następujących kontekstach:
- Logi zapytań użytkownika (treść promptów, timestamp, `session_id`)
- Klucze API providerów (związane z kontem użytkownika — dane osobowe pośrednie)
- Historia agentów: `agent_id`, opis, `last_run`, wyniki

Brak zdefiniowanej polityki retencji narusza RODO Art. 5(1)(e) (zasada ograniczenia przechowywania) i UODO. Audyt v5.9.0 wykazał brak jakichkolwiek mechanizmów automatycznego usuwania lub anonimizacji starych danych.

Rozważane podejścia:
- **R1** — Brak retencji (status quo — niezgodny z RODO)
- **R2** — Retencja oparta o czas (rolling window 90 dni dla logów)
- **R3** — Retencja oparta o zdarzenia (usunięcie po żądaniu użytkownika + 30 dni grace)
- **R4** — Pełna anonimizacja po 90 dniach zamiast usuwania

## Decyzja

Wdrożenie **R2 + R3 łącznie**: automatyczna retencja 90 dni dla logów zapytań (cron w `db.py`) oraz obsługa żądania usunięcia (RODO Art. 17 "prawo do bycia zapomnianym") z 30-dniowym grace period. Klucze API usuwane natychmiastowo na żądanie.

## Konsekwencje

### Pozytywne
- Zgodność z RODO Art. 5(1)(e) i Art. 17
- Redukcja rozmiaru bazy SQLite przy długotrwałym działaniu
- Jasna dokumentacja polityki w `PRIVACY_POLICY_PL.md` i `PRIVACY_POLICY_DE.md`

### Negatywne
- Utrata historycznych logów po 90 dniach — niemożność retrospekcji starszych sesji dla celów debugowania
- Implementacja żądania DSR (Art. 17) wymaga dedykowanego endpointu `/api/user/delete` (scope v5.10)

### Neutralne
- Użytkownicy mogą eksportować własne dane przed upłynięciem okresu retencji (prawo do przenoszenia — Art. 20)

## Alternatywy odrzucone

- **R4 (anonimizacja)**: technicznie złożona, trudna do audytowania; usuwanie daje lepszą pewność prawną
- **R1 (brak retencji)**: niezgodne z RODO — odrzucone

## Referencje

- `docs/RODO_COMPLIANCE.md` — pełna analiza compliance
- `docs/PRIVACY_POLICY_PL.md`, `PRIVACY_POLICY_DE.md` — polityki prywatności
- RODO Art. 5(1)(e), Art. 17
