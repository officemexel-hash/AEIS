#!/usr/bin/env python3
"""
SYLION Pion D — Runtime Module Tests

Tests for: signaling_server.py, device_harness.py, metrics_ingestion.py, abr_controller.py
Target: 40+ tests covering all runtime modules.
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path

import pytest

# --- R1: Signaling Server ---
from signaling_server import (
    SignalingServer,
    SessionFlowController,
    ICECandidate,
    ICEServerConfig,
    SDPMessage,
    SDPType,
    SessionState,
    SignalingError,
)

# --- R2: Device Harness ---
from device_harness import (
    DeviceHarness,
    SafeCommandRunner,
    DeviceType,
    DeviceState,
    DeployResult,
    CaptureBackend,
    ALLOWED_ADB_COMMANDS,
    ALLOWED_SSH_COMMANDS,
    PIXEL_DEPLOY_PATH,
    ROUTER_DEPLOY_PATH,
)

# --- R3: Metrics Ingestion ---
from metrics_ingestion import (
    MetricsCollector,
    MetricsStore,
    AlertEngine,
    MetricSample,
    MetricType,
    AlertSeverity,
    AlertState,
    ThresholdConfig,
)

# --- R4: ABR Controller ---
from abr_controller import (
    ABRController,
    ABRState,
    BitrateRung,
    CongestionSignal,
    EncoderProfile,
    EncoderSettings,
    NetworkEstimate,
    DEFAULT_BITRATE_LADDER,
)


# =========================================================================
# R1: Signaling Server Tests
# =========================================================================

class TestSignalingServer:
    """Tests for signaling_server.py."""

    def setup_method(self):
        self.server = SignalingServer(max_rooms=10)

    def test_create_room(self):
        room, token = self.server.create_room("pixel-9")
        assert room.room_id
        assert token
        assert len(room.participants) == 1
        assert room.state == SessionState.WAITING
        assert room.initiator.peer_id == "pixel-9"

    def test_join_room(self):
        room, _ = self.server.create_room("pixel-9")
        peer_token = self.server.join_room(room.room_id, "laptop")
        assert peer_token
        assert len(room.participants) == 2

    def test_room_full(self):
        room, _ = self.server.create_room("pixel-9", max_participants=2)
        self.server.join_room(room.room_id, "laptop")
        with pytest.raises(SignalingError, match="full"):
            self.server.join_room(room.room_id, "third-peer")

    def test_max_rooms(self):
        for i in range(10):
            self.server.create_room(f"peer-{i}")
        with pytest.raises(SignalingError, match="Max rooms"):
            self.server.create_room("overflow")

    def test_sdp_offer_answer(self):
        room, _ = self.server.create_room("pixel-9")
        self.server.join_room(room.room_id, "laptop")

        offer = SDPMessage(
            sdp_type=SDPType.OFFER,
            sdp="v=0\no=- 0 0 IN IP4 0.0.0.0\ns=-\nm=video 9 UDP/TLS/RTP/SAVPF 96",
            dtls_fingerprint="sha-256:AB:CD:EF",
        )
        self.server.relay_sdp(room.room_id, "pixel-9", offer)
        assert room.state == SessionState.OFFER_SENT

        answer = SDPMessage(
            sdp_type=SDPType.ANSWER,
            sdp="v=0\no=- 0 0 IN IP4 0.0.0.0\ns=-\nm=video 9 UDP/TLS/RTP/SAVPF 96",
            dtls_fingerprint="sha-256:AB:CD:EF",
        )
        self.server.relay_sdp(room.room_id, "laptop", answer)
        assert room.state == SessionState.ICE_GATHERING

    def test_invalid_sdp_rejected(self):
        room, _ = self.server.create_room("pixel-9")
        bad_sdp = SDPMessage(sdp_type=SDPType.OFFER, sdp="")
        with pytest.raises(SignalingError, match="Empty SDP"):
            self.server.relay_sdp(room.room_id, "pixel-9", bad_sdp)

    def test_ice_candidate_relay(self):
        room, _ = self.server.create_room("pixel-9")
        self.server.join_room(room.room_id, "laptop")

        candidate = ICECandidate(
            candidate="candidate:1 1 UDP 2130706431 192.168.1.1 12345 typ host",
            sdp_mid="0",
            sdp_mline_index=0,
        )
        self.server.relay_ice(room.room_id, "pixel-9", candidate)

        pending = self.server.get_pending_ice(room.room_id, "laptop")
        assert len(pending) == 1
        assert pending[0].candidate == candidate.candidate

    def test_connection_lifecycle(self):
        room, _ = self.server.create_room("pixel-9")
        self.server.join_room(room.room_id, "laptop")

        self.server.on_connected(room.room_id, "pixel-9")
        self.server.on_connected(room.room_id, "laptop")
        assert room.state == SessionState.CONNECTED

        self.server.on_disconnected(room.room_id, "pixel-9")
        assert room.state == SessionState.RECONNECTING

    def test_leave_and_close(self):
        room, _ = self.server.create_room("pixel-9")
        self.server.join_room(room.room_id, "laptop")

        self.server.leave_room(room.room_id, "laptop")
        assert len(room.participants) == 1

        self.server.leave_room(room.room_id, "pixel-9")
        assert self.server.room_count == 0

    def test_heartbeat(self):
        room, _ = self.server.create_room("pixel-9")
        alive = self.server.heartbeat(room.room_id, "pixel-9")
        assert alive is True

    def test_event_log(self):
        room, _ = self.server.create_room("pixel-9")
        self.server.join_room(room.room_id, "laptop")
        events = self.server.event_log
        assert len(events) >= 2
        assert events[0].event_type == "room_created"
        assert events[1].event_type == "peer_joined"

    def test_stats(self):
        room, _ = self.server.create_room("pixel-9")
        stats = self.server.get_stats()
        assert stats["total_rooms"] == 1

    def test_export_report(self):
        room, _ = self.server.create_room("pixel-9")
        report = self.server.export_report()
        assert "stats" in report
        assert "rooms" in report
        assert room.room_id in report["rooms"]

    def test_ice_server_config(self):
        config = ICEServerConfig(
            stun_urls=["stun:stun.example.com:3478"],
            turn_urls=["turn:turn.example.com:3478"],
            turn_username="user",
            turn_credential="pass",
        )
        servers = config.to_ice_servers()
        assert len(servers) == 2
        assert "urls" in servers[0]
        assert servers[1]["username"] == "user"


class TestSessionFlowController:
    """Tests for SessionFlowController."""

    def test_establish_session(self):
        server = SignalingServer()
        flow = SessionFlowController(server=server)

        offer = SDPMessage(
            sdp_type=SDPType.OFFER,
            sdp="v=0\no=- 0 0 IN IP4 0.0.0.0\ns=-\nm=video 9 UDP/TLS/RTP/SAVPF 96",
        )
        answer = SDPMessage(
            sdp_type=SDPType.ANSWER,
            sdp="v=0\no=- 0 0 IN IP4 0.0.0.0\ns=-\nm=video 9 UDP/TLS/RTP/SAVPF 96",
        )

        session = asyncio.run(
            flow.establish_session(
                "pixel-9", "laptop",
                sdp_offer=offer,
                sdp_answer=answer,
            )
        )
        assert session["room_id"]
        assert session["initiator_token"]
        assert session["peer_token"]


# =========================================================================
# R2: Device Harness Tests
# =========================================================================

class TestSafeCommandRunner:
    """Tests for SafeCommandRunner (dry-run mode)."""

    def setup_method(self):
        self.runner = SafeCommandRunner(dry_run=True)

    def test_adb_allowed_command(self):
        result = self.runner.run_adb("devices", [])
        assert result.success
        assert "[DRY_RUN]" in result.stdout

    def test_adb_blocked_command(self):
        result = self.runner.run_adb("root", [])
        assert not result.success
        assert "BLOCKED" in result.stderr

    def test_ssh_allowed_command(self):
        result = self.runner.run_ssh("uptime", [])
        assert result.success

    def test_ssh_blocked_command(self):
        result = self.runner.run_ssh("reboot", [])
        assert not result.success
        assert "BLOCKED" in result.stderr

    def test_rm_path_enforcement_pixel(self):
        """rm must only work under PIXEL_DEPLOY_PATH."""
        result = self.runner.run_adb("shell_rm", [PIXEL_DEPLOY_PATH + "/test"])
        assert result.success

        with pytest.raises(PermissionError):
            self.runner.run_adb("shell_rm", ["/etc/passwd"])

    def test_rm_path_enforcement_router(self):
        """rm must only work under ROUTER_DEPLOY_PATH."""
        result = self.runner.run_ssh("rm", [ROUTER_DEPLOY_PATH + "/test"])
        assert result.success

        with pytest.raises(PermissionError):
            self.runner.run_ssh("rm", ["/etc/config"])

    def test_command_history(self):
        self.runner.run_adb("devices", [])
        self.runner.run_ssh("uptime", [])
        assert len(self.runner.history) == 2


class TestDeviceHarness:
    """Tests for DeviceHarness (dry-run mode)."""

    def setup_method(self):
        self.runner = SafeCommandRunner(dry_run=True)
        self.harness = DeviceHarness(
            runner=self.runner,
            battery_threshold_pct=20,
        )

    def test_health_check_pixel(self):
        status = self.harness.health_check_pixel()
        assert status.device_type == DeviceType.PIXEL
        # Dry-run: devices check succeeds
        assert status.state in (DeviceState.ONLINE, DeviceState.UNKNOWN)

    def test_health_check_router(self):
        status = self.harness.health_check_router()
        assert status.device_type == DeviceType.ROUTER

    def test_health_check_all(self):
        result = self.harness.health_check_all()
        assert "pixel" in result
        assert "router" in result

    def test_deploy_pixel_no_binary(self):
        """Deploy should fail gracefully if binary doesn't exist."""
        report = self.harness.deploy_to_pixel()
        assert report.result == DeployResult.FAILED
        assert "not found" in report.error_message.lower()

    def test_deploy_pixel_with_binary(self):
        """Deploy with temp binary (dry-run)."""
        with tempfile.NamedTemporaryFile(suffix="-arm64", delete=False) as f:
            f.write(b"fake binary")
            binary = Path(f.name)

        self.harness.pixel_binary = binary
        report = self.harness.deploy_to_pixel()
        assert report.result == DeployResult.SUCCESS
        assert len(report.steps) > 0
        binary.unlink()

    def test_deploy_router_no_binary(self):
        report = self.harness.deploy_to_router()
        assert report.result == DeployResult.FAILED

    def test_stats(self):
        stats = self.harness.get_stats()
        assert "devices" in stats
        assert "deploys" in stats

    def test_export_report(self):
        report = self.harness.export_report()
        assert "stats" in report
        assert "deploy_reports" in report

    def test_allowlist_completeness(self):
        """Verify allowlists contain expected commands."""
        assert "push" in ALLOWED_ADB_COMMANDS
        assert "shell_battery" in ALLOWED_ADB_COMMANDS
        assert "scp" in ALLOWED_SSH_COMMANDS
        assert "health" in ALLOWED_SSH_COMMANDS


