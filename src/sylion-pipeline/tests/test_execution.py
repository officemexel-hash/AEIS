"""
SYLION Execution Package -- Unit Tests

Tests for 6 modules: tool_runner, connector_framework, workflow_engine,
job_runner, adapter_bus, retry_orchestrator.
"""

from __future__ import annotations

import json
import time

import pytest

from sylion.core.event_bus import EventBus, SylionEvent
from sylion.execution.tool_runner import ToolRunner
from sylion.execution.connector_framework import ConnectorFramework
from sylion.execution.workflow_engine import WorkflowEngine
from sylion.execution.job_runner import JobRunner
from sylion.execution.adapter_bus import AdapterBus
from sylion.execution.retry_orchestrator import RetryOrchestrator


# =====================================================================
# ToolRunner tests
# =====================================================================

class TestToolRunner:

    def test_register_tool(self):
        tr = ToolRunner()
        result = tr.register_tool("tool-1", "Formatter", description="Code formatter")
        assert result["tool_id"] == "tool-1"
        assert result["name"] == "Formatter"

    def test_execute_tool(self):
        tr = ToolRunner()
        tr.register_tool("tool-1", "Echo")
        result = tr.execute("tool-1", {"input": "test"})
        assert result["result"] == "executed"
        assert "exec_id" in result
        assert result["tool_id"] == "tool-1"

    def test_execute_nonexistent_tool(self):
        tr = ToolRunner()
        result = tr.execute("ghost-tool")
        assert result["result"] == "error"
        assert "not found" in result["error"]

    def test_get_tool(self):
        tr = ToolRunner()
        tr.register_tool("tool-g", "Getter", config={"timeout": 30})
        tool = tr.get_tool("tool-g")
        assert tool is not None
        assert tool["config"]["timeout"] == 30

    def test_get_execution(self):
        tr = ToolRunner()
        tr.register_tool("tool-e", "Exec Test")
        exec_result = tr.execute("tool-e", {"key": "val"})
        record = tr.get_execution(exec_result["exec_id"])
        assert record is not None
        assert record["status"] == "completed"

    def test_list_tools(self):
        tr = ToolRunner()
        tr.register_tool("t1", "Alpha")
        tr.register_tool("t2", "Beta")
        active = tr.list_tools(active_only=True)
        assert len(active) == 2

    def test_list_executions(self):
        tr = ToolRunner()
        tr.register_tool("t1", "Runner")
        tr.execute("t1")
        tr.execute("t1")
        execs = tr.list_executions(tool_id="t1")
        assert len(execs) == 2


# =====================================================================
# ConnectorFramework tests
# =====================================================================

class TestConnectorFramework:

    def test_register_connector(self):
        cf = ConnectorFramework()
        result = cf.register("conn-1", "GitHub API", connector_type="api",
                             endpoint="https://api.github.com",
                             auth_type="token")
        assert result["connector_id"] == "conn-1"
        assert result["status"] == "active"

    def test_get_connector(self):
        cf = ConnectorFramework()
        cf.register("conn-2", "Postgres DB", connector_type="database",
                     config={"port": 5432})
        conn = cf.get("conn-2")
        assert conn is not None
        assert conn["connector_type"] == "database"
        assert conn["config"]["port"] == 5432

    def test_list_connectors_by_type(self):
        cf = ConnectorFramework()
        cf.register("c1", "API One", connector_type="api")
        cf.register("c2", "DB One", connector_type="database")
        cf.register("c3", "API Two", connector_type="api")

        apis = cf.list_connectors(connector_type="api")
        assert len(apis) == 2
        dbs = cf.list_connectors(connector_type="database")
        assert len(dbs) == 1

    def test_update_status(self):
        cf = ConnectorFramework()
        cf.register("conn-s", "Status Test")
        assert cf.update_status("conn-s", "error") is True
        conn = cf.get("conn-s")
        assert conn["status"] == "error"

    def test_deregister(self):
        cf = ConnectorFramework()
        cf.register("conn-d", "Delete Me")
        assert cf.deregister("conn-d") is True
        assert cf.get("conn-d") is None
        assert cf.deregister("conn-d") is False

    def test_get_nonexistent_connector(self):
        cf = ConnectorFramework()
        assert cf.get("ghost") is None


# =====================================================================
# WorkflowEngine tests
# =====================================================================

