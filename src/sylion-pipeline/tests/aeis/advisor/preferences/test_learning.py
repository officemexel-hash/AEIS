"""Learning flow tests for advisor preferences."""

from __future__ import annotations

from sylion.aeis.advisor.preferences import learning


def test_soft_learning_updates_existing_level(monkeypatch):
    recorded = {}

    def _fake_upsert(*args):
        recorded["upsert"] = args
        return False, "medium"

    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.learning.resolver.find_most_specific_existing_level",
        lambda **kwargs: ("research", None),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.learning._db.get_preference_row",
        lambda *args, **kwargs: {"preference_value": "medium"},
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.learning._db.upsert_preference",
        _fake_upsert,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences.learning.audit.log_change",
        lambda **kwargs: recorded.setdefault("audit", kwargs),
    )

    updated_existing, key = learning.apply_soft_learning(
        user_id="u1",
        preference_key="cost_sensitivity",
        value="high",
        project_type="research",
        project_domain="software",
    )

    assert updated_existing is True
    assert key == "cost_sensitivity"
    assert recorded["upsert"][1] == "research"
    assert recorded["upsert"][2] is None


def test_hard_change_request_and_confirm():
    learning.reset_pending_requests()
    request = learning.request_hard_change(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="autonomy_level",
        proposed_value="auto",
        source_card_id="card-1",
        rationale="operator approved",
    )

    ok, confirmed, error = learning.confirm_hard_change(
        request_id=request.request_id,
        operator_signature="sig-1",
        confirmed=True,
    )

    assert ok is True
    assert error is None
    assert confirmed is not None
    assert confirmed.confirmed is True
