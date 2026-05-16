"""Numeric range validators."""
from __future__ import annotations


def require_in_range(value: float, lo: float | None, hi: float | None,
                     field_name: str) -> None:
    """Require lo <= value <= hi (inclusive on both sides)."""
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric, got {type(value).__name__}")
    if lo is not None and value < lo:
        raise ValueError(f"{field_name} must be >= {lo}, got {value}")
    if hi is not None and value > hi:
        raise ValueError(f"{field_name} must be <= {hi}, got {value}")


def require_positive(value: float, field_name: str) -> None:
    """Require value > 0."""
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"{field_name} must be > 0, got {value}")
