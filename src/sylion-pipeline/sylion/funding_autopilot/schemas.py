from __future__ import annotations

from pydantic import BaseModel, Field


class FundingCompanyProfileUpsert(BaseModel):
    company_id: str = "default"
    legal_name: str
    tax_id: str = ""
    registration_id: str = ""
    eu_vat: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    legal_form: str = ""
    established_at: str = ""
    sme_status: str = ""
    employees: int = 0
    annual_revenue: float = 0.0
    ebitda: float = 0.0
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    export_markets: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    products: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    patents: list[str] = Field(default_factory=list)
    team_competencies: list[str] = Field(default_factory=list)
    strategic_goals: list[str] = Field(default_factory=list)
    representative_name: str = ""
    representative_email: str = ""
    state_aid_total_eur: float = 0.0
    de_minimis_total_eur: float = 0.0
    prior_grants_count: int = 0
    notes: str = ""


class FundingRegistrySyncRequest(BaseModel):
    company_id: str = "default"
    krs: str
    apply_profile: bool = True


class FundingDocumentCreate(BaseModel):
    company_id: str = "default"
    document_type: str
    filename: str
    storage_path: str = ""
    status: str = "available"
    expires_at: float | None = None
    metadata: dict = Field(default_factory=dict)


class FundingProgrammeCreate(BaseModel):
    source_id: str = "manual"
    name: str
    country: str = ""
    region: str = ""
    institution: str = ""
    funding_type: str = ""
    summary: str = ""
    metadata: dict = Field(default_factory=dict)


class FundingCallCreate(BaseModel):
    programme_id: str
    title: str
    code: str = ""
    country: str = ""
    region: str = ""
    portal_url: str = ""
    opens_at: float | None = None
    closes_at: float | None = None
    min_project_budget: float = 0.0
    max_project_budget: float = 0.0
    grant_intensity_pct: float = 0.0
    trl_min: int = 0
    trl_max: int = 9
    requires_consortium: bool = False
    target_beneficiaries: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    required_partner_types: list[str] = Field(default_factory=list)
    eligible_costs: list[str] = Field(default_factory=list)
    evaluation_weights: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class FundingCallSearchRequest(BaseModel):
    query: str = ""
    company_id: str = "default"
    country: str = ""
    beneficiary_type: str = ""
    theme: str = ""
    budget_min: float | None = None
    budget_max: float | None = None
    open_only: bool = True


class GenerateFundingIdeasRequest(BaseModel):
    company_id: str = "default"
    limit: int = 5
    categories: list[str] = Field(default_factory=list)


class ConvertIdeaToProjectRequest(BaseModel):
    company_id: str = "default"
    call_id: str | None = None
    target_trl: int = 4


class CreateFundingProjectRequest(BaseModel):
    company_id: str = "default"
    title: str
    summary: str
    objective: str = ""
    category: str = ""
    budget_total: float = 0.0
    grant_requested: float = 0.0
    trl: int = 4
    target_markets: list[str] = Field(default_factory=list)
    partner_needs: list[str] = Field(default_factory=list)
    call_id: str | None = None


class RunMatchingRequest(BaseModel):
    project_id: str
    call_id: str | None = None
    top_k: int = 5


class EligibilityCheckRequest(BaseModel):
    project_id: str
    call_id: str | None = None


class RunScoringRequest(BaseModel):
    project_id: str
    call_id: str | None = None


class ConsortiumAnalyzeRequest(BaseModel):
    project_id: str


class ConsortiumCandidateInput(BaseModel):
    name: str
    partner_type: str
    country: str = ""
    expertise: list[str] = Field(default_factory=list)
    grant_track_record: int = 0
    contact_email: str = ""
    metadata: dict = Field(default_factory=dict)


class PartnerSearchRequest(BaseModel):
    project_id: str
    company_id: str = "default"
    partner_type: str = ""
    query: str = ""
    candidates: list[ConsortiumCandidateInput] = Field(default_factory=list)


class PartnerShortlistRequest(BaseModel):
    project_id: str
    limit: int = 5


class OutreachGenerateRequest(BaseModel):
    project_id: str
    partner_ids: list[str] = Field(default_factory=list)


class ApplicationCreateRequest(BaseModel):
    project_id: str
    company_id: str = "default"
    call_id: str | None = None


class ApplicationReviewRequest(BaseModel):
    review_modes: list[str] = Field(default_factory=lambda: ["formal", "financial", "technical", "market"])


class SubmissionPrepareRequest(BaseModel):
    application_id: str
    portal_url: str = ""


class SubmissionFillRequest(BaseModel):
    session_id: str


class SubmissionSaveDraftRequest(BaseModel):
    session_id: str


class SubmissionApprovalRequest(BaseModel):
    session_id: str
    action_type: str = "final_submit"
    requested_by: str = ""
    notes: str = ""


class SubmissionFinalizeRequest(BaseModel):
    session_id: str
    approved_by: str = ""
    confirm_legal: bool = False
    confirm_budget: bool = False
    confirm_documents: bool = False
    portal_submission_reference: str = ""


class ExecutiveReportRequest(BaseModel):
    company_id: str = "default"
