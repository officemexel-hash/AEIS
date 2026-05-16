# ADR-0011: PRAGMA WAL and foreign_keys Cached Once Per Process

**Status:** Accepted
**Date:** 2026-04-19
**Author:** performance-profiler-council (v5.9.1 re-audit)

## Context

Finding CRIT-01 (P0-5) identified that `dashboard/db.py:get_conn()` issued two PRAGMA statements on every new SQLite connection:
```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```
py-spy profiling showed that `get_conn()` was invoked 137 times per composite API request, and each call paid the ~0.667 ms PRAGMA round-trip overhead. Total overhead: approximately 91 ms per request, consuming 11–18% of total request latency measured under load.

These two PRAGMAs are idempotent per process — WAL mode persists at the file level and `foreign_keys` defaults are connection-scoped but never changed between calls. Repeating them on every connection is pure overhead.

Options considered:
- **P1** — Keep per-connection PRAGMA (status quo — rejected)
- **P2** — Set PRAGMAs once per process using a module-level `_PRAGMA_APPLIED` boolean flag (chosen)
- **P3** — SQLite connection pool with pre-warmed connections (over-engineered for single-user app)
- **P4** — Remove `foreign_keys=ON` entirely (unsafe — allows orphaned rows)

## Decision

Introduce a module-level flag `_PRAGMA_APPLIED = False` in `db.py`. The first call to `get_conn()` applies both PRAGMAs and sets `_PRAGMA_APPLIED = True`. All subsequent calls skip the PRAGMA block. A `threading.Lock` guards the flag update to prevent a race on startup when multiple threads call `get_conn()` simultaneously.

```python
_PRAGMA_LOCK = threading.Lock()
_PRAGMA_APPLIED = False

def _apply_pragma_once(conn):
    global _PRAGMA_APPLIED
    if not _PRAGMA_APPLIED:
        with _PRAGMA_LOCK:
            if not _PRAGMA_APPLIED:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")
                _PRAGMA_APPLIED = True
```

## Consequences

### Positive
- Eliminates ~91 ms of PRAGMA overhead per composite request — validated by re-running the py-spy profile after the patch.
- No semantic change: WAL mode and foreign key enforcement remain in effect throughout the process lifetime.

### Negative
- If the application ever opens connections to multiple SQLite files within the same process (e.g., a separate test database), the `_PRAGMA_APPLIED` flag would skip PRAGMAs for the second file. Currently this does not occur, but future multi-database scenarios require revisiting this pattern.

### Neutral
- The fix is isolated to `db.py`; no changes to callers of `get_conn()` are required.

## Alternatives Considered

- **P3 (connection pool)**: Would require a thread-local pool implementation and is disproportionate for a single-user local pipeline.
- **P4 (remove foreign_keys)**: Rejected — `foreign_keys=ON` is a correctness guarantee, not a performance knob.

## References

- `dashboard/db.py` — `get_conn()`, `_PRAGMA_APPLIED`, `_PRAGMA_LOCK`
- py-spy profile output in `reports/perf/crit01_pragma_profile.txt`
- Finding CRIT-01 in `FINDINGS_MATRIX_v591.md`
