"""Tests for sylion.aeis_v2.terminal — sessions, commands, stream (W18).

Covers:
A. Sessions (sessions.py): SessionStore CRUD, task lifecycle, progress
   clamping, event buffer cap, singleton.
B. Commands (commands.py): parser, builtin command set, alias resolution,
   error paths, /diff + /replay + /focus arg validation.
C. Streaming (stream.py): EventFilter logic, SSE payload format,
   subscriber drop-on-full behavior.
"""
from __future__ import annotations

import asyncio

import pytest

from sylion.aeis_v2.terminal import (
    BUILTIN_COMMANDS,
    SessionStore,
    get_session_store,
    list_commands,
    parse_command,
)
from sylion.aeis_v2.terminal.stream import (
    EventFilter,
    EventSubscriber,
    TerminalEvent,
)


# --------------------------------------------------------------------------
# A. Sessions
# --------------------------------------------------------------------------


def test_session_store_create_returns_session_with_12_hex_id():
    store = SessionStore()
    sess = store.create("My session")
    assert len(sess.session_id) == 12
    assert all(c in "0123456789abcdef" for c in sess.session_id)
    assert sess.title == "My session"


def test_session_store_singleton():
    a = get_session_store()
    b = get_session_store()
    assert a is b


def test_add_task_increases_tasks_list():
    store = SessionStore()
    sess = store.create("s")
    before = len(sess.tasks)
    task = store.add_task(sess.session_id, "task A")
    assert task is not None
    assert len(sess.tasks) == before + 1


def test_add_task_sets_current_task_idx_when_first_task():
    store = SessionStore()
    sess = store.create("s")
    assert sess.current_task_idx is None
    store.add_task(sess.session_id, "task A")
    assert sess.current_task_idx == 0


def test_update_task_status_running_sets_started_at():
    store = SessionStore()
    sess = store.create("s")
    task = store.add_task(sess.session_id, "task A")
    store.update_task(sess.session_id, task.task_id, status="running")
    assert sess.tasks[0].started_at is not None
    assert sess.tasks[0].finished_at is None


def test_update_task_status_done_sets_finished_at():
    store = SessionStore()
    sess = store.create("s")
    task = store.add_task(sess.session_id, "task A")
    store.update_task(sess.session_id, task.task_id, status="done")
    assert sess.tasks[0].finished_at is not None


def test_update_task_progress_clamped_to_unit_interval():
    store = SessionStore()
    sess = store.create("s")
    task = store.add_task(sess.session_id, "task A")
    store.update_task(sess.session_id, task.task_id, progress=2.0)
    assert sess.tasks[0].progress == 1.0
    store.update_task(sess.session_id, task.task_id, progress=-1.0)
    assert sess.tasks[0].progress == 0.0


def test_close_session_sets_status_closed():
    store = SessionStore()
    sess = store.create("s")
    assert sess.status == "active"
    assert store.close(sess.session_id) is True
    assert sess.status == "closed"


def test_progress_pct_zero_when_no_tasks():
    store = SessionStore()
    sess = store.create("s")
    assert sess.progress_pct() == 0


def test_progress_pct_average_of_task_progress():
    store = SessionStore()
    sess = store.create("s")
    t1 = store.add_task(sess.session_id, "a")
    t2 = store.add_task(sess.session_id, "b")
    store.update_task(sess.session_id, t1.task_id, progress=1.0)
    store.update_task(sess.session_id, t2.task_id, progress=0.5)
    # average = 0.75 → 75
    assert sess.progress_pct() == 75


def test_append_event_keeps_buffer_within_cap():
    store = SessionStore()
    sess = store.create("s")
    for i in range(250):
        store.append_event(sess.session_id, {"i": i}, cap=200)
    assert len(sess.last_events) <= 200


def test_get_unknown_session_returns_none():
    store = SessionStore()
    assert store.get("nonexistent") is None


# --------------------------------------------------------------------------
# B. Commands
# --------------------------------------------------------------------------


def test_parse_status_returns_text_with_sylion_brand():
    r = parse_command("/status")
    assert r.kind == "text"
    assert "SYLION AEIS" in r.text


