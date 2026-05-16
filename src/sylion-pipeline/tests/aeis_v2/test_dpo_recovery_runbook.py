"""Smoke test for the DPO Recovery Runbook.

Runs the documented step-by-step procedure (steps 1, 2, 3, 9.C, post-recovery
verification) against a synthesised violation. Keeps the runbook honest:
if a future audit_chain refactor breaks one of the runbook commands, this
test fires.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sylion.aeis_v2.audit_chain import (
    append_to_chain,
    invalidate_last_hash_cache,
    reset_last_hash_cache,
    verify_chain,
)


def test_runbook_doc_exists_and_carries_required_sections() -> None:
    """The runbook document must exist + cover every numbered section."""
    repo_root = Path(__file__).resolve().parents[3]
    runbook = repo_root / "docs" / "v2" / "operations" / "dpo_recovery_runbook.md"
    if not runbook.exists():
        # Fallback for repo layouts where parents[3] is sylion-pipeline/.
        repo_root = Path(__file__).resolve().parents[4]
        runbook = repo_root / "docs" / "v2" / "operations" / "dpo_recovery_runbook.md"
    assert runbook.exists(), "DPO runbook missing — sprint 3 E8 deliverable"
    text = runbook.read_text(encoding="utf-8")
    for section in (
        "## 1. Pre-flight checks",
        "## 2. Step-by-step procedure",
        "## 3. Decision tree",
        "## 4. Rollback triggers",
        "## 5. Stakeholder contacts",
        "## 6. Post-mortem template",
        "## 7. Reference: Tampered fault types",
    ):
        assert section in text, f"runbook missing section: {section}"


def test_runbook_step_1_capture_evidence(tmp_path: Path) -> None:
    """Step 1: copy the JSONL to an incident dir + sha256 the copy."""
    import hashlib
    import shutil

    reset_last_hash_cache()
    audit = tmp_path / "gdpr_dsr.jsonl"
    append_to_chain(audit, {"action": "access", "user_id": "u-1"})

    incident_dir = tmp_path / "incidents" / "audit-violation-001"
    incident_dir.mkdir(parents=True)
    snapshot = incident_dir / "gdpr_dsr.original.jsonl"
    shutil.copy2(audit, snapshot)

    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (incident_dir / "gdpr_dsr.sha256").write_text(digest)

    # The evidence snapshot must verify cleanly.
    assert verify_chain(snapshot) == []
    # Hash file present + non-empty.
    assert (incident_dir / "gdpr_dsr.sha256").read_text() == digest


def test_runbook_step_2_fault_report_json(tmp_path: Path) -> None:
    """Step 2: verify_chain returns structured Tampered entries we can JSON-dump."""
    audit = tmp_path / "x.jsonl"
    append_to_chain(audit, {"x": 1})
    # Tamper: append garbage.
    with open(audit, "a", encoding="utf-8") as f:
        f.write("not-json\n")

    faults = verify_chain(audit)
    assert faults  # non-empty
    # Every fault must JSON-serialise via to_dict (used by the CLI).
    payload = {"files": [{"name": audit.name, "faults": [
        f.to_dict() for f in faults
    ]}]}
    json.dumps(payload)


def test_runbook_step_3_first_fault_line_identification(tmp_path: Path) -> None:
    """Step 3: 'last clean line' = first_fault_line - 1."""
    audit = tmp_path / "x.jsonl"
    append_to_chain(audit, {"i": 1})
    append_to_chain(audit, {"i": 2})
    append_to_chain(audit, {"i": 3})
    # Tamper line 3 by appending garbage AFTER it.
    with open(audit, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    faults = verify_chain(audit)
    first_fault = min(f.line_no for f in faults)
    last_clean = first_fault - 1
    assert last_clean == 3  # 3 clean rows + 1 garbage line at 4


def test_runbook_step_9c_reconstruct_path(tmp_path: Path) -> None:
    """Step 9.C: truncate to last_clean_line, restore, verify rebuild.

    This is the recovery happy path: take a tampered chain, find the
    last clean row, truncate, swap in as the active chain, invalidate
    cache, confirm subsequent appends extend the recovered chain.
    """
    reset_last_hash_cache()
    audit = tmp_path / "gdpr_dsr.jsonl"
    append_to_chain(audit, {"a": 1})
    append_to_chain(audit, {"a": 2})
    append_to_chain(audit, {"a": 3})

    # Inject corruption at line 4.
    with open(audit, "a", encoding="utf-8") as f:
        f.write("not-json\n")

    # Step 3: identify last clean line.
    faults = verify_chain(audit)
    assert faults
    first_fault = min(f.line_no for f in faults)
    last_clean = first_fault - 1
    assert last_clean == 3

    # Step 9.C: truncate to last_clean.
    incident_dir = tmp_path / "incidents" / "x"
    incident_dir.mkdir(parents=True)
    recovered = incident_dir / "gdpr_dsr.recovered.jsonl"

    lines = audit.read_text(encoding="utf-8").splitlines()
    recovered.write_text("\n".join(lines[:last_clean]) + "\n", encoding="utf-8")

    # The recovered file must verify cleanly.
    assert verify_chain(recovered) == []

    # Step 9.C.4-5: restore as active + invalidate cache.
    audit.write_text(recovered.read_text(encoding="utf-8"), encoding="utf-8")
    invalidate_last_hash_cache(audit)

    # Step 9.C.6: subsequent emit extends the recovered chain.
    append_to_chain(audit, {"after_recovery": True})
    assert verify_chain(audit) == []


def test_runbook_cli_invocation_returns_machine_readable_json(
    tmp_path: Path,
) -> None:
    """Step 2 references `verify_audit_chains.py --json` — confirm contract."""
    import importlib.util

    repo_root = Path(__file__).resolve().parents[3]
    cli_path = repo_root / "scripts" / "v2" / "verify_audit_chains.py"
    if not cli_path.exists():
        cli_path = (
            Path(__file__).resolve().parents[4]
            / "scripts" / "v2" / "verify_audit_chains.py"
        )
    assert cli_path.exists()

    spec = importlib.util.spec_from_file_location("verify_audit_chains", cli_path)
    assert spec is not None and spec.loader is not None
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    # Stage a fault.
    p = tmp_path / "x.jsonl"
    append_to_chain(p, {"x": 1})
    with open(p, "a", encoding="utf-8") as f:
        f.write("garbage\n")

    # The CLI's own discover_chain_files + report_chain combo must yield
    # the same shape the runbook documents.
    files = cli.discover_chain_files(tmp_path)
    assert any(f.name == "x.jsonl" for f in files)
    clean, faults = cli.report_chain(p)
    assert clean is False
    assert all(hasattr(f, "to_dict") for f in faults)


def test_runbook_post_mortem_template_present() -> None:
    """The runbook's §6 carries the canonical post-mortem template."""
    repo_root = Path(__file__).resolve().parents[3]
    runbook = repo_root / "docs" / "v2" / "operations" / "dpo_recovery_runbook.md"
    if not runbook.exists():
        # Fallback for repo layouts where parents[3] is sylion-pipeline/.
        repo_root = Path(__file__).resolve().parents[4]
        runbook = repo_root / "docs" / "v2" / "operations" / "dpo_recovery_runbook.md"
    text = runbook.read_text(encoding="utf-8")
    # Required headings inside the post-mortem template block.
    for heading in (
        "## Summary",
        "## Timeline",
        "## Root cause",
        "## Blast radius",
        "## Action items",
    ):
        assert heading in text, f"post-mortem template missing: {heading}"
