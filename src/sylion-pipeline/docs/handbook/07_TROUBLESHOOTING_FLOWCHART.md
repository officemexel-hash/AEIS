# Troubleshooting Flowchart — SYLION Pipeline v5.9.2

Diagramy decyzyjne dla najczestszych problemow. Uzywaj ich jako punktu startowego przed kontaktem z supportem.

---

## Diagram glowny — "Pipeline nie dziala"

```
PROBLEM: Pipeline nie dziala / nie uruchamia sie
                    |
                    v
      Czy serwer dashboard odpowiada?
      curl http://localhost:8421/api/health/live
            /                      \
          TAK                      NIE
           |                        |
    HTTP 200?                  Czy proces dziala?
    /       \               ps aux | grep start.py
  TAK       NIE                 /         \
   |          |              TAK          NIE
   |    Problem aplikacji     |            |
   |    -> Sprawdz logi       |      Uruchom ponownie:
   |       (patrz nizej)   Blad?   python dashboard/start.py
   |                       /    \
   v                     TAK    NIE
Czy /api/health/ready          Czekaj na start (30s)
       zwraca 200?             i sprawdz ponownie
       /        \
     TAK        NIE
      |           |
   Pipeline    Sprawdz
   jest OK     co nie dziala:
              /api/health/detailed
```

---

## Diagram — problemy z baza danych

```
PROBLEM: Blad bazy danych
                    |
                    v
         Co widze w logu?
         /         |          \
"locked"   "integrity"    "migration failed"
    |           |                  |
    v           v                  v
Sprawdz czy    Uruchom:      Sprawdz:
jednoczesnie  rollback.sh   data/migration_errors.log
dziala wiecej  --integrity      |
niz 1 proc.   -check-only      v
    |             |        czy backup istnieje?
    |           FAIL?      ls ~/sylion/backups/
    |           /    \        /           \
    |         TAK    NIE    TAK           NIE
    |          |      |      |             |
Kill duplikat  |    OK      bash rollback.sh Skontaktuj sie
WEB_CONCURR=1  |           --from-backup=X  z supportem
    |          v
    |    Restore z backupu
    |    rollback.sh
    |    --from-backup=...
    v
restart serwisu:
systemctl restart sylion-dashboard
```

---

## Diagram — problemy z modelami AI

```
PROBLEM: Modele AI nie odpowiadaja / blad council
                    |
                    v
     Sprawdz /api/health/detailed
     -> sekcja "models"
                    |
          /api/circuit-breakers
                    |
            Ktory stan?
         /     |       |      \
      CLOSED  OPEN  HALF_OPEN  WSZYSTKIE OPEN
        |       |       |           |
      Blad    Czekaj  Sonda       Sprawdz
      kluczy  30s na  w toku      czy Ollama
      API?   HALF_OPEN           dziala:
        |           \             ollama list
      Sprawdz       v              /       \
      klucze     Jesli sonda     TAK       NIE
      w .env     fail -> OPEN    |         |
      lub UI      ponownie      LOCAL_ONLY Uruchom:
                                tryb      ollama serve
                                           + ollama pull
                                           llama3.1:8b
```

---

## Diagram — problemy z urzadzeniami

```
PROBLEM: Provisioning urzadzenia nie dziala
                    |
                    v
          Jaki typ urzadzenia?
          /                    \
      Pixel 9               Mudi router
          |                    |
    Sprawdz ADB:          Sprawdz SSH:
    adb devices           ssh root@192.168.8.1
          |                    |
    Czy widzi urz.?       Czy sie laczy?
       /       \             /        \
     TAK       NIE         TAK        NIE
      |         |           |          |
  Czy model  Sprawdz:   WG status:  Sprawdz:
  Pixel 9?   USB cable  wg show      - IP routera
   /     \   ADB mode   /     \     - SSH key
 TAK     NIE enabled  OK    FAIL    - Firewall
  |       |             |      |
 OK    WRONG_MODEL  Tunnel    wg-quick
        blad:       aktywny   down wg0
        -> zmien              wg-quick up wg0
        urzadzenie
```

---

## Diagram — problemy z HumanGate

```
PROBLEM: HumanGate sie nie pojawia / pipeline stoi
                    |
                    v
         GET /api/humangate/pending
                    |
            Czy sa wyniki?
            /              \
          TAK              NIE
           |                |
     Odpowiedz na       Pipeline stoi
     bramke przez UI    z innego powodu
     lub API            -> sprawdz logi
           |                i /api/health
     Status po odpowiedzi?
     /            |          \
   resumed    EXPIRED       REJECTED
      |           |              |
   Pipeline   Restart:      Pipeline NO-GO
   kontynuuje POST /api/     raport w UI
              humangate
              /HG-XXX/restart
```

---

