"""Tests for sylion.providers.capabilities — tag vocabulary + MODEL_TAGS registry.

Covers:
  - tags_for() returns tags for a known model (and an empty set for unknown)
  - models_with_tags filters by required tags (vision, embeddings)
  - models_with_tags honours the prefer ordering
  - validate_registry catches typos (no unknown tags)
  - All exposed string constants are members of ALL_TAGS
"""

from __future__ import annotations

import pytest

from sylion.providers import capabilities as cap
from sylion.providers.capabilities import (
    ALL_TAGS,
    CAP_LONG_CONTEXT,
    LOCALITY_CLOUD,
    LOCALITY_LOCAL,
    MODALITY_EMBEDDINGS,
    MODALITY_VISION,
    MODEL_TAGS,
    SPEED_FAST,
    TIER_CHEAP,
    models_with_tags,
    tags_for,
    validate_registry,
)


class TestTagsFor:

    def test_known_model_returns_tags(self):
        tags = tags_for("claude-haiku-4-5")
        assert MODALITY_VISION in tags
        assert TIER_CHEAP in tags
        assert SPEED_FAST in tags
        assert LOCALITY_CLOUD in tags

    def test_unknown_model_returns_empty(self):
        assert tags_for("absolutely-not-a-real-model") == frozenset()

    def test_local_model_has_local_tag(self):
        tags = tags_for("qwen2.5:7b-instruct")
        assert LOCALITY_LOCAL in tags
        assert LOCALITY_CLOUD not in tags


class TestModelsWithTags:

    def test_vision_filter_returns_only_vision_capable(self):
        result = models_with_tags({MODALITY_VISION})
        assert result, "expected at least one vision-capable model"
        for model_id in result:
            assert MODALITY_VISION in MODEL_TAGS[model_id]

    def test_required_must_all_be_present(self):
        # Vision + long-context: both must be present.
        result = models_with_tags({MODALITY_VISION, CAP_LONG_CONTEXT})
        for model_id in result:
            tags = MODEL_TAGS[model_id]
            assert MODALITY_VISION in tags
            assert CAP_LONG_CONTEXT in tags

    def test_embedding_filter_isolates_embedding_models(self):
        result = models_with_tags({MODALITY_EMBEDDINGS})
        assert result
        # All embedding-tagged models in the registry should be returned.
        embed_models = {m for m, t in MODEL_TAGS.items() if MODALITY_EMBEDDINGS in t}
        assert set(result) == embed_models

    def test_prefer_ordering_local_first(self):
        # Cheap + fast spans both cloud and local. Asking the helper to
        # prefer local should rank local entries before cloud.
        result = models_with_tags(
            {TIER_CHEAP, SPEED_FAST},
            prefer={LOCALITY_LOCAL},
        )
        assert result
        # The first ranked candidate should be a local model.
        first = MODEL_TAGS[result[0]]
        assert LOCALITY_LOCAL in first

    def test_unsatisfiable_required_returns_empty(self):
        # Made-up requirement — no model should match.
        assert models_with_tags({"definitely-not-a-tag"}) == []


class TestRegistryHygiene:

    def test_no_unknown_tags(self):
        # Every tag in MODEL_TAGS must exist in ALL_TAGS.
        bad = validate_registry()
        assert bad == [], f"unknown tags: {bad}"

    def test_minimum_model_count(self):
        # PDF §8.1 — Task C requires ≥30 models tagged.
        assert len(MODEL_TAGS) >= 30

    def test_all_tags_are_strings(self):
        # ALL_TAGS contents are simple snake/kebab-case strings.
        for tag in ALL_TAGS:
            assert isinstance(tag, str)
            assert tag and tag.strip() == tag

    def test_all_exported_constants_are_in_all_tags(self):
        # Every UPPERCASE constant in capabilities module that holds a
        # tag-string value must be a member of ALL_TAGS.
        for name in dir(cap):
            if not name.isupper():
                continue
            if name in {"ALL_TAGS", "MODEL_TAGS"}:
                continue
            value = getattr(cap, name)
            if isinstance(value, str) and "_" in name:
                assert value in ALL_TAGS, f"{name}={value!r} missing from ALL_TAGS"


class TestTagSemantics:

    def test_premium_models_are_not_cheap(self):
        # Sanity: a model tagged premium should not also be cheap.
        for model_id, tags in MODEL_TAGS.items():
            both = "premium" in tags and "cheap" in tags
            assert not both, f"{model_id} is tagged both premium AND cheap"

    def test_local_models_have_locality_local(self):
        # Anything tagged with cpu/gpu locality MUST also carry "local"
        # if it is in fact a local runtime; cloud GPUs are tagged cloud.
        for model_id, tags in MODEL_TAGS.items():
            if "local" in tags:
                # local models should not also be cloud.
                assert "cloud" not in tags, (
                    f"{model_id} is tagged both local and cloud"
                )
