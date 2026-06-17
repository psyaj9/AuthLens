# Implement PriorAuth Evidence Copilot MVP

- [x] Run current backend/client baseline checks before implementation.
- [x] Add SQLAlchemy/Alembic-backed database foundation and seeded demo JWT auth.
- [x] Add organization-scoped case CRUD and typed document metadata/upload APIs.
- [x] Add case-scoped vector metadata, criteria extraction, evidence matching, readiness report, draft, and citation verification APIs.
- [x] Replace the first-screen client workspace with a prior-auth case workflow through server-side Next.js proxy routes.
- [x] Verify backend tests, client lint/type/test/build, and rendered workflow.

## Review

- Baseline before implementation: backend unittest, client lint, client typecheck, and client unit tests passed.
- Added DB-backed prior-auth entities, Alembic migration scaffolding, demo seed command, JWT auth, organization scoping, audit events, typed documents, criteria, evidence, readiness, draft, and citation-check workflow APIs while keeping legacy Q&A routes.
- Replaced the client first screen with the prior-auth workspace, routed browser calls through Next route handlers, added demo login behavior, and updated e2e coverage for the new first screen.
- Verified with backend unittests, Alembic migration smoke, client lint/type/unit/build, Playwright desktop/mobile e2e, and a live browser render on local dev ports.

# Fix client API proxy 503/502

- [x] Inspect client proxy routes and backend health/upload handlers.
- [x] Reproduce the reported `/api/health` 503 and `/api/upload` 502 locally.
- [x] Apply the minimal root-cause fix.
- [ ] Verify focused client/backend tests and endpoint behavior.

## Review

- Pending.

# Rename Next.js app root to client and fix type diagnostic

- [x] Move the Next.js app source/config into `client/` without moving generated artifacts.
- [x] Remove stale generated old app-root artifacts after a workspace path safety check.
- [x] Update CI, docs, env templates, package metadata, and ignore rules for the `client/` root.
- [x] Fix the backend Pylance type diagnostic around cached Pinecone state.
- [x] Re-run backend and client verification commands.

## Review

- Moved the Next.js app to `client/` and kept generated dependency/build outputs ignored.
- Added `client/.env.example` and updated `.env.example`, README, CircleCI, and package metadata for the new app root.
- Annotated the Pinecone cache globals so assigning a resolved index name no longer conflicts with a literal `None` inference.
- Renamed the query route throwaway bindings so the dependency result is no longer reused for the Pinecone index name.
- Verified with backend unittests, focused Pyright, client lint/type/test/build/e2e, and an ignore-rule check for generated/local env artifacts.

# Build Next.js client and production deployment binding

- [x] Confirm baseline repo state and existing client directory status.
- [x] Harden FastAPI backend for production client binding.
- [x] Add stable API contracts, health check, upload validation, and internal token guard.
- [x] Build a Next.js client with server-side proxy route handlers.
- [x] Implement the approved AuthLens workspace UI with safety-edited demo copy.
- [x] Add Vercel, Render, CircleCI, and environment documentation/configuration.
- [x] Run security review and fix actionable findings.
- [x] Verify backend tests, client lint/type/test/build, and rendered workflow.

## Review

- Added `.gitignore` coverage for client dependencies, Next build output, Playwright output, coverage, TypeScript build info, and Python/tooling caches to avoid giant commits.
- Added FastAPI health, production CORS, internal token guard, typed response schemas, upload validation, production-safe error responses, production log redaction, and upload cleanup.
- Added a Next.js client under `client/` with server-side proxy route handlers, structured workspace components, PDF upload flow, question/answer flow, source/status panel, loading/error/empty states, and safety-edited demo copy.
- Added Render, Vercel, CircleCI, and local/deployment documentation/configuration.
- Ran subagent reviews for backend/security, client/build, and deploy/CI/git hygiene; fixed wildcard CORS, source-path disclosure, PDF signature validation, unsafe filenames, production upload logging, health contract validation, order-dependent tests, and async accessibility announcements.
- Verified backend with `.venv\Scripts\python.exe -m unittest discover tests` and client with `npm test`, `npm run lint`, `npm run typecheck`, and `npm run build`.
- Verified rendered UI with Playwright: `npm run test:e2e` reported all 4 desktop/mobile tests as passed before the process hang, then controlled desktop and mobile screenshots were captured at `1440x960` and `390x844`.

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

# Fix RetrievalQA prompt input mismatch

- [x] Confirm root cause from logs and LangChain RetrievalQA prompt contract.
- [x] Add regression coverage for prompt variables and chain-error HTTP status.
- [x] Change the custom QA prompt to use `question` inside the document-combine step.
- [x] Stop treating chain exceptions as successful query responses.
- [x] Verify focused query tests.

## Review

- Root cause: `RetrievalQA` is invoked with `{"query": ...}`, but the internal `stuff` prompt receives the question as `question`; the custom prompt incorrectly required `{query}`.
- Updated the QA prompt to use `input_variables=["context", "question"]` and `{question}` in the template.
- Updated `handle_query_chain` so chain exceptions are logged and re-raised instead of returned as a normal `{"error": ...}` payload.
- Added regression coverage for the prompt variables, handler exception propagation, and route-level `500` behavior.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_llm tests.test_query_handler tests.test_queries_route tests.test_app_startup`.

# Replace decommissioned Groq chat model

- [x] Confirm current Groq replacement model from official docs.
- [x] Add regression coverage for default and env-configurable Groq chat model.
- [x] Replace the decommissioned hardcoded model.
- [x] Verify focused LLM tests.

## Review

- Replaced the decommissioned `llama3-70b-8192` hardcode with `llama-3.1-8b-instant`.
- Added `GROQ_MODEL` support so `.env` can override the model without code changes.
- Confirmed Groq's official deprecation docs recommend `llama-3.3-70b-versatile` as the direct 70B replacement; kept the default on the lighter instant model for local/free-tier testing.
- Added tests for default model selection and env override.
- Verified with `.venv\Scripts\python.exe -m unittest tests.test_llm tests.test_query_handler tests.test_queries_route tests.test_app_startup`.
- Verified a live Groq smoke call with `llama-3.1-8b-instant` returns successfully.
