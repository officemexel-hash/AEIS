"""Tests for sylion.rebuild.lpw_manager -- LPWManager."""

import pytest

from sylion.rebuild.lpw_manager import LPWManager, LPWVersion, LPWSnapshot


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mgr():
    return LPWManager(db_path=":memory:")


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TestLPWVersion:
    def test_auto_timestamp(self):
        v = LPWVersion(module_id="mod-1", version="1.0")
        assert v.recorded_at > 0

    def test_default_status(self):
        v = LPWVersion(module_id="mod-1", version="1.0")
        assert v.status == "stable"


class TestLPWSnapshot:
    def test_auto_snapshot_id(self):
        s = LPWSnapshot(module_id="mod-1", version="1.0")
        assert len(s.snapshot_id) > 0

    def test_auto_timestamp(self):
        s = LPWSnapshot(module_id="mod-1", version="1.0")
        assert s.created_at > 0


# ---------------------------------------------------------------------------
# record()
# ---------------------------------------------------------------------------

class TestRecord:
    def test_record_returns_dict(self, mgr):
        r = mgr.record("mod-1", "1.0.0")
        assert r["module_id"] == "mod-1"
        assert r["version"] == "1.0.0"
        assert r["status"] == "stable"

    def test_record_with_snapshot_hash(self, mgr):
        r = mgr.record("mod-1", "1.0.0", snapshot_hash="abc123")
        lpw = mgr.get_lpw("mod-1")
        assert lpw["snapshot_hash"] == "abc123"

    def test_record_custom_status(self, mgr):
        r = mgr.record("mod-1", "1.0.0", status="verified")
        assert r["status"] == "verified"

    def test_record_replaces_existing(self, mgr):
        mgr.record("mod-1", "1.0.0")
        mgr.record("mod-1", "2.0.0")
        lpw = mgr.get_lpw("mod-1")
        assert lpw["version"] == "2.0.0"

    def test_multiple_modules(self, mgr):
        mgr.record("mod-1", "1.0")
        mgr.record("mod-2", "2.0")
        assert mgr.get_lpw("mod-1")["version"] == "1.0"
        assert mgr.get_lpw("mod-2")["version"] == "2.0"


# ---------------------------------------------------------------------------
# get_lpw()
# ---------------------------------------------------------------------------

class TestGetLPW:
    def test_get_existing(self, mgr):
        mgr.record("mod-1", "1.0.0")
        lpw = mgr.get_lpw("mod-1")
        assert lpw is not None
        assert lpw["module_id"] == "mod-1"

    def test_get_nonexistent_returns_none(self, mgr):
        assert mgr.get_lpw("ghost") is None


# ---------------------------------------------------------------------------
# snapshot()
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_create_snapshot(self, mgr):
        r = mgr.snapshot("mod-1", "1.0.0", content_hash="hash123")
        assert "snapshot_id" in r
        assert r["module_id"] == "mod-1"
        assert r["version"] == "1.0.0"

    def test_snapshot_with_description(self, mgr):
        r = mgr.snapshot("mod-1", "1.0", description="stable release")
        assert r["module_id"] == "mod-1"

    def test_multiple_snapshots(self, mgr):
        mgr.snapshot("mod-1", "1.0")
        mgr.snapshot("mod-1", "1.1")
        mgr.snapshot("mod-1", "1.2")
        history = mgr.get_history("mod-1")
        assert len(history) == 3


# ---------------------------------------------------------------------------
# restore()
# ---------------------------------------------------------------------------

class TestRestore:
    def test_restore_existing(self, mgr):
        mgr.record("mod-1", "1.0.0")
        r = mgr.restore("mod-1")
        assert r["module_id"] == "mod-1"
        assert r["version"] == "1.0.0"
        assert r["restored_at"] > 0

    def test_restore_nonexistent(self, mgr):
        r = mgr.restore("ghost")
        assert "error" in r
        assert r["module_id"] == "ghost"

    def test_restore_updates_restored_at(self, mgr):
        mgr.record("mod-1", "1.0")
        r = mgr.restore("mod-1")
        lpw = mgr.get_lpw("mod-1")
        assert lpw["restored_at"] > 0


# ---------------------------------------------------------------------------
# list_lpw()
# ---------------------------------------------------------------------------

class TestListLPW:
    def test_list_all(self, mgr):
        mgr.record("mod-1", "1.0")
        mgr.record("mod-2", "2.0")
        assert len(mgr.list_lpw()) == 2

    def test_filter_by_status(self, mgr):
        mgr.record("mod-1", "1.0", status="stable")
        mgr.record("mod-2", "2.0", status="verified")
        stable = mgr.list_lpw(status="stable")
        assert len(stable) == 1
        assert stable[0]["module_id"] == "mod-1"

    def test_limit(self, mgr):
        for i in range(5):
            mgr.record(f"mod-{i}", f"{i}.0")
        assert len(mgr.list_lpw(limit=3)) == 3

    def test_empty(self, mgr):
        assert mgr.list_lpw() == []


# ---------------------------------------------------------------------------
# get_history()
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_empty_history(self, mgr):
        assert mgr.get_history("mod-1") == []

    def test_returns_snapshots(self, mgr):
        mgr.snapshot("mod-1", "1.0")
        mgr.snapshot("mod-1", "1.1")
        history = mgr.get_history("mod-1")
        assert len(history) == 2

    def test_limit(self, mgr):
        for i in range(5):
            mgr.snapshot("mod-1", f"{i}.0")
        assert len(mgr.get_history("mod-1", limit=3)) == 3

    def test_different_modules_separate(self, mgr):
        mgr.snapshot("mod-1", "1.0")
        mgr.snapshot("mod-2", "2.0")
        assert len(mgr.get_history("mod-1")) == 1
        assert len(mgr.get_history("mod-2")) == 1


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestEvents:
    def test_record_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        mgr = LPWManager(db_path=":memory:", event_bus=MockBus())
        mgr.record("mod-1", "1.0")
        assert any(e.topic == "rebuild.lpw.recorded" for e in events)

    def test_snapshot_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        mgr = LPWManager(db_path=":memory:", event_bus=MockBus())
        mgr.snapshot("mod-1", "1.0")
        assert any(e.topic == "rebuild.lpw.snapshot_created" for e in events)

    def test_restore_emits(self):
        events = []

        class MockBus:
            def publish(self, ev):
                events.append(ev)

        mgr = LPWManager(db_path=":memory:", event_bus=MockBus())
        mgr.record("mod-1", "1.0")
        mgr.restore("mod-1")
        assert any(e.topic == "rebuild.lpw.restored" for e in events)
