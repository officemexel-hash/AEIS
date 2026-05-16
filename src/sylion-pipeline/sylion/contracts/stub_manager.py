"""
SYLION Contracts -- gRPC Stub Manager

Manages gRPC proto stub generation tracking, versioning, and staleness detection.
SQLite-backed, thread-safe, singleton pattern.

The actual protoc execution is a CI/build step; this manager tracks metadata
about generated stubs (versions, file hashes, timestamps) and detects when
stubs are stale relative to their source .proto files.

Event emissions:
  - contracts.stub.generated  — stub set generated or regenerated
  - contracts.stub.validated  — validation run completed
  - contracts.stub.regenerated — stale stubs regenerated
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.contracts.stub_manager")

# ---------------------------------------------------------------------------
# Schema version for the stub tracking table
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Canonical proto file list (from generate_stubs.py)
# ---------------------------------------------------------------------------

PROTO_FILES = [
    "common.proto",
    "core_v1.proto",
    "cognitive_v1.proto",
    "execution_v1.proto",
    "memory_v1.proto",
    "governance_v1.proto",
    "security_v1.proto",
    "efficiency_v1.proto",
    "aeis_v1.proto",
    "skills_v1.proto",
    "surface_v1.proto",
    "rebuild_v1.proto",
    "quality_v1.proto",
    "devices_v1.proto",
    "sdr_v1.proto",
    "cellular_v1.proto",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _file_hash(path: Path) -> str:
    """SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _proto_stem(proto_file: str) -> str:
    """e.g. 'core_v1.proto' -> 'core_v1'"""
    return proto_file.replace(".proto", "")


def _stub_files(stem: str, stub_dir: Path) -> list[Path]:
    """Expected stub file paths for a given proto stem."""
    return [
        stub_dir / f"{stem}_pb2.py",
        stub_dir / f"{stem}_pb2_grpc.py",
    ]


# ---------------------------------------------------------------------------
# StubManager
# ---------------------------------------------------------------------------

