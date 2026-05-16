"""Tests for ``sylion.aeis_v2.gdpr_v2.hard_purge`` — GDPR Article 17 cron.

Verifies the deferred companion to commit bc68430f. The cron walks
soft-deleted rows, physically purges those past the grace window, and
emits a tamper-evident chained audit JSONL via ``append_to_chain``.
"""
from __future__ import annotations

from pathlib import Path
import json
import time

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.gdpr_v2 import (
    DEFAULT_GRACE_PERIOD_S,
    DsrService,
    HardPurgeCron,
    PurgeReport,
    PurgeableInMemoryStore,
)


# ---------------------------------------------------------------------------
# DEFAULT_GRACE_PERIOD_S
# ---------------------------------------------------------------------------


def test_default_grace_period_is_30_days() -> None:
    assert DEFAULT_GRACE_PERIOD_S == 30 * 24 * 3600


# ---------------------------------------------------------------------------
# PurgeableInMemoryStore wrapper
# ---------------------------------------------------------------------------


def test_purgeable_store_lists_only_soft_deleted() -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-alive", {})
    s.upsert("u-erased", {})
    s.soft_delete("u-erased", ts=100.0)
    rows = list(s.list_with_deleted_at())
    assert rows == [("u-erased", 100.0)]


def test_purgeable_store_hard_purge_removes_row() -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-1", {})
    s.soft_delete("u-1", ts=100.0)
    assert s.hard_purge("u-1") is True
    assert "u-1" not in s._rows  # noqa: SLF001 — internal state assertion


def test_purgeable_store_hard_purge_refuses_alive_user() -> None:
    """hard_purge must only apply to soft-deleted rows — defensive guard."""
    s = PurgeableInMemoryStore()
    s.upsert("u-1", {})
    assert s.hard_purge("u-1") is False
    # Row still there.
    assert s.get("u-1") is not None


def test_purgeable_store_hard_purge_missing_returns_false() -> None:
    s = PurgeableInMemoryStore()
    assert s.hard_purge("absent") is False


# ---------------------------------------------------------------------------
# PurgeReport
# ---------------------------------------------------------------------------


def test_purge_report_duration_non_negative() -> None:
    r = PurgeReport(
        started_at=10.0, finished_at=15.0, candidates=0,
        purged=[], skipped=[], errors=[],
    )
    assert r.duration_s == 5.0


def test_purge_report_duration_clamps_negative_to_zero() -> None:
    """Out-of-order start/finish (clock skew) clamps to 0 — never negative."""
    r = PurgeReport(
        started_at=20.0, finished_at=15.0, candidates=0,
        purged=[], skipped=[], errors=[],
    )
    assert r.duration_s == 0.0


def test_purge_report_to_dict_serialisable() -> None:
    r = PurgeReport(
        started_at=10.0, finished_at=15.0, candidates=2,
        purged=["a"], skipped=["b"], errors=[],
    )
    d = r.to_dict()
    json.dumps(d)  # must round-trip
    assert d["candidates"] == 2
    assert d["purged"] == ["a"]


# ---------------------------------------------------------------------------
# HardPurgeCron — happy path
# ---------------------------------------------------------------------------


def test_purge_expired_purges_old_rows(tmp_path: Path) -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-old", {})
    s.upsert("u-fresh", {})
    s.soft_delete("u-old", ts=0.0)
    s.soft_delete("u-fresh", ts=time.time())

    cron = HardPurgeCron(
        s,
        audit_log_path=tmp_path / "purge.jsonl",
        grace_period_s=10,
    )
    report = cron.purge_expired(now=100.0)
    assert "u-old" in report.purged
    assert "u-fresh" in report.skipped
    assert report.candidates == 2


def test_purge_expired_no_candidates_zero_purged(tmp_path: Path) -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-1", {})  # alive — not soft-deleted
    cron = HardPurgeCron(
        s,
        audit_log_path=tmp_path / "purge.jsonl",
        grace_period_s=10,
    )
    report = cron.purge_expired(now=time.time())
    assert report.candidates == 0
    assert report.purged == []
    assert report.skipped == []


