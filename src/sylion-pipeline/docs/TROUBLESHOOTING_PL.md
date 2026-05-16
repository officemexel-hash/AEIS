# Troubleshooting — SYLION v5.9.0 (Polski)

15 najczęstszych problemów i ich rozwiązania.

---

## Problem 1: Port 8421 jest już zajęty

**Objaw:**

```
OSError: [Errno 98] Address already in use: ('0.0.0.0', 8421)
```

**Rozwiązanie:**

Znajdź proces używający portu i zakończ go:

```bash
# Linux / macOS
lsof -i :8421
# Wynik: kolumna PID zawiera numer procesu
kill -9 <PID>

# Windows
netstat -ano | findstr :8421
taskkill /PID <PID> /F
```

Alternatywnie zmień port w `.env`:

```ini
PORT=9000
```

I uruchom serwer ponownie.

---

## Problem 2: Logowanie zwraca błąd 429

**Objaw:** Strona logowania wyświetla komunikat `429 Too Many Requests` lub `Rate limit exceeded`.

**Przyczyna:** Rate limiter wykrył 5 lub więcej nieudanych prób logowania w ciągu 5 minut.

**Rozwiązanie:**

1. Poczekaj **10 minut** od ostatniej próby.
2. Upewnij się, że wpisujesz prawidłowe hasło (sprawdź CapsLock).
3. Jeśli nie pamiętasz hasła, po odczekaniu zresetuj je (patrz FAQ, pytanie nr 2).

Jeśli chcesz natychmiast odblokować IP (np. podczas testów):

```bash
# Usuń plik z listą zablokowanych IP (jeśli przechowywany osobno)
rm ~/sylion/rate_limit_state.json
# Następnie zrestartuj serwer
```

---

## Problem 3: Migracja bazy danych nie powiodła się

**Objaw:**

```
MigrationError: Migration to version X.X.X failed
```

**Rozwiązanie:**

1. Nie uruchamiaj serwera ponownie bez sprawdzenia stanu bazy.
2. Przywróć backup (tworzony automatycznie przed każdą migracją):

```bash
ls ~/sylion/backups/
cp ~/sylion/backups/sylion_pre_migration_XXXXXX.db ~/sylion/sylion.db
```

3. Sprawdź logi, żeby zrozumieć przyczynę błędu.
4. Jeśli problem się powtarza, zapoznaj się z `docs/ROLLBACK_PLAN.md`.

---

## Problem 4: Brak modułu argon2

**Objaw:**

```
ModuleNotFoundError: No module named 'argon2'
```

**Rozwiązanie:**

```bash
pip install argon2-cffi
```

Jeśli używasz wirtualnego środowiska, upewnij się, że jest aktywne:

```bash
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install argon2-cffi
```

---

## Problem 5: SQLite — baza danych zablokowana

**Objaw:**

```
sqlite3.OperationalError: database is locked
```

**Przyczyny i rozwiązania:**

1. **Inna instancja SYLION jest uruchomiona.** Sprawdź i zakończ wszystkie procesy:

```bash
ps aux | grep sylion   # Linux/macOS
tasklist | findstr sylion   # Windows
```

2. **Inny program (np. DB Browser for SQLite) ma otwartą bazę.** Zamknij go.

3. **Plik WAL nie został poprawnie zamknięty.** Wymuś checkpoint:

```bash
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
```

4. Jeśli problem się powtarza, sprawdź uprawnienia do pliku:

```bash
ls -la ~/sylion/sylion.db
chmod 600 ~/sylion/sylion.db
```

---

## Problem 6: Klucz API odrzucony (błąd 401 przy council)

**Objaw:** Council zwraca błąd `401 Unauthorized` lub `Invalid API key`.

**Rozwiązanie:**

1. Przejdź do **Dashboard → Ustawienia → API Keys**.
2. Sprawdź, czy klucz jest poprawnie skopiowany (bez spacji na początku/końcu).
3. Zweryfikuj klucz bezpośrednio na stronie dostawcy (Anthropic Console, OpenAI Platform, Google AI Studio).
4. Jeśli klucz wygasł lub został unieważniony — wygeneruj nowy.

