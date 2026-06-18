# Next PRD Implementation Phases

## Production Auth Token Parse Bug

- [x] Trace the production `/api/auth/register` and `/api/auth/login` response flow through the Next proxy and FastAPI route.
- [x] Add focused regression tests for successful browser auth responses that intentionally omit `access_token` and `token_type` from JSON.
- [x] Apply the smallest root-cause fix at the failing boundary.
- [x] Verify focused client auth proxy tests and relevant backend auth tests.

## Review

- Root cause: the FastAPI backend returns `access_token` / `token_type`, but the Next auth proxy intentionally strips the bearer token from browser JSON and stores it in an HTTP-only cookie. The client API helper was still parsing login/register responses with the backend token schema, causing the production Zod error after successful 200/201 auth responses.
- Fixed `loginUser` and `registerUser` to parse the browser-facing auth contract `{ user }` while preserving the backend token schema and secure cookie route behavior.
- Verification passed: red client regression reproduced the production missing-token Zod error; focused auth proxy/client tests passed 14 tests; client typecheck passed; client full Vitest passed 52 tests; client lint passed; backend unittest discovery passed 121 tests.

## Current Remaining Phase 4/5 Launch Gates

- [x] Re-read `README.md`, `priorauth_evidence_copilot_prd.md`, `tasks/todo.md`, and `docs/superpowers/plans/2026-06-18-next-prd-phases.md` to identify the true remaining work after the completed MVP slices.
- [x] Analyze `ChatGPT-Platform Novelty Development.md` and map its novelty/product requirements onto the current PriorAuth Evidence Copilot implementation path.
- [x] Run parallel read-only subagent reconnaissance for README/PRD/todo state, novelty-doc implications, and security scan seed surfaces.
- [x] Save the next implementation plan at `docs/superpowers/plans/2026-06-18-authlens-remaining-launch-gates.md`.
- [x] Run the real Codex Security repository scan with scoped emphasis on auth/session, cross-tenant direct IDs, exports/downloads, prompt injection, and upload handling.
- [x] Fix validated Codex Security findings in severity order, with regression tests and scan-report receipts.
- [x] Add executable live deployment smoke gates for the Render backend and Vercel client.
- [x] Expand the synthetic eval dataset beyond the 3-case smoke set toward the PRD target coverage.
- [x] Add a real password reset delivery path before enabling production forgot-password with `PASSWORD_RESET_DELIVERY_MODE=email` or `PASSWORD_RESET_DELIVERY_MODE=external`.
- [x] Run final backend, client, dependency-audit, synthetic-eval, Codex Security, and live deployment smoke verification.

### Current Launch-Gate Plan Notes

- The older phase plan remains useful as historical context, but Phase 0 through Phase 3 are now implemented and most Phase 4/5 slices are already done.
- The remaining Phase 4 work is now the larger PRD eval corpus beyond the expanded 12-case local gate.
- The remaining Phase 5 work is final release verification against the accumulated security, CI, deployment-smoke, reset-delivery, and dependency-audit gates.
- The novelty document reinforces the intended product boundary: AuthLens should stay positioned as a synthetic/de-identified, citation-backed prior-auth evidence-preparation workflow with human review, not as a diagnosis, treatment, payer-approval, or generic medical-chatbot system.
- Security reconnaissance seed risks for the real scan: legacy shared Pinecone Q&A upload/query routes, auth/reset rate limiting and token lifecycle, export download headers and content exposure, prompt injection across legacy and structured flows, PDF parser/resource limits, and edited-draft/export rendering assumptions.
- Deployment smoke should become a scriptable gate that checks `GET <render>/api/health/`, `GET <vercel>/`, and `GET <vercel>/api/health` so the client-to-backend binding is verified after deploy.
- Password reset delivery should add a delivery adapter, likely SMTP for `email` mode and a webhook handoff for `external` mode, and must not commit usable reset tokens if delivery fails.
- Codex Security scan bundle: `C:\tmp\codex-security-scans\AuthLens\d35c87ce_20260618-154542\report.md` and `report.html`.
- Validated scan findings to fix first: legacy Q&A unscoped Pinecone/public proxy exposure (`AL-001`, high), auth/reset attempt throttling (`AL-002`, medium), browser auth proxy token exposure (`AL-003`, medium), and PDF parser/indexing resource limits (`AL-004`, medium).
- Security fix receipt: `C:\tmp\codex-security-scans\AuthLens\d35c87ce_20260618-154542\artifacts\fix_report.md`.
- Deployment smoke gate is scripted in `scripts/deployment_smoke.py`, optional in CircleCI behind `AUTHLENS_RENDER_BACKEND_URL` and `AUTHLENS_VERCEL_CLIENT_URL`, and covered by `tests.test_deployment_smoke` plus deployment-config regression coverage.
- Synthetic eval coverage is now `phase7-expanded-v1` with 12 synthetic cases across missing evidence, ambiguous policy language, contradictory evidence, appeal denial letters, prompt injection, unsafe approval language, draft type, citation, and safety metrics.
- Password reset delivery now supports production `email` mode through SMTP and `external` mode through webhook handoff, requires provider config, does not expose production reset tokens, and rolls back token rows if delivery fails.

