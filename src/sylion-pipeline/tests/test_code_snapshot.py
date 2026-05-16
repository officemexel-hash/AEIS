"""Tests for SYLION Core Code Snapshot Engine (~40 tests)."""
import json
import time
import threading

import pytest

from sylion.core.code_snapshot import (
    CodeSnapshotEngine,
    get_code_snapshot_engine,
    reset_code_snapshot_engine,
)
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def engine(event_bus):
    return CodeSnapshotEngine(event_bus=event_bus)


@pytest.fixture
def engine_no_bus():
    return CodeSnapshotEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CONTENT_A = """\
def hello():
    print("hello")
    return True
"""

SAMPLE_CONTENT_B = """\
def hello():
    print("hello world")
    return True

def goodbye():
    print("goodbye")
"""

SAMPLE_CONTENT_C = """\
def hello():
    print("hello")
    return True
"""

EMPTY_CONTENT = ""


def _create_snapshot(engine, module_id="mod.test", version="1.0.0",
                     file_path="src/main.py", content=None, metadata=None):
    if content is None:
        content = SAMPLE_CONTENT_A
    return engine.create_snapshot(
        module_id=module_id,
        version=version,
        file_path=file_path,
        content=content,
        metadata=metadata,
    )


# ===========================================================================
# 1. Snapshot creation
# ===========================================================================

class TestCreateSnapshot:
    def test_create_returns_snapshot_id(self, engine):
        result = _create_snapshot(engine)
        assert "snapshot_id" in result
        assert isinstance(result["snapshot_id"], str)
        assert len(result["snapshot_id"]) > 0

    def test_create_returns_module_id(self, engine):
        result = _create_snapshot(engine, module_id="my.module")
        assert result["module_id"] == "my.module"

    def test_create_returns_version(self, engine):
        result = _create_snapshot(engine, version="2.0.0")
        assert result["version"] == "2.0.0"

    def test_create_returns_file_path(self, engine):
        result = _create_snapshot(engine, file_path="lib/foo.py")
        assert result["file_path"] == "lib/foo.py"

    def test_create_computes_sha256_hash(self, engine):
        import hashlib
        content = "line1\nline2\n"
        result = engine.create_snapshot("m", "1.0", "f.py", content)
        expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert result["content_hash"] == expected
        assert len(result["content_hash"]) == 64

    def test_create_computes_line_count(self, engine):
        content = "line1\nline2\nline3\n"
        result = engine.create_snapshot("m", "1.0", "f.py", content)
        assert result["line_count"] == 3

    def test_create_line_count_no_trailing_newline(self, engine):
        content = "line1\nline2"
        result = engine.create_snapshot("m", "1.0", "f.py", content)
        assert result["line_count"] == 2

    def test_create_line_count_empty_content(self, engine):
        result = engine.create_snapshot("m", "1.0", "f.py", "")
        assert result["line_count"] == 0

    def test_create_stores_metadata(self, engine):
        meta = {"author": "alice", "review": 123}
        result = _create_snapshot(engine, metadata=meta)
        assert result["metadata"] == meta

    def test_create_metadata_defaults_to_empty_dict(self, engine):
        result = _create_snapshot(engine)
        assert result["metadata"] == {}

    def test_create_sets_created_at(self, engine):
        before = time.time()
        result = _create_snapshot(engine)
        after = time.time()
        assert before <= result["created_at"] <= after

    def test_create_stores_in_database(self, engine):
        result = _create_snapshot(engine)
        fetched = engine.get_snapshot(result["snapshot_id"])
        assert fetched is not None
        assert fetched["snapshot_id"] == result["snapshot_id"]

    def test_create_unique_ids(self, engine):
        r1 = _create_snapshot(engine)
        r2 = _create_snapshot(engine)
        assert r1["snapshot_id"] != r2["snapshot_id"]

    def test_create_same_content_same_hash(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "hello\n")
        r2 = engine.create_snapshot("m", "2.0", "b.py", "hello\n")
        assert r1["content_hash"] == r2["content_hash"]


# ===========================================================================
# 2. Get snapshot
# ===========================================================================

