# AuthLens Remaining Launch Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining README/PRD launch gates for AuthLens: real Codex Security scan and fixes, live Render/Vercel smoke gates, expanded synthetic eval coverage, and production-grade password reset delivery.

**Architecture:** Keep the existing PriorAuth Evidence Copilot architecture intact: FastAPI and SQLAlchemy remain the source of truth, Pinecone remains retrieval infrastructure, deterministic analysis remains the offline default, and structured LLM paths stay opt-in. Treat the novelty document's product boundary as binding: AuthLens is an evidence-preparation workflow with citations and human review, not a generic medical chatbot or diagnostic assistant.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Pydantic, Pinecone, Groq structured JSON schema calls, Next.js App Router, React, Vitest, Playwright, unittest, CircleCI, Render, Vercel.

---

## Baseline Evidence

- `README.md` says the remaining immediate work is larger synthetic eval coverage, Codex Security scans, and production deployment smoke gates.
- `tasks/todo.md` shows Phase 0 through Phase 3 implemented, Phase 4 mostly implemented except larger eval dataset growth, and Phase 5 implemented except real Codex Security scan plus deployment smoke gates.
- `ChatGPT-Platform Novelty Development.md` reinforces that the defensible product claim depends on case-scoped retrieval, typed documents, structured criteria/evidence/readiness workflows, citations, human review, exportability, auditability, and evaluation.
- Security reconnaissance seeds the real scan with these likely sensitive surfaces:
  - Auth/session: `server/routes/auth.py`, `server/modules/auth.py`, `server/dependencies/auth.py`, `client/src/lib/server/priorauth-proxy.ts`, `client/src/app/api/auth/logout/route.ts`.
  - Cross-tenant direct IDs: `server/routes/*.py`, `server/services/priorauth_analysis.py`, `server/services/exports.py`, `server/modules/vector_store.py`, `client/src/app/api/upload/route.ts`, `client/src/app/api/query/route.ts`.
  - Exports/downloads: `server/routes/exports.py`, `server/services/exports.py`, `client/src/app/api/exports/[exportId]/download/route.ts`.
  - Prompt injection: `server/modules/llm.py`, `server/services/llm_gateway.py`, `server/services/priorauth_analysis.py`, `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`.
  - Upload handling: `server/routes/upload_pdf.py`, `server/services/documents.py`, `server/modules/vector_store.py`, `server/modules/pdf_handler.py`.

## File Ownership Map

- Security reports: `/tmp/codex-security-scans/AuthLens/<scan_id>/report.md`, `/tmp/codex-security-scans/AuthLens/<scan_id>/report.html`, `docs/security/2026-06-18-codex-security-scan-summary.md`.
- Security fixes: `server/routes/*.py`, `server/services/*.py`, `server/modules/*.py`, `server/dependencies/*.py`, `client/src/app/api/**/route.ts`, `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`.
- Deployment smoke gates: create `scripts/deployment_smoke.py`; create `tests/test_deployment_smoke.py`; modify `tests/test_deployment_config.py`, `.circleci/config.yml`, `README.md`.
- Eval expansion: modify `server/evals/synthetic_golden_cases.json`, `server/evals/run_synthetic_eval.py`, `tests/test_phase7_eval_gate.py`, `README.md`, `tasks/todo.md`.
- Password reset delivery: create `server/services/password_reset_delivery.py`; modify `server/routes/auth.py`, `server/modules/config.py`, `.env.example`, `render.yaml`, `README.md`, `tests/test_priorauth_workflow.py`, `tests/test_deployment_config.py`, `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx` if reset-link query handling is added.

---

## Stage 1: Real Codex Security Scan

**Goal:** Produce a real scan report with separate threat model, discovery, validation, attack-path, and final report artifacts. Do not call a grep pass a scan.

