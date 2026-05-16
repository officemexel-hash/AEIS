"""
SYLION Cognitive -- Feedback Collector

Manages structured feedback collection with categories, items, and responses.
Tracks user feedback on AI interactions through configurable questionnaires.

Tables:
  feedback_categories, feedback_items, feedback_responses

Singleton: get_feedback_collector() / reset_feedback_collector()
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.feedback_collector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ITEM_TYPES = ("text", "rating", "choice", "boolean", "scale")


# ---------------------------------------------------------------------------
# Feedback Collector
# ---------------------------------------------------------------------------

class FeedbackCollector:
    """Manages structured feedback collection.

    Thread-safe. SQLite-backed. Emits events on category creation and response submission.
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

    def _ensure_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS feedback_categories (
                category_id   TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                created_at    REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS feedback_items (
                item_id       TEXT PRIMARY KEY,
                category_id   TEXT NOT NULL,
                question      TEXT NOT NULL DEFAULT '',
                item_type     TEXT NOT NULL DEFAULT 'text',
                options_json  TEXT NOT NULL DEFAULT '[]',
                created_at    REAL NOT NULL,
                FOREIGN KEY (category_id) REFERENCES feedback_categories(category_id)
            );
            CREATE TABLE IF NOT EXISTS feedback_responses (
                response_id   TEXT PRIMARY KEY,
                item_id       TEXT NOT NULL,
                user_id       TEXT NOT NULL DEFAULT '',
                value         TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                submitted_at  REAL NOT NULL,
                FOREIGN KEY (item_id) REFERENCES feedback_items(item_id)
            );
            -- Rating-style feedback (1-5 stars per AI interaction).
            -- Co-located with form-style feedback so a single FeedbackCollector
            -- instance can answer both shapes; cognitive_routes.py /feedback
            -- endpoints bind here.
            CREATE TABLE IF NOT EXISTS feedback_ratings (
                feedback_id    TEXT PRIMARY KEY,
                user_id        TEXT NOT NULL,
                rating         INTEGER NOT NULL,
                category       TEXT NOT NULL DEFAULT 'general',
                comment        TEXT NOT NULL DEFAULT '',
                session_id     TEXT NOT NULL DEFAULT '',
                message_id     TEXT NOT NULL DEFAULT '',
                metadata_json  TEXT NOT NULL DEFAULT '{}',
                created_at     REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_fi_category ON feedback_items(category_id);
            CREATE INDEX IF NOT EXISTS idx_fr_item ON feedback_responses(item_id);
            CREATE INDEX IF NOT EXISTS idx_fr_user ON feedback_responses(user_id);
            CREATE INDEX IF NOT EXISTS idx_fr_submitted ON feedback_responses(submitted_at);
            CREATE INDEX IF NOT EXISTS idx_frt_user ON feedback_ratings(user_id);
            CREATE INDEX IF NOT EXISTS idx_frt_category ON feedback_ratings(category);
            CREATE INDEX IF NOT EXISTS idx_frt_session ON feedback_ratings(session_id);
            CREATE INDEX IF NOT EXISTS idx_frt_created ON feedback_ratings(created_at);
        """)
        self._conn.commit()

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="cognitive.feedback_collector",
            ))

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def create_category(self, name: str, description: str = "") -> dict:
        """Create a new feedback category. Returns category dict."""
        if not name or not name.strip():
            raise ValueError("Category name must not be empty")

        category_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO feedback_categories "
                "(category_id, name, description, created_at) VALUES (?, ?, ?, ?)",
                (category_id, name.strip(), description, now),
            )
            self._conn.commit()

        result = {
            "category_id": category_id, "name": name.strip(),
            "description": description, "created_at": now,
        }
        self._emit("category_created", {"category_id": category_id, "name": name.strip()})
        log.info("create_category %s [%s]", category_id[:12], name.strip())
        return result

    def list_categories(self) -> list[dict]:
        """List all feedback categories."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM feedback_categories ORDER BY created_at ASC",
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def create_item(self, category_id: str, question: str,
                    item_type: str = "text", options_json: str = "[]") -> dict:
        """Create a new feedback item within a category. Returns item dict."""
        if item_type not in VALID_ITEM_TYPES:
            raise ValueError(
                f"Invalid item_type '{item_type}'. "
                f"Must be one of {VALID_ITEM_TYPES}"
            )
        if not question or not question.strip():
            raise ValueError("Question must not be empty")
        try:
            opts = json.loads(options_json)
            if not isinstance(opts, list):
                raise ValueError("options_json must be a JSON array")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid options_json: {exc}") from exc

        item_id = self._uid()
        now = time.time()

        with self._lock:
            cat = self._conn.execute(
                "SELECT category_id FROM feedback_categories WHERE category_id = ?",
                (category_id,),
            ).fetchone()
            if not cat:
                raise ValueError(f"Category '{category_id}' not found")

            self._conn.execute(
                "INSERT INTO feedback_items "
                "(item_id, category_id, question, item_type, options_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, category_id, question.strip(), item_type, options_json, now),
            )
            self._conn.commit()

        result = {
            "item_id": item_id, "category_id": category_id,
            "question": question.strip(), "item_type": item_type,
            "options_json": options_json, "created_at": now,
        }
        log.info("create_item %s [%s]", item_id[:12], item_type)
        return result

    def list_items(self, category_id: str | None = None) -> list[dict]:
        """List feedback items, optionally filtered by category."""
        with self._lock:
            if category_id is not None:
                rows = self._conn.execute(
                    "SELECT * FROM feedback_items WHERE category_id = ? "
                    "ORDER BY created_at ASC",
                    (category_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM feedback_items ORDER BY created_at ASC",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------

    def submit_response(self, item_id: str, user_id: str, value: str,
                        metadata_json: str = "{}") -> dict:
        """Submit a response to a feedback item. Returns response dict."""
        try:
            meta = json.loads(metadata_json)
            if not isinstance(meta, dict):
                raise ValueError("metadata_json must be a JSON object")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid metadata_json: {exc}") from exc

        response_id = self._uid()
        now = time.time()

        with self._lock:
            item = self._conn.execute(
                "SELECT item_id FROM feedback_items WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            if not item:
                raise ValueError(f"Item '{item_id}' not found")

            self._conn.execute(
                "INSERT INTO feedback_responses "
                "(response_id, item_id, user_id, value, metadata_json, submitted_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (response_id, item_id, user_id, value, metadata_json, now),
            )
            self._conn.commit()

        result = {
            "response_id": response_id, "item_id": item_id,
            "user_id": user_id, "value": value,
            "metadata_json": metadata_json, "submitted_at": now,
        }
        self._emit("response_submitted", {
            "response_id": response_id, "item_id": item_id, "user_id": user_id,
        })
        log.info("submit_response %s for item %s by %s",
                 response_id[:12], item_id[:12], user_id[:12])
        return result

    def get_responses(self, item_id: str | None = None,
                      user_id: str | None = None) -> list[dict]:
        """Get responses with optional filters."""
        with self._lock:
            clauses: list[str] = []
            params: list = []

            if item_id is not None:
                clauses.append("item_id = ?")
                params.append(item_id)
            if user_id is not None:
                clauses.append("user_id = ?")
                params.append(user_id)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM feedback_responses{where} "
                f"ORDER BY submitted_at DESC",
                params,
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_item_stats(self, item_id: str) -> dict:
        """Get aggregate statistics for a specific item."""
        with self._lock:
            item_row = self._conn.execute(
                "SELECT * FROM feedback_items WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            if not item_row:
                return {"item_id": item_id, "response_count": 0}

            count_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_responses WHERE item_id = ?",
                (item_id,),
            ).fetchone()
            response_count = count_row["cnt"] if count_row else 0

            # Try to compute average for numeric values
            try:
                avg_row = self._conn.execute(
                    "SELECT AVG(CAST(value AS REAL)) as avg_val "
                    "FROM feedback_responses WHERE item_id = ?",
                    (item_id,),
                ).fetchone()
                avg_value = avg_row["avg_val"] if avg_row and avg_row["avg_val"] is not None else None
            except Exception:
                avg_value = None

        return {
            "item_id": item_id,
            "question": item_row["question"],
            "item_type": item_row["item_type"],
            "response_count": response_count,
            "avg_value": round(avg_value, 4) if avg_value is not None else None,
        }

    def get_category_stats(self) -> dict:
        """Get aggregate statistics across all categories."""
        with self._lock:
            cat_rows = self._conn.execute(
                "SELECT c.category_id, c.name, "
                "COUNT(DISTINCT i.item_id) as item_count, "
                "COUNT(r.response_id) as response_count "
                "FROM feedback_categories c "
                "LEFT JOIN feedback_items i ON c.category_id = i.category_id "
                "LEFT JOIN feedback_responses r ON i.item_id = r.item_id "
                "GROUP BY c.category_id ORDER BY c.created_at",
            ).fetchall()
            categories = [dict(r) for r in cat_rows]

            total_items = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_items",
            ).fetchone()["cnt"]

            total_responses = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM feedback_responses",
            ).fetchone()["cnt"]

        return {
            "total_categories": len(categories),
            "total_items": total_items,
            "total_responses": total_responses,
            "categories": categories,
        }

    def export_feedback(self, category_id: str | None = None) -> list[dict]:
        """Export feedback responses, optionally filtered by category."""
        with self._lock:
            if category_id is not None:
                rows = self._conn.execute(
                    "SELECT r.*, i.question, i.item_type, i.category_id "
                    "FROM feedback_responses r "
                    "JOIN feedback_items i ON r.item_id = i.item_id "
                    "WHERE i.category_id = ? "
                    "ORDER BY r.submitted_at DESC",
                    (category_id,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT r.*, i.question, i.item_type, i.category_id "
                    "FROM feedback_responses r "
                    "JOIN feedback_items i ON r.item_id = i.item_id "
                    "ORDER BY r.submitted_at DESC",
                ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Rating-style feedback (cognitive_routes.py /feedback endpoints).
    # Co-located here so the API has a single FeedbackCollector binding.
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_rating(row) -> dict:
        d = dict(row)
        meta = d.pop("metadata_json", "{}") or "{}"
        try:
            d["metadata"] = json.loads(meta)
        except Exception:
            d["metadata"] = {}
        return d

    def submit_feedback(self, user_id: str, rating: int, *,
                        category: str = "general",
                        comment: str | None = None,
                        session_id: str | None = None,
                        message_id: str | None = None,
                        metadata: dict | None = None) -> dict:
        """Record a star-rating feedback entry. Returns the persisted row."""
        if not user_id or not user_id.strip():
            raise ValueError("user_id must not be empty")
        if not isinstance(rating, int) or not 1 <= rating <= 5:
            raise ValueError("rating must be int in [1, 5]")
        feedback_id = self._uid()
        now = time.time()
        meta_json = json.dumps(metadata) if metadata else "{}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO feedback_ratings "
                "(feedback_id, user_id, rating, category, comment, session_id, "
                " message_id, metadata_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (feedback_id, user_id.strip(), rating, category or "general",
                 comment or "", session_id or "", message_id or "",
                 meta_json, now),
            )
            self._conn.commit()
        self._emit("rating_submitted", {
            "feedback_id": feedback_id, "user_id": user_id.strip(),
            "rating": rating, "category": category or "general",
        })
        return {
            "feedback_id": feedback_id, "user_id": user_id.strip(),
            "rating": rating, "category": category or "general",
            "comment": comment or "", "session_id": session_id or "",
            "message_id": message_id or "", "metadata": metadata or {},
            "created_at": now,
        }

    def list_feedback(self, *, user_id: str | None = None,
                      session_id: str | None = None,
                      category: str | None = None,
                      min_rating: int | None = None,
                      max_rating: int | None = None,
                      since: float | None = None,
                      limit: int = 50) -> list[dict]:
        """List rating entries with optional filters."""
        clauses = []
        params: list = []
        if user_id:
            clauses.append("user_id = ?"); params.append(user_id)
        if session_id:
            clauses.append("session_id = ?"); params.append(session_id)
        if category:
            clauses.append("category = ?"); params.append(category)
        if min_rating is not None:
            clauses.append("rating >= ?"); params.append(min_rating)
        if max_rating is not None:
            clauses.append("rating <= ?"); params.append(max_rating)
        if since is not None:
            clauses.append("created_at >= ?"); params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM feedback_ratings{where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_rating(r) for r in rows]

    def get_feedback(self, feedback_id: str) -> dict | None:
        """Get a rating entry by id, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM feedback_ratings WHERE feedback_id = ?",
                (feedback_id,),
            ).fetchone()
        return self._row_to_rating(row) if row else None

    def delete_feedback(self, feedback_id: str) -> bool:
        """Delete a rating entry. Returns True if a row was deleted."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM feedback_ratings WHERE feedback_id = ?",
                (feedback_id,),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_feedback_stats(self) -> dict:
        """Aggregate stats over the rating table."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS total, AVG(rating) AS avg_rating, "
                "MIN(created_at) AS first_at, MAX(created_at) AS last_at "
                "FROM feedback_ratings",
            ).fetchone()
            by_cat = self._conn.execute(
                "SELECT category, COUNT(*) AS count, AVG(rating) AS avg_rating "
                "FROM feedback_ratings GROUP BY category",
            ).fetchall()
        total = (row["total"] if row else 0) or 0
        avg = (row["avg_rating"] if row and row["avg_rating"] is not None else 0.0) or 0.0
        return {
            "total": total,
            "avg_rating": round(float(avg), 3),
            "first_at": (row["first_at"] if row else None),
            "last_at": (row["last_at"] if row else None),
            "by_category": [
                {"category": r["category"], "count": r["count"],
                 "avg_rating": round(float(r["avg_rating"] or 0.0), 3)}
                for r in by_cat
            ],
        }

    def get_average_rating(self, *, user_id: str | None = None,
                           category: str | None = None,
                           since: float | None = None) -> dict:
        """Average rating with optional filters."""
        clauses = []
        params: list = []
        if user_id:
            clauses.append("user_id = ?"); params.append(user_id)
        if category:
            clauses.append("category = ?"); params.append(category)
        if since is not None:
            clauses.append("created_at >= ?"); params.append(since)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS count, AVG(rating) AS avg_rating "
                f"FROM feedback_ratings{where}",
                params,
            ).fetchone()
        return {
            "count": (row["count"] if row else 0) or 0,
            "avg_rating": round(float((row["avg_rating"] if row and row["avg_rating"] is not None else 0.0) or 0.0), 3),
            "filters": {"user_id": user_id, "category": category, "since": since},
        }

    def get_summaries(self, *, category: str | None = None,
                      limit: int = 30) -> list[dict]:
        """Recent summary buckets per day for the given category."""
        clauses = []
        params: list = []
        if category:
            clauses.append("category = ?"); params.append(category)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(
                f"SELECT DATE(created_at, 'unixepoch') AS day, "
                f"COUNT(*) AS count, AVG(rating) AS avg_rating "
                f"FROM feedback_ratings{where} "
                f"GROUP BY day ORDER BY day DESC LIMIT ?",
                params,
            ).fetchall()
        return [
            {"day": r["day"], "count": r["count"],
             "avg_rating": round(float(r["avg_rating"] or 0.0), 3)}
            for r in rows
        ]

    def generate_summary(self, period: str, *,
                         category: str = "general") -> dict:
        """Generate a textual summary for a period (day/week/month)."""
        if period not in ("day", "week", "month"):
            raise ValueError("period must be one of: day, week, month")
        seconds = {"day": 86400, "week": 86400 * 7, "month": 86400 * 30}[period]
        since = time.time() - seconds
        clauses = ["created_at >= ?"]
        params: list = [since]
        if category:
            clauses.append("category = ?"); params.append(category)
        where = " WHERE " + " AND ".join(clauses)
        with self._lock:
            row = self._conn.execute(
                f"SELECT COUNT(*) AS count, AVG(rating) AS avg_rating "
                f"FROM feedback_ratings{where}",
                params,
            ).fetchone()
        return {
            "period": period,
            "category": category,
            "since": since,
            "count": (row["count"] if row else 0) or 0,
            "avg_rating": round(float((row["avg_rating"] if row and row["avg_rating"] is not None else 0.0) or 0.0), 3),
        }

    def get_trend(self, *, days: int = 7,
                  category: str | None = None) -> list[dict]:
        """Daily trend for the last N days."""
        if days < 1:
            days = 1
        since = time.time() - (days * 86400)
        clauses = ["created_at >= ?"]
        params: list = [since]
        if category:
            clauses.append("category = ?"); params.append(category)
        where = " WHERE " + " AND ".join(clauses)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT DATE(created_at, 'unixepoch') AS day, "
                f"COUNT(*) AS count, AVG(rating) AS avg_rating "
                f"FROM feedback_ratings{where} "
                f"GROUP BY day ORDER BY day ASC",
                params,
            ).fetchall()
        return [
            {"day": r["day"], "count": r["count"],
             "avg_rating": round(float(r["avg_rating"] or 0.0), 3)}
            for r in rows
        ]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_collector: FeedbackCollector | None = None


def get_feedback_collector(db_path: str | Path | None = None,
                           event_bus: EventBus | None = None) -> FeedbackCollector:
    global _collector
    if _collector is None:
        _collector = FeedbackCollector(db_path, event_bus)
    return _collector


def reset_feedback_collector(db_path: str | Path | None = None,
                             event_bus: EventBus | None = None) -> FeedbackCollector:
    global _collector
    _collector = FeedbackCollector(db_path, event_bus)
    return _collector