class StubManager:
    """Manages gRPC stub generation metadata.

    Tracks which proto files have had stubs generated, the content hash of
    the proto at generation time, the resulting stub file paths, and the
    generation timestamp.  All state lives in a SQLite table.

    Thread-safe via a single ``threading.Lock``.
    """

    def __init__(self, db_path: str = ":memory:", event_bus: Any = None):
        self._db_path = str(db_path)
        self._event_bus = event_bus
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS sylion_stub_registry (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                proto_file      TEXT    NOT NULL UNIQUE,
                service_name    TEXT    NOT NULL,
                proto_hash      TEXT    NOT NULL DEFAULT '',
                stub_version    INTEGER NOT NULL DEFAULT 1,
                status          TEXT    NOT NULL DEFAULT 'pending',
                pb2_path        TEXT    NOT NULL DEFAULT '',
                grpc_path       TEXT    NOT NULL DEFAULT '',
                generated_at    REAL    NOT NULL DEFAULT 0,
                updated_at      REAL    NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_stub_proto
                ON sylion_stub_registry(proto_file);
            CREATE INDEX IF NOT EXISTS idx_stub_service
                ON sylion_stub_registry(service_name);
            CREATE INDEX IF NOT EXISTS idx_stub_status
                ON sylion_stub_registry(status);
        """)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict[str, Any]):
        """Emit an event through the EventBus if available."""
        if self._event_bus is not None:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="contracts.stub_manager",
            ))

    def _detect_services(self, proto_path: Path) -> list[str]:
        """Extract service names from a .proto file (simple text scan)."""
        services: list[str] = []
        try:
            text = proto_path.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("service ") and stripped.endswith("{"):
                    name = stripped[len("service "):-1].strip()
                    services.append(name)
        except Exception:
            pass
        return services

    def _run_protoc(self, proto_path: Path, proto_dir: Path, output_dir: Path) -> bool:
        """Run protoc to generate stubs. Returns True on success.

        In production this invokes grpc_tools.protoc.  The actual command
        execution is mocked in tests via monkeypatching this method.
        """
        try:
            import subprocess
            import sys

            cmd = [
                sys.executable, "-m", "grpc_tools.protoc",
                f"--proto_path={proto_dir}",
                f"--python_out={output_dir}",
                f"--grpc_python_out={output_dir}",
                str(proto_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                log.error("protoc failed for %s: %s", proto_path.name, result.stderr.strip())
                return False
            return True
        except Exception as exc:
            log.error("protoc invocation failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_stubs(self, proto_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
        """Generate Python gRPC stubs from .proto files and track metadata.

        Returns a summary dict with counts of generated, skipped, and failed stubs.
        """
        proto_dir = Path(proto_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated = 0
        skipped = 0
        failed = 0
        now = time.time()

        for proto_file in PROTO_FILES:
            proto_path = proto_dir / proto_file
            stem = _proto_stem(proto_file)

            if not proto_path.exists():
                log.warning("proto file not found, skipping: %s", proto_file)
                skipped += 1
                continue

            # Compute current proto hash
            proto_hash = _file_hash(proto_path)
            services = self._detect_services(proto_path)
            service_name = services[0] if services else stem
            pb2_path = output_dir / f"{stem}_pb2.py"
            grpc_path = output_dir / f"{stem}_pb2_grpc.py"

            # Run protoc
            success = self._run_protoc(proto_path, proto_dir, output_dir)
            if not success:
                # Record failure
                with self._lock:
                    self._conn.execute(
                        """INSERT INTO sylion_stub_registry
                           (proto_file, service_name, proto_hash, stub_version, status, pb2_path, grpc_path, generated_at, updated_at)
                           VALUES (?, ?, ?, 1, 'failed', '', '', ?, ?)
                           ON CONFLICT(proto_file) DO UPDATE SET
                               proto_hash=excluded.proto_hash,
                               status='failed',
                               updated_at=excluded.updated_at
                        """,
                        (proto_file, service_name, proto_hash, now, now),
                    )
                    self._conn.commit()
                failed += 1
                continue

            # Determine new version number
            with self._lock:
                existing = self._conn.execute(
                    "SELECT stub_version, proto_hash FROM sylion_stub_registry WHERE proto_file=?",
                    (proto_file,),
                ).fetchone()

                if existing:
                    new_version = existing["stub_version"] + 1
                else:
                    new_version = 1

                self._conn.execute(
                    """INSERT INTO sylion_stub_registry
                       (proto_file, service_name, proto_hash, stub_version, status, pb2_path, grpc_path, generated_at, updated_at)
                       VALUES (?, ?, ?, ?, 'generated', ?, ?, ?, ?)
                       ON CONFLICT(proto_file) DO UPDATE SET
                           service_name=excluded.service_name,
                           proto_hash=excluded.proto_hash,
                           stub_version=excluded.stub_version,
                           status='generated',
                           pb2_path=excluded.pb2_path,
                           grpc_path=excluded.grpc_path,
                           generated_at=excluded.generated_at,
                           updated_at=excluded.updated_at
                    """,
                    (
                        proto_file, service_name, proto_hash, new_version,
                        str(pb2_path), str(grpc_path), now, now,
                    ),
                )
                self._conn.commit()

            generated += 1

        summary = {
            "generated": generated,
            "skipped": skipped,
            "failed": failed,
            "total_proto_files": len(PROTO_FILES),
        }

        self._emit("contracts.stub.generated", summary)
        log.info(
            "stub generation complete: %d generated, %d skipped, %d failed",
            generated, skipped, failed,
        )
        return summary

    def get_stub_status(self, service_name: str) -> dict[str, Any] | None:
        """Return generation metadata for a service, or None if not tracked.

        ``service_name`` can be either the gRPC service name (e.g.
        ``ModuleRegistryService``) or a proto stem (e.g. ``core_v1``).
        """
        with self._lock:
            # Try exact service_name match first
            row = self._conn.execute(
                "SELECT * FROM sylion_stub_registry WHERE service_name=?",
                (service_name,),
            ).fetchone()

            if row is None:
                # Try proto_file match (stem or full)
                row = self._conn.execute(
                    "SELECT * FROM sylion_stub_registry WHERE proto_file=? OR proto_file=?",
                    (service_name, f"{service_name}.proto"),
                ).fetchone()

        if row is None:
            return None

        return {
            "proto_file": row["proto_file"],
            "service_name": row["service_name"],
            "status": row["status"],
            "version": row["stub_version"],
            "proto_hash": row["proto_hash"],
            "pb2_path": row["pb2_path"],
            "grpc_path": row["grpc_path"],
            "generated_at": row["generated_at"],
            "updated_at": row["updated_at"],
        }

    def list_stubs(self) -> list[dict[str, Any]]:
        """List all tracked stubs with full metadata."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT proto_file, service_name, proto_hash, stub_version,
                          status, pb2_path, grpc_path, generated_at, updated_at
                   FROM sylion_stub_registry
                   ORDER BY proto_file"""
            ).fetchall()

        return [
            {
                "proto_file": r["proto_file"],
                "service_name": r["service_name"],
                "proto_hash": r["proto_hash"],
                "version": r["stub_version"],
                "status": r["status"],
                "pb2_path": r["pb2_path"],
                "grpc_path": r["grpc_path"],
                "generated_at": r["generated_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def validate_stubs(self, proto_dir: str | Path, stub_dir: str | Path) -> dict[str, Any]:
        """Check if all tracked stubs are up-to-date with their proto files.

        A stub is **stale** when:
          - The proto file has a different content hash than the one recorded.
          - The stub files (``_pb2.py`` / ``_pb2_grpc.py``) do not exist on disk.
          - The stub is tracked with status ``failed`` or ``pending``.

        Returns a dict with lists of valid, stale, and missing entries.
        """
        proto_dir = Path(proto_dir)
        stub_dir = Path(stub_dir)

        valid: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []

        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sylion_stub_registry ORDER BY proto_file"
            ).fetchall()

        for row in rows:
            proto_file = row["proto_file"]
            proto_path = proto_dir / proto_file
            stem = _proto_stem(proto_file)
            entry = {
                "proto_file": proto_file,
                "service_name": row["service_name"],
                "version": row["stub_version"],
            }

            # Status check
            if row["status"] in ("failed", "pending"):
                stale.append({**entry, "reason": f"status={row['status']}"})
                continue

            # Proto file existence
            if not proto_path.exists():
                missing.append({**entry, "reason": "proto_file_missing"})
                continue

            # Hash comparison
            current_hash = _file_hash(proto_path)
            if current_hash != row["proto_hash"]:
                stale.append({**entry, "reason": "proto_hash_changed"})
                continue

            # Stub file existence
            pb2, grpc = _stub_files(stem, stub_dir)
            if not pb2.exists() or not grpc.exists():
                stale.append({**entry, "reason": "stub_files_missing"})
                continue

            valid.append(entry)

        result = {
            "valid": valid,
            "stale": stale,
            "missing": missing,
            "valid_count": len(valid),
            "stale_count": len(stale),
            "missing_count": len(missing),
        }

        self._emit("contracts.stub.validated", result)
        return result

    def regenerate_stale(self, proto_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
        """Regenerate only the stubs that are stale or missing.

        Returns a summary of how many were regenerated, already current, or failed.
        """
        proto_dir = Path(proto_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Find stale entries
        stale_proto_files: list[str] = []
        with self._lock:
            rows = self._conn.execute(
                "SELECT proto_file FROM sylion_stub_registry WHERE status != 'generated'"
            ).fetchall()
            stale_proto_files = [r["proto_file"] for r in rows]

        # Also check for hash changes
        with self._lock:
            all_rows = self._conn.execute(
                "SELECT proto_file, proto_hash FROM sylion_stub_registry WHERE status = 'generated'"
            ).fetchall()

        for row in all_rows:
            proto_path = proto_dir / row["proto_file"]
            if proto_path.exists():
                current_hash = _file_hash(proto_path)
                if current_hash != row["proto_hash"]:
                    if row["proto_file"] not in stale_proto_files:
                        stale_proto_files.append(row["proto_file"])

        regenerated = 0
        already_current = len(PROTO_FILES) - len(stale_proto_files)
        failed = 0
        now = time.time()

        for proto_file in stale_proto_files:
            proto_path = proto_dir / proto_file
            stem = _proto_stem(proto_file)

            if not proto_path.exists():
                failed += 1
                continue

            proto_hash = _file_hash(proto_path)
            services = self._detect_services(proto_path)
            service_name = services[0] if services else stem
            pb2_path = output_dir / f"{stem}_pb2.py"
            grpc_path = output_dir / f"{stem}_pb2_grpc.py"

            success = self._run_protoc(proto_path, proto_dir, output_dir)
            if not success:
                with self._lock:
                    self._conn.execute(
                        """UPDATE sylion_stub_registry
                           SET status='failed', proto_hash=?, updated_at=?
                           WHERE proto_file=?
                        """,
                        (proto_hash, now, proto_file),
                    )
                    self._conn.commit()
                failed += 1
                continue

            with self._lock:
                self._conn.execute(
                    """UPDATE sylion_stub_registry
                       SET service_name=?, proto_hash=?,
                           stub_version=stub_version+1,
                           status='generated',
                           pb2_path=?, grpc_path=?,
                           updated_at=?
                       WHERE proto_file=?
                    """,
                    (service_name, proto_hash, str(pb2_path), str(grpc_path), now, proto_file),
                )
                self._conn.commit()

            regenerated += 1

        result = {
            "regenerated": regenerated,
            "already_current": already_current,
            "failed": failed,
            "total_checked": len(stale_proto_files),
        }

        self._emit("contracts.stub.regenerated", result)
        return result

    def get_stats(self) -> dict[str, Any]:
        """Return aggregate statistics about tracked stubs."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_stub_registry"
            ).fetchone()["cnt"]

            by_status = self._conn.execute(
                "SELECT status, COUNT(*) as cnt FROM sylion_stub_registry GROUP BY status"
            ).fetchall()

            stale_count = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM sylion_stub_registry WHERE status != 'generated'"
            ).fetchone()["cnt"]

            last_gen = self._conn.execute(
                "SELECT MAX(updated_at) as t FROM sylion_stub_registry"
            ).fetchone()["t"]

        status_counts = {r["status"]: r["cnt"] for r in by_status}

        return {
            "total_stubs": total,
            "stale_count": stale_count,
            "generated_count": status_counts.get("generated", 0),
            "failed_count": status_counts.get("failed", 0),
            "pending_count": status_counts.get("pending", 0),
            "last_generation_time": last_gen,
        }

    def close(self):
        """Close the database connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_manager: StubManager | None = None


def get_stub_manager(db_path: str = ":memory:", event_bus: Any = None) -> StubManager:
    """Return the global StubManager singleton."""
    global _manager
    if _manager is None:
        _manager = StubManager(db_path=db_path, event_bus=event_bus)
    return _manager
