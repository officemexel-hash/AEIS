"""
Tests for sylion.aeis.evidence_pack — EvidencePackCollector

Covers: create_pack, add_*_evidence, get_pack, list_packs,
verify_pack_integrity, seal_pack, get_stats, thread safety,
edge cases, and event emission.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.aeis.evidence_pack import (
    EvidenceItem,
    EvidencePack,
    EvidencePackCollector,
    _compute_checksum,
    _compute_integrity_hash,
    get_evidence_pack_collector,
)
from sylion.core.event_bus import EventBus, SylionEvent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def collector(bus):
    return EvidencePackCollector(event_bus=bus)


@pytest.fixture
def sealed_pack(collector):
    """Pre-built pack with one item, sealed."""
    r = collector.create_pack("D3", {"scope": "test"})
    pack_id = r["pack_id"]
    collector.add_observation_evidence(pack_id, {"metric": "cpu", "value": 0.8})
    collector.seal_pack(pack_id)
    return pack_id


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class TestEvidenceItem:
    def test_defaults(self):
        item = EvidenceItem()
        assert item.item_id
        assert item.timestamp > 0
        assert item.checksum

    def test_auto_fields(self):
        item = EvidenceItem(pack_id="abc", evidence_type="observation",
                            data={"k": 1}, timestamp=100.0)
        assert item.item_id
        assert item.checksum


class TestEvidencePack:
    def test_defaults(self):
        pack = EvidencePack()
        assert pack.pack_id
        assert pack.created_at > 0
        assert pack.sealed == 0

    def test_custom_fields(self):
        pack = EvidencePack(decision_class="D4", context={"x": 1},
                            created_at=50.0)
        assert pack.decision_class == "D4"
        assert pack.context == {"x": 1}


# ---------------------------------------------------------------------------
# create_pack
# ---------------------------------------------------------------------------

class TestCreatePack:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        assert "pack_id" in r
        assert r["decision_class"] == "D3"
        assert r["created_at"] > 0

    def test_with_context(self, collector):
        r = collector.create_pack("D4", {"module": "kernel", "risk": "high"})
        pack = collector.get_pack(r["pack_id"])
        assert pack["context"]["module"] == "kernel"
        assert pack["context"]["risk"] == "high"

    def test_empty_context(self, collector):
        r = collector.create_pack("D2")
        pack = collector.get_pack(r["pack_id"])
        assert pack["context"] == {}

    def test_emits_event(self, collector, bus):
        events = []
        bus.subscribe("aeis.evidence_pack.created", events.append)
        collector.create_pack("D5")
        assert len(events) == 1
        assert events[0].payload["decision_class"] == "D5"

    def test_unique_pack_ids(self, collector):
        ids = set()
        for _ in range(50):
            r = collector.create_pack("D3")
            ids.add(r["pack_id"])
        assert len(ids) == 50


# ---------------------------------------------------------------------------
# add_observation_evidence
# ---------------------------------------------------------------------------

class TestAddObservationEvidence:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        item = collector.add_observation_evidence(r["pack_id"], {
            "metric": "latency", "value": 42.0, "unit": "ms",
        })
        assert item["evidence_type"] == "observation"
        assert item["pack_id"] == r["pack_id"]
        assert item["checksum"]

    def test_emits_event(self, collector, bus):
        events = []
        bus.subscribe("aeis.evidence_pack.item_added", events.append)
        r = collector.create_pack("D3")
        collector.add_observation_evidence(r["pack_id"], {"m": "v"})
        assert len(events) == 1
        assert events[0].payload["evidence_type"] == "observation"

    def test_rejects_sealed_pack(self, collector, sealed_pack):
        with pytest.raises(ValueError, match="sealed"):
            collector.add_observation_evidence(sealed_pack, {"x": 1})

    def test_rejects_missing_pack(self, collector):
        with pytest.raises(ValueError, match="not found"):
            collector.add_observation_evidence("nonexistent", {"x": 1})


# ---------------------------------------------------------------------------
# add_proposal_evidence
# ---------------------------------------------------------------------------

class TestAddProposalEvidence:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        item = collector.add_proposal_evidence(r["pack_id"], {
            "title": "Optimize DB", "priority": 5,
        })
        assert item["evidence_type"] == "proposal"
        assert item["item_id"]

    def test_source_is_improvement_queue(self, collector):
        r = collector.create_pack("D3")
        collector.add_proposal_evidence(r["pack_id"], {"title": "t"})
        pack = collector.get_pack(r["pack_id"])
        assert pack["items"][0]["source"] == "improvement_queue"


# ---------------------------------------------------------------------------
# add_validation_evidence
# ---------------------------------------------------------------------------

class TestAddValidationEvidence:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        item = collector.add_validation_evidence(r["pack_id"], {
            "explanation_id": "abc", "verdict": "approved",
        })
        assert item["evidence_type"] == "validation"

    def test_source_is_self_explanation(self, collector):
        r = collector.create_pack("D3")
        collector.add_validation_evidence(r["pack_id"], {"v": "ok"})
        pack = collector.get_pack(r["pack_id"])
        assert pack["items"][0]["source"] == "self_explanation"


# ---------------------------------------------------------------------------
# add_boundary_evidence
# ---------------------------------------------------------------------------

class TestAddBoundaryEvidence:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        item = collector.add_boundary_evidence(r["pack_id"], {
            "scope": "api.call", "allowed": True,
        })
        assert item["evidence_type"] == "boundary"

    def test_source_is_self_limitation(self, collector):
        r = collector.create_pack("D3")
        collector.add_boundary_evidence(r["pack_id"], {"s": "x"})
        pack = collector.get_pack(r["pack_id"])
        assert pack["items"][0]["source"] == "self_limitation"


# ---------------------------------------------------------------------------
# get_pack
# ---------------------------------------------------------------------------

class TestGetPack:
    def test_full_pack(self, collector):
        r = collector.create_pack("D3", {"zone": "us-east"})
        pid = r["pack_id"]
        collector.add_observation_evidence(pid, {"m": "cpu"})
        collector.add_proposal_evidence(pid, {"title": "t"})
        collector.add_validation_evidence(pid, {"v": "ok"})
        collector.add_boundary_evidence(pid, {"s": "api"})

        pack = collector.get_pack(pid)
        assert pack is not None
        assert pack["decision_class"] == "D3"
        assert pack["context"]["zone"] == "us-east"
        assert len(pack["items"]) == 4

    def test_returns_none_for_missing(self, collector):
        assert collector.get_pack("nonexistent") is None

    def test_empty_pack_has_no_items(self, collector):
        r = collector.create_pack("D2")
        pack = collector.get_pack(r["pack_id"])
        assert pack["items"] == []

    def test_items_ordered_by_timestamp(self, collector):
        r = collector.create_pack("D3")
        pid = r["pack_id"]
        collector.add_observation_evidence(pid, {"order": 1})
        collector.add_proposal_evidence(pid, {"order": 2})
        collector.add_boundary_evidence(pid, {"order": 3})
        pack = collector.get_pack(pid)
        types = [i["evidence_type"] for i in pack["items"]]
        assert types == ["observation", "proposal", "boundary"]


# ---------------------------------------------------------------------------
# list_packs
# ---------------------------------------------------------------------------

class TestListPacks:
    def test_all_packs(self, collector):
        collector.create_pack("D3")
        collector.create_pack("D4")
        packs = collector.list_packs()
        assert len(packs) == 2

    def test_filter_by_class(self, collector):
        collector.create_pack("D3")
        collector.create_pack("D3")
        collector.create_pack("D4")
        packs = collector.list_packs(decision_class="D3")
        assert len(packs) == 2
        assert all(p["decision_class"] == "D3" for p in packs)

    def test_empty_result(self, collector):
        packs = collector.list_packs(decision_class="D0")
        assert packs == []

    def test_limit(self, collector):
        for i in range(10):
            collector.create_pack("D3", {"i": i})
        packs = collector.list_packs(limit=3)
        assert len(packs) == 3

    def test_context_parsed(self, collector):
        collector.create_pack("D3", {"k": "v"})
        packs = collector.list_packs()
        assert packs[0]["context"]["k"] == "v"


# ---------------------------------------------------------------------------
# verify_pack_integrity
# ---------------------------------------------------------------------------

class TestVerifyPackIntegrity:
    def test_valid_pack(self, collector):
        r = collector.create_pack("D3")
        pid = r["pack_id"]
        collector.add_observation_evidence(pid, {"m": "cpu", "v": 0.9})
        collector.add_proposal_evidence(pid, {"title": "fix"})

        result = collector.verify_pack_integrity(pid)
        assert result["valid"] is True
        assert result["item_count"] == 2
        assert result["mismatches"] == []

    def test_missing_pack(self, collector):
        result = collector.verify_pack_integrity("nonexistent")
        assert result["valid"] is False
        assert "error" in result

    def test_sealed_pack_integrity(self, collector, sealed_pack):
        result = collector.verify_pack_integrity(sealed_pack)
        assert result["valid"] is True

    def test_empty_pack_is_valid(self, collector):
        r = collector.create_pack("D2")
        result = collector.verify_pack_integrity(r["pack_id"])
        assert result["valid"] is True
        assert result["item_count"] == 0


# ---------------------------------------------------------------------------
# seal_pack
# ---------------------------------------------------------------------------

class TestSealPack:
    def test_basic(self, collector):
        r = collector.create_pack("D3")
        pid = r["pack_id"]
        collector.add_observation_evidence(pid, {"m": "x"})

        sealed = collector.seal_pack(pid)
        assert sealed["pack_id"] == pid
        assert sealed["integrity_hash"]
        assert sealed["sealed_at"] > 0

        pack = collector.get_pack(pid)
        assert pack["sealed"] == 1

    def test_double_seal_raises(self, collector, sealed_pack):
        with pytest.raises(ValueError, match="already sealed"):
            collector.seal_pack(sealed_pack)

    def test_missing_pack_raises(self, collector):
        with pytest.raises(ValueError, match="not found"):
            collector.seal_pack("nonexistent")

    def test_sealed_pack_rejects_items(self, collector, sealed_pack):
        with pytest.raises(ValueError, match="sealed"):
            collector.add_observation_evidence(sealed_pack, {"x": 1})

    def test_emits_sealed_event(self, collector, bus):
        events = []
        bus.subscribe("aeis.evidence_pack.sealed", events.append)
        r = collector.create_pack("D3")
        collector.seal_pack(r["pack_id"])
        assert len(events) == 1
        assert events[0].payload["integrity_hash"]


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty(self, collector):
        stats = collector.get_stats()
        assert stats["total_packs"] == 0
        assert stats["total_items"] == 0

    def test_after_operations(self, collector):
        r1 = collector.create_pack("D3")
        r2 = collector.create_pack("D4")
        collector.add_observation_evidence(r1["pack_id"], {"m": 1})
        collector.add_proposal_evidence(r1["pack_id"], {"t": 2})
        collector.add_validation_evidence(r2["pack_id"], {"v": 3})
        collector.add_boundary_evidence(r2["pack_id"], {"b": 4})
        collector.seal_pack(r1["pack_id"])

        stats = collector.get_stats()
        assert stats["total_packs"] == 2
        assert stats["total_items"] == 4
        assert stats["sealed_count"] == 1
        assert stats["open_count"] == 1
        assert stats["by_decision_class"]["D3"] == 1
        assert stats["by_decision_class"]["D4"] == 1
        assert stats["by_evidence_type"]["observation"] == 1
        assert stats["by_evidence_type"]["proposal"] == 1
        assert stats["by_evidence_type"]["validation"] == 1
        assert stats["by_evidence_type"]["boundary"] == 1


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_create_and_add(self, collector):
        """Many threads creating packs and adding items simultaneously."""
        errors: list[Exception] = []

        def worker(idx):
            try:
                r = collector.create_pack("D3", {"thread": idx})
                pid = r["pack_id"]
                for j in range(5):
                    collector.add_observation_evidence(
                        pid, {"thread": idx, "item": j},
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        stats = collector.get_stats()
        assert stats["total_packs"] == 10
        assert stats["total_items"] == 50

    def test_concurrent_seal(self, collector):
        """Only one thread should successfully seal a pack."""
        r = collector.create_pack("D3")
        pid = r["pack_id"]
        collector.add_observation_evidence(pid, {"m": 1})

        results: list[str] = []
        errors: list[Exception] = []

        def sealer():
            try:
                collector.seal_pack(pid)
                results.append("ok")
            except ValueError:
                errors.append("already sealed")

        threads = [threading.Thread(target=sealer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one successful seal
        assert len(results) == 1
        assert len(errors) == 4


# ---------------------------------------------------------------------------
# Checksum helpers
# ---------------------------------------------------------------------------

class TestChecksumHelpers:
    def test_compute_checksum_deterministic(self):
        c1 = _compute_checksum("p1", "obs", {"a": 1}, 100.0)
        c2 = _compute_checksum("p1", "obs", {"a": 1}, 100.0)
        assert c1 == c2

    def test_compute_checksum_differs_for_different_data(self):
        c1 = _compute_checksum("p1", "obs", {"a": 1}, 100.0)
        c2 = _compute_checksum("p1", "obs", {"a": 2}, 100.0)
        assert c1 != c2

    def test_compute_integrity_hash_deterministic(self):
        h1 = _compute_integrity_hash("p1", '[{"a":1}]', 50.0)
        h2 = _compute_integrity_hash("p1", '[{"a":1}]', 50.0)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_evidence_pack_collector_returns_instance(self):
        c = get_evidence_pack_collector()
        assert isinstance(c, EvidencePackCollector)

    def test_singleton_identity(self):
        c1 = get_evidence_pack_collector()
        c2 = get_evidence_pack_collector()
        assert c1 is c2


# ---------------------------------------------------------------------------
# Integration-style: full workflow
# ---------------------------------------------------------------------------

class TestFullWorkflow:
    def test_collect_seal_verify(self, collector):
        """End-to-end: create, populate, seal, verify."""
        r = collector.create_pack("D3", {"system": "sylion"})
        pid = r["pack_id"]

        collector.add_observation_evidence(pid, {
            "metric": "memory_mb", "value": 512.0, "unit": "MB",
        })
        collector.add_proposal_evidence(pid, {
            "improvement_id": "imp01", "title": "Reduce memory",
            "priority": 8,
        })
        collector.add_validation_evidence(pid, {
            "explanation_id": "expl01", "verdict": "approved",
            "confidence": 0.92,
        })
        collector.add_boundary_evidence(pid, {
            "scope": "api.call", "allowed": True,
            "remaining": 45,
        })

        # Before sealing: 4 items
        pack = collector.get_pack(pid)
        assert len(pack["items"]) == 4
        assert pack["sealed"] == 0

        # Seal
        sealed = collector.seal_pack(pid)
        assert sealed["integrity_hash"]

        # Verify integrity
        integrity = collector.verify_pack_integrity(pid)
        assert integrity["valid"] is True
        assert integrity["item_count"] == 4

        # Cannot add more items
        with pytest.raises(ValueError, match="sealed"):
            collector.add_observation_evidence(pid, {"m": "late"})

    def test_multiple_packs_independent(self, collector):
        """Packs are independent containers."""
        r1 = collector.create_pack("D3")
        r2 = collector.create_pack("D4")
        collector.add_observation_evidence(r1["pack_id"], {"m": 1})
        collector.add_proposal_evidence(r2["pack_id"], {"t": 2})

        p1 = collector.get_pack(r1["pack_id"])
        p2 = collector.get_pack(r2["pack_id"])

        assert len(p1["items"]) == 1
        assert p1["items"][0]["evidence_type"] == "observation"
        assert len(p2["items"]) == 1
        assert p2["items"][0]["evidence_type"] == "proposal"
