from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str


class MessageResponse(BaseModel):
    message: str


class QueryResponse(BaseModel):
    response: str
    source_documents: list[str] = Field(default_factory=list)


class DependencyHealth(BaseModel):
    pinecone: str = "not_checked"
    groq: str = "not_checked"
    google: str = "not_checked"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "authlens-api"
    environment: str
    dependencies: DependencyHealth = Field(default_factory=DependencyHealth)


Role = Literal["admin", "coordinator", "clinician_reviewer", "viewer"]
CaseStatus = Literal[
    "draft",
    "documents_uploaded",
    "criteria_extracted",
    "evidence_matched",
    "needs_more_documentation",
    "ready_for_review",
    "review_in_progress",
    "approved_for_export",
    "exported",
    "archived",
]
CaseType = Literal["prior_auth", "appeal"]
DocumentType = Literal[
    "payer_policy",
    "patient_note",
    "lab_result",
    "imaging_report",
    "medication_history",
    "referral_letter",
    "denial_letter",
    "other",
]
EvidenceStatus = Literal["met", "unclear", "not_found", "not_met"]


class OrganizationSummary(BaseModel):
    id: str
    name: str
    plan: str = "demo"


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    organization: OrganizationSummary


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class CaseCreate(BaseModel):
    patient_label: str
    payer_name: str
    specialty: str
    requested_service: str
    service_code: str | None = None
    plan_name: str | None = None
    diagnosis_summary: str | None = None
    case_type: CaseType = "prior_auth"
    assigned_to_user_id: str | None = None


class CaseUpdate(BaseModel):
    patient_label: str | None = None
    payer_name: str | None = None
    specialty: str | None = None
    requested_service: str | None = None
    service_code: str | None = None
    plan_name: str | None = None
    diagnosis_summary: str | None = None
    assigned_to_user_id: str | None = None


class CaseResponse(BaseModel):
    id: str
    patient_label: str
    payer_name: str
    plan_name: str | None = None
    specialty: str
    requested_service: str
    service_code: str | None = None
    diagnosis_summary: str | None = None
    case_type: CaseType
    status: CaseStatus
    readiness_score: float | None = None
    missing_required_criteria_count: int = 0
    assigned_to_user_id: str | None = None
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    cases: list[CaseResponse]


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    document_type: DocumentType
    file_name: str
    sha256: str
    mime_type: str
    page_count: int | None = None
    processing_status: str
    extraction_method: str
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class CriterionResponse(BaseModel):
    id: str
    criterion_code: str
    criterion_type: str
    requirement: str
    required_evidence: list[str]
    is_required: bool
    source_file: str
    source_page: str
    source_quote: str
    confidence: float
    ambiguity_notes: list[str] = Field(default_factory=list)
    reviewer_status: str


class CriteriaListResponse(BaseModel):
    criteria: list[CriterionResponse]
    missing_or_ambiguous_policy_info: list[str] = Field(default_factory=list)


class EvidenceMatchResponse(BaseModel):
    id: str
    criterion_id: str
    status: EvidenceStatus
    evidence_summary: str
    source_file: str
    source_page: str
    source_quote: str
    why_it_matters: str
    missing_evidence: list[str]
    conflicting_evidence: list[str]
    recommended_action: str
    confidence: float
    reviewer_override_status: str | None = None
    reviewer_override_reason: str | None = None


class EvidenceListResponse(BaseModel):
    matches: list[EvidenceMatchResponse]


class EvidenceOverrideRequest(BaseModel):
    reviewer_override_status: EvidenceStatus
    reviewer_override_reason: str = Field(min_length=1)


class ReadinessReportResponse(BaseModel):
    id: str
    case_id: str
    readiness_score: float
    overall_status: str
    summary: str
    highest_risk_items: list[str]
    recommended_next_steps: list[str]
    report_json: dict
    created_at: datetime


class DraftLetterResponse(BaseModel):
    id: str
    case_id: str
    letter_type: str
    status: str
    content_markdown: str
    created_by: str
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DraftListResponse(BaseModel):
    drafts: list[DraftLetterResponse]


class DraftUpdateRequest(BaseModel):
    content_markdown: str


class CitationCheckResponse(BaseModel):
    id: str
    draft_letter_id: str
    verification_status: str
    unsupported_claims: list[dict]
    weakly_supported_claims: list[dict]
    citation_errors: list[dict]
    safe_to_show_user: bool
    created_at: datetime
