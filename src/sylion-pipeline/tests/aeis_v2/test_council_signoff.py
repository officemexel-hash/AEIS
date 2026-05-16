"""Tests for ``sylion.aeis_v2.governance_v2.adr_signoff`` + the
Council Hybrid sign-off REST route.

Sprint 3 A1 deliverable — unblocks ADR-003 (W19 evaluator) by giving
Council Hybrid a way to flip a PROPOSED ADR to ACCEPTED with all the
expected gates: 9 votes per canonical role, critic signature match,
majority approve.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sylion.aeis_v2.audit_chain import verify_chain
from sylion.aeis_v2.governance_v2 import (
    AdrSignoffRequest,
    AdrSignoffResult,
    AdrVote,
    apply_signoff,
    compute_adr_signature,
    evaluate_signoff,
    load_adr_status,
    set_adr_status,
)
from sylion.governance.council_hybrid import VALID_ROLES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_PROPOSED_BODY = """\
# ADR-XYZ test

> **Status**: PROPOSED
> **Date**: 2026-04-28

## 1. Cel
Body content.
"""


@pytest.fixture
def adr_dir(tmp_path: Path) -> Path:
    """Return a tmp dir holding a single PROPOSED ADR file."""
    p = tmp_path / "ADR-001-test.md"
    p.write_text(_PROPOSED_BODY, encoding="utf-8")
    return tmp_path


@pytest.fixture
def adr_path(adr_dir: Path) -> Path:
    return adr_dir / "ADR-001-test.md"


def _all_approve_votes() -> list[AdrVote]:
    return [
        AdrVote(role=r, verdict="approve", confidence=0.85, rationale="ok")
        for r in VALID_ROLES
    ]


def _signoff_audit_to_tmp(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Redirect the module-level audit log path to a tmp file."""
    import sylion.aeis_v2.governance_v2.adr_signoff as mod

    audit = tmp_path / "adr_signoff.jsonl"
    monkeypatch.setattr(mod, "SIGNOFF_AUDIT_LOG_PATH", audit)
    return audit


# ---------------------------------------------------------------------------
# compute_adr_signature
# ---------------------------------------------------------------------------


def test_compute_signature_matches_sha256(adr_path: Path) -> None:
    expected = hashlib.sha256(adr_path.read_bytes()).hexdigest()
    assert compute_adr_signature(adr_path) == expected


def test_compute_signature_missing_file_returns_empty(tmp_path: Path) -> None:
    assert compute_adr_signature(tmp_path / "nope.md") == ""


# ---------------------------------------------------------------------------
# load_adr_status / set_adr_status
# ---------------------------------------------------------------------------


def test_load_status_reads_proposed(adr_path: Path) -> None:
    assert load_adr_status(adr_path) == "PROPOSED"


def test_load_status_missing_file_returns_none(tmp_path: Path) -> None:
    assert load_adr_status(tmp_path / "absent.md") is None


def test_load_status_no_status_line_returns_none(tmp_path: Path) -> None:
    p = tmp_path / "x.md"
    p.write_text("# Doc with no Status line\n")
    assert load_adr_status(p) is None


def test_set_status_flips_proposed_to_accepted(adr_path: Path) -> None:
    assert set_adr_status(adr_path, "ACCEPTED") is True
    assert load_adr_status(adr_path) == "ACCEPTED"


def test_set_status_no_change_when_same(adr_path: Path) -> None:
    """Idempotency: setting the same status returns False (no write)."""
    assert set_adr_status(adr_path, "PROPOSED") is False


def test_set_status_missing_file_returns_false(tmp_path: Path) -> None:
    assert set_adr_status(tmp_path / "nope.md", "ACCEPTED") is False


# ---------------------------------------------------------------------------
# evaluate_signoff — pure validation pipeline
# ---------------------------------------------------------------------------


def test_evaluate_happy_path() -> None:
    req = AdrSignoffRequest(
        adr_id="ADR-001-test.md",
        votes=_all_approve_votes(),
        critic_signature="abc123",
    )
    status, _detail = evaluate_signoff(
        req, expected_signature="abc123", current_status="PROPOSED",
    )
    assert status == "ok"


def test_evaluate_rejects_wrong_status() -> None:
    req = AdrSignoffRequest(
        adr_id="x.md",
        votes=_all_approve_votes(),
        critic_signature="abc",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc", current_status="ACCEPTED",
    )
    assert status == "wrong_status"


