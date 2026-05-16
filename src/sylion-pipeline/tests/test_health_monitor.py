"""Tests for SYLION AEIS Module Health Monitor (20+ tests)."""
import time

import pytest

from sylion.core.health_monitor import ModuleHealthMonitor, DEFAULT_HEALTHY_THRESHOLD, DEFAULT_DEGRADED_THRESHOLD
from sylion.core.module_registry import ModuleRegistry, ModuleManifest, ModuleKind
from sylion.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry():
    return ModuleRegistry()


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def monitor(registry, event_bus):
    return ModuleHealthMonitor(registry=registry, event_bus=event_bus)


def _register_module(registry, module_id="test.mod", kind=ModuleKind.CORE_KERNEL, plan="P01"):
    manifest = ModuleManifest(module_id=module_id, module_kind=kind, owner_plan=plan)
    registry.register(manifest)
    return manifest


# ===========================================================================
# 1. check_health — basic status classification
# ===========================================================================

def test_check_health_unknown_for_unregistered_module(monitor):
    """Unregistered module_id returns status=unknown."""
    result = monitor.check_health("nonexistent")
    assert result["status"] == "unknown"
    assert result["healthy"] is False
    assert result["age_seconds"] == -1
    assert result["last_heartbeat"] is None


def test_check_health_healthy_immediately_after_registration(monitor, registry):
    """Freshly registered module (< 60s) is healthy."""
    _register_module(registry, "mod.fresh")
    result = monitor.check_health("mod.fresh")
    assert result["status"] == "healthy"
    assert result["healthy"] is True
    assert result["age_seconds"] >= 0


def test_check_health_returns_correct_fields(monitor, registry):
    """check_health returns all expected keys."""
    _register_module(registry, "mod.fields")
    result = monitor.check_health("mod.fields")
    assert "module_id" in result
    assert "status" in result
    assert "last_heartbeat" in result
    assert "age_seconds" in result
    assert "healthy" in result


def test_check_health_degraded_with_old_heartbeat(monitor, registry):
    """Module with heartbeat 120s ago should be degraded."""
    _register_module(registry, "mod.degraded")
    # Manually age the heartbeat
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "mod.degraded"),
    )
    registry._conn.commit()
    result = monitor.check_health("mod.degraded")
    assert result["status"] == "degraded"
    assert result["healthy"] is False


def test_check_health_unhealthy_with_very_old_heartbeat(monitor, registry):
    """Module with heartbeat > 300s ago should be unhealthy."""
    _register_module(registry, "mod.unhealthy")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 600, "mod.unhealthy"),
    )
    registry._conn.commit()
    result = monitor.check_health("mod.unhealthy")
    assert result["status"] == "unhealthy"
    assert result["healthy"] is False


def test_check_health_boundary_exactly_60_seconds(monitor, registry):
    """Module at exactly 60s age is degraded (>= 60 check)."""
    _register_module(registry, "mod.boundary60")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 60, "mod.boundary60"),
    )
    registry._conn.commit()
    result = monitor.check_health("mod.boundary60")
    # age >= 60 means not healthy, but < 300 means degraded
    assert result["status"] == "degraded"


def test_check_health_boundary_exactly_300_seconds(monitor, registry):
    """Module at exactly 300s age is unhealthy (>= 300 check)."""
    _register_module(registry, "mod.boundary300")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 300, "mod.boundary300"),
    )
    registry._conn.commit()
    result = monitor.check_health("mod.boundary300")
    assert result["status"] == "unhealthy"


# ===========================================================================
# 2. check_all — bulk health check
# ===========================================================================

def test_check_all_empty_registry(monitor):
    """check_all on empty registry returns empty list."""
    results = monitor.check_all()
    assert results == []


def test_check_all_returns_all_modules(monitor, registry):
    """check_all returns health for every registered module."""
    _register_module(registry, "all.a")
    _register_module(registry, "all.b")
    _register_module(registry, "all.c")
    results = monitor.check_all()
    ids = {r["module_id"] for r in results}
    assert ids == {"all.a", "all.b", "all.c"}


def test_check_all_mixed_statuses(monitor, registry):
    """check_all returns mixed statuses when modules vary."""
    _register_module(registry, "mix.healthy")
    _register_module(registry, "mix.degraded")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "mix.degraded"),
    )
    registry._conn.commit()

    results = monitor.check_all()
    statuses = {r["module_id"]: r["status"] for r in results}
    assert statuses["mix.healthy"] == "healthy"
    assert statuses["mix.degraded"] == "degraded"


