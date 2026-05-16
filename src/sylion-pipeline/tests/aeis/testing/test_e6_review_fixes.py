"""W14 E6 review-fix regression tests.

Pins issues surfaced by Codex BLOCK 98% (9 bugs + 3 drifts) and
Claude self-audit (project-scoped findings, signature drift).
"""
from __future__ import annotations

import pytest

from sylion.aeis.testing.ontology import OntologyStore
from sylion.aeis.testing.ontology.objects import Finding, TestCharter
from sylion.aeis.testing.release_rail import (
    CHECKLIST, PROD_CHECKLIST, RC_CHECKLIST, ReleaseRail,
)
from sylion.pipeline.state_machine import (
    ALLOWED_TRANSITIONS, RELEASE_TRIGGER_STATES, STATES,
)


@pytest.fixture
def store():
    return OntologyStore()


# ---------------------------------------------------------------------------
# Codex bug — CHECKLIST class attribute exists
# ---------------------------------------------------------------------------


def test_release_rail_exposes_class_checklist():
    assert hasattr(ReleaseRail, "CHECKLIST")
    assert tuple(ReleaseRail.CHECKLIST) == RC_CHECKLIST
    assert tuple(CHECKLIST) == RC_CHECKLIST
    assert len(CHECKLIST) == 12
    assert len(PROD_CHECKLIST) == 6


# ---------------------------------------------------------------------------
# Codex bug — evaluate_for_project returns C6-compliant statuses only
# ---------------------------------------------------------------------------


def test_evaluate_for_project_returns_blocked_when_checklist_fails(store):
    rail = ReleaseRail(ontology=store)
    out = rail.evaluate_for_project("proj_demo")
    assert out["status"] == "blocked"
    assert "checklist_results" in out
    assert "blockers" in out
    assert "sot_approved" in out["blockers"]


def test_evaluate_for_project_returns_release_candidate_when_rc_clean(store):
    rail = ReleaseRail(ontology=store)
    overrides = {item: True for item in RC_CHECKLIST}
    overrides["all_mandatory_tests_passed"] = True
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    # All RC items satisfied but production checklist still empty -> RC.
    assert out["status"] == "release_candidate"


def test_evaluate_for_project_returns_production_ready_when_full(store):
    rail = ReleaseRail(ontology=store)
    overrides = {item: True for item in (*RC_CHECKLIST, *PROD_CHECKLIST)}
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    assert out["status"] == "production_ready"
    assert out["blockers"] == []


def test_evaluate_for_project_hydrates_project_mode_release_facts(store, monkeypatch):
    class FakeProjectStore:
        def get_project(self, project_id):
            assert project_id == "project_demo"
            return {
                "project_id": project_id,
                "canonical_book": "# Source of Truth",
                "masterplan": "# Masterplan",
                "canon_frozen_at": 123.0,
                "masterplan_frozen_at": 124.0,
                "canon_hash": "sha-canon",
                "masterplan_hash": "sha-masterplan",
                "approvals": {"book": True, "operating_model": True},
                "launch": {
                    "artifact_path": "/tmp/app.html",
                    "artifact_sha256": "sha-artifact",
                    "validation": {
                        "success": True,
                        "stages": {
                            "contract_tests": {"success": True},
                            "smoke_tests": {"success": True},
                        },
                    },
                    "audit": {
                        "results": [
                            {"status": "pass", "audit_type": "security_officer"},
                            {"status": "pass", "audit_type": "quality_perf_reviewer"},
                        ],
                    },
                },
                "events": [
                    {"event_type": "project.created"},
                    {"event_type": "project.canon.frozen"},
                    {"event_type": "project.masterplan.frozen"},
                    {"event_type": "project.build.completed"},
                    {"event_type": "project.validation.completed"},
                    {"event_type": "project.audit.completed"},
                    {"event_type": "project.execution.completed"},
                ],
            }

    import sylion.project_mode.store as project_store_mod

    monkeypatch.setattr(
        project_store_mod, "get_project_mode_store", lambda: FakeProjectStore(),
    )
    rail = ReleaseRail(ontology=store)
    out = rail.evaluate_for_project("project_demo")
    checks = out["checklist_results"]
    assert checks["sot_approved"] is True
    assert checks["masterplan_approved"] is True
    assert checks["all_mandatory_tests_passed"] is True
    assert checks["audit_chain_intact"] is True
    assert checks["artifact_hashes_present"] is True
    # Still not production-ready: a W14 Test Charter and production approvals
    # are separate release artifacts, not inferred from Project Mode launch.
    assert checks["test_charter_approved"] is False


def test_test_charter_accepts_project_mode_project_ids():
    charter = TestCharter(
        project_id="project_abcdef123456",
        source_of_truth_version="sha-canon",
        masterplan_version="sha-masterplan",
        required_test_classes=["T0", "T11"],
    )
    assert charter.project_id == "project_abcdef123456"


