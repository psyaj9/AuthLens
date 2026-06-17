from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    error: str


class MessageResponse(BaseModel):
    message: str


class QueryResponse(BaseModel):
    response: str
    source_documents: list[str] = Field(default_factory=list)


class DependencyHealth(BaseModel):
    pinecone: str = "not_checked"
    groq: str = "not_checked"
    google: str = "not_checked"


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "authlens-api"
    environment: str
    dependencies: DependencyHealth = Field(default_factory=DependencyHealth)
