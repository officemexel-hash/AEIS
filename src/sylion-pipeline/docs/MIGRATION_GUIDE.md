# Przewodnik migracji — SYLION v5.8.x → v5.9.0

| Pole            | Wartość                                     |
|-----------------|---------------------------------------------|
| **Wersja źródłowa** | v5.8.x (testowano: v5.8.8.1 production baseline) |
| **Wersja docelowa** | v5.9.0 „Breakthrough — 18 Skills Audit" |
| **Data wydania**    | 2026-04-19                              |
| **Rodzaj zmian**    | Wyłącznie addytywne — brak breaking changes |
| **Czas wdrożenia**  | ~5 minut (typowy), ~15 minut (z weryfikacją pełną) |
| **Ryzyko**          | NISKIE — migracje addytywne, automatyczny rollback możliwy |
| **Rollback**        | [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)  |

---

## Szybki start

```bash
# 1. Utwórz ręczny backup bazy danych (zalecane w produkcji)
cp ~/sylion/sylion.db ~/sylion/sylion.db.bak.manual.$(date +%Y%m%d)

# 2. Zaktualizuj kod
git fetch origin
git checkout v5.9.0
# lub: git pull && git checkout tags/v5.9.0

# 3. Zaktualizuj zależności Python
pip install -r requirements-lock.txt

# 4. Uruchom SYLION — migracje wykonają się automatycznie
python dashboard/start.py

# 5. Zweryfikuj wersję schematu
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Oczekiwany wynik: 1
```

---

## Wymagania wstępne

### Python i zależności

| Wymaganie         | Minimalna wersja | Zalecana wersja | Uwagi                                      |
|-------------------|------------------|-----------------|--------------------------------------------|
| Python            | 3.11             | 3.12            | 3.11 minimum; 3.12 tested and recommended |
| argon2-cffi       | 23.1.0           | ≥23.1.0         | **Wymagane** — bez tego `hash_password` rzuca RuntimeError (FIX-09) |
| bcrypt            | 4.0.0            | ≥4.0.0          | Opcjonalne (fallback po argon2-cffi)       |
| fastapi           | 0.111.0          | ≥0.111.0        | Bez zmian API                              |
| pydantic          | 2.6.0            | ≥2.6.0          | Wymagane do `AgentSpec` validation (M-01)  |

> **Krytyczne:** `argon2-cffi` jest teraz **twardą zależnością**. Jeśli nie jest zainstalowane,
> SYLION uruchomi się poprawnie, ale próba rejestracji lub zmiany hasła zakończy się
> `RuntimeError`. Uruchom `pip install -r requirements-lock.txt` by zapewnić prawidłowe zależności.

### Sprawdź zależności przed migracją

```bash
python -c "import argon2; print('argon2-cffi:', argon2.__version__)"
python -c "import pydantic; print('pydantic:', pydantic.VERSION)"
```

---

## Kroki migracji (szczegółowe)

### Krok 1 — Backup bazy danych

```bash
# Ręczny backup (zalecane przed każdym wdrożeniem produkcyjnym)
mkdir -p ~/sylion/backups
cp ~/sylion/sylion.db ~/sylion/backups/sylion.db.bak.pre-v590.$(date +%Y%m%dT%H%M%S)
echo "Backup: $(ls -lh ~/sylion/backups/sylion.db.bak.pre-v590.*)"
```

> **Uwaga:** SYLION v5.9.0 automatycznie tworzy backup w `~/sylion/sylion.db.bak.v5.9.0.YYYY-MM-DD.sqlite3`
> przy starcie (M-08). W środowiskach z FS tylko do odczytu (kontenery, K8s) automatyczny
> backup może się nie powieść — logowany jest komunikat WARNING. W takim przypadku ręczny
> backup przed wdrożeniem jest obowiązkowy.

### Krok 2 — Zatrzymanie aktywnych procesów SYLION

