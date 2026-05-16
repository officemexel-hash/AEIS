"""
SYLION Pion D — Adaptive Bitrate (ABR) Controller

Implements adaptive bitrate logic for the streaming pipeline.
Adjusts video encoder settings based on network conditions, device
capabilities, and latency budget.

ABR Algorithm:
  1. Monitor network bandwidth (from WebRTC stats)
  2. Select bitrate ladder rung based on available bandwidth
  3. Apply encoder profile (H.264 level, GOP, keyframe interval)
  4. React to congestion (REMB, transport-cc feedback)
  5. Respect battery/thermal constraints (throttle when hot)

Bitrate Ladder (config-driven):
  Rung  Resolution   FPS   Min-Max kbps   H.264 Profile
  0     640x360      30    300-800        Baseline
  1     854x480      30    500-1500       Main
  2     1280x720     30    1000-4000      High
  3     1920x1080    30    2000-8000      High

⚠️  LLM NEVER issues raw shell commands.
"""

from __future__ import annotations

import enum
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("abr_controller")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ABRState(enum.Enum):
    """ABR controller state."""
    IDLE = "IDLE"
    RAMPING_UP = "RAMPING_UP"
    STABLE = "STABLE"
    CONGESTED = "CONGESTED"
    RAMPING_DOWN = "RAMPING_DOWN"
    THROTTLED = "THROTTLED"      # Battery/thermal throttling
    PAUSED = "PAUSED"


class EncoderProfile(enum.Enum):
    """H.264 encoder profiles."""
    BASELINE = "Baseline"
    MAIN = "Main"
    HIGH = "High"


class CongestionSignal(enum.Enum):
    """Types of congestion feedback."""
    REMB = "REMB"                    # Receiver Estimated Maximum Bitrate
    TRANSPORT_CC = "transport-cc"    # Transport-wide congestion control
    PLI = "PLI"                      # Picture Loss Indication
    NACK = "NACK"                    # Negative Acknowledgement
    FIR = "FIR"                      # Full Intra Request
    PACKET_LOSS = "packet_loss"      # Observed packet loss
    RTT_SPIKE = "rtt_spike"          # RTT spike detected


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BitrateRung:
    """A single rung in the bitrate ladder."""
    index: int
    resolution: str          # "1920x1080"
    width: int
    height: int
    fps: int
    min_bitrate_kbps: int
    max_bitrate_kbps: int
    target_bitrate_kbps: int
    h264_profile: EncoderProfile
    h264_level: str = ""     # e.g., "3.1", "4.0", "5.1"
    keyframe_interval_s: float = 2.0
    gop_size: int = 60       # GOP size in frames (fps * keyframe_interval)

    @property
    def resolution_tuple(self) -> tuple[int, int]:
        return (self.width, self.height)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "resolution": self.resolution,
            "fps": self.fps,
            "min_bitrate_kbps": self.min_bitrate_kbps,
            "max_bitrate_kbps": self.max_bitrate_kbps,
            "target_bitrate_kbps": self.target_bitrate_kbps,
            "h264_profile": self.h264_profile.value,
            "h264_level": self.h264_level,
            "keyframe_interval_s": self.keyframe_interval_s,
            "gop_size": self.gop_size,
        }


@dataclass
class EncoderSettings:
    """Current encoder output settings — what the encoder should use NOW."""
    bitrate_kbps: int
    resolution: str
    width: int
    height: int
    fps: int
    h264_profile: EncoderProfile
    h264_level: str
    keyframe_interval_s: float
    gop_size: int
    rung_index: int
    hw_encoder: bool = True     # Hardware encoder (MediaCodec on Pixel)
    cbr_mode: bool = False      # Constant bitrate (vs VBR)
    max_qp: int = 51            # Maximum quantization parameter
    min_qp: int = 18            # Minimum quantization parameter

    def to_dict(self) -> dict[str, Any]:
        return {
            "bitrate_kbps": self.bitrate_kbps,
            "resolution": self.resolution,
            "fps": self.fps,
            "h264_profile": self.h264_profile.value,
            "h264_level": self.h264_level,
            "keyframe_interval_s": self.keyframe_interval_s,
            "gop_size": self.gop_size,
            "rung_index": self.rung_index,
            "hw_encoder": self.hw_encoder,
            "cbr_mode": self.cbr_mode,
            "max_qp": self.max_qp,
            "min_qp": self.min_qp,
        }


