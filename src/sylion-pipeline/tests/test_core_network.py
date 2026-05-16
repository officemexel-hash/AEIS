"""Tests for sylion.cellular.core_network — CoreNetworkEmulator."""

import threading
import time

import pytest

from sylion.cellular.core_network import CoreNetworkEmulator, get_core_network_emulator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def emulator():
    """Fresh in-memory CoreNetworkEmulator per test."""
    return CoreNetworkEmulator()


@pytest.fixture
def created_core(emulator):
    """Pre-create a core network and return its data dict."""
    return emulator.create(technology="4G", stack_name="srsRAN")


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

class TestCreate:
    def test_returns_core_record(self, emulator):
        data = emulator.create(technology="5G", stack_name="Open5GS")
        assert "core_id" in data
        assert len(data["core_id"]) == 12
        assert data["technology"] == "5G"
        assert data["stack_name"] == "Open5GS"
        assert data["status"] == "created"
        assert data["has_internet"] == 0
        assert isinstance(data["created_at"], float)

    def test_defaults(self, emulator):
        data = emulator.create(technology="4G")
        assert data["stack_name"] == ""
        assert data["status"] == "created"
        assert data["has_internet"] == 0

    def test_internet_forbidden(self, emulator):
        result = emulator.create(technology="4G", has_internet=True)
        assert "error" in result
        assert "Internet access forbidden" in result["error"]
        # Nothing stored
        assert emulator.list_cores() == []

    def test_no_internet_default(self, emulator):
        data = emulator.create(technology="4G")
        assert data["has_internet"] == 0

    def test_unique_core_ids(self, emulator):
        a = emulator.create(technology="4G")
        b = emulator.create(technology="5G")
        assert a["core_id"] != b["core_id"]


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_existing(self, emulator, created_core):
        result = emulator.get(created_core["core_id"])
        assert result is not None
        assert result["core_id"] == created_core["core_id"]
        assert result["technology"] == "4G"

    def test_nonexistent_returns_none(self, emulator):
        assert emulator.get("no-such-id") is None


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

class TestStart:
    def test_created_to_running(self, emulator, created_core):
        cid = created_core["core_id"]
        result = emulator.start(cid)
        assert result["status"] == "running"
        # Persisted
        assert emulator.get(cid)["status"] == "running"

    def test_not_found(self, emulator):
        result = emulator.start("nope")
        assert "error" in result
        assert "core not found" in result["error"]

    def test_preserves_other_fields(self, emulator, created_core):
        cid = created_core["core_id"]
        result = emulator.start(cid)
        assert result["technology"] == "4G"
        assert result["stack_name"] == "srsRAN"
        assert result["core_id"] == cid

    def test_start_already_running(self, emulator, created_core):
        cid = created_core["core_id"]
        emulator.start(cid)
        # Starting again should still set to running (idempotent)
        result = emulator.start(cid)
        assert result["status"] == "running"


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

class TestStop:
    def test_running_to_stopped(self, emulator, created_core):
        cid = created_core["core_id"]
        emulator.start(cid)
        result = emulator.stop(cid)
        assert result["status"] == "stopped"
        assert emulator.get(cid)["status"] == "stopped"

    def test_not_found(self, emulator):
        result = emulator.stop("nope")
        assert "error" in result
        assert "core not found" in result["error"]

    def test_stop_created_core(self, emulator, created_core):
        cid = created_core["core_id"]
        # Can stop a core that was never started
        result = emulator.stop(cid)
        assert result["status"] == "stopped"

    def test_stop_already_stopped(self, emulator, created_core):
        cid = created_core["core_id"]
        emulator.stop(cid)
        result = emulator.stop(cid)
        assert result["status"] == "stopped"


# ---------------------------------------------------------------------------
# list_cores
# ---------------------------------------------------------------------------

class TestListCores:
    def test_empty(self, emulator):
        assert emulator.list_cores() == []

    def test_returns_all(self, emulator):
        emulator.create(technology="4G")
        emulator.create(technology="5G")
        items = emulator.list_cores()
        assert len(items) == 2

    def test_filter_status(self, emulator):
        a = emulator.create(technology="4G")
        emulator.create(technology="5G")
        emulator.start(a["core_id"])
        running = emulator.list_cores(status="running")
        assert len(running) == 1
        assert running[0]["core_id"] == a["core_id"]

    def test_limit(self, emulator):
        for i in range(5):
            emulator.create(technology="4G")
        result = emulator.list_cores(limit=3)
        assert len(result) == 3

    def test_ordered_by_created_at_desc(self, emulator):
        emulator.create(technology="4G")
        time.sleep(0.01)
        emulator.create(technology="5G")
        items = emulator.list_cores()
        assert items[0]["technology"] == "5G"
        assert items[1]["technology"] == "4G"

    def test_filter_stopped(self, emulator):
        a = emulator.create(technology="4G")
        emulator.create(technology="5G")
        emulator.stop(a["core_id"])
        stopped = emulator.list_cores(status="stopped")
        assert len(stopped) == 1
        assert stopped[0]["core_id"] == a["core_id"]


# ---------------------------------------------------------------------------
# Full lifecycle integration
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    def test_create_start_stop(self, emulator):
        data = emulator.create(technology="4G", stack_name="srsRAN")
        cid = data["core_id"]

        assert emulator.get(cid)["status"] == "created"

        emulator.start(cid)
        assert emulator.get(cid)["status"] == "running"

        emulator.stop(cid)
        assert emulator.get(cid)["status"] == "stopped"

        # Can restart after stop
        emulator.start(cid)
        assert emulator.get(cid)["status"] == "running"


# ---------------------------------------------------------------------------
# Singleton helper
# ---------------------------------------------------------------------------

class TestGetCoreNetworkEmulator:
    def test_returns_instance(self):
        inst = get_core_network_emulator()
        assert isinstance(inst, CoreNetworkEmulator)

    def test_singleton(self):
        a = get_core_network_emulator()
        b = get_core_network_emulator()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creates(self, emulator):
        errors = []
        results = []

        def do_create(idx):
            try:
                data = emulator.create(technology="4G")
                results.append(data["core_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        assert len(set(results)) == 20

    def test_concurrent_start_stop(self, emulator):
        cores = [emulator.create(technology="4G")["core_id"] for _ in range(10)]
        errors = []

        def start_core(cid):
            try:
                emulator.start(cid)
            except Exception as e:
                errors.append(e)

        def stop_core(cid):
            try:
                emulator.stop(cid)
            except Exception as e:
                errors.append(e)

        threads = []
        for cid in cores:
            threads.append(threading.Thread(target=start_core, args=(cid,)))
            threads.append(threading.Thread(target=stop_core, args=(cid,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # All cores should exist and be in a valid state
        for cid in cores:
            data = emulator.get(cid)
            assert data["status"] in ("running", "stopped", "created")
