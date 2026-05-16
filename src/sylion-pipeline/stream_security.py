"""
SYLION Pion D — Stream Security Verifier

Runtime security checks for WebRTC streaming sessions:
  - DTLS fingerprint validation (SHA-256 match)
  - SRTP cipher audit (reject weak ciphers)
  - ICE candidate filtering (block non-TURN relay in prod)
  - Session token expiry / rotation enforcement
  - Certificate pinning check (expected vs observed)
  - Rate limiting (signaling msg/s, data channel msg/s)
  - Anomaly detection (unexpected codec switch, bitrate spike)
"""

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("stream_security")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SecurityLevel(str, Enum):
    """Overall session security assessment."""
    SECURE = "secure"
    DEGRADED = "degraded"
    INSECURE = "insecure"
    UNKNOWN = "unknown"


class CheckResult(str, Enum):
    """Individual check outcome."""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


class CipherStrength(str, Enum):
    STRONG = "strong"        # AES-256-GCM, CHACHA20
    ACCEPTABLE = "acceptable"  # AES-128-GCM
    WEAK = "weak"            # AES-128-CBC, RC4, NULL
    UNKNOWN = "unknown"


class CandidateType(str, Enum):
    HOST = "host"
    SRFLX = "srflx"      # Server-reflexive
    PRFLX = "prflx"      # Peer-reflexive
    RELAY = "relay"       # TURN relay


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DTLSFingerprint:
    """DTLS certificate fingerprint from SDP."""
    algorithm: str = "sha-256"
    value: str = ""          # hex fingerprint from SDP a=fingerprint
    peer_value: str = ""     # fingerprint observed during handshake
    verified: bool = False

    def verify(self) -> CheckResult:
        """Compare SDP fingerprint with handshake fingerprint."""
        if not self.value or not self.peer_value:
            log.warning("DTLS fingerprint missing: sdp=%s, peer=%s",
                        bool(self.value), bool(self.peer_value))
            return CheckResult.SKIP

        norm_sdp = self.value.replace(":", "").lower().strip()
        norm_peer = self.peer_value.replace(":", "").lower().strip()

        if norm_sdp == norm_peer:
            self.verified = True
            log.info("DTLS fingerprint OK: %s...%s", norm_sdp[:16], norm_sdp[-8:])
            return CheckResult.PASS
        else:
            log.error("DTLS fingerprint MISMATCH: SDP=%s..., PEER=%s...",
                      norm_sdp[:16], norm_peer[:16])
            return CheckResult.FAIL


@dataclass
class SRTPCipherInfo:
    """SRTP cipher suite info."""
    name: str = ""
    key_length: int = 0
    auth_tag_length: int = 0
    strength: CipherStrength = CipherStrength.UNKNOWN

    @staticmethod
    def classify(cipher_name: str) -> "SRTPCipherInfo":
        """Classify a cipher suite name into strength category."""
        cn = cipher_name.upper().strip()

        # Strong ciphers
        if "AES_256_GCM" in cn or "CHACHA20" in cn:
            return SRTPCipherInfo(
                name=cipher_name, key_length=256,
                auth_tag_length=128, strength=CipherStrength.STRONG,
            )

        # Acceptable ciphers
        if "AES_CM_128" in cn and "HMAC_SHA1_80" in cn:
            return SRTPCipherInfo(
                name=cipher_name, key_length=128,
                auth_tag_length=80, strength=CipherStrength.ACCEPTABLE,
            )
        if "AES_128_GCM" in cn:
            return SRTPCipherInfo(
                name=cipher_name, key_length=128,
                auth_tag_length=128, strength=CipherStrength.ACCEPTABLE,
            )

        # Weak ciphers
        if "NULL" in cn or "RC4" in cn or ("CBC" in cn and "128" in cn):
            return SRTPCipherInfo(
                name=cipher_name, key_length=128 if "128" in cn else 0,
                auth_tag_length=0, strength=CipherStrength.WEAK,
            )

        # HMAC_SHA1_32 — short auth tag, marginal
        if "HMAC_SHA1_32" in cn:
            return SRTPCipherInfo(
                name=cipher_name, key_length=128,
                auth_tag_length=32, strength=CipherStrength.WEAK,
            )

        return SRTPCipherInfo(name=cipher_name, strength=CipherStrength.UNKNOWN)


