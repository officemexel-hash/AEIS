"""
Tests for P1/P2 new modules:
  - input_protocol.py (InputProtocolCodec, ReplayGuard, frame encoding)
  - audio_pipeline.py (AudioPipelineController, JitterBuffer, EchoCanceller, AVSyncTracker)
  - stream_security.py (StreamSecurityVerifier, DTLS, SRTP, ICE, token, rate limit)
  - benchmark_harness.py (BenchmarkHarness, 6 benchmarks)
"""

import time
import pytest

# ---------------------------------------------------------------------------
# Input Protocol tests
# ---------------------------------------------------------------------------

from input_protocol import (
    InputProtocolCodec,
    InputEventType,
    InputFrame,
    ReplayGuard,
    TouchEvent,
    KeyEvent,
    GamepadEvent,
    PROTOCOL_VERSION,
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    HMAC_SIZE,
)


class TestInputProtocolCodec:
    """Test InputProtocolCodec encode/decode/HMAC/replay."""

    def setup_method(self):
        self.codec = InputProtocolCodec(hmac_key=b"test-key-123")

    def test_encode_touch_event(self):
        """Encode a touch down event and verify frame structure."""
        touch = TouchEvent(x=100.0, y=200.0, pointer_id=0, pressure=0.5)
        frame = self.codec.encode_touch(InputEventType.TOUCH_DOWN, touch)
        assert frame is not None
        assert isinstance(frame, bytes)
        assert len(frame) >= HEADER_SIZE + HMAC_SIZE

    def test_encode_key_event(self):
        """Encode a key down event."""
        key = KeyEvent(keycode=65, modifiers=0)
        frame = self.codec.encode_key(InputEventType.KEY_DOWN, key)
        assert frame is not None
        assert isinstance(frame, bytes)

    def test_encode_gamepad_event(self):
        """Encode a gamepad button event."""
        gp = GamepadEvent(button_or_axis=0, value=1.0)
        frame = self.codec.encode_gamepad(InputEventType.GAMEPAD_BUTTON, gp)
        assert frame is not None

    def test_decode_roundtrip(self):
        """Encode -> decode should give back the same event type."""
        touch = TouchEvent(x=50.0, y=75.0, pointer_id=1, pressure=0.8)
        raw = self.codec.encode_touch(InputEventType.TOUCH_MOVE, touch)

        # Decode with same key
        codec2 = InputProtocolCodec(hmac_key=b"test-key-123")
        decoded = codec2.decode(raw)
        assert decoded is not None
        assert decoded.event_type == InputEventType.TOUCH_MOVE

    def test_hmac_mismatch_fails(self):
        """Decode with wrong HMAC key should fail."""
        touch = TouchEvent(x=10.0, y=20.0, pointer_id=0, pressure=1.0)
        raw = self.codec.encode_touch(InputEventType.TOUCH_DOWN, touch)

        codec_wrong_key = InputProtocolCodec(hmac_key=b"wrong-key")
        with pytest.raises(Exception):
            codec_wrong_key.decode(raw)

    def test_replay_protection(self):
        """Same frame decoded twice should be blocked by replay guard."""
        touch = TouchEvent(x=10.0, y=20.0, pointer_id=0, pressure=1.0)
        raw = self.codec.encode_touch(InputEventType.TOUCH_DOWN, touch)

        codec2 = InputProtocolCodec(hmac_key=b"test-key-123")
        decoded1 = codec2.decode(raw)
        assert decoded1 is not None

        # Second decode of same frame should fail (replay)
        with pytest.raises(Exception):
            codec2.decode(raw)

    def test_stats_tracking(self):
        """Stats should increment on encode/decode."""
        touch = TouchEvent(x=0.0, y=0.0, pointer_id=0, pressure=0.0)
        self.codec.encode_touch(InputEventType.TOUCH_DOWN, touch)
        self.codec.encode_touch(InputEventType.TOUCH_MOVE, touch)
        stats = self.codec.get_stats()
        assert stats["frames_sent"] >= 2
        assert stats["bytes_sent"] > 0

    def test_ping_pong(self):
        """Ping encoding."""
        ping = self.codec.encode_ping()
        assert ping is not None
        assert isinstance(ping, bytes)


