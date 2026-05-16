"""gRPC wrapper tests for advisor preferences."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from sylion.aeis.advisor.preferences.grpc_server import PreferencesServicer
from sylion.aeis.advisor.preferences._models import PreferenceRow, ResolvedPreference, ResolutionLevel


def test_get_effective_maps_to_proto():
    row = PreferenceRow(
        user_id="u1",
        project_type="research",
        project_domain="software",
        preference_key="council_size",
        preference_value=7,
        set_by="user",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    service = SimpleNamespace(
        get_effective=lambda **kwargs: ResolvedPreference(
            value=7,
            resolution_level=ResolutionLevel.SPECIFIC,
            source_row=row,
        )
    )
    servicer = PreferencesServicer(service=service)
    response = servicer.GetEffective(
        SimpleNamespace(
            user_id="u1",
            project_type="research",
            project_domain="software",
            preference_key="council_size",
        ),
        None,
    )
    assert response.user_id == "u1"
    assert response.preference_key == "council_size"
    assert response.resolution_level != 0