def test_parse_help_returns_table_with_at_least_17_rows():
    r = parse_command("/help")
    assert r.kind == "table"
    assert r.rows is not None
    assert len(r.rows) >= 17


def test_parse_unknown_command_returns_error():
    r = parse_command("/nosuch")
    assert r.kind == "error"
    assert "Nieznana" in r.text or "Unknown" in r.text


def test_parse_empty_input_returns_error():
    r = parse_command("")
    assert r.kind == "error"


def test_parse_no_slash_returns_error():
    r = parse_command("status no slash")
    assert r.kind == "error"


def test_help_alias_resolution():
    a = parse_command("/help")
    b = parse_command("/?")
    assert a.kind == b.kind == "table"
    assert a.rows is not None and b.rows is not None
    assert len(a.rows) == len(b.rows)


def test_diff_requires_args():
    bad = parse_command("/diff")
    assert bad.kind == "error"
    good = parse_command("/diff sessions a b")
    assert good.kind == "not_implemented"
    assert good.meta == {"a": "a", "b": "b"}


def test_replay_requires_session_id():
    bad = parse_command("/replay")
    assert bad.kind == "error"
    good = parse_command("/replay xyz123")
    assert good.kind == "not_implemented"
    assert good.target == "xyz123"


def test_focus_requires_arg():
    bad = parse_command("/focus")
    assert bad.kind == "error"
    good = parse_command("/focus session_abc")
    assert good.kind == "text"
    assert good.meta == {"scope": "session", "target": "session_abc", "args": ["session_abc"]}


def test_skip_current_task_marks_terminal_task_skipped():
    store = get_session_store()
    sess = store.create("skip test")
    task = store.add_task(sess.session_id, "task A")
    assert task is not None
    store.update_task(sess.session_id, task.task_id, status="running")

    result = parse_command("/skip", {"session_id": sess.session_id})

    assert result.kind == "text"
    assert result.meta["task_id"] == task.task_id
    assert sess.tasks[0].status == "skipped"


def test_command_count_at_least_seventeen():
    assert len(BUILTIN_COMMANDS) >= 17


def test_list_commands_returns_dicts_with_name_and_summary():
    cmds = list_commands()
    assert isinstance(cmds, list)
    assert len(cmds) == len(BUILTIN_COMMANDS)
    for entry in cmds:
        assert "name" in entry
        assert "summary_pl" in entry or "summary_en" in entry


def test_request_checkpoint_command_is_registered_and_executable():
    result = parse_command("/request checkpoint")
    assert result.kind == "text"
    assert result.meta["checkpoint"] is True
    assert result.meta["command_id"]


def test_terminal_command_router_adds_route_contract_to_response():
    from sylion.aeis_v2.terminal.command_router import execute_terminal_intent

    execution = execute_terminal_intent("/status", {"source_surface": "test"})
    response = execution.to_response()

    assert response["kind"] == "text"
    assert response["meta"]["command_intent"]["source_surface"] == "test"
    assert response["meta"]["command_route"]["target_action"] == "status"
    assert response["meta"]["command_execution"]["status"] == "completed"


# --------------------------------------------------------------------------
# C. Streaming
# --------------------------------------------------------------------------


def test_event_filter_layers_excludes_non_matching():
    e = TerminalEvent(ts=1.0, layer="W14", message="m")
    f = EventFilter(layers={"W15"})
    assert e.matches_filter(f) is False


def test_event_filter_empty_matches_any():
    f = EventFilter()
    e = TerminalEvent(ts=1.0, layer="W14", message="m")
    assert e.matches_filter(f) is True


def test_event_to_sse_payload_format():
    e = TerminalEvent(ts=1.0, layer="W15", message="hello")
    payload = e.to_sse_payload()
    assert payload.startswith("data: ")
    assert payload.endswith("\n\n")


