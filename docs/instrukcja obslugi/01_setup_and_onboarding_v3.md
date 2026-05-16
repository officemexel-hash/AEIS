# FAZA 1 — Setup & Onboarding

> **Status**: 🟢 Active draft (przed soft-freeze)
> **Grupa**: A — Przygotowanie Operatora (1 z 11)
> **Typ**: jednorazowa, per operator-maszyna
> **Czas wykonania**: 5-15 min (skip tutorial) / 30-60 min (Standard tutorial) / 2-4h (Full build)
> **D-level**: D1 — trywialne, brak operacji finansowych ani danych krytycznych
> **Zależności**: brak (entry point)
> **Następnik**: Faza 2 (Provider Catalog Configuration)

---

## 1.1. Sens fazy i jej miejsce w cyklu

### 1.1.1. Czemu ta faza istnieje

AEIS to system z surface area znacznie większą niż typowa aplikacja AI:
- **15+ typów integracji** zewnętrznych (LLM API, modele lokalne, cloud providers, payment gateways, CDN, email, SMS, monitoring)
- **41 faz operacyjnych** w cyklu życia projektu
- **8 systemów Guards** działających w tle
- **W1-W19** warstw architektury które operator ostatecznie powinien rozumieć

Operator który "wchodzi i klika" bez przewodnika gubi się w pierwszych 30 minutach — i porzuca system w pierwszym tygodniu. To jest udokumentowane zjawisko w narzędziach klasy enterprise (Salesforce, Palantir Foundry, SAP). **Faza 1 jest tarczą przeciwko temu**.

### 1.1.2. Wynik fazy (definition of done)

Po fazie 1 operator:
- ✓ Ma działający workspace w `~/.sylion/<operator>/`
- ✓ Ma ustaloną tożsamość (display name, system name, email)
- ✓ Ma wybrany język UI (PL/EN)
- ✓ Ma master password ustawiony (lub świadomie pominięty)
- ✓ Wie czym jest AEIS (mental model)
- ✓ Wie gdzie znaleźć pomoc i jak wrócić do tutorial
- ✓ Ma **przynajmniej 1 model** dostępny (lokalny lub API) — **hard gate, P1.20**
- ✓ Wybrał wstępny autonomy preset (Conservative/Balanced/Aggressive)
- ✓ Wie co dalej (faza 2)

### 1.1.3. Co NIE jest w tej fazie (świadome wykluczenia)

Żeby operator nie został przeciążony, **te rzeczy są w późniejszych fazach**:

| Element | Dlaczego nie w fazie 1 | Gdzie |
|---|---|---|
| Klucze API (Anthropic, OpenAI, etc.) | Wymaga decyzji o providerach, modelach, budgetach | Faza 2 |
| Środowiska deploy (Hetzner, AWS) | Wymaga zrozumienia architektury, kosztów | Faza 3 |
| Council templates | Wymaga już ustawionych providers | Faza 12 |
| Konkretny projekt | To jest projekt-level, nie operator-level | Faza 16+ |
| Guards detail config | Wymaga modeli (faza 2) i defaults (faza 4) | Fazy 6-10 |

**Wyjątek**: lokalne modele auto-detection. Operator może mieć Ollama/LM Studio już zainstalowane — system to wykryje **w fazie 1**, żeby zapewnić że hard gate "minimum 1 model" jest możliwy bez wymuszenia natychmiastowego setup-u API keys.

---

## 1.2. Architektura instalacji (P1.18 = Tauri)

### 1.2.1. Single binary, embedded backend

AEIS dystrybuuje się jako **Tauri app**:
- Single installer per OS (Windows `.msi`, macOS `.dmg`, Linux `.AppImage` + `.deb`)
- Wewnątrz: Rust shell (Tauri) + embedded Python backend + Next.js frontend serwowany lokalnie
- Operator nie musi mieć preinstalowanego Pythona, Node, Dockera

```
┌──────────────────────────────────────────────────────┐
│  AEIS Desktop App (single binary ~180MB)             │
│  ┌────────────────────────────────────────────────┐  │
│  │ Tauri Shell (Rust)                            │  │
│  │   ├─ window management                        │  │
│  │   ├─ system tray                              │  │
│  │   ├─ native dialogs (file picker, etc.)       │  │
│  │   └─ auto-update                              │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Embedded backend (Python 3.13, FastAPI)       │  │
│  │   ├─ port: dynamic (default 8127)             │  │
│  │   ├─ database: ~/.sylion/<op>/aeis.db (SQLite)│  │
│  │   └─ workspace: ~/.sylion/<op>/workspace/     │  │
│  └────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────┐  │
│  │ Frontend (Next.js, statically built)          │  │
│  │   serwowany przez backend FastAPI             │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### 1.2.2. Web access jako opcja

Po starcie aplikacji desktop, operator widzi w status bar:
```
✓ AEIS running on http://localhost:8127
```

Jeśli woli pracować w przeglądarce (Chrome/Edge/Firefox) zamiast w app shell, otwiera URL. **Same workspace, ten sam stan, tylko inny renderer**.

Ale uwaga — **session jest powiązana z desktop app**. Jeśli operator zamknie desktop, browser-tab traci backend.

**Power-user mode** (faza 2-3 advanced settings): operator może uruchomić AEIS jako **headless server** (bez Tauri shell) i pracować tylko przez browser. Przydatne dla zespołów (deploy serwer-side z multi-operator) — ale to nie scope fazy 1.

### 1.2.3. Multi-operator (P1.3 = single per maszyna)

**Decyzja**: jeden operator per zainstalowana instancja AEIS. Storage: `~/.sylion/<operator-name>/`.

Konsekwencje:
- Kolejny operator na tej samej maszynie → osobna instalacja albo osobny system user
- Brak "user switching" w UI
- Brak współdzielonego workspace na lokalnej maszynie
- Multi-operator dostępne tylko w **headless server mode** (faza 3) — wtedy team łączy się przez web do shared backend

To **świadomy trade-off**: prostsze UX, mniejsze powierzchnie ataku, mniej confusion. Multi-tenancy zostaje jako server-side feature, nie desktop.

---

## 1.3. Pierwszy boot — chronologia kroków

### 1.3.1. Krok 1.A — Splash & system check (3-5 sekund, automatyczny)

Po instalacji i pierwszym uruchomieniu, operator widzi:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│                    ●  S Y L I O N                            │
│                       Autonomous Engineering                 │
│                       Intelligence System                    │
│                                                              │
│                    Initializing workspace…                   │
│                                                              │
│                    ✓ System check                           │
│                    ✓ Database init                          │
│                    ⠋ Local model scan…                      │
│                                                              │
│                                                              │
│                    v3.0.0  ·  build #2147                    │
└──────────────────────────────────────────────────────────────┘
```

**Co się dzieje w tle** (P1.13 + P1.17 = bardzo aktywny scan):

1. **System check** — sprawdza:
   - Wolne miejsce na dysku (min 2GB rekomendowane)
   - RAM (min 8GB, optymalnie 16+)
   - GPU (CUDA/Metal/ROCm — detekcja)
   - Pierwsze uruchomienie czy nie (czy istnieje `~/.sylion/`)

2. **Database init** — tworzy `~/.sylion/<op>/aeis.db` (SQLite z migrations)

3. **Local model scan** — skanuje agresywnie:
   - `which ollama` → `ollama list` jeśli istnieje
   - `~/.lmstudio/models/` jeśli istnieje
   - `~/.cache/lm-studio/` jeśli istnieje
   - `~/Models/`, `~/Downloads/`, `~/Documents/Models/` dla `*.gguf` files
   - System PATH dla `llama-server`, `vllm`, `text-generation-inference`
   - `which docker` + `docker ps` filtrowane po `ollama|vllm|tgi|llama` w obrazach

4. **GPU benchmark** (jeśli wykryte) — krótki micro-test (1-2 sek) żeby ustalić class:
   - "Fast inference" (RTX 4090, M3 Max, A100)
   - "Balanced" (RTX 4070, M2 Pro)
   - "Heavy/Slow" (CPU only, integrated GPU)

**Czas tego kroku**: 3-15 sekund zależnie od ile lokalnych modeli + GPU.

**Edge case**: jeśli scan trwa >30 sekund, splash pokazuje "Skip scan" link żeby operator mógł kontynuować bez auto-detect.

### 1.3.2. Krok 1.B — Welcome (jednorazowy ekran)

Po splash, operator widzi:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Welcome to SYLION AEIS                                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                                                        │  │
│  │   Twój Autonomous Engineering Intelligence System      │  │
│  │   jest gotowy do konfiguracji.                         │  │
│  │                                                        │  │
│  │   Następne 10-15 minut:                                │  │
│  │     1. Tożsamość operatora                             │  │
│  │     2. Scieżka danych                                  │  │
│  │     3. Tutorial (opcjonalny — możesz pominąć)          │  │
│  │     4. Pierwszy model (lokalny lub API)                │  │
│  │                                                        │  │
│  │   Po zakończeniu trafisz do Phase 2 — gdzie dodasz     │  │
│  │   pełen catalog providerów i kluczy.                   │  │
│  │                                                        │  │
│  │                                                        │  │
│  │              [  Rozpocznij  ]    [ Pomiń tutorial ]   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─ Quick info ──────────────────────────────────────────┐  │
│  │ Wykryto: 3 modele lokalne (Ollama)                    │  │
│  │           1 GPU (NVIDIA RTX 4090, CUDA 12.1)          │  │
│  │           14GB RAM dostępne                            │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Język:  [● Polski]  [○ English]    Already an user? [Sign in]│
└──────────────────────────────────────────────────────────────┘
```

**Decision points na tym ekranie**:

1. **Język UI** (P1.5 = b) — toggle PL/EN, default detected from OS locale
2. **Akcja** — Rozpocznij / Pomiń tutorial
3. **Sign in** (jeśli operator ma backup z innej maszyny) — przekierowanie do recovery flow

**"Sign in" flow** (edge case, faza 1.D w późniejszej iteracji):
- Operator wybiera plik `.aeis-backup` z innej instalacji
- System odszyfrowuje (master password z tamtej instalacji)
- Importuje workspace state
- Pomija większość fazy 1, idzie do fazy 2 z preinstalowanym setup

### 1.3.3. Krok 1.C — Identity setup

Pierwszy realny formularz. Pełen panel:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Krok 1 / 5  ·  Identity Setup                            │
│                                                              │
│  ┌── DISPLAY NAME (jak widzisz siebie w UI) ──────────────┐  │
│  │                                                        │  │
│  │  [ Robert                                       ]      │  │
│  │  ↑ pojawi się w nawigacji, raportach, audit chain     │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── SYSTEM NAME (technical identifier) ──────────────────┐  │
│  │                                                        │  │
│  │  [ robert.k                                     ]      │  │
│  │  ↑ używane w git commits, audit chains, logs.         │  │
│  │    Lowercase, kropki, alphanumeric. Bez spacji.        │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── EMAIL (dla notifications i future SSO) ──────────────┐  │
│  │                                                        │  │
│  │  [ robert@sylion.dev                            ]      │  │
│  │  ☐ używaj jako podstawowy kanał notifications          │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── ROLA (dla optymalizacji UI) ─────────────────────────┐  │
│  │                                                        │  │
│  │  [● Solo — sam pracuję                       ]         │  │
│  │  [○ Team Lead — zarządzam zespołem 2-15 osób ]         │  │
│  │  [○ Klient — testuję możliwości platformy    ]         │  │
│  │                                                        │  │
│  │  ↑ wpływa na default complexity UI w fazach 4-15      │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── TIME ZONE ───────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  Auto-detected:  Europe/Warsaw (UTC+2)                 │  │
│  │                                                        │  │
│  │  [● Confirm]  [○ Custom: ___________________ ]         │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                              [ ← Wstecz ]    [ Dalej → ]    │
└──────────────────────────────────────────────────────────────┘
```

**Decyzje operatora** (5 fields):

1. **Display name** — wolny tekst, max 64 znaki, default empty
2. **System name** — auto-suggested z display name (lowercase + kropki + lowercase + remove special chars), max 32 znaki, walidacja regex `^[a-z0-9.]+$`
3. **Email** — opcjonalny ale silnie sugerowany (dla recovery, notifications)
4. **Rola** (P1.6 implicit z rozszerzeniem) — Solo / Team Lead / Klient → 3 różne UI complexity profiles
5. **Time zone** (P1.7 = c hybrid) — auto-detect + confirm

**Edge cases**:
- System name już istnieje (np. operator robi reinstall) → "Wykryto poprzedni workspace dla `robert.k`. Importować? (link do recovery flow)"
- Email format invalid → live validation, czerwona ramka, błąd "Format email niepoprawny"
- Display name = "" → "Imię jest wymagane"
- System name = "admin", "root", "system", "aeis" → "Ta nazwa jest zarezerwowana"

### 1.3.4. Krok 1.D — Storage location

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Krok 2 / 5  ·  Storage Location                          │
│                                                              │
│  Twój workspace będzie zawierać:                             │
│  • Bazę pomysłów, projektów, audit chains                    │
│  • Klucze API (zaszyfrowane)                                 │
│  • Wygenerowane artefakty (kod, dokumenty)                   │
│  • Logi i metryki                                            │
│                                                              │
│  ┌── ŚCIEŻKA WORKSPACE (P1.2 = b) ────────────────────────┐  │
│  │                                                        │  │
│  │  Default:  ~/.sylion/robert.k/                         │  │
│  │  Estimated:  starts ~5MB → grows to 1-50GB            │  │
│  │                                                        │  │
│  │  [● Use default                                    ]   │  │
│  │  [○ Custom path: _____________________________ ]      │  │
│  │      ↑ click do file picker dialog                    │  │
│  │                                                        │  │
│  │  ⚠ Custom path advice:                                 │  │
│  │    • Wybierz dysk z >50GB wolnego miejsca              │  │
│  │    • Unikaj cloud-synced folderów (Dropbox, OneDrive)  │  │
│  │      — może powodować corruption SQLite                │  │
│  │    • Unikaj network drives (slow performance)          │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── BACKUP STRATEGY ─────────────────────────────────────┐  │
│  │                                                        │  │
│  │  Automatic local backups:                              │  │
│  │  [● Daily  (rekomendowane)]                            │  │
│  │  [○ Weekly                ]                            │  │
│  │  [○ Manual only           ]                            │  │
│  │                                                        │  │
│  │  Retention:  [ 30 days ▼ ]                             │  │
│  │  Backup path: ~/.sylion/robert.k/backups/              │  │
│  │  Size estimate: 10-500MB per backup                    │  │
│  │                                                        │  │
│  │  ☐ Wysyłaj backups do remote (faza 3 setup)            │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                              [ ← Wstecz ]    [ Dalej → ]    │
└──────────────────────────────────────────────────────────────┘
```

**Decyzje operatora**:
1. **Workspace path** — default lub custom (file picker dialog)
2. **Backup frequency** — Daily / Weekly / Manual only
3. **Backup retention** — 7 days / 30 days / 90 days / 365 days / forever
4. **Remote backup** — checkbox, ale config zostawiony do fazy 3

**Edge cases**:
- Custom path nie istnieje → "Czy utworzyć katalog X?"
- Custom path nie ma write permissions → error + "Wybierz inny path"
- Custom path na sieci (UNC w Windows, NFS, SMB mount) → warning ale nie block
- Custom path w cloud-synced folder → warning "Może powodować corruption SQLite, użyj lokalnego dysku"

### 1.3.5. Krok 1.E — Master Password (P1.4 = b: opcjonalny ale sugerowany)

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Krok 3 / 5  ·  Master Password                           │
│                                                              │
│  Master password szyfruje wrażliwe dane w workspace:        │
│  • Klucze API (Anthropic, OpenAI, etc.)                     │
│  • Cloud credentials (Hetzner, AWS, etc.)                    │
│  • Tokeny SSO (przyszłość)                                  │
│  • Backups                                                   │
│                                                              │
│  ┌── WŁĄCZ MASTER PASSWORD ──────────────────────────────┐  │
│  │                                                        │  │
│  │  [● Tak, używaj master password (rekomendowane)]      │  │
│  │  [○ Nie, zostaw bez password (low security mode)]     │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── USTAW PASSWORD ─────────────────────────────────────┐  │
│  │                                                        │  │
│  │  Password:        [ ●●●●●●●●●●●●●●● 👁 ]               │  │
│  │  Powtórz:         [ ●●●●●●●●●●●●●●● 👁 ]               │  │
│  │                                                        │  │
│  │  Strength:  ████████████░░░░░░░  Strong (75%)         │  │
│  │                                                        │  │
│  │  Wymagania:                                            │  │
│  │    ✓ Min 12 znaków                                    │  │
│  │    ✓ Min 1 wielka litera                              │  │
│  │    ✓ Min 1 cyfra                                      │  │
│  │    ✗ Min 1 znak specjalny                             │  │
│  │                                                        │  │
│  │  Hint (optional, niezaszyfrowany):                     │  │
│  │  [ Mój ulubiony cytat z 2017 + numer ulicy        ]   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── RECOVERY ───────────────────────────────────────────┐  │
│  │                                                        │  │
│  │  Po ustawieniu, system wygeneruje recovery seed (24    │  │
│  │  słów BIP-39). Zapisz go w bezpiecznym miejscu —      │  │
│  │  jeśli zapomnisz password, to JEDYNY sposób odzyskać  │  │
│  │  workspace.                                            │  │
│  │                                                        │  │
│  │  ⚠ Anthropic ani SYLION nie mogą zresetować twojego   │  │
│  │    workspace. Ten password jest tylko twój.           │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                              [ ← Wstecz ]    [ Dalej → ]    │
└──────────────────────────────────────────────────────────────┘
```

