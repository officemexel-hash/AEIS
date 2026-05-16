"""Enum-membership validators."""
from __future__ import annotations

from enum import Enum
from typing import Iterable


def _normalize(value: object) -> object:
    """Convert Enum -> its .value, leave other types as-is."""
    if isinstance(value, Enum):
        return value.value
    return value


def require_enum_value(value: object, enum_cls: type[Enum], field_name: str) -> None:
    """Require value (str or Enum) to be a member of enum_cls."""
    norm = _normalize(value)
    valid = tuple(member.value for member in enum_cls)
    if norm not in valid:
        raise ValueError(
            f"{field_name} must be one of {valid}, got: {value!r}"
        )


def require_enum_subset(values: Iterable[object], enum_cls: type[Enum],
                        field_name: str, allow_empty: bool = False) -> None:
    """Require all elements of an iterable to be members of enum_cls."""
    materialized = list(values)
    if not materialized and not allow_empty:
        raise ValueError(f"{field_name} must be a non-empty subset of {enum_cls.__name__}")
    valid = tuple(member.value for member in enum_cls)
    for v in materialized:
        if _normalize(v) not in valid:
            raise ValueError(
                f"{field_name} contains invalid value {v!r}; must be in {valid}"
            )
