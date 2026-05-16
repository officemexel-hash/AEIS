from datetime import datetime, timezone

from sylion.operator_mobile.bridge import (
    MobileBridge,
    MobilePushPayload,
    OperatorMobileBridge,
    StubPushProvider,
)
from sylion.operator_mobile.store import OperatorMobileStore


def test_bridge_implements_contract_and_notifies_bound_devices():
    store = OperatorMobileStore(db_path=":memory:")
    provider = StubPushProvider()
    bridge = OperatorMobileBridge(
        store=store,
        push_provider=provider,
        signing_secret="bridge-secret",
    )

    assert isinstance(bridge, MobileBridge)

    bridge.bind_device("operator-1", "token-1", "ios")

    payload = MobilePushPayload(
        ticket_id="ticket-1",
        title="Approval required",
        summary="Review deploy request",
        deeplink="/operator-mobile/queue/ticket-1",
        priority="P1",
        expires_at=datetime.now(timezone.utc),
        operator_id="operator-1",
    )
    bridge.notify_pending_ticket(payload)

    assert len(provider.sent) == 1
    sent = provider.sent[0]
    assert sent["devices"][0]["device_token"] == "token-1"
    state = bridge.get_notification_state("ticket-1")
    assert state is not None
    assert state["revoked"] is False
    assert state["operator_id"] == "operator-1"


def test_bridge_can_revoke_notification():
    store = OperatorMobileStore(db_path=":memory:")
    provider = StubPushProvider()
    bridge = OperatorMobileBridge(store=store, push_provider=provider)
    bridge.bind_device("operator-1", "token-1", "android")

    bridge.notify_pending_ticket(
        MobilePushPayload(
            ticket_id="ticket-2",
            title="Approval required",
            summary="Review project action",
            deeplink="/operator-mobile/queue/ticket-2",
            priority="P2",
            expires_at=datetime.now(timezone.utc),
            operator_id="operator-1",
        )
    )
    bridge.revoke_notification("ticket-2")

    assert provider.revoked[0]["ticket_id"] == "ticket-2"
    assert bridge.get_notification_state("ticket-2")["revoked"] is True
