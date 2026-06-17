import os
import time
from pathlib import Path
from dotenv import load_dotenv
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings

SERVER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SERVER_DIR / ".env")

UPLOAD_DIR = SERVER_DIR / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

PINECONE_CLOUD = "aws"
PINECONE_DIMENSION = 768
PINECONE_METRIC = "cosine"

_pinecone_index = None
_pinecone_index_name = None


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"{name} is not set")
    return value


def _index_names(indexes) -> set[str]:
    return {
        index if isinstance(index, str) else index.name
        for index in indexes
    }


def get_pinecone_index():
    global _pinecone_index, _pinecone_index_name

    if _pinecone_index is not None:
        return _pinecone_index, _pinecone_index_name

    google_api_key = _required_env("GOOGLE_API_KEY")
    pinecone_api_key = _required_env("PINECONE_API_KEY")
    pinecone_environment = _required_env("PINECONE_ENVIRONMENT")
    pinecone_index_name = _required_env("PINECONE_INDEX_NAME")

    os.environ["GOOGLE_API_KEY"] = google_api_key

    pinecone = Pinecone(api_key=pinecone_api_key)
    spec = ServerlessSpec(cloud=PINECONE_CLOUD, region=pinecone_environment)

    existing_indexes = _index_names(pinecone.list_indexes())

    if pinecone_index_name not in existing_indexes:
        pinecone.indexes.create(
            name=pinecone_index_name,
            dimension=PINECONE_DIMENSION,
            metric=PINECONE_METRIC,
            spec=spec
        )
        while not pinecone.indexes.describe(pinecone_index_name).status.ready:
            print(f"Waiting for index {pinecone_index_name} to be ready...")
            time.sleep(5)

    _pinecone_index = pinecone.index(pinecone_index_name)
    _pinecone_index_name = pinecone_index_name
    return _pinecone_index, _pinecone_index_name

# Load and process documents

def load_vector_store(uploaded_files):
    pinecone_index, pinecone_index_name = get_pinecone_index()
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
        metadata = [
            {**chunk.metadata, "text": chunk.page_content}
            for chunk in text_chunks
        ]
        vector_ids = [f"{Path(file_path).stem}-{i}" for i in range(len(text_chunks))]

        embedding = embeddings.embed_documents(texts)
        vectors = [
            (vector_id, values, item_metadata)
            for vector_id, values, item_metadata in zip(vector_ids, embedding, metadata)
        ]

        with tqdm(total=len(embedding), desc=f"Uploading {Path(file_path).name} to Pinecone") as pbar:
            pinecone_index.upsert(vectors=vectors)
            pbar.update(len(embedding))

        print(f"Uploaded {len(embedding)} vectors for {Path(file_path).name} to Pinecone index {pinecone_index_name}.")
