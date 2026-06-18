from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import ExportArtifact
from modules.schemas import ExportArtifactResponse
from services.exports import (
    create_letter_export,
    create_packet_export,
    create_readiness_export,
    get_export,
)
from services.audit import log_audit_event


router = APIRouter()


def export_response(artifact: ExportArtifact) -> ExportArtifactResponse:
    return ExportArtifactResponse(
        id=artifact.id,
        case_id=artifact.case_id,
        export_type=artifact.export_type,
        status=artifact.status,
        file_name=artifact.file_name,
        mime_type=artifact.mime_type,
        content_markdown=artifact.content_markdown,
        manifest_json=artifact.manifest_json,
        created_at=artifact.created_at,
    )


@router.post("/cases/{case_id}/exports/readiness-report", response_model=ExportArtifactResponse, status_code=201)
async def export_readiness_report(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    artifact = create_readiness_export(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return export_response(artifact)


@router.post("/cases/{case_id}/exports/letter", response_model=ExportArtifactResponse, status_code=201)
async def export_prior_auth_letter(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    artifact = create_letter_export(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return export_response(artifact)


@router.post("/cases/{case_id}/exports/packet", response_model=ExportArtifactResponse, status_code=201)
async def export_prior_auth_packet(
    case_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator", "clinician_reviewer")),
    db: Session = Depends(get_db),
):
    artifact = create_packet_export(
        db,
        case_id=case_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return export_response(artifact)


@router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    artifact = get_export(db, export_id=export_id, organization_id=current_user.organization_id)
    log_audit_event(
        db,
        organization_id=current_user.organization_id,
        case_id=artifact.case_id,
        user_id=current_user.user_id,
        action="export.downloaded",
        entity_type="export_artifact",
        entity_id=artifact.id,
        metadata={"export_type": artifact.export_type, "file_name": artifact.file_name},
    )
    db.commit()
    return Response(
        content=artifact.content_markdown,
        media_type=artifact.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.file_name}"'},
    )
