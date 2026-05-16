"""
SYLION Governance -- Self-Explanation Validator

Validates that self-explanations from AI decisions meet quality criteria.
Templates define required fields and quality checks; validate_explanation()
checks explanation data against them.

Thread-safe. SQLite-backed. EventBus integration.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from sylion.core.event_bus import EventBus, SylionEvent

log = logging.getLogger("sylion.governance.self_explanation_validator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCOPES: tuple[str, ...] = (
    "global", "module", "pipeline", "decision", "deployment",
)


# ---------------------------------------------------------------------------
# SelfExplanationValidator
# ---------------------------------------------------------------------------

class SelfExplanationValidator:
    """Validates self-explanations against configurable templates.

    Templates define required fields and quality criteria. Validation checks
    if explanation data satisfies all requirements.
    """

    def __init__(self, db_path: str | Path | None = None,
                 event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
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
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS explanation_templates (
                    template_id        TEXT PRIMARY KEY,
                    name               TEXT NOT NULL,
                    scope              TEXT NOT NULL,
                    required_fields    TEXT NOT NULL DEFAULT '[]',
                    quality_criteria   TEXT NOT NULL DEFAULT '[]',
                    is_active          INTEGER NOT NULL DEFAULT 1,
                    created_at         REAL NOT NULL,
                    updated_at         REAL NOT NULL
                )
            """)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS explanation_validations (
                    validation_id   TEXT PRIMARY KEY,
                    template_id     TEXT NOT NULL,
                    explanation_data TEXT NOT NULL DEFAULT '{}',
                    passed          INTEGER NOT NULL,
                    errors          TEXT NOT NULL DEFAULT '[]',
                    score           REAL NOT NULL DEFAULT 0.0,
                    validated_at    REAL NOT NULL
                )
            """)
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_templates_scope "
                "ON explanation_templates(scope)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_templates_name "
                "ON explanation_templates(name)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_validations_template "
                "ON explanation_validations(template_id)"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_validations_ts "
                "ON explanation_validations(validated_at)"
            )
            self._conn.commit()

    # ------------------------------------------------------------------
    # Template CRUD
    # ------------------------------------------------------------------

    def create_template(self, name: str, scope: str,
                        required_fields_json: list[dict] | str | None = None,
                        quality_criteria_json: list[dict] | str | None = None) -> dict:
        """Create a new explanation template.

        Args:
            name: Template name.
            scope: One of VALID_SCOPES.
            required_fields_json: List of required field definitions.
            quality_criteria_json: List of quality criteria definitions.

        Returns:
            Dict with template details.
        """
        if not name or not name.strip():
            raise ValueError("Template name must not be empty.")
        if scope not in VALID_SCOPES:
            raise ValueError(
                f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}."
            )

        required = self._parse_json_param(required_fields_json, [])
        criteria = self._parse_json_param(quality_criteria_json, [])

        template_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO explanation_templates
                (template_id, name, scope, required_fields, quality_criteria,
                 is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (template_id, name, scope,
                  json.dumps(required), json.dumps(criteria), now, now))
            self._conn.commit()

        self._emit("template_created", {
            "template_id": template_id,
            "name": name,
            "scope": scope,
        })

        log.info("created template %s (%s/%s)", template_id, name, scope)

        return {
            "template_id": template_id,
            "name": name,
            "scope": scope,
            "required_fields": required,
            "quality_criteria": criteria,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

    def update_template(self, template_id: str, *,
                        name: str | None = None,
                        scope: str | None = None,
                        required_fields_json: list[dict] | str | None = None,
                        quality_criteria_json: list[dict] | str | None = None,
                        is_active: bool | None = None) -> dict | None:
        """Update an existing template. Returns updated dict or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM explanation_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if not row:
                return None

            if scope is not None and scope not in VALID_SCOPES:
                raise ValueError(
                    f"Invalid scope '{scope}'. Must be one of {VALID_SCOPES}."
                )

            new_name = name if name is not None else row["name"]
            new_scope = scope if scope is not None else row["scope"]
            new_active = 1 if (is_active if is_active is not None else row["is_active"]) else 0
            new_required = self._parse_json_param(
                required_fields_json, json.loads(row["required_fields"]))
            new_criteria = self._parse_json_param(
                quality_criteria_json, json.loads(row["quality_criteria"]))

            now = time.time()
            self._conn.execute("""
                UPDATE explanation_templates
                SET name = ?, scope = ?, required_fields = ?,
                    quality_criteria = ?, is_active = ?, updated_at = ?
                WHERE template_id = ?
            """, (new_name, new_scope, json.dumps(new_required),
                  json.dumps(new_criteria), new_active, now, template_id))
            self._conn.commit()

        return {
            "template_id": template_id,
            "name": new_name,
            "scope": new_scope,
            "required_fields": new_required,
            "quality_criteria": new_criteria,
            "is_active": bool(new_active),
            "created_at": row["created_at"],
            "updated_at": now,
        }

    def delete_template(self, template_id: str) -> bool:
        """Delete a template. Returns True if deleted."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM explanation_templates WHERE template_id = ?",
                (template_id,),
            )
            self._conn.execute(
                "DELETE FROM explanation_validations WHERE template_id = ?",
                (template_id,),
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def list_templates(self, scope: str | None = None,
                       active_only: bool = False) -> list[dict]:
        """List templates, optionally filtered by scope."""
        with self._lock:
            q = "SELECT * FROM explanation_templates WHERE 1=1"
            params: list[Any] = []
            if scope is not None:
                q += " AND scope = ?"
                params.append(scope)
            if active_only:
                q += " AND is_active = 1"
            q += " ORDER BY created_at DESC"
            rows = self._conn.execute(q, params).fetchall()
        return [self._template_row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_explanation(self, template_id: str,
                             explanation_data: dict[str, Any]) -> dict:
        """Validate explanation data against a template.

        Checks:
        1. All required fields are present and non-empty.
        2. Quality criteria (min_length, max_length, pattern, type) are met.

        Returns:
            Dict with validation_id, passed, errors, score.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM explanation_templates WHERE template_id = ?",
                (template_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Template '{template_id}' not found.")

            required = json.loads(row["required_fields"])
            criteria = json.loads(row["quality_criteria"])

        errors: list[str] = []

        # Check required fields
        for field_def in required:
            field_name = field_def.get("name", "") if isinstance(field_def, dict) else str(field_def)
            value = explanation_data.get(field_name)
            if value is None or value == "":
                errors.append(f"Missing required field: {field_name}")

        # Check quality criteria
        for criterion in criteria:
            field_name = criterion.get("field", "")
            value = explanation_data.get(field_name)

            min_length = criterion.get("min_length")
            if min_length is not None and value is not None:
                if len(str(value)) < min_length:
                    errors.append(
                        f"Field '{field_name}' too short: "
                        f"{len(str(value))} < {min_length}"
                    )

            max_length = criterion.get("max_length")
            if max_length is not None and value is not None:
                if len(str(value)) > max_length:
                    errors.append(
                        f"Field '{field_name}' too long: "
                        f"{len(str(value))} > {max_length}"
                    )

            pattern = criterion.get("pattern")
            if pattern and value is not None:
                if not re.search(pattern, str(value)):
                    errors.append(
                        f"Field '{field_name}' does not match pattern: {pattern}"
                    )

            expected_type = criterion.get("type")
            if expected_type and value is not None:
                type_map = {
                    "string": str, "int": int, "float": (int, float),
                    "bool": bool, "list": list, "dict": dict,
                }
                expected_cls = type_map.get(expected_type)
                if expected_cls and not isinstance(value, expected_cls):
                    errors.append(
                        f"Field '{field_name}' has wrong type: "
                        f"expected {expected_type}, got {type(value).__name__}"
                    )

        passed = len(errors) == 0
        total_checks = len(required) + len(criteria)
        score = round(
            (total_checks - len(errors)) / total_checks, 4
        ) if total_checks > 0 else 1.0

        validation_id = uuid.uuid4().hex
        now = time.time()

        with self._lock:
            self._conn.execute("""
                INSERT INTO explanation_validations
                (validation_id, template_id, explanation_data, passed, errors, score, validated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (validation_id, template_id, json.dumps(explanation_data),
                  1 if passed else 0, json.dumps(errors), score, now))
            self._conn.commit()

        event_payload = {
            "validation_id": validation_id,
            "template_id": template_id,
            "passed": passed,
            "score": score,
            "error_count": len(errors),
        }

        if passed:
            self._emit("explanation_validated", event_payload)
        else:
            self._emit("validation_failed", {
                **event_payload,
                "errors": errors,
            })

        log.info("validated explanation against %s: passed=%s score=%.2f",
                 template_id, passed, score)

        return {
            "validation_id": validation_id,
            "template_id": template_id,
            "passed": passed,
            "errors": errors,
            "score": score,
            "validated_at": now,
        }

    def list_validations(self, template_id: str | None = None,
                         limit: int = 100) -> list[dict]:
        """List validations, optionally filtered by template."""
        with self._lock:
            q = "SELECT * FROM explanation_validations WHERE 1=1"
            params: list[Any] = []
            if template_id is not None:
                q += " AND template_id = ?"
                params.append(template_id)
            q += " ORDER BY validated_at DESC LIMIT ?"
            params.append(limit)
            rows = self._conn.execute(q, params).fetchall()
        return [self._validation_row_to_dict(r) for r in rows]

    def get_validation_stats(self) -> dict[str, Any]:
        """Aggregate validation statistics."""
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) FROM explanation_validations"
            ).fetchone()[0]

            passed_count = self._conn.execute(
                "SELECT COUNT(*) FROM explanation_validations WHERE passed = 1"
            ).fetchone()[0]

            failed_count = self._conn.execute(
                "SELECT COUNT(*) FROM explanation_validations WHERE passed = 0"
            ).fetchone()[0]

            avg_row = self._conn.execute(
                "SELECT AVG(score) as avg FROM explanation_validations"
            ).fetchone()
            avg_score = round(avg_row["avg"], 4) if avg_row["avg"] is not None else 0.0

            template_count = self._conn.execute(
                "SELECT COUNT(*) FROM explanation_templates"
            ).fetchone()[0]

        return {
            "total_validations": total,
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate": round(passed_count / total, 4) if total > 0 else 0.0,
            "average_score": avg_score,
            "template_count": template_count,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_param(value, default):
        if value is None:
            return default
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _template_row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["required_fields"] = json.loads(d.get("required_fields", "[]"))
        d["quality_criteria"] = json.loads(d.get("quality_criteria", "[]"))
        d["is_active"] = bool(d.get("is_active", 1))
        return d

    @staticmethod
    def _validation_row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        d["explanation_data"] = json.loads(d.get("explanation_data", "{}"))
        d["errors"] = json.loads(d.get("errors", "[]"))
        d["passed"] = bool(d.get("passed", 0))
        return d

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="governance.self_explanation_validator",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_validator: SelfExplanationValidator | None = None


def get_self_explanation_validator(db_path: str | Path | None = None,
                                   event_bus: EventBus | None = None) -> SelfExplanationValidator:
    """Return the global SelfExplanationValidator singleton."""
    global _validator
    if _validator is None:
        _validator = SelfExplanationValidator(db_path, event_bus)
    return _validator


def reset_self_explanation_validator() -> None:
    """Reset the global singleton (for testing)."""
    global _validator
    _validator = None
