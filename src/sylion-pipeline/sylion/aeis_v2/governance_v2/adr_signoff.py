"""Council Hybrid ADR sign-off — sprint 3 A1 deliverable.

Closes the ADR-003 unblock loop opened in sprint 2 (commit ``d4bf5a54``).
The sign-off endpoint accepts:

* 9 votes — exactly one per canonical Council role.
* a critic signature — sha256 hex of the ADR document content the
  Council reviewed; the operator computes this against the actual file
  on disk so any tampering between vote and apply invalidates the gate.

Validation is pure (in :func:`evaluate_signoff`) so the FastAPI route
can stay thin. A successful gate flips the ADR's ``Status:`` line from
``PROPOSED`` to ``ACCEPTED`` and emits a chained audit row to
``logs/v2/adr_signoff.jsonl``.

Per Kimi review k3_council_signoff_security (round 51:30):

* TOCTOU on the file: signature is recomputed inside :func:`apply_signoff`
  *under* the file-write step so attacker mutation between request and
  write fails the gate.
* RBAC: only ``owner`` can call (the calling endpoint enforces this);
  the helpers themselves are RBAC-agnostic for testability.
* Replay attack: nothing stops a caller from re-submitting the same
  signature, but ``set_adr_status`` is idempotent (status already
  ACCEPTED → returns False without raising) so replays are no-ops.
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from sylion.aeis_v2.audit_chain import append_to_chain
from sylion.governance.council_hybrid import VALID_ROLES, VALID_VERDICTS

log = logging.getLogger(__name__)

#: Audit JSONL for sign-off attempts. Mirrors the v2 logs/v2 convention.
SIGNOFF_AUDIT_LOG_PATH = (
    Path(__file__).resolve().parents[3]
    / "logs" / "v2" / "adr_signoff.jsonl"
)

#: ADR Status outcomes. PROPOSED is the only state from which we can
#: legitimately transition to ACCEPTED via this endpoint.
AdrSignoffStatus = Literal[
    "ok",
    "wrong_status",         # not PROPOSED in the file
    "missing_votes",        # < 9 votes or duplicate role
    "critic_signature_mismatch",
    "no_majority_approve",  # < 5 of 9 voted approve
    "adr_not_found",
]

#: Process-wide write lock so concurrent sign-off attempts don't race
#: on the same ADR file.
_SIGNOFF_LOCK = threading.RLock()

_STATUS_LINE_RE = re.compile(
    r"^(?P<prefix>\s*>\s*\*\*Status\*\*\s*:\s*)"
    r"(?P<status>[A-Z]+)"
    r"(?P<suffix>.*)$",
    re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class AdrVote:
    """Single role vote on an ADR."""

    role: str
    verdict: str
    confidence: float = 0.0
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "verdict": self.verdict,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


@dataclass(frozen=True, slots=True)
class AdrSignoffRequest:
    """Operator's full sign-off submission."""

    adr_id: str
    votes: list[AdrVote]
    critic_signature: str
    actor: str = "anonymous"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adr_id": self.adr_id,
            "votes": [v.to_dict() for v in self.votes],
            "critic_signature": self.critic_signature,
            "actor": self.actor,
        }


@dataclass(frozen=True, slots=True)
class AdrSignoffResult:
    """Outcome of an evaluation + apply round."""

    adr_id: str
    status: AdrSignoffStatus
    new_status: str | None
    approve_count: int
    reject_count: int
    conditional_count: int
    audit_event_id: str
    detail: str = ""

    @property
    def gate_passed(self) -> bool:
        return self.status == "ok" and self.new_status == "ACCEPTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adr_id": self.adr_id,
            "status": self.status,
            "new_status": self.new_status,
            "approve_count": self.approve_count,
            "reject_count": self.reject_count,
            "conditional_count": self.conditional_count,
            "audit_event_id": self.audit_event_id,
            "detail": self.detail,
            "gate_passed": self.gate_passed,
        }


# ---------------------------------------------------------------------------
# Signature primitives
# ---------------------------------------------------------------------------


def compute_adr_signature(doc_path: Path | str) -> str:
    """sha256 hex digest of the ADR document content.

    Returns the empty string if the file is missing — callers must
    distinguish from a real (64-hex-char) signature.
    """
    p = Path(doc_path)
    if not p.exists():
        return ""
    try:
        data = p.read_bytes()
    except OSError as exc:
        log.warning("adr_signoff: read failed (%s)", exc)
        return ""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Status read / write
# ---------------------------------------------------------------------------


def load_adr_status(doc_path: Path | str) -> str | None:
    """Return the current ``Status:`` value or ``None`` if missing/unreadable."""
    p = Path(doc_path)
    if not p.exists():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _STATUS_LINE_RE.search(text)
    if not m:
        return None
    return m.group("status")