---

## Problem 7: Strona nie ładuje się (SYLION nie odpowiada na http://localhost:8421)

**Możliwe przyczyny:**

1. Serwer nie jest uruchomiony — sprawdź konsolę, uruchom `python -m sylion serve`.
2. Używasz złego portu — sprawdź wartość `PORT` w `.env`.
3. Firewall blokuje port — dodaj wyjątek:

```bash
# Linux (UFW)
sudo ufw allow 8421/tcp

# macOS — sprawdź System Preferences → Security → Firewall
```

4. Przeglądarka używa cache'owanego błędu — spróbuj otworzyć w trybie prywatnym.

---

## Problem 8: Agent zwraca pusty wynik lub None

**Objaw:** Pipeline kończy się poprawnie, ale raport wybranego agenta jest pusty.

**Możliwe przyczyny:**

1. Agent nie obsługuje danego typu danych wejściowych.
2. Model AI zwrócił pustą odpowiedź (np. zbyt długi kontekst).
3. Błąd w logice agenta.

**Rozwiązanie:**

1. Sprawdź logi agenta w konsoli — poszukaj linii `[WARN]` lub `[ERROR]`.
2. Zmniejsz rozmiar danych wejściowych (np. podziel duży plik na mniejsze fragmenty).
3. Jeśli to własny agent — sprawdź implementację metody `run()`.

---

## Problem 9: Instalacja nie powiodła się — błąd pip

**Objaw:**

```
ERROR: Could not install packages due to an OSError
```

**Rozwiązanie:**

```bash
# Zaktualizuj pip
python -m pip install --upgrade pip

# Spróbuj instalacji z użyciem --user
pip install --user -r requirements.txt

# Na Linuxie możliwy brak uprawnień do katalogu:
chmod -R 755 venv/
```

---

## Problem 10: Council działa bardzo wolno

**Objaw:** Odpowiedź council zajmuje ponad 60 sekund.

**Możliwe przyczyny:**

1. Sieć jest powolna lub obciążona.
2. Modele API mają aktualnie duże opóźnienia (sprawdź statusy: status.anthropic.com, status.openai.com).
3. Dane wejściowe są bardzo duże (>10 000 tokenów).

**Rozwiązanie:**

1. Sprawdź statusy dostawców API.
2. Zmniejsz rozmiar kontekstu.
3. Tymczasowo wyłącz wolniejsze modele w **Dashboard → Ustawienia → Council**.
4. Zwiększ timeout w `.env`:

```ini
COUNCIL_TIMEOUT_SECONDS=120
```

---

## Problem 11: Brak miejsca na dysku

**Objaw:**

```
OSError: [Errno 28] No space left on device
```

**Rozwiązanie:**

1. Sprawdź użycie dysku:

```bash
df -h ~
du -sh ~/sylion/
```

2. Stare logi i backupy mogą zajmować dużo miejsca:

```bash
# Usuń logi starsze niż 30 dni
find ~/sylion/logs/ -name "*.log" -mtime +30 -delete

# Usuń stare backupy (zostaw kilka ostatnich)
ls -t ~/sylion/backups/ | tail -n +6 | xargs -I{} rm ~/sylion/backups/{}
```

---

## Problem 12: Błąd importu — nieprawidłowa wersja Pythona

**Objaw:**

```
SyntaxError: f-strings with = are only available in Python 3.8+
# lub
ImportError: cannot import name 'TypeAlias' from 'typing'
```

**Rozwiązanie:** SYLION wymaga Pythona **3.12 lub nowszego**.

```bash
python --version   # musi wykazać 3.12.x lub nowszy
```

Jeśli masz starszą wersję, zainstaluj Python 3.12 z python.org lub przez menedżer pakietów:

```bash
# Ubuntu / Debian
sudo apt install python3.12

# macOS (Homebrew)
brew install python@3.12

# Windows — pobierz instalator z python.org
```

---

## Problem 13: Human gate nie wyświetla się

**Objaw:** Pipeline przechodzi przez stage z human gate bez zatrzymywania się.

**Możliwe przyczyny:**

