"""Tests for ``sylion.aeis_v2.lifecycle_v2.IdeaLifecycle``.

Locks the canonical 11-state set + transition matrix + audit emission
contract.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.lifecycle_v2 import (
    IDEA_LIFECYCLE_STATES,
    IDEA_LIFECYCLE_TRANSITIONS,
    IdeaLifecycle,
    LifecycleEvent,
    is_terminal,
    is_valid_transition,
)


# ---------------------------------------------------------------------------
# Canonical state set
# ---------------------------------------------------------------------------


def test_canonical_eleven_states() -> None:
    """Exactly 11 states, matching MEMORY.md ``project_idea_lifecycle.md``."""
    assert IDEA_LIFECYCLE_STATES == frozenset({
        "draft", "submitted", "under_review", "approved", "rejected",
        "in_progress", "blocked", "completed", "archived",
        "soft_deleted", "hard_deleted",
    })
    assert len(IDEA_LIFECYCLE_STATES) == 11


def test_transition_matrix_keys_are_canonical() -> None:
    """Every state in the matrix must be one of the canonical 11."""
    assert set(IDEA_LIFECYCLE_TRANSITIONS) == set(IDEA_LIFECYCLE_STATES)


def test_transition_targets_are_canonical() -> None:
    """Every transition target must also be canonical."""
    for from_state, targets in IDEA_LIFECYCLE_TRANSITIONS.items():
        for t in targets:
            assert t in IDEA_LIFECYCLE_STATES, (
                f"{from_state} → {t}: {t} is not canonical"
            )


def test_hard_deleted_is_terminal() -> None:
    """No transitions out of hard_deleted (terminal state)."""
    assert IDEA_LIFECYCLE_TRANSITIONS["hard_deleted"] == frozenset()
    assert is_terminal("hard_deleted") is True


def test_only_hard_deleted_is_terminal() -> None:
    """All other states have at least one outgoing edge."""
    for s in IDEA_LIFECYCLE_STATES:
        if s == "hard_deleted":
            continue
        assert not is_terminal(s), f"{s} should have outgoing transitions"


# ---------------------------------------------------------------------------
# is_valid_transition pure helper
# ---------------------------------------------------------------------------


def test_valid_forward_transitions() -> None:
    assert is_valid_transition("draft", "submitted") is True
    assert is_valid_transition("submitted", "under_review") is True
    assert is_valid_transition("under_review", "approved") is True
    assert is_valid_transition("approved", "in_progress") is True
    assert is_valid_transition("in_progress", "completed") is True
    assert is_valid_transition("completed", "archived") is True


def test_valid_backward_transitions() -> None:
    """Per Kimi k3: backward edges allowed where the runbook says so."""
    assert is_valid_transition("rejected", "under_review") is True
    assert is_valid_transition("submitted", "draft") is True
    assert is_valid_transition("blocked", "in_progress") is True
    assert is_valid_transition("soft_deleted", "archived") is True


def test_invalid_skip_transitions() -> None:
    assert is_valid_transition("draft", "completed") is False
    assert is_valid_transition("draft", "approved") is False
    assert is_valid_transition("submitted", "completed") is False


def test_invalid_self_loop() -> None:
    """A self-transition is never valid."""
    for s in IDEA_LIFECYCLE_STATES:
        assert is_valid_transition(s, s) is False


def test_invalid_unknown_state() -> None:
    assert is_valid_transition("nonexistent", "draft") is False
    assert is_valid_transition("draft", "nonexistent") is False


def test_no_outgoing_from_hard_deleted() -> None:
    """Hard-deleted is the only terminal — every target rejected."""
    for target in IDEA_LIFECYCLE_STATES:
        assert is_valid_transition("hard_deleted", target) is False


# ---------------------------------------------------------------------------
# IdeaLifecycle.transition — emission + return value
# ---------------------------------------------------------------------------


def test_transition_valid_returns_true(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    assert lc.transition("idea-1", "draft", "submitted") is True


def test_transition_invalid_returns_false(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    assert lc.transition("idea-1", "draft", "completed") is False


def test_transition_records_invalid_attempts(tmp_path: Path) -> None:
    """Invalid transitions ARE audited (forensic signal)."""
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-1", "draft", "completed", actor="ops")
    rows = [
        json.loads(line)["content"]
        for line in audit.read_text(encoding="utf-8").splitlines() if line
    ]
    assert len(rows) == 1
    assert rows[0]["success"] is False
    assert rows[0]["from_state"] == "draft"
    assert rows[0]["to_state"] == "completed"
    assert "invalid" in rows[0]["detail"]


def test_transition_emits_chained_audit(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-1", "draft", "submitted")
    lc.transition("idea-1", "submitted", "under_review")
    lc.transition("idea-1", "under_review", "approved")
    assert verify_chain(audit) == []


def test_transition_carries_actor_and_detail(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition(
        "idea-1", "draft", "submitted",
        actor="founder@sylion", detail="batch submission",
    )
    rows = [
        json.loads(line)["content"]
        for line in audit.read_text(encoding="utf-8").splitlines() if line
    ]
    assert rows[0]["actor"] == "founder@sylion"
    assert rows[0]["detail"] == "batch submission"


# ---------------------------------------------------------------------------
# history() — chain walking
# ---------------------------------------------------------------------------


def test_history_empty_for_new_idea(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    assert lc.history("idea-fresh") == []


def test_history_returns_only_successful_events(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-1", "draft", "submitted")  # ok
    lc.transition("idea-1", "draft", "completed")  # invalid
    lc.transition("idea-1", "submitted", "under_review")  # ok
    history = lc.history("idea-1")
    assert len(history) == 2
    assert history[0]["to_state"] == "submitted"
    assert history[1]["to_state"] == "under_review"


def test_history_isolates_per_idea(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-A", "draft", "submitted")
    lc.transition("idea-B", "draft", "submitted")
    lc.transition("idea-A", "submitted", "under_review")
    assert len(lc.history("idea-A")) == 2
    assert len(lc.history("idea-B")) == 1


def test_history_missing_chain_returns_empty(tmp_path: Path) -> None:
    audit = tmp_path / "doesnotexist.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    assert lc.history("idea-1") == []


# ---------------------------------------------------------------------------
# current_state() — latest successful state
# ---------------------------------------------------------------------------


def test_current_state_default_when_no_history(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    assert lc.current_state("idea-1") == "draft"


def test_current_state_returns_latest_to_state(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-1", "draft", "submitted")
    lc.transition("idea-1", "submitted", "under_review")
    lc.transition("idea-1", "under_review", "approved")
    assert lc.current_state("idea-1") == "approved"


def test_current_state_skips_invalid_attempts(tmp_path: Path) -> None:
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    lc.transition("idea-1", "draft", "submitted")
    lc.transition("idea-1", "submitted", "completed")  # invalid skip
    assert lc.current_state("idea-1") == "submitted"


# ---------------------------------------------------------------------------
# LifecycleEvent serialisation
# ---------------------------------------------------------------------------


def test_event_to_dict_serialisable() -> None:
    e = LifecycleEvent(
        event_id="abc", ts=1.0, idea_id="i",
        from_state="draft", to_state="submitted",
        actor="ops", success=True, detail="x",
    )
    d = e.to_dict()
    json.dumps(d)
    assert d["event_id"] == "abc"
    assert d["success"] is True


# ---------------------------------------------------------------------------
# Integration with GDPR — soft_deleted ↔ archived consistency.
# ---------------------------------------------------------------------------


def test_soft_deleted_can_revert_to_archived(tmp_path: Path) -> None:
    """GDPR Article 12.3 reversal — soft_deleted → archived must be valid."""
    assert is_valid_transition("soft_deleted", "archived") is True


def test_hard_deleted_terminal_no_reversal(tmp_path: Path) -> None:
    """Hard-deleted is past the GDPR 30-day grace window — no reversal."""
    audit = tmp_path / "il.jsonl"
    lc = IdeaLifecycle(audit_log_path=audit)
    # Cannot transition from hard_deleted to anything.
    for target in IDEA_LIFECYCLE_STATES:
        assert lc.transition("idea-1", "hard_deleted", target) is False