class TestGetSnapshot:
    def test_get_existing_snapshot(self, engine):
        created = _create_snapshot(engine)
        fetched = engine.get_snapshot(created["snapshot_id"])
        assert fetched is not None
        assert fetched["snapshot_id"] == created["snapshot_id"]
        assert fetched["module_id"] == "mod.test"

    def test_get_nonexistent_returns_none(self, engine):
        result = engine.get_snapshot("nonexistent_id")
        assert result is None

    def test_get_parses_metadata_json(self, engine):
        meta = {"key": "value", "num": 42}
        created = _create_snapshot(engine, metadata=meta)
        fetched = engine.get_snapshot(created["snapshot_id"])
        assert fetched["metadata"]["key"] == "value"
        assert fetched["metadata"]["num"] == 42

    def test_get_returns_all_fields(self, engine):
        created = _create_snapshot(engine)
        fetched = engine.get_snapshot(created["snapshot_id"])
        expected_keys = {"snapshot_id", "module_id", "version",
                         "file_path", "content_hash", "line_count",
                         "created_at", "metadata"}
        assert set(fetched.keys()) == expected_keys


# ===========================================================================
# 3. List snapshots
# ===========================================================================

class TestListSnapshots:
    def test_list_all_snapshots(self, engine):
        _create_snapshot(engine, module_id="m1")
        _create_snapshot(engine, module_id="m2")
        _create_snapshot(engine, module_id="m3")
        results = engine.list_snapshots()
        assert len(results) == 3

    def test_list_filtered_by_module(self, engine):
        _create_snapshot(engine, module_id="alpha")
        _create_snapshot(engine, module_id="beta")
        _create_snapshot(engine, module_id="alpha")
        results = engine.list_snapshots(module_id="alpha")
        assert len(results) == 2
        assert all(r["module_id"] == "alpha" for r in results)

    def test_list_empty_when_no_snapshots(self, engine):
        results = engine.list_snapshots()
        assert results == []

    def test_list_empty_for_nonexistent_module(self, engine):
        _create_snapshot(engine, module_id="exists")
        results = engine.list_snapshots(module_id="nope")
        assert results == []

    def test_list_respects_limit(self, engine):
        for i in range(10):
            _create_snapshot(engine, module_id="m", version=f"v{i}")
        results = engine.list_snapshots(limit=5)
        assert len(results) == 5

    def test_list_ordered_by_created_at_desc(self, engine):
        r1 = _create_snapshot(engine, module_id="m", version="v1")
        r2 = _create_snapshot(engine, module_id="m", version="v2")
        r3 = _create_snapshot(engine, module_id="m", version="v3")
        results = engine.list_snapshots()
        assert results[0]["version"] == "v3"
        assert results[1]["version"] == "v2"
        assert results[2]["version"] == "v1"


# ===========================================================================
# 4. Delete snapshot
# ===========================================================================

class TestDeleteSnapshot:
    def test_delete_existing_snapshot(self, engine):
        created = _create_snapshot(engine)
        assert engine.delete_snapshot(created["snapshot_id"]) is True
        assert engine.get_snapshot(created["snapshot_id"]) is None

    def test_delete_nonexistent_returns_false(self, engine):
        assert engine.delete_snapshot("nonexistent") is False

    def test_delete_removes_related_diffs(self, engine):
        r1 = _create_snapshot(engine, content="old\n")
        r2 = _create_snapshot(engine, content="new\nextra\n")
        engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])

        # Delete the "from" snapshot
        engine.delete_snapshot(r1["snapshot_id"])

        # Diff referencing the deleted snapshot should be gone
        diffs = engine.list_diffs(snapshot_id=r1["snapshot_id"])
        assert len(diffs) == 0

    def test_delete_twice_returns_false(self, engine):
        created = _create_snapshot(engine)
        assert engine.delete_snapshot(created["snapshot_id"]) is True
        assert engine.delete_snapshot(created["snapshot_id"]) is False


# ===========================================================================
# 5. Diff snapshots
# ===========================================================================

