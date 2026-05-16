# PR Review — Sonnet (Correctness, Edge Cases, Testability)
## SYLION v5.8.8.1 → v5.9.0 | Reviewer: Claude Sonnet 4.6

**Verdict: REQUEST-CHANGES**

---

## Summary

The functional intent of v5.9.0 is correct and the major paths are well-reasoned. However, I identified three correctness issues that require fixes before merge: a SQL injection risk in `_run_migrations`, a subtle `prune_sessions` column name mismatch, and a backup strategy that silently succeeds without verifying backup integrity. There are also several edge cases in the retention logic and testability gaps.

---

## Inline Comments

### `db.py` — Correctness

**[db.py +808] SQL injection in `PRAGMA user_version = {version}` — MEDIUM/HIGH**
Severity: MEDIUM

```python
conn.execute(f"PRAGMA user_version = {version}")
```

`version` is an `int` from `range(current + 1, target + 1)`, so it cannot contain SQL injection characters. However, Python f-string interpolation into `conn.execute()` is a dangerous pattern that will fail linting (bandit B608, ruff S608) and trains future contributors to do the same with non-integer values. SQLite does not support parameterized PRAGMA statements (`PRAGMA user_version = ?` raises `sqlite3.OperationalError`), which is the root cause. The correct mitigation is:

```python
# Safe: version is int, validate explicitly
assert isinstance(version, int) and version >= 0, f"Invalid migration version: {version!r}"
conn.execute(f"PRAGMA user_version = {version:d}")  # :d format spec rejects non-int at format time
```

Add a comment explaining *why* parameterization is not possible for PRAGMA.

**[db.py +990–1010] `prune_sessions` — `expires_at` vs `ts` column**
Severity: MEDIUM

```python
"DELETE FROM sessions WHERE token IN "
"(SELECT token FROM sessions WHERE expires_at < ? LIMIT 1000)",
```