@dataclass
class ICECandidate:
    """Parsed ICE candidate."""
    foundation: str = ""
    component: int = 1
    protocol: str = "udp"
    priority: int = 0
    ip: str = ""
    port: int = 0
    candidate_type: CandidateType = CandidateType.HOST
    related_address: str = ""
    related_port: int = 0

    @property
    def is_private(self) -> bool:
        """Check if IP is RFC1918 / link-local."""
        if self.ip.startswith("10.") or self.ip.startswith("192.168."):
            return True
        if self.ip.startswith("172."):
            parts = self.ip.split(".")
            if len(parts) >= 2 and 16 <= int(parts[1]) <= 31:
                return True
        if self.ip.startswith("fe80:") or self.ip.startswith("169.254."):
            return True
        return False


@dataclass
class SessionToken:
    """Session authentication token with expiry tracking."""
    token_id: str = ""
    issued_at: float = 0.0
    expires_at: float = 0.0
    rotations: int = 0
    max_lifetime_s: float = 3600.0      # 1 hour default
    rotation_interval_s: float = 900.0   # 15 min rotation
    hmac_key: bytes = b""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def time_until_expiry(self) -> float:
        return max(0.0, self.expires_at - time.time())

    @property
    def needs_rotation(self) -> bool:
        age = time.time() - self.issued_at
        expected_rotations = int(age / self.rotation_interval_s)
        return self.rotations < expected_rotations

    def verify_hmac(self, message: bytes, received_mac: bytes) -> bool:
        """Verify HMAC of a message using session key."""
        if not self.hmac_key:
            return False
        expected = hmac.new(self.hmac_key, message, hashlib.sha256).digest()
        return hmac.compare_digest(expected, received_mac)


@dataclass
class RateLimitState:
    """Rate limiter for signaling/data channel messages."""
    window_s: float = 1.0
    max_per_window: int = 100
    _timestamps: list[float] = field(default_factory=list)
    _violations: int = 0

    def record(self, now: float | None = None) -> bool:
        """Record a message. Returns True if within limit, False if rate exceeded."""
        t = now or time.time()
        cutoff = t - self.window_s
        self._timestamps = [ts for ts in self._timestamps if ts > cutoff]
        self._timestamps.append(t)

        if len(self._timestamps) > self.max_per_window:
            self._violations += 1
            return False
        return True

    @property
    def current_rate(self) -> float:
        """Messages per second in current window."""
        if not self._timestamps:
            return 0.0
        now = time.time()
        cutoff = now - self.window_s
        recent = [ts for ts in self._timestamps if ts > cutoff]
        return len(recent) / self.window_s if self.window_s > 0 else 0.0

    @property
    def violations(self) -> int:
        return self._violations


