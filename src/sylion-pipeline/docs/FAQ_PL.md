# FAQ — SYLION v5.9.0 (Polski)

20 najczęściej zadawanych pytań.

---

## 1. Jak zmienić klucze API?

Przejdź do **Dashboard → Ustawienia → API Keys**. Klucze możesz edytować bezpośrednio w formularzu — po zapisaniu SYLION używa nowych wartości natychmiast, bez restartu. Klucze są przechowywane lokalnie w pliku `.env` i nigdy nie opuszczają Twojego komputera.

Alternatywnie edytuj plik `.env` ręcznie:

```ini
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
```

Po ręcznej edycji `.env` musisz zrestartować serwer.

---

## 2. Jak zresetować hasło administratora?

SYLION przechowuje dane logowania w bazie SQLite. Żeby zresetować hasło:

1. Zatrzymaj serwer (Ctrl+C w konsoli, gdzie działa `python -m sylion serve`).
2. Usuń bazę danych:

```bash
rm ~/sylion/sylion.db
```

3. Uruchom serwer ponownie. SYLION wyświetli nowy setup token.
4. Przejdź pod `http://localhost:8421/setup` i ustaw nowe hasło.

**Uwaga:** Usunięcie bazy danych kasuje całą historię pipeline'ów i agentów. Zrób backup, jeśli potrzebujesz zachować dane.

---

## 3. Co to są stage'e pipeline?

Stage (etap) to jeden krok w pipeline'ie audytu. Każdy stage uruchamia określony zestaw agentów i produkuje raport. Przykładowe stage'e:

- **collect** — zbieranie danych wejściowych (kod, konfiguracja)
- **analyze** — analiza statyczna i semantyczna
- **review** — ocena przez council
- **report** — generowanie raportu końcowego

Stage'e wykonują się sekwencyjnie. Możesz je konfigurować, pomijać lub dodawać własne przez panel **Pipeline** w Dashboard.

---

## 4. Jak działa human gate?

Human gate to punkt wstrzymania pipeline'u, w którym SYLION czeka na Twoją decyzję zanim przejdzie do następnego stage'u. Pojawia się automatycznie, gdy agent uzna, że wynik wymaga ludzkiej weryfikacji (np. decyzja o refaktoryzacji krytycznego modułu).

W Dashboard zobaczysz powiadomienie z pytaniem i przyciskami **"Zatwierdź"** / **"Odrzuć"** / **"Edytuj i zatwierdź"**. Pipeline wznawia działanie po Twojej decyzji.

Możesz wyłączyć human gate dla wybranych stage'ów w ustawieniach pipeline'u.

---

## 5. Czy dane są szyfrowane?

**At-rest (na dysku):** Nie. Baza danych SQLite (`~/sylion/sylion.db`) nie jest szyfrowana. SYLION działa w trybie local-dev single-user — szyfrowanie at-rest leży po Twojej stronie (np. FileVault na macOS, BitLocker na Windows, LUKS na Linuxie).

**In-transit (w sieci):** Domyślnie nie (HTTP). Jeśli uruchomisz SYLION za reverse proxy (nginx, Caddy) z certyfikatem TLS, komunikacja będzie szyfrowana (HTTPS). Instrukcję znajdziesz w dokumentacji reverse proxy w katalogu `docs/advanced/`.

Hasło użytkownika jest hashowane algorytmem Argon2id i nigdy nie jest przechowywane w postaci jawnej.

---

## 6. Co to jest council 4 modeli?

Council to mechanizm równoległego uruchamiania czterech modeli AI jednocześnie:

- **Claude Opus 4.7** (Anthropic)
- **Claude Sonnet 4.6** (Anthropic)
- **GPT-5.4** (OpenAI)
- **Gemini 3.1 Pro** (Google)

Każde zapytanie trafia do wszystkich czterech modeli równocześnie. Wyniki są zbierane i porównywane — konsensus jest podkreślany, rozbieżności są oznaczane. Dzięki temu unikasz "ślepych punktów" pojedynczego modelu.

---

## 7. Czemu rate limiter blokuje mi logowanie?

SYLION ma wbudowany rate limiter dla endpointu logowania: **5 nieudanych prób w ciągu 5 minut** powoduje blokadę IP na **10 minut**.

Jeśli widzisz błąd `429 Too Many Requests`:

1. Poczekaj 10 minut.
2. Upewnij się, że wpisujesz prawidłowe hasło.
3. Jeśli nie pamiętasz hasła — zresetuj je (patrz pytanie nr 2).

