"""SYLION AEIS v2 — W15 G3 WorkflowEngine.

Sprint 3 deliverable per W15 charter §4.G3 ("workflow rules + automations").

Provides a minimal, declarative workflow engine that fires on canonical
domain triggers (object create/update/status_change, scheduled cron) and
executes a small set of pluggable actions (emit_event, call_webhook,
send_email, run_script). Conditions use a tiny JSONPath-ish dotted
selector + comparison ops so operators can author rules in YAML
without writing Python.

Public API::

    rule = WorkflowRule(
        name="customer-vip-alert",
        trigger="on_status_change",
        conditions=[
            {"field": "object.type", "op": "eq", "value": "customer"},
            {"field": "object.status", "op": "eq", "value": "vip"},
        ],
        actions=[
            {"type": "emit_event",
             "topic": "customer.vip.activated",
             "payload": {"customer_id": "$.object.id"}},
        ],
    )
    engine = WorkflowEngine(audit_log_path=...)
    engine.fire(rule, {"object": {"type": "customer", "status": "vip", "id": "c1"}})

Per Kimi review k1 (round 54:30):

* ``call_webhook`` action validates URL — rejects non-https, localhost,
  and filesystem paths (`/etc/`, `/proc/`).
* ``send_email`` action strips `\n` / `\r` from subject + sender to
  prevent header injection.
* ``run_script`` action is **stubbed** (returns ``error: sandboxed``) —
  full sandboxing is outside sprint 3 scope (depends on W19 evaluator
  ACCEPTED status).
* Rule chaining is bounded by ``max_chain_depth`` (default 3) so a
  malicious rule cycle can't lock the engine.
"""

from sylion.aeis_v2.workflow_v2.engine import (
    DEFAULT_MAX_CHAIN_DEPTH,
    VALID_ACTION_TYPES,
    VALID_TRIGGERS,
    ActionResult,
    WorkflowEngine,
    WorkflowEvent,
    WorkflowRule,
    apply_condition_op,
    evaluate_workflow_conditions,
    extract_jsonpath,
    validate_workflow_rule_dict,
)

__all__ = [
    "ActionResult",
    "DEFAULT_MAX_CHAIN_DEPTH",
    "VALID_ACTION_TYPES",
    "VALID_TRIGGERS",
    "WorkflowEngine",
    "WorkflowEvent",
    "WorkflowRule",
    "apply_condition_op",
    "evaluate_workflow_conditions",
    "extract_jsonpath",
    "validate_workflow_rule_dict",
]
