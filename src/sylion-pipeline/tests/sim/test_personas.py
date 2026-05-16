"""Tests for persona catalog validity."""

from __future__ import annotations

import pytest

from sylion.sim.personas import PERSONAS, get_persona, list_persona_ids


class TestPersonaAttributes:
    def test_all_personas_have_valid_ids(self):
        ids = [p.id for p in PERSONAS]
        assert len(ids) == len(set(ids)), "Persona IDs must be unique"
        assert len(ids) == 10, "Expected exactly 10 personas"

    def test_tech_skill_in_range(self):
        for p in PERSONAS:
            assert 1 <= p.tech_skill <= 5, f"{p.id}: tech_skill out of range"

    def test_risk_appetite_in_range(self):
        for p in PERSONAS:
            assert 1 <= p.risk_appetite <= 5, f"{p.id}: risk_appetite out of range"

    def test_council_preference_in_range(self):
        for p in PERSONAS:
            assert 3 <= p.council_preference <= 9, f"{p.id}: council_preference out of range"

    def test_decision_speed_positive(self):
        for p in PERSONAS:
            assert p.decision_speed_p50 > 0, f"{p.id}: decision_speed must be positive"

    def test_default_distribution_sums_to_one(self):
        for p in PERSONAS:
            total = sum(p.default_distribution.values())
            assert 0.99 <= total <= 1.01, f"{p.id}: distribution sums to {total}, expected ~1.0"

    def test_typical_actions_non_empty(self):
        for p in PERSONAS:
            assert p.typical_actions, f"{p.id}: typical_actions must not be empty"

    def test_hard_change_policy_valid(self):
        valid = {"always_confirm", "mostly_confirm", "always_reject"}
        for p in PERSONAS:
            assert p.hard_change_policy in valid, f"{p.id}: invalid hard_change_policy"

    def test_cost_sensitivity_valid(self):
        valid = {"low", "medium", "high"}
        for p in PERSONAS:
            assert p.cost_sensitivity in valid, f"{p.id}: invalid cost_sensitivity"

    def test_autonomy_level_valid(self):
        valid = {"auto", "suggest", "manual"}
        for p in PERSONAS:
            assert p.autonomy_level in valid, f"{p.id}: invalid autonomy_level"

    def test_get_persona_lookup(self):
        for p in PERSONAS:
            assert get_persona(p.id) is p

    def test_get_persona_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_persona("nonexistent")

    def test_list_persona_ids(self):
        assert len(list_persona_ids()) == 10
