# FAQ — SYLION Pipeline v5.9.2

Najczesciej zadawane pytania o pipeline SYLION. Szczegolowe instrukcje znajduja sie w [06_USER_MANUAL.md](./06_USER_MANUAL.md) i [07_TROUBLESHOOTING_FLOWCHART.md](./07_TROUBLESHOOTING_FLOWCHART.md).

---

## Uzywanie pipeline

**P: Czy moge uzywac pipeline bez internetu?**

Tak, z ograniczeniami. Przy wylaczonej sieci dziala: lokalny Ollama (Tier 0), interfejs dashboard, provisioning przez lokalne ADB/SSH. Nie dziala: cloud models (Anthropic, OpenAI, Google). Pipeline automatycznie przechodzi w tryb LOCAL_ONLY — rada 4 modeli jest zdegradowana do lokalnego Ollama. Wyniki audytu beda mniej precyzyjne. Aby skonfigurowac Ollama: `ollama serve` i `ollama pull llama3.1:8b`.

---

**P: Ile moze trwac pelny audyt codebase?**

Zalezy od rozmiaru projektu i wybranego tier routingu. Orientacyjne czasy:

| Rozmiar projektu | Tier        | Szacowany czas |
|------------------|-------------|----------------|
| < 5 plikow       | LOCAL       | 1-3 min        |
| 5-30 plikow      | STANDARD    | 3-10 min       |
| 30-100 plikow    | PREMIUM     | 10-30 min      |
| > 100 plikow     | PREMIUM     | 30-90 min      |

Czas HumanGate nie wlicza sie — pipeline czeka na odpowiedz operatora.

---

**P: Czy pipeline dziala na Windows?**

Czescowo. Dashboard i audyt codebase dzialaja w pelni na Windows 10/11 przez `install.bat`. Provisioning urzadzen (Pixel 9 przez ADB, Mudi przez SSH) wymaga zainstalowania dodatkowych narzedzi (android-tools, openssh). Zalecane: WSL2 (Windows Subsystem for Linux) dla pelnej funkcjonalnosci. Ollama dla Windows jest dostepny jako oddzielna aplikacja.

---

**P: Co jesli HumanGate wygasa podczas mojego obiadu?**

Pipeline przechodzi w stan PAUSED — nie abortuje i nie aplikuje zmian automatycznie. Po powrocie znajdziesz bramke z etykieta EXPIRED. Kliknij "Restart" w UI lub wyslij `POST /api/humangate/{id}/restart`. Pipeline dostaje nowe 30 minut i wznawia oczekiwanie. Twoja decyzja sie nie zmienia — nadal musisz odpowiedziec.

---

**P: Jakie porty musza byc otwarte?**

| Port      | Protokol | Cel                                           |
|-----------|----------|-----------------------------------------------|
| 8421      | TCP      | Dashboard UI i API (za Caddy: 443)            |
| 443       | TCP      | HTTPS (Caddy reverse proxy, produkcja)        |
| 51820     | UDP      | WireGuard VPN                                 |
| 22        | TCP      | SSH do routera Mudi (z komputera pipeline)    |
| 11434     | TCP      | Ollama local (tylko localhost, nie otwieraj)  |
| 9090      | TCP      | Prometheus (tylko localhost lub wewn. siec)   |
| 3000      | TCP      | Grafana (tylko localhost lub wewn. siec)      |

Uwaga: porty 8421, 9090, 3000 domyslnie nasłuchuja tylko na 127.0.0.1. Dostep zewnetrzny: przez Caddy (443) lub SSH tunnel.

---

**P: Jak zresetowac haslo administratora?**

1. Zatrzymaj serwer: `systemctl stop sylion-dashboard` lub Ctrl+C
2. Usuń bazę danych: `rm ~/sylion/sylion.db`
3. Uruchom serwer ponownie: `python dashboard/start.py`
4. Skopiuj nowy setup token z konsoli
5. Przejdz pod `http://localhost:8421/setup` i ustaw nowe haslo

Uwaga: usuniecie bazy kasuje cala historie pipeline. Zrob backup jesli potrzebujesz zachowac dane: `bash scripts/backup.sh` przed krokiem 2.

---

**P: Czy pipeline przechowuje moj kod po audycie?**

