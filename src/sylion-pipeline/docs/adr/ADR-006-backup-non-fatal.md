# ADR-006: Non-fatal backup przed migracją schematu

| Pole          | Wartość                                                          |
|---------------|------------------------------------------------------------------|
| **ID**        | ADR-006                                                          |
| **Tytuł**     | Backup przed migracją jako operacja non-fatal na FS tylko do odczytu |
| **Status**    | Zaakceptowany                                                    |
| **Data**      | 2026-04-19                                                       |
| **Wersja**    | SYLION v5.9.0                                                    |
| **Zmiany**    | FIX-03, FIX-06, M-08                                            |
| **Autorzy**   | migration-council, sre-incident                                  |
| **Powiązane** | ADR-003, ROLLBACK_PLAN.md, DISASTER_RECOVERY.md                  |

---

## Status

**Zaakceptowany** — zatwierdzone przez migration-council (wynik GO-WITH-WARNINGS;
ostrzeżenie W-02: „backup skip musi być logowany na poziomie WARNING"). Implementacja
zweryfikowana przez `tests/test_migration_framework.py` (scenariusze: read-only FS,
K8s ephemeral volume, normalne FS).

---

## Kontekst

### Problem

M-08 wprowadził automatyczny backup bazy danych przed migracją schematu:

```
~/sylion/sylion.db.bak.v5.9.0.YYYY-MM-DD.sqlite3
```

Oryginalna implementacja wywoływała `raise` gdy operacja backup się nie powiodła
(np. `PermissionError`, `OSError: Read-only file system`). Skutkowało to:

1. **Blokadą migracji na kontenerach** — wiele środowisk kontenerowych (Docker z `--read-only`,
   K8s z `readOnlyRootFilesystem: true`, GrapheneOS) montuje filesystem jako tylko do odczytu.
   `~/sylion/` może być katalogiem konfiguracyjnym w wolumenie, ale katalog home może
   nie istnieć lub być read-only.
2. **Blokadą migracji na CI** — pipeline CI (GitHub Actions, GitLab CI) uruchamia testy
   bez katalogu `~/sylion/` z prawami zapisu.
3. **Nieoczekiwana krytyczność** — backup jest środkiem ostrożności, nie warunkiem koniecznym
   do poprawności migracji. Addytywna migracja (tylko ADD) jest sama w sobie bezpieczna
   do wycofania przez przywrócenie poprzedniego deploymentu.

### Natura migracji addytywnych

Kluczowym kontekstem dla tej decyzji jest zasada **wyłącznie addytywnych migracji**
(patrz ADR-003):

- Migracje v5.9.0 dodają wyłącznie nowe tabele, kolumny i indeksy.
- Poprzedni kod (v5.8.x) może działać na nowej bazie danych bez modyfikacji — ignoruje
  nieznane tabele i kolumny.
- Wycofanie deploymentu (rollback kodu) na bazę z nowym schematem jest **bezpieczne**.
- Backup jest miarą dodatkowej ostrożności (defense-in-depth), nie wymogiem atomowości.

### Środowiska bez możliwości backupu

| Środowisko          | Przyczyna braku backupu                              | Częstość      |
|---------------------|------------------------------------------------------|---------------|
| Docker `--read-only` | `~/` jest tmpfs lub brak mount point dla backup      | Wysoka (CI)   |
| K8s `readOnlyRootFilesystem` | PVC może nie być zamontowany pod `~/`         | Wysoka (prod) |
| GrapheneOS           | Ograniczone uprawnienia zapisu poza `/data/user/0/` | Średnia       |
| CI pipeline (GitHub Actions) | Brak trwałego katalogu `~/sylion/`          | Wysoka (CI)   |

---

## Decyzja

### Zasada: backup non-fatal, zawsze z logowaniem

Funkcja `_backup_db_before_migration` traktuje błędy zapisu jako **ostrzeżenie**, nie błąd:

```python
def _backup_db_before_migration(db_path: Path, version: int) -> bool:
    """
    Tworzy kopię zapasową bazy danych przed migracją.

    Returns:
        True jeśli backup się powiódł, False jeśli nie powiódł się (non-fatal).
    """
    today = date.today().isoformat()
    backup_path = Path.home() / "sylion" / f"sylion.db.bak.v5.9.0.{today}.sqlite3"

    try:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(db_path, backup_path)
        logger.info(
            "Backup przed migracją v%d: %s",
            version, backup_path
        )
        return True
    except (PermissionError, OSError) as exc:
        logger.warning(
            "Nie można utworzyć backupu przed migracją v%d (%s). "
            "Kontynuowanie migracji — migracje są addytywne i bezpieczne do wycofania. "
            "Zalecane ręczne zabezpieczenie bazy danych przed wdrożeniem w produkcji.",
            version, exc
        )
        return False
```

### Algorytm wywołania

```python
def _run_migrations(conn: sqlite3.Connection, db_path: Path) -> None:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version in range(current + 1, _DB_TARGET_VERSION + 1):
        backup_succeeded = _backup_db_before_migration(db_path, version)
        if not backup_succeeded:
            logger.warning("Migracja v%d wykonywana BEZ backupu.", version)
        _apply_migration(conn, version)  # zawsze wykonaj migrację
```

### Reguły niezmienne

1. **Backup zawsze próbowany** — nie jest pomijany bez próby; próba jest zawsze logowana.
2. **Błąd backupu zawsze logowany na WARNING** — widoczny w logach, nie cichy.
3. **Migracja wykonywana niezależnie od sukcesu backupu** — nie zablokowana przez niepowodzenie backupu.
4. **Komunikat ostrzeżenia jest opisowy** — instruuje administratora o ręcznym backupie w produkcji.
5. **Zwracana wartość** — `bool` informuje wywołującego o statusie backupu (do testowania).

---

## Konsekwencje

### Pozytywne

- **Kompatybilność z kontenerami** — SYLION uruchamia się poprawnie w Docker `--read-only`,
  K8s z `readOnlyRootFilesystem: true`, GrapheneOS, CI pipeline.
- **Nie blokuje CI/CD** — pipeline deweloperski i testy automatyczne nie wymagają
  specjalnej konfiguracji katalogu `~/sylion/`.
- **Przejrzystość** — ostrzeżenie w logach informuje administratora o braku backupu;
  decyzja o kontynuowaniu jest świadoma, nie milcząca.
- **Zgodność z zasadą addytywności** — addytywne migracje są strukturalnie bezpieczne
  bez backupu; rollback jest możliwy przez przywrócenie poprzedniego deploymentu.

### Negatywne

- **Niższy poziom ochrony na systemach FS tylko do odczytu** — brak automatycznego backupu
  w środowiskach gdzie backup jest niemożliwy. Administrator musi samodzielnie zadbać
  o backup przed wdrożeniem w produkcji (opisane w MIGRATION_GUIDE.md i ROLLBACK_PLAN.md).
- **Ryzyko przeoczenia ostrzeżenia** — administrator może nie zauważyć ostrzeżenia
  w logach gdy backup się nie powiódł. Mitigacja: monitoring logów na poziomie WARNING
  powinien być skonfigurowany w środowiskach produkcyjnych (patrz RUNBOOK_DEPLOY.md).

### Neutralne

- Decyzja nie zmienia semantyki migracji — nie jest możliwe cofnięcie migracji DDL bez backupu.
  ROLLBACK_PLAN.md opisuje procedurę przywracania z backup lub reinstalacji v5.8.x.
- Backup na systemach FS z możliwością zapisu działa identycznie jak w poprzedniej
  implementacji (FIX-03 nie zmienia happy path).

---

## Alternatywy rozważane

### Opcja A: Wymaganie FS z możliwością zapisu (fail hard)

**Odrzucona.** Blokuje SYLION na wielu legalnych środowiskach (kontenery, CI, mobile).
Nadmierne wymaganie dla narzędzia lokalnego.

### Opcja B: Backup do tymczasowego katalogu (`/tmp/`) jako fallback

**Rozważona, odrzucona.** `/tmp/` jest czyszczony przy restarcie systemu i może być
ephemeral (tmpfs). Backup w `/tmp/` daje fałszywe poczucie bezpieczeństwa — w wielu
środowiskach kontenerowych `/tmp/` jest w pamięci RAM i zniknie wraz z kontenerem.

### Opcja C: Backup wyłącznie gdy `_DB_TARGET_VERSION > current + 1` (duże skoki wersji)

**Odrzucona.** Komplikuje logikę bez znaczącej korzyści. Każda migracja jest potencjalnie
destruktywna dla istniejących danych; spójność: zawsze próbuj, nigdy nie blokuj.

### Opcja D: Konfigurowalny tryb `SYLION_REQUIRE_BACKUP=true/false`

**Rozważona, odłożona.** Zmienna środowiskowa umożliwia administratorom wymuszenie
krytyczności backupu w środowiskach produkcyjnych. Zaplanowane do v5.9.1 po ocenie
zapotrzebowania operacyjnego.
