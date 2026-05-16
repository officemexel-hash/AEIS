"""Tests for sylion.cellular.attack_vectors — AttackVectorLibrary."""

import json
import threading
import time

import pytest

from sylion.cellular.attack_vectors import AttackVectorLibrary, get_attack_vector_library


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lib():
    """Fresh in-memory AttackVectorLibrary per test."""
    return AttackVectorLibrary()


@pytest.fixture
def registered_vector(lib):
    """Pre-register a vector and return its data dict."""
    return lib.register(
        vector_id="vec-001",
        name="IMSI Catcher Passive",
        technology="4G",
        decision_class="D3",
        preconditions=["UE in RRC_IDLE"],
        steps=["Deploy eNodeB", "Collect IMSIs"],
        legal_basis="Telecom Act s.5",
    )


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_returns_full_record(self, lib):
        data = lib.register(
            vector_id="v1",
            name="Fake BTS",
            technology="5G",
            decision_class="D4",
            preconditions=["UE camped"],
            steps=["Step A", "Step B"],
            legal_basis="Court order",
        )
        assert data["vector_id"] == "v1"
        assert data["name"] == "Fake BTS"
        assert data["technology"] == "5G"
        assert data["decision_class"] == "D4"
        assert data["preconditions"] == ["UE camped"]
        assert data["steps"] == ["Step A", "Step B"]
        assert data["legal_basis"] == "Court order"
        assert data["lifecycle"] == "DRAFT"
        assert isinstance(data["created_at"], float)

    def test_defaults(self, lib):
        data = lib.register(vector_id="v2", name="Minimal")
        assert data["technology"] == "4G"
        assert data["decision_class"] == "D3"
        assert data["preconditions"] == []
        assert data["steps"] == []
        assert data["legal_basis"] == ""
        assert data["lifecycle"] == "DRAFT"

    def test_duplicate_vector_id_raises(self, lib):
        lib.register(vector_id="dup", name="First")
        with pytest.raises(Exception):
            lib.register(vector_id="dup", name="Second")


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

class TestGet:
    def test_existing(self, lib, registered_vector):
        result = lib.get("vec-001")
        assert result is not None
        assert result["vector_id"] == "vec-001"
        assert result["name"] == "IMSI Catcher Passive"

    def test_nonexistent_returns_none(self, lib):
        assert lib.get("no-such-id") is None

    def test_preconditions_and_steps_parsed(self, lib, registered_vector):
        data = lib.get("vec-001")
        assert isinstance(data["preconditions"], list)
        assert isinstance(data["steps"], list)
        assert data["preconditions"] == ["UE in RRC_IDLE"]
        assert data["steps"] == ["Deploy eNodeB", "Collect IMSIs"]


# ---------------------------------------------------------------------------
# list_vectors
# ---------------------------------------------------------------------------

class TestListVectors:
    def test_empty(self, lib):
        assert lib.list_vectors() == []

    def test_returns_all(self, lib):
        lib.register(vector_id="a", name="A", technology="4G")
        lib.register(vector_id="b", name="B", technology="5G")
        items = lib.list_vectors()
        ids = {i["vector_id"] for i in items}
        assert ids == {"a", "b"}

    def test_filter_technology(self, lib):
        lib.register(vector_id="a", name="A", technology="4G")
        lib.register(vector_id="b", name="B", technology="5G")
        result = lib.list_vectors(technology="5G")
        assert len(result) == 1
        assert result[0]["vector_id"] == "b"

    def test_filter_lifecycle(self, lib):
        lib.register(vector_id="a", name="A")
        lib.publish("a")
        lib.register(vector_id="b", name="B")
        result = lib.list_vectors(lifecycle="PUBLISHED")
        assert len(result) == 1
        assert result[0]["vector_id"] == "a"

    def test_combined_filter(self, lib):
        lib.register(vector_id="a", name="A", technology="4G")
        lib.publish("a")
        lib.register(vector_id="b", name="B", technology="5G")
        result = lib.list_vectors(technology="4G", lifecycle="PUBLISHED")
        assert len(result) == 1
        assert result[0]["vector_id"] == "a"

    def test_ordered_by_created_at_desc(self, lib):
        lib.register(vector_id="first", name="First")
        time.sleep(0.01)
        lib.register(vector_id="second", name="Second")
        items = lib.list_vectors()
        assert items[0]["vector_id"] == "second"
        assert items[1]["vector_id"] == "first"


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------

