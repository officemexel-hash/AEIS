# SYLION Pipeline v5.9.1

[![Version](https://img.shields.io/badge/version-5.9.1-blue.svg)](https://github.com/sylion/sylion-pipeline/releases/tag/v5.9.1)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE.md)
[![Build](https://img.shields.io/badge/build-passing-brightgreen.svg)](docs/CHANGELOG_v5.9.1.md)
[![Python](https://img.shields.io/badge/python-%3E%3D3.11-blue.svg)](https://python.org)
[![Release Date](https://img.shields.io/badge/released-2026--04--19-orange.svg)](CHANGELOG.md)

SYLION to lokalny pipeline AI do audytu i developmentu. Działa wyłącznie na Twoim komputerze — żadne dane nie opuszczają Twojej maszyny.

**Wersja:** 5.9.1  
**Build:** 2026-04-19  
**Kontakt:** support@sylion.example

---

## Co to jest?

SYLION koordynuje 48 agentów AI w ramach jednego spójnego pipeline'u. Cztery modele (Claude Opus 4.7, Sonnet 4.6, GPT-5.4, Gemini 3.1 Pro) pracują równolegle jako „council" — każda decyzja jest konsultowana przez wszystkie cztery modele jednocześnie.

Typowe zastosowania:

- Audyt kodu (bezpieczeństwo, jakość, wydajność)
- Automatyczne review pull requestów
- Generowanie dokumentacji
- Analiza zależności i długu technicznego

---

## Nowości w v5.9.1

### Anti-Hallucination Layers (Phantom v3)

v5.9.1 wprowadza kompletny stos 5 warstw anty-halucynacyjnych:

| Warstwa | Moduł | Opis |
|---------|-------|------|
| Layer 1 | `loop_guard.py` | Limit iteracji + token budget per agent |
| Layer 2 | `build_verification.py` | Weryfikacja spójności buildu po każdej iteracji |
| Layer 3 | `claim_provenance.py` + `file_verification.py` | **Phantom v3** — detekcja 4 typów PHANTOM_FILE |
| Layer 4 | `semantic_dedup.py` | Deduplikacja semantyczna raportów agentów |
| Layer 5 | `fact_checker.py` | Niezależna weryfikacja LLM twierdzeń o fixach |

**Phantom v3** (Layer 3) wykrywa fikcyjne operacje na plikach (PHANTOM_TYPE_1..4) i zatrzymuje pipeline na poziomie CRITICAL przed wdrożeniem fałszywych poprawek.

### Cost Tracker + Budget Per Model

Nowy moduł `dashboard/cost_tracker.py` zapewnia:

- Śledzenie kosztów LLM per provider, model, użytkownik i sesja
- Trwałe przechowywanie w SQLite (`cost_log` table z kolumną `user_id`)
- Endpoint `/api/finops/summary` — dzienny i miesięczny raport kosztów
- Endpoint `/api/finops/trend` — trend kosztów (ostatnie N miesięcy)
- Integracja z `BudgetGuard` — globalny dzienny limit kosztów (`max_cost_usd_per_day`)
- `budget_per_model` — opcjonalne limity per model (config)

Przykład konfiguracji w `config.py`:
```python
max_cost_usd_per_day: float = 10.0
budget_warning_threshold: float = 0.8  # alert przy 80% budżetu
budget_per_model: dict = {
    "anthropic/claude-opus-4-7": 5.0,
    "openai/gpt-5-4": 3.0,
}
```

### Księga 3.4 Fixed (BookGuardian)

`book_guardian.py` monitoruje integralność pliku specyfikacji produktu (`docs/KSIEGA_3_4_SPEC.md`):

- Weryfikacja SHA-256 przy każdym uruchomieniu pipeline'u
- Gate level: **CRITICAL** — pipeline zatrzymany automatycznie przy niezgodności
- Rebaseline: `python dashboard/book_guardian_rebase.py` (wymaga zatwierdzenia)
- Logi w `audit_log` z aktorem `book_guardian`

### Pozostałe nowości

- `POST /api/auth/logout-all` — unieważnienie wszystkich sesji użytkownika
- `test_v591_regressions.py` — 101 testów regresji (97 passed, 4 skipped, 0 failed)
- Rozszerzony `/api/health` (`db_ok`, `backup_age_hours`, `disk_free_gb`)
- Cykliczny dzienny backup w app lifespan (asyncio background task)
- pidfile + port-check w `start.py` — zapobiega podwójnemu startowi
- 7 nowych ADRs (ADR-0019..ADR-0025)

---

## Wymagania minimalne

| Element     | Minimum          |
|-------------|------------------|
| Python      | >=3.11 (3.12 tested, recommended) |
| RAM         | 8 GB             |
| System      | Linux, macOS, Windows 10/11 |
| Dysk        | 2 GB wolnego miejsca |

---

## Szybka instalacja

### Linux / macOS

```bash
git clone https://github.com/your-org/sylion.git
cd sylion
chmod +x install.sh
./install.sh
```

### Windows

```bat
git clone https://github.com/your-org/sylion.git
cd sylion
install.bat
```

---

## Uruchomienie

```bash
python -m sylion serve
```

Następnie otwórz przeglądarkę i przejdź pod adres:

```
http://localhost:8421
```

---

## Pierwsze logowanie (v6.0.0 — Create First Account)

Od wersji 6.0.0 **setup token nie jest już wymagany**. Po uruchomieniu serwera:

1. Otwórz `http://localhost:8421/` w przeglądarce.
2. Zostaniesz automatycznie przekierowany do ekranu **Pierwsze uruchomienie**.
3. Podaj **nazwę użytkownika** i **hasło** (minimum 8 znaków) — żaden token nie jest potrzebny.
4. Kliknij **Utwórz konto i zaloguj**.

Konto zostanie utworzone z rolą `owner`. Kolejne próby wywołania endpointu `/api/auth/setup`
zwrócą HTTP 403 `{"error": "first_account_exists"}`.

> **Migration note (v5.9.x → v6.0.0):** Jeśli posiadasz plik `SETUP_TOKEN.txt`, możesz go usunąć —
jeżeli baza danych już zawiera konto właściciela, token nie będzie używany.

---

## Dokumentacja

| Dokument | Opis |
|----------|------|
| [QUICKSTART_PL.md](docs/QUICKSTART_PL.md) | Od zera do pierwszego loginu w 5 minut |
| [FAQ_PL.md](docs/FAQ_PL.md) | 20 najczęstszych pytań |
| [TROUBLESHOOTING_PL.md](docs/TROUBLESHOOTING_PL.md) | 15 typowych problemów i ich rozwiązania |
| [RELEASE_NOTES_v5.9.0_PL.md](docs/RELEASE_NOTES_v5.9.0_PL.md) | Co nowego w poprzedniej wersji |
| [PHANTOM_V3_SPEC.md](docs/PHANTOM_V3_SPEC.md) | Specyfikacja Anti-Hallucination Layer 3 |
| [KSIEGA_3_4_SPEC.md](docs/KSIEGA_3_4_SPEC.md) | Specyfikacja produktu (BookGuardian baseline) |
| [ONBOARDING_CHECKLIST_PL.md](docs/ONBOARDING_CHECKLIST_PL.md) | 10-krokowy checklist dla nowego użytkownika |
| [QUICKSTART_DE.md](docs/QUICKSTART_DE.md) | Schnellstart auf Deutsch |
| [FAQ_DE.md](docs/FAQ_DE.md) | Häufige Fragen auf Deutsch |

---

## Struktura katalogów

```
sylion-pipeline/
├── README.md                    ← jesteś tutaj
├── CHANGELOG.md                 ← historia zmian (Keep-a-Changelog 1.1.0)
├── MANIFEST.json                ← metadane wersji i lista plików
├── CHECKSUMS.sha256             ← sumy kontrolne plików źródłowych
├── VERSION                      ← numer bieżącej wersji (5.9.1)
├── install.sh                   ← instalator Linux/macOS
├── install.bat                  ← instalator Windows
├── rollback.sh                  ← WAL-safe rollback do poprzedniej wersji
├── scripts/
│   └── regen-lock.sh           ← regeneracja requirements-lock.txt
├── dashboard/
│   ├── app.py                  ← FastAPI application (główny)
│   ├── db.py                   ← SQLite WAL + migracje
│   ├── start.py                ← entry point + pidfile + port-check
│   ├── cost_tracker.py         ← [v5.9.1] FinOps — śledzenie kosztów LLM
│   ├── seed_agents.py          ← inicjalizacja 48 agentów
│   ├── retention_cleaner.py    ← RODO — czyszczenie starych danych
│   └── bridge.py               ← bridge HTTP→WebSocket
├── docs/
│   ├── adr/                    ← Architecture Decision Records (ADR-0001..ADR-0025)
│   ├── PHANTOM_V3_SPEC.md      ← [v5.9.1] Anti-hallucination layer 3
│   └── KSIEGA_3_4_SPEC.md      ← [v5.9.1] BookGuardian baseline spec
├── fact_checker.py             ← [v5.9.1] Anti-hallucination layer 5
├── budget_guard.py             ← [v5.9.1] Globalny limit kosztów per dzień
├── build_verification.py       ← [v5.9.1] Anti-hallucination layer 2
├── claim_provenance.py         ← [v5.9.1] Anti-hallucination layer 3
├── file_verification.py        ← [v5.9.1] SHA-256 file integrity checks
├── semantic_dedup.py           ← [v5.9.1] Anti-hallucination layer 4
├── book_guardian.py            ← [v5.9.1] Integrity guard dla Księgi 3.4
├── orchestrator.py             ← główny orkiestrator agentów
└── tests/                      ← testy jednostkowe i integracyjne
```

---

## Baza danych

SYLION używa SQLite z trybem WAL. Baza danych jest przechowywana lokalnie:

```
~/sylion/sylion.db
```

Backup przed każdą migracją tworzony jest automatycznie. Ręczny backup:

```bash
cp ~/sylion/sylion.db ~/backup/sylion_$(date +%Y%m%d_%H%M%S).db
```

---

## Bezpieczeństwo

v5.9.1 naprawia 5 CRITICAL, 6 HIGH, 7 MEDIUM findings audytu v5.9.0:

- **CRITICAL** — błąd runtime fact_checker (zły model ID)
- **CRITICAL** — wyścig TOCTOU w `/api/auth/setup`
- **HIGH** — zmiana hasła nie unieważniała wszystkich sesji
- **HIGH** — Pixel 9 seed (PIX-1 — naprawa historycznego buga)
- CVE upgrades: litellm ≥1.83.0, starlette ≥0.49.1, python-multipart ≥0.0.26

Pełna lista: [docs/FIX_MAP_v5.9.1.md](docs/FIX_MAP_v5.9.1.md)

---

## Licencja

Do użytku prywatnego. Wszelkie prawa zastrzeżone. Zobacz [LICENSE.md](LICENSE.md).