def test_evaluate_for_project_status_in_canonical_set(store):
    """C6 requires only 3 status values."""
    rail = ReleaseRail(ontology=store)
    out = rail.evaluate_for_project("proj_demo")
    assert out["status"] in ("release_candidate", "production_ready", "blocked")


# ---------------------------------------------------------------------------
# Self-audit — project_id normalization rejects bad input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_pid", [
    "", "demo_no_prefix", "../proj_x", "proj_x/etc/passwd",
    "proj_x\\windows", "proj_x\x00null", None, 42,
])
def test_evaluate_for_project_rejects_bad_project_id(store, bad_pid):
    rail = ReleaseRail(ontology=store)
    out = rail.evaluate_for_project(bad_pid)
    assert out["status"] == "blocked"
    assert "invalid_project_id" in out["blockers"]


# ---------------------------------------------------------------------------
# Self-audit + Kimi attack #1 — project-scoped findings (no cross-project leak)
# ---------------------------------------------------------------------------


def test_evaluate_for_project_isolates_findings_across_projects(store):
    """A P0 finding tied to proj_other must not block proj_demo."""
    other = Finding(
        title="cross-project bleed", description="proj_other failure",
        discovered_by="evaluator", severity="P0",
        ticket_id="hg_proj_other_xyz",
    )
    store.create(other)
    rail = ReleaseRail(ontology=store)
    overrides = {item: True for item in RC_CHECKLIST}
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    # proj_other finding doesn't appear in proj_demo's checklist.
    assert out["checklist_results"]["no_p0_p1_findings"] is True


def test_evaluate_for_project_blocks_on_own_p0_finding(store):
    own = Finding(
        title="own bug", description="touches proj_demo flow",
        discovered_by="evaluator", severity="P0",
        ticket_id="hg_proj_demo_abc",
    )
    store.create(own)
    rail = ReleaseRail(ontology=store)
    overrides = {item: True for item in RC_CHECKLIST}
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    assert out["checklist_results"]["no_p0_p1_findings"] is False
    assert "no_p0_p1_findings" in out["blockers"]


def test_evaluate_for_project_blocks_on_own_d3_undecided(store):
    f = Finding(
        title="design", description="proj_demo classification needed",
        discovered_by="x", severity="P2", d_level="D3",
        ticket_id="hg_proj_demo",
    )
    store.create(f)
    rail = ReleaseRail(ontology=store)
    overrides = {item: True for item in RC_CHECKLIST}
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    assert out["checklist_results"]["d3_findings_decided"] is False


# ---------------------------------------------------------------------------
# Self-audit — extras dict cannot smuggle canonical checklist values
# ---------------------------------------------------------------------------


def test_extras_cannot_override_canonical_checklist_via_overrides(store):
    rail = ReleaseRail(ontology=store)
    overrides = {
        "extras": {
            "no_p0_p1_findings": True,  # smuggle attempt
            "audit_chain_intact": True,
        },
    }
    out = rail.evaluate_for_project("proj_demo", overrides=overrides)
    # Canonical items default false; extras smuggling rejected.
    assert out["status"] == "blocked"


# ---------------------------------------------------------------------------
# Codex bug — pipeline.state_machine extended append-only with 3 new states
# ---------------------------------------------------------------------------


def test_state_machine_has_release_states():
    for s in ("release_candidate", "production_ready", "blocked_by_test"):
        assert s in STATES


def test_state_machine_existing_states_unchanged():
    """Append-only: legacy states remain in the original positions."""
    legacy = ("idle", "planning", "planned", "generating", "reviewing",
              "complete", "archived", "paused", "cancelled")
    for i, state in enumerate(legacy):
        assert STATES[i] == state


@pytest.mark.parametrize("from_state,to_state", [
    ("complete", "release_candidate"),
    ("release_candidate", "production_ready"),
    ("release_candidate", "blocked_by_test"),
    ("blocked_by_test", "release_candidate"),
])
def test_state_machine_release_transitions_present(from_state, to_state):
    assert to_state in ALLOWED_TRANSITIONS[from_state]


def test_state_machine_release_trigger_states_listed():
    assert "complete" in RELEASE_TRIGGER_STATES
    assert "release_candidate" in RELEASE_TRIGGER_STATES
    assert "blocked_by_test" in RELEASE_TRIGGER_STATES


def test_state_machine_legacy_complete_transitions_kept():
    """Adding release_candidate must not have dropped 'complete -> archived'."""
    assert "archived" in ALLOWED_TRANSITIONS["complete"]


def test_blocked_by_test_can_only_go_back_or_cancel():
    nexts = ALLOWED_TRANSITIONS["blocked_by_test"]
    assert nexts == {"release_candidate", "cancelled"}
