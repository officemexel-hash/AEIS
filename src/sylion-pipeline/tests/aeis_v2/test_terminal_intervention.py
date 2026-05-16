"""W18 G2 step 1 — operator intervention API tests.

Covers the five new HTTP routes added in this commit:

    POST  /sessions/{id}/tasks/{tid}/pause
    POST  /sessions/{id}/tasks/{tid}/resume
    PATCH /sessions/{id}/tasks/{tid}              (operator edit)
    POST  /sessions/{id}/tasks/{tid}/skip
    POST  /sessions/{id}/cancel

Plus the audit JSONL emission and per-task ``intervention_log`` field.

The tests use a fresh ``SessionStore`` injected via the singleton getter
plus the FastAPI ``TestClient`` mounted on the production app — same
pattern as ``tests/aeis_v2/test_apps_routes.py`` and
``tests/aeis_v2/test_federation.py``. RBAC is disabled by default in the
project conftest so ``Depends(requires_role(...))`` passes through; the
shape of the dependency is still exercised by FastAPI's wiring.

State machine reminder
----------------------
::

    pending --(start)--> running --(pause)--> paused --(resume)--> running
        |                  |        |                  |
        |                  |        +--(patch ok)------+    (only paused/pending)
        |                  |
        +--(skip)----------+--(skip)---> skipped
        |                  |
        |                  +--(complete)--> done / failed
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from sylion.aeis_v2.terminal import get_session_store
from sylion.aeis_v2.terminal.sessions import SessionStore
from sylion.api import terminal_routes
from sylion.api.app import app


# --------------------------------------------------------------------------
# Test fixtures
# --------------------------------------------------------------------------


@pytest.fixture
def fresh_store(monkeypatch) -> SessionStore:
    """Replace the SessionStore singleton with a fresh instance per test.

    Without this, a stray task from a previous test would surface in the
    next test's session listing — especially noisy when tests run in
    parallel. We reach into the ``sessions`` module and swap the
    ``_store`` global so the route's call to ``get_session_store()``
    returns our isolated instance.
    """
    from sylion.aeis_v2.terminal import sessions as sessions_mod

    isolated = SessionStore()
    monkeypatch.setattr(sessions_mod, "_store", isolated)
    return isolated


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client mounted on the full production app."""
    return TestClient(app)


@pytest.fixture
def session_with_running_task(fresh_store: SessionStore) -> tuple[str, str]:
    """Create a session + one task already in ``running`` status.

    Returns ``(session_id, task_id)`` for direct use in pause/skip
    tests. We drive the task through ``store.update_task`` rather than
    going through HTTP because the goal is to set up state, not to
    exercise the start path.
    """
    sess = fresh_store.create("intervention test")
    task = fresh_store.add_task(sess.session_id, "step A", inputs={"k": "v0"})
    fresh_store.update_task(sess.session_id, task.task_id, status="running")
    return sess.session_id, task.task_id


# --------------------------------------------------------------------------
# A. Pause
# --------------------------------------------------------------------------


def test_pause_running_task_succeeds(
    client: TestClient,
    session_with_running_task: tuple[str, str],
    fresh_store: SessionStore,
) -> None:
    """Happy path: pausing a running task flips status to 'paused' and
    records intervention metadata."""
    sid, tid = session_with_running_task

    r = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/pause",
        json={"reason": "operator coffee break"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["task"]["status"] == "paused"
    assert body["task"]["pause_reason"] == "operator coffee break"
    assert body["task"]["paused_at"] is not None

    # Server-side state verifies the route mutated the same store.
    sess = fresh_store.get(sid)
    assert sess is not None
    task = sess.tasks[0]
    assert task.status == "paused"
    assert len(task.intervention_log) == 1
    assert task.intervention_log[0]["action"] == "pause"
    assert task.intervention_log[0]["reason"] == "operator coffee break"


def test_pause_pending_task_returns_409(
    client: TestClient, fresh_store: SessionStore,
) -> None:
    """A task that has not yet started ('pending') cannot be paused —
    pause is only meaningful for running tasks."""
    sess = fresh_store.create("s")
    task = fresh_store.add_task(sess.session_id, "pending step")
    # Task is still 'pending' — never moved to 'running'.
    assert task.status == "pending"

    r = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/{task.task_id}/pause",
        json={"reason": "x"},
    )
    assert r.status_code == 409, r.text
    assert "pending" in r.json()["detail"].lower()
    # Status unchanged.
    assert task.status == "pending"
    # No intervention recorded for the failed call.
    assert task.intervention_log == []


