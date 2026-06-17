import os

from dotenv import load_dotenv
from pinecone import Pinecone

from modules.vector_store import (
    PINECONE_DIMENSION,
    PINECONE_METRIC,
    SERVER_DIR,
    get_pinecone_index,
)


HEALTHCHECK_NAMESPACE = "authlens-healthcheck"
HEALTHCHECK_ID = "__authlens_healthcheck__"


def main():
    load_dotenv(SERVER_DIR / ".env")

    required_env = [
        "GOOGLE_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_ENVIRONMENT",
        "PINECONE_INDEX_NAME",
    ]
    missing = [name for name in required_env if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    index, index_name = get_pinecone_index()
    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
    description = pc.indexes.describe(index_name)

    print(f"Pinecone index: {index_name}")
    print(f"Ready: {description.status.ready}")
    print(f"Dimension: {description.dimension}")
    print(f"Metric: {description.metric}")

    if description.dimension != PINECONE_DIMENSION:
        raise RuntimeError(
            f"Index dimension is {description.dimension}, expected {PINECONE_DIMENSION}"
        )
    if description.metric != PINECONE_METRIC:
        raise RuntimeError(
            f"Index metric is {description.metric}, expected {PINECONE_METRIC}"
        )

    vector = [0.0] * PINECONE_DIMENSION
    vector[0] = 1.0
    index.upsert(
        vectors=[(HEALTHCHECK_ID, vector, {"source": "authlens-healthcheck"})],
        namespace=HEALTHCHECK_NAMESPACE,
    )
    result = index.query(
        vector=vector,
        top_k=1,
        namespace=HEALTHCHECK_NAMESPACE,
        include_metadata=True,
    )
    index.delete(ids=[HEALTHCHECK_ID], namespace=HEALTHCHECK_NAMESPACE)

    if not result.matches or result.matches[0].id != HEALTHCHECK_ID:
        raise RuntimeError("Pinecone healthcheck query did not return the test vector")

    print("Upsert/query/delete healthcheck: OK")


if __name__ == "__main__":
    main()