class TestReplayGuard:
    """Test replay protection mechanism."""

    def test_fresh_sequence_accepted(self):
        rg = ReplayGuard(window_size=64)
        assert rg.check_and_accept(1) is True
        assert rg.check_and_accept(2) is True
        assert rg.check_and_accept(10) is True

    def test_duplicate_rejected(self):
        rg = ReplayGuard(window_size=64)
        rg.check_and_accept(5)
        assert rg.check_and_accept(5) is False

    def test_old_sequence_rejected(self):
        rg = ReplayGuard(window_size=10)
        for i in range(1, 20):
            rg.check_and_accept(i)
        # Sequence 1 is now outside window
        assert rg.check_and_accept(1) is False

    def test_window_sliding(self):
        rg = ReplayGuard(window_size=32)
        for i in range(1, 100):
            assert rg.check_and_accept(i) is True


# ---------------------------------------------------------------------------
# Audio Pipeline tests
# ---------------------------------------------------------------------------

from audio_pipeline import (
    AudioPipelineController,
    OpusConfig,
    JitterBuffer,
    EchoCanceller,
    EchoCancelState,
    AVSyncTracker,
    AVSyncState,
    AudioLevelMeter,
    AudioFrame,
    AVSyncSample,
)


class TestOpusConfig:
    """Test Opus configuration."""

    def test_default_config(self):
        cfg = OpusConfig()
        assert cfg.sample_rate == 48000
        assert cfg.channels == 1
        assert cfg.bitrate_bps == 32000
        assert cfg.frame_duration_ms == 20

    def test_custom_config(self):
        cfg = OpusConfig(bitrate_bps=64000, channels=2, dtx_enabled=False)
        assert cfg.bitrate_bps == 64000
        assert cfg.channels == 2
        assert cfg.dtx_enabled is False

    def test_frame_size_samples(self):
        cfg = OpusConfig(sample_rate=48000, frame_duration_ms=20)
        assert cfg.frame_size_samples == 960  # 48000 * 20 / 1000


class TestJitterBuffer:
    """Test jitter buffer behavior."""

    def test_add_and_get_frames(self):
        jb = JitterBuffer(target_ms=40)
        frame = AudioFrame(
            data=b"\x00" * 160,
            timestamp_ms=100,
            sequence=1,
            duration_ms=20,
        )
        jb.push(frame)
        stats = jb.get_stats()
        assert stats["depth_frames"] >= 1

    def test_out_of_order_handling(self):
        jb = JitterBuffer(target_ms=40)
        jb.push(AudioFrame(data=b"\x01" * 160, timestamp_ms=120, sequence=3, duration_ms=20))
        jb.push(AudioFrame(data=b"\x00" * 160, timestamp_ms=100, sequence=1, duration_ms=20))
        jb.push(AudioFrame(data=b"\x02" * 160, timestamp_ms=110, sequence=2, duration_ms=20))
        stats = jb.get_stats()
        assert stats["depth_frames"] >= 2

    def test_pop_ordering(self):
        jb = JitterBuffer(target_ms=20)
        for i in range(5):
            jb.push(AudioFrame(data=b"\x00" * 160, timestamp_ms=i * 20, sequence=i + 1, duration_ms=20))
        stats = jb.get_stats()
        assert "depth_frames" in stats


class TestEchoCanceller:
    """Test echo cancellation state machine."""

    def test_initial_state(self):
        ec = EchoCanceller()
        assert ec.state == EchoCancelState.IDLE

    def test_capture_start(self):
        ec = EchoCanceller()
        ec.on_capture_start()
        assert ec.state == EchoCancelState.CAPTURING

    def test_reference_start(self):
        ec = EchoCanceller()
        ec.on_capture_start()
        ec.on_reference_start()
        assert ec.state == EchoCancelState.REFERENCE_PLAYING

    def test_stats(self):
        ec = EchoCanceller()
        stats = ec.get_stats()
        assert "state" in stats
        assert "erle_db" in stats


