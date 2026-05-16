# SYLION — Disaster Recovery Runbook

> **Model:** Gemini | **Wersja dokumentu:** 1.0.0 | **Data:** 2025-07-11  
> **Zakres:** Rollback v5.9.0 → v5.8.8.1 + pełne odtwarzanie po awarii (DR)

---

## Spis treści

1. [Scenariusze awarii i priorytety](#1-scenariusze-awarii-i-priorytety)
2. [Rollback v5.9.0 → v5.8.8.1 — procedura automatyczna](#2-rollback-automatyczny)
3. [Rollback v5.9.0 → v5.8.8.1 — procedura ręczna](#3-rollback-ręczny)
4. [Przywracanie bazy danych z backupu M-08](#4-przywracanie-bazy-danych)
5. [Instalacja z poprzedniego pakietu pip](#5-instalacja-pip-rollback)
6. [Weryfikacja po przywróceniu](#6-weryfikacja)
7. [Decision Tree — wybór procedury](#7-decision-tree)
8. [Kontakty i eskalacja DR](#8-kontakty-i-eskalacja)

---

## 1. Scenariusze awarii i priorytety

| ID | Scenariusz | RTO | RPO | Procedura |
|----|-----------|-----|-----|-----------|
| DR-01 | Błąd krytyczny po wdrożeniu v5.9.1 (app crash) | 15 min | 0 | [§2 Rollback automatyczny](#2-rollback-automatyczny) |
| DR-02 | Korupcja bazy danych SQLite | 30 min | backup M-08 | [§4 Restore DB](#4-przywracanie-bazy-danych) |
| DR-03 | Błąd pip install — brak możliwości startu | 20 min | N/A | [§5 Pip rollback](#5-instalacja-pip-rollback) |
| DR-04 | Utrata całego serwera (VPS crash) | 2 h | backup M-08 | Pełna reinstalacja |
| DR-05 | Znikające logi / brak audytu | 1 h | N/A | Restore z archiwum logów |

**RPO = Recovery Point Objective** (max. dopuszczalna utrata danych)  
**RTO = Recovery Time Objective** (max. czas przywrócenia usługi)

---

## 2. Rollback automatyczny

Użyj skryptu `rollback.sh` dla najszybszej ścieżki odtworzenia.

### Krok 1: Podgląd (dry-run)

```bash
chmod +x rollback.sh
./rollback.sh --dry-run
```

Skrypt wylistuje akcje bez ich wykonania. Zweryfikuj zanim uruchomisz produkcyjnie.

### Krok 2: Wykonanie rollbacku

```bash
./rollback.sh
```

Skrypt wykonuje automatycznie:
1. Zatrzymanie serwisu SYLION v5.9.1 (systemd lub kill)
2. Lokalizację backupu DB (`sylion.db.bak.v5.9.0.*.sqlite3`)
3. Snapshot bezpieczeństwa aktualnej DB (`sylion.db.safety.pre-rollback.*.sqlite3`)
4. Przywrócenie DB z backupu M-08
5. Weryfikację integralności SQLite (`PRAGMA integrity_check`)
6. Instalację pakietu v5.8.8.1 z archiwum ZIP
7. Restart serwisu
8. Healthcheck post-rollback

### Krok 3: Weryfikacja

```bash
curl http://127.0.0.1:8421/api/health
curl http://127.0.0.1:8421/api/version
```

Oczekiwana odpowiedź:
```json
{ "status": "healthy", "version": "5.8.8.1" }
```

---

## 3. Rollback ręczny

Gdy `rollback.sh` nie jest dostępny lub napotyka problemy.

### 3.1. Zatrzymaj SYLION v5.9.1

```bash
# Wariant systemd
sudo systemctl stop sylion

# Wariant manual
pkill -SIGTERM -f "uvicorn.*app.main"
sleep 3
pkill -SIGKILL -f "uvicorn.*app.main" 2>/dev/null || true
```

### 3.2. Utwórz snapshot bieżącej bazy (bezpieczeństwo)

```bash
cp sylion.db sylion.db.pre-rollback.$(date +%Y%m%d_%H%M%S).sqlite3
```

### 3.3. Przywróć bazę danych

```bash
# Znajdź backup
ls -lt sylion.db.bak.v5.9.0.*.sqlite3 | head -5

# Przywróć najnowszy backup
BACKUP=$(ls -t sylion.db.bak.v5.9.0.*.sqlite3 | head -1)
cp "$BACKUP" sylion.db
echo "Restored: $BACKUP → sylion.db"
```

### 3.4. Przywróć kod aplikacji v5.8.8.1

```bash
# Opcja A: Z archiwum ZIP
unzip -o sylion-v5.8.8.1.zip -d /tmp/sylion-prev
cp -r /tmp/sylion-prev/sylion-pipeline/app ./
cp /tmp/sylion-prev/sylion-pipeline/requirements-lock.txt ./requirements-lock-v5.8.8.1.txt

# Opcja B: Z git (jeśli repozytorium dostępne)
git stash
git checkout v5.8.8.1
```

### 3.5. Zainstaluj zależności v5.8.8.1

```bash
source .venv/bin/activate
pip install --no-cache-dir -r requirements-lock-v5.8.8.1.txt
```

### 3.6. Uruchom serwis v5.8.8.1

```bash
# Wariant systemd
sudo systemctl start sylion

# Wariant manual
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8421 --workers 2 &
```

---

## 4. Przywracanie bazy danych z backupu M-08

### Konwencja nazewnictwa backupów M-08

```
sylion.db.bak.v5.9.0.{TIMESTAMP}.sqlite3
sylion.db.bak.v5.9.0.20250711_020000.sqlite3   # przykład
```

### Lokalizacja backupów

```bash
# Standardowe lokalizacje
ls -lt backups/sylion.db.bak.v5.9.0.*.sqlite3 2>/dev/null
ls -lt ./sylion.db.bak.v5.9.0.*.sqlite3 2>/dev/null

# Lokalizacja M-08 na VPS
ls -lt /var/backups/sylion/*.sqlite3 2>/dev/null
ls -lt /home/sylion/backups/*.sqlite3 2>/dev/null
```

### Pełna procedura restore DB

```bash
# 1. Zatrzymaj aplikację (musi być offline przy restore!)
sudo systemctl stop sylion

# 2. Zidentyfikuj backup (wybierz najnowszy przed incydentem)
BACKUPS=$(ls -t sylion.db.bak.v5.9.0.*.sqlite3 2>/dev/null || ls -t backups/sylion.db.bak.v5.9.0.*.sqlite3)
echo "Dostępne backupy:"
echo "$BACKUPS" | head -10

# 3. Wybierz backup (domyślnie najnowszy)
SELECTED_BACKUP=$(echo "$BACKUPS" | head -1)
echo "Wybrany backup: $SELECTED_BACKUP"

# 4. Snapshot bieżącej bazy
cp sylion.db sylion.db.before-restore.$(date +%Y%m%d_%H%M%S).sqlite3

# 5. Restore
cp "$SELECTED_BACKUP" sylion.db

# 6. Weryfikacja integralności
sqlite3 sylion.db "PRAGMA integrity_check;"
sqlite3 sylion.db "PRAGMA foreign_key_check;"
sqlite3 sylion.db "SELECT COUNT(*) FROM agents;" 2>/dev/null || echo "(agents table not found)"

# 7. Start aplikacji
sudo systemctl start sylion
sleep 5
curl http://127.0.0.1:8421/api/health
```

### Restore z backupu zdalnego (M-08 na zewnętrznym storage)

```bash
# Jeśli backup na SSH/SCP
scp backup-server:/var/backups/sylion/sylion.db.bak.v5.9.0.latest.sqlite3 ./

# Jeśli backup na S3
aws s3 cp s3://firma-backups/sylion/sylion.db.bak.v5.9.0.latest.sqlite3 ./

# Jeśli backup zaszyfrowany (GPG)
gpg --decrypt sylion.db.bak.v5.9.0.latest.sqlite3.gpg > sylion.db.bak.decrypted.sqlite3
```

---

## 5. Instalacja pip z poprzedniego pakietu (v5.8.8.1)

### Opcja A: Z pliku requirements-lock.txt v5.8.8.1

```bash
# Plik requirements-lock.txt pochodzi z archiwum sylion-v5.8.8.1.zip
source .venv/bin/activate

# Deinstaluj pakiety v5.9.0 (opcjonalnie — nie zawsze wymagane)
pip freeze > /tmp/current-packages.txt
pip uninstall -y -r /tmp/current-packages.txt 2>/dev/null || true

# Zainstaluj v5.8.8.1
pip install --no-cache-dir -r requirements-lock-v5.8.8.1.txt
```

### Opcja B: Z archiwum ZIP v5.8.8.1 (bundled wheels)

```bash
# Jeśli archiwum zawiera katalog wheels/
unzip -o sylion-v5.8.8.1.zip wheels/ -d /tmp/sylion-prev

source .venv/bin/activate
pip install --no-index --find-links=/tmp/sylion-prev/wheels -r requirements-lock-v5.8.8.1.txt
```

### Opcja C: Z PyPI (jeśli pakiety publiczne)

```bash
source .venv/bin/activate
# Sprawdź wersje w requirements-lock-v5.8.8.1.txt i zainstaluj bezpośrednio
pip install fastapi==<wersja-z-lockfile> uvicorn==<wersja> ...
```

### Weryfikacja wersji po instalacji

```bash
source .venv/bin/activate
pip list | grep -E "fastapi|uvicorn|sqlalchemy|pyyaml"
python -c "import app; print(getattr(app, '__version__', 'unknown'))"
```

---

## 6. Weryfikacja po przywróceniu

### 6.1. Healthcheck API

```bash
# Podstawowy
curl -sf http://127.0.0.1:8421/api/health | python3 -m json.tool

# Wersja aplikacji
curl -sf http://127.0.0.1:8421/api/version

# Status agentów
curl -sf http://127.0.0.1:8421/api/agents | python3 -m json.tool
```

### 6.2. Weryfikacja bazy danych

```bash
# Integralność
sqlite3 sylion.db "PRAGMA integrity_check;"

# Liczba rekordów (porównaj z oczekiwaniami)
sqlite3 sylion.db "SELECT name, COUNT(*) FROM sqlite_master WHERE type='table' GROUP BY name;"

# Ostatnie modyfikacje
sqlite3 sylion.db "SELECT MAX(created_at) FROM agents;" 2>/dev/null || true
```

### 6.3. Logi aplikacji

```bash
# Systemd
journalctl -u sylion -n 100 --no-pager

# Plik logów
tail -50 logs/sylion.log 2>/dev/null || tail -50 app.log 2>/dev/null
```

### 6.4. Smoke test (podstawowe endpointy)

```bash
BASE="http://127.0.0.1:8421"

for endpoint in /api/health /api/version /api/agents; do
    code=$(curl -sf -o /dev/null -w "%{http_code}" "${BASE}${endpoint}" 2>/dev/null || echo "ERR")
    echo "${endpoint}: HTTP ${code}"
done
```

Oczekiwany wynik: wszystkie endpointy zwracają HTTP 200.

---

## 7. Decision Tree — wybór procedury

```
Problem po wdrożeniu v5.9.0?
│
├─► Aplikacja nie startuje lub crash loop?
│   └─► DR-01: ./rollback.sh (czas: ~10 min)
│
├─► Aplikacja startuje ale dane są uszkodzone?
│   └─► DR-02: §4 Restore DB z backupu M-08 (czas: ~20 min)
│
├─► Błąd importu Python / brakujące zależności?
│   └─► DR-03: §5 Pip rollback (czas: ~15 min)
│
├─► Serwer/VPS niedostępny?
│   └─► DR-04: Fresh install + restore DB (czas: ~2 h)
│       1. Uruchom nowy serwer
│       2. Zainstaluj OS + prerequisites
│       3. Rozpakuj sylion-v5.8.8.1.zip
│       4. ./install.sh
│       5. Przywróć backup DB (§4)
│
└─► Nie wiesz co się dzieje?
    └─► Zadzwoń do L2/L3 (patrz §8)
```

---

## 8. Kontakty i eskalacja DR

| Rola | Kontakt | Dostępność |
|------|---------|-----------|
| On-call Ops | oncall@firma.pl | 24/7 |
| Lead Developer | dev-lead@sylion.io | Godz. robocze |
| DBA | dba@firma.pl | 24/7 dla P1 |
| CTO (P1 eskalacja) | cto@sylion.io | P1 only |

### Klasyfikacja incydentów

| Priorytet | Definicja | Czas odpowiedzi |
|-----------|----------|----------------|
| P1 — Krytyczny | Aplikacja niedostępna produkcyjnie | 15 min |
| P2 — Wysoki | Degradacja funkcjonalności | 1 h |
| P3 — Średni | Błędy niekrytyczne, alerty | 4 h |

---

*Dokument wygenerowany przez Deployment Council SYLION v5.9.0 — model Gemini*  
*Ostatnia aktualizacja: 2025-07-11*