def test_evaluate_rejects_adr_not_found() -> None:
    req = AdrSignoffRequest(
        adr_id="x.md",
        votes=_all_approve_votes(),
        critic_signature="abc",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc", current_status=None,
    )
    assert status == "adr_not_found"


def test_evaluate_rejects_too_few_votes() -> None:
    req = AdrSignoffRequest(
        adr_id="x.md",
        votes=_all_approve_votes()[:8],
        critic_signature="abc",
    )
    status, detail = evaluate_signoff(
        req, expected_signature="abc", current_status="PROPOSED",
    )
    assert status == "missing_votes"
    assert "8" in detail


def test_evaluate_rejects_duplicate_role() -> None:
    votes = _all_approve_votes()
    votes[1] = AdrVote(role="planner", verdict="approve")  # duplicate planner
    req = AdrSignoffRequest(
        adr_id="x.md", votes=votes, critic_signature="abc",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc", current_status="PROPOSED",
    )
    assert status == "missing_votes"


def test_evaluate_rejects_invalid_verdict() -> None:
    votes = _all_approve_votes()
    votes[0] = AdrVote(role="planner", verdict="banana")
    req = AdrSignoffRequest(
        adr_id="x.md", votes=votes, critic_signature="abc",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc", current_status="PROPOSED",
    )
    assert status == "missing_votes"


def test_evaluate_rejects_signature_mismatch() -> None:
    req = AdrSignoffRequest(
        adr_id="x.md",
        votes=_all_approve_votes(),
        critic_signature="aaa111",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="bbb222", current_status="PROPOSED",
    )
    assert status == "critic_signature_mismatch"


def test_evaluate_signature_match_case_insensitive() -> None:
    req = AdrSignoffRequest(
        adr_id="x.md",
        votes=_all_approve_votes(),
        critic_signature="ABC123",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc123", current_status="PROPOSED",
    )
    assert status == "ok"


def test_evaluate_rejects_no_majority_approve() -> None:
    votes = [
        AdrVote(role=r, verdict="reject")
        for r in VALID_ROLES[:5]
    ] + [
        AdrVote(role=r, verdict="approve")
        for r in VALID_ROLES[5:]
    ]
    req = AdrSignoffRequest(
        adr_id="x.md", votes=votes, critic_signature="abc",
    )
    status, _ = evaluate_signoff(
        req, expected_signature="abc", current_status="PROPOSED",
    )
    assert status == "no_majority_approve"


# ---------------------------------------------------------------------------
# apply_signoff — full pipeline
# ---------------------------------------------------------------------------


