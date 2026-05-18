"""Global terminal command policy.

The project-scoped W18 terminal already routes high-risk project commands
through Human Gate. This module closes the global terminal gap: mutating
commands without a project scope must carry operator identity, environment,
risk class and rollback context, and D4+ commands must be approved before
they are accepted for dispatch.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from sylion.core.evidence_spine import EvidenceSpine, get_evidence_spine
from sylion.governance.ticket import GovernanceTicket, TicketStore, get_ticket_store

VALID_RISK_CLASSES: frozenset[str] = frozenset({"D0", "D1", "D2", "D3", "D4", "D5"})
D4_PLUS: frozenset[str] = frozenset({"D4", "D5"})
_RISK_ORDER: dict[str, int] = {level: idx for idx, level in enumerate(("D0", "D1", "D2", "D3", "D4", "D5"))}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("_", " ")
    text = text.replace("-", " ")
    return " ".join(text.split())


def _string_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",")]
        return [part for part in parts if part]
    if isinstance(value, Mapping):
        return [str(item).strip() for item in value.values() if str(item).strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_risk_class(value: Any) -> str:
    text = str(value or "").strip().upper()
    return text if text in VALID_RISK_CLASSES else ""


@dataclass(frozen=True)
class GlobalTerminalAction:
    key: str
    target_action: str
    default_risk_class: str
    risk_level: str
    summary: str
    aliases: tuple[str, ...]


_ACTIONS: tuple[GlobalTerminalAction, ...] = (
    GlobalTerminalAction(
        key="restart",
        target_action="restart_environment",
        default_risk_class="D4",
        risk_level="high",
        summary="Restart globalnego srodowiska runtime.",
        aliases=(
            "restart",
            "restart system",
            "system restart",
            "reboot",
            "reboot system",
            "uruchom ponownie",
            "zrestartuj",
        ),
    ),
    GlobalTerminalAction(
        key="rebuild",
        target_action="rebuild_environment",
        default_risk_class="D4",
        risk_level="high",
        summary="Odbudowa globalnego srodowiska lub obrazu runtime.",
        aliases=(
            "rebuild",
            "rebuild system",
            "system rebuild",
            "odbuduj",
            "odbuduj system",
        ),
    ),
    GlobalTerminalAction(
        key="policy_update",
        target_action="update_global_policy",
        default_risk_class="D4",
        risk_level="high",
        summary="Zmiana globalnej polityki runtime.",
        aliases=(
            "policy update",
            "update policy",
            "policy change",
            "zmien polityke",
            "aktualizuj polityke",
            "polityka update",
        ),
    ),
)


def classify_global_command_line(line: str) -> GlobalTerminalAction | None:
    """Return a global mutating action for supported terminal commands."""
    normalized = _normalize(line).lstrip("/")
    if not normalized:
        return None
    for action in _ACTIONS:
        if any(normalized == alias or normalized.startswith(f"{alias} ") for alias in action.aliases):
            return action
    return None


@dataclass(frozen=True)
class GlobalCommandPolicyRequest:
    raw_line: str
    normalized_line: str
    command_id: str
    action: GlobalTerminalAction
    actor: str
    actor_provided: bool
    environment_id: str
    risk_class: str
    risk_class_provided: bool
    rollback_hint: str
    source_surface: str = "terminal"
    project_ids: list[str] = field(default_factory=list)
    approval_ticket_ids: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_context(
        cls,
        line: str,
        ctx: Mapping[str, Any] | None = None,
        *,
        command_id: str = "",
    ) -> "GlobalCommandPolicyRequest":
        safe_ctx: Mapping[str, Any] = dict(ctx or {})
        action = classify_global_command_line(line)
        if action is None:
            raise ValueError("line is not a supported global terminal command")
        actor_raw = safe_ctx.get("actor") or safe_ctx.get("operator_id")
        risk_raw = safe_ctx.get("risk_class") or safe_ctx.get("decision_class")
        approval_ids = _string_list(safe_ctx.get("approval_ticket_ids"))
        if safe_ctx.get("approval_ticket_id") not in (None, ""):
            approval_ids.append(str(safe_ctx.get("approval_ticket_id")).strip())
        project_ids = _string_list(safe_ctx.get("project_ids"))
        declared_risk = _normalize_risk_class(risk_raw)
        default_risk = action.default_risk_class
        effective_risk = (
            declared_risk
            if declared_risk and _RISK_ORDER[declared_risk] >= _RISK_ORDER[default_risk]
            else default_risk
        )
        return cls(
            raw_line=str(line or ""),
            normalized_line=_normalize(line).lstrip("/"),
            command_id=command_id or str(safe_ctx.get("command_id") or "") or _uid("gcmd"),
            action=action,
            actor=str(actor_raw or "").strip(),
            actor_provided=bool(str(actor_raw or "").strip()),
            environment_id=str(safe_ctx.get("environment_id") or "").strip(),
            risk_class=effective_risk,
            risk_class_provided=bool(declared_risk),
            rollback_hint=str(safe_ctx.get("rollback_hint") or "").strip(),
            source_surface=str(safe_ctx.get("source_surface") or safe_ctx.get("route") or "terminal"),
            project_ids=project_ids,
            approval_ticket_ids=list(dict.fromkeys(approval_ids)),
            payload={
                "reason": safe_ctx.get("reason") or safe_ctx.get("notes") or "",
                "change_ref": safe_ctx.get("change_ref") or "",
                "declared_risk_class": declared_risk,
                "source_surface": safe_ctx.get("source_surface") or safe_ctx.get("route") or "terminal",
            },
        )


class GlobalTerminalPolicy:
    """Enforces metadata, Human Gate and replay isolation for global commands."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        evidence_spine: EvidenceSpine | None = None,
        ticket_store: TicketStore | None = None,
    ) -> None:
        self._db_path = str(db_path) if db_path else self._default_db_path()
        self._evidence_spine = evidence_spine or get_evidence_spine()
        self._ticket_store = ticket_store or get_ticket_store()
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._ensure_tables()

    @staticmethod
    def _default_db_path() -> str:
        return (
            os.environ.get("SYLION_TERMINAL_POLICY_DB_PATH")
            or os.environ.get("SYLION_DB_PATH")
            or ":memory:"
        )

    def _ensure_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS global_terminal_commands (
                record_id TEXT PRIMARY KEY,
                command_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target_action TEXT NOT NULL,
                raw_line TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT '',
                environment_id TEXT NOT NULL DEFAULT '',
                risk_class TEXT NOT NULL DEFAULT '',
                rollback_hint TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                project_ids_json TEXT NOT NULL DEFAULT '[]',
                ticket_ids_json TEXT NOT NULL DEFAULT '[]',
                approval_ticket_ids_json TEXT NOT NULL DEFAULT '[]',
                evidence_id TEXT NOT NULL DEFAULT '',
                replay_scope TEXT NOT NULL DEFAULT 'isolated',
                isolation_key TEXT NOT NULL DEFAULT '',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_gtc_command ON global_terminal_commands(command_id);
            CREATE INDEX IF NOT EXISTS idx_gtc_environment ON global_terminal_commands(environment_id);
            CREATE INDEX IF NOT EXISTS idx_gtc_action ON global_terminal_commands(action);
            CREATE INDEX IF NOT EXISTS idx_gtc_created ON global_terminal_commands(created_at);
        """)
        self._conn.commit()

    def evaluate(self, request: GlobalCommandPolicyRequest) -> dict[str, Any]:
        checks = self._checks(request)
        missing = [name for name, passed in checks.items() if not passed]
        if missing:
            return self._record(
                request,
                status="blocked_metadata",
                checks=checks,
                ticket_ids=[],
                message=(
                    "Globalna komenda jest zablokowana: wymagane pola to "
                    "actor/operator_id, environment_id, risk_class i rollback_hint."
                ),
            )

        if request.risk_class in D4_PLUS:
            approved = self._approved_coverage(request)
            if not approved["approved"]:
                ticket_ids = self._submit_gate_tickets(request, missing_targets=approved["missing_targets"])
                return self._record(
                    request,
                    status="pending_human_gate",
                    checks=checks,
                    ticket_ids=ticket_ids,
                    message=(
                        f"Globalna komenda {request.action.key} wymaga Human Gate "
                        f"{request.risk_class}. Utworzono ticket(y): {', '.join(ticket_ids)}."
                    ),
                )

        return self._record(
            request,
            status="approved",
            checks=checks,
            ticket_ids=[],
            message=(
                f"Globalna komenda {request.action.key} zaakceptowana dla "
                f"environment_id={request.environment_id}; replay_scope=isolated."
            ),
        )

    def _checks(self, request: GlobalCommandPolicyRequest) -> dict[str, bool]:
        return {
            "actor_present": request.actor_provided,
            "environment_id_present": bool(request.environment_id),
            "risk_class_present": request.risk_class_provided,
            "risk_class_valid": request.risk_class in VALID_RISK_CLASSES,
            "rollback_hint_present": bool(request.rollback_hint),
            "replay_isolation_declared": True,
        }

    def _approved_coverage(self, request: GlobalCommandPolicyRequest) -> dict[str, Any]:
        targets = request.project_ids or [""]
        approved_targets: set[str] = set()
        for ticket_id in request.approval_ticket_ids:
            ticket = self._ticket_store.get(ticket_id)
            if ticket is None or ticket.state != "approved" or ticket.origin != "global":
                continue
            if _RISK_ORDER.get(ticket.decision_class, -1) < _RISK_ORDER.get(request.risk_class, 0):
                continue
            payload = dict(ticket.payload or {})
            if payload.get("terminal_action") != request.action.key:
                continue
            if payload.get("environment_id") != request.environment_id:
                continue
            ticket_project = ticket.project_id or ""
            if request.project_ids and ticket_project not in request.project_ids:
                continue
            approved_targets.add(ticket_project)
        missing_targets = [target for target in targets if target not in approved_targets]
        return {"approved": not missing_targets, "missing_targets": missing_targets}

    def _submit_gate_tickets(self, request: GlobalCommandPolicyRequest, *, missing_targets: list[str]) -> list[str]:
        ticket_ids: list[str] = []
        targets = missing_targets or request.project_ids or [""]
        for target in targets:
            ticket = GovernanceTicket(
                origin="global",
                project_id=target or None,
                decision_class=request.risk_class,
                gate_type="blocking",
                priority="P0" if request.risk_class == "D5" else "P1",
                title=f"Global terminal {request.action.key}: {request.environment_id}",
                summary=(
                    f"{request.action.summary} Komenda: {request.raw_line}. "
                    f"Rollback: {request.rollback_hint}."
                ),
                payload={
                    "terminal_action": request.action.key,
                    "target_action": request.action.target_action,
                    "command_line": request.raw_line,
                    "normalized_line": request.normalized_line,
                    "environment_id": request.environment_id,
                    "risk_class": request.risk_class,
                    "rollback_hint": request.rollback_hint,
                    "project_ids": request.project_ids,
                    "replay_scope": "isolated",
                    "source_surface": request.source_surface,
                },
                requested_by=request.actor,
            )
            ticket_ids.append(self._ticket_store.submit(ticket))
        return ticket_ids

    def _record(
        self,
        request: GlobalCommandPolicyRequest,
        *,
        status: str,
        checks: dict[str, bool],
        ticket_ids: list[str],
        message: str,
    ) -> dict[str, Any]:
        record_id = _uid("gtc")
        created_at = time.time()
        isolation_key = f"{request.environment_id or 'unknown'}:{request.command_id}"
        payload = {
            "record_id": record_id,
            "command_id": request.command_id,
            "action": request.action.key,
            "target_action": request.action.target_action,
            "raw_line": request.raw_line,
            "actor": request.actor,
            "environment_id": request.environment_id,
            "risk_class": request.risk_class,
            "rollback_hint": request.rollback_hint,
            "status": status,
            "project_ids": request.project_ids,
            "ticket_ids": ticket_ids,
            "approval_ticket_ids": request.approval_ticket_ids,
            "checks": checks,
            "replay_scope": "isolated",
            "isolation_key": isolation_key,
            "created_at": created_at,
            "payload": request.payload,
        }
        artifact = self._evidence_spine.register_json_artifact(
            payload,
            source="terminal.global_policy",
            artifact_type="global_terminal_command",
            retention_policy="production-global-terminal-policy",
            metadata={
                "command_id": request.command_id,
                "environment_id": request.environment_id,
                "status": status,
                "action": request.action.key,
            },
            actor_id=request.actor or "unknown",
        )
        evidence_id = str(artifact["evidence_id"])
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO global_terminal_commands (
                    record_id, command_id, action, target_action, raw_line,
                    actor, environment_id, risk_class, rollback_hint, status,
                    project_ids_json, ticket_ids_json, approval_ticket_ids_json,
                    evidence_id, replay_scope, isolation_key, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    request.command_id,
                    request.action.key,
                    request.action.target_action,
                    request.raw_line,
                    request.actor,
                    request.environment_id,
                    request.risk_class,
                    request.rollback_hint,
                    status,
                    _canonical_json(request.project_ids),
                    _canonical_json(ticket_ids),
                    _canonical_json(request.approval_ticket_ids),
                    evidence_id,
                    "isolated",
                    isolation_key,
                    _canonical_json({**payload, "evidence_id": evidence_id}),
                    created_at,
                ),
            )
            self._conn.commit()
        return {
            **payload,
            "evidence_id": evidence_id,
            "message": message,
            "requires_human_gate": status == "pending_human_gate",
        }

    def get_command(self, command_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM global_terminal_commands
                WHERE command_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (command_id,),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def list_commands(self, *, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM global_terminal_commands
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def replay_isolated(self, command_id: str, *, environment_id: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM global_terminal_commands
                WHERE command_id = ? AND environment_id = ?
                ORDER BY created_at ASC
                """,
                (command_id, environment_id),
            ).fetchall()
            mixed = self._conn.execute(
                """
                SELECT COUNT(*) AS c FROM global_terminal_commands
                WHERE command_id = ? AND environment_id != ?
                """,
                (command_id, environment_id),
            ).fetchone()["c"]
        records = [self._row_to_dict(row) for row in rows]
        isolation_valid = bool(records) and all(
            record["environment_id"] == environment_id
            and record["replay_scope"] == "isolated"
            and record["isolation_key"].endswith(f":{command_id}")
            for record in records
        )
        return {
            "command_id": command_id,
            "environment_id": environment_id,
            "replay_scope": "isolated",
            "isolation_valid": isolation_valid,
            "mixed_environment_records": int(mixed or 0),
            "record_count": len(records),
            "records": records,
        }

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        for source, target in (
            ("project_ids_json", "project_ids"),
            ("ticket_ids_json", "ticket_ids"),
            ("approval_ticket_ids_json", "approval_ticket_ids"),
        ):
            try:
                data[target] = json.loads(data.pop(source) or "[]")
            except (TypeError, json.JSONDecodeError):
                data[target] = []
        try:
            data["payload"] = json.loads(data.pop("payload_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            data["payload"] = {}
        return data


_policy: GlobalTerminalPolicy | None = None
_policy_lock = threading.Lock()


def get_global_terminal_policy(
    db_path: str | Path | None = None,
    *,
    evidence_spine: EvidenceSpine | None = None,
    ticket_store: TicketStore | None = None,
) -> GlobalTerminalPolicy:
    global _policy
    with _policy_lock:
        if _policy is None:
            _policy = GlobalTerminalPolicy(
                db_path=db_path,
                evidence_spine=evidence_spine,
                ticket_store=ticket_store,
            )
        return _policy


def reset_global_terminal_policy(
    db_path: str | Path | None = None,
    *,
    evidence_spine: EvidenceSpine | None = None,
    ticket_store: TicketStore | None = None,
) -> GlobalTerminalPolicy | None:
    global _policy
    with _policy_lock:
        _policy = None
        if db_path is not None or evidence_spine is not None or ticket_store is not None:
            _policy = GlobalTerminalPolicy(
                db_path=db_path,
                evidence_spine=evidence_spine,
                ticket_store=ticket_store,
            )
        return _policy


__all__ = [
    "GlobalCommandPolicyRequest",
    "GlobalTerminalAction",
    "GlobalTerminalPolicy",
    "classify_global_command_line",
    "get_global_terminal_policy",
    "reset_global_terminal_policy",
]
