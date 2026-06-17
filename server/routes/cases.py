from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import EvidenceMatch, OrganizationMembership, PolicyCriterion, PriorAuthCase
from modules.schemas import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate
from services.audit import log_audit_event


router = APIRouter()


def _missing_required_count(db: Session, case_id: str) -> int:
    return db.scalar(
        select(func.count(PolicyCriterion.id))
        .outerjoin(EvidenceMatch, EvidenceMatch.criterion_id == PolicyCriterion.id)
        .where(
            PolicyCriterion.case_id == case_id,
            PolicyCriterion.is_required.is_(True),
            (EvidenceMatch.id.is_(None)) | (EvidenceMatch.status != "met"),
        )
    ) or 0


def case_response(db: Session, case: PriorAuthCase) -> CaseResponse:
    return CaseResponse(
        id=case.id,
        patient_label=case.patient_label,
        payer_name=case.payer_name,
        plan_name=case.plan_name,
        specialty=case.specialty,
        requested_service=case.requested_service,
        service_code=case.service_code,
        diagnosis_summary=case.diagnosis_summary,
        case_type=case.case_type,
        status=case.status,
        readiness_score=case.readiness_score,
        missing_required_criteria_count=_missing_required_count(db, case.id),
        assigned_to_user_id=case.assigned_to_user_id,
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def get_case_for_user(db: Session, case_id: str, current_user: CurrentUser) -> PriorAuthCase:
    case = db.scalar(
        select(PriorAuthCase).where(
            PriorAuthCase.id == case_id,
            PriorAuthCase.organization_id == current_user.organization_id,
        )
    )
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    return case


def validate_assignee(db: Session, assigned_to_user_id: str | None, organization_id: str) -> str | None:
    if assigned_to_user_id is None:
        return None
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == assigned_to_user_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned user must belong to the current organization",
        )
    return assigned_to_user_id


@router.post("/cases", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    payload: CaseCreate,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    case = PriorAuthCase(
        organization_id=current_user.organization_id,
        created_by_user_id=current_user.user_id,
        assigned_to_user_id=validate_assignee(db, payload.assigned_to_user_id, current_user.organization_id),
        patient_label=payload.patient_label,
        payer_name=payload.payer_name,
        plan_name=payload.plan_name,
        specialty=payload.specialty,
        requested_service=payload.requested_service,
        service_code=payload.service_code,
        diagnosis_summary=payload.diagnosis_summary,
        case_type=payload.case_type,
        status="draft",
    )
    db.add(case)
    db.flush()
    log_audit_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        user_id=current_user.user_id,
        action="case.created",
        entity_type="case",
        entity_id=case.id,
        metadata={"case_type": case.case_type, "requested_service": case.requested_service},
    )
    db.commit()
    db.refresh(case)
    return case_response(db, case)


@router.get("/cases", response_model=CaseListResponse)
async def list_cases(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cases = db.scalars(
        select(PriorAuthCase)
        .where(
            PriorAuthCase.organization_id == current_user.organization_id,
            PriorAuthCase.archived_at.is_(None),
        )
        .order_by(PriorAuthCase.updated_at.desc())
    ).all()
    return CaseListResponse(cases=[case_response(db, case) for case in cases])


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return case_response(db, get_case_for_user(db, case_id, current_user))


@router.patch("/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    payload: CaseUpdate,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    case = get_case_for_user(db, case_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    if "assigned_to_user_id" in changes:
        changes["assigned_to_user_id"] = validate_assignee(
            db,
            changes["assigned_to_user_id"],
            current_user.organization_id,
        )
    for field, value in changes.items():
        setattr(case, field, value)
    log_audit_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        user_id=current_user.user_id,
        action="case.updated",
        entity_type="case",
        entity_id=case.id,
        metadata={"updated_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(case)
    return case_response(db, case)


@router.post("/cases/{case_id}/archive", response_model=CaseResponse)
async def archive_case(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    case = get_case_for_user(db, case_id, current_user)
    case.status = "archived"
    case.archived_at = datetime.now(UTC)
    log_audit_event(
        db,
        organization_id=current_user.organization_id,
        case_id=case.id,
        user_id=current_user.user_id,
        action="case.archived",
        entity_type="case",
        entity_id=case.id,
    )
    db.commit()
    db.refresh(case)
    return case_response(db, case)
