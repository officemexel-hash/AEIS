from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from .governance_bridge import (
    submit_application_creation_ticket,
    submit_call_creation_ticket,
    submit_idea_conversion_ticket,
    submit_programme_creation_ticket,
    submit_scan_ticket,
)
from .permissions import resolve_actor
from .program_scanner import (
    compute_match_scores,
    scan_all,
)
from .schemas import (
    ApplicationCreateRequest,
    ApplicationReviewRequest,
    ConsortiumAnalyzeRequest,
    ConvertIdeaToProjectRequest,
    CreateFundingProjectRequest,
    EligibilityCheckRequest,
    FundingCallCreate,
    FundingCallSearchRequest,
    FundingCompanyProfileUpsert,
    FundingDocumentCreate,
    FundingProgrammeCreate,
    FundingRegistrySyncRequest,
    GenerateFundingIdeasRequest,
    OutreachGenerateRequest,
    PartnerSearchRequest,
    PartnerShortlistRequest,
    RunMatchingRequest,
    RunScoringRequest,
    SubmissionApprovalRequest,
    SubmissionFillRequest,
    SubmissionFinalizeRequest,
    SubmissionPrepareRequest,
    SubmissionSaveDraftRequest,
)
from .service import EXPORT_ARTIFACT_MEDIA_TYPES, FundingAutopilotService
from sylion.governance.ticket import GovernanceTicket
from sylion.governance.tickets import register_post_resolve_hook

router = APIRouter(prefix="/api/v1/funding", tags=["funding"])

_service = FundingAutopilotService()


def reset_funding_route_service(db_path: str | None = None) -> FundingAutopilotService:
    global _service
    _service = FundingAutopilotService(db_path=db_path)
    return _service


def _funding_post_resolve(ticket: GovernanceTicket, decision: str) -> None:
    payload = ticket.payload or {}
    if ticket.origin != "funding":
        return
    if payload.get("action") == "final_submission":
        session_id = str(payload.get("session_id") or "")
        if not session_id:
            return
        for approval in _service.store.list_approval_events(session_id=session_id):
            approval_payload = approval.get("payload_json", {}) or {}
            if str(approval_payload.get("governance_ticket_id") or "") != ticket.ticket_id:
                continue
            _service.store.update_approval_event(
                approval["approval_event_id"],
                {
                    "payload": {
                        **approval_payload,
                        "human_gate_state": decision,
                        "human_gate_resolved_by": ticket.resolved_by or "",
                        "human_gate_resolved_at": ticket.resolved_at,
                        "human_gate_reason": ticket.resolution_reason or "",
                    },
                },
            )
            break
        return
    if payload.get("action") != "idea_conversion":
        return
    if decision != "approved" or payload.get("project_id"):
        return
    result = _service.convert_idea_to_project(
        str(payload.get("idea_id") or ""),
        str(payload.get("company_id") or "default"),
        payload.get("call_id") or None,
        int(payload.get("target_trl") or 4),
        str(payload.get("actor") or "human_gate"),
    )
    project = (result or {}).get("project") if isinstance(result, dict) else None
    if isinstance(project, dict):
        ticket.payload["project_id"] = project.get("project_id", "")


register_post_resolve_hook(_funding_post_resolve)


@router.get("/health")
async def health() -> dict[str, object]:
    import time

    return {
        "status": "ok",
        "module": "funding",
        "version": "3.5.0",
        "timestamp": time.time(),
    }


def _raise_http(exc: ValueError) -> None:
    message = str(exc)
    status = 404 if "not found" in message.lower() else 400
    raise HTTPException(status, message)


@router.get("/company-profile")
async def get_company_profile(company_id: str = "default"):
    return _service.get_company_profile(company_id)


@router.put("/company-profile")
async def upsert_company_profile(body: FundingCompanyProfileUpsert, request: Request):
    return _service.save_company_profile(body.model_dump(), resolve_actor(request))


@router.get("/company-profile/readiness")
async def get_company_readiness(company_id: str = "default"):
    try:
        return _service.get_company_readiness(company_id)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/company-profile/documents")