Możesz zmienić limity w pliku `.env`:

```ini
RATE_LIMIT_LOGIN_ATTEMPTS=5
RATE_LIMIT_LOGIN_WINDOW_SECONDS=300
RATE_LIMIT_LOGIN_BLOCK_SECONDS=600
```

---

## 8. Jak zrobić backup bazy danych?

**Automatyczny backup:** SYLION tworzy kopię zapasową bazy danych automatycznie przed każdą migracją schematu. Backupy trafiają do `~/sylion/backups/`.

**Ręczny backup:**

```bash
cp ~/sylion/sylion.db ~/backup/sylion_$(date +%Y%m%d_%H%M%S).db
```

Zalecane jest regularne kopiowanie pliku na zewnętrzny nośnik lub do chmury (np. iCloud Drive, jeśli używasz macOS).

**Backup w trybie WAL:** SQLite w trybie WAL wymaga, żeby przy backupie skopiować również pliki pomocnicze, jeśli serwer działa. Bezpieczniejszy backup działającego serwera:

```bash
sqlite3 ~/sylion/sylion.db ".backup ~/backup/sylion_backup.db"
```

---

## 9. Gdzie są logi?

Domyślnie SYLION wypisuje logi na standardowe wyjście (stdout) konsoli, w której uruchomiłeś serwer.

Jeśli skonfigurowałeś logowanie do pliku (w `.env`):

```ini
LOG_DIR=~/sylion/logs
LOG_LEVEL=INFO
```

Pliki logów znajdziesz w `~/sylion/logs/`. Format: jeden plik dziennie, rotacja po 30 dniach.

Poziomy logów: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Na co dzień `INFO` wystarczy.

---

## 10. Jak dodać własnego agenta?

Własny agent to plik Python umieszczony w katalogu `sylion/agents/custom/`. Musi implementować interfejs `BaseAgent`:

```python
from sylion.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "my_agent"
    description = "Co robi ten agent"

    async def run(self, context):
        # Twoja logika
        return {"result": "..."}
```

Po dodaniu pliku zrestartuj serwer. Nowy agent pojawi się na liście w zakładce **Agenci**.

---

## 11. Jak zmienić port z 8421 na inny?

W pliku `.env` ustaw:

```ini
PORT=9000
```

Następnie zrestartuj serwer. Pamiętaj, żeby zaktualizować adresy URL w zakładkach przeglądarki.

---

## 12. Czy SYLION działa offline?

Częściowo. Sama aplikacja (serwer FastAPI, baza SQLite, interfejs webowy) działa offline. Jednak council wymaga połączenia z internetem, żeby wysłać zapytania do Anthropic, OpenAI i Google. Bez internetu council nie odpowie.

Jeśli potrzebujesz trybu w pełni offline, możesz skonfigurować lokalne modele (Ollama lub llama.cpp) jako zamienniki — instrukcja w `docs/advanced/LOCAL_MODELS.md`.

---

## 13. Jak zaktualizować SYLION do nowszej wersji?

```bash
git pull origin main
./install.sh   # lub install.bat na Windows
python -m sylion migrate
python -m sylion serve
```

Komenda `migrate` zaktualizuje schemat bazy danych i automatycznie stworzy backup przed zmianami.

---

## 14. Ile agentów działa równocześnie?

Domyślnie SYLION uruchamia do **8 agentów równolegle** (8 wątków). Możesz to zmienić w `.env`:

```ini
AGENT_CONCURRENCY=8
```

Wartość wyższa niż liczba rdzeni CPU zazwyczaj nie przynosi korzyści i może spowalniać system.

---

## 15. Co zrobić, gdy pipeline utknął w stanie "running"?

1. Sprawdź logi w konsoli lub `~/sylion/logs/` — poszukaj błędów.
2. Spróbuj anulować pipeline przez przycisk **"Anuluj"** w Dashboard → Pipeline.
3. Jeśli anulowanie nie działa, zrestartuj serwer (Ctrl+C, potem `python -m sylion serve`).
4. Niedokończone pipeline'y otrzymują status `failed` po restarcie.

---

## 16. Jak wyeksportować raport audytu?

W Dashboard → Pipeline kliknij na zakończony pipeline, a następnie wybierz **"Eksportuj raport"**. Dostępne formaty:

- JSON (pełne dane)
- Markdown (czytelny tekst)
- HTML (z formatowaniem)

Raport trafia do katalogu `~/sylion/reports/` lub możesz go pobrać bezpośrednio przez przeglądarkę.

