from unittest.mock import MagicMock, call

import pytest

from sylion.aeis.advisor._db import PgAdvisoryLock


def _conn(*rows):
    cur = MagicMock()
    cur.__enter__.return_value = cur
    cur.fetchone.side_effect = list(rows)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def test_enter_uses_blocking_lock():
    conn, cur = _conn()
    assert PgAdvisoryLock(conn, 7).__enter__() is not None
    cur.execute.assert_called_once_with("SELECT pg_advisory_lock(%s)", (7,))


def test_exit_unlocks():
    conn, cur = _conn()
    PgAdvisoryLock(conn, 9).__exit__(None, None, None)
    cur.execute.assert_called_once_with("SELECT pg_advisory_unlock(%s)", (9,))


def test_try_lock_retries_then_succeeds(monkeypatch):
    now = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr("sylion.aeis.advisor._db.time.time", lambda: next(now))
    sleep = []
    monkeypatch.setattr("sylion.aeis.advisor._db.time.sleep", sleep.append)
    conn, cur = _conn((False,), (True,))
    PgAdvisoryLock(conn, 3, timeout_s=1.0, sleep_s=0.01).__enter__()
    assert cur.execute.call_args_list == [call("SELECT pg_try_advisory_lock(%s)", (3,))] * 2
    assert sleep == [0.01]


def test_try_lock_times_out(monkeypatch):
    now = iter([0.0, 0.1, 0.2, 0.3])
    monkeypatch.setattr("sylion.aeis.advisor._db.time.time", lambda: next(now))
    monkeypatch.setattr("sylion.aeis.advisor._db.time.sleep", lambda _: None)
    conn, cur = _conn((False,), (False,), (False,))
    with pytest.raises(TimeoutError, match="11"):
        PgAdvisoryLock(conn, 11, timeout_s=0.25, sleep_s=0.01).__enter__()
    assert cur.execute.call_count == 2
