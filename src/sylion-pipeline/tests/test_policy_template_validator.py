from sylion.aeis_v2.policy_v2 import validate_policy_template


def test_validate_policy_template_accepts_valid_template():
    ok, msg = validate_policy_template("{{ actor.role == 'admin' }}")
    assert ok is True
    assert msg == "ok"


def test_validate_policy_template_rejects_too_long():
    ok, msg = validate_policy_template("a" * 4097)
    assert ok is False
    assert "max 4096" in msg


def test_validate_policy_template_rejects_banned_token():
    ok, msg = validate_policy_template("{{ __import__('os') }}")
    assert ok is False
    assert "__import__" in msg


def test_validate_policy_template_rejects_syntax_error():
    ok, msg = validate_policy_template("{% if user %}")
    assert ok is False
    assert msg.startswith("syntax:")


def test_validate_policy_template_blocks_case_insensitive_tokens():
    ok, msg = validate_policy_template("{{ ExEc('x') }}")
    assert ok is False
    assert "exec" in msg
