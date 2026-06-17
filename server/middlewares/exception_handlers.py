from fastapi import Request
from fastapi.responses import JSONResponse
from logger import logger 
from modules.config import is_production
from modules.schemas import ErrorResponse

async def catch_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        if is_production():
            logger.error("Unhandled exception while processing request.")
        else:
            logger.error(f"Unhandled exception: {e}")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(error="Internal Server Error").model_dump(),
        )