# =========================================================================
# R3: Metrics Ingestion Tests
# =========================================================================

class TestMetricsStore:
    """Tests for MetricsStore."""

    def test_ingest_and_retrieve(self):
        store = MetricsStore()
        sample = MetricSample(
            metric_type=MetricType.LATENCY_VIDEO,
            value=85.0, unit="ms", session_id="s1",
        )
        store.ingest(sample)
        assert store.total_ingested == 1

        latest = store.get_latest(MetricType.LATENCY_VIDEO)
        assert len(latest) == 1
        assert latest[0].value == 85.0

    def test_percentiles(self):
        store = MetricsStore()
        for v in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            store.ingest(MetricSample(
                metric_type=MetricType.LATENCY_VIDEO,
                value=float(v), unit="ms",
            ))
        stats = store.get_percentiles(MetricType.LATENCY_VIDEO, window_s=60)
        assert stats.count == 10
        assert stats.p50 == pytest.approx(55.0, abs=5)
        assert stats.p95 >= 90
        assert stats.min_val == 10.0
        assert stats.max_val == 100.0

    def test_ring_buffer(self):
        store = MetricsStore(max_samples_per_metric=5)
        for i in range(10):
            store.ingest(MetricSample(
                metric_type=MetricType.FPS, value=float(i), unit="fps",
            ))
        latest = store.get_latest(MetricType.FPS, count=10)
        assert len(latest) == 5  # Ring buffer capped at 5

    def test_batch_ingest(self):
        store = MetricsStore()
        samples = [
            MetricSample(metric_type=MetricType.BITRATE_VIDEO, value=3000 + i, unit="kbps")
            for i in range(10)
        ]
        count = store.ingest_batch(samples)
        assert count == 10
        assert store.total_ingested == 10