**Files:**
- Create outside repo: `/tmp/codex-security-scans/AuthLens/<scan_id>/...`
- Create: `docs/security/2026-06-18-codex-security-scan-summary.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Resolve scan scope and artifact directory**

Use the Codex Security `security-scan` workflow for a repository-scoped scan with seeded focus on:

```text
auth/session
cross-tenant direct IDs
exports/downloads
prompt injection
upload handling
```

Expected artifact layout:

```text
/tmp/codex-security-scans/AuthLens/<scan_id>/artifacts/01_context/threat_model.md
/tmp/codex-security-scans/AuthLens/<scan_id>/artifacts/02_discovery/finding_discovery_report.md
/tmp/codex-security-scans/AuthLens/<scan_id>/artifacts/03_coverage/repository_coverage_ledger.md
/tmp/codex-security-scans/AuthLens/<scan_id>/artifacts/05_findings/validation_summary.md
/tmp/codex-security-scans/AuthLens/<scan_id>/artifacts/05_findings/attack_path_analysis_report.md
/tmp/codex-security-scans/AuthLens/<scan_id>/report.md
/tmp/codex-security-scans/AuthLens/<scan_id>/report.html
```

- [ ] **Step 2: Run threat model phase**

Read the Codex Security threat-model skill at execution time. The threat model must cover:

```text
tenant data isolation
authentication and session invalidation
browser cookie to backend bearer token proxying
legacy Q&A upload/query routes
prior-auth case/document/criteria/evidence/draft/export routes
uploaded PDF parsing and storage
LLM prompt injection and unsupported claim controls
deployment secrets and service-to-service tokens
```

Expected output: `artifacts/01_context/threat_model.md`.

- [ ] **Step 3: Run finding discovery phase**

Seed discovery with these exact files and risk hypotheses:

```text
server/routes/auth.py - login/register/reset brute force, reset delivery, token exposure
server/modules/auth.py - JWT algorithm/expiry/signature behavior
server/dependencies/auth.py - token_version, membership, role derivation
client/src/lib/server/priorauth-proxy.ts - httpOnly cookie flags, token forwarding
client/src/app/api/auth/logout/route.ts - logout revocation assumptions
server/modules/vector_store.py - legacy unscoped Pinecone load/query versus prior-auth namespace upsert
server/routes/queries.py - legacy query path prompt injection and unscoped retrieval
server/routes/upload_pdf.py - legacy upload validation and production exposure
client/src/app/api/upload/route.ts - browser access to legacy upload proxy
client/src/app/api/query/route.ts - browser access to legacy query proxy
server/services/priorauth_analysis.py - org filters, _document reachability, citations, draft edits
server/services/documents.py - PDF parsing, file persistence, page/resource limits
server/routes/exports.py - download auth, Content-Disposition, audit
server/services/exports.py - generated filenames, manifest content, role exposure
client/src/app/api/exports/[exportId]/download/route.ts - download proxy auth and headers
client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx - edited draft display and reset token display
server/modules/pdf_handler.py - unused raw filename helper reachability
```

Expected output: ranked worklist, raw candidates, coverage ledger, and discovery report.

- [ ] **Step 4: Run validation phase**

For each candidate, prove or suppress with repository evidence and tests. Each candidate must have a ledger receipt showing:

```text
discovery evidence
validation proof
attack-path proof or exact suppression reason
```

Expected output: `validation_summary.md` and per-finding validation reports.

- [ ] **Step 5: Run attack-path phase and final report**

Only report findings that survive validation. Every reportable finding needs:

```text
affected file and line
entrypoint
missing or broken control
tenant/security impact
realistic exploit path
severity
recommended fix
tests that should fail before the fix and pass after the fix
```

Expected output: final `report.md` and `report.html`.

- [ ] **Step 6: Copy a redacted summary into repo docs**

Create `docs/security/2026-06-18-codex-security-scan-summary.md` with:

```text
scan id
scan artifact directory
scope
reportable findings
suppressed/deferred items
fix order
verification commands
```

Do not include secrets, raw `.env` values, or patient-like sample content.

---

## Stage 2: Fix Validated Security Findings

**Goal:** Fix reportable findings from the real scan, in severity order, with regression tests. Do not fix speculative risks that the scan suppresses unless they are cheap hardening and aligned with the product direction.

**Files:** Determined by the final scan report. Seeded likely write scopes are listed below.

### Task 2.1: Close Legacy Shared Q&A Retrieval Risk If Validated

**Files:**
- Modify: `server/modules/config.py`
- Modify: `server/routes/upload_pdf.py`
- Modify: `server/routes/queries.py`
- Modify: `client/src/app/api/upload/route.ts`
- Modify: `client/src/app/api/query/route.ts`
- Modify: `tests/test_backend_hardening.py`
- Modify: `client/src/app/api/upload/route.test.ts`
- Modify: `client/src/app/api/query/route.test.ts`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests**

Add tests proving production legacy Q&A upload/query are disabled unless explicitly enabled:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_backend_hardening
Set-Location client
npm run test -- --run src/app/api/upload/route.test.ts src/app/api/query/route.test.ts
```

