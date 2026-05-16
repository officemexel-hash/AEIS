from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionStateSnapshot:
    snapshot_id: str
    ts: float
    state_keys: list[str]
    state_hash: str

    @classmethod
    def capture(cls, session: dict) -> "SessionStateSnapshot":
        payload = json.dumps(session, sort_keys=True)
        return cls(
            snapshot_id=uuid.uuid4().hex,
            ts=time.time(),
            state_keys=sorted(session.keys()),
            state_hash=hashlib.sha256(payload.encode()).hexdigest()[:16],
        )