- [x] Execute Phase 0 from `docs/superpowers/plans/2026-06-18-next-prd-phases.md`: executable synthetic evals and cross-tenant direct-ID tests.
- [x] Execute Phase 1: reviewer workspace completion.
- [x] Execute Phase 2: export artifacts, download APIs, and packet manifest.
- [x] Execute Phase 3: appeal workflow with denial-letter extraction.
- [x] Execute Phase 4: structured LLM gateway and expanded eval runner.
- [x] Execute Phase 5: production-readiness hardening, security scan, and deployment gates.
- [x] Update `README.md` so it reflects the PriorAuth Evidence Copilot product, runtime architecture, multi-agent implementation architecture, setup, verification, deployment, and roadmap.

## Review

- Phase 0 guardrails are now implemented: `server/evals/run_synthetic_eval.py` executes the synthetic golden cases, fixture document bodies support offline smoke runs, draft safety is asserted, and focused eval tests pass.
- Added cross-tenant direct-ID coverage across cases, documents, criteria, evidence, reports, drafts, citation verification, approval, and audit routes.
- Fixed `/api/cases/{case_id}/drafts/appeal` so the deferred route performs auth and organization-scoped case lookup before returning `501`.
- Added defense-in-depth organization filters for child-row summary/delete paths and a regression test proving mismatched child-row tenants do not affect case summaries.
- Updated `README.md` around the current prior-auth workspace, including architecture diagrams, multi-agent implementation workflow, test commands, deployment notes, and remaining phases.
- Phase 1 reviewer workspace is now implemented: client helpers and local proxy coverage for criteria updates, evidence overrides, draft edits, citation verification, and approval; inline reviewer controls in the criteria/evidence/draft tabs; citation issue details; approval disabled until citation verification passes.
- Phase 1 verification passed: `npm run lint`, `npm run typecheck`, `npm run test` with 40 Vitest tests across 9 files, `npm run build`, and `npm run test:e2e` with 6 desktop/mobile Playwright tests.
- Phase 2 exports are now implemented: persisted `ExportArtifact` records, Alembic migration `20260618_0003`, readiness/letter/packet export APIs, markdown download API, packet document/citation manifest, export creation/download audit events, and client export controls/download links.
- Phase 2 verification passed: backend unittest discovery with 63 tests, `tests.test_exports` with 5 focused export tests, Alembic upgrade smoke through `20260618_0003`, client lint/typecheck/test/build, and Playwright desktop/mobile e2e with 6 tests.
- Phase 3 appeals are now implemented: appeal cases can upload denial letters, generate appeal drafts, cite denial-letter reasons, reuse verified patient evidence, and keep citation/human-review gates before approval.
- Added backend safety rules for appeal drafts: only `case_type="appeal"` can use the appeal draft route, missing denial letters fail before readiness-report checks, and denial reasons must retain a denial-letter file/page citation.
- Addressed Phase 3 review findings: appeal cases can no longer bypass denial-letter requirements through the prior-auth draft route, denial-letter citations must stay attached to the denial-reason line, and draft-generation UI/e2e coverage now follows admin/coordinator RBAC.
- Added/verified client appeal workflow support: appeal case creation, denial-letter document type, appeal draft helper/proxy route, and desktop/mobile e2e coverage for generating an appeal draft from a denial letter.
- Phase 3 verification passed after review fixes: backend unittest discovery with 67 tests, client lint/typecheck, Vitest with 47 tests across 10 files, Next production build, and Playwright desktop/mobile e2e with 8 tests.
- Phase 4 foundation is now started but not complete: added `server/services/llm_gateway.py`, `server/services/analysis_schemas.py`, Pydantic structured-output parsing, untrusted-document prompt framing, redacted failed `AnalysisRun` recording, and an opt-in `PRIORAUTH_ANALYSIS_MODE=llm` criteria extraction branch.
- Phase 4 focused verification passed after review fixes: `tests.test_llm_gateway` with 9 tests, seven LLM criteria integration tests for valid output, invalid output, ungrounded citations, blank source quotes, empty output, repeated provider failures, and provider failures with underlying causes; backend unittest discovery with 83 tests, client lint/typecheck, Vitest with 47 tests across 10 files, Next production build, and Playwright desktop/mobile e2e with 8 tests.
- Remaining Phase 4 scope: grow the synthetic eval dataset toward the PRD target set beyond the current 3-case smoke gate.
- Current Phase 4 provider-boundary slice:
  - [x] Add tests for the Groq JSON-schema request boundary and direct SDK dependency.
  - [x] Implement `generate_structured_output` through the Groq SDK while preserving fail-closed behavior and redacted errors.
  - [x] Update README/env docs for the real structured provider path.
  - [x] Verify focused gateway tests, backend discovery, client gates, and review findings.