1. Human gate jest wyłączony dla tego stage'u w konfiguracji pipeline'u.
2. Agent uznał, że weryfikacja nie jest wymagana.

**Rozwiązanie:**

1. Sprawdź konfigurację pipeline'u — w Dashboard → Pipeline → edytuj wybrany stage i włącz opcję `require_human_gate: true`.
2. Jeśli human gate jest włączony, ale nie wyświetla powiadomienia — sprawdź logi i upewnij się, że przeglądarka jest aktywna (powiadomienia działają przez WebSocket).

---

## Problem 14: Dane wyjściowe zawierają znaki zastępcze (?)

**Objaw:** W raporcie lub odpowiedzi agenta zamiast polskich liter pojawiają się znaki zapytania lub prostokąty.

**Przyczyna:** Problem z kodowaniem znaków.

**Rozwiązanie:**

Sprawdź ustawienia locale w systemie:

```bash
# Linux
locale
# Ustaw UTF-8 jeśli brak:
export LANG=pl_PL.UTF-8
export LC_ALL=pl_PL.UTF-8
```

W `.env` dodaj:

```ini
PYTHONIOENCODING=utf-8
```

---

## Problem 15: Błąd "Permission denied" przy uruchamianiu install.sh

**Objaw:**

```
bash: ./install.sh: Permission denied
```

**Rozwiązanie:**

```bash
chmod +x install.sh
./install.sh
```

Na Windows odpowiednik: kliknij prawym przyciskiem `install.bat` → "Uruchom jako administrator" (jeśli wymagane przez środowisko).

---

## Nie znalazłeś swojego problemu?

Sprawdź [FAQ_PL.md](FAQ_PL.md) lub przejrzyj logi serwera. Kontakt: robert.skorupka@icloud.com

<!-- v5.9.1 TROUBLESHOOTING additions -->
# Troubleshooting — SYLION v5.9.1 (Polski) — Uzupełnienia

Niniejszy plik zawiera **5 dodatkowych scenariuszy Troubleshooting** (numery 16–20)
uzupełniających `TROUBLESHOOTING_PL.md` (dotychczasowe problemy 1–15).
Wszystkie scenariusze są specyficzne dla wersji v5.9.1.

Docelowo wpisy te należy dołączyć do `TROUBLESHOOTING_PL.md` po problemie nr 15.

---

## Problem 16: 500 Internal Server Error przy pierwszym żądaniu /api/auth/login

**Objaw:**

```
HTTP/1.1 500 Internal Server Error
{"detail":"Internal server error"}
```

Błąd pojawia się tylko przy pierwszym uruchomieniu lub po usunięciu pliku bazy danych.
Logi serwera zawierają wpis podobny do:

```
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  ...
  sqlite3.OperationalError: no such table: users
```

**Przyczyna:** Race condition przy inicjalizacji bazy danych — `init_db()` jest wywoływane
asynchronicznie i może nie zakończyć się przed przyjęciem pierwszego żądania HTTP.
Tabela `users` nie istnieje jeszcze w momencie obsługi żądania logowania.

Dotyczy instalacji, w których:
- Baza danych `~/sylion/sylion.db` nie istnieje (nowa instalacja).
- Plik bazy był ręcznie usunięty w celu resetu.
- Aplikacja startuje z ustawionym `DB_PATH` wskazującym na nieistniejący plik.

**Rozwiązanie:**

### Krok 1 — Zainicjuj bazę danych ręcznie przed uruchomieniem serwera

```bash
cd ~/sylion/sylion-pipeline
source .venv/bin/activate

python - <<'EOF'
import sys
sys.path.insert(0, 'dashboard')
from db import init_db
init_db()
print("Baza danych zainicjowana pomyślnie.")
EOF
```

### Krok 2 — Sprawdź plik bazy

```bash
sqlite3 ~/sylion/sylion.db ".tables"
# Oczekiwane tabele: users, sessions, pipelines, audit_log, ...
```

Jeśli tabele są widoczne — uruchom serwer:

```bash
python dashboard/start.py
```

### Krok 3 — Weryfikacja

```bash
curl -s http://localhost:8421/api/health
# Oczekiwane: {"status":"ok","version":"5.9.1","db":"connected",...}
```

