from __future__ import annotations

import json
import sqlite3

from sylion.ops.backup_dr import (
    BackupPolicy,
    create_sqlite_backup,
    restore_sqlite_backup,
    run_sqlite_restore_drill,
    sha256_file,
)


def _seed_db(path):
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, customer_id INTEGER, body TEXT)")
        conn.executemany(
            "INSERT INTO customers (name) VALUES (?)",
            [("Ada",), ("Linus",)],
        )
        conn.executemany(
            "INSERT INTO notes (customer_id, body) VALUES (?, ?)",
            [(1, "first"), (2, "second"), (2, "third")],
        )
        conn.commit()
    finally:
        conn.close()


def test_sqlite_backup_writes_manifest_and_checksum(tmp_path):
    source = tmp_path / "aeis.db"
    _seed_db(source)

    manifest = create_sqlite_backup(source, tmp_path / "backups", backup_id="drill_001")

    assert manifest.backup_id == "drill_001"
    assert manifest.bytes > 0
    assert manifest.sha256 == sha256_file(manifest.backup_path)

    manifest_json = json.loads((tmp_path / "backups" / "drill_001.manifest.json").read_text())
    assert manifest_json["sha256"] == manifest.sha256
    assert manifest_json["retention_policy"] == "production-readiness-local-drill"


def test_sqlite_restore_preserves_rows(tmp_path):
    source = tmp_path / "aeis.db"
    _seed_db(source)
    manifest = create_sqlite_backup(source, tmp_path / "backups", backup_id="restore_001")

    restored = restore_sqlite_backup(manifest.backup_path, tmp_path / "restore" / "aeis_restored.db")

    conn = sqlite3.connect(restored)
    try:
        assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0] == 3
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        conn.close()


def test_restore_drill_reports_pass_and_rto(tmp_path):
    source = tmp_path / "aeis.db"
    _seed_db(source)

    result = run_sqlite_restore_drill(source, tmp_path / "drill", rto_target_minutes=30)

    assert result.passed is True
    assert result.status == "pass"
    assert result.integrity_check == "ok"
    assert result.rto_passed is True
    assert result.source_signature == {"customers": 2, "notes": 3}
    assert result.restored_signature == result.source_signature


def test_backup_policy_accepts_rpo_rto_with_wal_archive():
    policy = BackupPolicy(
        enabled=True,
        backup_interval_minutes=360,
        rpo_target_minutes=60,
        rto_target_minutes=30,
        backup_target="s3://aeis-prod-backups",
        wal_archive_enabled=True,
    )

    assert policy.validate() == []


def test_backup_policy_rejects_invalid_production_shape():
    policy = BackupPolicy(
        enabled=False,
        backup_interval_minutes=720,
        rpo_target_minutes=90,
        rto_target_minutes=45,
        backup_target="",
        wal_archive_enabled=False,
    )

    failures = policy.validate()

    assert "backup policy disabled" in failures
    assert "backup interval must be <= 360 minutes" in failures
    assert "RPO target must be <= 60 minutes" in failures
    assert "RTO target must be <= 30 minutes" in failures
    assert "backup target is required" in failures
    assert "WAL/archive stream is required when backup interval exceeds RPO" in failures
