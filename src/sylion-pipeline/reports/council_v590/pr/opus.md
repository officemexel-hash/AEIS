# PR Review — Opus (Architecture, Design, Breaking API Changes)
## SYLION v5.8.8.1 → v5.9.0 | Reviewer: Claude Opus 4.7

**Verdict: APPROVE-WITH-NITS**

---

## Summary

This PR introduces five cohesive architectural changes: a versioned migration framework (M-02), RODO-compliant data retention (M-03), Pydantic agent validation (M-01), a /api/dashboard query consolidation (M-06), and a batched dependency-check fast path (M-07). The design intent is sound. The public API surface of `db.py` is backward-compatible with the exception of one soft concern noted below.

---

## Inline Comments

### `db.py` — Architecture

**[db.py +39–55] `_db_init_lock` + `_DB_TARGET_VERSION` module-level constants**
Severity: NIT
The thread-level advisory lock correctly serializes `init_db()` across concurrent startup callers. However, the lock comment says "advisory — SQLite itself is safe under WAL", which is accurate for the *storage* layer but undersells the real risk: the `PRAGMA user_version = N` → `conn.commit()` sequence in `_run_migrations` must not interleave. The lock is therefore not advisory in the safety-relevant sense — the docstring should be updated to reflect that the lock is *functional*, not merely advisory, for correctness of the migration state machine.

**[db.py +70–81] `init_db()` delegation pattern**
Severity: NIT
Splitting into `init_db()` (lock wrapper) and `_init_db_unlocked()` is a clean pattern. However, `_init_db_unlocked` is not prefixed with a leading `_` in name only — it remains callable directly from tests, bypassing the lock. Consider whether it should be `__init_db_unlocked` (name-mangled) or whether a module-level `__all__` should exclude it to prevent accidental bypass in integration tests.

**[db.py +741–835] `_run_migrations()` — BEGIN EXCLUSIVE inside a context that may already hold a connection**
Severity: MEDIUM
`_run_migrations` issues `conn.execute("BEGIN EXCLUSIVE")` manually, then calls `conn.commit()` and `conn.rollback()` directly. If `_init_db_unlocked` is called with an externally-supplied `conn` (the `conn` parameter of `init_db`), and that connection already has an open transaction (e.g. from a test fixture), this will raise `sqlite3.OperationalError: cannot start a transaction within a transaction`. The v5.8.x calling convention passed `conn=None` (auto-create own connection) in all production paths, so this is safe today — but the API signature still permits external connections and the combination is a latent footgun. Recommend either: (a) asserting `conn` is freshly opened, or (b) checking `conn.in_transaction` before issuing `BEGIN EXCLUSIVE`.

