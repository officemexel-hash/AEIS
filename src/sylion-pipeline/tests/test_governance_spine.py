"""Comprehensive tests for sylion.governance.evidence_spine (GovernanceSpine)."""

import hashlib
import json
import sqlite3
import threading
import time

import pytest

from sylion.governance.evidence_spine import (
    GENESIS_PREV_HASH,
    GovernanceSpine,
    get_governance_spine,
    reset_governance_spine,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spine():
    """Fresh in-memory GovernanceSpine per test."""
    return GovernanceSpine()


@pytest.fixture
def populated_spine(spine):
    """Spine with several entries across different decisions."""
    entries = []
    for i in range(5):
        content = f"content-{i}"
        chash = hashlib.sha256(content.encode()).hexdigest()
        result = spine.append_entry(
            decision_id=f"dec-{i % 3}",
            entry_type=["decision", "gate_evaluation", "code_change", "cascade", "decision"][i],
            content_hash=chash,
            snapshot_id=f"snap-{i}" if i % 2 == 0 else None,
            metadata={"idx": i},
        )
        entries.append(result)
    return spine, entries


# ---------------------------------------------------------------------------
# Genesis hash
# ---------------------------------------------------------------------------

class TestGenesis:
    def test_genesis_hash_is_64_zeros(self):
        assert GENESIS_PREV_HASH == "0" * 64
        assert len(GENESIS_PREV_HASH) == 64


# ---------------------------------------------------------------------------
# Append entries
# ---------------------------------------------------------------------------

class TestAppendEntry:
    def test_append_creates_entry(self, spine):
        result = spine.append_entry(
            decision_id="dec-1",
            entry_type="decision",
            content_hash=hashlib.sha256(b"abc").hexdigest(),
        )
        assert "entry_id" in result
        assert result["decision_id"] == "dec-1"
        assert result["entry_type"] == "decision"

    def test_append_returns_entry_hash(self, spine):
        result = spine.append_entry(
            decision_id="dec-1",
            entry_type="decision",
            content_hash="chash1",
        )
        assert result["entry_hash"] != ""
        assert len(result["entry_hash"]) == 64

    def test_append_first_entry_has_genesis_prev(self, spine):
        result = spine.append_entry(
            decision_id="dec-1",
            entry_type="decision",
            content_hash="chash1",
        )
        assert result["prev_hash"] == GENESIS_PREV_HASH

    def test_append_second_entry_chains_to_first(self, spine):
        r1 = spine.append_entry(
            decision_id="dec-1", entry_type="decision", content_hash="chash1",
        )
        r2 = spine.append_entry(
            decision_id="dec-2", entry_type="gate_evaluation", content_hash="chash2",
        )
        assert r2["prev_hash"] == r1["entry_hash"]

    def test_append_increments_sequence(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        r2 = spine.append_entry(decision_id="d2", entry_type="decision", content_hash="c2")
        r3 = spine.append_entry(decision_id="d3", entry_type="decision", content_hash="c3")
        assert r1["sequence_num"] == 1
        assert r2["sequence_num"] == 2
        assert r3["sequence_num"] == 3

    def test_append_with_snapshot_id(self, spine):
        result = spine.append_entry(
            decision_id="d1", entry_type="decision",
            content_hash="c1", snapshot_id="snap-42",
        )
        assert result["snapshot_id"] == "snap-42"

    def test_append_with_module_states_hash(self, spine):
        result = spine.append_entry(
            decision_id="d1", entry_type="decision",
            content_hash="c1", module_states_hash="mshash",
        )
        entry = spine.get_entry(result["entry_id"])
        assert entry["module_states_hash"] == "mshash"

    def test_append_with_evidence_pack(self, spine):
        ep = [{"artefact": "test_result", "hash": "abc123"}]
        result = spine.append_entry(
            decision_id="d1", entry_type="decision",
            content_hash="c1", evidence_pack=ep,
        )
        entry = spine.get_entry(result["entry_id"])
        assert entry["evidence_pack"] == ep

    def test_append_with_metadata(self, spine):
        meta = {"source": "planner", "confidence": 0.95}
        result = spine.append_entry(
            decision_id="d1", entry_type="decision",
            content_hash="c1", metadata=meta,
        )
        entry = spine.get_entry(result["entry_id"])
        assert entry["metadata"]["source"] == "planner"

    def test_append_rejects_invalid_entry_type(self, spine):
        with pytest.raises(ValueError, match="Invalid entry_type"):
            spine.append_entry(
                decision_id="d1", entry_type="invalid_type",
                content_hash="c1",
            )

    def test_append_all_valid_entry_types(self, spine):
        for i, etype in enumerate(["decision", "gate_evaluation", "code_change", "cascade"]):
            result = spine.append_entry(
                decision_id="d1", entry_type=etype,
                content_hash=f"c{i}",
            )
            assert result["entry_type"] == etype

    def test_append_sets_created_at(self, spine):
        before = time.time()
        result = spine.append_entry(
            decision_id="d1", entry_type="decision", content_hash="c1",
        )
        after = time.time()
        assert before <= result["created_at"] <= after


# ---------------------------------------------------------------------------
# Hash linking correctness
# ---------------------------------------------------------------------------

class TestHashLinking:
    def test_entry_hash_is_sha256(self, spine):
        result = spine.append_entry(
            decision_id="d1", entry_type="decision", content_hash="c1",
        )
        entry = spine.get_entry(result["entry_id"])
        expected = hashlib.sha256(
            f"{GENESIS_PREV_HASH}|c1|d1|{entry['created_at']}".encode("utf-8")
        ).hexdigest()
        assert entry["entry_hash"] == expected

    def test_chain_of_three_hashes_link(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        r2 = spine.append_entry(decision_id="d2", entry_type="gate_evaluation", content_hash="c2")
        r3 = spine.append_entry(decision_id="d3", entry_type="code_change", content_hash="c3")

        e2 = spine.get_entry(r2["entry_id"])
        e3 = spine.get_entry(r3["entry_id"])

        assert e2["prev_hash"] == r1["entry_hash"]
        assert e3["prev_hash"] == r2["entry_hash"]

    def test_hash_changes_with_different_content(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="aaa")
        r2 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="bbb")
        assert r1["entry_hash"] != r2["entry_hash"]

    def test_hash_changes_with_different_decision_id(self, spine):
        r1 = spine.append_entry(decision_id="da", entry_type="decision", content_hash="c1")
        r2 = spine.append_entry(decision_id="db", entry_type="decision", content_hash="c1")
        assert r1["entry_hash"] != r2["entry_hash"]


# ---------------------------------------------------------------------------
# Sequence numbers
# ---------------------------------------------------------------------------

class TestSequenceNumbers:
    def test_starts_at_one(self, spine):
        r = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        assert r["sequence_num"] == 1

    def test_monotonically_increases(self, spine):
        results = []
        for i in range(10):
            r = spine.append_entry(decision_id=f"d{i}", entry_type="decision", content_hash=f"c{i}")
            results.append(r)
        seqs = [r["sequence_num"] for r in results]
        assert seqs == list(range(1, 11))


# ---------------------------------------------------------------------------
# Verify chain
# ---------------------------------------------------------------------------

class TestVerifyChain:
    def test_verify_empty_chain(self, spine):
        result = spine.verify_chain()
        assert result["valid"] is True
        assert result["broken_at"] is None
        assert result["total_entries"] == 0
        assert result["tampered_count"] == 0

    def test_verify_single_entry(self, spine):
        spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        result = spine.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 1

    def test_verify_multiple_entries(self, populated_spine):
        spine, _ = populated_spine
        result = spine.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 5

    def test_verify_detects_prev_hash_tampering(self, spine):
        spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        r2 = spine.append_entry(decision_id="d2", entry_type="decision", content_hash="c2")

        spine._conn.execute(
            "UPDATE spine_entries SET prev_hash = ? WHERE entry_id = ?",
            ("tampered!", r2["entry_id"]),
        )
        spine._conn.commit()

        result = spine.verify_chain()
        assert result["valid"] is False
        assert result["broken_at"] == r2["entry_id"]
        assert result["tampered_count"] >= 1

    def test_verify_detects_entry_hash_tampering(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")

        spine._conn.execute(
            "UPDATE spine_entries SET entry_hash = ? WHERE entry_id = ?",
            ("0" * 64, r1["entry_id"]),
        )
        spine._conn.commit()

        result = spine.verify_chain()
        assert result["valid"] is False
        assert result["broken_at"] == r1["entry_id"]

    def test_verify_marks_tampered_flag(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        spine._conn.execute(
            "UPDATE spine_entries SET entry_hash = 'x' WHERE entry_id = ?",
            (r1["entry_id"],),
        )
        spine._conn.commit()

        spine.verify_chain()

        entry = spine.get_entry(r1["entry_id"])
        assert entry["tampered"] == 1


# ---------------------------------------------------------------------------
# Get spine range
# ---------------------------------------------------------------------------

class TestGetSpine:
    def test_get_full_spine(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine()
        assert len(results) == 5

    def test_get_spine_from_seq(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine(from_seq=3)
        assert len(results) == 3
        assert results[0]["sequence_num"] == 3

    def test_get_spine_to_seq(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine(to_seq=2)
        assert len(results) == 2

    def test_get_spine_range(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine(from_seq=2, to_seq=4)
        assert len(results) == 3
        seqs = [r["sequence_num"] for r in results]
        assert seqs == [2, 3, 4]

    def test_get_spine_by_entry_type(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine(entry_type="decision")
        assert all(r["entry_type"] == "decision" for r in results)
        assert len(results) >= 1

    def test_get_spine_empty(self, spine):
        results = spine.get_spine()
        assert results == []

    def test_get_spine_ordered_by_sequence(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_spine()
        seqs = [r["sequence_num"] for r in results]
        assert seqs == sorted(seqs)


# ---------------------------------------------------------------------------
# Get single entry
# ---------------------------------------------------------------------------

class TestGetEntry:
    def test_get_existing_entry(self, spine):
        r = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        entry = spine.get_entry(r["entry_id"])
        assert entry is not None
        assert entry["entry_id"] == r["entry_id"]

    def test_get_nonexistent_entry(self, spine):
        entry = spine.get_entry("does-not-exist")
        assert entry is None

    def test_get_entry_has_all_fields(self, spine):
        r = spine.append_entry(
            decision_id="d1", entry_type="decision", content_hash="c1",
            snapshot_id="snap-1", module_states_hash="mshash",
            metadata={"key": "val"},
        )
        entry = spine.get_entry(r["entry_id"])
        assert entry["decision_id"] == "d1"
        assert entry["entry_type"] == "decision"
        assert entry["content_hash"] == "c1"
        assert entry["snapshot_id"] == "snap-1"
        assert entry["module_states_hash"] == "mshash"
        assert entry["metadata"]["key"] == "val"
        assert entry["sequence_num"] == 1
        assert entry["verified"] == 0
        assert entry["tampered"] == 0


# ---------------------------------------------------------------------------
# Get entries for decision
# ---------------------------------------------------------------------------

class TestGetEntriesForDecision:
    def test_returns_entries_for_decision(self, populated_spine):
        spine, entries = populated_spine
        results = spine.get_entries_for_decision("dec-0")
        assert len(results) == 2
        assert all(r["decision_id"] == "dec-0" for r in results)

    def test_returns_empty_for_unknown_decision(self, spine):
        results = spine.get_entries_for_decision("nonexistent")
        assert results == []

    def test_ordered_by_sequence(self, populated_spine):
        spine, _ = populated_spine
        results = spine.get_entries_for_decision("dec-0")
        seqs = [r["sequence_num"] for r in results]
        assert seqs == sorted(seqs)


# ---------------------------------------------------------------------------
# Mark verified
# ---------------------------------------------------------------------------

class TestMarkVerified:
    def test_mark_verified_success(self, spine):
        r = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        result = spine.mark_verified(r["entry_id"])
        assert result is not None
        assert result["verified"] is True
        assert result["verified_at"] > 0

    def test_mark_verified_persists(self, spine):
        r = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        spine.mark_verified(r["entry_id"])
        entry = spine.get_entry(r["entry_id"])
        assert entry["verified"] == 1
        assert entry["verified_at"] is not None

    def test_mark_verified_nonexistent(self, spine):
        result = spine.mark_verified("does-not-exist")
        assert result is None


# ---------------------------------------------------------------------------
# Chain stats
# ---------------------------------------------------------------------------

class TestChainStats:
    def test_empty_spine_stats(self, spine):
        stats = spine.get_chain_stats()
        assert stats["total_entries"] == 0
        assert stats["chain_valid"] is True
        assert stats["last_entry_hash"] == GENESIS_PREV_HASH
        assert stats["last_sequence"] == 0

    def test_stats_after_entries(self, populated_spine):
        spine, entries = populated_spine
        stats = spine.get_chain_stats()
        assert stats["total_entries"] == 5
        assert stats["chain_valid"] is True
        assert stats["last_entry_hash"] == entries[-1]["entry_hash"]
        assert stats["last_sequence"] == 5

    def test_stats_after_tampering(self, spine):
        r1 = spine.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")
        spine._conn.execute(
            "UPDATE spine_entries SET entry_hash = 'x' WHERE entry_id = ?",
            (r1["entry_id"],),
        )
        spine._conn.commit()

        stats = spine.get_chain_stats()
        assert stats["chain_valid"] is False


# ---------------------------------------------------------------------------
# Singleton pattern
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_instance(self):
        inst = get_governance_spine()
        assert isinstance(inst, GovernanceSpine)

    def test_get_idempotent(self):
        a = get_governance_spine()
        b = get_governance_spine()
        assert a is b

    def test_reset_creates_new_instance(self):
        a = get_governance_spine()
        b = reset_governance_spine()
        assert a is not b
        assert isinstance(b, GovernanceSpine)


# ---------------------------------------------------------------------------
# Event bus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_append_emits_event(self):
        published = []

        class MockBus:
            def publish(self, event):
                published.append(event)

        sp = GovernanceSpine(event_bus=MockBus())
        sp.append_entry(decision_id="d1", entry_type="decision", content_hash="c1")

        assert len(published) == 1
        assert published[0].topic == "governance.spine.appended"
        assert published[0].payload["decision_id"] == "d1"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_appends(self, spine):
        errors = []
        results = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def append_one(idx):
            for attempt in range(8):
                try:
                    r = spine.append_entry(
                        decision_id=f"d-{idx}",
                        entry_type="decision",
                        content_hash=f"c-{idx}",
                    )
                    results.append(r)
                    return
                except retriable:
                    if attempt == 7:
                        errors.append(RuntimeError(f"gave up at {idx}"))
                    time.sleep(0.05 * (2 ** attempt))
                except Exception as e:
                    errors.append(e)
                    return

        threads = [threading.Thread(target=append_one, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(results) == 20

        verification = spine.verify_chain()
        assert verification["valid"] is True
        assert verification["total_entries"] == 20

    def test_concurrent_reads_and_writes(self, spine):
        errors = []
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def writer():
            for i in range(10):
                for attempt in range(8):
                    try:
                        spine.append_entry(
                            decision_id=f"d-w{i}",
                            entry_type="decision",
                            content_hash=f"c-w{i}",
                        )
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError(f"writer gave up at {i}"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        def reader():
            for _ in range(10):
                for attempt in range(8):
                    try:
                        spine.get_spine()
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError("reader gave up"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors
        rows = spine.get_spine()
        assert len(rows) >= 20


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_large_chain_integrity(self, spine):
        for i in range(100):
            spine.append_entry(
                decision_id=f"d-{i % 10}",
                entry_type="decision",
                content_hash=hashlib.sha256(f"c-{i}".encode()).hexdigest(),
            )
        result = spine.verify_chain()
        assert result["valid"] is True
        assert result["total_entries"] == 100

    def test_none_optional_fields(self, spine):
        r = spine.append_entry(
            decision_id="d1", entry_type="decision", content_hash="c1",
        )
        entry = spine.get_entry(r["entry_id"])
        assert entry["snapshot_id"] is None
        assert entry["module_states_hash"] is None
        assert entry["evidence_pack"] is None
        assert entry["metadata"] is None

    def test_unicode_in_metadata(self, spine):
        meta = {"note": "cafe\u0301", "cn": "\u4f60\u597d"}
        r = spine.append_entry(
            decision_id="d1", entry_type="decision",
            content_hash="c1", metadata=meta,
        )
        entry = spine.get_entry(r["entry_id"])
        assert entry["metadata"]["note"] == "cafe\u0301"
        assert entry["metadata"]["cn"] == "\u4f60\u597d"

    def test_multiple_entries_same_decision(self, spine):
        for i in range(5):
            spine.append_entry(
                decision_id="same-decision",
                entry_type=["decision", "gate_evaluation", "code_change", "cascade", "decision"][i],
                content_hash=f"c{i}",
            )
        entries = spine.get_entries_for_decision("same-decision")
        assert len(entries) == 5
        types = [e["entry_type"] for e in entries]
        assert types == ["decision", "gate_evaluation", "code_change", "cascade", "decision"]
