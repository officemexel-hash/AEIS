# ADR-005: Haszowanie haseł — usunięcie fallbacku SHA-256

| Pole          | Wartość                                                          |
|---------------|------------------------------------------------------------------|
| **ID**        | ADR-005                                                          |
| **Tytuł**     | Hard-fail bez bezpiecznego backendu haszowania; usunięcie SHA-256 |
| **Status**    | Zaakceptowany                                                    |
| **Data**      | 2026-04-19                                                       |
| **Wersja**    | SYLION v5.9.0                                                    |
| **Zmiany**    | FIX-09, FIX-08                                                   |
| **Standard**  | OWASP ASVS V2.4, NIST SP 800-63B §5.1.1.2, RODO art. 32        |
| **CVSS**      | 8.1 (High) — rozwiązano                                          |
| **Autorzy**   | security-audit-council, pr-reviewer                              |
| **Powiązane** | ADR-004, CHANGELOG_v5.9.0.md §Bezpieczeństwo                    |

---

## Status

**Zaakceptowany** — zatwierdzone przez security-audit-council (znalezisko SEC-009, CVSS 8.1)
i pr-reviewer (bloker B-02). Implementacja zweryfikowana przez 12 testów jednostkowych
(`tests/test_password_hashing.py`).

Decyzja jest **nieodwracalna** w kontekście haszowania nowych haseł — brak drogi powrotu
do SHA-256 dla nowych zapisów. Stare hasła zahaszowane SHA-256 (legacy, przed SYLION v5.9.0)
mogą być przeczytane w trybie tylko do odczytu (weryfikacja) do czasu wymuszonej migracji
(patrz sekcja Konsekwencje).

---

## Kontekst

### Podatność (CVSS 8.1 — High)

Funkcja `hash_password` w `security.py` zawierała następującą logikę fallback:

```python
def hash_password(password: str) -> str:
    if ARGON2_AVAILABLE:
        return argon2.hash(password)
    if BCRYPT_AVAILABLE:
        return bcrypt.hash(password)
    # NIEBEZPIECZNE — cichy fallback
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()
```

**Problem:** W środowiskach gdzie `argon2-cffi` i `bcrypt` nie były zainstalowane
(np. minimalne obrazy Docker, środowiska CI z niepełnymi zależnościami, ręczne instalacje
bez `pip install -r requirements.txt`), SYLION cicho zapisywał hasła jako niesalted SHA-256.

**Skutki kryptograficzne:**
- SHA-256 jest funkcją skrótu ogólnego przeznaczenia, **nie** funkcją haszowania haseł.
  Nie zawiera soli, nie jest adaptacyjnie wolna, podatna na ataki słownikowe GPU i rainbow tables.
- Hasła zahaszowane SHA-256 mogą być łamane w tempie > 10 miliardów prób/sekundę na GPU
  (vs. ~1000 prób/sekundę dla Argon2id z typowymi parametrami).
- **Cicha degradacja** — użytkownik końcowy i administrator nie mają możliwości wykrycia,
  że hasła są przechowywane w słabym formacie, bez weryfikacji zewnętrznej.

**CVSS v3.1:** Base Score 8.1 (High) — Confidentiality: High (ujawnienie hasła → przejęcie konta).

**OWASP ASVS V2.4.1:** „Verify that passwords are stored using an appropriate, modern,
secure password hashing algorithm."

**RODO art. 32:** Wymóg wdrożenia odpowiednich środków technicznych zapewniających
bezpieczeństwo danych — SHA-256 dla haseł narusza ten wymóg.

### Analiza istniejących rekordów (v5.8.x)

Audyt bazy danych wykazał, że w środowiskach deweloperskich (nie produkcja) istniały
rekordy z hasłami w formacie SHA-256 (identyfikowalne po braku prefiksu `$argon2` lub `$2b$`).
Środowisko produkcyjne (v5.8.8.1) posiadało prawidłowe zależności — nie stwierdzono
rekordów SHA-256 w produkcji.

### Wymagania

1. Żadna ścieżka produkcyjna nie może haszować haseł algorytmem słabszym niż bcrypt.
2. Brak bezpiecznego backendu musi być wykryty **przed** zapisaniem pierwszego hasła.
3. Rozwiązanie nie może łamać istniejących instalacji z prawidłowo zainstalowanymi zależnościami.
4. Czytelny komunikat błędu — administrator musi wiedzieć jak naprawić problem.

---

## Decyzja

### Zmiany w `hash_password` (FIX-09)

Usuwamy fallback SHA-256 i zastępujemy go jawnym `RuntimeError`:

```python
def hash_password(password: str) -> str:
    """
    Haszuje hasło używając Argon2id (preferowany) lub bcrypt.
    Raises:
        RuntimeError: jeśli żaden bezpieczny backend nie jest dostępny.
                      Błąd musi zostać naprawiony przez instalację argon2-cffi lub bcrypt.
    """
    if ARGON2_AVAILABLE:
        return argon2.hash(password)
    if BCRYPT_AVAILABLE:
        return bcrypt.hash(password)
    raise RuntimeError(
        "Brak bezpiecznego backendu haszowania haseł. "
        "Zainstaluj argon2-cffi (zalecane): pip install argon2-cffi\n"
        "Lub bcrypt (alternatywa): pip install bcrypt\n"
        "SHA-256 nie jest akceptowalnym algorytmem haszowania haseł."
    )
```

### Tryb tylko do odczytu dla haseł SHA-256 (legacy)