Tak, przez krotki czas. Pliki ZIP sa usuwane automatycznie po 7 dniach (retencja `prune_workspace_uploads`). Metadane historii uploadow — po 90 dniach. Mozesz skrocic te okresy w `.env`. Kod NIE jest wysylany do zewnetrznych serwisow (poza API modeli AI — tylko prompt + diff, nie cale pliki zrodlowe).

---

**P: Jak dodac piaty model do Rady?**

1. Dodaj klucz API nowego providera do `.env`
2. Edytuj `agents.yaml` — dodaj model do sekcji `audit`:

```yaml
global:
  default_models:
    audit:
      - claude-sonnet-4-6
      - gpt-5-4
      - gemini-3-1-pro
      - deepseek-v3
      - nowy-model-id   # <- dodaj tutaj
```

3. Zaktualizuj `consensus_threshold` w `agents.yaml` (np. z 3 na 4 dla piatego modelu)
4. Uruchom `pytest tests/test_council.py` — regresje
5. Utwórz ADR dokumentujacy zmiane

Uwaga: dodanie piatego modelu zmienia logike konsensusu. Nalezy rowniez zaktualizowac progi w `budget_guard.py` i `02_SYSTEM_DECYZJI.md`.

---

**P: Co to jest SYLION TAILOR i czy moge go uzywac?**

SYLION TAILOR to osobny produkt — system zarzadzania dla zakladow krawieckich (zamowienia, faktury, KSeF, JPK, GoBD). Nie jest czescia tego pipeline ani SYLION Secure. Jesli szukasz TAILOR — jest to oddzielne oprogramowanie z osobna dokumentacja. Nie jest dostarczany w tym ZIP.

---

**P: Jak sprawdzic ile wydatem na modele AI w tym miesiacu?**

```bash
curl -b cookies.txt http://localhost:8421/api/cost/budget
```

Lub w UI: `Dashboard → Budget → Monthly Overview`. Grafana: dashboard "Cost Tracker" pokazuje trend dzienny i miesiczny per model.

---

## Bezpieczenstwo

**P: Czy moje klucze API sa bezpieczne?**

Klucze sa przechowywane w `.env` (plik lokalny, nie w bazie) i w tabeli `api_keys` (SQLite, pole `secret=1` oznacza ze nie pojawia sie w logach). Klucze NIE opuszczaja Twojego serwera — sa uzywane tylko do wywolywan API z procesu SYLION. Nie sa wysylane do zewnetrznych serwisow poza docelowym providerem (Anthropic / OpenAI / Google). Wazne: upewnij sie ze `.env` ma uprawnienia 600: `chmod 600 .env`.

---

**P: Czy dashboard jest bezpieczny w sieci lokalnej bez HTTPS?**

Dla developmentu na localhost: tak. Dla srodowisk gdzie do dashboardu ma dostep wiele osob lub dashboard jest dostepny poza localhost: nie — skonfiguruj Caddy z TLS. Gotowy `Caddyfile` jest w `deploy/Caddyfile`. Bez HTTPS: sesja cookie nie jest chroniona przez HSTS, ruch moze byc nasluchiwany w sieci.

---

**P: Co to jest Hallucination Guard i czy moge go wylaczyc?**

Hallucination Guard (warstwa 1-5 systemu anty-halucynacyjnego) weryfikuje ze agenci AI nie tworza "twierdzen" o kodzie ktory nie istnieje lub sie nie zmienil. Wyaczenie go oznacza ze pipeline moze aplikowac zmiany na podstawie nieprawdziwych twierdzen agentow. Mozesz wylaczyc poszczegolne warstwy przez feature flags, ale nie jest to zalecane w produkcji. Dla testow:

```bash
# Wylacz tylko Fact Checker (warstwa 5)
PATCH /api/config/flags/FACT_CHECKER_ENABLED {"value": false}
```

---

**P: Jak pipeline chroni przed prompt injection?**

Pipeline stosuje kilka warstw ochrony:

1. Dane uzytkownika (kod, pliki) sa przekazywane jako oddzielne parametry — nie interpolowane bezposrednio do system promptu
2. ClaimProvenance weryfikuje twierdzenia agentow wzgledem kodu zrodlowego
3. FileVerification (SHA-256) wykrywa jesli agent twierdzi ze zmienil plik ktorego nie zmienil
4. HumanGate wymagany dla wszystkich operacji krytycznych — czlowiek zatwierdza

Nie istnieje 100% ochrona przed prompt injection — to jest akceptowane ryzyko resztkowe.

---

