"""Tests for grpc.core_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_core_pb2, sylion_common_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.core_server import (
        ModuleRegistryServicer,
        EvidenceSpineServicer,
    )

    class MockContext:
        """Mock gRPC context for testing."""
        def __init__(self):
            self.code = None
            self.details = None

        def set_code(self, code):
            self.code = code

        def set_details(self, details):
            self.details = details


    class TestModuleRegistryServicer:
        @pytest.fixture
        def servicer(self):
            return ModuleRegistryServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_register_module(self, servicer, ctx):
            req = sylion_core_pb2.RegisterModuleRequest(
                module_id=sylion_common_pb2.ModuleId(
                    module_id="test-mod-1",
                    module_kind="A",
                ),
                description="Test module",
            )
            resp = servicer.RegisterModule(req, ctx)
            assert ctx.code is None  # no error
            assert resp.HasField("module")

        def test_get_module(self, servicer, ctx):
            # Register first
            reg_req = sylion_core_pb2.RegisterModuleRequest(
                module_id=sylion_common_pb2.ModuleId(
                    module_id="get-mod-1",
                    module_kind="A",
                ),
                description="Get test",
            )
            servicer.RegisterModule(reg_req, ctx)

            get_req = sylion_core_pb2.GetModuleRequest(module_id="get-mod-1")
            resp = servicer.GetModule(get_req, ctx)
            assert ctx.code is None
            assert resp.module.module_id.module_id == "get-mod-1"

        def test_get_module_not_found(self, servicer, ctx):
            req = sylion_core_pb2.GetModuleRequest(module_id="nonexistent")
            resp = servicer.GetModule(req, ctx)
            assert ctx.code is not None

        def test_list_modules(self, servicer, ctx):
            for i in range(3):
                servicer.RegisterModule(sylion_core_pb2.RegisterModuleRequest(
                    module_id=sylion_common_pb2.ModuleId(
                        module_id=f"list-mod-{i}",
                        module_kind="A",
                    ),
                    description=f"Module {i}",
                ), ctx)

            req = sylion_core_pb2.ListModulesRequest()
            resp = servicer.ListModules(req, ctx)
            assert len(resp.modules) >= 3


    class TestEvidenceSpineServicer:
        @pytest.fixture
        def servicer(self):
            return EvidenceSpineServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_append_entry(self, servicer, ctx):
            req = sylion_core_pb2.AppendEntryRequest(
                topic="test.topic",
                payload=b"test payload",
                source_module="test.module",
            )
            resp = servicer.AppendEntry(req, ctx)
            assert resp.entry.evidence_id != ""
            assert ctx.code is None

        def test_verify_chain(self, servicer, ctx):
            req = sylion_core_pb2.VerifyChainRequest(topic="test")
            resp = servicer.VerifyChain(req, ctx)
            assert resp.valid is True

        def test_get_entry(self, servicer, ctx):
            # Append first
            append_req = sylion_core_pb2.AppendEntryRequest(
                topic="get.topic",
                payload=b"payload",
                source_module="get.module",
            )
            append_resp = servicer.AppendEntry(append_req, ctx)
            entry_id = append_resp.entry.evidence_id

            get_req = sylion_core_pb2.GetEntryRequest(evidence_id=entry_id)
            resp = servicer.GetEntry(get_req, ctx)
            assert resp.entry.evidence_id == entry_id

        def test_get_entry_not_found(self, servicer, ctx):
            req = sylion_core_pb2.GetEntryRequest(evidence_id="nonexistent")
            resp = servicer.GetEntry(req, ctx)
            assert ctx.code is not None

        def test_replay(self, servicer, ctx):
            for i in range(3):
                servicer.AppendEntry(sylion_core_pb2.AppendEntryRequest(
                    topic="replay.topic",
                    payload=f"payload-{i}".encode(),
                    source_module="replay.module",
                ), ctx)

            req = sylion_core_pb2.ReplayRequest(topic="replay.topic")
            entries = list(servicer.Replay(req, ctx))
            assert len(entries) >= 3
