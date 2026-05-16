"""
SYLION Pion D — Audio Pipeline Runtime

Opus audio encoding/decoding pipeline with:
  - Configurable Opus parameters (bitrate, sample rate, channels, DTX)
  - Echo cancellation state machine
  - A/V sync tracking (drift detection + correction)
  - Jitter buffer simulation
  - Audio level metering (RMS + peak)
"""

import logging
import math
import struct
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("audio_pipeline")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_SAMPLE_RATE = 48000
DEFAULT_CHANNELS = 1  # Mono for voice
DEFAULT_BITRATE_BPS = 32000  # 32 kbps — good for voice
DEFAULT_FRAME_DURATION_MS = 20  # Opus standard frame
MAX_JITTER_BUFFER_MS = 200
DEFAULT_DTX_THRESHOLD_DB = -50.0  # Discontinuous transmission threshold


class AudioCodec(str, Enum):
    OPUS = "opus"
    AAC = "aac"   # Fallback


class EchoCancelState(str, Enum):
    IDLE = "idle"
    CAPTURING = "capturing"        # Recording near-end audio
    REFERENCE_PLAYING = "playing"  # Far-end audio playing through speaker
    CANCELLING = "cancelling"      # AEC active
    CONVERGING = "converging"      # AEC filter adapting


class AVSyncState(str, Enum):
    IN_SYNC = "in_sync"
    DRIFTING = "drifting"
    CORRECTING = "correcting"
    LOST = "lost"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OpusConfig:
    """Opus encoder configuration."""
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    bitrate_bps: int = DEFAULT_BITRATE_BPS
    frame_duration_ms: int = DEFAULT_FRAME_DURATION_MS
    dtx_enabled: bool = True         # Discontinuous transmission
    fec_enabled: bool = True         # Forward error correction
    cbr: bool = False                # Constant bitrate (False = VBR)
    application: str = "voip"        # "voip", "audio", or "lowdelay"
    complexity: int = 5              # 0-10, higher = better quality, more CPU
    max_bandwidth: str = "fullband"  # "narrowband", "mediumband", "wideband", "superwideband", "fullband"

    @property
    def frame_size_samples(self) -> int:
        return int(self.sample_rate * self.frame_duration_ms / 1000)

    def to_dict(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bitrate_bps": self.bitrate_bps,
            "frame_duration_ms": self.frame_duration_ms,
            "frame_size_samples": self.frame_size_samples,
            "dtx_enabled": self.dtx_enabled,
            "fec_enabled": self.fec_enabled,
            "cbr": self.cbr,
            "application": self.application,
            "complexity": self.complexity,
            "max_bandwidth": self.max_bandwidth,
        }


@dataclass
class AudioFrame:
    """A single audio frame (PCM or encoded)."""
    timestamp_ms: int
    duration_ms: int
    sequence: int
    data: bytes
    is_encoded: bool = False
    is_silence: bool = False   # DTX: silent frame
    rms_db: float = -100.0    # RMS level in dB
    peak_db: float = -100.0   # Peak level in dB


@dataclass
class AVSyncSample:
    """A single A/V sync measurement."""
    audio_pts_ms: int
    video_pts_ms: int
    drift_ms: float
    timestamp: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Jitter Buffer
# ---------------------------------------------------------------------------

class JitterBuffer:
    """Adaptive jitter buffer for audio frames.

    Smooths out network jitter by buffering frames and releasing
    them at a steady rate.
    """

    def __init__(self, target_ms: int = 40, max_ms: int = MAX_JITTER_BUFFER_MS):
        self.target_ms = target_ms
        self.max_ms = max_ms
        self._buffer: deque[AudioFrame] = deque()
        self._next_expected_seq: int = 0
        self._stats = {
            "frames_in": 0,
            "frames_out": 0,
            "frames_dropped": 0,
            "frames_late": 0,
            "frames_early": 0,
            "underruns": 0,
            "overruns": 0,
        }

    def push(self, frame: AudioFrame) -> None:
        """Add a frame to the buffer."""
        self._stats["frames_in"] += 1

        # Drop if buffer is full
        if len(self._buffer) * frame.duration_ms > self.max_ms:
            self._buffer.popleft()
            self._stats["overruns"] += 1
            self._stats["frames_dropped"] += 1

        # Insert in sequence order
        inserted = False
        for i in range(len(self._buffer) - 1, -1, -1):
            if self._buffer[i].sequence < frame.sequence:
                self._buffer.insert(i + 1, frame)
                inserted = True
                break
        if not inserted:
            self._buffer.appendleft(frame)

        # Track late/early
        if frame.sequence < self._next_expected_seq:
            self._stats["frames_late"] += 1

    def pop(self) -> AudioFrame | None:
        """Get the next frame for playout. Returns None on underrun."""
        if not self._buffer:
            self._stats["underruns"] += 1
            return None

        frame = self._buffer.popleft()
        self._next_expected_seq = frame.sequence + 1
        self._stats["frames_out"] += 1
        return frame

    @property
    def depth_ms(self) -> int:
        """Current buffer depth in milliseconds."""
        if not self._buffer:
            return 0
        return len(self._buffer) * (self._buffer[0].duration_ms if self._buffer else 20)

    @property
    def depth_frames(self) -> int:
        return len(self._buffer)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "depth_ms": self.depth_ms,
            "depth_frames": self.depth_frames,
            "target_ms": self.target_ms,
            "max_ms": self.max_ms,
        }


