"""Tests for ``scripts/v2/verify_audit_chains.py`` CLI.

Sprint 2 day 7 — DPO ergonomics. The CLI is loaded as a module via
importlib so we can call ``main()`` from tests without spawning a
subprocess.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import append_to_chain

#: Locate the CLI from the repo root.
#: tests/aeis_v2/test_*.py is 4 levels deep from repo root:
#:   <repo>/src/sylion-pipeline/tests/aeis_v2/test_*.py
#:    ^^      ^^^^^^^^^^^^^^^   ^^^^^   ^^^^^^^^   ^^^^^^^
#:   parents[3]                                    THIS FILE
_CLI_PATH = (
    Path(__file__).resolve().parents[3]
    / "scripts" / "v2" / "verify_audit_chains.py"
)
if not _CLI_PATH.exists():
    # Fallback for repo layouts where parents[3] is not the repo root.
    _CLI_PATH = (
        Path(__file__).resolve().parents[4]
        / "scripts" / "v2" / "verify_audit_chains.py"
    )


def _load_cli():
    """Load the CLI as a module and return the namespace."""
    spec = importlib.util.spec_from_file_location("verify_audit_chains", _CLI_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_discover_returns_sorted_jsonl_files(tmp_path: Path) -> None:
    cli = _load_cli()
    (tmp_path / "z.jsonl").write_text("")
    (tmp_path / "a.jsonl").write_text("")
    (tmp_path / "ignored.txt").write_text("")
    files = cli.discover_chain_files(tmp_path)
    assert [f.name for f in files] == ["a.jsonl", "z.jsonl"]


def test_discover_missing_root_returns_empty(tmp_path: Path) -> None:
    cli = _load_cli()
    assert cli.discover_chain_files(tmp_path / "nope") == []


def test_main_returns_0_on_clean_chains(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"hello": "world"})
    append_to_chain(p, {"hello": "world2"})

    rc = cli.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "[OK    ] x.jsonl" in out
    assert "1 clean" in out and "1 total" in out


def test_main_returns_1_on_tampered_chain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"hello": "world"})
    # Corrupt — append garbage.
    with open(p, "a", encoding="utf-8") as f:
        f.write("not-json\n")

    rc = cli.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert rc == 1
    assert "[FAULT ]" in out
    assert "fault(s)" in out


def test_main_returns_2_on_missing_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    rc = cli.main(["--root", str(tmp_path / "nope")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "root not found" in err


def test_main_json_output_machine_readable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"k": 1})
    rc = cli.main(["--root", str(tmp_path), "--json"])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert rc == 0
    assert payload["files"][0]["name"] == "x.jsonl"
    assert payload["files"][0]["clean"] is True
    assert payload["files"][0]["faults"] == []


def test_main_empty_root_returns_0_with_no_files_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    cli = _load_cli()
    rc = cli.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "no *.jsonl files" in out


def test_render_report_truncates_to_10_faults(tmp_path: Path) -> None:
    cli = _load_cli()
    from sylion.aeis_v2.audit_chain import Tampered

    p = tmp_path / "x.jsonl"
    p.write_text("")  # empty file
    faults = [
        Tampered(line_no=i, reason="r", expected="e", actual="a")
        for i in range(15)
    ]
    out = cli.render_report([(p, False, faults)])
    assert "and 5 more" in out
