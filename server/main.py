from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from middlewares.exception_handlers import catch_exceptions
from modules.config import get_allowed_origins
from modules.schemas import ErrorResponse
from routes.health import router as health_router
from routes.upload_pdf import router as upload_router
from routes.queries import router as query_router


app = FastAPI()


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content=ErrorResponse(error=detail).model_dump())


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware
app.middleware("http")(catch_exceptions)

# Routers
app.include_router(health_router, prefix="/api", tags=["Health"])
app.include_router(upload_router, prefix="/api", tags=["Upload PDF"])
app.include_router(query_router, prefix="/api", tags=["Queries"])