- Phase 4 provider-boundary verification passed after review fixes: focused gateway/deployment/criteria tests passed 27 tests, backend unittest discovery passed 91 tests, client lint/typecheck passed, Vitest passed 47 tests across 10 files, Next production build passed, and Playwright desktop/mobile e2e passed 8 tests.
- Current Phase 4 evidence/readiness LLM slice:
  - [x] Add tests for opt-in structured evidence matching and readiness reports.
  - [x] Ground `met` evidence matches to patient-document chunks only and fail closed on payer-policy or fabricated citations.
  - [x] Persist LLM readiness reports with documentation-completeness semantics and safe failed-run metadata.
  - [x] Verify focused backend tests, full backend discovery, and client gates.
  - [x] Complete focused review and address findings.
- Phase 4 evidence/readiness LLM verification passed: focused Phase 4 tests passed 27 tests, backend unittest discovery passed 95 tests, client lint/typecheck passed, Vitest passed 47 tests across 10 files, Next production build passed, and Playwright desktop/mobile e2e passed 8 tests.
- Phase 4 evidence/readiness review fixes added fail-closed coverage for duplicate LLM criterion codes, duplicate stored criterion codes, and unsafe readiness list text; focused `tests.test_llm_gateway` plus `tests.test_priorauth_workflow` passed 52 tests after fixes.
- Phase 4 evidence/readiness review-fix backend discovery passed 98 tests.
- Current Phase 4 expanded eval scoring slice:
  - [x] Add executable scoring for expected criteria coverage, evidence status outcomes, missing-item recall, and prompt-injection handling.
  - [x] Keep the smoke eval deterministic even when `PRIORAUTH_ANALYSIS_MODE=llm` is set locally.
  - [x] Update README and task tracker for implemented smoke-set scoring and remaining PRD dataset growth.
  - [x] Verify focused eval gate and backend discovery.
- Phase 4 expanded eval scoring verification passed: `tests.test_phase7_eval_gate` passed 3 tests, focused eval/gateway/workflow verification passed 55 tests, and backend unittest discovery passed 99 tests.
- Current Phase 5 auth/session hardening slice:
  - [x] Add token-version invalidation so password reset rejects pre-reset access tokens.
  - [x] Add Alembic migration `20260618_0004_user_token_version`.
  - [x] Update README and task tracker for reset-driven session invalidation.
  - [x] Verify focused auth tests and migration smoke.
- Phase 5 auth/session verification passed: password-reset access-token invalidation and adjacent reset tests passed 3 tests, deployment/auth focused verification passed 5 tests, Alembic upgrade smoke reached `20260618_0004` on a fresh temporary SQLite database, and backend unittest discovery passed 100 tests.
- Current Phase 5 production reset-delivery slice:
  - [x] Add production fail-closed behavior when `PASSWORD_RESET_DELIVERY_MODE` is unset.
  - [x] Reject invalid production reset-delivery modes without creating reset-token rows.
  - [x] Keep configured production reset requests from exposing raw reset tokens.
  - [x] Document `PASSWORD_RESET_DELIVERY_MODE` in `.env.example`, `render.yaml`, and `README.md`.
  - [x] Verify focused auth/deployment tests and full backend discovery.