**Decyzje operatora**:
1. Włącz / nie
2. Password (z dual-input verification)
3. Hint (opcjonalny)
4. Confirmation że rozumie że SYLION nie może go zresetować

**Po klick "Dalej"** (jeśli włączone), pojawia się recovery seed:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Recovery Seed — Zapisz natychmiast                       │
│                                                              │
│  ⚠  Te 24 słowa to JEDYNY sposób odzyskać workspace jeśli   │
│      zapomnisz master password. Anthropic ani SYLION nie    │
│      mogą ich odtworzyć.                                     │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │   1.  abandon       9.  comfort     17. flame        │   │
│  │   2.  ability      10. company      18. flash         │   │
│  │   3.  able         11. concept      19. flat          │   │
│  │   4.  about        12. consume      20. flavor        │   │
│  │   5.  above        13. contain      21. flight        │   │
│  │   6.  absent       14. control      22. floor         │   │
│  │   7.  absorb       15. depend       23. focus         │   │
│  │   8.  abstract     16. depth        24. forget        │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  [ Copy to clipboard ]  [ Print recovery card ]              │
│  [ Save to file (encrypted with second password) ]           │
│                                                              │
│  ☐ Zapisałem te słowa w bezpiecznym miejscu                  │
│                                                              │
│  [ Verify ] — wpisz słowa #3, #11, #19 żeby potwierdzić     │
│                                                              │
│                              [ ← Wstecz ]    [ Continue → ] │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**UX detail**: button "Continue" nieaktywny do momentu poprawnego wpisania 3 random words z seed (verification że operator naprawdę zapisał).

**Edge cases**:
- Operator wybrał "Nie" (bez password) → workspace działa, ale wszystkie sekrety storage'owane plain w zaszyfrowanej tylko na poziomie OS file permissions
- Operator pomija recovery seed (obchodzi UI w jakiś sposób) → impossible, button blocked
- Operator ma password manager (Bitwarden, 1Password) → "Save to password manager" extension support

### 1.3.6. Krok 1.F — Goals discovery (P1.10 = a)

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Krok 4 / 5  ·  Co zamierzasz głównie budować?            │
│                                                              │
│  Wybierz 1-3 typy projektów. AEIS dostosuje sugestie         │
│  domyślnych ustawień (modele, środowiska, autonomy).         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ☐  Apps internal — wewnętrzne narzędzia firmowe     │   │
│  │     CRM, dashboardy, panele zarządzania              │   │
│  │     • 1-100 użytkowników                             │   │
│  │     • Stack: zwykły web stack                        │   │
│  │     • Default autonomy: Balanced                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ☑  Public products — SaaS, e-commerce               │   │
│  │     Aplikacje dla zewnętrznych klientów              │   │
│  │     • Real money flow, real users                    │   │
│  │     • Multi-tenant rozważany                         │   │
│  │     • Default autonomy: Conservative                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ☐  Research / experimentation                       │   │
│  │     Eksperymenty AI, prototypy, R&D                  │   │
│  │     • Krótkie iteracje                               │   │
│  │     • Niski koszt per projekt                        │   │
│  │     • Default autonomy: Aggressive                   │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ☑  Cybersecurity tooling                            │   │
│  │     Systemy bezpieczne, sovereign infrastructure      │   │
│  │     • Hard policy enforcement                        │   │
│  │     • Air-gap możliwy                                │   │
│  │     • Default autonomy: Conservative + Hard Gates    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  ☐  Mixed / explore                                  │   │
│  │     Jeszcze nie wiem, chcę zobaczyć możliwości       │   │
│  │     • Standard defaults                              │   │
│  │     • Tutorial Standard rekomendowany                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Wybrałeś: Public products + Cybersecurity tooling           │
│                                                              │
│  AEIS sugeruje dla ciebie:                                   │
│   • Default autonomy: Conservative                           │
│   • Default budget per project: $50                          │
│   • Quality gates: Strict (zalecany W14 full)                │
│   • Hard gates: production deploy, GDPR Art.9                │
│                                                              │
│   (możesz zmienić wszystko w fazach 4-15)                    │
│                                                              │
│                              [ ← Wstecz ]    [ Dalej → ]    │
└──────────────────────────────────────────────────────────────┘
```

**Decyzje operatora**:
1. Wybór 1-3 typów projektów (multi-select)
2. Akceptacja sugerowanych defaults (lub continue z opcją zmienić w fazach 4-15)

**Co system robi w tle**:
Gdy operator wybierze, system pre-konfiguruje **draft templates** dla:
- Autonomy preset (faza 5)
- Budget defaults (faza 4)
- Quality gates strictness (faza 9)
- Council templates (faza 12)
- Test strategy (faza 13)

Operator zobaczy te drafts w kolejnych fazach i może je zaakceptować lub zmodyfikować.

### 1.3.7. Krok 1.G — Tutorial choice (P1.16 = d Layered)

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Krok 5 / 5  ·  Tutorial mode                             │
│                                                              │
│  AEIS może przeprowadzić Cię przez przykładowy projekt.      │
│  Wybierz głębokość (P1.16 = d Layered):                      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  [○] Quick (15-20 min)                               │   │
│  │      Sandboxed build na lokalnych modelach           │   │
│  │      Mock dane gdzie nie szkodzi                     │   │
│  │      Rzeczywiste artefakty (prosta apka)             │   │
│  │      Cost: $0 (lokalne modele)                       │   │
│  │      Idealne dla: zorientowania się w UX             │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  [●] Standard (45-60 min)                            │   │
│  │      Real LLM calls dla key faz (Council, Build)     │   │
│  │      Real artifacts                                  │   │
│  │      Może użyć API key (jeśli dostępny) albo lokalne │   │
│  │      Cost: $0-$3 zależnie od wyboru modeli           │   │
│  │      Idealne dla: zrozumienia full workflow           │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  [○] Full build (2-4 hours)                          │   │
│  │      Pełen real-world build                          │   │
│  │      Wymaga skonfigurowanych API keys                │   │
│  │      Real artifact ready to use after tutorial       │   │
│  │      Cost: $5-$30 zależnie od projektu               │   │
│  │      Idealne dla: prawdziwego pierwszego projektu    │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │  [○] Skip tutorial                                   │   │
│  │      Pomiń, eksploruj sam                            │   │
│  │      Możesz wrócić później przez `/tutorial` command │   │
│  │      lub Settings → Help → "Re-run onboarding"       │   │
│  │                                                       │   │
│  └───────────────────────────────────────────────────────┘   │
│                                                              │
│  ─────────────────────────────────────────────────────────   │
│                                                              │
│  ┌── PROJEKT TUTORIAL (jeśli wybrano Quick/Standard/Full) ┐  │
│  │                                                        │  │
│  │  Wybierz przykładowy projekt:                          │  │
│  │                                                        │  │
│  │  [○] Personal Knowledge Base                           │  │
│  │      Notatki + tagi + search, 100% lokalne, brak API  │  │
│  │      Quick: 15 min · Standard: 30 min · Full: 1.5h    │  │
│  │                                                        │  │
│  │  [●] Lokalny CRM dla freelancera (P1.19 = c MEDIUM)   │  │
│  │      Klienci + projekty + faktury, local auth, SQLite │  │
│  │      Quick: 20 min · Standard: 45 min · Full: 2h      │  │
│  │                                                        │  │
│  │  [○] Sylion Tailor Lite                                │  │
│  │      Web shop + mobile, multi-language, lokalny deploy │  │
│  │      Quick: niedostępne · Standard: 60 min · Full: 3h │  │
│  │                                                        │  │
│  │  [○] Custom (operator opisuje swój pomysł)             │  │
│  │      AEIS prowadzi przez fazy z twoim pomysłem        │  │
│  │      Niedostępne dla Quick (wymaga real workflow)     │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│                              [ ← Wstecz ]    [ Rozpocznij ] │
└──────────────────────────────────────────────────────────────┘
```

**Decyzje operatora** (2 dimensions):

1. **Tutorial depth**: Quick / Standard / Full / Skip
2. **Tutorial project** (jeśli nie skip): PKB / Lokalny CRM / Sylion Tailor Lite / Custom

**Disabled combinations** (UI grays out):
- Quick + Sylion Tailor Lite (zbyt complex dla Quick)
- Quick + Custom (Custom wymaga real workflow, nie sandbox)
- Full + brak API keys (Full wymaga real models w D3+)

**Co się dzieje po klick "Rozpocznij"**:
- System ustawia tutorial mode flag
- Tworzy throwaway project w `~/.sylion/<op>/tutorial/`
- Inicjuje pierwszy ekran tutorialu (faza-zależna od wyboru)
- Każdy krok ma overlay "Tutorial mode — [X/Y]" z przyciskiem "Exit tutorial"

**Tutorial logic** (pseudo):

```python
if depth == "Quick":
    use_models = "local_only"
    use_real_llm = ["context_enrichment", "council_quick"]  # only fast
    skip_phases = ["dry_run", "external_review", "production_deploy"]
    artifact_quality = "minimal"

elif depth == "Standard":
    use_models = "any_available"
    use_real_llm = ["context", "council_full", "masterplan", "build", "tests"]
    skip_phases = ["dry_run", "external_review"]
    artifact_quality = "production_grade"

elif depth == "Full":
    use_models = "any_available"
    use_real_llm = "all_phases"
    skip_phases = []
    artifact_quality = "production_grade_with_deploy"
```

### 1.3.8. Krok 1.H — Hard gate sprawdzenie (P1.20 = a Block)

Zanim operator opuści fazę 1, system sprawdza:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Pre-Phase 2 Check                                        │
│                                                              │
│  Sprawdzenie minimum requirements:                            │
│                                                              │
│  ✓  Operator identity: Robert (robert.k)                     │
│  ✓  Workspace: ~/.sylion/robert.k/                           │
│  ✓  Master password: enabled                                  │
│  ✓  Recovery seed: verified                                  │
│  ✓  Goals selected: Public products, Cybersecurity           │
│  ✓  Tutorial mode: Standard, Lokalny CRM                     │
│                                                              │
│  ✓  Local models detected: 3                                 │
│      • llama3.1:8b           (Ollama, 4.5 GB)                │
│      • qwen2.5:7b-instruct   (Ollama, 4.7 GB)                │
│      • bielik-11b-v2.6       (Ollama, 6.2 GB)                │
│                                                              │
│  ✓  GPU: NVIDIA RTX 4090, CUDA 12.1, 24 GB VRAM              │
│                                                              │
│  ✓  Hard gate passed:                                        │
│      Minimum 1 model dostępny → 3 lokalnych modeli           │
│      System może rozpocząć tutorial                           │
│                                                              │
│                                                              │
│              [ Continue to Phase 2 — Provider Catalog ]      │
│                                                              │
│  Lub:                                                        │
│              [ Run tutorial first ]                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Edge case — operator nie ma żadnego modelu**:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Hard Gate Failed — Required Setup                        │
│                                                              │
│  ⚠  AEIS wymaga przynajmniej 1 modelu (lokalnego lub API)   │
│      żeby rozpocząć projekt.                                 │
│                                                              │
│  Wykryto:                                                    │
│   ✗ 0 modeli lokalnych                                       │
│   ✗ 0 kluczy API                                             │
│                                                              │
│  ┌── OPCJE ───────────────────────────────────────────────┐ │
│  │                                                        │ │
│  │  Option A: Zainstaluj lokalny model (rekomendowane)    │ │
│  │            • Ollama: https://ollama.ai                  │ │
│  │              `ollama pull llama3.1:8b` (~4.5 GB)        │ │
│  │            • LM Studio: https://lmstudio.ai             │ │
│  │            Po instalacji kliknij "Re-scan"              │ │
│  │            [ Re-scan local models ]                     │ │
│  │                                                        │ │
│  │  Option B: Dodaj klucz API teraz                        │ │
│  │            Możesz pominąć fazę 2 onboardingu i dodać    │ │
│  │            jeden klucz teraz.                           │ │
│  │            [ Quick add API key → ]                      │ │
│  │                                                        │ │
│  │  Option C: Demo mode (tylko nauka, bez prawdziwych     │ │
│  │            artefaktów)                                  │ │
│  │            Nie polecane jako pierwsze doświadczenie.   │ │
│  │            [ Continue in demo mode ]                    │ │
│  │                                                        │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  Zgodnie z P1.20=a, faza 1 jest blokowana do momentu        │
│  spełnienia hard gate. Wybierz jedną z opcji powyżej.       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Operator MUSI wybrać A, B, lub C** żeby kontynuować. C ostatecznie pozwala go obejść, ale jawnie i z jasnym ostrzeżeniem.

---

## 1.4. Tutorial flow — szczegółowo

### 1.4.1. Lokalny CRM dla freelancera (przykład Standard, 45 min)

To jest **trzeci projekt** którego brakowało (P1.19=c). Definiuję go tu:

**Profil projektu**:
- Apka web dla pojedynczego freelancera (Robert sam jest user)
- Login + password (local SQLite, nie OAuth)
- Modele: Customer, Project, Invoice
- 3 strony: dashboard, klienci, projekty, faktury, settings
- Brak deploy (lokalnie tylko, `npm run dev`)
- Brak external API (no Stripe, no email service)
- Brak PII (testowe dane Robert wpisuje sam)
- D-level: D2 (auth + data ale local + low stakes)

**Czemu jest dobrym tutorial projektem**:
- Pokazuje **full pipeline** od idea→running app
- **Auth** (faza 22 Council security review trigger)
- **Persistence** (faza 27 ontology design)
- **Multi-page UI** (faza 28 frontend build)
- **Testy** (faza 37 W14 W14 quality gates)
- **Bez external complexity** (no API keys, no cloud, no money flow)
- **Krótkie wystarczająco** (45 min Standard)

**Tutorial walkthrough** (Standard, 45 min):

