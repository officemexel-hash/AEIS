# ROLLBACK PLAN — SYLION v5.9.0 → v5.8.8.1

**Status:** APPROVED  
**Author:** Migration Council v590 (Sonnet role)  
**Date:** 2026-04-18  
**Applies to:** Production SQLite dashboard DB + pipeline code rollback  
**Trigger condition:** M-02 migration failure, data corruption, or critical regression after deploying v5.9.0

---

## Decision Tree — When to Roll Back

```
init_db() raises exception?
  YES → Check PRAGMA user_version
    user_version == 0 → Migration failed, DB still at v5.8.8.1 state → OPTION A (restore backup, revert code)
    user_version == 1 → Migration committed but seeding failed → OPTION B (code revert only, keep migrated DB)
  NO → Application behaves incorrectly?
    Check db.py error logs for _seed_* failures
    Run PRAGMA integrity_check → if not "ok" → OPTION A
    If integrity ok → OPTION C (targeted hotfix)
```

---

## Prerequisites — Before Any Rollback

1. **Stop all uvicorn workers and pipeline processes:**
   ```bash
   pkill -f "uvicorn dashboard" || true
   pkill -f "sylion" || true
   ```

2. **Verify the M-08 backup exists** (created automatically before migration):
   ```bash
   ls -lh ~/sylion/sylion.db.bak.v5.8.9.*.sqlite3
   ```
   Expected: one or more files named `sylion.db.bak.v5.8.9.YYYY-MM-DD.sqlite3`

3. **Record the current DB state for post-mortem:**
   ```bash
   sqlite3 ~/sylion/sylion_dashboard.db "PRAGMA user_version; PRAGMA integrity_check; SELECT COUNT(*) FROM config; SELECT COUNT(*) FROM agents;"
   ```

---

## OPTION A — Full Rollback (code + DB)

**Use when:** Migration corrupted data, `user_version` is unexpected, or `PRAGMA integrity_check` fails.

### Step 1 — Restore DB from M-08 Backup

```bash
# Identify the backup (take the most recent if multiple)
BACKUP=$(ls -t ~/sylion/sylion.db.bak.v5.8.9.*.sqlite3 | head -1)
echo "Restoring from: $BACKUP"

# Verify backup integrity before restore
sqlite3 "$BACKUP" "PRAGMA integrity_check"
sqlite3 "$BACKUP" "PRAGMA user_version"   # Should be 0 for a pre-migration backup

# Stop any remaining connections
fuser -k ~/sylion/sylion_dashboard.db 2>/dev/null || true

# Backup the current (broken) state for post-mortem
cp ~/sylion/sylion_dashboard.db ~/sylion/sylion_dashboard.db.v590_broken.$(date +%Y%m%d_%H%M%S).sqlite3

# Restore
cp "$BACKUP" ~/sylion/sylion_dashboard.db
echo "Restore complete"

# Verify restore
sqlite3 ~/sylion/sylion_dashboard.db "PRAGMA user_version; PRAGMA integrity_check; SELECT COUNT(*) FROM config;"
```

### Step 2 — Restore DB from SQL Dump (alternative if M-08 backup is missing or corrupted)

If no M-08 backup is available, restore from the last manual `.sql` dump taken before the v5.9.0 deploy:

```bash
# Locate the last pre-upgrade SQL dump
ls -lh ~/backups/sylion_*.sql 2>/dev/null || ls -lh /var/backups/sylion_*.sql 2>/dev/null

# Restore from SQL dump
DUMP_FILE=~/backups/sylion_pre_v590_YYYYMMDD.sql
sqlite3 ~/sylion/sylion_dashboard.db < "$DUMP_FILE"

# Verify
sqlite3 ~/sylion/sylion_dashboard.db "PRAGMA user_version; PRAGMA integrity_check;"
```

**Expected state after DB restore:** `user_version = 0`, all pre-v5.9.0 data present.

### Step 3 — Revert Code to v5.8.8.1

```bash
# If using git
cd /path/to/sylion-pipeline
git log --oneline -10   # identify v5.8.8.1 commit hash
git checkout <v5.8.8.1-commit-hash>

# Or restore from versioned archive
tar -xzf ~/releases/sylion_v5.8.8.1.tar.gz -C /path/to/sylion-pipeline/
```