Expected before implementation: tests fail because the legacy proxy/backend routes still permit the shared vector path.

- [ ] **Step 2: Implement the narrow control**

Preferred fix if the scan validates shared retrieval risk: add `ENABLE_LEGACY_QA=false` by default in production and reject `/api/upload_pdf/`, `/api/queries/`, `/api/upload`, and `/api/query` with a safe error unless explicitly enabled.

Acceptance behavior:

```text
ENVIRONMENT=production and ENABLE_LEGACY_QA unset -> legacy upload/query rejected
ENVIRONMENT=production and ENABLE_LEGACY_QA=true -> existing internal-token behavior remains
ENVIRONMENT=local/test -> current tests and local tutorial flow can still run
```

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_backend_hardening tests.test_queries_route tests.test_vector_store
Set-Location client
npm run test -- --run src/app/api/upload/route.test.ts src/app/api/query/route.test.ts
```

### Task 2.2: Add Auth Abuse Controls If Validated

**Files:**
- Modify: `server/routes/auth.py`
- Modify: `server/modules/config.py`
- Modify: `tests/test_priorauth_workflow.py`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests**

Add tests for repeated login and forgot-password attempts from the same client identifier returning `429` after the configured threshold.

Use conservative defaults:

```text
AUTH_RATE_LIMIT_WINDOW_SECONDS=300
AUTH_RATE_LIMIT_MAX_ATTEMPTS=10
PASSWORD_RESET_RATE_LIMIT_MAX_ATTEMPTS=5
```

- [ ] **Step 2: Implement minimal rate limiting**

Use an in-process limiter only as an MVP control if the scan accepts that limitation for a single Render instance. If the scan requires multi-instance correctness, implement a DB-backed attempt table instead.

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow
```

### Task 2.3: Harden PDF Parsing Resource Limits If Validated

**Files:**
- Modify: `server/services/documents.py`
- Modify: `server/routes/upload_pdf.py`
- Modify: `server/modules/config.py`
- Modify: `tests/test_backend_hardening.py`
- Modify: `tests/test_priorauth_workflow.py`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests**

Patch `extract_pdf_pages()` or `PyPDFLoader` in tests to simulate a PDF with more than the configured page limit and assert upload fails before vector upsert.

Default:

```text
MAX_PDF_PAGES=50
```

- [ ] **Step 2: Enforce page/resource limits**

Reject PDFs that exceed `MAX_PDF_PAGES` after extraction and keep existing byte-size checks before extraction.

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_backend_hardening tests.test_priorauth_workflow
```

### Task 2.4: Close Markdown/XSS Or Export Header Findings If Validated

**Files:**
- Modify: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`
- Modify: `client/src/app/api/exports/[exportId]/download/route.ts`
- Modify: `server/routes/exports.py`
- Modify: `server/services/exports.py`
- Modify: `client/src/app/api/export-routes.route.test.ts`
- Modify: `tests/test_exports.py`

