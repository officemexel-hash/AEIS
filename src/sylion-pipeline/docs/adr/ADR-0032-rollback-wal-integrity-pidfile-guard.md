# ADR-0032: Rollback.sh WAL integrity + pidfile guard merge

**Status:** PROPOSED  
**Data:** 2026-04-20  
**Wersja:** 5.9.2  
**Autor:** SYLION AI Council / mega_audit/rollback_wal_integrity  

---

## Kontekst

ADR-0017 (rollback-sh-rewrite) przepisał `scripts/rollback.sh` z nową logiką atomowej zamiany backupu. Audyt mega_audit/rollback_wal_integrity wykrył dwa nowe problemy powstałe po tym przepisaniu:

**Problem 1 — WAL integrity check:**  
`rollback.sh` kopiował plik `.db` bez uprzedniej weryfikacji WAL (Write-Ahead Log). Gdy SYLION był uruchomiony podczas rollbacku, WAL (`sylion.db-wal`) i SHM (`sylion.db-shm`) mogły być niesynchronizowane z bazą. Przywrócenie samego `.db` bez towarzyszącego `.wal` powodowało korupcję bazy po restarcie. Testy (mega_audit/backup_rollback_deep) potwierdziły korupcję w 2 z 10 scenariuszy rollback przy aktywnym zapisie.

**Problem 2 — pidfile guard (TOCTOU):**  
`rollback.sh` sprawdzał czy SYLION nie jest uruchomiony przez `ps aux | grep start.py`. Ta technika zawierała TOCTOU (Time-Of-Check-Time-Of-Use): między sprawdzeniem a zatrzymaniem procesu, nowe żądania mogły modyfikować bazę. `mega_audit/prune_workspace_toctou` wskazał analogiczny problem w innych skryptach.

Dodatkowe rozważania:
- `rollback.sh` nie obsługiwał argumentu `--dry-run` — brak możliwości testowego podglądu operacji
- Brak logu audytowego rollbacku w `audit_log` SQLite — niemożność śledzenia kto/kiedy wykonał rollback

Rozważane warianty:
- **B1** — Kopiowanie `.db` + `.wal` + `.shm` (naiwne rozwiązanie — nie gwarantuje spójności)
- **B2** — `PRAGMA wal_checkpoint(FULL)` przed kopią + pidfile guard z `flock` (wybrana)
- **B3** — Zatrzymanie SYLION przed rollbackiem (destruktywne dla HA)
- **B4** — SQLite online backup API (`sqlite3_backup_init`) przez Python wrapper

## Decyzja

Wdrożenie **B2** z merge obu poprawek:

1. **WAL integrity**: przed rollbackiem `rollback.sh` wywołuje `sqlite3 sylion.db "PRAGMA wal_checkpoint(FULL);"` (wymaga `sqlite3` CLI). Jeśli checkpoint nie zakończy się w 30s — abort z kodem wyjścia 2 i komunikatem `SYL-7003` (wal checkpoint timeout).
2. **pidfile guard**: `rollback.sh` używa `flock -n /tmp/sylion_rollback.lock` (exclusive lock) zamiast `ps aux` grep. Jeśli lock niedostępny — abort z `SYL-7004` (concurrent rollback detected). SYLION (`start.py`) utrzymuje własny lockfile `/tmp/sylion.pid` — `rollback.sh` sprawdza jego istnienie przed `flock`.
3. **--dry-run**: flaga `--dry-run` wyświetla listę operacji bez wykonania (WAL check uruchomiony, ale kopiowanie pominięte).
4. **Audit log**: po udanym rollbacku `rollback.sh` zapisuje wpis do `audit_log` przez `sqlite3 sylion.db "INSERT INTO audit_log ..."`.

## Konsekwencje

### Pozytywne
- Eliminacja korupcji bazy po rollbacku przy aktywnym WAL
- Atomowy rollback: `flock` zapobiega równoległemu wywołaniu rollbacku z dwóch terminali
- `--dry-run` bezpieczny do testowania w środowiskach produkcyjnych
- Ślad audytowy rollbacku w bazie danych — wymaganie RODO (prawo do audytu operacji)

### Negatywne
- Wymaga `sqlite3` CLI i `flock` na serwerze (standardowe na Linux, brak na macOS bez Homebrew)
- `wal_checkpoint(FULL)` może zająć do 30s przy dużej bazie — blokuje rollback na ten czas
- Zapis do `audit_log` po rollbacku wymaga działającej bazy — nieosiągalne przy korupcji pre-rollback (edge case)

### Neutralne
- `flock` lockfile `/tmp/sylion_rollback.lock` usuwany przez `trap EXIT` w `rollback.sh`
- Kompatybilność wsteczna: rollback bez `--dry-run` zachowuje się identycznie jak poprzednio (poza WAL check)

## Alternatywy odrzucone

- **B1 (kopiowanie WAL+SHM)**: niespójność między plikami gdy SYLION pisze — odrzucone
- **B4 (Python backup API)**: wymaga Pythona w `rollback.sh` — komplikuje skrypt shell — odrzucone; planowane w v6.0 jako `rollback.py`

## Referencje

- `mega_audit/rollback_wal_integrity/` — analiza WAL integrity i TOCTOU
- `mega_audit/backup_rollback/`, `mega_audit/backup_rollback_deep/` — testy scenariuszy rollback
- `mega_audit/prune_workspace_toctou/` — analiza TOCTOU w skryptach
- ADR-0017 (rollback-sh-rewrite) — poprzednia wersja `rollback.sh`
- `scripts/rollback.sh` — zaktualizowany skrypt
- SQLite WAL documentation: https://www.sqlite.org/wal.html
