import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse
from modules.config import (
    format_upload_mb,
    get_max_upload_bytes,
    get_max_upload_files,
    get_max_upload_mb,
)
from modules.schemas import ErrorResponse, MessageResponse
from modules.security import require_internal_token
from modules.vector_store import load_vector_store
from logger import logger

router = APIRouter()

PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


class UploadValidationError(ValueError):
    pass


def _error_response(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        content=ErrorResponse(error=message).model_dump(),
        status_code=status_code,
    )


def _upload_size(uploaded_file: UploadFile) -> int:
    current_position = uploaded_file.file.tell()
    uploaded_file.file.seek(0, os.SEEK_END)
    size = uploaded_file.file.tell()
    uploaded_file.file.seek(current_position)
    return size


def _is_pdf_upload(uploaded_file: UploadFile, filename: str) -> bool:
    content_type = (uploaded_file.content_type or "").lower()
    return content_type in PDF_CONTENT_TYPES or Path(filename).suffix.lower() == ".pdf"


def _validate_uploaded_files(uploaded_files: List[UploadFile]) -> None:
    max_files = get_max_upload_files()
    if len(uploaded_files) > max_files:
        raise UploadValidationError(
            f"Upload limit exceeded. Maximum files allowed: {max_files}."
        )

    max_upload_bytes = get_max_upload_bytes()
    max_upload_mb = format_upload_mb(get_max_upload_mb())
    for uploaded_file in uploaded_files:
        filename = (uploaded_file.filename or "").strip()
        if not filename:
            raise UploadValidationError("Uploaded file must have a filename.")

        if not _is_pdf_upload(uploaded_file, filename):
            raise UploadValidationError("Only PDF uploads are allowed.")

        if _upload_size(uploaded_file) > max_upload_bytes:
            raise UploadValidationError(
                f"File {Path(filename).name} exceeds {max_upload_mb} MB upload limit."
            )


@router.post(
    "/upload_pdf/",
    response_model=MessageResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_pdf(
    uploaded_files: List[UploadFile] = File(...),
    _: None = Depends(require_internal_token),
):
    try:
        _validate_uploaded_files(uploaded_files)
        logger.info(f"Received {len(uploaded_files)} files for upload.")
        load_vector_store(uploaded_files)
        logger.info("Files uploaded and processed successfully.")
        return MessageResponse(message="Files uploaded and processed successfully.")
    except UploadValidationError as e:
        logger.warning(f"Rejected upload: {e}")
        return _error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return _error_response(str(e), 500)