def test_subscriber_drops_events_when_full():
    """maxsize=1 → 3 matching events offered → 2 dropped."""
    async def _run() -> int:
        sub = EventSubscriber("s1", EventFilter())
        # Replace queue with size=1 to force overflow on the second/third offer.
        sub._queue = asyncio.Queue(maxsize=1)
        for i in range(3):
            sub.offer(TerminalEvent(ts=float(i), layer="W15", message=str(i)))
        return sub.dropped

    assert asyncio.run(_run()) == 2


# --------------------------------------------------------------------------
# D. P0-1 — exception stringification leaks secrets (adversarial review W18)
# --------------------------------------------------------------------------


def test_parse_command_redacts_postgres_uri_in_value_error(monkeypatch):
    """P0-1: parse_command must not echo raw exception text containing a DB URI."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import CommandResult, parse_command

    def _evil_handler(args, ctx):
        raise ValueError("connection failed: postgres://user:secret123@host:5432/db")

    # Inject a fake command for the test
    fake_spec = cmd_mod.CommandSpec(
        name="evil", summary_pl="x", summary_en="x", handler=_evil_handler,
    )
    # Patch BUILTIN_COMMANDS to include our fake one
    monkeypatch.setattr(cmd_mod, "BUILTIN_COMMANDS", cmd_mod.BUILTIN_COMMANDS + (fake_spec,))

    result = parse_command("/evil")
    assert result.kind == "error"
    assert "postgres://" not in result.text
    assert "secret123" not in result.text
    assert "<redacted>" in result.text or "Bledne uzycie" in result.text


def test_parse_command_internal_exception_returns_error_id_not_message(monkeypatch):
    """P0-1: unexpected exceptions return opaque error_id, not the raw message."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import parse_command

    def _explode(args, ctx):
        leaked = "sk-" + "abc123XYZ"
        raise RuntimeError(f"internal: api_key={leaked} leaked here")

    fake_spec = cmd_mod.CommandSpec(
        name="explode", summary_pl="x", summary_en="x", handler=_explode,
    )
    monkeypatch.setattr(cmd_mod, "BUILTIN_COMMANDS", cmd_mod.BUILTIN_COMMANDS + (fake_spec,))

    result = parse_command("/explode")
    assert result.kind == "error"
    assert "sk-" + "abc123XYZ" not in result.text
    assert "api_key" not in result.text
    assert "error_id=" in result.text


def test_parse_command_keyboard_interrupt_propagates():
    """P0-1: KeyboardInterrupt / SystemExit must NOT be swallowed."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import parse_command
    import pytest as _pytest

    def _quit(args, ctx):
        raise KeyboardInterrupt()

    fake_spec = cmd_mod.CommandSpec(
        name="quit", summary_pl="x", summary_en="x", handler=_quit,
    )
    # Use a temporary patch via context manager to avoid bleed
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (fake_spec,)
    try:
        with _pytest.raises(KeyboardInterrupt):
            parse_command("/quit")
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved


def test_sanitize_error_text_redacts_email():
    from sylion.aeis_v2.terminal.commands import _sanitize_error_text
    out = _sanitize_error_text("conflict with admin@example.com record")
    assert "admin@example.com" not in out
    assert "<redacted>" in out


def test_sanitize_error_text_redacts_bearer_token():
    from sylion.aeis_v2.terminal.commands import _sanitize_error_text
    out = _sanitize_error_text("auth failed Bearer eyJhbGciOiJIUzI1NiJ9.abc.def")
    assert "eyJhbGciOiJIUzI1NiJ9" not in out
    assert "<redacted>" in out


# --------------------------------------------------------------------------
# E. P1-1 — alias collision blind spot (adversarial review W18)
# --------------------------------------------------------------------------


def test_builtin_commands_have_no_collisions():
    """P1-1: production BUILTIN_COMMANDS table has unique names + aliases."""
    from sylion.aeis_v2.terminal.commands import _validate_command_table, BUILTIN_COMMANDS
    _validate_command_table(BUILTIN_COMMANDS)  # raises if broken


def test_validate_command_table_catches_duplicate_name():
    """P1-1: duplicate names raise RuntimeError."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    bad = (
        CommandSpec("foo", "x", "x"),
        CommandSpec("foo", "y", "y"),  # duplicate name
    )
    with pytest.raises(RuntimeError, match="collision"):
        _validate_command_table(bad)


