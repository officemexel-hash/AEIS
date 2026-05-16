"""Comprehensive tests for sylion.surface.command_bus module.

Covers: submit, approve, reject, get, list, pending-for-module,
        stats, edge cases, thread safety, event emission.
"""
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.surface.command_bus import CommandBus, Intent, get_command_bus
import sylion.surface.command_bus as mod


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    mod._bus = None
    yield
    mod._bus = None


@pytest.fixture
def bus():
    return CommandBus()


@pytest.fixture
def bus_with_events():
    eb = EventBus()
    cb = CommandBus(event_bus=eb)
    collected = []
    eb.subscribe("*", lambda e: collected.append(e))
    return cb, collected


# ---------------------------------------------------------------------------
# Intent dataclass
# ---------------------------------------------------------------------------

class TestIntentDataclass:
    def test_auto_id(self):
        i = Intent()
        assert len(i.intent_id) == 32

    def test_auto_timestamp(self):
        before = time.time()
        i = Intent()
        after = time.time()
        assert before <= i.created_at <= after

    def test_defaults(self):
        i = Intent()
        assert i.intent_type == "SUBMIT"
        assert i.status == "PENDING"
        assert i.phase == "TWO_PHASE"
        assert i.expected_version == 0
        assert i.payload == {}

    def test_custom_values(self):
        i = Intent(
            intent_type="UPDATE",
            target_module="security",
            target_action="rotate",
            payload={"key": "val"},
            expected_version=5,
            phase="IMMEDIATE",
            created_by="alice",
        )
        assert i.intent_type == "UPDATE"
        assert i.target_module == "security"
        assert i.payload == {"key": "val"}
        assert i.phase == "IMMEDIATE"


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

class TestSubmit:
    def test_basic_submit(self, bus):
        r = bus.submit_intent(
            target_module="security",
            target_action="rotate_keys",
            created_by="admin",
        )
        assert r["status"] == "PENDING"
        assert r["phase"] == "TWO_PHASE"
        assert len(r["intent_id"]) == 32

    def test_submit_with_payload(self, bus):
        r = bus.submit_intent(
            target_module="core",
            target_action="config_update",
            payload={"timeout": 30, "retries": 3},
            created_by="ops",
        )
        intent = bus.get_intent(r["intent_id"])
        assert intent["payload"] == {"timeout": 30, "retries": 3}

    def test_submit_immediate_phase(self, bus):
        r = bus.submit_intent(
            target_module="core",
            target_action="ping",
            phase="IMMEDIATE",
        )
        assert r["phase"] == "IMMEDIATE"

    def test_submit_default_phase_is_two_phase(self, bus):
        r = bus.submit_intent(target_module="x", target_action="y")
        assert r["phase"] == "TWO_PHASE"

    def test_submit_with_expected_version(self, bus):
        r = bus.submit_intent(
            target_module="core",
            target_action="update",
            expected_version=7,
        )
        intent = bus.get_intent(r["intent_id"])
        assert intent["expected_version"] == 7

    def test_submit_multiple(self, bus):
        ids = set()
        for i in range(5):
            r = bus.submit_intent(target_module="mod", target_action=f"act{i}")
            ids.add(r["intent_id"])
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# Approve / Reject
# ---------------------------------------------------------------------------

