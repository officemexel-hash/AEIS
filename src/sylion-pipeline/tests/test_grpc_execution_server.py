"""Tests for grpc.execution_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_execution_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.execution_server import WorkflowServicer, JobServicer

    class MockContext:
        def __init__(self):
            self.code = None
            self.details = None
        def set_code(self, code):
            self.code = code
        def set_details(self, details):
            self.details = details

    class TestWorkflowServicer:
        @pytest.fixture
        def servicer(self):
            return WorkflowServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_create_workflow(self, servicer, ctx):
            req = sylion_execution_pb2.CreateWorkflowRequest(
                name="test-wf",
                description="Test workflow",
            )
            resp = servicer.CreateWorkflow(req, ctx)
            assert ctx.code is None
            assert resp.workflow.workflow_id != ""
            assert resp.workflow.name == "test-wf"

        def test_create_workflow_with_steps(self, servicer, ctx):
            req = sylion_execution_pb2.CreateWorkflowRequest(
                name="wf-steps",
                steps=[
                    sylion_execution_pb2.WorkflowStep(
                        step_id="s1", name="Step 1", handler="handler1",
                    ),
                ],
            )
            resp = servicer.CreateWorkflow(req, ctx)
            assert resp.workflow.workflow_id != ""

        def test_run_workflow(self, servicer, ctx):
            create_req = sylion_execution_pb2.CreateWorkflowRequest(name="run-wf")
            create_resp = servicer.CreateWorkflow(create_req, ctx)
            wf_id = create_resp.workflow.workflow_id

            run_req = sylion_execution_pb2.RunWorkflowRequest(workflow_id=wf_id)
            run_resp = servicer.RunWorkflow(run_req, ctx)
            assert ctx.code is None
            assert run_resp.run.run_id != ""

        def test_get_run(self, servicer, ctx):
            create_resp = servicer.CreateWorkflow(
                sylion_execution_pb2.CreateWorkflowRequest(name="get-run-wf"), ctx,
            )
            run_resp = servicer.RunWorkflow(
                sylion_execution_pb2.RunWorkflowRequest(
                    workflow_id=create_resp.workflow.workflow_id,
                ), ctx,
            )
            get_req = sylion_execution_pb2.GetRunRequest(run_id=run_resp.run.run_id)
            get_resp = servicer.GetRun(get_req, ctx)
            assert ctx.code is None
            assert get_resp.run.run_id == run_resp.run.run_id

        def test_get_run_not_found(self, servicer, ctx):
            req = sylion_execution_pb2.GetRunRequest(run_id="nonexistent")
            resp = servicer.GetRun(req, ctx)
            assert ctx.code is not None

        def test_list_workflows(self, servicer, ctx):
            for i in range(3):
                servicer.CreateWorkflow(
                    sylion_execution_pb2.CreateWorkflowRequest(name=f"list-wf-{i}"), ctx,
                )
            req = sylion_execution_pb2.ListWorkflowsRequest()
            resp = servicer.ListWorkflows(req, ctx)
            assert len(resp.workflows) >= 3

    class TestJobServicer:
        @pytest.fixture
        def servicer(self):
            return JobServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_submit_job(self, servicer, ctx):
            req = sylion_execution_pb2.SubmitJobRequest(
                job_type="test-job",
                payload=b"test payload",
            )
            resp = servicer.SubmitJob(req, ctx)
            assert ctx.code is None
            assert resp.job.job_id != ""
            assert resp.job.job_type == "test-job"

        def test_get_job(self, servicer, ctx):
            submit_resp = servicer.SubmitJob(
                sylion_execution_pb2.SubmitJobRequest(job_type="get-job"), ctx,
            )
            get_req = sylion_execution_pb2.GetJobRequest(job_id=submit_resp.job.job_id)
            get_resp = servicer.GetJob(get_req, ctx)
            assert ctx.code is None
            assert get_resp.job.job_id == submit_resp.job.job_id

        def test_get_job_not_found(self, servicer, ctx):
            req = sylion_execution_pb2.GetJobRequest(job_id="nonexistent")
            resp = servicer.GetJob(req, ctx)
            assert ctx.code is not None

        def test_get_next_job(self, servicer, ctx):
            servicer.SubmitJob(
                sylion_execution_pb2.SubmitJobRequest(job_type="next-job"), ctx,
            )
            req = sylion_execution_pb2.GetNextJobRequest(worker_id="w1")
            resp = servicer.GetNextJob(req, ctx)
            assert resp.job.job_id != ""

        def test_complete_job(self, servicer, ctx):
            submit_resp = servicer.SubmitJob(
                sylion_execution_pb2.SubmitJobRequest(job_type="complete-job"), ctx,
            )
            req = sylion_execution_pb2.CompleteJobRequest(
                job_id=submit_resp.job.job_id,
                result=b"done",
            )
            resp = servicer.CompleteJob(req, ctx)
            assert ctx.code is None

        def test_fail_job(self, servicer, ctx):
            submit_resp = servicer.SubmitJob(
                sylion_execution_pb2.SubmitJobRequest(job_type="fail-job"), ctx,
            )
            req = sylion_execution_pb2.FailJobRequest(
                job_id=submit_resp.job.job_id,
                error_message="something failed",
            )
            resp = servicer.FailJob(req, ctx)
            assert ctx.code is None

        def test_get_stats(self, servicer, ctx):
            servicer.SubmitJob(
                sylion_execution_pb2.SubmitJobRequest(job_type="stats-job"), ctx,
            )
            req = sylion_execution_pb2.GetStatsRequest()
            resp = servicer.GetStats(req, ctx)
            assert resp.stats.total_jobs >= 1
