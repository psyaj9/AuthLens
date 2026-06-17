from langchain_core.prompts import PromptTemplate
from langchain_classic.chains import RetrievalQA
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
GROQ_API_KEY: SecretStr | None = SecretStr(groq_api_key) if groq_api_key else None
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"


def get_llm(retriever):
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        temperature=0.2,
        max_tokens=2000,
    )
    
    prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""
        
        You are a medical assistant that helps understand medical questions and documents. 
        
        Your role is to provide clear, accurate, and helpful responses to medical inquiries, **while ensuring that the information you provide is based on reliable sources and evidence-based medical knowledge.**

        ---

        **Context:**
        {context}

        **User Query:**
        {question}

        ---

        **Answer:**
        - Respond to the user's query based on the provided context.
        - If the context does not contain sufficient information to answer the query, respond with "I'm sorry, but I don't have enough information to provide an answer to your question based on the provided
          context. Please consult a qualified healthcare professional for personalized medical advice."
        - Avoid providing personal medical advice or making diagnoses. Instead, focus on providing general information and guidance based on the context.
        - If the context contains conflicting information, acknowledge the discrepancies and provide a balanced view based on the available evidence.
        """
    )

    return RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": prompt},
        return_source_documents=True
    )
