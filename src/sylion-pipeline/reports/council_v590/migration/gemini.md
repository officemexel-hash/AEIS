# Gemini Council Report — Concurrency Test
## SYLION v5.9.0 — M-02 Framework Verification

**Date:** 2026-04-18  
**Model:** Gemini 3.1 Pro (concurrency role)  
**Scope:** 10 simultaneous `init_db()` threads, `_db_init_lock` correctness, migration applied exactly once, no corrupt state

---

## Test Configuration

- **DB:** `/tmp/concurrency_test.db` (fresh, no prior state)
- **Threads:** 10 concurrent `threading.Thread` instances
- **Synchronization:** `threading.Barrier(10)` — all 10 threads wait at barrier before simultaneously calling `init_db()`
- **_db_init_lock:** `threading.Lock()` in `db.py` module scope (not reentrant)

---

## Results

### Thread Completion

| Metric | Result |
|---|---|
| Threads launched | 10 |
| Threads succeeded | 10/10 ✅ |
| Threads errored | 0 ✅ |
| Elapsed time | 0.06s |
| Deadlock detected | None ✅ |

All 10 threads completed successfully. No hangs, no exceptions.

### Post-Concurrency DB State

| Check | Result |
|---|---|
| `PRAGMA user_version` | `1` ✅ |
| `PRAGMA integrity_check` | `ok` ✅ |
| `config` row count | `27` ✅ |
| `agents` row count | `48` ✅ |
| `prompts` row count | `48` ✅ |
| `config` duplicates | `[]` ✅ |
| `agents` duplicates | `[]` ✅ |
| `prompts` duplicates | `[]` ✅ |

### Migration Application Count

- **M-08 backup files created:** 1 (exactly one backup, proving migration ran exactly once)
- **_db_init_lock type:** `thread.lock` (stdlib `threading.Lock`, not `RLock`)
- **Migration applied:** 1 time (subsequent 9 threads found `user_version=1`, skipped)

---

## Lock Behavior Analysis

### `_db_init_lock` Implementation

```python
# db.py line 44
_db_init_lock = threading.Lock()

def init_db(conn=None):
    with _db_init_lock:
        return _init_db_unlocked(conn)
```

**Analysis:**
1. First thread to acquire the lock runs `_init_db_unlocked()` completely — creates tables, runs migration (`user_version: 0→1`), seeds data, commits.
2. Remaining 9 threads queue on the lock. When each acquires it:
   - `_run_migrations()` reads `user_version=1` → matches target → returns 0 (no-op)
   - Seed guards (`if count == 0`) fire correctly — prevent re-seeding
3. Lock is released cleanly after each thread completes.

**No TOCTOU (time-of-check/time-of-use) race detected.** The lock covers the entire read→migrate→seed→commit sequence.

### SQLite WAL Mode Interaction

`PRAGMA journal_mode=WAL` is set on every connection in `get_conn()`. Under WAL:
- Multiple readers can proceed concurrently
- Writers are serialized by SQLite's internal WAL writer lock
- `_db_init_lock` in Python provides an additional advisory layer above SQLite's locking — ensures the migrate→seed sequence is atomic at the application level, not just at the SQLite level

**This is the correct defense-in-depth approach.** SQLite WAL alone would prevent DB corruption, but would not prevent double-seeding. The Python lock prevents both.

### BEGIN EXCLUSIVE in _run_migrations

```python
conn.execute("BEGIN EXCLUSIVE")
```

This takes an exclusive write lock on the SQLite file during migration, blocking any concurrent write attempts at the DB level as well. Combined with `_db_init_lock` at the Python level, migration atomicity is doubly guaranteed.

---

## Issues Found

None. The `_db_init_lock` mechanism functions correctly under 10-thread concurrent load.

### Notable Observation — Lock Scope

`_db_init_lock` is module-level. This means it serializes `init_db()` calls **within the same process** only. In a multi-process deployment (multiple uvicorn worker processes via `--workers N`), each process has its own lock instance. SQLite's WAL writer lock + `BEGIN EXCLUSIVE` in `_run_migrations` prevents corruption across processes, but double-seeding at the process level is theoretically possible if two fresh processes start simultaneously with an empty DB.

**Severity: THEORETICAL** — In practice, `INSERT OR IGNORE` guards in all seed functions make cross-process double-seeding benign (no data corruption, only extra DB writes). `PRAGMA user_version` ensures migration runs once even across processes.

---

## Verdict

| Criterion | Result |
|---|---|
| 10/10 threads completed | ✅ PASS |
| user_version = 1 (not incremented multiple times) | ✅ PASS |
| DB integrity_check = ok | ✅ PASS |
| Zero duplicate rows | ✅ PASS |
| Migration applied exactly once (1 backup file) | ✅ PASS |
| No deadlock or thread starvation | ✅ PASS |
| Lock type correct (non-reentrant threading.Lock) | ✅ PASS |
| Multi-process theoretical gap | ⚠️ THEORETICAL |

**Concurrency Test: GO**  
(The multi-process theoretical gap is acceptable for the current single-process uvicorn deployment model. Document for future multi-worker consideration.)
