"""WorkflowEngine implementation."""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sylion.aeis_v2.audit_chain import append_to_chain

log = logging.getLogger(__name__)

#: Canonical trigger names. Extend with operator + Council Hybrid sign-off.
VALID_TRIGGERS: frozenset[str] = frozenset({
    "on_create", "on_update", "on_status_change", "scheduled",
})

#: Canonical action types. ``run_script`` is stubbed (sandboxed).
VALID_ACTION_TYPES: frozenset[str] = frozenset({
    "emit_event", "call_webhook", "send_email", "run_script",
})

#: Bounded chain depth — protects against malicious rule cycles
#: (per Kimi review k1 round 54:30).
DEFAULT_MAX_CHAIN_DEPTH: int = 3

#: Audit JSONL path — chained per ac97e957.
WORKFLOW_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "workflow_engine.jsonl"
)


# ---------------------------------------------------------------------------
# Condition primitives
# ---------------------------------------------------------------------------


_VALID_OPS = {"eq", "ne", "gt", "lt", "ge", "le", "in", "not_in", "contains"}


def apply_condition_op(value: Any, op: str, target: Any) -> bool:
    """Apply ``op`` to ``(value, target)``. Unknown op → ``False`` (deny)."""
    try:
        if op == "eq":
            return value == target
        if op == "ne":
            return value != target
        if op == "gt":
            return value > target  # type: ignore[operator]
        if op == "lt":
            return value < target  # type: ignore[operator]
        if op == "ge":
            return value >= target  # type: ignore[operator]
        if op == "le":
            return value <= target  # type: ignore[operator]
        if op == "in":
            return value in target
        if op == "not_in":
            return value not in target
        if op == "contains":
            return target in value  # type: ignore[operator]
    except Exception:  # noqa: BLE001 — type mismatch → fail-closed
        return False
    return False


def extract_jsonpath(expr: str, doc: dict[str, Any]) -> Any | None:
    """Walk a simple dotted path from ``$`` against ``doc``.

    Examples:
      ``$.object.id``
      ``$.list[0].name``

    Wildcard / filter syntax is not supported — the engine treats
    unknown expressions as a miss (returns None).
    """
    if not isinstance(expr, str) or not doc:
        return None
    # Accept '$.x' or '$x' or 'x'.
    expr = expr.lstrip("$")
    if expr.startswith("."):
        expr = expr[1:]
    if not expr:
        return doc
    cur: Any = doc
    # Split on '.' but tolerate '[N]' index segments.
    tokens = re.findall(r"[^.\[\]]+|\[\d+\]", expr)
    for tok in tokens:
        if tok.startswith("[") and tok.endswith("]"):
            try:
                idx = int(tok[1:-1])
            except ValueError:
                return None
            if not isinstance(cur, list) or not (0 <= idx < len(cur)):
                return None
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                return None
            if tok not in cur:
                return None
            cur = cur[tok]
    return cur


def evaluate_workflow_conditions(
    conditions: list[dict[str, Any]], context: dict[str, Any],
) -> bool:
    """Evaluate AND of conditions. Empty list → True."""
    if not conditions:
        return True
    for cond in conditions:
        if not isinstance(cond, dict):
            return False
        field = cond.get("field")
        op = cond.get("op")
        target = cond.get("value")
        if not isinstance(field, str) or not isinstance(op, str):
            return False
        actual = extract_jsonpath(field, context)
        if not apply_condition_op(actual, op, target):
            return False
    return True


# ---------------------------------------------------------------------------
# Rule + event + result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WorkflowRule:
    """A single workflow rule."""

    name: str
    trigger: str
    conditions: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trigger": self.trigger,
            "conditions": list(self.conditions),
            "actions": list(self.actions),
        }


@dataclass(frozen=True, slots=True)
class ActionResult:
    """Outcome of a single action invocation."""

    action_type: str
    status: str          # "ok" | "error" | "skipped" | "sandboxed"
    detail: str = ""
    payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_type": self.action_type,
            "status": self.status,
            "detail": self.detail,
            "payload": dict(self.payload) if self.payload else None,
        }


