# PROD R1 Backup/DR Primitives PASS1/PASS2

Date: 2026-05-18
Roadmap item: `PROD-P0-002 Backup/restore`
Decision pack: `results/decisions/PROD-D4-BACKUP-DR-PRIMITIVES_evidence_pack.json`
Status: `FROZEN_2X` for local backup/restore primitives and RPO/RTO policy validation

## Scope

This freeze covers the operational foundation for backup/DR:

- SQLite online backup for local/dev drill.
- Backup manifest with `backup_id`, source, backup path, SHA256, byte size and retention policy.
- Restore operation into an isolated target path.
- Restore drill with `PRAGMA integrity_check`, source/restored row-count signature and RTO check.
- Backup policy validation:
  - backup interval <= 360 minutes;
  - RPO <= 60 minutes;
  - RTO <= 30 minutes;
  - backup target required;
  - WAL/archive stream required when interval exceeds RPO.

## Files Changed

- `src/sylion-pipeline/sylion/ops/__init__.py`
- `src/sylion-pipeline/sylion/ops/backup_dr.py`
- `src/sylion-pipeline/tests/ops/test_backup_dr.py`

## Verification PASS1

```text
python -m pytest src\sylion-pipeline\tests\ops\test_backup_dr.py -q
5 passed
```

## Verification PASS2

```text
python -m pytest src\sylion-pipeline\tests\ops\test_backup_dr.py -q
5 passed
```

## Boundary

This does not claim a real production PostgreSQL restore drill yet. Remaining work:

- configure real staging PostgreSQL backup target;
- run pg_dump/basebackup/WAL archive restore drill;
- measure RPO/RTO against production-like data;
- attach restore evidence to the final DR runbook.

## Rollback

Rollback strategy is recorded in:

```text
results/decisions/PROD-D4-BACKUP-DR-PRIMITIVES_evidence_pack.json
```

Expected rollback time: 15 minutes.
Data loss risk: `NONE`.