Funkcja `verify_password` zachowuje zdolność **weryfikacji** starych haszy SHA-256
(tylko do odczytu, nigdy do zapisu), umożliwiając wymuszoną zmianę hasła przy
kolejnym logowaniu:

```python
def verify_password(plain: str, hashed: str) -> bool:
    if hashed.startswith("$argon2"):
        return argon2.verify(plain, hashed)
    if hashed.startswith("$2b$") or hashed.startswith("$2a$"):
        return bcrypt.verify(plain, hashed)
    # Tryb tylko do odczytu dla legacy SHA-256
    if len(hashed) == 64 and all(c in "0123456789abcdef" for c in hashed):
        import hashlib
        import warnings
        warnings.warn(
            "Hasło użytkownika zahaszowane SHA-256 (legacy). "
            "Wymagana zmiana hasła przy następnym logowaniu.",
            DeprecationWarning, stacklevel=2
        )
        return hashlib.sha256(plain.encode()).hexdigest() == hashed
    raise ValueError(f"Nierozpoznany format hasła: {hashed[:10]}...")
```

Po pomyślnej weryfikacji SHA-256: hasło jest natychmiast rehashowane do Argon2id
i zapisywane z powrotem do bazy danych (transparent upgrade przy logowaniu).

### Ograniczenie długości hasła (FIX-08)

Jednoczesnie wprowadzamy `max_length=1024` w modelach Pydantic:

```python
class LoginRequest(BaseModel):
    username: str
    password: str = Field(..., max_length=1024)

class SetupRequest(BaseModel):
    password: str = Field(..., max_length=1024)
```

Argon2 z parametrami `memory_cost=65536` (64 MB), `time_cost=3` na haśle o długości
10 MB zajmuje ~2-3 sekundy CPU, co umożliwia trivialny DoS. Limit 1024 bajtów eliminuje
ryzyko (CVSS 7.5) przy zachowaniu marginesu dla rzeczywistych haseł (najdłuższe
bezpieczne hasła to ~200-500 znaków).

---

## Konsekwencje

### Pozytywne

- **Eliminacja CVSS 8.1** — żadna ścieżka kodu nie może zapisać hasła w formacie SHA-256.
- **Fail-fast** — błąd konfiguracji (brak argon2/bcrypt) jest wykrywany przy pierwszej
  próbie rejestracji/zmiany hasła, nie przy retrospektywnym audycie.
- **Czytelny komunikat** — `RuntimeError` zawiera konkretną instrukcję naprawy.
- **Zgodność ze standardami** — OWASP ASVS V2.4.1, NIST SP 800-63B §5.1.1.2, RODO art. 32.
- **Transparent upgrade** — użytkownicy legacy SHA-256 są automatycznie migrowani przy
  pierwszym logowaniu bez ingerencji administratora.
- **Eliminacja CVSS 7.5 (DoS)** — `max_length=1024` odcina ataki długim hasłem.

### Negatywne

- **Breaking change dla instalacji bez zależności** — środowiska z nieprawidłowo
  zainstalowanymi zależnościami zobaczą `RuntimeError` przy rejestracji. Jest to
  **zamierzone** — lepiej jawny błąd niż cicha degradacja bezpieczeństwa.
- **Konieczność rehashowania legacy haseł** — użytkownicy z hasłami SHA-256 muszą
  się zalogować by zainicjować transparent upgrade. Nie ma automatycznej migracji
  wsadowej (wymaga znajomości plaintext, co jest niemożliwe).

### Neutralne

- `requirements.txt` (lockfile z M-04) zawiera `argon2-cffi>=23.1.0` jako hard dependency —
  poprawna instalacja gwarantuje dostępność Argon2.
- Decyzja jest spójna z zasadą minimalnego zaskoczenia: kod produkcyjny nie powinien
  zawierać cichych ścieżek degradacji bezpieczeństwa.

---

## Alternatywy rozważane

### Opcja A: Zachowanie fallbacku SHA-256 z ostrzeżeniem (deprecation warning)

**Odrzucona.** Ostrzeżenia (warnings) są łatwo ignorowane przez administratorów.
Cicha degradacja bezpieczeństwa jest gorsza niż jawny błąd. OWASP ASVS jednoznacznie
zabrania przechowywania haseł w SHA-256 bez adaptacyjnego kosztu.

### Opcja B: SHA-256 + PBKDF2 jako fallback (wolniejszy niż bare SHA-256)

**Odrzucona.** PBKDF2-SHA256 jest akceptowalny (NIST FIPS 140-2), ale gorszy od Argon2id
w ochronie przed atakami GPU/ASIC. Wprowadzanie kolejnego algorytmu fallback zwiększa
złożoność bez uzasadnienia — `requirements.txt` zapewnia argon2-cffi w każdej instalacji.

### Opcja C: Wymuszenie argon2-cffi jako wymagania setuptools (no-fallback by design)

**Rozważona, częściowo przyjęta.** `requirements.in` zawiera `argon2-cffi` jako hard
dependency. Jednakże `RuntimeError` w `hash_password` pozostaje jako defence-in-depth
na wypadek ręcznej instalacji bez pip lub błędu w środowisku build.

### Opcja D: Natychmiastowe odrzucenie logowania dla kont SHA-256 (force password reset)

**Odrzucona.** Wymusiłoby to ręczną interwencję administratora dla każdego użytkownika
legacy. Transparent upgrade przy pierwszym logowaniu jest ergonomicznie lepszy i nie
wymaga downtime serwisu.