```bash
# Sprawdź uruchomione instancje
ps aux | grep "start.py"

# Zatrzymaj gracefully (jeśli uruchomiony przez systemd)
systemctl stop sylion

# Lub przez PID
kill -SIGTERM $(cat ~/sylion/sylion.pid 2>/dev/null)
```

### Krok 3 — Aktualizacja kodu

```bash
# Opcja A: git (zalecane)
git fetch origin
git stash  # jeśli masz lokalne zmiany
git checkout v5.9.0

# Opcja B: release archive
wget https://github.com/sylion/sylion-pipeline/releases/download/v5.9.0/sylion-v5.9.0.tar.gz
tar xzf sylion-v5.9.0.tar.gz --strip-components=1
```

### Krok 4 — Aktualizacja zależności Python

```bash
# Zainstaluj z lockfile (deterministyczne wersje)
pip install -r requirements-lock.txt

# Weryfikacja krytycznej zależności
python -c "
import argon2
import pydantic
print(f'argon2-cffi: {argon2.__version__}')
print(f'pydantic: {pydantic.VERSION}')
print('Zależności OK')
"
```

### Krok 5 — Uruchomienie SYLION (automatyczne migracje)

```bash
python dashboard/start.py
```

Przy starcie SYLION v5.9.0 wykona automatycznie:

1. `_backup_db_before_migration` — backup do `~/sylion/sylion.db.bak.v5.9.0.YYYY-MM-DD.sqlite3`
2. `_run_migrations` — migracja schematu z `user_version=0` do `user_version=1`
3. Weryfikacja `_batch_imports_ok` (1 subprocess, nie 13)
4. `_seed_agents` z walidacją Pydantic `AgentSpec`

**Oczekiwane logi startu:**

```
INFO  [db] PRAGMA user_version: 0 → uruchamianie migracji
INFO  [db] Backup przed migracją v1: /home/user/sylion/sylion.db.bak.v5.9.0.2026-04-19.sqlite3
INFO  [db] Migracja v1: CREATE TABLE IF NOT EXISTS ...
INFO  [db] PRAGMA user_version ustawiono na 1
INFO  [db] Migracje zakończone. user_version=1
INFO  [app] SYLION v5.9.0 uruchomiony na http://0.0.0.0:8000
```

### Krok 6 — Weryfikacja po migracji

```bash
# Sprawdź wersję schematu
sqlite3 ~/sylion/sylion.db "PRAGMA user_version;"
# Oczekiwany wynik: 1

# Sprawdź nowe indeksy
sqlite3 ~/sylion/sylion.db ".indexes audit_log"
# Oczekiwany wynik: idx_audit_log_ts, idx_audit_log_actor

# Sprawdź nowe tabele (jeśli dodane przez migrację v1)
sqlite3 ~/sylion/sylion.db ".tables"

# Test logowania (weryfikacja rate limitera FIX-01)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "test123"}'
# Oczekiwany wynik: 200 OK lub 401 (nie 500)

# Test dashboardu (weryfikacja M-06 + FIX-02)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/dashboard
# Oczekiwany wynik: JSON bez klucza "unknown"
```

---

## Zmiany łamiące kompatybilność wsteczną

### Brak — wydanie wyłącznie addytywne

Wydanie v5.9.0 **nie zawiera żadnych zmian łamiących kompatybilność wsteczną** z v5.8.x:

| Obszar                  | Status          | Uwagi                                                    |
|-------------------------|-----------------|----------------------------------------------------------|
| API REST endpoints      | Bez zmian       | Kształt JSON zachowany; nowe endpointy nie dodane w 5.9  |
| Tabele bazy danych      | Tylko ADD       | Nowe tabele/kolumny dodane; istniejące niezmienione      |
| Zmienne środowiskowe    | Tylko ADD       | Nowe opcjonalne: `SYLION_RATELIMIT_*`, `SYLION_*_RETENTION_DAYS` |
| Plik konfiguracyjny     | Bez zmian       | `sylion.conf` kompatybilny w pełni                       |
| Python API (internal)   | Addytywne       | Nowe funkcje dodane; istniejące sygnatury niezmienione   |
| Zależności Python       | `argon2-cffi` wymagane | Poprzednio opcjonalne; teraz twarda zależność (FIX-09) |

