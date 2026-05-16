"""SYLION AEIS Advisor — Mobile Gateway (Etap 1 stub).

REST gateway mounted at ``/mobile/v1``. Etap 1 wires endpoints in-process to
``sylion.aeis.advisor.engine``; Etap 2 swaps the in-process call for a real
gRPC client and adds the Kotlin Multiplatform mobile app on top.
"""

from sylion.aeis.advisor.mobile_gateway.api import (
    build_mobile_router,
    reset_mobile_router,
)

__all__ = ["build_mobile_router", "reset_mobile_router"]
