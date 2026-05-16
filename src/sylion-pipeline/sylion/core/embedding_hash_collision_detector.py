from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Collision:
    hash: str
    texts: list[str]


class EmbeddingHashCollisionDetector:
    def check(self, texts: list[str]) -> list[Collision]:
        groups: dict[str, list[str]] = {}
        for text in texts:
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            groups.setdefault(key, []).append(text)
        return [
            Collision(hash=key, texts=group)
            for key, group in groups.items()
            if len(group) > 1
        ]
