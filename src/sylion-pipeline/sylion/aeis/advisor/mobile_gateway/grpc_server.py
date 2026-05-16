"""Mobile gateway server entrypoint.

Etap 1: register the FastAPI router on the SYLION application. Etap 2 will add
real gRPC delivery (push channels) plus device pairing handlers backed by
``sylion.security.auth``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from sylion.aeis.advisor.mobile_gateway.api import build_mobile_router

log = logging.getLogger("sylion.aeis.advisor.mobile_gateway.grpc_server")


def register_with_app(app: FastAPI) -> None:
    """Mount the mobile gateway router on the given FastAPI application."""
    app.include_router(build_mobile_router())
    log.info("mobile_gateway: REST router mounted at /mobile/v1")


def serve(host: str = "127.0.0.1", port: int = 50061) -> None:
    """Etap 1 stub. Etap 2: replace with grpc.server() wiring once stubs exist."""
    log.warning(
        "mobile_gateway grpc_server.serve() is a stub; mount FastAPI router via "
        "register_with_app() and let the existing HTTP server handle requests"
    )
    _ = host, port
