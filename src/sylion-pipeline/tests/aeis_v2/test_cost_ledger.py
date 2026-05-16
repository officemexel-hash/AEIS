"""Tests for sylion.aeis_v2.deployment.cost_ledger — W17 Phase 0.

Per ADR-001 Decision #3 the cost-ledger is event-sourced: every routing
decision (Phase 0) and every adapter call (G2) emits a ``cost.recorded``
event. These tests validate the Phase 0 spine — JSONL durable write +
best-effort event-bus broadcast + the JSONL-backed query/aggregate API.

Patterns mirror ``tests/aeis_v2/test_ontology_applier.py``:
- Autouse fixture monkeypatches ``COST_AUDIT_LOG_PATH`` onto ``tmp_path``
  so test rows never pollute the real ``logs/v2/cost_ledger.jsonl``.
- One integration test exercises ``federation.route()`` → cost row to
  prove the ``decision_id`` correlation works end-to-end.
"""
from __future__ import annotations

import json
import time

import pytest

from sylion.aeis_v2.deployment import cost_ledger as cost_ledger_mod
from sylion.aeis_v2.deployment.cost_ledger import (
    CostRecord,
    aggregate_cost_by,
    emit_cost_record,
    query_cost_jsonl,
)


@pytest.fixture(autouse=True)
def _redirect_cost_log(tmp_path, monkeypatch):
    """Redirect ``COST_AUDIT_LOG_PATH`` to ``tmp_path`` for every test.

    Without this fixture, ``emit_cost_record`` would append to the real
    repo file ``logs/v2/cost_ledger.jsonl`` whenever the suite runs. With
    it, every test gets an isolated cost ledger under ``tmp_path``.
    """
    monkeypatch.setattr(
        cost_ledger_mod, "COST_AUDIT_LOG_PATH", tmp_path / "cost_ledger.jsonl",
    )
    return tmp_path / "cost_ledger.jsonl"


# --------------------------------------------------------------------------
# 1. CostRecord shape
# --------------------------------------------------------------------------


def test_cost_record_to_dict_shape() -> None:
    """``CostRecord.to_dict`` must round-trip every field as JSON-friendly types.

    The schema is the contract for both the JSONL line format and the
    event_bus payload — downstream G2 PG ingestion subscribes to the
    same dict shape, so missing/renamed keys break the materialized
    view ingest.
    """
    record = CostRecord(
        ts=1700000000.5,
        session_id="sess-A",
        decision_id="dec-XYZ",
        host="node-1",
        model="qwen2.5:72b",
        tokens_in=100,
        tokens_out=200,
        cost_usd=0.0035,
        metadata={"phase": "0", "node_name": "laptop-warsaw"},
    )
    payload = record.to_dict()
    assert set(payload.keys()) == {
        "ts", "session_id", "decision_id", "host", "model",
        "tokens_in", "tokens_out", "cost_usd", "metadata",
    }
    assert payload["ts"] == 1700000000.5
    assert payload["session_id"] == "sess-A"
    assert payload["decision_id"] == "dec-XYZ"
    assert payload["host"] == "node-1"
    assert payload["model"] == "qwen2.5:72b"
    assert payload["tokens_in"] == 100
    assert payload["tokens_out"] == 200
    assert payload["cost_usd"] == pytest.approx(0.0035)
    assert payload["metadata"] == {"phase": "0", "node_name": "laptop-warsaw"}
    # Must be JSON-serializable (this is the actual JSONL format).
    line = json.dumps(payload)
    assert json.loads(line) == payload


# --------------------------------------------------------------------------
# 2. emit_cost_record writes JSONL
# --------------------------------------------------------------------------


