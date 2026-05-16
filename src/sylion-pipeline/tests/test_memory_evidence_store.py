"""
Comprehensive tests for sylion.memory.evidence_store — EvidenceStore class.
Tests: store, retrieve, query_by_type, query_by_pack, delete, get_stats,
       StoredEvidence dataclass, content hash verification, event emission,
       evidence spine integration, query logging, edge cases, thread safety.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time

import pytest

from sylion.memory.evidence_store import (
    EvidenceStore,
    StoredEvidence,
    get_evidence_store,
)
from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine, EvidenceEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> EvidenceStore:
    """Fresh in-memory EvidenceStore with no event_bus or spine."""
    return EvidenceStore()


@pytest.fixture
def store_with_bus() -> tuple[EvidenceStore, EventBus]:
    """EvidenceStore wired to a real in-memory EventBus."""
    bus = EventBus()
    s = EvidenceStore(event_bus=bus)
    return s, bus


@pytest.fixture
def store_with_spine() -> tuple[EvidenceStore, EvidenceSpine]:
    """EvidenceStore wired to a real in-memory EvidenceSpine."""
    spine = EvidenceSpine()
    s = EvidenceStore(evidence_spine=spine)
    return s, spine


@pytest.fixture
def store_with_bus_and_spine() -> tuple[EvidenceStore, EventBus, EvidenceSpine]:
    """EvidenceStore wired to both EventBus and EvidenceSpine."""
    bus = EventBus()
    spine = EvidenceSpine(event_bus=bus)
    s = EvidenceStore(event_bus=bus, evidence_spine=spine)
    return s, bus, spine


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# StoredEvidence dataclass
# ---------------------------------------------------------------------------

class TestStoredEvidence:

    def test_auto_evidence_id(self):
        e = StoredEvidence()
        assert e.evidence_id != ""
        assert len(e.evidence_id) == 32  # uuid4 hex

    def test_auto_created_at(self):
        before = time.time()
        e = StoredEvidence()
        after = time.time()
        assert before <= e.created_at <= after

    def test_auto_content_hash(self):
        e = StoredEvidence(content="hello")
        assert e.content_hash == _sha256("hello")

    def test_no_content_hash_when_empty(self):
        e = StoredEvidence()
        assert e.content_hash == ""

    def test_explicit_fields_preserved(self):
        e = StoredEvidence(
            evidence_id="abc123",
            pack_id="pack-1",
            artefact_type="test_result",
            name="my_test",
            content="payload",
            content_hash="explicit_hash",
            metadata={"key": "val"},
            created_at=12345.0,
        )
        assert e.evidence_id == "abc123"
        assert e.pack_id == "pack-1"
        assert e.artefact_type == "test_result"
        assert e.name == "my_test"
        assert e.content == "payload"
        assert e.content_hash == "explicit_hash"
        assert e.metadata == {"key": "val"}
        assert e.created_at == 12345.0

    def test_metadata_default_factory_isolation(self):
        e1 = StoredEvidence()
        e2 = StoredEvidence()
        e1.metadata["x"] = 1
        assert "x" not in e2.metadata


# ---------------------------------------------------------------------------
# EvidenceStore.__init__ and table creation
# ---------------------------------------------------------------------------

class TestEvidenceStoreInit:

    def test_in_memory_db(self):
        s = EvidenceStore()
        assert s._db_path == ":memory:"

    def test_custom_db_path(self, tmp_path):
        db_file = tmp_path / "test_evidence.db"
        s = EvidenceStore(db_path=db_file)
        assert s._db_path == str(db_file)
        rows = s._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r["name"] for r in rows]
        assert "stored_evidence" in table_names
        assert "evidence_queries" in table_names

    def test_indexes_created(self, store):
        rows = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
        ).fetchall()
        idx_names = {r["name"] for r in rows}
        assert "idx_evidence_pack" in idx_names
        assert "idx_evidence_type" in idx_names
        assert "idx_evidence_hash" in idx_names
        assert "idx_eq_ts" in idx_names


# ---------------------------------------------------------------------------
# store()
# ---------------------------------------------------------------------------

class TestStore:

    def test_returns_evidence_id_and_hash(self, store):
        result = store.store(content="test content")
        assert "evidence_id" in result
        assert "content_hash" in result
        assert result["content_hash"] == _sha256("test content")

    def test_generates_uuid_when_no_id(self, store):
        result = store.store(content="x")
        assert len(result["evidence_id"]) == 32  # uuid4 hex

    def test_uses_provided_evidence_id(self, store):
        result = store.store(evidence_id="my_custom_id", content="x")
        assert result["evidence_id"] == "my_custom_id"

    def test_stores_all_fields(self, store):
        store.store(
            evidence_id="eid1",
            pack_id="pack-42",
            artefact_type="benchmark",
            name="bench_test",
            content="benchmark_data",
            metadata={"version": 2, "tags": ["fast"]},
        )
        row = store.retrieve("eid1")
        assert row is not None
        assert row["pack_id"] == "pack-42"
        assert row["artefact_type"] == "benchmark"
        assert row["name"] == "bench_test"
        assert row["content"] == "benchmark_data"
        assert row["content_hash"] == _sha256("benchmark_data")
        meta = row["metadata"]
        assert meta["version"] == 2
        assert meta["tags"] == ["fast"]
        assert row["created_at"] > 0

    def test_default_empty_metadata(self, store):
        store.store(evidence_id="eid2", content="c")
        row = store.retrieve("eid2")
        assert row is not None
        assert row["metadata"] == {}

    def test_content_hash_integrity(self, store):
        store.store(evidence_id="h1", content="integrity check")
        row = store.retrieve("h1")
        assert row["content_hash"] == _sha256("integrity check")

    def test_upsert_replaces_existing(self, store):
        store.store(evidence_id="up1", content="original", name="first")
        store.store(evidence_id="up1", content="updated", name="second")
        row = store.retrieve("up1")
        assert row is not None
        assert row["content"] == "updated"
        assert row["name"] == "second"
        assert row["content_hash"] == _sha256("updated")

    def test_empty_content_still_works(self, store):
        result = store.store(evidence_id="empty_content", content="")
        assert result["content_hash"] == _sha256("")

    def test_unicode_content(self, store):
        text = "\u00e4\u00f6\u00fc Unicode test \u4e16\u754c"
        store.store(evidence_id="uni1", content=text)
        row = store.retrieve("uni1")
        assert row["content"] == text
        assert row["content_hash"] == _sha256(text)


# ---------------------------------------------------------------------------
# retrieve()
# ---------------------------------------------------------------------------

class TestRetrieve:

    def test_retrieve_existing(self, store):
        store.store(evidence_id="r1", content="data")
        row = store.retrieve("r1")
        assert row is not None
        assert row["evidence_id"] == "r1"
        assert row["content"] == "data"

    def test_retrieve_nonexistent(self, store):
        result = store.retrieve("does_not_exist")
        assert result is None

    def test_metadata_parsed_as_dict(self, store):
        store.store(evidence_id="rm1", content="c", metadata={"a": 1, "b": [2, 3]})
        row = store.retrieve("rm1")
        assert row is not None
        assert isinstance(row["metadata"], dict)
        assert row["metadata"]["a"] == 1
        assert row["metadata"]["b"] == [2, 3]

    def test_retrieve_after_delete_returns_none(self, store):
        store.store(evidence_id="rd1", content="c")
        store.delete("rd1")
        assert store.retrieve("rd1") is None


# ---------------------------------------------------------------------------
# query_by_type()
# ---------------------------------------------------------------------------

class TestQueryByType:

    def test_returns_matching_type(self, store):
        store.store(artefact_type="test_result", content="t1", evidence_id="qt1")
        store.store(artefact_type="test_result", content="t2", evidence_id="qt2")
        store.store(artefact_type="benchmark", content="b1", evidence_id="qt3")

        results = store.query_by_type("test_result")
        ids = [r["evidence_id"] for r in results]
        assert "qt1" in ids
        assert "qt2" in ids
        assert "qt3" not in ids

    def test_empty_when_no_match(self, store):
        results = store.query_by_type("nonexistent_type")
        assert results == []

    def test_limit_parameter(self, store):
        for i in range(10):
            store.store(artefact_type="log", content=f"log-{i}", evidence_id=f"ql{i}")

        results = store.query_by_type("log", limit=3)
        assert len(results) == 3

    def test_default_limit_100(self, store):
        for i in range(5):
            store.store(artefact_type="review", content=f"r-{i}", evidence_id=f"qr{i}")
        results = store.query_by_type("review")
        assert len(results) == 5

    def test_ordered_by_created_at_desc(self, store):
        ids = []
        for i in range(4):
            r = store.store(artefact_type="contract", content=f"c-{i}")
            ids.append(r["evidence_id"])

        results = store.query_by_type("contract")
        result_ids = [r["evidence_id"] for r in results]
        assert result_ids == list(reversed(ids))

    def test_query_by_type_logs_query(self, store):
        store.query_by_type("sometype")
        stats = store.get_stats()
        assert stats["total_queries"] >= 1


# ---------------------------------------------------------------------------
# query_by_pack()
# ---------------------------------------------------------------------------

class TestQueryByPack:

    def test_returns_matching_pack(self, store):
        store.store(pack_id="alpha", content="a1", evidence_id="qp1")
        store.store(pack_id="alpha", content="a2", evidence_id="qp2")
        store.store(pack_id="beta", content="b1", evidence_id="qp3")

        results = store.query_by_pack("alpha")
        ids = [r["evidence_id"] for r in results]
        assert "qp1" in ids
        assert "qp2" in ids
        assert "qp3" not in ids

    def test_empty_when_no_match(self, store):
        results = store.query_by_pack("nonexistent_pack")
        assert results == []

    def test_limit_parameter(self, store):
        for i in range(10):
            store.store(pack_id="bigpack", content=f"p-{i}", evidence_id=f"qbp{i}")

        results = store.query_by_pack("bigpack", limit=4)
        assert len(results) == 4

    def test_ordered_by_created_at_desc(self, store):
        ids = []
        for i in range(3):
            r = store.store(pack_id="ordered", content=f"o-{i}")
            ids.append(r["evidence_id"])

        results = store.query_by_pack("ordered")
        result_ids = [r["evidence_id"] for r in results]
        assert result_ids == list(reversed(ids))

    def test_query_by_pack_logs_query(self, store):
        store.query_by_pack("somepack")
        stats = store.get_stats()
        assert stats["total_queries"] >= 1


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

class TestDelete:

    def test_delete_existing(self, store):
        store.store(evidence_id="d1", content="to_delete")
        assert store.delete("d1") is True
        assert store.retrieve("d1") is None

    def test_delete_nonexistent(self, store):
        assert store.delete("no_such_id") is False

    def test_delete_idempotent(self, store):
        store.store(evidence_id="di1", content="c")
        assert store.delete("di1") is True
        assert store.delete("di1") is False

    def test_delete_does_not_affect_others(self, store):
        store.store(evidence_id="da1", content="keep")
        store.store(evidence_id="da2", content="remove")
        store.delete("da2")
        assert store.retrieve("da1") is not None
        assert store.retrieve("da2") is None

    def test_delete_updates_stats(self, store):
        store.store(evidence_id="ds1", content="c", artefact_type="test_result")
        store.store(evidence_id="ds2", content="c", artefact_type="test_result")
        assert store.get_stats()["total_evidence"] == 2
        store.delete("ds1")
        assert store.get_stats()["total_evidence"] == 1


# ---------------------------------------------------------------------------
# get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:

    def test_empty_store(self, store):
        stats = store.get_stats()
        assert stats["total_evidence"] == 0
        assert stats["by_type"] == {}
        assert stats["total_queries"] == 0

    def test_total_evidence_count(self, store):
        store.store(content="c1", evidence_id="s1")
        store.store(content="c2", evidence_id="s2")
        store.store(content="c3", evidence_id="s3")
        assert store.get_stats()["total_evidence"] == 3

    def test_by_type_breakdown(self, store):
        store.store(artefact_type="test_result", content="c", evidence_id="st1")
        store.store(artefact_type="test_result", content="c", evidence_id="st2")
        store.store(artefact_type="benchmark", content="c", evidence_id="st3")

        by_type = store.get_stats()["by_type"]
        assert by_type["test_result"] == 2
        assert by_type["benchmark"] == 1

    def test_total_queries_increments(self, store):
        store.query_by_type("t1")
        store.query_by_type("t2")
        store.query_by_pack("p1")
        assert store.get_stats()["total_queries"] == 3

    def test_by_type_empty_string_when_unspecified(self, store):
        store.store(content="c", evidence_id="set1")
        by_type = store.get_stats()["by_type"]
        assert "" in by_type
        assert by_type[""] == 1


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------

class TestEventEmission:

    def test_store_emits_event(self, store_with_bus):
        store, bus = store_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("evidence.stored", events.append)

        store.store(evidence_id="ev1", content="data", pack_id="p1")

        assert len(events) == 1
        evt = events[0]
        assert evt.topic == "evidence.stored"
        assert evt.payload["evidence_id"] == "ev1"
        assert evt.payload["pack_id"] == "p1"
        assert evt.payload["content_hash"] == _sha256("data")

    def test_delete_emits_event(self, store_with_bus):
        store, bus = store_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("evidence.deleted", events.append)

        store.store(evidence_id="evd1", content="c")
        store.delete("evd1")

        assert len(events) == 1
        assert events[0].topic == "evidence.deleted"
        assert events[0].payload["evidence_id"] == "evd1"

    def test_no_emit_on_delete_nonexistent(self, store_with_bus):
        store, bus = store_with_bus
        events: list[SylionEvent] = []
        bus.subscribe("evidence.deleted", events.append)

        store.delete("nonexistent")
        assert len(events) == 0

    def test_no_emit_without_event_bus(self, store):
        # Should not raise; event_bus is None
        store.store(evidence_id="noev", content="c")
        store.delete("noev")


# ---------------------------------------------------------------------------
# EvidenceSpine integration
# ---------------------------------------------------------------------------

class TestEvidenceSpineIntegration:

    def test_store_appends_to_spine(self, store_with_spine):
        store, spine = store_with_spine
        store.store(
            evidence_id="sp1",
            pack_id="pack-x",
            artefact_type="review",
            content="spine content",
        )

        entries = spine.query(source_plan="memory.evidence_store")
        assert len(entries) == 1
        e = entries[0]
        assert e["event_type"] == "evidence.stored"
        payload = json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"]
        assert payload["evidence_id"] == "sp1"
        assert payload["pack_id"] == "pack-x"
        assert payload["artefact_type"] == "review"
        assert payload["content_hash"] == _sha256("spine content")

    def test_no_spine_entry_when_spine_is_none(self, store):
        # store._evidence_spine is None; should not raise
        store.store(evidence_id="nosp", content="c")

    def test_multiple_stores_create_multiple_spine_entries(self, store_with_spine):
        store, spine = store_with_spine
        for i in range(3):
            store.store(evidence_id=f"ms{i}", content=f"c{i}")
        entries = spine.query(source_plan="memory.evidence_store")
        assert len(entries) == 3

    def test_spine_hash_chain_intact(self, store_with_spine):
        store, spine = store_with_spine
        store.store(evidence_id="hc1", content="first")
        store.store(evidence_id="hc2", content="second")

        entries = spine.query(source_plan="memory.evidence_store")
        assert entries[0]["hash"] == entries[1]["prev_hash"]


# ---------------------------------------------------------------------------
# Full integration: EventBus + EvidenceSpine together
# ---------------------------------------------------------------------------

class TestFullIntegration:

    def test_store_and_delete_both_emit_and_spine(self, store_with_bus_and_spine):
        store, bus, spine = store_with_bus_and_spine

        stored_events: list[SylionEvent] = []
        deleted_events: list[SylionEvent] = []
        bus.subscribe("evidence.stored", stored_events.append)
        bus.subscribe("evidence.deleted", deleted_events.append)

        store.store(evidence_id="fi1", pack_id="p1", artefact_type="test_result", content="data")
        store.delete("fi1")

        assert len(stored_events) == 1
        assert len(deleted_events) == 1
        spine_entries = spine.query(source_plan="memory.evidence_store")
        assert len(spine_entries) == 1  # only store appends to spine, not delete

    def test_crud_lifecycle(self, store):
        # Create
        r = store.store(
            evidence_id="lc1",
            pack_id="pack-lifecycle",
            artefact_type="screenshot",
            name="screen1",
            content="png-bytes",
            metadata={"resolution": "1920x1080"},
        )
        assert r["evidence_id"] == "lc1"

        # Read
        row = store.retrieve("lc1")
        assert row is not None
        assert row["name"] == "screen1"

        # Query by type
        results = store.query_by_type("screenshot")
        assert any(e["evidence_id"] == "lc1" for e in results)

        # Query by pack
        results = store.query_by_pack("pack-lifecycle")
        assert any(e["evidence_id"] == "lc1" for e in results)

        # Stats
        stats = store.get_stats()
        assert stats["total_evidence"] == 1
        assert stats["by_type"]["screenshot"] == 1

        # Delete
        assert store.delete("lc1") is True
        assert store.retrieve("lc1") is None
        assert store.get_stats()["total_evidence"] == 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_stores(self, store):
        n = 50
        errors: list[Exception] = []

        def worker(i: int):
            try:
                store.store(
                    evidence_id=f"ts_{i}",
                    pack_id=f"pack_{i % 5}",
                    artefact_type="test_result",
                    content=f"concurrent-{i}",
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert store.get_stats()["total_evidence"] == n

    def test_concurrent_store_and_delete(self, store):
        # Pre-populate
        for i in range(20):
            store.store(evidence_id=f"cd_{i}", content=f"c-{i}")

        errors: list[Exception] = []

        def deleter(i: int):
            try:
                store.delete(f"cd_{i}")
            except Exception as exc:
                errors.append(exc)

        def writer(i: int):
            try:
                store.store(evidence_id=f"cd_new_{i}", content=f"new-{i}")
            except Exception as exc:
                errors.append(exc)

        threads = (
            [threading.Thread(target=deleter, args=(i,)) for i in range(20)]
            + [threading.Thread(target=writer, args=(i,)) for i in range(20)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # All 20 new items should exist
        for i in range(20):
            assert store.retrieve(f"cd_new_{i}") is not None


# ---------------------------------------------------------------------------
# get_evidence_store() singleton
# ---------------------------------------------------------------------------

class TestGetEvidenceStore:

    def test_returns_evidence_store_instance(self):
        import sylion.memory.evidence_store as mod
        mod._store = None  # reset global
        s = get_evidence_store()
        assert isinstance(s, EvidenceStore)

    def test_singleton_returns_same_instance(self):
        import sylion.memory.evidence_store as mod
        mod._store = None
        s1 = get_evidence_store()
        s2 = get_evidence_store()
        assert s1 is s2

    def test_singleton_with_custom_db_path(self, tmp_path):
        import sylion.memory.evidence_store as mod
        mod._store = None
        db = tmp_path / "singleton.db"
        s = get_evidence_store(db_path=db)
        assert s._db_path == str(db)
        # Cleanup
        mod._store = None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_store_with_all_empty_strings(self, store):
        result = store.store()
        assert "evidence_id" in result
        assert "content_hash" in result
        row = store.retrieve(result["evidence_id"])
        assert row is not None

    def test_large_metadata(self, store):
        big_meta = {f"key_{i}": f"value_{i}" for i in range(100)}
        store.store(evidence_id="bigmeta", content="c", metadata=big_meta)
        row = store.retrieve("bigmeta")
        assert row is not None
        assert len(row["metadata"]) == 100

    def test_metadata_with_nested_structures(self, store):
        meta = {
            "nested": {"a": {"b": [1, 2, 3]}},
            "list": [{"x": 1}, {"x": 2}],
        }
        store.store(evidence_id="nested_meta", content="c", metadata=meta)
        row = store.retrieve("nested_meta")
        assert row["metadata"]["nested"]["a"]["b"] == [1, 2, 3]
        assert row["metadata"]["list"][0]["x"] == 1

    def test_special_characters_in_name(self, store):
        name = 'test with "quotes" and \'apostrophes\' and <html>'
        store.store(evidence_id="special_name", name=name, content="c")
        row = store.retrieve("special_name")
        assert row["name"] == name

    def test_very_long_content(self, store):
        content = "x" * 1_000_000
        result = store.store(evidence_id="long_content", content=content)
        row = store.retrieve("long_content")
        assert row["content"] == content
        assert row["content_hash"] == _sha256(content)

    def test_query_by_type_with_all_artefact_types(self, store):
        types = ["test_result", "benchmark", "review", "screenshot", "log", "contract"]
        for t in types:
            store.store(artefact_type=t, content=f"c-{t}", evidence_id=f"multi_{t}")

        for t in types:
            results = store.query_by_type(t)
            assert len(results) == 1
            assert results[0]["artefact_type"] == t

    def test_query_by_pack_returns_all_types(self, store):
        store.store(pack_id="mixed_pack", artefact_type="test_result", content="c1", evidence_id="mp1")
        store.store(pack_id="mixed_pack", artefact_type="benchmark", content="c2", evidence_id="mp2")
        store.store(pack_id="mixed_pack", artefact_type="review", content="c3", evidence_id="mp3")

        results = store.query_by_pack("mixed_pack")
        assert len(results) == 3
        types = {r["artefact_type"] for r in results}
        assert types == {"test_result", "benchmark", "review"}
