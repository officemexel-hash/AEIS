"""
Tests for sylion.security.hardened_audit -- HardenedAuditLogger

Covers log_event, hash chain integrity, chain verification,
tamper detection, querying, exporting, EventBus integration,
singleton, and concurrency.
"""

import threading
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.security.hardened_audit import (
    GENESIS_HASH,
    VALID_SEVERITIES,
    HardenedAuditLogger,
    get_hardened_audit,
    reset_hardened_audit,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger(event_bus: EventBus | None = None) -> HardenedAuditLogger:
    return HardenedAuditLogger(db_path=":memory:", event_bus=event_bus)


def _make_event(logger: HardenedAuditLogger, event_type: str = "test",
                actor: str = "tester", action: str = "do_something",
                severity: str = "info") -> dict:
    return logger.log_event(event_type, actor, action, severity=severity)


# ===========================================================================
# 1. Constants
# ===========================================================================


class TestConstants:
    def test_genesis_hash(self):
        assert GENESIS_HASH == "0" * 64
        assert len(GENESIS_HASH) == 64

    def test_valid_severities(self):
        assert "debug" in VALID_SEVERITIES
        assert "info" in VALID_SEVERITIES
        assert "warning" in VALID_SEVERITIES
        assert "error" in VALID_SEVERITIES
        assert "critical" in VALID_SEVERITIES


# ===========================================================================
# 2. Logging events
# ===========================================================================


class TestLogEvent:
    def test_basic_log(self):
        logger = _make_logger()
        ev = logger.log_event("login", "alice", "user_login")
        assert ev["log_id"] != ""
        assert ev["event_type"] == "login"
        assert ev["actor"] == "alice"
        assert ev["action"] == "user_login"
        assert ev["severity"] == "info"
        assert ev["timestamp"] > 0
        assert ev["prev_hash"] == GENESIS_HASH
        assert ev["entry_hash"] != ""

    def test_with_resource(self):
        logger = _make_logger()
        ev = logger.log_event("api", "bob", "api_call", resource="/health")
        assert ev["resource"] == "/health"

    def test_with_details_dict(self):
        logger = _make_logger()
        ev = logger.log_event("config", "admin", "config_change",
                              details_json={"key": "max_workers", "value": 10})
        assert '"key"' in ev["details"]

    def test_with_details_string(self):
        logger = _make_logger()
        ev = logger.log_event("test", "tester", "test", details_json='{"raw": true}')
        assert '"raw"' in ev["details"]

    def test_with_severity(self):
        logger = _make_logger()
        ev = logger.log_event("error", "system", "crash", severity="critical")
        assert ev["severity"] == "critical"

    def test_rejects_invalid_severity(self):
        logger = _make_logger()
        with pytest.raises(ValueError, match="Invalid severity"):
            logger.log_event("test", "tester", "test", severity="nuclear")

    def test_all_valid_severities(self):
        logger = _make_logger()
        for sev in VALID_SEVERITIES:
            ev = logger.log_event("test", "tester", "test", severity=sev)
            assert ev["severity"] == sev

    def test_chain_linkage(self):
        logger = _make_logger()
        ev1 = logger.log_event("type1", "alice", "action1")
        ev2 = logger.log_event("type2", "bob", "action2")
        assert ev2["prev_hash"] == ev1["entry_hash"]

    def test_entry_hash_deterministic(self):
        logger = _make_logger()
        ev = logger.log_event("t", "a", "act", resource="/r")
        # Recompute the hash manually
        raw = f"{ev['log_id']}|t|a|act|/r|{ev['timestamp']}|{ev['prev_hash']}"
        import hashlib
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        assert ev["entry_hash"] == expected


# ===========================================================================
# 3. Chain verification
# ===========================================================================


class TestVerifyChain:
    def test_valid_chain(self):
        logger = _make_logger()
        logger.log_event("t1", "a1", "act1")
        logger.log_event("t2", "a2", "act2")
        result = logger.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 2
        assert result["broken_at"] == []
        assert result["errors"] == []

    def test_empty_chain_is_valid(self):
        logger = _make_logger()
        result = logger.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 0

    def test_detects_tampered_entry_hash(self):
        logger = _make_logger()
        ev = logger.log_event("t1", "a1", "act1")
        logger.log_event("t2", "a2", "act2")
        logger._conn.execute(
            "UPDATE hardened_audit_log SET entry_hash = 'tampered' WHERE log_id = ?",
            (ev["log_id"],),
        )
        logger._conn.commit()
        result = logger.verify_chain()
        assert result["valid"] is False
        assert len(result["broken_at"]) > 0

    def test_detects_prev_hash_mismatch(self):
        logger = _make_logger()
        ev1 = logger.log_event("t1", "a1", "act1")
        logger.log_event("t2", "a2", "act2")
        logger._conn.execute(
            "UPDATE hardened_audit_log SET prev_hash = 'badhash' WHERE log_id != ?",
            (ev1["log_id"],),
        )
        logger._conn.commit()
        result = logger.verify_chain()
        assert result["valid"] is False

    def test_single_entry_valid(self):
        logger = _make_logger()
        logger.log_event("t", "a", "act")
        result = logger.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 1


# ===========================================================================
# 4. Tamper check
# ===========================================================================


class TestTamperCheck:
    def test_clean_chain(self):
        logger = _make_logger()
        logger.log_event("t1", "a1", "act1")
        result = logger.tamper_check()
        assert result["valid"] is True

    def test_tampered_chain(self):
        logger = _make_logger()
        ev = logger.log_event("t1", "a1", "act1")
        logger._conn.execute(
            "UPDATE hardened_audit_log SET actor = 'hacker' WHERE log_id = ?",
            (ev["log_id"],),
        )
        logger._conn.commit()
        result = logger.tamper_check()
        assert result["valid"] is False


# ===========================================================================
# 5. Chain operations
# ===========================================================================


class TestGetChain:
    def test_get_nonexistent_chain(self):
        logger = _make_logger()
        result = logger.get_chain("nope")
        assert result is None


# ===========================================================================
# 6. Querying
# ===========================================================================


class TestGetEvents:
    def test_list_all(self):
        logger = _make_logger()
        logger.log_event("t1", "alice", "act1")
        logger.log_event("t2", "bob", "act2")
        events = logger.get_events()
        assert len(events) == 2

    def test_filter_by_event_type(self):
        logger = _make_logger()
        logger.log_event("login", "alice", "login")
        logger.log_event("logout", "alice", "logout")
        events = logger.get_events(event_type="login")
        assert len(events) == 1
        assert events[0]["event_type"] == "login"

    def test_filter_by_actor(self):
        logger = _make_logger()
        logger.log_event("t1", "alice", "act1")
        logger.log_event("t2", "bob", "act2")
        events = logger.get_events(actor="alice")
        assert len(events) == 1
        assert events[0]["actor"] == "alice"

    def test_filter_by_both(self):
        logger = _make_logger()
        logger.log_event("login", "alice", "login")
        logger.log_event("login", "bob", "login")
        events = logger.get_events(event_type="login", actor="alice")
        assert len(events) == 1

    def test_limit(self):
        logger = _make_logger()
        for i in range(10):
            logger.log_event("t", f"a{i}", "act")
        events = logger.get_events(limit=5)
        assert len(events) == 5

    def test_details_parsed(self):
        logger = _make_logger()
        logger.log_event("t", "a", "act", details_json={"key": "val"})
        events = logger.get_events()
        assert events[0]["details"] == {"key": "val"}

    def test_empty(self):
        logger = _make_logger()
        assert logger.get_events() == []


# ===========================================================================
# 7. Export
# ===========================================================================


class TestExportEvents:
    def test_export_all(self):
        logger = _make_logger()
        logger.log_event("t1", "a1", "act1")
        logger.log_event("t2", "a2", "act2")
        exported = logger.export_events()
        assert len(exported) == 2
        assert exported[0]["timestamp"] <= exported[1]["timestamp"]

    def test_export_since(self):
        logger = _make_logger()
        ev1 = logger.log_event("t1", "a1", "act1")
        time.sleep(0.01)
        ev2 = logger.log_event("t2", "a2", "act2")
        exported = logger.export_events(since=ev2["timestamp"] - 0.001)
        assert len(exported) >= 1

    def test_export_empty(self):
        logger = _make_logger()
        assert logger.export_events() == []

    def test_export_details_parsed(self):
        logger = _make_logger()
        logger.log_event("t", "a", "act", details_json={"x": 1})
        exported = logger.export_events()
        assert exported[0]["details"] == {"x": 1}


# ===========================================================================
# 8. EventBus integration
# ===========================================================================


class TestEventBusIntegration:
    def test_audit_logged_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("audit_logged", lambda e: collected.append(e))
        logger = _make_logger(event_bus=bus)
        logger.log_event("t", "a", "act")
        assert len(collected) == 1
        assert "log_id" in collected[0].payload

    def test_chain_verified_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("chain_verified", lambda e: collected.append(e))
        logger = _make_logger(event_bus=bus)
        logger.log_event("t", "a", "act")
        logger.verify_chain()
        assert len(collected) == 1

    def test_tamper_detected_event(self):
        bus = EventBus(db_path=":memory:")
        collected = []
        bus.subscribe("tamper_detected", lambda e: collected.append(e))
        logger = _make_logger(event_bus=bus)
        ev = logger.log_event("t", "a", "act")
        logger._conn.execute(
            "UPDATE hardened_audit_log SET entry_hash = 'bad' WHERE log_id = ?",
            (ev["log_id"],),
        )
        logger._conn.commit()
        logger.verify_chain()
        assert len(collected) == 1

    def test_no_event_without_bus(self):
        logger = _make_logger(event_bus=None)
        logger.log_event("t", "a", "act")
        # Should not raise


# ===========================================================================
# 9. Singleton
# ===========================================================================


class TestSingleton:
    def test_get_hardened_audit(self):
        import sylion.security.hardened_audit as mod
        mod._logger = None
        l = get_hardened_audit(db_path=":memory:")
        assert isinstance(l, HardenedAuditLogger)
        mod._logger = None

    def test_reset_hardened_audit(self):
        import sylion.security.hardened_audit as mod
        mod._logger = None
        l1 = get_hardened_audit(db_path=":memory:")
        l2 = reset_hardened_audit(db_path=":memory:")
        assert l2 is not l1
        mod._logger = None

    def test_get_returns_same_instance(self):
        import sylion.security.hardened_audit as mod
        mod._logger = None
        l1 = get_hardened_audit(db_path=":memory:")
        l2 = get_hardened_audit()
        assert l1 is l2
        mod._logger = None


# ===========================================================================
# 10. Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_logging(self):
        logger = _make_logger()
        results = []
        errors = []

        def log_event(i):
            try:
                ev = logger.log_event("concurrent", f"actor_{i}", f"action_{i}")
                results.append(ev["log_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_event, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_verify(self):
        logger = _make_logger()
        for i in range(5):
            logger.log_event("t", "a", "act")

        results = []
        errors = []

        def verify():
            try:
                r = logger.verify_chain()
                results.append(r["valid"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=verify) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert all(results)
