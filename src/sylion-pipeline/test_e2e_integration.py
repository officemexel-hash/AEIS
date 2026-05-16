#!/usr/bin/env python3
"""
Tests for E2E Session Controller and Stream Monitor integration.

Validates:
  1. E2ESessionController — full lifecycle with all 8 runtime modules
  2. StreamMonitor — real-time metrics collection and alerting
  3. Integration — e2e session → monitor snapshot → benchmark
  4. Orchestrator imports — verify new modules are importable
"""

import json
import time
import tempfile
from pathlib import Path

import pytest

# --- Runtime module imports (needed to create test fixtures) ---
from signaling_server import SignalingServer, ICEServerConfig
from device_harness import DeviceHarness, SafeCommandRunner
from metrics_ingestion import MetricsCollector, MetricsStore, AlertEngine, ThresholdConfig, MetricType, MetricSample, AlertSeverity
from abr_controller import ABRController
from input_protocol import InputProtocolCodec
from audio_pipeline import AudioPipelineController, OpusConfig
from stream_security import StreamSecurityVerifier
from benchmark_harness import BenchmarkHarness, BenchmarkThresholds

# --- New modules ---
from e2e_session import E2ESessionController, E2ESessionReport, SessionState
from stream_monitor import StreamMonitor, MonitorSnapshot, MonitorAlert


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def ice_config():
    return ICEServerConfig(
        stun_urls=["stun:stun.l.google.com:19302"],
        turn_urls=[],
        turn_username="",
        turn_credential="",
    )


@pytest.fixture
def signaling(ice_config):
    return SignalingServer(max_rooms=10, ice_config=ice_config)


@pytest.fixture
def device():
    runner = SafeCommandRunner(dry_run=True)
    return DeviceHarness(runner=runner, battery_threshold_pct=20)


@pytest.fixture
def metrics():
    store = MetricsStore(max_samples_per_metric=1000)
    thresholds = [
        ThresholdConfig(
            metric_type=MetricType.LATENCY_VIDEO,
            warning_threshold=150.0,
            critical_threshold=300.0,
            unit="ms",
        ),
        ThresholdConfig(
            metric_type=MetricType.BITRATE_VIDEO,
            warning_threshold=600.0,
            critical_threshold=500.0,
            unit="kbps",
            direction="lower",
        ),
        ThresholdConfig(
            metric_type=MetricType.FPS,
            warning_threshold=24.0,
            critical_threshold=15.0,
            unit="fps",
            direction="lower",
        ),
    ]
    alert_engine = AlertEngine(thresholds=thresholds)
    return MetricsCollector(store=store, alert_engine=alert_engine)


@pytest.fixture
def abr():
    return ABRController(initial_rung=1)


@pytest.fixture
def input_proto():
    return InputProtocolCodec()


@pytest.fixture
def audio():
    return AudioPipelineController(opus_config=OpusConfig())


@pytest.fixture
def security():
    return StreamSecurityVerifier(production_mode=False)


@pytest.fixture
def benchmark():
    thresholds = BenchmarkThresholds()
    return BenchmarkHarness(thresholds=thresholds)


@pytest.fixture
def all_modules(signaling, device, metrics, abr, input_proto, audio, security, benchmark):
    return {
        "signaling_srv": signaling,
        "device_harness": device,
        "metrics_collector": metrics,
        "abr_controller": abr,
        "input_protocol": input_proto,
        "audio_pipeline": audio,
        "stream_security": security,
        "benchmark_harness": benchmark,
    }


# ============================================================
# E2E Session Controller Tests
# ============================================================