class TestWorkflowEngine:

    def test_create_workflow(self):
        we = WorkflowEngine()
        result = we.create_workflow("Deploy Pipeline", "Deploy to production",
                                    steps=[
                                        {"name": "build", "tool": "docker"},
                                        {"name": "test", "tool": "pytest"},
                                        {"name": "deploy", "tool": "k8s"},
                                    ])
        assert "workflow_id" in result
        assert result["name"] == "Deploy Pipeline"
        assert result["status"] == "draft"

    def test_get_workflow(self):
        we = WorkflowEngine()
        wf = we.create_workflow("Fetchable", steps=[{"name": "step1"}])
        fetched = we.get_workflow(wf["workflow_id"])
        assert fetched is not None
        assert len(fetched["steps"]) == 1

    def test_run_workflow(self):
        we = WorkflowEngine()
        wf = we.create_workflow("Runnable", steps=[
            {"name": "step_a", "tool": "tool_a"},
            {"name": "step_b", "tool": "tool_b"},
        ])
        run = we.run_workflow(wf["workflow_id"])
        assert run["status"] == "completed"
        assert run["steps_executed"] == 2
        assert "run_id" in run

    def test_run_workflow_records_run(self):
        we = WorkflowEngine()
        wf = we.create_workflow("Trackable", steps=[{"name": "s1"}])
        run = we.run_workflow(wf["workflow_id"])
        record = we.get_run(run["run_id"])
        assert record is not None
        assert record["status"] == "completed"
        assert len(record["step_results"]) == 1

    def test_run_nonexistent_workflow(self):
        we = WorkflowEngine()
        result = we.run_workflow("ghost-wf")
        assert "error" in result

    def test_list_workflows(self):
        we = WorkflowEngine()
        we.create_workflow("WF A")
        we.create_workflow("WF B")
        all_wfs = we.list_workflows()
        assert len(all_wfs) == 2

    def test_list_runs(self):
        we = WorkflowEngine()
        wf = we.create_workflow("MultiRun", steps=[{"name": "s"}])
        we.run_workflow(wf["workflow_id"])
        we.run_workflow(wf["workflow_id"])
        runs = we.list_runs(workflow_id=wf["workflow_id"])
        assert len(runs) == 2


# =====================================================================
# JobRunner tests
# =====================================================================

class TestJobRunner:

    def test_submit_job(self):
        jr = JobRunner()
        result = jr.submit("email", payload={"to": "user@test.com"}, priority=5)
        assert "job_id" in result
        assert result["status"] == "queued"

    def test_get_next_highest_priority(self):
        jr = JobRunner()
        jr.submit("low_prio", priority=1)
        jr.submit("high_prio", priority=10)
        jr.submit("mid_prio", priority=5)

        next_job = jr.get_next()
        assert next_job is not None
        assert next_job["job_type"] == "high_prio"
        assert next_job["status"] == "running"

    def test_complete_job(self):
        jr = JobRunner()
        job = jr.submit("report")
        next_job = jr.get_next()
        assert jr.complete(next_job["job_id"], result="Report generated") is True

        fetched = jr.get_job(next_job["job_id"])
        assert fetched["status"] == "completed"
        assert fetched["result"] == "Report generated"

    def test_fail_job(self):
        jr = JobRunner()
        job = jr.submit("failing_task")
        next_job = jr.get_next()
        assert jr.fail(next_job["job_id"], error="Connection timeout") is True

        fetched = jr.get_job(next_job["job_id"])
        assert fetched["status"] == "failed"
        assert fetched["error"] == "Connection timeout"

    def test_get_stats_returns_dict(self):
        """Quirk: get_stats() returns {'total_jobs': N, 'by_status': {...}}."""
        jr = JobRunner()
        jr.submit("type_a", priority=1)
        jr.submit("type_b", priority=2)
        j = jr.get_next()
        jr.complete(j["job_id"])

        stats = jr.get_stats()
        assert isinstance(stats, dict)
        assert "total_jobs" in stats
        assert "by_status" in stats
        assert stats["total_jobs"] == 2
        assert "completed" in stats["by_status"]
        assert stats["by_status"]["completed"] == 1

    def test_get_next_empty_queue(self):
        jr = JobRunner()
        assert jr.get_next() is None

    def test_list_jobs(self):
        jr = JobRunner()
        jr.submit("type_a")
        jr.submit("type_b")
        jr.submit("type_c")
        all_jobs = jr.list_jobs()
        assert len(all_jobs) == 3