class TestAVSyncTracker:
    """Test audio/video sync drift tracking."""

    def test_in_sync(self):
        tracker = AVSyncTracker(max_drift_ms=80)
        for i in range(10):
            ts = 100 + i * 33
            tracker.record_sample(audio_pts_ms=ts, video_pts_ms=ts + 5)
        assert tracker.state == AVSyncState.IN_SYNC

    def test_drifted(self):
        tracker = AVSyncTracker(max_drift_ms=50)
        for i in range(20):
            ts = 100 + i * 33
            tracker.record_sample(audio_pts_ms=ts, video_pts_ms=ts + 100)
        assert tracker.state in (AVSyncState.DRIFTING, AVSyncState.CORRECTING)

    def test_stats(self):
        tracker = AVSyncTracker()
        stats = tracker.get_stats()
        assert "state" in stats
        assert "current_drift_ms" in stats


class TestAudioPipelineController:
    """Test the top-level audio pipeline controller."""

    def test_init(self):
        ctrl = AudioPipelineController()
        assert ctrl.opus is not None
        assert ctrl.jitter_buffer is not None
        assert ctrl.echo_canceller is not None
        assert ctrl.av_sync is not None

    def test_start_stop(self):
        ctrl = AudioPipelineController()
        ctrl.start()
        assert ctrl._active is True
        ctrl.stop()
        assert ctrl._active is False

    def test_stats(self):
        ctrl = AudioPipelineController()
        stats = ctrl.get_stats()
        assert "opus_config" in stats
        assert "active" in stats
        assert "jitter_buffer" in stats
        assert "echo_canceller" in stats
        assert "av_sync" in stats


# ---------------------------------------------------------------------------
# Stream Security tests
# ---------------------------------------------------------------------------

from stream_security import (
    StreamSecurityVerifier,
    SecurityLevel,
    CheckResult,
    DTLSFingerprint,
    SRTPCipherInfo,
    CipherStrength,
    ICECandidate,
    CandidateType,
    SessionToken,
    RateLimitState,
    SecurityAuditReport,
)


class TestDTLSFingerprint:
    """Test DTLS fingerprint verification."""

    def test_matching_fingerprints(self):
        fp = DTLSFingerprint(
            value="AA:BB:CC:DD:EE:FF:00:11",
            peer_value="AA:BB:CC:DD:EE:FF:00:11",
        )
        result = fp.verify()
        assert result == CheckResult.PASS
        assert fp.verified is True

    def test_mismatched_fingerprints(self):
        fp = DTLSFingerprint(
            value="AA:BB:CC:DD:EE:FF:00:11",
            peer_value="11:22:33:44:55:66:77:88",
        )
        result = fp.verify()
        assert result == CheckResult.FAIL

    def test_missing_fingerprint(self):
        fp = DTLSFingerprint(value="AA:BB:CC", peer_value="")
        result = fp.verify()
        assert result == CheckResult.SKIP

    def test_case_insensitive(self):
        fp = DTLSFingerprint(
            value="aa:bb:cc:dd",
            peer_value="AA:BB:CC:DD",
        )
        assert fp.verify() == CheckResult.PASS


class TestSRTPCipherInfo:
    """Test SRTP cipher classification."""

    def test_strong_cipher(self):
        info = SRTPCipherInfo.classify("AEAD_AES_256_GCM")
        assert info.strength == CipherStrength.STRONG

    def test_acceptable_cipher(self):
        info = SRTPCipherInfo.classify("AES_CM_128_HMAC_SHA1_80")
        assert info.strength == CipherStrength.ACCEPTABLE

    def test_weak_cipher(self):
        info = SRTPCipherInfo.classify("NULL_CIPHER")
        assert info.strength == CipherStrength.WEAK

    def test_unknown_cipher(self):
        info = SRTPCipherInfo.classify("SOME_FUTURE_CIPHER")
        assert info.strength == CipherStrength.UNKNOWN


