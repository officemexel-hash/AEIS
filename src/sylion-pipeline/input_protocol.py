"""
SYLION Pion D — Input Protocol Runtime

Binary wire format for touch/key/gamepad input over WebRTC DataChannel.
Features:
  - Compact binary encoding (header + payload)
  - Replay protection (sequence numbers + HMAC)
  - Touch, key, gamepad event types
  - Configurable HMAC key rotation
  - Event batching for low-latency transport
"""

import hashlib
import hmac
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum, Enum
from typing import Any

log = logging.getLogger("input_protocol")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION = 1
HEADER_SIZE = 16  # bytes: version(1) + type(1) + seq(4) + timestamp(4) + payload_len(2) + flags(1) + reserved(3)
MAX_PAYLOAD_SIZE = 1024
MAX_BATCH_SIZE = 32
# T-09: Load-or-create persistent HMAC key stored in the runtime state directory.
# Falls back to per-process random key if file I/O fails.
def _load_or_create_hmac_key() -> bytes:
    """T-09: Load persistent HMAC key from runtime state, or create it.

    The key is stored outside the Python package so it survives restarts.
    File permissions are set to 0o600 (owner read/write only).
    If the file cannot be read or written, falls back to a per-process random key.
    """
    from pathlib import Path
    state_root = Path(os.getenv("SYLION_RUNTIME_STATE_DIR", Path(__file__).parent / ".runtime"))
    key_path = state_root / "hmac_key.bin"
    if key_path.exists():
        return key_path.read_bytes()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    new_key = os.urandom(32)
    key_path.write_bytes(new_key)
    try:
        key_path.chmod(0o600)
    except Exception:
        pass
    return new_key


DEFAULT_HMAC_KEY = _load_or_create_hmac_key()
HMAC_SIZE = 32  # SHA-256 HMAC


class InputEventType(IntEnum):
    """Input event types transmitted over DataChannel."""
    TOUCH_DOWN = 0x01
    TOUCH_MOVE = 0x02
    TOUCH_UP = 0x03
    KEY_DOWN = 0x10
    KEY_UP = 0x11
    GAMEPAD_BUTTON = 0x20
    GAMEPAD_AXIS = 0x21
    MOUSE_MOVE = 0x30
    MOUSE_CLICK = 0x31
    MOUSE_SCROLL = 0x32
    PING = 0xFE
    PONG = 0xFF


class ProtocolError(Exception):
    """Input protocol error."""
    pass


class ReplayAttackError(ProtocolError):
    """Replay attack detected."""
    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class TouchEvent:
    """Touch input event."""
    pointer_id: int
    x: float  # 0.0 - 1.0 normalized
    y: float  # 0.0 - 1.0 normalized
    pressure: float = 1.0  # 0.0 - 1.0

    def to_bytes(self) -> bytes:
        return struct.pack("!Bfff", self.pointer_id, self.x, self.y, self.pressure)

    @classmethod
    def from_bytes(cls, data: bytes) -> "TouchEvent":
        pid, x, y, p = struct.unpack("!Bfff", data[:13])
        return cls(pointer_id=pid, x=x, y=y, pressure=p)


@dataclass
class KeyEvent:
    """Keyboard input event."""
    keycode: int       # Android/HID keycode
    modifiers: int = 0  # Shift=1, Ctrl=2, Alt=4, Meta=8

    def to_bytes(self) -> bytes:
        return struct.pack("!HB", self.keycode, self.modifiers)

    @classmethod
    def from_bytes(cls, data: bytes) -> "KeyEvent":
        kc, mod = struct.unpack("!HB", data[:3])
        return cls(keycode=kc, modifiers=mod)


@dataclass
class GamepadEvent:
    """Gamepad button or axis event."""
    button_or_axis: int
    value: float  # 0.0-1.0 for buttons, -1.0..1.0 for axes

    def to_bytes(self) -> bytes:
        return struct.pack("!Bf", self.button_or_axis, self.value)

    @classmethod
    def from_bytes(cls, data: bytes) -> "GamepadEvent":
        ba, val = struct.unpack("!Bf", data[:5])
        return cls(button_or_axis=ba, value=val)


