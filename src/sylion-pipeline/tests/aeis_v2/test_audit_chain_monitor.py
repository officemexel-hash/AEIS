"""Tests for ``scripts/v2/audit_chain_monitor.py``."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import append_to_chain, verify_chain


def _load_cli():
    cli_path = (
        Path(__file__).resolve().parents[3]
        / "scripts" / "v2" / "audit_chain_monitor.py"
    )
    if not cli_path.exists():
        cli_path = (
            Path(__file__).resolve().parents[4]
            / "scripts" / "v2" / "audit_chain_monitor.py"
        )
    spec = importlib.util.spec_from_file_location("audit_chain_monitor", cli_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_discover_skips_alert_log_self(tmp_path: Path) -> None:
    cli = _load_cli()
    (tmp_path / "gdpr_dsr.jsonl").write_text("a\n")
    (tmp_path / "audit_chain_alert.jsonl").write_text("self\n")
    files = cli.discover_chain_files(tmp_path)
    names = {f.name for f in files}
    assert "gdpr_dsr.jsonl" in names
    assert "audit_chain_alert.jsonl" not in names


def test_discover_missing_root_returns_empty(tmp_path: Path) -> None:
    cli = _load_cli()
    assert cli.discover_chain_files(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# Slack payload + webhook stub
# ---------------------------------------------------------------------------


def test_build_slack_payload_includes_module_and_count() -> None:
    cli = _load_cli()
    p = cli.build_slack_payload("gdpr_dsr", 5, 42)
    assert p["text"]
    assert "gdpr_dsr" in p["text"]
    assert "5" in p["text"]
    assert isinstance(p["blocks"], list)


def test_build_slack_payload_handles_no_first_line() -> None:
    cli = _load_cli()
    p = cli.build_slack_payload("x", 0, None)
    assert "n/a" in p["text"]


def test_post_slack_webhook_handles_url_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()

    def _bad(*a, **kw):
        import urllib.error
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _bad)
    ok, detail = cli.post_slack_webhook("http://x", {})
    assert ok is False
    assert "url_error" in detail


def test_post_slack_webhook_returns_ok_on_2xx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()

    class _Resp:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def _good(*a, **kw):
        return _Resp()

    monkeypatch.setattr("urllib.request.urlopen", _good)
    ok, detail = cli.post_slack_webhook("http://x", {})
    assert ok is True


# ---------------------------------------------------------------------------
# run_once — happy clean run
# ---------------------------------------------------------------------------


def test_run_once_all_clean(tmp_path: Path) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    summary = cli.run_once(
        root=tmp_path, alert_log=tmp_path / "alert.jsonl",
    )
    assert summary["files_checked"] == 1
    assert summary["violations"] == []
    assert len(summary["clean"]) == 1


def test_run_once_with_violation(tmp_path: Path) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    # Tamper.
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    summary = cli.run_once(
        root=tmp_path, alert_log=tmp_path / "alert.jsonl",
    )
    assert len(summary["violations"]) == 1
    assert summary["violations"][0]["module"] == "x"
    assert summary["violations"][0]["fault_count"] >= 1


def test_run_once_emits_chained_alert(tmp_path: Path) -> None:
    """Alert ledger itself must remain a verifiable chain."""
    cli = _load_cli()
    alert = tmp_path / "alert.jsonl"
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    cli.run_once(root=tmp_path, alert_log=alert)
    assert verify_chain(alert) == []


def test_run_once_emits_run_heartbeat(tmp_path: Path) -> None:
    """Even with zero violations, the alert ledger gets a 'run' row."""
    cli = _load_cli()
    alert = tmp_path / "alert.jsonl"
    cli.run_once(root=tmp_path, alert_log=alert)
    rows = [
        json.loads(line)["content"]
        for line in alert.read_text(encoding="utf-8").splitlines() if line
    ]
    assert any(r.get("kind") == "audit_chain_alert.run" for r in rows)


# ---------------------------------------------------------------------------
# run_once with slack stub
# ---------------------------------------------------------------------------


def test_run_once_calls_slack_on_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    captured: list[tuple] = []

    def _fake_post(url, payload, *, timeout=5.0):
        captured.append((url, payload))
        return (True, "http 200")

    monkeypatch.setattr(cli, "post_slack_webhook", _fake_post)
    summary = cli.run_once(
        root=tmp_path,
        alert_log=tmp_path / "alert.jsonl",
        slack_webhook="https://hooks.slack.com/services/X",
    )
    assert len(captured) == 1
    assert summary["slack_results"][0]["ok"] is True


def test_run_once_skips_slack_on_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})

    captured: list[tuple] = []

    def _fake_post(url, payload, *, timeout=5.0):
        captured.append((url, payload))
        return (True, "http 200")

    monkeypatch.setattr(cli, "post_slack_webhook", _fake_post)
    cli.run_once(
        root=tmp_path,
        alert_log=tmp_path / "alert.jsonl",
        slack_webhook="https://hooks.slack.com/services/X",
    )
    assert captured == []  # no violations → no webhook fire


# ---------------------------------------------------------------------------
# main() exit codes
# ---------------------------------------------------------------------------


def test_main_returns_0_on_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    monkeypatch.delenv("SYLION_SLACK_WEBHOOK", raising=False)
    rc = cli.main([
        "--root", str(tmp_path),
        "--alert-log", str(tmp_path / "alert.jsonl"),
    ])
    assert rc == 0


def test_main_returns_1_on_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    monkeypatch.delenv("SYLION_SLACK_WEBHOOK", raising=False)
    rc = cli.main([
        "--root", str(tmp_path),
        "--alert-log", str(tmp_path / "alert.jsonl"),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "[VIOLATION]" in out


def test_main_returns_2_on_missing_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    rc = cli.main(["--root", str(tmp_path / "nope")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "root not found" in err


def test_main_json_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    monkeypatch.delenv("SYLION_SLACK_WEBHOOK", raising=False)
    rc = cli.main([
        "--root", str(tmp_path),
        "--alert-log", str(tmp_path / "alert.jsonl"),
        "--json",
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["files_checked"] == 1


def test_main_no_slack_flag_suppresses_webhook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even with SYLION_SLACK_WEBHOOK set, --no-slack suppresses calls."""
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    monkeypatch.setenv("SYLION_SLACK_WEBHOOK", "https://x")
    captured: list[tuple] = []

    def _fake_post(*a, **kw):
        captured.append(a)
        return (True, "ok")

    monkeypatch.setattr(cli, "post_slack_webhook", _fake_post)
    cli.main([
        "--root", str(tmp_path),
        "--alert-log", str(tmp_path / "alert.jsonl"),
        "--no-slack",
    ])
    assert captured == []
