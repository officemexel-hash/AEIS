"""W14 Truth Alignment Matrix.

For each feature, compares its presence/state across 7 layers:
  SoT, Masterplan, Runtime, API, UI, Tests, Docs

A feature is 'aligned' iff all 7 layers report the same truth.
Drift entries are computed from missing/contradicting layers.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("sylion.aeis.testing.truth_alignment")


LAYERS: tuple[str, ...] = (
    "sot", "masterplan", "runtime", "api", "ui", "test", "docs",
)


@dataclass
class FeatureSnapshot:
    """Per-layer snapshot for a single feature."""
    feature_id: str = ""
    sot: dict = field(default_factory=lambda: {"present": False})
    masterplan: dict = field(default_factory=lambda: {"present": False})
    runtime: dict = field(default_factory=lambda: {"present": False})
    api: dict = field(default_factory=lambda: {"present": False})
    ui: dict = field(default_factory=lambda: {"present": False})
    test: dict = field(default_factory=lambda: {"present": False})
    docs: dict = field(default_factory=lambda: {"present": False})
    captured_at: float = field(default_factory=time.time)

    def to_matrix_row(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            **{layer: getattr(self, layer) for layer in LAYERS},
            "captured_at": self.captured_at,
        }


class TruthAlignmentMatrix:
    """Build + query alignment matrices."""

    def __init__(self) -> None:
        self._snapshots: dict[str, FeatureSnapshot] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_snapshot(self, snapshot: FeatureSnapshot) -> None:
        self._snapshots[snapshot.feature_id] = snapshot

    def build_for_feature(self, feature_id: str) -> dict:
        """Return matrix entry for a single feature.

        Returns dict with: feature_id, per-layer state, aligned (bool),
        drift (list of drift descriptions).
        """
        snap = self._snapshots.get(feature_id)
        if snap is None:
            return {
                "feature_id": feature_id,
                "aligned": False,
                "drift": ["snapshot_missing"],
            }
        row = snap.to_matrix_row()
        aligned, drift = self._evaluate(snap)
        row["aligned"] = aligned
        row["drift"] = drift
        return row

    def list_drifts(self) -> list[dict]:
        """Return drift entries across all snapshots."""
        out: list[dict] = []
        for fid, snap in self._snapshots.items():
            aligned, drift = self._evaluate(snap)
            if not aligned:
                out.append({
                    "feature_id": fid,
                    "drift": drift,
                    "captured_at": snap.captured_at,
                })
        return out

    def list_aligned(self) -> list[str]:
        return [
            fid for fid, snap in self._snapshots.items()
            if self._evaluate(snap)[0]
        ]

    def health_summary(self) -> dict:
        total = len(self._snapshots)
        aligned = sum(1 for s in self._snapshots.values() if self._evaluate(s)[0])
        return {
            "total_features": total,
            "aligned": aligned,
            "drift": total - aligned,
            "alignment_pct": (aligned / total) if total else 1.0,
        }

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _evaluate(self, snap: FeatureSnapshot) -> tuple[bool, list[str]]:
        drift: list[str] = []

        # All layers must report the same `present` value
        present_set = {bool(getattr(snap, l).get("present", False)) for l in LAYERS}
        if len(present_set) > 1:
            for l in LAYERS:
                if not bool(getattr(snap, l).get("present", False)):
                    drift.append(f"{l}.present=false")

        # Hierarchy of truth: kod -> runtime -> API -> UI -> tests -> docs.
        # If runtime.present=true but sot.present=false -> drift (out-of-spec impl)
        if snap.runtime.get("present") and not snap.sot.get("present"):
            drift.append("runtime_without_sot_authorization")

        # If sot.present=true but runtime.present=false -> drift (unimplemented spec)
        if snap.sot.get("present") and not snap.runtime.get("present"):
            drift.append("sot_without_runtime_implementation")

        # docs.present=true while runtime.present=false -> docs ahead of code
        if snap.docs.get("present") and not snap.runtime.get("present"):
            drift.append("docs_without_runtime")

        # Mock badge inconsistency
        if snap.ui.get("present") and snap.ui.get("data_source") in (
            "mock", "demo", "fallback"
        ):
            if snap.runtime.get("present"):
                drift.append("ui_shows_mock_despite_live_runtime")

        return (len(drift) == 0, drift)


__all__ = ["TruthAlignmentMatrix", "FeatureSnapshot", "LAYERS"]
