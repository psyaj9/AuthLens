import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from langchain_community.document_loaders import PyPDFLoader
from sqlalchemy.orm import Session

from models.priorauth import Document, DocumentChunk, DocumentPage, PriorAuthCase
from modules.vector_store import upsert_priorauth_chunks
from services.audit import log_audit_event


SERVER_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = SERVER_DIR / "uploads" / "priorauth"
PDF_SIGNATURE = b"%PDF-"
SUPPORTED_DOCUMENT_TYPES = {
    "payer_policy",
    "patient_note",
    "lab_result",
    "imaging_report",
    "medication_history",
    "referral_letter",
    "denial_letter",
    "other",
}


def validate_document_type(document_type: str) -> str:
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported document type")
    return document_type


def safe_filename(filename: str | None) -> str:
    value = (filename or "").strip()
    path = Path(value)
    if not value or path.name != value or path.is_absolute() or ".." in path.parts or "/" in value or "\\" in value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded filename is not allowed.")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF uploads are allowed.")
    return value


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return [""]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        chunks.append(normalized[start:end])
        if end == len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def extract_pdf_pages(file_path: Path) -> list[tuple[int, str]]:
    try:
        pages = []
        for index, page in enumerate(PyPDFLoader(str(file_path)).load(), start=1):
            pages.append((index, page.page_content or ""))
        if pages:
            return pages
    except Exception:
        pass

    raw_text = file_path.read_bytes().decode("utf-8", errors="ignore")
    fallback = raw_text.replace("%PDF-1.4", "").replace("%PDF-", "").strip()
    return [(1, fallback)]


def create_case_document(
    db: Session,
    *,
    case: PriorAuthCase,
    user_id: str,
    uploaded_file: UploadFile,
    document_type: str,
) -> Document:
    document_type = validate_document_type(document_type)
    filename = safe_filename(uploaded_file.filename)
    content = uploaded_file.file.read()
    if not content.startswith(PDF_SIGNATURE):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only valid PDF uploads are allowed.")

    document = Document(
        organization_id=case.organization_id,
        case_id=case.id,
        uploaded_by_user_id=user_id,
        document_type=document_type,
        file_name=filename,
        file_uri="pending",
        sha256=hashlib.sha256(content).hexdigest(),
        mime_type=uploaded_file.content_type or "application/pdf",
        processing_status="processing",
    )
    db.add(document)
    db.flush()

    case_dir = UPLOAD_DIR / case.id
    case_dir.mkdir(parents=True, exist_ok=True)
    file_path = case_dir / f"{document.id}-{filename}"
    file_path.write_bytes(content)
    document.file_uri = str(file_path)

    pages = extract_pdf_pages(file_path)
    document.page_count = len(pages)
    chunk_payloads: list[dict] = []
    chunk_index = 0
    for page_number, page_text in pages:
        db.add(
            DocumentPage(
                document_id=document.id,
                case_id=case.id,
                organization_id=case.organization_id,
                page_number=page_number,
                text=page_text,
            )
        )
        for text_chunk in chunk_text(page_text):
            vector_id = f"{document.id}-{chunk_index}"
            chunk = DocumentChunk(
                document_id=document.id,
                case_id=case.id,
                organization_id=case.organization_id,
                document_type=document_type,
                chunk_index=chunk_index,
                text=text_chunk,
                page_start=page_number,
                page_end=page_number,
                token_count=len(text_chunk.split()),
                vector_id=vector_id,
            )
            db.add(chunk)
            db.flush()
            chunk_payloads.append(
                {
                    "id": chunk.id,
                    "vector_id": vector_id,
                    "text": text_chunk,
                    "organization_id": case.organization_id,
                    "case_id": case.id,
                    "document_id": document.id,
                    "document_type": document_type,
                    "file_name": filename,
                    "page_start": page_number,
                    "page_end": page_number,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

    upsert_priorauth_chunks(chunk_payloads)
    document.processing_status = "indexed"
    case.status = "documents_uploaded"
    log_audit_event(
        db,
        organization_id=case.organization_id,
        case_id=case.id,
        user_id=user_id,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        metadata={"document_type": document_type, "page_count": document.page_count},
    )
    db.commit()
    db.refresh(document)
    return document