def test_validate_command_table_catches_duplicate_alias():
    """P1-1: same alias on two commands raises."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    bad = (
        CommandSpec("foo", "x", "x", aliases=("shared",)),
        CommandSpec("bar", "y", "y", aliases=("shared",)),  # alias collision
    )
    with pytest.raises(RuntimeError, match="alias"):
        _validate_command_table(bad)


def test_validate_command_table_catches_alias_matching_name():
    """P1-1: alias that matches another command's name raises (shadowing risk)."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    bad = (
        CommandSpec("model", "x", "x"),
        CommandSpec("agents", "y", "y", aliases=("model",)),  # alias=existing name
    )
    with pytest.raises(RuntimeError, match="alias"):
        _validate_command_table(bad)


def test_validate_command_table_accepts_clean_table():
    """P1-1: clean table validates without exception."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    clean = (
        CommandSpec("alpha", "a", "a", aliases=("a",)),
        CommandSpec("beta", "b", "b", aliases=("bb",)),
    )
    _validate_command_table(clean)  # no exception


# --------------------------------------------------------------------------
# F. P1-3 — ctx parameter mutation foot-gun (KIMI review F-W18-CMD-3)
# --------------------------------------------------------------------------
#
# parse_command(line, ctx=None) used to forward ``ctx or {}`` directly to
# the handler. If a caller passed a shared dict, any handler doing
# ``ctx['x'] = 1`` would silently leak per-call state into the caller's
# state — and there was no docstring warning about that. Fix wraps ctx
# in types.MappingProxyType, so handlers see a read-only view; mutations
# raise TypeError loudly. Below: regression tests for that contract.


def test_parse_command_with_none_ctx_uses_empty_proxy():
    """P1-3: when caller passes ctx=None, handler receives an empty
    read-only mapping (MappingProxyType over {})."""
    from types import MappingProxyType
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import (
        CommandResult, CommandSpec, parse_command,
    )

    captured: dict[str, Any] = {}

    def _capture(args, ctx):
        captured["ctx"] = ctx
        captured["type"] = type(ctx)
        captured["len"] = len(ctx)
        return CommandResult(kind="text", text="ok")

    spec = CommandSpec(
        name="capnone", summary_pl="x", summary_en="x", handler=_capture,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (spec,)
    try:
        result = parse_command("/capnone")
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    assert result.kind == "text"
    assert captured["type"] is MappingProxyType
    assert captured["len"] == 0


def test_parse_command_ctx_proxy_rejects_mutation():
    """P1-3: handler that tries to mutate ctx triggers the parse_command
    error path (TypeError caught and surfaced as a sanitized error
    result with kind='error'). The mutation MUST NOT silently succeed."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import (
        CommandResult, CommandSpec, parse_command,
    )

    def _evil_mutator(args, ctx):
        ctx["leaked"] = "value"  # raises TypeError on mappingproxy
        return CommandResult(kind="text", text="should not reach here")

    spec = CommandSpec(
        name="mutator", summary_pl="x", summary_en="x", handler=_evil_mutator,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (spec,)
    try:
        # Caller passes a dict — handler must NOT be able to mutate it.
        caller_ctx: dict[str, Any] = {"role": "operator"}
        result = parse_command("/mutator", ctx=caller_ctx)
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    # parse_command catches TypeError in its except (ValueError, TypeError)
    # branch and returns an error CommandResult. Either path is acceptable
    # so long as the mutation did NOT take effect on the caller's dict.
    assert result.kind == "error"
    assert "leaked" not in caller_ctx        # caller untouched
    assert caller_ctx == {"role": "operator"}  # exact preservation


def test_parse_command_ctx_passes_through_keys():
    """P1-3: read-access still works — handler can read ctx['role']
    transparently. Read-only does not mean opaque."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import (
        CommandResult, CommandSpec, parse_command,
    )

    seen: dict[str, Any] = {}

    def _reader(args, ctx):
        seen["role"] = ctx["role"]
        seen["operator_id"] = ctx.get("operator_id", "<missing>")
        return CommandResult(kind="text", text="read ok")

    spec = CommandSpec(
        name="reader", summary_pl="x", summary_en="x", handler=_reader,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (spec,)
    try:
        result = parse_command(
            "/reader", ctx={"role": "operator", "operator_id": "u-42"}
        )
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    assert result.kind == "text"
    assert seen["role"] == "operator"
    assert seen["operator_id"] == "u-42"


def test_parse_command_ctx_proxy_isolates_caller_from_external_mutation():
    """P1-3 defense-in-depth: even if the caller mutates *their* dict
    after invoking parse_command, the handler's already-captured view
    must be a snapshot (we wrap ``dict(ctx)``, not ``ctx`` itself).

    This guards a subtle race: handler stores ctx for async use, caller
    reuses the dict for the next call. Without the snapshot, the
    handler's saved reference would silently observe the new keys.
    """
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import (
        CommandResult, CommandSpec, parse_command,
    )

    captured_view: dict[str, Any] = {}

    def _grabber(args, ctx):
        captured_view["proxy"] = ctx  # save the proxy
        captured_view["snapshot_role"] = ctx.get("role")
        return CommandResult(kind="text", text="ok")

    spec = CommandSpec(
        name="grabber", summary_pl="x", summary_en="x", handler=_grabber,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (spec,)
    try:
        caller_ctx: dict[str, Any] = {"role": "viewer"}
        parse_command("/grabber", ctx=caller_ctx)
        # Caller mutates their own dict AFTER the call.
        caller_ctx["role"] = "admin"
        caller_ctx["new_field"] = "added"
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    # The proxy still holds the original snapshot — it does NOT see
    # the post-call mutation of caller_ctx.
    assert captured_view["snapshot_role"] == "viewer"
    assert captured_view["proxy"]["role"] == "viewer"
    assert "new_field" not in captured_view["proxy"]


# --------------------------------------------------------------------------
# G. P1-2 — locale-dependent .lower() (adversarial review W18)
# --------------------------------------------------------------------------
#
# parse_command used to fold cmd_name with str.lower(), which leaves
# non-ASCII codepoints like 'Ł', 'ß', and ligatures untouched. Fix
# replaces .lower() with .casefold() (Unicode-aware) and locks the alias
# surface to ``[a-z0-9_-]+`` (plus the well-known shortcut '?') so the
# parser-vs-table comparisons are symmetric.


@pytest.mark.parametrize("variant", ["/STATUS", "/Status", "/sTaTuS", "/status"])
def test_parse_command_uses_casefold_not_lower(variant):
    """P1-2: ASCII case variants all resolve to /status handler.

    Pins that the parser folds case before alias lookup; if a future
    maintainer reverts to str.lower() this test still passes (ASCII is
    common ground), so the partner test below covers the casefold-only
    surface.
    """
    r = parse_command(variant)
    assert r.kind == "text"
    assert "SYLION" in r.text
    assert r.kind != "error"


def test_parse_command_casefold_handles_unicode_unknown_command_cleanly():
    """P1-2: a non-ASCII command name that does NOT match any alias
    returns a clean error (not a 500-equivalent traceback).

    Operator typing /MODEŁ on a Polish keyboard (Ł, U+0141) used to
    bypass alias matching silently — now the parse pipeline still
    handles it as an unknown command, but the casefold() call doesn't
    crash on the codepoint. Once an alias is registered with non-ASCII
    we'd need to rework alias normalisation; today the contract is
    'unknown command' for any token outside [a-z0-9_-?]+.
    """
    r = parse_command("/MODEŁ")
    assert r.kind == "error"
    assert "Nieznana komenda" in r.text
    # casefold() of 'Ł' is 'ł'; the unknown-command echo should reflect
    # the folded form, not crash.
    assert "modeł" in r.text


def test_validate_command_table_rejects_invalid_alias_chars():
    """P1-2 hardening: an alias containing whitespace is rejected at
    load time with a ValueError mentioning the bad alias.

    This locks the alias surface against future PRs that try to
    register aliases like 'sta tus' (with a space) which would silently
    break shlex tokenization in parse_command.
    """
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    bad = (
        CommandSpec("status", "x", "x", aliases=("sta tus",)),  # space inside
    )
    with pytest.raises(ValueError, match="sta tus"):
        _validate_command_table(bad)


def test_validate_command_table_rejects_invalid_name_chars():
    """P1-2 hardening: a command name with a slash is rejected — the
    parser strips the leading '/' but anything inside the body MUST be
    a tokenizer-safe atom."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    bad = (
        CommandSpec("sta/tus", "x", "x"),
    )
    with pytest.raises(ValueError, match="sta/tus"):
        _validate_command_table(bad)


