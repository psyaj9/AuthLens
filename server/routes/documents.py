from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user, require_roles
from models.priorauth import Document
from modules.schemas import DocumentListResponse, DocumentResponse
from routes.cases import get_case_for_user
from services.documents import create_case_document, delete_case_document


router = APIRouter()


def document_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        case_id=document.case_id,
        document_type=document.document_type,
        file_name=document.file_name,
        sha256=document.sha256,
        mime_type=document.mime_type,
        page_count=document.page_count,
        processing_status=document.processing_status,
        extraction_method=document.extraction_method,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/cases/{case_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_case_document(
    case_id: str,
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    case = get_case_for_user(db, case_id, current_user)
    document = create_case_document(
        db,
        case=case,
        user_id=current_user.user_id,
        uploaded_file=file,
        document_type=document_type,
    )
    return document_response(document)


@router.get("/cases/{case_id}/documents", response_model=DocumentListResponse)
async def list_case_documents(
    case_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    case = get_case_for_user(db, case_id, current_user)
    documents = db.scalars(
        select(Document)
        .where(Document.case_id == case.id, Document.organization_id == current_user.organization_id)
        .order_by(Document.created_at.desc())
    ).all()
    return DocumentListResponse(documents=[document_response(document) for document in documents])


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == current_user.organization_id,
        )
    )
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    return document_response(document)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(require_roles("admin", "coordinator")),
    db: Session = Depends(get_db),
):
    delete_case_document(
        db,
        document_id=document_id,
        organization_id=current_user.organization_id,
        user_id=current_user.user_id,
    )
    return Response(status_code=204)