class TestPublish:
    def test_draft_to_published(self, lib, registered_vector):
        result = lib.publish("vec-001")
        assert result["lifecycle"] == "PUBLISHED"
        assert result["vector_id"] == "vec-001"
        # Verify in DB
        assert lib.get("vec-001")["lifecycle"] == "PUBLISHED"

    def test_not_found(self, lib):
        result = lib.publish("nope")
        assert "error" in result

    def test_cannot_publish_non_draft(self, lib, registered_vector):
        lib.publish("vec-001")
        result = lib.publish("vec-001")
        assert "error" in result
        assert "PUBLISHED" in result["error"]


# ---------------------------------------------------------------------------
# deprecate
# ---------------------------------------------------------------------------

class TestDeprecate:
    def test_published_to_deprecated(self, lib, registered_vector):
        lib.publish("vec-001")
        result = lib.deprecate("vec-001")
        assert result["lifecycle"] == "DEPRECATED"
        assert lib.get("vec-001")["lifecycle"] == "DEPRECATED"

    def test_not_found(self, lib):
        result = lib.deprecate("nope")
        assert "error" in result

    def test_cannot_deprecate_draft(self, lib, registered_vector):
        result = lib.deprecate("vec-001")
        assert "error" in result
        assert "DRAFT" in result["error"]

    def test_cannot_deprecate_already_deprecated(self, lib, registered_vector):
        lib.publish("vec-001")
        lib.deprecate("vec-001")
        result = lib.deprecate("vec-001")
        assert "error" in result


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty(self, lib):
        stats = lib.get_stats()
        assert stats == {"total": 0, "DRAFT": 0, "PUBLISHED": 0, "DEPRECATED": 0}

    def test_mixed_lifecycle(self, lib):
        lib.register(vector_id="a", name="A")
        lib.register(vector_id="b", name="B")
        lib.register(vector_id="c", name="C")
        lib.publish("a")
        lib.publish("b")
        lib.deprecate("a")
        stats = lib.get_stats()
        assert stats["total"] == 3
        assert stats["DRAFT"] == 1
        assert stats["PUBLISHED"] == 1
        assert stats["DEPRECATED"] == 1


# ---------------------------------------------------------------------------
# Full lifecycle integration
# ---------------------------------------------------------------------------

class TestFullLifecycle:
    def test_draft_publish_deprecate(self, lib):
        lib.register(vector_id="lc", name="Lifecycle Test")
        assert lib.get("lc")["lifecycle"] == "DRAFT"

        lib.publish("lc")
        assert lib.get("lc")["lifecycle"] == "PUBLISHED"

        lib.deprecate("lc")
        assert lib.get("lc")["lifecycle"] == "DEPRECATED"

        stats = lib.get_stats()
        assert stats["DEPRECATED"] == 1
        assert stats["total"] == 1


# ---------------------------------------------------------------------------
# Singleton helper
# ---------------------------------------------------------------------------

class TestGetAttackVectorLibrary:
    def test_returns_instance(self):
        inst = get_attack_vector_library()
        assert isinstance(inst, AttackVectorLibrary)

    def test_singleton(self):
        a = get_attack_vector_library()
        b = get_attack_vector_library()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety (no mock — real concurrent writes)
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_registers(self, lib):
        errors = []

        def register(idx):
            try:
                lib.register(vector_id=f"t-{idx}", name=f"T{idx}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        items = lib.list_vectors()
        assert len(items) == 20