def test_emit_cost_record_writes_jsonl(_redirect_cost_log) -> None:
    """Each emit appends one parseable JSON line to the ledger file."""
    rec1 = CostRecord(
        ts=1.0, session_id="s1", decision_id="d1",
        host="h1", model="qwen2.5:72b",
        tokens_in=10, tokens_out=20, cost_usd=0.5,
    )
    rec2 = CostRecord(
        ts=2.0, session_id="s2", decision_id="d2",
        host="h2", model="gpt-4",
        tokens_in=100, tokens_out=50, cost_usd=1.5,
    )
    emit_cost_record(rec1)
    emit_cost_record(rec2)

    log_path = _redirect_cost_log
    assert log_path.exists()
    # Sprint 3: cost_ledger emit migrated to chained audit_chain format.
    # Each row is wrapped as ``{prev_hash, content: {kind, ...}, content_hash}``;
    # walk via the ``content`` subkey to compare semantic fields.
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row1 = json.loads(lines[0])["content"]
    row2 = json.loads(lines[1])["content"]
    assert row1["decision_id"] == "d1"
    assert row1["model"] == "qwen2.5:72b"
    assert row1["kind"] == "cost_ledger.record"
    assert row2["decision_id"] == "d2"
    assert row2["cost_usd"] == 1.5


# --------------------------------------------------------------------------
# 3. emit_cost_record swallows JSONL write failure
# --------------------------------------------------------------------------


def test_cost_ledger_audit_chain_verifies(_redirect_cost_log) -> None:
    """Sprint 3 — cost_ledger emit produces a verifiable chain."""
    from sylion.aeis_v2.audit_chain import verify_chain

    for i in range(5):
        emit_cost_record(CostRecord(
            ts=float(i), session_id=f"s{i}", decision_id=f"d-{i}",
            host="h", model="m", tokens_in=10, tokens_out=20, cost_usd=0.1,
        ))
    assert verify_chain(_redirect_cost_log) == []


def test_query_cost_jsonl_reads_chained_format(_redirect_cost_log) -> None:
    """Reader walks the chained `content` subkey transparently."""
    rec = CostRecord(
        ts=1.0, session_id="s1", decision_id="d-chain-1",
        host="h", model="m", tokens_in=10, tokens_out=20, cost_usd=0.1,
    )
    emit_cost_record(rec)
    rows = query_cost_jsonl()
    assert len(rows) == 1
    assert rows[0].decision_id == "d-chain-1"


def test_emit_cost_record_handles_jsonl_write_failure_gracefully(
    monkeypatch, caplog,
) -> None:
    """A disk error must not raise — the routing decision must still complete.

    Per ADR-001 #3, the JSONL is durable but best-effort: if the volume
    is full or read-only, the WARNING is logged and the event_bus
    broadcast still fires (G2 PG subscriber may pick it up live even
    when disk write fails). This test pins that contract.

    Sprint 3: emit migrated to ``append_to_chain`` (commit ac97e957).
    We now monkeypatch the chain helper to raise; the cost_ledger
    wrapper still logs ``"jsonl write failed"`` at WARNING and keeps
    the event-bus broadcast alive.
    """
    def _raise_on_append(*_args, **_kwargs):
        raise OSError("simulated disk full")

    # Replace ``append_to_chain`` at the import site inside cost_ledger.
    # The function is imported lazily inside emit_cost_record, so we
    # patch the audit_chain module's name binding.
    import sylion.aeis_v2.audit_chain as audit_chain_pkg
    monkeypatch.setattr(
        audit_chain_pkg, "append_to_chain", _raise_on_append,
    )
    record = CostRecord(
        ts=time.time(), session_id="x", decision_id="d-fail",
        host="h", model="m",
    )

    # Must NOT raise.
    with caplog.at_level("WARNING"):
        emit_cost_record(record)

    # The warning is logged so the operator can correlate (G2 will alert
    # on this from the PG subscriber's monitoring sidecar).
    assert any(
        "jsonl write failed" in rec.message.lower()
        or "simulated disk full" in rec.message
        for rec in caplog.records
    )


# --------------------------------------------------------------------------
# 4. query_cost_jsonl filters by model
# --------------------------------------------------------------------------


