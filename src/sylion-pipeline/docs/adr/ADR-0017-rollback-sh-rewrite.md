# ADR-0017: rollback.sh Rewritten Using SQLite .backup API

**Status:** Accepted
**Date:** 2026-04-19
**Author:** sre-incident-commander (v5.9.1 re-audit)

## Context

The SRE incident commander audit identified 6 bugs in `rollback.sh` that made it unreliable for production use:

1. **WAL not checkpointed before copy**: `cp sylion.db backup.db` copied the main file without flushing the WAL journal, producing a logically inconsistent backup.
2. **No exclusive lock**: two concurrent rollback attempts would corrupt the backup file.
3. **`cp` not atomic**: a crash mid-copy left a partial backup with no indication of failure.
4. **Hardcoded version string `v5.9.0`**: backup filename was static, not reflecting `CURRENT_VERSION`.
5. **No integrity check post-restore**: `PRAGMA integrity_check` was not run after restoring the backup.
6. **`set -e` absent**: failures in intermediate steps were silently ignored and rollback continued.

The script was the sole documented disaster-recovery tool. Six bugs in a DR script constitute a HIGH operational risk.

Options considered:
- **R1** — Patch individual bugs in existing `cp`-based approach
- **R2** — Rewrite using SQLite `.backup` API via `sqlite3` CLI (chosen)
- **R3** — Rewrite using Python `sqlite3.Connection.backup()` method called from a helper script
- **R4** — Replace rollback with `litestream` replication

## Decision

Rewrite `rollback.sh` using the `sqlite3` CLI `.backup` command, which internally uses the SQLite Online Backup API. This guarantees:

- WAL is fully checkpointed before the backup begins.
- The backup operation is atomic from SQLite's perspective.
- No exclusive filesystem lock is required.

Additional fixes applied:
- `set -euo pipefail` at the top of the script.
- Backup filename uses `${CURRENT_VERSION}` read from the `VERSION` file.
- `PRAGMA integrity_check` run on the restored database; rollback aborts if check returns anything other than `ok`.
- Pidfile guard prevents concurrent rollback executions.

```bash
sqlite3 "${DB_PATH}" ".backup '${BACKUP_PATH}'"
```

## Consequences

### Positive
- All 6 identified bugs resolved. Backup is WAL-safe and atomic.
- Dynamic version label in backup filename enables correct identification in post-incident investigation.

### Negative
- Requires `sqlite3` CLI to be installed on the host (it is not bundled with SYLION). On minimal container images without `sqlite3`, the rollback script fails immediately. The install guide now documents `sqlite3` as a runtime dependency.

### Neutral
- Existing backup files created by the old `cp` approach retain their `.db` extension and are compatible with the new restore procedure.

## Alternatives Considered

- **R3 (Python backup)**: Equivalent SQLite API access; Python is always present. Rejected because shell scripts are easier to run in emergency recovery scenarios where the Python virtualenv may not be activated.
- **R4 (litestream)**: Continuous replication is the correct long-term answer but requires infrastructure changes outside the scope of a patch release.

## References

- `rollback.sh` — rewritten script
- SQLite Online Backup API documentation
- `docs/DISASTER_RECOVERY.md` — updated procedure
- SRE audit findings (sre-incident-commander report, v5.9.1)
- `FINDINGS_MATRIX_v591.md` — rollback.sh 6 bugs (HIGH ops)
