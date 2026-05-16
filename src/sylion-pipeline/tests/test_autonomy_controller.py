"""Tests for AutonomyController -- 5-stage rollout per Masterplan R7."""
import time

import pytest

from sylion.aeis.autonomy_controller import (
    AutonomyAction,
    AutonomyController,
    AutonomyStage,
    get_autonomy_controller,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ctrl():
    """Fresh in-memory AutonomyController for each test."""
    return AutonomyController()


@pytest.fixture
def ctrl_at_propose(ctrl):
    """Controller advanced to PROPOSE stage."""
    ctrl.set_stage(AutonomyStage.PROPOSE, override_reason="test setup")
    return ctrl


@pytest.fixture
def ctrl_at_sandbox(ctrl):
    """Controller advanced to SANDBOX stage."""
    ctrl.set_stage(AutonomyStage.SANDBOX, override_reason="test setup")
    return ctrl


@pytest.fixture
def ctrl_at_limited(ctrl):
    """Controller advanced to LIMITED_PROD stage."""
    ctrl.set_stage(AutonomyStage.LIMITED_PROD, override_reason="test setup")
    return ctrl


@pytest.fixture
def ctrl_at_full(ctrl):
    """Controller advanced to FULL_GOVERNED stage."""
    ctrl.set_stage(AutonomyStage.FULL_GOVERNED, override_reason="test setup")
    return ctrl


# ===================================================================
# AutonomyStage enum
# ===================================================================

class TestAutonomyStageEnum:
    def test_observe_value(self):
        assert AutonomyStage.OBSERVE.value == "observe"

    def test_propose_value(self):
        assert AutonomyStage.PROPOSE.value == "propose"

    def test_sandbox_value(self):
        assert AutonomyStage.SANDBOX.value == "sandbox"

    def test_limited_prod_value(self):
        assert AutonomyStage.LIMITED_PROD.value == "limited"

    def test_full_governed_value(self):
        assert AutonomyStage.FULL_GOVERNED.value == "full"

    def test_five_stages_exist(self):
        assert len(AutonomyStage) == 5


# ===================================================================
# Initialization
# ===================================================================

class TestInitialization:
    def test_default_stage_is_observe(self, ctrl):
        assert ctrl.get_stage() == AutonomyStage.OBSERVE

    def test_stage_entered_at_is_set(self, ctrl):
        entered_at = ctrl.get_stage_entered_at()
        assert entered_at > 0
        assert entered_at <= time.time()

    def test_stats_initial(self, ctrl):
        stats = ctrl.get_stats()
        assert stats["current_stage"] == "observe"
        assert stats["total_actions"] == 0
        assert stats["total_gate_checks"] == 0


# ===================================================================
# Gate G-AUTONOMY-1 (observe)
# ===================================================================

class TestGateAutonomy1:
    def test_satisfied_when_clean(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": True,
            "observation_error_count": 0,
        })
        assert result["satisfied"] is True
        assert result["missing"] == []
        assert result["target_stage"] == "observe"

    def test_fails_with_errors(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": True,
            "observation_error_count": 3,
        })
        assert result["satisfied"] is False
        assert "observation_error_count == 0" in result["missing"]

    def test_fails_without_24h(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": False,
            "observation_error_count": 0,
        })
        assert result["satisfied"] is False
        assert "observation_24h_clean" in result["missing"]

    def test_fails_both_missing(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-1", {})
        assert result["satisfied"] is False
        assert len(result["missing"]) == 2

    def test_gate_check_persisted(self, ctrl):
        ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": True,
            "observation_error_count": 0,
        })
        history = ctrl.get_gate_history("G-AUTONOMY-1")
        assert len(history) == 1
        assert history[0]["gate_id"] == "G-AUTONOMY-1"
        assert history[0]["satisfied"] is True


# ===================================================================
# Gate G-AUTONOMY-2 (propose)
# ===================================================================

