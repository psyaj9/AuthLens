from fastapi import APIRouter, UploadFile, File, Form
from typing import List
from fastapi.responses import JSONResponse
from modules.vector_store import load_vector_store
from logger import logger

router = APIRouter()

@router.post("/upload_pdf/")
async def upload_pdf(uploaded_files: List[UploadFile] = File(...),):
    try:
        logger.info(f"Received {len(uploaded_files)} files for upload.")
        load_vector_store(uploaded_files)
        logger.info("Files uploaded and processed successfully.")
        return JSONResponse(content={"message": "Files uploaded and processed successfully."}, status_code=200)
    except Exception as e:
        logger.error(f"Error uploading files: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