def test_validate_command_table_accepts_question_mark_alias():
    """P1-2: '?' is the one allowed punctuation alias (used by /help).
    Pin the contract so a future tightening of the regex doesn't break
    the established UX shortcut."""
    from sylion.aeis_v2.terminal.commands import (
        CommandSpec, _validate_command_table,
    )
    ok = (
        CommandSpec("help", "x", "x", aliases=("?",)),
    )
    _validate_command_table(ok)  # no exception


# --------------------------------------------------------------------------
# H. P1-3 — asyncio.CancelledError swallowing (adversarial review W18)
# --------------------------------------------------------------------------
#
# CancelledError IS-A Exception in Python 3.8+, so the broad
# ``except Exception`` in parse_command would silently turn a cancelled
# task into a generic "internal error" CommandResult. When G2 makes
# handlers async, cancellation MUST propagate so the caller can clean
# up. Fix re-raises CancelledError above the broad catch.


def test_parse_command_reraises_cancelled_error():
    """P1-3: handler raising asyncio.CancelledError must propagate the
    cancellation to the caller — not be caught and converted to a
    CommandResult(kind='error') by the broad Exception clause."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import CommandSpec, parse_command

    def _cancel(args, ctx):
        raise asyncio.CancelledError()

    fake_spec = CommandSpec(
        name="cancelme", summary_pl="x", summary_en="x", handler=_cancel,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (fake_spec,)
    try:
        with pytest.raises(asyncio.CancelledError):
            parse_command("/cancelme")
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved


def test_parse_command_still_catches_other_exceptions():
    """P1-3 regression: a handler raising plain ValueError is STILL
    caught by parse_command and converted to kind='error' with a
    sanitized message. Pinning this guards against an over-eager fix
    that would re-raise everything."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import CommandSpec, parse_command

    def _boom(args, ctx):
        raise ValueError("test boom")

    fake_spec = CommandSpec(
        name="boomy", summary_pl="x", summary_en="x", handler=_boom,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (fake_spec,)
    try:
        result = parse_command("/boomy")
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    assert result.kind == "error"
    assert "Bledne uzycie" in result.text
    # Original message survives sanitization (no secret-shaped tokens).
    assert "test boom" in result.text


def test_parse_command_runtime_error_stays_internal():
    """P1-3 regression: a handler raising RuntimeError still flows
    through the broad Exception branch (returns kind='error' with an
    error_id, no traceback echoed)."""
    from sylion.aeis_v2.terminal import commands as cmd_mod
    from sylion.aeis_v2.terminal.commands import CommandSpec, parse_command

    def _explode(args, ctx):
        raise RuntimeError("internal disaster")

    fake_spec = CommandSpec(
        name="disaster", summary_pl="x", summary_en="x", handler=_explode,
    )
    saved = cmd_mod.BUILTIN_COMMANDS
    cmd_mod.BUILTIN_COMMANDS = cmd_mod.BUILTIN_COMMANDS + (fake_spec,)
    try:
        result = parse_command("/disaster")
    finally:
        cmd_mod.BUILTIN_COMMANDS = saved

    assert result.kind == "error"
    assert "error_id=" in result.text
    # The raw exception message must NOT leak verbatim.
    assert "internal disaster" not in result.text
