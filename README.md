# AuthLens

AuthLens is a FastAPI backend for uploading PDF medical documents, storing extracted chunks in Pinecone, and answering questions with Gemini embeddings plus a Groq-backed LangChain QA chain. The planned production topology is a Render-hosted Python API and a Vercel-hosted frontend rooted at `frontend/`.

## Safety Notice

AuthLens handles medical-document content and should be treated as a demo or internal review tool unless a separate clinical, privacy, and security review says otherwise. Do not upload real patient data, protected health information, or confidential documents into local demos, CI, preview deployments, or shared test accounts. Model answers are not medical advice and should direct users to qualified healthcare professionals for clinical decisions.

## Project Layout

- `server/` - FastAPI app, routes, LangChain/Pinecone modules, backend dependencies.
- `tests/` - backend unittest suite.
- `frontend/` - planned Vercel frontend root directory.
- `render.yaml` - Render Blueprint for the backend service.
- `.circleci/config.yml` - backend and frontend CI jobs.

## Local Backend Development

Use Python 3.12 or newer. The backend dependency source is `server/requirements.txt`; the root `pyproject.toml` does not currently declare runtime dependencies.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt
```

Create a local env file from `.env.example`, then fill in real values locally only. The API should be started from `server/` so imports resolve the same way as the test suite.

```powershell
Copy-Item .env.example .env
Set-Location server
..\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Main API routes:

- `POST /api/upload_pdf/` uploads PDF files and indexes extracted text.
- `POST /api/queries/` accepts form field `user_query` and returns an answer from retrieved context.
- `GET /api/health/` is the planned deployment health route used by Render.

## Environment Variables

Backend variables:

| Name | Required | Notes |
| --- | --- | --- |
| `GROQ_API_KEY` | Yes | Secret Groq API key. |
| `GROQ_MODEL` | No | Defaults to `llama-3.1-8b-instant`. |
| `GOOGLE_API_KEY` | Yes | Secret key for Gemini embeddings. |
| `PINECONE_API_KEY` | Yes | Secret Pinecone API key. |
| `PINECONE_ENVIRONMENT` | Yes | Pinecone environment/region for the index. |
| `PINECONE_INDEX_NAME` | Yes | Pinecone index name. |
| `ALLOWED_ORIGINS` | Yes | Comma-separated browser origins allowed to call the backend, such as local frontend and Vercel URLs. |
| `INTERNAL_API_TOKEN` | Production | Shared service token for frontend-to-backend calls when the backend enforces internal auth. |
| `MAX_UPLOAD_MB` | No | Upload size limit in megabytes. |
| `MAX_UPLOAD_FILES` | No | Maximum uploaded files per request. |
| `ENVIRONMENT` | No | Use `local`, `preview`, or `production`. |

Frontend variables belong in the frontend app:

| Name | Required | Notes |
| --- | --- | --- |
| `BACKEND_API_URL` | Yes | Server-side URL for the Render backend, for example `https://authlens-backend.onrender.com`. |
| `INTERNAL_API_TOKEN` | If backend uses it | Must match the backend value for service-to-service requests. |

Do not use `NEXT_PUBLIC_BACKEND_API_URL` for the backend service URL. Keep the backend URL server-side and proxy browser requests through frontend server routes where needed.

## Deployment

### Backend on Render

`render.yaml` defines one Python web service:

- Root directory: `server`
- Build command: `uv pip install -r requirements.txt`
- Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/api/health/`

Create the service from the Blueprint in the Render dashboard. Render will prompt for values marked `sync: false`; provide real values in Render only, not in git. Set `ALLOWED_ORIGINS` to the Vercel production domain and any preview/local origins you intentionally support. If `INTERNAL_API_TOKEN` is enabled, set the same secret in Render and Vercel.

### Frontend on Vercel

Create a separate Vercel project for the frontend and set the Project Root Directory to `frontend/`. Vercel will install and build from that directory. Configure:

- `BACKEND_API_URL` as the Render backend base URL.
- `INTERNAL_API_TOKEN` only if the backend requires it.

The frontend worker should add or maintain `frontend/.env.example` with those variables.

## CI

CircleCI runs two independent jobs:

- `backend-test` uses `cimg/python`, caches pip downloads by `server/requirements.txt`, installs backend dependencies, and runs `python -m unittest discover tests`.
- `frontend-test-build` uses `cimg/node`, verifies `frontend/package.json` and `frontend/package-lock.json`, caches npm downloads by `frontend/package-lock.json`, then runs `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test`, and `npm run build` from `frontend/`.

CircleCI dependency caches are keyed by dependency files and are treated as an optimization only; a cache miss should still perform a clean install.

## Verification Commands

Backend:

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
```

Frontend:

```powershell
Set-Location frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
```

Post-deploy smoke checks:

```powershell
curl.exe https://<render-backend-host>/api/health/
curl.exe https://<vercel-frontend-host>/
```
