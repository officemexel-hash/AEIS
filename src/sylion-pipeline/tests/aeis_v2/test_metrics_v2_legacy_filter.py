"""Regression test for metrics_v2 violation counter on mixed legacy chains.

Bug fixed 2026-04-28: ``sylion_v2_audit_chain_violations_total{module="council_wedge"}``
emitted 98 false-positive violations because ``council_wedge.jsonl`` is a
mixed file — first 98 rows are legacy raw JSONL (pre-migration), tail rows
are chained format starting fresh at GENESIS. The naive
``len(verify_chain(path))`` reports the legacy rows as ``missing_field``
faults; the real chained tail is intact.

The fix: ``_count_violations`` filters out faults whose line numbers fall
in the legacy section, mirroring the CLI ``verify_audit_chains.py``
behaviour for mixed files.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _write(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_count_violations_skips_legacy_only_file(tmp_path: Path) -> None:
    """A wholly-legacy file → 0 violations (legacy is not under contract)."""
    from sylion.api.metrics_v2_routes import _count_violations

    p = tmp_path / "legacy.jsonl"
    _write(p, [
        '{"ts": 1.0, "kind": "x", "actor": "a"}',
        '{"ts": 2.0, "kind": "y", "actor": "b"}',
    ])
    assert _count_violations(p) == 0


def test_count_violations_respects_clean_chained(tmp_path: Path) -> None:
    """A wholly-chained intact file → 0 violations."""
    from sylion.aeis_v2.audit_chain import append_to_chain
    from sylion.api.metrics_v2_routes import _count_violations

    p = tmp_path / "clean.jsonl"
    append_to_chain(p, {"kind": "test", "n": 1})
    append_to_chain(p, {"kind": "test", "n": 2})
    assert _count_violations(p) == 0


def test_count_violations_mixed_legacy_then_chained(tmp_path: Path) -> None:
    """Mixed file mirrors council_wedge.jsonl shape exactly."""
    from sylion.aeis_v2.audit_chain import append_to_chain
    from sylion.api.metrics_v2_routes import _count_violations

    p = tmp_path / "mixed.jsonl"
    # 3 legacy rows.
    legacy_rows = [
        '{"ts": 1.0, "kind": "old.event", "actor": "a"}',
        '{"ts": 2.0, "kind": "old.event", "actor": "b"}',
        '{"ts": 3.0, "kind": "old.event", "actor": "c"}',
    ]
    p.write_text("\n".join(legacy_rows) + "\n", encoding="utf-8")
    # 2 chained rows appended (the chain restarts from GENESIS automatically
    # because no prior row had prev_hash/content_hash to read).
    append_to_chain(p, {"kind": "new.event", "n": 1})
    append_to_chain(p, {"kind": "new.event", "n": 2})

    # Naive verify_chain reports the 3 legacy rows as faults; the metric
    # filter strips those.
    assert _count_violations(p) == 0


def test_count_violations_detects_real_tampering_in_chained_section(
    tmp_path: Path,
) -> None:
    """A real tampered row in the chained section MUST still be counted."""
    from sylion.aeis_v2.audit_chain import append_to_chain
    from sylion.api.metrics_v2_routes import _count_violations
    import json as _json

    p = tmp_path / "tampered.jsonl"
    append_to_chain(p, {"kind": "k", "v": 1})
    append_to_chain(p, {"kind": "k", "v": 2})
    append_to_chain(p, {"kind": "k", "v": 3})

    # Tamper row 2 by mutating content_hash.
    rows = p.read_text(encoding="utf-8").splitlines()
    obj = _json.loads(rows[1])
    obj["content_hash"] = "deadbeefdeadbeef"
    rows[1] = _json.dumps(obj)
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")

    # Tampered row → at least 1 fault counted (one per chain integrity rule).
    assert _count_violations(p) >= 1


def test_count_violations_handles_missing_file(tmp_path: Path) -> None:
    """Missing file path → 0, no exception."""
    from sylion.api.metrics_v2_routes import _count_violations

    assert _count_violations(tmp_path / "absent.jsonl") == 0


def test_legacy_line_numbers_helper(tmp_path: Path) -> None:
    """Per-line legacy detection works on mixed files."""
    from sylion.api.metrics_v2_routes import _legacy_line_numbers

    p = tmp_path / "mix.jsonl"
    p.write_text(
        '{"ts": 1, "kind": "x"}\n'  # legacy
        '\n'                           # blank
        '{"prev_hash": "a", "content": {"k": 1}, "content_hash": "b"}\n'  # chained
        'not even json\n'              # malformed, treated as non-legacy
        '{"ts": 2, "kind": "y"}\n',    # legacy
        encoding="utf-8",
    )
    legacy = _legacy_line_numbers(p)
    # Lines 1 and 5 are legacy; line 3 is chained; line 4 is malformed.
    assert legacy == {1, 5}
