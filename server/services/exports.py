import re
from io import BytesIO
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from sqlalchemy import select
from sqlalchemy.orm import Session

from models.priorauth import (
    Document,
    DraftLetter,
    EvidenceMatch,
    ExportArtifact,
    PriorAuthCase,
    ReadinessReport,
)
from services.audit import log_audit_event


EXPORT_NOTICE = (
    "Synthetic/de-identified use only. Clinician review is required before submission. "
    "This export does not diagnose, recommend treatment, or guarantee payer approval."
)
PDF_MIME_TYPE = "application/pdf"


def _inline_pdf_markup(text: str) -> str:
    escaped = escape(text)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)


def _pdf_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#54615a"))
    canvas.drawString(0.75 * inch, 0.45 * inch, "AuthLens PriorAuth Evidence Copilot")
    canvas.drawRightString(7.75 * inch, 0.45 * inch, f"Page {doc.page}")
    canvas.restoreState()


def render_export_pdf(content_markdown: str) -> bytes:
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "AuthLensHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0f2621"),
        spaceAfter=10,
    )
    subheading = ParagraphStyle(
        "AuthLensSubheading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#0f2621"),
        spaceBefore=8,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "AuthLensBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1f2e29"),
        spaceAfter=5,
    )
    bullet = ParagraphStyle(
        "AuthLensBullet",
        parent=body,
        leftIndent=14,
        firstLineIndent=-8,
        spaceAfter=4,
    )
    story = []
    for raw_line in content_markdown.splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 5))
        elif line.startswith("# "):
            story.append(Paragraph(_inline_pdf_markup(line[2:]), heading))
        elif line.startswith("## "):
            story.append(Paragraph(_inline_pdf_markup(line[3:]), subheading))
        elif line.startswith("- "):
            story.append(Paragraph(_inline_pdf_markup(line[2:]), bullet, bulletText="-"))
        else:
            story.append(Paragraph(_inline_pdf_markup(line), body))

    if not story:
        story.append(Paragraph("No export content generated.", body))

    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title="AuthLens export",
        pageCompression=0,
    )
    document.build(story, onFirstPage=_pdf_footer, onLaterPages=_pdf_footer)
    return buffer.getvalue()


def _case(db: Session, case_id: str, organization_id: str) -> PriorAuthCase:
    case = db.scalar(
        select(PriorAuthCase).where(
            PriorAuthCase.id == case_id,
            PriorAuthCase.organization_id == organization_id,
        )
    )
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-").lower()
    return slug or "prior-auth-case"


def _latest_report(db: Session, case_id: str, organization_id: str) -> ReadinessReport:
    report = db.scalar(
        select(ReadinessReport)
        .where(
            ReadinessReport.case_id == case_id,
            ReadinessReport.organization_id == organization_id,
        )
        .order_by(ReadinessReport.created_at.desc())
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Generate a readiness report before exporting")
    return report


def _latest_approved_draft(db: Session, case_id: str, organization_id: str) -> DraftLetter:
    draft = db.scalar(
        select(DraftLetter)
        .where(
            DraftLetter.case_id == case_id,
            DraftLetter.organization_id == organization_id,
            DraftLetter.letter_type == "prior_auth",
            DraftLetter.status == "approved",
        )
        .order_by(DraftLetter.approved_at.desc(), DraftLetter.updated_at.desc())
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approved draft required before export")
    return draft


def _documents(db: Session, case_id: str, organization_id: str) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .where(Document.case_id == case_id, Document.organization_id == organization_id)
            .order_by(Document.created_at)
        )
    )


def _citation_backed_matches(db: Session, case_id: str, organization_id: str) -> list[EvidenceMatch]:
    matches = list(
        db.scalars(
            select(EvidenceMatch)
            .where(EvidenceMatch.case_id == case_id, EvidenceMatch.organization_id == organization_id)
            .order_by(EvidenceMatch.created_at)
        )
    )
    return [
        match
        for match in matches
        if (match.reviewer_override_status or match.status) == "met"
        and match.source_file.strip()
        and match.source_page.strip()
        and match.source_quote.strip()
        and match.why_it_matters.strip()
    ]


def _document_manifest(documents: list[Document]) -> list[dict]:
    return [
        {
            "document_id": document.id,
            "file_name": document.file_name,
            "document_type": document.document_type,
            "page_count": document.page_count,
            "sha256": document.sha256,
        }
        for document in documents
    ]


def _citation_manifest(matches: list[EvidenceMatch]) -> list[dict]:
    return [
        {
            "evidence_match_id": match.id,
            "criterion_id": match.criterion_id,
            "source_file": match.source_file,
            "source_page": match.source_page,
            "source_quote": match.source_quote,
        }
        for match in matches
    ]


