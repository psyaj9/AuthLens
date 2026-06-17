from modules.llm import get_llm
from fastapi import APIRouter, Depends, Form
from fastapi.responses import JSONResponse
from modules.config import is_production
from modules.query_handler import handle_query_chain
from modules.schemas import ErrorResponse, QueryResponse
from modules.security import require_internal_token
from modules.vector_store import get_embeddings, get_pinecone_index
from langchain_core.documents import Document
from langchain_classic.schema import BaseRetriever
from pydantic import Field
from typing import List, Optional
from logger import logger

router = APIRouter()


def _error_response(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        content=ErrorResponse(error=message).model_dump(),
        status_code=status_code,
    )


@router.post(
    "/queries/",
    response_model=QueryResponse,
    responses={
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def queries(
    user_query: str = Form(...),
    _: None = Depends(require_internal_token),
):
    try:
        if is_production():
            logger.info("Received query for processing.")
        else:
            logger.info(f"Received query: {user_query}")

        pinecone_index, _ = get_pinecone_index()
        embeddings = get_embeddings()
        embedded_query = embeddings.embed_query(user_query)


        response = pinecone_index.query(vector=embedded_query, top_k=3,include_metadata=True)

        documents = [
            Document(
                page_content=match["metadata"].get("text", ""), 
                metadata={"source": match["metadata"].get("source", "Unknown")})
                for match in response.matches
        ]

        class SimpleRetriever(BaseRetriever):

            documents: List[Document] = Field(default_factory=list)
            tags: Optional[List[str]] = Field(default_factory=list)
            metadata: Optional[dict] = Field(default_factory=dict)

            def _get_relevant_documents(self, query: str) -> List[Document]:
                return self.documents

        retriever = SimpleRetriever(documents=documents)
        llm_chain = get_llm(retriever)
        response = handle_query_chain(llm_chain, user_query)
        if is_production():
            source_count = len(response.get("source_documents", []))
            logger.info(
                f"Query processed successfully. source_document_count={source_count}"
            )
        else:
            logger.info(f"Query processed successfully. Response: {response}")
        return response
    
    except Exception as e:
        if is_production():
            logger.error("Error processing query.")
            return _error_response("Unable to process query.", 500)
        else:
            logger.error(f"Error processing query: {e}")
            return _error_response(str(e), 500)