```
PHASE 16 — Project Inception (2 min)
  Tutorial overlay: "Wciśnij 'New Project'"
  Operator klika
  Tutorial: "Wybierz typ: Apps internal"
  Tutorial: "Nazwa: Mój CRM"
  Continue

PHASE 18 — Idea Capture (3 min)
  Tutorial overlay: "Wpisz pomysł — możemy podpowiedzieć"
  [Suggestion button: "Use suggested description"]
  Operator klika suggestion → pole wypełnia się gotowym opisem CRM
  Operator może edytować
  Continue

PHASE 19 — Context Enrichment (2 min, mostly automatic)
  Tutorial: "AEIS klasyfikuje, znajduje similar projects"
  System pokazuje: D-level: D2, similar: 0 (no history yet)

PHASE 20 — Model Selection round 1 (5 min, real)
  Tutorial: "AEIS sugeruje modele do dyskusji o pomyśle"
  System pokazuje: 3 lokalne modele detected
  Sugeruje:
    Planner → bielik-11b
    Critic → llama3.1
    Security → qwen2.5
  Operator akceptuje lub zmienia
  Continue (nawet w Standard używa lokalnych żeby było darmowe)

PHASE 21 — Skill Synthesis (2 min, automatic)
  Tutorial: "Skills tworzą się dla tego projektu..."
  System pokazuje listę: auth_local, sqlite_storage,
                          multi_page_ui, basic_testing

PHASE 22 — Council Per-Project Configuration (3 min)
  Tutorial: "Skonfiguruj radę dla tego projektu (lub akceptuj defaults)"
  Operator widzi 3 role z lokalnymi modelami
  Akceptuje defaults
  Continue

PHASE 23 — Council Deliberation (8 min, real)
  Tutorial: "Patrz jak modele dyskutują"
  Live preview Księgi po prawej
  Round 1: parallel verdicts
  Round 2: discussion
  Operator widzi A/B/C/D choice cards
  Tutorial: "Wybierz opcję — zalecamy A"

PHASE 24-25 — Operator Decisioning + Book Finalization (3 min)
  Operator klika A
  Księga się finalizuje
  Continue → "Strukturyzacja na moduły"

PHASE 26-30 — Planning (8 min)
  Skrócone — masterplan generated, test plan generated
  Operator widzi i akceptuje

PHASE 31 — Pre-Flight Cost Preview (1 min)
  System: "$0 (lokalne modele), 12 min ETA"
  Akceptuj

PHASE 32 — Dry-Run Simulation (skipped w Standard)

PHASE 33-35 — Build orchestration (10 min, real)
  Workery generują kod
  Tutorial pokazuje: "Patrz live activity"
  Operator widzi pliki: backend, frontend, tests

PHASE 37 — Quality Gates W14 (5 min, real)
  Tests run
  Coverage report
  Verdict: READY (lub findings + auto-repair demo)

PHASE 39 — Deployment Configuration (skipped — local only w tutorial)

PHASE 40 — Production Release (skipped — local only)
  Tutorial: "Run locally — uruchom apkę"
  System pokazuje: `cd ~/.sylion/robert.k/tutorial/mojcrm && npm run dev`

PHASE 41 — Closure & Memory (3 min)
  Tutorial: "Zarchiwizuj projekt, lessons learned"
  Operator klika "Archive"
  System pokazuje memory entries z tego projektu

POST-TUTORIAL
  "Tutorial zakończony! Co dalej?"
  Options:
    • Continue with this project (move from tutorial → real workspace)
    • Start fresh real project (Phase 16)
    • Configure providers (Phase 2)
    • Explore more tutorials
```

### 1.4.2. Tutorial UX — overlay pattern

Każdy ekran tutorialu ma **persistent overlay**:

```
┌─────────────────────────────────────────┬────────────────────┐
│  Aktualny ekran AEIS (np. Idea Capture) │                    │
│                                          │  TUTORIAL (Step 8/15) │
│  [normal UI of phase]                   │                    │
│                                          │  ▸ Idea Capture    │
│  ...                                    │                    │
│                                          │  Wpisz krótki opis │
│                                          │  pomysłu w polu    │
│                                          │  poniżej.          │
│                                          │                    │
│                                          │  💡 Sugestia:      │
│                                          │  [Use suggested]   │
│                                          │                    │
│                                          │  Po wpisaniu kliknij│
│                                          │  "Continue".       │
│                                          │                    │
│                                          │  ────────────────  │
│                                          │  [Pause tutorial]  │
│                                          │  [Exit tutorial]   │
└─────────────────────────────────────────┴────────────────────┘
```

**Key UX rules** dla tutorial overlay:
- **Persistent** — zawsze widoczny w trakcie tutorialu
- **Współdzielone miejsce z book panel** — przejmuje right side, book chowa się
- **Resume** — pause zachowuje stan, można wrócić
- **Exit** — confirms "Tracisz progress tutorialu, ale workspace zostaje. Continue?"

### 1.4.3. Personal Knowledge Base (Quick, 15-25 min)

Najlżejszy tutorial. Dla operatorów którzy chcą zobaczyć podstawowe UX bez
długiego buildu. **100% lokalne, bez API keys, bez deploy.**

**Profil projektu**: notatki tekstowe z tagami i full-text search,
markdown editor, SQLite, single-user, D-level: D1.

**Tutorial walkthrough Quick (15-25 min)**:

```
PHASE 16 — Project Inception (1 min)
  Tutorial: "Nowy projekt → Apps internal → Nazwa: Moje Notatki"

PHASE 17 — Project Configuration Override (1 min, kompresowany)
  Use global defaults (autonomy: Aggressive w Quick, budget: $0)

PHASE 18 — Idea Capture (1 min, pre-filled)
  "Aplikacja do notatek z tagami i wyszukiwaniem.
   Markdown editor. Wszystko lokalnie, bez logowania."
  Tagi: notes, local, simple, markdown

PHASE 19 — Context Enrichment (auto, 30 sek)
  D-level: D1, similar: 0

PHASE 20 — Model Selection round 1 (1 min)
  W Quick: 1 model gra wszystkie role (qwen2.5:7b)
  Cost optimization

PHASE 21 — Skill Synthesis (auto, 30 sek)
  4 skills: markdown_editor, sqlite_storage, fulltext_search, simple_ui

PHASE 22 — Council Per-Project Configuration (auto-skipped w Quick)
  1 rola Planner generic

PHASE 23 — Council Deliberation (3 min)
  Round 1 only (Quick)
  Live Księga (~5 sekcji)
  1-3 warianty A/B/C zamiast 4-6
  Tutorial: "Wybierz A"

PHASE 24-25 — Operator Decisioning + Book (1 min)
  Księga finalizuje (8 sekcji)

PHASE 26-30 — Planning (kompresowany, 2 min)
  Single role planner, 5-step plan
  Test plan: basic unit tests
  Skip dry-run

PHASE 31 — Pre-Flight Cost (auto, 10 sek)
  $0, 6-10 min ETA, auto-accept

PHASE 33-35 — Build (5-8 min, real local)
  qwen2.5:7b generuje 5-8 plików:
  - backend/app.py (FastAPI + SQLite)
  - backend/notes.py (CRUD)
  - backend/search.py (FTS5)
  - frontend/app.tsx (Next.js)
  - frontend/editor.tsx
  - frontend/notes_list.tsx
  - tests/basic.py

PHASE 37 — Quality Gates (1-2 min)
  ~50-70% coverage (basic tests)
  Verdict: READY z findings "tests minimal"

PHASE 39-40 — Deployment (skipped w Quick)
  Run lokalnie: `npm run dev`
  Browser: localhost:3000

PHASE 41 — Closure (1 min)
  Archive lub Promote to real project

POST-TUTORIAL
  "Quick zakończony w 18 min"
  Options: Try Standard / Use PKB / Configure providers
```

**Kluczowe różnice Quick vs Standard**:

| Aspekt | Quick (PKB) | Standard (CRM) |
|---|---|---|
| Czas | 15-25 min | 45-60 min |
| Council roles | 1 | 3-9 |
| Council rounds | 1 | 2-4 |
| Choices | 1-3 wariantów | 4-6 wariantów |
| Build files | 5-8 | 15-25 |
| Test coverage | 50-70% | 80-95% |
| Auto-decisions | Większość | Mieszane |
| Real-world use | Minimal | Wysoka |

### 1.4.4. Sylion Tailor Lite (Standard 60 min lub Full 3h)

**Najambitniejszy tutorial.** Pełen enterprise workflow: multi-environment,
real deploy, multi-language, multiple modeli. Niedostępny w Quick.

**Profil projektu**:
- Web shop dla atelier krawieckiego
- 3 storefronts: PL/EN/DE
- Konfigurator garniturów (basic, bez 3D scan w Lite)
- Stripe sandbox + Przelewy24 sandbox
- Atelier dashboard
- Mobile-responsive
- Deploy: lokalny (Standard) lub Hetzner cleanup-after (Full)
- D-level: D4 (production + payment + multi-language)

**Tutorial walkthrough Standard (45-60 min)**:

```
PHASE 16 — Project Inception (2 min)
  "Public products → Sylion Tailor Lite"

PHASE 17 — Project Configuration Override (3 min)
  D4 wymusza: autonomy Conservative
  Hard gates: production deploy, payment
  Customize budget: $5 (Standard) lub $30 (Full)

PHASE 18 — Idea Capture (3 min, pre-filled)
  "Web shop dla atelier.
   3 języki: PL/EN/DE.
   Konfigurator garniturów (kolor, materiał, krój).
   Stripe + Przelewy24 sandbox.
   Atelier dashboard z production tracking.
   Mobile-friendly. Tier: ready-to-wear i made-to-measure."

PHASE 19 — Context Enrichment (1 min)
  D-level: D4 (auto)
  Similar: 0

PHASE 20 — Model Selection round 1 (5 min)
  AEIS sugeruje 8-rolową radę dla D4:
    Planner       → claude-sonnet (Standard) / claude-opus (Full)
    Critic        → gpt-5 lub bielik-11b
    Security      → claude-opus (zawsze)
    Compliance    → bielik-11b lub PLLuM-70b
    Finance       → claude-sonnet
    UX Designer   → claude-sonnet
    QA Lead       → gpt-5
    Council Chair → claude-opus
  Standard: lokalne dominują, Full: więcej API

PHASE 21 — Skill Synthesis (2 min)
  12+ skills: next_js_app, multi_language_i18n, stripe_integration,
              przelewy24_integration, sqlite_with_migrations,
              product_catalog, cart_management, order_workflow,
              atelier_dashboard, responsive_mobile, accessibility_wcag,
              payment_security

PHASE 22 — Council Per-Project Configuration (5 min)
  8-role panel
  Per rola: model + thinking depth (Standard: medium / Full: high)
  Operator może dodać Payment Specialist (sugestia: tak)
  3 rundy default dla D4

PHASE 23 — Council Deliberation (10 min, real)
  Round 1: parallel verdicts
    Security: "biometric not applicable, payment data critical"
    Compliance: "GDPR consent + ToS Art. 38 dla custom orders"
    Critic: "Refund flow Stripe vs P24 inconsistent"
    UX: "konfigurator UX może być za complex dla mobile"
  
  Operator widzi A/B/C/D:
    "Approach do różnic Stripe vs P24 refund:
    A) Unified UI (one flow, system maps to provider)
    B) Per-provider UI (różne ekrany)
    C) Single provider only (skip P24 w MVP)
    D) Custom"
  Tutorial: "Wybierz A"
  
  Round 2: discussion na podstawie wyboru
  Round 3: consolidation + Critic signature

PHASE 24-25 — Operator Decisioning + Book (3 min)
  Księga finalizuje (15+ sekcji)

PHASE 26 — Model Selection round 2 (3 min)
  Modele dla masterplanu:
    Planner: claude-opus
    Architecture Reviewer: gpt-5

PHASE 27 — Skill Adaptation round 2 (1 min, auto)
  stripe_integration → stripe_with_p24_unified
  + ux_consistency_checker

PHASE 28 — Masterplan Synthesis (8 min, real)
  12-step masterplan:
    1. SETUP Next.js + TypeScript
    2. ONTOLOGY (W15) — Customer, Order, Product, Variant, Cart
    3. PRODUCT CATALOG — 5 sample products w 3 językach
    4. CONFIGURATOR — kolor + materiał + krój
    5. CART & CHECKOUT — multi-currency
    6. PAYMENTS — Stripe + Przelewy24 sandbox
    7. ORDER WORKFLOW — placed → confirmed → in_production → shipped
    8. ATELIER DASHBOARD — orders queue, production tracking
    9. MULTI-LANG — next-i18next (PL/EN/DE)
    10. MOBILE-RESPONSIVE — Tailwind
    11. TESTS — unit + e2e (Playwright)
    12. DEPLOY — lokalny (Standard) lub Hetzner (Full)

  ETA Standard: 30-40 min, $1-2
  ETA Full: 2-3h, $10-25

PHASE 29 — Test Plan Synthesis (3 min)
  L1 Unit: 25-40 testy, target 80%+
  L2 Integration: 8-12 (Stripe webhook, cart→checkout)
  L3 E2E: 5-8 Playwright (multi-lang, mobile, payment happy path)
  Human-like: 15-20 scenariuszy
  Gold standards: sample product/order w 3 językach

PHASE 30 — Pre-Flight Cost (1 min)
  Standard: $1.20-2.40, 30-40 min
  Full: $12-25, 2-3h
  Operator akceptuje

PHASE 31 — Dry-Run Simulation (5 min, opcjonalne)
  Standard: skip
  Full: real dry-run na cheap models, wykrywa problemy

PHASE 32 — Model Selection round 3 (3 min)
  Per moduł:
    Backend (FastAPI/Next.js API) → claude-sonnet + qwen-coder
    Frontend (React/TypeScript) → claude-sonnet
    Stripe integration → claude-opus (security critical)
    Przelewy24 → claude-opus + RAG P24 docs
    Tests → gpt-5
    Atelier dashboard → claude-sonnet
    i18n PL/EN/DE → bielik-11b + claude-sonnet

PHASE 33 — Environment Assignment (2 min)
  Standard: wszystko local
  Full: backend + frontend lokalnie, deploy Hetzner CX31
  Data residency: EU (Hetzner Warsaw)

PHASE 34 — Skill Adaptation round 3 (1 min, auto)
  + stripe_webhook_handler, p24_callback_validator,
    multi_currency_calculator

PHASE 35 — Build Orchestration (15-25 min, real)
  5 workers paralel:
    - frontend_designer (claude-sonnet)
    - backend_api_builder (claude-sonnet + qwen-coder)
    - stripe_integrator (claude-opus)
    - i18n_translator (bielik-11b)
    - test_writer (gpt-5)
  Live activity stream
  Mid-build interventions (faza 36):
    - "Stripe webhook potrzebuje endpointu — confirm path"
    - "P24 wymaga merchant ID — wpisz testowy"
    - "Atelier dashboard: 1 page czy SPA?" → A/B/C

PHASE 37 — Quality Gates W14 (8 min, real)
  L1 Unit: 38/40 pass
    Auto-repair R1-R3: fix 2 currency edge cases
    Re-run: 40/40
  L2 Integration: 11/12 pass
    Failed: Stripe webhook signature (test setup issue)
    Operator decision: skip (code OK)
  L3 E2E: 7/8 pass
    Failed: Mobile viewport rendering
    Auto-repair: CSS adjustment
    Re-run: 8/8
  Coverage: 84%
  Verdict: RC

PHASE 38 — External Review (skipped Standard / 10 min Full mock)
  Full: 2 medium findings, 0 critical → continue

PHASE 39 — Deployment Configuration (3 min)
  Standard: localhost:3000 + 8000, simple start
  Full: Hetzner CX31 warsaw-1, blue-green, cleanup po 24h ($0.42 + $0.20/h)

PHASE 40 — Production Release (5 min Standard / 15 min Full)
  Standard:
    `docker-compose up`
    Browser opens: localhost:3000
  Full:
    Provisioning Hetzner VPS
    Blue-green deploy
    Healthcheck (3 regions)
    DNS update do test subdomain
    SSL Let's Encrypt
    URL: https://tailor-lite-tutorial.sylion.dev
    Operator testuje na różnych urządzeniach
    Auto-cleanup po 24h: VPS decommission, DNS removal, cost report

PHASE 41 — Closure & Memory (3 min)
  System ekstraktuje:
    - Co działało dobrze
    - Co było trudne
    - Cost actual vs estimate
    - Time actual vs estimate
    - Quality metrics
  Memory entries dla future projektów
  Options: Continue using / Archive / Promote to template

POST-TUTORIAL
  Standard: 52 min, $1.84, 30 plików, 84% coverage
  Full: 2h 47min, $18.40, 45 plików, 91% coverage, deployed live
```

**Kluczowe różnice Standard vs Full Tailor**:

