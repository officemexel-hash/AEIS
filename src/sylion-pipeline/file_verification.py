#!/usr/bin/env python3
"""
SYLION File Verification Layer — SHA-256 Anti-Hallucination Guard
=================================================================

Phase 0.1 of the Consolidated Plan: hard detection of hallucinated changes
and artifact drift.  ONE FILE — drop into sylion-pipeline/ and run.

Contains:
  PART 1 — Core verification engine   (FileVerificationLayer)
  PART 2 — Pipeline integration bridge (HallucinationGuard)
  PART 3 — Unit tests                  (17 tests, 4 groups)
  PART 4 — End-to-end test            (CHANGELOG-v3.4.13 scenario)
  PART 5 — CLI runner                  (python file_verification.py)

Architecture:
  Before agent → snapshot all declared files (SHA-256 + size + mtime)
  Agent runs   → produces claims ("I fixed handler.go")
  After agent  → re-hash files → compare SHA before/after vs claims
  Mismatch     → HALLUCINATION → block + escalate to Human Gate (CRITICAL)

Detects 6 hallucination types:
  1. NO_ACTUAL_CHANGE    — agent claims "fixed" but SHA unchanged
  2. PHANTOM_FILE        — agent references non-existent file
  3. FILE_NOT_IN_SNAPSHOT — agent modifies file outside declared scope
  4. UNEXPECTED_DELETION — file gone without delete claim
  5. UNEXPECTED_CREATION — file appeared without create claim
  6. SIZE_MISMATCH       — reserved for future granularity

Integration points:
  - LoopGuard  (loop_guard.py)      → IterationRecord enrichment
  - Supervisor (supervisor.py)      → GateLevel.CRITICAL escalation
  - HumanGateUX (human_gate_ux.py) → ConsequenceDescriptor display
  - ContextPersistence              → EventType.AUDIT_FINDING logging

Usage in orchestrator.py:

    from file_verification import (
        FileVerificationLayer, HallucinationGuard, AgentClaim, ClaimAction,
    )

    file_layer = FileVerificationLayer(repo_root=cfg.workspace)
    halluc_guard = HallucinationGuard(
        file_layer=file_layer,
        loop_guard=loop_guard,
        human_gate=human_gate,
        audit_log_path=results_dir / "hallucinations.jsonl",
    )

    # Before agent:
    ctx = halluc_guard.before_iteration(agent_id, declared_files)
    # Agent runs...
    # After agent:
    claims = parse_agent_claims(conv.state.events)
    result = halluc_guard.after_iteration(agent_id, claims, ctx)
    if result.blocked:
        handle_blocked_agent(agent_id, result)

Run tests:
    python file_verification.py          # all tests
    python file_verification.py --e2e    # only e2e scenario
    python file_verification.py --unit   # only unit tests
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import unittest
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger("file_verification")

# Buffer size for reading files (64 KB chunks)
_HASH_BUF_SIZE = 65536


# ═══════════════════════════════════════════════════════════════════════════
# PART 1: CORE VERIFICATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ClaimAction(str, enum.Enum):
    """What the agent claims it did to a file."""
    MODIFIED = "modified"
    FIXED    = "fixed"
    CREATED  = "created"
    DELETED  = "deleted"
    NOOP     = "noop"


class HallucinationType(str, enum.Enum):
    """Categories of detected hallucinations."""
    NO_ACTUAL_CHANGE     = "no_actual_change"
    PHANTOM_FILE         = "phantom_file"
    FILE_NOT_IN_SNAPSHOT = "file_not_in_snapshot"
    UNEXPECTED_DELETION  = "unexpected_deletion"
    UNEXPECTED_CREATION  = "unexpected_creation"
    SIZE_MISMATCH        = "size_mismatch"


class Verdict(str, enum.Enum):
    """Overall verification verdict."""
    VERIFIED      = "verified"
    HALLUCINATION = "hallucination"
    PARTIAL       = "partial"
    NO_CLAIMS     = "no_claims"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileSnapshot:
    """SHA-256 snapshot of a single file at a point in time."""
    file_path: str
    sha256: str
    size_bytes: int
    mtime: float
    exists: bool = True
    snapshot_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mtime": self.mtime,
            "exists": self.exists,
            "snapshot_time": self.snapshot_time.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FileSnapshot:
        d = dict(d)
        d["snapshot_time"] = datetime.fromisoformat(d["snapshot_time"])
        return cls(**d)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileSnapshot):
            return NotImplemented
        return self.sha256 == other.sha256 and self.exists == other.exists


@dataclass
class AgentClaim:
    """A single claim made by an agent about a file action."""
    file_path: str
    action: ClaimAction
    description: str = ""
    finding_id: str | None = None
    agent_id: str = ""
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "action": self.action.value,
            "description": self.description,
            "finding_id": self.finding_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentClaim:
        d = dict(d)
        d["action"] = ClaimAction(d["action"])
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)


@dataclass
class Hallucination:
    """A single detected hallucination — mismatch between claim and reality."""
    hallucination_type: HallucinationType
    file_path: str
    agent_id: str
    description: str
    claim: AgentClaim | None = None
    sha_before: str | None = None
    sha_after: str | None = None
    severity: str = "critical"
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hallucination_type": self.hallucination_type.value,
            "file_path": self.file_path,
            "agent_id": self.agent_id,
            "description": self.description,
            "claim": self.claim.to_dict() if self.claim else None,
            "sha_before": self.sha_before,
            "sha_after": self.sha_after,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class VerificationResult:
    """Complete result of file verification after an agent iteration."""
    agent_id: str
    verdict: Verdict
    claims_total: int
    claims_verified: int
    claims_failed: int
    hallucinations: list[Hallucination] = field(default_factory=list)
    files_before: dict[str, FileSnapshot] = field(default_factory=dict)
    files_after: dict[str, FileSnapshot] = field(default_factory=dict)
    duration_ms: float = 0.0
    blocked: bool = False
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def hallucination_count(self) -> int:
        return len(self.hallucinations)

    @property
    def is_clean(self) -> bool:
        return self.verdict in (Verdict.VERIFIED, Verdict.NO_CLAIMS)

    def summary(self) -> str:
        if self.is_clean:
            return (
                f"[VERIFIED] agent={self.agent_id}: "
                f"{self.claims_verified}/{self.claims_total} claims OK"
            )
        return (
            f"[{self.verdict.value.upper()}] agent={self.agent_id}: "
            f"{self.hallucination_count} hallucination(s) detected, "
            f"{self.claims_verified}/{self.claims_total} claims verified"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "verdict": self.verdict.value,
            "claims_total": self.claims_total,
            "claims_verified": self.claims_verified,
            "claims_failed": self.claims_failed,
            "hallucination_count": self.hallucination_count,
            "hallucinations": [h.to_dict() for h in self.hallucinations],
            "blocked": self.blocked,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# Core: FileVerificationLayer
# ---------------------------------------------------------------------------

class FileVerificationLayer:
    """Core verification engine — snapshots files and detects hallucinations.

    Usage:
        layer = FileVerificationLayer(repo_root=Path("/path/to/sylion"))
        snapshots = layer.snapshot_files(["handler.go", "utils.go"])
        # agent runs ...
        claims = [AgentClaim(file_path="handler.go", action=ClaimAction.FIXED)]
        result = layer.verify_changes("programmer_go_1", claims, snapshots)
        if result.blocked:
            ...  # escalate
    """

    def __init__(
        self,
        repo_root: Path,
        fail_closed: bool = True,
        log_dir: Path | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.fail_closed = fail_closed
        self.log_dir = log_dir or (self.repo_root / "results" / "verification")
        self._history: list[VerificationResult] = []

        logger.info(
            "FileVerificationLayer initialized — repo=%s fail_closed=%s",
            self.repo_root, self.fail_closed,
        )

    # ------------------------------------------------------------------
    # SHA-256 hashing
    # ------------------------------------------------------------------

    @staticmethod
    def sha256_file(path: Path) -> str:
        """Compute SHA-256 hash of a file in 64KB chunks."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(_HASH_BUF_SIZE)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        """Compute SHA-256 hash of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    # ------------------------------------------------------------------
    # Snapshotting
    # ------------------------------------------------------------------

    def snapshot_file(self, rel_path: str) -> FileSnapshot:
        """Take SHA-256 snapshot of a single file relative to repo_root."""
        # Security: reject absolute paths and path traversal (v5.8.5 fix)
        if os.path.isabs(rel_path) or '..' in rel_path.split(os.sep):
            logger.warning("Path traversal attempt rejected: %s", rel_path)
            return FileSnapshot(
                file_path=rel_path, sha256="",
                size_bytes=0, mtime=0.0, exists=False,
            )
        abs_path = (self.repo_root / rel_path).resolve()
        # Ensure resolved path is within repo_root
        if not str(abs_path).startswith(str(self.repo_root.resolve())):
            logger.warning("Path escape rejected: %s -> %s", rel_path, abs_path)
            return FileSnapshot(
                file_path=rel_path, sha256="",
                size_bytes=0, mtime=0.0, exists=False,
            )
        abs_path = self.repo_root / rel_path
        if not abs_path.exists() or not abs_path.is_file():
            return FileSnapshot(
                file_path=rel_path, sha256="",
                size_bytes=0, mtime=0.0, exists=False,
            )
        stat = abs_path.stat()
        return FileSnapshot(
            file_path=rel_path,
            sha256=self.sha256_file(abs_path),
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
            exists=True,
        )

    def snapshot_files(self, rel_paths: list[str]) -> dict[str, FileSnapshot]:
        """Take snapshots of multiple files."""
        return {rp: self.snapshot_file(rp) for rp in rel_paths}

    def snapshot_directory(
        self,
        rel_dir: str = ".",
        extensions: set[str] | None = None,
        max_files: int = 500,
    ) -> dict[str, FileSnapshot]:
        """Snapshot all files in a directory (broad monitoring)."""
        abs_dir = self.repo_root / rel_dir
        if not abs_dir.is_dir():
            return {}
        snapshots: dict[str, FileSnapshot] = {}
        count = 0
        for root, _dirs, files in os.walk(abs_dir):
            for fname in files:
                if count >= max_files:
                    return snapshots
                abs_file = Path(root) / fname
                if extensions and abs_file.suffix not in extensions:
                    continue
                rel = str(abs_file.relative_to(self.repo_root))
                snapshots[rel] = self.snapshot_file(rel)
                count += 1
        return snapshots

    # ------------------------------------------------------------------
    # Verification — core logic
    # ------------------------------------------------------------------

    def verify_changes(
        self,
        agent_id: str,
        claims: list[AgentClaim],
        snapshots_before: dict[str, FileSnapshot],
        additional_watch_paths: list[str] | None = None,
    ) -> VerificationResult:
        """Verify agent claims against actual file changes.

        Main entry point after an agent iteration.
        """
        t_start = time.monotonic()
        hallucinations: list[Hallucination] = []
        verified_count = 0

        # 1. Re-snapshot all files
        all_paths = set(snapshots_before.keys())
        for claim in claims:
            all_paths.add(claim.file_path)
        if additional_watch_paths:
            all_paths.update(additional_watch_paths)
        snapshots_after = self.snapshot_files(list(all_paths))

        # 2. Check each claim
        for claim in claims:
            fp = claim.file_path
            before = snapshots_before.get(fp)
            after = snapshots_after.get(fp)

            check_fn = {
                ClaimAction.MODIFIED: self._check_modification_claim,
                ClaimAction.FIXED:    self._check_modification_claim,
                ClaimAction.CREATED:  self._check_creation_claim,
                ClaimAction.DELETED:  self._check_deletion_claim,
                ClaimAction.NOOP:     self._check_noop_claim,
            }[claim.action]

            halluc = check_fn(agent_id, claim, before, after)
            if halluc:
                hallucinations.append(halluc)
            else:
                verified_count += 1

        # 3. Detect undeclared modifications
        claimed_paths = {c.file_path for c in claims}
        for fp, snap_before in snapshots_before.items():
            if fp in claimed_paths:
                continue
            snap_after = snapshots_after.get(fp)
            if snap_after and snap_before.exists and snap_after.exists:
                if snap_before.sha256 != snap_after.sha256:
                    hallucinations.append(Hallucination(
                        hallucination_type=HallucinationType.FILE_NOT_IN_SNAPSHOT,
                        file_path=fp, agent_id=agent_id,
                        description=(
                            f"File '{fp}' changed (SHA differs) but agent "
                            f"made no claim about it. Undeclared modification."
                        ),
                        sha_before=snap_before.sha256,
                        sha_after=snap_after.sha256,
                    ))
            elif snap_before.exists and (not snap_after or not snap_after.exists):
                hallucinations.append(Hallucination(
                    hallucination_type=HallucinationType.UNEXPECTED_DELETION,
                    file_path=fp, agent_id=agent_id,
                    description=(
                        f"File '{fp}' was deleted but agent made no "
                        f"delete claim. Unexpected deletion."
                    ),
                    sha_before=snap_before.sha256, sha_after=None,
                ))

        # 4. Detect undeclared creations
        for fp, snap_after in snapshots_after.items():
            if fp in claimed_paths:
                continue
            snap_before = snapshots_before.get(fp)
            if snap_after.exists and (not snap_before or not snap_before.exists):
                hallucinations.append(Hallucination(
                    hallucination_type=HallucinationType.UNEXPECTED_CREATION,
                    file_path=fp, agent_id=agent_id,
                    description=(
                        f"File '{fp}' was created but agent made no "
                        f"create claim. Unexpected creation."
                    ),
                    sha_before=None, sha_after=snap_after.sha256,
                ))

        # 5-a. Detect undeclared size changes (GAP-02: SIZE_MISMATCH)
        _SIZE_MISMATCH_THRESHOLD = 0.10  # 10% change triggers flag
        for fp, snap_before in snapshots_before.items():
            if fp in claimed_paths:
                continue
            snap_after = snapshots_after.get(fp)
            if not snap_after or not snap_before.exists or not snap_after.exists:
                continue
            sz_before = snap_before.size_bytes
            sz_after = snap_after.size_bytes
            if sz_before == 0:
                continue
            ratio = abs(sz_after - sz_before) / sz_before
            if ratio > _SIZE_MISMATCH_THRESHOLD:
                hallucinations.append(Hallucination(
                    hallucination_type=HallucinationType.SIZE_MISMATCH,
                    file_path=fp, agent_id=agent_id,
                    description=(
                        f"File '{fp}' size changed from {sz_before}B to {sz_after}B "
                        f"({ratio * 100:.1f}% delta) without a MODIFIED claim."
                    ),
                    sha_before=snap_before.sha256,
                    sha_after=snap_after.sha256,
                ))

        # 5. Build result
        t_elapsed = (time.monotonic() - t_start) * 1000
        if not claims:
            verdict = Verdict.NO_CLAIMS
        elif not hallucinations:
            verdict = Verdict.VERIFIED
        elif verified_count > 0:
            verdict = Verdict.PARTIAL
        else:
            verdict = Verdict.HALLUCINATION

        blocked = bool(hallucinations) and self.fail_closed

        result = VerificationResult(
            agent_id=agent_id, verdict=verdict,
            claims_total=len(claims), claims_verified=verified_count,
            claims_failed=len(hallucinations),
            hallucinations=hallucinations,
            files_before=snapshots_before, files_after=snapshots_after,
            duration_ms=t_elapsed, blocked=blocked,
        )

        self._history.append(result)
        self._write_audit_log(result)

        if hallucinations:
            logger.warning(
                "HALLUCINATION DETECTED — agent=%s verdict=%s count=%d blocked=%s",
                agent_id, verdict.value, len(hallucinations), blocked,
            )
        else:
            logger.info(
                "Verification OK — agent=%s claims=%d verified=%d (%.1fms)",
                agent_id, len(claims), verified_count, t_elapsed,
            )

        return result

    # ------------------------------------------------------------------
    # Individual claim checks
    # ------------------------------------------------------------------

    def _check_modification_claim(
        self, agent_id: str, claim: AgentClaim,
        before: FileSnapshot | None, after: FileSnapshot | None,
    ) -> Hallucination | None:
        fp = claim.file_path

        if not after or not after.exists:
            return Hallucination(
                hallucination_type=HallucinationType.PHANTOM_FILE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims '{claim.action.value}' on '{fp}' "
                    f"but file does not exist after iteration."
                ),
                claim=claim,
                sha_before=before.sha256 if before else None,
                sha_after=None,
            )

        if not before or not before.exists:
            return Hallucination(
                hallucination_type=HallucinationType.PHANTOM_FILE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims '{claim.action.value}' on '{fp}' "
                    f"but file did not exist before iteration. "
                    f"Should be 'created', not '{claim.action.value}'."
                ),
                claim=claim,
                sha_before=None, sha_after=after.sha256,
            )

        # THE KEY CHECK: SHA unchanged = no actual modification
        if before.sha256 == after.sha256:
            return Hallucination(
                hallucination_type=HallucinationType.NO_ACTUAL_CHANGE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims '{claim.action.value}' on '{fp}' "
                    f"but SHA-256 is identical before and after: "
                    f"{before.sha256[:16]}. No actual change was made."
                ),
                claim=claim,
                sha_before=before.sha256, sha_after=after.sha256,
            )

        return None

    def _check_creation_claim(
        self, agent_id: str, claim: AgentClaim,
        before: FileSnapshot | None, after: FileSnapshot | None,
    ) -> Hallucination | None:
        fp = claim.file_path

        if not after or not after.exists:
            return Hallucination(
                hallucination_type=HallucinationType.PHANTOM_FILE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'created' '{fp}' but file "
                    f"does not exist after iteration."
                ),
                claim=claim,
            )

        if before and before.exists and before.sha256 == after.sha256:
            return Hallucination(
                hallucination_type=HallucinationType.NO_ACTUAL_CHANGE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'created' '{fp}' but file "
                    f"already existed with identical SHA: {before.sha256[:16]}."
                ),
                claim=claim,
                sha_before=before.sha256, sha_after=after.sha256,
            )

        return None

    def _check_deletion_claim(
        self, agent_id: str, claim: AgentClaim,
        before: FileSnapshot | None, after: FileSnapshot | None,
    ) -> Hallucination | None:
        fp = claim.file_path

        if not before or not before.exists:
            return Hallucination(
                hallucination_type=HallucinationType.PHANTOM_FILE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'deleted' '{fp}' but file "
                    f"did not exist before iteration."
                ),
                claim=claim,
            )

        if after and after.exists:
            return Hallucination(
                hallucination_type=HallucinationType.NO_ACTUAL_CHANGE,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'deleted' '{fp}' but file "
                    f"still exists after iteration with SHA: {after.sha256[:16]}."
                ),
                claim=claim,
                sha_before=before.sha256, sha_after=after.sha256,
            )

        return None

    def _check_noop_claim(
        self, agent_id: str, claim: AgentClaim,
        before: FileSnapshot | None, after: FileSnapshot | None,
    ) -> Hallucination | None:
        fp = claim.file_path

        # File existed before but vanished without a DELETE claim
        if before and before.exists and (not after or not after.exists):
            return Hallucination(
                hallucination_type=HallucinationType.UNEXPECTED_DELETION,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'noop' on '{fp}' but file was deleted "
                    f"without a delete claim. Unexpected deletion."
                ),
                claim=claim,
                sha_before=before.sha256, sha_after=None,
            )

        if (before and after and before.exists and after.exists
                and before.sha256 != after.sha256):
            return Hallucination(
                hallucination_type=HallucinationType.FILE_NOT_IN_SNAPSHOT,
                file_path=fp, agent_id=agent_id,
                description=(
                    f"Agent claims 'noop' on '{fp}' but SHA changed: "
                    f"{before.sha256[:16]} → {after.sha256[:16]}. "
                    f"Undeclared modification."
                ),
                claim=claim,
                sha_before=before.sha256, sha_after=after.sha256,
            )

        return None

    # ------------------------------------------------------------------
    # Audit log persistence
    # ------------------------------------------------------------------

    def _write_audit_log(self, result: VerificationResult) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / "verification_audit.jsonl"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error("Failed to write audit log: %s", e)

    # ------------------------------------------------------------------
    # History and reporting
    # ------------------------------------------------------------------

    @property
    def history(self) -> list[VerificationResult]:
        return list(self._history)

    @property
    def total_hallucinations(self) -> int:
        return sum(r.hallucination_count for r in self._history)

    @property
    def total_blocked(self) -> int:
        return sum(1 for r in self._history if r.blocked)

    def get_hallucinations_by_agent(self) -> dict[str, list[Hallucination]]:
        by_agent: dict[str, list[Hallucination]] = {}
        for result in self._history:
            for h in result.hallucinations:
                by_agent.setdefault(h.agent_id, []).append(h)
        return by_agent

    def get_hallucinations_by_type(self) -> dict[str, int]:
        by_type: dict[str, int] = {}
        for result in self._history:
            for h in result.hallucinations:
                key = h.hallucination_type.value
                by_type[key] = by_type.get(key, 0) + 1
        return by_type

    def export_report(self) -> dict[str, Any]:
        return {
            "total_verifications": len(self._history),
            "total_hallucinations": self.total_hallucinations,
            "total_blocked": self.total_blocked,
            "by_type": self.get_hallucinations_by_type(),
            "by_agent": {
                a: len(hs) for a, hs in self.get_hallucinations_by_agent().items()
            },
            "results": [r.to_dict() for r in self._history],
        }