**P: Jak zadbac o bezpieczenstwo klucza SSH do routera Mudi?**

Zalecane praktyki:
1. Generuj dedykowany klucz ED25519 dla SYLION: `ssh-keygen -t ed25519 -f ~/.ssh/mudi_sylion`
2. Ustaw passphrase na kluczu
3. Ogranicz klucz na routerze do komend SSH (`command=` w authorized_keys)
4. Nie uzywa tego klucza do innych celow
5. Sciezke do klucza ustaw w `.env` `DEVICE_ROUTER_SSH_KEY=~/.ssh/mudi_sylion`

---

## Provisioning urzadzen

**P: Czy moge provisionowac Pixel 7 lub 8?**

Nie. Pipeline obsługuje wylacznie rodzine Pixel 9 (Pixel 9, 9 Pro, 9 Pro XL, 9a, 9 Pro Fold). Decyzja architektoniczna C-003, ADR-0015. Pixel 7 i 8 maja inny model zagrozen i inne instrukcje hardeningu GrapheneOS. Dla starszych modeli skontaktuj sie z supportem.

---

**P: Co sie stanie jesli odlacze kabel USB podczas flashowania?**

Pixel przejdzie w stan bootloop lub niezdefiniowany stan bootloadera. To jest powazny problem — moze wymagac recznego odzyskania przez fastboot z innego komputera. Upewnij sie przed flashowaniem:
- Kabel USB jest stabilny (najlepiej kabel oficjalny Google)
- Laptop jest podlaczony do zasilania (nie na baterii)
- System nie przejdzie w tryb uśpienia

---

**P: Czy provisionig Pixela resetuje wszystkie dane?**

Tak. Krok OEM unlock wykonuje reset fabryczny Pixela (powrot do ustawien fabrycznych). Wszystkie dane na urzadzeniu zostana skasowane. Pipeline wymaga HumanGate CRITICAL z potwierdzeniem przez uzytkownika ze ma backup danych.

---

**P: Co to jest DEVICE_HARNESS_DRY_RUN i kiedy go wylaczac?**

`DEVICE_HARNESS_DRY_RUN=true` (domyslne) — pipeline symuluje wszystkie komendy ADB/SSH bez ich faktycznego wykonania. Idealne do testowania i onboardingu.

`DEVICE_HARNESS_DRY_RUN=false` — pipeline wysyla realne komendy do urzadzenia. Wylaczaj tylko gdy:
- Jestes gotowy na fizyczny provisioning
- Pixel 9 jest podlaczony i gotowy
- Masz backup wszelkich waznych danych
- Dry-run przeszedl bez bledow

---

**P: Czy kill switch WireGuard wplywa na dashboard SYLION?**

Nie, jesli dashboard dziala na tym samym komputerze co pipeline (localhost). Kill switch blokuje ruch na routerze Mudi — nie na komputerze z pipeline. Dashboard na localhost jest zawsze dostepny bez wzgledu na stan WG. Jesli dashboard jest na VPS dostepnym przez WG tunel — tak, kill switch odetnietez ten dostep.

---

## Konfiguracja i administracja

**P: Jak skonfigurowac alerty email od Alertmanagera?**

Edytuj `deploy/monitoring/alertmanager.yml`:

```yaml
receivers:
  - name: 'email-alert'
    email_configs:
      - to: 'admin@przyklad.pl'
        from: 'sylion@przyklad.pl'
        smarthost: 'smtp.przyklad.pl:587'
        auth_username: 'sylion@przyklad.pl'
        auth_password: 'haslo_smtp'
```

Nastepnie restartuj Alertmanager: `docker compose restart alertmanager`.

---

**P: Jak uruchomic SYLION jako serwis systemd (autostart)?**

Gotowy unit file: `deploy/sylion-dashboard.service`. Instalacja:

```bash
sudo cp deploy/sylion-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sylion-dashboard
sudo systemctl start sylion-dashboard
# Sprawdz status:
sudo systemctl status sylion-dashboard
```

---

**P: Jak skonfigurowac Caddy jako reverse proxy z TLS?**

Gotowy `Caddyfile` w `deploy/Caddyfile`. Wyedytuj adres domeny:

```
sylion.twoja-domena.pl {
    reverse_proxy localhost:8421
}
```

Nastepnie: `sudo caddy run --config deploy/Caddyfile`. Caddy automatycznie pobiera certyfikat Let's Encrypt.

---