# ===========================================================================
# 3. get_stats — aggregate statistics
# ===========================================================================

def test_get_stats_empty(monitor):
    """get_stats on empty registry returns zeros."""
    stats = monitor.get_stats()
    assert stats["total"] == 0
    assert stats["healthy"] == 0
    assert stats["degraded"] == 0
    assert stats["unhealthy"] == 0
    assert stats["unknown"] == 0
    assert stats["avg_age_seconds"] == -1.0


def test_get_stats_counts_correctly(monitor, registry):
    """get_stats counts modules in each status bucket."""
    _register_module(registry, "stats.ok")
    _register_module(registry, "stats.warn")
    _register_module(registry, "stats.bad")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "stats.warn"),
    )
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 600, "stats.bad"),
    )
    registry._conn.commit()

    stats = monitor.get_stats()
    assert stats["total"] == 3
    assert stats["healthy"] == 1
    assert stats["degraded"] == 1
    assert stats["unhealthy"] == 1


def test_get_stats_avg_age(monitor, registry):
    """get_stats computes average age correctly."""
    _register_module(registry, "avg.1")
    _register_module(registry, "avg.2")
    stats = monitor.get_stats()
    assert stats["avg_age_seconds"] >= 0
    assert stats["total"] == 2


# ===========================================================================
# 4. record_heartbeat — recording heartbeats
# ===========================================================================

def test_record_heartbeat_updates_status(monitor, registry):
    """Recording a heartbeat makes the module healthy."""
    _register_module(registry, "hb.update")
    # Age it
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "hb.update"),
    )
    registry._conn.commit()
    assert monitor.check_health("hb.update")["status"] == "degraded"

    # Now record heartbeat
    result = monitor.record_heartbeat("hb.update")
    assert result["status"] == "healthy"
    assert result["healthy"] is True


def test_record_heartbeat_unregistered_module(monitor):
    """Recording heartbeat for unregistered module returns error."""
    result = monitor.record_heartbeat("no.such.module")
    assert "error" in result
    assert result["status"] == "unknown"


def test_record_heartbeat_logs_to_table(monitor, registry):
    """Heartbeat is persisted to sylion_heartbeat_log table."""
    _register_module(registry, "hb.log")
    monitor.record_heartbeat("hb.log")
    monitor.record_heartbeat("hb.log")
    history = monitor.get_heartbeat_history("hb.log")
    assert len(history) == 2


def test_record_heartbeat_emits_event(monitor, registry, event_bus):
    """Heartbeat publishes a module.heartbeat event."""
    import json
    _register_module(registry, "hb.event")
    monitor.record_heartbeat("hb.event")
    events = event_bus.query(topic="module.heartbeat")
    assert len(events) >= 1
    # event_bus stores payload as JSON string
    payload = events[0]["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    assert payload["module_id"] == "hb.event"


# ===========================================================================
# 5. set_alert_threshold — per-module thresholds
# ===========================================================================

def test_set_alert_threshold_default(monitor, registry):
    """Default threshold is 300 seconds."""
    _register_module(registry, "thresh.default")
    threshold = monitor._get_threshold("thresh.default")
    assert threshold == DEFAULT_DEGRADED_THRESHOLD


def test_set_alert_threshold_custom(monitor, registry):
    """Custom threshold overrides the default."""
    _register_module(registry, "thresh.custom")
    monitor.set_alert_threshold("thresh.custom", 120)
    threshold = monitor._get_threshold("thresh.custom")
    assert threshold == 120


def test_set_alert_threshold_affects_classification(monitor, registry):
    """Lowering threshold makes module unhealthy sooner."""
    _register_module(registry, "thresh.affect")
    monitor.set_alert_threshold("thresh.affect", 60)

    # Heartbeat 90s ago: default would be degraded, but with 60s threshold it is unhealthy
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 90, "thresh.affect"),
    )
    registry._conn.commit()

    result = monitor.check_health("thresh.affect")
    assert result["status"] == "unhealthy"


def test_set_alert_threshold_returns_result(monitor, registry):
    """set_alert_threshold returns the configured values."""
    result = monitor.set_alert_threshold("thresh.ret", 45)
    assert result["module_id"] == "thresh.ret"
    assert result["max_age_seconds"] == 45


