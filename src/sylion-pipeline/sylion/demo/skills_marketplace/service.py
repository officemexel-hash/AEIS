"""MarketplaceService — D5 supply-chain hardening."""
from __future__ import annotations

import logging
import time
from typing import Any

from sylion.demo.skills_marketplace.models import (
    Skill, SkillDependency, SkillReview, SkillScanResult,
    DEFAULT_SKILL_BUDGET_USD, MAX_SKILL_BUDGET_USD,
)
from sylion.demo.skills_marketplace.store import MarketplaceStore

log = logging.getLogger("sylion.demo.skills_marketplace.service")

# Severity levels that block publication
BLOCKING_SEVERITIES = ("high", "critical")


class MarketplaceService:
    def __init__(
        self, store: MarketplaceStore, event_bus: Any = None,
    ) -> None:
        self._store = store
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Upload (status: uploaded -> scanning -> ready_for_review)
    # ------------------------------------------------------------------

    def upload_skill(
        self, name: str, version: str, author_id: str,
        sha256: str, signature_pubkey: str,
        description: str = "",
        cost_budget_usd: float = DEFAULT_SKILL_BUDGET_USD,
    ) -> Skill:
        # Anti-typosquat: exact name uniqueness check at version
        existing = [s for s in self._store.find_by_name(name)
                    if s.version == version]
        if existing:
            raise ValueError(
                f"skill {name}@{version} already published "
                f"(exact name + version match)"
            )
        s = Skill(
            name=name, version=version, author_id=author_id,
            sha256=sha256, signature_pubkey=signature_pubkey,
            description=description,
            cost_budget_usd=cost_budget_usd,
            status="uploaded",
        )
        return self._store.create_skill(s)

    def declare_dependency(
        self, skill_id: str, dep_name: str,
        dep_version_pin: str, dep_sha256: str,
    ) -> SkillDependency:
        """Declare a dependency. Anti-typosquat: dep_name must EXACTLY
        match a known marketplace skill (or be in allowlist for stdlib).
        """
        if self._store.get_skill(skill_id) is None:
            raise ValueError(f"skill not found: {skill_id}")
        # If dep_name exists as a different skill in marketplace,
        # ensure it matches exactly (no typosquat)
        candidates = self._store.find_by_name(dep_name)
        if not candidates:
            # Allow non-marketplace deps but warn — real impl would
            # check against an allowlist of trusted external packages
            log.warning("dep '%s' not in marketplace registry", dep_name)
        d = SkillDependency(
            skill_id=skill_id, dep_name=dep_name,
            dep_version_pin=dep_version_pin, dep_sha256=dep_sha256,
        )
        return self._store.add_dependency(d)

    # ------------------------------------------------------------------
    # Static scan (D5 mandatory)
    # ------------------------------------------------------------------

    def run_static_scan(
        self, skill_id: str, findings: list[dict] | None = None,
    ) -> SkillScanResult:
        """Run static security scan. Findings are caller-provided in this
        demo (real impl would integrate with sast tool).
        """
        s = self._store.get_skill(skill_id)
        if s is None:
            raise ValueError(f"skill not found: {skill_id}")
        self._store.update_skill_status(skill_id, "scanning")
        findings = findings or []
        severity_max = "none"
        for f in findings:
            sev = f.get("severity", "low")
            order = ("none", "low", "medium", "high", "critical")
            if order.index(sev) > order.index(severity_max):
                severity_max = sev
        scan = SkillScanResult(
            skill_id=skill_id, findings=findings, severity_max=severity_max,
        )
        self._store.add_scan(scan)
        # Auto-fail if blocking severity
        if severity_max in BLOCKING_SEVERITIES:
            self._store.update_skill_status(skill_id, "scan_failed")
        else:
            self._store.update_skill_status(skill_id, "ready_for_review")
        return scan

    # ------------------------------------------------------------------
    # Review + approve (D5: Council session required)
    # ------------------------------------------------------------------

    def submit_review(
        self, skill_id: str, reviewer_id: str,
        decision: str, rationale: str = "",
    ) -> SkillReview:
        s = self._store.get_skill(skill_id)
        if s is None:
            raise ValueError(f"skill not found: {skill_id}")
        if s.status not in ("ready_for_review", "approved"):
            raise ValueError(
                f"cannot review skill in status {s.status}"
            )
        r = SkillReview(
            skill_id=skill_id, reviewer_id=reviewer_id,
            decision=decision, rationale=rationale,
        )
        return self._store.add_review(r)

    def approve_skill(
        self, skill_id: str, council_session_id: str,
    ) -> Skill:
        """D5 approval — Council session REQUIRED."""
        if not council_session_id:
            raise PermissionError(
                "skill approval REQUIRES council_session_id (D5)"
            )
        s = self._store.get_skill(skill_id)
        if s is None:
            raise ValueError(f"skill not found: {skill_id}")
        if s.status != "ready_for_review":
            raise ValueError(
                f"cannot approve skill in status {s.status}"
            )
        # Check latest scan didn't have blocking findings
        scan = self._store.get_latest_scan(skill_id)
        if scan is None or scan.severity_max in BLOCKING_SEVERITIES:
            raise ValueError(
                "cannot approve: scan missing or has blocking findings"
            )
        self._store.update_skill_status(
            skill_id, "approved",
            council_session_id=council_session_id,
            approved_at=time.time(),
        )
        return self._store.get_skill(skill_id)

    # ------------------------------------------------------------------
    # Cost guard (per-execution check)
    # ------------------------------------------------------------------

    def can_execute(
        self, skill_id: str, projected_cost_usd: float,
    ) -> dict:
        """Pre-execution budget check (runaway cost guard)."""
        s = self._store.get_skill(skill_id)
        if s is None:
            return {"allowed": False, "reason": "skill not found"}
        if s.status != "approved":
            return {"allowed": False,
                    "reason": f"skill not approved (status={s.status})"}
        if projected_cost_usd > s.cost_budget_usd:
            return {
                "allowed": False,
                "reason": (
                    f"RUNAWAY COST: projected {projected_cost_usd:.2f} > "
                    f"budget {s.cost_budget_usd:.2f}"
                ),
            }
        return {"allowed": True, "reason": None}


__all__ = ["MarketplaceService", "BLOCKING_SEVERITIES"]
