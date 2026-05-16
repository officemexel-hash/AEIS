"""
SYLION Pion D — Benchmark Harness

End-to-end streaming benchmark suite with 6 core metrics:
  1. Setup time       — ICE + DTLS + first-frame latency
  2. Input-to-photon  — touch event → screen pixel update
  3. Bitrate adapt    — ABR ramp-up/ramp-down response time
  4. Reconnect        — ICE restart + session resume time
  5. Frame drop       — consecutive frame drop ratio under load
  6. AV sync          — audio/video drift measurement

Designed for GrapheneOS Pixel 8 + Mudi 750v2 router (OpenWrt) test bed.
Deploy binary to /data/local/tmp/sylion/ on device.
"""

import json
import logging
import math
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("benchmark_harness")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BenchmarkStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class MetricUnit(str, Enum):
    MS = "ms"
    S = "s"
    PERCENT = "%"
    KBPS = "kbps"
    FPS = "fps"
    FRAMES = "frames"
    COUNT = "count"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkThresholds:
    """Pass/fail thresholds for each benchmark metric."""
    # Setup time
    setup_time_p50_ms: float = 800.0     # 50th percentile
    setup_time_p95_ms: float = 2000.0    # 95th percentile — FAIL above

    # Input-to-photon
    input_to_photon_p50_ms: float = 50.0
    input_to_photon_p95_ms: float = 100.0
    input_to_photon_max_ms: float = 200.0

    # Bitrate adaptation
    abr_rampup_max_ms: float = 5000.0     # Max time to reach target bitrate
    abr_rampdown_max_ms: float = 2000.0   # Max time to drop bitrate on congestion

    # Reconnect
    reconnect_p50_ms: float = 1500.0
    reconnect_p95_ms: float = 4000.0
    reconnect_max_attempts: int = 3

    # Frame drop
    frame_drop_ratio_warn: float = 0.01   # 1% warning
    frame_drop_ratio_fail: float = 0.05   # 5% fail
    consecutive_drops_max: int = 5         # Max consecutive dropped frames

    # AV sync
    av_sync_drift_warn_ms: float = 40.0   # ±40ms warning
    av_sync_drift_fail_ms: float = 80.0   # ±80ms fail — ITU-T G.1010 limit


@dataclass
class MetricSample:
    """Single measurement sample."""
    value: float
    unit: MetricUnit
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    status: BenchmarkStatus
    samples: list[MetricSample] = field(default_factory=list)
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    mean: float = 0.0
    std_dev: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    unit: MetricUnit = MetricUnit.MS
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0

    def compute_stats(self) -> None:
        """Compute percentiles and stats from samples."""
        values = [s.value for s in self.samples]
        if not values:
            return

        values_sorted = sorted(values)
        n = len(values_sorted)

        self.min_val = values_sorted[0]
        self.max_val = values_sorted[-1]
        self.mean = statistics.mean(values_sorted)
        self.std_dev = statistics.stdev(values_sorted) if n > 1 else 0.0

        # Percentiles using nearest-rank method
        self.p50 = values_sorted[int(n * 0.50)] if n > 0 else 0.0
        self.p95 = values_sorted[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
        self.p99 = values_sorted[min(int(n * 0.99), n - 1)] if n > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "samples_count": len(self.samples),
            "p50": round(self.p50, 2),
            "p95": round(self.p95, 2),
            "p99": round(self.p99, 2),
            "mean": round(self.mean, 2),
            "std_dev": round(self.std_dev, 2),
            "min": round(self.min_val, 2),
            "max": round(self.max_val, 2),
            "unit": self.unit.value,
            "message": self.message,
            "duration_s": round(self.duration_s, 3),
            "details": self.details,
        }