Verify version:
```bash
cat VERSION   # should output: 5.8.8.1
```

### Step 4 — Restart Services

```bash
cd /path/to/sylion-pipeline
/tmp/sylion_venv/bin/python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8421 &

# Verify init_db() runs cleanly (check logs)
curl -s http://127.0.0.1:8421/api/health | python -m json.tool
```

### Step 5 — Validate Rollback Success

```bash
sqlite3 ~/sylion/sylion_dashboard.db <<'SQL'
PRAGMA user_version;           -- Expected: 0 (v5.8.8.1 does not set user_version)
PRAGMA integrity_check;        -- Expected: ok
SELECT COUNT(*) FROM config;   -- Should match pre-upgrade count
SELECT COUNT(*) FROM agents;   -- Should match pre-upgrade count
SELECT COUNT(*) FROM prompts;  -- Should match pre-upgrade count
SQL
```

---

## OPTION B — Code Revert Only (keep migrated DB)

**Use when:** `user_version = 1`, data intact, migration succeeded but application layer has bugs in v5.9.0 code.

**Important:** v5.8.8.1 code does NOT set `user_version`. After rollback, the DB will have `user_version = 1` but v5.8.8.1 code ignores it. This is safe — the new columns added by migration are additive-only (no regressions for old code reading them).

```bash
# Revert code only (DB stays at user_version=1 with new columns intact)
cd /path/to/sylion-pipeline
git checkout <v5.8.8.1-commit-hash>

# Restart
/tmp/sylion_venv/bin/python -m uvicorn dashboard.app:app --host 127.0.0.1 --port 8421 &

# Verify
curl -s http://127.0.0.1:8421/api/health
```

**Note:** If you later re-deploy v5.9.0, the migration will NOT re-run (user_version already = 1). This is correct behavior.

---

## OPTION C — Targeted Hotfix (no rollback)

**Use when:** user_version = 1, data intact, but a specific seed table has an issue (e.g., duplicate rows due to a seeding bug).

```bash
# Open DB directly
sqlite3 ~/sylion/sylion_dashboard.db

-- Check for duplicates
SELECT key, COUNT(*) FROM config GROUP BY key HAVING COUNT(*) > 1;
SELECT id, COUNT(*) FROM agents GROUP BY id HAVING COUNT(*) > 1;
SELECT id, COUNT(*) FROM prompts GROUP BY id HAVING COUNT(*) > 1;

-- Example: remove duplicate config rows keeping latest
DELETE FROM config WHERE rowid NOT IN (
    SELECT MAX(rowid) FROM config GROUP BY key
);

.quit
```

---

## Known Gaps in Migration Coverage

The following issue was identified by the Migration Council v590 shadow DB test:

**`config` table column gap:** `_migration_0_to_1` does NOT add missing columns (`category`, `label`, `description`, `secret`, `updated_at`) to the `config` table. This only affects DBs created with a bare 2-column `config` schema (pre-development, hand-crafted test DBs). Real v5.8.x production DBs already have the full config schema via `CREATE TABLE IF NOT EXISTS`.

**Mitigation if hit:** Manually run before `init_db()`:
```sql
ALTER TABLE config ADD COLUMN category TEXT NOT NULL DEFAULT 'general';
ALTER TABLE config ADD COLUMN label TEXT NOT NULL DEFAULT '';
ALTER TABLE config ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE config ADD COLUMN secret INTEGER NOT NULL DEFAULT 0;
ALTER TABLE config ADD COLUMN updated_at REAL NOT NULL DEFAULT 0;
```

---

## Rollback Decision Log Template

After completing rollback, fill in:

```
ROLLBACK EVENT
Date/Time:
Triggered by:
user_version at failure:
Option chosen: A / B / C
Backup used: ~/sylion/sylion.db.bak.v5.8.9.YYYY-MM-DD.sqlite3
Data loss: YES / NO
Recovery time:
Post-mortem ticket:
```

---

## References

- M-02 Migration framework: `dashboard/db.py:_run_migrations()`, `_migration_0_to_1()`
- M-08 Backup: `dashboard/db.py:_backup_db_before_migration()`
- Migration Council v590 report: `/home/user/workspace/council/v590/migration/CONSOLIDATED.md`
- CHANGELOG v5.8.8.1: `CHANGELOG_v5.8.8.1.md`