**[db.py +741] `_run_migrations` raises `RuntimeError` on downgrade**
Severity: DESIGN-NOTE (positive)
The downgrade-refusal guard (`current > target → RuntimeError`) is an excellent design choice. It prevents silent data-format corruption when rolling back the binary. Confirm this exception propagates all the way to the process exit code (it should — FastAPI's lifespan will catch it and abort startup). APPROVE.

**[db.py +770–772] `_backup_db_before_migration` — F-04 path traversal guard**
Severity: DESIGN-NOTE (positive)
`backup_path.resolve().relative_to(backup_dir.resolve())` is the correct TOCTOU-resistant approach for symlink-safe path validation. Confirmed safe. APPROVE.

**[db.py +905–908] `_MIGRATIONS` registry defined *after* `_migration_0_to_1`**
Severity: NIT
The registry is correct (forward-reference not needed in Python for dicts). However, placing `_MIGRATIONS` immediately after `_migration_0_to_1` means future contributors adding `_migration_1_to_2` must remember to (a) define the function before `_MIGRATIONS` and (b) bump `_DB_TARGET_VERSION`. A brief "how to add a migration" comment block at the registry site would reduce future mistakes. Currently the comment at `_DB_TARGET_VERSION` provides partial guidance but is physically distant.

**[db.py +910–940] `AgentSpec` Pydantic model (M-01)**
Severity: NIT
`Optional as Opt` alias is imported at line 20 (`from typing import Optional as Opt`) but `Optional` is *also* imported at line 19 (`from typing import Any, Optional`). This dual-import is redundant and mildly confusing. The alias `Opt` is used only inside `AgentSpec`; consider removing the duplicate `Optional` import or dropping the alias.

**[db.py +980–1038] `prune_audit_log` / `prune_sessions` — batched DELETE**
Severity: DESIGN-NOTE (positive)
Batching deletes at 1000 rows per transaction is correct for long-running WAL databases; unbounded deletes can stall readers for seconds. The `while True: … if deleted < 1000: break` pattern is idiomatic. APPROVE.

**[db.py +980] `prune_audit_log` — `time.time()` vs `datetime`**
Severity: NIT
`datetime` is imported at line 8 but used only in `_backup_db_before_migration` (for `datetime.date.today()`). `prune_audit_log` and `prune_sessions` use `time.time()` for cutoff arithmetic. This is consistent with the existing `prune_event_stream` function (which also uses `time.time()`). No issue — just confirm that `audit_log.ts` and `sessions.expires_at` are stored as Unix float seconds (not ISO strings) — if either column is an ISO datetime string, the `< ?` comparison will silently misbehave.

---

### `app.py` — Architecture

**[app.py +42–46] Import of `prune_audit_log`, `prune_sessions`**
Severity: DESIGN-NOTE (positive)
Clean addition. The `_PRUNE_TASKS` registry pattern (list of `(name, fn)` tuples) is extensible without further code changes. APPROVE.

**[app.py +58] `_PRUNE_INTERVAL_S` comment says "event_stream prune runs"**
Severity: NIT
The comment `# 24 hours between event_stream prune runs` is now stale — the interval governs all three retention tasks. Update to: `# 24 hours between retention prune runs`.

**[app.py +696–755] `/api/dashboard` — M-06 query consolidation**
Severity: DESIGN-NOTE (positive)
Collapsing 15 COUNT queries into 5 is a legitimate performance improvement with a zero-change JSON response shape (as noted in the diff comment "BYTE-IDENTICAL to v5.8.x"). The `COALESCE(status, 'draft')` and `COALESCE(status, 'active')` fallbacks are appropriate for NULL-tolerant GROUP BY. One concern: if a `baselines` or `prompts` row has a `status` value not in `{'draft','review','active'}`, it is silently dropped from `baselines_draft`/`baselines_review` but still counted in `baselines_total` (via `sum(baselines_by_status.values())`). This was true in v5.8.x too (the old queries only counted `draft` and `review` explicitly), so it's not a regression — but it's worth documenting.

**[app.py +129–137] Version bump to 5.9.0**
Severity: DESIGN-NOTE
`SYLION_CODENAME = "Breakthrough — 18 Skills Audit"` — confirm the em-dash character (`—`) is intentional and does not cause issues in environments that parse this string as ASCII (e.g., legacy log shippers). Recommend ASCII dash or escaping if in doubt.

---

### `start.py` — Architecture

**[start.py +42–45] `_BATCH_TIMEOUT = 20`, `_PER_PKG_TIMEOUT = 30`**
Severity: NIT
The `_BATCH_TIMEOUT` of 20s for a combined `import a; import b; … import m` (13 packages including `litellm`) may be too tight on cold CI runners with no pip cache. `litellm` alone can take 8–12s to import on first run in restricted environments. Consider raising to 30s or making it configurable via env var (`SYLION_BATCH_TIMEOUT`).

**[start.py +74–100] `_batch_imports_ok` — fallback on rc!=0 or timeout**
Severity: DESIGN-NOTE (positive)
The two-phase approach (batch fast path → per-package slow path on failure) is well-architected. The comment "safe because names come from our hardcoded `_CRITICAL_DEPS` dict (security3 F-03)" is correct. APPROVE.

**[start.py +106–164] Lockfile install (M-04)**
Severity: MEDIUM
The lockfile path is resolved as `DASHBOARD_DIR.parent / "requirements-lock.txt"`. In containerized deployments where the working directory is remapped or the dashboard is installed as a package (not a git checkout), `DASHBOARD_DIR.parent` may not be the repo root. If `_LOCK` does not exist, the code silently falls through to per-package install, which is the correct graceful degradation. However, if `_LOCK` exists at an unexpected location (e.g., a stale file from a previous deployment), it could install mismatched versions. Recommend adding a `# WARNING: this path is relative to the installed layout` comment and consider an env-var override (`SYLION_LOCKFILE`).

---

## Breaking API Changes Assessment

| Change | Breaking? | Notes |
|---|---|---|
| `init_db()` now acquires `_db_init_lock` | **No** — same signature | Callers passing external `conn` may hit BEGIN EXCLUSIVE conflict (latent, not current) |
| `_migrate_columns()` removed | **Internal only** — not exported | Safe |
| `prune_audit_log`, `prune_sessions` added to `db.py` public API | **Additive** | No breakage |
| `/api/dashboard` JSON response shape | **No change** (BYTE-IDENTICAL per comment) | Verify with integration test |
| `SYLION_VERSION = "5.9.0"` | Version string change | Expected |
| `_MIGRATIONS` + `_DB_TARGET_VERSION` globals | **Internal** | Not part of public API |

**No breaking API changes detected. Architecture is sound with minor nits.**

---

*Reviewed by: Opus (Claude Opus 4.7) — architecture, design, breaking changes*
