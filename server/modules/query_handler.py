from logger import logger

def handle_query_chain(chain, user_query: str):
    try:
        logger.debug(f"Handling query: {user_query}")
        result = chain({"query": user_query})
        response = {
            "response": result["result"],
            "source_documents": [doc.metadata.get("source", "Unknown") for doc in result["source_documents"]]
        }
        logger.debug(f"Query result: {response}")
        return response
    
    except Exception as e:
        logger.error(f"Error handling query: {e}")
        return {"error": str(e)}