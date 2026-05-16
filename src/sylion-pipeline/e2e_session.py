#!/usr/bin/env python3
"""
SYLION E2E Session Controller — wires all 8 runtime modules into a working
streaming session lifecycle.

Flow:
  1. Security pre-check (stream_security)
  2. Signaling: create room, exchange SDP/ICE
  3. Device: health-check target, verify readiness
  4. Audio: init pipeline, configure Opus, start AEC
  5. Input: init protocol codec, HMAC, replay guard
  6. ABR: set initial rung from network estimate
  7. Metrics: start collecting, wire alert engine
  8. Benchmark: optional — run full suite after session warm-up

This module does NOT run any shell commands.  It orchestrates the library
objects that are already initialized in the orchestrator global scope.

LLM NIGDY nie wydaje raw shell.  Only pre-approved scenarios.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("sylion.e2e_session")


# ---------------------------------------------------------------------------
# Session States
# ---------------------------------------------------------------------------

class SessionState(str, Enum):
    IDLE = "idle"
    SECURITY_CHECK = "security_check"
    SIGNALING = "signaling"
    DEVICE_PREP = "device_prep"
    AUDIO_INIT = "audio_init"
    INPUT_INIT = "input_init"
    ABR_INIT = "abr_init"
    METRICS_START = "metrics_start"
    STREAMING = "streaming"
    RECONNECTING = "reconnecting"
    BENCHMARK = "benchmark"
    ENDED = "ended"
    FAILED = "failed"


@dataclass
class SessionEvent:
    """Immutable event in session lifecycle."""
    timestamp: float
    state: str
    module: str
    detail: str
    ok: bool = True


@dataclass
class E2ESessionReport:
    """Full E2E session report — serializable to JSON."""
    session_id: str
    started_at: float = 0.0
    ended_at: float = 0.0
    final_state: str = "idle"
    events: list[dict] = field(default_factory=list)
    security_audit: dict = field(default_factory=dict)
    signaling: dict = field(default_factory=dict)
    device: dict = field(default_factory=dict)
    audio: dict = field(default_factory=dict)
    input_protocol: dict = field(default_factory=dict)
    abr: dict = field(default_factory=dict)
    metrics_snapshot: dict = field(default_factory=dict)
    benchmark: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, default=str))


# ---------------------------------------------------------------------------
# E2E Session Controller
# ---------------------------------------------------------------------------

class E2ESessionController:
    """
    Orchestrates a full streaming session across all runtime modules.

    Each module is optional (can be None) — the controller will skip
    unavailable modules and log warnings, allowing partial E2E runs.
    """

    def __init__(
        self,
        *,
        signaling_srv=None,      # SignalingServer
        device_harness=None,     # DeviceHarness
        metrics_collector=None,  # MetricsCollector
        abr_controller=None,     # ABRController
        input_protocol=None,     # InputProtocolCodec
        audio_pipeline=None,     # AudioPipelineController
        stream_security=None,    # StreamSecurityVerifier
        benchmark_harness=None,  # BenchmarkHarness
        session_id: str | None = None,
        on_event: Callable[[SessionEvent], None] | None = None,
    ):
        self.signaling = signaling_srv
        self.device = device_harness
        self.metrics = metrics_collector
        self.abr = abr_controller
        self.input = input_protocol
        self.audio = audio_pipeline
        self.security = stream_security
        self.benchmark = benchmark_harness

        self.session_id = session_id or f"e2e-{uuid.uuid4().hex[:8]}"
        self._state = SessionState.IDLE
        self._events: list[SessionEvent] = []
        self._report = E2ESessionReport(session_id=self.session_id)
        self._on_event = on_event

        # Signaling room tracking
        self._room_id: str | None = None
        self._initiator_id: str | None = None
        self._peer_id: str | None = None

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def report(self) -> E2ESessionReport:
        return self._report

    # -- helpers --

    def _transition(self, new_state: SessionState) -> None:
        old = self._state
        self._state = new_state
        log.debug("  Session %s: %s → %s", self.session_id, old.value, new_state.value)

    def _emit(self, module: str, detail: str, ok: bool = True) -> None:
        evt = SessionEvent(
            timestamp=time.time(),
            state=self._state.value,
            module=module,
            detail=detail,
            ok=ok,
        )
        self._events.append(evt)
        if self._on_event:
            self._on_event(evt)

    # -----------------------------------------------------------------------
    # Phase 1: Security Pre-Check
    # -----------------------------------------------------------------------

    def phase_security(self) -> bool:
        """Run stream_security full audit before session start."""
        self._transition(SessionState.SECURITY_CHECK)
        if not self.security:
            self._emit("stream_security", "SKIP — not initialized", ok=True)
            return True

        try:
            # Register session for rate limiting
            self.security.register_session(self.session_id)

            # Run full security audit
            audit = self.security.run_full_audit(session_id=self.session_id)
            self._report.security_audit = audit.to_dict() if hasattr(audit, "to_dict") else {}

            overall = audit.overall_level if hasattr(audit, "overall_level") else "UNKNOWN"
            self._emit("stream_security", f"Audit complete: level={overall}")

            # Block on INSECURE security level
            if hasattr(audit, "overall_level"):
                from stream_security import SecurityLevel
                if audit.overall_level == SecurityLevel.INSECURE:
                    self._emit("stream_security", "BLOCKED — INSECURE security level", ok=False)
                    return False

            log.info("  ✓ Security pre-check: %s", overall)
            return True

        except Exception as e:
            self._emit("stream_security", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"security: {e}")
            log.error("  ✗ Security pre-check failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 2: Signaling — Room + SDP/ICE
    # -----------------------------------------------------------------------

    def phase_signaling(
        self,
        initiator_id: str = "pixel",
        peer_id: str = "laptop",
    ) -> bool:
        """Create signaling room and simulate SDP/ICE exchange."""
        self._transition(SessionState.SIGNALING)
        self._initiator_id = initiator_id
        self._peer_id = peer_id

        if not self.signaling:
            self._emit("signaling", "SKIP — not initialized", ok=True)
            return True

        try:
            # Create room (returns (Room, token) tuple)
            room, init_token = self.signaling.create_room(
                initiator_id=initiator_id,
            )
            self._room_id = room.room_id
            self._emit("signaling", f"Room created: {self._room_id}")

            # Peer joins
            join_result = self.signaling.join_room(self._room_id, peer_id)
            self._emit("signaling", f"Peer joined: {peer_id} → {join_result}")

            # SDP Offer from initiator
            from signaling_server import SDPMessage, SDPType, ICECandidate
            offer = SDPMessage(
                sdp_type=SDPType.OFFER,
                sdp=f"v=0\no=- {self.session_id} 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\na=rtpmap:96 H264/90000\nm=audio 9 UDP/TLS/RTP/SAVPF 111\na=rtpmap:111 opus/48000/2",
            )
            self.signaling.relay_sdp(self._room_id, initiator_id, offer)
            self._emit("signaling", "SDP offer relayed (H264+Opus)")

            # SDP Answer from peer
            answer = SDPMessage(
                sdp_type=SDPType.ANSWER,
                sdp=f"v=0\no=- {self.session_id} 2 IN IP4 127.0.0.1\ns=-\nt=0 0\nm=video 9 UDP/TLS/RTP/SAVPF 96\na=rtpmap:96 H264/90000\nm=audio 9 UDP/TLS/RTP/SAVPF 111\na=rtpmap:111 opus/48000/2",
            )
            self.signaling.relay_sdp(self._room_id, peer_id, answer)
            self._emit("signaling", "SDP answer relayed")

            # ICE candidates
            for candidate_peer, candidate_info in [
                (initiator_id, "host 192.168.8.10 udp 9000"),
                (peer_id, "host 192.168.8.1 udp 9000"),
            ]:
                ice = ICECandidate(
                    candidate=f"candidate:1 1 udp 2113937151 {candidate_info}",
                    sdp_mid="0",
                    sdp_mline_index=0,
                )
                self.signaling.relay_ice(self._room_id, candidate_peer, ice)

            self.signaling.end_of_candidates(self._room_id, initiator_id)
            self.signaling.end_of_candidates(self._room_id, peer_id)
            self._emit("signaling", "ICE candidates exchanged, end-of-candidates sent")

            # Mark connected
            self.signaling.on_connected(self._room_id, initiator_id)
            self.signaling.on_connected(self._room_id, peer_id)
            self._emit("signaling", "Both peers CONNECTED")

            self._report.signaling = {
                "room_id": self._room_id,
                "initiator": initiator_id,
                "peer": peer_id,
                "state": self.signaling.get_room_state(self._room_id),
            }

            log.info("  ✓ Signaling: room=%s, both connected", self._room_id)
            return True

        except Exception as e:
            self._emit("signaling", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"signaling: {e}")
            log.error("  ✗ Signaling failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 3: Device Readiness
    # -----------------------------------------------------------------------

    def phase_device(self) -> bool:
        """Health-check all target devices."""
        self._transition(SessionState.DEVICE_PREP)
        if not self.device:
            self._emit("device_harness", "SKIP — not initialized", ok=True)
            return True

        try:
            health = self.device.health_check_all()
            device_report = {}
            all_ok = True
            for name, status in health.items():
                state_str = status.state.value if hasattr(status, "state") else str(status)
                device_report[name] = state_str
                if state_str not in ("ready", "idle", "ok"):
                    all_ok = False

            self._report.device = {"devices": device_report, "all_ok": all_ok}
            self._emit("device_harness", f"Health check: {device_report}")
            log.info("  ✓ Device health: %s (all_ok=%s)", device_report, all_ok)
            return True  # Allow even if not all ready (dry_run case)

        except Exception as e:
            self._emit("device_harness", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"device: {e}")
            log.error("  ✗ Device health check failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 4: Audio Pipeline Init
    # -----------------------------------------------------------------------

    def phase_audio(self) -> bool:
        """Initialize audio pipeline — Opus codec, echo cancellation, jitter buffer."""
        self._transition(SessionState.AUDIO_INIT)
        if not self.audio:
            self._emit("audio_pipeline", "SKIP — not initialized", ok=True)
            return True

        try:
            stats = self.audio.get_stats()
            self._report.audio = stats
            self._emit("audio_pipeline", f"Ready: codec={stats.get('codec')}, rate={stats.get('sample_rate')}")
            log.info("  ✓ Audio: codec=%s, rate=%s", stats.get("codec"), stats.get("sample_rate"))
            return True

        except Exception as e:
            self._emit("audio_pipeline", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"audio: {e}")
            log.error("  ✗ Audio init failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 5: Input Protocol Init
    # -----------------------------------------------------------------------

    def phase_input(self) -> bool:
        """Initialize input protocol — HMAC, replay guard, codec."""
        self._transition(SessionState.INPUT_INIT)
        if not self.input:
            self._emit("input_protocol", "SKIP — not initialized", ok=True)
            return True

        try:
            stats = self.input.get_stats()
            self._report.input_protocol = stats
            self._emit("input_protocol",
                        f"Ready: v{stats.get('protocol_version')}, hmac={stats.get('hmac_enabled')}")

            # Send a ping to verify protocol is working
            ping_bytes = self.input.encode_ping()
            self._emit("input_protocol", f"Ping encoded: {len(ping_bytes)} bytes")

            log.info("  ✓ Input protocol: v%s, hmac=%s",
                     stats.get("protocol_version"), stats.get("hmac_enabled"))
            return True

        except Exception as e:
            self._emit("input_protocol", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"input: {e}")
            log.error("  ✗ Input protocol init failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 6: ABR Init
    # -----------------------------------------------------------------------

    def phase_abr(self) -> bool:
        """Set initial ABR rung and verify controller state."""
        self._transition(SessionState.ABR_INIT)
        if not self.abr:
            self._emit("abr_controller", "SKIP — not initialized", ok=True)
            return True

        try:
            settings = self.abr.get_current_settings()
            stats = self.abr.get_stats()
            self._report.abr = {
                "initial_rung": stats.get("current_rung"),
                "resolution": settings.resolution,
                "bitrate_kbps": settings.bitrate_kbps,
                "fps": settings.fps,
                "state": stats.get("state"),
            }
            self._emit("abr_controller",
                        f"Ready: rung={stats.get('current_rung')}, "
                        f"{settings.resolution}@{settings.fps}fps, "
                        f"{settings.bitrate_kbps}kbps")
            log.info("  ✓ ABR: rung=%s, %s @ %d kbps",
                     stats.get("current_rung"), settings.resolution, settings.bitrate_kbps)
            return True

        except Exception as e:
            self._emit("abr_controller", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"abr: {e}")
            log.error("  ✗ ABR init failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Phase 7: Metrics Start
    # -----------------------------------------------------------------------

    def phase_metrics(self) -> bool:
        """Start metrics collection — verify ingestion and alert thresholds."""
        self._transition(SessionState.METRICS_START)
        if not self.metrics:
            self._emit("metrics_ingestion", "SKIP — not initialized", ok=True)
            return True

        try:
            dashboard = self.metrics.get_dashboard()
            self._report.metrics_snapshot = dashboard
            self._emit("metrics_ingestion", f"Ready: {dashboard.get('store_stats', {})}")
            log.info("  ✓ Metrics: store ready, alerts configured")
            return True

        except Exception as e:
            self._emit("metrics_ingestion", f"ERROR: {e}", ok=False)
            self._report.errors.append(f"metrics: {e}")
            log.error("  ✗ Metrics init failed: %s", e)
            return False

    # -----------------------------------------------------------------------
    # Full E2E Flow
    # -----------------------------------------------------------------------

    def run_e2e(
        self,
        initiator_id: str = "pixel",
        peer_id: str = "laptop",
        run_benchmark: bool = False,
        benchmark_kwargs: dict | None = None,
    ) -> E2ESessionReport:
        """
        Run complete E2E session lifecycle.

        Returns E2ESessionReport with all phase results.
        Raises no exceptions — all errors are captured in the report.
        """
        self._report.started_at = time.time()
        log.info("╔══════════════════════════════════════════════════╗")
        log.info("║  E2E SESSION: %s               ║", self.session_id[:20].ljust(20))
        log.info("╚══════════════════════════════════════════════════╝")

        phases = [
            ("security",   lambda: self.phase_security()),
            ("signaling",  lambda: self.phase_signaling(initiator_id, peer_id)),
            ("device",     lambda: self.phase_device()),
            ("audio",      lambda: self.phase_audio()),
            ("input",      lambda: self.phase_input()),
            ("abr",        lambda: self.phase_abr()),
            ("metrics",    lambda: self.phase_metrics()),
        ]

        for name, phase_fn in phases:
            try:
                ok = phase_fn()
                if not ok:
                    log.warning("  ⚠ Phase '%s' returned False — session degraded", name)
            except Exception as e:
                log.error("  ✗ Phase '%s' crashed: %s", name, e)
                self._report.errors.append(f"{name}: {e}")

        # Enter STREAMING state
        self._transition(SessionState.STREAMING)
        self._emit("e2e", "All phases complete — session is STREAMING")
        log.info("  ▶ Session %s is now STREAMING", self.session_id)

        # Optional: run benchmarks
        if run_benchmark and self.benchmark:
            self._transition(SessionState.BENCHMARK)
            try:
                bk = benchmark_kwargs or {}
                suite_report = self.benchmark.run_all(
                    run_id=f"e2e-{self.session_id}",
                    **bk,
                )
                self._report.benchmark = {
                    "run_id": suite_report.run_id,
                    "overall_status": suite_report.overall_status.value
                    if hasattr(suite_report.overall_status, "value")
                    else str(suite_report.overall_status),
                    "results": [
                        {
                            "name": r.name,
                            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                            "p50": r.p50,
                            "p95": r.p95,
                            "p99": r.p99,
                            "mean": r.mean,
                            "message": r.message,
                        }
                        for r in suite_report.results
                    ],
                    "duration_s": suite_report.duration_s,
                }
                self._emit("benchmark", f"Suite done: {suite_report.overall_status}")
                log.info("  ✓ Benchmark: %s (%d results)",
                         suite_report.overall_status, len(suite_report.results))
            except Exception as e:
                self._emit("benchmark", f"ERROR: {e}", ok=False)
                self._report.errors.append(f"benchmark: {e}")
                log.error("  ✗ Benchmark failed: %s", e)

        # End session
        self._transition(SessionState.ENDED)
        self._report.ended_at = time.time()
        self._report.final_state = self._state.value
        self._report.events = [
            {
                "timestamp": e.timestamp,
                "state": e.state,
                "module": e.module,
                "detail": e.detail,
                "ok": e.ok,
            }
            for e in self._events
        ]

        duration = self._report.ended_at - self._report.started_at
        error_count = len(self._report.errors)
        log.info("  ═══ E2E Session %s ENDED (%.1fs, %d errors) ═══",
                 self.session_id, duration, error_count)

        return self._report

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    def cleanup(self) -> None:
        """Cleanup session resources — close signaling room, unregister security."""
        if self.signaling and self._room_id:
            try:
                self.signaling.close_room(self._room_id)
                log.debug("  Closed room %s", self._room_id)
            except Exception:
                pass

        if self.security:
            try:
                self.security.unregister_session(self.session_id)
            except Exception:
                pass

        self._transition(SessionState.ENDED)