class TestAlertEngine:
    """Tests for AlertEngine."""

    def setup_method(self):
        self.engine = AlertEngine(
            thresholds=[
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
            ],
        )

    def test_no_alert_within_bounds(self):
        sample = MetricSample(
            metric_type=MetricType.LATENCY_VIDEO,
            value=80.0, unit="ms",
        )
        alert = self.engine.evaluate(sample)
        assert alert is None

    def test_warning_alert(self):
        sample = MetricSample(
            metric_type=MetricType.LATENCY_VIDEO,
            value=200.0, unit="ms",
        )
        alert = self.engine.evaluate(sample)
        assert alert is not None
        assert alert.severity == AlertSeverity.WARNING

    def test_critical_alert(self):
        sample = MetricSample(
            metric_type=MetricType.LATENCY_VIDEO,
            value=350.0, unit="ms",
        )
        alert = self.engine.evaluate(sample)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_lower_direction_alert(self):
        """Bitrate drops below threshold."""
        sample = MetricSample(
            metric_type=MetricType.BITRATE_VIDEO,
            value=400.0, unit="kbps",
        )
        alert = self.engine.evaluate(sample)
        assert alert is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_alert_dedup(self):
        """Same alert should not fire twice within dedup window."""
        sample = MetricSample(
            metric_type=MetricType.LATENCY_VIDEO,
            value=350.0, unit="ms",
        )
        a1 = self.engine.evaluate(sample)
        a2 = self.engine.evaluate(sample)
        assert a1 is not None
        assert a2 is None  # Deduped

    def test_alert_resolve(self):
        """Alert should resolve when metric returns to normal."""
        # Trigger
        self.engine.evaluate(MetricSample(
            metric_type=MetricType.LATENCY_VIDEO, value=350.0, unit="ms",
        ))
        assert len(self.engine.get_active_alerts()) == 1

        # Resolve
        self.engine.evaluate(MetricSample(
            metric_type=MetricType.LATENCY_VIDEO, value=50.0, unit="ms",
        ))
        assert len(self.engine.get_active_alerts()) == 0


