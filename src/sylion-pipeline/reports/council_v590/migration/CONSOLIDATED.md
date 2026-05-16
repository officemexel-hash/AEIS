# Migration Council v590 — CONSOLIDATED REPORT
## SYLION v5.9.0 — M-02 Framework Verification

**Date:** 2026-04-18  
**Version under test:** 5.9.0 (`dashboard/db.py`, M-02 migration framework)  
**Framework:** `_run_migrations`, `_migration_0_to_1`, `PRAGMA user_version`, `_db_init_lock`, M-08 backup  
**Council members:** Opus (shadow DB), Sonnet (rollback plan), GPT-5.4 (idempotency), Gemini (concurrency)

---

## FINAL VERDICT

# ✅ GO-WITH-WARNINGS

The M-02 migration framework is **production-ready** for the v5.8.x → v5.9.0 upgrade path. Two low-severity warnings are noted; neither blocks deployment.

---

## Council Matrix — All Tests

| Test | Model | Result | Issues |
|---|---|---|---|
| Shadow DB migration | Opus | ✅ PASS | ⚠️ config column gap (LOW) |
| Rollback plan | Sonnet | ✅ COMPLETE | — |
| Idempotency (5× init_db) | GPT-5.4 | ✅ PASS | ⚠️ _seed_admin re-runs (LOW) |
| Concurrency (10 threads) | Gemini | ✅ PASS | ⚠️ multi-process theoretical (THEORETICAL) |

---

## Test Results Detail

### 1. Shadow DB Test (Opus)

**Setup:** Pre-v5.9.0 schema simulated — 7 core tables with missing Phase 2/3 columns  
**Pre-seeded:** 7 rows across config, prompts, runs, human_gate, baselines, baseline_history, model_registry

| Check | Result |
|---|---|
| user_version: 0 → 1 | ✅ |
| All 7 pre-existing rows survived | ✅ |
| 24 columns added by _migration_0_to_1 | ✅ (24/24) |
| M-08 backup created before migration | ✅ |
| F-04 path traversal guard active | ✅ |
| `config` bare-schema gap | ⚠️ LOW |

**Finding (Opus-W1):** `_migration_0_to_1` does not add missing columns to `config`. A DB with only `(key, value)` in config causes `_seed_admin()` to fail post-migration. **This does not affect real v5.8.x upgrades** — all v5.8.x DBs have the full config schema. Only affects synthetic/hand-crafted bare DBs.

### 2. Rollback Plan (Sonnet)

**Deliverable:** `/home/user/workspace/SYLION_v590_work/sylion-pipeline/docs/ROLLBACK_PLAN.md`

Three rollback options documented:
- **Option A (full):** Restore M-08 backup + revert code — for corrupt DB
- **Option B (code-only):** Revert code, keep migrated DB — for app-layer bugs  
- **Option C (targeted):** SQL fix — for seeding issues

All options confirmed safe due to additive-only migration design. RTO estimates: < 2 min (Option A), < 1 min (Option B).

### 3. Idempotency Test (GPT-5.4)

**5 sequential `init_db()` runs on identical DB:**

| Metric | All 5 runs | Result |
|---|---|---|
| user_version | 1 | ✅ Stable |
| config rows | 27 | ✅ No growth |
| agents rows | 48 | ✅ No growth |
| prompts rows | 48 | ✅ No growth |
| model_registry rows | 17 | ✅ No growth |
| Duplicates (all tables) | 0 | ✅ |

**Finding (GPT54-W1):** `_seed_admin()` runs every `init_db()` when no users exist (guard is on `users` count, which stays 0). Each run generates a new setup token. Cosmetic/noisy, not a data issue. `INSERT OR REPLACE` ensures only one `setup_token` row in config.

### 4. Concurrency Test (Gemini)

**10 simultaneous `init_db()` via `threading.Barrier(10)`:**

| Metric | Result |
|---|---|
| Threads completed | 10/10 ✅ |
| Threads errored | 0 ✅ |
| Deadlock detected | None ✅ |
| user_version post-test | 1 ✅ |
| PRAGMA integrity_check | ok ✅ |
| Duplicate rows | 0 ✅ |
| M-08 backups created | 1 (migration ran exactly once) ✅ |
| _db_init_lock type | threading.Lock ✅ |

**Finding (Gemini-W1):** Lock is process-scoped only. Multi-process (uvicorn `--workers N`) could theoretically allow concurrent fresh-start migrations. `BEGIN EXCLUSIVE` + `PRAGMA user_version` check + `INSERT OR IGNORE` make this safe but not lock-serialized at the Python level across processes. **Theoretical only — current deployment is single-process.**

---

## Warnings Summary

| ID | Severity | Source | Description | Action |
|---|---|---|---|---|
| W1 | LOW | Opus | `config` table not covered by migration backfill | Add defensive `ALTER TABLE config ADD COLUMN` guards to `_migration_0_to_1`, or document minimum supported upgrade version |
| W2 | LOW | GPT-5.4 | `_seed_admin()` runs every `init_db()` when users=0 | Add `setup_token` existence check as secondary guard |
| W3 | THEORETICAL | Gemini | Multi-process startup race on `_db_init_lock` | Already mitigated by `BEGIN EXCLUSIVE` + `user_version` + `INSERT OR IGNORE`; document for future multi-worker config |

**None of the above block the GO verdict for the v5.8.x → v5.9.0 upgrade.**

---

## Migration Framework Assessment

### Strengths
1. **Versioned schema tracking** — `PRAGMA user_version` provides reliable, atomic version tracking
2. **WAL-safe backup** — M-08 online backup runs before first migration; F-04 prevents path traversal
3. **Idempotent column additions** — `PRAGMA table_info` checks prevent duplicate `ALTER TABLE`
4. **Transaction safety** — `BEGIN EXCLUSIVE` wraps each migration step
5. **Rollback on failure** — `conn.rollback()` in exception handler reverts partial migrations
6. **Thread safety** — `_db_init_lock` serializes startup races within a process
7. **Downgrade refusal** — `user_version > target` raises `RuntimeError`, prevents accidental downgrades

### Gaps (for future migrations)
1. `config` column backfill missing from `_migration_0_to_1`
2. No cross-process migration lock (acceptable for current deployment model)
3. `_seed_admin` guard could be tightened

---

## Files Written

| File | Description |
|---|---|
| `/home/user/workspace/council/v590/migration/opus.md` | Shadow DB test report |
| `/home/user/workspace/council/v590/migration/sonnet.md` | Rollback plan report |
| `/home/user/workspace/council/v590/migration/gpt54.md` | Idempotency test report |
| `/home/user/workspace/council/v590/migration/gemini.md` | Concurrency test report |
| `/home/user/workspace/council/v590/migration/CONSOLIDATED.md` | This document |
| `/home/user/workspace/SYLION_v590_work/sylion-pipeline/docs/ROLLBACK_PLAN.md` | Operator rollback runbook |

---

## Decision

**MIGRATION COUNCIL VERDICT: GO-WITH-WARNINGS**

The M-02 framework (`_run_migrations`, `_migration_0_to_1`, `PRAGMA user_version`) is approved for production deployment of SYLION v5.9.0. The three warnings are low-severity and do not affect the v5.8.x → v5.9.0 upgrade path in the current deployment environment.

Recommended follow-up actions (post-deploy, not blocking):
1. Add `config` column backfill guards to `_migration_0_to_1`
2. Tighten `_seed_admin` guard with `setup_token` key check
3. Document multi-process migration behavior in ADR

---

*Migration Council v590 — Signed off 2026-04-18*
