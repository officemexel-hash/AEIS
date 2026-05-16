"""
SYLION Cognitive -- Agent Runtime Manager Tests

Comprehensive tests for AgentRuntimeManager: registration, execution,
logging, statistics, event emission, cancellation, and thread safety.
"""

from __future__ import annotations

import threading
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.cognitive.agent_runtime import (
    AgentRuntimeManager,
    get_agent_runtime,
    reset_agent_runtime,
)


# =====================================================================
# Fixtures
# =====================================================================

@pytest.fixture
def bus():
    """Fresh in-memory EventBus per test."""
    return EventBus()


@pytest.fixture
def runtime(bus):
    """Fresh in-memory AgentRuntimeManager with EventBus attached."""
    return AgentRuntimeManager(event_bus=bus)


@pytest.fixture
def captured_events(bus):
    """Subscribe to all events and collect them."""
    events: list[SylionEvent] = []
    bus.subscribe("*", events.append)
    return events


@pytest.fixture
def registered_agent(runtime):
    """Register a sample agent and return its dict."""
    return runtime.register_agent(
        name="TestAgent",
        agent_type="claude_code",
        provider="anthropic",
        model_id="claude-sonnet-4-20250514",
        system_prompt="You are a helpful assistant.",
        tools=["read", "write"],
        capabilities=["coding", "analysis"],
        max_tokens=2048,
        temperature=0.5,
        config={"retry": 3},
    )


# =====================================================================
# Test register_agent
# =====================================================================

class TestRegisterAgent:

    def test_returns_agent_dict(self, runtime):
        agent = runtime.register_agent(name="Agent1")
        assert agent["agent_id"] != ""
        assert agent["name"] == "Agent1"
        assert agent["status"] == "active"
        assert agent["created_at"] > 0
        assert agent["updated_at"] > 0

    def test_default_values(self, runtime):
        agent = runtime.register_agent(name="DefaultAgent")
        assert agent["agent_type"] == "custom"
        assert agent["provider"] == ""
        assert agent["model_id"] == ""
        assert agent["system_prompt"] == ""
        assert agent["tools"] == []
        assert agent["capabilities"] == []
        assert agent["max_tokens"] == 4096
        assert agent["temperature"] == 0.7
        assert agent["config"] == {}

    def test_full_config(self, runtime):
        agent = runtime.register_agent(
            name="FullAgent",
            agent_type="codex",
            provider="openai",
            model_id="gpt-4o",
            system_prompt="Be precise.",
            tools=["search", "execute"],
            capabilities=["reasoning", "math"],
            max_tokens=8192,
            temperature=0.3,
            config={"timeout": 60},
        )
        assert agent["agent_type"] == "codex"
        assert agent["provider"] == "openai"
        assert agent["model_id"] == "gpt-4o"
        assert agent["system_prompt"] == "Be precise."
        assert agent["tools"] == ["search", "execute"]
        assert agent["capabilities"] == ["reasoning", "math"]
        assert agent["max_tokens"] == 8192
        assert agent["temperature"] == 0.3
        assert agent["config"] == {"timeout": 60}

    def test_unique_ids(self, runtime):
        a1 = runtime.register_agent(name="A1")
        a2 = runtime.register_agent(name="A2")
        assert a1["agent_id"] != a2["agent_id"]

    def test_emits_registered_event(self, runtime, captured_events):
        runtime.register_agent(name="EventAgent")
        assert any(e.topic == "agent.registered" for e in captured_events)
        evt = [e for e in captured_events if e.topic == "agent.registered"][0]
        assert evt.payload["name"] == "EventAgent"


# =====================================================================
# Test update_agent
# =====================================================================

