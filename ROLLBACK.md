# Rollback — SYLION Pipeline v6.2.0 → v6.0.0

## Kiedy rollback?

- Krytyczna regresja w produkcji.
- Klient integracyjny nie obsługuje nowego namespace `/api/human-gate/*` — ale wtedy wystarczy kontynuować używanie legacy `/api/human_gate/*` (działa z deprecation headers do 2026-12-31, **rollback nie jest konieczny**).
- Breaking behaviour w `init_db` (no seed default API keys) powoduje problem — dodaj klucze ręcznie przez `PUT /api/keys/{name}` **albo** ustaw `SYLION_USE_LEGACY_DB_PATH=1` (stare zachowanie), **też nie wymaga pełnego rollbacku**.

## Sposób 1: In-place restore z backupu (zalecany)

```bash
# 1. Zatrzymaj serwer v6.2.0
systemctl stop sylion || pkill -f 'uvicorn app:app'

# 2. Przywróć pliki z backupu (installer robi snapshot do .backup-YYYYMMDD-HHMMSS)
BACKUP_DIR=$(ls -td .backup-* | head -1)
cp -r "$BACKUP_DIR"/* .

# 3. Przywróć DB (jeśli była modyfikowana)
cp dashboard/sylion_dashboard.db.bak-v600 dashboard/sylion_dashboard.db

# 4. Uruchom v6.0.0
./scripts/start-server.sh   # z poprzedniej paczki
```

## Sposób 2: Git-based (jeśli repo jest pod git)

```bash
git stash                         # opcjonalnie
git checkout tags/v6.0.0 -- .
./scripts/install.sh              # z paczki v6.0.0
```

## Sposób 3: Automatyczny skrypt

```bash
./scripts/rollback.sh
```

Skrypt:
1. Zatrzymuje serwer.
2. Przywraca `*.py`, `VERSION`, `MANIFEST.json` z katalogu `.backup-*`.
3. Przywraca DB z `*.bak-v600`.
4. Weryfikuje `curl /api/version` → `6.0.0`.

## Checklist po rollbacku

- [ ] `GET /api/version` zwraca `6.0.0`
- [ ] `GET /api/health` → `status=ok`
- [ ] Stare klienty underscore human-gate nadal działają
- [ ] Baza nie jest uszkodzona (wejdź do dashboardu)
- [ ] Logi bez `ERROR`

## Ważne

Niektóre zmiany z v6.2.0 **nie wymagają rollbacku** — można je samodzielnie wyłączyć przez env:
- `SYLION_BOOKGUARDIAN_NO_MEMOIZE=1` — wyłącza PIPELINE-011.
- `SYLION_OLLAMA_DNS_FALLBACK=0` — wyłącza CONN-001.
- `SYLION_METRICS_OPEN=1` — wraca do otwartych metrics (B-008 opt-out).
- `SYLION_USE_LEGACY_DB_PATH=1` — stare zachowanie DB path (B-006 opt-out).

**Nie da się cofnąć** bez pełnego rollbacku:
- B-001 (JWT auto-gen) — nowy secret w `.env.generated`; stare JWT tokeny nieważne.
- B-007 (namespace dash) — ale legacy underscore nadal działa, więc nie ma potrzeby.