- Phase 5 production reset-delivery verification passed: production reset-delivery tests passed 3 tests, focused auth/deployment verification passed 11 tests, and backend unittest discovery passed 104 tests.
- Current Phase 5 CI eval-gate slice:
  - [x] Add a deployment-config regression requiring CircleCI to run the synthetic eval smoke gate.
  - [x] Add `Run synthetic eval smoke gate` to the CircleCI backend job.
  - [x] Update README CI docs to include the explicit eval command.
  - [x] Verify the focused deployment-config test and direct eval command.
- Phase 5 CI eval-gate verification passed: `tests.test_deployment_config.DeploymentConfigTests.test_circleci_runs_synthetic_eval_gate` passed, `.venv\Scripts\python.exe server\evals\run_synthetic_eval.py` passed 3/3 synthetic cases with no failed cases, and backend unittest discovery passed 105 tests.
- Current Phase 5 dependency-audit CI slice:
  - [x] Add backend CI gates for installing `pip-audit` and auditing `server/requirements.txt`.
  - [x] Add client CI gate for `npm audit --audit-level=high`.
  - [x] Add deployment-config regressions for both dependency-audit gates.
  - [x] Update README security/CI docs with local and CI audit commands.
  - [x] Verify Python and client dependency audits locally.
- Phase 5 dependency-audit verification passed: deployment-config tests passed 8 tests, Python `pip_audit` found no known backend vulnerabilities, `npm audit --audit-level=high` exited cleanly with only moderate Next/PostCSS advisories, and backend unittest discovery passed 107 tests.
- Current launch-gate completion slice:
  - [x] Codex Security scan and validated security fixes completed with scan receipts.
  - [x] Live deployment smoke gate added for Render backend health, Vercel client root, and Vercel `/api/health`.
  - [x] Synthetic eval dataset expanded from 3 to 12 cases with appeal and prompt-injection coverage plus rate metrics.
  - [x] Production password reset delivery added for SMTP email and external webhook modes with rollback on delivery failure.
- Final launch-gate verification passed: backend unittest discovery passed 121 tests, standalone synthetic eval passed 12/12 cases with all summary rates at 1.0, client lint/typecheck/unit/build/e2e passed, backend dependency audit found no known vulnerabilities, and client high-severity audit exited cleanly with only moderate Next/PostCSS advisories.
- Live Render/Vercel smoke was not executed against real deployments because `AUTHLENS_RENDER_BACKEND_URL` and `AUTHLENS_VERCEL_CLIENT_URL` are not configured in the current shell; the scripted gate and optional CircleCI wiring are covered by tests.
- Planning complete. Detailed execution plan is saved at `docs/superpowers/plans/2026-06-18-next-prd-phases.md`.
- Backend explorer recommended export APIs as the next backend slice: `server/routes/exports.py`, `server/services/exports.py`, `ExportArtifact`, Alembic migration, and export/download tests.
- Frontend explorer recommended reviewer UX first: criteria edits, evidence overrides, draft edit/verify/approve, audit views, then export UI.
- Security/eval explorer recommended executable synthetic evals, prompt-injection outcomes, cross-tenant direct-ID tests, auth/session hardening, env gates, dependency audit, and PHI boundary checks.
- Consolidated order: lock eval and tenant-isolation guardrails first, expose reviewer controls, then exports, appeals, structured LLM/evals, and production hardening.

# Complete Phase 7 MVP Gate And PRD Re-Review

- [x] Re-read the PRD and map current implementation against remaining MVP/Phase 7 requirements.
- [x] Add organization-scoped audit read APIs for case audit and organization audit.
- [x] Add synthetic golden-case smoke fixtures and validation tests.
- [x] Add explicit red-team/safety tests for prompt injection, unsupported draft claims, tenant isolation, and synthetic-only guardrails.
- [x] Verify backend/client/deployment checks after the Phase 7 changes.
- [x] Summarize completed phases and PRD next-stage roadmap.

## Review

