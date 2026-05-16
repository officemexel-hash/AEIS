"""Tests for ``sylion.api.metrics_v2_routes`` — Prometheus exposition endpoint."""
from __future__ import annotations

from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.api.metrics_v2_routes import (
    _AUDIT_FILES,
    _aggregate_council_decisions,
    _aggregate_dsr_actions,
    _count_chain_rows,
    _count_replay_runs,
    _count_violations,
    _format_metric_line,
    render_metrics,
)


# ---------------------------------------------------------------------------
# _format_metric_line
# ---------------------------------------------------------------------------


def test_format_metric_line_no_labels() -> None:
    assert _format_metric_line("foo", 42) == "foo 42"


def test_format_metric_line_single_label() -> None:
    assert _format_metric_line("foo", 1, {"k": "v"}) == 'foo{k="v"} 1'


def test_format_metric_line_multiple_labels_sorted() -> None:
    line = _format_metric_line("foo", 7, {"b": "2", "a": "1"})
    # Labels emitted in sorted order for determinism.
    assert line == 'foo{a="1",b="2"} 7'


def test_format_metric_line_escapes_quotes() -> None:
    line = _format_metric_line("foo", 1, {"k": 'has"quote'})
    assert '\\"' in line


# ---------------------------------------------------------------------------
# Helpers — file-level counters
# ---------------------------------------------------------------------------


def test_count_chain_rows_missing_file_zero(tmp_path: Path) -> None:
    assert _count_chain_rows(tmp_path / "absent.jsonl") == 0


