"""Tests for ``sylion.aeis_v2.lifecycle_v2.SessionLifecycle`` — W18 4-state."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.lifecycle_v2 import (
    SESSION_LIFECYCLE_STATES,
    SESSION_LIFECYCLE_TRANSITIONS,
    SessionLifecycle,
    SessionLifecycleEvent,
    session_is_terminal,
    session_is_valid_transition,
)


# ---------------------------------------------------------------------------
# Canonical state set
# ---------------------------------------------------------------------------


def test_canonical_four_states() -> None:
    assert SESSION_LIFECYCLE_STATES == frozenset({
        "active", "suspended", "replay_source", "archived",
    })
    assert len(SESSION_LIFECYCLE_STATES) == 4


def test_transition_keys_canonical() -> None:
    assert set(SESSION_LIFECYCLE_TRANSITIONS) == set(SESSION_LIFECYCLE_STATES)


def test_archived_terminal_only() -> None:
    assert SESSION_LIFECYCLE_TRANSITIONS["archived"] == frozenset()
    assert session_is_terminal("archived") is True
    for s in ("active", "suspended", "replay_source"):
        assert session_is_terminal(s) is False


# ---------------------------------------------------------------------------
# is_valid_transition
# ---------------------------------------------------------------------------


def test_active_to_all_non_active() -> None:
    """active → suspended/replay_source/archived all valid."""
    for target in ("suspended", "replay_source", "archived"):
        assert session_is_valid_transition("active", target) is True


def test_suspended_back_to_active() -> None:
    assert session_is_valid_transition("suspended", "active") is True


def test_replay_source_back_to_active() -> None:
    """A frozen replay-source can resume operations."""
    assert session_is_valid_transition("replay_source", "active") is True


def test_archived_to_anything_invalid() -> None:
    for target in SESSION_LIFECYCLE_STATES:
        assert session_is_valid_transition("archived", target) is False


def test_self_loop_invalid() -> None:
    for s in SESSION_LIFECYCLE_STATES:
        assert session_is_valid_transition(s, s) is False


def test_invalid_target_replay_source_from_suspended() -> None:
    """suspended → replay_source not valid (must go through active)."""
    assert session_is_valid_transition("suspended", "replay_source") is False


def test_unknown_state() -> None:
    assert session_is_valid_transition("ghost", "active") is False
    assert session_is_valid_transition("active", "ghost") is False


# ---------------------------------------------------------------------------
# SessionLifecycle.transition + history + current_state
# ---------------------------------------------------------------------------


def test_transition_valid_returns_true(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    assert lc.transition("sess-1", "active", "suspended") is True


def test_transition_invalid_returns_false(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    assert lc.transition("sess-1", "active", "ghost") is False


def test_transition_records_invalid_attempts(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    lc.transition("sess-1", "archived", "active", actor="ops")
    rows = [
        json.loads(line)["content"]
        for line in (tmp_path / "sl.jsonl").read_text(
            encoding="utf-8",
        ).splitlines() if line
    ]
    assert len(rows) == 1
    assert rows[0]["success"] is False
    assert rows[0]["from_state"] == "archived"


def test_transition_emits_chained_audit(tmp_path: Path) -> None:
    audit = tmp_path / "sl.jsonl"
    lc = SessionLifecycle(audit_log_path=audit)
    lc.transition("sess-1", "active", "suspended")
    lc.transition("sess-1", "suspended", "active")
    lc.transition("sess-1", "active", "replay_source")
    assert verify_chain(audit) == []


def test_history_returns_only_successful(tmp_path: Path) -> None:
    audit = tmp_path / "sl.jsonl"
    lc = SessionLifecycle(audit_log_path=audit)
    lc.transition("sess-1", "active", "suspended")
    lc.transition("sess-1", "active", "ghost")  # invalid
    lc.transition("sess-1", "suspended", "active")
    history = lc.history("sess-1")
    assert len(history) == 2


def test_history_isolates_per_session(tmp_path: Path) -> None:
    audit = tmp_path / "sl.jsonl"
    lc = SessionLifecycle(audit_log_path=audit)
    lc.transition("sess-A", "active", "suspended")
    lc.transition("sess-B", "active", "replay_source")
    assert len(lc.history("sess-A")) == 1
    assert len(lc.history("sess-B")) == 1


def test_history_missing_chain_returns_empty(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "absent.jsonl")
    assert lc.history("sess-x") == []


def test_current_state_default_active_when_no_history(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    assert lc.current_state("sess-fresh") == "active"


def test_current_state_reflects_latest_to_state(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    lc.transition("sess-1", "active", "suspended")
    lc.transition("sess-1", "suspended", "active")
    lc.transition("sess-1", "active", "replay_source")
    assert lc.current_state("sess-1") == "replay_source"


def test_current_state_default_override(tmp_path: Path) -> None:
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    assert lc.current_state("sess-x", default="archived") == "archived"


# ---------------------------------------------------------------------------
# Dataclass round-trip
# ---------------------------------------------------------------------------


def test_event_to_dict_serialisable() -> None:
    e = SessionLifecycleEvent(
        event_id="e1", ts=1.0, session_id="s1",
        from_state="active", to_state="archived",
        actor="ops", success=True, detail="done",
    )
    d = e.to_dict()
    json.dumps(d)
    assert d["session_id"] == "s1"


# ---------------------------------------------------------------------------
# Integration with replay-as-fork
# ---------------------------------------------------------------------------


def test_replay_source_state_blocks_other_transitions(tmp_path: Path) -> None:
    """replay_source → only active or archived are valid."""
    lc = SessionLifecycle(audit_log_path=tmp_path / "sl.jsonl")
    lc.transition("sess-1", "active", "replay_source")
    # replay_source → suspended NOT valid (must go through active)
    assert lc.transition("sess-1", "replay_source", "suspended") is False
    # replay_source → active IS valid
    assert lc.transition("sess-1", "replay_source", "active") is True


# ---------------------------------------------------------------------------
# Compatibility: SessionLifecycle and IdeaLifecycle don't collide.
# ---------------------------------------------------------------------------


def test_session_states_distinct_from_idea_states() -> None:
    """Per Kimi k3 — only ``archived`` overlaps; rest are distinct."""
    from sylion.aeis_v2.lifecycle_v2 import IDEA_LIFECYCLE_STATES

    overlap = SESSION_LIFECYCLE_STATES & IDEA_LIFECYCLE_STATES
    assert overlap == {"archived"}
