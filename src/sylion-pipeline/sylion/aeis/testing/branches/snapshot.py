"""Per-branch SQLite snapshot management.

Each isolated branch (simulation/repair/test/release) can own a snapshot
of the production ontology DB so a sandbox writes against it without
touching ``sylion_aeis.db``. Snapshots live under
``<base_dir>/sim_<branch_id>_*.db`` so the cleanup script can prune by
prefix on restart.

Lifecycle::

    snap = BranchSnapshot.create_for(branch_id="br_xxx", source_db="...")
    snap.path                 -> Path('sim_br_xxx_*.db')
    snap.hash                 -> sha256 of file bytes
    snap.discard()            -> deletes the file (idempotent)
    BranchSnapshot.cleanup_orphans(base_dir)   -> remove sim_*_*.db files
                                                  whose branches are merged
                                                  or discarded

A snapshot is just a copied SQLite file (or an empty DB if no source).
The hash lets the parent ontology persist a verifiable
``SimulationBranch.snapshot_db_path`` field plus its content hash so
crash recovery can identify orphaned files.
"""
from __future__ import annotations

import hashlib
import logging
import sqlite3
import tempfile
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger("sylion.aeis.testing.branches.snapshot")

DEFAULT_BASE_DIR = Path(tempfile.gettempdir()) / "sylion_w14_snapshots"
SNAPSHOT_PREFIX = "sim_"
SNAPSHOT_SUFFIX = ".db"


class BranchSnapshot:
    """Materialized per-branch SQLite snapshot."""

    def __init__(self, branch_id: str, path: Path) -> None:
        self.branch_id = branch_id
        self.path = path
        self.created_at: float = time.time()
        self._lock = threading.Lock()
        self._discarded = False

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    # Defensive whitelist for branch_id — only ASCII alphanum + underscore + dash.
    _BRANCH_ID_RE = __import__("re").compile(r"^[A-Za-z0-9_\-]+$")

    @classmethod
    def create_for(
        cls,
        branch_id: str,
        source_db: str | Path | None = None,
        base_dir: str | Path | None = None,
    ) -> "BranchSnapshot":
        """Create a fresh snapshot file under ``base_dir``.

        If ``source_db`` is provided the file is copied byte-for-byte
        (using SQLite ``backup()`` API to preserve WAL state). Otherwise
        an empty SQLite database is initialised.
        """
        if not branch_id:
            raise ValueError("branch_id is required")
        # Path traversal guard (Kimi attack vector #1):
        # reject path separators, traversal sequences, control chars, NULs.
        if (
            "/" in branch_id
            or "\\" in branch_id
            or ".." in branch_id
            or "\x00" in branch_id
            or "\n" in branch_id
            or "\r" in branch_id
            or branch_id.startswith(".")
            or not cls._BRANCH_ID_RE.match(branch_id)
        ):
            raise ValueError(
                f"branch_id contains illegal characters: {branch_id!r} "
                "(allowed: A-Za-z0-9_-, no separators, no leading dot)"
            )
        if "main" in branch_id.casefold():
            # Defensive: never produce a snapshot named after main.
            raise ValueError(
                f"branch_id contains 'main' ({branch_id!r}); refusing to "
                "create snapshot — W14 prohibits sim files shadowing main"
            )

        base = Path(base_dir) if base_dir else DEFAULT_BASE_DIR
        base.mkdir(parents=True, exist_ok=True)
        # File name: sim_<branch_id>_<uuid>.db
        token = uuid.uuid4().hex[:8]
        target = base / f"{SNAPSHOT_PREFIX}{branch_id}_{token}{SNAPSHOT_SUFFIX}"

        if source_db:
            src_path = Path(source_db)
            if not src_path.exists():
                raise FileNotFoundError(f"source_db does not exist: {src_path}")
            # Use SQLite online backup so a live source isn't corrupted.
            src_conn = sqlite3.connect(str(src_path))
            dst_conn = sqlite3.connect(str(target))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()
        else:
            # Touch an empty SQLite file with WAL enabled.
            conn = sqlite3.connect(str(target))
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            finally:
                conn.close()

        log.info("snapshot created: %s -> %s", branch_id, target)
        return cls(branch_id=branch_id, path=target)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def hash(self) -> str:
        """SHA256 of the snapshot file contents."""
        if self._discarded or not self.path.exists():
            return ""
        h = hashlib.sha256()
        with open(self.path, "rb") as f:
            while True:
                chunk = f.read(64 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    def discard(self) -> bool:
        """Delete the snapshot file. Returns True if it was removed."""
        with self._lock:
            if self._discarded:
                return False
            self._discarded = True
            try:
                if self.path.exists():
                    self.path.unlink()
                # Best-effort: also drop -wal/-shm side files
                for side in (".wal", ".shm"):
                    sp = Path(str(self.path) + side)
                    if sp.exists():
                        sp.unlink()
                # And SQLite ".journal"
                jp = Path(str(self.path) + "-journal")
                if jp.exists():
                    jp.unlink()
                return True
            except OSError:  # pragma: no cover
                log.exception("snapshot discard failed: %s", self.path)
                return False

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"BranchSnapshot(branch_id={self.branch_id!r}, "
            f"path={self.path!s}, discarded={self._discarded})"
        )

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    @classmethod
    def cleanup_orphans(
        cls,
        active_branch_ids: set[str],
        base_dir: str | Path | None = None,
    ) -> list[Path]:
        """Delete any sim_<id>_*.db whose branch_id is not in ``active``.

        Use case: after a process crash, the OntologyStore lists branches
        in MERGED or DISCARDED state. The caller passes in the set of
        currently OPEN branch_ids; everything else is fair game for
        cleanup.
        """
        base = Path(base_dir) if base_dir else DEFAULT_BASE_DIR
        if not base.exists():
            return []
        removed: list[Path] = []
        for f in base.glob(f"{SNAPSHOT_PREFIX}*{SNAPSHOT_SUFFIX}"):
            # Filename format: sim_<branch_id>_<token>.db
            stem = f.stem  # 'sim_<branch_id>_<token>'
            inner = stem[len(SNAPSHOT_PREFIX):]
            # Branch IDs themselves contain no underscores beyond the
            # prefix (br_<hex>), so the rsplit is safe.
            branch_id = inner.rsplit("_", 1)[0]
            if branch_id not in active_branch_ids:
                try:
                    f.unlink()
                    removed.append(f)
                    # Also drop side files
                    for side in ("-wal", "-shm", "-journal"):
                        sp = Path(str(f) + side)
                        if sp.exists():
                            sp.unlink()
                except OSError:  # pragma: no cover
                    log.exception("orphan cleanup failed: %s", f)
        if removed:
            log.info("cleanup_orphans: removed %d snapshot(s)", len(removed))
        return removed


__all__ = ["BranchSnapshot", "DEFAULT_BASE_DIR", "SNAPSHOT_PREFIX"]
