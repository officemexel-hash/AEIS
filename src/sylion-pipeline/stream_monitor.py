#!/usr/bin/env python3
"""
SYLION Stream Monitor — real-time monitoring of Pion D streaming sessions.

Consumes real metrics from MetricsCollector, ABRController, SignalingServer,
and StreamSecurityVerifier.  Produces dashboard-ready JSON and alert JSONL.

Unlike Stage 5.5 health-checks which only verify modules are alive,
this monitor reads actual streaming metrics: bitrate, latency percentiles,
frame drops, A/V sync drift, ABR tier changes, security violations.

LLM NIGDY nie wydaje raw shell.  Only pre-approved scenarios.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.stream_monitor")


class MonitorAlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class MonitorAlert:
    """Single monitoring alert."""
    timestamp: float
    level: str
    source: str
    metric: str
    value: float
    threshold: float
    message: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class MonitorSnapshot:
    """Point-in-time snapshot of all streaming metrics."""
    timestamp: float = 0.0
    session_id: str = ""

    # Latency
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0

    # Throughput
    bitrate_kbps: float = 0.0
    fps: float = 0.0
    resolution: str = ""

    # Quality
    frame_drop_pct: float = 0.0
    av_sync_drift_ms: float = 0.0

    # ABR
    abr_rung: int = -1
    abr_state: str = ""
    abr_transitions: int = 0

    # Network
    packet_loss_pct: float = 0.0
    rtt_ms: float = 0.0
    jitter_ms: float = 0.0

    # Security
    security_level: str = ""
    security_violations: int = 0
    rate_limit_breaches: int = 0

    # Signaling
    active_rooms: int = 0
    connected_peers: int = 0

    # Device
    battery_pct: int = -1
    thermal_state: str = ""

    # Alerts generated in this snapshot
    alerts: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class StreamMonitor:
    """
    Real-time stream monitor that reads actual metrics from runtime modules.

    Typical usage:
        monitor = StreamMonitor(
            metrics_collector=metrics_collector,
            abr_controller=abr_controller,
            signaling_srv=signaling_srv,
            stream_security=stream_security,
            device_harness=device_harness,
            audio_pipeline=audio_pipeline,
        )
        snapshot = monitor.collect_snapshot(session_id="e2e-abc123")
        monitor.save_snapshot(snapshot, output_dir)
    """

    def __init__(
        self,
        *,
        metrics_collector=None,   # MetricsCollector
        abr_controller=None,      # ABRController
        signaling_srv=None,       # SignalingServer
        stream_security=None,     # StreamSecurityVerifier
        device_harness=None,      # DeviceHarness
        audio_pipeline=None,      # AudioPipelineController
        # Alert thresholds
        latency_p95_warn_ms: float = 150.0,
        latency_p95_crit_ms: float = 300.0,
        frame_drop_warn_pct: float = 2.0,
        frame_drop_crit_pct: float = 5.0,
        bitrate_drop_warn_pct: float = 50.0,
        av_sync_warn_ms: float = 40.0,
        av_sync_crit_ms: float = 80.0,
    ):
        self.metrics = metrics_collector
        self.abr = abr_controller
        self.signaling = signaling_srv
        self.security = stream_security
        self.device = device_harness
        self.audio = audio_pipeline

        # Thresholds
        self._thresholds = {
            "latency_p95_warn_ms": latency_p95_warn_ms,
            "latency_p95_crit_ms": latency_p95_crit_ms,
            "frame_drop_warn_pct": frame_drop_warn_pct,
            "frame_drop_crit_pct": frame_drop_crit_pct,
            "bitrate_drop_warn_pct": bitrate_drop_warn_pct,
            "av_sync_warn_ms": av_sync_warn_ms,
            "av_sync_crit_ms": av_sync_crit_ms,
        }

        # History
        self._snapshots: list[MonitorSnapshot] = []
        self._alerts: list[MonitorAlert] = []
        self._baseline_bitrate: float | None = None

    def collect_snapshot(self, session_id: str = "") -> MonitorSnapshot:
        """
        Collect a real-time snapshot from all runtime modules.

        This reads ACTUAL metrics, not just health status.
        """
        snap = MonitorSnapshot(
            timestamp=time.time(),
            session_id=session_id,
        )
        alerts: list[MonitorAlert] = []

        # --- Metrics Ingestion: latency, bitrate, fps, frame drops ---
        if self.metrics:
            try:
                from metrics_ingestion import MetricType

                # Latency percentiles
                latency_stats = self.metrics.store.get_percentiles(
                    MetricType.LATENCY_VIDEO, window_s=300.0,
                )
                snap.latency_p50_ms = latency_stats.p50
                snap.latency_p95_ms = latency_stats.p95
                snap.latency_p99_ms = latency_stats.p99

                # Check latency thresholds
                if snap.latency_p95_ms > self._thresholds["latency_p95_crit_ms"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.CRITICAL.value,
                        source="metrics",
                        metric="latency_p95_ms",
                        value=snap.latency_p95_ms,
                        threshold=self._thresholds["latency_p95_crit_ms"],
                        message=f"Latency P95 CRITICAL: {snap.latency_p95_ms:.1f}ms > {self._thresholds['latency_p95_crit_ms']}ms",
                    ))
                elif snap.latency_p95_ms > self._thresholds["latency_p95_warn_ms"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.WARNING.value,
                        source="metrics",
                        metric="latency_p95_ms",
                        value=snap.latency_p95_ms,
                        threshold=self._thresholds["latency_p95_warn_ms"],
                        message=f"Latency P95 WARNING: {snap.latency_p95_ms:.1f}ms > {self._thresholds['latency_p95_warn_ms']}ms",
                    ))

                # Bitrate
                bitrate_stats = self.metrics.store.get_percentiles(
                    MetricType.BITRATE_VIDEO, window_s=300.0,
                )
                snap.bitrate_kbps = bitrate_stats.p50

                if self._baseline_bitrate is None and snap.bitrate_kbps > 0:
                    self._baseline_bitrate = snap.bitrate_kbps
                elif self._baseline_bitrate and snap.bitrate_kbps > 0:
                    drop_pct = ((self._baseline_bitrate - snap.bitrate_kbps) / self._baseline_bitrate) * 100
                    if drop_pct > self._thresholds["bitrate_drop_warn_pct"]:
                        alerts.append(MonitorAlert(
                            timestamp=snap.timestamp,
                            level=MonitorAlertLevel.WARNING.value,
                            source="metrics",
                            metric="bitrate_drop_pct",
                            value=drop_pct,
                            threshold=self._thresholds["bitrate_drop_warn_pct"],
                            message=f"Bitrate dropped {drop_pct:.1f}% from baseline {self._baseline_bitrate:.0f}kbps",
                        ))

                # FPS
                fps_stats = self.metrics.store.get_percentiles(
                    MetricType.FPS, window_s=300.0,
                )
                snap.fps = fps_stats.p50

                # Frame drops
                frame_drop_stats = self.metrics.store.get_percentiles(
                    MetricType.FRAME_DROP, window_s=300.0,
                )
                snap.frame_drop_pct = frame_drop_stats.p50

                if snap.frame_drop_pct > self._thresholds["frame_drop_crit_pct"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.CRITICAL.value,
                        source="metrics",
                        metric="frame_drop_pct",
                        value=snap.frame_drop_pct,
                        threshold=self._thresholds["frame_drop_crit_pct"],
                        message=f"Frame drop CRITICAL: {snap.frame_drop_pct:.2f}% > {self._thresholds['frame_drop_crit_pct']}%",
                    ))
                elif snap.frame_drop_pct > self._thresholds["frame_drop_warn_pct"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.WARNING.value,
                        source="metrics",
                        metric="frame_drop_pct",
                        value=snap.frame_drop_pct,
                        threshold=self._thresholds["frame_drop_warn_pct"],
                        message=f"Frame drop WARNING: {snap.frame_drop_pct:.2f}% > {self._thresholds['frame_drop_warn_pct']}%",
                    ))

                # Packet loss, RTT (via latency_input), jitter
                loss_stats = self.metrics.store.get_percentiles(
                    MetricType.PACKET_LOSS, window_s=300.0,
                )
                snap.packet_loss_pct = loss_stats.p50

                rtt_stats = self.metrics.store.get_percentiles(
                    MetricType.LATENCY_INPUT, window_s=300.0,
                )
                snap.rtt_ms = rtt_stats.p50

                jitter_stats = self.metrics.store.get_percentiles(
                    MetricType.JITTER, window_s=300.0,
                )
                snap.jitter_ms = jitter_stats.p50

            except Exception as e:
                log.warning("  Metrics collection partial failure: %s", e)

        # --- ABR Controller ---
        if self.abr:
            try:
                abr_stats = self.abr.get_stats()
                settings = self.abr.get_current_settings()
                snap.abr_rung = abr_stats.get("current_rung", -1)
                snap.abr_state = abr_stats.get("state", "")
                snap.abr_transitions = abr_stats.get("total_transitions", 0)
                snap.resolution = settings.resolution
            except Exception as e:
                log.warning("  ABR stats failed: %s", e)

        # --- Signaling ---
        if self.signaling:
            try:
                snap.active_rooms = self.signaling.room_count()
                rooms = self.signaling.list_rooms()
                snap.connected_peers = sum(
                    len(r.get("participants", []))
                    for r in rooms
                )
            except Exception as e:
                log.warning("  Signaling stats failed: %s", e)

        # --- Stream Security ---
        if self.security:
            try:
                sec_stats = self.security.get_stats()
                snap.security_level = sec_stats.get("overall_level", "")
                snap.security_violations = sec_stats.get("total_violations", 0)
                snap.rate_limit_breaches = sec_stats.get("rate_limit_breaches", 0)

                if snap.security_violations > 0:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.WARNING.value,
                        source="security",
                        metric="security_violations",
                        value=float(snap.security_violations),
                        threshold=0.0,
                        message=f"Security violations detected: {snap.security_violations}",
                    ))
            except Exception as e:
                log.warning("  Security stats failed: %s", e)

        # --- Audio Pipeline ---
        if self.audio:
            try:
                audio_stats = self.audio.get_stats()
                # A/V sync drift from audio pipeline
                drift = audio_stats.get("av_sync_drift_ms", 0.0)
                if isinstance(drift, (int, float)):
                    snap.av_sync_drift_ms = abs(drift)

                if snap.av_sync_drift_ms > self._thresholds["av_sync_crit_ms"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.CRITICAL.value,
                        source="audio",
                        metric="av_sync_drift_ms",
                        value=snap.av_sync_drift_ms,
                        threshold=self._thresholds["av_sync_crit_ms"],
                        message=f"A/V sync drift CRITICAL: {snap.av_sync_drift_ms:.1f}ms > {self._thresholds['av_sync_crit_ms']}ms",
                    ))
                elif snap.av_sync_drift_ms > self._thresholds["av_sync_warn_ms"]:
                    alerts.append(MonitorAlert(
                        timestamp=snap.timestamp,
                        level=MonitorAlertLevel.WARNING.value,
                        source="audio",
                        metric="av_sync_drift_ms",
                        value=snap.av_sync_drift_ms,
                        threshold=self._thresholds["av_sync_warn_ms"],
                        message=f"A/V sync drift WARNING: {snap.av_sync_drift_ms:.1f}ms > {self._thresholds['av_sync_warn_ms']}ms",
                    ))
            except Exception as e:
                log.warning("  Audio stats failed: %s", e)

        # --- Device Harness ---
        if self.device:
            try:
                health = self.device.health_check_all()
                for name, status in health.items():
                    if hasattr(status, "battery_pct"):
                        snap.battery_pct = status.battery_pct
                    if hasattr(status, "thermal_state"):
                        snap.thermal_state = str(status.thermal_state)
            except Exception as e:
                log.warning("  Device stats failed: %s", e)

        # Store alerts in snapshot
        snap.alerts = [a.to_dict() for a in alerts]
        self._alerts.extend(alerts)
        self._snapshots.append(snap)

        return snap

    def save_snapshot(self, snap: MonitorSnapshot, output_dir: Path) -> None:
        """Save snapshot as JSON and append alerts to JSONL."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save latest metrics
        metrics_path = output_dir / "streaming_metrics.json"
        metrics_path.write_text(json.dumps(snap.to_dict(), indent=2, default=str))

        # Append alerts to JSONL
        if snap.alerts:
            alerts_path = output_dir / "streaming_alerts.jsonl"
            with alerts_path.open("a") as f:
                for alert_dict in snap.alerts:
                    f.write(json.dumps(alert_dict, default=str) + "\n")

    def save_dashboard(self, output_dir: Path) -> Path:
        """Save full dashboard with history of all snapshots."""
        output_dir.mkdir(parents=True, exist_ok=True)
        dashboard_path = output_dir / "streaming_dashboard.json"

        dashboard = {
            "generated_at": time.time(),
            "total_snapshots": len(self._snapshots),
            "total_alerts": len(self._alerts),
            "thresholds": self._thresholds,
            "snapshots": [s.to_dict() for s in self._snapshots[-100:]],  # Last 100
            "alert_summary": {
                "critical": sum(1 for a in self._alerts if a.level == "critical"),
                "warning": sum(1 for a in self._alerts if a.level == "warning"),
                "info": sum(1 for a in self._alerts if a.level == "info"),
            },
        }

        dashboard_path.write_text(json.dumps(dashboard, indent=2, default=str))
        return dashboard_path

    def get_latest(self) -> MonitorSnapshot | None:
        """Get latest snapshot."""
        return self._snapshots[-1] if self._snapshots else None

    def get_alert_count(self) -> dict[str, int]:
        """Get alert counts by level."""
        return {
            "critical": sum(1 for a in self._alerts if a.level == "critical"),
            "warning": sum(1 for a in self._alerts if a.level == "warning"),
            "info": sum(1 for a in self._alerts if a.level == "info"),
            "total": len(self._alerts),
        }
