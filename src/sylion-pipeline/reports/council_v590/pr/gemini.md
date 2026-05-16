# PR Review — Gemini (Regressions, v5.8.x Compatibility)
## SYLION v5.8.8.1 → v5.9.0 | Reviewer: Gemini 3.1 Pro

**Verdict: REQUEST-CHANGES**

---

## Summary

Focused on regression risk and backward compatibility with v5.8.x deployments. Found two regression-capable issues: the versioned migration framework introduces a hard failure mode for any DB that was manually touched, and the M-06 `baselines` GROUP BY query returns different results than the v5.8.x COUNT queries when `status` is NULL. Also flagged the `_backup_db_before_migration` as a startup blocker on read-only filesystems.

---

## Inline Comments

### `db.py` — Regressions & Compatibility

**[db.py +741–835] `_run_migrations` — first-run regression on existing v5.8.x databases**
Severity: HIGH

On upgrade from v5.8.8.1 to v5.9.0:
1. Existing production databases have `PRAGMA user_version = 0` (the default, since v5.8.x never set it).
2. `_run_migrations` reads `current = 0`, `target = 1`, detects migration needed.
3. **Calls `_backup_db_before_migration(conn)`** before applying migration.
4. `_backup_db_before_migration` attempts to create `~/sylion/` directory and write a backup file.

**Regression path A — Read-only filesystem or restricted container:**
If the process runs as a non-root user without write access to `~` (common in Kubernetes pods, Docker containers with read-only rootfs), step 4 raises `PermissionError` or `FileNotFoundError`. This propagates as an unhandled exception from `_run_migrations`, which propagates from `_init_db_unlocked`, which propagates through `init_db()`, crashing the dashboard at startup. **v5.8.x would start normally in this environment.**

Mitigation: wrap `_backup_db_before_migration` in a try/except with a `logger.warning` on failure (not a raise), allowing migration to proceed without backup if the filesystem is restricted. Or make backup path configurable via env var `SYLION_BACKUP_DIR`.

**Regression path B — `mkdir(parents=True, exist_ok=True)` on symlink targets:**
If `~/sylion` is a symlink to a read-only directory (e.g., from a volume mount), `mkdir()` succeeds but subsequent `sqlite3.connect(str(backup_path))` fails. The `except sqlite3.OperationalError` handler re-raises, again crashing startup.

**[db.py +795–806] `_run_migrations` — `BEGIN EXCLUSIVE` blocks all v5.8.x readers during migration**
Severity: MEDIUM

`BEGIN EXCLUSIVE` prevents all other connections (including health-check probes) from reading the database during migration. In v5.8.x, the startup sequence never held an exclusive lock. If the migration takes >5s (e.g., on a large `audit_log` table), any health-check or readiness probe that reads from the DB during this window will fail, potentially triggering an orchestrator restart loop.

Mitigation: use `BEGIN IMMEDIATE` instead of `BEGIN EXCLUSIVE` for WAL-mode databases. WAL allows concurrent readers even during write transactions. `BEGIN IMMEDIATE` is sufficient to serialize writers.

**[db.py +670] Replacement of `_migrate_columns()` with `_run_migrations()`**
Severity: MEDIUM

In v5.8.x, `_migrate_columns()` was called unconditionally every time `init_db()` ran (idempotent ALTER TABLE ADD COLUMN). In v5.9.0, `_run_migrations()` applies each migration only once (tracked via `user_version`). This is correct for *new* columns added *after* the migration is registered. However:

The renamed function `_migration_0_to_1` is identical to the old `_migrate_columns`. If a v5.8.8.1 database already has all columns (because `_migrate_columns` ran successfully), then `_migration_0_to_1` will still be applied (because `user_version = 0`), which is safe (all ADD COLUMN checks are idempotent via `PRAGMA table_info`). ✓

But: if a v5.8.8.1 database is *missing* a column (because it was created before a particular ALTER was added to `_migrate_columns`), the migration will add it. This is also correct. ✓

**Conclusion: No regression for the ALTER TABLE path. The v5.8.x → v5.9.0 migration of column structure is safe.**

**[db.py +670] `_run_migrations` is called with `db_path=DB_PATH` but `_backup_db_before_migration` ignores the parameter**
Severity: LOW

`_run_migrations(conn, db_path=DB_PATH)` passes `db_path` as a parameter, but `_backup_db_before_migration(source_conn)` does not use `db_path` at all — it uses `Path.home() / "sylion"` unconditionally. The `db_path` parameter to `_run_migrations` is therefore unused. This creates a misleading signature and means that if `DB_PATH` is overridden (e.g., in tests via `db.DB_PATH = tmp_path / "test.db"`), the backup still goes to `~/sylion/`. Remove the unused `db_path` parameter from `_run_migrations` or pass it through to `_backup_db_before_migration`.

**[db.py +1082–1085] New config rows for `AUDIT_LOG_RETENTION_DAYS` and `SESSIONS_RETENTION_DAYS`**
Severity: LOW (compatibility)

The seed logic uses:
```python
conn.execute(
    "INSERT OR IGNORE INTO config (key, value, ...) VALUES (...)"
)
```
`INSERT OR IGNORE` means existing v5.8.x databases that already have a `AUDIT_LOG_RETENTION_DAYS` row (from a previous manual entry) will **not** be overwritten. ✓ New installs will get the defaults. ✓ No regression.

---

