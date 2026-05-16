"""Pydantic request/response models for the mobile gateway REST surface."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CardListResponse(BaseModel):
    cards: list[dict[str, Any]] = Field(default_factory=list)
    next_cursor: Optional[str] = None
    total: int = 0


class CardActionRequest(BaseModel):
    action: str
    operator_note: Optional[str] = None
    modified_recommendation: Optional[str] = None


class CardActionResponse(BaseModel):
    card_id: str
    action: str
    accepted: bool
    biometric_required: bool = False


class ProjectListResponse(BaseModel):
    projects: list[dict[str, Any]] = Field(default_factory=list)


class LifecyclePhase(BaseModel):
    hook: str
    phase_index: int
    status: str = "pending"


class ProjectLifecycleResponse(BaseModel):
    project_id: str
    phases: list[LifecyclePhase] = Field(default_factory=list)


class HumanGateTicketSummary(BaseModel):
    ticket_id: str
    title: str
    pending_since: float
    d_level: str = "D0"


class HumanGateListResponse(BaseModel):
    tickets: list[HumanGateTicketSummary] = Field(default_factory=list)


class HumanGateDecisionRequest(BaseModel):
    decision: str
    reviewer: str
    reason: Optional[str] = None


class FundingDeadlinesResponse(BaseModel):
    deadlines: list[dict[str, Any]] = Field(default_factory=list)


class PreferenceListResponse(BaseModel):
    operator_id: str
    preferences: dict[str, Any] = Field(default_factory=dict)


class PreferenceValueResponse(BaseModel):
    key: str
    value: Any
    source: str = "default"


class PreferencePutRequest(BaseModel):
    value: Any


class SyncSnapshotResponse(BaseModel):
    operator_id: str
    cards: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    human_gate_pending: list[HumanGateTicketSummary] = Field(default_factory=list)
    funding_deadlines: list[dict[str, Any]] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=dict)
    snapshot_taken_at: float = 0.0


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
