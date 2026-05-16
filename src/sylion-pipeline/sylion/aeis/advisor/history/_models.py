"""Dataclass models for the history module.

Map 1:1 to the canonical PG schema in `02_postgresql_schema.sql`:
- `CardAction` -> `advisor_history.card_actions`
- `LearningSignal` -> `advisor_history.learning_signals`

Type translations for SQLite MVP:
  UUID  -> TEXT
  JSONB -> TEXT (JSON-encoded)
  ENUM  -> TEXT (validated at app layer)
  TIMESTAMPTZ -> REAL (epoch seconds)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


CARD_ACTIONS = (
    "accept",
    "reject",
    "modify",
    "remind_later",
    "not_useful",
    "convert_to_human_gate",
    "convert_to_masterplan_change",
    "save_as_preference",
    "dont_learn_from_this",
)

SIGNAL_TYPES = (
    "card_acceptance",
    "card_rejection",
    "preference_save",
    "pattern_match",
    "dont_learn_flag",
)


def new_uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class CardAction:
    """Append-only operator interaction record."""

    action_event_id: str = field(default_factory=new_uuid)
    card_id: str = ""
    operator_id: str = ""
    action: str = "accept"
    operator_note: str = ""
    modified_recommendation: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    created_human_gate_ticket_id: str = ""
    created_masterplan_proposal_id: str = ""
    saved_preference_id: str = ""
    triggered_soft_learning: bool = False
    triggered_hard_learning_request: bool = False
    performed_at: float = field(default_factory=time.time)


@dataclass
class LearningSignal:
    """Aggregated input to soft / hard learning."""

    signal_id: str = field(default_factory=new_uuid)
    operator_id: str = ""
    signal_type: str = "card_acceptance"
    preference_key: str = ""
    context_project_type: str = ""
    context_project_domain: str = ""
    signal_strength: float = 0.0
    source_card_id: str = ""
    source_action_event_id: str = ""
    applied_to_preference: bool = False
    applied_at: float | None = None
    created_at: float = field(default_factory=time.time)
    # Hard learning lifecycle (not in canonical PG schema; tracked for MVP only).
    hard_change_status: str = ""  # '' | 'pending' | 'confirmed' | 'rejected'


@dataclass
class ConfidenceSnapshot:
    """Returned to the engine for the 4-component confidence formula."""

    similar_accepted_count: int = 0
    similar_rejected_count: int = 0
    similar_acceptance_rate: float = 0.0
    operator_accepted_count: int = 0
    operator_rejected_count: int = 0
    operator_acceptance_rate_for_type: float = 0.0
