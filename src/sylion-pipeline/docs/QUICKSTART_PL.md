# Quickstart — SYLION v5.9.1 (Polski)

Od zera do pierwszego loginu w 5 minut.

---

## Wymagania

Przed instalacją upewnij się, że masz:

| Element     | Wymaganie           |
|-------------|---------------------|
| Python      | 3.11 lub nowszy (3.12 zalecane) |
| RAM         | minimum 8 GB        |
| System      | Linux, macOS lub Windows 10/11 |
| Dysk        | 2 GB wolnego miejsca |
| Połączenie  | Internet (tylko podczas instalacji, do pobrania zależności) |

Sprawdź wersję Pythona:

```bash
python --version
# lub
python3 --version
```

---

## Krok 1 — Instalacja

### Linux / macOS

```bash
# Extract SYLION_v591.zip to your target directory
cd sylion
chmod +x install.sh
./install.sh
```

Skrypt `install.sh` automatycznie:

- tworzy wirtualne środowisko Python (`venv`)
- instaluje wszystkie zależności (`pip install -r requirements-lock.txt`)
- generuje domyślny plik `.env` na podstawie `.env.example`
- inicjalizuje bazę danych SQLite w `~/sylion/sylion.db`

### Windows

```bat
# Extract SYLION_v591.zip to your target directory
cd sylion
install.bat
```

`install.bat` wykonuje te same kroki co skrypt Linux/macOS, dostosowane do środowiska Windows.

---

## Krok 2 — Konfiguracja kluczy API

Po instalacji otwórz plik `.env` w edytorze tekstowym i uzupełnij klucze API modeli, z których zamierzasz korzystać:

```ini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

Klucze możesz też ustawić lub zmienić później przez Dashboard — patrz FAQ, pytanie nr 1.

---

## Krok 3 — Uruchomienie serwera

```bash
# Linux / macOS
python dashboard/start.py

# Windows
python dashboard/start.py
```

Jeśli instalacja przebiegła pomyślnie, w konsoli zobaczysz:

```
[SYLION] Starting server on http://localhost:8421
[SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
[SYLION] Database: /home/<user>/sylion/sylion.db (WAL mode)
[SYLION] Agents loaded: 48
[SYLION] Council models: Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro
```

Skopiuj **setup token** — będzie potrzebny w następnym kroku.

---

## Krok 4 — Pierwsze logowanie i ustawienie hasła

1. Otwórz przeglądarkę i przejdź pod adres:

```
http://localhost:8421/setup
```

2. Wklej skopiowany setup token w polu "Setup Token".

3. Wpisz hasło administratora (minimum 12 znaków). Hasło jest hashowane algorytmem Argon2id — nie jest nigdzie przesyłane ani przechowywane w postaci jawnej.

4. Kliknij "Utwórz konto administratora".

Od tej chwili logujesz się przez:

```
http://localhost:8421/login
```

---

## Krok 5 — Interfejs i pierwsze uruchomienie council

Po zalogowaniu zobaczysz Dashboard z następującymi sekcjami:

- **Pipeline** — zarządzanie etapami (stage'ami) audytu
- **Council** — panel czterech modeli AI
- **Agenci** — lista 48 agentów z ich statusem
- **Ustawienia** — klucze API, logi, konfiguracja

### Uruchomienie council

1. Przejdź do zakładki **Council** w menu bocznym.
2. Wpisz pytanie lub wklej fragment kodu w polu tekstowym.
3. Kliknij **"Uruchom Council"**.

Cztery modele (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) przetworzą zapytanie równolegle. Wyniki pojawią się w panelu po prawej stronie — każdy model osobno, z podsumowaniem konsensusu na dole.

---

## Co dalej?

- Przeczytaj [FAQ_PL.md](FAQ_PL.md), żeby poznać odpowiedzi na najczęstsze pytania.
- Jeśli coś nie działa — zajrzyj do [TROUBLESHOOTING_PL.md](TROUBLESHOOTING_PL.md).
- Nowe w tej wersji — [RELEASE_NOTES_v5.9.0_PL.md](RELEASE_NOTES_v5.9.0_PL.md).
- Checklist wdrożenia — [ONBOARDING_CHECKLIST_PL.md](ONBOARDING_CHECKLIST_PL.md).
