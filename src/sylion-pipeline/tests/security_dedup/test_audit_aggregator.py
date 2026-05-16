"""
Tests for security dedup K4.1 — AuditTrailAggregator canonical + shim forwards.
"""

from __future__ import annotations

import time

import pytest

from sylion.security.audit_trail_aggregator import (
    AuditTrailAggregator,
    get_audit_trail_aggregator,
    reset_audit_trail_aggregator,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_audit_trail_aggregator()
    yield
    reset_audit_trail_aggregator()


class TestCanonicalAggregator:
    def test_record_and_get_entry(self):
        agg = AuditTrailAggregator(":memory:")
        r = agg.record("api", "login", actor="alice", resource="/auth")
        assert r is not None
        assert r["entry_id"]
        assert agg.get_entry(r["entry_id"])["action"] == "login"

    def test_dedup_by_entry_id(self):
        agg = AuditTrailAggregator(":memory:")
        r1 = agg.record("api", "login", actor="alice", entry_id="evt-001")
        r2 = agg.record("api", "logout", actor="bob", entry_id="evt-001")
        assert r1 is not None
        assert r2 is None  # dedup
        assert agg.get_entry("evt-001")["action"] == "login"

    def test_replace_by_entry_id(self):
        agg = AuditTrailAggregator(":memory:")
        r1 = agg.record("api", "login", actor="alice", entry_id="evt-001")
        r2 = agg.record("api", "logout", actor="bob", entry_id="evt-001", replace=True)
        assert r1 is not None
        assert r2 is not None
        assert agg.get_entry("evt-001")["action"] == "logout"

    def test_custom_timestamp(self):
        agg = AuditTrailAggregator(":memory:")
        ts = time.time() - 3600
        r = agg.record("api", "login", timestamp=ts)
        assert abs(r["timestamp"] - ts) < 0.001

    def test_query_filters(self):
        agg = AuditTrailAggregator(":memory:")
        agg.record("api", "login", actor="alice", resource="/auth")
        agg.record("api", "logout", actor="bob", resource="/auth")
        agg.record("security", "alert", actor="alice", resource="/data")
        assert len(agg.query()) == 3
        assert len(agg.query(actor="alice")) == 2
        assert len(agg.query(source="security")) == 1
        assert len(agg.query(resource="/auth")) == 2

    def test_get_actor_history(self):
        agg = AuditTrailAggregator(":memory:")
        agg.record("api", "login", actor="alice")
        agg.record("api", "logout", actor="alice")
        hist = agg.get_actor_history("alice")
        assert len(hist) == 2

    def test_get_resource_timeline(self):
        agg = AuditTrailAggregator(":memory:")
        agg.record("api", "read", resource="/file1")
        agg.record("api", "write", resource="/file1")
        tl = agg.get_resource_timeline("/file1")
        assert len(tl) == 2

    def test_verify_integrity(self):
        agg = AuditTrailAggregator(":memory:")
        agg.record("api", "login")
        agg.record("api", "logout")
        result = agg.verify_integrity()
        assert result["valid"] is True
        assert result["total_entries"] == 2

    def test_stats(self):
        agg = AuditTrailAggregator(":memory:")
        agg.record("api", "login")
        agg.record("api", "logout")
        agg.record("security", "alert")
        stats = agg.get_stats()
        assert stats["total_entries"] == 3
        assert stats["by_source"]["api"] == 2
        assert stats["by_action"]["login"] == 1


class TestShimForwards:
    def test_audit_query_shim_delegates(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from sylion.security.audit_query import AuditQuery

        aq = AuditQuery(":memory:")
        aq.index_event("e1", "login", "alice", "/auth", time.time())
        assert aq.get_event("e1") is not None
        assert aq.get_event("e1")["event_type"] == "login"
        assert len(aq.query_events({"actor": "alice"})) == 1

    def test_hardened_audit_shim_still_functional(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from sylion.security.hardened_audit import HardenedAuditLogger

        hal = HardenedAuditLogger(":memory:")
        entry = hal.log_event("auth", "alice", "login")
        assert entry["log_id"]
        assert entry["entry_hash"]
        assert hal.verify_chain()["valid"] is True

    def test_audit_sink_shim_still_functional(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from sylion.security.audit_sink import AuditSink

        sink = AuditSink(":memory:")
        sub = sink.create_subscription("sub1", "audit.*", "webhook", {"url": "http://x"})
        assert sub["sub_id"]
        assert len(sink.list_subscriptions()) == 1

    def test_security_audit_shim_still_functional(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from sylion.security.security_audit import SecurityAuditor

        sa = SecurityAuditor(":memory:")
        finding = sa.create_finding("XSS", "high", "Reflected XSS")
        assert finding["finding_id"]
        assert sa.get_finding(finding["finding_id"])["title"] == "XSS"
