"""
Tests for sylion.rebuild.cutover_automation — CutoverAutomation

Covers:
  - initiate_cutover (approval validation, contract creation, lifecycle transition)
  - monitor_cutover (healthy metrics, rollback triggers)
  - complete_cutover (happy path, edge cases)
  - auto_rollback (heartbeat timeout, error rate, council revocation)
  - get_cutover_status / list_active_cutover
  - error rate computation
  - rollback contract persistence
  - event emission
  - thread safety
  - double-initiation guard
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.core.module_registry import (
    ModuleKind,
    ModuleLifecycleStage,
    ModuleManifest,
    ModuleRegistry,
)
from sylion.rebuild.cutover_automation import (
    CutoverAutomation,
    CutoverState,
    ERROR_RATE_THRESHOLD,
    HEARTBEAT_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry():
    """Fresh in-memory module registry with a module in 'dual' state."""
    reg = ModuleRegistry()
    manifest = ModuleManifest(
        module_id="mod-alpha",
        module_kind=ModuleKind.COGNITIVE,
        owner_plan="P01",
    )
    # Register in draft, then transition to dual
    reg.register(manifest)
    reg.transition("mod-alpha", ModuleLifecycleStage.BUILD)
    reg.transition("mod-alpha", ModuleLifecycleStage.VALIDATE)
    reg.transition("mod-alpha", ModuleLifecycleStage.SHADOW)
    reg.transition("mod-alpha", ModuleLifecycleStage.DUAL)
    return reg


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def automation(registry, event_bus):
    """CutoverAutomation wired to in-memory registry + event bus."""
    return CutoverAutomation(
        registry=registry,
        event_bus=event_bus,
        db_path=None,  # :memory:
    )


def _initiate(automation: CutoverAutomation, module_id: str = "mod-alpha",
              approval_id: str = "D3-2026-001") -> dict:
    """Helper to initiate a cutover."""
    return automation.initiate_cutover(module_id, approval_id)


# ===========================================================================
# 1. initiate_cutover — approval validation
# ===========================================================================

class TestInitiateCutoverApproval:
    def test_reject_empty_approval(self, automation):
        result = automation.initiate_cutover("mod-alpha", "")
        assert "error" in result
        assert "approval_id is required" in result["error"]

    def test_reject_whitespace_approval(self, automation):
        result = automation.initiate_cutover("mod-alpha", "   ")
        assert "error" in result

    def test_reject_bad_format_approval(self, automation):
        result = automation.initiate_cutover("mod-alpha", "short")
        assert "error" in result
        assert "invalid approval_id format" in result["error"]

    def test_reject_unknown_module(self, automation):
        result = automation.initiate_cutover("nonexistent", "D3-2026-999")
        assert "error" in result
        assert "not found" in result["error"]

    def test_reject_module_not_dual(self, registry):
        # Register a module that stays in draft
        manifest = ModuleManifest(
            module_id="mod-draft",
            module_kind=ModuleKind.MEMORY,
            owner_plan="P02",
        )
        registry.register(manifest)
        auto = CutoverAutomation(registry=registry)
        result = auto.initiate_cutover("mod-draft", "D3-2026-010")
        assert "error" in result
        assert "dual" in result["error"]


# ===========================================================================
# 2. initiate_cutover — happy path
# ===========================================================================

class TestInitiateCutoverHappyPath:
    def test_returns_session_id(self, automation):
        result = _initiate(automation)
        assert "session_id" in result
        assert len(result["session_id"]) == 32

    def test_state_is_active(self, automation):
        result = _initiate(automation)
        assert result["state"] == CutoverState.ACTIVE.value

    def test_contract_id_returned(self, automation):
        result = _initiate(automation)
        assert "contract_id" in result
        assert len(result["contract_id"]) == 32

    def test_module_lifecycle_is_cutover(self, automation, registry):
        _initiate(automation)
        mod = registry.get("mod-alpha")
        assert mod["lifecycle"] == "cutover"

    def test_rollback_contract_stored(self, automation):
        result = _initiate(automation)
        contract = automation._get_contract(result["contract_id"])
        assert contract is not None
        assert contract["module_id"] == "mod-alpha"

    def test_event_published(self, automation, event_bus):
        events = []
        event_bus.subscribe("rebuild.cutover.initiated",
                            lambda e: events.append(e))
        _initiate(automation)
        assert len(events) == 1
        assert events[0].payload["module_id"] == "mod-alpha"

    def test_double_initiation_rejected(self, automation):
        _initiate(automation)
        result = _initiate(automation)
        assert "error" in result
        # Rejected because module is no longer in 'dual' state
        assert "dual" in result["error"] or "active cutover already exists" in result["error"]


# ===========================================================================
# 3. complete_cutover
# ===========================================================================

class TestCompleteCutover:
    def test_complete_happy_path(self, automation, registry):
        _initiate(automation)
        result = automation.complete_cutover("mod-alpha")
        assert result["state"] == CutoverState.COMPLETED.value
        mod = registry.get("mod-alpha")
        assert mod["lifecycle"] == "stable"

    def test_complete_no_active_session(self, automation):
        result = automation.complete_cutover("mod-alpha")
        assert "error" in result
        assert "no active cutover" in result["error"]

    def test_complete_publishes_event(self, automation, event_bus):
        events = []
        event_bus.subscribe("rebuild.cutover.completed",
                            lambda e: events.append(e))
        _initiate(automation)
        automation.complete_cutover("mod-alpha")
        assert len(events) == 1

    def test_complete_idempotent_after_rollback(self, automation):
        _initiate(automation)
        automation.auto_rollback("mod-alpha", "test")
        result = automation.complete_cutover("mod-alpha")
        assert "error" in result  # no longer active


# ===========================================================================
# 4. auto_rollback
# ===========================================================================

class TestAutoRollback:
    def test_rollback_returns_rolled_back_state(self, automation, registry):
        _initiate(automation)
        result = automation.auto_rollback("mod-alpha", "degraded performance")
        assert result["state"] == CutoverState.ROLLED_BACK.value
        assert result["reason"] == "degraded performance"

    def test_rollback_restores_dual_lifecycle(self, automation, registry):
        _initiate(automation)
        automation.auto_rollback("mod-alpha", "test")
        mod = registry.get("mod-alpha")
        assert mod["lifecycle"] == "dual"

    def test_rollback_publishes_event(self, automation, event_bus):
        events = []
        event_bus.subscribe("rebuild.cutover.rolled_back",
                            lambda e: events.append(e))
        _initiate(automation)
        automation.auto_rollback("mod-alpha", "test")
        assert len(events) == 1
        assert events[0].payload["reason"] == "test"

    def test_rollback_no_active_session(self, automation):
        result = automation.auto_rollback("mod-alpha", "nothing")
        assert "error" in result

    def test_rollback_delegates_to_external_manager(self, registry, event_bus):
        rb_manager = MagicMock()
        auto = CutoverAutomation(registry=registry, event_bus=event_bus,
                                  rollback_manager=rb_manager)
        auto.initiate_cutover("mod-alpha", "D3-2026-050")
        auto.auto_rollback("mod-alpha", "external trigger")
        rb_manager.execute_rollback.assert_called_once()
        call_args = rb_manager.execute_rollback.call_args
        assert call_args[0][1] == "external trigger"


# ===========================================================================
# 5. monitor_cutover — health checks
# ===========================================================================

class TestMonitorCutover:
    def test_monitor_healthy_module(self, automation):
        _initiate(automation)
        # Heartbeat is fresh (just set by transition)
        result = automation.monitor_cutover("mod-alpha")
        assert result["healthy"] is True
        assert result["state"] == CutoverState.ACTIVE.value

    def test_monitor_heartbeat_timeout_triggers_rollback(self, automation, registry):
        _initiate(automation)
        # Artificially age the heartbeat
        registry._conn.execute(
            "UPDATE sylion_modules SET last_heartbeat = ? WHERE module_id = ?",
            (time.time() - HEARTBEAT_TIMEOUT_S - 10, "mod-alpha"),
        )
        registry._conn.commit()
        result = automation.monitor_cutover("mod-alpha")
        assert result["healthy"] is False
        assert "heartbeat timeout" in result["rollback_reason"]

    def test_monitor_error_rate_triggers_rollback(self, automation):
        _initiate(automation)
        # Record 6 errors out of 100 requests => 6% > 5%
        for _ in range(100):
            automation.record_request("mod-alpha")
        for _ in range(6):
            automation.record_error("mod-alpha", "test error")
        result = automation.monitor_cutover("mod-alpha")
        assert result["healthy"] is False
        assert "error rate" in result["rollback_reason"]

    def test_monitor_no_session(self, automation):
        result = automation.monitor_cutover("mod-alpha")
        assert "error" in result

    def test_monitor_completed_session(self, automation):
        _initiate(automation)
        automation.complete_cutover("mod-alpha")
        result = automation.monitor_cutover("mod-alpha")
        assert result["state"] == CutoverState.COMPLETED.value
        assert result["healthy"] is True


# ===========================================================================
# 6. get_cutover_status / list_active_cutover
# ===========================================================================

class TestStatusQueries:
    def test_status_no_session(self, automation):
        status = automation.get_cutover_status("mod-alpha")
        assert status["active"] is False
        assert status["state"] is None

    def test_status_active_session(self, automation):
        _initiate(automation)
        status = automation.get_cutover_status("mod-alpha")
        assert status["active"] is True
        assert status["state"] == CutoverState.ACTIVE.value

    def test_status_completed_session(self, automation):
        _initiate(automation)
        automation.complete_cutover("mod-alpha")
        status = automation.get_cutover_status("mod-alpha")
        assert status["active"] is False
        assert status["state"] == CutoverState.COMPLETED.value

    def test_list_active_empty(self, automation):
        active = automation.list_active_cutover()
        assert active == []

    def test_list_active_returns_active_only(self, automation):
        _initiate(automation)
        active = automation.list_active_cutover()
        assert len(active) == 1
        assert active[0]["module_id"] == "mod-alpha"

    def test_list_active_excludes_completed(self, automation):
        _initiate(automation)
        automation.complete_cutover("mod-alpha")
        active = automation.list_active_cutover()
        assert len(active) == 0


# ===========================================================================
# 7. Error rate computation
# ===========================================================================

class TestErrorRate:
    def test_zero_errors_zero_rate(self, automation):
        automation.record_request("mod-x", 10)
        rate = automation._compute_error_rate("mod-x")
        assert rate == 0.0

    def test_below_threshold(self, automation):
        automation.record_request("mod-y", 100)
        for _ in range(3):
            automation.record_error("mod-y")
        rate = automation._compute_error_rate("mod-y")
        assert rate == pytest.approx(0.03, abs=0.01)

    def test_above_threshold(self, automation):
        automation.record_request("mod-z", 100)
        for _ in range(10):
            automation.record_error("mod-z")
        rate = automation._compute_error_rate("mod-z")
        assert rate == pytest.approx(0.10, abs=0.01)
        assert rate > ERROR_RATE_THRESHOLD


# ===========================================================================
# 8. Council revocation
# ===========================================================================

class TestCouncilRevocation:
    def test_revoke_triggers_rollback(self, automation, registry):
        _initiate(automation)
        result = automation.revoke_approval("mod-alpha")
        assert result["state"] == CutoverState.ROLLED_BACK.value
        assert "revoked" in result["reason"]

    def test_revoke_no_active_cutover(self, automation):
        result = automation.revoke_approval("mod-alpha")
        assert "error" in result


# ===========================================================================
# 9. Rollback contract snapshot
# ===========================================================================

class TestRollbackContract:
    def test_contract_captures_snapshot(self, automation):
        result = _initiate(automation)
        contract = automation._get_contract(result["contract_id"])
        snapshot = eval(contract["snapshot"])  # stored as JSON string
        assert snapshot["module_id"] == "mod-alpha"
        assert snapshot["lifecycle"] == "dual"


# ===========================================================================
# 10. Thread safety
# ===========================================================================

class TestThreadSafety:
    def test_concurrent_initiate_only_one_succeeds(self, registry, event_bus):
        auto = CutoverAutomation(registry=registry, event_bus=event_bus)
        results = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(3)

        def do_init():
            barrier.wait(timeout=5)
            try:
                r = auto.initiate_cutover("mod-alpha", "D3-2026-THR")
            except Exception as exc:
                r = {"error": str(exc)}
            with results_lock:
                results.append(r)

        threads = [threading.Thread(target=do_init) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        # Exactly one thread should succeed; the others must fail for any reason
        successes = [r for r in results if "error" not in r]
        assert len(successes) == 1
        failures = [r for r in results if "error" in r]
        assert len(failures) == 2


# ===========================================================================
# 11. Metrics logging
# ===========================================================================

class TestMetricsLogging:
    def test_metrics_logged_during_monitor(self, automation):
        _initiate(automation)
        automation.monitor_cutover("mod-alpha")
        rows = automation._conn.execute(
            "SELECT * FROM cutover_metrics_log WHERE module_id = ?",
            ("mod-alpha",),
        ).fetchall()
        assert len(rows) >= 1
        assert rows[0]["heartbeat_age"] >= 0