def test_query_cost_jsonl_filters_by_model() -> None:
    """The model filter is exact match — no glob, no prefix."""
    emit_cost_record(CostRecord(
        ts=1.0, session_id="s", decision_id="d1", host="h",
        model="qwen2.5:72b", tokens_in=1, tokens_out=1, cost_usd=0.1,
    ))
    emit_cost_record(CostRecord(
        ts=2.0, session_id="s", decision_id="d2", host="h",
        model="gpt-4", tokens_in=1, tokens_out=1, cost_usd=0.2,
    ))
    emit_cost_record(CostRecord(
        ts=3.0, session_id="s", decision_id="d3", host="h",
        model="qwen2.5:72b", tokens_in=1, tokens_out=1, cost_usd=0.3,
    ))

    qwen_rows = query_cost_jsonl(model="qwen2.5:72b")
    assert len(qwen_rows) == 2
    assert {r.decision_id for r in qwen_rows} == {"d1", "d3"}

    gpt_rows = query_cost_jsonl(model="gpt-4")
    assert len(gpt_rows) == 1
    assert gpt_rows[0].decision_id == "d2"

    # No filter -> all 3.
    assert len(query_cost_jsonl()) == 3


# --------------------------------------------------------------------------
# 5. query_cost_jsonl filters by time window
# --------------------------------------------------------------------------


def test_query_cost_jsonl_filters_by_time_window() -> None:
    """``since_ts`` / ``until_ts`` are inclusive bounds."""
    for ts in (1.0, 5.0, 10.0, 15.0, 20.0):
        emit_cost_record(CostRecord(
            ts=ts, session_id="s",
            decision_id=f"d-{int(ts)}",
            host="h", model="m",
            cost_usd=ts,
        ))

    # Lower bound only.
    rows = query_cost_jsonl(since_ts=10.0)
    assert [r.ts for r in rows] == [10.0, 15.0, 20.0]

    # Upper bound only.
    rows = query_cost_jsonl(until_ts=10.0)
    assert [r.ts for r in rows] == [1.0, 5.0, 10.0]

    # Both bounds (window).
    rows = query_cost_jsonl(since_ts=5.0, until_ts=15.0)
    assert [r.ts for r in rows] == [5.0, 10.0, 15.0]

    # Empty window.
    rows = query_cost_jsonl(since_ts=100.0)
    assert rows == []


# --------------------------------------------------------------------------
# 6. aggregate_cost_by(model)
# --------------------------------------------------------------------------