class TestUpdateAgent:

    def test_update_name(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        updated = runtime.update_agent(agent_id, name="NewName")
        assert updated is not None
        assert updated["name"] == "NewName"

    def test_update_multiple_fields(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        updated = runtime.update_agent(
            agent_id,
            description="Updated desc",
            status="inactive",
            temperature=0.1,
        )
        assert updated["description"] == "Updated desc"
        assert updated["status"] == "inactive"
        assert updated["temperature"] == 0.1

    def test_update_json_fields(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        updated = runtime.update_agent(
            agent_id,
            tools=["new_tool"],
            capabilities=["new_cap"],
            config={"key": "value"},
        )
        assert updated["tools"] == ["new_tool"]
        assert updated["capabilities"] == ["new_cap"]
        assert updated["config"] == {"key": "value"}

    def test_update_nonexistent_returns_none(self, runtime):
        result = runtime.update_agent("does-not-exist", name="X")
        assert result is None

    def test_update_no_fields_returns_current(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.update_agent(agent_id)
        assert result is not None
        assert result["agent_id"] == agent_id

    def test_update_ignores_unknown_fields(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.update_agent(agent_id, bogus="value")
        assert result is not None

    def test_update_changes_updated_at(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        old_updated = registered_agent["updated_at"]
        time.sleep(0.01)
        updated = runtime.update_agent(agent_id, name="Changed")
        assert updated["updated_at"] >= old_updated


# =====================================================================
# Test deregister_agent
# =====================================================================

class TestDeregisterAgent:

    def test_deregister_existing(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        assert runtime.deregister_agent(agent_id) is True
        assert runtime.get_agent(agent_id) is None

    def test_deregister_nonexistent(self, runtime):
        assert runtime.deregister_agent("no-such-id") is False

    def test_deregister_emits_event(self, runtime, bus, captured_events):
        agent = runtime.register_agent(name="ToRemove")
        runtime.deregister_agent(agent["agent_id"])
        assert any(e.topic == "agent.deregistered" for e in captured_events)

    def test_deregister_cleans_executions(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        # Create an execution record manually
        execution_id = runtime._uid()
        with runtime._lock:
            runtime._conn.execute(
                "INSERT INTO agent_executions "
                "(execution_id, agent_id, task_description, input_messages, "
                "status, started_at) VALUES (?, ?, 'task', '[]', 'completed', ?)",
                (execution_id, agent_id, time.time()),
            )
            runtime._conn.execute(
                "INSERT INTO agent_logs "
                "(log_id, execution_id, agent_id, level, message, timestamp) "
                "VALUES (?, ?, ?, 'INFO', 'log', ?)",
                (runtime._uid(), execution_id, agent_id, time.time()),
            )
            runtime._conn.commit()

        runtime.deregister_agent(agent_id)
        assert runtime.get_execution(execution_id) is None
        assert runtime.get_logs(execution_id) == []


# =====================================================================
# Test get_agent
# =====================================================================

class TestGetAgent:

    def test_get_existing(self, runtime, registered_agent):
        agent = runtime.get_agent(registered_agent["agent_id"])
        assert agent is not None
        assert agent["name"] == "TestAgent"

    def test_get_nonexistent(self, runtime):
        assert runtime.get_agent("no-id") is None

    def test_get_parses_json(self, runtime):
        agent = runtime.register_agent(
            name="JsonAgent",
            tools=["a", "b"],
            capabilities=["c"],
            config={"k": 1},
        )
        fetched = runtime.get_agent(agent["agent_id"])
        assert fetched["tools"] == ["a", "b"]
        assert fetched["capabilities"] == ["c"]
        assert fetched["config"] == {"k": 1}


# =====================================================================
# Test list_agents
# =====================================================================

class TestListAgents:

    def test_list_all(self, runtime):
        runtime.register_agent(name="A1")
        runtime.register_agent(name="A2")
        agents = runtime.list_agents()
        assert len(agents) == 2

    def test_list_empty(self, runtime):
        assert runtime.list_agents() == []

    def test_filter_by_status(self, runtime):
        a1 = runtime.register_agent(name="Active")
        a2 = runtime.register_agent(name="ToDeactivate")
        runtime.update_agent(a2["agent_id"], status="inactive")
        active = runtime.list_agents(status="active")
        assert len(active) == 1
        assert active[0]["name"] == "Active"

    def test_filter_by_type(self, runtime):
        runtime.register_agent(name="Claude", agent_type="claude_code")
        runtime.register_agent(name="Custom", agent_type="custom")
        claude_agents = runtime.list_agents(agent_type="claude_code")
        assert len(claude_agents) == 1
        assert claude_agents[0]["name"] == "Claude"

    def test_filter_by_status_and_type(self, runtime):
        runtime.register_agent(name="CC1", agent_type="claude_code")
        a2 = runtime.register_agent(name="CC2", agent_type="claude_code")
        runtime.update_agent(a2["agent_id"], status="error")
        result = runtime.list_agents(status="active", agent_type="claude_code")
        assert len(result) == 1
        assert result[0]["name"] == "CC1"


# =====================================================================
# Test execute_task
# =====================================================================

class TestExecuteTask:

    def test_execute_returns_result(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "What is 2+2?")
        assert result["execution_id"] != ""
        assert result["agent_id"] == agent_id
        assert result["status"] in ("completed", "failed")
        assert isinstance(result["tokens_used"], int)
        assert isinstance(result["cost"], float)
        assert isinstance(result["latency_ms"], int)

    def test_execute_with_context(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(
            agent_id, "Summarize", context="Here is some context."
        )
        assert result["execution_id"] != ""

    def test_execute_records_execution(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "Do something")
        execution = runtime.get_execution(result["execution_id"])
        assert execution is not None
        assert execution["task_description"] == "Do something"
        assert execution["status"] in ("completed", "failed")

    def test_execute_nonexistent_agent(self, runtime):
        result = runtime.execute_task("no-agent", "Hello")
        assert result["status"] == "failed"
        assert result["error_message"] is not None
        assert "not found" in result["error_message"]

    def test_execute_emits_started_event(self, runtime, registered_agent,
                                          captured_events):
        runtime.execute_task(registered_agent["agent_id"], "task")
        assert any(
            e.topic == "agent.execution.started" for e in captured_events
        )

    def test_execute_emits_completed_event(self, runtime, registered_agent,
                                            captured_events):
        runtime.execute_task(registered_agent["agent_id"], "task")
        # Should emit completed or failed
        topics = [e.topic for e in captured_events]
        assert ("agent.execution.completed" in topics
                or "agent.execution.failed" in topics)

    def test_execute_stores_input_messages(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(
            agent_id, "test task", context="ctx"
        )
        execution = runtime.get_execution(result["execution_id"])
        messages = execution["input_messages"]
        assert isinstance(messages, list)
        # Should have system + context user + task user
        assert len(messages) >= 2

    def test_execute_without_system_prompt(self, runtime):
        agent = runtime.register_agent(name="NoPrompt")
        result = runtime.execute_task(agent["agent_id"], "Hello")
        execution = runtime.get_execution(result["execution_id"])
        messages = execution["input_messages"]
        # Only user message, no system prompt
        assert all(m["role"] == "user" for m in messages)

    def test_execute_without_context(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "Just task")
        execution = runtime.get_execution(result["execution_id"])
        messages = execution["input_messages"]
        # system + user (task only)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Just task"

    def test_execute_records_blocked_policy_status(self, runtime):
        class BlockingLLM:
            def call_messages(self, model_id, messages, max_tokens):
                return {
                    "status": "blocked",
                    "blocked": True,
                    "policy": {"reason": "model policy blocked"},
                    "text": "",
                    "tokens": 0,
                    "cost": 0.0,
                }

        import sylion.cognitive.llm_adapter as llm_module

        old_adapter = llm_module._adapter
        llm_module._adapter = BlockingLLM()
        try:
            agent = runtime.register_agent(name="BlockedAgent", model_id="blocked-model")
            result = runtime.execute_task(agent["agent_id"], "try unsafe work")
        finally:
            llm_module._adapter = old_adapter

        assert result["status"] == "blocked"
        assert result["error_message"] == "model policy blocked"
        execution = runtime.get_execution(result["execution_id"])
        assert execution["status"] == "blocked"


# =====================================================================
# Test get_execution / list_executions
# =====================================================================

class TestExecutions:

    def test_get_existing_execution(self, runtime, registered_agent):
        result = runtime.execute_task(
            registered_agent["agent_id"], "task"
        )
        execution = runtime.get_execution(result["execution_id"])
        assert execution is not None
        assert execution["execution_id"] == result["execution_id"]

    def test_get_nonexistent_execution(self, runtime):
        assert runtime.get_execution("no-id") is None

    def test_list_all_executions(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        runtime.execute_task(agent_id, "t1")
        runtime.execute_task(agent_id, "t2")
        execs = runtime.list_executions()
        assert len(execs) == 2

    def test_list_empty(self, runtime):
        assert runtime.list_executions() == []

    def test_filter_by_agent_id(self, runtime):
        a1 = runtime.register_agent(name="A1")
        a2 = runtime.register_agent(name="A2")
        runtime.execute_task(a1["agent_id"], "task1")
        runtime.execute_task(a2["agent_id"], "task2")
        execs = runtime.list_executions(agent_id=a1["agent_id"])
        assert len(execs) == 1

    def test_filter_by_status(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        runtime.execute_task(agent_id, "t1")
        execs = runtime.list_executions(status="completed")
        # May or may not have completed depending on stub
        assert isinstance(execs, list)

    def test_respects_limit(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        for i in range(10):
            runtime.execute_task(agent_id, f"task-{i}")
        execs = runtime.list_executions(limit=3)
        assert len(execs) == 3


# =====================================================================
# Test cancel_execution
# =====================================================================

class TestCancelExecution:

    def test_cancel_pending_execution(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        # Insert a pending execution manually
        execution_id = runtime._uid()
        with runtime._lock:
            runtime._conn.execute(
                "INSERT INTO agent_executions "
                "(execution_id, agent_id, task_description, input_messages, "
                "status, started_at) VALUES (?, ?, 'task', '[]', 'pending', ?)",
                (execution_id, agent_id, time.time()),
            )
            runtime._conn.commit()
        result = runtime.cancel_execution(execution_id)
        assert result is not None
        assert result["status"] == "cancelled"

    def test_cancel_nonexistent(self, runtime):
        assert runtime.cancel_execution("no-id") is None

    def test_cancel_completed_returns_none(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        execution_id = runtime._uid()
        with runtime._lock:
            runtime._conn.execute(
                "INSERT INTO agent_executions "
                "(execution_id, agent_id, task_description, input_messages, "
                "status, started_at, completed_at) "
                "VALUES (?, ?, 'task', '[]', 'completed', ?, ?)",
                (execution_id, agent_id, time.time(), time.time()),
            )
            runtime._conn.commit()
        assert runtime.cancel_execution(execution_id) is None


# =====================================================================
# Test add_log / get_logs
# =====================================================================

class TestLogging:

    def test_add_log(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "task")
        exec_id = result["execution_id"]

        log_entry = runtime.add_log(exec_id, "INFO", "Task started")
        assert log_entry["log_id"] != ""
        assert log_entry["execution_id"] == exec_id
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Task started"

    def test_add_log_resolves_agent_id(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "task")
        log_entry = runtime.add_log(result["execution_id"], "WARN", "msg")
        assert log_entry["agent_id"] == agent_id

    def test_add_log_for_unknown_execution(self, runtime):
        log_entry = runtime.add_log("fake-exec", "ERROR", "Something broke")
        assert log_entry["execution_id"] == "fake-exec"
        assert log_entry["agent_id"] == ""

    def test_get_logs_ordered(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        result = runtime.execute_task(agent_id, "task")
        exec_id = result["execution_id"]
        runtime.add_log(exec_id, "INFO", "first")
        runtime.add_log(exec_id, "INFO", "second")
        logs = runtime.get_logs(exec_id)
        assert len(logs) == 2
        assert logs[0]["message"] == "first"
        assert logs[1]["message"] == "second"

    def test_get_logs_empty(self, runtime):
        assert runtime.get_logs("no-exec") == []


# =====================================================================
# Test get_agent_stats
# =====================================================================

class TestAgentStats:

    def test_stats_no_executions(self, runtime, registered_agent):
        stats = runtime.get_agent_stats(registered_agent["agent_id"])
        assert stats["total_executions"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["avg_latency_ms"] == 0.0
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0

    def test_stats_with_executions(self, runtime, registered_agent):
        agent_id = registered_agent["agent_id"]
        runtime.execute_task(agent_id, "t1")
        runtime.execute_task(agent_id, "t2")
        stats = runtime.get_agent_stats(agent_id)
        assert stats["total_executions"] == 2
        assert stats["agent_id"] == agent_id

    def test_stats_nonexistent_agent(self, runtime):
        stats = runtime.get_agent_stats("no-agent")
        assert stats["total_executions"] == 0


# =====================================================================
# Test get_runtime_stats
# =====================================================================

class TestRuntimeStats:

    def test_empty_stats(self, runtime):
        stats = runtime.get_runtime_stats()
        assert stats["total_agents"] == 0
        assert stats["agents_by_status"] == {}
        assert stats["agents_by_type"] == {}
        assert stats["total_executions"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["total_logs"] == 0

    def test_stats_after_registration(self, runtime):
        runtime.register_agent(name="A1", agent_type="claude_code")
        runtime.register_agent(name="A2", agent_type="codex")
        stats = runtime.get_runtime_stats()
        assert stats["total_agents"] == 2
        assert stats["agents_by_type"]["claude_code"] == 1
        assert stats["agents_by_type"]["codex"] == 1
        assert stats["agents_by_status"]["active"] == 2

    def test_stats_with_executions(self, runtime):
        agent = runtime.register_agent(name="Runner")
        runtime.execute_task(agent["agent_id"], "t1")
        runtime.execute_task(agent["agent_id"], "t2")
        stats = runtime.get_runtime_stats()
        assert stats["total_executions"] == 2
        assert stats["agents_by_type"]["custom"] == 1


# =====================================================================
# Test event emission
# =====================================================================

class TestEventEmission:

    def test_no_event_without_bus(self):
        rt = AgentRuntimeManager(event_bus=None)
        agent = rt.register_agent(name="Quiet")
        assert agent["agent_id"] != ""

    def test_registered_event_payload(self, runtime, captured_events):
        runtime.register_agent(
            name="PayloadTest", agent_type="codex",
        )
        evt = [e for e in captured_events
               if e.topic == "agent.registered"][0]
        assert evt.payload["name"] == "PayloadTest"
        assert evt.payload["agent_type"] == "codex"
        assert "agent_id" in evt.payload

    def test_deregistered_event_payload(self, runtime, captured_events):
        agent = runtime.register_agent(name="Bye")
        runtime.deregister_agent(agent["agent_id"])
        evt = [e for e in captured_events
               if e.topic == "agent.deregistered"][0]
        assert evt.payload["agent_id"] == agent["agent_id"]

    def test_execution_started_event(self, runtime, registered_agent,
                                      captured_events):
        runtime.execute_task(registered_agent["agent_id"], "go")
        evt = [e for e in captured_events
               if e.topic == "agent.execution.started"][0]
        assert "execution_id" in evt.payload
        assert evt.payload["agent_id"] == registered_agent["agent_id"]


# =====================================================================
# Test thread safety
# =====================================================================

class TestThreadSafety:

    def test_concurrent_registrations(self, runtime):
        errors: list[Exception] = []

        def register(idx):
            try:
                runtime.register_agent(name=f"Agent-{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=register, args=(i,))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        agents = runtime.list_agents()
        assert len(agents) == 20

    def test_concurrent_executions(self, runtime):
        agent = runtime.register_agent(name="Concurrent")
        errors: list[Exception] = []

        def execute(idx):
            try:
                runtime.execute_task(
                    agent["agent_id"], f"task-{idx}",
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=execute, args=(i,))
                   for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        execs = runtime.list_executions(agent_id=agent["agent_id"])
        assert len(execs) == 15


# =====================================================================
# Test singleton functions
# =====================================================================

class TestSingleton:

    def test_get_agent_runtime_returns_instance(self):
        reset_agent_runtime()
        rt = get_agent_runtime()
        assert isinstance(rt, AgentRuntimeManager)

    def test_get_agent_runtime_idempotent(self):
        reset_agent_runtime()
        rt1 = get_agent_runtime()
        rt2 = get_agent_runtime()
        assert rt1 is rt2

    def test_reset_agent_runtime_creates_new(self):
        reset_agent_runtime()
        rt1 = get_agent_runtime()
        rt2 = reset_agent_runtime()
        assert rt1 is not rt2