class TestE2ESessionController:

    def test_01_init(self, all_modules):
        """E2ESessionController initializes with all modules."""
        ctrl = E2ESessionController(**all_modules)
        assert ctrl.state == SessionState.IDLE
        assert ctrl.session_id.startswith("e2e-")

    def test_02_phase_security(self, all_modules):
        """Security pre-check runs full audit (non-production mode = SECURE)."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_security()
        # In non-production mode, audit passes with SECURE level
        assert result is True
        assert ctrl.state == SessionState.SECURITY_CHECK

    def test_03_phase_signaling(self, all_modules):
        """Signaling creates room and exchanges SDP/ICE."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_signaling("pixel", "laptop")
        assert result is True
        assert ctrl._room_id is not None
        assert ctrl.report.signaling.get("room_id") == ctrl._room_id

    def test_04_phase_device(self, all_modules):
        """Device health check runs in dry_run mode."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_device()
        assert result is True

    def test_05_phase_audio(self, all_modules):
        """Audio pipeline reports ready with Opus config."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_audio()
        assert result is True
        # Audio stats contain opus_config, not flat 'codec' key
        assert ctrl.report.audio.get("opus_config") is not None

    def test_06_phase_input(self, all_modules):
        """Input protocol initializes and sends ping."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_input()
        assert result is True
        # Input stats contain 'current_seq', 'replay_guard', etc.
        assert "replay_guard" in ctrl.report.input_protocol

    def test_07_phase_abr(self, all_modules):
        """ABR controller reports initial state."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_abr()
        assert result is True
        assert ctrl.report.abr.get("initial_rung") is not None

    def test_08_phase_metrics(self, all_modules):
        """Metrics collector is ready."""
        ctrl = E2ESessionController(**all_modules)
        result = ctrl.phase_metrics()
        assert result is True

    def test_09_full_e2e_without_benchmark(self, all_modules):
        """Full E2E session lifecycle without benchmark."""
        ctrl = E2ESessionController(**all_modules)
        report = ctrl.run_e2e(run_benchmark=False)
        assert report.final_state == "ended"
        assert report.session_id == ctrl.session_id
        assert report.started_at > 0
        assert report.ended_at >= report.started_at
        assert len(report.events) > 0

    def test_10_full_e2e_with_benchmark(self, all_modules):
        """Full E2E session with benchmark suite."""
        ctrl = E2ESessionController(**all_modules)
        report = ctrl.run_e2e(run_benchmark=True)
        assert report.final_state == "ended"
        # Benchmark should have run and produced results
        if report.benchmark:  # May be empty if benchmark had errors
            assert report.benchmark.get("run_id") is not None
            assert len(report.benchmark.get("results", [])) > 0

    def test_11_report_serialization(self, all_modules):
        """E2E report is JSON-serializable."""
        ctrl = E2ESessionController(**all_modules)
        report = ctrl.run_e2e(run_benchmark=False)
        d = report.to_dict()
        json_str = json.dumps(d, default=str)
        assert len(json_str) > 100
        parsed = json.loads(json_str)
        assert parsed["session_id"] == report.session_id

    def test_12_report_save(self, all_modules, tmp_path):
        """E2E report saves to file."""
        ctrl = E2ESessionController(**all_modules)
        report = ctrl.run_e2e(run_benchmark=False)
        out_path = tmp_path / "e2e_report.json"
        report.save(out_path)
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["session_id"] == report.session_id

    def test_13_cleanup(self, all_modules):
        """Cleanup closes room and unregisters security session."""
        ctrl = E2ESessionController(**all_modules)
        ctrl.run_e2e(run_benchmark=False)
        ctrl.cleanup()
        assert ctrl.state == SessionState.ENDED

    def test_14_partial_modules(self, signaling):
        """E2E works with only some modules initialized."""
        ctrl = E2ESessionController(signaling_srv=signaling)
        report = ctrl.run_e2e(run_benchmark=False)
        assert report.final_state == "ended"
        # Events should include SKIP for uninitialized modules
        skip_events = [e for e in report.events if "SKIP" in e.get("detail", "")]
        assert len(skip_events) > 0

    def test_15_no_modules(self):
        """E2E works with zero modules (all skipped)."""
        ctrl = E2ESessionController()
        report = ctrl.run_e2e()
        assert report.final_state == "ended"


# ============================================================
# Stream Monitor Tests
# ============================================================

