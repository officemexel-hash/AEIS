from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PurgeDecisionLog:
    user_id: str
    ts: float
    actor: str
    reason: str

    def to_jsonl_line(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_jsonl_line(cls, s: str) -> "PurgeDecisionLog":
        return cls(**json.loads(s))


def log_purge(user_id: str, ts: float, actor: str, reason: str) -> PurgeDecisionLog:
    return PurgeDecisionLog(user_id=user_id, ts=ts, actor=actor, reason=reason)