# ═══════════════════════════════════════════════════════════════════════════
# PART 2: PIPELINE INTEGRATION BRIDGE (HallucinationGuard)
# ═══════════════════════════════════════════════════════════════════════════


class LoopGuardProtocol(Protocol):
    """Minimal interface from LoopGuard."""
    def record_iteration(
        self, agent_id: str, file_path: str, action: str,
        finding_id: str | None = None, patch_diff: str | None = None,
        cost_usd: float = 0.0, duration_sec: float = 0.0,
    ) -> Any: ...


class HumanGateProtocol(Protocol):
    """Minimal interface from HumanGate."""
    def request_approval(self, request: Any) -> Any: ...


class ContextPersistenceProtocol(Protocol):
    """Minimal interface from ContextPersistence."""
    def record_event(
        self, event_type: Any, agent_id: str,
        description: str, details: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass
class IterationContext:
    """Pre-iteration state: snapshot holder between before/after."""
    agent_id: str
    declared_files: list[str]
    snapshots: dict[str, FileSnapshot]
    additional_watch: list[str]
    start_time: float
    iteration_id: str = field(
        default_factory=lambda: str(uuid.uuid4())[:8]
    )

    @property
    def elapsed_sec(self) -> float:
        return time.monotonic() - self.start_time


class HallucinationGuard:
    """Bridges FileVerificationLayer with LoopGuard and Human Gate.

    Lifecycle per agent iteration:
      1. before_iteration(agent_id, files) → IterationContext
      2. [agent runs]
      3. after_iteration(agent_id, claims, ctx) → VerificationResult
    """

    def __init__(
        self,
        file_layer: FileVerificationLayer,
        loop_guard: LoopGuardProtocol | None = None,
        human_gate: HumanGateProtocol | None = None,
        context_persistence: ContextPersistenceProtocol | None = None,
        audit_log_path: Path | None = None,
        auto_escalate: bool = True,
    ) -> None:
        self.file_layer = file_layer
        self.loop_guard = loop_guard
        self.human_gate = human_gate
        self.context_persistence = context_persistence
        self.audit_log_path = audit_log_path or Path("results/hallucinations.jsonl")
        self.auto_escalate = auto_escalate

        self._total_iterations = 0
        self._total_hallucinations = 0
        self._total_blocked = 0
        self._results: list[VerificationResult] = []

    # ------------------------------------------------------------------
    # Before iteration
    # ------------------------------------------------------------------

    def before_iteration(
        self, agent_id: str, declared_files: list[str],
        additional_watch: list[str] | None = None,
    ) -> IterationContext:
        all_files = list(declared_files)
        watch = additional_watch or []
        all_files.extend(watch)
        snapshots = self.file_layer.snapshot_files(all_files)

        return IterationContext(
            agent_id=agent_id,
            declared_files=list(declared_files),
            snapshots=snapshots,
            additional_watch=watch,
            start_time=time.monotonic(),
        )

    # ------------------------------------------------------------------
    # After iteration
    # ------------------------------------------------------------------

    def after_iteration(
        self, agent_id: str, claims: list[AgentClaim],
        ctx: IterationContext,
    ) -> VerificationResult:
        self._total_iterations += 1

        result = self.file_layer.verify_changes(
            agent_id=agent_id, claims=claims,
            snapshots_before=ctx.snapshots,
            additional_watch_paths=ctx.additional_watch,
        )

        self._results.append(result)

        # Record in LoopGuard
        if self.loop_guard:
            for claim in claims:
                action = (
                    "hallucination"
                    if any(h.file_path == claim.file_path
                           for h in result.hallucinations)
                    else claim.action.value
                )
                self.loop_guard.record_iteration(
                    agent_id=agent_id, file_path=claim.file_path,
                    action=action, finding_id=claim.finding_id,
                    duration_sec=ctx.elapsed_sec,
                )

        # Handle hallucinations
        if result.hallucinations:
            self._total_hallucinations += len(result.hallucinations)
            if result.blocked:
                self._total_blocked += 1
            self._on_hallucination_detected(agent_id, result, ctx)

        # Record in ContextPersistence
        if self.context_persistence:
            try:
                from loop_guard import EventType
                event_type = (
                    EventType.AUDIT_FINDING
                    if result.hallucinations
                    else EventType.ITERATION_END
                )
                self.context_persistence.record_event(
                    event_type=event_type, agent_id=agent_id,
                    description=result.summary(),
                    details={"iteration_id": ctx.iteration_id,
                             "verdict": result.verdict.value,
                             "hallucination_count": result.hallucination_count},
                )
            except ImportError:
                pass

        # Audit log
        self._write_audit_entry(agent_id, result, ctx)

        return result

    # ------------------------------------------------------------------
    # Hallucination handler
    # ------------------------------------------------------------------

    def _on_hallucination_detected(
        self, agent_id: str, result: VerificationResult,
        ctx: IterationContext,
    ) -> None:
        logger.warning(
            "HALLUCINATION — agent=%s count=%d blocked=%s iter_id=%s",
            agent_id, result.hallucination_count, result.blocked,
            ctx.iteration_id,
        )
        for h in result.hallucinations:
            logger.warning(
                "  [%s] file=%s: %s (sha_before=%s sha_after=%s)",
                h.hallucination_type.value, h.file_path, h.description,
                (h.sha_before or "N/A")[:16], (h.sha_after or "N/A")[:16],
            )

        if self.auto_escalate and self.human_gate and result.blocked:
            self._escalate_to_human_gate(agent_id, result, ctx)

    def _escalate_to_human_gate(
        self, agent_id: str, result: VerificationResult,
        ctx: IterationContext,
    ) -> None:
        try:
            from supervisor import GateRequest, GateLevel
        except ImportError:
            logger.error("Cannot escalate — supervisor module not available.")
            return

        halluc_details = [
            {
                "type": h.hallucination_type.value,
                "file": h.file_path,
                "description": h.description,
                "sha_before": h.sha_before,
                "sha_after": h.sha_after,
            }
            for h in result.hallucinations
        ]

        gate_request = GateRequest(
            id=f"halluc-{ctx.iteration_id}",
            agent_name=agent_id,
            stage="VERIFICATION",
            level=GateLevel.CRITICAL,
            title=f"HALLUCINATION DETECTED — {agent_id}",
            description=(
                f"Agent '{agent_id}' produced {result.hallucination_count} "
                f"hallucinated claim(s). SHA-256 verification failed.\n\n"
                f"Verdict: {result.verdict.value}\n"
                f"Claims total: {result.claims_total}\n"
                f"Claims verified: {result.claims_verified}\n"
                f"Claims failed: {result.claims_failed}\n\n"
                f"Details:\n"
                + "\n".join(
                    f"  - [{d['type']}] {d['file']}: {d['description']}"
                    for d in halluc_details
                )
            ),
            action_plan=[
                {"step": "Review hallucination details below"},
                {"step": "Decide: block agent, reassign to different model, "
                         "or force continue with override"},
            ],
            risk_assessment=(
                f"Agent claims do not match file reality. "
                f"{result.hallucination_count} file(s) have SHA mismatch. "
                f"Continuing without review risks deploying unchanged code."
            ),
            proposed_commands=[],
            metadata={
                "hallucinations": halluc_details,
                "iteration_id": ctx.iteration_id,
                "verification_result": result.to_dict(),
            },
        )

        try:
            self.human_gate.request_approval(gate_request)
        except Exception as e:
            logger.error("Failed to escalate to Human Gate: %s", e)

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _write_audit_entry(
        self, agent_id: str, result: VerificationResult,
        ctx: IterationContext,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration_id": ctx.iteration_id,
            "agent_id": agent_id,
            "verdict": result.verdict.value,
            "claims_total": result.claims_total,
            "claims_verified": result.claims_verified,
            "claims_failed": result.claims_failed,
            "hallucination_count": result.hallucination_count,
            "blocked": result.blocked,
            "elapsed_sec": ctx.elapsed_sec,
            "hallucinations": [
                {"type": h.hallucination_type.value, "file": h.file_path,
                 "sha_before": h.sha_before, "sha_after": h.sha_after}
                for h in result.hallucinations
            ],
        }
        try:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error("Failed to write audit entry: %s", e)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_iterations": self._total_iterations,
            "total_hallucinations": self._total_hallucinations,
            "total_blocked": self._total_blocked,
            "hallucination_rate": (
                self._total_hallucinations / max(self._total_iterations, 1)
            ),
            "block_rate": (
                self._total_blocked / max(self._total_iterations, 1)
            ),
        }

    @property
    def results(self) -> list[VerificationResult]:
        return list(self._results)