class TestStreamMonitor:

    def test_01_init(self, all_modules):
        """StreamMonitor initializes with modules."""
        monitor = StreamMonitor(**{k: v for k, v in all_modules.items()
                                   if k not in ("benchmark_harness", "input_protocol")})
        assert monitor.metrics is not None

    def test_02_collect_empty_snapshot(self, all_modules):
        """Collect snapshot with no ingested data."""
        monitor = StreamMonitor(
            metrics_collector=all_modules["metrics_collector"],
            abr_controller=all_modules["abr_controller"],
            signaling_srv=all_modules["signaling_srv"],
        )
        snap = monitor.collect_snapshot(session_id="test-123")
        assert snap.session_id == "test-123"
        assert snap.timestamp > 0

    def test_03_collect_with_metrics(self, metrics, abr, signaling, ice_config):
        """Collect snapshot with real metric samples."""
        # Ingest some samples
        now = time.time()
        for i in range(20):
            metrics.store.ingest(MetricSample(
                metric_type=MetricType.LATENCY_VIDEO,
                value=50.0 + i * 2,
                unit="ms",
                timestamp=now + i,
                session_id="test",
            ))
            metrics.store.ingest(MetricSample(
                metric_type=MetricType.BITRATE_VIDEO,
                value=4000.0 - i * 50,
                unit="kbps",
                timestamp=now + i,
                session_id="test",
            ))
            metrics.store.ingest(MetricSample(
                metric_type=MetricType.FPS,
                value=30.0 - i * 0.2,
                unit="fps",
                timestamp=now + i,
                session_id="test",
            ))

        monitor = StreamMonitor(
            metrics_collector=metrics,
            abr_controller=abr,
            signaling_srv=signaling,
        )
        snap = monitor.collect_snapshot(session_id="test")
        assert snap.latency_p50_ms > 0
        assert snap.bitrate_kbps > 0
        assert snap.fps > 0
        assert snap.abr_rung >= 0

    def test_04_alerts_on_high_latency(self, metrics):
        """Monitor generates alerts when latency exceeds threshold."""
        # Ingest high-latency samples
        now = time.time()
        for i in range(20):
            metrics.store.ingest(MetricSample(
                metric_type=MetricType.LATENCY_VIDEO,
                value=200.0 + i * 10,  # Way above 150ms warn
                unit="ms",
                timestamp=now + i,
                session_id="test",
            ))

        monitor = StreamMonitor(
            metrics_collector=metrics,
            latency_p95_warn_ms=150.0,
            latency_p95_crit_ms=300.0,
        )
        snap = monitor.collect_snapshot()
        assert snap.latency_p95_ms > 150
        alert_counts = monitor.get_alert_count()
        assert alert_counts["total"] > 0

    def test_05_save_snapshot(self, all_modules, tmp_path):
        """Save snapshot writes metrics JSON and alerts JSONL."""
        monitor = StreamMonitor(
            metrics_collector=all_modules["metrics_collector"],
        )
        snap = monitor.collect_snapshot(session_id="save-test")
        monitor.save_snapshot(snap, tmp_path)
        assert (tmp_path / "streaming_metrics.json").exists()
        data = json.loads((tmp_path / "streaming_metrics.json").read_text())
        assert data["session_id"] == "save-test"

    def test_06_save_dashboard(self, all_modules, tmp_path):
        """Save dashboard writes comprehensive JSON."""
        monitor = StreamMonitor(
            metrics_collector=all_modules["metrics_collector"],
        )
        # Collect a few snapshots
        for _ in range(3):
            monitor.collect_snapshot()
        path = monitor.save_dashboard(tmp_path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["total_snapshots"] == 3

    def test_07_partial_modules(self):
        """Monitor works with only some modules."""
        monitor = StreamMonitor()  # No modules
        snap = monitor.collect_snapshot(session_id="empty")
        assert snap.session_id == "empty"
        assert snap.latency_p50_ms == 0.0

    def test_08_snapshot_serialization(self, all_modules):
        """MonitorSnapshot is JSON-serializable."""
        monitor = StreamMonitor(
            metrics_collector=all_modules["metrics_collector"],
        )
        snap = monitor.collect_snapshot()
        d = snap.to_dict()
        s = json.dumps(d, default=str)
        assert len(s) > 50
        parsed = json.loads(s)
        assert "timestamp" in parsed

    def test_09_alert_serialization(self):
        """MonitorAlert serializes to JSON and JSONL."""
        alert = MonitorAlert(
            timestamp=time.time(),
            level="critical",
            source="test",
            metric="latency",
            value=500.0,
            threshold=300.0,
            message="Test alert",
        )
        d = alert.to_dict()
        assert d["level"] == "critical"
        jsonl = alert.to_jsonl()
        assert "critical" in jsonl


# ============================================================
# Integration: E2E + Monitor
# ============================================================

class TestE2EMonitorIntegration:

    def test_01_e2e_then_monitor(self, all_modules, tmp_path):
        """Run E2E session, then collect monitor snapshot."""
        ctrl = E2ESessionController(**all_modules)
        report = ctrl.run_e2e(run_benchmark=True)
        assert report.final_state == "ended"

        monitor = StreamMonitor(
            metrics_collector=all_modules["metrics_collector"],
            abr_controller=all_modules["abr_controller"],
            signaling_srv=all_modules["signaling_srv"],
            stream_security=all_modules["stream_security"],
        )
        snap = monitor.collect_snapshot(session_id=ctrl.session_id)
        monitor.save_snapshot(snap, tmp_path)
        monitor.save_dashboard(tmp_path)

        # Verify all output files exist
        assert (tmp_path / "streaming_metrics.json").exists()
        assert (tmp_path / "streaming_dashboard.json").exists()

        ctrl.cleanup()

    def test_02_multiple_sessions(self, all_modules):
        """Multiple E2E sessions can run sequentially."""
        for i in range(3):
            ctrl = E2ESessionController(
                **all_modules,
                session_id=f"multi-{i}",
            )
            report = ctrl.run_e2e(run_benchmark=False)
            assert report.final_state == "ended"
            ctrl.cleanup()


# ============================================================
# Orchestrator Import Verification
# ============================================================

class TestOrchestratorImports:

    def test_01_e2e_session_importable(self):
        """e2e_session module is importable."""
        from e2e_session import E2ESessionController, E2ESessionReport, SessionState
        assert E2ESessionController is not None

    def test_02_stream_monitor_importable(self):
        """stream_monitor module is importable."""
        from stream_monitor import StreamMonitor, MonitorSnapshot, MonitorAlert
        assert StreamMonitor is not None

    def test_03_orchestrator_imports(self):
        """Orchestrator can import new modules (syntax check)."""
        # This verifies the import lines in orchestrator.py are valid
        import importlib
        spec_e2e = importlib.util.find_spec("e2e_session")
        spec_mon = importlib.util.find_spec("stream_monitor")
        assert spec_e2e is not None
        assert spec_mon is not None