def test_apply_happy_path_flips_status(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _signoff_audit_to_tmp(monkeypatch, tmp_path)
    adr_path = adr_dir / "ADR-001-test.md"
    sig = compute_adr_signature(adr_path)

    req = AdrSignoffRequest(
        adr_id="ADR-001-test.md",
        votes=_all_approve_votes(),
        critic_signature=sig,
        actor="owner",
    )
    result = apply_signoff(req, decisions_dir=adr_dir)

    assert isinstance(result, AdrSignoffResult)
    assert result.status == "ok"
    assert result.gate_passed is True
    assert result.new_status == "ACCEPTED"
    assert result.approve_count == 9
    # File on disk reflects the flip.
    assert load_adr_status(adr_path) == "ACCEPTED"


def test_apply_rejects_when_signature_stale(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """TOCTOU mitigation — file changed after request crafted."""
    _signoff_audit_to_tmp(monkeypatch, tmp_path)
    adr_path = adr_dir / "ADR-001-test.md"
    stale_sig = compute_adr_signature(adr_path)

    # Mutate the file between request craft and apply.
    adr_path.write_text(
        adr_path.read_text(encoding="utf-8") + "\n\n## EXTRA\n", encoding="utf-8",
    )

    req = AdrSignoffRequest(
        adr_id="ADR-001-test.md",
        votes=_all_approve_votes(),
        critic_signature=stale_sig,
        actor="owner",
    )
    result = apply_signoff(req, decisions_dir=adr_dir)
    assert result.status == "critic_signature_mismatch"
    # File stays PROPOSED.
    assert load_adr_status(adr_path) == "PROPOSED"


def test_apply_supports_adr_id_with_md_suffix(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Caller can pass adr_id with or without .md suffix — we resolve both."""
    _signoff_audit_to_tmp(monkeypatch, tmp_path)
    adr_path = adr_dir / "ADR-001-test.md"
    sig = compute_adr_signature(adr_path)

    req = AdrSignoffRequest(
        adr_id="ADR-001-test",  # without .md
        votes=_all_approve_votes(),
        critic_signature=sig,
        actor="owner",
    )
    result = apply_signoff(req, decisions_dir=adr_dir)
    assert result.gate_passed is True


def test_apply_emits_chained_audit(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    audit = _signoff_audit_to_tmp(monkeypatch, tmp_path)
    adr_path = adr_dir / "ADR-001-test.md"
    sig = compute_adr_signature(adr_path)
    req = AdrSignoffRequest(
        adr_id="ADR-001-test.md",
        votes=_all_approve_votes(),
        critic_signature=sig,
        actor="owner",
    )
    apply_signoff(req, decisions_dir=adr_dir)
    assert audit.exists()
    assert verify_chain(audit) == []
    contents = [
        json.loads(l)["content"]
        for l in audit.read_text(encoding="utf-8").splitlines() if l
    ]
    assert any(c.get("kind") == "adr_signoff.attempt" for c in contents)
    # Critic signature MUST NOT appear in the audit row (Kimi k3 finding).
    audit_blob = json.dumps(contents)
    assert sig not in audit_blob


def test_apply_does_not_flip_when_validation_fails(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _signoff_audit_to_tmp(monkeypatch, tmp_path)
    adr_path = adr_dir / "ADR-001-test.md"
    req = AdrSignoffRequest(
        adr_id="ADR-001-test.md",
        votes=_all_approve_votes()[:8],  # missing one
        critic_signature=compute_adr_signature(adr_path),
        actor="owner",
    )
    result = apply_signoff(req, decisions_dir=adr_dir)
    assert result.gate_passed is False
    # File stays PROPOSED.
    assert load_adr_status(adr_path) == "PROPOSED"


# ---------------------------------------------------------------------------
# REST endpoint
# ---------------------------------------------------------------------------


def test_endpoint_signoff_happy_path(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    _signoff_audit_to_tmp(monkeypatch, tmp_path)

    import sylion.api.council_signoff_routes as mod

    monkeypatch.setattr(mod, "_decisions_dir", lambda: adr_dir)

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    sig = compute_adr_signature(adr_dir / "ADR-001-test.md")
    body = {
        "votes": [
            {"role": r, "verdict": "approve", "confidence": 0.9}
            for r in VALID_ROLES
        ],
        "critic_signature": sig,
    }
    resp = client.post("/api/v1/council/sign-off-adr/ADR-001-test.md", json=body)
    assert resp.status_code == 200
    out = resp.json()
    assert out["gate_passed"] is True
    assert out["new_status"] == "ACCEPTED"


def test_endpoint_signoff_422_on_signature_mismatch(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    _signoff_audit_to_tmp(monkeypatch, tmp_path)

    import sylion.api.council_signoff_routes as mod

    monkeypatch.setattr(mod, "_decisions_dir", lambda: adr_dir)

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    body = {
        "votes": [
            {"role": r, "verdict": "approve"} for r in VALID_ROLES
        ],
        "critic_signature": "0" * 64,  # bogus
    }
    resp = client.post("/api/v1/council/sign-off-adr/ADR-001-test.md", json=body)
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert detail["error"] == "critic_signature_mismatch"


def test_endpoint_signoff_422_on_too_few_votes(
    adr_dir: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Pydantic min_length=9 rejects sub-9 votes at the framework layer."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SYLION_RBAC_DISABLED", "1")
    _signoff_audit_to_tmp(monkeypatch, tmp_path)

    import sylion.api.council_signoff_routes as mod

    monkeypatch.setattr(mod, "_decisions_dir", lambda: adr_dir)

    app = FastAPI()
    app.include_router(mod.router)
    client = TestClient(app)

    body = {
        "votes": [
            {"role": "planner", "verdict": "approve"},
        ],
        "critic_signature": "x" * 16,
    }
    resp = client.post("/api/v1/council/sign-off-adr/ADR-001-test.md", json=body)
    assert resp.status_code == 422
