from __future__ import annotations

import pytest

from sylion.aeis_v2.policy_v2.jinja_runner import render_template

SANDBOX_ATTACK_PAYLOADS: list[tuple[str, str]] = [
    ("{{ ''.__class__ }}", "__class__"),
    ("{{ ''.__class__.__mro__ }}", "__class__"),
    ("{{ ''.__class__.__mro__[1].__subclasses__() }}", "__class__"),
    ("{{ cycler.__init__.__globals__ }}", "__globals__"),
    ("{{ cycler.__init__ }}", ".__init__"),
    ("{{ exec('1+1') }}", "exec("),
    ("{{ open('/etc/passwd').read() }}", "open("),
    ("{{ __import__('os') }}", "__import__"),
    ("{{ getattr('', '__class__') }}", "getattr("),
    ("{{ eval('1+1') }}", "eval("),
]


@pytest.mark.parametrize(("template", "expected_error_substring"), SANDBOX_ATTACK_PAYLOADS)
def test_sandbox_attack_payloads_fail_as_expected(
    template: str, expected_error_substring: str,
) -> None:
    result = render_template(template, {})
    assert result.succeeded is False
    assert result.error is not None
    assert "sandbox:" in result.error
    assert expected_error_substring in result.error
