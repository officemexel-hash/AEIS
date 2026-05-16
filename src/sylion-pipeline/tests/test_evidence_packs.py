"""
tests/test_evidence_packs.py — Evidence Pack schema tests

Covers:
- Pack creation (D0-D5)
- Artefact addition and immutability rules
- Submit (freeze) with fidelity computation
- Validate + spine anchoring -> archived
- Fidelity scoring across decision classes
- Immutability enforcement
- Listing and filtering
"""

import hashlib
import time

import pytest

from sylion.core.event_bus import EventBus
from sylion.core.evidence_spine import EvidenceSpine
from sylion.governance.evidence_packs import (
    ARTEFACT_TYPES,
    EvidencePackManager,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def spine():
    return EvidenceSpine()


@pytest.fixture
def manager(spine, bus):
    return EvidencePackManager(evidence_spine=spine, event_bus=bus)


def _make_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# =====================================================================
# Creation
# =====================================================================

class TestPackCreation:

    def test_create_pack_basic(self, manager):
        pack = manager.create_pack("prop-001", "D3")
        assert pack.pack_id
        assert pack.proposal_id == "prop-001"
        assert pack.decision_class == "D3"
        assert pack.status == "draft"
        assert pack.fidelity_score == 0.0
        assert pack.validation_hash == ""
        assert pack.created_at > 0

    @pytest.mark.parametrize("dc", ["D0", "D1", "D2", "D3", "D4", "D5"])
    def test_create_all_decision_classes(self, manager, dc):
        pack = manager.create_pack("p", dc)
        assert pack.decision_class == dc
        assert pack.status == "draft"

    def test_create_pack_invalid_class(self, manager):
        with pytest.raises(ValueError, match="Invalid decision_class"):
            manager.create_pack("p", "D6")

    def test_create_pack_get_roundtrip(self, manager):
        pack = manager.create_pack("prop-002", "D4")
        retrieved = manager.get_pack(pack.pack_id)
        assert retrieved is not None
        assert retrieved["pack_id"] == pack.pack_id
        assert retrieved["proposal_id"] == "prop-002"
        assert retrieved["decision_class"] == "D4"
        assert retrieved["status"] == "draft"
        assert retrieved["artefacts"] == []

    def test_get_pack_nonexistent(self, manager):
        assert manager.get_pack("nonexistent") is None


# =====================================================================
# Artefacts
# =====================================================================

class TestArtefacts:

    def test_add_artefact(self, manager):
        pack = manager.create_pack("prop-a", "D3")
        art = manager.add_artefact(
            pack.pack_id, "unit_tests", "test_result",
            _make_hash("tests passed"), {"coverage": 0.95}
        )
        assert art.artefact_id
        assert art.pack_id == pack.pack_id
        assert art.name == "unit_tests"
        assert art.type == "test_result"
        assert art.content_hash == _make_hash("tests passed")
        assert art.metadata == {"coverage": 0.95}

    def test_add_multiple_artefacts(self, manager):
        pack = manager.create_pack("prop-b", "D5")
        for i, atype in enumerate(ARTEFACT_TYPES):
            art = manager.add_artefact(
                pack.pack_id, f"art-{i}", atype,
                _make_hash(f"content-{i}"), {"index": i}
            )
            assert art.type == atype

        retrieved = manager.get_pack(pack.pack_id)
        assert len(retrieved["artefacts"]) == 5

    def test_add_artefact_invalid_type(self, manager):
        pack = manager.create_pack("prop-c", "D3")
        with pytest.raises(ValueError, match="Invalid artefact type"):
            manager.add_artefact(pack.pack_id, "bad", "invalid_type", "hash123")

    def test_add_artefact_to_nonexistent_pack(self, manager):
        with pytest.raises(ValueError, match="Pack not found"):
            manager.add_artefact("nonexistent", "x", "test_result", "h")

    def test_cannot_add_artefact_to_submitted_pack(self, manager):
        pack = manager.create_pack("prop-d", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)

        with pytest.raises(RuntimeError, match="must be 'draft'"):
            manager.add_artefact(pack.pack_id, "more", "test_result", _make_hash("more"))

    def test_cannot_add_artefact_to_archived_pack(self, manager, spine):
        pack = manager.create_pack("prop-e", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)
        manager.validate_pack(pack.pack_id)

        with pytest.raises(RuntimeError, match="must be 'draft'"):
            manager.add_artefact(pack.pack_id, "more", "test_result", _make_hash("x"))


# =====================================================================
# Submit
# =====================================================================

class TestSubmit:

    def test_submit_with_artefacts(self, manager):
        pack = manager.create_pack("prop-s1", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        result = manager.submit_pack(pack.pack_id)
        assert result["status"] == "submitted"
        assert result["fidelity_score"] >= 0.0
        assert result["pack_id"] == pack.pack_id

    def test_submit_empty_pack_rejected(self, manager):
        pack = manager.create_pack("prop-s2", "D3")
        with pytest.raises(RuntimeError, match="minimum is 1"):
            manager.submit_pack(pack.pack_id)

    def test_submit_non_draft_rejected(self, manager):
        pack = manager.create_pack("prop-s3", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)

        with pytest.raises(RuntimeError, match="must be 'draft'"):
            manager.submit_pack(pack.pack_id)

    def test_submit_updates_status_in_db(self, manager):
        pack = manager.create_pack("prop-s4", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)

        retrieved = manager.get_pack(pack.pack_id)
        assert retrieved["status"] == "submitted"


# =====================================================================
# Validate
# =====================================================================

class TestValidate:

    def test_validate_submitted_pack(self, manager, spine):
        pack = manager.create_pack("prop-v1", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)
        result = manager.validate_pack(pack.pack_id)

        assert result["status"] == "archived"
        assert result["validation_hash"]
        assert result["spine_entry_id"]
        assert result["spine_hash"]
        assert result["artefact_count"] == 1

    def test_validate_anchors_to_spine(self, manager, spine):
        pack = manager.create_pack("prop-v2", "D3")
        for i, atype in enumerate(["test_result", "metric_snapshot", "contract_snapshot"]):
            manager.add_artefact(pack.pack_id, f"art-{i}", atype, _make_hash(f"c-{i}"))
        manager.submit_pack(pack.pack_id)
        result = manager.validate_pack(pack.pack_id)

        # Verify spine received an entry
        entries = spine.query(source_plan="governance.evidence_packs")
        assert len(entries) >= 1
        entry = entries[-1]
        assert entry["event_type"] == "evidence_pack.validated"
        import json
        payload = json.loads(entry["payload"]) if isinstance(entry["payload"], str) else entry["payload"]
        assert payload["pack_id"] == pack.pack_id

    def test_validate_without_spine(self, bus):
        mgr = EvidencePackManager(evidence_spine=None, event_bus=bus)
        pack = mgr.create_pack("prop-v3", "D2")
        mgr.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        mgr.submit_pack(pack.pack_id)
        result = mgr.validate_pack(pack.pack_id)

        assert result["status"] == "archived"
        assert result["validation_hash"]
        assert result["spine_entry_id"] == ""  # no spine
        assert result["spine_hash"] == ""

    def test_validate_non_submitted_rejected(self, manager):
        pack = manager.create_pack("prop-v4", "D2")
        with pytest.raises(RuntimeError, match="must be 'submitted'"):
            manager.validate_pack(pack.pack_id)

    def test_validate_nonexistent_pack(self, manager):
        with pytest.raises(ValueError, match="Pack not found"):
            manager.validate_pack("nonexistent")

    def test_validated_pack_is_archived(self, manager, spine):
        pack = manager.create_pack("prop-v5", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)
        manager.validate_pack(pack.pack_id)

        retrieved = manager.get_pack(pack.pack_id)
        assert retrieved["status"] == "archived"
        assert retrieved["validated_at"] > 0
        assert retrieved["validation_hash"] != ""


# =====================================================================
# Immutability
# =====================================================================

class TestImmutability:

    def test_archived_pack_cannot_be_modified(self, manager, spine):
        pack = manager.create_pack("prop-im1", "D3")
        for i, atype in enumerate(["test_result", "metric_snapshot", "contract_snapshot"]):
            manager.add_artefact(pack.pack_id, f"art-{i}", atype, _make_hash(f"c-{i}"))
        manager.submit_pack(pack.pack_id)
        manager.validate_pack(pack.pack_id)

        # Cannot submit again
        with pytest.raises(RuntimeError, match="must be 'draft'"):
            manager.submit_pack(pack.pack_id)

        # Cannot validate again
        with pytest.raises(RuntimeError, match="must be 'submitted'"):
            manager.validate_pack(pack.pack_id)

        # Cannot add artefacts
        with pytest.raises(RuntimeError, match="must be 'draft'"):
            manager.add_artefact(pack.pack_id, "new", "test_result", "h")


# =====================================================================
# Fidelity
# =====================================================================

class TestFidelity:

    def test_fidelity_d0_always_1(self, manager):
        pack = manager.create_pack("prop-f0", "D0")
        assert manager.compute_fidelity(pack.pack_id) == 1.0

    def test_fidelity_d1_always_1(self, manager):
        pack = manager.create_pack("prop-f1", "D1")
        assert manager.compute_fidelity(pack.pack_id) == 1.0

    def test_fidelity_d2_with_one_artefact(self, manager):
        pack = manager.create_pack("prop-f2", "D2")
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert fidelity == 1.0  # 1/1 * 1.0 integrity

    def test_fidelity_d3_partial(self, manager):
        pack = manager.create_pack("prop-f3", "D3")
        # Only 1 artefact, need 3
        manager.add_artefact(pack.pack_id, "tests", "test_result", _make_hash("ok"))
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert 0.0 < fidelity < 1.0  # 1/3 * 1.0 ≈ 0.333

    def test_fidelity_d3_full(self, manager):
        pack = manager.create_pack("prop-f3full", "D3")
        for i in range(3):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result", _make_hash(f"c-{i}")
            )
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert fidelity == 1.0  # 3/3 * 1.0

    def test_fidelity_d4_with_3_of_5(self, manager):
        pack = manager.create_pack("prop-f4", "D4")
        for i in range(3):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result", _make_hash(f"c-{i}")
            )
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert 0.0 < fidelity < 1.0  # 3/5 * 1.0 = 0.6

    def test_fidelity_d5_with_7_of_7(self, manager):
        pack = manager.create_pack("prop-f5", "D5")
        for i in range(7):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result", _make_hash(f"c-{i}")
            )
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert fidelity == 1.0

    def test_fidelity_penalizes_missing_hashes(self, manager):
        pack = manager.create_pack("prop-fh", "D3")
        for i in range(3):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result", "", {}
            )
        fidelity = manager.compute_fidelity(pack.pack_id)
        assert fidelity == 0.0  # 3/3 * 0.0 (no valid hashes)

    def test_fidelity_mixed_hashes(self, manager):
        pack = manager.create_pack("prop-fm", "D3")
        manager.add_artefact(pack.pack_id, "a1", "test_result", _make_hash("ok"), {})
        manager.add_artefact(pack.pack_id, "a2", "test_result", "", {})
        manager.add_artefact(pack.pack_id, "a3", "test_result", _make_hash("ok2"), {})
        fidelity = manager.compute_fidelity(pack.pack_id)
        # 3/3 completeness, but hash_integrity = 0.5 (some missing)
        assert fidelity == 0.5

    def test_fidelity_nonexistent_pack(self, manager):
        assert manager.compute_fidelity("nonexistent") == 0.0

    def test_submit_computes_fidelity(self, manager):
        pack = manager.create_pack("prop-fs", "D4")
        for i in range(5):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result", _make_hash(f"c-{i}")
            )
        result = manager.submit_pack(pack.pack_id)
        assert result["fidelity_score"] == 1.0


