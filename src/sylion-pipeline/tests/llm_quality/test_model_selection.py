"""Wave A-LLM FIX-023 -- decision_class -> model tier selection.

DoD per PROMPT_01 sec 7:
  [x] D5 -> deep model (opus-tier).
  [x] D0 -> cheap-fast model (haiku-tier).
"""

from __future__ import annotations

import pytest

from sylion.cognitive.council import (
    DECISION_CLASS_TIERS,
    MODEL_TIER_HIERARCHY,
    select_model_for_class,
)
from sylion.cognitive.council.voting import (
    override_class_tier,
    reset_class_tiers,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_class_tiers()
    yield
    reset_class_tiers()


# ---------------------------------------------------------------------------
# DoD coverage
# ---------------------------------------------------------------------------

class TestDoDMapping:

    def test_d0_returns_cheap_fast(self):
        assert select_model_for_class("D0") == "haiku-tier"

    def test_d5_returns_deep_slow(self):
        assert select_model_for_class("D5") == "opus-tier"

    @pytest.mark.parametrize("dc, expected", [
        ("D0", "haiku-tier"),
        ("D1", "haiku-tier"),
        ("D2", "sonnet-tier"),
        ("D3", "sonnet-tier"),
        ("D4", "opus-tier"),
        ("D5", "opus-tier"),
    ])
    def test_full_mapping(self, dc, expected):
        assert select_model_for_class(dc) == expected


# ---------------------------------------------------------------------------
# Tier hierarchy is monotonic in cost
# ---------------------------------------------------------------------------

class TestTierHierarchy:

    def test_three_tiers(self):
        assert len(MODEL_TIER_HIERARCHY) == 3

    def test_tier_order(self):
        assert MODEL_TIER_HIERARCHY == ("haiku-tier", "sonnet-tier", "opus-tier")

    def test_higher_decision_class_gets_higher_or_equal_tier(self):
        order = {tier: i for i, tier in enumerate(MODEL_TIER_HIERARCHY)}
        ranks = [order[select_model_for_class(f"D{i}")] for i in range(6)]
        assert ranks == sorted(ranks), (
            f"tier ranks should be non-decreasing: {ranks}"
        )


# ---------------------------------------------------------------------------
# Operator override + reset
# ---------------------------------------------------------------------------

class TestOverride:

    def test_override_single_class(self):
        override_class_tier("D2", "opus-tier")
        assert select_model_for_class("D2") == "opus-tier"

    def test_override_does_not_leak_to_other_classes(self):
        override_class_tier("D2", "opus-tier")
        assert select_model_for_class("D0") == "haiku-tier"
        assert select_model_for_class("D5") == "opus-tier"

    def test_override_invalid_tier_rejected(self):
        with pytest.raises(ValueError):
            override_class_tier("D2", "ferrari-tier")

    def test_reset_restores_default(self):
        override_class_tier("D0", "opus-tier")
        reset_class_tiers()
        assert select_model_for_class("D0") == "haiku-tier"

    def test_unknown_class_raises(self):
        with pytest.raises(KeyError):
            select_model_for_class("D9")


# ---------------------------------------------------------------------------
# Mapping mutations are isolated -- registry is rebuildable
# ---------------------------------------------------------------------------

class TestRegistryShape:

    def test_initial_keys_are_d0_through_d5(self):
        assert set(DECISION_CLASS_TIERS) == {"D0", "D1", "D2", "D3", "D4", "D5"}

    def test_initial_values_in_tier_hierarchy(self):
        assert all(
            tier in MODEL_TIER_HIERARCHY
            for tier in DECISION_CLASS_TIERS.values()
        )
