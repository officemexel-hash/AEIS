"""Tests for ``sylion.aeis_v2.audit_chain.rotator`` — sprint 3 D-rotator."""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import (
    DEFAULT_RETAIN_DAYS,
    DEFAULT_SIZE_MB_THRESHOLD,
    AuditRotator,
    EvictionReport,
    RotationDecision,
    append_to_chain,
    invalidate_last_hash_cache,
    reset_last_hash_cache,
    verify_chain,
)
from sylion.aeis_v2.audit_chain.rotator import _next_seq_for_date, _today_iso


# ---------------------------------------------------------------------------
# Defaults & validation
# ---------------------------------------------------------------------------


def test_defaults_documented_at_module_level() -> None:
    assert DEFAULT_SIZE_MB_THRESHOLD == 100
    assert DEFAULT_RETAIN_DAYS == 90


def test_constructor_rejects_non_positive_size(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        AuditRotator(size_mb_threshold=0, audit_log_path=tmp_path / "x.jsonl")


def test_constructor_rejects_non_positive_retain(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        AuditRotator(retain_days=0, audit_log_path=tmp_path / "x.jsonl")


# ---------------------------------------------------------------------------
# _today_iso + _next_seq_for_date — naming primitives
# ---------------------------------------------------------------------------


def test_today_iso_format() -> None:
    out = _today_iso(_dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc))
    assert out == "2026-04-28"


def test_today_iso_naive_datetime_treated_as_utc() -> None:
    out = _today_iso(_dt.datetime(2026, 4, 28))
    assert out == "2026-04-28"


def test_next_seq_returns_one_for_empty_dir(tmp_path: Path) -> None:
    assert _next_seq_for_date(tmp_path, "x", "2026-04-28") == 1


def test_next_seq_increments_per_existing_rotation(tmp_path: Path) -> None:
    (tmp_path / "x.2026-04-28.1.jsonl").write_text("")
    (tmp_path / "x.2026-04-28.2.jsonl").write_text("")
    (tmp_path / "x.2026-04-28.5.jsonl").write_text("")
    assert _next_seq_for_date(tmp_path, "x", "2026-04-28") == 6


def test_next_seq_isolated_per_date(tmp_path: Path) -> None:
    (tmp_path / "x.2026-04-27.3.jsonl").write_text("")
    assert _next_seq_for_date(tmp_path, "x", "2026-04-28") == 1


def test_next_seq_isolated_per_stem(tmp_path: Path) -> None:
    (tmp_path / "y.2026-04-28.1.jsonl").write_text("")
    assert _next_seq_for_date(tmp_path, "x", "2026-04-28") == 1


# ---------------------------------------------------------------------------
# rotate_if_needed
# ---------------------------------------------------------------------------


def test_rotate_skips_missing_file(tmp_path: Path) -> None:
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    decision = rot.rotate_if_needed(tmp_path / "absent.jsonl")
    assert decision.rotated is False
    assert decision.reason == "empty_or_missing"


def test_rotate_skips_empty_file(tmp_path: Path) -> None:
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    p = tmp_path / "x.jsonl"
    p.write_text("")
    decision = rot.rotate_if_needed(p)
    assert decision.rotated is False
    assert decision.reason == "empty_or_missing"


def test_rotate_skips_under_threshold(tmp_path: Path) -> None:
    rot = AuditRotator(
        size_mb_threshold=100, audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    decision = rot.rotate_if_needed(p)
    assert decision.rotated is False
    assert decision.reason == "under_threshold"


def test_rotate_force_midnight_rotates_small_file(tmp_path: Path) -> None:
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    decision = rot.rotate_if_needed(
        p, force_midnight=True,
        now=_dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc),
    )
    assert decision.rotated is True
    assert decision.forced_by_midnight is True
    assert decision.rotated_to is not None
    assert decision.rotated_to.name == "x.2026-04-28.1.jsonl"
    assert not p.exists()
    assert decision.rotated_to.exists()


def test_rotate_size_threshold_triggers_rotation(tmp_path: Path) -> None:
    rot = AuditRotator(
        size_mb_threshold=1,  # 1 MB threshold for ease of testing
        audit_log_path=tmp_path / "audit.jsonl",
    )
    p = tmp_path / "big.jsonl"
    # Manufacture a >1 MB file directly (chain content is irrelevant
    # for size triggering).
    p.write_text("x" * (1024 * 1024 + 1024), encoding="utf-8")
    decision = rot.rotate_if_needed(p)
    assert decision.rotated is True
    assert decision.forced_by_size is True


def test_rotate_invalidates_cache(tmp_path: Path) -> None:
    """After rotation the cache entry for the original path is gone."""
    from sylion.aeis_v2.audit_chain.chain import _LAST_HASH_CACHE, _cache_key

    reset_last_hash_cache()
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    assert _cache_key(p) in _LAST_HASH_CACHE
    rot.rotate_if_needed(p, force_midnight=True)
    assert _cache_key(p) not in _LAST_HASH_CACHE


def test_rotate_appends_after_rotation_start_new_chain(tmp_path: Path) -> None:
    """The original path is gone; new appends start fresh from genesis."""
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"i": 1})
    append_to_chain(p, {"i": 2})
    rot.rotate_if_needed(p, force_midnight=True)
    # New chain starts.
    append_to_chain(p, {"after": True})
    assert verify_chain(p) == []
    # Both chains independently verifiable.
    rotated = next(p.parent.glob("x.*.1.jsonl"))
    assert verify_chain(rotated) == []