---

## 17. Czy mogę uruchomić kilka instancji SYLION?

Nie zalecane. SQLite nie jest przeznaczone do obsługi wielu równoczesnych pisarzy z różnych procesów. Tryb WAL poprawia sytuację, ale przy wielu instancjach możesz napotkać błędy blokowania bazy.

Jeśli potrzebujesz wielu instancji, rozważ migrację do PostgreSQL (patrz `docs/advanced/POSTGRES_MIGRATION.md`).

---

## 18. Jak wyłączyć council i używać tylko jednego modelu?

W `.env` ustaw:

```ini
COUNCIL_ENABLED=false
COUNCIL_DEFAULT_MODEL=claude-opus-4.7
```

Wszystkie zapytania trafią wyłącznie do wybranego modelu. Możesz też to zmienić tymczasowo w Dashboard → Ustawienia → Council.

---

## 19. Skąd wiem, że serwer działa poprawnie?

SYLION udostępnia endpoint health check:

```bash
curl http://localhost:8421/health
```

Odpowiedź:

```json
{
  "status": "ok",
  "version": "5.9.0",
  "build": "2026-04-19",
  "db": "connected",
  "agents": 48
}
```

Jeśli `status` to cokolwiek innego niż `"ok"`, sprawdź logi.

---

## 20. Jak skontaktować się z pomocą techniczną?

SYLION jest projektem single-user do prywatnego użytku. W razie problemów:

1. Sprawdź [TROUBLESHOOTING_PL.md](TROUBLESHOOTING_PL.md).
2. Przejrzyj logi (`~/sylion/logs/` lub stdout).
3. Zajrzyj do repozytorium — sekcja Issues na GitHubie.
4. Kontakt bezpośredni: robert.skorupka@icloud.com

<!-- v5.9.1 FAQ additions -->
# FAQ — SYLION v5.9.1 (Polski) — Uzupełnienia

Niniejszy plik zawiera **7 dodatkowych pytań FAQ** (numery 21–27) uzupełniających
`FAQ_PL.md` (dotychczasowe pytania 1–20). Wszystkie wpisy dotyczą luk zidentyfikowanych
w raporcie `audit_LATEST/18_user_manual.md` dla wersji v5.9.1.

Docelowo te pytania należy dołączyć do `FAQ_PL.md` po pytaniu nr 20.

---

## 21. Dlaczego nie mogę się zalogować na HTTP? [Secure cookie]

**Pytanie:** Po uruchomieniu SYLION bez HTTPS otwiera się strona logowania, wpisuję prawidłowe
hasło, ale po kliknięciu „Zaloguj" strona odświeża się i nadal prosi o dane. Dashboard
nie otwiera się.

**Przyczyna:** Od wersji v5.9.1 flaga cookie sesji `Secure` jest **domyślnie włączona**
(zmiana w ramach naprawy F-015). Przeglądarka odrzuca cookie `Secure` przesyłane przez
niezaszyfrowane połączenie HTTP — sesja nie jest zapisywana i każde żądanie traktowane
jest jako niezalogowane.

**Rozwiązania (wybierz jedno):**

### Opcja A — Uruchom SYLION za reverse proxy z TLS (zalecane na produkcji)

Skonfiguruj Caddy lub nginx z certyfikatem TLS. Przykładowy Caddyfile:

```
sylion.example.com {
    reverse_proxy 127.0.0.1:8421
}
```

Caddy automatycznie uzyska certyfikat Let's Encrypt. Szczegółowy poradnik:
`docs/RUNBOOK_DEPLOY.md §3.5`.

### Opcja B — Wyłącz flagę Secure (tylko do lokalnych testów)

Dodaj do pliku `.env`:

```ini
SESSION_COOKIE_SECURE=0
```

Następnie zrestartuj serwer. **Uwaga:** tej opcji nie stosuj na serwerze dostępnym
z sieci zewnętrznej — sesja będzie podatna na przechwycenie.

**Weryfikacja:**

```bash
curl -c /tmp/cookies.txt -b /tmp/cookies.txt \
     -X POST http://localhost:8421/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"TwojeHaslo"}'
```

Jeśli odpowiedź zawiera `{"status":"ok"}` — logowanie działa.
Jeśli odpowiedź to `{"status":"error","message":"Unauthorized"}` przy poprawnym haśle —
sprawdź wartość `SESSION_COOKIE_SECURE` w `.env`.

---

## 22. Jak zrotować klucz API przez dashboard?

