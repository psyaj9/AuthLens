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

# Fix Google embedding model 404

- [x] Confirm root cause from the upload error and live embedding probe.
- [x] Add regression coverage for the Google embedding model configuration.
- [x] Update upload and query paths to use the working embedding model consistently.
- [x] Verify focused tests and a live embedding dimension check.

## Review

- Replaced the invalid Google embedding model ID with the live-working Gemini embedding model.
- Forced 768-dimensional embeddings so uploaded vectors match the existing Pinecone index.
- Reused the same embedding helper for upload and query requests.
- Added regression coverage for the embedding constructor configuration.
- Ignored runtime PDF uploads under `server/uploads/`.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_vector_store tests.test_app_startup`.
- Verified a live embedding probe returns `dim=768`.

# Fix query endpoint 422

- [x] Confirm why `/api/queries/` asks Postman for `retriever`.
- [x] Add route coverage proving only `user_query` is required.
- [x] Remove the client-facing `retriever` form dependency.
- [x] Verify focused route and startup tests.

## Review

- Removed the unnecessary client-facing `retriever` form field from `/api/queries/`.
- Kept `SimpleRetriever` internal so the API only needs `user_query` from Postman.
- Added route coverage proving `POST /api/queries/` accepts only `user_query`.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_queries_route tests.test_app_startup tests.test_vector_store`.

# Print query responses and fix LangChain deprecation

- [x] Confirm deprecated call site and current LangChain replacement.
- [x] Add coverage that `handle_query_chain` uses `invoke()` and logs query/response.
- [x] Add console logging so query and LLM response appear in the server console.
- [x] Verify focused query handler/logger tests.

## Review

- Replaced deprecated `chain({"query": user_query})` with `chain.invoke({"query": user_query})`.
- Logged the exact user query and final LLM response at INFO level.
- Added a console stream handler so app logs appear in the uvicorn terminal as well as `server/app.log`.
- Closed existing logger handlers before reconfiguration to avoid duplicate handlers and file-handle leaks during imports.
- Added regression coverage for the query handler and console logger setup.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_query_handler tests.test_logger tests.test_queries_route tests.test_app_startup`.
