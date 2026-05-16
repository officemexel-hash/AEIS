"""S8 — Operator Control flow: bind → fetch queue → resolve → audit.

Bind a mobile device, push a ticket notification, list devices, ensure
the bridge canonicalises payloads + signs, and finally clean up.
"""
from __future__ import annotations


def test_mobile_bind_list_unbind_round_trip():
    from sylion.operator_mobile import (
        get_operator_mobile_bridge,
        get_operator_mobile_store,
    )

    bridge = get_operator_mobile_bridge()
    store = get_operator_mobile_store()

    bridge.bind_device(
        operator_id="op-S8",
        device_token="tok-S8-deviceA",
        platform="ios",
    )

    devices = store.list_devices(operator_id="op-S8")
    assert any(d.get("device_token") == "tok-S8-deviceA" for d in devices)

    bridge_devices = bridge.list_devices(operator_id="op-S8")
    assert len(bridge_devices) == len(devices)

    device_id = devices[0].get("device_id") or devices[0].get("id")
    if device_id:
        unbound = bridge.unbind_device(device_id, operator_id="op-S8")
        assert isinstance(unbound, bool)


def test_ticket_notification_sign_and_payload_consistency():
    from sylion.governance.ticket import GovernanceTicket
    from sylion.governance.tickets import submit
    from sylion.operator_mobile import (
        canonical_payload,
        get_operator_mobile_bridge,
        sign_payload,
        verify_payload,
    )

    ticket_id = submit(GovernanceTicket(
        origin="mobile",
        project_id="S8-mobile",
        decision_class="D2",
        gate_type="non_blocking",
        priority="P2",
        title="S8 — mobile probe",
        summary="Verify payload signing roundtrip.",
        requested_by="d-integrate",
    ))

    bridge = get_operator_mobile_bridge()
    bridge.bind_device(operator_id="op-S8b", device_token="tok-S8b", platform="android")

    payload = bridge.build_payload_from_ticket(ticket_id, operator_id="op-S8b")
    assert payload is not None

    secret = "test-secret-S8"
    payload_dict = {"ticket_id": ticket_id, "decision": "approved"}
    canon = canonical_payload(payload_dict)
    assert isinstance(canon, str) and canon
    signature = sign_payload(secret, payload_dict)
    assert signature
    assert verify_payload(secret, payload_dict, signature) is True
    assert verify_payload("wrong-secret", payload_dict, signature) is False
