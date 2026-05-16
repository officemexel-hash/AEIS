from __future__ import annotations

import hashlib
import json


class AuditEventChain:
    def __init__(self):
        self.events: list[dict] = []

    def append(self, content: dict) -> dict:
        prev_hash = self.events[-1]["content_hash"] if self.events else ""
        raw = f"{prev_hash}{json.dumps(content, sort_keys=True)}".encode()
        event = {
            "prev_hash": prev_hash,
            "content": content,
            "content_hash": hashlib.sha256(raw).hexdigest(),
        }
        self.events.append(event)
        return event

    def verify(self) -> bool:
        prev_hash = ""
        for event in self.events:
            raw = f"{prev_hash}{json.dumps(event['content'], sort_keys=True)}".encode()
            if event["prev_hash"] != prev_hash:
                return False
            if hashlib.sha256(raw).hexdigest() != event["content_hash"]:
                return False
            prev_hash = event["content_hash"]
        return True