# ---------------------------------------------------------------------------
# Echo Cancellation State Machine
# ---------------------------------------------------------------------------

class EchoCanceller:
    """Echo cancellation state tracker.

    Real AEC is done by the platform (WebRTC's built-in AEC3 or device DSP).
    This module tracks state and provides telemetry.
    """

    def __init__(self):
        self._state = EchoCancelState.IDLE
        self._state_history: list[tuple[float, EchoCancelState]] = []
        self._convergence_start: float | None = None
        self._echo_return_loss_db: float = 0.0  # ERLE metric
        self._stats = {
            "state_changes": 0,
            "total_cancelling_ms": 0.0,
            "echo_events": 0,
        }

    @property
    def state(self) -> EchoCancelState:
        return self._state

    def on_capture_start(self) -> None:
        """Near-end microphone started capturing."""
        self._transition(EchoCancelState.CAPTURING)

    def on_reference_start(self) -> None:
        """Far-end audio started playing (speaker output)."""
        self._transition(EchoCancelState.REFERENCE_PLAYING)

    def on_aec_active(self) -> None:
        """AEC is actively cancelling echo."""
        self._transition(EchoCancelState.CANCELLING)
        self._convergence_start = time.monotonic()

    def on_aec_converged(self, erle_db: float = 0.0) -> None:
        """AEC filter has converged."""
        self._echo_return_loss_db = erle_db
        self._transition(EchoCancelState.CONVERGING)
        if self._convergence_start:
            elapsed = (time.monotonic() - self._convergence_start) * 1000
            self._stats["total_cancelling_ms"] += elapsed

    def on_echo_detected(self) -> None:
        """Echo detected in captured audio."""
        self._stats["echo_events"] += 1
        if self._state != EchoCancelState.CANCELLING:
            self.on_aec_active()

    def on_stop(self) -> None:
        """Audio pipeline stopped."""
        self._transition(EchoCancelState.IDLE)

    def _transition(self, new_state: EchoCancelState) -> None:
        if new_state != self._state:
            self._state_history.append((time.monotonic(), new_state))
            self._stats["state_changes"] += 1
            log.debug("EchoCanceller: %s → %s", self._state.value, new_state.value)
            self._state = new_state

    def get_stats(self) -> dict:
        return {
            "state": self._state.value,
            "erle_db": round(self._echo_return_loss_db, 1),
            **self._stats,
            "history_len": len(self._state_history),
        }


# ---------------------------------------------------------------------------
# A/V Sync Tracker
# ---------------------------------------------------------------------------

