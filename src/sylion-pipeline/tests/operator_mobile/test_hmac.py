from sylion.operator_mobile.secrets import sign_payload, verify_payload


def test_sign_and_verify_payload_roundtrip():
    payload = {
        "ticket_id": "tick-1",
        "priority": "P1",
        "summary": "Approve deployment",
    }
    signature = sign_payload("secret-key", payload)

    assert signature
    assert verify_payload("secret-key", payload, signature) is True
    assert verify_payload("wrong-secret", payload, signature) is False
