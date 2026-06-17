from logger import logger

def handle_query_chain(chain, user_query: str):
    try:
        logger.info(f"User query: {user_query}")
        result = chain.invoke({"query": user_query})
        response = {
            "response": result["result"],
            "source_documents": [doc.metadata.get("source", "Unknown") for doc in result["source_documents"]]
        }
        logger.info(f"LLM response: {response['response']}")
        return response
    
    except Exception as e:
        logger.error(f"Error handling query: {e}")
        return {"error": str(e)}
