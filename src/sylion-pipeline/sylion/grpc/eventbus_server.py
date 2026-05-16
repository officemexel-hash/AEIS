"""
SYLION gRPC -- Event Bus Service Server

Wraps sylion.core.event_bus.EventBus to serve EventBusService RPCs.
"""

from __future__ import annotations

import logging

import grpc

import uuid

from sylion.core.event_bus import get_event_bus, SylionEvent

log = logging.getLogger("sylion.grpc.eventbus_server")

try:
    from sylion.grpc_stubs import sylion_core_pb2
    from sylion.grpc_stubs import sylion_core_pb2_grpc
    from sylion.grpc_stubs import sylion_common_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False
    log.warning("gRPC stubs not available, EventBus server disabled")


if _HAS_STUBS:

    _SEVERITY_MAP = {
        sylion_core_pb2.DEBUG: "DEBUG",
        sylion_core_pb2.INFO: "INFO",
        sylion_core_pb2.WARNING: "WARNING",
        sylion_core_pb2.ERROR: "ERROR",
        sylion_core_pb2.CRITICAL: "CRITICAL",
    }

    class EventBusServicer(sylion_core_pb2_grpc.EventBusServiceServicer):
        """gRPC server for Event Bus."""

        def __init__(self):
            self._bus = get_event_bus()

        def PublishEvent(self, request, context):
            event = SylionEvent(
                event_id=uuid.uuid4().hex,
                topic=request.topic,
                payload={"raw": request.payload.decode("utf-8", errors="replace")} if request.payload else {},
                source_module=request.source,
            )
            event_id = self._bus.publish(event)
            return sylion_core_pb2.PublishEventResponse(
                event=sylion_core_pb2.Event(
                    event_id=event_id,
                    topic=request.topic,
                    payload=request.payload,
                    source=request.source,
                    severity=request.severity,
                )
            )

        def Subscribe(self, request, context):
            events = self._bus.query(
                topic=request.topic_filter if request.topic_filter else None,
                limit=1000,
            )
            for ev in events:
                yield sylion_core_pb2.Event(
                    event_id=ev.get("event_id", ""),
                    topic=ev.get("topic", ""),
                    payload=ev.get("payload", "").encode("utf-8") if isinstance(ev.get("payload"), str) else b"",
                    source=ev.get("source_module", ""),
                )

        def ListEvents(self, request, context):
            events = self._bus.query(
                topic=request.topic_filter if request.topic_filter else None,
                since=request.since_epoch if request.since_epoch else None,
                limit=request.page_size or 100,
            )
            pb_events = []
            for ev in events:
                payload_raw = ev.get("payload", "")
                if isinstance(payload_raw, str):
                    payload_bytes = payload_raw.encode("utf-8")
                elif isinstance(payload_raw, dict):
                    import json
                    payload_bytes = json.dumps(payload_raw).encode("utf-8")
                else:
                    payload_bytes = b""
                pb_events.append(sylion_core_pb2.Event(
                    event_id=ev.get("event_id", ""),
                    topic=ev.get("topic", ""),
                    payload=payload_bytes,
                    source=ev.get("source_module", ""),
                ))
            return sylion_core_pb2.ListEventsResponse(events=pb_events)

        def AckEvent(self, request, context):
            ok = self._bus.ack(request.event_id)
            return sylion_core_pb2.AckEventResponse(acknowledged=ok)
