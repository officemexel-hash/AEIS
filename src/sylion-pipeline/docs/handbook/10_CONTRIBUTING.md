# Contributing — SYLION Pipeline v5.9.2

Wytyczne dla osob chcacych wspolpracowac przy rozwoju pipeline. Obejmuja styl kodu, testy, proces ADR, template PR i oczekiwane sprawdzenia CI.

---

## Spis tresci

- [Styl kodu (ruff)](#styl-kodu-ruff)
- [Testy (pytest)](#testy-pytest)
- [Proces ADR](#proces-adr)
- [PR Template](#pr-template)
- [CI — oczekiwane sprawdzenia](#ci--oczekiwane-sprawdzenia)
- [Konwencje commitow](#konwencje-commitow)
- [Zglaszanie bledow security](#zglaszanie-bledow-security)

---

## Styl kodu (ruff)

### Konfiguracja

Projekt uzywa `ruff` jako jedynego lintera i formattera (zastepuje flake8, isort, black).

```bash
# Instalacja (juz w requirements-lock.txt)
pip install ruff

# Sprawdzenie
ruff check .

# Automatyczna naprawa
ruff check --fix .

# Formatowanie
ruff format .
```

### Reguly

Konfiguracja w `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
    "S",   # flake8-bandit (security)
    "ANN", # type annotations
]
ignore = [
    "ANN101",  # missing self annotation (redundant)
    "S101",    # assert usage (tylko dla testow OK)
]
```

### Wymagania obowiazkowe

- 0 bledow ruff (CI blokuje PR z bledami)
- 0 warningow ruff (CI blokuje PR z warningami)
- Type hints dla wszystkich nowych funkcji publicznych (Python 3.12+)
- Docstringi dla modulow i klas publicznych

### Przykladowe poprawne sygnatury

```python
def select_tier(
    task_description: str,
    files_changed: list[str],
    security_sensitive_flag: bool = False,
) -> Tier:
    """Classify task by cost tier for LLM routing.

    Args:
        task_description: Human-readable task description.
        files_changed: List of file paths that will be modified.
        security_sensitive_flag: Force PREMIUM tier if True.

    Returns:
        Tier enum value (LOCAL=0, CHEAP=1, STANDARD=2, PREMIUM=3).
    """
```

---

## Testy (pytest)

### Uruchomienie

```bash
# Wszystkie testy
pytest

# Z pomiarem pokrycia
pytest --cov=dashboard --cov-report=html

# Tylko konkretna kategoria
pytest tests/test_health_v2.py -v

# Szybki smoke test (bez testow wolnych)
pytest -m "not slow"
```

### Wymagania

- Nowy kod musi miec testy pokrywajace przynajmniej:
  - Happy path (poprawne wejscie)
  - Error path (bledne wejscie, blady zewnetrzne)
  - Edge cases (wartosci graniczne, puste dane)
- Dla endpointow API: test auth (401), CSRF (403), rate limit (429), valid (200)
- Dla operacji DB: test z in-memory SQLite, test rollback przy bledzie
- Brak mockowan SQLite — uzywaj fixture z in-memory DB

### Fixture in-memory DB (standard)

```python
import pytest
from dashboard.db import get_conn, init_db

@pytest.fixture
def db_conn():
    """Fresh in-memory SQLite for each test."""
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()

@pytest.fixture
def client(db_conn):
    """Test client with in-memory DB."""
    from fastapi.testclient import TestClient
    from dashboard.app import app
    with TestClient(app) as c:
        yield c
```

### Konwencja nazewnicza testow

```
test_<co_testujemy>_<kiedy_warunek>_<oczekiwany_wynik>

# Przyklady:
test_login_valid_credentials_returns_200
test_login_wrong_password_returns_401
test_login_rate_limit_exceeded_returns_429
test_csrf_missing_token_returns_403
test_upload_zip_path_traversal_returns_400
test_budget_guard_exceeded_blocks_llm_calls
```

### Oznaczenia

```python
@pytest.mark.slow         # test > 5 sekund (wyklucz z szybkiego CI)
@pytest.mark.security     # test bezpieczenstwa (zawsze uruchamiaj)
@pytest.mark.integration  # test integracyjny (wymaga zewnetrznych serwisow)
```

---

## Proces ADR

### Kiedy tworzyc ADR

ADR (Architecture Decision Record) jest wymagany gdy:
- Zmiana dotyka architektury systemu (nowy modul, nowa zaleznosc zewnetrzna)
- Zmiana dotyka bezpieczenstwa (nowy endpoint, zmiana auth, nowe permissions)
- Zmiana jest nieodwracalna lub trudno odwracalna
- Zmiana jest kontrowersyjna lub nie jest oczywistym wyborem

Drobne naprawy (fix typo, refactor bez zmiany API) nie wymagaja ADR.

### Format ADR

```markdown
# ADR-NNNN: [Tytul decyzji]

Data: RRRR-MM-DD
Status: PROPOSED | ACCEPTED | REJECTED | SUPERSEDED | DEPRECATED
Autorzy: [imie/nick]
Supersedes: ADR-MMMM (jesli zastepuje inna decyzje)
Related: ADR-PPPP, ADR-QQQQ

## Kontekst

[Co sie dzieje, jaki problem rozwiazujemy. Max 2 akapity.]

## Decyzja

[Jaka decyzje podjeto i dlaczego. Konkretne, aktywne zdania.]

## Konsekwencje

### Pozytywne

- [Korzysc 1]
- [Korzysc 2]

### Negatywne / ryzyka

- [Ryzyko lub koszt 1]
- [Ryzyko lub koszt 2]

### Neutralne

- [Zmiana bez jednoznacznej oceny]
```

### Numeracja

Format: `ADR-NNNN` gdzie NNNN to kolejny numer (zero-padded do 4 cyfr). Nastepny numer po v5.9.2: `ADR-0036`.

Plik: `docs/adr/ADR-NNNN-krotki-opis-kebab-case.md`

---

## PR Template

Kazdy Pull Request musi uzywac template z `.github/pull_request_template.md`:

```markdown
## Opis zmiany

[Co zmieniam i dlaczego — max 3 zdania]

## Typ zmiany

- [ ] bugfix (non-breaking)
- [ ] feature (non-breaking)
- [ ] breaking change
- [ ] documentation
- [ ] security fix

## Checklist

- [ ] ruff check . -- 0 bledow
- [ ] pytest -- wszystkie testy zielone
- [ ] Nowe testy dodane dla nowego kodu
- [ ] ADR wygenerowane (jesli decyzja architektoniczna)
- [ ] CHANGELOG zaktualizowany
- [ ] Brak plain-text secrets w kodzie (grep -r "sk-" .)
- [ ] Brak plikow .env w commicie
- [ ] Dokumentacja zaktualizowana (jesli zmiana API)

## Security impact

[Czy zmiana ma wplyw na bezpieczenstwo? Jesli tak — opisz krotko]

## Jak przetestowac

[Krok po kroku jak przetestowac lokalnie]

## Powiazane ADR / Issues

ADR-NNNN, Issue #NNN
```

---

## CI — oczekiwane sprawdzenia

GitHub Actions uruchamia nastepujace workflowy (`.github/workflows/`):

### ci.yml (pull_request, push do main)

| Krok          | Warunek sukcesu                              |
|---------------|----------------------------------------------|
| ruff check    | 0 bledow, 0 warningow                        |
| pytest        | >= 95% PASS, 0 FAIL                          |
| pip-audit     | 0 CVE critical, 0 CVE high                  |
| env_lint.py   | Brak zmiennych srodowiskowych poza whitelist |
| validate-manifest | SKILL_MANIFEST.md aktualny             |

### security.yml (push do main, codziennie)

| Krok              | Warunek sukcesu                          |
|-------------------|------------------------------------------|
| pip-audit (pelen) | 0 CVE critical                           |
| secret scan       | 0 plain-text kluczy w kodzie             |
| Dependabot review | Wszystkie alerty reviewed                |

### docker.yml (push do main z tagiem v*.*)

| Krok           | Warunek sukcesu                           |
|----------------|-------------------------------------------|
| docker build   | Build bez bledow (multi-stage)            |
| docker test    | Health check HTTP 200 po uruchomieniu     |
| docker push    | Push do rejestru (tylko tagi v*.*.*)      |

### Lokalne uruchomienie CI

```bash
# Wszystkie sprawdzenia CI lokalnie (przed PR)
make ci

# Lub krok po kroku:
ruff check .
pytest
pip-audit
python scripts/env_lint.py
```

---

## Konwencje commitow

Pipeline uzywa Conventional Commits:

```
<type>(<scope>): <description>

[optional body]

[optional footer: ADR-NNNN, Fixes #NNN]
```

### Typy

| Typ      | Kiedy                                           |
|----------|-------------------------------------------------|
| feat     | Nowa funkcja                                    |
| fix      | Naprawa bledu                                   |
| sec      | Naprawa bezpieczenstwa                          |
| docs     | Zmiana dokumentacji                             |
| test     | Dodanie lub zmiana testow                       |
| refactor | Refaktoryzacja bez zmiany zachowania            |
| chore    | Zmiany konfiguracji, CI, zaleznosci             |
| perf     | Optymalizacja wydajnosci                        |

### Przyklady

```
feat(wireguard): add kill switch activation via API

Implements POST /api/devices/kill-switch with enable/disable action.
Kill switch uses iptables OUTPUT DROP policy on Mudi router.

ADR-0027

fix(csrf): cover /api/pipeline/run with CSRF middleware

Endpoint was whitelisted but should not be — it's a mutating endpoint.
Now requires X-CSRF-Token header.

Fixes #142, ADR-0026

sec(auth): replace MD5 session tokens with UUID4

Previous implementation used MD5(username+timestamp) which is predictable.
Now using secrets.token_hex(32).
```

---

## Zglaszanie bledow security

Bledy bezpieczenstwa NIE powinny byc zglaszane jako publiczne Issues na GitHub.

Wyslij raport na: security@sylion.example

Format raportu:

```
Temat: [SECURITY] Krotki opis podatnosci

CVE-ID (jesli znane): CVE-XXXX-NNNNN lub "nieznane"
CVSS Score (szacunek): X.X
OWASP Kategoria: A0X
Wersja dotknieta: v5.9.X

Opis:
[Co odkryto — jasno i bez technicznych skrotow]

Reprodukcja:
1. Krok 1
2. Krok 2
[...]

Dowod (Proof of Concept):
[Kod lub curl — opcjonalnie]

Wplyw:
[Co moze zrobic atakujacy po wyeksploatowaniu]

Sugerowana naprawa:
[Opcjonalnie]
```

Czas odpowiedzi: 24h potwierdzenie. Naprawa P1 SEC: < 24h dla krytycznych.

---

## Lokalne srodowisko developerskie

```bash
# Klonowanie
git clone https://github.com/your-org/sylion-pipeline.git
cd sylion-pipeline

# Instalacja developerska
bash install.sh
source venv/bin/activate

# Instalacja dodatkowych narzedzi dev
pip install ruff pytest pytest-cov pre-commit

# Konfiguracja pre-commit hooks
pre-commit install

# Uruchomienie w trybie dev (hot-reload)
SYLION_ENV=development python dashboard/start.py --reload

# Uruchomienie testow w watch mode
pytest --watch tests/
```

---

*Poprzednia sekcja: [09_GLOSSARY.md](./09_GLOSSARY.md)*
*Powrot do indeksu: [README.md](./README.md)*
