# Fix server logger startup failure

- [x] Confirm root cause from traceback and local logger setup.
- [x] Add a regression check for importing the server logger from the `server` cwd.
- [x] Fix logger path resolution so it is independent of the process cwd.
- [x] Add a regression check that app import does not contact Pinecone.
- [x] Move Pinecone index setup out of module import and into upload processing.
- [x] Verify the regression checks and uvicorn app import.

## Review

- Added regression coverage for logger import from the `server` working directory.
- Added regression coverage to ensure app import does not contact Pinecone.
- Fixed logger file path resolution to use `server/app.log` regardless of process cwd.
- Deferred Pinecone setup until PDF upload processing, so uvicorn can import the FastAPI app without external API side effects.
- Added Python cache and local app log ignores to reduce generated-file noise.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_logger tests.test_app_startup`.
- Verified uvicorn serves `/openapi.json` on `127.0.0.1:8765`.

# Reset Pinecone integration

- [x] Inspect current Pinecone code and SDK shape.
- [x] Update Pinecone setup to current serverless vector-index usage.
- [x] Add a safe live Pinecone diagnostic that does not print secrets.
- [x] Verify tests, live Pinecone readiness, and uvicorn startup.

## Review

- Updated Pinecone integration to use the current SDK style: `pc.indexes.create(...)` and `pc.index(...)`.
- Standardized the app on a normal serverless vector index using Google embeddings, not Pinecone integrated inference.
- Set the vector index defaults to dimension `768` and metric `cosine`.
- Reused the same Pinecone helper from upload and query routes.
- Added retrieved chunk text into Pinecone metadata so query results contain document content.
- Added `server/check_pinecone.py` for safe live diagnostics without printing secrets.
- Verified live Pinecone index `auth-index`: ready, dimension `768`, metric `cosine`, upsert/query/delete healthcheck OK.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_vector_store tests.test_logger tests.test_app_startup`.
- Verified uvicorn serves `/openapi.json` on `127.0.0.1:8765`.