| Aspekt | Standard (45-60 min) | Full (2-3h) |
|---|---|---|
| Council depth | Medium thinking | High/Maximum |
| Models | Lokalne dominują | API providers więcej |
| External review | Skip | Real (mock) |
| Dry-run | Skip | Real |
| Deploy | Lokalny Docker | Hetzner real cloud |
| Tests | L1+L2+L3 | L1+L2+L3+L4 |
| Cost | $1-3 | $12-25 |
| Cleanup | No | Yes (auto 24h) |
| Real production-like | Demo | Near-production |

### 1.4.5. Wybór tutorialu — decyzja kosztowo-czasowa

| Aspekt | Quick PKB | Standard CRM | Standard Tailor | Full Tailor |
|---|---|---|---|---|
| Czas | 15-25 min | 45-60 min | 50-70 min | 2-3h |
| Cost | $0 | $0-1 | $1-3 | $12-25 |
| API keys req? | Nie | Opcjonalne | Sugerowane | Wymagane |
| GPU req? | Sugerowane | Sugerowane | Sugerowane | Wymagane |
| Real deploy? | Nie | Nie | Lokalny | Hetzner real |
| Multi-language? | Nie | Nie | Tak (3) | Tak (3) |
| Payment integration? | Nie | Nie | Sandbox | Sandbox |
| Council roles | 1 | 5-6 | 8 | 10+ |
| Council rounds | 1 | 2-3 | 3 | 4 |
| Skills generated | 4 | 8-12 | 12-15 | 15-20 |
| Build files | 5-8 | 12-18 | 25-35 | 35-50 |
| Test coverage | ~50% | ~75% | ~84% | ~91% |
| External review? | Nie | Nie | Nie | Tak (mock) |
| Cleanup needed? | Nie | Nie | Nie | Tak (24h) |
| Real-world output? | Minimal | Średnio | Wysoka | Bardzo wysoka |
| Najlepsze dla | Smoke test | First real flow | Enterprise patterns | Pełen workflow |

**Default recommendation**:
- Pierwszy raz operator → **Standard CRM** (balanced)
- Power-user, krótki czas → **Quick PKB**
- Prawdziwa pierwsza praca → **Standard Tailor**
- Maksymalna nauka, gotowość do real deploy → **Full Tailor**

---

## 1.5. Settings panels w fazie 1

W tej fazie operator dotyka **6 settings panels**:

### Panel 1.5.1 — Identity Panel

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Display name | text | empty | 1-64 chars | Yes (Settings → Profile) |
| System name | text | auto from display | regex `^[a-z0-9.]+$`, 1-32 chars | Limited (audit chains use this) |
| Email | email | empty | RFC 5322 | Yes |
| Role | select | Solo | Solo / TeamLead / Klient | Yes (changes UI complexity) |
| Time zone | select | auto-detect | IANA TZ list | Yes |

### Panel 1.5.2 — Storage Panel

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Workspace path | path | `~/.sylion/<op>/` | writable, non-cloud-synced | Limited (migration required) |
| Backup frequency | select | Daily | Daily/Weekly/Manual | Yes |
| Backup retention | select | 30 days | 7/30/90/365/forever | Yes |
| Remote backup | bool | off | — | Yes (faza 3) |

### Panel 1.5.3 — Security Panel

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Master password enabled | bool | suggested ON | — | Yes (but downgrade requires re-enter password) |
| Master password | password | — | min 12 chars + complexity | Yes |
| Recovery seed | generated | 24 BIP-39 words | — | Yes (regenerate via Settings → Security) |
| Hint | text | empty | optional | Yes |

### Panel 1.5.4 — Profile Panel

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Project goals | multi-select | empty | 1-3 categories | Yes (regenerates suggested defaults) |
| Initial autonomy preset | select | Balanced | Conservative/Balanced/Aggressive | Yes (faza 5 detail config) |

### Panel 1.5.5 — Tutorial Panel

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Tutorial depth | select | Standard | Quick/Standard/Full/Skip | Yes (re-run via `/tutorial`) |
| Tutorial project | select | Lokalny CRM | PKB/CRM/Tailor/Custom | Re-run with new |
| Show overlay tips | bool | ON | — | Yes (Settings → Help) |

### Panel 1.5.6 — Notifications Panel (P1.14 = c partial)

| Field | Type | Default | Validation | Edit later |
|---|---|---|---|---|
| Default channel | select | In-app | In-app/Email/Slack/SMS/None | Yes (faza 4 fine-tuning) |
| Email for notifications | email | from identity | RFC 5322 | Yes |
| Severity threshold | select | Info+ | Info/Warning/Critical/Off | Yes |

**Faza 1 ustawia tylko default channel.** Pełna konfiguracja per typu zdarzenia (Council finalize, HG required, deploy success, error, ...) jest w fazie 4.

---

## 1.6. Decision points — pełna lista

W fazie 1 operator podejmuje **16 decyzji** (rozszerzone z poprzednich 9).
Każda ma default, reversibility, wpływ na późniejsze fazy.

### 1.6.1. Decyzje krytyczne (9)

| # | Decyzja | Default | Reversible? | Wpływ |
|---|---|---|---|---|
| 1 | Język UI | OS detected | Yes (Settings) | UI everywhere |
| 2 | Display name + system name | empty | Limited | Audit chains, git commits |
| 3 | Email | empty | Yes | Notifications, recovery, future SSO |
| 4 | Workspace path | `~/.sylion/<op>/` | Limited (migration) | Storage location |
| 5 | Master password | suggested ON | Yes (re-enter required) | Encryption of secrets |
| 6 | Backup strategy | Daily, 30d retention | Yes | Recovery options |
| 7 | Project goals (1-3) | empty | Yes | Suggested defaults w fazach 4-15 |
| 8 | Tutorial depth + project | Standard, CRM | Yes (re-run) | Onboarding experience |
| 9 | Default notification channel | In-app | Yes (faza 4) | Where alerts arrive |

### 1.6.2. Decyzje rozszerzone (7)

| # | Decyzja | Default | Reversible? | Wpływ |
|---|---|---|---|---|
| 10 | Operator role/typ | Solo | Yes | UI complexity profile |
| 11 | Time zone | Auto-detect | Yes | Timestamps, scheduling |
| 12 | Theme (dark/light/auto) | Auto (z OS) | Yes | UI aesthetic |
| 13 | Accessibility settings | Standard | Yes | Font size, contrast, screen reader |
| 14 | Telemetry opt-in | OFF (default GDPR) | Yes | Anonymous usage stats do SYLION |
| 15 | Update policy | Notify only | Yes | Auto-update / Notify / Manual |
| 16 | Initial autonomy preset | Balanced | Yes (faza 5) | Default L0-L5 dla wszystkich projektów |

### 1.6.3. Sub-options details per decyzja

#### Decyzja #5 — Master Password (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Min length | 12 | 8-64 (system enforces 12+) |
| Require uppercase | Yes | Yes/No |
| Require lowercase | Yes | Yes/No |
| Require digits | Yes | Yes/No |
| Require special chars | No | Yes/No (force complexity) |
| Recovery seed length | 24 words | 12 / 24 (BIP-39) |
| Recovery hint stored | Encrypted | Plain / Encrypted / None |
| Failed attempts before lockout | 10 | 3 / 5 / 10 / 20 |
| Lockout duration | 15 min | 1 / 5 / 15 / 60 / 1440 (24h) min |
| Re-prompt on critical actions | Yes | Yes/No |

#### Decyzja #6 — Backup Strategy (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Frequency | Daily | Hourly / Daily / Weekly / Manual |
| Time of day (jeśli scheduled) | 03:00 local | 00:00-23:59 |
| Retention | 30 days | 7 / 30 / 90 / 365 / forever |
| Compression | Yes (zstd) | None / gzip / zstd / xz |
| Encryption | Yes (master password) | None / Master pwd / Separate pwd |
| Include logs? | Yes | Yes / No (smaller backup) |
| Include cache? | No | Yes (faster restore) / No (smaller) |
| Verify after backup | Yes | Yes / No |
| Local backup path | `~/.sylion/<op>/backups/` | Custom path |
| Remote backup | OFF | OFF / S3 / Backblaze / SCP target |

#### Decyzja #11 — Time Zone (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Time zone | Auto-detect z OS | IANA TZ list (~600 zones) |
| Display format | 24h | 12h / 24h |
| Date format | ISO 8601 (YYYY-MM-DD) | ISO / EU (DD.MM.YYYY) / US (MM/DD/YYYY) |
| Week starts | Monday | Monday / Sunday / Saturday |
| First day of fiscal year | January 1 | Configurable per operator |
| DST handling | Auto | Auto / Disable (always standard) |

#### Decyzja #12 — Theme (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Theme mode | Auto | Auto (follow OS) / Light / Dark |
| Accent color | Green (SYLION default) | 8 preset colors / Custom hex |
| Density | Standard | Compact / Standard / Comfortable |
| Font family | System default | System / Inter / JetBrains Mono / Custom |
| Font size base | 14px | 12 / 14 / 16 / 18 / 20 px |
| Animations | Enabled | Enabled / Reduced / Disabled |
| High contrast mode | OFF | OFF / ON (WCAG AAA) |

#### Decyzja #13 — Accessibility (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Screen reader optimizations | Auto-detect | Off / On / Auto |
| Keyboard navigation | Always available | Always / Visible / Off |
| Focus indicators | Standard | Standard / Enhanced (thicker) |
| Color blind mode | OFF | OFF / Protanopia / Deuteranopia / Tritanopia |
| Reduce motion | Auto (z OS) | Auto / Always / Never |
| Show shortcuts hints | Yes | Yes / No |
| Larger touch targets | Auto (mobile) | Auto / Always / Never |
| Captions for audio (future) | OFF | OFF / Polish / English / Auto |

#### Decyzja #14 — Telemetry (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Anonymous usage stats | OFF | ON / OFF |
| Crash reports | OFF | ON / OFF / Ask each time |
| Performance metrics | OFF | ON / OFF |
| Feature usage (which faza, how often) | OFF | ON / OFF |
| Error logs (sanitized) | OFF | ON / OFF |
| Send frequency (jeśli ON) | Weekly | Hourly / Daily / Weekly / Monthly |
| Recipient | SYLION team | SYLION / Self-hosted / Both |
| Operator can review before send? | Yes | Yes / No (auto-send) |

#### Decyzja #15 — Update Policy (sub-options)

| Sub-option | Default | Range / Options |
|---|---|---|
| Update mode | Notify only | Auto / Notify only / Manual |
| Update channel | Stable | Stable / Beta / Dev (3 channels) |
| Check frequency | Daily | Hourly / Daily / Weekly / Manual |
| Critical patches | Auto-install | Auto-install / Notify / Defer |
| Major versions | Manual approval | Auto / Notify / Manual |
| Update during work hours? | Ask | Always / Never / Ask |
| Restart policy | Defer to next launch | Immediate / Defer to launch / Schedule |
| Rollback option | Keep 1 previous | Keep 0 / 1 / 3 versions |

### 1.6.4. Decision dependency graph

Niektóre decyzje są **zależne** od poprzednich:

```
Decision #1 (Język UI)
  ├─ wpływa na: #11 (date format defaults — EU dla PL, US dla EN)
  └─ wpływa na: #12 (font defaults — może być inny dla cyrylicy/CJK w przyszłości)

Decision #5 (Master password ON)
  ├─ enables: backup encryption (Decision #6 sub-option)
  ├─ enables: secrets storage w fazie 2
  └─ blocks: niektóre opcje "expose API key in plain logs"

Decision #7 (Project goals)
  ├─ wpływa na: Decision #16 (autonomy preset suggestion)
  ├─ wpływa na: defaults w fazach 4-15
  └─ wpływa na: tutorial project recommendation w Decision #8

Decision #10 (Operator role)
  ├─ Solo → minimum UI complexity, fewer settings exposed
  ├─ Team Lead → multi-user features eksponowane (mimo że jeden operator)
  └─ Klient → onboarding-heavy UX, więcej tooltips i help

Decision #14 (Telemetry)
  └─ jeśli ON: wpływa na consent flow w fazach 2-3 (gdy nowe dane są zbierane)
```

### 1.6.5. Decyzje które operator **może** odłożyć

Nie wszystkie decyzje muszą być podjęte w fazie 1. Lista tych które operator
może świadomie pominąć:

| Decyzja | Sposób pominięcia | Konsekwencja |
|---|---|---|
| #3 Email | "Skip email setup" link | Notifications limited do in-app, brak email recovery |
| #5 Master password | "Continue without password" | Sekrety storage w plain, low security mode |
| #7 Project goals | "Decide later" link | Defaults bez project-type optimization |
| #11 Time zone | "Use UTC" | Wszystko w UTC do operator zmieni w settings |
| #12 Theme | Auto z OS | Theme może się zmienić gdy operator zmieni OS theme |
| #13 Accessibility | Standard defaults | A11y features wyłączone do operator włączy |
| #14 Telemetry | OFF (default) | Brak telemetrii dopóki operator explicit włączy |
| #15 Update policy | Notify (default) | Updates pokazane jako notification |
| #16 Autonomy preset | Balanced (default) | Default użyte do faza 5 customization |

**Decyzje które MUSZĄ być podjęte** (cannot skip):
- #1 Język UI (system musi wyświetlać coś)
- #2 Display + system name (potrzebne dla audit chains)
- #4 Workspace path (system musi gdzieś zapisywać)
- #6 Backup strategy (minimum default selected)
- #8 Tutorial decision (Skip jest valid choice ale musi być explicit)
- #9 Notification channel (minimum In-app jest wybrany default)
- #10 Operator role (Solo jest default ale wybór wymagany)

---

## 1.7. Edge cases i error handling

Edge cases pogrupowane w 6 kategorii. Per kategoria 3-4 scenariusze.
Total: 22 edge cases. Każdy ma trigger, co system robi, co operator widzi
(skrócony ASCII), decision points, recovery.

### Kategoria A — Środowisko techniczne (4 cases)

#### EC-A1: Maszyna poniżej minimum RAM (4GB zamiast 8GB+)

**Trigger**: Splash → system check wykrywa <8GB RAM.

System pokazuje ostrzeżenie, ale nie blokuje (operator może chcieć
spróbować z lekkimi lokalnymi modelami):

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  RAM poniżej rekomendowanego minimum                      │
│                                                              │
│  Wykryto: 4 GB RAM                                           │
│  Rekomendowane: 8 GB minimum, 16+ GB optymalne               │
│                                                              │
│  Konsekwencje przy <8 GB:                                    │
│   • Lokalne modele >7B parametrów nie zadziałają             │
│   • Council deliberation z >5 ról może crashować             │
│   • Tutorial Standard może timeout                           │
│   • SQLite może spowalniać przy >10 projektach               │
│                                                              │
│  Sugerowane działanie:                                       │
│   • Używaj API providers (chmura) zamiast lokalnych          │
│   • Lokalnie tylko modele do 3B params (qwen2.5:3b)          │
│   • Tutorial Quick zamiast Standard                          │
│                                                              │
│  [● Continue (świadomy ograniczeń)]                          │
│  [○ Cancel install]                                          │
│  [○ Show diagnostic — co konkretnie dzieje się przy <8GB]    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**:
1. Continue z ograniczeniami (system zapamiętuje "low_ram_mode = true",
   filtruje sugestie modeli ≤3B params)
2. Cancel install
3. Diagnostic deep dive (modal z testami: ile pamięci zużywa idle, ile
   przy Council, projection per typ projektu)

**Recovery**: jeśli operator continue i potem crashuje przy faza 23,
system shows "Twoja maszyna ma 4GB RAM. Council requested 7B model.
Switch do 3B?" + sugestia restart z low_ram_mode.

#### EC-A2: Dysk pełny w trakcie instalacji

**Trigger**: install proces wymaga ~180MB binary + ~500MB initial models
(jeśli operator wybierze auto-download), dostępne <800MB.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Niewystarczająco miejsca na dysku                        │
│                                                              │
│  Wymagane:                                                   │
│   • Binary: 180 MB                                           │
│   • Workspace bootstrap: 50 MB                               │
│   • Initial backups slot: 100 MB                             │
│   • Buffer dla 30 dni użycia: 500 MB                         │
│   ────────────                                               │
│   TOTAL: ~830 MB                                             │
│                                                              │
│  Dostępne na C:\: 642 MB                                     │
│                                                              │
│  Opcje:                                                      │
│   [● Wybierz inny dysk (D:, E:, external)                ]   │
│   [○ Zwolnij miejsce na C:\ i retry                      ]   │
│   [○ Continue z ryzykiem (system może crashować przy        ]│
│      pierwszych projektach)                                  │
│   [○ Cancel install                                       ]  │
│                                                              │
│  💡 Tip: AEIS workspace rośnie ~50-200 MB per projekt.       │
│         Z 642 MB starczy na ~3-5 projektów.                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: zmiana ścieżki workspace + binary, free space tool,
ignore warning, anuluj.