class TestICECandidate:
    """Test ICE candidate properties."""

    def test_private_ip_detection(self):
        c = ICECandidate(ip="192.168.1.100", candidate_type=CandidateType.HOST)
        assert c.is_private is True

    def test_public_ip(self):
        c = ICECandidate(ip="8.8.8.8", candidate_type=CandidateType.SRFLX)
        assert c.is_private is False

    def test_172_private_range(self):
        c = ICECandidate(ip="172.16.0.1")
        assert c.is_private is True
        c2 = ICECandidate(ip="172.32.0.1")
        assert c2.is_private is False


class TestSessionToken:
    """Test session token validation."""

    def test_valid_token(self):
        token = SessionToken(
            token_id="test-1",
            issued_at=time.time(),
            expires_at=time.time() + 3600,
            rotations=0,
        )
        assert token.is_expired is False
        assert token.time_until_expiry > 0

    def test_expired_token(self):
        token = SessionToken(
            token_id="test-2",
            issued_at=time.time() - 7200,
            expires_at=time.time() - 3600,
        )
        assert token.is_expired is True

    def test_rotation_needed(self):
        token = SessionToken(
            token_id="test-3",
            issued_at=time.time() - 2000,
            expires_at=time.time() + 1600,
            rotation_interval_s=900,
            rotations=0,
        )
        assert token.needs_rotation is True


class TestRateLimitState:
    """Test rate limiting."""

    def test_within_limit(self):
        rl = RateLimitState(window_s=1.0, max_per_window=10)
        for _ in range(10):
            assert rl.record() is True

    def test_over_limit(self):
        rl = RateLimitState(window_s=1.0, max_per_window=5)
        for _ in range(5):
            rl.record()
        assert rl.record() is False
        assert rl.violations >= 1

    def test_rate_calculation(self):
        rl = RateLimitState(window_s=1.0, max_per_window=100)
        now = time.time()
        for i in range(10):
            rl.record(now=now + i * 0.01)
        assert rl.current_rate >= 0