class TestApproveReject:
    def test_approve_pending(self, bus):
        r = bus.submit_intent(target_module="core", target_action="restart")
        result = bus.approve_intent(r["intent_id"], approver="council")
        assert result["status"] == "APPLIED"
        assert result["intent_id"] == r["intent_id"]

    def test_approve_sets_resolved_fields(self, bus):
        r = bus.submit_intent(target_module="core", target_action="restart")
        bus.approve_intent(r["intent_id"], approver="bob")
        intent = bus.get_intent(r["intent_id"])
        assert intent["status"] == "APPLIED"
        assert intent["resolved_by"] == "bob"
        assert intent["resolved_at"] > 0

    def test_reject_pending(self, bus):
        r = bus.submit_intent(target_module="core", target_action="delete")
        result = bus.reject_intent(
            r["intent_id"], reason="unsafe", rejector="guardian",
        )
        assert result["status"] == "REJECTED"

    def test_reject_sets_reason(self, bus):
        r = bus.submit_intent(target_module="core", target_action="nuke")
        bus.reject_intent(r["intent_id"], reason="too dangerous", rejector="admin")
        intent = bus.get_intent(r["intent_id"])
        assert intent["rejection_reason"] == "too dangerous"
        assert intent["resolved_by"] == "admin"

    def test_approve_nonexistent(self, bus):
        result = bus.approve_intent("nonexistent_id")
        assert result["error"] == "intent not found"

    def test_reject_nonexistent(self, bus):
        result = bus.reject_intent("nonexistent_id")
        assert result["error"] == "intent not found"

    def test_approve_already_approved(self, bus):
        r = bus.submit_intent(target_module="x", target_action="y")
        bus.approve_intent(r["intent_id"])
        result = bus.approve_intent(r["intent_id"])
        assert "error" in result
        assert "not pending" in result["error"].lower()

    def test_reject_already_approved(self, bus):
        r = bus.submit_intent(target_module="x", target_action="y")
        bus.approve_intent(r["intent_id"])
        result = bus.reject_intent(r["intent_id"])
        assert "error" in result

    def test_approve_already_rejected(self, bus):
        r = bus.submit_intent(target_module="x", target_action="y")
        bus.reject_intent(r["intent_id"])
        result = bus.approve_intent(r["intent_id"])
        assert "error" in result


# ---------------------------------------------------------------------------
# Get / List / Pending
# ---------------------------------------------------------------------------

