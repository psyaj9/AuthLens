import os
import time
from pathlib import Path
from dotenv import load_dotenv
from tqdm.auto import tqdm
from pinecone import Pinecone, ServerlessSpec
from langchain_community.document_loaders import PyPDFLoader
from langchain_classic.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from logger import logger
from modules.config import is_production

SERVER_DIR = Path(__file__).resolve().parents[1]
load_dotenv(SERVER_DIR / ".env")

UPLOAD_DIR = SERVER_DIR / "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

PINECONE_CLOUD = "aws"
PINECONE_DIMENSION = 768
PINECONE_METRIC = "cosine"
EMBEDDING_MODEL = "gemini-embedding-2-preview"

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
            if is_production():
                logger.info("Waiting for Pinecone index readiness.")
            else:
                logger.info(f"Waiting for index {pinecone_index_name} to be ready...")
            time.sleep(5)

    _pinecone_index = pinecone.index(pinecone_index_name)
    _pinecone_index_name = pinecone_index_name
    return _pinecone_index, _pinecone_index_name


def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        output_dimensionality=PINECONE_DIMENSION,
    )

# Load and process documents

def _safe_upload_filename(filename: str | None) -> str:
    if filename is None or not filename.strip():
        raise ValueError("Uploaded file must have a filename")

    return Path(filename.strip()).name


def load_vector_store(uploaded_files):
    pinecone_index, pinecone_index_name = get_pinecone_index()
    embeddings = get_embeddings()
    filepaths = []

    try:
        for file in uploaded_files:
            save_path = Path(UPLOAD_DIR) / _safe_upload_filename(file.filename)
            with open(save_path, "wb") as f:
                f.write(file.file.read())
            filepaths.append(save_path)

        for file_path in filepaths:
            loader = PyPDFLoader(str(file_path))
            documents = loader.load()

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
            text_chunks = text_splitter.split_documents(documents)

            texts = [chunk.page_content for chunk in text_chunks]
            metadata = [
                {**chunk.metadata, "text": chunk.page_content}
                for chunk in text_chunks
            ]
            vector_ids = [f"{file_path.stem}-{i}" for i in range(len(text_chunks))]

            embedding = embeddings.embed_documents(texts)
            vectors = [
                (vector_id, values, item_metadata)
                for vector_id, values, item_metadata in zip(vector_ids, embedding, metadata)
            ]

            upload_description = (
                "Uploading document to Pinecone"
                if is_production()
                else f"Uploading {file_path.name} to Pinecone"
            )
            with tqdm(total=len(embedding), desc=upload_description) as pbar:
                pinecone_index.upsert(vectors=vectors)
                pbar.update(len(embedding))

            if is_production():
                logger.info(
                    f"Uploaded vectors to Pinecone. vector_count={len(embedding)}"
                )
            else:
                logger.info(
                    f"Uploaded {len(embedding)} vectors for {file_path.name} to Pinecone index {pinecone_index_name}."
                )
    finally:
        for file_path in filepaths:
            file_path.unlink(missing_ok=True)
