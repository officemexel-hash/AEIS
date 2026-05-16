from sylion.cognitive.idea_lifecycle_transitions import (
    IDEA_LIFECYCLE_TRANSITIONS,
    is_valid_transition,
)


def test_has_all_11_states():
    assert len(IDEA_LIFECYCLE_TRANSITIONS) == 11


def test_valid_forward_transition():
    assert is_valid_transition("draft", "submitted")


def test_valid_restore_transition():
    assert is_valid_transition("archived", "draft")


def test_invalid_transition():
    assert not is_valid_transition("draft", "completed")


def test_unknown_and_terminal_states():
    assert not is_valid_transition("missing", "draft")
    assert not is_valid_transition("hard_deleted", "draft")
