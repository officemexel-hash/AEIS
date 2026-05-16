"""Comprehensive tests for sylion.skills.executor (SkillsExecutor class)."""

import json
import sqlite3
import threading
import time

import pytest

from sylion.skills.executor import (
    Execution,
    SkillsExecutor,
    get_skills_executor,
)
from sylion.skills.registry import get_skills_registry, reset_skills_registry
from sylion.skills.runtime import reset_skills_runtime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def executor(tmp_path):
    """Fresh executor with registered runtime skills per test.

    SkillsExecutor intentionally fails closed for unknown skills; these tests
    exercise successful execution through registered PUBLISHED skills.
    """

    db_path = tmp_path / "skills_executor.sqlite"
    reset_skills_registry(db_path=db_path)
    reset_skills_runtime(db_path=db_path)
    executor = SkillsExecutor(db_path=db_path)
    registry = get_skills_registry(db_path=db_path)
    for skill_id in ("skill-1", "s1", "skill-alpha", "skill-beta", "skill-gamma"):
        registry.register(skill_id, skill_id.replace("-", " ").title(), domain="test")
        registry.publish(skill_id)
    return executor


@pytest.fixture
def populated_executor(executor):
    """Executor with several executions across skills."""
    r1 = executor.execute("skill-alpha", {"action": "analyze"})
    r2 = executor.execute("skill-alpha", {"action": "validate"})
    r3 = executor.execute("skill-beta", {"action": "generate"})
    r4 = executor.execute("skill-gamma", {"query": "test"})
    return executor, (r1, r2, r3, r4)


# ---------------------------------------------------------------------------
# Execution dataclass
# ---------------------------------------------------------------------------

class TestExecution:
    def test_execution_auto_generates_id(self):
        ex = Execution()
        assert ex.exec_id != ""
        assert len(ex.exec_id) == 32  # uuid4 hex

    def test_execution_auto_generates_timestamp(self):
        before = time.time()
        ex = Execution()
        after = time.time()
        assert before <= ex.timestamp <= after

    def test_execution_default_status(self):
        ex = Execution()
        assert ex.status == "pending"

    def test_execution_custom_values(self):
        ex = Execution(
            exec_id="custom-id",
            skill_id="s1",
            status="completed",
            duration_ms=42,
        )
        assert ex.exec_id == "custom-id"
        assert ex.skill_id == "s1"
        assert ex.status == "completed"
        assert ex.duration_ms == 42


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

class TestExecute:
    def test_execute_basic(self, executor):
        result = executor.execute("skill-1", {"key": "value"})
        assert result["skill_id"] == "skill-1"
        assert result["status"] == "completed"
        assert "exec_id" in result
        assert "output" in result
        assert "duration_ms" in result

    def test_execute_no_input(self, executor):
        result = executor.execute("skill-1")
        assert result["status"] == "completed"

    def test_execute_output_contains_result(self, executor):
        result = executor.execute("skill-1")
        assert result["output"]["result"] == "executed"
        assert result["output"]["skill_id"] == "skill-1"

    def test_execute_duration_non_negative(self, executor):
        result = executor.execute("skill-1")
        assert result["duration_ms"] >= 0

    def test_execute_generates_unique_exec_id(self, executor):
        r1 = executor.execute("skill-1")
        r2 = executor.execute("skill-1")
        assert r1["exec_id"] != r2["exec_id"]

    def test_execute_persists_to_db(self, executor):
        result = executor.execute("skill-1", {"x": 1})
        record = executor.get_execution(result["exec_id"])
        assert record is not None
        assert record["skill_id"] == "skill-1"
        assert record["input_data"] == {"x": 1}
        assert record["status"] == "completed"

    def test_execute_input_data_serialized(self, executor):
        data = {"nested": {"a": [1, 2]}, "val": True}
        result = executor.execute("s1", data)
        record = executor.get_execution(result["exec_id"])
        assert record["input_data"] == data

    def test_execute_with_empty_dict_input(self, executor):
        result = executor.execute("s1", {})
        record = executor.get_execution(result["exec_id"])
        assert record["input_data"] == {}


# ---------------------------------------------------------------------------
# GetExecution
# ---------------------------------------------------------------------------

class TestGetExecution:
    def test_get_existing(self, populated_executor):
        executor, (r1, _, _, _) = populated_executor
        record = executor.get_execution(r1["exec_id"])
        assert record is not None
        assert record["exec_id"] == r1["exec_id"]
        assert record["skill_id"] == "skill-alpha"

    def test_get_not_found(self, executor):
        assert executor.get_execution("nonexistent") is None

    def test_get_deserializes_json_fields(self, populated_executor):
        executor, (r1, _, _, _) = populated_executor
        record = executor.get_execution(r1["exec_id"])
        assert isinstance(record["input_data"], dict)
        assert isinstance(record["output_data"], dict)

    def test_get_all_fields_present(self, populated_executor):
        executor, (r1, _, _, _) = populated_executor
        record = executor.get_execution(r1["exec_id"])
        expected_keys = {
            "exec_id", "skill_id", "input_data", "output_data",
            "status", "duration_ms", "error", "timestamp",
        }
        assert expected_keys.issubset(record.keys())