@dataclass
class NetworkEstimate:
    """Network bandwidth estimate from WebRTC feedback."""
    available_kbps: float        # Estimated available bandwidth
    rtt_ms: float = 0.0          # Round-trip time
    packet_loss_pct: float = 0.0 # Observed packet loss
    jitter_ms: float = 0.0       # Observed jitter
    timestamp: float = field(default_factory=time.time)
    source: CongestionSignal = CongestionSignal.REMB

    def to_dict(self) -> dict[str, Any]:
        return {
            "available_kbps": round(self.available_kbps, 1),
            "rtt_ms": round(self.rtt_ms, 1),
            "packet_loss_pct": round(self.packet_loss_pct, 2),
            "jitter_ms": round(self.jitter_ms, 1),
            "source": self.source.value,
        }


@dataclass
class ABRDecision:
    """A recorded ABR decision (for logging and debugging)."""
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    previous_rung: int = 0
    new_rung: int = 0
    previous_bitrate_kbps: int = 0
    new_bitrate_kbps: int = 0
    network_estimate: NetworkEstimate | None = None
    state: ABRState = ABRState.IDLE
    throttle_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "reason": self.reason,
            "previous_rung": self.previous_rung,
            "new_rung": self.new_rung,
            "previous_bitrate_kbps": self.previous_bitrate_kbps,
            "new_bitrate_kbps": self.new_bitrate_kbps,
            "network_estimate": self.network_estimate.to_dict() if self.network_estimate else None,
            "state": self.state.value,
            "throttle_reason": self.throttle_reason,
        }


# ---------------------------------------------------------------------------
# Default bitrate ladder
# ---------------------------------------------------------------------------

DEFAULT_BITRATE_LADDER: list[BitrateRung] = [
    BitrateRung(
        index=0, resolution="640x360", width=640, height=360,
        fps=30, min_bitrate_kbps=300, max_bitrate_kbps=800,
        target_bitrate_kbps=500,
        h264_profile=EncoderProfile.BASELINE, h264_level="3.0",
        keyframe_interval_s=2.0, gop_size=60,
    ),
    BitrateRung(
        index=1, resolution="854x480", width=854, height=480,
        fps=30, min_bitrate_kbps=500, max_bitrate_kbps=1500,
        target_bitrate_kbps=1000,
        h264_profile=EncoderProfile.MAIN, h264_level="3.1",
        keyframe_interval_s=2.0, gop_size=60,
    ),
    BitrateRung(
        index=2, resolution="1280x720", width=1280, height=720,
        fps=30, min_bitrate_kbps=1000, max_bitrate_kbps=4000,
        target_bitrate_kbps=2500,
        h264_profile=EncoderProfile.HIGH, h264_level="4.0",
        keyframe_interval_s=2.0, gop_size=60,
    ),
    BitrateRung(
        index=3, resolution="1920x1080", width=1920, height=1080,
        fps=30, min_bitrate_kbps=2000, max_bitrate_kbps=8000,
        target_bitrate_kbps=5000,
        h264_profile=EncoderProfile.HIGH, h264_level="5.1",
        keyframe_interval_s=2.0, gop_size=60,
    ),
]


# ---------------------------------------------------------------------------
# ABR Controller
# ---------------------------------------------------------------------------

