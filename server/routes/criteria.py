from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import PolicyCriterion
from modules.schemas import CriteriaListResponse, CriterionResponse, CriterionUpdateRequest
from services.priorauth_analysis import extract_criteria, list_criteria, update_criterion


router = APIRouter()


def criterion_response(criterion: PolicyCriterion) -> CriterionResponse:
    return CriterionResponse(
        id=criterion.id,
        criterion_code=criterion.criterion_code,
        criterion_type=criterion.criterion_type,
        requirement=criterion.requirement,
        required_evidence=criterion.required_evidence,
        is_required=criterion.is_required,
        source_file=criterion.source_file,
        source_page=criterion.source_page,
        source_quote=criterion.source_quote,
        confidence=criterion.confidence,
        ambiguity_notes=criterion.ambiguity_notes,
        reviewer_status=criterion.reviewer_status,
    )


@router.post("/cases/{case_id}/criteria/extract", response_model=CriteriaListResponse)
async def extract_case_criteria(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    criteria = extract_criteria(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return CriteriaListResponse(criteria=[criterion_response(criterion) for criterion in criteria])


@router.get("/cases/{case_id}/criteria", response_model=CriteriaListResponse)
async def get_case_criteria(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    criteria = list_criteria(db, case_id=case_id, organization_id=current_user.organization_id)
    return CriteriaListResponse(criteria=[criterion_response(criterion) for criterion in criteria])


@router.patch("/criteria/{criterion_id}", response_model=CriterionResponse)
async def edit_criterion(
    criterion_id: str,
    payload: CriterionUpdateRequest,
    current_user: CurrentUser = Depends(require_roles("admin", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    criterion = update_criterion(
        db,
        criterion_id=criterion_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return criterion_response(criterion)
