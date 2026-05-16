"""gRPC server stub for the history module.

Until proto codegen lands in `_generated/history_pb2*.py`, this file exposes
the service through a thin Python facade. When `grpcio` and the generated
stubs are available, replace `serve()` with the standard wiring.
"""

from __future__ import annotations

import logging

from sylion.aeis.advisor.history.service import (
    AdvisorHistoryService,
    get_history_service,
)

log = logging.getLogger("sylion.aeis.advisor.history.grpc_server")


def serve(host: str = "127.0.0.1", port: int = 50061) -> None:
    """Run the history gRPC server (placeholder).

    Once codegen runs:

        import grpc
        from concurrent import futures
        from sylion.aeis.advisor._generated import history_pb2_grpc
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        history_pb2_grpc.add_HistoryServiceServicer_to_server(_Servicer(), server)
        server.add_insecure_port(f"{host}:{port}")
        server.start()
        server.wait_for_termination()
    """
    log.warning(
        "history grpc_server.serve() is a stub until proto codegen runs; "
        "use get_history_service() in-process for now"
    )
    get_history_service()


def get_service() -> AdvisorHistoryService:
    """Return the in-process service (REST adapters and tests use this)."""
    return get_history_service()
