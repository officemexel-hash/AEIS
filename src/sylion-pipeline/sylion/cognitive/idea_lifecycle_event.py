from __future__ import annotations

import time


def make_lifecycle_event(
    idea_id: str,
    from_state: str,
    to_state: str,
    actor: str,
    ts: float | None = None,
) -> dict:
    return {
        "idea_id": idea_id,
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "ts": time.time() if ts is None else ts,
    }