@dataclass(frozen=True, slots=True)
class WorkflowEvent:
    """One audit row capturing a rule fire attempt."""

    event_id: str
    ts: float
    rule_name: str
    trigger: str
    matched: bool
    action_results: list[ActionResult] = field(default_factory=list)
    chain_depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "rule_name": self.rule_name,
            "trigger": self.trigger,
            "matched": self.matched,
            "action_results": [r.to_dict() for r in self.action_results],
            "chain_depth": self.chain_depth,
        }


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def validate_workflow_rule_dict(d: dict[str, Any]) -> tuple[bool, list[str]]:
    """Required-field + canonical-value validation."""
    errors: list[str] = []
    if not isinstance(d.get("name"), str) or not d["name"].strip():
        errors.append("name: must be non-empty str")
    if d.get("trigger") not in VALID_TRIGGERS:
        errors.append(
            f"trigger: must be one of {sorted(VALID_TRIGGERS)}",
        )
    if not isinstance(d.get("conditions"), list):
        errors.append("conditions: must be list")
    actions = d.get("actions")
    if not isinstance(actions, list) or not actions:
        errors.append("actions: must be non-empty list")
    else:
        for i, a in enumerate(actions):
            if not isinstance(a, dict) or "type" not in a:
                errors.append(f"actions[{i}]: must be dict with 'type'")
                continue
            if a["type"] not in VALID_ACTION_TYPES:
                errors.append(
                    f"actions[{i}].type: must be one of "
                    f"{sorted(VALID_ACTION_TYPES)}",
                )
    return (not errors, errors)


# ---------------------------------------------------------------------------
# Action validators (security layer)
# ---------------------------------------------------------------------------