class TestGateAutonomy2:
    def test_satisfied_when_accurate(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-2", {
            "explanation_accuracy": 0.95,
            "boundaries_mapped": True,
        })
        assert result["satisfied"] is True
        assert result["target_stage"] == "propose"

    def test_fails_below_accuracy(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-2", {
            "explanation_accuracy": 0.85,
            "boundaries_mapped": True,
        })
        assert result["satisfied"] is False
        assert "explanation_accuracy > 0.90" in result["missing"]

    def test_fails_without_boundaries(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-2", {
            "explanation_accuracy": 0.95,
            "boundaries_mapped": False,
        })
        assert result["satisfied"] is False
        assert "boundaries_mapped" in result["missing"]

    def test_exact_90_accuracy_fails(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-2", {
            "explanation_accuracy": 0.90,
            "boundaries_mapped": True,
        })
        assert result["satisfied"] is False


# ===================================================================
# Gate G-AUTONOMY-3 (sandbox)
# ===================================================================

class TestGateAutonomy3:
    def test_satisfied_with_10_proposals(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-3", {
            "improvement_proposals_count": 10,
            "all_proposals_reviewed": True,
        })
        assert result["satisfied"] is True
        assert result["target_stage"] == "sandbox"

    def test_fails_below_10(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-3", {
            "improvement_proposals_count": 9,
            "all_proposals_reviewed": True,
        })
        assert result["satisfied"] is False

    def test_fails_unreviewed(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-3", {
            "improvement_proposals_count": 15,
            "all_proposals_reviewed": False,
        })
        assert result["satisfied"] is False
        assert "all_proposals_reviewed" in result["missing"]


# ===================================================================
# Gate G-AUTONOMY-4 (limited-prod)
# ===================================================================

class TestGateAutonomy4:
    def test_satisfied_with_5_executions(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-4", {
            "sandbox_executions_count": 5,
            "sandbox_side_effects": 0,
        })
        assert result["satisfied"] is True
        assert result["target_stage"] == "limited"

    def test_fails_below_5_executions(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-4", {
            "sandbox_executions_count": 4,
            "sandbox_side_effects": 0,
        })
        assert result["satisfied"] is False

    def test_fails_with_side_effects(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-4", {
            "sandbox_executions_count": 10,
            "sandbox_side_effects": 1,
        })
        assert result["satisfied"] is False
        assert "sandbox_side_effects == 0" in result["missing"]


# ===================================================================
# Gate G-AUTONOMY-5 (full-governed)
# ===================================================================

class TestGateAutonomy5:
    def test_satisfied_all_met(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-5", {
            "council_approved": True,
            "external_reviewed": True,
            "limited_prod_days_clean": 30,
        })
        assert result["satisfied"] is True
        assert result["target_stage"] == "full"

    def test_fails_without_council(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-5", {
            "council_approved": False,
            "external_reviewed": True,
            "limited_prod_days_clean": 30,
        })
        assert result["satisfied"] is False
        assert "council_approved" in result["missing"]

    def test_fails_without_external_review(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-5", {
            "council_approved": True,
            "external_reviewed": False,
            "limited_prod_days_clean": 30,
        })
        assert result["satisfied"] is False
        assert "external_reviewed" in result["missing"]

    def test_fails_below_30_days(self, ctrl):
        result = ctrl.check_gate("G-AUTONOMY-5", {
            "council_approved": True,
            "external_reviewed": True,
            "limited_prod_days_clean": 29,
        })
        assert result["satisfied"] is False
        assert "limited_prod_days_clean >= 30" in result["missing"]


# ===================================================================
# Unknown gate
# ===================================================================

class TestUnknownGate:
    def test_unknown_gate_returns_not_satisfied(self, ctrl):
        result = ctrl.check_gate("G-UNKNOWN", {})
        assert result["satisfied"] is False
        assert "Unknown gate: G-UNKNOWN" in result["missing"]