## Diagram — problemy z kosztami i budzetem

```
PROBLEM: Pipeline zablokowany przez Budget Guard
                    |
                    v
         GET /api/cost/budget
                    |
            Sprawdz status:
         /         |           \
      NORMAL    WARNING       EXCEEDED
         |         |              |
      Kontynuuj Uwazaj na     Opcje:
      normalnie  koszty       1. Czekaj do jutra
                              2. Admin reset:
                                 POST /api/cost/reset
                              3. Zwieksz limit:
                                 PATCH /api/config/flags
                                 /MAX_COST_USD_PER_DAY
                              4. Przejdz na local-only:
                                 council_mode: "local-only"
```

---

## Diagram — problemy z WireGuard kill switch

```
PROBLEM: Brak internetu na urzadzeniu przez Mudi
                    |
                    v
       Czy kill switch jest aktywny?
       ssh root@192.168.8.1 "iptables -L OUTPUT"
                    |
          Czy polityka OUTPUT to DROP?
              /              \
            TAK              NIE
             |                |
     Kill switch aktywny   Inny problem
             |             (routing, DNS)
     Czy tunel WG dziala?
     wg show | grep "latest handshake"
         /             \
       TAK              NIE (brak lub > 3 min)
        |                |
     Ruch powinien   Restart tunelu:
     dzialac przez   wg-quick down wg0
     tunel. Sprawdz  wg-quick up wg0
     routing:             |
     ip route         Sprawdz handshake
                      po 30 sekundach
                           |
                    Jesli nadal fail:
                    Sprawdz serwer VPN
                    (endpoint dostepny?)
                    ping SERVER_IP -c 3
```

---

## Diagram — problemy z backup / rollback

```
PROBLEM: Potrzebuje przywrocic poprzedni stan
                    |
                    v
       Czy wiem co poszlo zle?
          /              \
        TAK              NIE
         |                |
  Czy jest backup?   Uruchom diagnozę:
  ls ~/sylion/backups/  rollback.sh
         |             --integrity-check-only
    /         \              |
  TAK         NIE          Wynik?
   |            |          /       \
  Uruchom    Czy jest    OK        FAIL
  rollback:  backup z       |          |
  bash       migracji?  Baza OK   Restore
  rollback.sh ls ~/sylion/ Sprawdz  z backupu
  --list-backups backups/  logi
```

---

## Tabela szybkiego rozwiazywania

| Objaw                           | Pierwsze sprawdzenie                        | Szybkie rozwiazanie                         |
|---------------------------------|---------------------------------------------|---------------------------------------------|
| Port 8421 niedostepny           | `ps aux | grep start.py`                    | `python dashboard/start.py`                 |
| "database is locked"            | `ps aux | grep python` (wiele procesow?)    | Kill duplikat, WEB_CONCURRENCY=1            |
| "429 Too Many Requests" logowanie | Czekaj 10 minut                           | Lub reset rate_limit_state.json             |
| Council vote: wszyscy FAIL      | `/api/circuit-breakers`                     | Sprawdz klucze API, restart CB              |
| HumanGate expired               | `/api/humangate/pending`                    | POST .../restart                            |
| Pixel: ADB not found            | `adb version`                               | `apt install android-tools-adb`             |
| Pixel: WRONG_MODEL              | `adb devices`                               | Podlacz Pixel 9 family                      |
| WG: brak internetu              | `wg show` na routerze                       | `wg-quick down wg0 && wg-quick up wg0`      |
| Budget exceeded                 | `/api/cost/budget`                          | Czekaj do jutra lub admin reset             |
| Ollama OOM                      | `journalctl -u ollama`                      | Zmien na mniejszy model (8B)                |
| Migration failed                | `cat data/migration_errors.log`             | `rollback.sh --from-backup=...`             |
| Upload rejected (path traversal)| Sprawdz zawartosc ZIP                       | Utwórz nowe archiwum bez `../`              |

---

## Kontakty eskalacyjne

| Problem                          | Pierwsza linia                        | Eskalacja                          |
|----------------------------------|---------------------------------------|------------------------------------|
| Bledy kodu / pipeline            | Handbook sekcja 10 (A-L)              | GitHub Issues / support@sylion.example |
| Bezpieczenstwo / CVE             | `docs/security/PIXEL_THREAT_MODEL.md` | Natychmiast: security@sylion.example |
| Utrata danych                    | `rollback.sh --list-backups`          | support@sylion.example (PILNE)     |
| Incydent produkcyjny             | `docs/sre/INCIDENT_RESPONSE.md`       | On-call SRE                        |

---

*Poprzednia sekcja: [06_USER_MANUAL.md](./06_USER_MANUAL.md)*
*Nastepna sekcja: [08_FAQ.md](./08_FAQ.md)*