**Recovery**: jeśli operator continue i potem disk full mid-build:
system pause project, alert "Disk usage 95%, free 234 MB. Pipeline pauzowany.
Zwolnij miejsce żeby kontynuować."

#### EC-A3: Antywirus karantuje instalator albo binary

**Trigger**: Windows Defender / McAfee / Kaspersky wykrywa Tauri shell jako
"unknown publisher" i blokuje. AEIS nie startuje albo binary jest deleted
podczas użycia.

System (jeśli zdąży się załadować przed kwarantanną) pokazuje:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Possible antivirus interference detected                 │
│                                                              │
│  Wykryto:                                                    │
│   • Plik 'aeis-backend.exe' został przeniesiony przez        │
│     Windows Defender (SmartScreen)                           │
│   • System może nie działać poprawnie                        │
│                                                              │
│  Co zrobić:                                                  │
│                                                              │
│   1. Dodaj wyjątek dla AEIS w antywirusie:                   │
│      Path: C:\Program Files\SYLION AEIS\                     │
│      Files: *.exe, *.dll, *.py                               │
│                                                              │
│   2. Verify integrity (SHA-256 hash):                        │
│      Pobrane: a3f2b9c8...                                    │
│      Expected: a3f2b9c8...                                   │
│      [Verify now]                                            │
│                                                              │
│   3. Jeśli nadal kłopoty:                                    │
│      • Pobierz signed installer z https://sylion.dev         │
│      • Zgłoś problem do antivirus vendor                     │
│                                                              │
│  [Open antivirus exclusions]  [Verify hash]  [Continue]      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: open antivirus settings (auto-launch), verify hash,
continue z ryzykiem, kontakt support.

**Recovery**: system co N minut sprawdza czy expected files istnieją.
Jeśli zniknęły mid-session → emergency save state, alert operator.

#### EC-A4: GPU detection failure / wrong driver

**Trigger**: operator ma NVIDIA GPU ale wrong CUDA version, lub Apple Silicon
ale Metal nie działa (rare), lub AMD bez ROCm setup.

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ  GPU wykryte ale nie skonfigurowane                       │
│                                                              │
│  Sprzęt: NVIDIA GeForce RTX 4090, 24 GB VRAM                 │
│  Status: ✗ CUDA driver nie wykryty                           │
│                                                              │
│  Bez CUDA:                                                   │
│   • Lokalne modele będą używać CPU (10-50x wolniej)          │
│   • Modele >7B params praktycznie unusable                   │
│   • Tutorial Quick może timeout                              │
│                                                              │
│  Aby włączyć CUDA:                                           │
│   1. Pobierz CUDA Toolkit 12.x                              │
│      https://developer.nvidia.com/cuda-downloads             │
│   2. Po instalacji restart AEIS                              │
│   3. Auto-detection ponowi sprawdzenie                       │
│                                                              │
│  Lub:                                                        │
│   • Continue tylko z CPU (nie polecane dla Council)          │
│   • Używaj API providers zamiast lokalnych                   │
│                                                              │
│  [Open CUDA download]  [Re-scan]  [Continue CPU-only]        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: instaluj CUDA + restart, re-scan (jeśli drivery są
ale pre-detection failed), continue CPU-only z ograniczeniami.

**Recovery**: jeśli later operator instaluje CUDA, AEIS przy każdym starcie
re-scan i auto-enable GPU mode. Notification: "CUDA wykryte! Lokalne modele
przyspieszają 10-30x."

---

### Kategoria B — Błędy operatora (4 cases)

#### EC-B1: Display name z 5000 znakami / specjalnymi

**Trigger**: operator wkleja tekst z buffer (np. cały paragraf z Worda) zamiast
imienia. Albo wpisuje emoji-flood, albo polskie znaki + emoji.

System reaguje **live validation**:

```
┌── DISPLAY NAME ─────────────────────────────────────────────┐
│                                                              │
│ [ 🚀🚀🚀 Robert "The Builder" Kowalski 🇵🇱 z Warsaw...    ]│
│                                                              │
│ ⚠ Imię za długie (124 znaki, max 64)                         │
│ ⚠ Polskie znaki OK, ale wykryte 23 emoji — czy zachować?     │
│                                                              │
│ Sugestie:                                                    │
│ [Zachowaj pierwsze 64 znaki]                                 │
│ [Usuń emoji]                                                 │
│ [Skopiuj tylko podstawowe imię: "Robert Kowalski"]           │
│ [Pozostaw co wpisałem (przycięte)]                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: 4 opcje cleanup, plus operator może edytować ręcznie.

**Edge case wewnątrz**: jeśli operator wkleja tekst z **invisible characters**
(zero-width space U+200B, BOM, RTL marks), system wykrywa i shows:

```
⚠ Wykryto 3 niewidzialne znaki:
   • U+200B (zero-width space) × 2
   • U+FEFF (BOM) × 1

Czy zachować? Mogą powodować problemy w git commits, audit chains.
[Usuń]  [Zachowaj]  [Show me which]
```

**Recovery**: jeśli operator submit z invisibles a potem audit chain pokazuje
dziwne zachowania — system może później audit identity chars i propose cleanup.

#### EC-B2: Email invalid albo cudzy email

**Trigger**: operator wpisuje `wlasnaska@niemamemaila.com` (typo), albo
`admin@anthropic.com` (cudzy email celowo lub nieświadomie).

System ma 3 levels validation:

```
Level 1: Format check (live)
  Input: "robert"  → ❌ Brak @ (nie email)
  Input: "robert@"  → ❌ Brak domeny
  Input: "robert@sylion"  → ❌ Brak TLD
  Input: "robert@sylion.dev"  → ✓ Format OK

Level 2: Domain DNS check (na blur)
  Input: "robert@sylion.dev"  → DNS query
  Result: ✓ Domain exists, MX record OK

Level 3: Reachability test (opt-in)
  ┌─────────────────────────────────────────────────────────┐
  │ Verify email by sending test message?                   │
  │                                                         │
  │ AEIS wyśle email z linkiem confirmacyjnym.              │
  │ Bez verify, niektóre features (recovery, alerts) mogą   │
  │ nie działać.                                            │
  │                                                         │
  │ [Send verification]  [Skip — verify later]              │
  └─────────────────────────────────────────────────────────┘
```

**Edge case "cudzy email"**:

System NIE może wykryć że operator wpisał czyjś email. Ale może wykryć
podejrzane wzorce:

```
⚠ Adres email wygląda na służbowy / publiczny:
   • 'admin@anthropic.com' — typowy admin email
   • 'support@stripe.com' — known company email
   • 'noreply@google.com' — system email

Czy to twój prywatny adres, czy chcesz użyć innego?

[Use this email]  [Change to personal]  [Skip email setup]
```

**Decision points**: użyj mimo to, zmień, pomiń email setup całkowicie
(notifications limited).

**Recovery**: jeśli email się okaże nieprawidłowy/cudzy później (operator
nie dostaje notifications) → Settings → Profile → "Update email" + re-verify.

#### EC-B3: Operator zamknie okno w środku setup-u

**Trigger**: operator klika X na window (Tauri) podczas storage setup
(krok 2 z 5), nie używa "Cancel" button.

System **nie ma okazji** zapytać "save progress?" jeśli sygnał TERM
przychodzi nagle. Ale ma backup mechanism.

**Co system robi**:
1. Każdy step setup-u zapisuje partial state w `~/.sylion/.partial-setup.json`
2. Przy następnym launch:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Wykryto niedokończony setup                              │
│                                                              │
│  Ostatnio przerwałeś setup w kroku 2/5 (Storage).            │
│  Data: 2026-04-29 14:32                                      │
│                                                              │
│  Zachowane dotychczas:                                       │
│   ✓ Display name: "Robert"                                   │
│   ✓ System name: "robert.k"                                  │
│   ✓ Email: r@s.dev                                           │
│   ✓ Time zone: Europe/Warsaw                                 │
│   ✗ Storage path: nie wybrano                                │
│   ✗ Master password: nie ustawiono                           │
│   ✗ Goals: nie wybrano                                       │
│   ✗ Tutorial: nie skonfigurowano                             │
│                                                              │
│  [● Continue from step 2 (Storage)]                          │
│  [○ Restart setup od początku]                               │
│  [○ Discard partial setup, exit]                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: continue, restart, discard.

**Edge case wewnątrz**: jeśli operator restart 3+ razy bez ukończenia,
system shows "Setup się nie udaje? [Get help]" + link do troubleshooting
albo kontakt.

**Recovery**: zawsze możliwa, partial state nie wycieka (encrypted-at-rest
po master password setup; przed tym tylko niewinne dane).

#### EC-B4: Master password = "password123" (słabe hasło ale operator akceptuje)

**Trigger**: operator wpisuje banalnie słabe hasło. System ma strength meter.

```
┌── MASTER PASSWORD ────────────────────────────────────────────┐
│                                                                │
│  Password:    [ ●●●●●●●●●●● 👁 ]                              │
│  Powtórz:     [ ●●●●●●●●●●● 👁 ]                              │
│                                                                │
│  Strength:  ███░░░░░░░░░░░░░  Bardzo słabe (15%)              │
│                                                                │
│  ⚠ Wykryte problemy:                                          │
│   ✗ Występuje w słownikach (rocyou, common-passwords-100k)    │
│   ✗ Tylko lowercase letters                                   │
│   ✗ Brak cyfr                                                 │
│   ✗ Brak znaków specjalnych                                   │
│   ✗ Sekwencyjne znaki (123 na końcu)                         │
│                                                                │
│  Czas złamania: ~2 sekundy (offline brute force)              │
│                                                                │
│  Sugerowane:                                                   │
│   • Minimum 12 znaków                                         │
│   • Mix: wielkie + małe + cyfra + znak specjalny              │
│   • Albo passphrase: 4-5 random słów                          │
│                                                                │
│  [Generuj silne hasło]  [Continue z słabym (NIE POLECANE)]    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Edge case — operator ignoruje warning**: po klick "Continue z słabym":

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠ Potwierdzenie świadomego użycia słabego hasła             │
│                                                              │
│  Twoje hasło jest na liście top 100 najczęściej używanych.   │
│  Atakujący z dostępem do twojego dysku może odszyfrować      │
│  workspace w sekundach.                                      │
│                                                              │
│  Konsekwencje:                                               │
│   • Klucze API mogą wyciec                                   │
│   • Cloud credentials zagrożone                              │
│   • Audit chains mogą być sfałszowane                        │
│   • Backup files łatwe do złamania                           │
│                                                              │
│  Czy na pewno użyć tego hasła?                               │
│                                                              │
│  Wpisz "ROZUMIEM" aby kontynuować:                           │
│  [ _________________ ]                                       │
│                                                              │
│  [Cancel — wybierz silniejsze]  [Use weak password]          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: silniejsze hasło (powrót do edytora), generator AEIS,
świadomy użycie słabego (z friction barrier).

**Recovery**: w przyszłości Settings → Security pokazuje "Twoje master
password jest słabe (15%). Zmień teraz." z każdym uruchomieniem AEIS
(nag screen).

---

### Kategoria C — Atak / złośliwy aktor (3 cases)

#### EC-C1: Workspace path = `/etc/` lub system path

**Trigger**: operator (przez pomyłkę albo celowo) wpisuje workspace path
w system directory: `/etc/`, `/usr/`, `/Windows/System32/`,
`C:\Program Files\` etc.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Niebezpieczna ścieżka workspace                          │
│                                                              │
│  Wpisana ścieżka: /etc/sylion/                               │
│                                                              │
│  Ta lokalizacja:                                             │
│   ✗ Jest w katalogu systemowym                               │
│   ✗ Wymaga root/admin permissions                            │
│   ✗ Może zostać overwritten przez OS update                  │
│   ✗ Może spowodować security issues (file permissions)       │
│   ✗ Backup tools mogą tego nie indeksować                    │
│                                                              │
│  AEIS NIE pozwala na workspace w:                            │
│   • /etc/, /usr/, /sys/, /proc/, /dev/                       │
│   • C:\Windows\, C:\Program Files\                           │
│   • /System/, /Library/ (macOS)                              │
│   • Root directories (/, C:\)                                │
│   • Temp directories (/tmp/, %TEMP%)                         │
│                                                              │
│  Sugerowane lokalizacje:                                     │
│   [● ~/.sylion/robert.k/       (default, recommended)    ]   │
│   [○ ~/Documents/SYLION/        (więcej widoczne)        ]   │
│   [○ /home/robert/work/aeis/    (custom user path)       ]   │
│   [○ Inny custom path: __________________________ ]          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: forced choice z whitelisted area.

**Edge case wewnątrz**: operator próbuje obejść przez symlink
(`~/.sylion/` → `/etc/sylion/`). System na bootstrap rozwiazuje symlinks
i sprawdza realpath. Jeśli realpath jest blocked → ten sam error.

**Edge case "social engineering"**: tutorial z innej strony mówi "wpisz
`/Library/AEIS/` żeby zobaczyć ukryte features". System hardcoded blokuje,
nie da się obejść argumentem.

#### EC-C2: Złośliwy ollama w PATH (supply chain attack)

**Trigger**: operator instalował coś z untrusted source które dodało
`malicious-ollama` do PATH przed real ollama. System scan wykrywa "ollama"
binary który nie jest tym czego operator oczekuje.

System sprawdza fingerprint:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Możliwa kompromitacja Ollama binary                      │
│                                                              │
│  Wykryto ollama w PATH: /usr/local/bin/ollama                │
│                                                              │
│  Verification:                                               │
│   • Binary signature: nieznana (oczekiwana: Ollama Inc)      │
│   • Hash SHA-256: ec3a1f...                                  │
│   • Known hashes (Ollama official): nie pasuje               │
│   • Owner: 'unknown_user' (oczekiwany: root lub homebrew)    │
│                                                              │
│  Możliwe wyjaśnienia:                                        │
│   • Custom build z source (legit, ale nieweryfikowalny)      │
│   • Dev version (legit, ale nieoficjalna)                    │
│   • Compromised binary (potential attack)                    │
│   • Inny program udający ollama                              │
│                                                              │
│  Co zrobić:                                                  │
│   [● Pomiń tę instalację, używaj tylko official paths]       │
│   [○ Re-install ollama z oficjalnego źródła]                 │
│   [○ Continue z ryzykiem (NIEZALECANE)]                      │
│   [○ Show diagnostic — które API endpoints wywoła ten binary]│
│                                                              │
│  ⚠ Jeśli używasz tego binary, twoje prompts (potencjalnie    │
│    z secrets, kodem) idą do nieznanego serwera/procesu.      │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: skip (tylko zaufane), reinstall z oficjalnego,
continue z risk acknowledgement, network diagnostic.

**Edge case wewnątrz "diagnostic"**: AEIS może uruchomić binary w sandboxie
i sprawdzić co to robi (które porty otwiera, jakie HTTP requests). Pokazuje
report.

**Recovery**: jeśli operator zignorował i potem wykrył kompromitację —
incident response flow: rotate API keys, audit ostatnie projekty, alert.

#### EC-C3: Brute force master password (operator AFK)

**Trigger**: operator zostawia laptop unlocked, ktoś próbuje brute force
master password przez UI (10+ failed attempts).

System ma rate limiting:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Wykryto wielokrotne failed login attempts                │
│                                                              │
│  Próby:                                                      │
│   • 09:14:23 — failed                                        │
│   • 09:14:31 — failed                                        │
│   • 09:14:38 — failed                                        │
│   • ... (10 prób w 2 minutach)                               │
│                                                              │
│  Workspace zablokowany na 15 minut.                          │
│                                                              │
│  Następna próba możliwa za: 14 min 23 sek                    │
│                                                              │
│  Aby odblokować wcześniej:                                   │
│   • Wpisz recovery seed (24 słowa)                           │
│   • Lub poczekaj cooldown                                    │
│                                                              │
│  ⚠ Jeśli to nie ty:                                          │
│   • Zamknij laptop natychmiast                               │
│   • Zmień master password po odblokowaniu                    │
│   • Sprawdź audit chain (kto fizycznie miał dostęp)          │
│   • Rotate wszystkie API keys w fazie 2                      │
│                                                              │
│  [Wait]  [Use recovery seed]  [Emergency wipe (irreversible)]│
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: czekać, użyć seed (instant unlock), emergency wipe
(usuwa workspace całkowicie — nuclear option dla skompromitowanej maszyny).

**Edge case wewnątrz "emergency wipe"**:

```
⚠ EMERGENCY WIPE — workspace zostanie nieodwracalnie usunięty.

