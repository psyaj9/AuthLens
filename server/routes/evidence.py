from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import EvidenceMatch
from modules.schemas import EvidenceListResponse, EvidenceMatchResponse, EvidenceOverrideRequest
from services.priorauth_analysis import list_matches, match_evidence, update_match_override


router = APIRouter()


def evidence_response(match: EvidenceMatch) -> EvidenceMatchResponse:
    return EvidenceMatchResponse(
        id=match.id,
        criterion_id=match.criterion_id,
        status=match.status,
        evidence_summary=match.evidence_summary,
        source_file=match.source_file,
        source_page=match.source_page,
        source_quote=match.source_quote,
        why_it_matters=match.why_it_matters,
        missing_evidence=match.missing_evidence,
        conflicting_evidence=match.conflicting_evidence,
        recommended_action=match.recommended_action,
        confidence=match.confidence,
        reviewer_override_status=match.reviewer_override_status,
        reviewer_override_reason=match.reviewer_override_reason,
    )


@router.post("/cases/{case_id}/evidence/match", response_model=EvidenceListResponse)
async def match_case_evidence(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    matches = match_evidence(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return EvidenceListResponse(matches=[evidence_response(match) for match in matches])


@router.get("/cases/{case_id}/evidence", response_model=EvidenceListResponse)
async def get_case_evidence(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    matches = list_matches(db, case_id=case_id, organization_id=current_user.organization_id)
    return EvidenceListResponse(matches=[evidence_response(match) for match in matches])


@router.patch("/evidence-matches/{match_id}", response_model=EvidenceMatchResponse)
async def override_evidence_match(
    match_id: str,
    payload: EvidenceOverrideRequest,
    current_user: CurrentUser = Depends(require_roles("admin", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    match = update_match_override(
        db,
        match_id=match_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        status_value=payload.reviewer_override_status,
        reason=payload.reviewer_override_reason,
    )
    return evidence_response(match)
