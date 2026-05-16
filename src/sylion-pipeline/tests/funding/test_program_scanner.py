"""
Tests for funding_autopilot.program_scanner (FIX-100).
"""

from __future__ import annotations

import datetime as dt
import time

import pytest

from sylion.funding_autopilot.program_scanner import (
    FundingCall,
    compute_match_scores,
    scan_all,
    scan_feng,
    scan_horizon_europe,
    scan_ncbr,
    scan_regional,
)
from sylion.funding_autopilot.store import FundingAutopilotStore


@pytest.fixture
def memory_store():
    store = FundingAutopilotStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def scanner_now(monkeypatch):
    now = dt.datetime(2026, 4, 30, tzinfo=dt.timezone.utc).timestamp()
    monkeypatch.setattr("sylion.funding_autopilot.program_scanner.time.time", lambda: now)
    return now


class TestIndividualScanners:
    def test_horizon_europe_returns_calls(self):
        calls = scan_horizon_europe()
        assert len(calls) >= 2
        assert all(c.programme_id == "programme_horizon_europe" for c in calls)
        assert any("HORIZON" in c.title for c in calls)

    def test_ncbr_returns_calls(self):
        calls = scan_ncbr()
        assert calls == []

    def test_feng_returns_calls(self):
        calls = scan_feng()
        assert len(calls) >= 2
        assert all(c.programme_id == "programme_feng" for c in calls)
        assert any(c.country == "PL" for c in calls)
        assert any("PARP" in c.code or "FENG" in c.code for c in calls)

    def test_regional_returns_calls(self):
        calls = scan_regional()
        assert len(calls) >= 2
        assert {c.programme_id for c in calls} <= {"programme_digital_europe", "programme_eu_tenders"}


class TestScanAll:
    def test_scan_all_persists(self, memory_store, scanner_now):
        calls = scan_all(store=memory_store)
        assert len(calls) >= 2
        assert all(c.closes_at is None or c.closes_at >= scanner_now for c in calls)
        stored = memory_store.list_calls()
        assert len(stored) == len(calls)
        assert all(c.get("closes_at") is None or c["closes_at"] >= scanner_now for c in stored)

    def test_scan_all_dedup(self, memory_store, scanner_now):
        c1 = scan_all(store=memory_store)
        c2 = scan_all(store=memory_store)
        assert len(c1) == len(c2)
        stored = memory_store.list_calls()
        # Should not duplicate on second run
        assert len(stored) == len(c1)
        assert all(c.get("closes_at") is None or c["closes_at"] >= scanner_now for c in stored)

    def test_scan_all_force_refresh(self, memory_store, scanner_now):
        c1 = scan_all(store=memory_store)
        c2 = scan_all(store=memory_store, force_refresh=True)
        assert len(c1) == len(c2)
        stored = memory_store.list_calls()
        assert len(stored) == len(c1)
        assert all(c.get("closes_at") is None or c["closes_at"] >= scanner_now for c in stored)

    def test_scan_all_removes_stale_stored_calls(self, memory_store, scanner_now):
        scan_all(store=memory_store)
        memory_store.create_call(
            FundingCall(
                programme_id="programme_feng",
                title="Closed guard fixture",
                code="CLOSED-2026-03",
                country="PL",
                portal_url="https://feng.parp.gov.pl/component/grants/grants/sciezka-smart",
                opens_at=scanner_now - 86400 * 60,
                closes_at=scanner_now - 86400,
            ).to_store_payload()
        )
        scan_all(store=memory_store)
        stored_codes = {row.get("code") for row in memory_store.list_calls()}
        assert "CLOSED-2026-03" not in stored_codes


class TestMatchScoring:
    def test_match_scores_returned(self, memory_store, scanner_now):
        scan_all(store=memory_store)
        memory_store.upsert_company_profile(
            "default",
            {
                "description": "We build AI and cloud software for European clients",
                "sectors": ["software", "AI"],
                "keywords": ["machine learning", "digital twins"],
            },
        )
        results = compute_match_scores("default", store=memory_store)
        assert len(results) >= 2
        for r in results:
            assert "match_score" in r
            assert 0.0 <= r["match_score"] <= 1.0
            assert r.get("closes_at") is None or r["closes_at"] >= scanner_now

    def test_match_scores_sorted_desc(self, memory_store):
        scan_all(store=memory_store)
        memory_store.upsert_company_profile(
            "default",
            {
                "description": "AI cybersecurity quantum",
                "sectors": ["security"],
                "keywords": ["cyber"],
            },
        )
        results = compute_match_scores("default", store=memory_store)
        scores = [r["match_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_no_profile_returns_zero_scores(self, memory_store, scanner_now):
        scan_all(store=memory_store)
        results = compute_match_scores("missing", store=memory_store)
        assert all(r["match_score"] == 0.0 for r in results)
        assert all(r.get("closes_at") is None or r["closes_at"] >= scanner_now for r in results)