**Pytanie:** Jeden z moich kluczy API (OpenAI / Anthropic / Google) wygasł lub został
unieważniony. Jak zaktualizować go bez restartu serwera?

**Odpowiedź:**

1. Otwórz **Dashboard → Ustawienia → API Keys** (lub `http://localhost:8421/settings/api-keys`).
2. Znajdź wiersz odpowiadający kluczowi do zmiany (np. `OPENAI_API_KEY`).
3. Kliknij ikonę **ołówka** (edytuj) przy danym kluczu.
4. Wklej nową wartość klucza — pole jest maskowane gwiazdkami dla bezpieczeństwa.
5. Kliknij **Zapisz**. SYLION zastosuje nowy klucz natychmiast, bez restartu serwera.

**Alternatywna metoda przez plik `.env`:**

```bash
# Zatrzymaj serwer
kill $(lsof -t -i :8421)

# Edytuj .env — zmień odpowiedni klucz
nano .env
# np. OPENAI_API_KEY=sk-proj-NowyKlucz...

# Uruchom serwer
python dashboard/start.py
```

**Weryfikacja klucza po zmianie:**

Przejdź do **Dashboard → Council** i kliknij „Testuj połączenie" przy modelu,
którego klucz zmieniałeś. Zielony znacznik potwierdza poprawność.

**Uwaga dotycząca bezpieczeństwa (F-001):** Wersja v5.9.1 nadal zawiera hardcodowane
klucze w `dashboard/db.py:1081-1086` (naprawiane w v5.9.2). Przed każdym deployem
uruchom:

```bash
grep -n "sk-" dashboard/db.py
```

Jeśli wynik nie jest pusty — zrotuj klucze i usuń literały z kodu.

---

## 23. Jak przywrócić poprzednią wersję po nieudanym update? [rollback.sh]

**Pytanie:** Zainstalowałem nową wersję SYLION, ale coś poszło nie tak (błędy w logach,
dashboard nie odpowiada). Jak cofnąć się do poprzedniej wersji?

**Odpowiedź:**

SYLION v5.9.1 zawiera przepisany `rollback.sh` (naprawa F-004/F-005/F-006) z obsługą
WAL i weryfikacją integralności przed podmianą bazy.

**Krok 1 — Podgląd (dry run):**

```bash
./rollback.sh --dry-run
```

Wypisuje, co zostałoby przywrócone, nie dotykając żadnego pliku.

**Krok 2 — Wykonanie rollbacku:**

```bash
# Zatrzymaj serwer
sudo systemctl stop sylion
# lub: kill $(lsof -t -i :8421)

# Przywróć ostatni działający backup bazy
./rollback.sh

# Uruchom serwer
sudo systemctl start sylion
```

Skrypt przeszukuje backupy w kolejności:
1. `$HOME/sylion/backups/` (domyślna lokalizacja `install.sh`)
2. `./backups/`
3. `/var/backups/sylion/`

**Kody wyjścia `rollback.sh`:**

| Kod | Znaczenie |
|-----|-----------|
| `0` | Sukces — baza przywrócona |
| `1` | Brak backupu do przywrócenia |
| `2` | Backup uszkodzony (`PRAGMA integrity_check` failed) |
| `3` | Brak uprawnień lub wolnego miejsca na dysku |

**Jeśli rollback bazy nie wystarczy** (np. też pliki kodu są uszkodzone):

```bash
# Przywróć cały katalog aplikacji z kopii sprzed upgrade'u
cp -a /opt/sylion.pre-v591 /opt/sylion
sudo systemctl start sylion
```

---

## 24. Co zrobić, gdy Pixel 9 nie jest wykrywany przez SYLION?

**Pytanie:** Podłączyłem telefon Google Pixel 9 przez USB, ale SYLION nie widzi urządzenia
w panelu. Co sprawdzić?

**Odpowiedź:**

Problemy z wykrywaniem Pixel 9 dotyczą trzech warstw: systemu Linux (udev), autoryzacji
ADB oraz trybu debugowania w telefonie.

### Krok 1 — Sprawdź reguły udev (Linux)

