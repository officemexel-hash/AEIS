"""Tests for ``scripts/v2/migrate_cost_ledger_to_pg.py`` CLI."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_cli():
    cli_path = (
        Path(__file__).resolve().parents[3]
        / "scripts" / "v2" / "migrate_cost_ledger_to_pg.py"
    )
    if not cli_path.exists():
        cli_path = (
            Path(__file__).resolve().parents[4]
            / "scripts" / "v2" / "migrate_cost_ledger_to_pg.py"
        )
    spec = importlib.util.spec_from_file_location(
        "migrate_cost_ledger_to_pg", cli_path,
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(decision_id: str) -> dict:
    return {
        "ts": 1.0, "session_id": "s", "decision_id": decision_id,
        "host": "h", "model": "m",
        "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# Default behaviour — defaults to dry-run for safety.
# ---------------------------------------------------------------------------


def test_no_mode_defaults_to_dry_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1")])
    rc = cli.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "DRY-RUN" in out


def test_dry_run_explicit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1"), _row("d2")])
    rc = cli.main(["--root", str(tmp_path), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "2 rows seen" in out
    assert "2 valid" in out


def test_dry_run_json_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    _write_jsonl(tmp_path / "cost_ledger.jsonl", [_row("d1")])
    rc = cli.main(["--root", str(tmp_path), "--dry-run", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["total_seen"] == 1
    assert payload["total_valid"] == 1


def test_dry_run_counts_invalid_rows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "cost_ledger.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(_row("d1")) + "\n"
        + "not-json\n"
        + json.dumps({"ts": 1.0}) + "\n",  # missing decision_id
        encoding="utf-8",
    )
    rc = cli.main(["--root", str(tmp_path), "--dry-run", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["total_seen"] == 3
    assert payload["total_valid"] == 1
    assert payload["total_invalid"] == 2


def test_dry_run_missing_root_returns_zero_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    rc = cli.main(["--root", str(tmp_path / "nope"), "--dry-run", "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["total_seen"] == 0


# ---------------------------------------------------------------------------
# DSN required for non-dry-run modes.
# ---------------------------------------------------------------------------


def test_apply_without_dsn_fails_with_exit_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    monkeypatch.delenv("SYLION_PG_DSN", raising=False)
    rc = cli.main(["--root", str(tmp_path), "--apply"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "DSN" in err.upper() or "dsn" in err


def test_schema_only_without_dsn_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    monkeypatch.delenv("SYLION_PG_DSN", raising=False)
    rc = cli.main(["--root", str(tmp_path), "--schema-only"])
    assert rc == 2


def test_dry_run_does_not_require_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = _load_cli()
    monkeypatch.delenv("SYLION_PG_DSN", raising=False)
    rc = cli.main(["--root", str(tmp_path), "--dry-run"])
    assert rc == 0


# ---------------------------------------------------------------------------
# Mutually exclusive mode flags.
# ---------------------------------------------------------------------------


def test_dry_run_and_apply_mutually_exclusive(tmp_path: Path) -> None:
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli.main(["--root", str(tmp_path), "--dry-run", "--apply"])