# --------------------------------------------------------------------------
# B. Resume
# --------------------------------------------------------------------------


def test_resume_paused_task_succeeds(
    client: TestClient,
    session_with_running_task: tuple[str, str],
    fresh_store: SessionStore,
) -> None:
    """Resume flips paused -> running, clears paused_at + pause_reason,
    and records the second intervention."""
    sid, tid = session_with_running_task

    # First pause it.
    p1 = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/pause",
        json={"reason": "wait"},
    )
    assert p1.status_code == 200

    # Then resume.
    r = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/resume",
        json={"reason": "back at it"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["task"]["status"] == "running"
    assert body["task"]["paused_at"] is None
    assert body["task"]["pause_reason"] == ""

    sess = fresh_store.get(sid)
    assert sess is not None
    task = sess.tasks[0]
    assert task.status == "running"
    # Two interventions: pause + resume.
    actions = [e["action"] for e in task.intervention_log]
    assert actions == ["pause", "resume"]


def test_resume_running_task_returns_409(
    client: TestClient,
    session_with_running_task: tuple[str, str],
) -> None:
    """A task that is already running cannot be resumed — resume is
    only valid from 'paused'."""
    sid, tid = session_with_running_task

    r = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/resume",
        json={"reason": "noop"},
    )
    assert r.status_code == 409, r.text
    assert "running" in r.json()["detail"].lower()


# --------------------------------------------------------------------------
# C. Patch (mid-flight edit)
# --------------------------------------------------------------------------


def test_patch_paused_task_updates_inputs(
    client: TestClient,
    session_with_running_task: tuple[str, str],
    fresh_store: SessionStore,
) -> None:
    """Operator pauses, then PATCHes ``inputs`` and ``title``. Both
    fields update; the diff appears in the response and in the audit."""
    sid, tid = session_with_running_task

    # Pause first so PATCH is allowed.
    pr = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/pause",
        json={"reason": "fix typo"},
    )
    assert pr.status_code == 200

    # Now patch.
    patch = client.patch(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}",
        json={
            "title": "step A (corrected)",
            "inputs": {"k": "v1", "max_tokens": 1024},
            "notes": "operator fixed param",
        },
    )
    assert patch.status_code == 200, patch.text
    body = patch.json()
    assert body["ok"] is True
    assert body["task"]["title"] == "step A (corrected)"
    assert body["task"]["inputs"] == {"k": "v1", "max_tokens": 1024}
    assert body["task"]["notes"] == "operator fixed param"
    # Diff shows the before/after for every changed field.
    diff = body["diff"]
    assert "title" in diff
    assert diff["inputs"]["from"] == {"k": "v0"}
    assert diff["inputs"]["to"] == {"k": "v1", "max_tokens": 1024}

    # Server-side the task is paused (PATCH does not auto-resume).
    sess = fresh_store.get(sid)
    assert sess is not None
    task = sess.tasks[0]
    assert task.status == "paused"
    # Three interventions logged: pause + patch.
    actions = [e["action"] for e in task.intervention_log]
    assert actions == ["pause", "patch"]


