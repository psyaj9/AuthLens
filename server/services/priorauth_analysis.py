import re
from datetime import UTC, datetime
from math import floor

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from models.priorauth import (
    AnalysisRun,
    CitationCheck,
    Document,
    DocumentChunk,
    DraftLetter,
    EvidenceMatch,
    PolicyCriterion,
    PriorAuthCase,
    ReadinessReport,
)
from services.audit import log_audit_event


PATIENT_DOCUMENT_TYPES = {
    "patient_note",
    "lab_result",
    "imaging_report",
    "medication_history",
    "referral_letter",
    "other",
}
STOPWORDS = {
    "and",
    "are",
    "before",
    "coverage",
    "documented",
    "documents",
    "for",
    "must",
    "of",
    "or",
    "requires",
    "the",
    "with",
}
BANNED_DRAFT_TERMS = {"guaranteed approval", "must approve", "approved for coverage", "this patient qualifies"}
REQUIRED_DRAFT_DISCLAIMER = "clinician review is required"


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


def _chunks(db: Session, *, case_id: str, organization_id: str, document_types: set[str]) -> list[DocumentChunk]:
    return list(
        db.scalars(
            select(DocumentChunk)
            .where(
                DocumentChunk.case_id == case_id,
                DocumentChunk.organization_id == organization_id,
                DocumentChunk.document_type.in_(document_types),
            )
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
    )


def _document(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _keywords(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
        if word not in STOPWORDS
    }


def _short_quote(text: str, limit: int = 220) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:limit]


def _effective_match_status(match: EvidenceMatch) -> str:
    return match.reviewer_override_status or match.status


def _has_required_citation(match: EvidenceMatch) -> bool:
    return all(
        value.strip()
        for value in [
            match.source_file,
            match.source_page,
            match.source_quote,
            match.why_it_matters,
        ]
    )


def _is_citation_backed_met(match: EvidenceMatch) -> bool:
    return _effective_match_status(match) == "met" and _has_required_citation(match)


def extract_criteria(db: Session, *, case_id: str, organization_id: str, user_id: str) -> list[PolicyCriterion]:
    case = _case(db, case_id, organization_id)
    policy_chunks = _chunks(
        db,
        case_id=case.id,
        organization_id=organization_id,
        document_types={"payer_policy"},
    )
    if not policy_chunks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a payer policy before extraction")

    run = AnalysisRun(
        organization_id=organization_id,
        case_id=case.id,
        run_type="criteria_extraction",
        status="completed",
        model_version="deterministic-mvp",
    )
    db.add(run)
    db.flush()

    candidates: list[tuple[DocumentChunk, str]] = []
    for chunk in policy_chunks:
        for sentence in _sentences(chunk.text):
            if re.search(r"\b(require|requires|required|must|document|criteria|coverage)\b", sentence, re.I):
                candidates.append((chunk, sentence))
    if not candidates:
        candidates = [(policy_chunks[0], policy_chunks[0].text or "Policy criteria were not clearly stated.")]

    db.execute(
        delete(PolicyCriterion).where(
            PolicyCriterion.case_id == case.id,
            PolicyCriterion.organization_id == organization_id,
        )
    )
    criteria: list[PolicyCriterion] = []
    for index, (chunk, sentence) in enumerate(candidates[:8], start=1):
        document = _document(db, chunk.document_id)
        criterion = PolicyCriterion(
            organization_id=organization_id,
            case_id=case.id,
            analysis_run_id=run.id,
            criterion_code=f"C{index}",
            criterion_type="documentation" if re.search(r"\bdocument", sentence, re.I) else "medical_necessity",
            requirement=sentence.rstrip(".") + ".",
            required_evidence=[f"Documentation supporting: {_short_quote(sentence, 90)}"],
            is_required=True,
            source_document_id=document.id,
            source_file=document.file_name,
            source_page=str(chunk.page_start),
            source_quote=_short_quote(sentence),
            confidence=0.82,
            ambiguity_notes=[],
            extraction_version=1,
        )
        db.add(criterion)
        criteria.append(criterion)

    case.status = "criteria_extracted"
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=case.id,
        user_id=user_id,
        action="criteria.extracted",
        entity_type="case",
        entity_id=case.id,
        metadata={"criteria_count": len(criteria)},
    )
    db.commit()
    for criterion in criteria:
        db.refresh(criterion)
    return criteria


def list_criteria(db: Session, *, case_id: str, organization_id: str) -> list[PolicyCriterion]:
    _case(db, case_id, organization_id)
    return list(
        db.scalars(
            select(PolicyCriterion)
            .where(PolicyCriterion.case_id == case_id, PolicyCriterion.organization_id == organization_id)
            .order_by(PolicyCriterion.criterion_code)
        )
    )