The `prune_audit_log` function correctly uses `ts` (the column defined in the CREATE TABLE for `audit_log`). The sessions table uses `expires_at` here. This needs to be verified against the actual schema. In v5.8.x the sessions table DDL must be audited — if `expires_at` is a Unix timestamp float, the comparison is correct. If it is an ISO 8601 string (common in session libraries), `< ?` with a float cutoff will silently delete *nothing* (string < float is always False in SQLite's type affinity rules). Recommend adding a schema-check test:

```python
def test_prune_sessions_column_types():
    conn = get_conn()
    cols = {r["name"]: r["type"] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()}
    assert cols.get("expires_at") in ("REAL", "INTEGER", "NUMERIC"), \
        "sessions.expires_at must be numeric for prune_sessions cutoff comparison"
```

**[db.py +765–790] `_backup_db_before_migration` — no integrity check after backup**
Severity: LOW

The backup uses `source_conn.backup(dest_conn)` which is the correct SQLite online backup API. However, there is no post-backup integrity verification (`PRAGMA integrity_check` on `dest_conn`). If the source DB is already corrupted (page checksum errors under WAL), the backup succeeds but reproduces the corruption. The subsequent migration then runs against a DB that may be damaged. Recommend:

```python
result = dest_conn.execute("PRAGMA integrity_check").fetchone()
if result[0] != "ok":
    raise RuntimeError(f"M-08: backup integrity check failed: {result[0]}")
```

**[db.py +780] `_backup_db_before_migration` — F-04 date-based filename collision**
Severity: LOW

The backup filename includes `datetime.date.today().isoformat()`. If `init_db()` is called twice on the same day (e.g., two test runs, or a service restart), the second call silently overwrites the first backup with `source_conn.backup(dest_conn)` on a newly opened `dest_conn`. The v5.8.9 backup from 09:00 is lost when the 14:00 restart produces the same filename. Consider appending a timestamp or UUID suffix:

```python
ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
backup_path = backup_dir / f"sylion.db.bak.{version_tag}.{ts}.sqlite3"
```

**[db.py +795–806] `_run_migrations` — `conn.execute("BEGIN EXCLUSIVE")` without checking autocommit state**
Severity: MEDIUM

If `conn` was returned by `get_conn()` and `executescript()` was called on it earlier in `_init_db_unlocked` (which it is — the `CREATE TABLE IF NOT EXISTS` block), `executescript()` issues an implicit `COMMIT` before executing. So at the point `_run_migrations` is called, the connection is not in a transaction. This is correct for the current call stack. However, the behavior is fragile because it relies on `executescript`'s implicit commit behavior. Adding `conn.execute("ROLLBACK TO SAVEPOINT sp_pre_migrate") if conn.in_transaction` guard or a comment explaining the ordering dependency would improve robustness.

**[db.py +942–980] `_get_retention_days` — `≤ 0` fallback is silent for UI users**
Severity: LOW

The function logs a warning when `n <= 0` and falls back to default. However, a user who enters `0` in the UI (intending "disable retention") will silently get 365-day retention instead. This is confusing. Either: (a) treat `0` as "infinite retention" (never prune), or (b) document in the config label that `0` and negative values are invalid and fall back to default. Currently the label says `≤ 0 → użyj domyślnej` which is correct — confirm the UI actually displays this description.

**[db.py +1466] `agent_id = None` scope reset (H-04)**
Severity: NIT (positive change)

The explicit `agent_id = None` reset before each loop iteration is the correct fix for the `locals().get()` unreliability in v5.8.8.1. The fallback in the `except` block now uses a proper priority chain: `agent_id if not None → a.get("id") if dict → repr(a)`. This is cleaner and testable. APPROVE.

---

### Edge Cases

**[db.py +940–980] `prune_audit_log` / `prune_sessions` — no max-iteration guard**
Severity: LOW

The `while True: … if deleted < 1000: break` loop assumes the DELETE will eventually converge. If a concurrent writer is inserting rows faster than 1000/tx (unlikely but possible in high-throughput deployments), this loop runs indefinitely. Add a max-iterations guard:

```python
MAX_BATCHES = 10_000
batches = 0
while batches < MAX_BATCHES:
    batches += 1
    ...
    if deleted < 1000:
        break
else:
    logger.warning("M-03: prune_audit_log hit max-batch limit (%d), stopping", MAX_BATCHES)
```

**[app.py +696–755] M-06 — `baselines_total = sum(baselines_by_status.values())`**
Severity: LOW

If the `baselines` table is empty, `baselines_by_status` is `{}` and `sum({}.values()) == 0`. This is correct. However, the `or 0` guard on agents_row fields (`agents_row["total"] or 0`) maps `None` to `0`, which is correct for empty tables. The same guard is missing for `baselines_total` and `prompts_total` — but since `sum([])` returns `0`, this is safe. Low priority.

**[start.py +74–100] `_batch_imports_ok` — script injection via semicolon in package names**
Severity: LOW (mitigated)

```python
script = "; ".join(f"import {n}" for n in import_names)
```

The comment correctly notes that `import_names` come from the hardcoded `_CRITICAL_DEPS` dict. If a future contributor adds a package with a non-identifier name (e.g., `"some-pkg"` with a hyphen), the generated script becomes `import some-pkg` which raises `SyntaxError` in the subprocess (returncode != 0), triggering the slow-path fallback — harmless but potentially confusing. Add a guard:

```python
assert all(n.isidentifier() or "." in n for n in import_names), \
    f"Non-identifier import names in _CRITICAL_DEPS: {import_names}"
```

---

### Testability

**[db.py +72–81] `init_db()` / `_db_init_lock` — untestable lock contention**
Severity: LOW

The `_db_init_lock` is a module-level `threading.Lock()`. There is no way to inject a mock lock or reset it between tests. If a test calls `init_db()` with an already-held lock (simulating a contention scenario), it will deadlock. Recommend exposing a `_reset_db_init_lock()` function or using a `threading.RLock()` to allow re-entrant calls in test fixtures.

**[db.py +835–908] `_run_migrations` — `_DB_TARGET_VERSION` is a module global, not injectable**
Severity: LOW

Testing the downgrade-refusal path (`current > target → RuntimeError`) requires setting `_DB_TARGET_VERSION` to a value lower than the DB's `user_version`. This is possible via `db._DB_TARGET_VERSION = 0` in tests but not clean. Consider: `_run_migrations(conn, db_path, target_version=_DB_TARGET_VERSION)` with an injectable parameter:

```python
def _run_migrations(conn, db_path, *, target_version=_DB_TARGET_VERSION):
```

**[start.py +11–14] `importlib` and `subprocess` now module-level — improved testability**
Severity: POSITIVE

The M-07 change of moving `import subprocess` to module level is explicitly motivated by test patchability (`monkey-patch subprocess.run`). This is correct and improves testability. APPROVE.

---

## Summary of Issues

| ID | File | Line | Severity | Description |
|---|---|---|---|---|
| C-01 | db.py | +808 | MEDIUM | f-string PRAGMA interpolation — needs `{version:d}` + comment |
| C-02 | db.py | +990–1010 | MEDIUM | `sessions.expires_at` type not verified — may silently prune nothing |
| C-03 | db.py | +765–790 | LOW | No post-backup integrity check |
| C-04 | db.py | +780 | LOW | Date-only backup filename — same-day overwrites |
| C-05 | db.py | +795–806 | MEDIUM | BEGIN EXCLUSIVE without in_transaction guard (latent) |
| C-06 | db.py | +942–980 | LOW | No max-iteration guard in prune loops |
| C-07 | db.py | +940 | LOW | `≤ 0` retention config silently falls back (UX confusion) |
| C-08 | start.py | +75 | LOW | Package name not validated as identifier before script join |
| T-01 | db.py | +72–81 | LOW | `_db_init_lock` not injectable/resettable for tests |
| T-02 | db.py | +835 | LOW | `_DB_TARGET_VERSION` not injectable in `_run_migrations` |

**C-01, C-02, C-05 must be resolved before merge (MEDIUM). Others are nits/lows.**

---

*Reviewed by: Sonnet (Claude Sonnet 4.6) — correctness, edge cases, testability*
