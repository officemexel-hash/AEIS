"""
Comprehensive tests for sylion.execution.tool_runner.

Tests ToolRunner class: register_tool, execute, get_tool, get_execution,
list_tools, list_executions, edge cases, thread safety, event emission.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from unittest.mock import MagicMock

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.tool_runner import (
    Tool,
    ToolExecution,
    ToolRunner,
    get_tool_runner,
)


def python_command(payload: object = "", exit_code: int = 0) -> list[str]:
    rendered = payload if isinstance(payload, str) else json.dumps(payload)
    script = (
        "import sys;"
        f"sys.stdout.write({rendered!r});"
        f"sys.exit({int(exit_code)})"
    )
    return [sys.executable, "-c", script]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner() -> ToolRunner:
    """Fresh in-memory ToolRunner per test."""
    return ToolRunner()


@pytest.fixture
def runner_with_bus() -> tuple[ToolRunner, MagicMock]:
    """ToolRunner with a mock EventBus."""
    bus = MagicMock(spec=EventBus)
    tr = ToolRunner(event_bus=bus)
    return tr, bus


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestDataclasses:

    def test_tool_defaults(self):
        t = Tool()
        assert t.tool_id == ""
        assert t.name == ""
        assert t.description == ""
        assert t.tool_type == "python"
        assert t.config == {}
        assert t.active == 1

    def test_tool_with_values(self):
        t = Tool(tool_id="t1", name="Formatter", tool_type="shell",
                 config={"timeout": 30})
        assert t.tool_id == "t1"
        assert t.name == "Formatter"
        assert t.tool_type == "shell"
        assert t.config["timeout"] == 30

    def test_tool_execution_defaults(self):
        te = ToolExecution()
        assert te.exec_id == ""
        assert te.tool_id == ""
        assert te.status == "pending"
        assert te.result == ""
        assert te.error == ""


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------

class TestRegisterTool:

    def test_basic_register(self, runner):
        result = runner.register_tool("tool-1", "Formatter")
        assert result["tool_id"] == "tool-1"
        assert result["name"] == "Formatter"

    def test_with_description(self, runner):
        runner.register_tool("t1", "MyTool", description="Does things")
        tool = runner.get_tool("t1")
        assert tool["description"] == "Does things"

    def test_with_tool_type(self, runner):
        runner.register_tool("t1", "Shell", tool_type="shell")
        tool = runner.get_tool("t1")
        assert tool["tool_type"] == "shell"

    def test_default_tool_type_is_python(self, runner):
        runner.register_tool("t1", "Default")
        tool = runner.get_tool("t1")
        assert tool["tool_type"] == "python"

    def test_with_config(self, runner):
        runner.register_tool("t1", "ConfigTool", config={"timeout": 30, "retries": 3})
        tool = runner.get_tool("t1")
        assert tool["config"]["timeout"] == 30
        assert tool["config"]["retries"] == 3

    def test_default_config_empty(self, runner):
        runner.register_tool("t1", "NoConfig")
        tool = runner.get_tool("t1")
        assert tool["config"] == {}

    def test_upsert_replaces_existing(self, runner):
        runner.register_tool("t1", "V1")
        runner.register_tool("t1", "V2", description="updated")
        tool = runner.get_tool("t1")
        assert tool["name"] == "V2"
        assert tool["description"] == "updated"

    def test_active_by_default(self, runner):
        runner.register_tool("t1", "Active")
        tool = runner.get_tool("t1")
        assert tool["active"] == 1

    def test_emits_registered_event(self, runner_with_bus):
        tr, bus = runner_with_bus
        tr.register_tool("t1", "EventTool", tool_type="shell")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert isinstance(event, SylionEvent)
        assert event.topic == "execution.tool.registered"
        assert event.payload["tool_id"] == "t1"
        assert event.payload["tool_type"] == "shell"


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------

class TestExecute:

    def test_execute_registered_tool(self, runner):
        runner.register_tool("t1", "Echo")
        result = runner.execute("t1", {"input": "test"})
        assert result["result"] == "executed"
        assert result["tool_id"] == "t1"
        assert "exec_id" in result

    def test_execute_without_input(self, runner):
        runner.register_tool("t1", "NoInput")
        result = runner.execute("t1")
        assert result["result"] == "executed"

    def test_execute_nonexistent_tool(self, runner):
        result = runner.execute("ghost-tool")
        assert result["result"] == "error"
        assert "not found" in result["error"]

    def test_execute_returns_exec_id(self, runner):
        runner.register_tool("t1", "Exec")
        r1 = runner.execute("t1")
        r2 = runner.execute("t1")
        assert r1["exec_id"] != r2["exec_id"]

    def test_records_execution(self, runner):
        runner.register_tool("t1", "Rec")
        result = runner.execute("t1")
        record = runner.get_execution(result["exec_id"])
        assert record is not None
        assert record["status"] == "completed"
        assert record["tool_id"] == "t1"

    def test_execution_has_timestamps(self, runner):
        runner.register_tool("t1", "Time")
        result = runner.execute("t1")
        record = runner.get_execution(result["exec_id"])
        assert record["started_at"] > 0
        assert record["completed_at"] > 0
        assert record["completed_at"] >= record["started_at"]

    def test_emits_executed_event(self, runner_with_bus):
        tr, bus = runner_with_bus
        tr.register_tool("t1", "EventExec")
        bus.publish.reset_mock()
        tr.execute("t1")
        bus.publish.assert_called_once()
        event = bus.publish.call_args[0][0]
        assert event.topic == "execution.tool.executed"
        assert event.payload["status"] == "completed"

    def test_shell_tool_executes_argv_list(self, runner):
        runner.register_tool(
            "shell-ok",
            "ShellOK",
            tool_type="shell",
            config={"command": python_command("shell-ok")},
        )
        result = runner.execute("shell-ok", {"input": "ignored"})
        assert result["result"] == "executed"
        record = runner.get_execution(result["exec_id"])
        payload = json.loads(record["result"])
        assert payload["handler"] == "shell"
        assert payload["stdout"] == "shell-ok"

    def test_shell_tool_rejects_string_command(self, runner):
        runner.register_tool(
            "shell-bad",
            "ShellBad",
            tool_type="shell",
            config={"command": "echo unsafe"},
        )
        result = runner.execute("shell-bad")
        assert result["result"] == "error"
        assert "argv list" in result["error"]


# ---------------------------------------------------------------------------
# get_tool
# ---------------------------------------------------------------------------

class TestGetTool:

    def test_existing_tool(self, runner):
        runner.register_tool("t1", "Fetch")
        tool = runner.get_tool("t1")
        assert tool is not None
        assert tool["name"] == "Fetch"

    def test_nonexistent_returns_none(self, runner):
        assert runner.get_tool("ghost") is None

    def test_config_deserialized(self, runner):
        runner.register_tool("t1", "Conf", config={"k": "v"})
        tool = runner.get_tool("t1")
        assert isinstance(tool["config"], dict)
        assert tool["config"]["k"] == "v"

    def test_returns_all_fields(self, runner):
        runner.register_tool("t1", "Full", description="desc", tool_type="shell")
        tool = runner.get_tool("t1")
        assert "tool_id" in tool
        assert "name" in tool
        assert "description" in tool
        assert "tool_type" in tool
        assert "config" in tool
        assert "active" in tool


# ---------------------------------------------------------------------------
# get_execution
# ---------------------------------------------------------------------------

class TestGetExecution:

    def test_existing_execution(self, runner):
        runner.register_tool("t1", "Exec")
        result = runner.execute("t1")
        record = runner.get_execution(result["exec_id"])
        assert record is not None
        assert record["status"] == "completed"

    def test_nonexistent_returns_none(self, runner):
        assert runner.get_execution("ghost-exec") is None

    def test_execution_fields(self, runner):
        runner.register_tool("t1", "Fields")
        result = runner.execute("t1", {"data": "test"})
        record = runner.get_execution(result["exec_id"])
        assert "exec_id" in record
        assert "tool_id" in record
        assert "input_hash" in record
        assert "result" in record
        assert "status" in record
        assert "started_at" in record
        assert "completed_at" in record
        assert "error" in record


# ---------------------------------------------------------------------------
# list_tools
# ---------------------------------------------------------------------------

class TestListTools:

    def test_empty(self, runner):
        assert runner.list_tools() == []

    def test_lists_all_active(self, runner):
        runner.register_tool("t1", "Alpha")
        runner.register_tool("t2", "Beta")
        tools = runner.list_tools()
        assert len(tools) == 2

    def test_active_only_by_default(self, runner):
        runner.register_tool("t1", "Active")
        tools = runner.list_tools(active_only=True)
        assert len(tools) == 1

    def test_includes_inactive(self, runner):
        runner.register_tool("t1", "Tool1")
        runner.register_tool("t2", "Tool2")
        # Mark one inactive via direct SQL
        runner._conn.execute("UPDATE tools SET active = 0 WHERE tool_id = 't1'")
        runner._conn.commit()
        active = runner.list_tools(active_only=True)
        all_tools = runner.list_tools(active_only=False)
        assert len(active) == 1
        assert len(all_tools) == 2

    def test_ordered_by_name(self, runner):
        runner.register_tool("t1", "Zebra")
        runner.register_tool("t2", "Alpha")
        runner.register_tool("t3", "Middle")
        tools = runner.list_tools()
        assert tools[0]["name"] == "Alpha"
        assert tools[1]["name"] == "Middle"
        assert tools[2]["name"] == "Zebra"

    def test_config_deserialized(self, runner):
        runner.register_tool("t1", "Conf", config={"x": 1})
        tools = runner.list_tools()
        assert isinstance(tools[0]["config"], dict)
        assert tools[0]["config"]["x"] == 1


# ---------------------------------------------------------------------------
# list_executions
# ---------------------------------------------------------------------------

class TestListExecutions:

    def test_empty(self, runner):
        assert runner.list_executions() == []

    def test_all_executions(self, runner):
        runner.register_tool("t1", "Tool")
        runner.execute("t1")
        runner.execute("t1")
        execs = runner.list_executions()
        assert len(execs) == 2

    def test_filter_by_tool_id(self, runner):
        runner.register_tool("t1", "A")
        runner.register_tool("t2", "B")
        runner.execute("t1")
        runner.execute("t1")
        runner.execute("t2")
        t1_execs = runner.list_executions(tool_id="t1")
        assert len(t1_execs) == 2
        t2_execs = runner.list_executions(tool_id="t2")
        assert len(t2_execs) == 1

    def test_limit(self, runner):
        runner.register_tool("t1", "Limited")
        for _ in range(10):
            runner.execute("t1")
        execs = runner.list_executions(limit=5)
        assert len(execs) == 5

    def test_ordered_by_started_at_desc(self, runner):
        runner.register_tool("t1", "Order")
        runner.execute("t1")
        time.sleep(0.01)
        runner.execute("t1")
        execs = runner.list_executions()
        assert execs[0]["started_at"] >= execs[1]["started_at"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_register_same_tool_twice_upserts(self, runner):
        runner.register_tool("dup", "V1")
        runner.register_tool("dup", "V2", description="updated")
        tools = runner.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "V2"

    def test_execute_after_upsert_still_works(self, runner):
        runner.register_tool("t1", "V1")
        runner.register_tool("t1", "V2")
        result = runner.execute("t1")
        assert result["result"] == "executed"

    def test_config_with_complex_types(self, runner):
        runner.register_tool("t1", "Complex", config={
            "nested": {"a": 1},
            "list": [1, 2, 3],
            "null": None,
        })
        tool = runner.get_tool("t1")
        assert tool["config"]["nested"]["a"] == 1
        assert tool["config"]["list"] == [1, 2, 3]

    def test_empty_input_data(self, runner):
        runner.register_tool("t1", "Empty")
        result = runner.execute("t1", {})
        assert result["result"] == "executed"

    def test_large_number_of_executions(self, runner):
        runner.register_tool("t1", "Load")
        for _ in range(50):
            runner.execute("t1")
        execs = runner.list_executions(limit=100)
        assert len(execs) == 50


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestToolRunnerThreadSafety:

    def test_concurrent_register(self):
        tr = ToolRunner()
        errors = []

        def register(tool_id, name):
            try:
                tr.register_tool(tool_id, name)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register, args=(f"t-{i}", f"Tool-{i}"))
                   for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        tools = tr.list_tools()
        assert len(tools) == 20

    def test_concurrent_execute(self):
        """Execute tools concurrently. Each thread uses its own tool
        to avoid SQLite contention on the same connection."""
        tr = ToolRunner()
        n = 30
        for i in range(n):
            tr.register_tool(f"tool-{i}", f"Tool-{i}")

        results = []
        errors = []

        def execute_tool(i):
            try:
                r = tr.execute(f"tool-{i}")
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=execute_tool, args=(i,))
                   for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == n
        exec_ids = [r["exec_id"] for r in results]
        assert len(set(exec_ids)) == n

    def test_concurrent_register_and_execute(self):
        """Register tools sequentially, then execute concurrently on
        separate targets to avoid SQLite contention."""
        tr = ToolRunner()
        n = 15
        errors = []

        # Register all tools first (sequential)
        for i in range(n):
            tr.register_tool(f"t-{i}", f"Tool-{i}")

        def exec_tool(i):
            try:
                tr.execute(f"t-{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=exec_tool, args=(i,))
                   for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        execs = tr.list_executions()
        assert len(execs) == n


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestGetToolRunnerSingleton:

    def test_returns_instance(self):
        import sylion.execution.tool_runner as mod
        mod._runner = None
        tr = get_tool_runner()
        assert isinstance(tr, ToolRunner)
        mod._runner = None

    def test_singleton_reuse(self):
        import sylion.execution.tool_runner as mod
        mod._runner = None
        tr1 = get_tool_runner()
        tr2 = get_tool_runner()
        assert tr1 is tr2
        mod._runner = None

    def test_singleton_with_args(self):
        import sylion.execution.tool_runner as mod
        mod._runner = None
        bus = MagicMock(spec=EventBus)
        tr = get_tool_runner(event_bus=bus)
        assert tr._event_bus is bus
        mod._runner = None
