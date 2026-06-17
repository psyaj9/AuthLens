from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import AuditEvent
from modules.schemas import AuditEventListResponse, AuditEventResponse
from routes.cases import get_case_for_user


router = APIRouter()


def audit_event_response(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        organization_id=event.organization_id,
        case_id=event.case_id,
        user_id=event.user_id,
        actor_type=event.actor_type,
        action=event.action,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        metadata=event.metadata_json,
        created_at=event.created_at,
    )


@router.get("/cases/{case_id}/audit", response_model=AuditEventListResponse)
async def list_case_audit(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = get_case_for_user(db, case_id, current_user)
    events = db.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == current_user.organization_id,
            AuditEvent.case_id == case.id,
        )
        .order_by(AuditEvent.created_at.desc())
    ).all()
    return AuditEventListResponse(events=[audit_event_response(event) for event in events])


@router.get("/audit", response_model=AuditEventListResponse)
async def list_organization_audit(
    current_user: CurrentUser = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == current_user.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(250)
    ).all()
    return AuditEventListResponse(events=[audit_event_response(event) for event in events])
