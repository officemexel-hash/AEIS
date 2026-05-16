from sylion.cognitive.idea_lifecycle_validator import IdeaLifecycleValidator as V


def test_has_all_11_states():
    assert len(V.VALID_TRANSITIONS) == 11


def test_valid_submission_transition():
    assert V.validate("draft", "submitted")


def test_valid_restore_transition():
    assert V.validate("archived", "draft")


def test_invalid_skip_transition():
    assert not V.validate("draft", "completed")


def test_unknown_and_terminal_states():
    assert not V.validate("missing", "draft")
    assert not V.validate("hard_deleted", "draft")