def _validate_webhook_url(url: str) -> tuple[bool, str]:
    """Reject non-https, localhost/private, filesystem paths."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return (False, "url must start with https://")
    lowered = url.lower()
    blocked_hosts = (
        "localhost", "127.0.0.1", "0.0.0.0", "169.254.",
        "10.", "192.168.", "::1",
    )
    if any(h in lowered for h in blocked_hosts):
        return (False, "host blocked (private/loopback)")
    if any(p in lowered for p in ("/etc/", "/proc/", "/sys/", "/var/")):
        return (False, "filesystem path blocked")
    return (True, "ok")


def _scrub_email_field(text: str) -> str:
    """Strip CR/LF and other header-injection vectors."""
    if not isinstance(text, str):
        return ""
    return text.replace("\r", "").replace("\n", "").strip()


# ---------------------------------------------------------------------------
# WorkflowEngine
# ---------------------------------------------------------------------------


class WorkflowEngine:
    """Executes WorkflowRules with bounded chain depth + audit emission.

    Action handlers can be overridden via ``register_action_handler`` —
    production deployments inject real webhook callers + email senders;
    tests can hook stubs. Default handlers return ``("error", "stub
    not configured")`` which prevents accidental external calls.
    """

    def __init__(
        self,
        *,
        audit_log_path: Path | str | None = None,
        max_chain_depth: int = DEFAULT_MAX_CHAIN_DEPTH,
    ) -> None:
        if max_chain_depth <= 0:
            raise ValueError("max_chain_depth must be positive")
        self._audit_log_path = (
            Path(audit_log_path) if audit_log_path is not None
            else WORKFLOW_AUDIT_LOG_PATH
        )
        self._max_chain_depth = max_chain_depth
        self._lock = threading.RLock()
        self._handlers: dict[str, Any] = {}
        self._chain_depth = 0

    @property
    def max_chain_depth(self) -> int:
        return self._max_chain_depth

    def register_action_handler(
        self, action_type: str, handler: Any,
    ) -> None:
        """Hook a custom ``(action: dict, context: dict) -> ActionResult`` callable."""
        if action_type not in VALID_ACTION_TYPES:
            raise ValueError(
                f"unknown action_type {action_type!r}; "
                f"must be one of {sorted(VALID_ACTION_TYPES)}"
            )
        self._handlers[action_type] = handler

    def _emit_audit(self, event: WorkflowEvent) -> None:
        try:
            append_to_chain(
                self._audit_log_path,
                {"kind": "workflow_engine.fire", **event.to_dict()},
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("workflow_engine: audit emit failed (%s)", exc)

    # ------------------------------------------------------------------
    # Default action handlers — safe-by-default no-ops.
    # ------------------------------------------------------------------

    def _default_emit_event(
        self, action: dict[str, Any], context: dict[str, Any],
    ) -> ActionResult:
        topic = action.get("topic")
        if not isinstance(topic, str) or not topic:
            return ActionResult(
                action_type="emit_event",
                status="error", detail="missing topic",
            )
        return ActionResult(
            action_type="emit_event",
            status="ok",
            detail=f"emit topic={topic}",
            payload={"topic": topic, "data": action.get("payload")},
        )

    def _default_call_webhook(
        self, action: dict[str, Any], context: dict[str, Any],
    ) -> ActionResult:
        url = action.get("url", "")
        ok, detail = _validate_webhook_url(url)
        if not ok:
            return ActionResult(
                action_type="call_webhook",
                status="error",
                detail=detail,
            )
        # Default impl does NOT actually call out — production handlers
        # override this.
        return ActionResult(
            action_type="call_webhook",
            status="skipped",
            detail="default handler does not perform network calls",
            payload={"url": url},
        )

    def _default_send_email(
        self, action: dict[str, Any], context: dict[str, Any],
    ) -> ActionResult:
        subject = _scrub_email_field(str(action.get("subject", "")))
        sender = _scrub_email_field(str(action.get("from", "")))
        if not subject:
            return ActionResult(
                action_type="send_email",
                status="error", detail="missing subject",
            )
        return ActionResult(
            action_type="send_email",
            status="skipped",
            detail="default handler does not send email",
            payload={"subject": subject, "from": sender},
        )

    def _default_run_script(
        self, action: dict[str, Any], context: dict[str, Any],
    ) -> ActionResult:
        # Sandboxed by default — production must explicitly register a
        # handler after Council Hybrid sign-off (analogous to W19 jinja
        # evaluator gate).
        return ActionResult(
            action_type="run_script",
            status="sandboxed",
            detail="run_script disabled by default",
        )

    def _resolve_handler(self, action_type: str):
        if action_type in self._handlers:
            return self._handlers[action_type]
        return {
            "emit_event": self._default_emit_event,
            "call_webhook": self._default_call_webhook,
            "send_email": self._default_send_email,
            "run_script": self._default_run_script,
        }.get(action_type)

    # ------------------------------------------------------------------
    # Public — fire a rule
    # ------------------------------------------------------------------

    def fire(
        self,
        rule: WorkflowRule,
        context: dict[str, Any],
    ) -> WorkflowEvent:
        """Match conditions; if matched, run actions; emit audit row."""
        with self._lock:
            self._chain_depth += 1
            depth = self._chain_depth

            try:
                # Bounded chain protection (per Kimi k1 round 54:30).
                if depth > self._max_chain_depth:
                    event = WorkflowEvent(
                        event_id=str(uuid.uuid4()),
                        ts=time.time(),
                        rule_name=rule.name,
                        trigger=rule.trigger,
                        matched=False,
                        action_results=[ActionResult(
                            action_type="<chain>",
                            status="error",
                            detail=(
                                f"max_chain_depth={self._max_chain_depth} "
                                "exceeded — possible rule cycle"
                            ),
                        )],
                        chain_depth=depth,
                    )
                    self._emit_audit(event)
                    return event

                if rule.trigger not in VALID_TRIGGERS:
                    event = WorkflowEvent(
                        event_id=str(uuid.uuid4()),
                        ts=time.time(),
                        rule_name=rule.name,
                        trigger=rule.trigger,
                        matched=False,
                        action_results=[ActionResult(
                            action_type="<trigger>",
                            status="error",
                            detail=f"unknown trigger {rule.trigger!r}",
                        )],
                        chain_depth=depth,
                    )
                    self._emit_audit(event)
                    return event

                matched = evaluate_workflow_conditions(
                    rule.conditions, context,
                )
                if not matched:
                    event = WorkflowEvent(
                        event_id=str(uuid.uuid4()),
                        ts=time.time(),
                        rule_name=rule.name,
                        trigger=rule.trigger,
                        matched=False,
                        action_results=[],
                        chain_depth=depth,
                    )
                    self._emit_audit(event)
                    return event

                results: list[ActionResult] = []
                for action in rule.actions:
                    if not isinstance(action, dict):
                        results.append(ActionResult(
                            action_type="<unknown>",
                            status="error",
                            detail="action is not a dict",
                        ))
                        continue
                    a_type = action.get("type")
                    if a_type not in VALID_ACTION_TYPES:
                        results.append(ActionResult(
                            action_type=str(a_type),
                            status="error",
                            detail=f"unknown action_type {a_type!r}",
                        ))
                        continue
                    handler = self._resolve_handler(a_type)
                    if handler is None:
                        results.append(ActionResult(
                            action_type=a_type,
                            status="error",
                            detail="no handler registered",
                        ))
                        continue
                    try:
                        results.append(handler(action, context))
                    except Exception as exc:  # noqa: BLE001
                        results.append(ActionResult(
                            action_type=a_type,
                            status="error",
                            detail=f"handler raised: {type(exc).__name__}",
                        ))

                event = WorkflowEvent(
                    event_id=str(uuid.uuid4()),
                    ts=time.time(),
                    rule_name=rule.name,
                    trigger=rule.trigger,
                    matched=True,
                    action_results=results,
                    chain_depth=depth,
                )
                self._emit_audit(event)
                return event
            finally:
                self._chain_depth -= 1


__all__ = [
    "ActionResult",
    "DEFAULT_MAX_CHAIN_DEPTH",
    "VALID_ACTION_TYPES",
    "VALID_TRIGGERS",
    "WORKFLOW_AUDIT_LOG_PATH",
    "WorkflowEngine",
    "WorkflowEvent",
    "WorkflowRule",
    "apply_condition_op",
    "evaluate_workflow_conditions",
    "extract_jsonpath",
    "validate_workflow_rule_dict",
]