@dataclass
class SecurityCheckReport:
    """Result of a single security check."""
    check_name: str
    result: CheckResult
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class SecurityAuditReport:
    """Complete security audit of a streaming session."""
    session_id: str
    checks: list[SecurityCheckReport] = field(default_factory=list)
    overall_level: SecurityLevel = SecurityLevel.UNKNOWN
    timestamp: float = field(default_factory=time.time)
    recommendations: list[str] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.result == CheckResult.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.result == CheckResult.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.result == CheckResult.WARN)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "overall_level": self.overall_level.value,
            "pass": self.pass_count,
            "fail": self.fail_count,
            "warn": self.warn_count,
            "checks": [
                {
                    "name": c.check_name,
                    "result": c.result.value,
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Main: StreamSecurityVerifier
# ---------------------------------------------------------------------------

class StreamSecurityVerifier:
    """Runtime security verifier for WebRTC streaming sessions.

    Performs a battery of checks:
      1. DTLS fingerprint match
      2. SRTP cipher strength audit
      3. ICE candidate filtering (prod → relay-only)
      4. Session token validity
      5. Rate limiting (signaling + data channel)
      6. Certificate pinning (optional)
      7. Anomaly detection (codec switch, bitrate spike)
    """

    # --- Configurable thresholds ---
    WEAK_CIPHER_BLOCK: bool = True                 # Block weak ciphers entirely
    REQUIRE_RELAY_IN_PROD: bool = True             # Only TURN relay in production
    SIGNALING_RATE_LIMIT: int = 50                 # msgs/s
    DATACHANNEL_RATE_LIMIT: int = 200              # msgs/s
    MAX_BITRATE_SPIKE_FACTOR: float = 3.0          # 3× normal = anomaly
    TOKEN_MAX_LIFETIME_S: float = 3600.0           # 1 hour
    TOKEN_ROTATION_INTERVAL_S: float = 900.0       # 15 min

    def __init__(
        self,
        production_mode: bool = True,
        pinned_certs: list[str] | None = None,
        custom_rate_limits: dict[str, int] | None = None,
    ):
        self._production_mode = production_mode
        self._pinned_certs: list[str] = pinned_certs or []
        self._sessions: dict[str, dict[str, Any]] = {}

        # Rate limiters per session
        self._signaling_limiters: dict[str, RateLimitState] = {}
        self._datachannel_limiters: dict[str, RateLimitState] = {}

        if custom_rate_limits:
            self.SIGNALING_RATE_LIMIT = custom_rate_limits.get(
                "signaling", self.SIGNALING_RATE_LIMIT)
            self.DATACHANNEL_RATE_LIMIT = custom_rate_limits.get(
                "datachannel", self.DATACHANNEL_RATE_LIMIT)

        self._anomaly_baselines: dict[str, dict[str, float]] = {}  # session → metric → baseline
        self._audit_history: list[SecurityAuditReport] = []

        log.info("StreamSecurityVerifier init: prod=%s, pinned_certs=%d, "
                 "sig_rate=%d/s, dc_rate=%d/s",
                 production_mode, len(self._pinned_certs),
                 self.SIGNALING_RATE_LIMIT, self.DATACHANNEL_RATE_LIMIT)

    # ----- Session lifecycle -----

    def register_session(self, session_id: str, token: SessionToken | None = None) -> None:
        """Register a new streaming session for monitoring."""
        self._sessions[session_id] = {
            "token": token,
            "registered_at": time.time(),
            "last_audit": 0.0,
            "audit_count": 0,
        }
        self._signaling_limiters[session_id] = RateLimitState(
            max_per_window=self.SIGNALING_RATE_LIMIT,
        )
        self._datachannel_limiters[session_id] = RateLimitState(
            max_per_window=self.DATACHANNEL_RATE_LIMIT,
        )
        log.info("Session registered: %s (token=%s)", session_id, bool(token))

    def unregister_session(self, session_id: str) -> None:
        """Remove session from monitoring."""
        self._sessions.pop(session_id, None)
        self._signaling_limiters.pop(session_id, None)
        self._datachannel_limiters.pop(session_id, None)
        self._anomaly_baselines.pop(session_id, None)
        log.info("Session unregistered: %s", session_id)

    # ----- Individual checks -----

    def check_dtls_fingerprint(self, fp: DTLSFingerprint) -> SecurityCheckReport:
        """Check 1: DTLS fingerprint match."""
        result = fp.verify()
        msg = "DTLS fingerprint verified" if result == CheckResult.PASS else (
            "DTLS fingerprint MISMATCH — possible MITM" if result == CheckResult.FAIL
            else "DTLS fingerprint data incomplete"
        )
        return SecurityCheckReport(
            check_name="dtls_fingerprint",
            result=result,
            message=msg,
            details={
                "algorithm": fp.algorithm,
                "sdp_fp": fp.value[:24] + "..." if fp.value else "",
                "peer_fp": fp.peer_value[:24] + "..." if fp.peer_value else "",
                "verified": fp.verified,
            },
        )

    def check_srtp_cipher(self, cipher_name: str) -> SecurityCheckReport:
        """Check 2: SRTP cipher strength."""
        info = SRTPCipherInfo.classify(cipher_name)

        if info.strength == CipherStrength.STRONG:
            return SecurityCheckReport(
                check_name="srtp_cipher",
                result=CheckResult.PASS,
                message=f"Strong cipher: {cipher_name}",
                details={"strength": info.strength.value, "key_bits": info.key_length},
            )
        elif info.strength == CipherStrength.ACCEPTABLE:
            return SecurityCheckReport(
                check_name="srtp_cipher",
                result=CheckResult.PASS,
                message=f"Acceptable cipher: {cipher_name}",
                details={"strength": info.strength.value, "key_bits": info.key_length},
            )
        elif info.strength == CipherStrength.WEAK:
            r = CheckResult.FAIL if self.WEAK_CIPHER_BLOCK else CheckResult.WARN
            return SecurityCheckReport(
                check_name="srtp_cipher",
                result=r,
                message=f"Weak cipher detected: {cipher_name}",
                details={"strength": info.strength.value, "key_bits": info.key_length,
                         "blocked": self.WEAK_CIPHER_BLOCK},
            )
        else:
            return SecurityCheckReport(
                check_name="srtp_cipher",
                result=CheckResult.WARN,
                message=f"Unknown cipher: {cipher_name}",
                details={"strength": info.strength.value},
            )

    def check_ice_candidates(
        self, candidates: list[ICECandidate],
    ) -> SecurityCheckReport:
        """Check 3: ICE candidate filtering.

        In production mode, only TURN relay candidates are allowed.
        Host/srflx candidates leak internal IPs.
        """
        if not candidates:
            return SecurityCheckReport(
                check_name="ice_candidates",
                result=CheckResult.SKIP,
                message="No ICE candidates to check",
            )

        type_counts: dict[str, int] = {}
        private_ips: list[str] = []
        for c in candidates:
            ct = c.candidate_type.value
            type_counts[ct] = type_counts.get(ct, 0) + 1
            if c.is_private and c.candidate_type != CandidateType.RELAY:
                private_ips.append(c.ip)

        has_relay = type_counts.get("relay", 0) > 0
        has_non_relay = any(
            type_counts.get(ct, 0) > 0
            for ct in ["host", "srflx", "prflx"]
        )

        if self._production_mode and self.REQUIRE_RELAY_IN_PROD:
            if has_non_relay:
                return SecurityCheckReport(
                    check_name="ice_candidates",
                    result=CheckResult.FAIL,
                    message="Non-relay ICE candidates in production mode (IP leak risk)",
                    details={
                        "types": type_counts,
                        "private_ips_exposed": private_ips,
                        "production_mode": True,
                    },
                )
            elif has_relay:
                return SecurityCheckReport(
                    check_name="ice_candidates",
                    result=CheckResult.PASS,
                    message="Only TURN relay candidates (production-safe)",
                    details={"types": type_counts},
                )
            else:
                return SecurityCheckReport(
                    check_name="ice_candidates",
                    result=CheckResult.FAIL,
                    message="No relay candidates — connectivity may fail",
                    details={"types": type_counts},
                )
        else:
            # Dev mode: warn but don't fail
            if private_ips:
                return SecurityCheckReport(
                    check_name="ice_candidates",
                    result=CheckResult.WARN,
                    message=f"Private IPs exposed via ICE ({len(private_ips)} found) — ok in dev",
                    details={"types": type_counts, "private_ips": private_ips},
                )
            return SecurityCheckReport(
                check_name="ice_candidates",
                result=CheckResult.PASS,
                message="ICE candidates OK (dev mode)",
                details={"types": type_counts},
            )

    def check_session_token(
        self, session_id: str,
    ) -> SecurityCheckReport:
        """Check 4: Session token validity and rotation."""
        session = self._sessions.get(session_id)
        if not session or not session.get("token"):
            return SecurityCheckReport(
                check_name="session_token",
                result=CheckResult.SKIP,
                message="No session token configured",
            )

        token: SessionToken = session["token"]

        if token.is_expired:
            return SecurityCheckReport(
                check_name="session_token",
                result=CheckResult.FAIL,
                message=f"Session token EXPIRED (expired {time.time() - token.expires_at:.0f}s ago)",
                details={
                    "token_id": token.token_id,
                    "expired_at": token.expires_at,
                    "rotations": token.rotations,
                },
            )

        if token.needs_rotation:
            return SecurityCheckReport(
                check_name="session_token",
                result=CheckResult.WARN,
                message=(
                    f"Token rotation overdue "
                    f"(rotations={token.rotations}, "
                    f"age={time.time() - token.issued_at:.0f}s)"
                ),
                details={
                    "token_id": token.token_id,
                    "rotations": token.rotations,
                    "needs_rotation": True,
                    "ttl_s": token.time_until_expiry,
                },
            )

        return SecurityCheckReport(
            check_name="session_token",
            result=CheckResult.PASS,
            message=f"Token valid (TTL={token.time_until_expiry:.0f}s, rotations={token.rotations})",
            details={
                "token_id": token.token_id,
                "ttl_s": token.time_until_expiry,
                "rotations": token.rotations,
            },
        )

    def check_rate_limit(
        self, session_id: str, channel: str = "signaling",
    ) -> SecurityCheckReport:
        """Check 5: Rate limiting for signaling / data channel."""
        limiter = (
            self._signaling_limiters.get(session_id)
            if channel == "signaling"
            else self._datachannel_limiters.get(session_id)
        )

        if not limiter:
            return SecurityCheckReport(
                check_name=f"rate_limit_{channel}",
                result=CheckResult.SKIP,
                message=f"No rate limiter for session {session_id}",
            )

        rate = limiter.current_rate
        violations = limiter.violations
        limit = limiter.max_per_window

        if violations > 0:
            return SecurityCheckReport(
                check_name=f"rate_limit_{channel}",
                result=CheckResult.WARN if violations < 10 else CheckResult.FAIL,
                message=f"Rate limit violations: {violations} (current={rate:.1f}/{limit}/s)",
                details={
                    "channel": channel,
                    "current_rate": rate,
                    "limit": limit,
                    "violations": violations,
                },
            )

        return SecurityCheckReport(
            check_name=f"rate_limit_{channel}",
            result=CheckResult.PASS,
            message=f"{channel} rate OK ({rate:.1f}/{limit}/s)",
            details={"channel": channel, "current_rate": rate, "limit": limit},
        )

    def check_certificate_pin(
        self, observed_fingerprint: str,
    ) -> SecurityCheckReport:
        """Check 6: Certificate pinning."""
        if not self._pinned_certs:
            return SecurityCheckReport(
                check_name="certificate_pin",
                result=CheckResult.SKIP,
                message="No pinned certificates configured",
            )

        norm = observed_fingerprint.replace(":", "").lower().strip()
        for pin in self._pinned_certs:
            # P2-A fix: constant-time comparison to prevent timing side-channel
            if hmac.compare_digest(
                pin.replace(":", "").lower().strip().encode(),
                norm.encode(),
            ):
                return SecurityCheckReport(
                    check_name="certificate_pin",
                    result=CheckResult.PASS,
                    message="Certificate matches pinned fingerprint",
                    details={"matched_pin": pin[:24] + "..."},
                )

        return SecurityCheckReport(
            check_name="certificate_pin",
            result=CheckResult.FAIL,
            message="Certificate does NOT match any pinned fingerprint",
            details={
                "observed": norm[:24] + "...",
                "pinned_count": len(self._pinned_certs),
            },
        )

    def check_anomaly(
        self,
        session_id: str,
        metric_name: str,
        current_value: float,
    ) -> SecurityCheckReport:
        """Check 7: Anomaly detection (unexpected value spikes)."""
        baselines = self._anomaly_baselines.setdefault(session_id, {})

        if metric_name not in baselines:
            # First observation — set baseline
            baselines[metric_name] = current_value
            return SecurityCheckReport(
                check_name=f"anomaly_{metric_name}",
                result=CheckResult.PASS,
                message=f"Baseline set for {metric_name}={current_value:.2f}",
                details={"baseline": current_value, "current": current_value},
            )

        baseline = baselines[metric_name]
        if baseline <= 0:
            # Can't compute ratio with zero baseline
            baselines[metric_name] = current_value
            return SecurityCheckReport(
                check_name=f"anomaly_{metric_name}",
                result=CheckResult.PASS,
                message=f"{metric_name}: baseline updated (was 0)",
                details={"baseline": current_value, "current": current_value},
            )

        ratio = current_value / baseline

        if ratio > self.MAX_BITRATE_SPIKE_FACTOR:
            return SecurityCheckReport(
                check_name=f"anomaly_{metric_name}",
                result=CheckResult.WARN,
                message=(
                    f"Anomaly: {metric_name} spiked {ratio:.1f}× "
                    f"(baseline={baseline:.1f}, current={current_value:.1f})"
                ),
                details={
                    "baseline": baseline,
                    "current": current_value,
                    "ratio": ratio,
                    "threshold": self.MAX_BITRATE_SPIKE_FACTOR,
                },
            )

        # Update baseline with exponential moving average
        alpha = 0.3
        baselines[metric_name] = alpha * current_value + (1 - alpha) * baseline

        return SecurityCheckReport(
            check_name=f"anomaly_{metric_name}",
            result=CheckResult.PASS,
            message=f"{metric_name} normal ({current_value:.1f}, baseline={baseline:.1f})",
            details={"baseline": baseline, "current": current_value, "ratio": ratio},
        )

    # ----- Record rate-limited messages -----

    def record_signaling_message(self, session_id: str) -> bool:
        """Record a signaling message. Returns True if within rate limit."""
        limiter = self._signaling_limiters.get(session_id)
        if not limiter:
            return True
        return limiter.record()

    def record_datachannel_message(self, session_id: str) -> bool:
        """Record a data channel message. Returns True if within rate limit."""
        limiter = self._datachannel_limiters.get(session_id)
        if not limiter:
            return True
        return limiter.record()

    # ----- Full audit -----

    def run_full_audit(
        self,
        session_id: str,
        dtls_fp: DTLSFingerprint | None = None,
        srtp_cipher: str | None = None,
        ice_candidates: list[ICECandidate] | None = None,
        cert_fingerprint: str | None = None,
        anomaly_metrics: dict[str, float] | None = None,
    ) -> SecurityAuditReport:
        """Run all security checks for a session.

        Returns a SecurityAuditReport with individual check results
        and an overall security level.
        """
        report = SecurityAuditReport(session_id=session_id)

        # Check 1: DTLS fingerprint
        if dtls_fp:
            report.checks.append(self.check_dtls_fingerprint(dtls_fp))
        else:
            report.checks.append(SecurityCheckReport(
                check_name="dtls_fingerprint",
                result=CheckResult.SKIP,
                message="No DTLS fingerprint provided",
            ))

        # Check 2: SRTP cipher
        if srtp_cipher:
            report.checks.append(self.check_srtp_cipher(srtp_cipher))
        else:
            report.checks.append(SecurityCheckReport(
                check_name="srtp_cipher",
                result=CheckResult.SKIP,
                message="No SRTP cipher info provided",
            ))

        # Check 3: ICE candidates
        if ice_candidates is not None:
            report.checks.append(self.check_ice_candidates(ice_candidates))
        else:
            report.checks.append(SecurityCheckReport(
                check_name="ice_candidates",
                result=CheckResult.SKIP,
                message="No ICE candidates provided",
            ))

        # Check 4: Session token
        report.checks.append(self.check_session_token(session_id))

        # Check 5: Rate limits
        report.checks.append(self.check_rate_limit(session_id, "signaling"))
        report.checks.append(self.check_rate_limit(session_id, "datachannel"))

        # Check 6: Certificate pinning
        if cert_fingerprint:
            report.checks.append(self.check_certificate_pin(cert_fingerprint))

        # Check 7: Anomaly detection
        if anomaly_metrics:
            for metric_name, value in anomaly_metrics.items():
                report.checks.append(self.check_anomaly(session_id, metric_name, value))

        # --- Determine overall level ---
        report.overall_level = self._compute_overall_level(report.checks)

        # --- Generate recommendations ---
        report.recommendations = self._generate_recommendations(report.checks)

        # --- Record ---
        session = self._sessions.get(session_id)
        if session:
            session["last_audit"] = time.time()
            session["audit_count"] = session.get("audit_count", 0) + 1

        self._audit_history.append(report)

        log.info("Security audit for %s: %s (pass=%d, warn=%d, fail=%d)",
                 session_id, report.overall_level.value,
                 report.pass_count, report.warn_count, report.fail_count)

        return report

    # ----- Helpers -----

    @staticmethod
    def _compute_overall_level(checks: list[SecurityCheckReport]) -> SecurityLevel:
        """Compute overall security level from check results."""
        fails = sum(1 for c in checks if c.result == CheckResult.FAIL)
        warns = sum(1 for c in checks if c.result == CheckResult.WARN)

        if fails > 0:
            return SecurityLevel.INSECURE
        if warns >= 3:
            return SecurityLevel.DEGRADED
        if warns > 0:
            return SecurityLevel.DEGRADED
        return SecurityLevel.SECURE

    @staticmethod
    def _generate_recommendations(checks: list[SecurityCheckReport]) -> list[str]:
        """Generate actionable recommendations from check results."""
        recs: list[str] = []

        for c in checks:
            if c.result == CheckResult.FAIL:
                if "dtls" in c.check_name:
                    recs.append(
                        "CRITICAL: DTLS fingerprint mismatch detected — "
                        "investigate potential MITM attack. Terminate session immediately."
                    )
                elif "cipher" in c.check_name:
                    recs.append(
                        "Upgrade SRTP cipher to AES-256-GCM or CHACHA20-POLY1305. "
                        "Block weak ciphers in SDP offer."
                    )
                elif "ice" in c.check_name:
                    recs.append(
                        "Configure ICE to use only TURN relay candidates in production. "
                        "Set iceTransportPolicy='relay' in RTCConfiguration."
                    )
                elif "token" in c.check_name:
                    recs.append(
                        "Session token expired — force re-authentication. "
                        "Implement automatic token refresh before expiry."
                    )
                elif "rate_limit" in c.check_name:
                    recs.append(
                        "Excessive rate limit violations — potential DoS. "
                        "Consider IP-based throttling or session termination."
                    )
                elif "certificate" in c.check_name:
                    recs.append(
                        "Certificate pinning failed — possible certificate replacement. "
                        "Verify TLS termination and certificate chain."
                    )
            elif c.result == CheckResult.WARN:
                if "token" in c.check_name:
                    recs.append(
                        "Token rotation overdue — schedule immediate rotation "
                        "to limit exposure window."
                    )
                elif "anomaly" in c.check_name:
                    recs.append(
                        f"Anomaly detected in {c.check_name}: {c.message}. "
                        "Monitor closely and investigate if persistent."
                    )

        return recs

    # ----- Stats -----

    def get_stats(self) -> dict[str, Any]:
        """Get verifier statistics."""
        return {
            "active_sessions": len(self._sessions),
            "total_audits": len(self._audit_history),
            "production_mode": self._production_mode,
            "pinned_certs": len(self._pinned_certs),
            "rate_limits": {
                "signaling": self.SIGNALING_RATE_LIMIT,
                "datachannel": self.DATACHANNEL_RATE_LIMIT,
            },
        }

    def get_session_audit_history(self, session_id: str) -> list[dict]:
        """Get audit history for a specific session."""
        return [
            r.to_dict()
            for r in self._audit_history
            if r.session_id == session_id
        ]

    def health_check(self) -> CheckResult:
        """Simple health check — returns PASS if verifier is operational."""
        return CheckResult.PASS
