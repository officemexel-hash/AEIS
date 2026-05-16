from __future__ import annotations

from dataclasses import asdict, is_dataclass


class FrozenSet:
    def __init__(self, values: set[object] | frozenset[object]):
        self._values = frozenset(values)

    def __contains__(self, item: object) -> bool:
        return item in self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def ratio_of(self, other: "FrozenSet") -> float:
        if len(other) == 0:
            return 0.0
        return len(self._values & other._values) / len(other)


def deduplicate_by_key(items: list[dict], key: str) -> list[dict]:
    seen: set[object] = set()
    unique_items: list[dict] = []

    for item in items:
        value = item[key]
        if value in seen:
            continue
        seen.add(value)
        unique_items.append(item)

    return unique_items


def dataclass_to_dict_recursive(obj) -> dict:
    def convert(value):
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return convert(value.to_dict())
        if is_dataclass(value):
            return {k: convert(v) for k, v in asdict(value).items()}
        if isinstance(value, dict):
            return {k: convert(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [convert(v) for v in value]
        return value

    return convert(obj)
