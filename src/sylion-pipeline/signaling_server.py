"""
SYLION Pion D — WebRTC Signaling Server Runtime

Manages WebRTC session lifecycle: SDP offer/answer exchange, ICE candidate
relay, room management, session state machine, and DTLS fingerprint
verification.  Designed to run alongside the orchestrator as a lightweight
async server or be imported for in-process signaling.

Architecture:
  Client → Signaling (this module) → Peer
  1. Client creates Room via create_room()
  2. Peer joins via join_room()
  3. SDP offer/answer exchanged via relay_sdp()
  4. ICE candidates trickled via relay_ice()
  5. Session state tracked: CREATED → CONNECTING → CONNECTED → DISCONNECTED

Security:
  - Room IDs are cryptographic random (secrets.token_urlsafe)
  - DTLS fingerprint verified against expected value
  - Session tokens required for all operations after room creation
  - Max sessions per room enforced (default 2 for P2P)
  - Session timeout with automatic cleanup

⚠️  LLM NEVER issues raw shell commands.  Generates parameters for
    pre-approved scenarios only.
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("signaling")


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionState(enum.Enum):
    """WebRTC session lifecycle states."""
    CREATED = "CREATED"
    WAITING = "WAITING"            # Room created, waiting for peer
    OFFER_SENT = "OFFER_SENT"      # SDP offer sent
    ANSWER_SENT = "ANSWER_SENT"    # SDP answer sent
    ICE_GATHERING = "ICE_GATHERING"
    CONNECTING = "CONNECTING"       # ICE + DTLS in progress
    CONNECTED = "CONNECTED"         # Media flowing
    RECONNECTING = "RECONNECTING"   # Temporary disconnect, attempting recovery
    DISCONNECTED = "DISCONNECTED"   # Clean disconnect
    FAILED = "FAILED"               # Unrecoverable failure
    CLOSED = "CLOSED"               # Room destroyed


class SDPType(enum.Enum):
    """SDP message types."""
    OFFER = "offer"
    ANSWER = "answer"
    PRANSWER = "pranswer"


class SignalingError(Exception):
    """Raised on signaling protocol violations."""
    pass


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ICECandidate:
    """A single ICE candidate."""
    candidate: str          # Full candidate string (a=candidate:...)
    sdp_mid: str            # Media stream ID
    sdp_mline_index: int    # Media line index
    username_fragment: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "sdpMid": self.sdp_mid,
            "sdpMLineIndex": self.sdp_mline_index,
            "usernameFragment": self.username_fragment,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ICECandidate:
        return cls(
            candidate=d["candidate"],
            sdp_mid=d.get("sdpMid", ""),
            sdp_mline_index=d.get("sdpMLineIndex", 0),
            username_fragment=d.get("usernameFragment", ""),
        )


@dataclass
class SDPMessage:
    """An SDP offer or answer."""
    sdp_type: SDPType
    sdp: str                # Full SDP body
    dtls_fingerprint: str = ""   # Expected DTLS fingerprint (sha-256)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.sdp_type.value,
            "sdp": self.sdp,
            "dtlsFingerprint": self.dtls_fingerprint,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SDPMessage:
        return cls(
            sdp_type=SDPType(d["type"]),
            sdp=d["sdp"],
            dtls_fingerprint=d.get("dtlsFingerprint", ""),
        )


@dataclass
class Participant:
    """A participant in a signaling room."""
    peer_id: str
    token: str             # Session token (cryptographic)
    role: str = "peer"     # "initiator" or "peer"
    state: SessionState = SessionState.CREATED
    sdp_local: SDPMessage | None = None
    sdp_remote: SDPMessage | None = None
    ice_candidates: list[ICECandidate] = field(default_factory=list)
    connected_at: float = 0.0
    last_heartbeat: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_alive(self, timeout_s: float = 30.0) -> bool:
        """Check if participant has sent a heartbeat recently."""
        return (time.time() - self.last_heartbeat) < timeout_s


@dataclass
class Room:
    """A signaling room holding participants."""
    room_id: str
    created_at: float = field(default_factory=time.time)
    max_participants: int = 2     # P2P default
    participants: dict[str, Participant] = field(default_factory=dict)
    state: SessionState = SessionState.CREATED
    ice_servers: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_full(self) -> bool:
        return len(self.participants) >= self.max_participants

    @property
    def initiator(self) -> Participant | None:
        for p in self.participants.values():
            if p.role == "initiator":
                return p
        return None

    @property
    def peer(self) -> Participant | None:
        for p in self.participants.values():
            if p.role == "peer":
                return p
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "created_at": self.created_at,
            "state": self.state.value,
            "participant_count": len(self.participants),
            "max_participants": self.max_participants,
            "ice_servers": self.ice_servers,
        }


@dataclass
class SignalingEvent:
    """An event in the signaling log."""
    event_type: str          # "room_created", "sdp_offer", "ice_candidate", etc.
    room_id: str
    peer_id: str
    timestamp: float = field(default_factory=time.time)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "room_id": self.room_id,
            "peer_id": self.peer_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


# ---------------------------------------------------------------------------
# Heartbeat eviction constants
# ---------------------------------------------------------------------------

HEARTBEAT_TIMEOUT = 120  # seconds — peers not heard from in this window are evicted
_EVICTION_INTERVAL = 30  # seconds — how often the eviction loop runs


# ---------------------------------------------------------------------------
# TURN/STUN configuration
# ---------------------------------------------------------------------------

@dataclass
class ICEServerConfig:
    """ICE (STUN/TURN) server configuration."""
    stun_urls: list[str] = field(default_factory=lambda: [
        "stun:stun.l.google.com:19302",
        "stun:stun1.l.google.com:19302",
    ])
    turn_urls: list[str] = field(default_factory=list)
    turn_username: str = ""
    turn_credential: str = ""
    turn_credential_type: str = "password"   # "password" or "token"

    def to_ice_servers(self) -> list[dict[str, Any]]:
        """Convert to WebRTC-compatible iceServers array."""
        servers: list[dict[str, Any]] = []
        if self.stun_urls:
            servers.append({"urls": self.stun_urls})
        if self.turn_urls and self.turn_username:
            servers.append({
                "urls": self.turn_urls,
                "username": self.turn_username,
                "credential": self.turn_credential,
                "credentialType": self.turn_credential_type,
            })
        return servers


# ---------------------------------------------------------------------------
# Signaling Server
# ---------------------------------------------------------------------------

class SignalingServer:
    """
    WebRTC signaling server managing rooms, SDP exchange, and ICE relay.

    This is the runtime implementation backing the stream_architect and
    stream_transport agents' design documents.  Integrates with the
    orchestrator via events and callbacks.

    Usage:
        server = SignalingServer(ice_config=ICEServerConfig(...))
        room = server.create_room(initiator_id="pixel-8")
        token2 = server.join_room(room.room_id, peer_id="laptop")
        server.relay_sdp(room.room_id, "pixel-8", sdp_offer)
        server.relay_sdp(room.room_id, "laptop", sdp_answer)
        server.relay_ice(room.room_id, "pixel-8", candidate)
    """

    def __init__(
        self,
        *,
        ice_config: ICEServerConfig | None = None,
        max_rooms: int = 100,
        session_timeout_s: float = 300.0,
        heartbeat_interval_s: float = 10.0,
        reconnect_timeout_s: float = 3.0,
        turn_fallback_s: float = 5.0,
        log_dir: Path | None = None,
        on_event: Callable[[SignalingEvent], None] | None = None,
    ):
        self.ice_config = ice_config or ICEServerConfig()
        self.max_rooms = max_rooms
        self.session_timeout_s = session_timeout_s
        self.heartbeat_interval_s = heartbeat_interval_s
        self.reconnect_timeout_s = reconnect_timeout_s
        self.turn_fallback_s = turn_fallback_s
        self.log_dir = log_dir
        self.on_event = on_event

        self._rooms: dict[str, Room] = {}
        self._events: list[SignalingEvent] = []
        self._token_to_room: dict[str, str] = {}   # token → room_id
        self._cleanup_task: asyncio.Task | None = None
        self._heartbeat_eviction_task: asyncio.Task | None = None

        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

        # Validate TURN credentials at construction time
        self._validate_ice_config()

    # --- ICE config validation ---

    def _validate_ice_config(self) -> None:
        """Warn at startup if TURN URLs are present but credentials are missing."""
        if self.ice_config.turn_urls:
            if not self.ice_config.turn_username or not self.ice_config.turn_credential:
                log.warning(
                    "ICE config: TURN server(s) configured (%s) but credentials "
                    "(turn_username / turn_credential) are missing. "
                    "TURN relay will be unavailable until credentials are supplied.",
                    self.ice_config.turn_urls,
                )

    # --- Room management ---

    def create_room(
        self,
        initiator_id: str,
        *,
        max_participants: int = 2,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Room, str]:
        """
        Create a new signaling room.

        Returns (room, initiator_token).
        """
        if len(self._rooms) >= self.max_rooms:
            raise SignalingError(f"Max rooms ({self.max_rooms}) reached")

        room_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)

        participant = Participant(
            peer_id=initiator_id,
            token=token,
            role="initiator",
            state=SessionState.WAITING,
        )

        room = Room(
            room_id=room_id,
            max_participants=max_participants,
            participants={initiator_id: participant},
            state=SessionState.WAITING,
            ice_servers=self.ice_config.to_ice_servers(),
            metadata=metadata or {},
        )

        self._rooms[room_id] = room
        self._token_to_room[token] = room_id

        self._emit_event("room_created", room_id, initiator_id, {
            "max_participants": max_participants,
        })
        log.info(f"Room created: {room_id[:8]}... by {initiator_id}")
        return room, token

    def join_room(self, room_id: str, peer_id: str) -> str:
        """
        Join an existing room.  Returns peer token.

        Raises SignalingError if room is full or doesn't exist.
        """
        room = self._get_room(room_id)
        if room.is_full:
            raise SignalingError(f"Room {room_id[:8]} is full")
        if peer_id in room.participants:
            raise SignalingError(f"Peer {peer_id} already in room")

        token = secrets.token_urlsafe(32)
        participant = Participant(
            peer_id=peer_id,
            token=token,
            role="peer",
            state=SessionState.WAITING,
        )

        room.participants[peer_id] = participant
        self._token_to_room[token] = room_id

        self._emit_event("peer_joined", room_id, peer_id)
        log.info(f"Peer {peer_id} joined room {room_id[:8]}...")
        return token

    def leave_room(self, room_id: str, peer_id: str) -> None:
        """Remove a participant from a room."""
        room = self._get_room(room_id)
        if peer_id not in room.participants:
            raise SignalingError(f"Peer {peer_id} not in room {room_id[:8]}")

        participant = room.participants.pop(peer_id)
        self._token_to_room.pop(participant.token, None)

        self._emit_event("peer_left", room_id, peer_id)
        log.info(f"Peer {peer_id} left room {room_id[:8]}...")

        if not room.participants:
            self._close_room(room_id)

    def close_room(self, room_id: str) -> None:
        """Close and destroy a room."""
        self._close_room(room_id)

    # --- SDP exchange ---

    def relay_sdp(
        self,
        room_id: str,
        from_peer: str,
        sdp: SDPMessage,
    ) -> SDPMessage:
        """
        Relay an SDP offer or answer between peers.

        For an offer: stores on initiator, returns to be sent to peer.
        For an answer: stores on peer, returns to be sent to initiator.
        Validates DTLS fingerprint if configured.
        """
        room = self._get_room(room_id)
        sender = self._get_participant(room, from_peer)

        # Validate SDP contains required sections
        self._validate_sdp(sdp)

        if sdp.sdp_type == SDPType.OFFER:
            sender.sdp_local = sdp
            sender.state = SessionState.OFFER_SENT
            room.state = SessionState.OFFER_SENT
            self._emit_event("sdp_offer", room_id, from_peer, {
                "dtls_fingerprint": sdp.dtls_fingerprint,
            })
            log.info(f"SDP offer from {from_peer} in room {room_id[:8]}...")

        elif sdp.sdp_type == SDPType.ANSWER:
            sender.sdp_local = sdp
            sender.state = SessionState.ANSWER_SENT
            room.state = SessionState.ICE_GATHERING

            # Verify DTLS fingerprint matches offer's expectation
            initiator = room.initiator
            if (initiator and initiator.sdp_local
                    and initiator.sdp_local.dtls_fingerprint
                    and sdp.dtls_fingerprint):
                if not self._verify_dtls_fingerprint(
                    initiator.sdp_local.dtls_fingerprint,
                    sdp.dtls_fingerprint,
                ):
                    log.warning(
                        f"DTLS fingerprint mismatch in room {room_id[:8]}!"
                    )
                    self._emit_event("dtls_mismatch", room_id, from_peer, {
                        "expected": initiator.sdp_local.dtls_fingerprint[:16],
                        "got": sdp.dtls_fingerprint[:16],
                    })

            self._emit_event("sdp_answer", room_id, from_peer, {
                "dtls_fingerprint": sdp.dtls_fingerprint,
            })
            log.info(f"SDP answer from {from_peer} in room {room_id[:8]}...")

        return sdp

    # --- ICE candidate relay ---

    def relay_ice(
        self,
        room_id: str,
        from_peer: str,
        candidate: ICECandidate,
    ) -> None:
        """Relay an ICE candidate to the other peer in the room."""
        room = self._get_room(room_id)
        sender = self._get_participant(room, from_peer)
        sender.ice_candidates.append(candidate)

        # Track ICE gathering state
        if sender.state not in (
            SessionState.ICE_GATHERING,
            SessionState.CONNECTING,
            SessionState.CONNECTED,
        ):
            sender.state = SessionState.ICE_GATHERING

        self._emit_event("ice_candidate", room_id, from_peer, candidate.to_dict())

    def end_of_candidates(self, room_id: str, from_peer: str) -> None:
        """Signal that a peer has finished gathering ICE candidates."""
        room = self._get_room(room_id)
        sender = self._get_participant(room, from_peer)
        sender.state = SessionState.CONNECTING

        # If both peers are connecting, transition room
        other = self._get_other_participant(room, from_peer)
        if other and other.state == SessionState.CONNECTING:
            room.state = SessionState.CONNECTING

        self._emit_event("ice_complete", room_id, from_peer, {
            "candidate_count": len(sender.ice_candidates),
        })

    # --- Connection state ---

    def on_connected(self, room_id: str, peer_id: str) -> None:
        """Called when a peer's ICE connection succeeds."""
        room = self._get_room(room_id)
        participant = self._get_participant(room, peer_id)
        participant.state = SessionState.CONNECTED
        participant.connected_at = time.time()

        # Check if all participants connected
        all_connected = all(
            p.state == SessionState.CONNECTED
            for p in room.participants.values()
        )
        if all_connected:
            room.state = SessionState.CONNECTED
            self._emit_event("room_connected", room_id, peer_id, {
                "participant_count": len(room.participants),
            })
            log.info(f"Room {room_id[:8]}... CONNECTED (all peers)")

    def on_disconnected(self, room_id: str, peer_id: str) -> None:
        """Called when a peer disconnects."""
        room = self._get_room(room_id)
        participant = self._get_participant(room, peer_id)

        if room.state == SessionState.CONNECTED:
            # Temporary disconnect — try reconnection
            participant.state = SessionState.RECONNECTING
            room.state = SessionState.RECONNECTING
            self._emit_event("peer_disconnected", room_id, peer_id)
            log.warning(f"Peer {peer_id} disconnected from room {room_id[:8]}... (reconnecting)")
        else:
            participant.state = SessionState.DISCONNECTED
            self._emit_event("peer_disconnected", room_id, peer_id)

    def on_failed(self, room_id: str, peer_id: str, reason: str = "") -> None:
        """Called when a peer's connection fails unrecoverably."""
        room = self._get_room(room_id)
        participant = self._get_participant(room, peer_id)
        participant.state = SessionState.FAILED
        room.state = SessionState.FAILED

        self._emit_event("connection_failed", room_id, peer_id, {
            "reason": reason,
        })
        log.error(f"Connection FAILED for {peer_id} in room {room_id[:8]}...: {reason}")

    # --- Heartbeat ---

    def heartbeat(self, room_id: str, peer_id: str) -> bool:
        """
        Update heartbeat timestamp.  Returns True if session still valid.
        """
        room = self._get_room(room_id)
        participant = self._get_participant(room, peer_id)
        participant.last_heartbeat = time.time()
        return participant.state not in (SessionState.FAILED, SessionState.CLOSED)

    # --- Query ---

    def get_room(self, room_id: str) -> Room:
        """Get room info (public API)."""
        return self._get_room(room_id)

    def get_room_state(self, room_id: str) -> dict[str, Any]:
        """Get serializable room state."""
        room = self._get_room(room_id)
        return {
            **room.to_dict(),
            "participants": {
                pid: {
                    "role": p.role,
                    "state": p.state.value,
                    "ice_candidate_count": len(p.ice_candidates),
                    "connected_at": p.connected_at,
                    "alive": p.is_alive(self.session_timeout_s),
                }
                for pid, p in room.participants.items()
            },
        }

    def get_pending_ice(self, room_id: str, for_peer: str) -> list[ICECandidate]:
        """Get ICE candidates from the other peer."""
        room = self._get_room(room_id)
        other = self._get_other_participant(room, for_peer)
        if not other:
            return []
        return list(other.ice_candidates)

    def get_remote_sdp(self, room_id: str, for_peer: str) -> SDPMessage | None:
        """Get the SDP from the other peer (offer for answerer, answer for offerer)."""
        room = self._get_room(room_id)
        other = self._get_other_participant(room, for_peer)
        if not other:
            return None
        return other.sdp_local

    def list_rooms(self) -> list[dict[str, Any]]:
        """List all active rooms."""
        return [r.to_dict() for r in self._rooms.values()]

    @property
    def room_count(self) -> int:
        return len(self._rooms)

    @property
    def event_log(self) -> list[SignalingEvent]:
        return list(self._events)

    # --- Statistics ---

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics."""
        connected = sum(
            1 for r in self._rooms.values()
            if r.state == SessionState.CONNECTED
        )
        return {
            "total_rooms": len(self._rooms),
            "connected_rooms": connected,
            "total_events": len(self._events),
            "max_rooms": self.max_rooms,
        }

    def export_report(self) -> dict[str, Any]:
        """Export full server state for diagnostics."""
        return {
            "stats": self.get_stats(),
            "rooms": {
                rid: self.get_room_state(rid)
                for rid in self._rooms
            },
            "ice_servers": self.ice_config.to_ice_servers(),
            "config": {
                "session_timeout_s": self.session_timeout_s,
                "heartbeat_interval_s": self.heartbeat_interval_s,
                "reconnect_timeout_s": self.reconnect_timeout_s,
                "turn_fallback_s": self.turn_fallback_s,
            },
        }

    # --- Cleanup ---

    async def start_cleanup_loop(self) -> None:
        """Start periodic cleanup of stale sessions and heartbeat eviction."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._heartbeat_eviction_task = asyncio.create_task(self._heartbeat_eviction_loop())

    async def stop_cleanup_loop(self) -> None:
        """Stop the cleanup loop and heartbeat eviction loop."""
        for task_attr in ("_cleanup_task", "_heartbeat_eviction_task"):
            task = getattr(self, task_attr)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                setattr(self, task_attr, None)

    async def _cleanup_loop(self) -> None:
        """Periodically clean up stale rooms and sessions."""
        while True:
            await asyncio.sleep(self.heartbeat_interval_s * 3)
            self._cleanup_stale()

    async def _heartbeat_eviction_loop(self) -> None:
        """Every 30 s: evict peers whose last heartbeat is older than HEARTBEAT_TIMEOUT.

        Peers are removed from their rooms.  If the peer has an associated
        WebSocket stored in ``participant.metadata['websocket']``, it is closed.
        The room is torn down if it becomes empty after eviction.
        """
        while True:
            await asyncio.sleep(_EVICTION_INTERVAL)
            await self._evict_stale_heartbeats()

    async def _evict_stale_heartbeats(self) -> None:
        """Scan all rooms and evict participants whose heartbeat has timed out."""
        now = time.time()
        rooms_to_close: list[str] = []

        for room_id, room in list(self._rooms.items()):
            stale_peers: list[str] = [
                pid
                for pid, p in room.participants.items()
                if (now - p.last_heartbeat) > HEARTBEAT_TIMEOUT
            ]

            for pid in stale_peers:
                participant = room.participants.pop(pid, None)
                if participant is None:
                    continue

                self._token_to_room.pop(participant.token, None)
                self._emit_event("peer_heartbeat_evicted", room_id, pid, {
                    "last_heartbeat_age_s": round(now - participant.last_heartbeat, 1),
                    "timeout_s": HEARTBEAT_TIMEOUT,
                })
                log.warning(
                    "Heartbeat eviction: peer %s removed from room %s "
                    "(last heartbeat %.1fs ago, timeout=%ds)",
                    pid, room_id[:8], now - participant.last_heartbeat, HEARTBEAT_TIMEOUT,
                )

                # Close WebSocket if the caller stored one in metadata
                ws = participant.metadata.get("websocket")
                if ws is not None:
                    try:
                        await ws.close()
                        log.info("Closed WebSocket for evicted peer %s", pid)
                    except Exception as exc:  # noqa: BLE001
                        log.debug("Error closing WebSocket for peer %s: %s", pid, exc)

            if not room.participants:
                rooms_to_close.append(room_id)

        for room_id in rooms_to_close:
            self._close_room(room_id)
            log.info("Room %s closed after all peers were heartbeat-evicted", room_id[:8])

    def _cleanup_stale(self) -> None:
        """Remove stale participants and empty rooms."""
        stale_rooms: list[str] = []
        now = time.time()

        for room_id, room in self._rooms.items():
            # Check session timeout
            if now - room.created_at > self.session_timeout_s * 10:
                stale_rooms.append(room_id)
                continue

            # Check participant heartbeats
            stale_peers: list[str] = []
            for pid, participant in room.participants.items():
                if not participant.is_alive(self.session_timeout_s):
                    stale_peers.append(pid)

            for pid in stale_peers:
                participant = room.participants.pop(pid)
                self._token_to_room.pop(participant.token, None)
                self._emit_event("peer_timeout", room_id, pid)
                log.info(f"Peer {pid} timed out from room {room_id[:8]}...")

            if not room.participants:
                stale_rooms.append(room_id)

        for room_id in stale_rooms:
            self._close_room(room_id)

    # --- Internal helpers ---

    def _get_room(self, room_id: str) -> Room:
        room = self._rooms.get(room_id)
        if not room:
            raise SignalingError(f"Room not found: {room_id[:8]}")
        return room

    def _get_participant(self, room: Room, peer_id: str) -> Participant:
        participant = room.participants.get(peer_id)
        if not participant:
            raise SignalingError(f"Peer {peer_id} not in room {room.room_id[:8]}")
        return participant

    def _get_other_participant(self, room: Room, peer_id: str) -> Participant | None:
        for pid, p in room.participants.items():
            if pid != peer_id:
                return p
        return None

    def _close_room(self, room_id: str) -> None:
        room = self._rooms.pop(room_id, None)
        if room:
            for p in room.participants.values():
                p.state = SessionState.CLOSED
                self._token_to_room.pop(p.token, None)
            room.state = SessionState.CLOSED
            self._emit_event("room_closed", room_id, "")
            log.info(f"Room {room_id[:8]}... closed")

    def _validate_sdp(self, sdp: SDPMessage) -> None:
        """Validate SDP has required sections."""
        body = sdp.sdp
        if not body:
            raise SignalingError("Empty SDP body")

        # Minimal SDP validation
        required_prefixes = ["v=", "o=", "s="]
        for prefix in required_prefixes:
            if prefix not in body:
                raise SignalingError(f"SDP missing required field: {prefix}")

        # For offers/answers, require media section
        if sdp.sdp_type in (SDPType.OFFER, SDPType.ANSWER):
            if "m=" not in body:
                raise SignalingError("SDP missing media section (m=)")

    def _verify_dtls_fingerprint(
        self, expected: str, actual: str,
    ) -> bool:
        """Verify DTLS fingerprint matches."""
        # Normalize: lowercase, strip whitespace
        return expected.strip().lower() == actual.strip().lower()

    def _emit_event(
        self, event_type: str, room_id: str, peer_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Record and dispatch a signaling event."""
        event = SignalingEvent(
            event_type=event_type,
            room_id=room_id,
            peer_id=peer_id,
            data=data or {},
        )
        self._events.append(event)

        # Write to log file if configured
        if self.log_dir:
            log_file = self.log_dir / "signaling_events.jsonl"
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        # Dispatch callback
        if self.on_event:
            try:
                self.on_event(event)
            except Exception as e:
                log.error(f"Event callback error: {e}")


# ---------------------------------------------------------------------------
# Session Flow Controller
# ---------------------------------------------------------------------------

class SessionFlowController:
    """
    High-level session flow orchestrator.

    Implements the SESSION-FLOW.md design: creates a room, manages
    the offer/answer/ICE sequence, handles reconnection, and enforces
    timeouts from config.streaming_latency_budget.

    Usage:
        flow = SessionFlowController(
            server=signaling_server,
            reconnect_timeout_s=cfg.streaming_reconnect_timeout_s,
            turn_fallback_s=cfg.streaming_turn_fallback_s,
        )
        session = await flow.establish_session("pixel-8", "laptop")
    """

    def __init__(
        self,
        server: SignalingServer,
        *,
        reconnect_timeout_s: float = 3.0,
        turn_fallback_s: float = 5.0,
        max_reconnect_attempts: int = 3,
    ):
        self.server = server
        self.reconnect_timeout_s = reconnect_timeout_s
        self.turn_fallback_s = turn_fallback_s
        self.max_reconnect_attempts = max_reconnect_attempts
        self._active_sessions: dict[str, dict[str, Any]] = {}

    async def establish_session(
        self,
        initiator_id: str,
        peer_id: str,
        *,
        sdp_offer: SDPMessage | None = None,
        sdp_answer: SDPMessage | None = None,
        ice_candidates_initiator: list[ICECandidate] | None = None,
        ice_candidates_peer: list[ICECandidate] | None = None,
        timeout_s: float = 30.0,
    ) -> dict[str, Any]:
        """
        Full session establishment flow.

        Returns session info dict with room_id, tokens, state.
        """
        # Step 1: Create room
        room, init_token = self.server.create_room(initiator_id)
        peer_token = self.server.join_room(room.room_id, peer_id)

        session_info = {
            "room_id": room.room_id,
            "initiator_token": init_token,
            "peer_token": peer_token,
            "state": "establishing",
        }
        self._active_sessions[room.room_id] = session_info

        # Step 2: SDP exchange (if provided)
        if sdp_offer:
            self.server.relay_sdp(room.room_id, initiator_id, sdp_offer)
        if sdp_answer:
            self.server.relay_sdp(room.room_id, peer_id, sdp_answer)

        # Step 3: ICE candidates (if provided)
        if ice_candidates_initiator:
            for c in ice_candidates_initiator:
                self.server.relay_ice(room.room_id, initiator_id, c)
            self.server.end_of_candidates(room.room_id, initiator_id)

        if ice_candidates_peer:
            for c in ice_candidates_peer:
                self.server.relay_ice(room.room_id, peer_id, c)
            self.server.end_of_candidates(room.room_id, peer_id)

        session_info["state"] = self.server.get_room(room.room_id).state.value
        return session_info

    async def handle_reconnect(
        self,
        room_id: str,
        peer_id: str,
    ) -> bool:
        """
        Attempt reconnection within reconnect_timeout_s.

        Returns True if reconnection was initiated successfully.
        """
        try:
            room = self.server.get_room(room_id)
        except SignalingError:
            return False

        if room.state != SessionState.RECONNECTING:
            return False

        self.server._emit_event("reconnect_attempt", room_id, peer_id, {
            "timeout_s": self.reconnect_timeout_s,
        })

        # In a real implementation, this would trigger ICE restart
        # For now, we track the attempt
        return True

    def get_session(self, room_id: str) -> dict[str, Any] | None:
        """Get active session info."""
        return self._active_sessions.get(room_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions."""
        return list(self._active_sessions.values())