def test_purge_expired_emits_chained_audit_run_row(tmp_path: Path) -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-old", {})
    s.soft_delete("u-old", ts=0.0)
    audit = tmp_path / "purge.jsonl"
    cron = HardPurgeCron(s, audit_log_path=audit, grace_period_s=10)
    cron.purge_expired(now=100.0)

    assert audit.exists()
    # Chain must verify cleanly.
    assert verify_chain(audit) == []
    # And contain at least the per-row + the run summary kinds.
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    kinds = {c.get("kind") for c in contents}
    assert "gdpr.hard_purge.row" in kinds
    assert "gdpr.hard_purge.run" in kinds


def test_purge_expired_skipped_row_logged(tmp_path: Path) -> None:
    s = PurgeableInMemoryStore()
    s.upsert("u-fresh", {})
    s.soft_delete("u-fresh", ts=99.0)  # still inside grace window
    audit = tmp_path / "purge.jsonl"
    cron = HardPurgeCron(s, audit_log_path=audit, grace_period_s=100)
    cron.purge_expired(now=100.0)
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    skipped_rows = [
        c for c in contents
        if c.get("kind") == "gdpr.hard_purge.row" and c.get("outcome") == "skipped"
    ]
    assert len(skipped_rows) == 1
    assert skipped_rows[0]["user_id"] == "u-fresh"


# ---------------------------------------------------------------------------
# HardPurgeCron — error path
# ---------------------------------------------------------------------------


class _ExplodingStore(PurgeableInMemoryStore):
    """Store whose ``hard_purge`` always raises — error-path coverage."""

    def hard_purge(self, user_id: str) -> bool:  # type: ignore[override]
        raise RuntimeError("boom")


def test_purge_expired_records_errors(tmp_path: Path) -> None:
    s = _ExplodingStore()
    s.upsert("u-1", {})
    s.soft_delete("u-1", ts=0.0)
    cron = HardPurgeCron(
        s,
        audit_log_path=tmp_path / "purge.jsonl",
        grace_period_s=10,
    )
    report = cron.purge_expired(now=100.0)
    assert report.errors == ["u-1"]
    assert report.purged == []


def test_purge_expired_short_grace_warns(tmp_path: Path, caplog) -> None:
    """Configurations under 24h emit a warning log."""
    import logging
    caplog.set_level(logging.WARNING, logger="sylion.aeis_v2.gdpr_v2.hard_purge")
    HardPurgeCron(
        PurgeableInMemoryStore(),
        audit_log_path=tmp_path / "p.jsonl",
        grace_period_s=60,
    )
    assert any("grace_period_s=60" in rec.getMessage() for rec in caplog.records)


# ---------------------------------------------------------------------------
# Integration with DsrService — soft-delete then purge.
# ---------------------------------------------------------------------------


def test_dsr_then_purge_end_to_end(tmp_path: Path) -> None:
    """Full GDPR flow: erase via DSR, run cron, user is gone."""
    s = PurgeableInMemoryStore()
    s.upsert("u-1", {"name": "Robert"})
    svc = DsrService(store=s, audit_log_path=tmp_path / "dsr.jsonl")
    cron = HardPurgeCron(
        s,
        audit_log_path=tmp_path / "purge.jsonl",
        grace_period_s=10,
    )

    # Step 1 — DSR ERASURE flips the soft-delete flag.
    erase = svc.erase("u-1", actor="owner")
    assert erase.success is True
    soft_ts = erase.payload["soft_delete_ts"]

    # Step 2 — cron runs after the grace window.
    report = cron.purge_expired(now=soft_ts + 100)
    assert "u-1" in report.purged

    # Step 3 — subsequent ACCESS confirms the row is gone (404 semantics).
    assert svc.access("u-1").success is False


def test_purge_expired_returns_purge_report_type(tmp_path: Path) -> None:
    cron = HardPurgeCron(
        PurgeableInMemoryStore(),
        audit_log_path=tmp_path / "p.jsonl",
        grace_period_s=10,
    )
    out = cron.purge_expired(now=time.time())
    assert isinstance(out, PurgeReport)


def test_purge_expired_audit_chain_integrity_preserved(tmp_path: Path) -> None:
    """Multiple cron runs across days produce a single verifiable chain."""
    s = PurgeableInMemoryStore()
    audit = tmp_path / "p.jsonl"
    cron = HardPurgeCron(s, audit_log_path=audit, grace_period_s=10)

    s.upsert("u-1", {})
    s.soft_delete("u-1", ts=0.0)
    cron.purge_expired(now=100.0)

    s.upsert("u-2", {})
    s.soft_delete("u-2", ts=200.0)
    cron.purge_expired(now=400.0)

    assert verify_chain(audit) == []
