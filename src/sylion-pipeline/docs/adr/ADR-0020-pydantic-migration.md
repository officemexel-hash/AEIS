# ADR-0020: Migracja walidacji danych do Pydantic v2

**Status:** Accepted
**Data:** 2026-04-19
**Autor:** council re-audit v5.9.0

## Kontekst

W v5.8.8.1 (ADR-0001) utrzymano ręczny guard `isinstance(a, dict) and "id" in a` jako stop-gap. Pydantic był już obecny w `start.py` ale nieuwzględniony w `requirements-lock.txt`. Wraz z v5.9.0 Pydantic v2 jest poprawnie spięty jako zależność i używany do walidacji konfiguracji agentów (`agents.yaml`) i danych wejściowych API.

Rozważane warianty:
- **W1** — Zachować ręczne guardy (status quo z v5.8.8.1)
- **W2** — Pydantic v2 `BaseModel` z `model_validator` (wybrana)
- **W3** — Marshmallow jako alternatywa do walidacji schematów
- **W4** — TypedDict + runtime `isinstance` checks

## Decyzja

Migracja do **Pydantic v2 `BaseModel`** dla walidacji `AgentConfig` i `ProviderKey`. Pydantic generuje czytelne `ValidationError` z kontekstem pola, co zastępuje "paranoidalne" ręczne guardy z ADR-0001.

## Konsekwencje

### Pozytywne
- Czytelne komunikaty błędów walidacji z nazwami pól i typami
- Automatyczna typizacja i coercion (np. `str` → `int` dla portów)
- Stop-gap guard z ADR-0001 usunięty — redukcja długu technicznego
- Pydantic v2 jest ~5× szybszy od v1 przy walidacji dużych list agentów

### Negatywne
- Zależność od zewnętrznej biblioteki (`pydantic~=2.7`) — wzrost rozmiaru paczki o ~4 MB
- Istnieje ryzyko breaking changes między minor wersjami Pydantic v2; wymaga pin w `requirements-lock.txt`

### Neutralne
- Istniejące testy (`test_seed_agents_*`) wymagały aktualizacji sygnatur — zakres: 3 pliki testów

## Alternatywy odrzucone

- **Marshmallow**: dojrzały, ale wolniejszy od Pydantic v2 i mniej zintegrowany z type hints
- **TypedDict + isinstance**: brak automatycznego error reporting, powielenie problemu z ADR-0001

## Referencje

- ADR-0001 (seed-agents-guard) — pierwotna decyzja o stop-gap
- `dashboard/db.py` — `AgentConfig`, `ProviderKey` modele
- `requirements-lock.txt` — pin `pydantic==2.7.4`