> **Jedyna potencjalnie odczuwalna zmiana:** Jeśli środowisko nie miało zainstalowanego
> `argon2-cffi`, operacje haszowania haseł rzucają teraz `RuntimeError` zamiast cicho
> degradować do SHA-256. Jest to **celowa zmiana bezpieczeństwa** (FIX-09).

---

## Nowe zmienne środowiskowe (opcjonalne)

Wszystkie nowe zmienne środowiskowe mają wartości domyślne zgodne z poprzednim zachowaniem
systemu — nie są wymagane do aktualizacji konfiguracji.

| Zmienna                          | Domyślna | Opis                                    |
|----------------------------------|----------|-----------------------------------------|
| `SYLION_RATELIMIT_WINDOW`        | `300`    | Okno rate limitera logowania (sekundy)  |
| `SYLION_RATELIMIT_MAX_ATTEMPTS`  | `5`      | Maks. prób logowania w oknie            |
| `SYLION_RATELIMIT_LOCKOUT`       | `600`    | Czas blokady konta (sekundy)            |
| `SYLION_AUDIT_RETENTION_DAYS`    | `365`    | Retencja audit_log (RODO art. 5)        |
| `SYLION_SESSION_RETENTION_DAYS`  | `30`     | Retencja sesji                          |

---

## Migracje bazy danych — szczegóły

### Schemat migracji v1

Migracja v1 (pierwsza formalna migracja) wykonuje następujące operacje DDL:

```sql
-- Indeksy dla audit_log (FIX-11)
CREATE INDEX IF NOT EXISTS idx_audit_log_ts
    ON audit_log (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_actor
    ON audit_log (actor, timestamp DESC);

-- Kolumna retencji (M-03) — jeśli nie istnieje
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS expires_at INTEGER;

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS expires_at INTEGER;
```

Wszystkie operacje używają `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` — są idempotentne.

### Weryfikacja schematu po migracji

```bash
sqlite3 ~/sylion/sylion.db << 'EOF'
-- Wersja schematu
SELECT 'user_version:', user_version FROM pragma_user_version;

-- Indeksy audit_log
SELECT 'Indeksy audit_log:', name FROM sqlite_master
WHERE type='index' AND tbl_name='audit_log';

-- Kolumny audit_log
PRAGMA table_info(audit_log);
EOF
```

---

## Rollback

Jeśli konieczny jest powrót do v5.8.8.1:

### Rollback kodu (zawsze bezpieczny — migracje addytywne)

```bash
# Powrót do poprzedniego tagu
git checkout v5.8.8.1
pip install -r requirements-lock.txt

# Uruchom — baza danych z user_version=1 jest kompatybilna z v5.8.x
# (dodatkowe tabele/kolumny są ignorowane przez starszy kod)
python dashboard/start.py
```

> **Ważne:** Kod v5.8.x będzie działać poprawnie na bazie danych z schematem v5.9.0.
> Nowe indeksy i kolumny są ignorowane przez starszy kod. Nie ma potrzeby przywracania
> bazy danych dla rollbacku kodu.

### Rollback bazy danych (tylko jeśli wymagana pełna izolacja)

Jeśli konieczne jest przywrócenie dokładnie stanu v5.8.x (np. usunięcie nowych indeksów
dla diagnostyki):

```bash
# Zatrzymaj SYLION
systemctl stop sylion

# Przywróć backup automatyczny (v5.9.0 backup)
cp ~/sylion/sylion.db.bak.v5.9.0.2026-04-19.sqlite3 ~/sylion/sylion.db

# Lub ręczny backup sprzed migracji
cp ~/sylion/backups/sylion.db.bak.pre-v590.TIMESTAMP ~/sylion/sylion.db

# Powróć do kodu v5.8.8.1
git checkout v5.8.8.1

# Uruchom
python dashboard/start.py
```

