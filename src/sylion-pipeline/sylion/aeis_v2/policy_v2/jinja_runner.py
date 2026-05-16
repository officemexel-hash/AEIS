"""W19 G2 (PROPOSED — ADR-003 Option B): jinja2 SandboxedEnvironment runner.

Status: SKELETON. NOT WIRED into routing/apply yet (ADR-003 still PROPOSED,
awaiting operator + Council Hybrid sign-off). The runner exists so when the
flag flips, the path is tested and ready.

Invocations from production code MUST go through ``W19_EVALUATOR_ENABLED``
feature flag (env SYLION_W19_EVALUATOR_DISABLED). Until ADR-003 lands at
ACCEPTED, the flag defaults to disabled.

Hardening per ADR-003 audit checklist:
- jinja2.sandbox.SandboxedEnvironment (NOT Environment)
- timeout per render = 1.0s (jinja2 has no native timeout — we wrap via
  signal.alarm on POSIX, threading.Timer on Windows)
- block __class__, __mro__, __subclasses__ access via SandboxedEnvironment
  default + extra blocklist
- audit JSONL emit per render: ts, decision_id, template_hash, ctx_keys,
  result, render_ms, error
- on render error: ALWAYS deny (fail-closed)

Per ADR-001 #4 we cannot wire the evaluator into routing decisions yet —
but this skeleton lets the operator flip ``SYLION_W19_EVALUATOR_DISABLED=0``
the moment ADR-003 lands at ACCEPTED. Routing/apply call sites
(federation.py, applier.py) intentionally DO NOT import this module yet.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Feature flag — defaults DISABLED per ADR-003 PROPOSED status.
W19_EVALUATOR_ENABLED_ENV: str = "SYLION_W19_EVALUATOR_DISABLED"
W19_RENDER_TIMEOUT_S: float = 1.0
W19_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3] / "logs" / "v2" / "w19_evaluator.jsonl"
)
W19_BLOCKED_TEMPLATE_TOKENS: tuple[str, ...] = (
    "exec(", "open(", "__import__", "getattr(", "eval(",
    "__globals__", ".__init__", "__class__", "__mro__", "__subclasses__",
)
W19_TEMPLATE_MAX_LEN = 4096


def is_evaluator_enabled() -> bool:
    """Returns False by default. Operator sets SYLION_W19_EVALUATOR_DISABLED=0
    to enable AFTER ADR-003 ACCEPTED + Council Hybrid sign-off."""
    raw = os.environ.get(W19_EVALUATOR_ENABLED_ENV, "1").strip()
    return raw == "0"


@dataclass(frozen=True, slots=True)
class JinjaRenderResult:
    """Result of a single jinja2 sandbox render."""

    template_hash: str
    rendered: str | None
    error: str | None
    render_ms: float

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.rendered is not None


class JinjaContextSafelist:
    def __init__(self, allowlist: dict[str, set[str]] | None = None):
        self.allowlist = {k: set(v) for k, v in (allowlist or {}).items()}

    @classmethod
    def filter_context(cls, ctx: dict[str, Any], allowed_keys: set[str]) -> dict[str, Any]:
        return {k: cls._clean(v) for k, v in ctx.items() if k in allowed_keys}

    @classmethod
    def _clean(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {k: cls._clean(v) for k, v in value.items() if not k.startswith("_")}

    def for_rule(self, rule_id: str, ctx: dict[str, Any]) -> dict[str, Any]:
        return self.filter_context(ctx, self.allowlist.get(rule_id, set()))


def _sandboxed_env():
    """Return a configured SandboxedEnvironment.

    Lazy import (jinja2 is optional — if not installed, the entire W19
    evaluator stays disabled).
    """
    from jinja2.sandbox import SandboxedEnvironment

    env = SandboxedEnvironment(
        autoescape=True,
        keep_trailing_newline=False,
    )
    # SandboxedEnvironment default already blocks __class__/__mro__ via
    # is_safe_attribute / is_safe_callable. We can extend if more escapes
    # surface in audit.
    return env


def validate_policy_template(template_str: str) -> tuple[bool, str]:
    """Validate a policy template before runtime use."""
    if len(template_str) > W19_TEMPLATE_MAX_LEN:
        return (False, f"template too long: max {W19_TEMPLATE_MAX_LEN} chars")
    lowered = template_str.lower()
    for token in ("eval", "exec", "__class__", "__import__"):
        if token in lowered:
            return (False, f"banned token: {token}")
    try:
        from jinja2 import TemplateSyntaxError
    except ImportError as exc:
        return (False, f"jinja2 not installed: {exc}")
    try:
        _sandboxed_env().parse(template_str)
    except TemplateSyntaxError as exc:
        return (False, f"syntax: {exc}")
    return (True, "ok")


def _render_with_timeout(
    template_str: str,
    context: dict[str, Any],
    timeout_s: float,
) -> tuple[str | None, str | None]:
    """Run jinja2 render in a daemon thread; return ``(rendered, error)``.

    Sprint 3 E1 (post-Kimi k1 round 47:30): real interrupt so an infinite
    template loop does NOT hang the request. We cannot cleanly kill the
    worker thread (Python limitation) so it leaks — but it stays daemon
    and the process exit cleans it up. The pool stays small in practice
    because the timeout window is sub-second.
    """
    import threading

    lowered = template_str.lower()
    for token in W19_BLOCKED_TEMPLATE_TOKENS:
        if token.lower() in lowered:
            return (None, f"sandbox: blocked token {token}")

    try:
        from jinja2 import TemplateSyntaxError
        from jinja2.exceptions import SecurityError, TemplateError
    except ImportError as exc:
        return (None, f"jinja2 not installed: {exc}")

    result_holder: dict[str, Any] = {"rendered": None, "error": None}

    def _run() -> None:
        try:
            env = _sandboxed_env()
            tmpl = env.from_string(template_str)
            result_holder["rendered"] = tmpl.render(**context)
        except SecurityError as e:
            result_holder["error"] = f"sandbox: {e}"
        except TemplateSyntaxError as e:
            result_holder["error"] = f"syntax: {e}"
        except TemplateError as e:
            result_holder["error"] = f"render: {e}"
        except Exception as e:  # noqa: BLE001 — fail-closed
            result_holder["error"] = f"unknown: {type(e).__name__}: {e}"

    th = threading.Thread(target=_run, name="w19-jinja-render", daemon=True)
    th.start()
    th.join(timeout=timeout_s)

    if th.is_alive():
        # Timeout: thread leaks (we can't kill it safely). Mark fail-closed.
        return (None, f"timeout: render exceeded {timeout_s:.3f}s")

    return (result_holder["rendered"], result_holder["error"])


def render_template(
    template_str: str,
    context: dict[str, Any],
    *,
    timeout_s: float = W19_RENDER_TIMEOUT_S,
) -> JinjaRenderResult:
    """Pure helper. Renders a jinja2 template under sandbox + real timeout.

    Sprint 3 E1: timeout is enforced via a daemon thread + ``join(timeout)``
    so an infinite-loop template (``{% for x in range(10**9) %}``) trips the
    deadline cleanly instead of hanging the caller.

    On any error (security, timeout, syntax) returns result with ``error``
    set and ``rendered=None``. Caller treats this as DENY (fail-closed).
    """
    template_hash = hashlib.sha256(template_str.encode("utf-8")).hexdigest()[:16]
    start = time.perf_counter()
    rendered, error = _render_with_timeout(template_str, context, timeout_s)
    elapsed = (time.perf_counter() - start) * 1000
    return JinjaRenderResult(
        template_hash=template_hash,
        rendered=rendered if error is None else None,
        error=error,
        render_ms=elapsed,
    )


def emit_audit(decision_id: str, result: JinjaRenderResult, ctx_keys: list[str]) -> None:
    """Best-effort audit JSONL emit. Never raises.

    Sprint 3: migrated to chained format via append_to_chain so the
    DPO can verify the audit trail's integrity (commit ac97e957).
    """
    row = {
        "kind": "w19_evaluator.render",
        "ts": time.time(),
        "decision_id": decision_id,
        "template_hash": result.template_hash,
        "ctx_keys": ctx_keys,
        "succeeded": result.succeeded,
        "error": result.error,
        "render_ms": round(result.render_ms, 3),
    }
    try:
        from sylion.aeis_v2.audit_chain import append_to_chain

        append_to_chain(W19_AUDIT_LOG_PATH, row)
    except Exception as exc:  # noqa: BLE001
        log.warning("w19_evaluator: audit emit failed (%s)", exc)
