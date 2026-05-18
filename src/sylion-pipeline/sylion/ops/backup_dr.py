"""Backup and restore drill primitives for AEIS production readiness."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class BackupManifest:
    backup_id: str
    source_path: str
    backup_path: str
    manifest_path: str
    sha256: str
    bytes: int
    created_at: str
    engine: str = "sqlite"
    retention_policy: str = "production-readiness-local-drill"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RestoreDrillResult:
    status: str
    backup_id: str
    backup_path: str
    restore_path: str
    started_at: str
    finished_at: str
    duration_seconds: float
    rto_target_minutes: int
    rto_passed: bool
    integrity_check: str
    source_signature: dict[str, int]
    restored_signature: dict[str, int]

    @property
    def passed(self) -> bool:
        return (
            self.status == "pass"
            and self.rto_passed
            and self.integrity_check == "ok"
            and self.source_signature == self.restored_signature
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["passed"] = self.passed
        return data


@dataclass(frozen=True)
class BackupPolicy:
    enabled: bool
    backup_interval_minutes: int
    rpo_target_minutes: int
    rto_target_minutes: int
    backup_target: str
    wal_archive_enabled: bool = False

    def validate(self) -> list[str]:
        failures: list[str] = []
        if not self.enabled:
            failures.append("backup policy disabled")
        if self.backup_interval_minutes <= 0:
            failures.append("backup interval must be positive")
        if self.backup_interval_minutes > 360:
            failures.append("backup interval must be <= 360 minutes")
        if self.rpo_target_minutes <= 0 or self.rpo_target_minutes > 60:
            failures.append("RPO target must be <= 60 minutes")
        if self.rto_target_minutes <= 0 or self.rto_target_minutes > 30:
            failures.append("RTO target must be <= 30 minutes")
        if not self.backup_target.strip():
            failures.append("backup target is required")
        if self.backup_interval_minutes > self.rpo_target_minutes and not self.wal_archive_enabled:
            failures.append("WAL/archive stream is required when backup interval exceeds RPO")
        return failures


def create_sqlite_backup(
    source_db: str | Path,
    backup_dir: str | Path,
    *,
    backup_id: str | None = None,
    retention_policy: str = "production-readiness-local-drill",
) -> BackupManifest:
    source = Path(source_db)
    if not source.exists():
        raise FileNotFoundError(f"source database does not exist: {source}")

    backup_root = Path(backup_dir)
    backup_root.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bid = backup_id or f"sqlite_{stamp}_{hashlib.sha256(str(source).encode()).hexdigest()[:8]}"
    backup_path = backup_root / f"{bid}.db"
    manifest_path = backup_root / f"{bid}.manifest.json"

    src_conn = sqlite3.connect(str(source))
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    manifest = BackupManifest(
        backup_id=bid,
        source_path=str(source),
        backup_path=str(backup_path),
        manifest_path=str(manifest_path),
        sha256=sha256_file(backup_path),
        bytes=backup_path.stat().st_size,
        created_at=_utc_now(),
        retention_policy=retention_policy,
    )
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def _sqlite_signature(db_path: str | Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        signature: dict[str, int] = {}
        for (table_name,) in rows:
            quoted = '"' + table_name.replace('"', '""') + '"'
            count = conn.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
            signature[table_name] = int(count)
        return signature
    finally:
        conn.close()


def _sqlite_integrity(db_path: str | Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return str(row[0]) if row else "missing"
    finally:
        conn.close()


def restore_sqlite_backup(backup_path: str | Path, restore_path: str | Path) -> Path:
    source = Path(backup_path)
    target = Path(restore_path)
    if not source.exists():
        raise FileNotFoundError(f"backup database does not exist: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    for suffix in ("-wal", "-shm", "-journal"):
        side = Path(str(target) + suffix)
        if side.exists():
            side.unlink()
    shutil.copy2(source, target)
    return target


def run_sqlite_restore_drill(
    source_db: str | Path,
    work_dir: str | Path,
    *,
    rto_target_minutes: int = 30,
) -> RestoreDrillResult:
    started = time.perf_counter()
    started_at = _utc_now()
    work = Path(work_dir)
    manifest = create_sqlite_backup(source_db, work / "backups")
    restore_path = work / "restore" / f"{manifest.backup_id}.restored.db"
    restore_sqlite_backup(manifest.backup_path, restore_path)

    source_signature = _sqlite_signature(source_db)
    restored_signature = _sqlite_signature(restore_path)
    integrity = _sqlite_integrity(restore_path)
    duration = time.perf_counter() - started
    rto_passed = duration <= (rto_target_minutes * 60)
    status = "pass" if integrity == "ok" and source_signature == restored_signature and rto_passed else "fail"

    return RestoreDrillResult(
        status=status,
        backup_id=manifest.backup_id,
        backup_path=manifest.backup_path,
        restore_path=str(restore_path),
        started_at=started_at,
        finished_at=_utc_now(),
        duration_seconds=round(duration, 6),
        rto_target_minutes=rto_target_minutes,
        rto_passed=rto_passed,
        integrity_check=integrity,
        source_signature=source_signature,
        restored_signature=restored_signature,
    )
