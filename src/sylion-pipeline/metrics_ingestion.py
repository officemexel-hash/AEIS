"""
SYLION Pion D — Metrics Ingestion Pipeline

Collects runtime telemetry from WebRTC sessions and devices, feeds it
to stream_monitor agent for anomaly detection and alerting.

Metrics collected:
  - Latency (P50/P95/P99, input latency, A/V sync drift)
  - Bitrate (video/audio, per-direction)
  - Packet loss (RTP, RTCP)
  - Jitter (inter-arrival, buffer)
  - Frame stats (drop rate, FPS, resolution changes)
  - ICE stats (candidate type, TURN usage, reconnections)
  - Device stats (battery, thermal, CPU)

Architecture:
  WebRTC Stats API → MetricsCollector → MetricsStore → stream_monitor
                                      → AlertEngine → Human Gate

All thresholds read from config.streaming_latency_budget.

⚠️  LLM NEVER issues raw shell commands.
"""

from __future__ import annotations

import enum
import json
import logging
import math
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("metrics_ingestion")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MetricType(enum.Enum):
    """Types of streaming metrics."""
    LATENCY_VIDEO = "latency_video"
    LATENCY_INPUT = "latency_input"
    LATENCY_AUDIO = "latency_audio"
    AV_SYNC_DRIFT = "av_sync_drift"
    BITRATE_VIDEO = "bitrate_video"
    BITRATE_AUDIO = "bitrate_audio"
    PACKET_LOSS = "packet_loss"
    JITTER = "jitter"
    FRAME_DROP = "frame_drop"
    FPS = "fps"
    RESOLUTION = "resolution"
    ICE_STATE = "ice_state"
    TURN_USAGE = "turn_usage"
    RECONNECTION = "reconnection"
    BATTERY = "battery"
    THERMAL = "thermal"
    CPU_USAGE = "cpu_usage"


class AlertSeverity(enum.Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"


class AlertState(enum.Enum):
    """Alert lifecycle state."""
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MetricSample:
    """A single metric measurement."""
    metric_type: MetricType
    value: float
    unit: str              # "ms", "kbps", "pct", "fps", "celsius", etc.
    session_id: str = ""
    device: str = ""       # "pixel", "router", "laptop"
    timestamp: float = field(default_factory=time.time)
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric_type.value,
            "value": self.value,
            "unit": self.unit,
            "session_id": self.session_id,
            "device": self.device,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


@dataclass
class PercentileStats:
    """Computed percentile statistics for a metric."""
    count: int = 0
    min_val: float = 0.0
    max_val: float = 0.0
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    stddev: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "min": self.min_val,
            "max": self.max_val,
            "mean": round(self.mean, 2),
            "p50": round(self.p50, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "stddev": round(self.stddev, 2),
        }


@dataclass
class Alert:
    """A threshold violation alert."""
    alert_id: str
    severity: AlertSeverity
    metric_type: MetricType
    threshold: float
    actual_value: float
    message: str
    session_id: str = ""
    device: str = ""
    state: AlertState = AlertState.ACTIVE
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity.value,
            "metric": self.metric_type.value,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "message": self.message,
            "session_id": self.session_id,
            "device": self.device,
            "state": self.state.value,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }


@dataclass
class ThresholdConfig:
    """Threshold configuration for a single metric — read from config.py."""
    metric_type: MetricType
    warning_threshold: float
    critical_threshold: float
    unit: str
    direction: str = "upper"   # "upper" = alert when value > threshold
                               # "lower" = alert when value < threshold

    def check(self, value: float) -> AlertSeverity | None:
        """Check if value violates threshold.  Returns severity or None."""
        if self.direction == "upper":
            if value >= self.critical_threshold:
                return AlertSeverity.CRITICAL
            if value >= self.warning_threshold:
                return AlertSeverity.WARNING
        else:  # lower
            if value <= self.critical_threshold:
                return AlertSeverity.CRITICAL
            if value <= self.warning_threshold:
                return AlertSeverity.WARNING
        return None


# ---------------------------------------------------------------------------
# Metrics Store (in-memory ring buffer)
# ---------------------------------------------------------------------------

