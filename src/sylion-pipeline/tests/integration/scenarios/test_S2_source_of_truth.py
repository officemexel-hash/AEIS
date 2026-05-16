"""S2 — Source of Truth: workspace canonical_book vs project_mode docs.

Verifies that the canonical_book / canonical_book_input fields persisted on
the project record are stable across read paths and survive an
upsert-roundtrip without drift.
"""
from __future__ import annotations


def test_canonical_book_round_trip_from_workspace_to_project_mode():
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    project_id = "S2-source-of-truth"
    canonical_input = "PROJECT BOOK v1.0\n\n## Chapter 1\nThe pipeline shall be honest."
    canonical_final = canonical_input + "\n\n## Chapter 2\nThe operator stays in the loop."

    store.upsert_project({
        "project_id": project_id,
        "name": "S2 — Truth plane",
        "canonical_book_input": canonical_input,
        "canonical_book": canonical_final,
    })

    p1 = store.get_project(project_id)
    assert p1 is not None
    assert p1["canonical_book_input"] == canonical_input
    assert p1["canonical_book"] == canonical_final

    store.upsert_project({
        "project_id": project_id,
        "name": "S2 — Truth plane",
        "canonical_book_input": canonical_input,
        "canonical_book": canonical_final,
        "phase": "execution",
    })

    p2 = store.get_project(project_id)
    assert p2["canonical_book_input"] == canonical_input
    assert p2["canonical_book"] == canonical_final
    assert p2["phase"] == "execution"


def test_listing_view_keeps_truth_alignment():
    from sylion.project_mode.store import get_project_mode_store

    store = get_project_mode_store()
    project_id = "S2-list-view"
    book = "Listing-view truth probe content."
    store.upsert_project({
        "project_id": project_id,
        "canonical_book": book,
        "canonical_book_input": book,
    })

    direct = store.get_project(project_id)
    listed = next((p for p in store.list_projects() if p["project_id"] == project_id), None)
    assert listed is not None
    assert listed["canonical_book"] == direct["canonical_book"] == book