# ═══════════════════════════════════════════════════════════════════════════
# PART 3: UNIT TESTS — 17 tests in 4 groups
# ═══════════════════════════════════════════════════════════════════════════


class _TestBase(unittest.TestCase):
    """Base: creates temp repo with sample Go files."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.mkdtemp(prefix="sylion_test_")
        self.repo = Path(self.tmp_dir)
        (self.repo / "cmd").mkdir()
        (self.repo / "internal" / "handler").mkdir(parents=True)

        self._write("cmd/main.go", "package main\n\nfunc main() {}\n")
        self._write("internal/handler/handler.go",
                     'package handler\n\nimport "fmt"\n\n'
                     'func Handle(w http.ResponseWriter, r *http.Request) {\n'
                     '    fmt.Fprintf(w, "OK")\n}\n')
        self._write("internal/handler/utils.go",
                     "package handler\n\nfunc sanitize(s string) string {\n"
                     "    return s\n}\n")
        self._write("go.mod", "module sylion\n\ngo 1.22\n")

        self.layer = FileVerificationLayer(
            repo_root=self.repo, fail_closed=True,
            log_dir=self.repo / ".verification_logs",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write(self, rel_path: str, content: str) -> Path:
        p = self.repo / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _read(self, rel_path: str) -> str:
        return (self.repo / rel_path).read_text(encoding="utf-8")

    def _delete(self, rel_path: str) -> None:
        (self.repo / rel_path).unlink()


# --- GROUP 1: Happy Path (5 tests) ---

class TestHappyPath(_TestBase):

    def test_01_modify_claim_verified(self):
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])
        self._write(fp, self._read(fp).replace('"OK"', '"OK\\n"'))
        claims = [AgentClaim(file_path=fp, action=ClaimAction.MODIFIED,
                             description="Added newline")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.VERIFIED)
        self.assertFalse(result.blocked)

    def test_02_fix_claim_verified(self):
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])
        self._write(fp, self._read(fp).replace("func Handle(",
                                                "func Handle(ctx context.Context, "))
        claims = [AgentClaim(file_path=fp, action=ClaimAction.FIXED,
                             description="Added context param")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_03_create_claim_verified(self):
        fp = "internal/handler/middleware.go"
        snapshots = self.layer.snapshot_files([fp])
        self._write(fp, "package handler\n\nfunc Auth() {}\n")
        claims = [AgentClaim(file_path=fp, action=ClaimAction.CREATED)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_04_delete_claim_verified(self):
        fp = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp])
        self._delete(fp)
        claims = [AgentClaim(file_path=fp, action=ClaimAction.DELETED)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.VERIFIED)

    def test_05_noop_claim_verified(self):
        fp = "go.mod"
        snapshots = self.layer.snapshot_files([fp])
        claims = [AgentClaim(file_path=fp, action=ClaimAction.NOOP)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.VERIFIED)


# --- GROUP 2: Hallucination Detection (7 tests) ---

class TestHallucinationDetection(_TestBase):

    def test_06_no_actual_change_fixed(self):
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])
        claims = [AgentClaim(file_path=fp, action=ClaimAction.FIXED,
                             description="Fixed error handling")]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        self.assertEqual(result.hallucinations[0].hallucination_type,
                         HallucinationType.NO_ACTUAL_CHANGE)

    def test_07_phantom_file(self):
        fp = "internal/handler/nonexistent.go"
        snapshots = self.layer.snapshot_files([fp])
        claims = [AgentClaim(file_path=fp, action=ClaimAction.MODIFIED)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertEqual(result.hallucinations[0].hallucination_type,
                         HallucinationType.PHANTOM_FILE)

    def test_08_file_not_in_snapshot_undeclared(self):
        fp_claimed = "internal/handler/handler.go"
        fp_undeclared = "go.mod"
        snapshots = self.layer.snapshot_files([fp_claimed, fp_undeclared])
        self._write(fp_claimed, self._read(fp_claimed) + "\n// patched\n")
        self._write(fp_undeclared, "module sylion\n\ngo 1.23\n")
        claims = [AgentClaim(file_path=fp_claimed, action=ClaimAction.MODIFIED)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.FILE_NOT_IN_SNAPSHOT, types)

    def test_09_unexpected_deletion(self):
        fp_keep = "internal/handler/handler.go"
        fp_vanish = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp_keep, fp_vanish])
        self._delete(fp_vanish)
        claims = [AgentClaim(file_path=fp_keep, action=ClaimAction.NOOP)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.UNEXPECTED_DELETION, types)

    def test_10_unexpected_creation(self):
        fp_watch = "internal/handler/handler.go"
        fp_surprise = "internal/handler/backdoor.go"
        snapshots = self.layer.snapshot_files([fp_watch, fp_surprise])
        self._write(fp_surprise, "package handler\n// surprise!\n")
        claims = [AgentClaim(file_path=fp_watch, action=ClaimAction.NOOP)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        types = {h.hallucination_type for h in result.hallucinations}
        self.assertIn(HallucinationType.UNEXPECTED_CREATION, types)

    def test_11_delete_nonexistent(self):
        fp = "internal/handler/imaginary.go"
        snapshots = self.layer.snapshot_files([fp])
        claims = [AgentClaim(file_path=fp, action=ClaimAction.DELETED)]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.hallucinations[0].hallucination_type,
                         HallucinationType.PHANTOM_FILE)

    def test_12_changelog_v3_4_13_scenario(self):
        """THE critical test — agent claims fixed but SHA unchanged."""
        fp = "internal/handler/handler.go"
        snapshots = self.layer.snapshot_files([fp])
        sha_before = snapshots[fp].sha256

        claims = [AgentClaim(
            file_path=fp, action=ClaimAction.FIXED,
            description="Fixed err.Error() — CHANGELOG-v3.4.13",
            finding_id="F-SEC-042", agent_id="programmer_go_1",
        )]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)

        self.assertEqual(sha_before, self.layer.snapshot_file(fp).sha256)
        self.assertEqual(result.verdict, Verdict.HALLUCINATION)
        self.assertTrue(result.blocked)
        h = result.hallucinations[0]
        self.assertEqual(h.hallucination_type, HallucinationType.NO_ACTUAL_CHANGE)
        self.assertEqual(h.sha_before, h.sha_after)


# --- GROUP 3: Partial Verification (1 test) ---

class TestPartialVerification(_TestBase):

    def test_13_mixed_claims(self):
        fp_real = "internal/handler/handler.go"
        fp_fake = "internal/handler/utils.go"
        snapshots = self.layer.snapshot_files([fp_real, fp_fake])
        self._write(fp_real, self._read(fp_real) + "\n// real change\n")
        claims = [
            AgentClaim(file_path=fp_real, action=ClaimAction.MODIFIED),
            AgentClaim(file_path=fp_fake, action=ClaimAction.FIXED,
                       description="HALLUCINATED"),
        ]
        result = self.layer.verify_changes("programmer_go_1", claims, snapshots)
        self.assertEqual(result.verdict, Verdict.PARTIAL)
        self.assertEqual(result.claims_verified, 1)
        self.assertEqual(result.claims_failed, 1)
        self.assertTrue(result.blocked)


# --- GROUP 4: Edge Cases (4 tests) ---

class TestEdgeCases(_TestBase):

    def test_14_no_claims_no_changes(self):
        snapshots = self.layer.snapshot_files(["go.mod"])
        result = self.layer.verify_changes("programmer_go_1", [], snapshots)
        self.assertEqual(result.verdict, Verdict.NO_CLAIMS)
        self.assertFalse(result.blocked)

    def test_15_claim_validation_action_types(self):
        fp = "cmd/main.go"
        snapshots = self.layer.snapshot_files([fp])
        for action in ClaimAction:
            claim = AgentClaim(file_path=fp, action=action)
            result = self.layer.verify_changes("test_agent", [claim], snapshots)
            self.assertIsInstance(result, VerificationResult)

    def test_16_sha_consistency(self):
        fp = "cmd/main.go"
        s1 = self.layer.snapshot_file(fp)
        s2 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s2.sha256)
        self.assertEqual(len(s1.sha256), 64)
        content = self._read(fp)
        self._write(fp, content)
        s3 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s3.sha256)

    def test_17_large_file_handling(self):
        fp = "large_test_file.bin"
        data = b"SYLION_TEST_BLOCK" * (2 * 1024 * 1024 // 17 + 1)
        (self.repo / fp).write_bytes(data)
        s1 = self.layer.snapshot_file(fp)
        self.assertGreater(s1.size_bytes, 1_000_000)
        s2 = self.layer.snapshot_file(fp)
        self.assertEqual(s1.sha256, s2.sha256)
        data_mod = bytearray(data)
        data_mod[1000] = (data_mod[1000] + 1) % 256
        (self.repo / fp).write_bytes(bytes(data_mod))
        s3 = self.layer.snapshot_file(fp)
        self.assertNotEqual(s1.sha256, s3.sha256)


# ═══════════════════════════════════════════════════════════════════════════
# PART 4: END-TO-END TEST — CHANGELOG-v3.4.13 scenario
# ═══════════════════════════════════════════════════════════════════════════

class MockLoopGuard:
    """Captures record_iteration calls for testing."""
    def __init__(self):
        self.records: list[dict] = []

    def record_iteration(self, agent_id, file_path, action, **kw):
        self.records.append({"agent_id": agent_id, "file_path": file_path,
                             "action": action, **kw})


class MockHumanGate:
    """Captures request_approval calls for testing."""
    def __init__(self):
        self.requests: list[Any] = []

    def request_approval(self, request):
        self.requests.append(request)


def run_e2e_test() -> bool:
    """Full CHANGELOG-v3.4.13 scenario — returns True if all assertions pass."""
    print("=" * 70)
    print("E2E TEST: CHANGELOG-v3.4.13 Hallucination Scenario")
    print("=" * 70)

    tmp = tempfile.mkdtemp(prefix="sylion_e2e_")
    repo = Path(tmp)
    (repo / "internal" / "handler").mkdir(parents=True)

    handler_content = (
        'package handler\n\nimport (\n    "fmt"\n    "net/http"\n)\n\n'
        'func Handle(w http.ResponseWriter, r *http.Request) {\n'
        '    err := doSomething()\n'
        '    if err != nil {\n'
        '        fmt.Fprintf(w, "error: %s", err.Error())\n'
        '        return\n    }\n'
        '    fmt.Fprintf(w, "OK")\n}\n\n'
        'func doSomething() error { return nil }\n'
    )
    (repo / "internal" / "handler" / "handler.go").write_text(
        handler_content, encoding="utf-8"
    )

    file_layer = FileVerificationLayer(
        repo_root=repo, fail_closed=True, log_dir=repo / ".logs",
    )
    mock_lg = MockLoopGuard()
    mock_hg = MockHumanGate()
    guard = HallucinationGuard(
        file_layer=file_layer, loop_guard=mock_lg, human_gate=mock_hg,
        audit_log_path=repo / ".logs" / "hallucinations.jsonl",
    )

    # STEP 1: before_iteration
    print("\n[1] before_iteration — snapshotting handler.go")
    ctx = guard.before_iteration(
        "programmer_go_1", ["internal/handler/handler.go"],
    )
    sha_before = ctx.snapshots["internal/handler/handler.go"].sha256
    print(f"    SHA before: {sha_before[:32]}...")

    # STEP 2: agent does NOTHING
    print("[2] Agent runs — does NOT modify handler.go (hallucination)")

    # STEP 3: agent claims FIXED
    print("[3] Agent claims: FIXED handler.go (CHANGELOG-v3.4.13)")
    claims = [AgentClaim(
        file_path="internal/handler/handler.go",
        action=ClaimAction.FIXED,
        description="Fixed err.Error() handling — fmt.Errorf (CHANGELOG-v3.4.13)",
        finding_id="F-SEC-042", agent_id="programmer_go_1",
    )]

    # STEP 4: after_iteration
    print("[4] after_iteration — verifying claims vs reality")
    result = guard.after_iteration("programmer_go_1", claims, ctx)

    sha_after = file_layer.snapshot_file("internal/handler/handler.go").sha256
    print(f"\n    SHA after:  {sha_after[:32]}...")
    print(f"    Verdict:    {result.verdict.value}")
    print(f"    Blocked:    {result.blocked}")
    if result.hallucinations:
        h = result.hallucinations[0]
        print(f"    Type:       {h.hallucination_type.value}")

    # Assertions
    print("\n" + "-" * 70)
    all_pass = True

    def check(name, cond):
        nonlocal all_pass
        s = "PASS" if cond else "FAIL"
        if not cond:
            all_pass = False
        print(f"  [{s}] {name}")

    check("SHA unchanged",                    sha_before == sha_after)
    check("Verdict = HALLUCINATION",          result.verdict == Verdict.HALLUCINATION)
    check("1 hallucination detected",         result.hallucination_count == 1)
    check("Type = NO_ACTUAL_CHANGE",          result.hallucinations[0].hallucination_type == HallucinationType.NO_ACTUAL_CHANGE)
    check("Agent blocked",                    result.blocked is True)
    check("LoopGuard: action=hallucination",  mock_lg.records[0]["action"] == "hallucination")
    check("HumanGate: CRITICAL escalation",   len(mock_hg.requests) == 1 and mock_hg.requests[0].level.value == "critical")
    check("Audit log written",               (repo / ".logs" / "hallucinations.jsonl").exists())

    shutil.rmtree(tmp, ignore_errors=True)

    print("-" * 70)
    print(f"RESULT: {'ALL 8 PASS' if all_pass else 'SOME FAILED'}")
    print("=" * 70)
    return all_pass


# ═══════════════════════════════════════════════════════════════════════════
# PART 5: CLI RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Run all tests or specific subsets via CLI flags."""
    mode = "all"
    if "--e2e" in sys.argv:
        mode = "e2e"
    elif "--unit" in sys.argv:
        mode = "unit"

    results = []

    if mode in ("all", "unit"):
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print("║  UNIT TESTS — 17 tests, 4 groups                           ║")
        print("╚══════════════════════════════════════════════════════════════╝\n")

        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for cls in (TestHappyPath, TestHallucinationDetection,
                    TestPartialVerification, TestEdgeCases):
            suite.addTests(loader.loadTestsFromTestCase(cls))

        runner = unittest.TextTestRunner(verbosity=2)
        unit_result = runner.run(suite)
        results.append(unit_result.wasSuccessful())

    if mode in ("all", "e2e"):
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print("║  E2E TEST — CHANGELOG-v3.4.13 scenario                     ║")
        print("╚══════════════════════════════════════════════════════════════╝\n")

        e2e_ok = run_e2e_test()
        results.append(e2e_ok)

    # Summary
    print("\n" + "=" * 70)
    if all(results):
        print("ALL TESTS PASSED")
    else:
        print("SOME TESTS FAILED")
    print("=" * 70)

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
