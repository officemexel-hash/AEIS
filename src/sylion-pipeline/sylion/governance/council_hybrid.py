"""
SYLION Governance -- Council Hybrid

Multi-model deliberation engine with parallel analysis, discussion rounds,
and consolidation.  Models submit independent analyses, then engage in
structured discussion rounds before a consolidated verdict is produced.

Tables:
  hybrid_council_sessions  -- deliberation sessions
  model_analyses           -- per-model analysis + verdict
  discussion_rounds        -- structured discussion contributions

Phases: parallel_analysis -> verdicts -> discussion -> consolidated

Singleton: get_council_hybrid() / reset_council_hybrid()
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

log = logging.getLogger("sylion.governance.council_hybrid")

VALID_PHASES = ("parallel_analysis", "verdicts", "discussion", "consolidated", "closed")

VALID_VERDICTS = ("approve", "reject", "conditional")

# Sentinels are guard evaluators, so their contract is pass/warn/fail. Keep
# "reject" for older audit rows and migration compatibility.
VALID_SENTINEL_VERDICTS = ("pass", "warn", "fail", "reject")

# Canonical council roles (CLAUDE_AEIS_FULL_MODEL row 14 + hard adversarial critic).
VALID_ROLES = (
    "planner", "architect", "critic", "adversarial_critic", "verifier", "governance",
    "cost_sentinel", "security_sentinel",
    "domain_specialist", "funding_specialist",
)

# Canonical 5 council ranks
VALID_RANKS = ("primary", "senior", "support", "review_only", "validation_only")

# Default voting weight per role (sums roughly to 1.0 across primary roles).
# Sentinels and review-only roles have lower default weight; critic roles carry
# blocking power via signature requirement, not vote weight inflation.
DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "planner":            1.0,
    "architect":          1.0,
    "critic":             1.0,
    "adversarial_critic":  1.0,
    "verifier":           0.8,
    "governance":         1.0,
    "cost_sentinel":      0.5,
    "security_sentinel":  0.5,
    "domain_specialist":  0.8,
    "funding_specialist": 0.8,
}

# Rank multiplier on top of role weight.
RANK_MULTIPLIER: dict[str, float] = {
    "primary":         1.0,
    "senior":          0.9,
    "support":         0.7,
    "review_only":     0.5,
    "validation_only": 0.4,
}

SENTINEL_ROLES = ("cost_sentinel", "security_sentinel")


def compute_role_weight(
    role: str, rank: str, role_weights: dict, rank_multiplier: dict,
) -> float:
    if not isinstance(role, str) or not isinstance(rank, str):
        raise TypeError("role and rank must be strings")
    return float(role_weights.get(role, 1.0) * rank_multiplier.get(rank, 1.0))


class CouncilHybrid:
    """Multi-model deliberation engine.

    Phases: parallel_analysis -> verdicts -> discussion -> consolidated

    Every method is thread-safe via an RLock.  Events are published through
    the optional EventBus.
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
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS hybrid_council_sessions (
                session_id       TEXT PRIMARY KEY,
                topic            TEXT NOT NULL,
                models           TEXT NOT NULL DEFAULT '[]',
                context          TEXT NOT NULL DEFAULT '',
                moderator_model  TEXT NOT NULL DEFAULT '',
                phase            TEXT NOT NULL DEFAULT 'parallel_analysis',
                status           TEXT NOT NULL DEFAULT 'open',
                consolidated_text TEXT NOT NULL DEFAULT '',
                consensus_level  REAL NOT NULL DEFAULT 0.0,
                created_at       REAL NOT NULL,
                closed_at        REAL
            );
            CREATE INDEX IF NOT EXISTS idx_hcs_phase ON hybrid_council_sessions(phase);
            CREATE INDEX IF NOT EXISTS idx_hcs_status ON hybrid_council_sessions(status);

            CREATE TABLE IF NOT EXISTS model_analyses (
                analysis_id      TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                model_id         TEXT NOT NULL,
                analysis_text    TEXT NOT NULL DEFAULT '',
                verdict          TEXT NOT NULL DEFAULT '',
                confidence       REAL NOT NULL DEFAULT 0.0,
                rationale        TEXT NOT NULL DEFAULT '',
                rating           REAL,
                created_at       REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hybrid_council_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ma_session ON model_analyses(session_id);
            CREATE INDEX IF NOT EXISTS idx_ma_model  ON model_analyses(model_id);

            CREATE TABLE IF NOT EXISTS discussion_rounds (
                round_id         TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                round_number     INTEGER NOT NULL DEFAULT 0,
                model_id         TEXT NOT NULL,
                contribution     TEXT NOT NULL DEFAULT '',
                reaction_to      TEXT,
                created_at       REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hybrid_council_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_dr_session ON discussion_rounds(session_id);

            CREATE TABLE IF NOT EXISTS council_participants (
                participant_id   TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                model_id         TEXT NOT NULL,
                role             TEXT NOT NULL,
                rank             TEXT NOT NULL DEFAULT 'primary',
                weight           REAL NOT NULL DEFAULT 1.0,
                joined_at        REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hybrid_council_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_cp_session ON council_participants(session_id);
            CREATE INDEX IF NOT EXISTS idx_cp_role    ON council_participants(role);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cp_unique
                ON council_participants(session_id, model_id, role);

            CREATE TABLE IF NOT EXISTS council_critic_signatures (
                signature_id     TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                model_id         TEXT NOT NULL,
                signed_decision  TEXT NOT NULL,
                signature_hash   TEXT NOT NULL,
                rationale        TEXT NOT NULL DEFAULT '',
                signed_at        REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hybrid_council_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_ccs_session ON council_critic_signatures(session_id);

            CREATE TABLE IF NOT EXISTS council_sentinel_evaluations (
                evaluation_id    TEXT PRIMARY KEY,
                session_id       TEXT NOT NULL,
                sentinel_role    TEXT NOT NULL,
                model_id         TEXT NOT NULL,
                verdict          TEXT NOT NULL,
                score            REAL NOT NULL DEFAULT 0.0,
                details          TEXT NOT NULL DEFAULT '',
                evaluated_at     REAL NOT NULL,
                FOREIGN KEY (session_id) REFERENCES hybrid_council_sessions(session_id)
            );
            CREATE INDEX IF NOT EXISTS idx_cse_session  ON council_sentinel_evaluations(session_id);
            CREATE INDEX IF NOT EXISTS idx_cse_role     ON council_sentinel_evaluations(sentinel_role);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uid() -> str:
        return uuid.uuid4().hex[:12]

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="",
                topic=topic,
                payload=payload,
                source_module="governance.council_hybrid",
            ))

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> dict:
        d = dict(row)
        # Decode JSON fields on sessions
        for key in ("models",):
            if key in d and isinstance(d[key], str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d

    def _session_row(self, row: sqlite3.Row) -> dict:
        d = dict(row)
        if "models" in d and isinstance(d["models"], str):
            try:
                d["models"] = json.loads(d["models"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ------------------------------------------------------------------
    # Public API -- Sessions
    # ------------------------------------------------------------------

    def open_session(
        self,
        topic: str,
        models: list[str],
        context: str | None = None,
        moderator_model: str | None = None,
    ) -> dict:
        """Create a new hybrid council session.

        Returns the created session dict.
        """
        session_id = self._uid()
        now = time.time()
        models_json = json.dumps(models, sort_keys=True)

        with self._lock:
            self._conn.execute("""
                INSERT INTO hybrid_council_sessions
                (session_id, topic, models, context, moderator_model,
                 phase, status, consolidated_text, consensus_level,
                 created_at, closed_at)
                VALUES (?, ?, ?, ?, ?, 'parallel_analysis', 'open', '', 0.0, ?, NULL)
            """, (
                session_id, topic, models_json,
                context or "", moderator_model or "",
                now,
            ))
            self._conn.commit()

        result = {
            "session_id": session_id,
            "topic": topic,
            "models": models,
            "context": context or "",
            "moderator_model": moderator_model or "",
            "phase": "parallel_analysis",
            "status": "open",
            "created_at": now,
        }

        self._emit("council.session.opened", {
            "session_id": session_id,
            "topic": topic,
        })
        log.info("council session opened: %s -- %s", session_id, topic)
        return result

    def get_session(self, session_id: str) -> dict | None:
        """Return a single session by ID."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hybrid_council_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return self._session_row(row)

    def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """List sessions, optionally filtered by status."""
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM hybrid_council_sessions "
                    "WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM hybrid_council_sessions "
                    "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [self._session_row(r) for r in rows]

    def close_session(self, session_id: str) -> dict | None:
        """Close an open session."""
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            self._conn.execute(
                "UPDATE hybrid_council_sessions "
                "SET status = 'closed', closed_at = ?, phase = 'closed' "
                "WHERE session_id = ?",
                (now, session_id),
            )
            self._conn.commit()

        self._emit("council.session.closed", {
            "session_id": session_id,
        })
        log.info("council session closed: %s", session_id)
        return {"session_id": session_id, "status": "closed", "closed_at": now}

    # ------------------------------------------------------------------
    # Public API -- Analyses
    # ------------------------------------------------------------------

    def add_analysis(
        self,
        session_id: str,
        model_id: str,
        analysis_text: str,
        verdict: str,
        confidence: float,
        rationale: str,
    ) -> dict:
        """Add a model analysis to a session.

        Returns the created analysis dict.
        """
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Invalid verdict '{verdict}', "
                f"must be one of {VALID_VERDICTS}"
            )

        analysis_id = self._uid()
        now = time.time()

        with self._lock:
            # Verify session exists
            row = self._conn.execute(
                "SELECT session_id, phase FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            self._conn.execute("""
                INSERT INTO model_analyses
                (analysis_id, session_id, model_id, analysis_text,
                 verdict, confidence, rationale, rating, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)
            """, (
                analysis_id, session_id, model_id, analysis_text,
                verdict, confidence, rationale, now,
            ))

            # Advance phase from parallel_analysis to verdicts if still there
            current_phase = row["phase"]
            if current_phase == "parallel_analysis":
                self._conn.execute(
                    "UPDATE hybrid_council_sessions SET phase = 'verdicts' "
                    "WHERE session_id = ?",
                    (session_id,),
                )

            self._conn.commit()

        result = {
            "analysis_id": analysis_id,
            "session_id": session_id,
            "model_id": model_id,
            "analysis_text": analysis_text,
            "verdict": verdict,
            "confidence": confidence,
            "rationale": rationale,
            "created_at": now,
        }

        self._emit("council.analysis.added", {
            "session_id": session_id,
            "analysis_id": analysis_id,
            "model_id": model_id,
            "verdict": verdict,
        })
        log.info("analysis added: %s model=%s verdict=%s",
                 analysis_id, model_id, verdict)
        return result

    def get_analyses(self, session_id: str) -> list[dict]:
        """Return all model analyses for a session."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM model_analyses WHERE session_id = ? "
                "ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Public API -- Discussion
    # ------------------------------------------------------------------

    def add_discussion_round(
        self,
        session_id: str,
        round_number: int,
        model_id: str,
        contribution: str,
        reaction_to: str | None = None,
    ) -> dict:
        """Add a discussion round contribution.

        Returns the created discussion round dict.
        """
        round_id = self._uid()
        now = time.time()

        with self._lock:
            # Verify session exists
            row = self._conn.execute(
                "SELECT session_id, phase FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            self._conn.execute("""
                INSERT INTO discussion_rounds
                (round_id, session_id, round_number, model_id,
                 contribution, reaction_to, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                round_id, session_id, round_number, model_id,
                contribution, reaction_to, now,
            ))

            # Advance phase to discussion if still in verdicts or parallel_analysis
            current_phase = row["phase"]
            if current_phase in ("parallel_analysis", "verdicts"):
                self._conn.execute(
                    "UPDATE hybrid_council_sessions SET phase = 'discussion' "
                    "WHERE session_id = ?",
                    (session_id,),
                )

            self._conn.commit()

        result = {
            "round_id": round_id,
            "session_id": session_id,
            "round_number": round_number,
            "model_id": model_id,
            "contribution": contribution,
            "reaction_to": reaction_to,
            "created_at": now,
        }

        self._emit("council.discussion.round", {
            "session_id": session_id,
            "round_id": round_id,
            "round_number": round_number,
            "model_id": model_id,
        })
        log.info("discussion round added: %s round=%d model=%s",
                 round_id, round_number, model_id)
        return result

    def get_discussion(self, session_id: str) -> list[dict]:
        """Return all discussion rounds for a session."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM discussion_rounds WHERE session_id = ? "
                "ORDER BY round_number ASC, created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._parse_row(r) for r in rows]

    # ------------------------------------------------------------------
    # Public API -- Consolidation
    # ------------------------------------------------------------------

    def set_consolidated(
        self,
        session_id: str,
        consolidated_text: str,
        consensus_level: float,
    ) -> dict:
        """Set the consolidated result for a session.

        Returns the updated session dict.
        """
        now = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            self._conn.execute(
                "UPDATE hybrid_council_sessions "
                "SET consolidated_text = ?, consensus_level = ?, "
                "    phase = 'consolidated' "
                "WHERE session_id = ?",
                (consolidated_text, consensus_level, session_id),
            )
            self._conn.commit()

        result = {
            "session_id": session_id,
            "consolidated_text": consolidated_text,
            "consensus_level": consensus_level,
            "phase": "consolidated",
            "updated_at": now,
        }

        self._emit("council.session.consolidated", {
            "session_id": session_id,
            "consensus_level": consensus_level,
        })
        log.info("session consolidated: %s consensus=%.2f",
                 session_id, consensus_level)
        return result

    def get_consolidated(self, session_id: str) -> dict | None:
        """Return the consolidated result for a session, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT session_id, consolidated_text, consensus_level, phase "
                "FROM hybrid_council_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        if not row["consolidated_text"]:
            return None
        return {
            "session_id": row["session_id"],
            "consolidated_text": row["consolidated_text"],
            "consensus_level": row["consensus_level"],
            "phase": row["phase"],
        }

    # ------------------------------------------------------------------
    # Public API -- Summary & Stats
    # ------------------------------------------------------------------

    def get_session_summary(self, session_id: str) -> dict:
        """Return full summary: session + analyses + discussion + consolidated."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM hybrid_council_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return {}

            session = self._session_row(row)

            analyses = self._conn.execute(
                "SELECT * FROM model_analyses WHERE session_id = ? "
                "ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()

            discussion = self._conn.execute(
                "SELECT * FROM discussion_rounds WHERE session_id = ? "
                "ORDER BY round_number ASC, created_at ASC",
                (session_id,),
            ).fetchall()

        session["analyses"] = [self._parse_row(r) for r in analyses]
        session["discussion"] = [self._parse_row(r) for r in discussion]

        if session.get("consolidated_text"):
            session["consolidated"] = {
                "consolidated_text": session["consolidated_text"],
                "consensus_level": session["consensus_level"],
            }
        else:
            session["consolidated"] = None

        return session

    def rate_analysis(
        self,
        session_id: str,
        model_id: str,
        rating: float,
    ) -> dict:
        """Rate a specific model's analysis within a session.

        Returns the updated analysis dict.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT analysis_id FROM model_analyses "
                "WHERE session_id = ? AND model_id = ?",
                (session_id, model_id),
            ).fetchone()
            if not row:
                raise ValueError(
                    f"No analysis found for session={session_id} model={model_id}"
                )

            self._conn.execute(
                "UPDATE model_analyses SET rating = ? "
                "WHERE session_id = ? AND model_id = ?",
                (rating, session_id, model_id),
            )
            self._conn.commit()

        return {
            "session_id": session_id,
            "model_id": model_id,
            "rating": rating,
        }

    def get_model_stats(self) -> dict:
        """Return aggregated stats across all sessions for each model."""
        with self._lock:
            rows = self._conn.execute("""
                SELECT
                    model_id,
                    COUNT(*) as total_analyses,
                    AVG(confidence) as avg_confidence,
                    AVG(COALESCE(rating, 0)) as avg_rating,
                    SUM(CASE WHEN verdict = 'approve' THEN 1 ELSE 0 END) as approves,
                    SUM(CASE WHEN verdict = 'reject' THEN 1 ELSE 0 END) as rejects,
                    SUM(CASE WHEN verdict = 'conditional' THEN 1 ELSE 0 END) as conditionals
                FROM model_analyses
                GROUP BY model_id
                ORDER BY model_id
            """).fetchall()

        stats = {}
        for r in rows:
            d = dict(r)
            model_id = d["model_id"]
            stats[model_id] = {
                "total_analyses": d["total_analyses"],
                "avg_confidence": round(d["avg_confidence"], 4),
                "avg_rating": round(d["avg_rating"], 4),
                "approves": d["approves"],
                "rejects": d["rejects"],
                "conditionals": d["conditionals"],
            }
        return stats


    # ------------------------------------------------------------------
    # Public API -- Canonical roles, ranks, weights
    # ------------------------------------------------------------------

    def add_participant(
        self,
        session_id: str,
        model_id: str,
        role: str,
        rank: str = "primary",
        weight: float | None = None,
    ) -> dict:
        """Attach a model to a session under a canonical role+rank.

        ``weight`` defaults to DEFAULT_ROLE_WEIGHTS[role] * RANK_MULTIPLIER[rank]
        if not supplied. Same (session_id, model_id, role) triple is unique.
        Returns the participant dict.
        """
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role '{role}', must be one of {VALID_ROLES}"
            )
        if rank not in VALID_RANKS:
            raise ValueError(
                f"Invalid rank '{rank}', must be one of {VALID_RANKS}"
            )

        if weight is None:
            weight = round(
                compute_role_weight(role, rank, DEFAULT_ROLE_WEIGHTS, RANK_MULTIPLIER), 4
            )

        participant_id = self._uid()
        now = time.time()

        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            try:
                self._conn.execute("""
                    INSERT INTO council_participants
                    (participant_id, session_id, model_id, role, rank,
                     weight, joined_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    participant_id, session_id, model_id, role, rank,
                    float(weight), now,
                ))
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Participant already exists for session={session_id} "
                    f"model={model_id} role={role}"
                ) from exc
            self._conn.commit()

        result = {
            "participant_id": participant_id,
            "session_id": session_id,
            "model_id": model_id,
            "role": role,
            "rank": rank,
            "weight": float(weight),
            "joined_at": now,
        }
        self._emit("council.participant.added", {
            "session_id": session_id,
            "participant_id": participant_id,
            "model_id": model_id,
            "role": role,
            "rank": rank,
        })
        log.info("council participant added: session=%s model=%s role=%s rank=%s",
                 session_id, model_id, role, rank)
        return result

    def list_participants(
        self,
        session_id: str,
        role: str | None = None,
        rank: str | None = None,
    ) -> list[dict]:
        """List participants of a session, optionally filtered by role/rank."""
        sql = ("SELECT * FROM council_participants WHERE session_id = ?")
        args: list[Any] = [session_id]
        if role is not None:
            sql += " AND role = ?"
            args.append(role)
        if rank is not None:
            sql += " AND rank = ?"
            args.append(rank)
        sql += " ORDER BY joined_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        return [dict(r) for r in rows]

    def remove_participant(self, session_id: str, participant_id: str) -> bool:
        """Detach a participant. Returns True if a row was removed."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM council_participants "
                "WHERE session_id = ? AND participant_id = ?",
                (session_id, participant_id),
            )
            self._conn.commit()
            removed = cur.rowcount > 0
        if removed:
            self._emit("council.participant.removed", {
                "session_id": session_id,
                "participant_id": participant_id,
            })
        return removed

    # ------------------------------------------------------------------
    # Public API -- Critic signature
    # ------------------------------------------------------------------

    def record_critic_signature(
        self,
        session_id: str,
        model_id: str,
        signed_decision: str,
        rationale: str = "",
    ) -> dict:
        """Record a critic's signature on a council decision.

        ``signed_decision`` must be one of VALID_VERDICTS. The model_id must
        be a participant in the session under role='critic' or
        role='adversarial_critic'. Returns the
        signature dict including a signature_hash for audit.
        """
        import hashlib
        if signed_decision not in VALID_VERDICTS:
            raise ValueError(
                f"signed_decision must be one of {VALID_VERDICTS}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            crit = self._conn.execute(
                "SELECT participant_id FROM council_participants "
                "WHERE session_id = ? AND model_id = ? AND role IN ('critic', 'adversarial_critic')",
                (session_id, model_id),
            ).fetchone()
            if not crit:
                raise ValueError(
                    f"Model '{model_id}' is not a critic participant in "
                    f"session '{session_id}'"
                )

            sig_payload = f"{session_id}|{model_id}|{signed_decision}|{rationale}".encode()
            sig_hash = hashlib.sha256(sig_payload).hexdigest()[:32]
            signature_id = self._uid()
            now = time.time()
            self._conn.execute("""
                INSERT INTO council_critic_signatures
                (signature_id, session_id, model_id, signed_decision,
                 signature_hash, rationale, signed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                signature_id, session_id, model_id, signed_decision,
                sig_hash, rationale, now,
            ))
            self._conn.commit()

        result = {
            "signature_id": signature_id,
            "session_id": session_id,
            "model_id": model_id,
            "signed_decision": signed_decision,
            "signature_hash": sig_hash,
            "rationale": rationale,
            "signed_at": now,
        }
        self._emit("council.critic.signed", {
            "session_id": session_id,
            "model_id": model_id,
            "signed_decision": signed_decision,
        })
        log.info("council critic signature: session=%s model=%s decision=%s",
                 session_id, model_id, signed_decision)
        return result

    def get_critic_signatures(self, session_id: str) -> list[dict]:
        """Return all critic signatures for a session, oldest first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM council_critic_signatures "
                "WHERE session_id = ? ORDER BY signed_at ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def has_critic_signature(self, session_id: str) -> bool:
        """True iff at least one critic signature exists for this session."""
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM council_critic_signatures "
                "WHERE session_id = ? LIMIT 1",
                (session_id,),
            ).fetchone()
        return row is not None

    def get_critic_signature_roles(self, session_id: str) -> set[str]:
        """Return critic roles that signed the session decision."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT p.role FROM council_critic_signatures s "
                "JOIN council_participants p "
                "ON p.session_id = s.session_id AND p.model_id = s.model_id "
                "WHERE s.session_id = ? AND p.role IN ('critic', 'adversarial_critic')",
                (session_id,),
            ).fetchall()
        return {str(row["role"]) for row in rows}

    # ------------------------------------------------------------------
    # Public API -- Sentinel evaluations (cost / security)
    # ------------------------------------------------------------------

    def record_sentinel_evaluation(
        self,
        session_id: str,
        sentinel_role: str,
        model_id: str,
        verdict: str,
        score: float = 0.0,
        details: str = "",
    ) -> dict:
        """Record a cost/security sentinel evaluation.

        sentinel_role must be one of SENTINEL_ROLES.
        verdict must be one of VALID_SENTINEL_VERDICTS.
        Returns the evaluation dict.
        """
        if sentinel_role not in SENTINEL_ROLES:
            raise ValueError(
                f"sentinel_role must be one of {SENTINEL_ROLES}"
            )
        if verdict not in VALID_SENTINEL_VERDICTS:
            raise ValueError(
                f"verdict must be one of {VALID_SENTINEL_VERDICTS}"
            )

        with self._lock:
            row = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Session '{session_id}' not found")

            evaluation_id = self._uid()
            now = time.time()
            self._conn.execute("""
                INSERT INTO council_sentinel_evaluations
                (evaluation_id, session_id, sentinel_role, model_id,
                 verdict, score, details, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evaluation_id, session_id, sentinel_role, model_id,
                verdict, float(score), details, now,
            ))
            self._conn.commit()

        result = {
            "evaluation_id": evaluation_id,
            "session_id": session_id,
            "sentinel_role": sentinel_role,
            "model_id": model_id,
            "verdict": verdict,
            "score": float(score),
            "details": details,
            "evaluated_at": now,
        }
        self._emit("council.sentinel.evaluated", {
            "session_id": session_id,
            "sentinel_role": sentinel_role,
            "verdict": verdict,
        })
        log.info("council sentinel eval: session=%s role=%s verdict=%s score=%.2f",
                 session_id, sentinel_role, verdict, score)
        return result

    def get_sentinel_evaluations(
        self,
        session_id: str,
        sentinel_role: str | None = None,
    ) -> list[dict]:
        """Return sentinel evaluations for a session."""
        sql = ("SELECT * FROM council_sentinel_evaluations "
               "WHERE session_id = ?")
        args: list[Any] = [session_id]
        if sentinel_role is not None:
            sql += " AND sentinel_role = ?"
            args.append(sentinel_role)
        sql += " ORDER BY evaluated_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, tuple(args)).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Public API -- Weighted consensus
    # ------------------------------------------------------------------

    def compute_weighted_consensus(self, session_id: str) -> dict:
        """Compute weighted-vote consensus over the analyses of a session.

        Pairs each analysis verdict with the participant weight (matched by
        model_id) and returns:
          {
            "session_id": ...,
            "verdict": "approve" | "reject" | "conditional" | "tie",
            "weights": {"approve": w1, "reject": w2, "conditional": w3},
            "total_weight": float,
            "by_model": [...],
            "critic_signed": bool,
            "sentinel_blocks": [<sentinel_role>...]   # failing/rejecting sentinels
          }

        Notes:
        - Models that submitted analyses but are not participants get weight 1.0
          (anonymous fallback).
        - The newest evaluation per sentinel role is authoritative. If the
          latest verdict is 'fail' or legacy 'reject', that role is recorded
          in ``sentinel_blocks``.
        - If verdict ties between two values, returns 'tie'.
        """
        with self._lock:
            sess = self._conn.execute(
                "SELECT session_id FROM hybrid_council_sessions "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not sess:
                raise ValueError(f"Session '{session_id}' not found")

            participants = self._conn.execute(
                "SELECT model_id, role, rank, weight "
                "FROM council_participants WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            analyses = self._conn.execute(
                "SELECT model_id, verdict FROM model_analyses "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            sentinel_rows = self._conn.execute(
                "SELECT sentinel_role, verdict, evaluated_at FROM council_sentinel_evaluations "
                "WHERE session_id = ?",
                (session_id,),
            ).fetchall()

        weight_by_model: dict[str, float] = {
            p["model_id"]: float(p["weight"]) for p in participants
        }

        weights = {"approve": 0.0, "reject": 0.0, "conditional": 0.0}
        by_model = []
        for a in analyses:
            mid = a["model_id"]
            v = a["verdict"]
            w = weight_by_model.get(mid, 1.0)
            if v in weights:
                weights[v] += w
            by_model.append({"model_id": mid, "verdict": v, "weight": w})

        # Decide verdict — pick the largest, tie if top two are equal.
        ordered = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
        if not ordered or ordered[0][1] == 0.0:
            verdict = "no_data"
        elif len(ordered) > 1 and ordered[0][1] == ordered[1][1]:
            verdict = "tie"
        else:
            verdict = ordered[0][0]

        latest_sentinel_by_role: dict[str, tuple[float, str]] = {}
        for row in sentinel_rows:
            role = str(row["sentinel_role"])
            verdict_value = str(row["verdict"])
            evaluated_at = float(row["evaluated_at"] or 0.0)
            previous = latest_sentinel_by_role.get(role)
            if previous is None or evaluated_at >= previous[0]:
                latest_sentinel_by_role[role] = (evaluated_at, verdict_value)

        sentinel_blocks = sorted(
            role
            for role, (_, verdict_value) in latest_sentinel_by_role.items()
            if verdict_value in {"fail", "reject"}
        )

        participant_roles = {str(p["role"]) for p in participants}
        required_critic_roles = sorted(role for role in {"critic", "adversarial_critic"} if role in participant_roles)
        signature_roles = self.get_critic_signature_roles(session_id)
        critic_signed = bool(required_critic_roles) and all(role in signature_roles for role in required_critic_roles)

        return {
            "session_id": session_id,
            "verdict": verdict,
            "weights": {k: round(v, 4) for k, v in weights.items()},
            "total_weight": round(sum(weights.values()), 4),
            "by_model": by_model,
            "critic_signed": critic_signed,
            "critic_signature_roles": sorted(signature_roles),
            "required_critic_roles": required_critic_roles,
            "adversarial_critic_signed": "adversarial_critic" in signature_roles,
            "sentinel_blocks": sentinel_blocks,
        }

    def consolidate_with_signatures(
        self,
        session_id: str,
        consolidated_text: str,
        require_critic: bool = True,
        require_sentinels_pass: bool = True,
    ) -> dict:
        """Set consolidated, but enforce critic-signature + sentinel-pass gates.

        - If ``require_critic`` is True and no critic has signed, raises
          ``ValueError`` ("missing critic signature").
        - All unique participant models must have submitted an analysis row;
          otherwise the model wait barrier blocks consolidation.
        - If ``require_sentinels_pass`` is True and any sentinel failed/rejected,
          raises ``ValueError`` ("sentinel block: ...").

        On success, computes the weighted consensus and writes
        ``consolidated_text`` + the consensus_level (sum of winning verdict
        weight / total_weight).
        """
        consensus = self.compute_weighted_consensus(session_id)
        if require_critic and not consensus["critic_signed"]:
            raise ValueError(
                f"missing critic signature for session '{session_id}'"
            )
        with self._lock:
            participant_rows = self._conn.execute(
                "SELECT DISTINCT model_id FROM council_participants WHERE session_id = ?",
                (session_id,),
            ).fetchall()
            analysis_rows = self._conn.execute(
                "SELECT DISTINCT model_id FROM model_analyses WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        expected_models = {
            str(row["model_id"]) for row in participant_rows if str(row["model_id"] or "").strip()
        }
        received_models = {
            str(row["model_id"]) for row in analysis_rows if str(row["model_id"] or "").strip()
        }
        missing_models = sorted(expected_models - received_models)
        if missing_models:
            raise ValueError(
                f"model wait barrier: missing analyses for {','.join(missing_models)}"
            )
        if require_sentinels_pass and consensus["sentinel_blocks"]:
            raise ValueError(
                f"sentinel block: {','.join(consensus['sentinel_blocks'])}"
            )

        verdict = consensus["verdict"]
        total = consensus["total_weight"] or 1.0
        winning = consensus["weights"].get(verdict, 0.0) if verdict in (
            "approve", "reject", "conditional"
        ) else 0.0
        level = round(winning / total, 4) if total else 0.0

        return self.set_consolidated(session_id, consolidated_text, level)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_instance: CouncilHybrid | None = None


def get_council_hybrid(db_path: str | Path | None = None,
                       event_bus: EventBus | None = None) -> CouncilHybrid:
    global _instance
    if _instance is None:
        _instance = CouncilHybrid(db_path, event_bus)
    return _instance


def reset_council_hybrid(db_path: str | Path | None = None,
                         event_bus: EventBus | None = None) -> CouncilHybrid:
    global _instance
    _instance = CouncilHybrid(db_path, event_bus)
    return _instance
