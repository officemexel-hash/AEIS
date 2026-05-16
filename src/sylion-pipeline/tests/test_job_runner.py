"""
Comprehensive tests for sylion.execution.job_runner.

Tests JobRunner class: submit, get_next, complete, fail, get_job,
list_jobs, get_stats, edge cases, thread safety, event emission.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.job_runner import (
    Job,
    JobRunner,
    get_job_runner,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> JobRunner:
    """Fresh in-memory JobRunner per test."""
    return JobRunner()


@pytest.fixture
def runner_with_bus() -> tuple[JobRunner, MagicMock]:
    """JobRunner with a mock EventBus."""
    bus = MagicMock(spec=EventBus)
    jr = JobRunner(event_bus=bus)
    return jr, bus


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestJobDataclass:

    def test_defaults(self):
        job = Job()
        assert job.job_id == ""
        assert job.status == "queued"
        assert job.priority == 0
        assert job.payload == {}

    def test_auto_timestamp(self):
        before = time.time()
        job = Job(job_type="test")
        after = time.time()
        assert before <= job.created_at <= after

    def test_no_auto_timestamp_when_set(self):
        job = Job(created_at=999.0)
        assert job.created_at == 999.0

    def test_with_payload(self):
        job = Job(job_type="email", payload={"to": "a@b.com"}, priority=5)
        assert job.payload["to"] == "a@b.com"
        assert job.priority == 5


# ---------------------------------------------------------------------------
# submit
# ---------------------------------------------------------------------------

class TestSubmit:

    def test_basic_submit(self, runner):
        result = runner.submit("email")
        assert "job_id" in result
        assert result["status"] == "queued"

    def test_with_payload(self, runner):
        result = runner.submit("report", payload={"format": "pdf"})
        job = runner.get_job(result["job_id"])
        assert job["payload"]["format"] == "pdf"

    def test_with_priority(self, runner):
        result = runner.submit("high", priority=10)
        job = runner.get_job(result["job_id"])
        assert job["priority"] == 10

    def test_default_payload_empty(self, runner):
        result = runner.submit("minimal")
        job = runner.get_job(result["job_id"])
        assert job["payload"] == {}

    def test_default_priority_zero(self, runner):
        result = runner.submit("minimal")
        job = runner.get_job(result["job_id"])
        assert job["priority"] == 0

    def test_unique_job_ids(self, runner):
        r1 = runner.submit("a")
        r2 = runner.submit("b")
        assert r1["job_id"] != r2["job_id"]

    def test_emits_submitted_event(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.submit("email", payload={"to": "x"}, priority=3)
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert isinstance(event, SylionEvent)
        assert event.topic == "execution.job.submitted"
        assert event.payload["job_type"] == "email"
        assert event.payload["priority"] == 3


# ---------------------------------------------------------------------------
# get_next
# ---------------------------------------------------------------------------

class TestGetNext:

    def test_returns_highest_priority(self, runner):
        runner.submit("low", priority=1)
        runner.submit("high", priority=10)
        runner.submit("mid", priority=5)
        job = runner.get_next()
        assert job["job_type"] == "high"
        assert job["status"] == "running"

    def test_empty_queue_returns_none(self, runner):
        assert runner.get_next() is None

    def test_fifo_on_same_priority(self, runner):
        runner.submit("first", priority=5)
        time.sleep(0.01)
        runner.submit("second", priority=5)
        job = runner.get_next()
        assert job["job_type"] == "first"

    def test_marks_as_running(self, runner):
        runner.submit("task")
        job = runner.get_next()
        assert job["status"] == "running"
        assert job["started_at"] > 0

    def test_payload_deserialized(self, runner):
        runner.submit("data", payload={"key": "value"})
        job = runner.get_next()
        assert isinstance(job["payload"], dict)
        assert job["payload"]["key"] == "value"

    def test_subsequent_get_next_skips_running(self, runner):
        runner.submit("only")
        first = runner.get_next()
        assert first is not None
        second = runner.get_next()
        assert second is None

    def test_emits_started_event(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.submit("task")
        bus.publish.reset_mock()
        jr.get_next()
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.job.started"


# ---------------------------------------------------------------------------
# complete
# ---------------------------------------------------------------------------

class TestComplete:

    def test_complete_running_job(self, runner):
        runner.submit("task")
        job = runner.get_next()
        assert runner.complete(job["job_id"], result="Done") is True
        fetched = runner.get_job(job["job_id"])
        assert fetched["status"] == "completed"
        assert fetched["result"] == "Done"

    def test_complete_nonexistent_returns_false(self, runner):
        assert runner.complete("ghost-id") is False

    def test_sets_completed_at(self, runner):
        runner.submit("task")
        job = runner.get_next()
        runner.complete(job["job_id"])
        fetched = runner.get_job(job["job_id"])
        assert fetched["completed_at"] > 0

    def test_emits_completed_event(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.submit("task")
        job = jr.get_next()
        bus.publish.reset_mock()
        jr.complete(job["job_id"], result="ok")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.job.completed"

    def test_no_event_on_nonexistent(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.complete("ghost-id")
        bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# fail
# ---------------------------------------------------------------------------

class TestFail:

    def test_fail_running_job(self, runner):
        runner.submit("task")
        job = runner.get_next()
        assert runner.fail(job["job_id"], error="Timeout") is True
        fetched = runner.get_job(job["job_id"])
        assert fetched["status"] == "failed"
        assert fetched["error"] == "Timeout"

    def test_fail_nonexistent_returns_false(self, runner):
        assert runner.fail("ghost-id") is False

    def test_sets_completed_at(self, runner):
        runner.submit("task")
        job = runner.get_next()
        runner.fail(job["job_id"])
        fetched = runner.get_job(job["job_id"])
        assert fetched["completed_at"] > 0

    def test_emits_failed_event(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.submit("task")
        job = jr.get_next()
        bus.publish.reset_mock()
        jr.fail(job["job_id"], error="err")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.job.failed"

    def test_no_event_on_nonexistent_fail(self, runner_with_bus):
        jr, bus = runner_with_bus
        jr.fail("ghost-id")
        bus.publish.assert_not_called()


# ---------------------------------------------------------------------------
# get_job
# ---------------------------------------------------------------------------

class TestGetJob:

    def test_existing_job(self, runner):
        result = runner.submit("fetch")
        job = runner.get_job(result["job_id"])
        assert job is not None
        assert job["job_type"] == "fetch"

    def test_nonexistent_returns_none(self, runner):
        assert runner.get_job("ghost") is None

    def test_payload_parsed(self, runner):
        runner.submit("data", payload={"x": 1})
        jobs = runner.list_jobs()
        job = runner.get_job(jobs[0]["job_id"])
        assert isinstance(job["payload"], dict)
        assert job["payload"]["x"] == 1


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestListJobs:

    def test_empty(self, runner):
        assert runner.list_jobs() == []

    def test_all_jobs(self, runner):
        runner.submit("a")
        runner.submit("b")
        runner.submit("c")
        jobs = runner.list_jobs()
        assert len(jobs) == 3

    def test_filter_by_status(self, runner):
        runner.submit("queued_job")
        runner.submit("to_complete")
        job = runner.get_next()
        runner.complete(job["job_id"])
        queued = runner.list_jobs(status="queued")
        completed = runner.list_jobs(status="completed")
        assert len(queued) == 1
        assert len(completed) == 1

    def test_limit(self, runner):
        for i in range(10):
            runner.submit(f"job-{i}")
        jobs = runner.list_jobs(limit=5)
        assert len(jobs) == 5

    def test_ordered_by_created_at_desc(self, runner):
        runner.submit("first")
        time.sleep(0.01)
        runner.submit("second")
        jobs = runner.list_jobs()
        assert jobs[0]["job_type"] == "second"
        assert jobs[1]["job_type"] == "first"

    def test_payloads_deserialized(self, runner):
        runner.submit("data", payload={"k": "v"})
        jobs = runner.list_jobs()
        assert isinstance(jobs[0]["payload"], dict)
        assert jobs[0]["payload"]["k"] == "v"


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:

    def test_empty_stats(self, runner):
        stats = runner.get_stats()
        assert stats["total_jobs"] == 0
        assert stats["by_status"] == {}

    def test_stats_after_submit(self, runner):
        runner.submit("a")
        runner.submit("b")
        stats = runner.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["by_status"]["queued"] == 2

    def test_stats_mixed_statuses(self, runner):
        runner.submit("a")
        runner.submit("b")
        job = runner.get_next()
        runner.complete(job["job_id"])
        stats = runner.get_stats()
        assert stats["total_jobs"] == 2
        assert stats["by_status"]["completed"] == 1
        assert stats["by_status"]["queued"] == 1

    def test_stats_after_fail(self, runner):
        runner.submit("failing")
        job = runner.get_next()
        runner.fail(job["job_id"])
        stats = runner.get_stats()
        assert stats["by_status"]["failed"] == 1

    def test_stats_returns_dict(self, runner):
        stats = runner.get_stats()
        assert isinstance(stats, dict)
        assert "total_jobs" in stats
        assert "by_status" in stats


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestJobRunnerThreadSafety:

    def test_concurrent_submit(self):
        jr = JobRunner()
        results = []
        errors = []

        def submit_job(name):
            try:
                r = jr.submit(name, payload={"thread": name})
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=submit_job, args=(f"job-{i}",))
                   for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 30
        stats = jr.get_stats()
        assert stats["total_jobs"] == 30

    def test_concurrent_get_next(self):
        jr = JobRunner()
        for i in range(20):
            jr.submit(f"job-{i}", priority=i)

        picked = []
        errors = []

        def get_job():
            try:
                job = jr.get_next()
                if job:
                    picked.append(job["job_id"])
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_job) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(picked) == 20
        # No duplicates
        assert len(set(picked)) == 20

    def test_concurrent_submit_and_complete(self):
        jr = JobRunner()
        job_ids = []
        errors = []

        # Submit all
        for i in range(10):
            r = jr.submit(f"job-{i}")
            job_ids.append(r["job_id"])

        # Pick all
        for _ in range(10):
            jr.get_next()

        # Complete concurrently
        def complete_job(jid):
            try:
                jr.complete(jid, result="done")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=complete_job, args=(jid,))
                   for jid in job_ids]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = jr.get_stats()
        assert stats["by_status"]["completed"] == 10


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestGetJobRunnerSingleton:

    def test_returns_instance(self):
        import sylion.execution.job_runner as mod
        mod._runner = None
        jr = get_job_runner()
        assert isinstance(jr, JobRunner)
        mod._runner = None

    def test_singleton_reuse(self):
        import sylion.execution.job_runner as mod
        mod._runner = None
        jr1 = get_job_runner()
        jr2 = get_job_runner()
        assert jr1 is jr2
        mod._runner = None

    def test_singleton_with_args(self):
        import sylion.execution.job_runner as mod
        mod._runner = None
        bus = MagicMock(spec=EventBus)
        jr = get_job_runner(event_bus=bus)
        assert jr._event_bus is bus
        mod._runner = None
