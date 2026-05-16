"""Tests for sylion.aeis_v2.terminal modules (W18)."""
from __future__ import annotations

import pytest

from sylion.aeis_v2.terminal import (
    BUILTIN_COMMANDS, CommandResult, SessionStore, TerminalSession,
    get_session_store, list_commands, parse_command,
)
from sylion.aeis_v2.terminal.stream import (
    EventFilter, EventSubscriber, TerminalBroadcaster, TerminalEvent,
    get_broadcaster,
)

@pytest.fixture
def session_store():
    return SessionStore()

def test_session_store_singleton(session_store):
    assert get_session_store() is session_store

def test_create_session_returns_object():
    session = TerminalSession.create('My session')
    assert isinstance(session, TerminalSession)
    assert len(session.session_id) == 12
    assert session.tasks == []

def test_session_id_format():
    session_id = TerminalSession.create('Test session').session_id
    assert len(session_id) == 12

def test_add_task_to_session():
    session = TerminalSession.create('My session')
    task_count_before = len(session.tasks)
    session.add_task('Task 1', status='todo')
    task_count_after = len(session.tasks)
    assert task_count_after == task_count_before + 1

def test_update_task_status():
    session = TerminalSession.create('My session')
    session.add_task('Task 1', status='todo')
    assert session.tasks[0].status != 'running'
    session.update_task(0, {'status': 'running'})
    assert session.tasks[0].started_at is not None
    session.update_task(0, {'status': 'done'})
    assert session.tasks[0].finished_at is not None

def test_update_task_progress_clamped():
    task = TerminalSession.Task('Task 1', status='todo')
    task.progress = 2.0
    assert task.progress == 1.0
    task.progress = -1.0
    assert task.progress == 0.0

def test_close_session():
    session = TerminalSession.create('My session')
    session.close()
    assert session.status == 'closed'

def test_progress_pct_zero_when_no_tasks(session_store):
    session = TerminalSession.create('Test session', store=session_store)
    result = CommandResult.parse_command('/progress')
    assert result.kind == 'text'
    assert result.text == '0%'

def test_append_event_caps_buffer():
    broadcaster = get_broadcaster()
    event_filter = EventFilter(layers=['W14'], cap=200)
    subscriber = EventSubscriber(broadcaster, filter=event_filter)
    for _ in range(250):
        broadcaster.send(TerminalEvent(layer='W13', message='Test event'))
    assert len(subscriber.buffer) == 200

def test_get_unknown_session_returns_none():
    session_store = SessionStore()
    result = CommandResult.parse_command('/show abc')
    assert result.kind == 'error'
    assert result.text == "No such session: 'abc'"

@pytest.mark.parametrize("command, expected_kind", [
    ("/status", {"kind": "text", "text": "SYLION AEIS"}),
    ("/help", {"kind": "table", "rows": [{"name": "command", "summary": "de
"description"}] * 14}),
    ("/foobar", {"kind": "error", "text": "Unknown command: '/foobar'"}),
    ("", {"kind": "error", "text": "Command is empty."}),
    ("/?", {"kind": "table", "rows": [{"name": "command", "summary": "descr
"description"}] * 14}),
])
def test_parse_command(command, expected_kind):
    result = parse_command(command)
    assert result.kind == expected_kind["kind"]
    if "text" in expected_kind:
        assert expected_kind["text"] in result.text
    if "rows" in expected_kind:
        assert len(result.data) == len(expected_kind["rows"])

@pytest.mark.parametrize("command, expected", [
    ("diff sessions a b", {"kind": "not_implemented", "meta": ["a", "b"]}),
"b"]}),
    ("replay", {"kind": "error", "text": "No session id provided."})
provided."}),
    ("replay xyz", {"kind": "not_implemented", "meta": {"target": "xyz"}}),
"xyz"}}),
    ("focus", {"kind": "error", "text": "No focus target provided.
provided."}),
])
def test_parse_command_error(command, expected):
    result = parse_command(command)
    assert result.kind == expected["kind"]
    if "text" in expected:
        assert expected["text"] in result.text
    if "meta" in expected:
        assert expected["meta"].items() <= result.data.items()

def test_list_commands_returns_dict_per_command():
    commands = list_commands()
    for command_name, cmd_data in BUILTIN_COMMANDS.items():
        assert command_name in commands
        assert isinstance(commands[command_name], dict)
        assert "name" in commands[command_name]
        assert "args" in commands[command_name]
        assert "summary" in commands[command_name]

def test_event_filter_layers():
    event = TerminalEvent(layer='W14', message='Test')
    filter_ = EventFilter(layers=['W15'])
    assert not filter_.match(event)

def test_event_filter_empty_matches_all():
    filter_ = EventFilter()
    events = [TerminalEvent(layer='W13', message='Test') for _ in range(20)
range(20)]
    matches = sum(filter_.match(e) for e in events)
    assert matches == 20

def test_subscriber_drops_when_full():
    broadcaster = get_broadcaster(queue_max=1)
    subscriber = EventSubscriber(broadcaster, filter=EventFilter(layers=['W
filter=EventFilter(layers=['W14']))
    broadcaster.send(TerminalEvent(layer='W13', message='Test'))
    broadcaster.send(TerminalEvent(layer='W13', message='Another Test'))
    assert subscriber.dropped_count == 1

def test_subscriber_filter_pre_drop():
    broadcaster = get_broadcaster(queue_max=1)
    subscriber = EventSubscriber(broadcaster, filter=EventFilter(layers=['W
filter=EventFilter(layers=['W15']))
    broadcaster.send(TerminalEvent(layer='W14', message='Test'))
    assert len(subscriber.buffer) == 0

def test_to_sse_payload_format():
    event = TerminalEvent(layer='W13', message='Test')
    payload = event.to_sse_payload()
    assert payload.startswith('data: ')
    assert payload.endswith('\n\n')

