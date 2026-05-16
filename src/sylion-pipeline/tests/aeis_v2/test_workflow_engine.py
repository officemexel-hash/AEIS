"""Tests for ``sylion.aeis_v2.workflow_v2`` — W15 G3 WorkflowEngine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.workflow_v2 import (
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


# ---------------------------------------------------------------------------
# Module invariants
# ---------------------------------------------------------------------------


def test_canonical_triggers() -> None:
    assert VALID_TRIGGERS == frozenset({
        "on_create", "on_update", "on_status_change", "scheduled",
    })


def test_canonical_action_types() -> None:
    assert VALID_ACTION_TYPES == frozenset({
        "emit_event", "call_webhook", "send_email", "run_script",
    })


def test_default_max_chain_depth_is_3() -> None:
    assert DEFAULT_MAX_CHAIN_DEPTH == 3


# ---------------------------------------------------------------------------
# apply_condition_op
# ---------------------------------------------------------------------------


def test_op_eq() -> None:
    assert apply_condition_op(5, "eq", 5) is True
    assert apply_condition_op(5, "eq", 6) is False


def test_op_ne() -> None:
    assert apply_condition_op(5, "ne", 6) is True
    assert apply_condition_op(5, "ne", 5) is False


def test_op_gt_lt_ge_le() -> None:
    assert apply_condition_op(10, "gt", 5) is True
    assert apply_condition_op(10, "lt", 20) is True
    assert apply_condition_op(10, "ge", 10) is True
    assert apply_condition_op(10, "le", 10) is True


def test_op_in_not_in() -> None:
    assert apply_condition_op("a", "in", ["a", "b"]) is True
    assert apply_condition_op("c", "in", ["a", "b"]) is False
    assert apply_condition_op("c", "not_in", ["a", "b"]) is True


def test_op_contains() -> None:
    assert apply_condition_op([1, 2, 3], "contains", 2) is True
    assert apply_condition_op([1, 2], "contains", 9) is False


def test_op_unknown_returns_false() -> None:
    assert apply_condition_op(1, "magic", 1) is False


def test_op_type_mismatch_falls_to_false() -> None:
    """gt across str/int blows up → fail-closed False."""
    assert apply_condition_op("abc", "gt", 5) is False


# ---------------------------------------------------------------------------
# extract_jsonpath
# ---------------------------------------------------------------------------


def test_extract_root_returns_doc() -> None:
    d = {"a": 1}
    assert extract_jsonpath("$", d) == d


def test_extract_simple_dotted() -> None:
    d = {"a": {"b": {"c": 42}}}
    assert extract_jsonpath("$.a.b.c", d) == 42


def test_extract_with_index() -> None:
    d = {"items": [{"id": "x"}, {"id": "y"}]}
    assert extract_jsonpath("$.items[1].id", d) == "y"


def test_extract_missing_returns_none() -> None:
    assert extract_jsonpath("$.missing.key", {"a": 1}) is None


def test_extract_index_out_of_range_returns_none() -> None:
    assert extract_jsonpath("$.list[5]", {"list": [1]}) is None


def test_extract_invalid_doc_returns_none() -> None:
    assert extract_jsonpath("$.x", {}) is None


# ---------------------------------------------------------------------------
# evaluate_workflow_conditions
# ---------------------------------------------------------------------------


def test_eval_empty_conditions_true() -> None:
    assert evaluate_workflow_conditions([], {"x": 1}) is True


def test_eval_single_condition_match() -> None:
    conds = [{"field": "$.status", "op": "eq", "value": "vip"}]
    assert evaluate_workflow_conditions(conds, {"status": "vip"}) is True


def test_eval_single_condition_mismatch() -> None:
    conds = [{"field": "$.status", "op": "eq", "value": "vip"}]
    assert evaluate_workflow_conditions(conds, {"status": "bronze"}) is False


def test_eval_and_semantics() -> None:
    conds = [
        {"field": "$.type", "op": "eq", "value": "customer"},
        {"field": "$.priority", "op": "ge", "value": 5},
    ]
    assert evaluate_workflow_conditions(
        conds, {"type": "customer", "priority": 7},
    ) is True
    assert evaluate_workflow_conditions(
        conds, {"type": "customer", "priority": 3},
    ) is False


def test_eval_invalid_condition_dict_false() -> None:
    """Malformed condition entries fail-close."""
    assert evaluate_workflow_conditions(
        [{"field": 123, "op": "eq", "value": 1}], {},
    ) is False


# ---------------------------------------------------------------------------
# validate_workflow_rule_dict
# ---------------------------------------------------------------------------


def _good_rule_dict() -> dict[str, Any]:
    return {
        "name": "r1",
        "trigger": "on_create",
        "conditions": [],
        "actions": [{"type": "emit_event", "topic": "t"}],
    }


def test_validate_happy_path() -> None:
    ok, errors = validate_workflow_rule_dict(_good_rule_dict())
    assert ok is True
    assert errors == []


def test_validate_rejects_missing_name() -> None:
    d = _good_rule_dict()
    del d["name"]
    ok, errs = validate_workflow_rule_dict(d)
    assert ok is False
    assert any("name" in e for e in errs)


def test_validate_rejects_unknown_trigger() -> None:
    d = _good_rule_dict()
    d["trigger"] = "on_full_moon"
    ok, errs = validate_workflow_rule_dict(d)
    assert ok is False
    assert any("trigger" in e for e in errs)


def test_validate_rejects_empty_actions() -> None:
    d = _good_rule_dict()
    d["actions"] = []
    ok, _ = validate_workflow_rule_dict(d)
    assert ok is False


def test_validate_rejects_unknown_action_type() -> None:
    d = _good_rule_dict()
    d["actions"] = [{"type": "magic"}]
    ok, errs = validate_workflow_rule_dict(d)
    assert ok is False
    assert any("action" in e for e in errs)


# ---------------------------------------------------------------------------
# WorkflowEngine.fire — happy path
# ---------------------------------------------------------------------------


def test_fire_unknown_trigger_records_error(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_full_moon",
        actions=[{"type": "emit_event", "topic": "x"}],
    )
    event = eng.fire(rule, {})
    assert event.matched is False
    assert any("unknown trigger" in r.detail for r in event.action_results)


def test_fire_no_match_no_actions(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        conditions=[{"field": "$.x", "op": "eq", "value": 99}],
        actions=[{"type": "emit_event", "topic": "t"}],
    )
    event = eng.fire(rule, {"x": 1})
    assert event.matched is False
    assert event.action_results == []


def test_fire_emit_event_default_handler(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "emit_event", "topic": "customer.vip"}],
    )
    event = eng.fire(rule, {})
    assert event.matched is True
    assert len(event.action_results) == 1
    assert event.action_results[0].status == "ok"
    assert event.action_results[0].action_type == "emit_event"


def test_fire_emit_event_missing_topic_errors(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "emit_event"}],  # no topic
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "error"


# ---------------------------------------------------------------------------
# WorkflowEngine — call_webhook URL validation (Kimi k1)
# ---------------------------------------------------------------------------


def test_webhook_rejects_non_https(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "call_webhook", "url": "http://example.com/x"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "error"
    assert "https" in event.action_results[0].detail


def test_webhook_rejects_localhost(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "call_webhook", "url": "https://localhost/x"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "error"
    assert "blocked" in event.action_results[0].detail.lower()


def test_webhook_rejects_filesystem_path(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "call_webhook",
                  "url": "https://example.com/etc/passwd"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "error"


def test_webhook_accepts_valid_https(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "call_webhook",
                  "url": "https://hooks.example.com/svc"}],
    )
    event = eng.fire(rule, {})
    # Default handler does not perform network calls — returns "skipped".
    assert event.action_results[0].status == "skipped"


# ---------------------------------------------------------------------------
# WorkflowEngine — send_email header injection (Kimi k1)
# ---------------------------------------------------------------------------


def test_email_strips_newlines_in_subject(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "send_email",
                  "subject": "ok\r\nBcc: attacker@evil",
                  "from": "noreply@sylion"}],
    )
    event = eng.fire(rule, {})
    payload = event.action_results[0].payload
    assert payload is not None
    assert "\r" not in payload["subject"]
    assert "\n" not in payload["subject"]


def test_email_missing_subject_errors(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "send_email", "from": "x@y"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "error"


# ---------------------------------------------------------------------------
# WorkflowEngine — run_script sandboxed by default
# ---------------------------------------------------------------------------


def test_run_script_sandboxed_by_default(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "run_script", "code": "print('hi')"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "sandboxed"


# ---------------------------------------------------------------------------
# WorkflowEngine — handler injection
# ---------------------------------------------------------------------------


def test_register_action_handler_overrides_default(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    captured: list[dict] = []

    def my_handler(action: dict, context: dict) -> ActionResult:
        captured.append(action)
        return ActionResult(
            action_type="run_script", status="ok", detail="my impl",
        )

    eng.register_action_handler("run_script", my_handler)
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "run_script", "code": "noop"}],
    )
    event = eng.fire(rule, {})
    assert event.action_results[0].status == "ok"
    assert event.action_results[0].detail == "my impl"
    assert len(captured) == 1


def test_register_invalid_action_type_raises(tmp_path: Path) -> None:
    eng = WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl")
    with pytest.raises(ValueError):
        eng.register_action_handler("magic", lambda a, c: ActionResult(
            action_type="x", status="ok",
        ))


# ---------------------------------------------------------------------------
# WorkflowEngine — chain depth bound (Kimi k1)
# ---------------------------------------------------------------------------


def test_max_chain_depth_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        WorkflowEngine(audit_log_path=tmp_path / "wf.jsonl", max_chain_depth=0)


def test_chain_depth_exceeded_records_error(tmp_path: Path) -> None:
    """Manually drive depth past the limit via a rule that fires itself."""
    eng = WorkflowEngine(
        audit_log_path=tmp_path / "wf.jsonl", max_chain_depth=2,
    )
    fires: list[WorkflowEvent] = []

    def chained_handler(action: dict, context: dict) -> ActionResult:
        # Re-invoke the engine on the same rule — drives chain depth.
        nested_rule = WorkflowRule(
            name="r1", trigger="on_create",
            actions=[{"type": "run_script", "code": "noop"}],
        )
        fires.append(eng.fire(nested_rule, context))
        return ActionResult(
            action_type="run_script", status="ok", detail="nested",
        )

    eng.register_action_handler("run_script", chained_handler)
    rule = WorkflowRule(
        name="r1", trigger="on_create",
        actions=[{"type": "run_script", "code": "noop"}],
    )
    eng.fire(rule, {})
    # Eventually one of the nested fires is rejected for max_chain_depth.
    chain_errors = []
    for f in fires:
        for r in f.action_results:
            if r.action_type == "<chain>":
                chain_errors.append(r)
    assert any(
        "max_chain_depth" in r.detail for r in chain_errors
    ), "expected max_chain_depth refusal somewhere in the chain"


# ---------------------------------------------------------------------------
# Audit chain integrity
# ---------------------------------------------------------------------------


def test_workflow_audit_chain_verifies(tmp_path: Path) -> None:
    audit = tmp_path / "wf.jsonl"
    eng = WorkflowEngine(audit_log_path=audit)
    rules = [
        WorkflowRule(
            name=f"r{i}", trigger="on_create",
            actions=[{"type": "emit_event", "topic": f"t{i}"}],
        )
        for i in range(3)
    ]
    for r in rules:
        eng.fire(r, {})
    assert verify_chain(audit) == []


# ---------------------------------------------------------------------------
# Dataclass round-trip
# ---------------------------------------------------------------------------


def test_workflow_rule_to_dict_round_trip() -> None:
    r = WorkflowRule(
        name="r1", trigger="on_create",
        conditions=[{"field": "$.x", "op": "eq", "value": 1}],
        actions=[{"type": "emit_event", "topic": "t"}],
    )
    d = r.to_dict()
    json.dumps(d)
    assert d["name"] == "r1"
    assert d["trigger"] == "on_create"


def test_action_result_to_dict_round_trip() -> None:
    a = ActionResult(
        action_type="emit_event", status="ok",
        detail="d", payload={"k": "v"},
    )
    d = a.to_dict()
    json.dumps(d)
    assert d["status"] == "ok"