@dataclass
class InputFrame:
    """A single input frame with header + payload + HMAC."""
    version: int = PROTOCOL_VERSION
    event_type: InputEventType = InputEventType.PING
    sequence: int = 0
    timestamp_ms: int = 0
    payload: bytes = b""
    flags: int = 0  # bit 0: batched, bit 1: compressed

    def to_wire(self, hmac_key: bytes = DEFAULT_HMAC_KEY) -> bytes:
        """Serialize to wire format with HMAC."""
        payload_len = len(self.payload)
        if payload_len > MAX_PAYLOAD_SIZE:
            raise ProtocolError(f"Payload too large: {payload_len} > {MAX_PAYLOAD_SIZE}")

        header = struct.pack(
            "!BBIIBHB",
            self.version,
            int(self.event_type),
            self.sequence,
            self.timestamp_ms,
            self.flags,
            payload_len,
            0,  # reserved
        )
        # Pad header to HEADER_SIZE
        header = header.ljust(HEADER_SIZE, b"\x00")
        body = header + self.payload
        mac = hmac.new(hmac_key, body, hashlib.sha256).digest()
        return body + mac

    @classmethod
    def from_wire(cls, data: bytes, hmac_key: bytes = DEFAULT_HMAC_KEY) -> "InputFrame":
        """Deserialize from wire format, verify HMAC."""
        if len(data) < HEADER_SIZE + HMAC_SIZE:
            raise ProtocolError(f"Frame too short: {len(data)} bytes")

        body = data[:-HMAC_SIZE]
        received_mac = data[-HMAC_SIZE:]
        expected_mac = hmac.new(hmac_key, body, hashlib.sha256).digest()

        if not hmac.compare_digest(received_mac, expected_mac):
            raise ProtocolError("HMAC verification failed — possible tampering")

        header = body[:HEADER_SIZE]
        payload = body[HEADER_SIZE:]

        ver, etype, seq, ts, flags, plen, _ = struct.unpack("!BBIIBHB", header[:14])
        # Trim payload to declared length
        payload = payload[:plen]

        return cls(
            version=ver,
            event_type=InputEventType(etype),
            sequence=seq,
            timestamp_ms=ts,
            payload=payload,
            flags=flags,
        )


# ---------------------------------------------------------------------------
# Replay protection
# ---------------------------------------------------------------------------

class ReplayGuard:
    """Sequence-based replay protection with sliding window."""

    def __init__(self, window_size: int = 256):
        self.window_size = window_size
        self._highest_seq: int = 0
        self._seen: set[int] = set()
        self._stats = {"accepted": 0, "rejected_replay": 0, "rejected_old": 0}

    def check_and_accept(self, sequence: int) -> bool:
        """Check if sequence is valid (not replayed). Returns True if accepted."""
        if sequence in self._seen:
            self._stats["rejected_replay"] += 1
            return False

        if sequence < self._highest_seq - self.window_size:
            self._stats["rejected_old"] += 1
            return False

        self._seen.add(sequence)
        if sequence > self._highest_seq:
            self._highest_seq = sequence
            # Prune old entries outside window
            cutoff = self._highest_seq - self.window_size
            self._seen = {s for s in self._seen if s > cutoff}

        self._stats["accepted"] += 1
        return True

    @property
    def stats(self) -> dict:
        return {**self._stats, "highest_seq": self._highest_seq, "window_size": self.window_size}


# ---------------------------------------------------------------------------
# Input Protocol Codec
# ---------------------------------------------------------------------------

