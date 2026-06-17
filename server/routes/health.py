from fastapi import APIRouter

from modules.config import get_environment
from modules.schemas import HealthResponse

router = APIRouter()


@router.get("/health/", response_model=HealthResponse)
async def health():
    return HealthResponse(environment=get_environment())