class TestQuery:
    def test_get_intent_found(self, bus):
        r = bus.submit_intent(
            target_module="m", target_action="a",
            payload={"k": "v"}, created_by="dev",
        )
        intent = bus.get_intent(r["intent_id"])
        assert intent is not None
        assert intent["intent_id"] == r["intent_id"]
        assert intent["payload"] == {"k": "v"}
        assert intent["created_by"] == "dev"

    def test_get_intent_not_found(self, bus):
        assert bus.get_intent("missing") is None

    def test_list_all_intents(self, bus):
        bus.submit_intent(target_module="a", target_action="x")
        bus.submit_intent(target_module="b", target_action="y")
        assert len(bus.list_intents()) == 2

    def test_list_by_status(self, bus):
        r1 = bus.submit_intent(target_module="a", target_action="x")
        bus.submit_intent(target_module="b", target_action="y")
        bus.approve_intent(r1["intent_id"])
        pending = bus.list_intents(status="PENDING")
        assert len(pending) == 1
        applied = bus.list_intents(status="APPLIED")
        assert len(applied) == 1

    def test_list_respects_limit(self, bus):
        for i in range(10):
            bus.submit_intent(target_module="m", target_action=f"a{i}")
        assert len(bus.list_intents(limit=3)) == 3

    def test_get_pending_for_module(self, bus):
        bus.submit_intent(target_module="target_mod", target_action="a1")
        bus.submit_intent(target_module="target_mod", target_action="a2")
        bus.submit_intent(target_module="other_mod", target_action="a3")
        pending = bus.get_pending_for_module("target_mod")
        assert len(pending) == 2
        assert all(p["target_module"] == "target_mod" for p in pending)

    def test_get_pending_excludes_resolved(self, bus):
        r = bus.submit_intent(target_module="mod", target_action="a")
        bus.submit_intent(target_module="mod", target_action="b")
        bus.approve_intent(r["intent_id"])
        pending = bus.get_pending_for_module("mod")
        assert len(pending) == 1

    def test_get_pending_for_empty_module(self, bus):
        pending = bus.get_pending_for_module("nonexistent")
        assert pending == []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_empty_stats(self, bus):
        stats = bus.get_stats()
        assert stats["total_intents"] == 0
        assert stats["by_status"] == {}
        assert stats["by_phase"] == {}

    def test_stats_with_data(self, bus):
        bus.submit_intent(target_module="x", target_action="y", phase="TWO_PHASE")
        bus.submit_intent(target_module="x", target_action="z", phase="IMMEDIATE")
        stats = bus.get_stats()
        assert stats["total_intents"] == 2
        assert stats["by_status"]["PENDING"] == 2
        assert stats["by_phase"]["TWO_PHASE"] == 1
        assert stats["by_phase"]["IMMEDIATE"] == 1

    def test_stats_after_approve_reject(self, bus):
        r1 = bus.submit_intent(target_module="x", target_action="y")
        r2 = bus.submit_intent(target_module="x", target_action="z")
        bus.submit_intent(target_module="x", target_action="w")
        bus.approve_intent(r1["intent_id"])
        bus.reject_intent(r2["intent_id"])
        stats = bus.get_stats()
        assert stats["by_status"]["APPLIED"] == 1
        assert stats["by_status"]["REJECTED"] == 1
        assert stats["by_status"]["PENDING"] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:
    def test_submit_emits_event(self, bus_with_events):
        bus, events = bus_with_events
        bus.submit_intent(target_module="m", target_action="a")
        assert any("intent_submitted" in e.topic for e in events)

    def test_approve_emits_event(self, bus_with_events):
        bus, events = bus_with_events
        r = bus.submit_intent(target_module="m", target_action="a")
        bus.approve_intent(r["intent_id"], approver="bob")
        topics = [e.topic for e in events]
        assert "surface.command_bus.intent_approved" in topics

    def test_reject_emits_event(self, bus_with_events):
        bus, events = bus_with_events
        r = bus.submit_intent(target_module="m", target_action="a")
        bus.reject_intent(r["intent_id"])
        topics = [e.topic for e in events]
        assert "surface.command_bus.intent_rejected" in topics

    def test_no_event_bus_no_crash(self, bus):
        # bus fixture has no event_bus -- should not raise
        bus.submit_intent(target_module="m", target_action="a")
        bus.approve_intent(bus.list_intents()[0]["intent_id"])


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestFactory:
    def test_get_command_bus_returns_same(self):
        b1 = get_command_bus()
        b2 = get_command_bus()
        assert b1 is b2

    def test_get_command_bus_with_custom_db(self):
        b = get_command_bus(db_path=":memory:")
        assert isinstance(b, CommandBus)


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_submits(self, bus):
        errors = []

        def submit(idx):
            try:
                bus.submit_intent(
                    target_module="mod",
                    target_action=f"action_{idx}",
                    created_by=f"thread_{idx}",
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert bus.get_stats()["total_intents"] == 20

    def test_concurrent_approve(self, bus):
        results = []
        r = bus.submit_intent(target_module="m", target_action="a")
        barrier = threading.Barrier(3)

        def try_approve():
            barrier.wait()
            results.append(bus.approve_intent(r["intent_id"], approver="t"))

        threads = [threading.Thread(target=try_approve) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [x for x in results if "error" not in x]
        errors = [x for x in results if "error" in x]
        assert len(successes) == 1
        assert len(errors) == 2


# ---------------------------------------------------------------------------
# Intent events log
# ---------------------------------------------------------------------------

class TestIntentEventsLog:
    def test_submit_creates_event_record(self, bus):
        r = bus.submit_intent(target_module="m", target_action="a")
        intent = bus.get_intent(r["intent_id"])
        # The internal events table should have a record
        row = bus._conn.execute(
            "SELECT COUNT(*) as cnt FROM intent_events WHERE intent_id = ?",
            (r["intent_id"],),
        ).fetchone()
        assert row["cnt"] >= 1

    def test_approve_appends_event(self, bus):
        r = bus.submit_intent(target_module="m", target_action="a")
        bus.approve_intent(r["intent_id"])
        row = bus._conn.execute(
            "SELECT COUNT(*) as cnt FROM intent_events WHERE intent_id = ? AND event_type = 'INTENT_APPROVED'",
            (r["intent_id"],),
        ).fetchone()
        assert row["cnt"] == 1
