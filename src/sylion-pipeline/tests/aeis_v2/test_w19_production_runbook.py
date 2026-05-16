"""Smoke test for the W19 production runbook.

Mirrors the DPO recovery runbook smoke test pattern (commit dffaa4fc):
keeps the runbook honest by locking every numbered section + every
documented command stays callable as the W19 surface evolves.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def _runbook_path() -> Path:
    """Resolve the runbook path tolerating both repo layouts."""
    p = (
        Path(__file__).resolve().parents[3]
        / "docs" / "v2" / "operations" / "w19_production_runbook.md"
    )
    if not p.exists():
        p = (
            Path(__file__).resolve().parents[4]
            / "docs" / "v2" / "operations" / "w19_production_runbook.md"
        )
    return p


def test_runbook_exists() -> None:
    assert _runbook_path().exists(), "W19 production runbook missing"


def test_runbook_has_required_sections() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    for header in (
        "## 1. Pre-deploy checklist",
        "## 2. ADR-003 sign-off workflow",
        "## 3. Canary dial procedure",
        "## 4. Observability gates",
        "## 5. Rollback triggers",
        "## 6. Incident response",
        "## 7. DPO involvement criteria",
        "## 8. Council split-brain procedure",
        "## 9. jinja2 CVE response",
        "## 10. Policy template version migration",
        "## 11. Operator UI walkthrough",
    ):
        assert header in text, f"missing section: {header}"


def test_runbook_documents_kill_switch() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    assert "SYLION_W19_EVALUATOR_DISABLED=1" in text
    assert "kill switch" in text.lower()


def test_runbook_documents_canary_stages() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    for stage in ("0 → 1%", "1 → 5%", "5 → 25%", "25 → 50%", "50 → 100%"):
        assert stage in text, f"runbook missing canary stage: {stage}"


def test_runbook_references_council_vote_dispatcher() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    assert "scripts/v2/run_w19_adr003_council_vote.py" in text
    assert "--apply" in text
    assert "--dry-run" in text or "dry-run" in text.lower()


def test_runbook_references_audit_chain_monitor() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    assert "audit_chain_monitor" in text
    assert "verify_audit_chains.py" in text


def test_runbook_references_dpo_runbook() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    assert "dpo_recovery_runbook" in text


def test_runbook_documents_rollback_triggers() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    for trigger in (
        "Deny rate",
        "p95 render",
        "Audit chain violation",
        "Sandbox escape",
    ):
        assert trigger in text, f"missing rollback trigger: {trigger}"


def test_runbook_documents_metric_names() -> None:
    text = _runbook_path().read_text(encoding="utf-8")
    for metric in (
        "sylion_v2_audit_chain_size",
        "sylion_v2_audit_chain_violations_total",
        "adapter_bus_circuit_state",
        "adapter_bus_dispatch_total",
    ):
        assert metric in text, f"runbook missing metric: {metric}"


def test_runbook_exit_criteria_complete() -> None:
    """Production complete checklist must enumerate the 6 criteria."""
    text = _runbook_path().read_text(encoding="utf-8")
    assert "PRODUCTION COMPLETE" in text
    # 6 numbered criteria.
    for i in range(1, 7):
        assert f"\n{i}. " in text, f"missing criterion #{i}"