def test_count_chain_rows_counts_non_empty_lines(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    append_to_chain(p, {"x": 2})
    append_to_chain(p, {"x": 3})
    assert _count_chain_rows(p) == 3


def test_count_violations_clean_chain_zero(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    assert _count_violations(p) == 0


def test_count_violations_tampered_nonzero(tmp_path: Path) -> None:
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    # Append garbage line.
    with open(p, "a", encoding="utf-8") as f:
        f.write("not json\n")
    assert _count_violations(p) > 0


# ---------------------------------------------------------------------------
# Aggregators
# ---------------------------------------------------------------------------


def test_aggregate_dsr_actions_tallies_by_action(tmp_path: Path) -> None:
    p = tmp_path / "gdpr_dsr.jsonl"
    append_to_chain(p, {"action": "access"})
    append_to_chain(p, {"action": "access"})
    append_to_chain(p, {"action": "rectification"})
    counts = _aggregate_dsr_actions(p)
    assert counts == {"access": 2, "rectification": 1}


def test_aggregate_council_decisions_only_counts_decision_kind(tmp_path: Path) -> None:
    p = tmp_path / "council_wedge.jsonl"
    append_to_chain(p, {"kind": "council_wedge.decision", "verdict": "approve"})
    append_to_chain(p, {"kind": "council_wedge.decision", "verdict": "reject"})
    append_to_chain(p, {"kind": "council_wedge.other"})  # ignored
    counts = _aggregate_council_decisions(p)
    assert counts == {"approve": 1, "reject": 1}


def test_count_replay_runs_only_counts_run_kind(tmp_path: Path) -> None:
    p = tmp_path / "replay_fork.jsonl"
    append_to_chain(p, {"kind": "replay_fork.run"})
    append_to_chain(p, {"kind": "replay_fork.run"})
    append_to_chain(p, {"kind": "other"})
    assert _count_replay_runs(p) == 2


# ---------------------------------------------------------------------------
# render_metrics — full output shape
# ---------------------------------------------------------------------------


def test_render_metrics_empty_root_emits_zero_counters(tmp_path: Path) -> None:
    out = render_metrics(log_root=tmp_path)
    # All audit_chain modules report size=0.
    for module in _AUDIT_FILES:
        assert f'sylion_v2_audit_chain_size{{module="{module}"}} 0' in out
    # All DSR actions report 0.
    for action in ("access", "rectification", "erasure", "portability"):
        assert (
            f'sylion_v2_gdpr_dsr_actions_total{{action="{action}"}} 0' in out
        )
    # All council verdicts report 0.
    for verdict in ("approve", "reject", "conditional", "tie", "no_data"):
        assert (
            f'sylion_v2_council_decisions_total{{verdict="{verdict}"}} 0' in out
        )
    # Replay runs is a single counter without labels.
    assert "sylion_v2_replay_runs_total 0" in out


def test_render_metrics_includes_help_and_type_lines(tmp_path: Path) -> None:
    out = render_metrics(log_root=tmp_path)
    assert "# HELP sylion_v2_audit_chain_size" in out
    assert "# TYPE sylion_v2_audit_chain_size gauge" in out
    assert "# TYPE sylion_v2_gdpr_dsr_actions_total counter" in out
    assert "# TYPE sylion_v2_replay_runs_total counter" in out


def test_render_metrics_picks_up_actual_audit_data(tmp_path: Path) -> None:
    """Populate JSONLs and confirm the gauge / counter values reflect them."""
    dsr_p = tmp_path / "gdpr_dsr.jsonl"
    council_p = tmp_path / "council_wedge.jsonl"
    replay_p = tmp_path / "replay_fork.jsonl"

    append_to_chain(dsr_p, {"action": "access"})
    append_to_chain(dsr_p, {"action": "erasure"})
    append_to_chain(council_p, {"kind": "council_wedge.decision", "verdict": "approve"})
    append_to_chain(replay_p, {"kind": "replay_fork.run"})

    out = render_metrics(log_root=tmp_path)
    # 2 DSR rows total — 1 access + 1 erasure.
    assert 'sylion_v2_gdpr_dsr_actions_total{action="access"} 1' in out
    assert 'sylion_v2_gdpr_dsr_actions_total{action="erasure"} 1' in out
    # 1 council approval.
    assert 'sylion_v2_council_decisions_total{verdict="approve"} 1' in out
    # 1 replay run.
    assert "sylion_v2_replay_runs_total 1" in out
    # All chains clean → 0 violations.
    for module in _AUDIT_FILES:
        assert (
            f'sylion_v2_audit_chain_violations_total{{module="{module}"}} 0' in out
        )


def test_render_metrics_violations_increase_on_tamper(tmp_path: Path) -> None:
    p = tmp_path / "gdpr_dsr.jsonl"
    append_to_chain(p, {"action": "access"})
    # Tamper.
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")
    out = render_metrics(log_root=tmp_path)
    # 1 violation surfaced.
    assert (
        'sylion_v2_audit_chain_violations_total{module="gdpr_dsr"}' in out
    )
    # The numeric line should be > 0.
    for line in out.splitlines():
        if (
            line.startswith(
                'sylion_v2_audit_chain_violations_total{module="gdpr_dsr"}'
            )
        ):
            value = int(line.rsplit(" ", 1)[1])
            assert value >= 1
            break


def test_render_metrics_terminates_with_newline(tmp_path: Path) -> None:
    out = render_metrics(log_root=tmp_path)
    assert out.endswith("\n")


# ---------------------------------------------------------------------------
# Endpoint smoke (RBAC disabled).
# ---------------------------------------------------------------------------


def test_default_log_root_matches_producer_path() -> None:
    """REGRESSION (2026-04-28 runtime): _DEFAULT_LOG_ROOT must point at the
    same dir that audit_chain producers write to.

    All producers (gdpr_dsr/replay_fork/council_wedge/hard_purge/etc.)
    use ``Path(__file__).resolve().parents[3] / "logs" / "v2"`` from
    ``aeis_v2/<sub>/<module>.py`` which resolves to
    ``sylion-pipeline/logs/v2``. The metrics endpoint must scan the
    SAME root or counters always read 0.

    This test pins the path equivalence using an actual producer
    (gdpr_v2/dsr.py) as the source of truth so any future ``parents[N]``
    drift fails this test before reaching prod.
    """
    from sylion.api.metrics_v2_routes import _DEFAULT_LOG_ROOT
    import sylion.aeis_v2.gdpr_v2.dsr as dsr_mod

    expected_root = Path(dsr_mod.__file__).resolve().parents[3] / "logs" / "v2"
    assert _DEFAULT_LOG_ROOT.resolve() == expected_root.resolve(), (
        f"metrics_v2 _DEFAULT_LOG_ROOT={_DEFAULT_LOG_ROOT} does not match "
        f"producer audit_log_path root={expected_root}"
    )


def test_render_metrics_uses_audit_profile_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audit mode metrics must read the isolated chain directory."""
    audit_id = "TEST_METRICS_AUDIT_ROOT"
    monkeypatch.setenv("SYLION_AUDIT_PROFILE_ID", audit_id)

    from sylion.api.metrics_v2_routes import _effective_log_root

    root = _effective_log_root()
    assert audit_id in root.as_posix()
    assert root.as_posix().endswith(f"sylion/logs/audit/{audit_id}")


def test_endpoint_metrics_v2_returns_text(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")

    from sylion.api.metrics_v2_routes import router

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.get("/api/v1/metrics/v2")
    assert resp.status_code == 200
    body = resp.text
    assert "sylion_v2_audit_chain_size" in body
    # Plain text content type.
    assert resp.headers["content-type"].startswith("text/plain")