def update_criterion(
    db: Session,
    *,
    criterion_id: str,
    organization_id: str,
    user_id: str,
    changes: dict,
) -> PolicyCriterion:
    criterion = db.scalar(
        select(PolicyCriterion).where(
            PolicyCriterion.id == criterion_id,
            PolicyCriterion.organization_id == organization_id,
        )
    )
    if criterion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Criterion not found")

    allowed_fields = {"requirement", "required_evidence", "is_required", "ambiguity_notes", "reviewer_status"}
    applied_fields = []
    for field, value in changes.items():
        if field in allowed_fields:
            setattr(criterion, field, value)
            applied_fields.append(field)
    if applied_fields:
        criterion.extraction_version += 1
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=criterion.case_id,
        user_id=user_id,
        action="criteria.updated",
        entity_type="policy_criterion",
        entity_id=criterion.id,
        metadata={"updated_fields": sorted(applied_fields), "extraction_version": criterion.extraction_version},
    )
    db.commit()
    db.refresh(criterion)
    return criterion


def match_evidence(db: Session, *, case_id: str, organization_id: str, user_id: str) -> list[EvidenceMatch]:
    case = _case(db, case_id, organization_id)
    criteria = list_criteria(db, case_id=case.id, organization_id=organization_id)
    if not criteria:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Extract criteria before matching evidence")
    patient_chunks = _chunks(
        db,
        case_id=case.id,
        organization_id=organization_id,
        document_types=PATIENT_DOCUMENT_TYPES,
    )

    run = AnalysisRun(
        organization_id=organization_id,
        case_id=case.id,
        run_type="evidence_matching",
        status="completed",
        model_version="deterministic-mvp",
    )
    db.add(run)
    db.flush()
    db.execute(
        delete(EvidenceMatch).where(
            EvidenceMatch.case_id == case.id,
            EvidenceMatch.organization_id == organization_id,
        )
    )

    matches: list[EvidenceMatch] = []
    for criterion in criteria:
        criterion_terms = _keywords(criterion.requirement)
        best_chunk = None
        best_score = 0
        for chunk in patient_chunks:
            score = len(criterion_terms.intersection(_keywords(chunk.text)))
            if score > best_score:
                best_score = score
                best_chunk = chunk

        if best_chunk is not None and best_score >= 2 and best_chunk.text.strip():
            document = _document(db, best_chunk.document_id)
            match = EvidenceMatch(
                organization_id=organization_id,
                case_id=case.id,
                criterion_id=criterion.id,
                analysis_run_id=run.id,
                status="met",
                evidence_summary=f"The provided patient documentation appears to support {criterion.criterion_code}.",
                source_document_id=document.id,
                source_chunk_id=best_chunk.id,
                source_file=document.file_name,
                source_page=str(best_chunk.page_start),
                source_quote=_short_quote(best_chunk.text),
                why_it_matters="This source quote is tied to the payer criterion and should be reviewed by a clinician.",
                missing_evidence=[],
                conflicting_evidence=[],
                recommended_action="Clinician reviewer should confirm the cited evidence before submission.",
                confidence=min(0.95, 0.55 + best_score / 10),
                model_version="deterministic-mvp",
            )
        else:
            match = EvidenceMatch(
                organization_id=organization_id,
                case_id=case.id,
                criterion_id=criterion.id,
                analysis_run_id=run.id,
                status="not_found",
                evidence_summary=f"No patient documentation was found for {criterion.criterion_code}.",
                source_file="",
                source_page="",
                source_quote="",
                why_it_matters="Required evidence must be cited before this criterion can be considered supported.",
                missing_evidence=criterion.required_evidence,
                conflicting_evidence=[],
                recommended_action=f"Add documentation for: {', '.join(criterion.required_evidence)}.",
                confidence=0.7,
                model_version="deterministic-mvp",
            )
        db.add(match)
        matches.append(match)

    case.status = "evidence_matched"
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=case.id,
        user_id=user_id,
        action="evidence.matched",
        entity_type="case",
        entity_id=case.id,
        metadata={"match_count": len(matches)},
    )
    db.commit()
    for match in matches:
        db.refresh(match)
    return matches


def list_matches(db: Session, *, case_id: str, organization_id: str) -> list[EvidenceMatch]:
    _case(db, case_id, organization_id)
    return list(
        db.scalars(
            select(EvidenceMatch)
            .where(EvidenceMatch.case_id == case_id, EvidenceMatch.organization_id == organization_id)
            .order_by(EvidenceMatch.created_at)
        )
    )


