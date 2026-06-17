from fastapi import APIRouter, UploadFile, File, Form
from typing import List
from modules.vector_store import load_vector_store
from fastapi.responses import JSONResponse
from logger import logger