def test_patch_running_task_returns_409(
    client: TestClient,
    session_with_running_task: tuple[str, str],
) -> None:
    """Editing a running task is forbidden — would race with the agent.
    The state machine demands pause first."""
    sid, tid = session_with_running_task

    r = client.patch(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}",
        json={"title": "no good"},
    )
    assert r.status_code == 409, r.text
    detail = r.json()["detail"].lower()
    assert "running" in detail
    assert "paused" in detail or "pending" in detail


# --------------------------------------------------------------------------
# D. Skip
# --------------------------------------------------------------------------


def test_skip_task_records_intervention(
    client: TestClient,
    session_with_running_task: tuple[str, str],
    fresh_store: SessionStore,
) -> None:
    """Skip flips status to 'skipped', sets finished_at, and writes
    one audit row."""
    sid, tid = session_with_running_task

    r = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/skip",
        json={"reason": "stuck on retry"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["task"]["status"] == "skipped"

    sess = fresh_store.get(sid)
    assert sess is not None
    task = sess.tasks[0]
    assert task.status == "skipped"
    assert task.finished_at is not None
    # Exactly one intervention.
    assert len(task.intervention_log) == 1
    entry = task.intervention_log[0]
    assert entry["action"] == "skip"
    assert entry["reason"] == "stuck on retry"
    assert entry["before_state"]["status"] == "running"
    assert entry["after_state"]["status"] == "skipped"


def test_skip_done_task_returns_409(
    client: TestClient, fresh_store: SessionStore,
) -> None:
    """Skipping an already-completed task is rejected — done is
    terminal, skipping it would muddy the audit."""
    sess = fresh_store.create("s")
    task = fresh_store.add_task(sess.session_id, "done step")
    fresh_store.update_task(sess.session_id, task.task_id, status="done")

    r = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/{task.task_id}/skip",
        json={"reason": "no point"},
    )
    assert r.status_code == 409, r.text
    assert task.status == "done"


# --------------------------------------------------------------------------
# E. Cancel
# --------------------------------------------------------------------------


