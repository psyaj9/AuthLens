import os
import shutil
from fastapi import UploadFile
import tempfile

UPLOAD_DIR = "./uploads"

def save_uploaded_files(uploaded_files: list[UploadFile]) -> list[str]:
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_file_paths = []
    for uploaded_file in uploaded_files:
        file_path = os.path.join(UPLOAD_DIR, uploaded_file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(uploaded_file.file, f)
        saved_file_paths.append(file_path)
    return saved_file_paths