Wymaga:
  • Wpisania recovery seed (proof of ownership)
  • Wpisania "WIPE EVERYTHING" (proof of intent)
  • 30-second countdown (proof of deliberation)

Po wipe:
  ✗ Wszystkie projekty stracone
  ✗ Wszystkie audit chains stracone
  ✗ Wszystkie klucze API stracone (musisz revoke z provider sites!)
  ✗ Wszystkie backup files lokalne usunięte

AEIS po wipe:
  ✓ Restart do clean state (pusta baza)
  ✓ Operator może zacząć od nowa lub odinstalować

Rozważ alternatywy:
  • Disconnect maszynę od internetu (atakujący nie może exfilltrate)
  • Zadzwoń security expert
  • Backup workspace na external drive zanim wipe
```

**Recovery po wipe**: tylko z external backup (jeśli operator robił).
W przeciwnym razie: clean install.

---

### Kategoria D — Multi-instance / multi-tenant edge cases (3 cases)

#### EC-D1: Drugi operator próbuje workspace na tej samej maszynie

**Trigger**: Robert ma workspace `~/.sylion/robert.k/`. Jego współpracownik
Anna próbuje uruchomić AEIS na tej samej maszynie. Default behavior:
single-operator (P1.3 = a). Ale Anna chce swój workspace.

System przy splash:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Wykryto istniejący workspace                             │
│                                                              │
│  Active operator: Robert (robert.k)                          │
│  Workspace: ~/.sylion/robert.k/                              │
│                                                              │
│  Czy to ty?                                                  │
│                                                              │
│  [● Tak — kontynuuj jako Robert]                             │
│  [○ Nie — utwórz nowy workspace dla mnie]                    │
│  [○ Switch do innego workspace]                              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Jeśli "Nie — utwórz nowy":

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Nowy operator na tej maszynie                            │
│                                                              │
│  Mimo że P1.3 ustawione na "single-operator per maszyna",    │
│  możesz utworzyć dodatkowy workspace dla siebie.             │
│                                                              │
│  Konsekwencje:                                               │
│   ✓ Twój workspace będzie w ~/.sylion/<your-name>/           │
│   ✓ Pełna separacja od workspace Roberta                     │
│   ✓ Osobne settings, projekty, audit chains                  │
│   ⚠ Współdzielicie ten sam binary AEIS                       │
│   ⚠ Tylko jeden operator może mieć aktywny system tray icon  │
│   ⚠ Ports konfliktują (drugi operator dostanie auto-port)    │
│                                                              │
│  Twoje system info:                                          │
│   OS user: anna                                              │
│   Suggested system name: anna.k                              │
│                                                              │
│  [Continue jako nowy operator]  [Cancel]                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: continue (faza 1 dla Anny od początku), cancel,
switch (jeśli istnieje już Anna's workspace).

**Edge case wewnątrz "switch"**: jeśli operator widzi listę 3 workspaces
(robert.k, anna.k, dev) — pokazuje selector. Każdy ma własny master password.

#### EC-D2: Operator używa AEIS na maszynie wirtualnej (snapshot)

**Trigger**: VM-based environment (VMware, VirtualBox, Parallels).
Operator robi snapshot, potem rollback. Workspace state cofa się ale
backups (jeśli na external storage) nie.

System detect VM environment przy bootstrap:

```
┌──────────────────────────────────────────────────────────────┐
│  ℹ  Wykryto wirtualną maszynę                                │
│                                                              │
│  Hypervisor: VMware Workstation                              │
│                                                              │
│  Specjalne uwagi dla VM:                                     │
│   • Snapshots mogą cofnąć stan workspace (utrata danych!)    │
│   • Performance: -10-30% vs native                            │
│   • GPU passthrough wymagany dla lokalnych modeli            │
│   • Sieciowanie: NAT/Bridged wpływa na port forwarding        │
│                                                              │
│  Sugerowane:                                                 │
│   ☑ Auto-backup do external host folder (poza snapshot)      │
│   ☑ Notification przy snapshot/rollback events               │
│   ☑ External backup co N minut (zalecane: 30min)             │
│                                                              │
│  [Continue z VM-aware settings]  [Continue normalnie]         │
│  [Show me jak skonfigurować shared folder dla backups]       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: VM-aware mode (specialne settings), normal mode,
help dla backup shared folder.

**Edge case wewnątrz "rollback detection"**: jeśli AEIS wykryje że current
file mtime jest **starsza** niż last audit chain entry → wykrywa rollback:

```
⚠ Wykryto cofnięcie czasu w workspace.

Audit chain ma wpis z 2026-04-29 14:32, ale current time to
2026-04-29 14:15. Możliwe że:
  • VM snapshot rollback
  • System clock cofnięty
  • Workspace skopiowany z innej maszyny

Co zrobić:
  • Restore z external backup (jeśli dostępny)
  • Continue z aktualnym state (audit chain będzie miało gap)
  • Investigate (manual review)
```

#### EC-D3: Konflikt z innym narzędziem o port 8127

**Trigger**: AEIS chce port 8127 (default). Coś już go używa (npm dev
server, Docker container, inny user-mode service).

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Port 8127 zajęty                                         │
│                                                              │
│  AEIS wymaga lokalnego portu HTTP. Default 8127 zajęty przez:│
│                                                              │
│  Process: node (PID 4823)                                    │
│  Command: npm run dev                                        │
│  Path: /home/robert/projects/some-app                        │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Auto-find free port]                                     │
│      System znajdzie pierwszy wolny port w zakresie          │
│      8127-8200. Aktualnie wolny: 8128                        │
│                                                              │
│  [○ Manual port selection]                                   │
│      Wpisz port: [ _____ ] (1024-65535)                      │
│                                                              │
│  [○ Kill blocking process and retry]                         │
│      ⚠ Może zatrzymać twoją inną pracę. Sprawdź process      │
│        powyżej zanim zaakceptujesz.                          │
│                                                              │
│  [○ Cancel — zatrzymaj proces ręcznie i zrestartuj AEIS]     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: auto port (najczęstsze), manual port, kill process,
cancel.

**Edge case wewnątrz**: jeśli operator wybiera nowy port, system zapamiętuje
go w preferences. Następne uruchomienie automatycznie używa tego portu.
Web access URL aktualizuje się na nowy.

---

### Kategoria E — Recovery / disaster (4 cases)

#### EC-E1: Workspace corruption po bad shutdown

**Trigger**: power loss / kernel panic / forced shutdown podczas SQLite write.
Database może być w inconsistent state.

Przy następnym launch:

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Workspace może być uszkodzony                            │
│                                                              │
│  Wykryto:                                                    │
│   • SQLite database lock file istnieje (zwykle = open)       │
│   • Last journal entry: incomplete                           │
│   • Last clean shutdown: 2026-04-28 (1 dzień temu)           │
│   • Last activity: 2026-04-29 14:32 (przed crashem?)         │
│                                                              │
│  Diagnostyka:                                                │
│   [● Run SQLite integrity check (~30 sek)]                   │
│                                                              │
│  Jeśli OK:                                                   │
│   → Continue normalnie                                        │
│                                                              │
│  Jeśli corruption:                                           │
│   [○ Restore z latest backup (data: 2026-04-28 03:00)]       │
│   [○ Try repair (best effort, może utracić ostatnie zmiany)] │
│   [○ Manual recovery (advanced)]                             │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Po integrity check**:

Jeśli OK:
```
✓ Database OK. Recovery nie potrzebne.
  Last journal entry replay-owalny.
  Czas restore: 2 sekundy.
  [Continue]
```

Jeśli corruption:
```
✗ Database corruption wykryte:
  • Table 'audit_chain' rows 1247-1302 nieczytelne
  • Foreign key violation w 'projects' table

Sugerowane:
  Restore z backup (utrata: ~12h pracy)
  → Continue z restore

Lub:
  Try repair (utrata: ostatnie 5-10 wpisów)
  → Może być dobre dla większości
```

**Decision points**: restore z backup, try repair, manual recovery.

**Edge case wewnątrz "manual recovery"**: open file manager z paths do
SQLite + journals + backups. Operator (advanced user) może użyć tools
typu `sqlite3 .recover`.

#### EC-E2: Operator zapomniał master password ALE ma seed phrase

**Trigger**: operator wraca do AEIS po 6 miesiącach, nie pamięta hasła.
Ale ma seed phrase zapisaną.

Login screen:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Workspace login                                          │
│                                                              │
│  Master password:  [ _____________________ ]                 │
│  Hint: "Mój ulubiony cytat z 2017 + numer ulicy"             │
│                                                              │
│  [Login]  [Forgot password?]                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Po klick "Forgot password?":

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Recovery via seed phrase                                 │
│                                                              │
│  Wpisz 24 słowa recovery seed:                               │
│                                                              │
│  1.  [_______]   9.  [_______]   17. [_______]               │
│  2.  [_______]  10.  [_______]   18. [_______]               │
│  3.  [_______]  11.  [_______]   19. [_______]               │
│  4.  [_______]  12.  [_______]   20. [_______]               │
│  5.  [_______]  13.  [_______]   21. [_______]               │
│  6.  [_______]  14.  [_______]   22. [_______]               │
│  7.  [_______]  15.  [_______]   23. [_______]               │
│  8.  [_______]  16.  [_______]   24. [_______]               │
│                                                              │
│  💡 Suggestions:                                             │
│   • Każde słowo z BIP-39 wordlist (autocomplete)             │
│   • Kolejność matter (nie pomieszaj!)                        │
│   • Spaces between words ignored                             │
│   • Case insensitive                                         │
│                                                              │
│  [Verify seed]  [Cancel]                                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

Po verify:

```
✓ Seed valid. Workspace odszyfrowany.

Następny krok:
  ⚠ Musisz ustawić nowy master password.
  
  New password:  [ _____________________ ]
  Repeat:        [ _____________________ ]
  Strength:      ████████████░░  Strong (75%)
  
  [Set new password and continue]
```

**Decision points**: wpisz seed, verify, set new password.

**Edge case wewnątrz**: jeśli seed wpisany niepoprawnie 5 razy → 1h cooldown
+ alert "Możliwa próba ataku przez seed brute-force".

**Recovery po new password**: stary password jest nieważny. Wszystkie backups
(jeśli zaszyfrowane starym) muszą być re-encrypted lub stają się nieczytelne.
System pokazuje warning.

#### EC-E3: Operator zgubił seed phrase ALE pamięta password

**Trigger**: operator pamięta master password (loguje się normalnie), ale
przeczytał że seed jest ważny i chce sprawdzić — okazuje się że plik z seed
zniknął/spalono kartę.

```
Settings → Security → "Recovery seed status"

┌──────────────────────────────────────────────────────────────┐
│  ●  Recovery Seed Status                                     │
│                                                              │
│  Seed: ✓ Generated 2026-03-15                                │
│        ✗ Not verified jako "safely stored"                   │
│                                                              │
│  ⚠ Jeśli zgubisz seed I zapomnisz password — workspace      │
│    JEST NIEODZYSKIWALNY.                                     │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Show seed again]                                         │
│      Wymaga master password.                                 │
│      Pokaż na ekranie z opcjami:                             │
│        - Print recovery card                                 │
│        - Save to encrypted file                              │
│        - Email do siebie (encrypted attachment)              │
│        - Fizyczne wpisanie na papier                         │
│                                                              │
│  [○ Generate NEW seed]                                       │
│      ⚠ Stara seed przestanie działać.                        │
│      Workspace re-encrypted z nową kombinacją.               │
│      Wszystkie backups zrobione przed tym muszą być          │
│      re-zaszyfrowane lub stają się nieczytelne.              │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: show seed (zachowuje original), generate new (rotation
operation).

**Edge case wewnątrz "generate new seed"**:

```
⚠ Generation new seed wymaga full re-encryption.

Czas: 2-15 minut (zależnie od rozmiaru workspace).
Może crash AEIS jeśli przerwany — therefore wymaga:
  ✓ Pełen backup workspace
  ✓ Nieprzerwane zasilanie
  ✓ Master password verification

[Start re-encryption]  [Cancel]
```

Po sukcesie: nowa seed (verify znów), stary password nadal ważny.

#### EC-E4: Krytyczna aktualizacja AEIS w trakcie tutorialu

**Trigger**: operator jest w środku Standard tutoriala (45 min). AEIS
sprawdza updates, znajduje critical security patch.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Critical Security Update Available                       │
│                                                              │
│  Wersja: v3.0.1 → v3.0.2                                     │
│  Type: Security patch (HIGH severity)                        │
│  Issue: CVE-2026-XXXX (Council deliberation injection)       │
│                                                              │
│  Aktualnie:                                                  │
│   • Tutorial w trakcie: faza 23 (Council Deliberation)       │
│   • Postęp: 8/15 kroków                                       │
│   • Update wymaga restart                                    │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Pause tutorial, install update, resume]                  │
│      Tutorial state zachowany.                               │
│      Czas update: 2-5 min.                                   │
│      Po restart automatycznie wracasz do tutorialu.          │
│                                                              │
│  [○ Defer update do końca tutorialu (~30 min)]               │
│      ⚠ Pracujesz z znaną luką do tego czasu.                 │
│      System wyłączy non-essential network calls.             │
│                                                              │
│  [○ Defer 24h]                                               │
│      ⚠ Mocno NIE polecane dla critical security.             │
│      Wymaga "I accept the risk" confirmation.                │
│                                                              │
│  [○ Update notes — co dokładnie naprawia]                    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: pause + install + resume (recommended), defer end of
tutorial, defer 24h (with friction), read notes.

**Edge case wewnątrz "defer 24h"**:

```
⚠ Defer 24h dla critical security patch

Wpisz "I ACCEPT THE RISK" aby kontynuować.
Po 24h system automatycznie zainstaluje update (force).
W tym czasie:
  ✗ Council deliberacje wyłączone (znana luka)
  ✗ Network egress dla LLM API ograniczony
  ✗ Audit chain ma "vulnerable_period" markers

