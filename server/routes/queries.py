from modules.llm import get_llm
from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from modules.query_handler import handle_query_chain
from modules.vector_store import get_pinecone_index
from langchain_core.documents import Document
from langchain_classic.schema import BaseRetriever
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pydantic import Field
from typing import List, Optional
from logger import logger

router = APIRouter()

@router.post("/queries")
async def queries(
    user_query: str = Form(...),
    retriever: BaseRetriever = Form(...),
):
    try:
        logger.info(f"Received query: {user_query}")

        pinecone_index, _ = get_pinecone_index()
        embeddings = GoogleGenerativeAIEmbeddings(model="model/embeddings-001")
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
        logger.info(f"Query processed successfully. Response: {response}")
        return response
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)
