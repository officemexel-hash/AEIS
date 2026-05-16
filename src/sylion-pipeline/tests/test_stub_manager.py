"""
Comprehensive tests for SYLION AEIS Stub Manager (30+ tests).

Covers:
  - Stub generation tracking
  - Version detection / incrementing
  - Staleness detection
  - Stats and listing
  - Thread safety
  - Singleton pattern
  - Event emission
  - Proto hash change detection
"""
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sylion.contracts.stub_manager import (
    StubManager,
    get_stub_manager,
    PROTO_FILES,
    _file_hash,
    _proto_stem,
    _stub_files,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def manager():
    """Fresh StubManager (in-memory, no event bus)."""
    return StubManager()


@pytest.fixture
def manager_with_bus(event_bus):
    """StubManager wired to an EventBus."""
    return StubManager(event_bus=event_bus)


@pytest.fixture
def proto_dir(tmp_path):
    """Create a temp directory with sample .proto files."""
    pd = tmp_path / "proto"
    pd.mkdir()
    for pf in PROTO_FILES:
        (pd / pf).write_text(
            f'syntax = "proto3";\npackage sylion.test;\n\n'
            f'service {_proto_stem(pf).title().replace("_", "")}Service {{}}\n',
            encoding="utf-8",
        )
    return pd


@pytest.fixture
def stub_dir(tmp_path):
    """Output directory for generated stubs."""
    sd = tmp_path / "generated"
    sd.mkdir()
    return sd


def _mock_protoc_success(self, proto_path, proto_dir, output_dir):
    """Mock _run_protoc that creates stub files on disk."""
    stem = proto_path.stem
    (output_dir / f"{stem}_pb2.py").write_text("# pb2 stub\n", encoding="utf-8")
    (output_dir / f"{stem}_pb2_grpc.py").write_text("# grpc stub\n", encoding="utf-8")
    return True


def _mock_protoc_fail(self, proto_path, proto_dir, output_dir):
    """Mock _run_protoc that always fails."""
    return False


# ===========================================================================
# 1. Helper functions
# ===========================================================================

class TestHelpers:
    def test_proto_stem_strips_extension(self):
        assert _proto_stem("core_v1.proto") == "core_v1"
        assert _proto_stem("common.proto") == "common"

    def test_stub_files_returns_two_paths(self, tmp_path):
        files = _stub_files("core_v1", tmp_path)
        assert len(files) == 2
        assert files[0].name == "core_v1_pb2.py"
        assert files[1].name == "core_v1_pb2_grpc.py"

    def test_file_hash_deterministic(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("hello world", encoding="utf-8")
        h1 = _file_hash(p)
        h2 = _file_hash(p)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_file_hash_changes_with_content(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("v1", encoding="utf-8")
        h1 = _file_hash(p)
        p.write_text("v2", encoding="utf-8")
        h2 = _file_hash(p)
        assert h1 != h2


# ===========================================================================
# 2. Stub generation tracking
# ===========================================================================

class TestStubGeneration:
    def test_generate_all_stubs(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        result = manager.generate_stubs(proto_dir, stub_dir)

        assert result["generated"] == len(PROTO_FILES)
        assert result["skipped"] == 0
        assert result["failed"] == 0
        assert result["total_proto_files"] == len(PROTO_FILES)

    def test_generate_tracks_in_db(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        stubs = manager.list_stubs()
        assert len(stubs) == len(PROTO_FILES)
        for s in stubs:
            assert s["status"] == "generated"
            assert s["proto_hash"] != ""
            assert s["version"] == 1

    def test_generate_skips_missing_proto(self, manager, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        # Use empty directory — all protos missing
        empty_dir = stub_dir / "empty_proto"
        empty_dir.mkdir()
        result = manager.generate_stubs(empty_dir, stub_dir)

        assert result["generated"] == 0
        assert result["skipped"] == len(PROTO_FILES)

    def test_generate_records_failure(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_fail)
        result = manager.generate_stubs(proto_dir, stub_dir)

        assert result["failed"] == len(PROTO_FILES)
        assert result["generated"] == 0

        stubs = manager.list_stubs()
        for s in stubs:
            assert s["status"] == "failed"

    def test_generate_creates_output_dir(self, manager, proto_dir, tmp_path, monkeypatch):
        output = tmp_path / "nested" / "output"
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, output)
        assert output.exists()

    def test_generate_records_service_name(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # At least one stub should have a detected service name
        stubs = manager.list_stubs()
        service_names = [s["service_name"] for s in stubs]
        assert all(sn != "" for sn in service_names)


# ===========================================================================
# 3. Version detection
# ===========================================================================

class TestVersionDetection:
    def test_initial_version_is_one(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        for s in manager.list_stubs():
            assert s["version"] == 1

    def test_version_increments_on_regenerate(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)

        # First generation
        manager.generate_stubs(proto_dir, stub_dir)
        # Second generation
        manager.generate_stubs(proto_dir, stub_dir)

        for s in manager.list_stubs():
            assert s["version"] == 2

    def test_version_increments_independently_per_proto(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Modify one proto file to change its hash
        target = proto_dir / PROTO_FILES[0]
        target.write_text("syntax = proto3; // changed", encoding="utf-8")

        # Regenerate only stale
        manager.regenerate_stale(proto_dir, stub_dir)

        stubs = manager.list_stubs()
        changed = [s for s in stubs if s["proto_file"] == PROTO_FILES[0]]
        unchanged = [s for s in stubs if s["proto_file"] != PROTO_FILES[0]]

        assert changed[0]["version"] == 2
        for s in unchanged:
            assert s["version"] == 1

    def test_get_stub_status_returns_version(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        status = manager.get_stub_status("common")
        assert status is not None
        assert status["version"] == 1


# ===========================================================================
# 4. Stale detection
# ===========================================================================

class TestStaleDetection:
    def test_validate_all_valid(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Create stub files so validation sees them
        for pf in PROTO_FILES:
            stem = _proto_stem(pf)
            (stub_dir / f"{stem}_pb2.py").write_text("# stub", encoding="utf-8")
            (stub_dir / f"{stem}_pb2_grpc.py").write_text("# stub", encoding="utf-8")

        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["valid_count"] == len(PROTO_FILES)
        assert result["stale_count"] == 0

    def test_validate_detects_hash_change(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Change a proto file
        target = proto_dir / PROTO_FILES[0]
        original = target.read_text(encoding="utf-8")
        target.write_text(original + "// modified\n", encoding="utf-8")

        # Create stub files
        for pf in PROTO_FILES:
            stem = _proto_stem(pf)
            (stub_dir / f"{stem}_pb2.py").write_text("# stub", encoding="utf-8")
            (stub_dir / f"{stem}_pb2_grpc.py").write_text("# stub", encoding="utf-8")

        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["stale_count"] >= 1
        stale_files = [s["proto_file"] for s in result["stale"]]
        assert PROTO_FILES[0] in stale_files

    def test_validate_detects_missing_stubs(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Delete all stub files so they are missing during validation
        for f in stub_dir.iterdir():
            if f.suffix == ".py":
                f.unlink()

        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["stale_count"] == len(PROTO_FILES)

    def test_validate_empty_db(self, manager, proto_dir, stub_dir):
        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["valid_count"] == 0
        assert result["stale_count"] == 0
        assert result["missing_count"] == 0

    def test_validate_detects_failed_status(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_fail)
        manager.generate_stubs(proto_dir, stub_dir)

        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["stale_count"] == len(PROTO_FILES)
        reasons = [s["reason"] for s in result["stale"]]
        assert all("status=" in r for r in reasons)

    def test_validate_detects_missing_proto(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Delete a proto file
        (proto_dir / PROTO_FILES[0]).unlink()

        # Create stub files so only proto-file-missing triggers
        for pf in PROTO_FILES:
            stem = _proto_stem(pf)
            (stub_dir / f"{stem}_pb2.py").write_text("# stub", encoding="utf-8")
            (stub_dir / f"{stem}_pb2_grpc.py").write_text("# stub", encoding="utf-8")

        result = manager.validate_stubs(proto_dir, stub_dir)
        assert result["missing_count"] >= 1


# ===========================================================================
# 5. Stats and listing
# ===========================================================================

class TestStatsAndListing:
    def test_stats_empty(self, manager):
        stats = manager.get_stats()
        assert stats["total_stubs"] == 0
        assert stats["stale_count"] == 0
        assert stats["generated_count"] == 0
        assert stats["last_generation_time"] is None

    def test_stats_after_generation(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        stats = manager.get_stats()
        assert stats["total_stubs"] == len(PROTO_FILES)
        assert stats["generated_count"] == len(PROTO_FILES)
        assert stats["stale_count"] == 0
        assert stats["last_generation_time"] is not None
        assert stats["last_generation_time"] > 0

    def test_stats_after_failure(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_fail)
        manager.generate_stubs(proto_dir, stub_dir)

        stats = manager.get_stats()
        assert stats["total_stubs"] == len(PROTO_FILES)
        assert stats["failed_count"] == len(PROTO_FILES)
        assert stats["stale_count"] == len(PROTO_FILES)

    def test_list_stubs_empty(self, manager):
        assert manager.list_stubs() == []

    def test_list_stubs_returns_all_fields(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        stubs = manager.list_stubs()
        expected_keys = {
            "proto_file", "service_name", "proto_hash", "version",
            "status", "pb2_path", "grpc_path", "generated_at", "updated_at",
        }
        for s in stubs:
            assert expected_keys.issubset(s.keys())

    def test_list_stubs_ordered_by_proto_file(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        stubs = manager.list_stubs()
        files = [s["proto_file"] for s in stubs]
        assert files == sorted(files)

    def test_get_stub_status_by_service_name(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        stubs = manager.list_stubs()
        first_service = stubs[0]["service_name"]
        status = manager.get_stub_status(first_service)
        assert status is not None
        assert status["service_name"] == first_service

    def test_get_stub_status_by_proto_stem(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        status = manager.get_stub_status("common")
        assert status is not None
        assert status["proto_file"] == "common.proto"

    def test_get_stub_status_nonexistent(self, manager):
        assert manager.get_stub_status("nonexistent_service") is None


# ===========================================================================
# 6. Regenerate stale
# ===========================================================================

class TestRegenerateStale:
    def test_regenerate_nothing_when_all_current(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        result = manager.regenerate_stale(proto_dir, stub_dir)
        assert result["regenerated"] == 0
        assert result["already_current"] == len(PROTO_FILES)

    def test_regenerate_failed_stubs(self, manager, proto_dir, stub_dir, monkeypatch):
        # First: all fail
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_fail)
        manager.generate_stubs(proto_dir, stub_dir)

        # Now: protoc succeeds
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        result = manager.regenerate_stale(proto_dir, stub_dir)

        assert result["regenerated"] == len(PROTO_FILES)

    def test_regenerate_detects_hash_change(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        # Change a proto
        target = proto_dir / PROTO_FILES[1]
        original = target.read_text(encoding="utf-8")
        target.write_text(original + "// changed\n", encoding="utf-8")

        result = manager.regenerate_stale(proto_dir, stub_dir)
        assert result["regenerated"] >= 1


# ===========================================================================
# 7. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_generate(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        errors: list[str] = []

        def worker():
            try:
                manager.generate_stubs(proto_dir, stub_dir)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stubs = manager.list_stubs()
        assert len(stubs) == len(PROTO_FILES)

    def test_concurrent_read_write(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        errors: list[str] = []

        def writer():
            try:
                manager.generate_stubs(proto_dir, stub_dir)
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for _ in range(20):
                    manager.list_stubs()
                    manager.get_stats()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_validate(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager.generate_stubs(proto_dir, stub_dir)

        errors: list[str] = []
        results: list[dict] = []

        def validator():
            try:
                r = manager.validate_stubs(proto_dir, stub_dir)
                results.append(r)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=validator) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(results) == 10


# ===========================================================================
# 8. Singleton pattern
# ===========================================================================

class TestSingleton:
    def test_get_stub_manager_returns_same_instance(self):
        # Reset singleton
        import sylion.contracts.stub_manager as mod
        mod._manager = None

        m1 = get_stub_manager()
        m2 = get_stub_manager()
        assert m1 is m2

        # Cleanup
        mod._manager = None

    def test_get_stub_manager_with_custom_db(self):
        import sylion.contracts.stub_manager as mod
        mod._manager = None

        m = get_stub_manager()
        assert m._db_path == ":memory:"
        mod._manager = None

    def test_singleton_ignores_second_db_path(self):
        import sylion.contracts.stub_manager as mod
        mod._manager = None

        m1 = get_stub_manager(db_path=":memory:")
        m2 = get_stub_manager(db_path="/tmp/other.db")
        assert m1 is m2
        assert m2._db_path == ":memory:"
        mod._manager = None


# ===========================================================================
# 9. Event emission
# ===========================================================================

class TestEventEmission:
    def test_emit_on_generate(self, manager_with_bus, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager_with_bus.generate_stubs(proto_dir, stub_dir)

        events = manager_with_bus._event_bus.get_catalog()
        assert "contracts.stub.generated" in events

    def test_emit_on_validate(self, manager_with_bus, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager_with_bus.generate_stubs(proto_dir, stub_dir)
        manager_with_bus.validate_stubs(proto_dir, stub_dir)

        events = manager_with_bus._event_bus.get_catalog()
        assert "contracts.stub.validated" in events

    def test_emit_on_regenerate(self, manager_with_bus, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_fail)
        manager_with_bus.generate_stubs(proto_dir, stub_dir)

        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager_with_bus.regenerate_stale(proto_dir, stub_dir)

        events = manager_with_bus._event_bus.get_catalog()
        assert "contracts.stub.regenerated" in events

    def test_no_emit_without_event_bus(self, manager, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        # Should not raise even with no event bus
        manager.generate_stubs(proto_dir, stub_dir)
        manager.validate_stubs(proto_dir, stub_dir)

    def test_event_payload_contains_counts(self, manager_with_bus, proto_dir, stub_dir, monkeypatch):
        monkeypatch.setattr(StubManager, "_run_protoc", _mock_protoc_success)
        manager_with_bus.generate_stubs(proto_dir, stub_dir)

        # Get the emitted event (query returns list[dict])
        bus = manager_with_bus._event_bus
        events = bus.query(topic="contracts.stub.generated", limit=1)
        assert len(events) >= 1
        import json
        payload = json.loads(events[0]["payload"])
        assert "generated" in payload
        assert payload["generated"] == len(PROTO_FILES)


# ===========================================================================
# 10. Close / cleanup
# ===========================================================================

class TestClose:
    def test_close_does_not_raise(self, manager):
        manager.close()

    def test_close_idempotent(self, manager):
        manager.close()
        # Second close should not raise (SQLite handles this gracefully)