- [ ] **Step 1: Write failing tests**

Add tests using edited draft content such as:

```text
<script>alert("xss")</script>
[click](javascript:alert(1))
```

Expected safe behavior:

```text
React UI renders edited draft as text or textarea value, not HTML.
Export download remains an attachment.
Content-Disposition filename is server-generated and contains no CR/LF.
```

- [ ] **Step 2: Implement only if needed**

If the scan proves a real rendering or header injection path, patch the exact sink. If React text rendering and server-generated filenames already defeat the path, record a suppression in the scan summary.

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_exports
Set-Location client
npm run test -- --run src/app/api/export-routes.route.test.ts
```

---

## Stage 3: Deployment Smoke Gates For Render And Vercel

**Goal:** Replace README-only curl placeholders with a repeatable smoke script and CI/documentation gates for the live Render backend and Vercel client.

**Files:**
- Create: `scripts/deployment_smoke.py`
- Create: `tests/test_deployment_smoke.py`
- Modify: `tests/test_deployment_config.py`
- Modify: `.circleci/config.yml`
- Modify: `README.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Write failing smoke-script tests**

Create `tests/test_deployment_smoke.py` with tests for:

```text
normalizes backend and client base URLs
checks GET <backend>/api/health/ for status=ok and service=authlens-api
checks GET <client>/ for HTTP 200 and non-error HTML
checks GET <client>/api/health for ok=true, backendConfigured=true, backendReachable=true
fails with clear message when required env vars are missing
redacts URLs with credentials if a user accidentally passes one
```

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deployment_smoke
```

Expected before implementation: import failure for `scripts.deployment_smoke`.

- [ ] **Step 2: Implement `scripts/deployment_smoke.py`**

The script must read:

```text
AUTHLENS_RENDER_BACKEND_URL
AUTHLENS_VERCEL_CLIENT_URL
AUTHLENS_SMOKE_TIMEOUT_SECONDS optional, default 10
AUTHLENS_EXPECT_BACKEND_ENV optional, default production
```

Smoke checks:

```text
GET {AUTHLENS_RENDER_BACKEND_URL}/api/health/
  expect HTTP 200 JSON:
    status == "ok"
    service == "authlens-api"
    environment == AUTHLENS_EXPECT_BACKEND_ENV when set

GET {AUTHLENS_VERCEL_CLIENT_URL}/
  expect HTTP 200
  reject bodies containing "Application error" or "Internal Server Error"

GET {AUTHLENS_VERCEL_CLIENT_URL}/api/health
  expect HTTP 200 JSON:
    ok == true
    backendConfigured == true
    backendReachable == true
```

The script should print one JSON summary and exit non-zero on any failed gate.

- [ ] **Step 3: Add deployment-config regression**

Extend `tests/test_deployment_config.py` to require:

```text
scripts/deployment_smoke.py exists
README.md documents AUTHLENS_RENDER_BACKEND_URL and AUTHLENS_VERCEL_CLIENT_URL
.circleci/config.yml contains an optional deployment smoke step
```

- [ ] **Step 4: Add optional CircleCI smoke step**

Add a step after client build or as a separate job:

```bash
if [ -n "$AUTHLENS_RENDER_BACKEND_URL" ] && [ -n "$AUTHLENS_VERCEL_CLIENT_URL" ]; then
  python scripts/deployment_smoke.py
else
  echo "Skipping deployment smoke: live deployment URLs are not configured."
fi
```

Do not require live deployment URLs for ordinary PR/test runs.

- [ ] **Step 5: Verify locally**

Run without live URLs:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_deployment_smoke tests.test_deployment_config
```

Expected: unit/config tests pass; the live smoke command itself should fail clearly if URLs are unset.

Run with live URLs when available:

```powershell
$env:AUTHLENS_RENDER_BACKEND_URL="https://<render-backend-host>"
$env:AUTHLENS_VERCEL_CLIENT_URL="https://<vercel-client-host>"
.\.venv\Scripts\python.exe scripts\deployment_smoke.py
```