class TestMetricsCollector:
    """Tests for MetricsCollector facade."""

    def test_record_latency(self):
        collector = MetricsCollector()
        alert = collector.record_latency("session-1", 85.0)
        assert alert is None  # No thresholds configured by default

    def test_record_and_report(self):
        collector = MetricsCollector()
        for i in range(10):
            collector.record_latency("s1", 80.0 + i)
            collector.record_bitrate("s1", 3000.0 + i * 100)

        report = collector.get_session_report("s1")
        assert "metrics" in report
        assert "latency_video" in report["metrics"]

    def test_dashboard(self):
        collector = MetricsCollector()
        collector.record_fps("s1", 30.0)
        dashboard = collector.get_dashboard()
        assert "store_stats" in dashboard
        assert "alert_stats" in dashboard

    def test_export_metrics_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = MetricsCollector(log_dir=Path(tmpdir))
            collector.record_latency("s1", 85.0)
            data = collector.export_metrics_json()
            assert "dashboard" in data
            assert "thresholds" in data

            # Check file was written
            assert (Path(tmpdir) / "streaming_metrics.json").exists()


# =========================================================================
# R4: ABR Controller Tests
# =========================================================================

class TestABRController:
    """Tests for ABRController."""

    def setup_method(self):
        self.abr = ABRController(initial_rung=1)

    def test_initial_settings(self):
        settings = self.abr.get_current_settings()
        assert settings.rung_index == 1
        assert settings.resolution == "854x480"
        assert settings.h264_profile == EncoderProfile.MAIN

    def test_ramp_up_on_surplus(self):
        """High bandwidth should ramp up."""
        estimate = NetworkEstimate(available_kbps=10000)
        settings = self.abr.on_network_estimate(estimate)
        assert settings.rung_index == 2  # Ramped up from 1 to 2

    def test_ramp_down_on_low_bandwidth(self):
        """Low bandwidth should ramp down."""
        estimate = NetworkEstimate(available_kbps=200)
        settings = self.abr.on_network_estimate(estimate)
        assert settings.rung_index == 0  # Ramped down from 1 to 0

    def test_stable_within_bounds(self):
        """Bandwidth within rung bounds should keep same rung."""
        estimate = NetworkEstimate(available_kbps=1000)
        settings = self.abr.on_network_estimate(estimate)
        assert settings.rung_index == 1  # Same rung

    def test_congestion_pli_drops_rung(self):
        """PLI should immediately drop one rung."""
        self.abr._current_rung = 2
        settings = self.abr.on_congestion(CongestionSignal.PLI)
        assert settings.rung_index == 1

    def test_congestion_nack_reduces_bitrate(self):
        """NACK should reduce bitrate within rung."""
        old_bitrate = self.abr._target_bitrate_kbps
        self.abr.on_congestion(CongestionSignal.NACK)
        assert self.abr._target_bitrate_kbps < old_bitrate

    def test_battery_throttle(self):
        """Low battery should throttle to low rung."""
        self.abr._current_rung = 3
        settings = self.abr.on_battery_low(15)
        assert settings.rung_index <= 1
        assert self.abr.state == ABRState.THROTTLED

    def test_thermal_throttle(self):
        """Thermal event should throttle."""
        self.abr._current_rung = 3
        settings = self.abr.on_thermal_throttle(85.0)
        assert settings.rung_index <= 1
        assert self.abr.state == ABRState.THROTTLED

    def test_clear_throttle(self):
        self.abr.on_battery_low(15)
        assert self.abr.state == ABRState.THROTTLED
        self.abr.clear_throttle()
        assert self.abr.state == ABRState.STABLE

    def test_no_ramp_up_during_throttle(self):
        """Cannot ramp up while throttled."""
        self.abr._current_rung = 0
        self.abr.on_battery_low(10)  # Throttle
        estimate = NetworkEstimate(available_kbps=50000)
        settings = self.abr.on_network_estimate(estimate)
        # Should stay at throttled rung, not ramp up
        assert settings.rung_index <= 1

    def test_default_ladder(self):
        assert len(DEFAULT_BITRATE_LADDER) == 4
        assert DEFAULT_BITRATE_LADDER[0].resolution == "640x360"
        assert DEFAULT_BITRATE_LADDER[3].resolution == "1920x1080"

    def test_stats(self):
        stats = self.abr.get_stats()
        assert "current_rung" in stats
        assert "state" in stats
        assert "ladder_size" in stats

    def test_export_report(self):
        report = self.abr.export_report()
        assert "stats" in report
        assert "current_settings" in report
        assert "ladder" in report

    def test_encoder_settings_serialization(self):
        settings = self.abr.get_current_settings()
        d = settings.to_dict()
        assert "bitrate_kbps" in d
        assert "resolution" in d
        assert "h264_profile" in d


# =========================================================================
# Cross-module integration
# =========================================================================

class TestRuntimeIntegration:
    """Cross-module integration tests."""

    def test_metrics_to_abr(self):
        """Metrics collector feeds ABR controller."""
        collector = MetricsCollector()
        abr = ABRController(initial_rung=2)

        # Simulate high latency → ABR should react
        for _ in range(5):
            collector.record_latency("s1", 300.0)

        # Get bandwidth estimate from metrics
        stats = collector.store.get_percentiles(MetricType.LATENCY_VIDEO)
        assert stats.p50 > 200

        # ABR reacts to congestion
        settings = abr.on_congestion(CongestionSignal.RTT_SPIKE)
        assert settings.bitrate_kbps < 4000

    def test_signaling_to_metrics(self):
        """Signaling events can be translated to metrics."""
        server = SignalingServer()
        collector = MetricsCollector()

        events = []
        server.on_event = lambda e: events.append(e)

        room, _ = server.create_room("pixel-9")
        server.join_room(room.room_id, "laptop")

        assert len(events) >= 2

        # Simulate recording connection time as metric
        connect_time_ms = 150.0
        alert = collector.record_latency(room.room_id, connect_time_ms)
        assert collector.store.total_ingested == 1
