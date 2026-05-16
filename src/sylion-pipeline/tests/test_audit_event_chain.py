from sylion.governance.audit_event_chain import AuditEventChain


def test_single_event():
    chain = AuditEventChain()
    event = chain.append({"id": 1})
    assert event["prev_hash"] == ""
    assert chain.verify() is True


def test_multi_event_chain():
    chain = AuditEventChain()
    first = chain.append({"id": 1})
    second = chain.append({"id": 2})
    assert second["prev_hash"] == first["content_hash"]
    assert chain.verify() is True


def test_tampered_event_detection():
    chain = AuditEventChain()
    chain.append({"id": 1})
    chain.append({"id": 2})
    chain.events[1]["content"]["id"] = 9
    assert chain.verify() is False


def test_fresh_chain():
    assert AuditEventChain().verify() is True