# =====================================================================
# AdapterBus tests
# =====================================================================

class TestAdapterBus:

    def test_register_route(self):
        ab = AdapterBus()
        result = ab.register_route(
            "connector", "github",
            "tool", "formatter",
            transform={"format": "json"},
        )
        assert "route_id" in result
        assert result["active"] is True

    def test_route_lookup(self):
        ab = AdapterBus()
        ab.register_route("connector", "jira", "tool", "notifier")
        ab.register_route("connector", "jira", "tool", "archiver")
        ab.register_route("connector", "slack", "tool", "messenger")

        jira_routes = ab.route("connector", "jira")
        assert len(jira_routes) == 2
        slack_routes = ab.route("connector", "slack")
        assert len(slack_routes) == 1

    def test_route_with_transform(self):
        ab = AdapterBus()
        ab.register_route("src", "s1", "tgt", "t1",
                          transform={"key_mapping": {"a": "b"}})
        routes = ab.route("src", "s1")
        assert len(routes) == 1
        assert routes[0]["transform"]["key_mapping"] == {"a": "b"}

    def test_remove_route(self):
        ab = AdapterBus()
        result = ab.register_route("src", "s1", "tgt", "t1")
        assert ab.remove_route(result["route_id"]) is True
        assert ab.remove_route(result["route_id"]) is False
        assert len(ab.route("src", "s1")) == 0

    def test_list_routes(self):
        ab = AdapterBus()
        ab.register_route("type_a", "s1", "type_b", "t1")
        ab.register_route("type_a", "s2", "type_b", "t2")
        ab.register_route("type_c", "s3", "type_d", "t3")

        all_routes = ab.list_routes()
        assert len(all_routes) == 3

        filtered = ab.list_routes(source_type="type_a")
        assert len(filtered) == 2

    def test_route_no_match(self):
        ab = AdapterBus()
        results = ab.route("nonexistent", "nope")
        assert results == []


# =====================================================================
# RetryOrchestrator tests
# =====================================================================

class TestRetryOrchestrator:

    def test_create_policy(self):
        ro = RetryOrchestrator()
        result = ro.create_policy("test-policy", max_retries=5)
        assert "policy_id" in result
        assert result["name"] == "test-policy"
        assert result["max_retries"] == 5

    def test_register_attempt(self):
        ro = RetryOrchestrator()
        ro.create_policy("svc-auth", max_retries=3)
        attempt = ro.register_attempt("service", "auth", error_type="timeout", error_message="connection lost")
        assert "attempt_id" in attempt
        assert attempt["attempt_number"] == 1

    def test_get_next_delay(self):
        ro = RetryOrchestrator()
        policy = ro.create_policy("delay-test", max_retries=3, base_delay_ms=100, backoff_factor=2.0)
        delay = ro.get_next_delay(policy["policy_id"], 1)
        assert delay > 0

    def test_record_success(self):
        ro = RetryOrchestrator()
        ro.create_policy("success-test", max_retries=3)
        ro.register_attempt("service", "test", error_type="err", error_message="fail")
        result = ro.record_success("service", "test")
        assert result is True

    def test_dlq_after_max_retries(self):
        ro = RetryOrchestrator()
        ro.create_policy("dlq-test", max_retries=2)
        ro.register_attempt("service", "dlq", error_type="err", error_message="fail1")
        ro.register_attempt("service", "dlq", error_type="err", error_message="fail2")
        dlq = ro.get_dlq_entries()
        assert len(dlq) >= 1

    def test_get_attempts(self):
        ro = RetryOrchestrator()
        ro.create_policy("log-test", max_retries=5)
        ro.register_attempt("svc", "logs", error_type="err1", error_message="e1")
        ro.register_attempt("svc", "logs", error_type="err2", error_message="e2")
        attempts = ro.get_attempts(operation_type="svc")
        assert len(attempts) >= 2

    def test_get_stats(self):
        ro = RetryOrchestrator()
        ro.create_policy("stats-test", max_retries=3)
        ro.register_attempt("svc", "stats", error_type="err", error_message="fail")
        stats = ro.get_stats()
        assert isinstance(stats, dict)
        assert stats["total_attempts"] >= 1