# ---------------------------------------------------------------------------
# ListExecutions
# ---------------------------------------------------------------------------

class TestListExecutions:
    def test_list_all(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions()
        assert len(results) == 4

    def test_list_filter_by_skill(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(skill_id="skill-alpha")
        assert len(results) == 2
        assert all(r["skill_id"] == "skill-alpha" for r in results)

    def test_list_filter_by_status(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(status="completed")
        assert len(results) == 4
        assert all(r["status"] == "completed" for r in results)

    def test_list_filter_status_no_match(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(status="failed")
        assert results == []

    def test_list_combined_filters(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(skill_id="skill-alpha", status="completed")
        assert len(results) == 2

    def test_list_limit(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(limit=2)
        assert len(results) == 2

    def test_list_ordered_by_timestamp_desc(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions()
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_list_empty(self, executor):
        results = executor.list_executions()
        assert results == []


# ---------------------------------------------------------------------------
# GetStats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty(self, executor):
        stats = executor.get_stats()
        assert stats["total_executions"] == 0
        assert stats["by_status"] == {}
        assert stats["avg_duration_ms"] == 0.0
        assert stats["by_skill"] == {}

    def test_stats_populated(self, populated_executor):
        executor, _ = populated_executor
        stats = executor.get_stats()
        assert stats["total_executions"] == 4
        assert stats["by_status"]["completed"] == 4
        assert stats["avg_duration_ms"] >= 0.0

    def test_stats_by_skill(self, populated_executor):
        executor, _ = populated_executor
        stats = executor.get_stats()
        assert stats["by_skill"]["skill-alpha"] == 2
        assert stats["by_skill"]["skill-beta"] == 1
        assert stats["by_skill"]["skill-gamma"] == 1

    def test_stats_avg_duration_type(self, populated_executor):
        executor, _ = populated_executor
        stats = executor.get_stats()
        assert isinstance(stats["avg_duration_ms"], float)

    def test_stats_total_equals_sum_of_status(self, populated_executor):
        executor, _ = populated_executor
        stats = executor.get_stats()
        total_by_status = sum(stats["by_status"].values())
        assert stats["total_executions"] == total_by_status


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------

class TestGetSkillsExecutorFactory:
    def test_factory_returns_instance(self):
        inst = get_skills_executor()
        assert isinstance(inst, SkillsExecutor)

    def test_factory_idempotent(self):
        a = get_skills_executor()
        b = get_skills_executor()
        assert a is b


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_executes(self, executor):
        errors = []
        results = []

        def run_exec(idx):
            try:
                r = executor.execute(f"skill-{idx}", {"idx": idx})
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_exec, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = executor.get_stats()
        assert stats["total_executions"] == 30

    def test_concurrent_reads_and_writes(self, executor):
        """Writers insert rows; readers only call list_executions (safe concurrent reads
        with SQLite in WAL mode). get_stats is verified separately after writes complete,
        since in-memory SQLite has no WAL and AVG can return None mid-write."""
        errors = []
        write_count = 20
        retriable = (sqlite3.OperationalError, sqlite3.InterfaceError)

        def writer():
            for i in range(10):
                for attempt in range(8):
                    try:
                        executor.execute("s-writer", {"i": i})
                        break
                    except retriable:
                        if attempt == 7:
                            errors.append(RuntimeError(f"writer gave up on iteration {i}"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        def reader():
            for _ in range(10):
                for attempt in range(8):
                    try:
                        executor.list_executions()
                        break
                    except (sqlite3.OperationalError, sqlite3.InterfaceError, TypeError):
                        if attempt == 7:
                            errors.append(RuntimeError("reader gave up"))
                        time.sleep(0.05 * (2 ** attempt))
                    except Exception as e:
                        errors.append(e)
                        break

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        time.sleep(0.1)
        for t in threads:
            t.join(timeout=10)

        assert not errors
        stats = executor.get_stats()
        assert stats["total_executions"] == write_count


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_execute_large_input(self, executor):
        big_data = {"payload": "x" * 100_000}
        result = executor.execute("s1", big_data)
        record = executor.get_execution(result["exec_id"])
        assert record["input_data"]["payload"] == "x" * 100_000

    def test_execute_special_characters_in_input(self, executor):
        data = {"unicode": "cafe\u0301", "emoji": "\U0001f600", "quotes": '"hello"'}
        result = executor.execute("s1", data)
        record = executor.get_execution(result["exec_id"])
        assert record["input_data"] == data

    def test_execute_null_input_treated_as_empty(self, executor):
        result = executor.execute("s1", None)
        record = executor.get_execution(result["exec_id"])
        assert record["input_data"] == {}

    def test_list_executions_limit_one(self, populated_executor):
        executor, _ = populated_executor
        results = executor.list_executions(limit=1)
        assert len(results) == 1