def test_rotate_seq_increments_for_same_day(tmp_path: Path) -> None:
    """Two rotations on the same day produce .1 and .2 files."""
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    p = tmp_path / "x.jsonl"
    now = _dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc)
    append_to_chain(p, {"a": 1})
    rot.rotate_if_needed(p, force_midnight=True, now=now)
    append_to_chain(p, {"a": 2})
    rot.rotate_if_needed(p, force_midnight=True, now=now)
    assert (tmp_path / "x.2026-04-28.1.jsonl").exists()
    assert (tmp_path / "x.2026-04-28.2.jsonl").exists()


# ---------------------------------------------------------------------------
# evict_old
# ---------------------------------------------------------------------------


def test_evict_missing_dir_returns_empty(tmp_path: Path) -> None:
    rot = AuditRotator(audit_log_path=tmp_path / "audit.jsonl")
    rep = rot.evict_old(tmp_path / "nope")
    assert rep.deleted == [] and rep.kept == [] and rep.errors == []


def test_evict_keeps_recent_rotations(tmp_path: Path) -> None:
    rot = AuditRotator(retain_days=30, audit_log_path=tmp_path / "audit.jsonl")
    today = _dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc)
    recent = today - _dt.timedelta(days=10)
    name = f"x.{recent.strftime('%Y-%m-%d')}.1.jsonl"
    (tmp_path / name).write_text("x")
    rep = rot.evict_old(tmp_path, now=today)
    assert len(rep.kept) == 1
    assert rep.deleted == []


def test_evict_deletes_aged_rotations(tmp_path: Path) -> None:
    rot = AuditRotator(retain_days=30, audit_log_path=tmp_path / "audit.jsonl")
    today = _dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc)
    old = today - _dt.timedelta(days=100)
    name = f"x.{old.strftime('%Y-%m-%d')}.1.jsonl"
    (tmp_path / name).write_text("x")
    rep = rot.evict_old(tmp_path, now=today)
    assert len(rep.deleted) == 1
    assert rep.kept == []
    assert not (tmp_path / name).exists()


def test_evict_ignores_non_rotated_files(tmp_path: Path) -> None:
    """Original chain files (no date+seq pattern) must NEVER be deleted."""
    rot = AuditRotator(retain_days=1, audit_log_path=tmp_path / "audit.jsonl")
    (tmp_path / "x.jsonl").write_text("active chain")
    (tmp_path / "README.md").write_text("notes")
    rep = rot.evict_old(
        tmp_path, now=_dt.datetime(2030, 1, 1, tzinfo=_dt.timezone.utc),
    )
    assert (tmp_path / "x.jsonl").exists()
    assert (tmp_path / "README.md").exists()
    assert rep.deleted == []


def test_evict_handles_unparseable_date(tmp_path: Path) -> None:
    rot = AuditRotator(retain_days=1, audit_log_path=tmp_path / "audit.jsonl")
    (tmp_path / "x.not-a-date.1.jsonl").write_text("garbage name")
    rep = rot.evict_old(
        tmp_path, now=_dt.datetime(2030, 1, 1, tzinfo=_dt.timezone.utc),
    )
    # Doesn't match the regex — ignored entirely (not even reported as error).
    assert rep.deleted == [] and rep.errors == []


# ---------------------------------------------------------------------------
# run_daily — cron entrypoint
# ---------------------------------------------------------------------------


def test_run_daily_rotates_each_chain_and_evicts(tmp_path: Path) -> None:
    rot = AuditRotator(retain_days=30, audit_log_path=tmp_path / "audit.jsonl")
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    append_to_chain(a, {"x": 1})
    append_to_chain(b, {"x": 2})

    # Pre-existing aged rotation that should be evicted.
    today = _dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc)
    aged = today - _dt.timedelta(days=100)
    aged_name = f"a.{aged.strftime('%Y-%m-%d')}.1.jsonl"
    (tmp_path / aged_name).write_text("aged")

    summary = rot.run_daily([a, b], directory=tmp_path, now=today)
    assert summary["rotated_count"] == 2
    assert len(summary["rotations"]) == 2
    assert all(r["rotated"] for r in summary["rotations"])
    # Aged rotation evicted.
    assert any(
        Path(p).name == aged_name for p in summary["eviction"]["deleted"]
    )


def test_run_daily_audit_emission_is_chained(tmp_path: Path) -> None:
    """Rotator's own audit JSONL must verify as a chain."""
    audit = tmp_path / "audit_rotation.jsonl"
    rot = AuditRotator(audit_log_path=audit)
    a = tmp_path / "a.jsonl"
    append_to_chain(a, {"x": 1})
    rot.run_daily([a], directory=tmp_path,
                  now=_dt.datetime(2026, 4, 28, tzinfo=_dt.timezone.utc))
    assert verify_chain(audit) == []
    # And carries the canonical kinds.
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    kinds = {c.get("kind") for c in contents}
    assert "audit_rotation.rotate" in kinds
    assert "audit_rotation.evict" in kinds
    assert "audit_rotation.run_daily" in kinds


# ---------------------------------------------------------------------------
# Dataclass to_dict round-trips
# ---------------------------------------------------------------------------


def test_rotation_decision_to_dict_serialisable(tmp_path: Path) -> None:
    d = RotationDecision(
        path=tmp_path / "x.jsonl",
        rotated=True,
        reason="rotated",
        rotated_to=tmp_path / "x.2026-04-28.1.jsonl",
        size_mb=12.5,
        forced_by_size=False,
        forced_by_midnight=True,
    )
    payload = d.to_dict()
    json.dumps(payload)  # must not raise
    assert payload["rotated"] is True
    assert payload["size_mb"] == 12.5


def test_eviction_report_to_dict_serialisable(tmp_path: Path) -> None:
    rep = EvictionReport(
        deleted=[tmp_path / "a"], kept=[tmp_path / "b"], errors=["x"],
    )
    payload = rep.to_dict()
    json.dumps(payload)
    assert "a" in payload["deleted"][0]