Szczegółowy plan rollbacku: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)

---

## Weryfikacja bezpieczeństwa po migracji

### Test rate limitera (FIX-01)

```bash
# Wykonaj 6 prób logowania (limit: 5/5min)
for i in $(seq 1 6); do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"wrong_password"}')
  echo "Próba $i: HTTP $HTTP"
done
# Oczekiwany wynik: próby 1-5 → HTTP 401, próba 6 → HTTP 429
```

### Test limitu długości hasła (FIX-08)

```bash
# Hasło > 1024 znaków powinno zwrócić HTTP 422
LONG_PASSWORD=$(python3 -c "print('x'*1025)")
curl -s -o /dev/null -w "%{http_code}" -X POST \
  http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"$LONG_PASSWORD\"}"
# Oczekiwany wynik: 422
```

### Test RuntimeError bez argon2 (FIX-09 — weryfikacja dokumentacyjna)

```bash
# Sprawdź że argon2-cffi jest zainstalowane
python -c "import argon2; print('OK:', argon2.__version__)"
# Jeśli wynik to ModuleNotFoundError — wykonaj: pip install argon2-cffi
```

---

## Rozwiązywanie problemów

### Problem: `RuntimeError: Brak bezpiecznego backendu haszowania haseł`

**Przyczyna:** `argon2-cffi` i `bcrypt` nie są zainstalowane.

**Rozwiązanie:**
```bash
pip install argon2-cffi
# lub
pip install -r requirements-lock.txt
```

### Problem: `WARNING: Nie można utworzyć backupu przed migracją`

**Przyczyna:** System plików jest tylko do odczytu (kontener, K8s, GrapheneOS).

**Działanie:** Ostrzeżenie — migracja kontynuuje poprawnie. Upewnij się, że wykonałeś
ręczny backup przed wdrożeniem (Krok 1).

### Problem: Dashboard zwraca klucz `"unknown"` w JSON

**Przyczyna:** Starszy kod v5.8.x z oryginalnym M-06 (COALESCE, bez FIX-02).

**Rozwiązanie:** Upewnij się, że masz kod v5.9.0 z FIX-02 (`WHERE status IS NOT NULL`).

### Problem: `PRAGMA user_version` zwraca 0 po restarcie

**Przyczyna:** Migracja nie wykonała się (brak uprawnień zapisu do bazy danych lub
baza danych jest w trybie WAL bez checkpointu).

**Rozwiązanie:**
```bash
# Sprawdź uprawnienia
ls -la ~/sylion/sylion.db
# Wymuszony checkpoint WAL
sqlite3 ~/sylion/sylion.db "PRAGMA wal_checkpoint(FULL);"
# Uruchom ponownie
python dashboard/start.py
```

### Problem: Logowanie blokowane natychmiast (rate limiter zbyt agresywny)

**Przyczyna:** Poprzednie nieudane próby logowania (np. z testów) zapełniły sliding window.

**Rozwiązanie:** Poczekaj 10 minut (czas blokady) lub zrestartuj serwer (reset in-memory
liczników). Lub dostosuj parametry:
```bash
export SYLION_RATELIMIT_MAX_ATTEMPTS=10
export SYLION_RATELIMIT_WINDOW=60
python dashboard/start.py
```

---

## Wsparcie

- Dokumentacja deploymentu: [RUNBOOK_DEPLOY.md](./RUNBOOK_DEPLOY.md)
- Plan wycofania: [ROLLBACK_PLAN.md](./ROLLBACK_PLAN.md)
- Odtwarzanie po katastrofie: [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md)
- Procedury incydentów: [INCIDENT_RESPONSE.md](./INCIDENT_RESPONSE.md)
- Rejestr zmian: [CHANGELOG_v5.9.0.md](./CHANGELOG_v5.9.0.md)
- Decyzje architektoniczne: [adr/](./adr/)
