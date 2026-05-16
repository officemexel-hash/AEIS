"""
SYLION Governance -- Evidence Workflow Tests

Tests for EvidenceWorkflow: pack creation, artefact management,
validation rules per decision class, submission, query, and event emission.
"""

from __future__ import annotations

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.evidence_spine import EvidenceSpine
from sylion.governance.evidence_workflow import (
    EvidenceArtefact,
    EvidencePack,
    EvidenceWorkflow,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def spine():
    return EvidenceSpine()


@pytest.fixture
def wf(bus, spine):
    return EvidenceWorkflow(evidence_spine=spine, event_bus=bus)


def _artefact(name, artefact_type, has_hash=True):
    a = EvidenceArtefact(
        name=name,
        artefact_type=artefact_type,
        description=f"Test {artefact_type}",
        source="test",
    )
    if has_hash:
        a.compute_hash(f"content-of-{name}")
    return a


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEvidencePackCreation:

    def test_create_pack(self, wf):
        result = wf.create_pack("prop-1", "D3", created_by="agent-1")
        assert "pack_id" in result
        assert result["status"] == "draft"

    def test_create_pack_stored_in_db(self, wf):
        result = wf.create_pack("prop-2", "D2")
        pack = wf.get_pack(result["pack_id"])
        assert pack is not None
        assert pack["proposal_id"] == "prop-2"
        assert pack["decision_class"] == "D2"

    def test_create_pack_emits_event(self, wf, bus):
        events = []
        bus.subscribe("evidence.pack_created", lambda e: events.append(e))
        wf.create_pack("prop-3", "D1")
        assert len(events) == 1
        assert events[0].payload["proposal_id"] == "prop-3"

    def test_get_pack_not_found(self, wf):
        assert wf.get_pack("nonexistent") is None


class TestEvidenceArtefactManagement:

    def test_add_artefact(self, wf):
        pack = wf.create_pack("prop-a", "D3")
        art = _artefact("unit-tests", "test_result")
        result = wf.add_artefact(pack["pack_id"], art)
        assert result["added"] is True
        assert result["artefact_id"] == art.artefact_id

    def test_add_artefact_updates_pack_hash(self, wf):
        pack = wf.create_pack("prop-b", "D3")
        art = _artefact("bench-1", "benchmark")
        result = wf.add_artefact(pack["pack_id"], art)
        assert result["pack_hash"] != ""
        assert len(result["pack_hash"]) == 64

    def test_add_artefact_to_nonexistent_pack(self, wf):
        art = _artefact("x", "test_result")
        result = wf.add_artefact("ghost", art)
        assert result["added"] is False
        assert "not found" in result["message"]

    def test_add_multiple_artefacts(self, wf):
        pack = wf.create_pack("prop-c", "D3")
        for t in ("test_result", "benchmark", "review"):
            wf.add_artefact(pack["pack_id"], _artefact(f"{t}-1", t))
        stored = wf.get_pack(pack["pack_id"])
        assert len(stored["artefacts"]) == 3

    def test_artefact_without_hash(self, wf):
        pack = wf.create_pack("prop-d", "D2")
        art = _artefact("no-hash", "test_result", has_hash=False)
        wf.add_artefact(pack["pack_id"], art)
        stored = wf.get_pack(pack["pack_id"])
        assert stored["artefacts"][0]["hash"] == ""


class TestEvidencePackValidation:

    def test_validate_d2_pack_with_test_result(self, wf):
        pack = wf.create_pack("prop-v1", "D2")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is True
        assert result["status"] == "validated"

    def test_validate_d3_pack_missing_artefacts(self, wf):
        pack = wf.create_pack("prop-v2", "D3")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is False
        assert "benchmark" in result["missing_types"]
        assert "review" in result["missing_types"]

    def test_validate_d4_pack_all_required(self, wf):
        pack = wf.create_pack("prop-v3", "D4")
        for t in ("test_result", "benchmark", "review", "contract"):
            wf.add_artefact(pack["pack_id"], _artefact(f"{t}-d4", t))
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is True

    def test_validate_d5_pack_all_required(self, wf):
        pack = wf.create_pack("prop-v4", "D5")
        for t in ("test_result", "benchmark", "review", "contract", "log"):
            wf.add_artefact(pack["pack_id"], _artefact(f"{t}-d5", t))
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is True

    def test_validate_pack_artefact_without_hash_fails(self, wf):
        pack = wf.create_pack("prop-v5", "D2")
        art = _artefact("bad", "test_result", has_hash=False)
        wf.add_artefact(pack["pack_id"], art)
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is False
        assert "bad" in result["no_hash"]

    def test_validate_nonexistent_pack(self, wf):
        result = wf.validate_pack("ghost")
        assert result["valid"] is False
        assert "not found" in result["message"]

    def test_validate_d0_no_requirements(self, wf):
        pack = wf.create_pack("prop-v6", "D0")
        result = wf.validate_pack(pack["pack_id"])
        assert result["valid"] is True
        assert result["missing_types"] == []


class TestEvidencePackSubmission:

    def test_submit_valid_pack(self, wf):
        pack = wf.create_pack("prop-s1", "D2")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        result = wf.submit_pack(pack["pack_id"])
        assert result["submitted"] is True

    def test_submit_invalid_pack_fails(self, wf):
        pack = wf.create_pack("prop-s2", "D3")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        result = wf.submit_pack(pack["pack_id"])
        assert result["submitted"] is False
        assert "validation failed" in result["message"].lower()

    def test_submit_records_in_evidence_spine(self, wf, spine):
        pack = wf.create_pack("prop-s3", "D2")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        wf.submit_pack(pack["pack_id"])
        entries = spine.query(source_plan="governance.evidence_workflow")
        assert len(entries) == 1
        assert entries[0]["event_type"] == "evidence_pack.submitted"

    def test_submit_emits_event(self, wf, bus):
        events = []
        bus.subscribe("evidence.pack_submitted", lambda e: events.append(e))
        pack = wf.create_pack("prop-s4", "D2")
        wf.add_artefact(pack["pack_id"], _artefact("tests", "test_result"))
        wf.submit_pack(pack["pack_id"])
        assert len(events) == 1


class TestEvidencePackQuery:

    def test_list_packs_unfiltered(self, wf):
        wf.create_pack("p1", "D1")
        wf.create_pack("p2", "D2")
        packs = wf.list_packs()
        assert len(packs) == 2

    def test_list_packs_filter_by_proposal(self, wf):
        wf.create_pack("target-prop", "D2")
        wf.create_pack("other-prop", "D3")
        packs = wf.list_packs(proposal_id="target-prop")
        assert len(packs) == 1
        assert packs[0]["proposal_id"] == "target-prop"

    def test_list_packs_filter_by_status(self, wf):
        pid = wf.create_pack("p1", "D2")["pack_id"]
        wf.add_artefact(pid, _artefact("t", "test_result"))
        wf.submit_pack(pid)
        wf.create_pack("p2", "D1")
        submitted = wf.list_packs(status="submitted")
        assert len(submitted) == 1

    def test_get_pack_parses_artefacts_json(self, wf):
        pid = wf.create_pack("p-parse", "D2")["pack_id"]
        wf.add_artefact(pid, _artefact("a1", "test_result"))
        wf.add_artefact(pid, _artefact("a2", "benchmark"))
        pack = wf.get_pack(pid)
        assert isinstance(pack["artefacts"], list)
        assert len(pack["artefacts"]) == 2
        assert "artefacts_json" not in pack


class TestEvidenceArtefactDataclass:

    def test_compute_hash_deterministic(self):
        art = EvidenceArtefact(name="test", artefact_type="test_result")
        h1 = art.compute_hash("hello world")
        art2 = EvidenceArtefact(name="test2", artefact_type="review")
        h2 = art2.compute_hash("hello world")
        assert h1 == h2
        assert len(h1) == 64

    def test_compute_pack_hash(self):
        a1 = EvidenceArtefact(name="a", artefact_type="test_result")
        a1.compute_hash("content-a")
        a2 = EvidenceArtefact(name="b", artefact_type="review")
        a2.compute_hash("content-b")
        pack = EvidencePack(artefacts=[a1, a2])
        ph = pack.compute_pack_hash()
        assert ph != ""
        assert len(ph) == 64