class AVSyncTracker:
    """Track audio/video synchronization drift.

    Monitors PTS difference between audio and video streams.
    Triggers correction when drift exceeds threshold.
    """

    def __init__(self, max_drift_ms: float = 50.0, correction_step_ms: float = 5.0):
        self.max_drift_ms = max_drift_ms
        self.correction_step_ms = correction_step_ms
        self._state = AVSyncState.IN_SYNC
        self._samples: deque[AVSyncSample] = deque(maxlen=100)
        self._corrections_applied: int = 0
        self._total_correction_ms: float = 0.0

    @property
    def state(self) -> AVSyncState:
        return self._state

    def record_sample(self, audio_pts_ms: int, video_pts_ms: int) -> AVSyncSample:
        """Record an A/V sync measurement and update state."""
        drift = float(audio_pts_ms - video_pts_ms)
        sample = AVSyncSample(
            audio_pts_ms=audio_pts_ms,
            video_pts_ms=video_pts_ms,
            drift_ms=drift,
        )
        self._samples.append(sample)

        # Update state based on drift
        abs_drift = abs(drift)
        if abs_drift <= self.max_drift_ms:
            if self._state == AVSyncState.CORRECTING:
                self._state = AVSyncState.IN_SYNC
                log.info("AVSync: correction complete, back in sync (drift=%.1fms)", drift)
            elif self._state != AVSyncState.IN_SYNC:
                self._state = AVSyncState.IN_SYNC
        elif abs_drift <= self.max_drift_ms * 3:
            if self._state != AVSyncState.CORRECTING:
                self._state = AVSyncState.DRIFTING
                log.warning("AVSync: drifting (%.1fms, threshold=%.1fms)", drift, self.max_drift_ms)
        else:
            self._state = AVSyncState.LOST
            log.error("AVSync: LOST (drift=%.1fms)", drift)

        return sample

    def get_correction_ms(self) -> float:
        """Get recommended correction in milliseconds.

        Positive = audio is ahead (delay audio or advance video).
        Negative = audio is behind (advance audio or delay video).
        Returns 0.0 if in sync.
        """
        if not self._samples:
            return 0.0

        avg_drift = sum(s.drift_ms for s in self._samples) / len(self._samples)
        if abs(avg_drift) <= self.max_drift_ms:
            return 0.0

        correction = -avg_drift  # Negate: if audio ahead, we delay it
        # Clamp to step size for smooth correction
        if abs(correction) > self.correction_step_ms:
            correction = self.correction_step_ms if correction > 0 else -self.correction_step_ms

        self._corrections_applied += 1
        self._total_correction_ms += abs(correction)
        self._state = AVSyncState.CORRECTING

        return correction

    @property
    def current_drift_ms(self) -> float:
        if not self._samples:
            return 0.0
        return self._samples[-1].drift_ms

    @property
    def avg_drift_ms(self) -> float:
        if not self._samples:
            return 0.0
        return sum(s.drift_ms for s in self._samples) / len(self._samples)

    def get_stats(self) -> dict:
        return {
            "state": self._state.value,
            "current_drift_ms": round(self.current_drift_ms, 2),
            "avg_drift_ms": round(self.avg_drift_ms, 2),
            "max_drift_threshold_ms": self.max_drift_ms,
            "corrections_applied": self._corrections_applied,
            "total_correction_ms": round(self._total_correction_ms, 2),
            "samples": len(self._samples),
        }


# ---------------------------------------------------------------------------
# Audio Level Meter
# ---------------------------------------------------------------------------

class AudioLevelMeter:
    """Compute RMS and peak levels from PCM audio data."""

    @staticmethod
    def compute_levels(pcm_data: bytes, sample_width: int = 2) -> tuple[float, float]:
        """Compute RMS and peak levels in dB from PCM data.

        Args:
            pcm_data: Raw PCM audio bytes (16-bit signed LE).
            sample_width: Bytes per sample (2 for 16-bit).

        Returns:
            (rms_db, peak_db) tuple.
        """
        if not pcm_data or len(pcm_data) < sample_width:
            return (-100.0, -100.0)

        num_samples = len(pcm_data) // sample_width
        if num_samples == 0:
            return (-100.0, -100.0)

        # Unpack 16-bit signed samples
        samples = struct.unpack(f"<{num_samples}h", pcm_data[:num_samples * sample_width])

        # Peak
        peak = max(abs(s) for s in samples)
        peak_db = 20 * math.log10(peak / 32768.0) if peak > 0 else -100.0

        # RMS
        sum_sq = sum(s * s for s in samples)
        rms = math.sqrt(sum_sq / num_samples)
        rms_db = 20 * math.log10(rms / 32768.0) if rms > 0 else -100.0

        return (round(rms_db, 1), round(peak_db, 1))

    @staticmethod
    def is_silence(rms_db: float, threshold_db: float = DEFAULT_DTX_THRESHOLD_DB) -> bool:
        """Check if audio level qualifies as silence for DTX."""
        return rms_db <= threshold_db


# ---------------------------------------------------------------------------
# Audio Pipeline Controller
# ---------------------------------------------------------------------------