def test_aggregate_cost_by_model_sums_correctly() -> None:
    """Per-model totals add cost_usd, tokens_in, tokens_out, and call_count."""
    emit_cost_record(CostRecord(
        ts=1.0, session_id="s1", decision_id="d1", host="h",
        model="qwen", tokens_in=100, tokens_out=50, cost_usd=0.10,
    ))
    emit_cost_record(CostRecord(
        ts=2.0, session_id="s2", decision_id="d2", host="h",
        model="qwen", tokens_in=200, tokens_out=80, cost_usd=0.25,
    ))
    emit_cost_record(CostRecord(
        ts=3.0, session_id="s3", decision_id="d3", host="h",
        model="gpt", tokens_in=10, tokens_out=20, cost_usd=0.05,
    ))

    agg = aggregate_cost_by(group_by="model")
    assert set(agg.keys()) == {"qwen", "gpt"}

    qwen = agg["qwen"]
    assert qwen["total_usd"] == pytest.approx(0.35)
    assert qwen["total_tokens_in"] == pytest.approx(300.0)
    assert qwen["total_tokens_out"] == pytest.approx(130.0)
    assert qwen["call_count"] == pytest.approx(2.0)

    gpt = agg["gpt"]
    assert gpt["total_usd"] == pytest.approx(0.05)
    assert gpt["call_count"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# 7. aggregate_cost_by(session_id)
# --------------------------------------------------------------------------


def test_aggregate_cost_by_session_returns_per_session_totals() -> None:
    """Same machinery, different group key — proves group_by parameter works."""
    emit_cost_record(CostRecord(
        ts=1.0, session_id="alpha", decision_id="d1", host="h",
        model="m", tokens_in=10, tokens_out=10, cost_usd=0.1,
    ))
    emit_cost_record(CostRecord(
        ts=2.0, session_id="alpha", decision_id="d2", host="h",
        model="m", tokens_in=20, tokens_out=10, cost_usd=0.2,
    ))
    emit_cost_record(CostRecord(
        ts=3.0, session_id="beta", decision_id="d3", host="h",
        model="m", tokens_in=5, tokens_out=5, cost_usd=0.05,
    ))

    agg = aggregate_cost_by(group_by="session_id")
    assert set(agg.keys()) == {"alpha", "beta"}
    assert agg["alpha"]["call_count"] == pytest.approx(2.0)
    assert agg["alpha"]["total_usd"] == pytest.approx(0.3)
    assert agg["beta"]["call_count"] == pytest.approx(1.0)
    assert agg["beta"]["total_usd"] == pytest.approx(0.05)


def test_aggregate_cost_by_rejects_invalid_group_by() -> None:
    """``group_by`` must be one of the documented dimensions."""
    with pytest.raises(ValueError) as exc:
        aggregate_cost_by(group_by="bogus")
    assert "group_by" in str(exc.value)


# --------------------------------------------------------------------------
# 8. Integration: federation.route() emits a cost row keyed on decision_id
# --------------------------------------------------------------------------


def test_route_emits_cost_record_with_decision_id() -> None:
    """``FederationRouter.route`` must produce a JSONL line per chosen decision.

    ADR-001 #3 says cost-recording is wired into the router's success
    path. We register a node, route a request that picks it, and assert
    the cost ledger now has a row whose ``decision_id`` matches the
    returned ``RoutingDecision.decision_id``.
    """
    from sylion.aeis_v2.deployment.federation import (
        FederationRouter,
        RoutingRequest,
    )
    from sylion.aeis_v2.deployment.nodes import (
        Node,
        NodeKind,
        NodeStatus,
        PrivacyLevel,
    )
    from sylion.aeis_v2.deployment.registry import NodeRegistry

    reg = NodeRegistry()
    node = reg.register(Node(
        node_id="",
        name="laptop-warsaw",
        kind=NodeKind.HYBRID,
        status=NodeStatus.ONLINE,
        locality="local",
        available_models=["qwen2.5:72b"],
        cost_per_1k_tokens_usd={"qwen2.5:72b": 0.001},
    ))
    rtr = FederationRouter(reg)
    decision = rtr.route(RoutingRequest(
        model_id="qwen2.5:72b",
        privacy_level=PrivacyLevel.LOCAL_ONLY,
    ))
    assert decision.chosen_node_id == node.node_id
    assert decision.decision_id  # non-empty

    rows = query_cost_jsonl(model="qwen2.5:72b")
    matching = [r for r in rows if r.decision_id == decision.decision_id]
    assert len(matching) == 1, (
        f"expected exactly 1 cost row for decision {decision.decision_id}, "
        f"got {len(matching)}; all rows: {[r.to_dict() for r in rows]}"
    )
    cost_row = matching[0]
    assert cost_row.host == node.node_id
    assert cost_row.model == "qwen2.5:72b"
    # Phase 0 placeholder — tokens=0, cost_usd=0.0; G2 reconciles after
    # the actual adapter call lands.
    assert cost_row.tokens_in == 0
    assert cost_row.tokens_out == 0
    assert cost_row.cost_usd == 0.0
    # Metadata captures the cost-per-1k so reconciliation can derive
    # cost_usd later.
    assert cost_row.metadata.get("cost_per_1k") == pytest.approx(0.001)
    assert cost_row.metadata.get("phase") == "0"


def test_route_no_cost_row_when_no_node_chosen() -> None:
    """Nothing is emitted when the router finds no matching node.

    Empty registry → ``chosen_node_id is None`` → cost ledger remains
    empty. The routing audit row still records the rejection (different
    file), but cost ledger is reserved for actual placements.
    """
    from sylion.aeis_v2.deployment.federation import (
        FederationRouter,
        RoutingRequest,
    )
    from sylion.aeis_v2.deployment.registry import NodeRegistry

    reg = NodeRegistry()  # empty
    rtr = FederationRouter(reg)
    decision = rtr.route(RoutingRequest(model_id="qwen2.5:72b"))
    assert decision.chosen_node_id is None

    assert query_cost_jsonl() == []
