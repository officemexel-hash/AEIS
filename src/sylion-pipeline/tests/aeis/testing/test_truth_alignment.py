"""Truth Alignment Matrix tests."""
from __future__ import annotations

import pytest

from sylion.aeis.testing.truth_alignment import (
    LAYERS, FeatureSnapshot, TruthAlignmentMatrix,
)


def test_layers_constant():
    assert len(LAYERS) == 7
    assert "sot" in LAYERS
    assert "runtime" in LAYERS
    assert "docs" in LAYERS


def test_aligned_feature_no_drift():
    snap = FeatureSnapshot(
        feature_id="feat_aligned",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": True}, api={"present": True},
        ui={"present": True, "data_source": "live"},
        test={"present": True}, docs={"present": True},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap)
    row = m.build_for_feature("feat_aligned")
    assert row["aligned"] is True
    assert row["drift"] == []


def test_drift_detected_when_runtime_without_sot():
    snap = FeatureSnapshot(
        feature_id="feat_unauth",
        sot={"present": False}, masterplan={"present": False},
        runtime={"present": True}, api={"present": True},
        ui={"present": True}, test={"present": False},
        docs={"present": False},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap)
    row = m.build_for_feature("feat_unauth")
    assert row["aligned"] is False
    assert "runtime_without_sot_authorization" in row["drift"]


def test_drift_when_sot_without_runtime():
    snap = FeatureSnapshot(
        feature_id="feat_unimpl",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": False}, api={"present": False},
        ui={"present": False}, test={"present": False},
        docs={"present": False},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap)
    row = m.build_for_feature("feat_unimpl")
    assert row["aligned"] is False
    assert "sot_without_runtime_implementation" in row["drift"]


def test_drift_when_docs_ahead_of_code():
    snap = FeatureSnapshot(
        feature_id="feat_docs_only",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": False}, api={"present": False},
        ui={"present": False}, test={"present": False},
        docs={"present": True},  # docs say it's done; runtime says no
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap)
    row = m.build_for_feature("feat_docs_only")
    assert row["aligned"] is False
    assert "docs_without_runtime" in row["drift"]


def test_drift_when_ui_shows_mock_with_live_runtime():
    snap = FeatureSnapshot(
        feature_id="feat_mock_ui",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": True}, api={"present": True},
        ui={"present": True, "data_source": "mock"},  # bug
        test={"present": True}, docs={"present": True},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap)
    row = m.build_for_feature("feat_mock_ui")
    assert row["aligned"] is False
    assert "ui_shows_mock_despite_live_runtime" in row["drift"]


def test_unknown_feature_returns_drift_snapshot_missing():
    m = TruthAlignmentMatrix()
    row = m.build_for_feature("feat_notexist")
    assert row["aligned"] is False
    assert row["drift"] == ["snapshot_missing"]


def test_list_drifts_returns_only_drift_features():
    aligned = FeatureSnapshot(
        feature_id="feat_ok",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": True}, api={"present": True},
        ui={"present": True, "data_source": "live"},
        test={"present": True}, docs={"present": True},
    )
    drifted = FeatureSnapshot(
        feature_id="feat_bad",
        sot={"present": False}, masterplan={"present": False},
        runtime={"present": True},  # rogue
        api={"present": False}, ui={"present": False},
        test={"present": False}, docs={"present": False},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(aligned)
    m.upsert_snapshot(drifted)
    drifts = m.list_drifts()
    assert len(drifts) == 1
    assert drifts[0]["feature_id"] == "feat_bad"


def test_health_summary():
    m = TruthAlignmentMatrix()
    for i in range(3):
        m.upsert_snapshot(FeatureSnapshot(
            feature_id=f"f_{i}",
            sot={"present": True}, masterplan={"present": True},
            runtime={"present": True}, api={"present": True},
            ui={"present": True, "data_source": "live"},
            test={"present": True}, docs={"present": True},
        ))
    m.upsert_snapshot(FeatureSnapshot(
        feature_id="f_drift",
        sot={"present": False}, masterplan={"present": False},
        runtime={"present": True}, api={"present": True},
        ui={"present": True}, test={"present": True}, docs={"present": True},
    ))
    summary = m.health_summary()
    assert summary["total_features"] == 4
    assert summary["aligned"] == 3
    assert summary["drift"] == 1
    assert summary["alignment_pct"] == pytest.approx(0.75)


def test_list_aligned():
    snap_ok = FeatureSnapshot(
        feature_id="f_ok",
        sot={"present": True}, masterplan={"present": True},
        runtime={"present": True}, api={"present": True},
        ui={"present": True, "data_source": "live"},
        test={"present": True}, docs={"present": True},
    )
    m = TruthAlignmentMatrix()
    m.upsert_snapshot(snap_ok)
    assert m.list_aligned() == ["f_ok"]
