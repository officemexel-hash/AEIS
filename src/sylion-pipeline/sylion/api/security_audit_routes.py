"""
SYLION API -- Security Audit routes.

Endpoints for the SecurityAuditor module:
  create_finding, update_finding, get_finding, list_findings,
  start_scan, complete_scan, get_scan, list_scans,
  create_remediation, complete_remediation, get_security_stats.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/v1/security-audit", tags=["Security Audit"])


# ---------------------------------------------------------------------------
# Lazy accessor
# ---------------------------------------------------------------------------

_security_auditor = None


def _get_security_auditor():
    global _security_auditor
    if _security_auditor is not None:
        return _security_auditor
    from sylion.security.security_audit import get_security_auditor
    _security_auditor = get_security_auditor()
    return _security_auditor


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateFindingRequest(BaseModel):
    title: str
    severity: str = "medium"
    description: str = ""
    module: str = ""
    recommendation: str = ""


class UpdateFindingRequest(BaseModel):
    title: str | None = None
    severity: str | None = None
    description: str | None = None
    module: str | None = None
    recommendation: str | None = None
    status: str | None = None


class StartScanRequest(BaseModel):
    scope: str
    scan_type: str = "full"


class CompleteScanRequest(BaseModel):
    findings_count: int = 0


class CreateRemediationRequest(BaseModel):
    finding_id: str
    action_type: str = ""
    assignee: str = ""


class CompleteRemediationRequest(BaseModel):
    result: str = ""


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

@router.post("/findings", status_code=201)
def create_finding(body: CreateFindingRequest):
    """Create a new security finding."""
    sa = _get_security_auditor()
    try:
        return sa.create_finding(
            title=body.title,
            severity=body.severity,
            description=body.description,
            module=body.module,
            recommendation=body.recommendation,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/findings/list")
def list_findings(severity: str | None = None,
                  status: str | None = None,
                  module: str | None = None):
    """List findings with optional filters."""
    sa = _get_security_auditor()
    return {"findings": sa.list_findings(
        severity=severity, status=status, module=module,
    )}


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str):
    """Retrieve a finding by ID."""
    sa = _get_security_auditor()
    result = sa.get_finding(finding_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Finding {finding_id} not found")
    return result


@router.patch("/findings/{finding_id}")
def update_finding(finding_id: str, body: UpdateFindingRequest):
    """Update a security finding."""
    sa = _get_security_auditor()
    try:
        result = sa.update_finding(
            finding_id=finding_id,
            title=body.title,
            severity=body.severity,
            description=body.description,
            module=body.module,
            recommendation=body.recommendation,
            status=body.status,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Finding {finding_id} not found")
    return result


# ---------------------------------------------------------------------------
# Scans
# ---------------------------------------------------------------------------

@router.post("/scans", status_code=201)
def start_scan(body: StartScanRequest):
    """Start a new security scan."""
    sa = _get_security_auditor()
    return sa.start_scan(scope=body.scope, scan_type=body.scan_type)


@router.get("/scans/list")
def list_scans(status: str | None = None):
    """List scans with optional status filter."""
    sa = _get_security_auditor()
    return {"scans": sa.list_scans(status=status)}


@router.get("/scans/{scan_id}")
def get_scan(scan_id: str):
    """Retrieve a scan by ID."""
    sa = _get_security_auditor()
    result = sa.get_scan(scan_id)
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Scan {scan_id} not found")
    return result


@router.post("/scans/{scan_id}/complete")
def complete_scan(scan_id: str, body: CompleteScanRequest):
    """Complete a running scan."""
    sa = _get_security_auditor()
    try:
        result = sa.complete_scan(
            scan_id, findings_count=body.findings_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Scan {scan_id} not found")
    return result


# ---------------------------------------------------------------------------
# Remediations
# ---------------------------------------------------------------------------

@router.post("/remediations", status_code=201)
def create_remediation(body: CreateRemediationRequest):
    """Create a remediation for a finding."""
    sa = _get_security_auditor()
    try:
        return sa.create_remediation(
            finding_id=body.finding_id,
            action_type=body.action_type,
            assignee=body.assignee,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/remediations/{remediation_id}/complete")
def complete_remediation(remediation_id: str, body: CompleteRemediationRequest):
    """Complete a pending remediation."""
    sa = _get_security_auditor()
    try:
        result = sa.complete_remediation(
            remediation_id, result=body.result,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404,
                            detail=f"Remediation {remediation_id} not found")
    return result


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_security_audit_module_stats():
    """Get aggregate security audit statistics from the SecurityAuditor module.

    Distinct from /api/v1/security/audit/stats which surfaces the
    audit-trail aggregator. Separate operation_id avoids OpenAPI clash.
    """
    sa = _get_security_auditor()
    return sa.get_security_stats()
