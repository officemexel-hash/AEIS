"""SYLION Core Kernel - module registry, contracts, event bus, decision engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from sylion.core.bundle_assembler import (
    BundleAssembler,
    get_bundle_assembler,
    reset_bundle_assembler,
)
from sylion.core.contract_registry import (
    ContractRegistry,
    get_contract_registry,
    reset_contract_registry,
)
from sylion.core.embedding_hash_collision_detector import (
    Collision,
    EmbeddingHashCollisionDetector,
)


def deduplicate_by_key(items: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Return items keeping the first record for each value of ``key``."""
    seen: set[Any] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        value = item.get(key)
        if value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


@dataclass(frozen=True)
class FrozenSet:
    """Small wrapper used by legacy core tests for overlap ratios."""

    values: frozenset[Any]

    def __init__(self, values: Iterable[Any]):
        object.__setattr__(self, "values", frozenset(values))

    def __contains__(self, item: Any) -> bool:
        return item in self.values

    def __iter__(self):
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def ratio_of(self, other: "FrozenSet") -> float:
        if len(other) == 0:
            return 0.0
        return len(self.values.intersection(other.values)) / len(other)


@dataclass(frozen=True)
class TimeWindow:
    start: float
    end: float

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("end must be greater than or equal to start")

    @property
    def duration_seconds(self) -> float:
        return self.end - self.start

    def contains(self, timestamp: float) -> bool:
        return self.start <= timestamp <= self.end

    def overlaps_with(self, other: "TimeWindow") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass
class RateLimitTracker:
    _calls: dict[str, list[float]] = field(default_factory=dict)

    def record_call(self, node_id: str, timestamp: float) -> None:
        self._calls.setdefault(node_id, []).append(float(timestamp))

    def is_over_limit(self, node_id: str, *, window_seconds: float, max_count: int) -> bool:
        if window_seconds < 0:
            raise ValueError("window_seconds must be non-negative")
        if max_count < 0:
            raise ValueError("max_count must be non-negative")
        calls = self._calls.get(node_id, [])
        if not calls:
            return False
        newest = max(calls)
        cutoff = newest - window_seconds
        kept = [ts for ts in calls if ts >= cutoff]
        self._calls[node_id] = kept
        return len(kept) > max_count


__all__ = [
    "ContractRegistry",
    "get_contract_registry",
    "reset_contract_registry",
    "BundleAssembler",
    "get_bundle_assembler",
    "reset_bundle_assembler",
    "Collision",
    "EmbeddingHashCollisionDetector",
    "deduplicate_by_key",
    "FrozenSet",
    "TimeWindow",
    "RateLimitTracker",
]