**Długoterminowe obejście:** Problem jest naprawiany w v5.9.2 przez synchroniczną
inicjalizację `init_db()` w startup hook FastAPI. Do tego czasu zawsze uruchom
ręczne `init_db()` po usunięciu bazy.

---

## Problem 17: 403 Forbidden po deployu za reverse proxy (nginx / Caddy)

**Objaw:**

```
HTTP/1.1 403 Forbidden
{"detail":"Forbidden: IP not in trusted proxy list"}
```

Błąd pojawia się po uruchomieniu SYLION za nginx lub Caddy. Dashboard nie jest
dostępny — każde żądanie kończy się 403.

Logi SYLION zawierają:

```
WARNING: Request from untrusted proxy 203.0.113.45 — rejected
```

**Przyczyna:** Od v5.9.1 SYLION wymaga `proxy_headers=True` i sprawdza, czy adres
proxy jest na liście `SYLION_FORWARDED_ALLOW_IPS`. Domyślna wartość to `127.0.0.1`
(tylko lokalny proxy). Zewnętrzny IP nginx/Caddy lub loadbalancera nie jest uwzględniony.

**Rozwiązanie:**

### Krok 1 — Dodaj IP proxy do zmiennej środowiskowej

W pliku `.env`:

```ini
# Pojedynczy proxy na tej samej maszynie:
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1

# Proxy na innym hoście (np. loadbalancer na 10.0.0.5):
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1,10.0.0.5

# Cloudflare lub CDN (zakres CIDR):
SYLION_FORWARDED_ALLOW_IPS=127.0.0.1,103.21.244.0/22,103.22.200.0/22
```

### Krok 2 — Sprawdź konfigurację reverse proxy

**Caddy** (zalecany) — Caddyfile musi wstrzykiwać nagłówki:

```
sylion.example.com {
    reverse_proxy 127.0.0.1:8421 {
        header_up X-Forwarded-For {remote_host}
        header_up X-Real-IP {remote_host}
    }
}
```

**nginx** — sprawdź sekcję `location`:

```nginx
location / {
    proxy_pass http://127.0.0.1:8421;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
}
```

### Krok 3 — Zrestartuj serwer SYLION

```bash
sudo systemctl restart sylion
```

### Krok 4 — Weryfikacja rate limitera (test z F-002)

```bash
# Wyślij 6 prób logowania z błędnym hasłem
for i in {1..6}; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://sylion.example.com/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"zlehaklo"}')
  echo "Próba $i: HTTP $CODE"
done
# Oczekiwane: próby 1-5 → 401, próba 6 → 429
```

Jeśli próba 6 zwraca 429 — rate limiter działa poprawnie z proxy.

---

## Problem 18: ImportError: cannot import name 'run_codebase_audit'

**Objaw:**

```
ImportError: cannot import name 'run_codebase_audit' from 'sylion.agents.auditor'
```

lub

```
AttributeError: module 'sylion.agents.auditor' has no attribute 'run_codebase_audit'
```

Błąd pojawia się przy próbie uruchomienia pipeline audytu kodu lub przy imporcie
modułu `auditor` w skryptach zewnętrznych.

**Przyczyna:** Funkcja `run_codebase_audit` istnieje w v5.9.0, ale jej sygnatura
zmieniła się w v5.9.1 i wymaga patcha z v5.9.2 do pełnego działania.
Problem dotyczy sytuacji, gdy:
- Zewnętrzny skrypt lub wtyczka importuje `run_codebase_audit` bezpośrednio.
- Masz zainstalowane stare pliki konfiguracyjne pipeline'u z v5.8.x.
- Mieszasz pliki z różnych wersji (zip v5.9.0 + pliki z v5.9.1).

**Rozwiązanie:**

### Krok 1 — Sprawdź zainstalowaną wersję

```bash
python -c "import sys; sys.path.insert(0,'dashboard'); import version; print(version.__version__)"
# lub:
curl http://localhost:8421/api/health | python -m json.tool
```

### Krok 2 — Upewnij się, że wszystkie pliki pochodzą z v5.9.1

