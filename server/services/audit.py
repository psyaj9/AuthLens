from sqlalchemy.orm import Session

from models.priorauth import AuditEvent


def log_audit_event(
    db: Session,
    *,
    organization_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    case_id: str | None = None,
    user_id: str | None = None,
    actor_type: str = "user",
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            organization_id=organization_id,
            case_id=case_id,
            user_id=user_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata or {},
        )
    )
