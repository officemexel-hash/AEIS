# GPT-5.4 Council Report — Idempotency Test
## SYLION v5.9.0 — M-02 Framework Verification

**Date:** 2026-04-18  
**Model:** GPT-5.4 (idempotency / math-logic role)  
**Scope:** `init_db()` × 5 sequential runs, `user_version` stability, no duplicates in seed tables

---

## Test Configuration

- **DB:** `/tmp/idempotency_test.db` (fresh, created on first run)
- **Runs:** 5 sequential calls to `db.init_db()`
- **_db_init_lock:** Active (serializes runs even in single-thread context)

---

## Results

### user_version Across 5 Runs

| Run | user_version | Expected |
|---|---|---|
| 1 | 1 | 1 ✅ |
| 2 | 1 | 1 ✅ |
| 3 | 1 | 1 ✅ |
| 4 | 1 | 1 ✅ |
| 5 | 1 | 1 ✅ |

**All 5 runs: user_version = 1. PASS.**

### Seed Table Row Counts (stable across all 5 runs)

| Table | Run 1 | Run 2 | Run 3 | Run 4 | Run 5 |
|---|---|---|---|---|---|
| `config` | 27 | 27 | 27 | 27 | 27 |
| `users` | 0 | 0 | 0 | 0 | 0 |
| `agents` | 48 | 48 | 48 | 48 | 48 |
| `prompts` | 48 | 48 | 48 | 48 | 48 |
| `model_registry` | 17 | 17 | 17 | 17 | 17 |

Row counts are **perfectly stable** across all 5 runs. No accumulation.

### Duplicate Check (final state after 5 runs)

| Table | Duplicates |
|---|---|
| `config` (GROUP BY key) | `[]` ✅ |
| `agents` (GROUP BY id) | `[]` ✅ |
| `prompts` (GROUP BY id) | `[]` ✅ |
| `model_registry` (GROUP BY id) | `[]` ✅ |

**Zero duplicates in any seed table after 5 init_db() calls.**

---

## Idempotency Mechanism Analysis

### Migration (`_run_migrations`)
After run 1 sets `user_version=1`, all subsequent runs hit:
```python
if current == target:
    logger.debug("M-02: DB already at user_version=%d, no migrations", current)
    return 0
```
Migration is skipped on runs 2–5. **Correct.**

### Config seed (`_seed_defaults`)
Guard: `if row["c"] == 0: _seed_defaults(conn)`. After run 1 inserts 27 rows, the guard prevents re-seeding. **Correct.**

### Agents seed (`_seed_agents`)
Uses `INSERT OR IGNORE` keyed on `id`. Even if called every run, no duplicates accumulate. **Correct.**

### Prompts seed (`_seed_prompts`)
Uses `INSERT OR IGNORE` keyed on `id`. Idempotent regardless of call count. **Correct.**

### Models seed (`_seed_models`)
Always runs (`_seed_models(conn)` has no guard). Uses `INSERT OR IGNORE`. No duplicates. **Correct.**

### Admin seed (`_seed_admin`)
Guard: `if row["c"] == 0: _seed_admin(conn)` on `users` table count. Since no users are inserted (only setup token in `config`), `users` count stays 0 and `_seed_admin` **runs every time**. This generates a new setup token on each call.

**Observation:** `_seed_admin` runs 5× because `users` table remains at 0. Each run inserts a new `setup_token` into `config` via `INSERT OR REPLACE`. The result is correct (only one `setup_token` row, always current), but generates 5 console print statements and 5 SETUP_TOKEN.txt writes. This is a cosmetic issue, not a data correctness issue.

---

## Issues Found

### ⚠️ MINOR — _seed_admin runs every init_db() when no users exist

**Behavior:** `_seed_admin()` is guarded by `users` count. Since no real user is created during seeding (only a config token), the guard never suppresses re-runs.

**Impact:** On every `init_db()` call (including re-entrant startup), a new setup token is generated and printed to console. This is **not a security issue** (tokens are hashed, previous token is overwritten) but is noisy and potentially confusing.

**Severity: LOW (cosmetic/UX)**

**Recommendation:** Guard `_seed_admin()` additionally by checking if `setup_token` key exists in `config`:
```python
if conn.execute("SELECT COUNT(*) FROM config WHERE key='setup_token'").fetchone()[0] == 0:
    _seed_admin(conn)
```

---

## Verdict

| Criterion | Result |
|---|---|
| user_version = 1 on all 5 runs | ✅ PASS |
| No new migrations on runs 2–5 | ✅ PASS |
| No duplicates in config | ✅ PASS |
| No duplicates in agents | ✅ PASS |
| No duplicates in prompts | ✅ PASS |
| No duplicates in model_registry | ✅ PASS |
| Row counts stable across all runs | ✅ PASS |
| _seed_admin re-runs when no users | ⚠️ LOW |

**Idempotency Test: GO-WITH-WARNINGS**