def update_match_override(
    db: Session,
    *,
    match_id: str,
    organization_id: str,
    user_id: str,
    status_value: str,
    reason: str,
) -> EvidenceMatch:
    match = db.scalar(
        select(EvidenceMatch).where(
            EvidenceMatch.id == match_id,
            EvidenceMatch.organization_id == organization_id,
        )
    )
    if match is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence match not found")
    if status_value == "met" and not _has_required_citation(match):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A met override requires source quote, file, page, and rationale",
        )
    match.reviewer_override_status = status_value
    match.reviewer_override_reason = reason
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=match.case_id,
        user_id=user_id,
        action="evidence.override",
        entity_type="evidence_match",
        entity_id=match.id,
        metadata={"override_status": status_value},
    )
    db.commit()
    db.refresh(match)
    return match


def generate_readiness_report(db: Session, *, case_id: str, organization_id: str, user_id: str) -> ReadinessReport:
    case = _case(db, case_id, organization_id)
    criteria = list_criteria(db, case_id=case.id, organization_id=organization_id)
    matches = list_matches(db, case_id=case.id, organization_id=organization_id)
    if not criteria or not matches:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Run criteria extraction and evidence matching first")

    matches_by_criterion = {match.criterion_id: match for match in matches}
    possible = 0.0
    earned = 0.0
    missing_items: list[str] = []
    for criterion in criteria:
        weight = 2.0 if criterion.is_required else 1.0
        possible += weight
        match = matches_by_criterion.get(criterion.id)
        status_value = _effective_match_status(match) if match else "not_found"
        if match is not None and _is_citation_backed_met(match):
            earned += weight
        elif status_value == "unclear":
            earned += weight * 0.5
            missing_items.append(f"{criterion.criterion_code}: {criterion.requirement}")
        else:
            missing_items.append(f"{criterion.criterion_code}: {criterion.requirement}")

    score = floor(100 * earned / possible) if possible else 0
    if score >= 85 and not missing_items:
        overall_status = "ready_for_review"
    else:
        overall_status = "needs_more_documentation"

    run = AnalysisRun(
        organization_id=organization_id,
        case_id=case.id,
        run_type="readiness_report",
        status="completed",
        model_version="deterministic-mvp",
    )
    db.add(run)
    db.flush()
    report_json = {
        "met_count": sum(1 for match in matches if _is_citation_backed_met(match)),
        "missing_or_unclear_items": missing_items,
        "score_interpretation": "documentation completeness only",
    }
    report = ReadinessReport(
        organization_id=organization_id,
        case_id=case.id,
        analysis_run_id=run.id,
        readiness_score=score,
        overall_status=overall_status,
        summary=f"This readiness score reflects documentation completeness only: {score} out of 100.",
        highest_risk_items=missing_items[:5],
        recommended_next_steps=missing_items[:5] or ["Clinician reviewer should confirm citations before submission."],
        report_json=report_json,
    )
    db.add(report)
    case.readiness_score = score
    case.status = overall_status
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=case.id,
        user_id=user_id,
        action="readiness.generated",
        entity_type="readiness_report",
        entity_id=report.id,
        metadata={"readiness_score": score, "overall_status": overall_status},
    )
    db.commit()
    db.refresh(report)
    return report


def latest_report(db: Session, *, case_id: str, organization_id: str) -> ReadinessReport:
    _case(db, case_id, organization_id)
    report = db.scalar(
        select(ReadinessReport)
        .where(ReadinessReport.case_id == case_id, ReadinessReport.organization_id == organization_id)
        .order_by(ReadinessReport.created_at.desc())
    )
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Readiness report not found")
    return report


def create_prior_auth_draft(db: Session, *, case_id: str, organization_id: str, user_id: str) -> DraftLetter:
    case = _case(db, case_id, organization_id)
    report = latest_report(db, case_id=case.id, organization_id=organization_id)
    matches = [
        match
        for match in list_matches(db, case_id=case.id, organization_id=organization_id)
        if _is_citation_backed_met(match)
    ]
    lines = [
        f"Subject: Prior authorization request for {case.requested_service}",
        "",
        f"This draft is prepared for clinician review for synthetic case {case.patient_label}.",
        "",
        "Payer criteria addressed:",
    ]
    for match in matches:
        lines.append(
            f"- The provided documents indicate supporting evidence: {match.evidence_summary} "
            f"[{match.source_file}, page {match.source_page}]"
        )
    if report.highest_risk_items:
        lines.append("")
        lines.append("Missing or unclear documentation to review before submission:")
        for item in report.highest_risk_items:
            lines.append(f"- {item}")
    lines.extend(
        [
            "",
            "Clinician review is required before submission. This draft does not diagnose, recommend treatment, or guarantee payer approval.",
        ]
    )
    draft = DraftLetter(
        organization_id=organization_id,
        case_id=case.id,
        letter_type="prior_auth",
        status="draft",
        content_markdown="\n".join(lines),
        model_version="deterministic-mvp",
        source_report_id=report.id,
        created_by="ai",
    )
    db.add(draft)
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=case.id,
        user_id=user_id,
        action="draft.generated",
        entity_type="draft_letter",
        entity_id=draft.id,
        metadata={"letter_type": "prior_auth"},
    )
    db.commit()
    db.refresh(draft)
    return draft


