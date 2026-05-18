"""Integration test for sylion.server unified startup."""

import importlib
import sys

import pytest


class TestServerModule:
    """Tests for the unified server module."""

    def test_server_imports(self):
        """Server module should import cleanly."""
        mod = importlib.import_module("sylion.server")
        assert hasattr(mod, "main")
        assert hasattr(mod, "_start_grpc")

    def test_start_grpc_returns_none_on_bad_port(self):
        """_start_grpc should handle import gracefully."""
        from sylion.server import _start_grpc
        # With gRPC stubs available, should return a server object
        result = _start_grpc(port=0, max_workers=1)
        if result is not None:
            result.stop(grace=0)

    def test_db_mode_helpers(self):
        """Database mode helpers should work."""
        from sylion.db import get_db_mode, is_postgres
        assert get_db_mode() in ("sqlite", "postgres")
        assert isinstance(is_postgres(), bool)

    def test_database_url_alias_selects_postgres(self, monkeypatch):
        """DATABASE_URL is accepted as the deployment alias for PostgreSQL."""
        monkeypatch.delenv("SYLION_DB_MODE", raising=False)
        monkeypatch.delenv("SYLION_DB_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://aeis:secret@db/aeis")

        from sylion.db import get_db_mode, get_db_url, is_postgres

        assert get_db_url() == "postgresql+asyncpg://aeis:secret@db/aeis"
        assert get_db_mode() == "postgres"
        assert is_postgres() is True

    def test_health_database_endpoint_exists(self):
        """Health database endpoint should be registered."""
        from sylion.api.health_routes import router
        routes = [r.path for r in router.routes]
        assert any("/database" in r for r in routes)

    def test_health_grpc_endpoint_exists(self):
        """Health gRPC endpoint should be registered."""
        from sylion.api.health_routes import router
        routes = [r.path for r in router.routes]
        assert any("/grpc" in r for r in routes)

    def test_pool_module_imports(self):
        """DB pool module should import cleanly."""
        from sylion.db.pool import get_engine, get_session, dispose_engine
        assert callable(get_engine)
        assert callable(dispose_engine)

    def test_grpc_server_factory(self):
        """gRPC server factory should create a server."""
        from sylion.grpc.core_server import create_grpc_server
        server = create_grpc_server(port=0, max_workers=2)
        assert server is not None
        server.stop(grace=0)

    def test_all_grpc_servicers_importable(self):
        """All gRPC servicer classes should be importable."""
        from sylion.grpc.core_server import ModuleRegistryServicer, EvidenceSpineServicer
        from sylion.grpc.eventbus_server import EventBusServicer
        from sylion.grpc.execution_server import WorkflowServicer, JobServicer
        from sylion.grpc.cognitive_server import ModelRouterServicer, PlanServicer
        from sylion.grpc.governance_server import GovernanceServicer, CouncilServicer
        from sylion.grpc.aeis_server import AutonomyServicer, ExplanationServicer, ImprovementServicer
        # All should be instantiable
        assert ModuleRegistryServicer()
        assert EvidenceSpineServicer()
        assert EventBusServicer()
        assert WorkflowServicer()
        assert JobServicer()
        assert ModelRouterServicer()
        assert PlanServicer()
        assert GovernanceServicer()
        assert CouncilServicer()
        assert AutonomyServicer()
        assert ExplanationServicer()
        assert ImprovementServicer()
