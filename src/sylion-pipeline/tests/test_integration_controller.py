"""Tests for sylion.aeis.integration_controller module."""
import pytest
from sylion.aeis.integration_controller import IntegrationController


class TestIntegrationController:
    @pytest.fixture
    def ctrl(self):
        return IntegrationController()

    def test_initial_stage_is_observe(self, ctrl):
        stage = ctrl.get_current_stage()
        assert stage["stage"] == "observe"

    def test_start_stage(self, ctrl):
        result = ctrl.start_stage("propose")
        assert result["to_stage"] == "propose"

    def test_start_invalid_stage(self, ctrl):
        result = ctrl.start_stage("invalid")
        assert "error" in result

    def test_get_stage_prerequisites(self, ctrl):
        prereqs = ctrl.get_stage_prerequisites("propose")
        assert prereqs["valid"] is True
        assert isinstance(prereqs["prerequisites"], list)

    def test_get_stage_prerequisites_invalid(self, ctrl):
        prereqs = ctrl.get_stage_prerequisites("nonexistent")
        assert prereqs["valid"] is False

    def test_validate_transition_forward(self, ctrl):
        result = ctrl.validate_transition("observe", "propose")
        assert result["valid"] is True

    def test_validate_transition_skip(self, ctrl):
        result = ctrl.validate_transition("observe", "sandbox")
        assert result["valid"] is False

    def test_validate_transition_invalid(self, ctrl):
        result = ctrl.validate_transition("observe", "invalid")
        assert result["valid"] is False

    def test_advance_stage(self, ctrl):
        result = ctrl.advance_stage()
        assert result["advanced"] is True
        assert result["to_stage"] == "propose"

    def test_advance_from_highest(self, ctrl):
        for _ in range(4):
            ctrl.advance_stage()
        result = ctrl.advance_stage()
        assert result["advanced"] is False

    def test_emergency_downgrade(self, ctrl):
        ctrl.advance_stage()
        result = ctrl.emergency_downgrade("test emergency")
        assert result["downgraded"] is True
        assert result["to_stage"] == "observe"

    def test_emergency_from_observe(self, ctrl):
        result = ctrl.emergency_downgrade("noop")
        assert result["downgraded"] is False

    def test_get_stage_history(self, ctrl):
        ctrl.start_stage("propose")
        history = ctrl.get_stage_history()
        assert len(history) >= 1

    def test_get_stats(self, ctrl):
        ctrl.start_stage("propose")
        stats = ctrl.get_stats()
        assert stats["current_stage"] == "propose"
        assert stats["total_transitions"] >= 1
