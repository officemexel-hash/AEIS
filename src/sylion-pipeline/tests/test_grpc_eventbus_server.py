"""Tests for grpc.eventbus_server module."""

import pytest

try:
    from sylion.grpc_stubs import sylion_core_pb2
    _HAS_STUBS = True
except ImportError:
    _HAS_STUBS = False

pytestmark = pytest.mark.skipif(not _HAS_STUBS, reason="gRPC stubs not available")


if _HAS_STUBS:
    from sylion.grpc.eventbus_server import EventBusServicer

    class MockContext:
        def __init__(self):
            self.code = None
            self.details = None
        def set_code(self, code):
            self.code = code
        def set_details(self, details):
            self.details = details

    class TestEventBusServicer:
        @pytest.fixture
        def servicer(self):
            return EventBusServicer()

        @pytest.fixture
        def ctx(self):
            return MockContext()

        def test_publish_event(self, servicer, ctx):
            req = sylion_core_pb2.PublishEventRequest(
                topic="test.topic",
                payload=b"hello",
                source="test.module",
                severity=sylion_core_pb2.INFO,
            )
            resp = servicer.PublishEvent(req, ctx)
            assert ctx.code is None
            assert resp.event.event_id != ""
            assert resp.event.topic == "test.topic"

        def test_subscribe_returns_events(self, servicer, ctx):
            servicer.PublishEvent(sylion_core_pb2.PublishEventRequest(
                topic="sub.topic", payload=b"data", source="s",
            ), ctx)

            req = sylion_core_pb2.SubscribeRequest(topic_filter="sub.topic")
            events = list(servicer.Subscribe(req, ctx))
            assert len(events) >= 1

        def test_list_events(self, servicer, ctx):
            for i in range(3):
                servicer.PublishEvent(sylion_core_pb2.PublishEventRequest(
                    topic=f"list.topic.{i}", source="s",
                ), ctx)

            req = sylion_core_pb2.ListEventsRequest(topic_filter="list.topic.0")
            resp = servicer.ListEvents(req, ctx)
            assert len(resp.events) >= 1

        def test_list_events_all(self, servicer, ctx):
            servicer.PublishEvent(sylion_core_pb2.PublishEventRequest(
                topic="list.all", source="s",
            ), ctx)
            req = sylion_core_pb2.ListEventsRequest()
            resp = servicer.ListEvents(req, ctx)
            assert len(resp.events) >= 1

        def test_ack_event(self, servicer, ctx):
            pub_resp = servicer.PublishEvent(sylion_core_pb2.PublishEventRequest(
                topic="ack.topic", source="s",
            ), ctx)
            ack_req = sylion_core_pb2.AckEventRequest(event_id=pub_resp.event.event_id)
            ack_resp = servicer.AckEvent(ack_req, ctx)
            assert ack_resp.acknowledged is True

        def test_ack_nonexistent(self, servicer, ctx):
            req = sylion_core_pb2.AckEventRequest(event_id="nonexistent")
            resp = servicer.AckEvent(req, ctx)
            assert resp.acknowledged is False