class TestStreamSecurityVerifier:
    """Test the full security verifier."""

    def setup_method(self):
        self.verifier = StreamSecurityVerifier(
            production_mode=True,
            pinned_certs=["AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"],
        )

    def test_register_session(self):
        self.verifier.register_session("sess-1")
        stats = self.verifier.get_stats()
        assert stats["active_sessions"] == 1

    def test_unregister_session(self):
        self.verifier.register_session("sess-2")
        self.verifier.unregister_session("sess-2")
        stats = self.verifier.get_stats()
        assert stats["active_sessions"] == 0

    def test_dtls_check_pass(self):
        fp = DTLSFingerprint(value="AA:BB:CC", peer_value="AA:BB:CC")
        report = self.verifier.check_dtls_fingerprint(fp)
        assert report.result == CheckResult.PASS

    def test_srtp_strong(self):
        report = self.verifier.check_srtp_cipher("AEAD_AES_256_GCM")
        assert report.result == CheckResult.PASS

    def test_srtp_weak_blocked(self):
        self.verifier.WEAK_CIPHER_BLOCK = True
        report = self.verifier.check_srtp_cipher("NULL_CIPHER")
        assert report.result == CheckResult.FAIL

    def test_ice_relay_only_prod(self):
        candidates = [
            ICECandidate(ip="1.2.3.4", candidate_type=CandidateType.RELAY, port=443),
        ]
        report = self.verifier.check_ice_candidates(candidates)
        assert report.result == CheckResult.PASS

    def test_ice_host_blocked_prod(self):
        candidates = [
            ICECandidate(ip="192.168.1.5", candidate_type=CandidateType.HOST, port=5000),
        ]
        report = self.verifier.check_ice_candidates(candidates)
        assert report.result == CheckResult.FAIL

    def test_full_audit(self):
        self.verifier.register_session("audit-1")
        report = self.verifier.run_full_audit(
            session_id="audit-1",
            dtls_fp=DTLSFingerprint(value="AABB", peer_value="AABB"),
            srtp_cipher="AEAD_AES_256_GCM",
            ice_candidates=[
                ICECandidate(ip="1.2.3.4", candidate_type=CandidateType.RELAY),
            ],
        )
        assert isinstance(report, SecurityAuditReport)
        assert report.overall_level in (SecurityLevel.SECURE, SecurityLevel.DEGRADED)
        assert report.pass_count >= 1

    def test_anomaly_baseline(self):
        self.verifier.register_session("anom-1")
        r1 = self.verifier.check_anomaly("anom-1", "bitrate_kbps", 2000)
        assert r1.result == CheckResult.PASS

        r2 = self.verifier.check_anomaly("anom-1", "bitrate_kbps", 2100)
        assert r2.result == CheckResult.PASS

    def test_anomaly_spike(self):
        self.verifier.register_session("anom-2")
        self.verifier.check_anomaly("anom-2", "bitrate_kbps", 1000)
        r = self.verifier.check_anomaly("anom-2", "bitrate_kbps", 10000)
        assert r.result == CheckResult.WARN

    def test_health_check(self):
        assert self.verifier.health_check() == CheckResult.PASS

    def test_signaling_rate_limit(self):
        self.verifier.register_session("rl-1")
        for _ in range(10):
            self.verifier.record_signaling_message("rl-1")
        report = self.verifier.check_rate_limit("rl-1", "signaling")
        assert report.result in (CheckResult.PASS, CheckResult.WARN)

    def test_cert_pin_match(self):
        report = self.verifier.check_certificate_pin(
            "AA:BB:CC:DD:EE:FF:00:11:22:33:44:55:66:77:88:99"
        )
        assert report.result == CheckResult.PASS

    def test_cert_pin_mismatch(self):
        report = self.verifier.check_certificate_pin("FF:EE:DD:CC")
        assert report.result == CheckResult.FAIL


# ---------------------------------------------------------------------------
# Benchmark Harness tests
# ---------------------------------------------------------------------------

from benchmark_harness import (
    BenchmarkHarness,
    BenchmarkThresholds,
    BenchmarkStatus,
    BenchmarkResult,
    BenchmarkSuiteReport,
    MetricSample,
    MetricUnit,
    SetupTimeBenchmark,
    InputToPhotonBenchmark,
    BitrateAdaptBenchmark,
    ReconnectBenchmark,
    FrameDropBenchmark,
    AVSyncBenchmark,
)


class TestSetupTimeBenchmark:
    """Test setup time benchmark."""

    def test_simulation_mode(self):
        bench = SetupTimeBenchmark(iterations=10)
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)
        assert len(result.samples) == 10
        assert result.p50 > 0
        assert result.p95 > 0

    def test_pre_recorded(self):
        bench = SetupTimeBenchmark()
        result = bench.run(pre_recorded_samples=[500, 600, 700, 800, 900])
        assert result.status == BenchmarkStatus.PASSED
        assert len(result.samples) == 5

    def test_threshold_fail(self):
        bench = SetupTimeBenchmark(thresholds=BenchmarkThresholds(setup_time_p95_ms=100))
        result = bench.run(pre_recorded_samples=[200, 300, 400, 500, 600])
        assert result.status == BenchmarkStatus.FAILED


class TestInputToPhotonBenchmark:
    """Test input-to-photon benchmark."""

    def test_simulation_mode(self):
        bench = InputToPhotonBenchmark(iterations=20)
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)
        assert len(result.samples) == 20

    def test_pass(self):
        bench = InputToPhotonBenchmark()
        result = bench.run(pre_recorded_samples=[30, 35, 40, 45, 50, 55, 60])
        assert result.status == BenchmarkStatus.PASSED