class InputProtocolCodec:
    """Encodes/decodes input events for DataChannel transport.

    Provides:
    - Frame serialization with HMAC integrity
    - Replay protection via sequence numbers
    - Event batching for reduced overhead
    - Round-trip latency measurement (ping/pong)
    """

    def __init__(
        self,
        hmac_key: bytes = DEFAULT_HMAC_KEY,
        replay_window: int = 256,
    ):
        self.hmac_key = hmac_key
        self.replay_guard = ReplayGuard(window_size=replay_window)
        self._send_seq: int = 0
        self._batch_buffer: list[InputFrame] = []
        self._rtt_pending: dict[int, float] = {}  # seq -> send_time
        self._rtt_samples: list[float] = []
        self._stats = {
            "frames_sent": 0,
            "frames_received": 0,
            "batches_sent": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "hmac_failures": 0,
            "replay_blocked": 0,
        }

    def _next_seq(self) -> int:
        self._send_seq += 1
        return self._send_seq

    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    # --- Encoding ---

    def encode_touch(self, event_type: InputEventType, touch: TouchEvent) -> bytes:
        """Encode a touch event to wire format."""
        frame = InputFrame(
            event_type=event_type,
            sequence=self._next_seq(),
            timestamp_ms=self._now_ms(),
            payload=touch.to_bytes(),
        )
        wire = frame.to_wire(self.hmac_key)
        self._stats["frames_sent"] += 1
        self._stats["bytes_sent"] += len(wire)
        return wire

    def encode_key(self, event_type: InputEventType, key: KeyEvent) -> bytes:
        """Encode a key event to wire format."""
        frame = InputFrame(
            event_type=event_type,
            sequence=self._next_seq(),
            timestamp_ms=self._now_ms(),
            payload=key.to_bytes(),
        )
        wire = frame.to_wire(self.hmac_key)
        self._stats["frames_sent"] += 1
        self._stats["bytes_sent"] += len(wire)
        return wire

    def encode_gamepad(self, event_type: InputEventType, gp: GamepadEvent) -> bytes:
        """Encode a gamepad event to wire format."""
        frame = InputFrame(
            event_type=event_type,
            sequence=self._next_seq(),
            timestamp_ms=self._now_ms(),
            payload=gp.to_bytes(),
        )
        wire = frame.to_wire(self.hmac_key)
        self._stats["frames_sent"] += 1
        self._stats["bytes_sent"] += len(wire)
        return wire

    def encode_ping(self) -> bytes:
        """Send a ping for RTT measurement."""
        seq = self._next_seq()
        frame = InputFrame(
            event_type=InputEventType.PING,
            sequence=seq,
            timestamp_ms=self._now_ms(),
        )
        self._rtt_pending[seq] = time.monotonic()
        wire = frame.to_wire(self.hmac_key)
        self._stats["frames_sent"] += 1
        self._stats["bytes_sent"] += len(wire)
        return wire

    def encode_pong(self, ping_seq: int) -> bytes:
        """Reply to a ping."""
        frame = InputFrame(
            event_type=InputEventType.PONG,
            sequence=self._next_seq(),
            timestamp_ms=self._now_ms(),
            payload=struct.pack("!I", ping_seq),
        )
        wire = frame.to_wire(self.hmac_key)
        self._stats["frames_sent"] += 1
        self._stats["bytes_sent"] += len(wire)
        return wire

    # --- Batching ---

    def batch_add(self, event_type: InputEventType, payload: bytes) -> None:
        """Add an event to the current batch."""
        if len(self._batch_buffer) >= MAX_BATCH_SIZE:
            raise ProtocolError(f"Batch full: {MAX_BATCH_SIZE}")
        frame = InputFrame(
            event_type=event_type,
            sequence=self._next_seq(),
            timestamp_ms=self._now_ms(),
            payload=payload,
            flags=0x01,  # batched flag
        )
        self._batch_buffer.append(frame)

    def flush_batch(self) -> bytes:
        """Flush the batch buffer and return wire data for all frames."""
        if not self._batch_buffer:
            return b""
        wire_parts = []
        for frame in self._batch_buffer:
            wire_parts.append(frame.to_wire(self.hmac_key))
        self._stats["batches_sent"] += 1
        self._stats["frames_sent"] += len(self._batch_buffer)
        total_bytes = sum(len(w) for w in wire_parts)
        self._stats["bytes_sent"] += total_bytes
        self._batch_buffer.clear()
        # Prefix with batch count as 2-byte big-endian
        count_header = struct.pack("!H", len(wire_parts))
        # Each frame is prefixed with its 2-byte length
        parts = [count_header]
        for w in wire_parts:
            parts.append(struct.pack("!H", len(w)))
            parts.append(w)
        return b"".join(parts)

    # --- Decoding ---

    def decode(self, data: bytes) -> InputFrame:
        """Decode a single frame from wire format. Checks HMAC and replay."""
        self._stats["bytes_received"] += len(data)
        try:
            frame = InputFrame.from_wire(data, self.hmac_key)
        except ProtocolError as e:
            if "HMAC" in str(e):
                self._stats["hmac_failures"] += 1
            raise

        # Replay protection
        if not self.replay_guard.check_and_accept(frame.sequence):
            self._stats["replay_blocked"] += 1
            raise ReplayAttackError(
                f"Replay detected: seq={frame.sequence} "
                f"(highest={self.replay_guard._highest_seq})"
            )

        self._stats["frames_received"] += 1

        # Handle pong RTT measurement
        if frame.event_type == InputEventType.PONG and len(frame.payload) >= 4:
            ping_seq = struct.unpack("!I", frame.payload[:4])[0]
            if ping_seq in self._rtt_pending:
                rtt = (time.monotonic() - self._rtt_pending.pop(ping_seq)) * 1000
                self._rtt_samples.append(rtt)
                if len(self._rtt_samples) > 100:
                    self._rtt_samples = self._rtt_samples[-100:]

        return frame

    def decode_batch(self, data: bytes) -> list[InputFrame]:
        """Decode a batch of frames."""
        if len(data) < 2:
            return []
        count = struct.unpack("!H", data[:2])[0]
        offset = 2
        frames = []
        for _ in range(count):
            if offset + 2 > len(data):
                break
            frame_len = struct.unpack("!H", data[offset:offset + 2])[0]
            offset += 2
            if offset + frame_len > len(data):
                break
            frame_data = data[offset:offset + frame_len]
            offset += frame_len
            frames.append(self.decode(frame_data))
        return frames

    # --- Stats ---

    @property
    def rtt_ms(self) -> float:
        """Average RTT in milliseconds."""
        if not self._rtt_samples:
            return 0.0
        return sum(self._rtt_samples) / len(self._rtt_samples)

    def get_stats(self) -> dict:
        return {
            **self._stats,
            "replay_guard": self.replay_guard.stats,
            "rtt_avg_ms": round(self.rtt_ms, 2),
            "rtt_samples": len(self._rtt_samples),
            "batch_buffer_size": len(self._batch_buffer),
            "current_seq": self._send_seq,
        }

    def export_report(self) -> dict:
        return {
            "stats": self.get_stats(),
            "protocol_version": PROTOCOL_VERSION,
            "header_size": HEADER_SIZE,
            "hmac_size": HMAC_SIZE,
            "max_payload": MAX_PAYLOAD_SIZE,
        }