[ _________________ ]
[Continue with risk]  [Install now zamiast defer]
```

**Recovery**: po update, tutorial state restore z snapshot. Jeśli auto-resume
fail (np. data structure changed in update) → operator startuje tutorial od
początku z notification "Tutorial restartowany z powodu update v3.0.2".

---

### Kategoria F — Integracja z innymi narzędziami (4 cases)

#### EC-F1: VS Code workspace folder coliduje z AEIS workspace

**Trigger**: operator używa VS Code i otwiera `~/.sylion/robert.k/` jako
workspace folder w VS Code. VS Code tworzy `.vscode/` folder, settings.json,
może auto-format pliki AEIS.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Wykryto VS Code activity w workspace                     │
│                                                              │
│  Wykryto:                                                    │
│   • .vscode/ folder utworzony w ~/.sylion/robert.k/          │
│   • .vscode/settings.json modyfikowany 5 min temu            │
│   • Pliki audit_chain/*.jsonl modyfikowane przez external    │
│     proces (mtime niezgodne z AEIS write logs)               │
│                                                              │
│  Konsekwencje:                                               │
│   ✗ Audit chain integrity może być uszkodzona                │
│   ✗ JSON formatting przez prettier może łamać parsing        │
│   ✗ Auto-save VS Code może zapisać partial writes            │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Add ~/.sylion/ do .vscode/settings.json exclude list]    │
│      VS Code przestanie indeksować workspace AEIS.           │
│                                                              │
│  [○ Move AEIS workspace do innej lokalizacji]                │
│      Sugerowane: ~/.aeis-storage/ (less likely w IDE).       │
│                                                              │
│  [○ Continue z risk acknowledgement]                         │
│      ⚠ Możliwe future audit chain corruption.                │
│                                                              │
│  [○ Show diagnostic — które pliki są modyfikowane]            │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: VS Code exclude (auto-config), move workspace,
continue z risk.

**Edge case wewnątrz**: jeśli operator chce eksplorować pliki w VS Code
(read-only), AEIS może utworzyć **mirror folder** z symlinks (read-only),
oddzielnie od workspace.

#### EC-F2: Git repository w workspace (operator zrobił `git init`)

**Trigger**: operator chce versionować settings AEIS w git (np. dla
collab z zespołem). Robi `git init` w `~/.sylion/robert.k/`.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Git repository wykryte w workspace                       │
│                                                              │
│  Path: ~/.sylion/robert.k/.git/                              │
│  Created: 5 min temu                                         │
│  Status: clean (nothing committed)                           │
│                                                              │
│  ⚠ KRYTYCZNE OSTRZEŻENIE:                                    │
│                                                              │
│  Workspace zawiera secrets:                                  │
│   • API keys (encrypted ale w plikach)                       │
│   • Cloud credentials                                        │
│   • Master password hash + salt                              │
│                                                              │
│  Jeśli git repo zostanie:                                    │
│   • git push do public/private remote → secrets wycieka      │
│   • git history retains everything → nawet "deleted" secrets │
│                                                              │
│  Sugerowane akcje:                                           │
│                                                              │
│  [● Auto-create .gitignore z secret paths]                   │
│      Excludes: secrets/, credentials/, *.key, *.pem,         │
│                api_keys.db, master.salt, cloud_*.json         │
│      Operator może git add reszta safely.                    │
│                                                              │
│  [○ Create separate config-export folder dla git]            │
│      Sanitized export (bez secrets) → ~/.aeis-config-export/ │
│      Operator git tracks tę kopię, nie workspace.            │
│                                                              │
│  [○ Remove .git/ całkowicie]                                 │
│      Workspace nie powinien być git tracked.                 │
│                                                              │
│  [○ Continue (zrozumiałem ryzyko)]                           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: gitignore (most safe + flexible), separate export,
remove git, continue.

**Edge case wewnątrz "gitignore"**: AEIS dynamiczne aktualizuje gitignore
gdy nowe rodzaje secret files są tworzone (np. dodanie nowego cloud
provider w fazie 3 → gitignore dodaje jego credentials path).

#### EC-F3: Dropbox / OneDrive próbuje sync workspace folder

**Trigger**: operator dał workspace path w Dropbox folder (pomylenie się),
albo Dropbox dynamicznie monitoruje home folder.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Cloud sync conflict wykryty                              │
│                                                              │
│  Wykryto:                                                    │
│   • Workspace path: ~/Dropbox/sylion/                        │
│   • Active cloud sync: Dropbox (running)                     │
│   • Last sync: 2 min temu                                    │
│                                                              │
│  Dlaczego to jest problem:                                   │
│                                                              │
│  ✗ SQLite databases mogą być corrupted by sync               │
│    Dropbox może upload partial state podczas write           │
│                                                              │
│  ✗ Audit chain hashes mogą się rozjechać                     │
│    Sync tworzy "conflict copies" przy concurrent writes      │
│                                                              │
│  ✗ Secrets mogą wyciec do cloud bez wiedzy                   │
│    Mimo że encrypted, klucze szyfrujące są w innych plikach  │
│                                                              │
│  ✗ Performance: każdy write może trwać sekundy               │
│    Dropbox czeka na sync confirmation                        │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Migrate workspace do non-synced location]                │
│      Sugerowane: ~/.sylion/ (standard, nie w Dropbox)        │
│      Czas migracji: 30 sek - 5 min (zależnie od rozmiaru)    │
│                                                              │
│  [○ Add ~/Dropbox/sylion/ do Dropbox exclude list]           │
│      Auto-config Dropbox client (jeśli możliwe).             │
│                                                              │
│  [○ Continue z risk (NIE POLECANE)]                          │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: migrate (najlepiej), exclude (jeśli operator chce
zostać w tej lokalizacji), continue (z big warning).

**Edge case wewnątrz "migrate"**: pokazuje progress bar, weryfikuje
checksums przed/po, opcja rollback jeśli coś pójdzie źle podczas migration.

#### EC-F4: Antywirus karantuje wygenerowane pliki w trakcie tutorial build

**Trigger**: tutorial Standard generuje real code (np. Python files dla
backend). Antywirus może rozpoznać niektóre wzorce (np. subprocess calls)
jako podejrzane i blokować/karantować.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠  Antivirus interference wykryta podczas build             │
│                                                              │
│  Build phase: 26 (Build Orchestration)                       │
│  Status: PARTIALLY COMPLETED                                 │
│                                                              │
│  Antywirus karantował:                                       │
│   • backend/api_routes.py (zawiera subprocess.run())         │
│   • backend/scripts/install.sh (executable script)           │
│   • frontend/build.js (npm build trigger)                    │
│                                                              │
│  Konsekwencje:                                               │
│   ✗ Build incomplete (3/12 plików missing)                   │
│   ✗ Tutorial nie może continue do testowania                  │
│   ✗ Możliwe że więcej plików będzie blocked w future         │
│                                                              │
│  Opcje:                                                      │
│                                                              │
│  [● Add tutorial workspace do antivirus exclusions]          │
│      Path: ~/.sylion/robert.k/tutorial/                      │
│      System pokaże instrukcje per antivirus brand:           │
│        Windows Defender, McAfee, Kaspersky, ESET, Bitdefender │
│                                                              │
│  [○ Restore karantowane pliki i retry build]                 │
│      Wymaga manual akcji w antivirus UI.                     │
│      Po restore, build retry automatycznie.                  │
│                                                              │
│  [○ Skip blocked patterns w tutorial]                        │
│      AEIS regeneruje kod bez subprocess/script triggers.     │
│      Tutorial ograniczony, ale ukończalny.                   │
│                                                              │
│  [○ Switch tutorial do innego projektu]                      │
│      PKB nie generuje executable scripts → bezpieczniejszy.  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Decision points**: antivirus exclude, restore + retry, skip blocked
patterns, switch tutorial.

**Edge case wewnątrz**: AEIS może mieć **whitelist mode** dla generated
code — sygnatura SYLION embedded w plikach pozwala antivirus producentom
rozpoznać że to legit AEIS output (jeśli future kontakty z AV vendors).

---

## 1.7.X. Edge cases summary table

Wszystkie 22 edge cases dla quick reference:

| ID | Kategoria | Trigger | Hard block? | Recovery |
|---|---|---|---|---|
| EC-A1 | Tech | RAM <8GB | No (warning) | Use API/3B models |
| EC-A2 | Tech | Dysk pełny | Tak | Free space / change path |
| EC-A3 | Tech | Antywirus block | Tak | Add exclusion / verify hash |
| EC-A4 | Tech | GPU drivers missing | No (limited) | Install CUDA / use API |
| EC-B1 | Operator | Display name overflow | No (live valid.) | Truncate / clean |
| EC-B2 | Operator | Email invalid | No (live valid.) | Re-enter / skip |
| EC-B3 | Operator | Window closed mid-setup | No | Resume from partial |
| EC-B4 | Operator | Weak password | No (warning) | Force confirm "ROZUMIEM" |
| EC-C1 | Atak | System path workspace | Tak | Whitelist only |
| EC-C2 | Atak | Compromised binary | No (warning) | Re-install / skip |
| EC-C3 | Atak | Brute force password | Tak | Cooldown / seed unlock |
| EC-D1 | Multi | Drugi operator | No | Create new workspace |
| EC-D2 | Multi | VM environment | No (info) | Enable VM mode |
| EC-D3 | Multi | Port konflikt | No | Auto-find port |
| EC-E1 | Recovery | Workspace corruption | Tak (until fix) | Restore / repair |
| EC-E2 | Recovery | Forgot password | Tak | Use seed |
| EC-E3 | Recovery | Lost seed | No | Show seed / regenerate |
| EC-E4 | Recovery | Critical update mid-tutorial | No | Install / defer |
| EC-F1 | Integracja | VS Code workspace conflict | No (warning) | Exclude / move |
| EC-F2 | Integracja | git init w workspace | No (critical warn) | gitignore / export |
| EC-F3 | Integracja | Dropbox sync workspace | No (warn) | Migrate / exclude |
| EC-F4 | Integracja | Antivirus block builds | No | Exclude / restore |

**Hard block** = operator nie może continue dopóki nie rozwiązany.
**No** = system pozwala continue (z warning lub modyfikacjami).

---

## 1.8. Telemetria i audit chain

### 1.8.1. Co system loguje w fazie 1

Każdy krok generuje entry w `audit_chain/onboarding.jsonl`:

```jsonl
{"ts":"2026-04-29T14:30:01Z","event":"onboarding.start","operator":"robert.k"}
{"ts":"2026-04-29T14:30:02Z","event":"system.check","gpu":"RTX 4090","ram_gb":32,"disk_free_gb":847}
{"ts":"2026-04-29T14:30:05Z","event":"local.scan.complete","models_found":3,"providers":["ollama"]}
{"ts":"2026-04-29T14:31:14Z","event":"identity.set","display":"Robert","system":"robert.k","email":"r@s.dev"}
{"ts":"2026-04-29T14:32:08Z","event":"storage.configured","path":"~/.sylion/robert.k/"}
{"ts":"2026-04-29T14:33:42Z","event":"password.enabled","strength":75}
{"ts":"2026-04-29T14:34:11Z","event":"recovery.seed.verified"}
{"ts":"2026-04-29T14:35:28Z","event":"goals.selected","categories":["public_products","cybersecurity"]}
{"ts":"2026-04-29T14:36:00Z","event":"tutorial.start","depth":"standard","project":"crm_freelancer"}
```

**Hash chain** — każdy entry ma `prev_hash` linkujący do poprzedniego (tamper-evident).

### 1.8.2. Co NIE jest logowane (privacy)

- Master password (oczywiste)
- Recovery seed słowa (tylko fact że verified)
- Email (jeśli operator wybierze "private email" flag w settings)
- Treść pomysłów wpisanych w tutorialu (logowane tylko fact że tutorial zakończony)

---

## 1.9. Inheritance pattern w fazie 1

Faza 1 ustanawia **defaults** dla późniejszych faz. Każde ustawienie z fazy
1 propaguje przez 4 poziomy: **Global → Project → Phase → Decision**.

### 1.9.1. Tabela override paths

| Setting (z fazy 1) | Override w fazie | Sposób override |
|---|---|---|
| Język UI | Faza 4 (Workspace Defaults) | Settings → Profile → Language |
| System name | nieznlienialne (audit chain) | Wymaga migration tool |
| Workspace path | nieznlienialne | Settings → Storage → Migrate |
| Master password | Faza 4 albo Settings → Security | Re-auth required |
| Backup strategy | Faza 4 (Workspace Defaults) | Bezpośrednio w Settings |
| Project goals | Faza 4 (Workspace Defaults) | Aktualizuje suggested defaults |
| Default autonomy preset | Faza 5 (Autonomy Configuration) | Pełna konfiguracja 10 wymiarów |
| Default notification channel | Faza 4 (Workspace Defaults) | Per-event customization |
| Theme | Faza 4 / Settings → Appearance | Per-component override |
| Telemetry | Faza 4 / Settings → Privacy | Per-event opt-in |
| Update policy | Faza 4 / Settings → System | Per-update decision |
| Time zone | Settings → Profile | Project-level override w fazie 17 |
| Tutorial mode | Settings → Help | Re-run via `/tutorial` command |
| Operator role | Settings → Profile | Wymaga restart (UI complexity rebuild) |

### 1.9.2. Konkretne przykłady inheritance

**Przykład 1 — Autonomy preset (single dimension)**:

```
Faza 1 sets:    Default autonomy: Balanced
                ↓
Faza 5 reads:   Inherited from Faza 1: Balanced
                Operator może zmienić per dimension (10 wymiarów L0-L5)
                Override: Conservative dla cost_decisions, Aggressive dla rest
                ↓
Faza 17 reads:  Inherited from Faza 5: Mixed (Conservative cost / Aggressive rest)
                Project-level: ten projekt jest D5, więc forced Conservative
                Override: project = full Conservative (wszystkie wymiary)
                ↓
Faza 23 reads:  Inherited from project: Conservative
                Operator może override per round
                Round override: użyj Aggressive tylko dla tej deliberacji
                ↓
Faza 24 reads:  Inherited from round: Aggressive
                Decision override: dla tej jednej decyzji wróć do Conservative
                (operator chce dodatkowy review)
```

**Przykład 2 — Język UI (cross-cutting setting)**:

```
Faza 1 sets:    Język UI: PL
                ↓
Wpływ na fazę 4: Notification templates default PL
                  Project goals descriptions PL
                  Workspace status messages PL
                ↓
Wpływ na fazę 5: Autonomy explanation tooltips PL
                  Hard gates descriptions PL
                ↓
Wpływ na fazę 12: Council templates names może być po PL ("Architekt", "Krytyk")
                   ALBO po EN (więcej zgodne z technical convention)
                   Operator wybiera w fazie 12
                ↓
Wpływ na fazę 17: Project-level override możliwe (np. ten projekt po EN
                   bo zespół międzynarodowy)
                ↓
Wpływ na fazę 23: Council deliberation language wybór:
                   - PL UI ale modele dyskutują po EN (technical accuracy)
                   - PL UI + modele po PL (consistency, ale niektóre concept lose)
                   - Mixed (każdy model w swoim native)
```

**Przykład 3 — Notification channel (event-specific propagation)**:

```
Faza 1 sets:    Default channel: In-app
                ↓
Faza 4 expands: Per typ event:
                  Council finalize → In-app + Email
                  HG required → In-app + Email + SMS (jeśli skonfigurowane)
                  Build complete → In-app
                  Critical error → Email + Slack (jeśli skonfigurowane)
                  Cost threshold → Email
                  Deploy success → Slack
                ↓
Faza 17 reads:  Inherited z fazy 4
                Project-level override: ten projekt critical, dodaj SMS
                dla wszystkich D4+ events
                ↓
Faza 23 reads:  Operator może wyciszyć notyfikacje dla tej sesji
                ("Don't bother me, I'm watching live")
                ↓
Faza 24 reads:  Decision-level: ta jedna decyzja ma silent mode
                (operator wie że to D5, czeka na finalize bez interrupt)
```

**Przykład 4 — Backup strategy (cross-system propagation)**:

```
Faza 1 sets:    Daily, 30d retention, encrypted z master password
                ↓
Faza 2 reads:   API keys storage używa same encryption pattern
                Backup includes encrypted keys
                ↓
Faza 3 reads:   Cloud credentials storage uses same encryption
                Cloud backup config może być extension w fazie 3
                ↓
Faza 17 reads:  Project-level: dodatkowy backup pre/post każdej Council session
                ("milestone backups" beyond daily)
                ↓
Faza 41 reads:  Closure phase wymusza final backup przed archiwizacją
                Może override retention dla zarchiwizowanych: forever
```

**Przykład 5 — Project goals (suggested defaults propagation)**:

```
Faza 1 sets:    Goals: Public products + Cybersecurity
                ↓
Faza 4 reads:   Suggested defaults:
                  Budget per project: $50 (vs $20 dla Apps internal)
                  Default autonomy: Conservative
                  Notifications: Email + In-app (vs In-app only)
                  Backup frequency: Daily (vs Weekly)
                ↓
Faza 5 reads:   Suggested autonomy preset: Conservative
                Hard gates: production deploy MANDATORY
                                cost > $10 MANDATORY
                ↓
Faza 6-10 reads: Guards configurations use Conservative thresholds
                  Cost Guard: alerts at 50%, pause at 80%
                  Security Guard: scan every 5 min vs 30 min
                ↓
