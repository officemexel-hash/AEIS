from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import funding_db_path

log = logging.getLogger("sylion.funding_autopilot.store")


def _invalidate_funding_cache() -> None:
    """Phase 3 W1.3 — drop funding.programs cache after any catalog write.

    Programmes and calls are read together by ``list_programmes`` and
    ``list_calls``; we invalidate the namespace as a whole on every write
    so callers can never observe a torn read between the two.
    """
    try:
        from sylion.infra.cache import get_cache
        get_cache().invalidate("sylion:funding.programs:*")
    except Exception:                              # noqa: BLE001
        log.warning("funding.programs cache invalidation failed", exc_info=True)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=True, default=str)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class FundingAutopilotStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or funding_db_path()
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA busy_timeout = 30000")
            self._conn.execute("PRAGMA foreign_keys=ON")
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL")
            self._migrate(self._conn)
        return self._conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS funding_company_profiles (
                company_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS funding_company_documents (
                document_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                document_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'available',
                expires_at REAL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(company_id) REFERENCES funding_company_profiles(company_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_programmes (
                programme_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL DEFAULT 'manual',
                name TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                institution TEXT NOT NULL DEFAULT '',
                funding_type TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS funding_calls (
                call_id TEXT PRIMARY KEY,
                programme_id TEXT NOT NULL,
                title TEXT NOT NULL,
                code TEXT NOT NULL DEFAULT '',
                country TEXT NOT NULL DEFAULT '',
                region TEXT NOT NULL DEFAULT '',
                portal_url TEXT NOT NULL DEFAULT '',
                opens_at REAL,
                closes_at REAL,
                min_project_budget REAL NOT NULL DEFAULT 0,
                max_project_budget REAL NOT NULL DEFAULT 0,
                grant_intensity_pct REAL NOT NULL DEFAULT 0,
                trl_min INTEGER NOT NULL DEFAULT 0,
                trl_max INTEGER NOT NULL DEFAULT 9,
                requires_consortium INTEGER NOT NULL DEFAULT 0,
                target_beneficiaries_json TEXT NOT NULL DEFAULT '[]',
                themes_json TEXT NOT NULL DEFAULT '[]',
                required_documents_json TEXT NOT NULL DEFAULT '[]',
                required_partner_types_json TEXT NOT NULL DEFAULT '[]',
                eligible_costs_json TEXT NOT NULL DEFAULT '[]',
                evaluation_weights_json TEXT NOT NULL DEFAULT '{}',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(programme_id) REFERENCES funding_programmes(programme_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_ideas (
                idea_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                recommended_call_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                recommendation TEXT NOT NULL DEFAULT '',
                budget_estimate REAL NOT NULL DEFAULT 0,
                grant_estimate REAL NOT NULL DEFAULT 0,
                difficulty TEXT NOT NULL DEFAULT 'medium',
                risk_level TEXT NOT NULL DEFAULT 'medium',
                chance_pct REAL NOT NULL DEFAULT 0,
                idea_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(company_id) REFERENCES funding_company_profiles(company_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_projects (
                project_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                idea_id TEXT NOT NULL DEFAULT '',
                call_id TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                project_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(company_id) REFERENCES funding_company_profiles(company_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_matches (
                match_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                call_id TEXT NOT NULL,
                fit_score REAL NOT NULL DEFAULT 0,
                success_probability REAL NOT NULL DEFAULT 0,
                readiness_score REAL NOT NULL DEFAULT 0,
                risk_score REAL NOT NULL DEFAULT 0,
                match_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES funding_projects(project_id) ON DELETE CASCADE,
                FOREIGN KEY(call_id) REFERENCES funding_calls(call_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_partner_candidates (
                partner_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                name TEXT NOT NULL,
                partner_type TEXT NOT NULL,
                country TEXT NOT NULL DEFAULT '',
                expertise_json TEXT NOT NULL DEFAULT '[]',
                grant_track_record INTEGER NOT NULL DEFAULT 0,
                contact_email TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                score REAL NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES funding_projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_outreach_messages (
                message_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                partner_id TEXT NOT NULL,
                message_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES funding_projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_applications (
                application_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                call_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                package_json TEXT NOT NULL DEFAULT '{}',
                review_json TEXT NOT NULL DEFAULT '{}',
                export_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(project_id) REFERENCES funding_projects(project_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_submission_sessions (
                session_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft_prepared',
                portal_url TEXT NOT NULL DEFAULT '',
                draft_reference TEXT NOT NULL DEFAULT '',
                prepared_fields_json TEXT NOT NULL DEFAULT '{}',
                validation_json TEXT NOT NULL DEFAULT '{}',
                receipt_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(application_id) REFERENCES funding_applications(application_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_approval_events (
                approval_event_id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                action_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_by TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at REAL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                FOREIGN KEY(application_id) REFERENCES funding_applications(application_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS funding_alerts (
                alert_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                application_id TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT 'info',
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                due_at REAL,
                is_resolved INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS funding_audit_events (
                event_id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL DEFAULT '',
                application_id TEXT NOT NULL DEFAULT '',
                actor TEXT NOT NULL DEFAULT '',
                action_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_funding_calls_closes_at ON funding_calls(closes_at);
            CREATE INDEX IF NOT EXISTS idx_funding_ideas_company ON funding_ideas(company_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_funding_projects_company ON funding_projects(company_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_funding_matches_project ON funding_matches(project_id, success_probability DESC);
            CREATE INDEX IF NOT EXISTS idx_funding_applications_company ON funding_applications(company_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_funding_alerts_company ON funding_alerts(company_id, due_at);

            -- Phase 3 W1.2: FK indexes (DELETE CASCADE cost + JOIN perf).
            CREATE INDEX IF NOT EXISTS idx_funding_calls_programme              ON funding_calls(programme_id);
            CREATE INDEX IF NOT EXISTS idx_funding_company_documents_company    ON funding_company_documents(company_id);
            CREATE INDEX IF NOT EXISTS idx_funding_matches_call                 ON funding_matches(call_id);
            CREATE INDEX IF NOT EXISTS idx_funding_partner_candidates_project   ON funding_partner_candidates(project_id);
            CREATE INDEX IF NOT EXISTS idx_funding_outreach_messages_project    ON funding_outreach_messages(project_id);
            CREATE INDEX IF NOT EXISTS idx_funding_applications_project         ON funding_applications(project_id);
            CREATE INDEX IF NOT EXISTS idx_funding_applications_call            ON funding_applications(call_id);
            CREATE INDEX IF NOT EXISTS idx_funding_submission_sessions_app      ON funding_submission_sessions(application_id);
            CREATE INDEX IF NOT EXISTS idx_funding_approval_events_app          ON funding_approval_events(application_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_funding_audit_events_app             ON funding_audit_events(application_id, created_at DESC);
            """
        )
        conn.commit()

    def _row_to_dict(self, row: sqlite3.Row, json_fields: dict[str, Any]) -> dict[str, Any]:
        payload = dict(row)
        for key, default in json_fields.items():
            payload[key] = _json_loads(payload.get(key), default)
        return payload

    def upsert_company_profile(self, company_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        payload = dict(profile)
        payload["company_id"] = company_id
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT company_id FROM funding_company_profiles WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE funding_company_profiles SET profile_json = ?, updated_at = ? WHERE company_id = ?",
                (_json_dumps(payload), now, company_id),
            )
        else:
            conn.execute(
                "INSERT INTO funding_company_profiles (company_id, profile_json, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (company_id, _json_dumps(payload), now, now),
            )
        conn.commit()
        return self.get_company_profile(company_id)

    def get_company_profile(self, company_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT company_id, profile_json, created_at, updated_at FROM funding_company_profiles WHERE company_id = ?",
            (company_id,),
        ).fetchone()
        if not row:
            return None
        payload = self._row_to_dict(row, {"profile_json": {}})
        profile = dict(payload["profile_json"])
        profile["company_id"] = payload["company_id"]
        profile["created_at"] = payload["created_at"]
        profile["updated_at"] = payload["updated_at"]
        return profile

    def add_company_document(self, company_id: str, document: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        document_id = document.get("document_id") or _uid("fund_doc")
        self._get_conn().execute(
            """
            INSERT OR REPLACE INTO funding_company_documents
            (document_id, company_id, document_type, filename, storage_path, status, expires_at, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM funding_company_documents WHERE document_id = ?), ?), ?)
            """,
            (
                document_id,
                company_id,
                document.get("document_type", ""),
                document.get("filename", ""),
                document.get("storage_path", ""),
                document.get("status", "available"),
                document.get("expires_at"),
                _json_dumps(document.get("metadata", {})),
                document_id,
                now,
                now,
            ),
        )
        self._get_conn().commit()
        row = self._get_conn().execute(
            "SELECT * FROM funding_company_documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
        return self._row_to_dict(row, {"metadata_json": {}})

    def list_company_documents(self, company_id: str) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM funding_company_documents WHERE company_id = ? ORDER BY updated_at DESC",
            (company_id,),
        ).fetchall()
        return [self._row_to_dict(row, {"metadata_json": {}}) for row in rows]

    def create_programme(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        programme_id = payload.get("programme_id") or _uid("fund_programme")
        self._get_conn().execute(
            """
            INSERT INTO funding_programmes
            (programme_id, source_id, name, country, region, institution, funding_type, summary, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                programme_id,
                payload.get("source_id", "manual"),
                payload.get("name", ""),
                payload.get("country", ""),
                payload.get("region", ""),
                payload.get("institution", ""),
                payload.get("funding_type", ""),
                payload.get("summary", ""),
                _json_dumps(payload.get("metadata", {})),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        # Phase 3 W1.3: a new programme invalidates the cached catalog.
        _invalidate_funding_cache()
        return self.get_programme(programme_id)

    def list_programmes(self) -> list[dict[str, Any]]:
        """List funding programmes.

        Phase 3 W1.3: cached under ``funding.programs`` (TTL 1h).
        Invalidated by every write to the programmes/calls tables.
        """
        cache_key: str | None = None
        try:
            from sylion.infra.cache import default_ttl, get_cache, make_key

            cache_key = make_key("funding.programs", "list_programmes")
            cached_payload = get_cache().get(cache_key)
            if cached_payload is not None:
                return cached_payload
        except Exception:                          # noqa: BLE001
            log.warning("funding.programs cache get failed", exc_info=True)
            cache_key = None

        rows = self._get_conn().execute(
            "SELECT * FROM funding_programmes ORDER BY updated_at DESC, name ASC"
        ).fetchall()
        result = [self._row_to_dict(row, {"metadata_json": {}}) for row in rows]

        if cache_key is not None:
            try:
                from sylion.infra.cache import default_ttl, get_cache

                get_cache().set(
                    cache_key,
                    result,
                    ttl=default_ttl("funding.programs"),
                )
            except Exception:                      # noqa: BLE001
                log.warning("funding.programs cache set failed", exc_info=True)

        return result

    def get_programme(self, programme_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_programmes WHERE programme_id = ?",
            (programme_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row, {"metadata_json": {}})

    def create_call(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        call_id = payload.get("call_id") or _uid("fund_call")
        self._get_conn().execute(
            """
            INSERT INTO funding_calls
            (call_id, programme_id, title, code, country, region, portal_url, opens_at, closes_at,
             min_project_budget, max_project_budget, grant_intensity_pct, trl_min, trl_max, requires_consortium,
             target_beneficiaries_json, themes_json, required_documents_json, required_partner_types_json,
             eligible_costs_json, evaluation_weights_json, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                payload.get("programme_id", ""),
                payload.get("title", ""),
                payload.get("code", ""),
                payload.get("country", ""),
                payload.get("region", ""),
                payload.get("portal_url", ""),
                payload.get("opens_at"),
                payload.get("closes_at"),
                float(payload.get("min_project_budget", 0) or 0),
                float(payload.get("max_project_budget", 0) or 0),
                float(payload.get("grant_intensity_pct", 0) or 0),
                int(payload.get("trl_min", 0) or 0),
                int(payload.get("trl_max", 9) or 9),
                1 if payload.get("requires_consortium") else 0,
                _json_dumps(payload.get("target_beneficiaries", [])),
                _json_dumps(payload.get("themes", [])),
                _json_dumps(payload.get("required_documents", [])),
                _json_dumps(payload.get("required_partner_types", [])),
                _json_dumps(payload.get("eligible_costs", [])),
                _json_dumps(payload.get("evaluation_weights", {})),
                _json_dumps(payload.get("metadata", {})),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        # Phase 3 W1.3: a new call invalidates the cached catalog.
        _invalidate_funding_cache()
        return self.get_call(call_id)

    def list_calls(self) -> list[dict[str, Any]]:
        """List funding calls. Cached under ``funding.programs`` (TTL 1h)."""
        cache_key: str | None = None
        try:
            from sylion.infra.cache import default_ttl, get_cache, make_key

            cache_key = make_key("funding.programs", "list_calls")
            cached_payload = get_cache().get(cache_key)
            if cached_payload is not None:
                return cached_payload
        except Exception:                          # noqa: BLE001
            log.warning("funding.programs cache get failed", exc_info=True)
            cache_key = None

        rows = self._get_conn().execute(
            "SELECT * FROM funding_calls ORDER BY COALESCE(closes_at, 9e18) ASC, updated_at DESC"
        ).fetchall()
        result = [
            self._row_to_dict(
                row,
                {
                    "target_beneficiaries_json": [],
                    "themes_json": [],
                    "required_documents_json": [],
                    "required_partner_types_json": [],
                    "eligible_costs_json": [],
                    "evaluation_weights_json": {},
                    "metadata_json": {},
                },
            )
            for row in rows
        ]

        if cache_key is not None:
            try:
                from sylion.infra.cache import default_ttl, get_cache

                get_cache().set(
                    cache_key,
                    result,
                    ttl=default_ttl("funding.programs"),
                )
            except Exception:                      # noqa: BLE001
                log.warning("funding.programs cache set failed", exc_info=True)

        return result

    def get_call(self, call_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_calls WHERE call_id = ?",
            (call_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(
            row,
            {
                "target_beneficiaries_json": [],
                "themes_json": [],
                "required_documents_json": [],
                "required_partner_types_json": [],
                "eligible_costs_json": [],
                "evaluation_weights_json": {},
                "metadata_json": {},
            },
        )

    def replace_ideas(self, company_id: str, ideas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conn = self._get_conn()
        conn.execute("DELETE FROM funding_ideas WHERE company_id = ?", (company_id,))
        now = _now()
        for item in ideas:
            idea_id = item.get("idea_id") or _uid("fund_idea")
            item["idea_id"] = idea_id
            conn.execute(
                """
                INSERT INTO funding_ideas
                (idea_id, company_id, recommended_call_id, title, category, recommendation, budget_estimate,
                 grant_estimate, difficulty, risk_level, chance_pct, idea_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idea_id,
                    company_id,
                    item.get("recommended_call_id", ""),
                    item.get("title", ""),
                    item.get("category", ""),
                    item.get("recommendation", ""),
                    float(item.get("budget_estimate", 0) or 0),
                    float(item.get("grant_estimate", 0) or 0),
                    item.get("difficulty", "medium"),
                    item.get("risk_level", "medium"),
                    float(item.get("chance_pct", 0) or 0),
                    _json_dumps(item),
                    now,
                    now,
                ),
            )
        conn.commit()
        return self.list_ideas(company_id)

    def list_ideas(self, company_id: str) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM funding_ideas WHERE company_id = ? ORDER BY chance_pct DESC, updated_at DESC",
            (company_id,),
        ).fetchall()
        items = []
        for row in rows:
            payload = self._row_to_dict(row, {"idea_json": {}})
            item = dict(payload["idea_json"])
            item["idea_id"] = payload["idea_id"]
            item["company_id"] = payload["company_id"]
            item["recommended_call_id"] = payload["recommended_call_id"]
            item["chance_pct"] = payload["chance_pct"]
            item["created_at"] = payload["created_at"]
            item["updated_at"] = payload["updated_at"]
            items.append(item)
        return items

    def get_idea(self, idea_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_ideas WHERE idea_id = ?",
            (idea_id,),
        ).fetchone()
        if not row:
            return None
        payload = self._row_to_dict(row, {"idea_json": {}})
        item = dict(payload["idea_json"])
        item["idea_id"] = payload["idea_id"]
        item["company_id"] = payload["company_id"]
        item["recommended_call_id"] = payload["recommended_call_id"]
        item["chance_pct"] = payload["chance_pct"]
        item["created_at"] = payload["created_at"]
        item["updated_at"] = payload["updated_at"]
        return item

    def create_project(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        project_id = payload.get("project_id") or _uid("fund_project")
        data = dict(payload)
        data["project_id"] = project_id
        self._get_conn().execute(
            """
            INSERT INTO funding_projects (project_id, company_id, idea_id, call_id, title, status, project_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                payload.get("company_id", "default"),
                payload.get("idea_id", ""),
                payload.get("call_id", ""),
                payload.get("title", ""),
                payload.get("status", "draft"),
                _json_dumps(data),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        return self.get_project(project_id)

    def update_project(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        data = dict(payload)
        data["project_id"] = project_id
        self._get_conn().execute(
            "UPDATE funding_projects SET title = ?, status = ?, project_json = ?, updated_at = ? WHERE project_id = ?",
            (data.get("title", ""), data.get("status", "draft"), _json_dumps(data), now, project_id),
        )
        self._get_conn().commit()
        return self.get_project(project_id)

    def list_projects(self, company_id: str | None = None) -> list[dict[str, Any]]:
        if company_id:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_projects WHERE company_id = ? ORDER BY updated_at DESC",
                (company_id,),
            ).fetchall()
        else:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_projects ORDER BY updated_at DESC"
            ).fetchall()
        return [self._project_from_row(row) for row in rows]

    def _project_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = self._row_to_dict(row, {"project_json": {}})
        item = dict(payload["project_json"])
        item["project_id"] = payload["project_id"]
        item["company_id"] = payload["company_id"]
        item["idea_id"] = payload["idea_id"]
        item["call_id"] = payload["call_id"]
        item["status"] = payload["status"]
        item["created_at"] = payload["created_at"]
        item["updated_at"] = payload["updated_at"]
        return item

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if not row:
            return None
        return self._project_from_row(row)

    def replace_matches(self, project_id: str, matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conn = self._get_conn()
        conn.execute("DELETE FROM funding_matches WHERE project_id = ?", (project_id,))
        now = _now()
        for item in matches:
            match_id = item.get("match_id") or _uid("fund_match")
            item["match_id"] = match_id
            conn.execute(
                """
                INSERT INTO funding_matches
                (match_id, project_id, call_id, fit_score, success_probability, readiness_score, risk_score, match_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    match_id,
                    project_id,
                    item.get("call_id", ""),
                    float(item.get("fit_score", 0) or 0),
                    float(item.get("success_probability", 0) or 0),
                    float(item.get("readiness_score", 0) or 0),
                    float(item.get("risk_score", 0) or 0),
                    _json_dumps(item),
                    now,
                ),
            )
        conn.commit()
        return self.list_matches(project_id)

    def list_matches(self, project_id: str) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM funding_matches WHERE project_id = ? ORDER BY success_probability DESC, fit_score DESC",
            (project_id,),
        ).fetchall()
        items = []
        for row in rows:
            payload = self._row_to_dict(row, {"match_json": {}})
            item = dict(payload["match_json"])
            item["match_id"] = payload["match_id"]
            item["project_id"] = payload["project_id"]
            items.append(item)
        return items

    def replace_partner_candidates(self, project_id: str, company_id: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conn = self._get_conn()
        for candidate in candidates:
            partner_id = candidate.get("partner_id") or _uid("fund_partner")
            candidate["partner_id"] = partner_id
            expertise = candidate.get("expertise")
            if expertise is None:
                expertise = candidate.get("expertise_json", [])
            metadata = candidate.get("metadata")
            if metadata is None:
                metadata = candidate.get("metadata_json", {})
            conn.execute(
                """
                INSERT OR REPLACE INTO funding_partner_candidates
                (partner_id, project_id, company_id, name, partner_type, country, expertise_json, grant_track_record,
                 contact_email, metadata_json, score, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM funding_partner_candidates WHERE partner_id = ?), ?), ?)
                """,
                (
                    partner_id,
                    project_id,
                    company_id,
                    candidate.get("name", ""),
                    candidate.get("partner_type", ""),
                    candidate.get("country", ""),
                    _json_dumps(expertise),
                    int(candidate.get("grant_track_record", 0) or 0),
                    candidate.get("contact_email", ""),
                    _json_dumps(metadata),
                    float(candidate.get("score", 0) or 0),
                    partner_id,
                    _now(),
                    _now(),
                ),
            )
        conn.commit()
        return self.list_partner_candidates(project_id)

    def list_partner_candidates(self, project_id: str) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM funding_partner_candidates WHERE project_id = ? ORDER BY score DESC, updated_at DESC",
            (project_id,),
        ).fetchall()
        return [
            self._row_to_dict(row, {"expertise_json": [], "metadata_json": {}})
            for row in rows
        ]

    def replace_outreach_messages(self, project_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        conn = self._get_conn()
        conn.execute("DELETE FROM funding_outreach_messages WHERE project_id = ?", (project_id,))
        now = _now()
        for item in messages:
            message_id = item.get("message_id") or _uid("fund_msg")
            conn.execute(
                """
                INSERT INTO funding_outreach_messages (message_id, project_id, partner_id, message_type, subject, body, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    project_id,
                    item.get("partner_id", ""),
                    item.get("message_type", "intro_email"),
                    item.get("subject", ""),
                    item.get("body", ""),
                    now,
                ),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM funding_outreach_messages WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def create_application(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        application_id = payload.get("application_id") or _uid("fund_app")
        data = dict(payload)
        data["application_id"] = application_id
        self._get_conn().execute(
            """
            INSERT INTO funding_applications
            (application_id, company_id, project_id, call_id, status, package_json, review_json, export_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application_id,
                payload.get("company_id", "default"),
                payload.get("project_id", ""),
                payload.get("call_id", ""),
                payload.get("status", "draft"),
                _json_dumps(payload.get("package", {})),
                _json_dumps(payload.get("review", {})),
                _json_dumps(payload.get("exports", {})),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        return self.get_application(application_id)

    def update_application(self, application_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        self._get_conn().execute(
            """
            UPDATE funding_applications
            SET status = ?, package_json = ?, review_json = ?, export_json = ?, updated_at = ?
            WHERE application_id = ?
            """,
            (
                payload.get("status", "draft"),
                _json_dumps(payload.get("package", {})),
                _json_dumps(payload.get("review", {})),
                _json_dumps(payload.get("exports", {})),
                now,
                application_id,
            ),
        )
        self._get_conn().commit()
        return self.get_application(application_id)

    def get_application(self, application_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_applications WHERE application_id = ?",
            (application_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row, {"package_json": {}, "review_json": {}, "export_json": {}})

    def list_applications(self, company_id: str | None = None) -> list[dict[str, Any]]:
        if company_id:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_applications WHERE company_id = ? ORDER BY updated_at DESC",
                (company_id,),
            ).fetchall()
        else:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_applications ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_dict(row, {"package_json": {}, "review_json": {}, "export_json": {}}) for row in rows]

    def create_submission_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        session_id = payload.get("session_id") or _uid("fund_submit")
        self._get_conn().execute(
            """
            INSERT INTO funding_submission_sessions
            (session_id, application_id, status, portal_url, draft_reference, prepared_fields_json, validation_json, receipt_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.get("application_id", ""),
                payload.get("status", "draft_prepared"),
                payload.get("portal_url", ""),
                payload.get("draft_reference", ""),
                _json_dumps(payload.get("prepared_fields", {})),
                _json_dumps(payload.get("validation", {})),
                _json_dumps(payload.get("receipt", {})),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        return self.get_submission_session(session_id)

    def update_submission_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        self._get_conn().execute(
            """
            UPDATE funding_submission_sessions
            SET status = ?, portal_url = ?, draft_reference = ?, prepared_fields_json = ?, validation_json = ?, receipt_json = ?, updated_at = ?
            WHERE session_id = ?
            """,
            (
                payload.get("status", "draft_prepared"),
                payload.get("portal_url", ""),
                payload.get("draft_reference", ""),
                _json_dumps(payload.get("prepared_fields", {})),
                _json_dumps(payload.get("validation", {})),
                _json_dumps(payload.get("receipt", {})),
                now,
                session_id,
            ),
        )
        self._get_conn().commit()
        return self.get_submission_session(session_id)

    def get_submission_session(self, session_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_submission_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row, {"prepared_fields_json": {}, "validation_json": {}, "receipt_json": {}})

    def list_submission_sessions(self, application_id: str | None = None) -> list[dict[str, Any]]:
        if application_id:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_submission_sessions WHERE application_id = ? ORDER BY updated_at DESC",
                (application_id,),
            ).fetchall()
        else:
            rows = self._get_conn().execute(
                "SELECT * FROM funding_submission_sessions ORDER BY updated_at DESC"
            ).fetchall()
        return [self._row_to_dict(row, {"prepared_fields_json": {}, "validation_json": {}, "receipt_json": {}}) for row in rows]

    def create_approval_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        approval_event_id = payload.get("approval_event_id") or _uid("fund_approval")
        self._get_conn().execute(
            """
            INSERT INTO funding_approval_events
            (approval_event_id, application_id, session_id, action_type, status, requested_by, approved_by, approved_at, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_event_id,
                payload.get("application_id", ""),
                payload.get("session_id", ""),
                payload.get("action_type", "final_submit"),
                payload.get("status", "pending"),
                payload.get("requested_by", ""),
                payload.get("approved_by", ""),
                payload.get("approved_at"),
                _json_dumps(payload.get("payload", {})),
                now,
                now,
            ),
        )
        self._get_conn().commit()
        return self.get_approval_event(approval_event_id)

    def update_approval_event(self, approval_event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        current = self.get_approval_event(approval_event_id)
        base_payload = dict(current.get("payload_json", {}) if current else {})
        base_payload.update(payload.get("payload", {}))
        self._get_conn().execute(
            """
            UPDATE funding_approval_events
            SET status = ?, requested_by = ?, approved_by = ?, approved_at = ?, payload_json = ?, updated_at = ?
            WHERE approval_event_id = ?
            """,
            (
                payload.get("status", current.get("status", "pending") if current else "pending"),
                payload.get("requested_by", current.get("requested_by", "") if current else ""),
                payload.get("approved_by", current.get("approved_by", "") if current else ""),
                payload.get("approved_at", current.get("approved_at") if current else None),
                _json_dumps(base_payload),
                now,
                approval_event_id,
            ),
        )
        self._get_conn().commit()
        return self.get_approval_event(approval_event_id)

    def get_approval_event(self, approval_event_id: str) -> dict[str, Any] | None:
        row = self._get_conn().execute(
            "SELECT * FROM funding_approval_events WHERE approval_event_id = ?",
            (approval_event_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row, {"payload_json": {}})

    def list_approval_events(self, application_id: str | None = None, session_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM funding_approval_events WHERE 1=1"
        params: list[Any] = []
        if application_id:
            query += " AND application_id = ?"
            params.append(application_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        query += " ORDER BY updated_at DESC"
        rows = self._get_conn().execute(query, tuple(params)).fetchall()
        return [self._row_to_dict(row, {"payload_json": {}}) for row in rows]

    def replace_alerts(self, company_id: str, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM funding_alerts WHERE company_id = ?", (company_id,))
                now = _now()
                for item in alerts:
                    conn.execute(
                        """
                        INSERT INTO funding_alerts
                        (alert_id, company_id, application_id, severity, kind, message, due_at, is_resolved, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.get("alert_id", _uid("fund_alert")),
                            company_id,
                            item.get("application_id", ""),
                            item.get("severity", "info"),
                            item.get("kind", ""),
                            item.get("message", ""),
                            item.get("due_at"),
                            1 if item.get("is_resolved") else 0,
                            now,
                            now,
                        ),
                    )
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
        return self.list_alerts(company_id)

    def list_alerts(self, company_id: str) -> list[dict[str, Any]]:
        rows = self._get_conn().execute(
            "SELECT * FROM funding_alerts WHERE company_id = ? ORDER BY COALESCE(due_at, 9e18) ASC, updated_at DESC",
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def record_audit_event(self, actor: str, action_type: str, payload: dict[str, Any], company_id: str = "", application_id: str = "") -> dict[str, Any]:
        event_id = _uid("fund_audit")
        now = _now()
        self._get_conn().execute(
            """
            INSERT INTO funding_audit_events (event_id, company_id, application_id, actor, action_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, company_id, application_id, actor, action_type, _json_dumps(payload), now),
        )
        self._get_conn().commit()
        return {"event_id": event_id, "company_id": company_id, "application_id": application_id, "actor": actor, "action_type": action_type, "payload": payload, "created_at": now}


_store: FundingAutopilotStore | None = None
_store_lock = threading.Lock()


def get_funding_store(db_path: str | None = None) -> FundingAutopilotStore:
    global _store
    target_db_path = db_path or funding_db_path()
    with _store_lock:
        if _store is None:
            _store = FundingAutopilotStore(target_db_path)
        elif str(_store.db_path) != str(target_db_path):
            _store.close()
            _store = FundingAutopilotStore(target_db_path)
        return _store


def reset_funding_store(db_path: str | None = None) -> FundingAutopilotStore:
    global _store
    target_db_path = db_path or funding_db_path()
    with _store_lock:
        if _store is not None:
            _store.close()
        _store = FundingAutopilotStore(target_db_path)
        return _store
