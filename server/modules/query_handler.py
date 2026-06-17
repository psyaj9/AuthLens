from logger import logger
from modules.config import is_production

def handle_query_chain(chain, user_query: str):
    try:
        if is_production():
            logger.info("User query received.")
        else:
            logger.info(f"User query: {user_query}")

        result = chain.invoke({"query": user_query})
        response = {
            "response": result["result"],
            "source_documents": [doc.metadata.get("source", "Unknown") for doc in result["source_documents"]]
        }
        if is_production():
            logger.info(
                f"LLM response generated. source_document_count={len(response['source_documents'])}"
            )
        else:
            logger.info(f"LLM response: {response['response']}")
        return response
    
    except Exception as e:
        if is_production():
            logger.error("Error handling query.")
        else:
            logger.error(f"Error handling query: {e}")
        raise