# ===================================================================
# Advance stage
# ===================================================================

class TestAdvanceStage:
    def test_advance_observe_to_propose(self, ctrl):
        result = ctrl.advance_stage({
            "explanation_accuracy": 0.95,
            "boundaries_mapped": True,
        })
        assert result["advanced"] is True
        assert result["to_stage"] == "propose"
        assert ctrl.get_stage() == AutonomyStage.PROPOSE

    def test_advance_blocked_by_gate(self, ctrl):
        result = ctrl.advance_stage({
            "explanation_accuracy": 0.80,
            "boundaries_mapped": True,
        })
        assert result["advanced"] is False
        assert ctrl.get_stage() == AutonomyStage.OBSERVE
        assert len(result["missing"]) > 0

    def test_advance_at_max_stage_returns_false(self, ctrl_at_full):
        result = ctrl_at_full.advance_stage({})
        assert result["advanced"] is False
        assert result["message"] == "Already at maximum autonomy stage"

    def test_sequential_advancement(self, ctrl):
        # Stage 1 -> 2
        r = ctrl.advance_stage({
            "explanation_accuracy": 0.95,
            "boundaries_mapped": True,
        })
        assert r["advanced"] is True

        # Stage 2 -> 3
        r = ctrl.advance_stage({
            "improvement_proposals_count": 12,
            "all_proposals_reviewed": True,
        })
        assert r["advanced"] is True

        # Stage 3 -> 4
        r = ctrl.advance_stage({
            "sandbox_executions_count": 6,
            "sandbox_side_effects": 0,
        })
        assert r["advanced"] is True

        # Stage 4 -> 5
        r = ctrl.advance_stage({
            "council_approved": True,
            "external_reviewed": True,
            "limited_prod_days_clean": 35,
        })
        assert r["advanced"] is True
        assert ctrl.get_stage() == AutonomyStage.FULL_GOVERNED


# ===================================================================
# can_execute / authorize
# ===================================================================

class TestCanExecute:
    def test_observe_allows_read(self, ctrl):
        assert ctrl.can_execute(AutonomyAction.READ) is True

    def test_observe_blocks_propose(self, ctrl):
        assert ctrl.can_execute(AutonomyAction.PROPOSE) is False

    def test_observe_blocks_sandbox(self, ctrl):
        assert ctrl.can_execute(AutonomyAction.EXECUTE_SANDBOX) is False

    def test_propose_allows_propose(self, ctrl_at_propose):
        assert ctrl_at_propose.can_execute(AutonomyAction.PROPOSE) is True

    def test_propose_blocks_sandbox(self, ctrl_at_propose):
        assert ctrl_at_propose.can_execute(AutonomyAction.EXECUTE_SANDBOX) is False

    def test_sandbox_allows_sandbox(self, ctrl_at_sandbox):
        assert ctrl_at_sandbox.can_execute(AutonomyAction.EXECUTE_SANDBOX) is True

    def test_sandbox_blocks_limited(self, ctrl_at_sandbox):
        assert ctrl_at_sandbox.can_execute(AutonomyAction.EXECUTE_LIMITED) is False

    def test_limited_allows_limited(self, ctrl_at_limited):
        assert ctrl_at_limited.can_execute(AutonomyAction.EXECUTE_LIMITED) is True

    def test_limited_blocks_full(self, ctrl_at_limited):
        assert ctrl_at_limited.can_execute(AutonomyAction.EXECUTE_FULL) is False

    def test_full_allows_everything(self, ctrl_at_full):
        for action in AutonomyAction:
            assert ctrl_at_full.can_execute(action) is True


# ===================================================================
# authorize and record_action
# ===================================================================