class ABRController:
    """
    Adaptive Bitrate Controller for SYLION streaming pipeline.

    Selects the optimal bitrate/resolution based on network conditions
    and device constraints.  Integrates with:
      - MetricsCollector (for bandwidth estimates)
      - SignalingServer (for REMB/transport-cc feedback)
      - DeviceHarness (for battery/thermal status)

    Usage:
        controller = ABRController.from_config(cfg)
        settings = controller.get_current_settings()
        # On network feedback:
        controller.on_network_estimate(NetworkEstimate(available_kbps=3000))
        # On congestion:
        controller.on_congestion(CongestionSignal.PLI)
        # On battery low:
        controller.on_battery_low(15)
    """

    def __init__(
        self,
        *,
        ladder: list[BitrateRung] | None = None,
        initial_rung: int = 1,
        min_bitrate_kbps: int = 500,
        max_bitrate_kbps: int = 8000,
        ramp_up_interval_s: float = 5.0,
        ramp_down_interval_s: float = 1.0,
        congestion_cooldown_s: float = 10.0,
        battery_threshold_pct: int = 20,
        thermal_throttle_rung: int = 1,
        hw_encoder: bool = True,
        log_dir: Path | None = None,
    ):
        self.ladder = ladder or DEFAULT_BITRATE_LADDER
        self.min_bitrate_kbps = min_bitrate_kbps
        self.max_bitrate_kbps = max_bitrate_kbps
        self.ramp_up_interval_s = ramp_up_interval_s
        self.ramp_down_interval_s = ramp_down_interval_s
        self.congestion_cooldown_s = congestion_cooldown_s
        self.battery_threshold_pct = battery_threshold_pct
        self.thermal_throttle_rung = thermal_throttle_rung
        self.hw_encoder = hw_encoder
        self.log_dir = log_dir

        # State
        self._current_rung: int = min(initial_rung, len(self.ladder) - 1)
        self._state: ABRState = ABRState.IDLE
        self._last_ramp_up: float = 0.0
        self._last_ramp_down: float = 0.0
        self._last_congestion: float = 0.0
        self._network_estimates: list[NetworkEstimate] = []
        self._decisions: list[ABRDecision] = []
        self._throttle_reason: str = ""
        self._target_bitrate_kbps: int = self.ladder[self._current_rung].target_bitrate_kbps

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_config(cls, cfg: Any) -> ABRController:
        """Create ABRController from PipelineConfig."""
        # Build ladder from config
        target_fps = cfg.streaming_target_fps
        max_w, max_h = cfg.streaming_max_resolution.split("x")
        max_w, max_h = int(max_w), int(max_h)

        ladder = []
        for i, rung in enumerate(DEFAULT_BITRATE_LADDER):
            # Clamp to config limits
            r = BitrateRung(
                index=i,
                resolution=rung.resolution,
                width=min(rung.width, max_w),
                height=min(rung.height, max_h),
                fps=min(rung.fps, target_fps),
                min_bitrate_kbps=max(rung.min_bitrate_kbps, cfg.streaming_min_bitrate_kbps),
                max_bitrate_kbps=min(rung.max_bitrate_kbps, cfg.streaming_max_bitrate_kbps),
                target_bitrate_kbps=rung.target_bitrate_kbps,
                h264_profile=rung.h264_profile,
                h264_level=rung.h264_level,
                keyframe_interval_s=rung.keyframe_interval_s,
                gop_size=rung.fps * int(rung.keyframe_interval_s),
            )
            # Only include rungs within max resolution
            if rung.width <= max_w and rung.height <= max_h:
                ladder.append(r)

        log_dir = cfg.results_dir / "abr" if hasattr(cfg, "results_dir") else None

        return cls(
            ladder=ladder or DEFAULT_BITRATE_LADDER,
            min_bitrate_kbps=cfg.streaming_min_bitrate_kbps,
            max_bitrate_kbps=cfg.streaming_max_bitrate_kbps,
            battery_threshold_pct=cfg.streaming_battery_threshold_pct,
            log_dir=log_dir,
        )

    # --- Current settings ---

    def get_current_settings(self) -> EncoderSettings:
        """Get the current encoder settings based on ABR state."""
        rung = self.ladder[self._current_rung]

        # Clamp target bitrate
        bitrate = max(
            rung.min_bitrate_kbps,
            min(self._target_bitrate_kbps, rung.max_bitrate_kbps),
        )

        return EncoderSettings(
            bitrate_kbps=bitrate,
            resolution=rung.resolution,
            width=rung.width,
            height=rung.height,
            fps=rung.fps,
            h264_profile=rung.h264_profile,
            h264_level=rung.h264_level,
            keyframe_interval_s=rung.keyframe_interval_s,
            gop_size=rung.gop_size,
            rung_index=self._current_rung,
            hw_encoder=self.hw_encoder,
        )

    @property
    def current_rung(self) -> BitrateRung:
        return self.ladder[self._current_rung]

    @property
    def state(self) -> ABRState:
        return self._state

    # --- Network feedback ---

    def on_network_estimate(self, estimate: NetworkEstimate) -> EncoderSettings:
        """
        Process a network bandwidth estimate.  May trigger rung change.

        Returns updated encoder settings.
        """
        self._network_estimates.append(estimate)

        # Keep last 30 estimates
        if len(self._network_estimates) > 30:
            self._network_estimates = self._network_estimates[-30:]

        now = time.time()
        rung = self.ladder[self._current_rung]

        # Check for congestion cooldown
        if now - self._last_congestion < self.congestion_cooldown_s:
            return self.get_current_settings()

        available = estimate.available_kbps

        # === Ramp DOWN: available bandwidth below current min ===
        if available < rung.min_bitrate_kbps * 0.8:
            if now - self._last_ramp_down >= self.ramp_down_interval_s:
                self._ramp_down("bandwidth_low", estimate)

        # === Ramp UP: available bandwidth significantly above current max ===
        elif available > rung.max_bitrate_kbps * 1.2:
            if now - self._last_ramp_up >= self.ramp_up_interval_s:
                self._ramp_up("bandwidth_surplus", estimate)

        # === Stable: adjust target within rung ===
        else:
            # Proportionally adjust bitrate within rung bounds
            ratio = min(available / rung.max_bitrate_kbps, 1.0)
            new_target = int(
                rung.min_bitrate_kbps
                + ratio * (rung.max_bitrate_kbps - rung.min_bitrate_kbps)
            )
            self._target_bitrate_kbps = new_target
            self._state = ABRState.STABLE

        return self.get_current_settings()

    def on_congestion(self, signal: CongestionSignal) -> EncoderSettings:
        """
        React to congestion signal.  Immediately reduces quality.

        Returns updated encoder settings.
        """
        now = time.time()
        self._last_congestion = now

        if signal in (CongestionSignal.PLI, CongestionSignal.FIR):
            # Picture loss — drop one rung immediately
            self._ramp_down(f"congestion_{signal.value}")
        elif signal == CongestionSignal.NACK:
            # Packet loss — reduce bitrate within rung
            self._target_bitrate_kbps = int(self._target_bitrate_kbps * 0.8)
            self._state = ABRState.CONGESTED
            self._record_decision("nack_reduce", None)
        elif signal == CongestionSignal.PACKET_LOSS:
            self._ramp_down(f"congestion_{signal.value}")
        elif signal == CongestionSignal.RTT_SPIKE:
            # RTT spike — reduce bitrate within rung
            self._target_bitrate_kbps = int(self._target_bitrate_kbps * 0.7)
            self._state = ABRState.CONGESTED
            self._record_decision("rtt_spike_reduce", None)

        return self.get_current_settings()

    # --- Device constraints ---

    def on_battery_low(self, battery_pct: int) -> EncoderSettings:
        """
        React to low battery.  Throttle to lower rung to save power.
        """
        if battery_pct < self.battery_threshold_pct:
            self._throttle_reason = f"battery_low_{battery_pct}pct"
            max_rung = self.thermal_throttle_rung
            old_rung = self._current_rung
            if self._current_rung > max_rung:
                self._current_rung = max_rung
                self._target_bitrate_kbps = self.ladder[max_rung].target_bitrate_kbps
            # Always enter THROTTLED state when battery is low,
            # even if already at or below max_rung
            self._state = ABRState.THROTTLED
            self._record_decision(self._throttle_reason, None)
            log.warning(
                f"ABR: battery throttle {old_rung} → {self._current_rung} "
                f"(battery={battery_pct}%)"
            )
        return self.get_current_settings()

    def on_thermal_throttle(self, temperature_c: float = 0.0) -> EncoderSettings:
        """
        React to thermal throttling.  Drop to low rung.
        """
        self._throttle_reason = f"thermal_{temperature_c:.0f}C"
        max_rung = min(self.thermal_throttle_rung, len(self.ladder) - 1)
        old_rung = self._current_rung
        if self._current_rung > max_rung:
            self._current_rung = max_rung
            self._target_bitrate_kbps = self.ladder[max_rung].target_bitrate_kbps
        # Always enter THROTTLED state on thermal event
        self._state = ABRState.THROTTLED
        self._record_decision(self._throttle_reason, None)
        log.warning(f"ABR: thermal throttle {old_rung} → {self._current_rung}")
        return self.get_current_settings()

    def clear_throttle(self) -> None:
        """Clear battery/thermal throttle."""
        if self._state == ABRState.THROTTLED:
            self._state = ABRState.STABLE
            self._throttle_reason = ""
            log.info("ABR: throttle cleared")

    # --- Internal rung changes ---

    def _ramp_up(self, reason: str, estimate: NetworkEstimate | None = None) -> None:
        """Move up one rung on the bitrate ladder."""
        if self._state == ABRState.THROTTLED:
            return  # Don't ramp up during throttle

        if self._current_rung >= len(self.ladder) - 1:
            return  # Already at max

        old_rung = self._current_rung
        self._current_rung += 1
        new = self.ladder[self._current_rung]
        self._target_bitrate_kbps = new.target_bitrate_kbps
        self._last_ramp_up = time.time()
        self._state = ABRState.RAMPING_UP

        self._record_decision(reason, estimate)
        log.info(
            f"ABR: ramp UP {old_rung} → {self._current_rung} "
            f"({self.ladder[old_rung].resolution} → {new.resolution}) "
            f"reason={reason}"
        )

    def _ramp_down(self, reason: str, estimate: NetworkEstimate | None = None) -> None:
        """Move down one rung on the bitrate ladder."""
        if self._current_rung <= 0:
            # Already at lowest — just reduce bitrate
            rung = self.ladder[0]
            self._target_bitrate_kbps = max(
                rung.min_bitrate_kbps,
                int(self._target_bitrate_kbps * 0.7),
            )
            self._state = ABRState.CONGESTED
            self._record_decision(reason, estimate)
            return

        old_rung = self._current_rung
        self._current_rung -= 1
        new = self.ladder[self._current_rung]
        self._target_bitrate_kbps = new.target_bitrate_kbps
        self._last_ramp_down = time.time()
        self._state = ABRState.RAMPING_DOWN

        self._record_decision(reason, estimate)
        log.info(
            f"ABR: ramp DOWN {old_rung} → {self._current_rung} "
            f"({self.ladder[old_rung].resolution} → {new.resolution}) "
            f"reason={reason}"
        )

    def _record_decision(
        self, reason: str, estimate: NetworkEstimate | None,
    ) -> None:
        """Record ABR decision for logging."""
        decision = ABRDecision(
            reason=reason,
            previous_rung=self._current_rung,
            new_rung=self._current_rung,
            previous_bitrate_kbps=self._target_bitrate_kbps,
            new_bitrate_kbps=self._target_bitrate_kbps,
            network_estimate=estimate,
            state=self._state,
            throttle_reason=self._throttle_reason,
        )
        self._decisions.append(decision)

        if self.log_dir:
            log_file = self.log_dir / "abr_decisions.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(decision.to_dict(), ensure_ascii=False) + "\n")

    # --- Reporting ---

    def get_stats(self) -> dict[str, Any]:
        """Get ABR controller statistics."""
        return {
            "current_rung": self._current_rung,
            "current_resolution": self.ladder[self._current_rung].resolution,
            "target_bitrate_kbps": self._target_bitrate_kbps,
            "state": self._state.value,
            "throttle_reason": self._throttle_reason,
            "total_decisions": len(self._decisions),
            "ladder_size": len(self.ladder),
            "hw_encoder": self.hw_encoder,
        }

    def export_report(self) -> dict[str, Any]:
        """Export full ABR state and decision history."""
        return {
            "stats": self.get_stats(),
            "current_settings": self.get_current_settings().to_dict(),
            "ladder": [r.to_dict() for r in self.ladder],
            "recent_decisions": [
                d.to_dict() for d in self._decisions[-20:]
            ],
            "recent_estimates": [
                e.to_dict() for e in self._network_estimates[-10:]
            ],
            "config": {
                "min_bitrate_kbps": self.min_bitrate_kbps,
                "max_bitrate_kbps": self.max_bitrate_kbps,
                "ramp_up_interval_s": self.ramp_up_interval_s,
                "ramp_down_interval_s": self.ramp_down_interval_s,
                "congestion_cooldown_s": self.congestion_cooldown_s,
                "battery_threshold_pct": self.battery_threshold_pct,
            },
        }

    def export_bitrate_ladder_json(self, output_path: Path | None = None) -> dict[str, Any]:
        """
        Export bitrate ladder in stream_encoder compatible format.

        Produces bitrate_ladder.json artifact.
        """
        data = {
            "ladder": [r.to_dict() for r in self.ladder],
            "current_rung": self._current_rung,
            "hw_encoder": self.hw_encoder,
        }

        path = output_path or (self.log_dir / "bitrate_ladder.json" if self.log_dir else None)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        return data