class MetricsStore:
    """
    In-memory ring buffer for metric samples.

    Stores last N samples per metric type with O(1) insert.
    Computes percentiles on demand.
    """

    def __init__(self, *, max_samples_per_metric: int = 10000):
        self.max_samples = max_samples_per_metric
        self._buffers: dict[MetricType, deque[MetricSample]] = {}
        self._total_ingested: int = 0

    def ingest(self, sample: MetricSample) -> None:
        """Ingest a single metric sample."""
        if sample.metric_type not in self._buffers:
            self._buffers[sample.metric_type] = deque(maxlen=self.max_samples)
        self._buffers[sample.metric_type].append(sample)
        self._total_ingested += 1

    def ingest_batch(self, samples: list[MetricSample]) -> int:
        """Ingest multiple samples.  Returns count ingested."""
        for s in samples:
            self.ingest(s)
        return len(samples)

    def get_percentiles(
        self,
        metric_type: MetricType,
        *,
        window_s: float = 60.0,
        session_id: str = "",
    ) -> PercentileStats:
        """Compute percentile statistics for a metric within a time window."""
        buf = self._buffers.get(metric_type)
        if not buf:
            return PercentileStats()

        cutoff = time.time() - window_s
        values = [
            s.value for s in buf
            if s.timestamp >= cutoff
            and (not session_id or s.session_id == session_id)
        ]

        if not values:
            return PercentileStats()

        values_sorted = sorted(values)
        n = len(values_sorted)

        return PercentileStats(
            count=n,
            min_val=values_sorted[0],
            max_val=values_sorted[-1],
            mean=statistics.mean(values),
            p50=self._percentile(values_sorted, 50),
            p95=self._percentile(values_sorted, 95),
            p99=self._percentile(values_sorted, 99),
            stddev=statistics.stdev(values) if n > 1 else 0.0,
        )

    def get_latest(
        self, metric_type: MetricType, count: int = 1,
    ) -> list[MetricSample]:
        """Get the N most recent samples for a metric."""
        buf = self._buffers.get(metric_type)
        if not buf:
            return []
        return list(buf)[-count:]

    def get_rate(
        self,
        metric_type: MetricType,
        *,
        window_s: float = 60.0,
    ) -> float:
        """Get sample ingestion rate (samples/sec) for a metric."""
        buf = self._buffers.get(metric_type)
        if not buf:
            return 0.0
        cutoff = time.time() - window_s
        count = sum(1 for s in buf if s.timestamp >= cutoff)
        return count / window_s if window_s > 0 else 0.0

    @property
    def total_ingested(self) -> int:
        return self._total_ingested

    @property
    def metric_types(self) -> list[MetricType]:
        return list(self._buffers.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get store statistics."""
        return {
            "total_ingested": self._total_ingested,
            "metric_types": len(self._buffers),
            "buffer_sizes": {
                mt.value: len(buf) for mt, buf in self._buffers.items()
            },
        }

    @staticmethod
    def _percentile(sorted_values: list[float], pct: float) -> float:
        """Compute percentile from pre-sorted values."""
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[int(f)] * (c - k) + sorted_values[int(c)] * (k - f)


# ---------------------------------------------------------------------------
# Alert Engine
# ---------------------------------------------------------------------------

class AlertEngine:
    """
    Evaluates metrics against thresholds and generates alerts.

    Thresholds are derived from config.streaming_latency_budget.
    Supports dedup (no repeated alerts for the same ongoing violation)
    and auto-resolve when metric returns to normal.
    """

    def __init__(
        self,
        *,
        thresholds: list[ThresholdConfig] | None = None,
        dedup_window_s: float = 60.0,
        on_alert: Callable[[Alert], None] | None = None,
        log_dir: Path | None = None,
    ):
        self.thresholds = {t.metric_type: t for t in (thresholds or [])}
        self.dedup_window_s = dedup_window_s
        self.on_alert = on_alert
        self.log_dir = log_dir

        self._active_alerts: dict[str, Alert] = {}  # key → alert
        self._alert_history: list[Alert] = []
        self._alert_counter: int = 0

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def evaluate(self, sample: MetricSample) -> Alert | None:
        """Evaluate a sample against thresholds.  Returns Alert if triggered."""
        threshold = self.thresholds.get(sample.metric_type)
        if not threshold:
            return None

        severity = threshold.check(sample.value)

        # Key for dedup: metric_type + session + device
        alert_key = f"{sample.metric_type.value}:{sample.session_id}:{sample.device}"

        if severity is None:
            # Value within bounds — resolve any active alert
            existing = self._active_alerts.pop(alert_key, None)
            if existing:
                existing.state = AlertState.RESOLVED
                existing.resolved_at = time.time()
                self._alert_history.append(existing)
                log.info(f"Alert RESOLVED: {existing.message}")
            return None

        # Check dedup: don't re-alert within window
        existing = self._active_alerts.get(alert_key)
        if existing and (time.time() - existing.created_at) < self.dedup_window_s:
            return None  # Already alerted recently

        # Create new alert
        self._alert_counter += 1
        alert = Alert(
            alert_id=f"STREAM-ALERT-{self._alert_counter:04d}",
            severity=severity,
            metric_type=sample.metric_type,
            threshold=(
                threshold.critical_threshold if severity == AlertSeverity.CRITICAL
                else threshold.warning_threshold
            ),
            actual_value=sample.value,
            message=(
                f"{sample.metric_type.value} {severity.value}: "
                f"{sample.value}{sample.unit} exceeds "
                f"{'critical' if severity == AlertSeverity.CRITICAL else 'warning'} "
                f"threshold ({threshold.critical_threshold if severity == AlertSeverity.CRITICAL else threshold.warning_threshold}{sample.unit})"
            ),
            session_id=sample.session_id,
            device=sample.device,
        )

        self._active_alerts[alert_key] = alert
        self._alert_history.append(alert)

        # Log alert
        self._log_alert(alert)

        # Callback
        if self.on_alert:
            try:
                self.on_alert(alert)
            except Exception as e:
                log.error(f"Alert callback error: {e}")

        return alert

    def evaluate_batch(self, samples: list[MetricSample]) -> list[Alert]:
        """Evaluate batch of samples.  Returns list of triggered alerts."""
        alerts = []
        for s in samples:
            alert = self.evaluate(s)
            if alert:
                alerts.append(alert)
        return alerts

    def get_active_alerts(self) -> list[Alert]:
        """Get all currently active (unresolved) alerts."""
        return [a for a in self._active_alerts.values() if a.state == AlertState.ACTIVE]

    def acknowledge(self, alert_id: str) -> bool:
        """Acknowledge an active alert.  Returns True if found."""
        for alert in self._active_alerts.values():
            if alert.alert_id == alert_id:
                alert.state = AlertState.ACKNOWLEDGED
                return True
        return False

    @property
    def alert_count(self) -> int:
        return len(self._alert_history)

    def get_stats(self) -> dict[str, Any]:
        """Get alert engine statistics."""
        active = [a for a in self._active_alerts.values() if a.state == AlertState.ACTIVE]
        return {
            "total_alerts": len(self._alert_history),
            "active_alerts": len(active),
            "critical_active": sum(1 for a in active if a.severity == AlertSeverity.CRITICAL),
            "warning_active": sum(1 for a in active if a.severity == AlertSeverity.WARNING),
            "thresholds_configured": len(self.thresholds),
        }

    def _log_alert(self, alert: Alert) -> None:
        """Write alert to JSONL log."""
        if self.log_dir:
            log_file = self.log_dir / "streaming_alerts.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(alert.to_dict(), ensure_ascii=False) + "\n")

        if alert.severity == AlertSeverity.CRITICAL:
            log.critical(f"ALERT: {alert.message}")
        elif alert.severity == AlertSeverity.WARNING:
            log.warning(f"ALERT: {alert.message}")
        else:
            log.info(f"ALERT: {alert.message}")


# ---------------------------------------------------------------------------
# Metrics Collector (facade for stream_monitor)
# ---------------------------------------------------------------------------

class MetricsCollector:
    """
    Main facade: collects metrics, stores them, evaluates alerts.

    This is what the stream_monitor agent and orchestrator interact with.
    Feeds data from WebRTC stats API (via signaling server events) and
    device harness health checks.

    Usage:
        collector = MetricsCollector.from_config(cfg)
        collector.record_latency(session_id="room-abc", value=85.0)
        collector.record_bitrate(session_id="room-abc", value=4500.0)
        stats = collector.get_session_report("room-abc")
    """

    def __init__(
        self,
        *,
        store: MetricsStore | None = None,
        alert_engine: AlertEngine | None = None,
        log_dir: Path | None = None,
    ):
        self.store = store or MetricsStore()
        self.alert_engine = alert_engine or AlertEngine()
        self.log_dir = log_dir

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, cfg: Any) -> MetricsCollector:
        """Create MetricsCollector with thresholds from PipelineConfig."""
        # Build thresholds from streaming config
        thresholds = [
            ThresholdConfig(
                metric_type=MetricType.LATENCY_VIDEO,
                warning_threshold=cfg.streaming_latency_p95_ms,
                critical_threshold=cfg.streaming_latency_p99_ms,
                unit="ms",
            ),
            ThresholdConfig(
                metric_type=MetricType.LATENCY_INPUT,
                warning_threshold=cfg.streaming_input_latency_ms * 1.5,
                critical_threshold=cfg.streaming_input_latency_ms * 3.0,
                unit="ms",
            ),
            ThresholdConfig(
                metric_type=MetricType.AV_SYNC_DRIFT,
                warning_threshold=cfg.streaming_av_sync_drift_ms,
                critical_threshold=cfg.streaming_av_sync_drift_ms * 2,
                unit="ms",
            ),
            ThresholdConfig(
                metric_type=MetricType.FRAME_DROP,
                warning_threshold=cfg.streaming_frame_drop_max_pct,
                critical_threshold=cfg.streaming_frame_drop_max_pct * 3,
                unit="pct",
            ),
            ThresholdConfig(
                metric_type=MetricType.PACKET_LOSS,
                warning_threshold=1.0,    # 1% warning
                critical_threshold=5.0,   # 5% critical
                unit="pct",
            ),
            ThresholdConfig(
                metric_type=MetricType.BITRATE_VIDEO,
                warning_threshold=cfg.streaming_min_bitrate_kbps * 1.2,
                critical_threshold=cfg.streaming_min_bitrate_kbps,
                unit="kbps",
                direction="lower",  # Alert when bitrate drops BELOW threshold
            ),
            ThresholdConfig(
                metric_type=MetricType.FPS,
                warning_threshold=cfg.streaming_target_fps * 0.8,
                critical_threshold=cfg.streaming_target_fps * 0.5,
                unit="fps",
                direction="lower",
            ),
            ThresholdConfig(
                metric_type=MetricType.BATTERY,
                warning_threshold=cfg.streaming_battery_threshold_pct * 1.5,
                critical_threshold=cfg.streaming_battery_threshold_pct,
                unit="pct",
                direction="lower",
            ),
            ThresholdConfig(
                metric_type=MetricType.RECONNECTION,
                warning_threshold=cfg.streaming_reconnect_timeout_s,
                critical_threshold=cfg.streaming_reconnect_timeout_s * 2,
                unit="s",
            ),
        ]

        log_dir = cfg.results_dir / "streaming_metrics" if hasattr(cfg, "results_dir") else None
        alert_engine = AlertEngine(thresholds=thresholds, log_dir=log_dir)
        store = MetricsStore()

        return cls(store=store, alert_engine=alert_engine, log_dir=log_dir)

    # --- Convenience recording methods ---

    def record_latency(
        self, session_id: str, value: float,
        *, device: str = "", metric: MetricType = MetricType.LATENCY_VIDEO,
    ) -> Alert | None:
        """Record a latency measurement.  Returns alert if threshold violated."""
        sample = MetricSample(
            metric_type=metric,
            value=value,
            unit="ms",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_bitrate(
        self, session_id: str, value: float,
        *, device: str = "", audio: bool = False,
    ) -> Alert | None:
        """Record bitrate measurement (kbps)."""
        mt = MetricType.BITRATE_AUDIO if audio else MetricType.BITRATE_VIDEO
        sample = MetricSample(
            metric_type=mt,
            value=value,
            unit="kbps",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_packet_loss(
        self, session_id: str, value: float, *, device: str = "",
    ) -> Alert | None:
        """Record packet loss percentage."""
        sample = MetricSample(
            metric_type=MetricType.PACKET_LOSS,
            value=value,
            unit="pct",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_jitter(
        self, session_id: str, value: float, *, device: str = "",
    ) -> Alert | None:
        """Record jitter measurement (ms)."""
        sample = MetricSample(
            metric_type=MetricType.JITTER,
            value=value,
            unit="ms",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_frame_drop(
        self, session_id: str, value: float, *, device: str = "",
    ) -> Alert | None:
        """Record frame drop percentage."""
        sample = MetricSample(
            metric_type=MetricType.FRAME_DROP,
            value=value,
            unit="pct",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_fps(
        self, session_id: str, value: float, *, device: str = "",
    ) -> Alert | None:
        """Record FPS measurement."""
        sample = MetricSample(
            metric_type=MetricType.FPS,
            value=value,
            unit="fps",
            session_id=session_id,
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_battery(
        self, device: str, value: float,
    ) -> Alert | None:
        """Record device battery percentage."""
        sample = MetricSample(
            metric_type=MetricType.BATTERY,
            value=value,
            unit="pct",
            device=device,
        )
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_raw(self, sample: MetricSample) -> Alert | None:
        """Record raw metric sample."""
        self.store.ingest(sample)
        return self.alert_engine.evaluate(sample)

    def record_batch(self, samples: list[MetricSample]) -> list[Alert]:
        """Record batch of samples.  Returns triggered alerts."""
        self.store.ingest_batch(samples)
        return self.alert_engine.evaluate_batch(samples)

    # --- Reporting ---

    def get_session_report(self, session_id: str) -> dict[str, Any]:
        """Get comprehensive metrics report for a session."""
        report: dict[str, Any] = {"session_id": session_id, "metrics": {}}

        for mt in MetricType:
            stats = self.store.get_percentiles(mt, session_id=session_id)
            if stats.count > 0:
                report["metrics"][mt.value] = stats.to_dict()

        report["alerts"] = [
            a.to_dict() for a in self.alert_engine.get_active_alerts()
            if a.session_id == session_id
        ]

        return report

    def get_dashboard(self) -> dict[str, Any]:
        """Get dashboard-ready summary across all sessions."""
        return {
            "store_stats": self.store.get_stats(),
            "alert_stats": self.alert_engine.get_stats(),
            "active_alerts": [a.to_dict() for a in self.alert_engine.get_active_alerts()],
            "metric_summaries": {
                mt.value: self.store.get_percentiles(mt, window_s=300).to_dict()
                for mt in self.store.metric_types
            },
        }

    def export_metrics_json(self, output_path: Path | None = None) -> dict[str, Any]:
        """
        Export metrics in stream_monitor compatible format.

        Produces streaming_metrics.json artifact for stream_monitor agent.
        """
        data = {
            "timestamp": time.time(),
            "dashboard": self.get_dashboard(),
            "thresholds": {
                mt.value: {
                    "warning": tc.warning_threshold,
                    "critical": tc.critical_threshold,
                    "unit": tc.unit,
                    "direction": tc.direction,
                }
                for mt, tc in self.alert_engine.thresholds.items()
            },
        }

        path = output_path or (self.log_dir / "streaming_metrics.json" if self.log_dir else None)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log.info(f"Metrics exported to {path}")

        return data

    def get_stats(self) -> dict[str, Any]:
        """Get collector statistics."""
        return {
            "store": self.store.get_stats(),
            "alerts": self.alert_engine.get_stats(),
        }

    def export_report(self) -> dict[str, Any]:
        """Export full collector state for diagnostics."""
        return {
            "stats": self.get_stats(),
            "dashboard": self.get_dashboard(),
        }
