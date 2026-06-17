from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middlewares.exception_handlers import catch_exceptions
from routes.upload_pdf import router as upload_router
from routes.queries import router as query_router


app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middlware
app.middleware("http")(catch_exceptions)

# Routers
app.include_router(upload_router, prefix="/api", tags=["Upload PDF"])
app.include_router(query_router, prefix="/api", tags=["Queries"])