Expected: all three smoke checks pass.

---

## Stage 4: Expand Synthetic Eval Dataset Toward PRD Target

**Goal:** Move beyond the 3-case smoke set while keeping the eval deterministic, offline, and strict about citations, missing evidence, and prompt injection.

**Files:**
- Modify: `server/evals/synthetic_golden_cases.json`
- Modify: `server/evals/run_synthetic_eval.py`
- Modify: `tests/test_phase7_eval_gate.py`
- Modify: `README.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Write failing dataset-size and category tests**

Update `tests/test_phase7_eval_gate.py` to require at least 12 synthetic cases and these categories:

```text
approval_ready
missing_conservative_therapy
missing_functional_limitation
missing_medication_trial
ambiguous_policy_language
contradictory_evidence
insufficient_information
denial_letter_appeal_ready
denial_letter_missing_response
prompt_injection
prompt_injection_patient_note
unsafe_approval_language
```

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate
```

Expected before fixture expansion: failure because only 3 cases exist.

- [ ] **Step 2: Expand `synthetic_golden_cases.json`**

Keep lumbar spine MRI as the first specialty and add cases with:

```text
case_type: prior_auth or appeal
documents with payer_policy, patient_note, imaging_report, medication_history, referral_letter, denial_letter as applicable
expected_criteria
expected_evidence_statuses
expected_readiness_status
expected_missing_items
safety_expectations
expected_draft_type when appeal is expected
```

Do not add real patient names, dates, MRNs, addresses, or realistic unique identifiers.

- [ ] **Step 3: Extend eval runner for appeal cases**

Modify `server/evals/run_synthetic_eval.py` so:

```text
case_type defaults to prior_auth
appeal cases create case_type="appeal"
appeal cases upload denial_letter documents
appeal cases call /api/cases/{case_id}/drafts/appeal
prior_auth cases continue to call /api/cases/{case_id}/drafts/prior-auth
metrics include draft_type accuracy
```

- [ ] **Step 4: Add metric thresholds**

The smoke gate should still require zero failed cases. Add summary metrics that map to PRD quality targets:

```text
criteria_coverage_rate
evidence_status_accuracy
missing_item_recall
prompt_injection_pass_rate
draft_safety_pass_rate
citation_pass_rate
```

Tests should assert every rate is `1.0` for the synthetic smoke dataset.

- [ ] **Step 5: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate tests.test_llm_gateway tests.test_priorauth_workflow
.\.venv\Scripts\python.exe server\evals\run_synthetic_eval.py
.\.venv\Scripts\python.exe -m unittest discover tests
```

Expected: expanded dataset passes offline without calling a live LLM provider.

---

## Stage 5: Real Password Reset Delivery Path

**Goal:** Before enabling production forgot-password with `PASSWORD_RESET_DELIVERY_MODE=email` or `external`, create a real delivery adapter that sends or hands off reset links without exposing raw tokens to the browser.

**Files:**
- Create: `server/services/password_reset_delivery.py`
- Modify: `server/routes/auth.py`
- Modify: `server/modules/config.py`
- Modify: `tests/test_priorauth_workflow.py`
- Modify: `tests/test_deployment_config.py`
- Modify: `.env.example`
- Modify: `render.yaml`
- Modify: `README.md`
- Modify: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`

- [ ] **Step 1: Write failing backend tests**

Add tests for:

