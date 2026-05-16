"""W17 cost_ledger JSONL → PostgreSQL migration.

Sprint 3 final deliverable. Migrates the durable JSONL spine to a
real Postgres ``cost_records`` table so the W17 evidence-spine charter
can ship the ``mv_cost_ledger`` materialised view (G2).

The migrator is **idempotent** by design (Kimi review k1_pg_migration_safety
round 53:00):

* Each row carries a stable ``decision_id`` UUID — used as PK in PG.
* Re-running the migration on the same JSONL file inserts zero rows
  (``ON CONFLICT (decision_id) DO NOTHING``).
* The audit JSONL records every batch attempt with file path + counts
  + outcome, so a partial migration can be resumed by replaying.

Usage::

    migrator = CostLedgerPgMigrator(
        connection_factory=lambda: psycopg.connect(dsn),
    )
    migrator.ensure_schema()
    report = migrator.migrate_directory(Path("logs/v2/"))

Returns a :class:`MigrationReport` with per-file outcomes + global
totals. Audit emit goes through ``append_to_chain`` (commit ac97e957)
to ``logs/v2/cost_ledger_migration.jsonl``.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from sylion.aeis_v2.audit_chain import append_to_chain

log = logging.getLogger(__name__)

#: Idempotent DDL — runs before first migration.
PG_COST_LEDGER_DDL: str = """
CREATE TABLE IF NOT EXISTS cost_records (
    decision_id text        PRIMARY KEY,
    ts          timestamptz NOT NULL,
    session_id  text        NOT NULL DEFAULT '',
    host        text        NOT NULL DEFAULT '',
    model       text        NOT NULL,
    tokens_in   bigint      NOT NULL DEFAULT 0,
    tokens_out  bigint      NOT NULL DEFAULT 0,
    cost_usd    numeric(12,6) NOT NULL DEFAULT 0,
    metadata    jsonb       NOT NULL DEFAULT '{}'::jsonb,
    inserted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS cost_records_ts_idx ON cost_records (ts);
CREATE INDEX IF NOT EXISTS cost_records_model_idx ON cost_records (model);
CREATE INDEX IF NOT EXISTS cost_records_host_idx ON cost_records (host);
"""

#: Default batch size — large enough to amortise round-trips, small
#: enough to keep transactions short.
DEFAULT_BATCH_SIZE: int = 500

#: Audit JSONL for the migrator's own actions.
DEFAULT_MIGRATION_AUDIT_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "cost_ledger_migration.jsonl"
)


@dataclass(frozen=True, slots=True)
class FileMigrationOutcome:
    """Result of migrating one JSONL file."""

    path: str
    rows_seen: int
    rows_inserted: int
    rows_skipped_existing: int
    rows_invalid: int
    elapsed_ms: float
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "rows_seen": self.rows_seen,
            "rows_inserted": self.rows_inserted,
            "rows_skipped_existing": self.rows_skipped_existing,
            "rows_invalid": self.rows_invalid,
            "elapsed_ms": round(self.elapsed_ms, 3),
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class MigrationReport:
    """Aggregate result of a directory-level migration."""

    files: list[FileMigrationOutcome] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def total_rows_inserted(self) -> int:
        return sum(f.rows_inserted for f in self.files)

    @property
    def total_rows_seen(self) -> int:
        return sum(f.rows_seen for f in self.files)

    @property
    def total_rows_skipped(self) -> int:
        return sum(f.rows_skipped_existing for f in self.files)

    @property
    def total_rows_invalid(self) -> int:
        return sum(f.rows_invalid for f in self.files)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.finished_at - self.started_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "files": [f.to_dict() for f in self.files],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": self.duration_s,
            "total_rows_inserted": self.total_rows_inserted,
            "total_rows_seen": self.total_rows_seen,
            "total_rows_skipped": self.total_rows_skipped,
            "total_rows_invalid": self.total_rows_invalid,
        }


_REQUIRED_FIELDS: tuple[str, ...] = (
    "ts", "session_id", "decision_id", "host", "model",
    "tokens_in", "tokens_out", "cost_usd",
)


def _validate_row(row: dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    for k in _REQUIRED_FIELDS:
        if k not in row:
            return False
    if not isinstance(row.get("decision_id"), str) or not row["decision_id"]:
        return False
    if not isinstance(row.get("ts"), (int, float)):
        return False
    return True


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any] | None]]:
    """Yield ``(line_no, row_or_None)`` for every non-empty line.

    Sprint 3 chained-format support: when the line is shaped as
    ``{"prev_hash": ..., "content": {...}, "content_hash": ...}`` (the
    canonical chained audit format from commit ac97e957) we unwrap to
    ``content`` so the rest of the migrator can keep its raw-dict
    contract. Pre-migration (legacy) rows are flat dicts; they pass
    through unchanged.

    Malformed lines yield ``None`` so the caller can count invalids.
    """
    if not path.exists():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    yield (line_no, None)
                    continue
                # Detect chained format and unwrap.
                if (
                    isinstance(parsed, dict)
                    and isinstance(parsed.get("content"), dict)
                    and "content_hash" in parsed
                ):
                    inner = parsed["content"]
                    # Skip non-cost-record rows that may share the chain.
                    if inner.get("kind") not in (None, "cost_ledger.record"):
                        continue
                    yield (line_no, inner)
                else:
                    yield (line_no, parsed)
    except OSError as exc:
        log.warning("cost_ledger_migrator: read failed (%s)", exc)


class CostLedgerPgMigrator:
    """Idempotent JSONL → PG migration for the W17 cost ledger."""

    def __init__(
        self,
        *,
        connection_factory: Any | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        audit_log_path: Path | str | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if connection_factory is None:
            raise ValueError("connection_factory is required")
        self._connection_factory = connection_factory
        self._batch_size = batch_size
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else DEFAULT_MIGRATION_AUDIT_PATH
        )
        self._lock = threading.RLock()
        self._init_done = False

    def _emit(self, payload: dict[str, Any]) -> None:
        try:
            append_to_chain(self._audit_log_path, payload)
        except Exception as exc:  # noqa: BLE001
            log.warning("cost_ledger_migrator: audit emit failed (%s)", exc)

    def ensure_schema(self) -> None:
        with self._lock:
            if self._init_done:
                return
            with self._connection_factory() as conn:
                with conn.cursor() as cur:
                    cur.execute(PG_COST_LEDGER_DDL)
                conn.commit()
            self._init_done = True
        self._emit({"kind": "cost_ledger_migration.schema_applied"})

    # ------------------------------------------------------------------
    # File-level migration
    # ------------------------------------------------------------------

    def migrate_file(self, path: Path | str) -> FileMigrationOutcome:
        p = Path(path)
        started = time.perf_counter()
        rows_seen = 0
        rows_invalid = 0
        rows_inserted = 0
        rows_skipped_existing = 0

        if not p.exists():
            outcome = FileMigrationOutcome(
                path=str(p), rows_seen=0, rows_inserted=0,
                rows_skipped_existing=0, rows_invalid=0,
                elapsed_ms=0.0, sha256="",
            )
            self._emit({
                "kind": "cost_ledger_migration.file",
                "outcome": "missing",
                **outcome.to_dict(),
            })
            return outcome

        sha = _file_sha256(p)
        batch: list[tuple[Any, ...]] = []

        with self._lock:
            with self._connection_factory() as conn:
                with conn.cursor() as cur:
                    for line_no, row in parse_jsonl(p):
                        rows_seen += 1
                        if row is None or not _validate_row(row):
                            rows_invalid += 1
                            continue
                        batch.append((
                            row["decision_id"],
                            float(row["ts"]),
                            row["session_id"],
                            row["host"],
                            row["model"],
                            int(row["tokens_in"]),
                            int(row["tokens_out"]),
                            float(row["cost_usd"]),
                            json.dumps(
                                row.get("metadata") or {},
                                ensure_ascii=False,
                            ),
                        ))
                        if len(batch) >= self._batch_size:
                            ins, skp = self._flush_batch(cur, batch)
                            rows_inserted += ins
                            rows_skipped_existing += skp
                            batch.clear()
                    if batch:
                        ins, skp = self._flush_batch(cur, batch)
                        rows_inserted += ins
                        rows_skipped_existing += skp
                conn.commit()

        elapsed_ms = (time.perf_counter() - started) * 1000
        outcome = FileMigrationOutcome(
            path=str(p),
            rows_seen=rows_seen,
            rows_inserted=rows_inserted,
            rows_skipped_existing=rows_skipped_existing,
            rows_invalid=rows_invalid,
            elapsed_ms=elapsed_ms,
            sha256=sha,
        )
        self._emit({
            "kind": "cost_ledger_migration.file",
            "outcome": "ok",
            **outcome.to_dict(),
        })
        log.info(
            "cost_ledger_migrator: %s — seen=%d inserted=%d "
            "skipped_existing=%d invalid=%d elapsed_ms=%.1f",
            p, rows_seen, rows_inserted,
            rows_skipped_existing, rows_invalid, elapsed_ms,
        )
        return outcome

    def _flush_batch(self, cur: Any, batch: list[tuple]) -> tuple[int, int]:
        """Insert one batch with ON CONFLICT DO NOTHING. Returns (inserted, skipped)."""
        # Use executemany with ON CONFLICT for idempotency. We track the
        # affected count via cur.rowcount — for executemany psycopg
        # returns total rows touched, so 'skipped' is len(batch) - inserted.
        cur.executemany(
            """
            INSERT INTO cost_records
                (decision_id, ts, session_id, host, model,
                 tokens_in, tokens_out, cost_usd, metadata)
            VALUES (%s, to_timestamp(%s), %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (decision_id) DO NOTHING
            """,
            batch,
        )
        affected = cur.rowcount if cur.rowcount is not None else 0
        if affected < 0:
            affected = 0
        # When executemany returns the per-call rowcount summed; treat
        # it as the upper bound on inserted rows.
        inserted = min(affected, len(batch))
        skipped = len(batch) - inserted
        return inserted, skipped

    # ------------------------------------------------------------------
    # Directory-level migration (the canonical entry point)
    # ------------------------------------------------------------------

    def migrate_directory(
        self, directory: Path | str, *, glob: str = "cost_ledger*.jsonl",
    ) -> MigrationReport:
        d = Path(directory)
        started = time.time()
        files: list[FileMigrationOutcome] = []
        if d.exists():
            for p in sorted(d.glob(glob)):
                files.append(self.migrate_file(p))
        finished = time.time()
        report = MigrationReport(
            files=files, started_at=started, finished_at=finished,
        )
        self._emit({
            "kind": "cost_ledger_migration.run",
            "directory": str(d),
            "glob": glob,
            **report.to_dict(),
        })
        return report


__all__ = [
    "CostLedgerPgMigrator",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MIGRATION_AUDIT_PATH",
    "FileMigrationOutcome",
    "MigrationReport",
    "PG_COST_LEDGER_DDL",
    "parse_jsonl",
]
