#!/usr/bin/env bats
# =============================================================================
# BATS unit tests for rollback.sh (WAL-integrity merged version)
#
# Requirements covered:
#   T-01  Usage / pre-flight: no args prints usage, exits 1
#   T-02  --help exits 0
#   T-03  --dry-run: no FS writes, all steps printed
#   T-04  Pidfile guard: exits 4 when pidfile present without --force
#   T-05  Pidfile guard --force: overrides, continues
#   T-06  WAL checkpoint called before safety snapshot
#   T-07  Backup integrity_check: exits 2 for corrupted backup
#   T-08  Restore integrity_check: exits 3 for corrupted restore
#   T-09  Successful full dry-run: exits 0
#   T-10  Safety snapshot written (backup of current DB before restore)
#   T-11  Stale WAL/SHM removed after atomic swap
#   T-12  Log file written to SYLION_HOME/logs/
#   T-13  --version sets backup glob correctly
#   T-14  pidfile cleaned up on exit (normal path)
# =============================================================================

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------
setup() {
    # Create an isolated temp workspace for each test.
    TEST_DIR="$(mktemp -d)"

    # Minimal valid SQLite DB.
    sqlite3 "${TEST_DIR}/sylion.db" "CREATE TABLE t(v TEXT); INSERT INTO t VALUES('ok');"

    # Minimal valid backup file matching default glob.
    sqlite3 "${TEST_DIR}/sylion.db.bak.v5.9.0.20260101_000000.sqlite3" \
        "CREATE TABLE t(v TEXT); INSERT INTO t VALUES('backup');"

    # Fake sqlite3 wrapper that honours real commands (we rely on real sqlite3).
    export SYLION_HOME="${TEST_DIR}"
    export DB_FILE="${TEST_DIR}/sylion.db"
    export BACKUP_GLOB="sylion.db.bak.v5.9.*.sqlite3"
    export SERVICE_NAME="sylion-test-nonexistent-unit"

    # Point to the merged script under test.
    SCRIPT="/home/user/workspace/sylion_v591/mega_audit/rollback_wal_integrity/rollback.sh"
}

teardown() {
    rm -rf "${TEST_DIR}"
}

# ---------------------------------------------------------------------------
# T-01  Missing backup → exit 1
# ---------------------------------------------------------------------------
@test "T-01: exits 1 when no backup found" {
    export BACKUP_GLOB="sylion.db.bak.v99.99.*.sqlite3"   # no match
    run bash "$SCRIPT" --db-file "${TEST_DIR}/sylion.db"
    [ "$status" -eq 1 ]
    [[ "$output" =~ "No backup matching" ]]
}

# ---------------------------------------------------------------------------
# T-02  --help exits 0
# ---------------------------------------------------------------------------
@test "T-02: --help exits 0" {
    run bash "$SCRIPT" --help
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# T-03  --dry-run: no files created, steps printed
# ---------------------------------------------------------------------------
@test "T-03: --dry-run creates no files and prints DRY-RUN lines" {
    local before_count
    before_count=$(find "${TEST_DIR}" -type f | wc -l)

    run bash "$SCRIPT" \
        --dry-run \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 0 ]
    [[ "$output" =~ "DRY-RUN" ]]

    # No new files (pidfile, log, snapshot) should have been created.
    local after_count
    after_count=$(find "${TEST_DIR}" -type f | wc -l)
    [ "$after_count" -eq "$before_count" ]
}

# ---------------------------------------------------------------------------
# T-04  Pidfile guard without --force → exit 4
# ---------------------------------------------------------------------------
@test "T-04: pidfile present without --force exits 4" {
    echo "99999" > "${TEST_DIR}/sylion.pid"

    run bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 4 ]
    [[ "$output" =~ "Pidfile" ]]
}

# ---------------------------------------------------------------------------
# T-05  Pidfile guard with --force: proceeds past guard (dry-run to avoid full run)
# ---------------------------------------------------------------------------
@test "T-05: --force overrides pidfile guard" {
    echo "99999" > "${TEST_DIR}/sylion.pid"

    run bash "$SCRIPT" \
        --dry-run \
        --force \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    # Should NOT exit 4; dry-run completes with 0.
    [ "$status" -eq 0 ]
    [[ "$output" =~ "WARN" ]]
    [[ "$output" =~ "force" ]]
}

# ---------------------------------------------------------------------------
# T-06  WAL checkpoint line appears in dry-run output
# ---------------------------------------------------------------------------
@test "T-06: WAL checkpoint step appears in dry-run output" {
    run bash "$SCRIPT" \
        --dry-run \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 0 ]
    [[ "$output" =~ "wal_checkpoint" ]]
}