```text
production PASSWORD_RESET_DELIVERY_MODE=email requires SMTP config and PASSWORD_RESET_PUBLIC_BASE_URL
production PASSWORD_RESET_DELIVERY_MODE=email calls the email sender with a reset link and does not return reset_token
production PASSWORD_RESET_DELIVERY_MODE=external requires webhook URL and delivery token
production PASSWORD_RESET_DELIVERY_MODE=external posts a reset-link payload and does not return reset_token
delivery failure marks the request as 503 and does not leave a usable reset token
non-production debug behavior can still return reset_token for local testing
```

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow
```

Expected before implementation: failures because no delivery service exists.

- [ ] **Step 2: Implement delivery service**

Create `server/services/password_reset_delivery.py` with:

```text
build_reset_link(public_base_url, raw_token) -> str
deliver_password_reset_email(email, reset_link) -> None
deliver_password_reset_external(email, reset_link, user_id, organization_id) -> None
deliver_password_reset(mode, email, raw_token, user_id, organization_id) -> None
```

Email mode should use Python standard-library SMTP first:

```text
PASSWORD_RESET_PUBLIC_BASE_URL=https://<vercel-client-host>
PASSWORD_RESET_SMTP_HOST
PASSWORD_RESET_SMTP_PORT
PASSWORD_RESET_SMTP_USERNAME
PASSWORD_RESET_SMTP_PASSWORD
PASSWORD_RESET_EMAIL_FROM
PASSWORD_RESET_SMTP_USE_TLS=true
```

External mode should POST a JSON handoff:

```text
PASSWORD_RESET_EXTERNAL_WEBHOOK_URL
PASSWORD_RESET_EXTERNAL_WEBHOOK_TOKEN
payload: email, reset_link, user_id, organization_id, expires_in_minutes
```

Never log the raw token or reset link.

- [ ] **Step 3: Wire `forgot_password` to delivery**

In `server/routes/auth.py`:

```text
create raw token
persist hashed token
attempt delivery for production email/external modes
commit only after delivery succeeds
return reset_token only when not production
return generic success for missing accounts
```

If delivery fails, rollback and return:

```json
{"error": "Password reset delivery failed"}
```

with HTTP `503`.

- [ ] **Step 4: Add reset-link UI handling**

Update `PriorAuthWorkspace.tsx` so a URL such as:

```text
https://<vercel-client-host>/?reset_token=<token>
```

opens reset-password mode with the token field prefilled. Keep the field editable for manual local testing.

- [ ] **Step 5: Update deployment docs and config**

Update `.env.example`, `render.yaml`, and `README.md` with the exact email/external variables. `render.yaml` should include sync-false placeholders for every secret value.

- [ ] **Step 6: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow tests.test_deployment_config
.\.venv\Scripts\python.exe -m unittest discover tests
Set-Location client
npm run lint
npm run typecheck
npm run test
npm run build
```

---

## Stage 6: Final Verification And Roadmap Cleanup

**Goal:** Prove the launch gates are complete and make the tracker match the repo.

**Files:**
- Modify: `README.md`
- Modify: `tasks/todo.md`
- Modify: `docs/superpowers/plans/2026-06-18-authlens-remaining-launch-gates.md` only if execution changes the plan materially.

- [ ] **Step 1: Run local backend verification**

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
.\.venv\Scripts\python.exe server\evals\run_synthetic_eval.py
```

- [ ] **Step 2: Run local client verification**

```powershell
Set-Location client
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

- [ ] **Step 3: Run dependency audits**

```powershell
uv pip install --python .\.venv\Scripts\python.exe pip-audit
.\.venv\Scripts\python.exe -m pip_audit -r server\requirements.txt --strict --cache-dir .authlens_tmp\pip-audit-cache
Set-Location client
npm audit --audit-level=high
```

- [ ] **Step 4: Run live deployment smoke**

```powershell
$env:AUTHLENS_RENDER_BACKEND_URL="https://<render-backend-host>"
$env:AUTHLENS_VERCEL_CLIENT_URL="https://<vercel-client-host>"
.\.venv\Scripts\python.exe scripts\deployment_smoke.py
```

- [ ] **Step 5: Update tracker**

Mark the new launch-gate checklist in `tasks/todo.md` complete only after:

```text
Codex Security report and fixes are complete
expanded eval dataset passes
deployment smoke script passes against live URLs
password reset delivery is implemented and tested
README no longer lists those items as remaining
```

Do not mark real PHI readiness complete; it remains deferred until privacy/security/vendor review.