# =====================================================================
# List / Filter
# =====================================================================

class TestListPacks:

    def test_list_all_packs(self, manager):
        manager.create_pack("p1", "D2")
        manager.create_pack("p2", "D3")
        packs = manager.list_packs()
        assert len(packs) == 2

    def test_list_by_status(self, manager):
        pack = manager.create_pack("p1", "D2")
        manager.add_artefact(pack.pack_id, "t", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)
        manager.create_pack("p2", "D3")

        drafts = manager.list_packs(status="draft")
        submitted = manager.list_packs(status="submitted")
        assert len(drafts) == 1
        assert len(submitted) == 1

    def test_list_by_decision_class(self, manager):
        manager.create_pack("p1", "D2")
        manager.create_pack("p2", "D3")
        manager.create_pack("p3", "D3")

        d3_packs = manager.list_packs(decision_class="D3")
        assert len(d3_packs) == 2

    def test_list_by_status_and_class(self, manager):
        pack = manager.create_pack("p1", "D3")
        manager.add_artefact(pack.pack_id, "t", "test_result", _make_hash("ok"))
        manager.submit_pack(pack.pack_id)
        manager.create_pack("p2", "D3")

        result = manager.list_packs(status="submitted", decision_class="D3")
        assert len(result) == 1
        assert result[0]["status"] == "submitted"
        assert result[0]["decision_class"] == "D3"


