from sylion.governance.ticket import GovernanceTicket
from sylion.operator_mobile.bridge import OperatorMobileBridge, StubPushProvider
from sylion.operator_mobile.dispatcher import OperatorMobileDispatcher
from sylion.operator_mobile.store import OperatorMobileStore


def test_dispatcher_fetches_pending_and_pushes_to_operator_devices():
    store = OperatorMobileStore(db_path=":memory:")
    provider = StubPushProvider()
    bridge = OperatorMobileBridge(store=store, push_provider=provider)
    bridge.bind_device("op-1", "token-1", "ios")

    ticket = GovernanceTicket(
        origin="mobile",
        project_id="proj-1",
        decision_class="D3",
        gate_type="blocking",
        priority="P1",
        title="Deploy to production",
        summary="Need operator approval",
        payload={"operator_id": "op-1"},
        requested_by="dispatcher-test",
    )

    dispatcher = OperatorMobileDispatcher(
        bridge=bridge,
        governance_fetch_pending=lambda **_: [ticket],
    )

    result = dispatcher.poll_once()

    assert result == {"tickets": 1, "dispatched": 1, "skipped": 0}
    assert len(provider.sent) == 1
    assert provider.sent[0]["envelope"]["payload"]["ticket_id"] == ticket.ticket_id


def test_dispatcher_skips_tickets_without_operator_binding_hint():
    bridge = OperatorMobileBridge(
        store=OperatorMobileStore(db_path=":memory:"),
        push_provider=StubPushProvider(),
    )
    ticket = GovernanceTicket(
        origin="mobile",
        title="No owner",
        summary="No operator mapping available",
        payload={},
        requested_by="dispatcher-test",
    )
    dispatcher = OperatorMobileDispatcher(
        bridge=bridge,
        governance_fetch_pending=lambda **_: [ticket],
    )

    result = dispatcher.poll_once()

    assert result == {"tickets": 1, "dispatched": 0, "skipped": 1}