class TestAuthorize:
    def test_authorize_read_at_observe(self, ctrl):
        result = ctrl.authorize(AutonomyAction.READ)
        assert result["allowed"] is True

    def test_authorize_propose_at_observe_denied(self, ctrl):
        result = ctrl.authorize(AutonomyAction.PROPOSE)
        assert result["allowed"] is False

    def test_authorize_records_action(self, ctrl):
        ctrl.authorize(AutonomyAction.READ)
        history = ctrl.get_action_history("read")
        assert len(history) == 1
        assert history[0]["allowed"] is True

    def test_record_action_custom(self, ctrl):
        ctrl.record_action(AutonomyAction.PROPOSE, {"allowed": False, "reason": "stage too low"})
        history = ctrl.get_action_history()
        assert len(history) == 1
        assert history[0]["details"]["reason"] == "stage too low"


# ===================================================================
# set_stage (override)
# ===================================================================

class TestSetStage:
    def test_set_to_propose(self, ctrl):
        result = ctrl.set_stage(AutonomyStage.PROPOSE, "test")
        assert result["new_stage"] == "propose"
        assert ctrl.get_stage() == AutonomyStage.PROPOSE

    def test_set_invalid_raises(self, ctrl):
        with pytest.raises(ValueError):
            ctrl.set_stage("invalid_stage")

    def test_set_updates_entered_at(self, ctrl):
        old_entered = ctrl.get_stage_entered_at()
        time.sleep(0.01)
        ctrl.set_stage(AutonomyStage.SANDBOX, "test")
        new_entered = ctrl.get_stage_entered_at()
        assert new_entered > old_entered


# ===================================================================
# get_stats
# ===================================================================

class TestGetStats:
    def test_stats_with_activity(self, ctrl):
        ctrl.authorize(AutonomyAction.READ)
        ctrl.authorize(AutonomyAction.PROPOSE)
        stats = ctrl.get_stats()
        assert stats["total_actions"] == 2
        assert stats["allowed_actions"] == 1
        assert stats["denied_actions"] == 1
        assert stats["by_action"]["read"] == 1
        assert stats["by_action"]["propose"] == 1


# ===================================================================
# Gate history
# ===================================================================

class TestGateHistory:
    def test_empty_history(self, ctrl):
        history = ctrl.get_gate_history()
        assert history == []

    def test_history_after_checks(self, ctrl):
        ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": True,
            "observation_error_count": 0,
        })
        ctrl.check_gate("G-AUTONOMY-2", {
            "explanation_accuracy": 0.95,
            "boundaries_mapped": True,
        })
        all_history = ctrl.get_gate_history()
        assert len(all_history) == 2

        g1_history = ctrl.get_gate_history("G-AUTONOMY-1")
        assert len(g1_history) == 1
        assert g1_history[0]["gate_id"] == "G-AUTONOMY-1"

    def test_gate_history_parses_checks_json(self, ctrl):
        ctrl.check_gate("G-AUTONOMY-1", {
            "observation_24h_clean": True,
            "observation_error_count": 0,
        })
        history = ctrl.get_gate_history("G-AUTONOMY-1")
        assert isinstance(history[0]["checks"], list)
        assert len(history[0]["checks"]) == 2


# ===================================================================
# Action history
# ===================================================================

class TestActionHistory:
    def test_action_history_filters(self, ctrl):
        ctrl.authorize(AutonomyAction.READ)
        ctrl.authorize(AutonomyAction.PROPOSE)
        ctrl.authorize(AutonomyAction.READ)

        read_history = ctrl.get_action_history("read")
        assert len(read_history) == 2

        propose_history = ctrl.get_action_history("propose")
        assert len(propose_history) == 1


# ===================================================================
# Singleton
# ===================================================================

class TestSingleton:
    def test_get_autonomy_controller_returns_instance(self):
        # Reset global singleton
        import sylion.aeis.autonomy_controller as mod
        mod._controller = None
        c = get_autonomy_controller()
        assert isinstance(c, AutonomyController)
        # Cleanup
        mod._controller = None