async def list_company_documents(company_id: str = "default"):
    return {"documents": _service.store.list_company_documents(company_id)}


@router.post("/company-profile/documents")
async def add_company_document(body: FundingDocumentCreate, request: Request):
    try:
        return _service.add_company_document(body.model_dump(), resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.get("/company-profile/state-aid")
async def get_state_aid(company_id: str = "default"):
    profile = _service.get_company_profile(company_id)
    return {
        "company_id": company_id,
        "state_aid_total_eur": profile.get("state_aid_total_eur", 0.0),
        "de_minimis_total_eur": profile.get("de_minimis_total_eur", 0.0),
        "prior_grants_count": profile.get("prior_grants_count", 0),
    }


@router.get("/company-profile/registry-sync")
async def get_company_registry_sync(company_id: str = "default"):
    return _service.get_company_registry_sync(company_id)


@router.post("/company-profile/registry-sync")
async def sync_company_registry(body: FundingRegistrySyncRequest, request: Request):
    try:
        return _service.sync_company_registry(body.company_id, body.krs, resolve_actor(request), body.apply_profile)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/sources")
async def list_sources():
    return _service.list_sources()


@router.get("/programmes")
async def list_programmes():
    return _service.list_programmes()


@router.post("/programmes")
async def create_programme(body: FundingProgrammeCreate, request: Request):
    programme = _service.create_programme(body.model_dump(), resolve_actor(request))
    try:
        ticket_id = submit_programme_creation_ticket(programme)
        if isinstance(programme, dict):
            programme.setdefault("governance_ticket_id", ticket_id)
    except Exception as exc:
        raise HTTPException(500, "Failed to submit governance ticket for funding programme creation") from exc
    return programme


@router.get("/calls")
async def list_calls():
    return _service.list_calls()


@router.post("/calls")
async def create_call(body: FundingCallCreate, request: Request):
    try:
        call = _service.create_call(body.model_dump(), resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)
        return  # unreachable, _raise_http raises
    try:
        ticket_id = submit_call_creation_ticket(call)
        if isinstance(call, dict):
            call.setdefault("governance_ticket_id", ticket_id)
    except Exception as exc:
        raise HTTPException(500, "Failed to submit governance ticket for funding call creation") from exc
    return call


@router.post("/calls/search")
async def search_calls(body: FundingCallSearchRequest):
    return _service.search_calls(body.model_dump())


@router.get("/calls/scored")
async def list_calls_scored(
    company_id: str = "default",
    programme: str | None = None,
    since: float | None = None,
    min_match: float = 0.0,
):
    """List currently open funding calls with TF-IDF match scores."""
    calls = compute_match_scores(company_id)
    if programme:
        calls = [c for c in calls if c.get("programme_id", "").lower().endswith(programme.lower())]
    if since is not None:
        calls = [c for c in calls if (c.get("closes_at") or 0) >= since]
    if min_match > 0:
        calls = [c for c in calls if c.get("match_score", 0) >= min_match]
    return {"company_id": company_id, "calls": calls}


@router.get("/calls/{call_id}")
async def get_call(call_id: str):
    call = _service.store.get_call(call_id)
    if call is None:
        raise HTTPException(404, f"Funding call '{call_id}' not found")
    return call


@router.get("/ideas")
async def list_ideas(company_id: str = "default"):
    return {"ideas": _service.store.list_ideas(company_id)}


@router.post("/ideas/generate")
async def generate_ideas(body: GenerateFundingIdeasRequest):
    try:
        return _service.generate_ideas(body.company_id, body.limit)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str):
    try:
        return _service.get_idea(idea_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/ideas/{idea_id}/convert-to-project")
async def convert_idea_to_project(idea_id: str, body: ConvertIdeaToProjectRequest, request: Request):
    actor = resolve_actor(request)
    try:
        _service.get_idea(idea_id)
        _service.get_company_profile(body.company_id)
    except ValueError as exc:
        _raise_http(exc)
        return
    try:
        ticket_id = submit_idea_conversion_ticket(
            idea_id=idea_id,
            call_id=body.call_id,
            company_id=body.company_id,
            target_trl=body.target_trl,
            actor=actor,
        )
    except Exception:
        raise HTTPException(500, "Failed to submit Human Gate ticket for funding idea conversion")
    return {
        "status": "pending_human_gate",
        "idea_id": idea_id,
        "governance_ticket_id": ticket_id,
        "message": "Konwersja pomysłu na projekt oczekuje na akceptację Human Gate.",
    }


@router.get("/projects")
async def list_projects(company_id: str | None = None):
    return _service.list_projects(company_id)


@router.post("/projects")
async def create_project(body: CreateFundingProjectRequest, request: Request):
    try:
        return _service.create_project(body.model_dump(), resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    try:
        return _service.get_project(project_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/matching/run")
async def run_matching(body: RunMatchingRequest):
    try:
        return _service.run_matching(body.project_id, call_id=body.call_id, top_k=body.top_k)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/matching/results/{project_id}")
async def get_matching_results(project_id: str):
    try:
        return _service.get_matching_results(project_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/eligibility/check")
async def check_eligibility(body: EligibilityCheckRequest):
    try:
        return _service.check_eligibility(body.project_id, body.call_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/scoring/run")
async def run_scoring(body: RunScoringRequest):
    try:
        return _service.run_scoring(body.project_id, body.call_id)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/scoring/{project_id}")
async def get_scoring(project_id: str):
    try:
        return _service.get_scoring(project_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/consortium/analyze")
async def analyze_consortium(body: ConsortiumAnalyzeRequest):
    try:
        return _service.analyze_consortium(body.project_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/consortium/partners/search")
async def search_partners(body: PartnerSearchRequest):
    try:
        return _service.search_partners(body.model_dump())
    except ValueError as exc:
        _raise_http(exc)


@router.post("/consortium/partners/shortlist")
async def shortlist_partners(body: PartnerShortlistRequest):
    try:
        return _service.shortlist_partners(body.project_id, body.limit)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/consortium/outreach/generate")
async def generate_outreach(body: OutreachGenerateRequest):
    try:
        return _service.generate_outreach(body.project_id, body.partner_ids)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/application/create")
async def create_application(body: ApplicationCreateRequest, request: Request):
    try:
        app_obj = _service.create_application(body.project_id, body.company_id, body.call_id, resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)
        return
    application_id = (app_obj or {}).get("application_id") if isinstance(app_obj, dict) else None
    amount = float((app_obj or {}).get("amount_requested_eur", 0.0)) if isinstance(app_obj, dict) else 0.0
    try:
        ticket_id = submit_application_creation_ticket(application_id or "", body.project_id, body.call_id, amount)
        if isinstance(app_obj, dict):
            app_obj.setdefault("governance_ticket_id", ticket_id)
    except Exception as exc:
        raise HTTPException(500, "Failed to submit governance ticket for funding application creation") from exc
    return app_obj


@router.get("/application/{application_id}")
async def get_application(application_id: str):
    try:
        return _service.get_application(application_id)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/application/{application_id}/documents")
async def get_application_documents(application_id: str):
    try:
        return _service.get_application_documents(application_id)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/application/{application_id}/review")
async def review_application(application_id: str, body: ApplicationReviewRequest):
    try:
        return _service.review_application(application_id, body.review_modes)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/application/{application_id}/export")
async def export_application(application_id: str):
    try:
        return _service.export_application(application_id)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/application/{application_id}/export/{artifact_type}")
async def download_application_export(application_id: str, artifact_type: str):
    try:
        artifact_path = _service.get_application_export_file(application_id, artifact_type)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    artifact = artifact_type.strip().lower()
    return FileResponse(
        artifact_path,
        media_type=EXPORT_ARTIFACT_MEDIA_TYPES.get(artifact, "application/octet-stream"),
        filename=artifact_path.name,
    )


@router.post("/submission/prepare")
async def prepare_submission(body: SubmissionPrepareRequest, request: Request):
    try:
        return _service.prepare_submission(body.application_id, body.portal_url, resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.post("/submission/fill")
async def fill_submission(body: SubmissionFillRequest, request: Request):
    try:
        return _service.fill_submission(body.session_id, resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.post("/submission/save-draft")
async def save_submission_draft(body: SubmissionSaveDraftRequest, request: Request):
    try:
        return _service.save_draft(body.session_id, resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.get("/submission/preview")
async def preview_submission(request: Request, session_id: str = Query(...)):
    try:
        return _service.preview_submission(session_id, resolve_actor(request))
    except ValueError as exc:
        _raise_http(exc)


@router.post("/submission/request-approval")
async def request_submission_approval(body: SubmissionApprovalRequest, request: Request):
    try:
        actor = body.requested_by or resolve_actor(request)
        return _service.request_approval(body.session_id, body.action_type, actor, body.notes)
    except ValueError as exc:
        _raise_http(exc)


@router.post("/submission/submit")
async def submit_application(body: SubmissionFinalizeRequest):
    try:
        return _service.submit(
            body.session_id,
            body.approved_by,
            body.confirm_legal,
            body.confirm_budget,
            body.confirm_documents,
            body.portal_submission_reference,
        )
    except ValueError as exc:
        _raise_http(exc)
        return


@router.get("/submission/receipt")
async def get_submission_receipt(session_id: str = Query(...)):
    try:
        return _service.get_submission_receipt(session_id)
    except ValueError as exc:
        _raise_http(exc)


@router.get("/submission/sessions")
async def list_submission_sessions(application_id: str | None = None):
    return _service.list_submission_sessions(application_id)


@router.get("/submission/approvals")
async def list_submission_approvals(application_id: str | None = None, session_id: str | None = None):
    return _service.list_submission_approvals(application_id, session_id)


@router.get("/crm/applications")
async def list_crm_applications(company_id: str = "default"):
    return _service.list_crm_applications(company_id)


@router.get("/deadlines")
async def list_deadlines(company_id: str = "default"):
    return _service.list_deadlines(company_id)


@router.get("/alerts")
async def list_alerts(company_id: str = "default"):
    return _service.list_alerts(company_id)


@router.get("/reports/executive")
async def get_executive_report(company_id: str = "default"):
    try:
        return _service.get_executive_report(company_id)
    except ValueError as exc:
        _raise_http(exc)


# ---------------------------------------------------------------------------
# Scanner routes (K1.1)
# ---------------------------------------------------------------------------

_scan_job_status: dict[str, dict] = {}


@router.post("/scan/trigger")
async def trigger_scan(force_refresh: bool = False, since_days: int = 30):
    """Trigger an async funding programme scan."""
    import uuid
    job_id = f"scan_{uuid.uuid4().hex[:12]}"
    try:
        calls = scan_all(since_days=since_days, force_refresh=force_refresh)
        ticket_id = None
        try:
            ticket_id = submit_scan_ticket(
                job_id=job_id,
                force_refresh=force_refresh,
                since_days=since_days,
                calls_found=len(calls),
            )
        except Exception as exc:
            raise HTTPException(500, "Failed to submit governance ticket for funding scan") from exc
        _scan_job_status[job_id] = {
            "status": "completed",
            "calls_found": len(calls),
            "since_days": since_days,
            "force_refresh": force_refresh,
            "governance_ticket_id": ticket_id,
        }
        return {
            "job_id": job_id,
            "status": "completed",
            "calls_found": len(calls),
            "governance_ticket_id": ticket_id,
        }
    except Exception as exc:
        _scan_job_status[job_id] = {"status": "failed", "error": str(exc)}
        raise HTTPException(500, str(exc))


@router.get("/scan/status/{job_id}")
async def get_scan_status(job_id: str):
    """Get status of a scan job."""
    status = _scan_job_status.get(job_id)
    if not status:
        raise HTTPException(404, f"Job {job_id} not found")
    return {"job_id": job_id, **status}