```bash
# Sprawdź czy nie masz mieszanych wersji
grep -r "run_codebase_audit" sylion/ --include="*.py" -l
```

Wszystkie odwołania powinny wskazywać na `sylion/agents/auditor.py`.

### Krok 3 — Tymczasowe obejście (do czasu patcha v5.9.2)

Jeśli funkcja jest wywoływana z zewnętrznego skryptu, użyj zamiennika:

```python
# Zamiast:
from sylion.agents.auditor import run_codebase_audit
run_codebase_audit(path="/my/code")

# Użyj:
from sylion.agents.auditor import CodebaseAuditorAgent
agent = CodebaseAuditorAgent()
import asyncio
result = asyncio.run(agent.run({"path": "/my/code"}))
```

### Krok 4 — Jeśli używasz pipeline'ów z v5.8.x

Zaktualizuj pliki konfiguracyjne pipeline'u:

```bash
# Znajdź stare konfiguracje
grep -r "run_codebase_audit" ~/sylion/ --include="*.yaml" --include="*.json" -l

# Ręcznie zmień na nowe API lub usuń i odtwórz pipeline w Dashboard
```

**Status:** Pełny patch dostarczony będzie w v5.9.2. Śledź `docs/FIX_MAP_v5.9.1.md`
pod pozycją F-028 (planowany).

---

## Problem 19: dashboard/sylion_dashboard.db ma rozmiar 0 bajtów

**Objaw:**

```bash
ls -la ~/sylion/
# -rw-r--r-- 1 user user    0 Apr 19 10:00 sylion_dashboard.db
```

lub w logach:

```
ERROR: Database file is empty (0 bytes) — possible init_db failure
sqlite3.DatabaseError: file is not a database
```

Dashboard ładuje się, ale historia pipeline'ów, agentów i ustawień jest pusta.
Każde kolejne uruchomienie resetuje dane.

**Przyczyna:** Bug w `init_db()` — przy pewnych warunkach startowych (np. brak uprawnień
zapisu do katalogu, pełny dysk w momencie inicjalizacji, przerwany proces) plik bazy
danych jest tworzony (touch), ale nie jest poprawnie inicjalizowany schematem SQLite.
Efekt: plik 0-bajtowy zamiast poprawnej bazy.

**Rozwiązanie:**

### Krok 1 — Sprawdź uprawnienia i miejsce na dysku

```bash
# Sprawdź uprawnienia katalogu
ls -la ~/sylion/
# Katalog musi być zapisywalny przez użytkownika serwera

# Sprawdź dostępne miejsce
df -h ~
# Minimum: 100 MB wolne
```

### Krok 2 — Usuń plik 0-bajtowy i zainicjuj bazę od nowa

```bash
# Zatrzymaj serwer
kill $(lsof -t -i :8421) 2>/dev/null || true

# Usuń uszkodzony plik
rm ~/sylion/sylion_dashboard.db
rm -f ~/sylion/sylion_dashboard.db-wal ~/sylion/sylion_dashboard.db-shm

# Zainicjuj bazę ręcznie
cd ~/sylion/sylion-pipeline
source .venv/bin/activate
python - <<'EOF'
import sys
sys.path.insert(0, 'dashboard')
from db import init_db
init_db()
print("init_db() zakończone sukcesem.")
EOF

# Sprawdź rozmiar
ls -lh ~/sylion/sylion_dashboard.db
# Oczekiwane: kilkanaście KB (nie 0 bajtów)
```

### Krok 3 — Przywróć dane z backupu (jeśli dostępny)

```bash
# Lista dostępnych backupów
ls -lt ~/sylion/backups/ | head -5

# Przywróć ostatni backup
cp ~/sylion/backups/sylion_pre_migration_XXXXXX.db ~/sylion/sylion_dashboard.db
sqlite3 ~/sylion/sylion_dashboard.db "PRAGMA integrity_check;"
# Oczekiwane: ok
```

### Krok 4 — Uruchom serwer i zweryfikuj

```bash
python dashboard/start.py &
sleep 3
curl http://localhost:8421/api/health
# Oczekiwane: {"status":"ok","db":"connected",...}
```