- Added case-scoped and organization-scoped audit read APIs, including admin-only organization audit access and cross-tenant denial coverage.
- Added Phase 7 smoke golden fixtures for 3 synthetic lumbar MRI cases: approval-ready, missing conservative therapy, and prompt-injection.
- Hardened legacy query/upload paths and prior-auth flows with production fail-fast config validation, production fail-closed internal token behavior, reset-token invalidation, untrusted-document prompt rules, draft human-review disclaimer verification, and secure production auth cookies.
- Verified backend with `.venv\Scripts\python.exe -m unittest discover tests` passing 55 tests.
- Verified client with `npm run lint`, `npm run typecheck`, `npm run test` passing 33 Vitest tests, and `npm run build`.
- `npm run test:e2e` was blocked because an existing Next dev server was already running for this project on port 3010; manual Playwright desktop/mobile login smoke checks against that server passed.
- Security/dependency notes: `npm audit --audit-level=high` reported only moderate Next/PostCSS advisories with no safe non-breaking fix from npm audit; Python dependency audit could not run because `pip_audit` is not installed in the venv.

# Harden Legacy Debug Proxy POST Routes

- [x] Add failing cross-origin mutation tests for `/api/query` and `/api/upload`.
- [x] Run focused client route tests and confirm the new tests fail for the missing guard.
- [x] Reuse the prior-auth cross-origin rejection behavior in the legacy POST routes.
- [x] Rerun focused client route tests.

## Review

- Added legacy query/upload route coverage for mismatched `Origin` and cross-site `Sec-Fetch-Site`, proving the routes return 403 and do not proxy to the backend.
- Implemented a shared backend-proxy origin/fetch-metadata check and called it before body parsing in both legacy POST routes.
- Red step: `npm test -- src/app/api/query/route.test.ts src/app/api/upload/route.test.ts` failed 4 new tests because the routes returned backend 502 errors instead of cross-origin 403.
- Green step: focused route tests passed 12 tests; expanded focused proxy tests passed 19 tests across 3 files.

# Fix Render Postgres Deployment Startup

- [x] Confirm the Render traceback points to SQLAlchemy's Postgres driver import.
- [x] Add a deployment-config regression test for the Postgres driver and Render migration start command.
- [x] Add the missing Postgres DBAPI dependency and align README deployment instructions with `render.yaml`.
- [x] Verify focused deployment-config tests and backend test suite.

## Review

- Root cause: Render used a Postgres `DATABASE_URL`, so SQLAlchemy selected the `psycopg2` dialect driver, but `psycopg2` was not installed by `server/requirements.txt`.
- Added `psycopg2-binary` to backend requirements and regression coverage so this deployment dependency does not get removed accidentally.
- Confirmed `render.yaml` already runs Alembic before Uvicorn, then fixed README to document the same command and warn manual Render services must copy it into the dashboard.
- Verified `tests.test_deployment_config`, full backend unittest discovery, dependency installation through `uv pip`, and a fake-Postgres SQLAlchemy import smoke reporting driver `psycopg2`.

# Add Self-Service Accounts And Production DB Guidance

- [x] Add registration and password reset backend tests before implementation.
- [x] Implement organization-creating registration, forgot-password, and reset-password endpoints.
- [x] Remove static seeded demo accounts and default demo credentials from code/docs.
- [x] Add client auth helpers, proxy routes, and account-first login/register/reset UI.
- [x] Verify backend/client full test, lint, typecheck, build, e2e, and migration smoke.
- [x] Generate one-time JWT secret for user copy/paste without reading local env files.

## Review

- Added self-service registration, forgot-password, and reset-password flows while keeping organization creation scoped to the registered admin user.
- Removed static demo account seeding and visible default demo credentials from backend, client, tests, and README.
- Hardened the login form against stale browser autofill so removed demo credentials do not reappear in persistent local browser profiles.
- Verified with backend unittest discovery, Alembic migration smoke, client lint/typecheck/unit/build, Playwright desktop/mobile e2e, browser-rendered login fields, and a static search for removed demo credentials.
- Generated the JWT secret for copy/paste only; it was not written to the repo or read from any `.env` file.

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
- Post-review safety fixes: draft approval now requires current citation verification, effective evidence overrides control readiness/drafts/citations, `met` overrides require existing citation-backed evidence, low-readiness cases serialize as `needs_more_documentation`, typed uploads enforce size limits, assignees must belong to the org, criteria edits are audited, and mutating Next proxy routes reject cross-origin requests.
- Final verification after review fixes: backend unittest discover passed 42 tests, client Vitest passed 25 tests across 7 files, client lint/typecheck/build passed, and Playwright desktop/mobile e2e passed 4 tests.

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