def _store_export(
    db: Session,
    *,
    case: PriorAuthCase,
    organization_id: str,
    user_id: str,
    export_type: str,
    file_name: str,
    content_markdown: str,
    manifest_json: dict,
) -> ExportArtifact:
    artifact = ExportArtifact(
        organization_id=organization_id,
        case_id=case.id,
        created_by_user_id=user_id,
        export_type=export_type,
        status="ready",
        file_name=file_name,
        mime_type=PDF_MIME_TYPE,
        content_markdown=content_markdown,
        manifest_json=manifest_json,
    )
    db.add(artifact)
    db.flush()
    if export_type == "packet":
        case.status = "exported"
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=case.id,
        user_id=user_id,
        action="export.created",
        entity_type="export_artifact",
        entity_id=artifact.id,
        metadata={"export_type": export_type, "file_name": file_name},
    )
    db.commit()
    db.refresh(artifact)
    return artifact


def create_readiness_export(db: Session, *, case_id: str, organization_id: str, user_id: str) -> ExportArtifact:
    case = _case(db, case_id, organization_id)
    report = _latest_report(db, case.id, organization_id)
    content = "\n".join(
        [
            f"# Readiness Report: {case.patient_label}",
            "",
            EXPORT_NOTICE,
            "",
            f"Requested service: {case.requested_service}",
            f"Readiness score: {report.readiness_score}",
            f"Overall status: {report.overall_status}",
            "",
            report.summary,
            "",
            "Recommended next steps:",
            *[f"- {step}" for step in report.recommended_next_steps],
        ]
    )
    manifest = {
        "synthetic_only": True,
        "export_type": "readiness_report",
        "case_id": case.id,
        "readiness_report_id": report.id,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _store_export(
        db,
        case=case,
        organization_id=organization_id,
        user_id=user_id,
        export_type="readiness_report",
        file_name=f"{_slug(case.patient_label)}-readiness-report.pdf",
        content_markdown=content,
        manifest_json=manifest,
    )


def create_letter_export(db: Session, *, case_id: str, organization_id: str, user_id: str) -> ExportArtifact:
    case = _case(db, case_id, organization_id)
    draft = _latest_approved_draft(db, case.id, organization_id)
    content = "\n".join(
        [
            f"# Prior Authorization Letter: {case.patient_label}",
            "",
            EXPORT_NOTICE,
            "",
            draft.content_markdown,
        ]
    )
    manifest = {
        "synthetic_only": True,
        "export_type": "letter",
        "case_id": case.id,
        "draft_letter_id": draft.id,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _store_export(
        db,
        case=case,
        organization_id=organization_id,
        user_id=user_id,
        export_type="letter",
        file_name=f"{_slug(case.patient_label)}-prior-auth-letter.pdf",
        content_markdown=content,
        manifest_json=manifest,
    )


def create_packet_export(db: Session, *, case_id: str, organization_id: str, user_id: str) -> ExportArtifact:
    case = _case(db, case_id, organization_id)
    report = _latest_report(db, case.id, organization_id)
    draft = _latest_approved_draft(db, case.id, organization_id)
    documents = _documents(db, case.id, organization_id)
    citations = _citation_backed_matches(db, case.id, organization_id)
    document_manifest = _document_manifest(documents)
    citation_manifest = _citation_manifest(citations)
    content = "\n".join(
        [
            f"# Prior Authorization Packet: {case.patient_label}",
            "",
            EXPORT_NOTICE,
            "",
            "## Readiness Summary",
            f"- Score: {report.readiness_score}",
            f"- Status: {report.overall_status}",
            f"- Summary: {report.summary}",
            "",
            "## Approved Draft",
            draft.content_markdown,
            "",
            "## Document Manifest",
            *[f"- {item['file_name']} ({item['document_type']}, pages: {item['page_count'] or 'unknown'})" for item in document_manifest],
            "",
            "## Verified Citations",
            *[f"- {item['source_file']}, page {item['source_page']}: {item['source_quote']}" for item in citation_manifest],
        ]
    )
    manifest = {
        "synthetic_only": True,
        "export_type": "packet",
        "case_id": case.id,
        "readiness_report_id": report.id,
        "draft_letter_id": draft.id,
        "documents": document_manifest,
        "citations": citation_manifest,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    return _store_export(
        db,
        case=case,
        organization_id=organization_id,
        user_id=user_id,
        export_type="packet",
        file_name=f"{_slug(case.patient_label)}-prior-auth-packet.pdf",
        content_markdown=content,
        manifest_json=manifest,
    )


def get_export(db: Session, *, export_id: str, organization_id: str) -> ExportArtifact:
    artifact = db.scalar(
        select(ExportArtifact).where(
            ExportArtifact.id == export_id,
            ExportArtifact.organization_id == organization_id,
        )
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return artifact