@dataclass
class BenchmarkSuiteReport:
    """Complete benchmark suite report."""
    run_id: str
    timestamp: float = field(default_factory=time.time)
    results: list[BenchmarkResult] = field(default_factory=list)
    device_info: dict[str, str] = field(default_factory=dict)
    network_info: dict[str, str] = field(default_factory=dict)
    overall_status: BenchmarkStatus = BenchmarkStatus.PENDING
    duration_s: float = 0.0

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == BenchmarkStatus.PASSED)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == BenchmarkStatus.FAILED)

    def compute_overall(self) -> None:
        """Determine overall status from individual results."""
        if any(r.status == BenchmarkStatus.FAILED for r in self.results):
            self.overall_status = BenchmarkStatus.FAILED
        elif any(r.status == BenchmarkStatus.ERROR for r in self.results):
            self.overall_status = BenchmarkStatus.ERROR
        elif all(r.status in (BenchmarkStatus.PASSED, BenchmarkStatus.SKIPPED)
                 for r in self.results):
            self.overall_status = BenchmarkStatus.PASSED
        else:
            self.overall_status = BenchmarkStatus.RUNNING

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "total": len(self.results),
            "duration_s": round(self.duration_s, 3),
            "device_info": self.device_info,
            "network_info": self.network_info,
            "results": [r.to_dict() for r in self.results],
        }

    def save_json(self, path: Path) -> None:
        """Save report as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("Benchmark report saved: %s", path)


# ---------------------------------------------------------------------------
# Individual Benchmark Implementations
# ---------------------------------------------------------------------------

class SetupTimeBenchmark:
    """Benchmark 1: Session setup time (ICE negotiation + DTLS + first frame).

    Measures the end-to-end time from initiating a WebRTC connection
    to receiving the first decodable video frame.
    """

    def __init__(self, iterations: int = 10, thresholds: BenchmarkThresholds | None = None):
        self.iterations = iterations
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        setup_fn: Callable[[], float] | None = None,
        pre_recorded_samples: list[float] | None = None,
    ) -> BenchmarkResult:
        """Run setup time benchmark.

        Args:
            setup_fn: Callable that performs one setup and returns elapsed_ms.
            pre_recorded_samples: Use pre-recorded measurements instead of live.
        """
        result = BenchmarkResult(name="setup_time", unit=MetricUnit.MS, status=BenchmarkStatus.RUNNING)
        t0 = time.monotonic()

        if pre_recorded_samples:
            for val in pre_recorded_samples:
                result.samples.append(MetricSample(value=val, unit=MetricUnit.MS))
        elif setup_fn:
            for i in range(self.iterations):
                try:
                    elapsed_ms = setup_fn()
                    result.samples.append(MetricSample(
                        value=elapsed_ms, unit=MetricUnit.MS,
                        metadata={"iteration": i},
                    ))
                except Exception as e:
                    log.warning("Setup iteration %d failed: %s", i, e)
                    result.samples.append(MetricSample(
                        value=float("inf"), unit=MetricUnit.MS,
                        metadata={"iteration": i, "error": str(e)},
                    ))
        else:
            # Simulation mode — generate realistic samples
            import random
            rng = random.Random(42)
            for i in range(self.iterations):
                # Realistic setup: 400-1200ms with occasional spikes
                base = rng.gauss(700, 150)
                spike = rng.random() < 0.1  # 10% chance of spike
                val = base * 2.5 if spike else max(200, base)
                result.samples.append(MetricSample(
                    value=val, unit=MetricUnit.MS,
                    metadata={"iteration": i, "simulated": True},
                ))

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        # Evaluate against thresholds
        if result.p95 <= self.thresholds.setup_time_p95_ms:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"Setup time OK: p50={result.p50:.0f}ms, "
                f"p95={result.p95:.0f}ms (limit={self.thresholds.setup_time_p95_ms:.0f}ms)"
            )
        else:
            result.status = BenchmarkStatus.FAILED
            result.message = (
                f"Setup time SLOW: p95={result.p95:.0f}ms "
                f"exceeds limit={self.thresholds.setup_time_p95_ms:.0f}ms"
            )

        return result


class InputToPhotonBenchmark:
    """Benchmark 2: Input-to-photon latency.

    Measures the delay from touch input event to the corresponding
    screen pixel update. Critical for interactive streaming quality.
    """

    def __init__(self, iterations: int = 50, thresholds: BenchmarkThresholds | None = None):
        self.iterations = iterations
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        measure_fn: Callable[[], float] | None = None,
        pre_recorded_samples: list[float] | None = None,
    ) -> BenchmarkResult:
        result = BenchmarkResult(
            name="input_to_photon", unit=MetricUnit.MS,
            status=BenchmarkStatus.RUNNING,
        )
        t0 = time.monotonic()

        if pre_recorded_samples:
            for val in pre_recorded_samples:
                result.samples.append(MetricSample(value=val, unit=MetricUnit.MS))
        elif measure_fn:
            for i in range(self.iterations):
                try:
                    latency_ms = measure_fn()
                    result.samples.append(MetricSample(
                        value=latency_ms, unit=MetricUnit.MS,
                        metadata={"iteration": i},
                    ))
                except Exception as e:
                    log.warning("Input-to-photon iteration %d failed: %s", i, e)
        else:
            import random
            rng = random.Random(123)
            for i in range(self.iterations):
                # Realistic: 20-80ms, occasional outliers
                base = rng.gauss(45, 12)
                outlier = rng.random() < 0.05
                val = base * 3.0 if outlier else max(10, base)
                result.samples.append(MetricSample(
                    value=val, unit=MetricUnit.MS,
                    metadata={"iteration": i, "simulated": True},
                ))

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        if result.p95 <= self.thresholds.input_to_photon_p95_ms:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"Input-to-photon OK: p50={result.p50:.1f}ms, "
                f"p95={result.p95:.1f}ms (limit={self.thresholds.input_to_photon_p95_ms:.0f}ms)"
            )
        else:
            result.status = BenchmarkStatus.FAILED
            result.message = (
                f"Input-to-photon SLOW: p95={result.p95:.1f}ms "
                f"exceeds limit={self.thresholds.input_to_photon_p95_ms:.0f}ms"
            )

        result.details["max_allowed_ms"] = self.thresholds.input_to_photon_max_ms
        result.details["max_exceeded"] = result.max_val > self.thresholds.input_to_photon_max_ms

        return result


class BitrateAdaptBenchmark:
    """Benchmark 3: ABR bitrate adaptation response time.

    Measures how quickly the encoder adapts bitrate in response to
    network condition changes (congestion ramp-down, recovery ramp-up).
    """

    def __init__(self, thresholds: BenchmarkThresholds | None = None):
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        rampup_samples_ms: list[float] | None = None,
        rampdown_samples_ms: list[float] | None = None,
        abr_controller: Any | None = None,
    ) -> BenchmarkResult:
        result = BenchmarkResult(
            name="bitrate_adapt", unit=MetricUnit.MS,
            status=BenchmarkStatus.RUNNING,
        )
        t0 = time.monotonic()

        rampup_times: list[float] = rampup_samples_ms or []
        rampdown_times: list[float] = rampdown_samples_ms or []

        if not rampup_times and not rampdown_times:
            # Simulation mode
            import random
            rng = random.Random(456)

            # Simulate 5 ramp-up tests
            for _ in range(5):
                rampup_times.append(max(500, rng.gauss(3000, 800)))

            # Simulate 5 ramp-down tests
            for _ in range(5):
                rampdown_times.append(max(200, rng.gauss(1200, 400)))

        # Record all samples
        for val in rampup_times:
            result.samples.append(MetricSample(
                value=val, unit=MetricUnit.MS,
                metadata={"direction": "rampup"},
            ))
        for val in rampdown_times:
            result.samples.append(MetricSample(
                value=val, unit=MetricUnit.MS,
                metadata={"direction": "rampdown"},
            ))

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        # Check thresholds separately
        rampup_ok = True
        rampdown_ok = True

        if rampup_times:
            rampup_p95 = sorted(rampup_times)[min(int(len(rampup_times) * 0.95), len(rampup_times) - 1)]
            rampup_ok = rampup_p95 <= self.thresholds.abr_rampup_max_ms
            result.details["rampup_p95_ms"] = round(rampup_p95, 1)
            result.details["rampup_limit_ms"] = self.thresholds.abr_rampup_max_ms

        if rampdown_times:
            rampdown_p95 = sorted(rampdown_times)[min(int(len(rampdown_times) * 0.95), len(rampdown_times) - 1)]
            rampdown_ok = rampdown_p95 <= self.thresholds.abr_rampdown_max_ms
            result.details["rampdown_p95_ms"] = round(rampdown_p95, 1)
            result.details["rampdown_limit_ms"] = self.thresholds.abr_rampdown_max_ms

        if rampup_ok and rampdown_ok:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"ABR adaptation OK: rampup p95={result.details.get('rampup_p95_ms', 0):.0f}ms, "
                f"rampdown p95={result.details.get('rampdown_p95_ms', 0):.0f}ms"
            )
        else:
            result.status = BenchmarkStatus.FAILED
            parts = []
            if not rampup_ok:
                parts.append(f"rampup p95={result.details.get('rampup_p95_ms', 0):.0f}ms > {self.thresholds.abr_rampup_max_ms:.0f}ms")
            if not rampdown_ok:
                parts.append(f"rampdown p95={result.details.get('rampdown_p95_ms', 0):.0f}ms > {self.thresholds.abr_rampdown_max_ms:.0f}ms")
            result.message = f"ABR adaptation SLOW: {', '.join(parts)}"

        return result


class ReconnectBenchmark:
    """Benchmark 4: ICE restart + session resume time.

    Measures recovery time after network interruption — ICE restart,
    DTLS renegotiation, and stream resumption.
    """

    def __init__(self, iterations: int = 5, thresholds: BenchmarkThresholds | None = None):
        self.iterations = iterations
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        reconnect_fn: Callable[[], tuple[float, int]] | None = None,
        pre_recorded_samples: list[tuple[float, int]] | None = None,
    ) -> BenchmarkResult:
        """Run reconnect benchmark.

        reconnect_fn returns (elapsed_ms, attempt_count).
        pre_recorded_samples: list of (elapsed_ms, attempts).
        """
        result = BenchmarkResult(
            name="reconnect", unit=MetricUnit.MS,
            status=BenchmarkStatus.RUNNING,
        )
        t0 = time.monotonic()

        attempt_counts: list[int] = []

        if pre_recorded_samples:
            for val_ms, attempts in pre_recorded_samples:
                result.samples.append(MetricSample(
                    value=val_ms, unit=MetricUnit.MS,
                    metadata={"attempts": attempts},
                ))
                attempt_counts.append(attempts)
        elif reconnect_fn:
            for i in range(self.iterations):
                try:
                    elapsed_ms, attempts = reconnect_fn()
                    result.samples.append(MetricSample(
                        value=elapsed_ms, unit=MetricUnit.MS,
                        metadata={"iteration": i, "attempts": attempts},
                    ))
                    attempt_counts.append(attempts)
                except Exception as e:
                    log.warning("Reconnect iteration %d failed: %s", i, e)
        else:
            import random
            rng = random.Random(789)
            for i in range(self.iterations):
                attempts = rng.choice([1, 1, 1, 2, 2, 3])
                base = rng.gauss(1200, 400) * attempts
                val = max(300, base)
                result.samples.append(MetricSample(
                    value=val, unit=MetricUnit.MS,
                    metadata={"iteration": i, "attempts": attempts, "simulated": True},
                ))
                attempt_counts.append(attempts)

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        max_attempts_seen = max(attempt_counts) if attempt_counts else 0
        result.details["max_attempts_seen"] = max_attempts_seen
        result.details["max_attempts_allowed"] = self.thresholds.reconnect_max_attempts

        time_ok = result.p95 <= self.thresholds.reconnect_p95_ms
        attempts_ok = max_attempts_seen <= self.thresholds.reconnect_max_attempts

        if time_ok and attempts_ok:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"Reconnect OK: p50={result.p50:.0f}ms, p95={result.p95:.0f}ms, "
                f"max_attempts={max_attempts_seen}"
            )
        else:
            parts = []
            if not time_ok:
                parts.append(f"p95={result.p95:.0f}ms > {self.thresholds.reconnect_p95_ms:.0f}ms")
            if not attempts_ok:
                parts.append(f"max_attempts={max_attempts_seen} > {self.thresholds.reconnect_max_attempts}")
            result.status = BenchmarkStatus.FAILED
            result.message = f"Reconnect SLOW: {', '.join(parts)}"

        return result


class FrameDropBenchmark:
    """Benchmark 5: Video frame drop analysis under load.

    Monitors the ratio of dropped frames and detects consecutive
    frame drops that cause visible stutter.
    """

    def __init__(self, thresholds: BenchmarkThresholds | None = None):
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        total_frames: int = 0,
        dropped_frames: int = 0,
        consecutive_drop_max: int = 0,
        frame_timestamps: list[float] | None = None,
    ) -> BenchmarkResult:
        """Run frame drop benchmark.

        Can use pre-computed stats or analyze raw frame timestamps.
        """
        result = BenchmarkResult(
            name="frame_drop", unit=MetricUnit.PERCENT,
            status=BenchmarkStatus.RUNNING,
        )
        t0 = time.monotonic()

        if frame_timestamps and len(frame_timestamps) > 1:
            # Analyze frame timestamps to detect drops
            total_frames, dropped_frames, consecutive_drop_max = (
                self._analyze_frame_timestamps(frame_timestamps)
            )

        if total_frames == 0:
            # Simulation mode
            import random
            rng = random.Random(321)
            total_frames = 1800  # 60s at 30fps
            # Simulate ~2% drop rate with occasional bursts
            drops = []
            for _ in range(total_frames):
                if drops and drops[-1] and rng.random() < 0.3:
                    drops.append(True)  # Consecutive drop more likely after a drop
                else:
                    drops.append(rng.random() < 0.02)

            dropped_frames = sum(drops)
            # Find max consecutive drops
            max_consec = 0
            current_consec = 0
            for d in drops:
                if d:
                    current_consec += 1
                    max_consec = max(max_consec, current_consec)
                else:
                    current_consec = 0
            consecutive_drop_max = max_consec

        drop_ratio = dropped_frames / total_frames if total_frames > 0 else 0.0

        result.samples.append(MetricSample(
            value=drop_ratio * 100, unit=MetricUnit.PERCENT,
            metadata={
                "total_frames": total_frames,
                "dropped_frames": dropped_frames,
                "consecutive_max": consecutive_drop_max,
            },
        ))

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        result.details["total_frames"] = total_frames
        result.details["dropped_frames"] = dropped_frames
        result.details["drop_ratio"] = round(drop_ratio, 6)
        result.details["consecutive_drop_max"] = consecutive_drop_max
        result.details["consecutive_limit"] = self.thresholds.consecutive_drops_max

        ratio_ok = drop_ratio <= self.thresholds.frame_drop_ratio_fail
        consec_ok = consecutive_drop_max <= self.thresholds.consecutive_drops_max

        if ratio_ok and consec_ok:
            if drop_ratio > self.thresholds.frame_drop_ratio_warn:
                result.status = BenchmarkStatus.PASSED  # Technically pass but close
                result.message = (
                    f"Frame drops marginal: {drop_ratio:.2%} "
                    f"(warn={self.thresholds.frame_drop_ratio_warn:.1%}), "
                    f"max_consecutive={consecutive_drop_max}"
                )
            else:
                result.status = BenchmarkStatus.PASSED
                result.message = (
                    f"Frame drops OK: {drop_ratio:.2%} ({dropped_frames}/{total_frames}), "
                    f"max_consecutive={consecutive_drop_max}"
                )
        else:
            parts = []
            if not ratio_ok:
                parts.append(f"drop_ratio={drop_ratio:.2%} > {self.thresholds.frame_drop_ratio_fail:.1%}")
            if not consec_ok:
                parts.append(f"consecutive={consecutive_drop_max} > {self.thresholds.consecutive_drops_max}")
            result.status = BenchmarkStatus.FAILED
            result.message = f"Frame drops EXCESSIVE: {', '.join(parts)}"

        return result

    @staticmethod
    def _analyze_frame_timestamps(
        timestamps: list[float],
    ) -> tuple[int, int, int]:
        """Analyze frame timestamps to detect drops.

        Assumes ~33ms interval for 30fps. A gap > 1.5× expected = dropped frame.
        Returns (total_frames, dropped_frames, max_consecutive_drops).
        """
        if len(timestamps) < 2:
            return len(timestamps), 0, 0

        # Estimate expected interval from median
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        expected_interval = sorted(intervals)[len(intervals) // 2]

        if expected_interval <= 0:
            return len(timestamps), 0, 0

        total = len(timestamps)
        dropped = 0
        max_consec = 0
        current_consec = 0

        for interval in intervals:
            if interval > expected_interval * 1.5:
                # Dropped frame(s)
                estimated_drops = max(1, round(interval / expected_interval) - 1)
                dropped += estimated_drops
                current_consec += estimated_drops
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        return total, dropped, max_consec


class AVSyncBenchmark:
    """Benchmark 6: Audio/Video synchronization drift.

    Measures the timing offset between audio and video streams.
    ITU-T G.1010: audio should be within ±80ms of video.
    """

    def __init__(self, thresholds: BenchmarkThresholds | None = None):
        self.thresholds = thresholds or BenchmarkThresholds()

    def run(
        self,
        drift_samples_ms: list[float] | None = None,
        audio_timestamps: list[float] | None = None,
        video_timestamps: list[float] | None = None,
    ) -> BenchmarkResult:
        """Run AV sync benchmark.

        drift_samples_ms: pre-computed drift measurements (positive = audio ahead).
        Alternatively, provide raw audio/video timestamp pairs for computation.
        """
        result = BenchmarkResult(
            name="av_sync", unit=MetricUnit.MS,
            status=BenchmarkStatus.RUNNING,
        )
        t0 = time.monotonic()

        drifts: list[float] = []

        if drift_samples_ms:
            drifts = drift_samples_ms
        elif audio_timestamps and video_timestamps:
            # Compute drift from timestamp pairs
            min_len = min(len(audio_timestamps), len(video_timestamps))
            for i in range(min_len):
                drift_ms = (audio_timestamps[i] - video_timestamps[i]) * 1000
                drifts.append(drift_ms)
        else:
            # Simulation mode
            import random
            rng = random.Random(654)
            for _ in range(100):
                # Drift: mostly small, occasional larger drifts
                drift = rng.gauss(5, 20)  # Slight audio-ahead bias
                if rng.random() < 0.05:
                    drift = rng.gauss(0, 60)  # Occasional larger drift
                drifts.append(drift)

        for val in drifts:
            result.samples.append(MetricSample(
                value=abs(val), unit=MetricUnit.MS,
                metadata={"raw_drift_ms": val, "direction": "audio_ahead" if val > 0 else "video_ahead"},
            ))

        result.duration_s = time.monotonic() - t0
        result.compute_stats()

        # Use absolute values for threshold comparison
        abs_drifts = [abs(d) for d in drifts]
        abs_sorted = sorted(abs_drifts)
        n = len(abs_sorted)

        abs_p95 = abs_sorted[min(int(n * 0.95), n - 1)] if n > 0 else 0
        abs_max = abs_sorted[-1] if abs_sorted else 0

        result.details["abs_drift_p95_ms"] = round(abs_p95, 2)
        result.details["abs_drift_max_ms"] = round(abs_max, 2)
        result.details["mean_drift_ms"] = round(statistics.mean(drifts), 2) if drifts else 0
        result.details["itu_limit_ms"] = self.thresholds.av_sync_drift_fail_ms

        if abs_p95 <= self.thresholds.av_sync_drift_warn_ms:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"AV sync OK: abs_p95={abs_p95:.1f}ms, "
                f"mean_drift={result.details['mean_drift_ms']:.1f}ms"
            )
        elif abs_p95 <= self.thresholds.av_sync_drift_fail_ms:
            result.status = BenchmarkStatus.PASSED
            result.message = (
                f"AV sync marginal: abs_p95={abs_p95:.1f}ms "
                f"(warn={self.thresholds.av_sync_drift_warn_ms:.0f}ms, "
                f"limit={self.thresholds.av_sync_drift_fail_ms:.0f}ms)"
            )
        else:
            result.status = BenchmarkStatus.FAILED
            result.message = (
                f"AV sync FAILED: abs_p95={abs_p95:.1f}ms "
                f"exceeds ITU limit={self.thresholds.av_sync_drift_fail_ms:.0f}ms"
            )

        return result


# ---------------------------------------------------------------------------
# Main: BenchmarkHarness
# ---------------------------------------------------------------------------

class BenchmarkHarness:
    """Orchestrates the full benchmark suite.

    Runs all 6 benchmarks in sequence, collects results, and produces
    a comprehensive report. Designed for the SYLION test bed:
      - Pixel 8 (GrapheneOS) via USB/ADB
      - Mudi 750v2 router (OpenWrt) via Ethernet
      - Binary deployed to /data/local/tmp/sylion/
    """

    def __init__(
        self,
        thresholds: BenchmarkThresholds | None = None,
        device_info: dict[str, str] | None = None,
        network_info: dict[str, str] | None = None,
        output_dir: Path | None = None,
    ):
        self.thresholds = thresholds or BenchmarkThresholds()
        self.device_info = device_info or {
            "model": "Pixel 8",
            "os": "GrapheneOS",
            "deploy_path": "/data/local/tmp/sylion/",
            "connection": "USB/ADB",
        }
        self.network_info = network_info or {
            "router": "Mudi 750v2",
            "firmware": "OpenWrt",
            "connection": "Ethernet (isolated LAN)",
        }
        self.output_dir = output_dir or Path("benchmark_results")

        self._benchmarks: dict[str, Any] = {
            "setup_time": SetupTimeBenchmark(thresholds=self.thresholds),
            "input_to_photon": InputToPhotonBenchmark(thresholds=self.thresholds),
            "bitrate_adapt": BitrateAdaptBenchmark(thresholds=self.thresholds),
            "reconnect": ReconnectBenchmark(thresholds=self.thresholds),
            "frame_drop": FrameDropBenchmark(thresholds=self.thresholds),
            "av_sync": AVSyncBenchmark(thresholds=self.thresholds),
        }

        self._run_history: list[BenchmarkSuiteReport] = []

        log.info("BenchmarkHarness init: %d benchmarks, output=%s",
                 len(self._benchmarks), self.output_dir)

    def run_all(
        self,
        run_id: str | None = None,
        skip: list[str] | None = None,
        setup_fn: Callable[[], float] | None = None,
        input_fn: Callable[[], float] | None = None,
        reconnect_fn: Callable[[], tuple[float, int]] | None = None,
        rampup_samples: list[float] | None = None,
        rampdown_samples: list[float] | None = None,
        frame_total: int = 0,
        frame_dropped: int = 0,
        frame_consec_max: int = 0,
        frame_timestamps: list[float] | None = None,
        av_drift_samples: list[float] | None = None,
        audio_ts: list[float] | None = None,
        video_ts: list[float] | None = None,
    ) -> BenchmarkSuiteReport:
        """Run the full benchmark suite.

        All measurement functions are optional — if not provided,
        simulated data is used for demonstration/testing.
        """
        import uuid as _uuid
        rid = run_id or f"bench-{_uuid.uuid4().hex[:8]}"
        skip_set = set(skip or [])

        report = BenchmarkSuiteReport(
            run_id=rid,
            device_info=self.device_info,
            network_info=self.network_info,
        )

        t0 = time.monotonic()
        log.info("╔══════════════════════════════════════════════════╗")
        log.info("║  BENCHMARK SUITE: %s                    ║", rid[:20].ljust(20))
        log.info("╚══════════════════════════════════════════════════╝")

        # 1. Setup time
        if "setup_time" not in skip_set:
            log.info("  [1/6] Running: setup_time")
            r = self._benchmarks["setup_time"].run(setup_fn=setup_fn)
            report.results.append(r)
            log.info("  [1/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="setup_time", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        # 2. Input-to-photon
        if "input_to_photon" not in skip_set:
            log.info("  [2/6] Running: input_to_photon")
            r = self._benchmarks["input_to_photon"].run(measure_fn=input_fn)
            report.results.append(r)
            log.info("  [2/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="input_to_photon", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        # 3. Bitrate adapt
        if "bitrate_adapt" not in skip_set:
            log.info("  [3/6] Running: bitrate_adapt")
            r = self._benchmarks["bitrate_adapt"].run(
                rampup_samples_ms=rampup_samples,
                rampdown_samples_ms=rampdown_samples,
            )
            report.results.append(r)
            log.info("  [3/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="bitrate_adapt", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        # 4. Reconnect
        if "reconnect" not in skip_set:
            log.info("  [4/6] Running: reconnect")
            r = self._benchmarks["reconnect"].run(reconnect_fn=reconnect_fn)
            report.results.append(r)
            log.info("  [4/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="reconnect", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        # 5. Frame drop
        if "frame_drop" not in skip_set:
            log.info("  [5/6] Running: frame_drop")
            r = self._benchmarks["frame_drop"].run(
                total_frames=frame_total,
                dropped_frames=frame_dropped,
                consecutive_drop_max=frame_consec_max,
                frame_timestamps=frame_timestamps,
            )
            report.results.append(r)
            log.info("  [5/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="frame_drop", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        # 6. AV sync
        if "av_sync" not in skip_set:
            log.info("  [6/6] Running: av_sync")
            r = self._benchmarks["av_sync"].run(
                drift_samples_ms=av_drift_samples,
                audio_timestamps=audio_ts,
                video_timestamps=video_ts,
            )
            report.results.append(r)
            log.info("  [6/6] %s: %s", r.status.value.upper(), r.message)
        else:
            report.results.append(BenchmarkResult(
                name="av_sync", status=BenchmarkStatus.SKIPPED,
                message="Skipped by user",
            ))

        report.duration_s = time.monotonic() - t0
        report.compute_overall()

        log.info("═" * 50)
        log.info("BENCHMARK SUITE COMPLETE: %s (passed=%d, failed=%d, time=%.1fs)",
                 report.overall_status.value.upper(),
                 report.passed_count, report.failed_count, report.duration_s)

        # Save report
        self.output_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.output_dir / f"{rid}.json"
        report.save_json(report_path)

        self._run_history.append(report)

        return report

    def get_stats(self) -> dict[str, Any]:
        """Get harness statistics."""
        return {
            "benchmarks": list(self._benchmarks.keys()),
            "total_runs": len(self._run_history),
            "device": self.device_info,
            "network": self.network_info,
            "thresholds": {
                "setup_p95_ms": self.thresholds.setup_time_p95_ms,
                "input_photon_p95_ms": self.thresholds.input_to_photon_p95_ms,
                "abr_rampup_ms": self.thresholds.abr_rampup_max_ms,
                "reconnect_p95_ms": self.thresholds.reconnect_p95_ms,
                "frame_drop_fail": self.thresholds.frame_drop_ratio_fail,
                "av_sync_fail_ms": self.thresholds.av_sync_drift_fail_ms,
            },
        }

    def get_history(self) -> list[dict]:
        """Get all run history as dicts."""
        return [r.to_dict() for r in self._run_history]

    def health_check(self) -> str:
        """Simple health check."""
        return "OK"
