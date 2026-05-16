from __future__ import annotations

from types import SimpleNamespace

from sylion.aeis.advisor.actions.retry import retry_route


def test_retry_route_updates_success(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.retry.audit.get_route_for_retry",
        lambda route_audit_id: (route_audit_id, "card-1", "accept", {"operator_id": "op-1"}, "failed"),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.retry.get_handler",
        lambda action: SimpleNamespace(
            handle=lambda ctx: SimpleNamespace(success=True, error_message=None)
        ),
    )
    updated: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "sylion.aeis.advisor.actions.retry.audit.update_route_status",
        lambda route_audit_id, status, error_message: updated.append((route_audit_id, status.value)),
    )
    success, status, error = retry_route("route-1")
    assert (success, status, error) == (True, "success", None)
    assert updated == [("route-1", "success")]
