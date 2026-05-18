from __future__ import annotations

from sylion.core.evidence_spine import EvidenceSpine
from sylion.quality.load_test import LoadTestProfile, LoadTestRunner
from sylion.worker.registry import WorkerRegistry


def test_load_test_10x_records_metrics_and_passes_thresholds():
    runner = LoadTestRunner(
        db_path=":memory:",
        evidence_spine=EvidenceSpine(":memory:"),
        worker_registry=WorkerRegistry(":memory:"),
    )

    run = runner.run_10x(LoadTestProfile(
        expected_peak_operations=5,
        peak_multiplier=10,
        target_p99_ms=500,
        worker_count=2,
    ))

    assert run["status"] == "pass"
    assert run["target_operations"] == 50
    assert run["evidence_id"]
    metrics = run["payload"]["metrics"]
    assert metrics["p99_ms"] <= 500
    assert metrics["dispatch_p99_ms"] <= 500
    assert metrics["db_connections_opened"] <= 5
    assert run["payload"]["checks"]["no_memory_leak_detected"] is True


def test_load_test_fails_closed_when_p99_target_is_too_low():
    runner = LoadTestRunner(
        db_path=":memory:",
        evidence_spine=EvidenceSpine(":memory:"),
        worker_registry=WorkerRegistry(":memory:"),
    )

    run = runner.run_10x(LoadTestProfile(
        expected_peak_operations=2,
        peak_multiplier=10,
        target_p99_ms=0.001,
        worker_count=1,
    ))

    assert run["status"] == "fail"
    assert run["payload"]["checks"]["p99_under_target"] is False


def test_load_test_profile_requires_10x_multiplier():
    profile = LoadTestProfile(expected_peak_operations=5, peak_multiplier=9)

    try:
        profile.validate()
    except ValueError as exc:
        assert "peak_multiplier must be at least 10" in str(exc)
    else:
        raise AssertionError("profile.validate() should fail for multiplier below 10")
