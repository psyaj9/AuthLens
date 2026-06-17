import os
import time
from pathlib import Path
from dotenv import load_dotenv
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")

if GOOGLE_API_KEY is None:
    raise RuntimeError("GOOGLE_API_KEY is not set")

if PINECONE_ENVIRONMENT is None:
    raise RuntimeError("PINECONE_ENVIRONMENT is not set")

if PINECONE_INDEX_NAME is None:
    raise RuntimeError("PINECONE_INDEX_NAME is not set")

if PINECONE_API_KEY is None:
    raise RuntimeError("PINECONE_API_KEY is not set")


os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

UPLOAD_DIR="./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialise Pinecone client
pinecone = Pinecone(api_key=PINECONE_API_KEY)
spec = ServerlessSpec(cloud="aws", region=PINECONE_ENVIRONMENT)


existing_indexes = [i.name for i in pinecone.list_indexes()]

if PINECONE_INDEX_NAME not in existing_indexes:
    pinecone.create_index(
        name=PINECONE_INDEX_NAME,
        dimension=768,
        metric="dotproduct",
        spec=spec
    )
    while not pinecone.describe_index(PINECONE_INDEX_NAME).status.ready:
        print(f"Waiting for index {PINECONE_INDEX_NAME} to be ready...")
        time.sleep(5)
    
pinecone_index = pinecone.Index(PINECONE_INDEX_NAME)

# Load and process documents

def load_vector_store(uploaded_files):
    embeddings = GoogleGenerativeAIEmbeddings(model="model/embeddings-001")
    filepath = []
    

    for file in uploaded_files:
        save_path = Path(UPLOAD_DIR) / file.filename
        with open(save_path, "wb") as f:
            f.write(file.file.read())
        filepath.append(str(save_path))
    
    for file_path in filepath:
        loader = PyPDFLoader(file_path)
        documents = loader.load()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        text_chunks = text_splitter.split_documents(documents)
        
        texts = [chunk.page_content for chunk in text_chunks]
        metadata = [chunk.metadata for chunk in text_chunks]
        vector_ids = [f"{Path(file_path).stem}-{i}" for i in range(len(text_chunks))]

        embedding = embeddings.embed_documents(texts)
        vectors = [
            (vector_id, values, item_metadata)
            for vector_id, values, item_metadata in zip(vector_ids, embedding, metadata)
        ]

        with tqdm(total=len(embedding), desc=f"Uploading {Path(file_path).name} to Pinecone") as pbar:
            pinecone_index.upsert(vectors=vectors)
            pbar.update(len(embedding))

        print(f"Uploaded {len(embedding)} vectors for {Path(file_path).name} to Pinecone index {PINECONE_INDEX_NAME}.")
