"""Tests for W16 Apps Builder Phase 0 cascade per ADR-001 #2."""
from __future__ import annotations

import pytest

from sylion.aeis_v2.apps_v2 import (
    DEMO_TEMPLATES,
    AppTemplate,
    MatchResult,
    list_templates,
    match_idea_to_templates,
    rank_templates,
    score_tag_overlap,
)


# --------------------------------------------------------------------------
# A. Tag-overlap scoring (Jaccard)
# --------------------------------------------------------------------------


def test_score_tag_overlap_perfect_match() -> None:
    s = score_tag_overlap({"a", "b"}, {"a", "b"})
    assert s == 1.0


def test_score_tag_overlap_disjoint_returns_zero() -> None:
    s = score_tag_overlap({"a", "b"}, {"c", "d"})
    assert s == 0.0


def test_score_tag_overlap_partial() -> None:
    s = score_tag_overlap({"a", "b", "c"}, {"a", "b", "d", "e"})
    # intersection = {a,b} (2), union = {a,b,c,d,e} (5) → 2/5 = 0.4
    assert s == pytest.approx(0.4)


def test_score_tag_overlap_empty_sets_returns_zero() -> None:
    assert score_tag_overlap(set(), set()) == 0.0


# --------------------------------------------------------------------------
# B. AppTemplate dataclass
# --------------------------------------------------------------------------


def test_apptemplate_to_dict_shape() -> None:
    tpl = DEMO_TEMPLATES[0]
    d = tpl.to_dict()
    assert d["id"] == tpl.id
    assert d["name_pl"] == tpl.name_pl
    assert isinstance(d["object_type_ids"], list)
    assert isinstance(d["widget_ids"], list)
    assert isinstance(d["tags"], list)


def test_apptemplate_matches_tags_uses_jaccard() -> None:
    tpl = AppTemplate(
        id="t", name_pl="T", description_pl="d",
        object_type_ids=["customer"], widget_ids=["KpiCard"],
        tags=["a", "b", "c"],
    )
    assert tpl.matches_tags({"a", "b"}) == pytest.approx(2 / 3)


def test_apptemplate_is_frozen() -> None:
    tpl = DEMO_TEMPLATES[0]
    with pytest.raises((AttributeError, TypeError)):
        tpl.id = "modified"  # type: ignore[misc]


# --------------------------------------------------------------------------
# C. Demo template library
# --------------------------------------------------------------------------


def test_demo_templates_has_at_least_5_entries() -> None:
    assert len(DEMO_TEMPLATES) >= 5


def test_demo_templates_have_unique_ids() -> None:
    ids = [t.id for t in DEMO_TEMPLATES]
    assert len(ids) == len(set(ids))


def test_demo_templates_widget_ids_are_known_palette() -> None:
    """Every widget_id must match a real widget in the v2 palette."""
    palette = {
        "AdvisorCardFeed", "AlertBanner", "ChartWidget", "CommandButton",
        "DateRangePicker", "JsonViewer", "KpiCard", "ObjectFormEditor",
        "ObjectListView", "TabsWidget",
    }
    for tpl in DEMO_TEMPLATES:
        for wid in tpl.widget_ids:
            assert wid in palette, f"{tpl.id} uses unknown widget {wid}"


def test_list_templates_returns_serializable_dicts() -> None:
    items = list_templates()
    assert len(items) == len(DEMO_TEMPLATES)
    assert all("id" in d and "name_pl" in d for d in items)


# --------------------------------------------------------------------------
# D. rank_templates
# --------------------------------------------------------------------------


def test_rank_templates_filters_below_min_score() -> None:
    """Templates with score < 0.05 must be filtered."""
    ranked = rank_templates({"completely-unknown-tag"}, list(DEMO_TEMPLATES))
    assert ranked == []


def test_rank_templates_returns_descending_score() -> None:
    ranked = rank_templates(
        {"inspekcja", "raport", "audyt"}, list(DEMO_TEMPLATES), top_n=3,
    )
    assert len(ranked) >= 1
    # First match should be inspection_field which has these tags
    assert ranked[0][0].id == "inspection_field"
    # Scores monotonically decreasing
    scores = [s for _, s in ranked]
    assert scores == sorted(scores, reverse=True)


def test_rank_templates_respects_top_n() -> None:
    # Use very generic tags so all templates score
    big_query = {
        "inspekcja", "zatwierdzanie", "magazyn", "czas-pracy", "serwis",
    }
    ranked = rank_templates(big_query, list(DEMO_TEMPLATES), top_n=2)
    assert len(ranked) <= 2


# --------------------------------------------------------------------------
# E. match_idea_to_templates (idea→app studio cascade Phase 0)
# --------------------------------------------------------------------------


def test_match_idea_to_templates_finds_inspection_app() -> None:
    """Idea text using template's exact tags maps to inspection_field.

    Phase 0: naive whitespace split + lowercase. No stemming, so tags must
    appear in their canonical form (matching tag literals in DEMO_TEMPLATES).
    G1 will add stemming + embeddings to handle Polish declinations.
    """
    results = match_idea_to_templates(
        "inspekcja terenowa raport audyt monitorowanie",
        top_n=3,
    )
    assert len(results) >= 1
    assert results[0].template.id == "inspection_field"
    assert results[0].method == "tag_overlap"
    assert "Pokrycie tagow" in results[0].reason_pl


def test_match_idea_to_templates_returns_match_result_objects() -> None:
    results = match_idea_to_templates("workflow zatwierdzania dokumentow")
    assert all(isinstance(r, MatchResult) for r in results)
    assert results[0].template.id == "approval_workflow"


def test_match_idea_to_templates_returns_empty_for_nonsense() -> None:
    """Nonsense input that overlaps zero tags returns empty list."""
    results = match_idea_to_templates("xyzzy frobnicate quuxbar")
    assert results == []


def test_match_idea_to_templates_to_dict_serializable() -> None:
    results = match_idea_to_templates("magazyn inwentaryzacja stany")
    assert len(results) >= 1
    d = results[0].to_dict()
    assert "template" in d and isinstance(d["template"], dict)
    assert "score" in d and isinstance(d["score"], float)
    assert d["method"] == "tag_overlap"
    assert "reason_pl" in d
