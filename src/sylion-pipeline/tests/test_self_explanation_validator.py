"""Tests for SYLION Governance -- Self-Explanation Validator.

Covers: template CRUD, validation logic, validation stats, EventBus integration,
thread safety, and singleton management.
"""
import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.governance.self_explanation_validator import (
    VALID_SCOPES,
    SelfExplanationValidator,
    get_self_explanation_validator,
    reset_self_explanation_validator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator():
    """Fresh SelfExplanationValidator with :memory: SQLite."""
    return SelfExplanationValidator(db_path=":memory:")


@pytest.fixture
def validator_with_bus():
    """SelfExplanationValidator connected to a real EventBus."""
    bus = EventBus(db_path=":memory:")
    return SelfExplanationValidator(db_path=":memory:", event_bus=bus), bus


# ---------------------------------------------------------------------------
# Test: create_template
# ---------------------------------------------------------------------------

class TestCreateTemplate:
    def test_creates_with_basic_params(self, validator):
        result = validator.create_template("quality-check", "global")
        assert "template_id" in result
        assert result["name"] == "quality-check"
        assert result["scope"] == "global"
        assert result["is_active"] is True
        assert result["required_fields"] == []
        assert result["quality_criteria"] == []

    def test_creates_with_required_fields(self, validator):
        fields = [{"name": "reasoning"}, {"name": "evidence"}]
        result = validator.create_template("fields-t", "module", required_fields_json=fields)
        assert result["required_fields"] == fields

    def test_creates_with_quality_criteria(self, validator):
        criteria = [{"field": "reasoning", "min_length": 10}]
        result = validator.create_template("criteria-t", "pipeline", quality_criteria_json=criteria)
        assert result["quality_criteria"] == criteria

    def test_creates_with_json_string_params(self, validator):
        fields = '[{"name": "x"}]'
        result = validator.create_template("json-t", "decision",
                                           required_fields_json=fields)
        assert len(result["required_fields"]) == 1

    def test_rejects_empty_name(self, validator):
        with pytest.raises(ValueError, match="must not be empty"):
            validator.create_template("", "global")

    def test_rejects_whitespace_name(self, validator):
        with pytest.raises(ValueError, match="must not be empty"):
            validator.create_template("   ", "global")

    def test_rejects_invalid_scope(self, validator):
        with pytest.raises(ValueError, match="Invalid scope"):
            validator.create_template("test", "invalid")

    def test_all_valid_scopes(self, validator):
        for scope in VALID_SCOPES:
            result = validator.create_template(f"t-{scope}", scope)
            assert result["scope"] == scope

    def test_template_id_is_unique(self, validator):
        t1 = validator.create_template("u1", "global")
        t2 = validator.create_template("u2", "global")
        assert t1["template_id"] != t2["template_id"]

    def test_timestamps_set(self, validator):
        before = time.time()
        result = validator.create_template("ts", "global")
        after = time.time()
        assert before <= result["created_at"] <= after


# ---------------------------------------------------------------------------
# Test: update_template
# ---------------------------------------------------------------------------

class TestUpdateTemplate:
    def test_updates_name(self, validator):
        t = validator.create_template("old", "global")
        updated = validator.update_template(t["template_id"], name="new")
        assert updated["name"] == "new"

    def test_updates_scope(self, validator):
        t = validator.create_template("scope-t", "global")
        updated = validator.update_template(t["template_id"], scope="module")
        assert updated["scope"] == "module"

    def test_updates_required_fields(self, validator):
        t = validator.create_template("fields-u", "global")
        new_fields = [{"name": "summary"}]
        updated = validator.update_template(t["template_id"], required_fields_json=new_fields)
        assert updated["required_fields"] == new_fields

    def test_updates_quality_criteria(self, validator):
        t = validator.create_template("crit-u", "global")
        new_crit = [{"field": "x", "max_length": 100}]
        updated = validator.update_template(t["template_id"], quality_criteria_json=new_crit)
        assert updated["quality_criteria"] == new_crit

    def test_updates_is_active(self, validator):
        t = validator.create_template("active-u", "global")
        updated = validator.update_template(t["template_id"], is_active=False)
        assert updated["is_active"] is False

    def test_returns_none_for_missing(self, validator):
        result = validator.update_template("nonexistent", name="x")
        assert result is None

    def test_rejects_invalid_scope(self, validator):
        t = validator.create_template("inv", "global")
        with pytest.raises(ValueError, match="Invalid scope"):
            validator.update_template(t["template_id"], scope="bad")

    def test_preserves_on_partial_update(self, validator):
        fields = [{"name": "a"}]
        t = validator.create_template("partial", "global", required_fields_json=fields)
        updated = validator.update_template(t["template_id"], name="renamed")
        assert updated["name"] == "renamed"
        assert updated["required_fields"] == fields


# ---------------------------------------------------------------------------
# Test: delete_template
# ---------------------------------------------------------------------------

class TestDeleteTemplate:
    def test_deletes_existing(self, validator):
        t = validator.create_template("del", "global")
        assert validator.delete_template(t["template_id"]) is True

    def test_returns_false_for_missing(self, validator):
        assert validator.delete_template("nonexistent") is False

    def test_cascades_validations(self, validator):
        t = validator.create_template("cascade", "global",
                                      required_fields_json=[{"name": "x"}])
        validator.validate_explanation(t["template_id"], {"x": "hello"})
        validator.delete_template(t["template_id"])
        validations = validator.list_validations(template_id=t["template_id"])
        assert validations == []


# ---------------------------------------------------------------------------
# Test: list_templates
# ---------------------------------------------------------------------------

class TestListTemplates:
    def test_lists_all(self, validator):
        validator.create_template("t1", "global")
        validator.create_template("t2", "module")
        assert len(validator.list_templates()) == 2

    def test_filter_by_scope(self, validator):
        validator.create_template("s1", "global")
        validator.create_template("s2", "module")
        result = validator.list_templates(scope="global")
        assert len(result) == 1

    def test_active_only(self, validator):
        t1 = validator.create_template("a1", "global")
        validator.create_template("a2", "global")
        validator.update_template(t1["template_id"], is_active=False)
        result = validator.list_templates(active_only=True)
        assert len(result) == 1

    def test_empty_list(self, validator):
        assert validator.list_templates() == []


# ---------------------------------------------------------------------------
# Test: validate_explanation
# ---------------------------------------------------------------------------

class TestValidateExplanation:
    def test_passes_with_all_required_fields(self, validator):
        t = validator.create_template("pass-t", "global",
                                      required_fields_json=[{"name": "reasoning"}])
        result = validator.validate_explanation(t["template_id"], {"reasoning": "because X"})
        assert result["passed"] is True
        assert result["errors"] == []
        assert result["score"] == 1.0

    def test_fails_missing_required_field(self, validator):
        t = validator.create_template("fail-t", "global",
                                      required_fields_json=[{"name": "evidence"}])
        result = validator.validate_explanation(t["template_id"], {})
        assert result["passed"] is False
        assert len(result["errors"]) == 1
        assert "Missing required field" in result["errors"][0]

    def test_fails_empty_required_field(self, validator):
        t = validator.create_template("empty-t", "global",
                                      required_fields_json=[{"name": "x"}])
        result = validator.validate_explanation(t["template_id"], {"x": ""})
        assert result["passed"] is False

    def test_min_length_criterion(self, validator):
        t = validator.create_template("minlen", "global",
                                      quality_criteria_json=[
                                          {"field": "reasoning", "min_length": 10}
                                      ])
        ok = validator.validate_explanation(t["template_id"],
                                            {"reasoning": "this is a long enough explanation"})
        assert ok["passed"] is True

        fail = validator.validate_explanation(t["template_id"], {"reasoning": "short"})
        assert fail["passed"] is False

    def test_max_length_criterion(self, validator):
        t = validator.create_template("maxlen", "global",
                                      quality_criteria_json=[
                                          {"field": "summary", "max_length": 20}
                                      ])
        ok = validator.validate_explanation(t["template_id"], {"summary": "ok"})
        assert ok["passed"] is True

        fail = validator.validate_explanation(t["template_id"],
                                              {"summary": "this is way too long for the max"})
        assert fail["passed"] is False

    def test_pattern_criterion(self, validator):
        t = validator.create_template("pattern", "global",
                                      quality_criteria_json=[
                                          {"field": "code", "pattern": r"^[\w]+$"}
                                      ])
        ok = validator.validate_explanation(t["template_id"], {"code": "abc123"})
        assert ok["passed"] is True

        fail = validator.validate_explanation(t["template_id"], {"code": "abc 123!"})
        assert fail["passed"] is False

    def test_type_criterion(self, validator):
        t = validator.create_template("type", "global",
                                      quality_criteria_json=[
                                          {"field": "score", "type": "float"}
                                      ])
        ok = validator.validate_explanation(t["template_id"], {"score": 0.9})
        assert ok["passed"] is True

        fail = validator.validate_explanation(t["template_id"], {"score": "not_a_number"})
        assert fail["passed"] is False

    def test_type_string(self, validator):
        t = validator.create_template("type-str", "global",
                                      quality_criteria_json=[
                                          {"field": "name", "type": "string"}
                                      ])
        result = validator.validate_explanation(t["template_id"], {"name": "hello"})
        assert result["passed"] is True

    def test_type_list(self, validator):
        t = validator.create_template("type-list", "global",
                                      quality_criteria_json=[
                                          {"field": "items", "type": "list"}
                                      ])
        ok = validator.validate_explanation(t["template_id"], {"items": [1, 2]})
        assert ok["passed"] is True

        fail = validator.validate_explanation(t["template_id"], {"items": "not list"})
        assert fail["passed"] is False

    def test_type_dict(self, validator):
        t = validator.create_template("type-dict", "global",
                                      quality_criteria_json=[
                                          {"field": "meta", "type": "dict"}
                                      ])
        ok = validator.validate_explanation(t["template_id"], {"meta": {"k": "v"}})
        assert ok["passed"] is True

    def test_no_rules_always_passes(self, validator):
        t = validator.create_template("no-rules", "global")
        result = validator.validate_explanation(t["template_id"], {})
        assert result["passed"] is True
        assert result["score"] == 1.0

    def test_score_calculation(self, validator):
        t = validator.create_template("score", "global",
                                      required_fields_json=[{"name": "a"}],
                                      quality_criteria_json=[
                                          {"field": "b", "min_length": 5}
                                      ])
        # Provide "b" that fails the min_length criterion
        result = validator.validate_explanation(t["template_id"], {"a": "ok", "b": "hi"})
        # 1 required field passed + 1 criterion failed = 1 out of 2 = 0.5
        assert result["score"] == 0.5

    def test_score_all_pass(self, validator):
        t = validator.create_template("score-all", "global",
                                      required_fields_json=[{"name": "a"}],
                                      quality_criteria_json=[
                                          {"field": "b", "min_length": 5}
                                      ])
        result = validator.validate_explanation(t["template_id"],
                                                {"a": "ok", "b": "hello world"})
        assert result["score"] == 1.0

    def test_score_with_missing_field_not_counted(self, validator):
        t = validator.create_template("score-skip", "global",
                                      required_fields_json=[{"name": "a"}],
                                      quality_criteria_json=[
                                          {"field": "b", "min_length": 5}
                                      ])
        # "b" is missing so criterion is not checked, only required field counts
        result = validator.validate_explanation(t["template_id"], {"a": "ok"})
        assert result["score"] == 1.0

    def test_raises_for_missing_template(self, validator):
        with pytest.raises(ValueError, match="not found"):
            validator.validate_explanation("nonexistent", {})

    def test_validation_id_is_unique(self, validator):
        t = validator.create_template("uniq", "global")
        r1 = validator.validate_explanation(t["template_id"], {})
        r2 = validator.validate_explanation(t["template_id"], {})
        assert r1["validation_id"] != r2["validation_id"]

    def test_validation_timestamp(self, validator):
        t = validator.create_template("ts-v", "global")
        before = time.time()
        result = validator.validate_explanation(t["template_id"], {})
        after = time.time()
        assert before <= result["validated_at"] <= after


# ---------------------------------------------------------------------------
# Test: list_validations
# ---------------------------------------------------------------------------

class TestListValidations:
    def test_lists_all(self, validator):
        t = validator.create_template("lv", "global")
        validator.validate_explanation(t["template_id"], {})
        validator.validate_explanation(t["template_id"], {})
        assert len(validator.list_validations()) == 2

    def test_filter_by_template(self, validator):
        t1 = validator.create_template("lv1", "global")
        t2 = validator.create_template("lv2", "global")
        validator.validate_explanation(t1["template_id"], {})
        validator.validate_explanation(t2["template_id"], {})
        result = validator.list_validations(template_id=t1["template_id"])
        assert len(result) == 1

    def test_respects_limit(self, validator):
        t = validator.create_template("lvlim", "global")
        for _ in range(10):
            validator.validate_explanation(t["template_id"], {})
        result = validator.list_validations(limit=5)
        assert len(result) == 5


# ---------------------------------------------------------------------------
# Test: get_validation_stats
# ---------------------------------------------------------------------------

class TestGetValidationStats:
    def test_empty_stats(self, validator):
        stats = validator.get_validation_stats()
        assert stats["total_validations"] == 0
        assert stats["passed"] == 0
        assert stats["failed"] == 0
        assert stats["pass_rate"] == 0.0
        assert stats["average_score"] == 0.0
        assert stats["template_count"] == 0

    def test_counts_pass_fail(self, validator):
        t = validator.create_template("stats", "global",
                                      required_fields_json=[{"name": "x"}])
        validator.validate_explanation(t["template_id"], {"x": "ok"})
        validator.validate_explanation(t["template_id"], {})
        stats = validator.get_validation_stats()
        assert stats["total_validations"] == 2
        assert stats["passed"] == 1
        assert stats["failed"] == 1
        assert stats["pass_rate"] == 0.5

    def test_template_count(self, validator):
        validator.create_template("tc1", "global")
        validator.create_template("tc2", "global")
        stats = validator.get_validation_stats()
        assert stats["template_count"] == 2


# ---------------------------------------------------------------------------
# Test: EventBus integration
# ---------------------------------------------------------------------------

class TestEventBusIntegration:
    def test_template_created_event(self, validator_with_bus):
        validator, bus = validator_with_bus
        events = []
        bus.subscribe("template_created", lambda e: events.append(e))
        validator.create_template("ev-create", "global")
        assert len(events) == 1
        assert events[0].payload["name"] == "ev-create"

    def test_explanation_validated_event(self, validator_with_bus):
        validator, bus = validator_with_bus
        events = []
        bus.subscribe("explanation_validated", lambda e: events.append(e))
        t = validator.create_template("ev-pass", "global",
                                      required_fields_json=[{"name": "x"}])
        validator.validate_explanation(t["template_id"], {"x": "ok"})
        assert len(events) == 1
        assert events[0].payload["passed"] is True

    def test_validation_failed_event(self, validator_with_bus):
        validator, bus = validator_with_bus
        events = []
        bus.subscribe("validation_failed", lambda e: events.append(e))
        t = validator.create_template("ev-fail", "global",
                                      required_fields_json=[{"name": "x"}])
        validator.validate_explanation(t["template_id"], {})
        assert len(events) == 1
        assert events[0].payload["passed"] is False

    def test_no_event_without_bus(self, validator):
        t = validator.create_template("no-bus", "global",
                                      required_fields_json=[{"name": "x"}])
        validator.validate_explanation(t["template_id"], {})


# ---------------------------------------------------------------------------
# Test: thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_creates(self, validator):
        errors = []

        def create(i):
            try:
                validator.create_template(f"t-{i}", "global")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=create, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(validator.list_templates()) == 20

    def test_concurrent_validations(self, validator):
        t = validator.create_template("conc-v", "global")
        errors = []

        def validate(i):
            try:
                validator.validate_explanation(t["template_id"], {"x": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=validate, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self, validator):
        t = validator.create_template("rw", "global")
        errors = []

        def reader():
            try:
                for _ in range(50):
                    validator.list_templates()
                    validator.list_validations()
                    validator.get_validation_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    validator.validate_explanation(t["template_id"], {"x": i})
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Test: singleton management
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_returns_same_instance(self):
        reset_self_explanation_validator()
        s1 = get_self_explanation_validator(db_path=":memory:")
        s2 = get_self_explanation_validator()
        assert s1 is s2
        reset_self_explanation_validator()

    def test_reset_clears_singleton(self):
        s1 = get_self_explanation_validator(db_path=":memory:")
        reset_self_explanation_validator()
        s2 = get_self_explanation_validator(db_path=":memory:")
        assert s1 is not s2
        reset_self_explanation_validator()
