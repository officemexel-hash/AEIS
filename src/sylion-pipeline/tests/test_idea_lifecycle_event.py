from __future__ import annotations

import time

from sylion.cognitive.idea_lifecycle_event import make_lifecycle_event


def test_returns_expected_fields():
    row = make_lifecycle_event("i1", "draft", "submitted", "alice", 123.5)
    assert row == {"idea_id": "i1", "from_state": "draft", "to_state": "submitted", "actor": "alice", "ts": 123.5}


def test_ts_defaults_to_now():
    before = time.time()
    row = make_lifecycle_event("i1", "draft", "submitted", "alice")
    after = time.time()
    assert before <= row["ts"] <= after


def test_preserves_empty_from_state():
    row = make_lifecycle_event("i1", "", "draft", "alice", 1.0)
    assert row["from_state"] == ""


def test_preserves_actor_verbatim():
    row = make_lifecycle_event("i1", "draft", "approved", "", 1.0)
    assert row["actor"] == ""