class AudioPipelineController:
    """Top-level audio pipeline controller.

    Manages Opus config, jitter buffer, echo cancellation,
    A/V sync, and level metering.
    """

    def __init__(
        self,
        opus_config: OpusConfig | None = None,
        jitter_target_ms: int = 40,
        max_drift_ms: float = 50.0,
    ):
        self.opus = opus_config or OpusConfig()
        self.jitter_buffer = JitterBuffer(target_ms=jitter_target_ms)
        self.echo_canceller = EchoCanceller()
        self.av_sync = AVSyncTracker(max_drift_ms=max_drift_ms)
        self.level_meter = AudioLevelMeter()

        self._send_seq: int = 0
        self._frames_encoded: int = 0
        self._frames_decoded: int = 0
        self._dtx_frames: int = 0
        self._total_encode_ms: float = 0.0
        self._active: bool = False

    def start(self) -> None:
        """Start the audio pipeline."""
        self._active = True
        self.echo_canceller.on_capture_start()
        log.info(
            "AudioPipeline: started (rate=%dHz, channels=%d, bitrate=%dkbps, dtx=%s, fec=%s)",
            self.opus.sample_rate, self.opus.channels,
            self.opus.bitrate_bps // 1000,
            self.opus.dtx_enabled, self.opus.fec_enabled,
        )

    def stop(self) -> None:
        """Stop the audio pipeline."""
        self._active = False
        self.echo_canceller.on_stop()
        log.info("AudioPipeline: stopped")

    def encode_frame(self, pcm_data: bytes) -> AudioFrame:
        """Encode a PCM audio frame (simulation — real encoding needs libopus).

        In production, this would call libopus via ctypes/cffi.
        Here we simulate the pipeline for testing.
        """
        t0 = time.monotonic()
        self._send_seq += 1

        rms_db, peak_db = self.level_meter.compute_levels(pcm_data)
        is_dtx_silence = self.opus.dtx_enabled and AudioLevelMeter.is_silence(rms_db)

        if is_dtx_silence:
            self._dtx_frames += 1
            # DTX: send a minimal comfort noise frame
            encoded_data = b"\x00" * 2  # Minimal frame
        else:
            # Simulate Opus encoding (in production: opus_encode())
            # Compress to ~bitrate equivalent
            target_bytes = int(self.opus.bitrate_bps * self.opus.frame_duration_ms / 8000)
            encoded_data = pcm_data[:target_bytes] if len(pcm_data) > target_bytes else pcm_data

        frame = AudioFrame(
            timestamp_ms=int(time.monotonic() * 1000),
            duration_ms=self.opus.frame_duration_ms,
            sequence=self._send_seq,
            data=encoded_data,
            is_encoded=True,
            is_silence=is_dtx_silence,
            rms_db=rms_db,
            peak_db=peak_db,
        )

        elapsed = (time.monotonic() - t0) * 1000
        self._total_encode_ms += elapsed
        self._frames_encoded += 1

        return frame

    def receive_frame(self, frame: AudioFrame) -> AudioFrame | None:
        """Receive an encoded frame from network, buffer it, return next playout frame."""
        self.jitter_buffer.push(frame)
        self._frames_decoded += 1
        return self.jitter_buffer.pop()

    def record_av_sync(self, audio_pts_ms: int, video_pts_ms: int) -> float:
        """Record A/V sync sample and return recommended correction."""
        self.av_sync.record_sample(audio_pts_ms, video_pts_ms)
        return self.av_sync.get_correction_ms()

    def get_stats(self) -> dict:
        avg_encode = (
            self._total_encode_ms / self._frames_encoded
            if self._frames_encoded > 0 else 0.0
        )
        return {
            "active": self._active,
            # Top-level convenience keys (used by E2ESessionController.phase_audio)
            "codec": AudioCodec.OPUS.value,
            "sample_rate": self.opus.sample_rate,
            # Full nested config for detailed inspection
            "opus_config": self.opus.to_dict(),
            "frames_encoded": self._frames_encoded,
            "frames_decoded": self._frames_decoded,
            "dtx_frames": self._dtx_frames,
            "avg_encode_ms": round(avg_encode, 3),
            "jitter_buffer": self.jitter_buffer.get_stats(),
            "echo_canceller": self.echo_canceller.get_stats(),
            "av_sync": self.av_sync.get_stats(),
        }

    def export_report(self) -> dict:
        return {
            "stats": self.get_stats(),
            "codec": AudioCodec.OPUS.value,
        }