def set_adr_status(doc_path: Path | str, new_status: str) -> bool:
    """Rewrite the ``Status:`` line. Returns False on miss / no change."""
    p = Path(doc_path)
    if not p.exists():
        return False
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return False
    new_text, count = _STATUS_LINE_RE.subn(
        lambda m: f"{m.group('prefix')}{new_status}{m.group('suffix')}",
        text,
        count=1,
    )
    if count == 0:
        return False
    if new_text == text:
        return False
    try:
        p.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        log.warning("adr_signoff: status write failed (%s)", exc)
        return False
    return True


# ---------------------------------------------------------------------------
# Validation pipeline
# ---------------------------------------------------------------------------


def _tally_votes(votes: Iterable[AdrVote]) -> tuple[int, int, int]:
    """Return ``(approve, reject, conditional)`` counts."""
    approve = reject = conditional = 0
    for v in votes:
        if v.verdict == "approve":
            approve += 1
        elif v.verdict == "reject":
            reject += 1
        elif v.verdict == "conditional":
            conditional += 1
    return approve, reject, conditional


def evaluate_signoff(
    request: AdrSignoffRequest,
    *,
    expected_signature: str,
    current_status: str | None,
) -> tuple[AdrSignoffStatus, str]:
    """Pure validation: would this request flip the gate?

    Returns ``(status, detail)`` where ``status`` is one of
    :data:`AdrSignoffStatus`. Does NOT touch the filesystem.
    """
    if current_status is None:
        return ("adr_not_found", "ADR file missing or unreadable")

    if current_status != "PROPOSED":
        return (
            "wrong_status",
            f"current status is {current_status!r}; need PROPOSED",
        )

    # 9 votes, one per canonical role, all valid verdicts.
    if len(request.votes) != 9:
        return (
            "missing_votes",
            f"expected 9 votes, got {len(request.votes)}",
        )
    seen_roles = {v.role for v in request.votes}
    if seen_roles != set(VALID_ROLES):
        missing = sorted(set(VALID_ROLES) - seen_roles)
        extra = sorted(seen_roles - set(VALID_ROLES))
        return (
            "missing_votes",
            f"role mismatch — missing={missing!r} extra={extra!r}",
        )
    for v in request.votes:
        if v.verdict not in VALID_VERDICTS:
            return (
                "missing_votes",
                f"invalid verdict {v.verdict!r} from role {v.role!r}",
            )

    # Critic signature (case-insensitive comparison).
    if request.critic_signature.lower() != expected_signature.lower():
        return (
            "critic_signature_mismatch",
            "critic_signature does not match current ADR document hash",
        )

    # Need majority approve (≥ 5 of 9).
    approve, _reject, _cond = _tally_votes(request.votes)
    if approve < 5:
        return (
            "no_majority_approve",
            f"approve_count={approve} < 5",
        )

    return ("ok", "all gates passed")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _emit_audit(payload: dict[str, Any]) -> None:
    try:
        append_to_chain(SIGNOFF_AUDIT_LOG_PATH, payload)
    except Exception as exc:  # noqa: BLE001
        log.warning("adr_signoff: audit emit failed (%s)", exc)


def apply_signoff(
    request: AdrSignoffRequest,
    *,
    decisions_dir: Path,
) -> AdrSignoffResult:
    """Validate + flip status under a single lock.

    Recomputes the signature *inside* the lock (TOCTOU mitigation) so
    a request crafted against an earlier file version fails the gate
    if the file was edited between vote and apply.
    """
    import uuid

    approve, reject, conditional = _tally_votes(request.votes)
    audit_event_id = str(uuid.uuid4())

    with _SIGNOFF_LOCK:
        adr_path = decisions_dir / request.adr_id
        if not adr_path.exists():
            # Try .md suffix.
            alt = decisions_dir / f"{request.adr_id}.md"
            if alt.exists():
                adr_path = alt

        current = load_adr_status(adr_path)
        expected = compute_adr_signature(adr_path)
        status, detail = evaluate_signoff(
            request,
            expected_signature=expected,
            current_status=current,
        )

        new_status: str | None = None
        if status == "ok":
            ok = set_adr_status(adr_path, "ACCEPTED")
            if ok:
                new_status = "ACCEPTED"
            else:
                status = "wrong_status"
                detail = "status write failed"

    result = AdrSignoffResult(
        adr_id=request.adr_id,
        status=status,
        new_status=new_status,
        approve_count=approve,
        reject_count=reject,
        conditional_count=conditional,
        audit_event_id=audit_event_id,
        detail=detail,
    )
    _emit_audit({
        "kind": "adr_signoff.attempt",
        "ts": time.time(),
        "actor": request.actor,
        "request": {
            "adr_id": request.adr_id,
            "vote_count": len(request.votes),
            # Don't echo the critic_signature in the audit — it's a
            # secret on the wire (per Kimi k3 finding).
            "approve_count": approve,
            "reject_count": reject,
            "conditional_count": conditional,
        },
        "result": result.to_dict(),
    })
    log.info(
        "adr_signoff: adr=%s status=%s gate_passed=%s",
        request.adr_id, result.status, result.gate_passed,
    )
    return result