def test_cancel_session_skips_all_open_tasks(
    client: TestClient, fresh_store: SessionStore,
) -> None:
    """Cancel closes the session and forces every open task (pending /
    running / paused) to skipped. Already-terminal tasks are left as-is."""
    sess = fresh_store.create("cancel me")

    # 1 pending, 1 running, 1 paused, 1 already-done.
    t_pending = fresh_store.add_task(sess.session_id, "pending")
    t_running = fresh_store.add_task(sess.session_id, "running")
    t_paused = fresh_store.add_task(sess.session_id, "paused")
    t_done = fresh_store.add_task(sess.session_id, "done")
    fresh_store.update_task(sess.session_id, t_running.task_id, status="running")
    fresh_store.update_task(sess.session_id, t_paused.task_id, status="paused")
    fresh_store.update_task(sess.session_id, t_done.task_id, status="done")

    r = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/cancel",
        json={"reason": "operator pressed escape"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "closed"
    # Three open tasks were skipped; the done one is untouched.
    assert body["skipped_count"] == 3
    assert set(body["skipped_task_ids"]) == {
        t_pending.task_id, t_running.task_id, t_paused.task_id,
    }

    # Verify server state.
    final = fresh_store.get(sess.session_id)
    assert final is not None
    assert final.status == "closed"
    statuses = {t.task_id: t.status for t in final.tasks}
    assert statuses[t_pending.task_id] == "skipped"
    assert statuses[t_running.task_id] == "skipped"
    assert statuses[t_paused.task_id] == "skipped"
    assert statuses[t_done.task_id] == "done"  # untouched


# --------------------------------------------------------------------------
# F. Audit JSONL
# --------------------------------------------------------------------------


def test_intervention_audit_log_has_entries(
    client: TestClient,
    fresh_store: SessionStore,
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Every intervention writes one JSON line to the audit log path.

    We redirect ``INTERVENTION_AUDIT_LOG_PATH`` to a tmp file and exercise
    pause + resume + skip; the file should grow by exactly 3 lines, each
    a valid JSON object with the expected keys.
    """
    audit_path = tmp_path / "intervention_audit.jsonl"
    monkeypatch.setattr(
        terminal_routes, "INTERVENTION_AUDIT_LOG_PATH", audit_path,
    )

    # Set up: a session with one running task and one pending task.
    sess = fresh_store.create("audit-test")
    t1 = fresh_store.add_task(sess.session_id, "running step")
    t2 = fresh_store.add_task(sess.session_id, "pending step")
    fresh_store.update_task(sess.session_id, t1.task_id, status="running")

    # Pause t1, then resume, then skip t2 — three interventions.
    r1 = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/{t1.task_id}/pause",
        json={"reason": "p"},
    )
    assert r1.status_code == 200
    r2 = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/{t1.task_id}/resume",
        json={"reason": "r"},
    )
    assert r2.status_code == 200
    r3 = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/{t2.task_id}/skip",
        json={"reason": "s"},
    )
    assert r3.status_code == 200

    # The file exists and has exactly 3 well-formed JSONL rows.
    assert audit_path.exists()
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 3
    actions = [row["action"] for row in rows]
    assert actions == ["pause", "resume", "skip"]
    for row in rows:
        # Every row carries the canonical schema.
        for key in ("ts", "session_id", "task_id", "action", "actor", "reason", "before", "after"):
            assert key in row, f"missing {key} in audit row {row!r}"
        assert row["session_id"] == sess.session_id


def test_audit_jsonl_best_effort_on_disk_failure(
    client: TestClient,
    session_with_running_task: tuple[str, str],
    tmp_path: Path,
    monkeypatch,
) -> None:
    """If the audit JSONL cannot be written (disk full, permission
    error, ...) the API call must still succeed — pause is more
    important than a missing audit row.

    Strategy: redirect the audit path to a *directory* path (so
    ``open(..., "a")`` raises ``IsADirectoryError`` / ``PermissionError``)
    and verify the pause route still returns 200. The per-task
    intervention_log still receives the entry because that is in-memory
    and unaffected by disk failures.
    """
    sid, tid = session_with_running_task

    # Pointing the audit path at an existing directory makes the open
    # call raise on every platform (IsADirectoryError on POSIX,
    # PermissionError on Windows). Either way the route's try/except
    # in _emit_intervention_audit must swallow it.
    monkeypatch.setattr(
        terminal_routes, "INTERVENTION_AUDIT_LOG_PATH", tmp_path,
    )

    r = client.post(
        f"/api/v1/terminal/sessions/{sid}/tasks/{tid}/pause",
        json={"reason": "ok"},
    )
    assert r.status_code == 200, r.text
    # Even with the file write blowing up, the per-task log (in-memory)
    # is untouched and still receives the entry.
    from sylion.aeis_v2.terminal import sessions as sessions_mod
    sess = sessions_mod._store.get(sid)  # type: ignore[union-attr]
    assert sess is not None
    assert len(sess.tasks[0].intervention_log) == 1
    assert sess.tasks[0].intervention_log[0]["action"] == "pause"


# --------------------------------------------------------------------------
# G. State-machine 404s
# --------------------------------------------------------------------------


def test_pause_unknown_task_returns_404(
    client: TestClient, fresh_store: SessionStore,
) -> None:
    """Operator pointing at a task that does not exist gets 404, not
    409 — distinguishing 'no such task' from 'wrong state' makes
    debugging easier on the frontend."""
    sess = fresh_store.create("s")
    r = client.post(
        f"/api/v1/terminal/sessions/{sess.session_id}/tasks/nope/pause",
        json={"reason": "x"},
    )
    assert r.status_code == 404


def test_cancel_unknown_session_returns_404(
    client: TestClient, fresh_store: SessionStore,
) -> None:
    r = client.post(
        "/api/v1/terminal/sessions/no-such-session/cancel",
        json={"reason": "x"},
    )
    assert r.status_code == 404
