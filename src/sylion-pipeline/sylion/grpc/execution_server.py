"""
SYLION gRPC -- Execution Service Servers

Implements gRPC service servers for execution modules:
- WorkflowService
- JobService

Wraps existing SQLite-backed services to serve proto-defined RPCs.
"""

from __future__ import annotations

import logging

import grpc

from sylion.execution.workflow_engine import get_workflow_engine
from sylion.execution.job_runner import get_job_runner

log = logging.getLogger("sylion.grpc.execution_server")

try:
    from sylion.grpc_stubs import sylion_execution_pb2
    from sylion.grpc_stubs import sylion_execution_pb2_grpc
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, execution servers disabled")


if _HAS_STUBS:

    class WorkflowServicer(sylion_execution_pb2_grpc.WorkflowServiceServicer):
        """gRPC server for Workflow Engine."""

        def __init__(self):
            self._engine = get_workflow_engine()

        def CreateWorkflow(self, request, context):
            steps = []
            for s in request.steps:
                steps.append({
                    "step_id": s.step_id,
                    "name": s.name,
                    "handler": s.handler,
                    "depends_on": list(s.depends_on),
                    "config": dict(s.config),
                    "timeout_ms": s.timeout_ms,
                    "max_retries": s.max_retries,
                })
            result = self._engine.create_workflow(
                name=request.name,
                description=request.description,
                steps=steps or None,
            )
            return sylion_execution_pb2.CreateWorkflowResponse(
                workflow=sylion_execution_pb2.Workflow(
                    workflow_id=result.get("workflow_id", ""),
                    name=result.get("name", ""),
                    description=result.get("description", ""),
                )
            )

        def RunWorkflow(self, request, context):
            try:
                result = self._engine.run_workflow(request.workflow_id)
            except Exception as exc:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(str(exc))
                return sylion_execution_pb2.RunWorkflowResponse()
            return sylion_execution_pb2.RunWorkflowResponse(
                run=sylion_execution_pb2.WorkflowRun(
                    run_id=result.get("run_id", ""),
                    workflow_id=result.get("workflow_id", ""),
                )
            )

        def GetRun(self, request, context):
            result = self._engine.get_run(request.run_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Run {request.run_id} not found")
                return sylion_execution_pb2.GetRunResponse()
            return sylion_execution_pb2.GetRunResponse(
                run=sylion_execution_pb2.WorkflowRun(
                    run_id=result.get("run_id", ""),
                    workflow_id=result.get("workflow_id", ""),
                    error_message=result.get("error", ""),
                )
            )

        def ListWorkflows(self, request, context):
            results = self._engine.list_workflows()
            wfs = []
            for r in results:
                wfs.append(sylion_execution_pb2.Workflow(
                    workflow_id=r.get("workflow_id", ""),
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                ))
            return sylion_execution_pb2.ListWorkflowsResponse(workflows=wfs)

    class JobServicer(sylion_execution_pb2_grpc.JobServiceServicer):
        """gRPC server for Job Runner."""

        def __init__(self):
            self._runner = get_job_runner()

        def SubmitJob(self, request, context):
            result = self._runner.submit(
                job_type=request.job_type,
                payload={"raw": request.payload.decode("utf-8", errors="replace")} if request.payload else None,
                priority=request.priority,
            )
            return sylion_execution_pb2.SubmitJobResponse(
                job=sylion_execution_pb2.Job(
                    job_id=result.get("job_id", ""),
                    job_type=request.job_type,
                    payload=request.payload,
                )
            )

        def GetJob(self, request, context):
            result = self._runner.get_job(request.job_id)
            if not result:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Job {request.job_id} not found")
                return sylion_execution_pb2.GetJobResponse()
            return sylion_execution_pb2.GetJobResponse(
                job=sylion_execution_pb2.Job(
                    job_id=result.get("job_id", ""),
                    job_type=result.get("job_type", ""),
                    error_message=result.get("error", ""),
                )
            )

        def GetNextJob(self, request, context):
            result = self._runner.get_next()
            if not result:
                return sylion_execution_pb2.GetNextJobResponse()
            return sylion_execution_pb2.GetNextJobResponse(
                job=sylion_execution_pb2.Job(
                    job_id=result.get("job_id", ""),
                    job_type=result.get("job_type", ""),
                )
            )

        def CompleteJob(self, request, context):
            ok = self._runner.complete(
                request.job_id,
                result=request.result.decode("utf-8", errors="replace") if request.result else "",
            )
            if not ok:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Job {request.job_id} not found")
            return sylion_execution_pb2.CompleteJobResponse()

        def FailJob(self, request, context):
            ok = self._runner.fail(
                request.job_id,
                error=request.error_message,
            )
            if not ok:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details(f"Job {request.job_id} not found")
            return sylion_execution_pb2.FailJobResponse()

        def GetStats(self, request, context):
            stats = self._runner.get_stats()
            return sylion_execution_pb2.GetStatsResponse(
                stats=sylion_execution_pb2.JobStats(
                    total_jobs=stats.get("total_jobs", 0),
                    completed_jobs=stats.get("by_status", {}).get("completed", 0),
                    failed_jobs=stats.get("by_status", {}).get("failed", 0),
                )
            )
