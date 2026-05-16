"""AEIS Advisor — Subscription gRPC server stub."""

from __future__ import annotations

import logging

from sylion.aeis.advisor.subscription.service import SubscriptionService

log = logging.getLogger("sylion.aeis.advisor.subscription.grpc_server")


class SubscriptionServicer:
    """gRPC servicer for SubscriptionService (placeholder)."""

    def __init__(self, service: SubscriptionService | None = None):
        from sylion.aeis.advisor.subscription.service import get_subscription_service
        self._service = service or get_subscription_service()

    def RecordUsage(self, request, context):
        log.info("RecordUsage called")
        return {}

    def GetUsageReport(self, request, context):
        log.info("GetUsageReport called")
        return {}

    def ComputeROI(self, request, context):
        log.info("ComputeROI called")
        return {}

    def ListAvailablePlans(self, request, context):
        log.info("ListAvailablePlans called")
        return {}

    def RegisterCustomPlan(self, request, context):
        log.info("RegisterCustomPlan called")
        return {}