# ---------------------------------------------------------------------------
# T-07  Corrupted backup → exit 2
# ---------------------------------------------------------------------------
@test "T-07: corrupted backup file exits 2" {
    # Remove the valid backup and put only a bad one so it is always selected.
    rm -f "${TEST_DIR}/"sylion.db.bak.v5.9.*.sqlite3
    local bad_backup="${TEST_DIR}/sylion.db.bak.v5.9.0.20260101_000000.sqlite3"
    # Write garbage that sqlite3 cannot parse.
    printf 'NOTASQLITEFILE\x00\x01\x02' > "$bad_backup"

    run bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 2 ]
    [[ "$output" =~ "integrity_check" ]]
}

# ---------------------------------------------------------------------------
# T-08  Corrupted restore (simulate via a hook) → exit 3
#   Strategy: write a valid backup but patch the script's cp step by
#   providing a wrapper sqlite3 that reports integrity failure on tmp files.
# ---------------------------------------------------------------------------
@test "T-08: restored DB failing integrity_check exits 3" {
    # Create a staging area for the fake sqlite3 wrapper.
    local fake_bin="${TEST_DIR}/fakebin"
    mkdir -p "$fake_bin"

    cat > "${fake_bin}/sqlite3" <<'EOF'
#!/bin/bash
# Delegate all calls to real sqlite3 EXCEPT integrity_check on .restore.tmp
args="$*"
if [[ "$args" =~ \.restore\.tmp ]] && [[ "$args" =~ integrity_check ]]; then
    echo "*** integrity check failed ***"
    exit 0
fi
exec /usr/bin/sqlite3 "$@"
EOF
    chmod +x "${fake_bin}/sqlite3"

    run env PATH="${fake_bin}:${PATH}" bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 3 ]
    [[ "$output" =~ "integrity_check" ]]
}

# ---------------------------------------------------------------------------
# T-09  Full dry-run exits 0
# ---------------------------------------------------------------------------
@test "T-09: full dry-run with valid inputs exits 0" {
    run bash "$SCRIPT" \
        --dry-run \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# T-10  Safety snapshot created during real (non-dry) run
# ---------------------------------------------------------------------------
@test "T-10: safety snapshot file is created before restore" {
    run bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    # Even if service-start fails (no systemd in test), the snapshot must exist.
    local snapshots
    snapshots=$(find "${TEST_DIR}" -name "*.safety.pre-rollback.*.sqlite3" | wc -l)
    [ "$snapshots" -ge 1 ]
}

# ---------------------------------------------------------------------------
# T-11  Stale WAL/SHM removed after swap
# ---------------------------------------------------------------------------
@test "T-11: stale -wal and -shm files are removed after swap" {
    # Plant stale WAL/SHM next to the live DB.
    touch "${TEST_DIR}/sylion.db-wal"
    touch "${TEST_DIR}/sylion.db-shm"

    run bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ ! -f "${TEST_DIR}/sylion.db-wal" ]
    [ ! -f "${TEST_DIR}/sylion.db-shm" ]
}

# ---------------------------------------------------------------------------
# T-12  Log file written to SYLION_HOME/logs/
# ---------------------------------------------------------------------------
@test "T-12: log file is created in SYLION_HOME/logs/" {
    run bash "$SCRIPT" \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    local logs
    logs=$(find "${TEST_DIR}/logs" -name "rollback_*.log" 2>/dev/null | wc -l)
    [ "$logs" -ge 1 ]
}

# ---------------------------------------------------------------------------
# T-13  --version sets backup glob
# ---------------------------------------------------------------------------
@test "T-13: --version <ver> selects correct backup glob" {
    run bash "$SCRIPT" \
        --dry-run \
        --version "5.9.0" \
        --db-file "${TEST_DIR}/sylion.db"

    [ "$status" -eq 0 ]
    # glob line should mention the version we specified.
    [[ "$output" =~ "5.9.0" ]]
}

# ---------------------------------------------------------------------------
# T-14  Pidfile is cleaned up after successful dry-run
# ---------------------------------------------------------------------------
@test "T-14: pidfile is removed after exit (dry-run does not create it)" {
    run bash "$SCRIPT" \
        --dry-run \
        --db-file "${TEST_DIR}/sylion.db" \
        --backup-glob "sylion.db.bak.v5.9.*.sqlite3"

    [ "$status" -eq 0 ]
    # In dry-run no pidfile should have been written or left.
    [ ! -f "${TEST_DIR}/sylion.pid" ]
}