# =====================================================================
# Full lifecycle
# =====================================================================

class TestFullLifecycle:

    def test_d3_full_lifecycle(self, manager, spine):
        """D3 decision: create -> add 3 artefacts -> submit -> validate -> archived."""
        pack = manager.create_pack("lifecycle-1", "D3")

        artefact_types = ["test_result", "metric_snapshot", "contract_snapshot"]
        for i, atype in enumerate(artefact_types):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", atype,
                _make_hash(f"content-{i}"), {"step": i}
            )

        # Submit
        submit_result = manager.submit_pack(pack.pack_id)
        assert submit_result["status"] == "submitted"
        assert submit_result["fidelity_score"] == 1.0

        # Validate + anchor to spine
        validate_result = manager.validate_pack(pack.pack_id, spine=spine)
        assert validate_result["status"] == "archived"
        assert validate_result["validation_hash"]
        assert validate_result["spine_hash"]

        # Verify spine integrity
        valid, msg = spine.verify_chain()
        assert valid, f"Spine chain broken: {msg}"

        # Verify pack is immutable
        with pytest.raises(RuntimeError):
            manager.add_artefact(pack.pack_id, "late", "test_result", "h")

    def test_d5_full_lifecycle(self, manager, spine):
        """D5 decision: needs 7 artefacts for full fidelity."""
        pack = manager.create_pack("lifecycle-2", "D5")

        for i in range(7):
            manager.add_artefact(
                pack.pack_id, f"art-{i}", "test_result",
                _make_hash(f"d5-content-{i}"), {"idx": i}
            )

        submit_result = manager.submit_pack(pack.pack_id)
        assert submit_result["fidelity_score"] == 1.0

        validate_result = manager.validate_pack(pack.pack_id)
        assert validate_result["status"] == "archived"

    def test_multiple_packs_spine_chain(self, manager, spine):
        """Multiple packs validated sequentially maintain spine integrity."""
        for dc in ["D2", "D2", "D2"]:
            pack = manager.create_pack(f"multi-{dc}", dc)
            manager.add_artefact(
                pack.pack_id, "tests", "test_result", _make_hash(f"pack-{pack.pack_id}")
            )
            manager.submit_pack(pack.pack_id)
            manager.validate_pack(pack.pack_id, spine=spine)

        valid, msg = spine.verify_chain()
        assert valid, f"Spine chain broken after multiple packs: {msg}"

        entries = spine.query(source_plan="governance.evidence_packs")
        assert len(entries) == 3