**Zapobieganie w przyszłości:** Dodaj do crontab automatyczny backup:

```bash
# Codziennie o 02:00
0 2 * * * sqlite3 ~/sylion/sylion_dashboard.db ".backup '~/sylion/backups/sylion_$(date +\%Y\%m\%d).db.bak'" 2>/dev/null
```

---

## Problem 20: fstat: No such file or directory SETUP_TOKEN.txt

**Objaw:**

```
[SYLION] ERROR: Cannot read SETUP_TOKEN.txt: [Errno 2] No such file or directory: 'SETUP_TOKEN.txt'
```

lub serwer uruchamia się, ale strona `/setup` wyświetla:

```
Setup token not found. Please check server logs or restart the server.
```

Błąd pojawia się przy pierwszej instalacji lub po resecie bazy danych.

**Przyczyna:** Przy pierwszym uruchomieniu SYLION generuje SETUP_TOKEN i zapisuje go
do pliku `SETUP_TOKEN.txt` w katalogu roboczym (bieżący katalog przy uruchomieniu `python dashboard/start.py`).
Jeśli serwer jest uruchomiony z innego katalogu niż `sylion-pipeline/`, plik jest tworzony
w złej lokalizacji — i nie może być odczytany przy kolejnym żądaniu.

**Rozwiązanie:**

### Krok 1 — Uruchom serwer z właściwego katalogu

```bash
# ZAWSZE uruchamiaj z katalogu sylion-pipeline/
cd ~/sylion/sylion-pipeline   # lub /opt/sylion/sylion-pipeline
python dashboard/start.py
```

### Krok 2 — Znajdź wygenerowany token

```bash
# Szukaj pliku SETUP_TOKEN.txt w możliwych lokalizacjach
find ~ -name "SETUP_TOKEN.txt" 2>/dev/null
find /opt -name "SETUP_TOKEN.txt" 2>/dev/null
find /tmp -name "SETUP_TOKEN.txt" 2>/dev/null
```

Jeśli plik istnieje — odczytaj token:

```bash
cat /ścieżka/do/SETUP_TOKEN.txt
```

### Krok 3 — Odczytaj token z logów serwera

Token jest zawsze wypisywany w logach przy starcie:

```bash
# Jeśli logowanie do pliku jest włączone
grep "Setup token" ~/sylion/logs/*.log

# Lub bezpośrednio w stdout konsoli uruchamiającej serwer
# Szukaj linii: [SYLION] Setup token: XXXX-XXXX-XXXX-XXXX
```

### Krok 4 — Wygeneruj token ponownie (jeśli nie można go odczytać)

```bash
# Zatrzymaj serwer
kill $(lsof -t -i :8421) 2>/dev/null || true

# Usuń stary token i bazę (lub tylko token jeśli dane są ważne)
rm -f ~/sylion/sylion-pipeline/SETUP_TOKEN.txt

# Przy następnym starcie token zostanie wygenerowany od nowa
cd ~/sylion/sylion-pipeline
python dashboard/start.py
# Skopiuj token z wypisanej linii: [SYLION] Setup token: ...
```

### Krok 5 — Dokończ setup

Otwórz `http://localhost:8421/setup` w przeglądarce, wklej token i ustaw hasło administratora.

**Uwaga:** Token jest jednorazowy — po pomyślnym ustawieniu hasła plik `SETUP_TOKEN.txt`
jest usuwany automatycznie. Jeśli strona `/setup` mówi „already configured" — hasło
zostało już ustawione. Użyj endpointu `/login` lub zresetuj hasło zgodnie z FAQ, pytanie nr 2.

---

## Nie znalazłeś swojego problemu?

Sprawdź [FAQ_PL.md](FAQ_PL.md), [FAQ_PL_v591_additions.md](FAQ_PL_v591_additions.md)
lub przejrzyj logi serwera. Kontakt: support@sylion.example

---

*Uzupełnienia do TROUBLESHOOTING_PL.md dla SYLION v5.9.1 — 2026-04-19*
*Scenariusze specyficzne dla v5.9.1, zidentyfikowane w: audit_LATEST/18_user_manual.md*