Faza 12 reads:  Council templates: D4+ require external review checkpoint
                  D5 require full board (10+ roles)
                ↓
Faza 17 reads:  Per-project: każdy nowy projekt inheritsje te defaults
                  Operator może override gdy projekt jest research/internal
```

### 1.9.3. Override conflict resolution

Co się dzieje gdy 2 levels wskazują **różne** wartości?

**Przykład**: faza 1 mówi "autonomy Balanced", faza 5 mówi "autonomy
Conservative", faza 17 (project) mówi "autonomy Aggressive".

**Reguła**: **najnowsza decyzja wygrywa, ale zawsze pokazujesz inheritance**:

```
Faza 23 (Council Deliberation):
  Effective autonomy: Aggressive (project-level override)
  
  Inheritance chain:
    Global default (Faza 1):    Balanced
    Operator config (Faza 5):   Conservative ←  override
    Project override (Faza 17): Aggressive ← override (najnowsze)
  
  [Restore to Conservative]  [Restore to Balanced]  [Keep Aggressive]
```

Operator może w każdej chwili **zaprzeczyć override** i wrócić do
poprzedniego poziomu.

### 1.9.4. Edge case — partial inheritance

Co jeśli faza 5 override'uje **część** z 10 wymiarów autonomy ale nie wszystkie?

**Przykład**:
- Faza 1: autonomy preset = Balanced (= L2 dla wszystkich 10 wymiarów)
- Faza 5: override tylko `cost_decisions` na L4 (Aggressive), reszta zostaje
- Faza 17: override tylko `model_selection` na L1 (Guided), reszta zostaje

**Effective config w fazie 23**:
```
DIM-1 Council formation:           L2 (Balanced, z fazy 1)
DIM-2 Council voting threshold:    L2 (Balanced, z fazy 1)
DIM-3 Cost decisions:              L4 (Aggressive, z fazy 5)  ← override
DIM-4 Model selection:             L1 (Guided, z fazy 17)     ← override
DIM-5 Environment selection:       L2 (Balanced, z fazy 1)
DIM-6 Skill creation:              L2 (Balanced, z fazy 1)
DIM-7 Quality verdicts:            L2 (Balanced, z fazy 1)
DIM-8 Deploy authorization:        L2 (Balanced, z fazy 1)
DIM-9 Mid-flight overrides:        L2 (Balanced, z fazy 1)
DIM-10 Cascade re-evaluation:      L2 (Balanced, z fazy 1)
```

UI pokazuje to jako **multi-color inheritance map**:

```
Autonomy Profile (this project):

  ████ ████ ████ ████ ████ ████ ████ ████ ████ ████
  L2   L2   L4   L1   L2   L2   L2   L2   L2   L2

  Inherited from:
    [████ Faza 1 default]  (8 dimensions)
    [████ Faza 5 override]  (1 dimension: cost_decisions)
    [████ Project override] (1 dimension: model_selection)

  [Edit each dimension]  [Reset to Faza 1]  [Save as new preset]
```

---

## 1.10. Co dalej (przejście do fazy 2)

Po fazie 1, operator widzi:

```
┌──────────────────────────────────────────────────────────────┐
│  ●  Faza 1 zakończona  ·  Welcome to AEIS, Robert            │
│                                                              │
│  Twój workspace jest gotowy.                                 │
│                                                              │
│  Następne kroki (możesz iść w dowolnej kolejności):          │
│                                                              │
│  ┌── PRIORYTETOWE ──────────────────────────────────────┐   │
│  │  [→] Faza 2 — Provider Catalog Configuration          │   │
│  │      Dodaj klucze API (Anthropic, OpenAI, Google,    │   │
│  │      OpenRouter), konfiguruj lokalne modele.          │   │
│  │      Czas: 10-30 min                                 │   │
│  │      Status: 3 lokalne modele już dodane             │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌── KONFIGURACJA ──────────────────────────────────────┐   │
│  │  [ ] Faza 3 — Environment Configuration               │   │
│  │       Local + VPS + cloud + sovereign + edge          │   │
│  │  [ ] Faza 4 — Workspace Defaults                      │   │
│  │       Budgety, autonomy, notifications, shortcuts     │   │
│  │  [ ] Faza 5 — Autonomy Configuration                  │   │
│  │       10 wymiarów autonomy + hard gates               │   │
│  │  [ ] Faza 6-10 — Guards Setup (6 fazy)               │   │
│  │       Coherence, Cost, Security, Quality, Provenance  │   │
│  │  [ ] Faza 11 — Skills Library Bootstrap              │   │
│  │  [ ] Fazy 12-15 — Templates                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌── LUB ─────────────────────────────────────────────────┐  │
│  │  [→] Rozpocznij pierwszy projekt (Faza 16)            │  │
│  │       System użyje minimum config + lokalnych modeli  │  │
│  │       Tutorial już zakończony? Zacznij real project!  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌── POMOC ──────────────────────────────────────────────┐  │
│  │  • `/help` — lista wszystkich komend terminala        │  │
│  │  • `/tutorial` — re-run tutorial                       │  │
│  │  • Settings → Help — full documentation              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Recommended path** (z highlightem):
- Faza 2 (Provider Catalog) — niezbędne jeśli chcesz API
- Faza 4 (Workspace Defaults) — szybkie tuning
- Faza 16 (New Project) — możesz pominąć fazy 5-15 i wrócić do nich gdy zajdzie potrzeba

**Power user path**:
- Wszystkie fazy 2-15 w kolejności — pełen setup przed pierwszym projektem
- Operator który ma czasu i chce mieć wszystko przed startem

---

## 1.11. Otwarte pytania zanim freeze

Przed soft-freeze fazy 1, kilka rzeczy które operator może chcieć zmienić — zostawiam jako TBD:

**TBD-1**: Auto-start przy boot OS?
- Tak default / nie default? Niektórzy chcą AEIS gotowe przy starcie systemu.
- Decyzja: faza 4 ma to ustawienie; faza 1 nie wymusza.

**TBD-2**: Crash recovery strategy?
- Co jeśli AEIS crashuje w środku Council deliberation? Resume możliwe?
- Decyzja: nie scope fazy 1, faza 4 albo dedicated incident response page.

**TBD-3**: Update policy?
- Auto-update / notify only / manual?
- Decyzja: faza 4, default Notify only.

**TBD-4**: Telemetry opt-out?
- Anonymous usage stats wysyłane do SYLION dla improvement?
- Decyzja: musi być opt-in (GDPR), check w fazie 4. W fazie 1 default OFF.

**TBD-5**: Multi-window?
- Operator może mieć 2 okna AEIS jednocześnie (np. terminal w jednym, dashboard w drugim)?
- Decyzja: tak, naturalnie wspierane przez Tauri. Workspace state synchronized via backend.

---

## 1.12. Acceptance criteria fazy 1 (DoD)

Faza 1 jest **kompletna gdy** wszystkie sekcje poniżej są ✓.

### 1.12.1. Identity zakończone

```
✓ Display name wprowadzony
   ✓ Length 1-64 znaków
   ✓ Bez invisible characters (post-cleanup)
   ✓ Bez zarezerwowanych nazw (admin, root, system, aeis)

✓ System name wprowadzony
   ✓ Regex match: ^[a-z0-9.]+$
   ✓ Length 1-32 znaków
   ✓ Unique na tej maszynie (no conflict z istniejącymi workspace)
   ✓ Operator confirmed że to nieznlienialne (audit chain dependency)

✓ Email obsłużony (jedna z opcji):
   ✓ Email wprowadzony I format valid (RFC 5322)
   ✓ Email DNS check passed (domena istnieje, MX record OK)
   ✓ ALBO operator explicit "Skip email setup"

✓ Operator role wybrany
   ✓ Solo / Team Lead / Klient — explicit choice (nie tylko default)

✓ Time zone confirmed
   ✓ Auto-detected I confirmed
   ✓ ALBO custom value selected
```

### 1.12.2. Storage skonfigurowany

```
✓ Workspace path zaakceptowany
   ✓ Default `~/.sylion/<op>/` LUB custom path
   ✓ Path is writable (test write w bootstrap)
   ✓ Path nie w blocked list (/etc/, /Windows/, etc.)
   ✓ Path nie w cloud-synced folder (warning shown, operator confirmed)

✓ Backup strategy ustanowiona
   ✓ Frequency wybrane (Daily/Weekly/Manual)
   ✓ Retention wybrane (7-365 dni lub forever)
   ✓ Backup path validated (writable, separate od workspace path)

✓ Storage health check passed
   ✓ Min 2GB wolnego miejsca (warning jeśli mniej)
   ✓ Read/write speed acceptable (>10 MB/s, warning jeśli mniej)
   ✓ SQLite test pass (create test DB, write, read, delete)
```

### 1.12.3. Security ustanowione

```
✓ Master password obsłużone (jedna z opcji):
   ✓ Password ustanowiony
      ✓ Min 12 znaków (system enforced)
      ✓ Strength meter > 50% (warning poniżej, ale allowed)
      ✓ Password verified (dual input matched)
   ✓ Recovery seed obsłużone:
      ✓ 24 słowa BIP-39 wygenerowane
      ✓ Operator verified 3 random words ze seed
      ✓ Operator confirmed "I saved this securely"
   ✓ ALBO operator świadomie pominął password
      ✓ Wpisał "ROZUMIEM" w confirmation
      ✓ System zalogował low_security_mode = true

✓ Workspace encryption initialized
   ✓ Master key generated (jeśli password ON)
   ✓ Test encrypt/decrypt pass
   ✓ First audit chain entry encrypted
```

### 1.12.4. Profile & preferences

```
✓ Język UI wybrany
   ✓ PL lub EN explicit
   ✓ Locale strings loaded
   ✓ Date/time format inherited from language choice

✓ Theme wybrane (lub Auto)
   ✓ Auto / Light / Dark
   ✓ Accent color wybrany (default Green OK)
   ✓ Density wybrane (default Standard OK)

✓ Accessibility settings
   ✓ Default accepted LUB customized
   ✓ Color blind mode OFF jako default LUB explicit selection

✓ Project goals wybrane (1-3 z 5 kategorii)
   ✓ Min 1 wybrane
   ✓ Max 3 wybrane
   ✓ ALBO explicit "Decide later" link clicked

✓ Initial autonomy preset wybrany
   ✓ Conservative / Balanced / Aggressive
   ✓ Operator widzi że może modify w fazie 5
```

### 1.12.5. Tutorial decision

```
✓ Tutorial mode wybrane
   ✓ Quick (Personal Knowledge Base)
   ✓ Standard (Lokalny CRM lub Sylion Tailor Lite)
   ✓ Full (Lokalny CRM lub Sylion Tailor Lite z deploy)
   ✓ Skip (explicit "Skip tutorial" button)

✓ Tutorial project wybrany (jeśli not skip)
   ✓ Project compatibility z tutorial depth verified
   ✓ Quick + Sylion Tailor Lite = NOT ALLOWED (forced switch lub change depth)

✓ Tutorial state initialized (jeśli not skip)
   ✓ Throwaway project utworzony w `~/.sylion/<op>/tutorial/`
   ✓ First tutorial step prepared
```

### 1.12.6. Hard gate — minimum 1 model

```
✓ Minimum 1 model dostępny (P1.20=a Block enforcement)
   ✓ Min 1 lokalny model wykryty (Ollama/LM Studio/llama.cpp)
   ✓ ALBO min 1 API key dodany w Quick add (faza 1 shortcut)
   ✓ ALBO Demo mode explicit chosen (z confirmation "I understand
        this is for learning only, not real artifacts")

✓ Model functional check pass
   ✓ Test inference: model echoes "Hello AEIS" prompt successfully
   ✓ Latency < 30s dla simple prompt
   ✓ ALBO model marked as "available but slow" w warning
```

### 1.12.7. Notifications & integrations

```
✓ Default notification channel wybrany
   ✓ In-app (always available, default)
   ✓ + opcjonalnie Email/Slack/SMS jeśli skonfigurowane
   ✓ Operator widzi że full configuration jest w fazie 4

✓ Telemetry decision
   ✓ OFF (default GDPR-compliant)
   ✓ ALBO ON z explicit consent
```

### 1.12.8. Audit & compliance

```
✓ Onboarding audit chain zapisany
   ✓ `audit_chain/onboarding.jsonl` istnieje
   ✓ Min 8 entries (1 per krok faza 1.A-1.H)
   ✓ Hash chain valid (verify_chain script pass)
   ✓ Last entry: "phase_1.complete"

✓ System ready signals
   ✓ Backend health check: 200 OK
   ✓ Frontend loads bez console errors
   ✓ Database migrations applied
   ✓ Audit chain initialized
```

### 1.12.9. Exit state ready

```
✓ Operator widzi "Faza 1 zakończona" screen
✓ "Phase 2" highlighted jako recommended next step
✓ Skip-to-Phase-16 button visible (advanced users)
✓ Help system accessible (`/help` command lub Settings → Help)
✓ Settings panel ready dla future modifications
✓ Workspace fully bootstrapped (15 sub-folders created)
```

### 1.12.10. Hard fail conditions

Faza 1 **MUSI być powtórzona** (rollback) jeśli któreś z poniższych:

```
✗ Workspace path failed write test → restart Krok 1.D z innym path
✗ Master password verification failed → restart Krok 1.E
✗ Recovery seed nie verified po 5 próbach → restart Krok 1.E
✗ Database migration failed → restart full faza 1
✗ Audit chain initialization failed → restart full faza 1 (system integrity)
✗ Hard gate "min 1 model" nie spełniony → block w Kroku 1.H
✗ Critical security update wymagany → install + restart faza 1
```

### 1.12.11. Soft warnings (continue allowed)

System pokazuje warning ale operator może continue:

```
⚠ Disk space < 5GB (sugerowane więcej)
⚠ RAM < 8GB (modele większe niż 3B nie zadziałają)
⚠ GPU brak/wrong drivers (CPU only, 10-50x wolniej)
⚠ Network offline (Faza 2 nie zadziała dla API providers)
⚠ Master password słabe (strength < 50%)
⚠ Email format suspicious (np. admin@known-company.com)
⚠ Workspace path w cloud-synced folder
⚠ Antywirus może blokować future operations
⚠ VM environment wykryte (snapshot risks)
```

### 1.12.12. Audit acceptance test

System może uruchomić **automated acceptance test** sprawdzający DoD:

```bash
$ aeis-cli phase1-acceptance-test

Running Phase 1 acceptance test...

[1/9] Identity check          ✓ PASS
[2/9] Storage check           ✓ PASS
[3/9] Security check          ✓ PASS  (master password ON, seed verified)
[4/9] Profile check           ✓ PASS
[5/9] Tutorial check          ✓ PASS  (Standard/CRM selected)
[6/9] Hard gate check         ✓ PASS  (3 local models, qwen2.5:7b functional)
[7/9] Notifications check     ✓ PASS
[8/9] Audit chain check       ✓ PASS  (8 entries, hash chain valid)
[9/9] Exit state check        ✓ PASS

DoD: 9/9 ✓
Soft warnings: 0
Phase 1 ACCEPTED. Ready to proceed to Phase 2.
```

Operator może w każdej chwili uruchomić tę komendę żeby sprawdzić czy
faza 1 nadal jest valid (np. po manual changes w settings).

---

## 1.13. Czas wykonania (kalibracja)

| Ścieżka | Czas | Komentarz |
|---|---|---|
| Skip tutorial, minimum input | 5-7 min | Power user który dokładnie wie co chce |
| Standard skip tutorial | 10-15 min | Default expected dla większości |
| With Quick tutorial | 25-35 min | Zalecane jako prawdziwe pierwsze doświadczenie |
| With Standard tutorial | 60-90 min | Pełne onboarding + nauka |
| With Full tutorial | 3-5h | Real first project |

---

## Status fazy

🟢 **Outline + adaptive Q&A complete** (~8000 słów)

⏳ Po Twojej akceptacji — **soft freeze** + przejście do **Faza 2 — Provider Catalog Configuration**.

Faza 2 będzie dłuższa (~10000-12000 słów) bo dotyczy 50+ providers, capability matrix, OpenRouter integration, lokalne modele setup, fallback chains. Estimate: 35-45 min mojej pracy.