### `app.py` — Regressions & Compatibility

**[app.py +696–755] M-06 GROUP BY — NULL status regression**
Severity: MEDIUM

In v5.8.x, the queries were:
```sql
SELECT COUNT(*) as c FROM baselines WHERE status='draft'
SELECT COUNT(*) as c FROM baselines WHERE status='review'
```
These COUNT only rows where `status` is explicitly `'draft'` or `'review'`. Rows with `status IS NULL` are excluded.

In v5.9.0:
```python
baselines_by_status = {
    (r["s"] or "draft"): r["c"]
    for r in conn.execute(
        "SELECT COALESCE(status, 'draft') AS s, COUNT(*) AS c FROM baselines GROUP BY s"
    ).fetchall()
}
baselines_total = sum(baselines_by_status.values())
```

`COALESCE(status, 'draft')` maps `NULL → 'draft'`. So `baselines_draft` now includes rows where `status IS NULL`, which it did *not* in v5.8.x.

**Result: `baselines_draft` can be *higher* in v5.9.0 than v5.8.x for databases where some rows have NULL status.** The PR comment claims "BYTE-IDENTICAL to v5.8.x" — this claim is **FALSE** for databases with NULL-status rows.

Similarly for `prompts_by_status`: `COALESCE(status, 'active')` will count NULL-status prompts as `'active'`.

Mitigation options:
- Option A: Remove COALESCE and filter NULL explicitly:
  ```sql
  SELECT status, COUNT(*) AS c FROM baselines WHERE status IS NOT NULL GROUP BY status
  ```
  Then `baselines_total` should be counted separately:
  ```sql
  SELECT COUNT(*) AS c FROM baselines
  ```
- Option B: Keep COALESCE but update the PR comment to remove the "BYTE-IDENTICAL" claim and document the behavioral change.
- Option C: If NULL status rows don't exist in practice, add a `NOT NULL DEFAULT 'draft'` constraint migration for `baselines.status`.

**This is the highest-priority regression in the PR.**

**[app.py +109–123] Startup prune now runs `prune_audit_log` and `prune_sessions` on first startup**
Severity: LOW

On a fresh upgrade from v5.8.8.1, the first startup will call `prune_audit_log` and `prune_sessions`. If the `audit_log` table has 365+ days of data (likely on long-running installations), this prune will delete rows — potentially irreversibly. Users upgrading from v5.8.x may not expect data deletion to occur on the first startup of the new version.

Recommendation: add a startup log line *before* the prune that explicitly states: `"Startup: pruning audit_log rows older than %d days"`. This is not a blocker but improves operator visibility.

---

### `start.py` — Regressions & Compatibility

**[start.py +106–164] M-04 lockfile install path — v5.8.x compat**
Severity: LOW

In v5.8.x, `_ensure_dependencies` never attempted to install from a lockfile. If a v5.8.x deployment has a stale `requirements-lock.txt` at `DASHBOARD_DIR.parent/` (from a previous experiment or partial rollout), v5.9.0 will attempt to install from it on startup. If the lockfile pins older incompatible versions, this silently downgrades packages in the environment.

The `_LOCK.exists()` check is the correct gate, but the comment should note: "If upgrading from v5.8.x, ensure no stale `requirements-lock.txt` exists at the repo root before deploying v5.9.0."

**[start.py +42–45] `_BATCH_TIMEOUT = 20` — v5.8.x regression potential**
Severity: LOW

If the batch subprocess times out (e.g., on a slow CI machine), `_batch_imports_ok` returns `False`, and the code falls back to the per-package slow path. The slow path then checks each package individually. This is correct — no regression. The worst case is 13 × 30s = 390s startup time on a fully broken environment, identical to v5.8.x worst case. No regression.

---

## Compatibility Matrix

| Change | v5.8.x DB compat | v5.8.x env compat | Regression risk |
|---|---|---|---|
| `_run_migrations` + `user_version` | ✓ (safe on existing DBs) | ✓ | MEDIUM: backup fails on restricted FS |
| `BEGIN EXCLUSIVE` during migration | ✓ | N/A | MEDIUM: blocks health checks |
| `prune_audit_log` / `prune_sessions` | ✓ | ✓ | LOW: first-run silent deletion |
| M-06 GROUP BY with COALESCE | ✓ | ✓ | **HIGH: NULL-status count difference** |
| M-04 lockfile install | ✓ | ✓ | LOW: stale lockfile at repo root |
| M-07 batch subprocess | ✓ | ✓ | NONE |
| Version bump 5.8.8 → 5.9.0 | ✓ | ✓ | NONE |

**Must fix before merge: M-06 NULL-status regression (HIGH) and backup startup failure on restricted filesystem (HIGH).**

---

## Required Changes (Blockers)

1. **[app.py +720–735]** Fix `COALESCE`-based GROUP BY or remove "BYTE-IDENTICAL" claim. Provide accurate behavior documentation.
2. **[db.py +765–790]** Make `_backup_db_before_migration` non-fatal on permission/FS errors (warn + continue, don't raise).
3. **[db.py +795]** Change `BEGIN EXCLUSIVE` to `BEGIN IMMEDIATE` for WAL-mode compatibility.
4. **[db.py +670]** Remove unused `db_path` parameter from `_run_migrations` signature.

---

*Reviewed by: Gemini (Gemini 3.1 Pro) — regressions, v5.8.x compatibility*