def get_draft(db: Session, *, draft_id: str, organization_id: str) -> DraftLetter:
    draft = db.scalar(
        select(DraftLetter).where(
            DraftLetter.id == draft_id,
            DraftLetter.organization_id == organization_id,
        )
    )
    if draft is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return draft


def list_drafts(db: Session, *, case_id: str, organization_id: str) -> list[DraftLetter]:
    _case(db, case_id, organization_id)
    return list(
        db.scalars(
            select(DraftLetter)
            .where(DraftLetter.case_id == case_id, DraftLetter.organization_id == organization_id)
            .order_by(DraftLetter.created_at.desc())
        )
    )


def update_draft(db: Session, *, draft_id: str, organization_id: str, user_id: str, content: str) -> DraftLetter:
    draft = get_draft(db, draft_id=draft_id, organization_id=organization_id)
    draft.content_markdown = content
    draft.status = "needs_revision"
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=draft.case_id,
        user_id=user_id,
        action="draft.edited",
        entity_type="draft_letter",
        entity_id=draft.id,
    )
    db.commit()
    db.refresh(draft)
    return draft


def verify_citations(db: Session, *, draft_id: str, organization_id: str, user_id: str) -> CitationCheck:
    draft = get_draft(db, draft_id=draft_id, organization_id=organization_id)
    matches = list_matches(db, case_id=draft.case_id, organization_id=organization_id)
    valid_citations = {
        f"{match.source_file}, page {match.source_page}".lower()
        for match in matches
        if _is_citation_backed_met(match)
    }
    found_citations = {citation.lower() for citation in re.findall(r"\[([^\]]+)\]", draft.content_markdown)}
    citation_errors = [
        {"citation": citation, "issue": "Citation does not match verified evidence"}
        for citation in sorted(found_citations)
        if citation not in valid_citations
    ]
    unsupported_claims = []
    if "provided documents indicate" in draft.content_markdown.lower() and not found_citations:
        unsupported_claims.append(
            {
                "claim": "Draft references provided documents without citations",
                "issue": "Material claims require citations",
                "recommended_fix": "Add source file and page citation.",
            }
        )
    lowered = draft.content_markdown.lower()
    for term in BANNED_DRAFT_TERMS:
        if term in lowered:
            unsupported_claims.append(
                {
                    "claim": term,
                    "issue": "Draft contains prohibited clinical or approval language",
                    "recommended_fix": "Use documentation-support wording only.",
                }
            )
    if REQUIRED_DRAFT_DISCLAIMER not in lowered:
        unsupported_claims.append(
            {
                "claim": "human review disclaimer",
                "issue": "Draft is missing the required human review disclaimer",
                "recommended_fix": "Restore clinician review language before approval.",
            }
        )
    status_value = "pass" if not citation_errors and not unsupported_claims else "fail"
    check = CitationCheck(
        organization_id=organization_id,
        case_id=draft.case_id,
        draft_letter_id=draft.id,
        verification_status=status_value,
        unsupported_claims=unsupported_claims,
        weakly_supported_claims=[],
        citation_errors=citation_errors,
        safe_to_show_user=True,
    )
    db.add(check)
    draft.status = "ready_for_review" if status_value == "pass" else "needs_revision"
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=draft.case_id,
        user_id=user_id,
        action="citation.verified",
        entity_type="citation_check",
        entity_id=check.id,
        metadata={"verification_status": status_value},
    )
    db.commit()
    db.refresh(check)
    return check


def approve_draft(db: Session, *, draft_id: str, organization_id: str, user_id: str) -> DraftLetter:
    draft = get_draft(db, draft_id=draft_id, organization_id=organization_id)
    latest_check = db.scalar(
        select(CitationCheck)
        .where(CitationCheck.draft_letter_id == draft.id, CitationCheck.organization_id == organization_id)
        .order_by(CitationCheck.created_at.desc())
    )
    if draft.status != "ready_for_review":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft must be citation-verified after the latest edit")
    if latest_check is None or latest_check.verification_status != "pass":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Citation verification must pass before approval")
    draft.status = "approved"
    draft.reviewed_by_user_id = user_id
    draft.approved_at = datetime.now(UTC)
    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=draft.case_id,
        user_id=user_id,
        action="draft.approved",
        entity_type="draft_letter",
        entity_id=draft.id,
    )
    db.commit()
    db.refresh(draft)
    return draft
