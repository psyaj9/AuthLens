from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from middlewares.exception_handlers import catch_exceptions
from modules.config import get_allowed_origins
from modules.schemas import ErrorResponse
from routes.audit import router as audit_router
from routes.auth import router as auth_router
from routes.cases import router as cases_router
from routes.criteria import router as criteria_router
from routes.drafts import router as drafts_router
from routes.documents import router as documents_router
from routes.evidence import router as evidence_router
from routes.health import router as health_router
from routes.reports import router as reports_router
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
app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(audit_router, prefix="/api", tags=["Audit"])
app.include_router(cases_router, prefix="/api", tags=["Cases"])
app.include_router(documents_router, prefix="/api", tags=["Documents"])
app.include_router(criteria_router, prefix="/api", tags=["Criteria"])
app.include_router(evidence_router, prefix="/api", tags=["Evidence"])
app.include_router(reports_router, prefix="/api", tags=["Reports"])
app.include_router(drafts_router, prefix="/api", tags=["Drafts"])
app.include_router(upload_router, prefix="/api", tags=["Upload PDF"])
app.include_router(query_router, prefix="/api", tags=["Queries"])
