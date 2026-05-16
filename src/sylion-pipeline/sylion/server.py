#!/usr/bin/env python3
"""
SYLION Unified Server — FastAPI + gRPC

Starts both the FastAPI HTTP server and gRPC server simultaneously.

Usage:
    python -m sylion.server [--http-port 8421] [--grpc-port 50051] [--no-grpc]
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import threading
from concurrent import futures

log = logging.getLogger("sylion.server")


def _start_grpc(port: int, max_workers: int = 10):
    """Start gRPC server in the current thread (blocking)."""
    try:
        from sylion.grpc.core_server import create_grpc_server
        server = create_grpc_server(port=port, max_workers=max_workers)
        server.start()
        log.info("gRPC server listening on [::]:%d", port)
        return server
    except ImportError as exc:
        log.warning("gRPC server disabled: %s", exc)
        return None


def main():
    parser = argparse.ArgumentParser(description="SYLION Unified Server")
    parser.add_argument("--http-port", type=int,
                        default=int(os.getenv("SYLION_HTTP_PORT", "8421")),
                        help="FastAPI HTTP port (default: 8421)")
    parser.add_argument("--grpc-port", type=int,
                        default=int(os.getenv("SYLION_GRPC_PORT", "50051")),
                        help="gRPC port (default: 50051)")
    parser.add_argument("--no-grpc", action="store_true",
                        help="Disable gRPC server")
    parser.add_argument("--host", default="127.0.0.1",
                        help="Host to bind HTTP to (default: 127.0.0.1)")
    parser.add_argument("--log-level", default="info",
                        choices=["debug", "info", "warning", "error"],
                        help="Log level (default: info)")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Graceful shutdown on SIGTERM/SIGINT
    _shutdown = threading.Event()

    def _signal_handler(signum, _frame):
        log.info("Received signal %s, shutting down...", signal.Signals(signum).name)
        _shutdown.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    grpc_server = None
    grpc_thread = None
    grpc_ready = threading.Event()

    # Start gRPC in background thread if enabled
    if not args.no_grpc:
        def _grpc_worker():
            nonlocal grpc_server
            grpc_server = _start_grpc(args.grpc_port, 10)
            grpc_ready.set()
            if grpc_server:
                grpc_server.wait_for_termination()

        grpc_thread = threading.Thread(
            target=_grpc_worker,
            daemon=True,
            name="sylion-grpc",
        )
        grpc_thread.start()
        grpc_ready.wait(timeout=5)
        log.info("gRPC server ready")

    # Start FastAPI in main thread
    log.info("FastAPI server starting on %s:%d", args.host, args.http_port)
    try:
        import uvicorn
        uvicorn.run(
            "sylion.api.app:app",
            host=args.host,
            port=args.http_port,
            log_level="info",
            workers=1,
            timeout_graceful_shutdown=3,
        )
    except ImportError:
        log.error("uvicorn not available")
        sys.exit(1)
    finally:
        if grpc_server:
            log.info("Shutting down gRPC server...")
            grpc_server.stop(grace=2)
            grpc_server.wait_for_termination(timeout=5)


if __name__ == "__main__":
    main()
