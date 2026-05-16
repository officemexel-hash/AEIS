"""Central W18 command router.

This module is the single backend entry point for operator commands coming
from the global W18 terminal, project W18 terminal, and dashboard actions that
want terminal-equivalent evidence. It keeps the old slash-command parser as
the read-only fallback, but wraps every command in a route/execution contract
with ownership, target, decision class and audit metadata.
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from fastapi import HTTPException

from sylion.aeis_v2.terminal.commands import CommandResult, parse_command

log = logging.getLogger("sylion.aeis_v2.terminal.command_router")

_LOG_PATH = Path(__file__).resolve().parents[3] / "logs" / "v2" / "command_router_audit.jsonl"


@dataclass
class CommandIntent:
    command_id: str = ""
    raw_line: str = ""
    normalized_line: str = ""
    source_surface: str = "terminal"
    operator_id: str = "operator"
    project_id: str = ""
    environment_id: str = ""
    agent_id: str = ""
    worker_id: str = ""
    model_id: str = ""
    decision_class: str = "D1"
    risk_level: str = "low"
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.command_id:
            self.command_id = uuid.uuid4().hex
        if not self.created_at:
            self.created_at = time.time()


@dataclass
class CommandRoute:
    route_id: str = ""
    owner: str = "terminal.parser"
    target_kind: str = "terminal_command"
    target_id: str = ""
    target_action: str = ""
    phase: str = "IMMEDIATE"
    requires_human_gate: bool = False
    dispatch_mode: str = "local_backend"
    route_reason: str = ""

    def __post_init__(self) -> None:
        if not self.route_id:
            self.route_id = uuid.uuid4().hex


@dataclass
class CommandExecution:
    intent: CommandIntent
    route: CommandRoute
    status: str = "completed"
    result: CommandResult = field(default_factory=lambda: CommandResult(kind="text", text=""))
    command_bus_intent_id: str = ""
    governance_ticket_id: str = ""
    audit_ref: str = ""

    def to_response(self) -> dict[str, Any]:
        meta = dict(self.result.meta or {})
        meta["command_intent"] = asdict(self.intent)
        meta["command_route"] = asdict(self.route)
        meta["command_execution"] = {
            "status": self.status,
            "command_bus_intent_id": self.command_bus_intent_id,
            "governance_ticket_id": self.governance_ticket_id,
            "audit_ref": self.audit_ref,
        }
        return {
            "kind": self.result.kind,
            "text": self.result.text,
            "rows": self.result.rows,
            "headers": self.result.headers,
            "target": self.result.target,
            "meta": meta,
        }


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _ctx_str(ctx: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = ctx.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


def _build_intent(line: str, ctx: Mapping[str, Any]) -> CommandIntent:
    return CommandIntent(
        raw_line=str(line or ""),
        normalized_line=_normalize(line).lstrip("/"),
        source_surface=_ctx_str(ctx, "source_surface", "route") or "terminal",
        operator_id=_ctx_str(ctx, "operator_id", "actor") or "operator",
        project_id=_ctx_str(ctx, "project_id"),
        environment_id=_ctx_str(ctx, "environment_id"),
        agent_id=_ctx_str(ctx, "agent_id"),
        worker_id=_ctx_str(ctx, "worker_id"),
        model_id=_ctx_str(ctx, "model_id"),
    )


def _route_intent(intent: CommandIntent) -> CommandRoute:
    line = intent.normalized_line
    route = CommandRoute(target_id=intent.project_id)
    if line in {"request checkpoint", "checkpoint", "zapisz checkpoint", "punkt kontrolny"}:
        intent.decision_class = "D1"
        route.owner = "terminal.command_router"
        route.target_kind = "audit_checkpoint"
        route.target_action = "request_checkpoint"
        route.route_reason = "Operator requested a checkpoint marker."
        return route

    if intent.project_id and "zamroz" in line and (
        "ksieg" in line or "kanon" in line or "source of truth" in line or "zrodlo prawdy" in line
    ):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "project_mode.round_meta"
        route.target_kind = "project"
        route.target_action = "freeze_canon"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Project Source of Truth freeze requires Human Gate."
        return route

    if intent.project_id and "zamroz" in line and "masterplan" in line:
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "project_mode.round_meta"
        route.target_kind = "project"
        route.target_action = "freeze_masterplan"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Project Masterplan freeze requires Human Gate."
        return route

    if intent.project_id and "autoryzuj" in line and (
        "budow" in line or "build" in line or "runda 3" in line
    ):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "project_mode.round_meta"
        route.target_kind = "project"
        route.target_action = "authorize_build"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Build authorization controls cost, external actions and execution."
        return route

    if intent.project_id and (
        "bramka" in line or "human gate" in line or "humangate" in line
    ):
        intent.decision_class = "D1"
        route.owner = "governance.tickets"
        route.target_kind = "project"
        route.target_action = "list_project_human_gates"
        route.route_reason = "Operator asked for project-scoped Human Gate state."
        return route

    if intent.project_id and line.startswith("runtime ustaw"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.runtime_configuration"
        route.target_kind = "project"
        route.target_action = "runtime_configuration"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Execution runtime topology/configuration changes affect worker ownership and cost posture."
        return route

    if intent.project_id and line.startswith("build initialize"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.phase32"
        route.target_kind = "project"
        route.target_action = "initialize_build"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Build initialization provisions workspace, workers, environments and repository ownership."
        return route

    if intent.project_id and line.startswith("workers smoke start"):
        intent.decision_class = "D3"
        intent.risk_level = "high"
        route.owner = "execution_start.phase32"
        route.target_kind = "project"
        route.target_action = "live_spawn_workers"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Live local worker process spawning requires operator authorization and audit evidence."
        return route

    if intent.project_id and line.startswith("workers smoke stop"):
        intent.decision_class = "D1"
        route.owner = "execution_start.phase32"
        route.target_kind = "project"
        route.target_action = "stop_live_workers"
        route.phase = "IMMEDIATE"
        route.requires_human_gate = False
        route.route_reason = "Stopping local smoke workers is a safety cleanup action."
        return route

    if intent.project_id and line.startswith("execution start"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.phase33"
        route.target_kind = "project"
        route.target_action = "start_sequential_execution"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Sequential execution starts worker activity and must be tied to project evidence."
        return route

    if intent.project_id and line.startswith("dispatch pause"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.dispatch_control"
        route.target_kind = "project"
        route.target_action = "pause_dispatch"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Pausing dispatch changes active worker flow and must be project-scoped."
        return route

    if intent.project_id and line.startswith("dispatch resume"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.dispatch_control"
        route.target_kind = "project"
        route.target_action = "resume_dispatch"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Resuming dispatch reopens worker activity and must follow project ownership rules."
        return route

    if intent.project_id and line.startswith("dispatch cancel"):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "execution_start.dispatch_control"
        route.target_kind = "project"
        route.target_action = "cancel_dispatch"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Cancelling dispatch terminates the active phase33 run and requires explicit Human Gate evidence."
        return route

    if intent.project_id and line.startswith("rada reconvene"):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "execution_start.phase34"
        route.target_kind = "project"
        route.target_action = "reconvene_mid_build_council"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Mid-build council changes the execution plan and requires governance traceability."
        return route

    if intent.project_id and line.startswith("build orchestration activate"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.phase35"
        route.target_kind = "project"
        route.target_action = "activate_orchestration"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Build orchestration activates cross-worker coordination and guardrails."
        return route

    if intent.project_id and line.startswith("build complete"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.phase36"
        route.target_kind = "project"
        route.target_action = "complete_build"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Build completion finalizes worker output, artifacts, costs and readiness for quality gates."
        return route

    if intent.project_id and line.startswith("quality gates run"):
        intent.decision_class = "D3"
        intent.risk_level = "medium"
        route.owner = "execution_start.phase37"
        route.target_kind = "project"
        route.target_action = "run_quality_gates"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Quality gates promote the build toward customer acceptance and must be auditable."
        return route

    if intent.project_id and line.startswith("acceptance complete"):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "execution_start.phase38"
        route.target_kind = "project"
        route.target_action = "complete_acceptance_testing"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Acceptance completion records customer or operator sign-off before pre-deploy authorization."
        return route

    if intent.project_id and line.startswith("predeploy authorize"):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "execution_start.phase39"
        route.target_kind = "project"
        route.target_action = "authorize_predeploy"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Pre-deploy authorization is the final hard gate before release or local rehearsal."
        return route

    if intent.project_id and line.startswith("production deploy execute"):
        intent.decision_class = "D5"
        intent.risk_level = "critical"
        route.owner = "execution_start.phase40"
        route.target_kind = "project"
        route.target_action = "execute_production_deploy"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Production deploy or local release rehearsal executes the highest-risk release action."
        return route

    if intent.project_id and line.startswith("project close"):
        intent.decision_class = "D4"
        intent.risk_level = "high"
        route.owner = "execution_start.phase41"
        route.target_kind = "project"
        route.target_action = "close_project"
        route.phase = "TWO_PHASE"
        route.requires_human_gate = True
        route.route_reason = "Project closure finalizes delivery, audit, cost reconciliation and long-horizon memory."
        return route

    if line.startswith("report workers"):
        intent.decision_class = "D1"
        route.owner = "terminal.report"
        route.target_kind = "worker_pool"
        route.target_action = "report_workers"
        route.route_reason = "Read-only worker report."
        return route

    if line.startswith("report ") or line.startswith("show ") or line.startswith("status"):
        intent.decision_class = "D1"
        route.owner = "terminal.parser"
        route.target_action = line.split(" ", 1)[0]
        route.route_reason = "Read-only slash command."
        return route

    if line.startswith("/"):
        route.target_action = line[1:].split(" ", 1)[0]
    else:
        route.target_action = line.split(" ", 1)[0] if line else ""
    route.route_reason = "Fallback to slash-command parser."
    return route


def _submit_to_command_bus(intent: CommandIntent, route: CommandRoute, *, auto_approve_by: str = "") -> str:
    try:
        from sylion.surface.command_bus import get_command_bus

        submitted = get_command_bus().submit_intent(
            intent_type="COMMAND",
            target_module=route.owner,
            target_action=route.target_action,
            payload={
                "command_id": intent.command_id,
                "raw_line": intent.raw_line,
                "normalized_line": intent.normalized_line,
                "source_surface": intent.source_surface,
                "project_id": intent.project_id,
                "environment_id": intent.environment_id,
                "agent_id": intent.agent_id,
                "worker_id": intent.worker_id,
                "model_id": intent.model_id,
                "route": asdict(route),
            },
            created_by=intent.operator_id,
            phase=route.phase,
        )
        intent_id = str(submitted.get("intent_id") or "")
        if intent_id and (route.phase == "IMMEDIATE" or auto_approve_by):
            get_command_bus().approve_intent(intent_id, approver=auto_approve_by or "command_router")
        return intent_id
    except Exception:  # noqa: BLE001
        log.warning("command_router: command bus submit failed", exc_info=True)
        return ""


def _audit_execution(execution: CommandExecution) -> str:
    row = {
        "ts": time.time(),
        "intent": asdict(execution.intent),
        "route": asdict(execution.route),
        "status": execution.status,
        "result_kind": execution.result.kind,
        "governance_ticket_id": execution.governance_ticket_id,
        "command_bus_intent_id": execution.command_bus_intent_id,
    }
    try:
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return str(_LOG_PATH)
    except Exception:  # noqa: BLE001
        log.warning("command_router: audit write failed", exc_info=True)
        return ""


def _http_error_result(exc: HTTPException) -> CommandResult:
    return CommandResult(
        kind="error",
        text=str(exc.detail or f"HTTP {exc.status_code}"),
        meta={"http_status": exc.status_code},
    )


def _project_status_line(project: dict[str, Any]) -> str:
    approvals = dict(project.get("approvals") or {})
    return (
        f"book={bool(approvals.get('book') or project.get('canon_frozen_at'))}, "
        f"masterplan={bool(approvals.get('operating_model') or project.get('masterplan_frozen_at'))}, "
        f"build_authorized={bool(project.get('build_authorized_at'))}"
    )


def _execute_freeze_canon(intent: CommandIntent) -> CommandResult:
    from sylion.api.projects_freeze_routes import freeze_canon
    from sylion.project_mode import get_project_mode_store

    try:
        result = freeze_canon(intent.project_id, None)
    except HTTPException as exc:
        return _http_error_result(exc)
    ticket_id = str(result.get("pending_governance_ticket_id") or result.get("ticket_id") or "")
    if result.get("freeze_status") == "already_frozen":
        project = get_project_mode_store().get_project(intent.project_id) or result
        return CommandResult(
            kind="text",
            text=f"Ksiega projektu jest juz zamrozona. Stan: {_project_status_line(project)}.",
            meta={"status": "already_frozen", "project_id": intent.project_id},
        )
    return CommandResult(
        kind="text",
        text=(
            "Utworzono bramke czlowieka dla zamrozenia Ksiegi. "
            f"Ticket: {ticket_id}. Ksiega nie jest zamrozona do czasu akceptacji."
        ),
        meta={"status": "pending_human_gate", "ticket_id": ticket_id, "project_id": intent.project_id},
    )


def _execute_freeze_masterplan(intent: CommandIntent) -> CommandResult:
    from sylion.api.projects_freeze_routes import freeze_masterplan
    from sylion.project_mode import get_project_mode_store

    try:
        result = freeze_masterplan(intent.project_id, None)
    except HTTPException as exc:
        return _http_error_result(exc)
    ticket_id = str(result.get("pending_governance_ticket_id") or result.get("ticket_id") or "")
    if result.get("freeze_status") == "already_frozen":
        project = get_project_mode_store().get_project(intent.project_id) or result
        return CommandResult(
            kind="text",
            text=f"Masterplan projektu jest juz zamrozony. Stan: {_project_status_line(project)}.",
            meta={"status": "already_frozen", "project_id": intent.project_id},
        )
    return CommandResult(
        kind="text",
        text=(
            "Utworzono bramke czlowieka dla zamrozenia Masterplanu. "
            f"Ticket: {ticket_id}. Budowa pozostaje zablokowana do akceptacji."
        ),
        meta={"status": "pending_human_gate", "ticket_id": ticket_id, "project_id": intent.project_id},
    )


def _execute_authorize_build(intent: CommandIntent, ctx: Mapping[str, Any]) -> CommandResult:
    from sylion.api.projects_freeze_routes import BuildAuthorizeBody, authorize_build
    from sylion.project_mode import get_project_mode_store

    project = get_project_mode_store().get_project(intent.project_id) or {}
    if project.get("build_authorized_at"):
        return CommandResult(
            kind="text",
            text=f"Budowa jest juz autoryzowana. Stan: {_project_status_line(project)}.",
            meta={"status": "already_authorized", "project_id": intent.project_id},
        )
    raw_cost = ctx.get("cost_cap_usd") or ctx.get("build_cost_cap_usd") or project.get("cost_cap_usd") or 10.0
    try:
        cost_cap = float(raw_cost)
    except (TypeError, ValueError):
        cost_cap = 10.0
    autonomy = str(ctx.get("autonomy_level") or ctx.get("build_autonomy_level") or project.get("autonomy_level") or "L2")
    if autonomy not in {"L0", "L1", "L2", "L3", "L4"}:
        autonomy = "L2"
    external_policy = ctx.get("external_actions_policy")
    if not isinstance(external_policy, dict):
        external_policy = {
            "external_publish": "blocked",
            "export_requires_human_gate": True,
            "source": "w18_command_router",
        }
    try:
        result = authorize_build(
            intent.project_id,
            BuildAuthorizeBody(
                cost_cap_usd=max(cost_cap, 0.01),
                autonomy_level=autonomy,
                external_actions_policy=external_policy,
            ),
        )
    except HTTPException as exc:
        return _http_error_result(exc)
    ticket_id = str(result.get("pending_governance_ticket_id") or result.get("ticket_id") or "")
    return CommandResult(
        kind="text",
        text=(
            "Utworzono bramke czlowieka Rundy 3 dla autoryzacji budowy. "
            f"Ticket: {ticket_id}. Workery nie startuja bez akceptacji."
        ),
        meta={"status": "pending_human_gate", "ticket_id": ticket_id, "project_id": intent.project_id},
    )


def _execute_list_project_gates(intent: CommandIntent) -> CommandResult:
    from sylion.governance.tickets import fetch_pending
    from sylion.project_mode import get_project_mode_store

    tickets = fetch_pending(project_id=intent.project_id)
    rows = []
    for ticket in tickets:
        rows.append({
            "ticket_id": ticket.ticket_id,
            "origin": ticket.origin,
            "decision_class": ticket.decision_class,
            "gate_type": ticket.gate_type,
            "priority": ticket.priority,
            "state": ticket.state,
            "title": ticket.title,
        })
    project = get_project_mode_store().get_project(intent.project_id) or {}
    if rows:
        return CommandResult(
            kind="table",
            headers=["ticket_id", "origin", "decision_class", "gate_type", "priority", "state", "title"],
            rows=rows,
            text=f"{len(rows)} oczekujacych bramek czlowieka dla projektu {intent.project_id}.",
            meta={"project_id": intent.project_id, "pending_count": len(rows)},
        )
    return CommandResult(
        kind="text",
        text=(
            "Ten projekt nie ma oczekujacego biletu bramki czlowieka. "
            f"Stan rund: {_project_status_line(project)}."
        ),
        meta={"project_id": intent.project_id, "pending_count": 0},
    )


def _execute_checkpoint(intent: CommandIntent) -> CommandResult:
    if intent.project_id:
        try:
            from sylion.project_mode import get_project_mode_store

            store = get_project_mode_store()
            if store.get_project(intent.project_id):
                store.add_event(
                    intent.project_id,
                    "terminal.checkpoint.requested",
                    {"command_id": intent.command_id, "source_surface": intent.source_surface},
                )
        except Exception:  # noqa: BLE001
            log.warning("command_router: project checkpoint event failed", exc_info=True)
    return CommandResult(
        kind="text",
        text=f"Checkpoint zapisany dla W18. command_id={intent.command_id}.",
        meta={"checkpoint": True, "command_id": intent.command_id, "project_id": intent.project_id},
    )


def record_terminal_evidence(
    line: str,
    ctx: Mapping[str, Any] | None = None,
    *,
    result_text: str = "",
    result_meta: Mapping[str, Any] | None = None,
    status: str = "completed",
    governance_ticket_id: str = "",
) -> CommandExecution:
    """Record an already-executed dashboard action in the W18 command ledger.

    Execution-start routes perform the domain mutation themselves because they
    create files, workers and phase artifacts. This helper gives those actions
    the same CommandIntent/CommandRoute/CommandExecution evidence contract as
    the interactive terminal, without executing the command twice.
    """
    safe_ctx: Mapping[str, Any] = dict(ctx or {})
    intent = _build_intent(line, safe_ctx)
    route = _route_intent(intent)
    auto_approve_by = ""
    if governance_ticket_id:
        auto_approve_by = f"governance_ticket:{governance_ticket_id}"
    result = CommandResult(
        kind="text",
        text=result_text or f"Recorded W18 command evidence for {route.target_action or intent.normalized_line}.",
        meta=dict(result_meta or {}),
    )
    bus_id = _submit_to_command_bus(intent, route, auto_approve_by=auto_approve_by)
    execution = CommandExecution(
        intent=intent,
        route=route,
        status=status,
        result=result,
        command_bus_intent_id=bus_id,
        governance_ticket_id=governance_ticket_id,
    )
    execution.audit_ref = _audit_execution(execution)
    return execution


def execute_terminal_intent(line: str, ctx: Mapping[str, Any] | None = None) -> CommandExecution:
    """Route and execute one W18 command."""
    safe_ctx: Mapping[str, Any] = dict(ctx or {})
    intent = _build_intent(line, safe_ctx)
    route = _route_intent(intent)
    bus_id = _submit_to_command_bus(intent, route)
    result: CommandResult
    if route.target_action == "freeze_canon":
        result = _execute_freeze_canon(intent)
    elif route.target_action == "freeze_masterplan":
        result = _execute_freeze_masterplan(intent)
    elif route.target_action == "authorize_build":
        result = _execute_authorize_build(intent, safe_ctx)
    elif route.target_action == "list_project_human_gates":
        result = _execute_list_project_gates(intent)
    elif route.target_action == "request_checkpoint":
        result = _execute_checkpoint(intent)
    else:
        result = parse_command(str(line or ""), dict(safe_ctx))

    ticket_id = ""
    if result.meta:
        ticket_id = str(result.meta.get("ticket_id") or result.meta.get("pending_governance_ticket_id") or "")
    status = "failed" if result.kind == "error" else "pending_human_gate" if ticket_id else "completed"
    execution = CommandExecution(
        intent=intent,
        route=route,
        status=status,
        result=result,
        command_bus_intent_id=bus_id,
        governance_ticket_id=ticket_id,
    )
    execution.audit_ref = _audit_execution(execution)
    return execution


__all__ = [
    "CommandExecution",
    "CommandIntent",
    "CommandRoute",
    "execute_terminal_intent",
    "record_terminal_evidence",
]
