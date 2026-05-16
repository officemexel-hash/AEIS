import hashlib
import json

import pytest

from sylion.core.session_state_snapshot import SessionStateSnapshot


def test_capture_returns_expected_snapshot(monkeypatch):
    monkeypatch.setattr("sylion.core.session_state_snapshot.time.time", lambda: 123.4)
    monkeypatch.setattr("sylion.core.session_state_snapshot.uuid.uuid4", lambda: type("U", (), {"hex": "abc"})())
    session = {"b": 2, "a": 1}
    snap = SessionStateSnapshot.capture(session)
    assert snap == SessionStateSnapshot("abc", 123.4, ["a", "b"], hashlib.sha256(json.dumps(session, sort_keys=True).encode()).hexdigest()[:16])


def test_capture_sorts_keys():
    assert SessionStateSnapshot.capture({"z": 1, "a": 2}).state_keys == ["a", "z"]


def test_capture_hash_is_order_independent():
    assert SessionStateSnapshot.capture({"a": 1, "b": 2}).state_hash == SessionStateSnapshot.capture({"b": 2, "a": 1}).state_hash


def test_capture_raises_for_non_jsonable_value():
    with pytest.raises(TypeError):
        SessionStateSnapshot.capture({"bad": object()})
