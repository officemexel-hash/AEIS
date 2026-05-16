# Tooltips PL - operator console SYLION v2

> Krótkie etykiety (max 10 słów PL) dla głównych modułów konsoli operatora.
> Curated from `docs/v2/_drafts/ollama_batch/batch_D/d3_tooltips.md`.

## Główne moduły

| Moduł | Tooltip PL |
|-------|------------|
| Apps Builder | Tworzenie i zarządzanie aplikacjami w jednym miejscu. |
| Federacja | Połącz zasoby w jedną, spójną sieć. |
| Terminal | Zdalny dostęp do systemu w trybie terminala. |
| Ontologia | Definiowanie struktur danych i relacji w organizacji. |
| Policy Plane | Zarządzanie politykami bezpieczeństwa i zgodności. |

## Status dot (dashboard)

> Zaczerpnięte z `docs/v2/_drafts/ollama_batch/batch_E/e5_dashboard_help.md`.

| Symbol | Status | Co oznacza |
|--------|--------|------------|
| zielony | OK | Metryka działa poprawnie. |
| amber | zero | Brak aktywności, ale niekoniecznie błąd. |
| czerwony | niedostępny | Krytyczny problem wymagający interwencji. |

## Komunikaty błędów (skrót)

> Zaczerpnięte z `docs/v2/_drafts/ollama_batch/batch_B/16_error_messages.md`.

| Kod | Komunikat skrócony |
|-----|--------------------|
| `PG_UNAVAILABLE` | PostgreSQL niedostępny: sprawdź czy serwer bazy działa i port 5432 jest otwarty. |
| `MANIFEST_INVALID` | Weryfikacja manifestu nie powiodła się: zweryfikuj składnię YAML i wymagane pola. |
| `RBAC_DENIED` | Dostęp zabroniony przez RBAC: sprawdź uprawnienia roli i polityki ACL. |
| `BREAKER_OPEN` | Circuit breaker otwarty: poczekaj na automatyczne odnowienie lub zmniejsz liczbę żądań. |
| `RATE_LIMIT_EXCEEDED` | Limit przepustowości przekroczony: ogranicz liczbę żądań lub zwiększ limit. |

## Powiązane

- **Glossary** - `glossary.md` (dłuższe wyjaśnienia 2-zdaniowe).
- **FAQ** - `FAQ.md`.
- **ADR-001 / ADR-002** - decyzje architektoniczne.