**P: Ile miejsca na dysku potrzebuje SYLION?**

Minimalne wymagania: 2 GB. Realistyczne:

| Komponent                | Rozmiar typowy  |
|--------------------------|-----------------|
| Kod Python + venv        | ~400 MB         |
| Baza SQLite              | 10-100 MB       |
| Backupy (domyslnie 90 dni) | 50-500 MB     |
| Workspace uploads (7 dni) | 0-2 GB        |
| Modele Ollama (optional) | 4-40 GB per model |
| Logi (30 dni)            | 10-100 MB       |

Suma bez Ollama: ~1-3 GB. Z Ollama 8B: +5 GB. Z Ollama 70B: +40 GB.

---

**P: Czy moge zmienic port dashboard z 8421 na inny?**

Tak. W `.env`:

```ini
DASHBOARD_PORT=9000
```

Pamietaj o aktualizacji Caddyfile i reguł firewalla jesli uzywasz Caddy lub iptables.

---

**P: Jak sprawdzic, ze konfiguracja jest poprawna przed pierwszym uruchomieniem?**

```bash
# Sprawdz skladnie .env
python -c "from dotenv import dotenv_values; v=dotenv_values(); print(f'Loaded {len(v)} vars')"

# Sprawdz polaczenie z modelami
python -c "
import anthropic, os
from dotenv import load_dotenv
load_dotenv()
c = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
r = c.messages.create(model='claude-haiku-3-5-20241022', max_tokens=10,
                       messages=[{'role':'user','content':'ping'}])
print('Anthropic OK:', r.content[0].text)
"

# Sprawdz SQLite
python -c "import sqlite3; c=sqlite3.connect(':memory:'); print('SQLite OK:', sqlite3.sqlite_version)"
```

---

**P: Jakie sa roznice miedzy v5.9.1 a v5.9.2?**

Glowne zmiany:

| Zmiana                          | v5.9.1  | v5.9.2       |
|---------------------------------|---------|--------------|
| CSRF coverage                   | 23/71   | 71/71 (DONE) |
| Pixel domyslne urzadzenie       | Pixel 8 | Pixel 9      |
| WireGuard implementacja         | Brak    | Pelna (kill switch, DNS tunnel) |
| Diagnostyka                     | v1      | v2 (82 kody SYL-*) |
| DB schema                       | v3      | v4           |
| rollback.sh                     | Nie WAL-safe | WAL-safe + flock |
| run_codebase_audit()            | Brak (P0-007) | Wdrozone |
| Fact Checker model ID           | Bledny  | Naprawiony   |
| P0 blokerów                     | 10 open | 0 open       |

Pelna lista: `docs/RELEASE_NOTES_v5.9.2_PL.md`.

---

**P: Czy SYLION Pipeline jest zgodny z RODO?**

Pipeline implementuje minimum RODO wymagane dla narzedzia developerskiego:
- Art. 5 — zasady przetwarzania: logi bez danych osobowych, minimalizacja danych
- Art. 17 — prawo do usuniecia: `purge_soft_deleted_users` (soft-delete + twardee usuniecie po 30 dniach)
- Art. 30 — rejestr czynnosci: `audit_log` table, retencja 90 dni
- Art. 32 — bezpieczenstwo: Argon2id, CSRF, security headers, TLS

SYLION NIE przetwarza danych osobowych uzytkownikow koncowych (to sa dane developera, nie jego klientow). DPIA dostepna: `docs/DPIA_v591.md`.

---

**P: Jak zatrzymac pipeline w awaryjnej sytuacji?**

Opcje od najszybszej do najlepszej:

1. PILNE: Feature flag kill switch (HTTP 200ms):

```bash
curl -b cookies.txt \
  -H "X-CSRF-Token: TOKEN" \
  -X PATCH http://localhost:8421/api/config/flags/PIPELINE_EMERGENCY_STOP \
  -d '{"value": true}'
```

2. Zatrzymaj serwis systemd (wszystkie requesty: 503):

```bash
systemctl stop sylion-dashboard
```

3. Kill procesu (ostatecznosc):

```bash
kill -9 $(pgrep -f "dashboard/start.py")
```

---

*Poprzednia sekcja: [07_TROUBLESHOOTING_FLOWCHART.md](./07_TROUBLESHOOTING_FLOWCHART.md)*
*Nastepna sekcja: [09_GLOSSARY.md](./09_GLOSSARY.md)*
