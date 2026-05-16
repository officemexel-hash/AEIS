# Gemini — I/O Benchmark: SYLION v5.9.0

**Perspective:** SQLite I/O — WAL reads, `prune_audit_log` batch behavior, index adequacy  
**Measured:** WAL mode config, prune throughput, PRAGMA index_list across all tables  
**Environment:** Python 3.12.8, SQLite (bundled), fresh tmpfile DB + production DB  
**Methodology:** Fresh DB seeded with 5500 rows (5000 old/prunable + 500 new), real `prune_audit_log()` call  

---

## 1. SQLite WAL Configuration

| PRAGMA | Value | Assessment |
|---|---|---|
| `journal_mode` | `wal` | ✅ WAL enabled (set in `get_conn()`) |
| `synchronous` | `2` (FULL) | ✅ Durability ensured |
| `page_size` | `4096` bytes | ✅ Standard, cache-aligned |
| `cache_size` | `-2000` (2 MB) | ✅ Default; adequate for small dashboard DB |

WAL mode is correctly applied on every connection in `get_conn()` via `conn.execute("PRAGMA journal_mode=WAL")`. All reads are non-blocking (WAL allows concurrent readers + 1 writer).

---

## 2. `prune_audit_log` — Batch 1000 rows/tx

### Setup

| Parameter | Value |
|---|---|
| Rows seeded (old, prunable) | 5000 |
| Rows seeded (recent, kept) | 500 |
| Retention config (`AUDIT_LOG_RETENTION_DAYS`) | 365 days |
| Old row age | 400 days (> 365 threshold) |

### Results

| Metric | Value |
|---|---|
| Rows before prune | 5500 |
| Rows deleted | 5000 |
| Rows after prune | 500 (correct — only recent rows remain) |
| Prune total time | **5.11 ms** |
| Batches executed | 5 × 1000 rows |
| Throughput | **979 rows/ms** |

### Batch behavior analysis

```sql
-- Each batch iteration executes:
DELETE FROM audit_log WHERE id IN
  (SELECT id FROM audit_log WHERE ts < ? LIMIT 1000)
-- followed by: conn.commit()
```

5 batches × 1000 rows = 5000 rows deleted in 5.11 ms total. Each batch gets its own transaction and `COMMIT`, preventing long WAL frames that would stall concurrent readers. **The 1000 rows/tx limit is appropriate and working correctly.**

| Batch | Expected rows | Cumulative |
|---|---|---|
| 1 | 1000 | 1000 |
| 2 | 1000 | 2000 |
| 3 | 1000 | 3000 |
| 4 | 1000 | 4000 |
| 5 | 1000 | 5000 |

---

## 3. Index Analysis (PRAGMA index_list)

### Tables with explicit performance indexes

| Table | Index Name | Columns | Unique | Assessment |
|---|---|---|---|---|
| `audit_log` | `sqlite_autoindex_audit_log_1` | `id` | YES | ⚠️ PK only — no `ts` index |
| `cost_log` | `idx_cost_log_ts` | `ts` | NO | ✅ Good — time-range queries |
| `cost_log` | `idx_cost_log_agent` | `agent_id` | NO | ✅ Good |
| `cost_log` | `idx_cost_log_run` | `run_id` | NO | ✅ Good |
| `cost_log` | `idx_cost_log_model` | `model_id` | NO | ✅ Good |
| `event_stream` | `idx_event_stream_ts` | `ts` | NO | ✅ Good — SSE polling |
| `event_stream` | `idx_event_stream_channel_id` | `channel`, `id` | NO | ✅ Good |
| `sessions` | `sqlite_autoindex_sessions_2` | `token` | YES | ✅ Auth lookup fast |
| `code_versions` | `idx_code_versions_at` | `created_at` | NO | ✅ Good |
| `upload_history` | `idx_upload_history_at` | `uploaded_at` | NO | ✅ Good |
| `upload_history` | `idx_upload_history_sha256` | `sha256` | NO | ✅ Dedup fast |

### Tables WITHOUT indexes (no explicit index beyond PK)

| Table | Risk | Query pattern |
|---|---|---|
| `audit_log` | ⚠️ **MISSING `ts` INDEX** | `prune_audit_log` does `WHERE ts < ?` FULL SCAN |
| `streaming_metrics` | LOW | Small table, no time queries |
| `sqlite_sequence` | N/A | System table |

### Critical finding: `audit_log` missing `ts` index

The `prune_audit_log` query pattern is:
```sql
SELECT id FROM audit_log WHERE ts < ? LIMIT 1000
```

Without an index on `ts`, this is a **full table scan** on every batch iteration. With 5000 rows this is fast (5.11 ms total), but at production scale (millions of audit events) performance will degrade linearly.

**Recommended addition:**
```sql
CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts);
```

This index would reduce each `prune_audit_log` batch from O(n) to O(log n + 1000).

---

## 4. WAL Checkpoint

After prune benchmark:

| Metric | Value |
|---|---|
| WAL file exists | YES |
| WAL file size | 1021 KB |
| Checkpoint result (PASSIVE) | rc=0, 254 frames logged, 254 checkpointed |

WAL checkpoint completed successfully — no stuck frames, clean state.

---

## Regression Assessment

| Metric | Status | Notes |
|---|---|---|
| WAL mode enabled | ✅ OK | Correctly set in `get_conn()` |
| `prune_audit_log` correctness | ✅ OK | 5000 rows deleted, 500 retained — exact |
| `prune_audit_log` throughput | ✅ OK | 979 rows/ms, 5 batches of 1000 |
| Batch atomicity | ✅ OK | Each 1000-row batch committed independently |
| `audit_log.ts` index | ⚠️ MISSING | Not a regression (was missing before), but should be added |
| Overall index coverage | ✅ OK | High-traffic tables (`cost_log`, `event_stream`, `sessions`) well-indexed |

**Verdict: NO PERFORMANCE REGRESSIONS detected in I/O layer. One pre-existing gap: missing `ts` index on `audit_log` causes full scans in `prune_audit_log`. Recommend adding `idx_audit_log_ts` in next migration.**
