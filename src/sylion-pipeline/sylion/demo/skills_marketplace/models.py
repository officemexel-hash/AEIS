"""Skills Marketplace domain — D5 supply-chain hardening."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

SKILL_STATUS = (
    "uploaded",        # raw upload, awaiting scan
    "scanning",        # static scan in progress
    "scan_failed",     # malicious findings
    "ready_for_review",
    "approved",
    "rejected",
    "deprecated",
)

# Per-skill execution budget (USD)
DEFAULT_SKILL_BUDGET_USD = 10.0
MAX_SKILL_BUDGET_USD = 100.0


@dataclass
class Skill:
    skill_id: str = field(default_factory=lambda: f"skill_{uuid.uuid4().hex[:12]}")
    name: str = ""
    version: str = "1.0.0"
    author_id: str = ""
    description: str = ""
    sha256: str = ""
    signature_pubkey: str = ""    # author's public key (signed package)
    status: str = "uploaded"
    cost_budget_usd: float = DEFAULT_SKILL_BUDGET_USD
    council_session_id: str | None = None  # required for approve (D5)
    created_at: float = field(default_factory=time.time)
    approved_at: float | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("name must be alphanumeric (with - or _)")
        if not self.author_id:
            raise ValueError("author_id required")
        if len(self.sha256) != 64:
            raise ValueError("sha256 must be 64-char hex")
        if not self.signature_pubkey or len(self.signature_pubkey) < 32:
            raise ValueError("signature_pubkey required (signed packages only)")
        if self.status not in SKILL_STATUS:
            raise ValueError(f"invalid status: {self.status}")
        if self.cost_budget_usd < 0:
            raise ValueError("cost_budget_usd must be non-negative")
        if self.cost_budget_usd > MAX_SKILL_BUDGET_USD:
            raise ValueError(
                f"cost_budget_usd exceeds hard cap: "
                f"{self.cost_budget_usd} > {MAX_SKILL_BUDGET_USD}"
            )


@dataclass
class SkillDependency:
    """Dependency declaration with EXACT name match (anti-typosquat)."""
    dep_id: str = field(default_factory=lambda: f"dep_{uuid.uuid4().hex[:12]}")
    skill_id: str = ""
    dep_name: str = ""           # exact registered name
    dep_version_pin: str = ""    # exact version, no ranges
    dep_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.dep_name:
            raise ValueError("dep_name required")
        if any(c in self.dep_version_pin for c in ("^", "~", ">", "<", "*")):
            raise ValueError(
                "dep_version_pin must be EXACT (no ranges allowed)"
            )
        if len(self.dep_sha256) != 64:
            raise ValueError(
                "dep_sha256 required (64 char hex) — verifies dependency"
            )


@dataclass
class SkillScanResult:
    """Static security scan output."""
    scan_id: str = field(default_factory=lambda: f"scan_{uuid.uuid4().hex[:12]}")
    skill_id: str = ""
    findings: list[dict] = field(default_factory=list)
    severity_max: str = "none"   # none, low, medium, high, critical
    scanned_at: float = field(default_factory=time.time)
    scanner_version: str = "1.0"


@dataclass
class SkillReview:
    review_id: str = field(default_factory=lambda: f"rev_{uuid.uuid4().hex[:12]}")
    skill_id: str = ""
    reviewer_id: str = ""
    decision: str = ""           # approve, reject, request_changes
    rationale: str = ""
    reviewed_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not self.reviewer_id:
            raise ValueError("reviewer_id required")
        if self.decision not in ("approve", "reject", "request_changes"):
            raise ValueError(f"invalid decision: {self.decision}")


__all__ = [
    "Skill", "SkillDependency", "SkillReview", "SkillScanResult",
    "SKILL_STATUS",
    "DEFAULT_SKILL_BUDGET_USD", "MAX_SKILL_BUDGET_USD",
]