def test_set_alert_threshold_update_existing(monitor, registry):
    """Updating an existing threshold overwrites the old value."""
    _register_module(registry, "thresh.upd")
    monitor.set_alert_threshold("thresh.upd", 100)
    assert monitor._get_threshold("thresh.upd") == 100
    monitor.set_alert_threshold("thresh.upd", 200)
    assert monitor._get_threshold("thresh.upd") == 200


# ===========================================================================
# 6. get_heartbeat_history
# ===========================================================================

def test_get_heartbeat_history_empty(monitor, registry):
    """No heartbeats returns empty list."""
    _register_module(registry, "hist.empty")
    history = monitor.get_heartbeat_history("hist.empty")
    assert history == []


def test_get_heartbeat_history_respects_limit(monitor, registry):
    """History is capped by the limit parameter."""
    _register_module(registry, "hist.limit")
    for _ in range(10):
        monitor.record_heartbeat("hist.limit")
    history = monitor.get_heartbeat_history("hist.limit", limit=3)
    assert len(history) == 3


def test_get_heartbeat_history_sorted_desc(monitor, registry):
    """History is sorted by timestamp descending."""
    _register_module(registry, "hist.sort")
    monitor.record_heartbeat("hist.sort")
    monitor.record_heartbeat("hist.sort")
    history = monitor.get_heartbeat_history("hist.sort")
    assert len(history) == 2
    assert history[0]["timestamp"] >= history[1]["timestamp"]


# ===========================================================================
# 7. Integration — multiple modules, varied health
# ===========================================================================

def test_integration_full_workflow(monitor, registry, event_bus):
    """End-to-end: register, heartbeat, age, check stats."""
    _register_module(registry, "wf.a")
    _register_module(registry, "wf.b")
    _register_module(registry, "wf.c")

    # Record heartbeats
    monitor.record_heartbeat("wf.a")
    monitor.record_heartbeat("wf.b")
    monitor.record_heartbeat("wf.c")

    # All healthy
    stats = monitor.get_stats()
    assert stats["healthy"] == 3

    # Age one module to degraded
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "wf.b"),
    )
    registry._conn.commit()

    # Age another to unhealthy
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 500, "wf.c"),
    )
    registry._conn.commit()

    stats = monitor.get_stats()
    assert stats["healthy"] == 1
    assert stats["degraded"] == 1
    assert stats["unhealthy"] == 1

    # Recover the unhealthy module
    monitor.record_heartbeat("wf.c")
    assert monitor.check_health("wf.c")["status"] == "healthy"


def test_integration_heartbeat_heals_degraded(monitor, registry):
    """A degraded module becomes healthy after a new heartbeat."""
    _register_module(registry, "heal.mod")
    registry._conn.execute(
        "UPDATE sylion_modules SET last_heartbeat=? WHERE module_id=?",
        (time.time() - 120, "heal.mod"),
    )
    registry._conn.commit()
    assert monitor.check_health("heal.mod")["status"] == "degraded"

    monitor.record_heartbeat("heal.mod")
    assert monitor.check_health("heal.mod")["status"] == "healthy"


# ===========================================================================
# 8. Thread safety / close
# ===========================================================================

def test_close_does_not_crash(monitor, registry):
    """Monitor close() completes without error."""
    _register_module(registry, "close.mod")
    monitor.record_heartbeat("close.mod")
    monitor.close()


def test_monitor_with_no_event_bus(registry):
    """Monitor works without an event_bus (graceful None handling)."""
    mon = ModuleHealthMonitor(registry=registry, event_bus=None)
    _register_module(registry, "noeb.mod", plan="P01")
    result = mon.record_heartbeat("noeb.mod")
    assert result["status"] == "healthy"
    assert result["healthy"] is True
    mon.close()


def test_monitor_with_persistent_db(registry, event_bus, tmp_path):
    """Monitor can use a file-based SQLite database."""
    db_file = tmp_path / "health_test.db"
    mon = ModuleHealthMonitor(registry=registry, event_bus=event_bus, db_path=str(db_file))
    _register_module(registry, "persist.mod")
    mon.record_heartbeat("persist.mod")
    history = mon.get_heartbeat_history("persist.mod")
    assert len(history) == 1
    mon.close()
