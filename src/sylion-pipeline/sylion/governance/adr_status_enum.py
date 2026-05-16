from __future__ import annotations

from enum import Enum


class AdrStatusEnum(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
