"""Tests for ``scripts/v2/run_w19_adr003_council_vote.py``."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path
from typing import Any

import pytest


def _load_cli():
    cli_path = (
        Path(__file__).resolve().parents[3]
        / "scripts" / "v2" / "run_w19_adr003_council_vote.py"
    )
    if not cli_path.exists():
        cli_path = (
            Path(__file__).resolve().parents[4]
            / "scripts" / "v2" / "run_w19_adr003_council_vote.py"
        )
    spec = importlib.util.spec_from_file_location(
        "run_w19_adr003_council_vote", cli_path,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_PROPOSED_ADR = """\
# ADR-003: W19 evaluator unblock — test fixture

> **Status**: PROPOSED
> **Date**: 2026-04-28

## 1. Cel
Test body.
"""


@pytest.fixture
def adr_dir(tmp_path: Path) -> Path:
    p = tmp_path / "ADR-003.md"
    p.write_text(_PROPOSED_ADR, encoding="utf-8")
    return tmp_path


@pytest.fixture
def adr_path(adr_dir: Path) -> Path:
    return adr_dir / "ADR-003.md"


@pytest.fixture
def isolate_signoff_audit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    """Redirect adr_signoff audit log so it doesn't pollute prod state."""
    import sylion.aeis_v2.governance_v2.adr_signoff as mod

    monkeypatch.setattr(mod, "SIGNOFF_AUDIT_LOG_PATH", tmp_path / "signoff.jsonl")
    return tmp_path


# ---------------------------------------------------------------------------
# aggregate_votes
# ---------------------------------------------------------------------------


def test_aggregate_all_approve_passes_majority() -> None:
    cli = _load_cli()
    votes = [
        {"role": f"r{i}", "verdict": "approve",
         "confidence": 0.9, "rationale": "ok", "error": False}
        for i in range(9)
    ]
    summary = cli.aggregate_votes(votes)
    assert summary["counts"]["approve"] == 9
    assert summary["approve_majority"] is True


def test_aggregate_4_approve_no_majority() -> None:
    cli = _load_cli()
    votes = [
        {"role": f"r{i}",
         "verdict": "approve" if i < 4 else "reject",
         "confidence": 0.5, "rationale": "x", "error": False}
        for i in range(9)
    ]
    summary = cli.aggregate_votes(votes)
    assert summary["counts"]["approve"] == 4
    assert summary["approve_majority"] is False


def test_aggregate_5_approve_passes() -> None:
    cli = _load_cli()
    votes = [
        {"role": f"r{i}",
         "verdict": "approve" if i < 5 else "conditional",
         "confidence": 0.5, "rationale": "x", "error": False}
        for i in range(9)
    ]
    summary = cli.aggregate_votes(votes)
    assert summary["counts"]["approve"] == 5
    assert summary["approve_majority"] is True


def test_aggregate_counts_errors() -> None:
    cli = _load_cli()
    votes = [
        {"role": f"r{i}", "verdict": "approve",
         "confidence": 1.0, "rationale": "x", "error": (i == 0)}
        for i in range(9)
    ]
    summary = cli.aggregate_votes(votes)
    assert summary["errors"] == 1


# ---------------------------------------------------------------------------
# main() — dry-run + apply paths
# ---------------------------------------------------------------------------


def _stub_evaluator_factory(verdict: str = "approve"):
    """Replace make_ollama_evaluator with a deterministic closure."""

    def _evaluator(role: str, top_score: float, tags: list[str]):
        return (verdict, 0.9, f"[{role}/scripted] {verdict}")

    def _factory():
        return _evaluator

    return _factory


def test_main_default_is_dry_run(
    adr_path: Path, isolate_signoff_audit,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    import sylion.aeis_v2.council_v2 as council_pkg

    monkeypatch.setattr(
        council_pkg, "make_ollama_evaluator",
        _stub_evaluator_factory("approve"),
    )

    rc = cli.main(["--adr", str(adr_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "approve=9" in out
    assert "approve_majority=True" in out
    # File still PROPOSED — dry-run.
    from sylion.aeis_v2.governance_v2 import load_adr_status
    assert load_adr_status(adr_path) == "PROPOSED"


def test_main_apply_flips_status_when_majority(
    adr_path: Path, isolate_signoff_audit,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    import sylion.aeis_v2.council_v2 as council_pkg

    monkeypatch.setattr(
        council_pkg, "make_ollama_evaluator",
        _stub_evaluator_factory("approve"),
    )

    rc = cli.main(["--adr", str(adr_path), "--apply"])
    out = capsys.readouterr().out

    from sylion.aeis_v2.governance_v2 import load_adr_status
    assert load_adr_status(adr_path) == "ACCEPTED"
    assert rc == 0
    assert "gate_passed=True" in out


def test_main_apply_does_not_flip_when_no_majority(
    adr_path: Path, isolate_signoff_audit,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    import sylion.aeis_v2.council_v2 as council_pkg

    monkeypatch.setattr(
        council_pkg, "make_ollama_evaluator",
        _stub_evaluator_factory("reject"),
    )

    rc = cli.main(["--adr", str(adr_path), "--apply"])
    from sylion.aeis_v2.governance_v2 import load_adr_status
    assert load_adr_status(adr_path) == "PROPOSED"
    assert rc == 1


def test_main_json_output(
    adr_path: Path, isolate_signoff_audit,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    import sylion.aeis_v2.council_v2 as council_pkg

    monkeypatch.setattr(
        council_pkg, "make_ollama_evaluator",
        _stub_evaluator_factory("approve"),
    )

    rc = cli.main(["--adr", str(adr_path), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["summary"]["counts"]["approve"] == 9
    assert payload["summary"]["approve_majority"] is True
    assert len(payload["votes"]) == 9


def test_main_returns_2_on_missing_adr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    rc = cli.main(["--adr", str(tmp_path / "absent.md"), "--apply"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "not found" in err


def test_main_dry_run_and_apply_mutually_exclusive(adr_path: Path) -> None:
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli.main(["--adr", str(adr_path), "--dry-run", "--apply"])


def test_main_records_role_count_in_output(
    adr_path: Path, isolate_signoff_audit,
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    import sylion.aeis_v2.council_v2 as council_pkg

    monkeypatch.setattr(
        council_pkg, "make_ollama_evaluator",
        _stub_evaluator_factory("approve"),
    )

    cli.main(["--adr", str(adr_path), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    # All 9 canonical roles present in the result.
    role_set = {v["role"] for v in payload["votes"]}
    from sylion.governance.council_hybrid import VALID_ROLES
    assert role_set == set(VALID_ROLES)
