# Repository Guidelines

## Application Context

AuthLens is a FastAPI backend for uploading PDFs and answering medical-document questions. The API app is `server/main.py`; run it from the `server` directory so imports like `from logger import logger` and `from routes...` resolve the same way they do in the tests.

- `POST /api/upload_pdf/` ingests uploaded PDF files and stores text chunks in Pinecone.
- `POST /api/queries/` accepts a form field named `user_query`, embeds it, retrieves matching Pinecone chunks, and sends the context to the Groq-backed LangChain QA chain.
- Vector storage lives in Pinecone with 768-dimensional Gemini embeddings from `server/modules/vector_store.py`.
- Answer generation is configured in `server/modules/llm.py`; the default Groq model is `llama-3.1-8b-instant`, with `GROQ_MODEL` available as an environment override.
- Runtime logs are written to `server/app.log` and also streamed to the server console.

## Development Commands

- Run the full test suite from the repo root: `.venv\Scripts\python.exe -m unittest discover tests`
- Run a focused query-handler test: `.venv\Scripts\python.exe -m unittest tests.test_query_handler`
- Start the API from `server`: `..\.venv\Scripts\python.exe -m uvicorn main:app --reload`

Dependencies are tracked in `server/requirements.txt`; the root `pyproject.toml` currently has an empty dependency list. Do not document setup steps that rely on `.venv\Scripts\pip.exe` unless pip has been repaired in the local venv.

## Environment Notes

Keep secrets in `.env` only. Never print, commit, or summarize secret values from local config, logs, terminals, or credential stores.

Required runtime variables are `GROQ_API_KEY`, `GOOGLE_API_KEY`, `PINECONE_API_KEY`, `PINECONE_ENVIRONMENT`, and `PINECONE_INDEX_NAME`. `server/app.log`, `server/uploads/`, `.env`, `.venv`, and Python caches are ignored runtime artifacts and should stay out of commits.

## Testing And Verification

Use the unittest suite as the default verification path. For vector store, Pinecone, embedding, or model changes, prefer mocked unit tests first; run live checks only when credentials, rate limits, and cost are intentionally in scope.

## Workflow Orchestration

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
