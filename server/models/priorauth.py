from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(64), nullable=False, default="demo")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("user"))
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("mem"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (Index("ix_membership_user_org", "user_id", "organization_id", unique=True),)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("reset"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PriorAuthCase(Base, TimestampMixin):
    __tablename__ = "prior_auth_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("case"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    patient_label: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    specialty: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_service: Mapped[str] = mapped_column(String(255), nullable=False)
    service_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_type: Mapped[str] = mapped_column(String(64), nullable=False, default="prior_auth")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft", index=True)
    readiness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_cases_org_status", "organization_id", "status"),)


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("doc"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    uploaded_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processing_status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending", index=True)
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False, default="text")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_documents_case_type", "case_id", "document_type"),)


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("page"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extraction_method: Mapped[str] = mapped_column(String(64), nullable=False, default="text")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("chunk"))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    section_heading: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vector_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (Index("ix_chunks_case_type", "case_id", "document_type"),)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("run"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    run_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="completed")
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PolicyCriterion(Base, TimestampMixin):
    __tablename__ = "policy_criteria"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("crit"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    criterion_code: Mapped[str] = mapped_column(String(32), nullable=False)
    criterion_type: Mapped[str] = mapped_column(String(64), nullable=False, default="medical_necessity")
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    required_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    source_page: Mapped[str] = mapped_column(String(64), nullable=False)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ambiguity_notes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    extraction_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reviewer_status: Mapped[str] = mapped_column(String(64), nullable=False, default="unreviewed")

    __table_args__ = (Index("ix_criteria_case_code", "case_id", "criterion_code"),)


class EvidenceMatch(Base, TimestampMixin):
    __tablename__ = "evidence_matches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("match"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    criterion_id: Mapped[str] = mapped_column(ForeignKey("policy_criteria.id"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("document_chunks.id"), nullable=True)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_page: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    source_quote: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=False, default="")
    missing_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    conflicting_evidence: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewer_override_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReadinessReport(Base):
    __tablename__ = "readiness_reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("report"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    analysis_run_id: Mapped[str | None] = mapped_column(ForeignKey("analysis_runs.id"), nullable=True)
    readiness_score: Mapped[float] = mapped_column(Float, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    highest_risk_items: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommended_next_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DraftLetter(Base, TimestampMixin):
    __tablename__ = "draft_letters"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("draft"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    letter_type: Mapped[str] = mapped_column(String(64), nullable=False, default="prior_auth")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_report_id: Mapped[str | None] = mapped_column(ForeignKey("readiness_reports.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, default="ai")
    reviewed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CitationCheck(Base):
    __tablename__ = "citation_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("cite"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    draft_letter_id: Mapped[str] = mapped_column(ForeignKey("draft_letters.id"), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(64), nullable=False)
    unsupported_claims: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    weakly_supported_claims: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    citation_errors: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    safe_to_show_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExportArtifact(Base):
    __tablename__ = "export_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("export"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    export_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="application/pdf")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (Index("ix_exports_case_type", "case_id", "export_type"),)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("audit"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(64), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
