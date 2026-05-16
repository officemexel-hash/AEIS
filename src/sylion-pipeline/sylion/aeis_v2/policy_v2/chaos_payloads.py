from __future__ import annotations


def make_chaos_payload(kind: str) -> dict:
    payloads = {
        "sandbox_escape": {"template": "{{ ''.__class__.__mro__[1].__subclasses__() }}", "context": {}},
        "timeout_loop": {"template": "{% for _ in range(10**9) %}x{% endfor %}", "context": {}},
        "memory_bomb": {"template": "{{ blob * copies }}", "context": {"blob": "X" * 1000000, "copies": 1000}},
        "malformed_jinja": {"template": "{{ user ", "context": {"user": "alice"}},
        "unicode_bomb": {"template": "{{ text }}", "context": {"text": ("A\u2066\u202e" + "💣") * 2000}},
    }
    if kind not in payloads:
        raise ValueError(f"unknown chaos kind: {kind}")
    return payloads[kind]


def get_chaos_payload(kind: str) -> dict:
    expected = {
        "sandbox_escape": "sandbox",
        "timeout_loop": "timeout",
        "malformed_jinja": "syntax",
    }
    payload = dict(make_chaos_payload(kind))
    payload["expected_error_substring"] = expected.get(kind, "")
    return payload
