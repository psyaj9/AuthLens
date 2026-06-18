import hashlib
import re
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from langchain_community.document_loaders import PyPDFLoader
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from logger import logger
from models.priorauth import (
    AnalysisRun,
    CitationCheck,
    Document,
    DocumentChunk,
    DocumentPage,
    DraftLetter,
    EvidenceMatch,
    ExportArtifact,
    PolicyCriterion,
    PriorAuthCase,
    ReadinessReport,
)
from modules.config import (
    format_upload_mb,
    get_max_document_chunks,
    get_max_extracted_chars,
    get_max_pdf_pages,
    get_max_upload_bytes,
    get_max_upload_mb,
)
from modules.vector_store import upsert_priorauth_chunks
from modules.vector_store import delete_priorauth_vectors
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


def enforce_document_resource_limits(pages: list[tuple[int, str]]) -> None:
    max_pages = get_max_pdf_pages()
    if len(pages) > max_pages:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"PDF page limit exceeded. Maximum pages allowed: {max_pages}.",
        )

    max_chars = get_max_extracted_chars()
    extracted_chars = sum(len(page_text) for _, page_text in pages)
    if extracted_chars > max_chars:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"PDF text limit exceeded. Maximum extracted characters allowed: {max_chars}.",
        )


def read_limited_upload(uploaded_file: UploadFile) -> bytes:
    max_bytes = get_max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = uploaded_file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File {safe_filename(uploaded_file.filename)} exceeds {format_upload_mb(get_max_upload_mb())} MB upload limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


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
    content = read_limited_upload(uploaded_file)
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
    enforce_document_resource_limits(pages)
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

    max_chunks = get_max_document_chunks()
    if len(chunk_payloads) > max_chunks:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Document chunk limit exceeded. Maximum chunks allowed: {max_chunks}.",
        )

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


def _remove_uploaded_file(file_uri: str) -> None:
    try:
        file_path = Path(file_uri).resolve()
        file_path.relative_to(UPLOAD_DIR.resolve())
    except (OSError, ValueError):
        return

    try:
        file_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning(f"Unable to remove deleted document file: {exc}")


def _delete_case_analysis_outputs(db: Session, *, case_id: str, organization_id: str) -> None:
    draft_ids = list(
        db.scalars(
            select(DraftLetter.id).where(
                DraftLetter.case_id == case_id,
                DraftLetter.organization_id == organization_id,
            )
        )
    )
    if draft_ids:
        db.execute(
            delete(CitationCheck).where(
                CitationCheck.draft_letter_id.in_(draft_ids),
                CitationCheck.organization_id == organization_id,
            )
        )

    for model in (
        ExportArtifact,
        DraftLetter,
        ReadinessReport,
        EvidenceMatch,
        PolicyCriterion,
        AnalysisRun,
    ):
        db.execute(
            delete(model).where(
                model.case_id == case_id,
                model.organization_id == organization_id,
            )
        )


def delete_case_document(
    db: Session,
    *,
    document_id: str,
    organization_id: str,
    user_id: str,
) -> None:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    case = db.get(PriorAuthCase, document.case_id)
    vector_ids = list(
        db.scalars(
            select(DocumentChunk.vector_id).where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.organization_id == organization_id,
            )
        )
    )
    remaining_document_count = db.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            Document.case_id == document.case_id,
            Document.organization_id == organization_id,
            Document.id != document.id,
        )
    )
    file_uri = document.file_uri

    delete_priorauth_vectors(vector_ids, organization_id)
    _delete_case_analysis_outputs(db, case_id=document.case_id, organization_id=organization_id)
    db.execute(
        delete(DocumentPage).where(
            DocumentPage.document_id == document.id,
            DocumentPage.organization_id == organization_id,
        )
    )
    db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.document_id == document.id,
            DocumentChunk.organization_id == organization_id,
        )
    )
    db.delete(document)

    if case is not None and case.organization_id == organization_id:
        case.readiness_score = None
        case.status = "documents_uploaded" if remaining_document_count else "draft"

    log_audit_event(
        db,
        organization_id=organization_id,
        case_id=document.case_id,
        user_id=user_id,
        action="document.deleted",
        entity_type="document",
        entity_id=document.id,
        metadata={"document_type": document.document_type, "file_name": document.file_name},
    )
    db.commit()
    _remove_uploaded_file(file_uri)
