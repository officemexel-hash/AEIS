"""Resolver tests for advisor preferences."""

from __future__ import annotations

from datetime import datetime, timezone

from sylion.aeis.advisor.preferences import resolver
from sylion.aeis.advisor.preferences._models import ResolutionLevel


def test_specific_level_wins(monkeypatch):
    now = datetime.now(timezone.utc)
    rows = {
        ("u1", "research", "software", "council_size"): {
            "user_id": "u1",
            "project_type": "research",
            "project_domain": "software",
            "preference_key": "council_size",
            "preference_value": 7,
            "set_by": "user",
            "created_at": now,
            "updated_at": now,
        },
        ("u1", "research", None, "council_size"): {
            "user_id": "u1",
            "project_type": "research",
            "project_domain": None,
            "preference_key": "council_size",
            "preference_value": 5,
            "set_by": "user",
            "created_at": now,
            "updated_at": now,
        },
    }
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences._db.get_preference_row",
        lambda user_id, project_type, project_domain, preference_key: rows.get(
            (user_id, project_type, project_domain, preference_key)
        ),
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences._db.get_system_default",
        lambda preference_key: 3,
    )

    resolved = resolver.resolve_effective(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="council_size",
    )
    assert resolved.value == 7
    assert resolved.resolution_level == ResolutionLevel.SPECIFIC


def test_system_default_fallback(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences._db.get_preference_row",
        lambda user_id, project_type, project_domain, preference_key: None,
    )
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences._db.get_system_default",
        lambda preference_key: "suggest",
    )

    resolved = resolver.resolve_effective(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="autonomy_level",
    )
    assert resolved.value == "suggest"
    assert resolved.resolution_level == ResolutionLevel.SYSTEM_DEFAULT


def test_find_most_specific_existing_level(monkeypatch):
    monkeypatch.setattr(
        "sylion.aeis.advisor.preferences._db.get_preference_row",
        lambda user_id, project_type, project_domain, preference_key: (
            {"ok": True} if (project_type, project_domain) == (None, "software") else None
        ),
    )
    assert resolver.find_most_specific_existing_level(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="cost_sensitivity",
    ) == (None, "software")
