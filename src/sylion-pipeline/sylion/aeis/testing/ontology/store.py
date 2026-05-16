"""W14 OntologyStore — SQLite-backed CRUD for 25 testing-ontology objects.

Contract C1 (docs/w14_workplan/W14_INTEGRATION_CONTRACTS.md):
    create / get / list / update / link / get_related / history.

Storage strategy: each ontology object is serialized as JSON in a single
canonical table per object kind (`w14_<table>`). This keeps the migration
flat and avoids per-field schema sprawl while still supporting the spec's
indexes via dedicated columns. Relations are stored in `w14_testing_relations`
and every mutation appends to `w14_testing_history` (audit log, append-only).

Thread-safety: a single threading.RLock guards all DB access. Connection is
opened with `check_same_thread=False` and uses WAL mode for non-memory paths.

Events: when an event_bus is provided, every mutation emits a SylionEvent
with topic `aeis.testing.ontology.<verb>` and payload containing the object
id, kind, and operator metadata.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from sylion.aeis.testing.ontology.objects import (
    OBJECT_TABLE_MAP,
    PRIMARY_KEY_MAP,
)
from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.aeis.testing.ontology.store")

T = TypeVar("T")

DEFAULT_LIMIT = 100
MAX_LIMIT = 10000

# Hard caps to defuse JSON bombs / oversized rows on read.
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024  # 4 MB — generous, but bounded
MAX_JSON_DEPTH = 64


class OntologyStore:
    """SQLite-backed thread-safe CRUD store for W14 testing ontology.

    Parameters
    ----------
    db_path: str | Path | None
        Path to SQLite file. ``None`` (default) means ``:memory:``.
    event_bus: EventBus | None
        Optional bus; when provided, mutations emit SylionEvent envelopes.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self) -> None:
        """Create per-object tables + relations + history. Idempotent."""
        with self._lock:
            for table in OBJECT_TABLE_MAP.values():
                self._conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        obj_id      TEXT PRIMARY KEY,
                        payload     TEXT NOT NULL,
                        created_at  REAL NOT NULL,
                        updated_at  REAL NOT NULL,
                        deleted_at  REAL
                    )
                """)
                self._conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_created "
                    f"ON {table}(created_at)"
                )
                self._conn.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_deleted "
                    f"ON {table}(deleted_at)"
                )

            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS w14_testing_relations (
                    relation_id  TEXT PRIMARY KEY,
                    src_id       TEXT NOT NULL,
                    dst_id       TEXT NOT NULL,
                    relation     TEXT NOT NULL,
                    created_at   REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_rel_triple "
                "ON w14_testing_relations(src_id, dst_id, relation)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_src "
                "ON w14_testing_relations(src_id, relation)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_dst "
                "ON w14_testing_relations(dst_id, relation)"
            )

            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS w14_testing_history (
                    history_id  TEXT PRIMARY KEY,
                    obj_id      TEXT NOT NULL,
                    obj_kind    TEXT NOT NULL,
                    verb        TEXT NOT NULL,
                    payload     TEXT NOT NULL,
                    actor       TEXT NOT NULL DEFAULT '',
                    timestamp   REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hist_obj "
                "ON w14_testing_history(obj_id, timestamp)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_hist_kind "
                "ON w14_testing_history(obj_kind, timestamp)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _table_for(self, obj_or_type: Any) -> str:
        cls = obj_or_type if isinstance(obj_or_type, type) else type(obj_or_type)
        if cls not in OBJECT_TABLE_MAP:
            raise ValueError(
                f"Unsupported ontology type: {cls.__name__}; "
                f"must be one of {[c.__name__ for c in OBJECT_TABLE_MAP]}"
            )
        return OBJECT_TABLE_MAP[cls]

    def _pk_for(self, obj_or_type: Any) -> str:
        cls = obj_or_type if isinstance(obj_or_type, type) else type(obj_or_type)
        if cls not in PRIMARY_KEY_MAP:
            raise ValueError(f"Unknown primary key for {cls.__name__}")
        return PRIMARY_KEY_MAP[cls]

    @staticmethod
    def _serialize(obj: Any) -> str:
        if not is_dataclass(obj):
            raise TypeError(
                f"Expected dataclass instance, got {type(obj).__name__}"
            )
        return json.dumps(asdict(obj), default=str, sort_keys=True)

    @staticmethod
    def _check_depth(value: Any, depth: int = 0) -> None:
        if depth > MAX_JSON_DEPTH:
            raise ValueError(f"payload nesting exceeds {MAX_JSON_DEPTH}")
        if isinstance(value, dict):
            for v in value.values():
                OntologyStore._check_depth(v, depth + 1)
        elif isinstance(value, list):
            for v in value:
                OntologyStore._check_depth(v, depth + 1)

    @staticmethod
    def _deserialize(cls: type[T], payload: str) -> T:
        if len(payload) > MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"payload size {len(payload)}B exceeds cap {MAX_PAYLOAD_BYTES}B"
            )
        data = json.loads(payload)
        OntologyStore._check_depth(data)
        # Filter to fields actually defined on the dataclass — tolerates
        # additive schema changes without crashing on legacy rows.
        valid_field_names = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        kwargs = {k: v for k, v in data.items() if k in valid_field_names}
        return cls(**kwargs)  # type: ignore[call-arg]

    def _emit(self, verb: str, obj_id: str, obj_kind: str,
              payload: dict[str, Any]) -> None:
        if not self._event_bus:
            return
        try:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=f"aeis.testing.ontology.{verb}",
                payload={
                    "obj_id": obj_id,
                    "obj_kind": obj_kind,
                    **payload,
                },
                source_module="aeis.testing.ontology",
            ))
        except Exception:  # pragma: no cover
            log.exception("event emit failed for %s/%s", obj_kind, obj_id)

    def _record_history(
        self,
        obj_id: str,
        obj_kind: str,
        verb: str,
        payload_json: str,
        actor: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO w14_testing_history "
            "(history_id, obj_id, obj_kind, verb, payload, actor, timestamp) "
            "VALUES (?,?,?,?,?,?,?)",
            (
                uuid.uuid4().hex,
                obj_id,
                obj_kind,
                verb,
                payload_json,
                actor,
                time.time(),
            ),
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(self, obj: T, actor: str = "") -> T:
        """Insert a new ontology object. Returns the persisted object."""
        if not is_dataclass(obj):
            raise TypeError("create() expects a dataclass instance")
        cls = type(obj)
        table = self._table_for(cls)
        pk = self._pk_for(cls)
        obj_id = getattr(obj, pk)
        payload = self._serialize(obj)
        now = time.time()

        with self._lock:
            try:
                self._conn.execute(
                    f"INSERT INTO {table} "
                    "(obj_id, payload, created_at, updated_at) "
                    "VALUES (?,?,?,?)",
                    (obj_id, payload, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Duplicate {cls.__name__} id: {obj_id}"
                ) from exc
            self._record_history(obj_id, cls.__name__, "create", payload, actor)
            self._conn.commit()

        self._emit("created", obj_id, cls.__name__, {})
        log.debug("created %s %s", cls.__name__, obj_id)
        return obj

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, obj_type: type[T], obj_id: str) -> T | None:
        table = self._table_for(obj_type)
        with self._lock:
            row = self._conn.execute(
                f"SELECT payload, deleted_at FROM {table} WHERE obj_id = ?",
                (obj_id,),
            ).fetchone()
        if not row or row["deleted_at"] is not None:
            return None
        try:
            return self._deserialize(obj_type, row["payload"])
        except ValueError:
            log.warning(
                "row %s in %s rejected by deserializer (size/depth cap)",
                obj_id, table,
            )
            return None

    def list(
        self,
        obj_type: type[T],
        filters: dict[str, Any] | None = None,
        limit: int = DEFAULT_LIMIT,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[T]:
        """List objects.

        Filters are applied **before** LIMIT/OFFSET so pagination stays
        consistent. We push string/scalar filters into SQL via a JSON
        match on the serialized payload (sqlite ``LIKE`` is parameterized,
        so it remains injection-safe), then apply richer filters in
        Python on the smaller candidate set.
        """
        if limit <= 0 or limit > MAX_LIMIT:
            raise ValueError(f"limit must be in (0, {MAX_LIMIT}], got {limit}")
        if offset < 0:
            raise ValueError("offset must be >= 0")

        table = self._table_for(obj_type)
        clauses: list[str] = ["1=1"]
        params: list[Any] = []
        sql_filterable, py_filterable = _split_filters(filters or {})

        for key, value in sql_filterable.items():
            # JSON-encoded match against the canonical, sort_keys serialization.
            # Boolean/None/numeric compactly serialize without surrounding spaces;
            # strings include the quote chars so "source": "SoT" -> ..."source": "SoT",...
            json_token = json.dumps({key: value}, sort_keys=True, default=str)
            # Strip braces -> "key": value
            inner = json_token[1:-1]
            clauses.append("payload LIKE ?")
            params.append(f"%{inner}%")

        if not include_deleted:
            clauses.append("deleted_at IS NULL")

        sql = (
            f"SELECT payload FROM {table} WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])

        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        results: list[T] = []
        for row in rows:
            try:
                obj = self._deserialize(obj_type, row["payload"])
            except Exception:
                log.exception("failed to deserialize row in %s", table)
                continue
            if py_filterable and not _matches_filters(obj, py_filterable):
                continue
            if sql_filterable and not _matches_filters(obj, sql_filterable):
                # LIKE can produce false positives on substrings that happen to
                # contain the token; verify exact equality on the candidate set.
                continue
            results.append(obj)
        return results

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, obj: T, actor: str = "") -> T:
        """Update an existing object in-place. Returns the persisted object.

        Enforces declared status-transition graphs (e.g. TestCharter follows
        ``CHARTER_TRANSITIONS``) so callers cannot bypass the lifecycle by
        mutating the field directly.
        """
        if not is_dataclass(obj):
            raise TypeError("update() expects a dataclass instance")
        cls = type(obj)
        table = self._table_for(cls)
        pk = self._pk_for(cls)
        obj_id = getattr(obj, pk)
        payload = self._serialize(obj)
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                f"SELECT payload FROM {table} WHERE obj_id = ?", (obj_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"{cls.__name__} not found: {obj_id}")
            previous = self._deserialize(cls, row["payload"])
            self._enforce_transitions(previous, obj)
            self._conn.execute(
                f"UPDATE {table} SET payload = ?, updated_at = ? "
                "WHERE obj_id = ?",
                (payload, now, obj_id),
            )
            self._record_history(obj_id, cls.__name__, "update", payload, actor)
            self._conn.commit()

        self._emit("updated", obj_id, cls.__name__, {})
        log.debug("updated %s %s", cls.__name__, obj_id)
        return obj

    @staticmethod
    def _enforce_transitions(previous: Any, proposed: Any) -> None:
        """Apply status-transition graphs declared in objects.py.

        Kimi E7 attack #1: Finding's R-status graph is now enforced at the
        store layer too, so a caller bypassing FindingStore.transition()
        and going straight to ontology.update() can no longer mutate
        ``r_status`` outside the legal R0-R9 set.
        """
        from sylion.aeis.testing.ontology.objects import (  # local to avoid cycles
            CHARTER_TRANSITIONS,
            Finding,
            TestCharter,
        )
        from sylion.aeis.testing.ontology._validators import (
            require_status_transition,
        )

        if isinstance(previous, TestCharter):
            require_status_transition(
                previous.status, proposed.status, CHARTER_TRANSITIONS,
                "TestCharter.status",
            )
        elif isinstance(previous, Finding):
            from sylion.aeis.testing.findings import _ALLOWED as FINDING_GRAPH
            require_status_transition(
                previous.r_status, proposed.r_status, FINDING_GRAPH,
                "Finding.r_status",
            )

    def soft_delete(self, obj_type: type, obj_id: str, actor: str = "") -> bool:
        table = self._table_for(obj_type)
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE {table} SET deleted_at = ?, updated_at = ? "
                "WHERE obj_id = ? AND deleted_at IS NULL",
                (now, now, obj_id),
            )
            if cur.rowcount == 0:
                return False
            self._record_history(
                obj_id,
                obj_type.__name__,
                "soft_delete",
                json.dumps({"deleted_at": now}),
                actor,
            )
            self._conn.commit()
        self._emit("soft_deleted", obj_id, obj_type.__name__, {})
        return True

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------

    def link(self, src_id: str, dst_id: str, relation: str,
             actor: str = "") -> None:
        if not src_id or not dst_id or not relation:
            raise ValueError("src_id, dst_id, relation are all required")
        if src_id == dst_id:
            raise ValueError("self-relations are not allowed")
        with self._lock:
            try:
                self._conn.execute(
                    "INSERT INTO w14_testing_relations "
                    "(relation_id, src_id, dst_id, relation, created_at) "
                    "VALUES (?,?,?,?,?)",
                    (uuid.uuid4().hex, src_id, dst_id, relation, time.time()),
                )
                self._record_history(
                    src_id,
                    "Relation",
                    "link",
                    json.dumps({
                        "src_id": src_id,
                        "dst_id": dst_id,
                        "relation": relation,
                    }),
                    actor,
                )
                self._conn.commit()
            except sqlite3.IntegrityError:
                # idempotent on duplicate (same src/dst/relation)
                pass
        self._emit("linked", src_id, "Relation", {
            "dst_id": dst_id, "relation": relation,
        })

    def unlink(self, src_id: str, dst_id: str, relation: str,
               actor: str = "") -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM w14_testing_relations "
                "WHERE src_id = ? AND dst_id = ? AND relation = ?",
                (src_id, dst_id, relation),
            )
            if cur.rowcount == 0:
                return False
            self._record_history(
                src_id,
                "Relation",
                "unlink",
                json.dumps({
                    "src_id": src_id, "dst_id": dst_id, "relation": relation,
                }),
                actor,
            )
            self._conn.commit()
        self._emit("unlinked", src_id, "Relation", {
            "dst_id": dst_id, "relation": relation,
        })
        return True

    def get_related(self, src_id: str, relation: str) -> list[str]:
        """Return ids reachable from src_id via the named relation."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT dst_id FROM w14_testing_relations "
                "WHERE src_id = ? AND relation = ? "
                "ORDER BY created_at ASC",
                (src_id, relation),
            ).fetchall()
        return [r["dst_id"] for r in rows]

    def get_inverse_related(self, dst_id: str, relation: str) -> list[str]:
        """Return ids that point to dst_id via the named relation."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT src_id FROM w14_testing_relations "
                "WHERE dst_id = ? AND relation = ? "
                "ORDER BY created_at ASC",
                (dst_id, relation),
            ).fetchall()
        return [r["src_id"] for r in rows]

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def history(self, obj_id: str) -> list[dict[str, Any]]:
        """Return chronological audit log entries for an object id."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT history_id, obj_id, obj_kind, verb, payload, actor, "
                "timestamp FROM w14_testing_history "
                "WHERE obj_id = ? ORDER BY timestamp ASC",
                (obj_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats / health
    # ------------------------------------------------------------------

    def count(self, obj_type: type, include_deleted: bool = False) -> int:
        table = self._table_for(obj_type)
        sql = f"SELECT COUNT(*) AS cnt FROM {table}"
        if not include_deleted:
            sql += " WHERE deleted_at IS NULL"
        with self._lock:
            row = self._conn.execute(sql).fetchone()
        return int(row["cnt"]) if row else 0

    def health(self) -> dict[str, Any]:
        with self._lock:
            counts = {
                cls.__name__: self.count(cls)
                for cls in OBJECT_TABLE_MAP
            }
            history_total = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM w14_testing_history"
            ).fetchone()["cnt"]
            relations_total = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM w14_testing_relations"
            ).fetchone()["cnt"]
        return {
            "ok": True,
            "db_path": self._db_path,
            "counts": counts,
            "history_total": history_total,
            "relations_total": relations_total,
            "ts": time.time(),
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------------------------------------------------------------------------
# In-memory filter helpers (used by .list)
# ---------------------------------------------------------------------------


def _split_filters(
    filters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Partition filters into SQL-pushable (scalar equality) and Python-only.

    Lists/tuples/sets stay in Python because SQL JSON LIKE doesn't model
    membership; everything else is a candidate for the LIKE prefilter.
    """
    sql_filterable: dict[str, Any] = {}
    py_filterable: dict[str, Any] = {}
    for key, value in filters.items():
        if isinstance(value, (list, tuple, set, dict)):
            py_filterable[key] = value
        else:
            sql_filterable[key] = value
    return sql_filterable, py_filterable


def _matches_filters(obj: Any, filters: dict[str, Any]) -> bool:
    """Return True if every filter key matches an attribute on obj."""
    for key, expected in filters.items():
        if not hasattr(obj, key):
            return False
        actual = getattr(obj, key)
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        else:
            if actual != expected:
                return False
    return True


# ---------------------------------------------------------------------------
# Singleton helper (thread-safe init via double-checked lock)
# ---------------------------------------------------------------------------


_singleton: OntologyStore | None = None
_singleton_db_path: str | None = None
_singleton_lock = threading.Lock()


def get_ontology_store(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> OntologyStore:
    global _singleton, _singleton_db_path
    requested_path = str(db_path) if db_path is not None else None
    if _singleton is None or (
        requested_path is not None and _singleton_db_path != requested_path
    ):
        with _singleton_lock:
            if _singleton is not None and (
                requested_path is not None and _singleton_db_path != requested_path
            ):
                try:
                    _singleton.close()
                except Exception:
                    pass
                _singleton = None
            if _singleton is None:
                _singleton = OntologyStore(db_path=db_path, event_bus=event_bus)
                _singleton_db_path = requested_path or ":memory:"
    return _singleton


def reset_ontology_store() -> None:
    """Test-only: drop the singleton so the next call rebuilds it."""
    global _singleton, _singleton_db_path
    with _singleton_lock:
        if _singleton is not None:
            try:
                _singleton.close()
            except Exception:
                pass
        _singleton = None
        _singleton_db_path = None


__all__ = [
    "OntologyStore",
    "get_ontology_store",
    "reset_ontology_store",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
]