```bash
# Sprawdź czy reguły dla Google są zainstalowane
ls /etc/udev/rules.d/ | grep -i android

# Jeśli brak — dodaj regułę dla Pixel 9 (vendor ID Google: 18d1)
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"' \
     | sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Następnie odłącz i ponownie podłącz telefon.

### Krok 2 — Autoryzuj ADB

```bash
# Sprawdź czy ADB widzi urządzenie
adb devices
```

Oczekiwany wynik: `emulator-XXXX    device` lub `SERIALNUMER    device`.

Jeśli widzisz `unauthorized`:
1. Na telefonie pojawi się okno dialogowe „Zezwolić temu komputerowi na debugowanie USB?".
2. Zaznacz „Zawsze zezwalaj z tego komputera" i kliknij OK.
3. Uruchom ponownie: `adb devices`.

### Krok 3 — Włącz tryb debugowania USB

Na telefonie:
1. **Ustawienia → O telefonie → Informacje o oprogramowaniu**.
2. Dotknij **Numer kompilacji** 7 razy — pojawi się „Jesteś programistą".
3. **Ustawienia → System → Opcje programisty**.
4. Włącz **Debugowanie USB**.

### Krok 4 — Sprawdź typ połączenia USB

Pixel 9 domyślnie ustawia tryb „Tylko ładowanie". Przesuń powiadomienie USB z góry ekranu
i wybierz **Przesyłanie plików (MTP)** lub **PTP**.

### Krok 5 — Weryfikacja w SYLION

Po pomyślnej autoryzacji ADB:
1. Przejdź do **Dashboard → Urządzenia**.
2. Kliknij **Odśwież**. Pixel 9 powinien pojawić się na liście.

Jeśli nadal brak urządzenia — sprawdź logi: `cat ~/sylion/logs/device_manager.log`.

---

## 25. Mudi wymaga WireGuard — jak zainstalować na routerze GL.iNet Mudi?

**Pytanie:** SYLION z modułem SDR wymaga połączenia VPN przez WireGuard na routerze GL.iNet
Mudi (GL-E750). Jak zainstalować WireGuard na tym urządzeniu?

**Odpowiedź:**

GL.iNet Mudi działa na OpenWrt. Poniżej instalacja i konfiguracja WireGuard:

### Instalacja modułu jądra WireGuard

```bash
# Zaloguj się do routera przez SSH
ssh root@192.168.8.1

# Zaktualizuj indeks pakietów
opkg update

# Zainstaluj WireGuard (moduł jądra + narzędzia)
opkg install kmod-wireguard wireguard-tools

# Sprawdź czy moduł załadował się poprawnie
lsmod | grep wireguard
```

### Generowanie kluczy

```bash
# Na routerze
wg genkey | tee /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key
chmod 600 /etc/wireguard/private.key

cat /etc/wireguard/public.key   # Skopiuj klucz publiczny do konfiguracji serwera VPN
```

### Konfiguracja interfejsu WireGuard

Utwórz plik `/etc/config/network` (sekcja dla wg0):

```
config interface 'wg0'
    option proto 'wireguard'
    option private_key 'TWOJ_KLUCZ_PRYWATNY'
    option listen_port '51820'
    list addresses '10.0.0.2/24'

config wireguard_wg0
    option public_key 'KLUCZ_PUBLICZNY_SERWERA'
    option endpoint_host 'vpn.example.com'
    option endpoint_port '51820'
    list allowed_ips '0.0.0.0/0'
    option persistent_keepalive '25'
```

### Uruchomienie

```bash
ifup wg0
# Sprawdź status
wg show
```

### Integracja z SYLION

Po uruchomieniu WireGuard skonfiguruj SYLION, żeby trasa SDR przechodziła przez interfejs `wg0`:

```ini
# .env
SDR_VPN_INTERFACE=wg0
SDR_VPN_GATEWAY=10.0.0.1
```

Więcej szczegółów: `sylion-pipeline/device/WIREGUARD_TODO.md` i
`sylion-pipeline/sdr/FARADAY_CAGE.md`.

---

## 26. Jak przeprowadzić migrację z v5.8 do v5.9.1?

**Pytanie:** Używam SYLION v5.8.x. Jak bezpiecznie przejść bezpośrednio na v5.9.1?

**Odpowiedź:**

Migracja z v5.8.x do v5.9.1 obejmuje trzy kroki migracji schematu bazy danych (1→2→3),
które wykonywane są automatycznie. Poniżej pełna procedura:

### Wymagania wstępne

- Python **3.11 lub nowszy** (zalecane 3.12)
- Wolne miejsce: min. 500 MB (backup bazy + nowe zależności)
- Dostęp do kluczy API (zostaną zweryfikowane po migracji)

### Krok 1 — Backup przed migracją

```bash
# Backup bazy danych (krytyczne!)
sqlite3 ~/sylion/sylion.db \
  ".backup '~/sylion/backups/sylion-pre-v591-$(date +%Y%m%d-%H%M%S).db.bak'"

