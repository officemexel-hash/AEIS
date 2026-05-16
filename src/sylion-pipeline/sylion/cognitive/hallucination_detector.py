"""
SYLION Cognitive -- Hallucination Detector

Detects and records potential hallucinations from LLM outputs.
Tracks verification status, confidence scores, and recurring patterns.

Tables:
  hallucination_checks, hallucination_patterns

Singleton: get_hallucination_detector() / reset_hallucination_detector()
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
import uuid
from collections import Counter
from pathlib import Path

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.cognitive.hallucination_detector")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = ("pending", "verified", "hallucination", "false_positive", "inconclusive")
VALID_SOURCE_TYPES = ("llm_call", "council_analysis", "chat_message", "plan_task", "evaluation")


# ---------------------------------------------------------------------------
# Hallucination Detector
# ---------------------------------------------------------------------------

class HallucinationDetector:
    """Detects and records potential hallucinations from LLM outputs.

    Thread-safe. SQLite-backed. Emits events on hallucination detection.
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
            CREATE TABLE IF NOT EXISTS hallucination_checks (
                check_id           TEXT PRIMARY KEY,
                source_type        TEXT NOT NULL DEFAULT '',
                source_id          TEXT NOT NULL DEFAULT '',
                claim              TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'pending',
                confidence         REAL NOT NULL DEFAULT 0.0,
                evidence           TEXT NOT NULL DEFAULT '',
                detected_at        REAL NOT NULL,
                resolved_at        REAL
            );
            CREATE TABLE IF NOT EXISTS hallucination_patterns (
                pattern_id   TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL DEFAULT '',
                description  TEXT NOT NULL DEFAULT '',
                frequency    INTEGER NOT NULL DEFAULT 1,
                last_seen    REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_hc_status ON hallucination_checks(verification_status);
            CREATE INDEX IF NOT EXISTS idx_hc_source_type ON hallucination_checks(source_type);
            CREATE INDEX IF NOT EXISTS idx_hc_detected_at ON hallucination_checks(detected_at);
            CREATE INDEX IF NOT EXISTS idx_hp_pattern_type ON hallucination_patterns(pattern_type);
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
                source_module="cognitive.hallucination_detector",
            ))

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_source_type(source_type: str):
        if source_type not in VALID_SOURCE_TYPES:
            raise ValueError(
                f"Invalid source_type '{source_type}'. "
                f"Must be one of {VALID_SOURCE_TYPES}"
            )

    @staticmethod
    def _validate_status(status: str):
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status '{status}'. "
                f"Must be one of {VALID_STATUSES}"
            )

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def check_claim(self, source_type: str, source_id: str, claim: str,
                    expected_answer: str = "") -> dict:
        """Create a new hallucination check record. Returns check dict."""
        self._validate_source_type(source_type)

        check_id = self._uid()
        now = time.time()

        with self._lock:
            self._conn.execute(
                "INSERT INTO hallucination_checks "
                "(check_id, source_type, source_id, claim, "
                "verification_status, confidence, evidence, detected_at, resolved_at) "
                "VALUES (?, ?, ?, ?, 'pending', 0.0, ?, ?, NULL)",
                (check_id, source_type, source_id, claim, expected_answer, now),
            )
            self._conn.commit()

        result = {
            "check_id": check_id,
            "source_type": source_type,
            "source_id": source_id,
            "claim": claim,
            "verification_status": "pending",
            "confidence": 0.0,
            "evidence": expected_answer,
            "detected_at": now,
            "resolved_at": None,
        }
        log.info("check_claim %s for %s/%s", check_id[:12], source_type, source_id[:12])
        return result

    def verify_check(self, check_id: str, is_hallucination: bool,
                     confidence: float, evidence: str = "") -> dict | None:
        """Update verification status of a check. Returns updated dict or None."""
        status = "hallucination" if is_hallucination else "verified"
        self._validate_status(status)

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, confidence))

        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hallucination_checks WHERE check_id = ?",
                (check_id,),
            ).fetchone()
            if not row:
                return None

            self._conn.execute(
                "UPDATE hallucination_checks "
                "SET verification_status = ?, confidence = ?, evidence = ? "
                "WHERE check_id = ?",
                (status, confidence, evidence, check_id),
            )
            self._conn.commit()

        result = dict(row)
        result["verification_status"] = status
        result["confidence"] = confidence
        result["evidence"] = evidence

        if is_hallucination:
            self._emit("hallucination.detected", {
                "check_id": check_id,
                "source_type": result["source_type"],
                "source_id": result["source_id"],
                "claim": result["claim"],
                "confidence": confidence,
                "evidence": evidence,
            })

        log.info("verify_check %s -> %s (confidence=%.2f)", check_id[:12], status, confidence)
        return result

    def list_checks(self, status: str | None = None,
                    source_type: str | None = None,
                    limit: int = 100) -> list[dict]:
        """List checks with optional filters."""
        with self._lock:
            clauses: list[str] = []
            params: list = []

            if status is not None:
                self._validate_status(status)
                clauses.append("verification_status = ?")
                params.append(status)
            if source_type is not None:
                self._validate_source_type(source_type)
                clauses.append("source_type = ?")
                params.append(source_type)

            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            rows = self._conn.execute(
                f"SELECT * FROM hallucination_checks{where} "
                f"ORDER BY detected_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()

        return [dict(r) for r in rows]

    def get_check(self, check_id: str) -> dict | None:
        """Retrieve a single check by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hallucination_checks WHERE check_id = ?",
                (check_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_stats(self) -> dict:
        """Aggregate counts by verification status."""
        with self._lock:
            total_row = self._conn.execute(
                "SELECT COUNT(*) as cnt FROM hallucination_checks",
            ).fetchone()
            total = total_row["cnt"] if total_row else 0

            status_rows = self._conn.execute(
                "SELECT verification_status, COUNT(*) as cnt "
                "FROM hallucination_checks GROUP BY verification_status",
            ).fetchall()
            by_status = {r["verification_status"]: r["cnt"] for r in status_rows}

            source_rows = self._conn.execute(
                "SELECT source_type, COUNT(*) as cnt "
                "FROM hallucination_checks GROUP BY source_type",
            ).fetchall()
            by_source_type = {r["source_type"]: r["cnt"] for r in source_rows}

            avg_row = self._conn.execute(
                "SELECT AVG(confidence) as avg_conf "
                "FROM hallucination_checks WHERE verification_status = 'hallucination'",
            ).fetchone()

        return {
            "total": total,
            "by_status": {s: by_status.get(s, 0) for s in VALID_STATUSES},
            "by_source_type": by_source_type,
            "avg_hallucination_confidence": round(avg_row["avg_conf"], 4)
            if avg_row and avg_row["avg_conf"] is not None else 0.0,
        }

    def detect_patterns(self) -> list[dict]:
        """Analyze checks for recurring hallucination patterns.

        Looks for:
          - Frequent hallucinations grouped by source_type
          - Frequent hallucinations grouped by similarity of claim prefix
        Returns list of pattern dicts and upserts into hallucination_patterns.
        """
        with self._lock:
            # Pattern 1: hallucination frequency by source_type
            source_rows = self._conn.execute(
                "SELECT source_type, COUNT(*) as cnt "
                "FROM hallucination_checks "
                "WHERE verification_status = 'hallucination' "
                "GROUP BY source_type HAVING cnt >= 1 "
                "ORDER BY cnt DESC",
            ).fetchall()

            # Pattern 2: hallucination by claim prefix (first 80 chars)
            claim_rows = self._conn.execute(
                "SELECT SUBSTR(claim, 1, 80) as claim_prefix, COUNT(*) as cnt "
                "FROM hallucination_checks "
                "WHERE verification_status = 'hallucination' "
                "GROUP BY claim_prefix HAVING cnt > 1 "
                "ORDER BY cnt DESC",
            ).fetchall()

            now = time.time()
            patterns: list[dict] = []

            # Upsert source-type patterns
            for r in source_rows:
                pattern_id = self._uid()
                desc = f"Recurring hallucinations from source_type '{r['source_type']}'"
                self._upsert_pattern(
                    f"source_type:{r['source_type']}",
                    "source_type_recurring",
                    desc,
                    r["cnt"],
                    now,
                )
                patterns.append({
                    "pattern_type": "source_type_recurring",
                    "description": desc,
                    "frequency": r["cnt"],
                    "source_type": r["source_type"],
                })

            # Upsert claim-prefix patterns
            for r in claim_rows:
                desc = f"Repeated hallucination claim prefix: '{r['claim_prefix']}...'"
                self._upsert_pattern(
                    f"claim_prefix:{r['claim_prefix']}",
                    "claim_prefix_recurring",
                    desc,
                    r["cnt"],
                    now,
                )
                patterns.append({
                    "pattern_type": "claim_prefix_recurring",
                    "description": desc,
                    "frequency": r["cnt"],
                    "claim_prefix": r["claim_prefix"],
                })

            self._conn.commit()

        log.info("detect_patterns found %d patterns", len(patterns))
        return patterns

    def _upsert_pattern(self, pattern_key: str, pattern_type: str,
                        description: str, frequency: int, last_seen: float):
        """Insert or update a hallucination_pattern row."""
        existing = self._conn.execute(
            "SELECT pattern_id, frequency FROM hallucination_patterns WHERE pattern_id = ?",
            (pattern_key,),
        ).fetchone()

        if existing:
            new_freq = max(existing["frequency"], frequency)
            self._conn.execute(
                "UPDATE hallucination_patterns "
                "SET frequency = ?, last_seen = ?, description = ? "
                "WHERE pattern_id = ?",
                (new_freq, last_seen, description, pattern_key),
            )
        else:
            self._conn.execute(
                "INSERT INTO hallucination_patterns "
                "(pattern_id, pattern_type, description, frequency, last_seen) "
                "VALUES (?, ?, ?, ?, ?)",
                (pattern_key, pattern_type, description, frequency, last_seen),
            )

    def resolve_check(self, check_id: str) -> dict | None:
        """Mark a check as resolved by setting resolved_at timestamp."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hallucination_checks WHERE check_id = ?",
                (check_id,),
            ).fetchone()
            if not row:
                return None

            now = time.time()
            self._conn.execute(
                "UPDATE hallucination_checks SET resolved_at = ? WHERE check_id = ?",
                (now, check_id),
            )
            self._conn.commit()

        result = dict(row)
        result["resolved_at"] = now
        log.info("resolve_check %s", check_id[:12])
        return result


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_detector: HallucinationDetector | None = None


def get_hallucination_detector(db_path: str | Path | None = None,
                               event_bus: EventBus | None = None) -> HallucinationDetector:
    global _detector
    if _detector is None:
        _detector = HallucinationDetector(db_path, event_bus)
    return _detector


def reset_hallucination_detector(db_path: str | Path | None = None,
                                 event_bus: EventBus | None = None) -> HallucinationDetector:
    global _detector
    _detector = HallucinationDetector(db_path, event_bus)
    return _detector
