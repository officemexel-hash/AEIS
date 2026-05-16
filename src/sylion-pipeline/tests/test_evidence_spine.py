"""
Comprehensive tests for sylion.core.evidence_spine — EvidenceSpine class.
Tests: append, verify_chain, query, replay, hash chain integrity, edge cases.
"""
from __future__ import annotations

import json
import time
import threading

import pytest

from sylion.core.evidence_spine import (
    EvidenceSpine,
    EvidenceEntry,
    GENESIS_PREV_HASH,
    _compute_chain_hash,
    _canonical_json,
    get_evidence_spine,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _spine(bus: EventBus | None = None) -> EvidenceSpine:
    return EvidenceSpine(event_bus=bus)


def _entry(source_plan: str = "P01", event_type: str = "test.event",
           payload: dict | None = None, actor_id: str = "actor-1") -> EvidenceEntry:
    return EvidenceEntry(
        source_plan=source_plan,
        event_type=event_type,
        payload=payload or {},
        actor_id=actor_id,
    )


# ---------------------------------------------------------------------------
# EvidenceEntry dataclass
# ---------------------------------------------------------------------------

class TestEvidenceEntry:

    def test_auto_entry_id(self):
        e = EvidenceEntry(source_plan="P01", event_type="t")
        assert e.entry_id != ""

    def test_auto_timestamp(self):
        e = EvidenceEntry(source_plan="P01", event_type="t")
        assert e.timestamp > 0

    def test_explicit_fields(self):
        e = EvidenceEntry(
            source_plan="P02", event_type="custom", payload={"k": 1},
            actor_id="bob"
        )
        assert e.source_plan == "P02"
        assert e.event_type == "custom"
        assert e.payload == {"k": 1}
        assert e.actor_id == "bob"

    def test_default_payload_empty(self):
        e = EvidenceEntry(source_plan="P01", event_type="t")
        assert e.payload == {}

    def test_default_signature_empty(self):
        e = EvidenceEntry(source_plan="P01", event_type="t")
        assert e.signature == ""


# ---------------------------------------------------------------------------
# _canonical_json helper
# ---------------------------------------------------------------------------

class TestCanonicalJson:

    def test_sorted_keys(self):
        result = _canonical_json({"b": 2, "a": 1})
        assert result == '{"a":1,"b":2}'

    def test_compact_separators(self):
        result = _canonical_json({"x": 1})
        assert ": " not in result
        assert ", " not in result

    def test_nested_sorting(self):
        result = _canonical_json({"z": {"b": 1, "a": 2}})
        assert '"a":2' in result


# ---------------------------------------------------------------------------
# _compute_chain_hash helper
# ---------------------------------------------------------------------------

class TestComputeChainHash:

    def test_deterministic(self):
        h1 = _compute_chain_hash("id1", '{"a":1}', "prev", 100.0)
        h2 = _compute_chain_hash("id1", '{"a":1}', "prev", 100.0)
        assert h1 == h2

    def test_different_inputs_different_hash(self):
        h1 = _compute_chain_hash("id1", '{"a":1}', "prev", 100.0)
        h2 = _compute_chain_hash("id2", '{"a":1}', "prev", 100.0)
        assert h1 != h2

    def test_returns_64_char_hex(self):
        h = _compute_chain_hash("id", '{}', "0" * 64, 1.0)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------

class TestAppend:

    def test_append_returns_entry_info(self):
        sp = _spine()
        e = _entry()
        result = sp.append(e)
        assert "entry_id" in result
        assert "hash" in result
        assert "prev_hash" in result
        assert result["entry_id"] == e.entry_id

    def test_first_entry_has_genesis_prev_hash(self):
        sp = _spine()
        result = sp.append(_entry())
        assert result["prev_hash"] == GENESIS_PREV_HASH

    def test_second_entry_chains_from_first(self):
        sp = _spine()
        r1 = sp.append(_entry())
        r2 = sp.append(_entry())
        assert r2["prev_hash"] == r1["hash"]

    def test_append_multiple_entries(self):
        sp = _spine()
        for i in range(5):
            sp.append(_entry(payload={"i": i}))
        entries = sp.query()
        assert len(entries) == 5

    def test_append_sets_hash_on_entry(self):
        sp = _spine()
        e = _entry()
        sp.append(e)
        assert e.hash != ""
        assert e.prev_hash != ""

    def test_append_emits_event_to_bus(self):
        bus = EventBus()
        sp = _spine(bus=bus)
        sp.append(_entry())
        events = bus.query(topic="evidence.appended")
        assert len(events) == 1
        assert events[0]["source_module"] == "core.evidence_spine"

    def test_append_without_event_bus(self):
        sp = _spine(bus=None)
        result = sp.append(_entry())
        assert "hash" in result  # no crash


# ---------------------------------------------------------------------------
# verify_chain
# ---------------------------------------------------------------------------

class TestVerifyChain:

    def test_empty_spine_is_valid(self):
        sp = _spine()
        valid, msg = sp.verify_chain()
        assert valid is True
        assert "empty" in msg

    def test_single_entry_valid(self):
        sp = _spine()
        sp.append(_entry())
        valid, msg = sp.verify_chain()
        assert valid is True
        assert "1 entries" in msg

    def test_multi_entry_chain_valid(self):
        sp = _spine()
        for i in range(10):
            sp.append(_entry(payload={"i": i}))
        valid, msg = sp.verify_chain()
        assert valid is True
        assert "10 entries" in msg

    def test_chain_break_detection(self):
        sp = _spine()
        sp.append(_entry())
        sp.append(_entry())
        # Tamper with the second entry's hash directly in DB
        sp._conn.execute(
            "UPDATE evidence_spine SET hash = 'deadbeef' WHERE rowid = 2"
        )
        sp._conn.commit()
        valid, msg = sp.verify_chain()
        assert valid is False
        assert "hash mismatch" in msg

    def test_prev_hash_break_detection(self):
        sp = _spine()
        sp.append(_entry())
        sp.append(_entry())
        sp._conn.execute(
            "UPDATE evidence_spine SET prev_hash = 'tampered' WHERE rowid = 2"
        )
        sp._conn.commit()
        valid, msg = sp.verify_chain()
        assert valid is False
        assert "chain break" in msg


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

class TestQuery:

    def test_query_all(self):
        sp = _spine()
        sp.append(_entry(source_plan="P01"))
        sp.append(_entry(source_plan="P02"))
        results = sp.query()
        assert len(results) == 2

    def test_query_by_source_plan(self):
        sp = _spine()
        sp.append(_entry(source_plan="P01"))
        sp.append(_entry(source_plan="P02"))
        sp.append(_entry(source_plan="P01"))
        results = sp.query(source_plan="P01")
        assert len(results) == 2

    def test_query_by_event_type(self):
        sp = _spine()
        sp.append(_entry(event_type="type.a"))
        sp.append(_entry(event_type="type.b"))
        results = sp.query(event_type="type.a")
        assert len(results) == 1

    def test_query_by_since(self):
        sp = _spine()
        sp.append(_entry())
        cutoff = time.time() + 0.001
        time.sleep(0.01)
        sp.append(_entry())
        results = sp.query(since=cutoff)
        assert len(results) == 1

    def test_query_limit(self):
        sp = _spine()
        for i in range(20):
            sp.append(_entry())
        results = sp.query(limit=5)
        assert len(results) == 5

    def test_query_ordered_by_timestamp_asc(self):
        sp = _spine()
        sp.append(_entry(payload={"order": 1}))
        time.sleep(0.01)
        sp.append(_entry(payload={"order": 2}))
        results = sp.query()
        assert results[0]["timestamp"] <= results[1]["timestamp"]

    def test_query_combined_filters(self):
        sp = _spine()
        sp.append(_entry(source_plan="P01", event_type="x"))
        sp.append(_entry(source_plan="P01", event_type="y"))
        sp.append(_entry(source_plan="P02", event_type="x"))
        results = sp.query(source_plan="P01", event_type="x")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

class TestReplay:

    def test_replay_all(self):
        sp = _spine()
        sp.append(_entry())
        sp.append(_entry())
        results = sp.replay()
        assert len(results) == 2

    def test_replay_since(self):
        sp = _spine()
        sp.append(_entry())
        cutoff = time.time() + 0.001
        time.sleep(0.01)
        sp.append(_entry())
        results = sp.replay(since=cutoff)
        assert len(results) == 1

    def test_replay_empty(self):
        sp = _spine()
        results = sp.replay()
        assert results == []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_evidence_spine_returns_instance(self):
        import sylion.core.evidence_spine as mod
        mod._spine = None
        spine = get_evidence_spine()
        assert isinstance(spine, EvidenceSpine)
        mod._spine = None


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:

    def test_concurrent_append_no_crash(self):
        """Concurrent appends must not crash. Chain integrity under true
        concurrency is not guaranteed by the SQLite implementation (see
        BEGIN IMMEDIATE race on _get_last_hash). This test verifies
        thread-safety against exceptions only."""
        sp = _spine()
        errors = []

        def append_n(n):
            try:
                for i in range(20):
                    sp.append(_entry(
                        source_plan=f"P{n}",
                        payload={"i": i},
                    ))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=append_n, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        entries = sp.query(limit=1000)
        assert len(entries) == 100

    def test_sequential_append_chain_valid(self):
        """Sequential appends always produce a valid chain."""
        sp = _spine()
        for i in range(50):
            sp.append(_entry(payload={"i": i}))
        valid, msg = sp.verify_chain()
        assert valid is True
        assert "50 entries" in msg