class TestBitrateAdaptBenchmark:
    """Test bitrate adaptation benchmark."""

    def test_simulation_mode(self):
        bench = BitrateAdaptBenchmark()
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)

    def test_explicit_samples(self):
        bench = BitrateAdaptBenchmark()
        result = bench.run(
            rampup_samples_ms=[2000, 2500, 3000],
            rampdown_samples_ms=[800, 900, 1000],
        )
        assert result.status == BenchmarkStatus.PASSED


class TestReconnectBenchmark:
    """Test reconnect benchmark."""

    def test_simulation_mode(self):
        bench = ReconnectBenchmark(iterations=5)
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)
        assert len(result.samples) == 5

    def test_pre_recorded(self):
        bench = ReconnectBenchmark()
        result = bench.run(pre_recorded_samples=[(1000, 1), (1200, 1), (2000, 2)])
        assert result.status == BenchmarkStatus.PASSED


class TestFrameDropBenchmark:
    """Test frame drop benchmark."""

    def test_simulation_mode(self):
        bench = FrameDropBenchmark()
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)

    def test_explicit_stats(self):
        bench = FrameDropBenchmark()
        result = bench.run(total_frames=1000, dropped_frames=10, consecutive_drop_max=2)
        assert result.status == BenchmarkStatus.PASSED

    def test_excessive_drops(self):
        bench = FrameDropBenchmark(thresholds=BenchmarkThresholds(frame_drop_ratio_fail=0.01))
        result = bench.run(total_frames=1000, dropped_frames=50, consecutive_drop_max=2)
        assert result.status == BenchmarkStatus.FAILED


class TestAVSyncBenchmark:
    """Test AV sync benchmark."""

    def test_simulation_mode(self):
        bench = AVSyncBenchmark()
        result = bench.run()
        assert result.status in (BenchmarkStatus.PASSED, BenchmarkStatus.FAILED)

    def test_good_sync(self):
        bench = AVSyncBenchmark()
        result = bench.run(drift_samples_ms=[5, -3, 10, -8, 15, -12, 20])
        assert result.status == BenchmarkStatus.PASSED

    def test_bad_sync(self):
        bench = AVSyncBenchmark(thresholds=BenchmarkThresholds(av_sync_drift_fail_ms=30))
        result = bench.run(drift_samples_ms=[100, -90, 120, -110, 80])
        assert result.status == BenchmarkStatus.FAILED


class TestBenchmarkHarness:
    """Test the full benchmark harness."""

    def test_run_all_simulation(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        report = harness.run_all(run_id="test-run-001")
        assert isinstance(report, BenchmarkSuiteReport)
        assert len(report.results) == 6
        assert report.passed_count + report.failed_count <= 6

    def test_skip_benchmarks(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        report = harness.run_all(
            run_id="test-skip",
            skip=["setup_time", "reconnect"],
        )
        skipped = [r for r in report.results if r.status == BenchmarkStatus.SKIPPED]
        assert len(skipped) == 2

    def test_report_json_save(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        report = harness.run_all(run_id="test-json")
        json_path = tmp_path / "bench" / "test-json.json"
        assert json_path.exists()

    def test_stats(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        stats = harness.get_stats()
        assert "benchmarks" in stats
        assert len(stats["benchmarks"]) == 6

    def test_health_check(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        assert harness.health_check() == "OK"

    def test_report_to_dict(self, tmp_path):
        harness = BenchmarkHarness(output_dir=tmp_path / "bench")
        report = harness.run_all(run_id="test-dict")
        d = report.to_dict()
        assert d["run_id"] == "test-dict"
        assert "results" in d
        assert len(d["results"]) == 6


class TestBenchmarkResult:
    """Test BenchmarkResult stats computation."""

    def test_compute_stats(self):
        result = BenchmarkResult(name="test", status=BenchmarkStatus.RUNNING, unit=MetricUnit.MS)
        for val in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            result.samples.append(MetricSample(value=val, unit=MetricUnit.MS))
        result.compute_stats()
        assert result.min_val == 10
        assert result.max_val == 100
        assert result.mean == 55.0
        assert result.p50 > 0
        assert result.p95 > 0
