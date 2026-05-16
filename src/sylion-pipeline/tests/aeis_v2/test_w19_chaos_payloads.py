from __future__ import annotations

from sylion.aeis_v2.policy_v2 import get_chaos_payload


def test_sandbox_escape_payload():
    p = get_chaos_payload("sandbox_escape")
    assert "__subclasses__" in p["template"]
    assert p["expected_error_substring"] in {"sandbox", "security"}


def test_timeout_loop_payload():
    p = get_chaos_payload("timeout_loop")
    assert "10**9" in p["template"] and p["expected_error_substring"] == "timeout"


def test_memory_bomb_payload():
    p = get_chaos_payload("memory_bomb")
    assert p["template"] == "{{ blob * copies }}" and p["expected_error_substring"] == ""


def test_malformed_jinja_payload():
    p = get_chaos_payload("malformed_jinja")
    assert p["template"] == "{{ user " and p["expected_error_substring"] == "syntax"


def test_unicode_bomb_payload():
    p = get_chaos_payload("unicode_bomb")
    assert "\U0001f4a3" in p["context"]["text"] and p["expected_error_substring"] == ""
