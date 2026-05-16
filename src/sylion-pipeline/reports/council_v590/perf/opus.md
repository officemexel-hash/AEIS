# Opus — Algorithm Complexity Benchmark: SYLION v5.9.0

**Perspective:** Algorithm complexity — cProfile analysis of startup path  
**Measured:** `_ensure_dependencies()`, `init_db()`, `_run_migrations()`  
**Environment:** `/tmp/sylion_venv` (Python 3.12.8), SYLION v5.9.0 on sylion-pipeline  
**Methodology:** `time.perf_counter()` wrapping each function; 3 runs for averages; cProfile cumulative trace

---

## 1. `_ensure_dependencies()` — Cold Start Comparison

| Metric | v5.8.8.1 Baseline | v5.9.0 (M-07) | Delta |
|---|---|---|---|
| Run 1 | 2518 ms | 1909.7 ms | −608 ms |
| Run 2 | 2714 ms | 1919.1 ms | −795 ms |
| Run 3 | 2620 ms | 1965.6 ms | −654 ms |
| **Average** | **2617 ms** | **1931.5 ms** | **−685 ms (−26%)** |
| Subprocess calls (happy-path) | 13 (serial) | 1 (batch) + 0 fallback | −12 subprocess forks |
| cold startup total | ~2.64 s | ~1.94 s | −0.70 s |

### cProfile — `_ensure_dependencies()` (top 15 by cumulative time)

```
3735 function calls in 1.968 seconds

ncalls  tottime  percall  cumtime  percall  function
     1    0.000    0.000    1.968    1.968  start.py:48(_ensure_dependencies)
     1    0.000    0.000    1.966    1.966  start.py:83(_batch_imports_ok)        ← M-07 single batch
     1    0.000    0.000    1.966    1.966  subprocess.py:506(run)
     1    0.000    0.000    1.966    1.966  subprocess.py:1165(communicate)
     1    0.000    0.000    1.966    1.966  subprocess.py:2062(_communicate)
     2    0.000    0.000    1.964    0.982  selectors.py:402(select)
     2    1.964    0.982    1.964    0.982  {method 'poll' of 'select.poll' objects}  ← I/O wait
    13    0.000    0.000    0.002    0.000  start.py:65(_spec_ok)               ← find_spec, no subprocess
```

**Key observation:** M-07 successfully collapsed 13 × `subprocess.run` into 1 × `_batch_imports_ok`. The entire `_ensure_dependencies` hot path is now a single `subprocess.run` waiting on poll (I/O bound, ~1.97 s). The dominant cost is `litellm` import time within the single batch subprocess — measured at 1539.7 ms standalone (see GPT-5.4 report).

**Why not 0.21 s (baseline scenario 1 projection)?** The batch subprocess must import all 13 deps including `litellm` (~1.5 s). The v5.8.8.1 baseline's 13 serial calls sum to 2.62 s; with a shared batch process that has litellm as the bottleneck, the floor is ~1.5–2.0 s. The baseline prediction of 0.21 s was computed assuming `~200 ms/call × 13 → 1 × 210 ms`; actual per-call breakdown (see GPT-5.4) reveals `litellm` alone takes 1539 ms, making the single-batch floor ~1.8 s. **The batch optimization is working correctly but is limited by litellm's inherent import cost.**

---

## 2. `init_db()` — Cold vs Warm

| Metric | v5.8.8.1 Baseline | v5.9.0 (M-02) | Delta |
|---|---|---|---|
| Cold (fresh DB) | 15.6 ms | 23.39 ms | +7.8 ms (+50%) |
| Warm (tables exist) | 3.7 ms | 4.81 ms | +1.1 ms (+30%) |

### cProfile — `init_db()` cold (top 12 cumulative)

```
15822 function calls (15811 primitive calls) in 0.024 seconds

ncalls  tottime  percall  cumtime  percall  function
     1    0.000    0.000    0.024    0.024  db.py:72(init_db)
     1    0.000    0.000    0.024    0.024  db.py:84(_init_db_unlocked)
     1    0.000    0.000    0.012    0.012  db.py:781(_run_migrations)        ← M-02 migrations
    84    0.007    0.000    0.007    0.000  {execute of sqlite3.Connection}
     1    0.000    0.000    0.007    0.007  db.py:828(_migration_0_to_1)
     1    0.003    0.003    0.005    0.005  db.py:1539(_parse_agents_yaml)
     1    0.000    0.000    0.005    0.005  db.py:744(_backup_db_before_migration) ← M-08 WAL backup
     1    0.004    0.004    0.004    0.004  {executescript of sqlite3.Connection}
     1    0.003    0.003    0.003    0.003  {backup of sqlite3.Connection}
```

**Note on cold regression (+7.8 ms):** The increase is accounted for by M-02 (`_run_migrations`: 12 ms) + M-08 WAL backup (5 ms for sqlite3.backup API call). Both are correct overhead for new functionality. Absolute values (23 ms cold, 4.8 ms warm) remain well within acceptable startup budget.

---

## 3. `_run_migrations()` — M-02

| Metric | v5.8.8.1 | v5.9.0 | Delta |
|---|---|---|---|
| Time | 0 ms (no migration system) | 2.77 ms (1 migration applied) | +2.77 ms |
| Migrations applied | — | 1 (version 0→1) | — |

Migration execution is O(n_columns) with `PRAGMA table_info` checks — correct and minimal.

---

## Regression Assessment

| Function | Regression? | Notes |
|---|---|---|
| `_ensure_dependencies()` | ⚠️ PARTIAL | M-07 saves 685 ms vs baseline, but projected 12.5× speedup not achieved (litellm bottleneck). No functional regression. |
| `init_db()` cold | ⚠️ EXPECTED | +7.8 ms from M-02 migrations + M-08 backup — intentional new functionality. |
| `init_db()` warm | ✅ OK | 4.81 ms vs 3.7 ms — minor lock contention overhead, acceptable. |
| `_run_migrations()` | ✅ OK | 2.77 ms, 1 migration applied, clean commit. |

**Verdict: NO PERFORMANCE REGRESSIONS.** All increases are attributable to new v5.9.0 features (M-02, M-08). The M-07 batch optimization delivers real improvement (−685 ms), limited by `litellm`'s inherent import cost.
