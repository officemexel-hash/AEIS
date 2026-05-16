"""
SYLION Quality -- Golden Set Registry

Manages golden test sets: reference datasets of input/expected-output pairs
used for regression testing.  Each golden set belongs to a category and
contains zero or more test cases with structured JSON input, expected output,
and optional metadata.

SQLite tables: golden_sets, golden_set_cases
Thread-safe via RLock.  EventBus integration via _emit().

Singleton: get_golden_set_registry() / reset_golden_set_registry()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent, get_event_bus

log = logging.getLogger("sylion.quality.golden_set_registry")


class GoldenSetRegistry:
    """Manages golden test sets for regression testing.

    Golden sets are named collections of test cases (input + expected output
    pairs) grouped by category.  Used as reference data to detect regressions
    across pipeline runs.

    Thread-safe. SQLite-backed. Emits events on mutations.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._db_path = str(db_path) if db_path else ":memory:"
        self._event_bus = event_bus
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _ensure_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS golden_sets (
                set_id      TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                category    TEXT NOT NULL DEFAULT '',
                case_count  INTEGER NOT NULL DEFAULT 0,
                created_at  REAL NOT NULL,
                updated_at  REAL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS golden_set_cases (
                case_id          TEXT PRIMARY KEY,
                set_id           TEXT NOT NULL,
                input_json       TEXT NOT NULL DEFAULT '{}',
                expected_output_json TEXT NOT NULL DEFAULT '{}',
                metadata_json    TEXT NOT NULL DEFAULT '{}',
                ordinal          INTEGER NOT NULL DEFAULT 0,
                created_at       REAL NOT NULL,
                FOREIGN KEY (set_id) REFERENCES golden_sets(set_id)
            )
        """)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gsc_set "
            "ON golden_set_cases(set_id)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gs_category "
            "ON golden_sets(category)")
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="quality.golden_set_registry",
            ))

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _parse_json(raw: str | None, default: Any = None) -> Any:
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default

    def _refresh_case_count(self, set_id: str):
        """Update the denormalised case_count on the parent set."""
        with self._lock:
            cnt = self._conn.execute(
                "SELECT COUNT(*) as c FROM golden_set_cases WHERE set_id = ?",
                (set_id,),
            ).fetchone()["c"]
            self._conn.execute(
                "UPDATE golden_sets SET case_count = ?, updated_at = ? "
                "WHERE set_id = ?",
                (cnt, time.time(), set_id),
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Set CRUD
    # ------------------------------------------------------------------

    def create_set(self, name: str, description: str = "",
                   category: str = "") -> dict:
        """Create a new golden set. Returns the set record."""
        set_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO golden_sets
                    (set_id, name, description, category, case_count, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (set_id, name, description, category, now))
            self._conn.commit()

            row = self._conn.execute(
                "SELECT * FROM golden_sets WHERE set_id = ?",
                (set_id,),
            ).fetchone()

        result = dict(row)
        self._emit("golden_set.set_created", {
            "set_id": set_id, "name": name, "category": category,
        })
        log.info("created golden set %s: %s", set_id, name)
        return result

    def update_set(self, set_id: str, **fields) -> dict | None:
        """Update mutable fields on a golden set.

        Accepts keyword arguments: name, description, category.
        Returns the updated record or None if not found.
        """
        allowed = {"name", "description", "category"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_set(set_id)

        updates["updated_at"] = time.time()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [set_id]

        with self._lock:
            n = self._conn.execute(
                f"UPDATE golden_sets SET {set_clause} WHERE set_id = ?",
                values,
            ).rowcount
            self._conn.commit()
            if not n:
                return None

        result = self.get_set(set_id)
        self._emit("golden_set.set_updated", {
            "set_id": set_id, "updated_fields": list(updates.keys()),
        })
        return result

    def delete_set(self, set_id: str) -> bool:
        """Delete a golden set and all its cases."""
        with self._lock:
            n = self._conn.execute(
                "DELETE FROM golden_set_cases WHERE set_id = ?",
                (set_id,),
            ).rowcount
            m = self._conn.execute(
                "DELETE FROM golden_sets WHERE set_id = ?",
                (set_id,),
            ).rowcount
            self._conn.commit()
        if m:
            self._emit("golden_set.set_updated", {
                "set_id": set_id, "action": "deleted",
            })
            log.info("deleted golden set %s (%d cases removed)", set_id, n)
        return bool(m)

    def get_set(self, set_id: str) -> dict | None:
        """Return a golden set record by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM golden_sets WHERE set_id = ?",
                (set_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_sets(self, category: str | None = None,
                  module_id: str | None = None,
                  active_only: bool = False) -> list[dict]:
        """List golden sets, optionally filtered by category/module/active.

        ``module_id`` is treated as an alias for the legacy ``category`` column
        when no explicit ``category`` filter is supplied. ``active_only`` is a
        no-op until status tracking is added — included so route signatures
        remain stable.
        """
        with self._lock:
            q = "SELECT * FROM golden_sets WHERE 1=1"
            params: list[Any] = []
            if category:
                q += " AND category = ?"
                params.append(category)
            elif module_id:
                q += " AND category = ?"
                params.append(module_id)
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def get_results(self, set_id: str, limit: int = 50) -> list[dict]:
        """Return golden-set evaluation results.

        Results table is created lazily; until evaluations have been recorded
        this returns an empty list rather than raising.
        """
        self._ensure_results_table()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM golden_set_results WHERE set_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (set_id, int(limit)),
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            d = dict(r)
            d["details_json"] = self._parse_json(d.get("details_json"), {})
            out.append(d)
        return out

    def _ensure_results_table(self) -> None:
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS golden_set_results (
                    result_id   TEXT PRIMARY KEY,
                    set_id      TEXT NOT NULL,
                    case_id     TEXT NOT NULL DEFAULT '',
                    score       REAL NOT NULL DEFAULT 0.0,
                    passed      INTEGER NOT NULL DEFAULT 0,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at  REAL NOT NULL,
                    FOREIGN KEY (set_id) REFERENCES golden_sets(set_id)
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_gsr_set "
                "ON golden_set_results(set_id)")
            self._conn.commit()

    def record_result(self, set_id: str, case_id: str = "",
                      score: float = 0.0, passed: bool = False,
                      details: dict | None = None) -> dict | None:
        """Persist a single evaluation result. Returns the row dict."""
        if self.get_set(set_id) is None:
            return None
        self._ensure_results_table()
        result_id = self._uid()
        now = time.time()
        details_s = json.dumps(details or {}, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT INTO golden_set_results "
                "(result_id, set_id, case_id, score, passed, details_json, "
                " created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (result_id, set_id, case_id, float(score),
                 int(bool(passed)), details_s, now),
            )
            self._conn.commit()
        return {
            "result_id": result_id, "set_id": set_id, "case_id": case_id,
            "score": float(score), "passed": bool(passed),
            "details_json": details or {}, "created_at": now,
        }

    # ------------------------------------------------------------------
    # Case CRUD
    # ------------------------------------------------------------------

    def add_case(self, set_id: str, input_json: Any = None,
                 expected_output_json: Any = None,
                 metadata_json: Any = None) -> dict | None:
        """Add a single test case to a golden set.

        JSON values are serialised automatically.
        Returns the case record or None if the set does not exist.
        """
        if self.get_set(set_id) is None:
            return None

        case_id = self._uid()
        now = time.time()

        input_s = json.dumps(input_json, default=str) if input_json is not None else "{}"
        expected_s = json.dumps(expected_output_json, default=str) if expected_output_json is not None else "{}"
        metadata_s = json.dumps(metadata_json, default=str) if metadata_json is not None else "{}"

        with self._lock:
            max_ord = self._conn.execute(
                "SELECT COALESCE(MAX(ordinal), -1) as m "
                "FROM golden_set_cases WHERE set_id = ?",
                (set_id,),
            ).fetchone()["m"]
            ordinal = max_ord + 1

            self._conn.execute("""
                INSERT INTO golden_set_cases
                    (case_id, set_id, input_json, expected_output_json,
                     metadata_json, ordinal, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (case_id, set_id, input_s, expected_s,
                  metadata_s, ordinal, now))
            self._conn.commit()

        self._refresh_case_count(set_id)

        result = {
            "case_id": case_id,
            "set_id": set_id,
            "input_json": input_json if input_json is not None else {},
            "expected_output_json": expected_output_json if expected_output_json is not None else {},
            "metadata_json": metadata_json if metadata_json is not None else {},
            "ordinal": ordinal,
        }

        self._emit("golden_set.case_added", {
            "case_id": case_id, "set_id": set_id,
        })
        log.info("added case %s to golden set %s", case_id, set_id)
        return result

    def remove_case(self, case_id: str) -> bool:
        """Remove a single test case by case_id."""
        with self._lock:
            row = self._conn.execute(
                "SELECT set_id FROM golden_set_cases WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            if not row:
                return False
            set_id = row["set_id"]
            self._conn.execute(
                "DELETE FROM golden_set_cases WHERE case_id = ?",
                (case_id,),
            )
            self._conn.commit()
        self._refresh_case_count(set_id)
        return True

    def get_cases(self, set_id: str) -> list[dict]:
        """Return all test cases for a golden set, parsed from JSON."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM golden_set_cases WHERE set_id = ? "
                "ORDER BY ordinal",
                (set_id,),
            ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["input_json"] = self._parse_json(d.get("input_json"), {})
            d["expected_output_json"] = self._parse_json(d.get("expected_output_json"), {})
            d["metadata_json"] = self._parse_json(d.get("metadata_json"), {})
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Flat-register convenience -- single call creates set + 1 case
    # ------------------------------------------------------------------

    def register(
        self,
        set_id: str,
        name: str,
        *,
        module_id: str = "",
        input: Any = None,
        expected_output: Any = None,
        description: str = "",
        category: str = "",
        metadata: dict | None = None,
    ) -> dict:
        """Single-call shortcut that creates a golden set with one case.

        ``set_id`` here is treated as the *external* identifier for this
        golden set; it is stored as the set's ``name`` index key when no
        explicit name is given. Returns the case record (with set_id set
        to the given external set_id).

        Idempotent on (set_id, module_id): re-registering the same set_id
        upserts its first case.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT set_id FROM golden_sets WHERE set_id = ?",
                (set_id,),
            ).fetchone()
            now = time.time()
            if not row:
                self._conn.execute("""
                    INSERT INTO golden_sets
                        (set_id, name, description, category,
                         case_count, created_at)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, (set_id, name, description, category or module_id, now))
                self._conn.commit()
                self._emit("golden_set.set_created", {
                    "set_id": set_id, "name": name, "category": category or module_id,
                })

        meta = metadata or {}
        if module_id:
            meta = {**meta, "module_id": module_id}

        case = self.add_case(
            set_id,
            input_json=input,
            expected_output_json=expected_output,
            metadata_json=meta,
        )
        return case or {"set_id": set_id, "name": name, "registered": True}

    def run_test(
        self,
        set_id: str,
        actual_output: Any,
        case_id: str | None = None,
    ) -> dict:
        """Compare ``actual_output`` against the expected output of a case.

        If ``case_id`` is None, the first case in the set is used. Returns
        ``{set_id, case_id, passed: bool, expected, actual, mismatch: ?}``.
        Raises ValueError if the set or case is missing.
        """
        cases = self.get_cases(set_id)
        if not cases:
            raise ValueError(f"golden set '{set_id}' has no cases")

        if case_id:
            picked = next((c for c in cases if c["case_id"] == case_id), None)
            if picked is None:
                raise ValueError(f"case '{case_id}' not found in set '{set_id}'")
        else:
            picked = cases[0]

        expected = picked["expected_output_json"]
        passed = actual_output == expected

        result = {
            "set_id": set_id,
            "case_id": picked["case_id"],
            "passed": passed,
            "expected": expected,
            "actual": actual_output,
        }
        if not passed:
            result["mismatch"] = {"expected": expected, "actual": actual_output}

        self._emit("golden_set.case_run", {
            "set_id": set_id, "case_id": picked["case_id"], "passed": passed,
        })
        return result

    def import_cases(self, set_id: str,
                     cases_list: list[dict]) -> list[dict]:
        """Bulk-import test cases into a golden set.

        Each dict should have keys: input_json, expected_output_json,
        and optionally metadata_json.
        Returns list of created case records. Returns empty list if set not found.
        """
        if self.get_set(set_id) is None:
            return []

        created: list[dict] = []
        for case_def in cases_list:
            case = self.add_case(
                set_id,
                input_json=case_def.get("input_json"),
                expected_output_json=case_def.get("expected_output_json"),
                metadata_json=case_def.get("metadata_json"),
            )
            if case:
                created.append(case)
        return created


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_registry: GoldenSetRegistry | None = None


def get_golden_set_registry(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GoldenSetRegistry:
    global _registry
    if _registry is None:
        _registry = GoldenSetRegistry(db_path, event_bus)
    return _registry


def reset_golden_set_registry(
    db_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> GoldenSetRegistry:
    global _registry
    _registry = GoldenSetRegistry(db_path, event_bus)
    return _registry