# Backup całego katalogu aplikacji
cp -a ~/sylion ~/sylion.bak-v58
```

### Krok 2 — Zatrzymaj serwer v5.8

```bash
sudo systemctl stop sylion
# lub: kill $(lsof -t -i :8421)
```

### Krok 3 — Rozpakuj i zainstaluj v5.9.1

```bash
cd ~/
unzip SYLION_v591.zip -d /tmp/sylion-v591
rsync -a --delete /tmp/sylion-v591/sylion-pipeline/ ~/sylion/sylion-pipeline/

cd ~/sylion/sylion-pipeline
source .venv/bin/activate  # lub: python -m venv .venv && source .venv/bin/activate
pip install -r requirements-lock.txt --upgrade
```

### Krok 4 — Migracja schematu (automatyczna)

```bash
# Migracja DB wykonuje się automatycznie przy pierwszym starcie.
# Sprawdź wersję przed i po:
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Oczekiwane: 2 (v5.9.1 docelowy user_version)
```

### Krok 5 — Rotacja kluczy API (obowiązkowe!)

Patrz pytanie nr 22 (F-001 — hardcoded klucze w `dashboard/db.py`). Wykonaj rotację
przed uruchomieniem.

### Krok 6 — Uruchom i zweryfikuj

```bash
python dashboard/start.py

# W innym terminalu:
curl http://localhost:8421/api/health
# Oczekiwane: {"status":"ok","version":"5.9.1",...}
```

Pełny przewodnik migracji: `docs/MIGRATION_GUIDE.md`.

---

## 27. Ile miesięcznie kosztują API? Jak działa tier routing?

**Pytanie:** Używam council z 19 modelami. Jak szacować miesięczne koszty? Czym jest
„tier routing"?

**Odpowiedź:**

### Modele w SYLION v5.9.1 (19 modeli)

Council korzysta domyślnie z 4 modeli równolegle:

| Model | Dostawca | Cena (przybliżona, USD) |
|-------|----------|------------------------|
| Claude Opus 4.7 | Anthropic | ~$15 / 1M tokenów wejścia, ~$75 / 1M wyjścia |
| Claude Sonnet 4.6 | Anthropic | ~$3 / 1M wejścia, ~$15 / 1M wyjścia |
| GPT-5.4 | OpenAI | ~$10 / 1M wejścia, ~$30 / 1M wyjścia |
| Gemini 3.1 Pro | Google | ~$3.5 / 1M wejścia, ~$10.5 / 1M wyjścia |

*(Ceny orientacyjne — zawsze sprawdź aktualne cenniki na stronach dostawców.)*

### Tier routing

Tier routing to mechanizm SYLION, który automatycznie kieruje zapytania do modelu
o odpowiedniej mocy i koszcie:

- **Tier 1 (tani, szybki):** Sonnet 4.6, Gemini 3.1 Pro — stosowany dla prostych
  zadań (np. formatowanie, streszczenia).
- **Tier 2 (drogi, dokładny):** Opus 4.7, GPT-5.4 — stosowany dla złożonych analiz
  (code review, security audit).

Konfiguracja w `.env`:

```ini
COUNCIL_TIER_ROUTING=true
COUNCIL_TIER1_MODELS=claude-sonnet-4.6,gemini-3.1-pro
COUNCIL_TIER2_MODELS=claude-opus-4.7,gpt-5.4
```

### Szacowanie miesięcznych kosztów

Przyjmując typowe użycie (10 pipeline'ów dziennie, ~50k tokenów na pipeline):

- Bez tier routingu: ~**$200–400/miesiąc** (wszystkie 4 modele dla każdego zapytania)
- Z tier routingiem: ~**$60–120/miesiąc** (Tier 2 tylko dla złożonych zadań)

**Monitorowanie kosztów:**

Przejdź do **Dashboard → FinOps → Zużycie API** — zobaczysz dzienny i miesięczny
koszt per model.

Możesz też ustawić limit:

```ini
COUNCIL_MONTHLY_BUDGET_USD=100
COUNCIL_BUDGET_ACTION=warn  # lub: pause (zatrzymuje council po przekroczeniu)
```

---

*Uzupełnienia do FAQ_PL.md dla SYLION v5.9.1 — 2026-04-19*
*Luki zidentyfikowane w: audit_LATEST/18_user_manual.md*
