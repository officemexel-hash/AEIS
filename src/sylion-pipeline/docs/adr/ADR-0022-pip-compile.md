# ADR-0022: Lockfile zarządzany przez pip-compile (requirements-lock.txt)

**Status:** Accepted
**Data:** 2026-04-19
**Autor:** council re-audit v5.9.0

## Kontekst

Przed v5.9.0 projekt zawierał `requirements.txt` z niedoprecyzowanymi wersjami zależności (np. `fastapi>=0.100`, `pydantic`). Skutkowało to:
- Niereprodukowalnymi buildami — różne wersje bibliotek na różnych maszynach
- Audyt v5.9.0 wykazał brak `requirements.txt` w katalogu głównym (plik usunięty po refactorze), co powodowało `pip install -r requirements.txt → FileNotFoundError`
- `install.sh` używał `requirements-lock.txt` z hashami, ale dokumentacja wskazywała na nieistniejący `requirements.txt`

Rozważane podejścia:
- **P1** — Przywrócenie `requirements.txt` z pinned versions (ręcznie utrzymywany)
- **P2** — `pip-compile` generujący `requirements-lock.txt` z hashami z `requirements.in` (wybrana)
- **P3** — Poetry / PDM jako menadżer zależności z własnym lockfile
- **P4** — Conda environment z `environment.yml`

## Decyzja

Standardem dla projektu jest **`pip-compile` (pip-tools)**. Plik `requirements.in` zawiera high-level zależności, a `requirements-lock.txt` jest generowany przez `pip-compile --generate-hashes`. `install.sh` używa wyłącznie `requirements-lock.txt`. Dokumentacja zaktualizowana we wszystkich plikach user manual (v5.9.0).

## Konsekwencje

### Pozytywne
- Pełna reprodukowalność instalacji dzięki pinned hashe SHA-256
- `install.sh --require-hashes` zapewnia supply-chain integrity
- Jeden autorytatywny plik zależności (`requirements-lock.txt`) eliminuje niejednoznaczność

### Negatywne
- Developerzy muszą pamiętać o regeneracji `requirements-lock.txt` po każdej zmianie `requirements.in` (dodatkowy krok w procesie wydania)
- `pip-compile` musi być zainstalowany w środowisku deweloperskim jako dodatkowe narzędzie

### Neutralne
- Migracja z Poetry/PDM odrzucona ze względu na prostotę projektu i brak potrzeby virtualenv management

## Alternatywy odrzucone

- **Poetry**: nadmierna złożoność dla projektu tej skali; brak integracji z `install.sh`
- **Conda**: nieodpowiednie dla środowisk bez conda (Windows VPS, Linux bez Miniconda)

## Referencje

- `requirements.in` — wysokopoziomowe zależności
- `requirements-lock.txt` — wygenerowany lockfile z hashami
- `install.sh` (linia `REQ_FILE`) — używa `requirements-lock.txt`
