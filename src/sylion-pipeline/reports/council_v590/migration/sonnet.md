# Sonnet Council Report — Rollback Plan
## SYLION v5.9.0 — M-02 Framework Verification

**Date:** 2026-04-18  
**Model:** Claude Sonnet 4.6 (rollback plan role)  
**Scope:** Rollback strategy v5.9.0 → v5.8.8.1, M-08 backup recovery, SQL restore path

---

## Deliverable

**ROLLBACK_PLAN.md** has been written to:
```
/home/user/workspace/SYLION_v590_work/sylion-pipeline/docs/ROLLBACK_PLAN.md
```

File size: 7,153 bytes | 221 lines

---

## Rollback Plan Summary

Three rollback options are documented:

| Option | Trigger | Action |
|---|---|---|
| **A — Full** | Corrupt DB, integrity_check fails, unexpected user_version | Restore from M-08 backup or SQL dump + revert code to v5.8.8.1 |
| **B — Code only** | user_version=1, data intact, v5.9.0 app-layer bug | Revert code to v5.8.8.1 only; leave migrated DB as-is |
| **C — Targeted** | Seeding issue, duplicate rows | Direct SQL fix, no code or DB restore needed |

---

## M-08 Backup Verification

The M-08 (`_backup_db_before_migration`) mechanism was confirmed functional:
- Backup is created before the **first** migration in any `init_db()` run
- Uses sqlite3 online backup API — WAL-safe, works on live DB
- F-04 path traversal guard active (resolved path must stay under `~/sylion/`)
- Backup file confirmed: `~/sylion/sylion.db.bak.v5.8.9.2026-04-18.sqlite3`
- Backup created in the shadow DB test (Opus): **1 file for 10 concurrent threads** (migration ran once, backup ran once)

---

## Key Rollback Considerations

### 1. Additive-only migrations
All columns added by `_migration_0_to_1` are additive with DEFAULT values. v5.8.8.1 code can safely read a DB with `user_version=1` — new columns are ignored by old SELECT statements.

**Implication for Option B:** Code rollback without DB rollback is safe. The extra columns do no harm.

### 2. user_version after code rollback
v5.8.8.1 code does not write `PRAGMA user_version`. After Option B rollback, the DB remains at `user_version=1`. When v5.9.0 is re-deployed later, `_run_migrations` correctly skips re-applying migration (already at target).

### 3. Multiple backup files
If multiple deployments are attempted in one day, only one backup file exists per date (filename is deterministic: `sylion.db.bak.v5.8.9.YYYY-MM-DD.sqlite3`). Subsequent same-day `init_db()` calls on an already-migrated DB (`user_version=1`) skip the migration entirely — no new backup is created, and the existing backup is **not overwritten**. This is safe.

### 4. Gap — config table column coverage
`_migration_0_to_1` does not backfill missing `config` columns. The rollback plan includes a manual SQL workaround. This gap should be fixed in a future migration step.

---

## Estimated Recovery Times

| Scenario | Estimated RTO |
|---|---|
| Option A (M-08 backup restore, local) | < 2 minutes |
| Option A (SQL dump restore, local) | < 5 minutes |
| Option B (code revert only) | < 1 minute |
| Option C (SQL fix) | < 5 minutes |

---

## Verdict

**Rollback plan: COMPLETE**
- Three-option decision tree covers all failure scenarios
- M-08 backup confirmed functional (WAL-safe, F-04 guarded)
- Additive-only migration makes Option B (code rollback, keep DB) safe
- SQL restore path documented as fallback if M-08 backup missing
