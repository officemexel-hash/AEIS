"""Tests for sylion.quality.golden_set_registry -- GoldenSetRegistry.

~40 tests covering: create_set, update_set, delete_set, get_set, list_sets,
add_case, remove_case, get_cases, import_cases, singleton, concurrency,
edge cases, JSON parsing, error handling.
"""

from __future__ import annotations

import json
import threading

import pytest

from sylion.quality.golden_set_registry import (
    GoldenSetRegistry,
    get_golden_set_registry,
    reset_golden_set_registry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_golden_set_registry()
    yield
    reset_golden_set_registry()


@pytest.fixture
def reg():
    return GoldenSetRegistry(db_path=":memory:")


# ===========================================================================
# TestCreateSet
# ===========================================================================

class TestCreateSet:

    def test_create_returns_set_id(self, reg):
        result = reg.create_set("My Set")
        assert "set_id" in result
        assert isinstance(result["set_id"], str)
        assert len(result["set_id"]) > 0

    def test_create_returns_name(self, reg):
        result = reg.create_set("My Set")
        assert result["name"] == "My Set"

    def test_create_with_description(self, reg):
        result = reg.create_set("S1", description="A description")
        assert result["description"] == "A description"

    def test_create_with_category(self, reg):
        result = reg.create_set("S1", category="unit")
        assert result["category"] == "unit"

    def test_create_default_description_empty(self, reg):
        result = reg.create_set("S1")
        assert result["description"] == ""

    def test_create_default_category_empty(self, reg):
        result = reg.create_set("S1")
        assert result["category"] == ""

    def test_create_has_created_at(self, reg):
        result = reg.create_set("S1")
        assert result["created_at"] > 0

    def test_create_initial_case_count_zero(self, reg):
        result = reg.create_set("S1")
        assert result["case_count"] == 0

    def test_create_generates_unique_ids(self, reg):
        a = reg.create_set("A")
        b = reg.create_set("B")
        assert a["set_id"] != b["set_id"]


# ===========================================================================
# TestUpdateSet
# ===========================================================================

class TestUpdateSet:

    def test_update_name(self, reg):
        s = reg.create_set("Original")
        result = reg.update_set(s["set_id"], name="Updated")
        assert result["name"] == "Updated"

    def test_update_description(self, reg):
        s = reg.create_set("S")
        result = reg.update_set(s["set_id"], description="New desc")
        assert result["description"] == "New desc"

    def test_update_category(self, reg):
        s = reg.create_set("S")
        result = reg.update_set(s["set_id"], category="integration")
        assert result["category"] == "integration"

    def test_update_nonexistent_returns_none(self, reg):
        result = reg.update_set("nonexistent", name="X")
        assert result is None

    def test_update_no_fields_returns_record(self, reg):
        s = reg.create_set("S")
        result = reg.update_set(s["set_id"])
        assert result is not None
        assert result["name"] == "S"

    def test_update_ignores_unknown_fields(self, reg):
        s = reg.create_set("S")
        result = reg.update_set(s["set_id"], bogus="val", name="New")
        assert result["name"] == "New"

    def test_update_sets_updated_at(self, reg):
        s = reg.create_set("S")
        result = reg.update_set(s["set_id"], name="X")
        assert result["updated_at"] is not None


# ===========================================================================
# TestDeleteSet
# ===========================================================================

class TestDeleteSet:

    def test_delete_existing(self, reg):
        s = reg.create_set("S")
        assert reg.delete_set(s["set_id"]) is True

    def test_delete_nonexistent(self, reg):
        assert reg.delete_set("nonexistent") is False

    def test_delete_removes_from_list(self, reg):
        s = reg.create_set("S")
        reg.delete_set(s["set_id"])
        assert reg.list_sets() == []

    def test_delete_removes_cases(self, reg):
        s = reg.create_set("S")
        reg.add_case(s["set_id"], input_json={"a": 1},
                     expected_output_json={"b": 2})
        reg.delete_set(s["set_id"])
        assert reg.get_cases(s["set_id"]) == []

    def test_delete_only_affects_target(self, reg):
        s1 = reg.create_set("S1")
        s2 = reg.create_set("S2")
        reg.delete_set(s1["set_id"])
        assert reg.get_set(s2["set_id"]) is not None


# ===========================================================================
# TestGetSet
# ===========================================================================

class TestGetSet:

    def test_get_existing(self, reg):
        s = reg.create_set("S")
        result = reg.get_set(s["set_id"])
        assert result is not None
        assert result["name"] == "S"

    def test_get_nonexistent(self, reg):
        assert reg.get_set("nonexistent") is None


# ===========================================================================
# TestListSets
# ===========================================================================

class TestListSets:

    def test_list_empty(self, reg):
        assert reg.list_sets() == []

    def test_list_returns_all(self, reg):
        reg.create_set("A")
        reg.create_set("B")
        assert len(reg.list_sets()) == 2

    def test_list_filter_by_category(self, reg):
        reg.create_set("A", category="unit")
        reg.create_set("B", category="integration")
        result = reg.list_sets(category="unit")
        assert len(result) == 1
        assert result[0]["category"] == "unit"

    def test_list_no_match_category(self, reg):
        reg.create_set("A", category="unit")
        assert reg.list_sets(category="integration") == []

    def test_list_ordered_desc(self, reg):
        reg.create_set("First")
        reg.create_set("Second")
        sets = reg.list_sets()
        assert sets[0]["name"] == "Second"


# ===========================================================================
# TestAddCase
# ===========================================================================

class TestAddCase:

    def test_add_case_returns_case_id(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"], input_json={"x": 1},
                         expected_output_json={"y": 2})
        assert "case_id" in c
        assert isinstance(c["case_id"], str)

    def test_add_case_returns_input(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"], input_json={"x": 1},
                         expected_output_json={"y": 2})
        assert c["input_json"] == {"x": 1}

    def test_add_case_returns_expected_output(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"], input_json={"x": 1},
                         expected_output_json={"y": 2})
        assert c["expected_output_json"] == {"y": 2}

    def test_add_case_with_metadata(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"], input_json={"x": 1},
                         expected_output_json={"y": 2},
                         metadata_json={"priority": "high"})
        assert c["metadata_json"] == {"priority": "high"}

    def test_add_case_defaults_empty_json(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"])
        assert c["input_json"] == {}
        assert c["expected_output_json"] == {}
        assert c["metadata_json"] == {}

    def test_add_case_nonexistent_set_returns_none(self, reg):
        result = reg.add_case("nonexistent", input_json={"x": 1})
        assert result is None

    def test_add_case_increments_count(self, reg):
        s = reg.create_set("S")
        reg.add_case(s["set_id"])
        reg.add_case(s["set_id"])
        updated = reg.get_set(s["set_id"])
        assert updated["case_count"] == 2

    def test_add_case_assigns_ordinal(self, reg):
        s = reg.create_set("S")
        c1 = reg.add_case(s["set_id"])
        c2 = reg.add_case(s["set_id"])
        assert c1["ordinal"] == 0
        assert c2["ordinal"] == 1


# ===========================================================================
# TestRemoveCase
# ===========================================================================

class TestRemoveCase:

    def test_remove_existing(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"])
        assert reg.remove_case(c["case_id"]) is True

    def test_remove_nonexistent(self, reg):
        assert reg.remove_case("nonexistent") is False

    def test_remove_decrements_count(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"])
        reg.add_case(s["set_id"])
        reg.remove_case(c["case_id"])
        updated = reg.get_set(s["set_id"])
        assert updated["case_count"] == 1

    def test_remove_not_in_get_cases(self, reg):
        s = reg.create_set("S")
        c = reg.add_case(s["set_id"])
        reg.remove_case(c["case_id"])
        cases = reg.get_cases(s["set_id"])
        assert len(cases) == 0


# ===========================================================================
# TestGetCases
# ===========================================================================

class TestGetCases:

    def test_empty(self, reg):
        s = reg.create_set("S")
        assert reg.get_cases(s["set_id"]) == []

    def test_returns_all(self, reg):
        s = reg.create_set("S")
        reg.add_case(s["set_id"], input_json={"a": 1})
        reg.add_case(s["set_id"], input_json={"b": 2})
        cases = reg.get_cases(s["set_id"])
        assert len(cases) == 2

    def test_json_parsed(self, reg):
        s = reg.create_set("S")
        reg.add_case(s["set_id"], input_json={"x": 1},
                     expected_output_json={"y": 2},
                     metadata_json={"z": 3})
        cases = reg.get_cases(s["set_id"])
        c = cases[0]
        assert c["input_json"] == {"x": 1}
        assert c["expected_output_json"] == {"y": 2}
        assert c["metadata_json"] == {"z": 3}

    def test_ordered_by_ordinal(self, reg):
        s = reg.create_set("S")
        reg.add_case(s["set_id"], input_json={"ord": 0})
        reg.add_case(s["set_id"], input_json={"ord": 1})
        cases = reg.get_cases(s["set_id"])
        assert cases[0]["input_json"]["ord"] == 0
        assert cases[1]["input_json"]["ord"] == 1


# ===========================================================================
# TestImportCases
# ===========================================================================

class TestImportCases:

    def test_import_multiple(self, reg):
        s = reg.create_set("S")
        cases_list = [
            {"input_json": {"a": 1}, "expected_output_json": {"b": 2}},
            {"input_json": {"c": 3}, "expected_output_json": {"d": 4}},
        ]
        result = reg.import_cases(s["set_id"], cases_list)
        assert len(result) == 2

    def test_import_updates_count(self, reg):
        s = reg.create_set("S")
        reg.import_cases(s["set_id"], [
            {"input_json": {"x": 1}},
            {"input_json": {"y": 2}},
            {"input_json": {"z": 3}},
        ])
        assert reg.get_set(s["set_id"])["case_count"] == 3

    def test_import_nonexistent_set(self, reg):
        result = reg.import_cases("nonexistent", [{"input_json": {}}])
        assert result == []

    def test_import_empty_list(self, reg):
        s = reg.create_set("S")
        result = reg.import_cases(s["set_id"], [])
        assert result == []


# ===========================================================================
# TestSingleton
# ===========================================================================

class TestSingleton:

    def test_get_returns_instance(self):
        inst = get_golden_set_registry(db_path=":memory:")
        assert isinstance(inst, GoldenSetRegistry)

    def test_get_idempotent(self):
        a = get_golden_set_registry(db_path=":memory:")
        b = get_golden_set_registry()
        assert a is b

    def test_reset_creates_new(self):
        a = get_golden_set_registry(db_path=":memory:")
        reset_golden_set_registry(db_path=":memory:")
        b = get_golden_set_registry(db_path=":memory:")
        assert a is not b


# ===========================================================================
# TestConcurrency
# ===========================================================================

class TestConcurrency:

    def test_concurrent_create_sets(self, reg):
        errors = []

        def create(i):
            try:
                reg.create_set(f"Set {i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(reg.list_sets()) == 20

    def test_concurrent_add_cases(self, reg):
        s = reg.create_set("S")
        errors = []

        def add_case(i):
            try:
                reg.add_case(s["set_id"], input_json={"i": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_case, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert reg.get_set(s["set_id"])["case_count"] == 20