class TestDiffSnapshots:
    def test_diff_returns_diff_id(self, engine):
        r1 = _create_snapshot(engine, content="a\n")
        r2 = _create_snapshot(engine, content="b\nc\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        assert "diff_id" in diff
        assert isinstance(diff["diff_id"], str)

    def test_diff_includes_from_and_to(self, engine):
        r1 = _create_snapshot(engine, content="x\n")
        r2 = _create_snapshot(engine, content="y\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        assert diff["from_snapshot"] == r1["snapshot_id"]
        assert diff["to_snapshot"] == r2["snapshot_id"]

    def test_diff_identical_content(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "same\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "same\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        assert diff["lines_added"] == 0
        assert diff["lines_removed"] == 0
        assert diff["lines_changed"] == 0

    def test_diff_more_lines_in_target(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "line1\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "line1\nline2\nline3\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        assert diff["lines_added"] == 2  # 3 - 1 = 2 net added
        assert diff["lines_removed"] == 0

    def test_diff_fewer_lines_in_target(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\nb\nc\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        assert diff["lines_added"] == 0
        assert diff["lines_removed"] == 2  # 3 - 1 = 2 net removed

    def test_diff_raises_on_missing_from(self, engine):
        r2 = _create_snapshot(engine, content="x\n")
        with pytest.raises(ValueError, match="not found"):
            engine.diff_snapshots("nonexistent", r2["snapshot_id"])

    def test_diff_raises_on_missing_to(self, engine):
        r1 = _create_snapshot(engine, content="x\n")
        with pytest.raises(ValueError, match="not found"):
            engine.diff_snapshots(r1["snapshot_id"], "nonexistent")

    def test_diff_stores_result(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\nb\n")
        diff = engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        fetched = engine.get_diff(diff["diff_id"])
        assert fetched is not None
        assert fetched["diff_id"] == diff["diff_id"]

    def test_get_nonexistent_diff_returns_none(self, engine):
        assert engine.get_diff("nonexistent") is None

    def test_list_diffs_by_snapshot(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\nb\n")
        r3 = engine.create_snapshot("m", "3.0", "a.py", "a\nb\nc\n")
        engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        engine.diff_snapshots(r2["snapshot_id"], r3["snapshot_id"])

        diffs = engine.list_diffs(snapshot_id=r2["snapshot_id"])
        assert len(diffs) == 2

    def test_list_all_diffs(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\nb\n")
        engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        diffs = engine.list_diffs()
        assert len(diffs) == 1


# ===========================================================================
# 6. Get latest snapshot
# ===========================================================================

class TestGetLatestSnapshot:
    def test_returns_most_recent(self, engine):
        _create_snapshot(engine, module_id="m", version="1.0", content="a\n")
        time.sleep(0.01)
        latest = _create_snapshot(engine, module_id="m", version="2.0", content="b\n")
        time.sleep(0.01)
        _create_snapshot(engine, module_id="m", version="3.0", content="c\n")

        result = engine.get_latest_snapshot("m")
        assert result is not None
        assert result["version"] == "3.0"

    def test_returns_none_for_unknown_module(self, engine):
        assert engine.get_latest_snapshot("no.such.module") is None

    def test_returns_none_when_no_snapshots(self, engine):
        assert engine.get_latest_snapshot("anything") is None

    def test_does_not_mix_modules(self, engine):
        _create_snapshot(engine, module_id="alpha", version="1.0")
        _create_snapshot(engine, module_id="beta", version="9.0")
        result = engine.get_latest_snapshot("alpha")
        assert result["module_id"] == "alpha"
        assert result["version"] == "1.0"


# ===========================================================================
# 7. Rollback
# ===========================================================================

class TestRollback:
    def test_rollback_returns_snapshot(self, engine):
        created = _create_snapshot(engine, content="original\n")
        result = engine.rollback_to_snapshot(created["snapshot_id"])
        assert result is not None
        assert result["snapshot_id"] == created["snapshot_id"]
        assert result["content_hash"] == created["content_hash"]

    def test_rollback_nonexistent_returns_none(self, engine):
        result = engine.rollback_to_snapshot("nonexistent")
        assert result is None

    def test_rollback_returns_full_snapshot_data(self, engine):
        meta = {"reason": "bug fix"}
        created = _create_snapshot(engine, metadata=meta)
        result = engine.rollback_to_snapshot(created["snapshot_id"])
        assert result["module_id"] == created["module_id"]
        assert result["version"] == created["version"]
        assert result["file_path"] == created["file_path"]
        assert result["content_hash"] == created["content_hash"]


# ===========================================================================
# 8. Event emission
# ===========================================================================

class TestEventEmission:
    def test_create_emits_snapshot_created(self, engine, event_bus):
        _create_snapshot(engine)
        events = event_bus.query(topic="snapshot.created")
        assert len(events) == 1
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert "snapshot_id" in payload
        assert payload["module_id"] == "mod.test"

    def test_diff_emits_snapshot_diff(self, engine, event_bus):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\nb\n")
        engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        events = event_bus.query(topic="snapshot.diff")
        assert len(events) == 1
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert "diff_id" in payload
        assert payload["lines_added"] == 1

    def test_rollback_emits_snapshot_rollback(self, engine, event_bus):
        created = _create_snapshot(engine)
        engine.rollback_to_snapshot(created["snapshot_id"])
        events = event_bus.query(topic="snapshot.rollback")
        assert len(events) == 1
        payload = events[0]["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        assert payload["snapshot_id"] == created["snapshot_id"]

    def test_no_events_without_bus(self, engine_no_bus):
        """Operations complete without errors even with no event bus."""
        created = _create_snapshot(engine_no_bus)
        r2 = engine_no_bus.create_snapshot("m", "2.0", "a.py", "b\n")
        engine_no_bus.diff_snapshots(created["snapshot_id"], r2["snapshot_id"])
        engine_no_bus.rollback_to_snapshot(created["snapshot_id"])


# ===========================================================================
# 9. Stats
# ===========================================================================

class TestStats:
    def test_stats_empty(self, engine):
        stats = engine.get_stats()
        assert stats["total_snapshots"] == 0
        assert stats["total_modules"] == 0
        assert stats["total_diffs"] == 0
        assert stats["total_lines"] == 0

    def test_stats_after_snapshots(self, engine):
        _create_snapshot(engine, module_id="m1", content="a\nb\n")
        _create_snapshot(engine, module_id="m2", content="x\n")
        stats = engine.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["total_modules"] == 2
        assert stats["total_lines"] == 3  # 2 + 1

    def test_stats_counts_diffs(self, engine):
        r1 = engine.create_snapshot("m", "1.0", "a.py", "a\n")
        r2 = engine.create_snapshot("m", "2.0", "a.py", "a\nb\n")
        engine.diff_snapshots(r1["snapshot_id"], r2["snapshot_id"])
        stats = engine.get_stats()
        assert stats["total_diffs"] == 1

    def test_stats_same_module(self, engine):
        _create_snapshot(engine, module_id="m", version="1.0")
        _create_snapshot(engine, module_id="m", version="2.0")
        stats = engine.get_stats()
        assert stats["total_snapshots"] == 2
        assert stats["total_modules"] == 1


# ===========================================================================
# 10. Content diff utility
# ===========================================================================

class TestComputeContentDiff:
    def test_identical_content(self):
        result = CodeSnapshotEngine.compute_content_diff("a\nb\n", "a\nb\n")
        assert result["lines_added"] == 0
        assert result["lines_removed"] == 0
        assert result["lines_changed"] == 0

    def test_added_lines(self):
        result = CodeSnapshotEngine.compute_content_diff("a\n", "a\nb\nc\n")
        assert result["lines_added"] == 2
        assert result["lines_removed"] == 0

    def test_removed_lines(self):
        result = CodeSnapshotEngine.compute_content_diff("a\nb\nc\n", "a\n")
        assert result["lines_removed"] == 2
        assert result["lines_added"] == 0

    def test_changed_lines(self):
        from_content = "a\nb\nc\n"
        to_content = "x\ny\nc\n"
        result = CodeSnapshotEngine.compute_content_diff(from_content, to_content)
        assert result["lines_added"] == 2
        assert result["lines_removed"] == 2
        assert result["lines_changed"] == 2

    def test_empty_to_content(self):
        result = CodeSnapshotEngine.compute_content_diff("a\nb\n", "")
        assert result["lines_removed"] == 2
        assert result["lines_added"] == 0


# ===========================================================================
# 11. Singleton functions
# ===========================================================================

class TestSingleton:
    def test_get_returns_engine(self):
        reset_code_snapshot_engine()
        eng = get_code_snapshot_engine()
        assert isinstance(eng, CodeSnapshotEngine)

    def test_get_returns_same_instance(self):
        reset_code_snapshot_engine()
        eng1 = get_code_snapshot_engine()
        eng2 = get_code_snapshot_engine()
        assert eng1 is eng2

    def test_reset_creates_new_instance(self):
        reset_code_snapshot_engine()
        eng1 = get_code_snapshot_engine()
        reset_code_snapshot_engine()
        eng2 = get_code_snapshot_engine()
        assert eng1 is not eng2


# ===========================================================================
# 12. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_snapshot_creation(self, engine):
        """Multiple threads creating snapshots simultaneously."""
        results = []
        errors = []

        def create_snap(idx):
            try:
                r = engine.create_snapshot(
                    module_id=f"mod.concurrent_{idx}",
                    version="1.0",
                    file_path=f"file_{idx}.py",
                    content=f"content {idx}\n",
                )
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create_snap, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20
        ids = {r["snapshot_id"] for r in results}
        assert len(ids) == 20  # all unique

    def test_concurrent_read_write(self, engine):
        """Reads and writes happening simultaneously."""
        _create_snapshot(engine, module_id="rw.mod")

        errors = []

        def reader():
            try:
                for _ in range(50):
                    engine.list_snapshots(module_id="rw.mod")
                    engine.get_latest_snapshot("rw.mod")
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    engine.create_snapshot(
                        module_id="rw.mod",
                        version=f"v{i}",
                        file_path="f.py",
                        content=f"v{i}\n",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ===========================================================================
# 13. Persistence
# ===========================================================================

class TestPersistence:
    def test_file_based_db(self, tmp_path):
        db_file = tmp_path / "snapshots.db"
        bus = EventBus()

        eng1 = CodeSnapshotEngine(db_path=str(db_file), event_bus=bus)
        created = eng1.create_snapshot("m", "1.0", "a.py", "hello\n")
        eng1._conn.close()

        eng2 = CodeSnapshotEngine(db_path=str(db_file), event_bus=bus)
        fetched = eng2.get_snapshot(created["snapshot_id"])
        assert fetched is not None
        assert fetched["module_id"] == "m"
        assert fetched["version"] == "1.0"
        eng2._conn.close()


# ===========================================================================
# 14. Integration workflow
# ===========================================================================

class TestIntegrationWorkflow:
    def test_full_lifecycle(self, engine, event_bus):
        """Create -> diff -> rollback -> delete lifecycle."""
        # Create two versions
        v1 = engine.create_snapshot(
            module_id="lifecycle.mod",
            version="1.0.0",
            file_path="core.py",
            content="def old():\n    pass\n",
            metadata={"branch": "main"},
        )
        v2 = engine.create_snapshot(
            module_id="lifecycle.mod",
            version="2.0.0",
            file_path="core.py",
            content="def new():\n    pass\n\ndef extra():\n    pass\n",
            metadata={"branch": "feature"},
        )

        # Get latest
        latest = engine.get_latest_snapshot("lifecycle.mod")
        assert latest["version"] == "2.0.0"

        # Compute diff: v1 has 2 lines, v2 has 5 lines -> 3 net added
        diff = engine.diff_snapshots(v1["snapshot_id"], v2["snapshot_id"])
        assert diff["lines_added"] == 3  # 5 lines - 2 lines
        assert diff["lines_removed"] == 0

        # List snapshots
        snaps = engine.list_snapshots(module_id="lifecycle.mod")
        assert len(snaps) == 2

        # Rollback to v1
        rollback_data = engine.rollback_to_snapshot(v1["snapshot_id"])
        assert rollback_data["version"] == "1.0.0"
        assert rollback_data["metadata"]["branch"] == "main"

        # Verify events
        created_events = event_bus.query(topic="snapshot.created")
        assert len(created_events) == 2

        diff_events = event_bus.query(topic="snapshot.diff")
        assert len(diff_events) == 1

        rollback_events = event_bus.query(topic="snapshot.rollback")
        assert len(rollback_events) == 1

        # Delete old snapshot
        assert engine.delete_snapshot(v1["snapshot_id"]) is True
        assert engine.get_snapshot(v1["snapshot_id"]) is None

        # Diff for v1 should be gone
        remaining_diffs = engine.list_diffs(snapshot_id=v1["snapshot_id"])
        assert len(remaining_diffs) == 0

        # Stats
        stats = engine.get_stats()
        assert stats["total_snapshots"] == 1
        assert stats["total_diffs"] == 0

    def test_multiple_modules_workflow(self, engine):
        """Multiple modules each with multiple snapshots."""
        for mod in ("auth", "api", "db"):
            for ver in ("1.0", "2.0", "3.0"):
                engine.create_snapshot(
                    module_id=mod,
                    version=ver,
                    file_path=f"{mod}/main.py",
                    content=f"{mod} {ver}\n",
                )

        # Latest for each module
        assert engine.get_latest_snapshot("auth")["version"] == "3.0"
        assert engine.get_latest_snapshot("api")["version"] == "3.0"
        assert engine.get_latest_snapshot("db")["version"] == "3.0"

        stats = engine.get_stats()
        assert stats["total_snapshots"] == 9
        assert stats["total_modules"] == 3
