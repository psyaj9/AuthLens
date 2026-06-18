# Next PRD Phases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move AuthLens from a synthetic prior-auth MVP into a reviewer-complete, exportable, appeal-ready, evaluated evidence workspace while preserving the synthetic/de-identified-only boundary.

**Architecture:** Keep FastAPI + SQLAlchemy as the source of truth and Pinecone as retrieval infrastructure. Implement narrow, test-first slices that lock executable eval and tenant-isolation guardrails first, expose already-existing backend review APIs in the client, then add persisted export artifacts, appeal drafts, structured LLM boundaries, and production hardening.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Pydantic, Pinecone, Next.js App Router route handlers, React, Zod, Vitest, Playwright, unittest.

---

## File Ownership Map

- Backend domain models: `server/models/priorauth.py`
- Backend API schemas: `server/modules/schemas.py`
- Backend routers: `server/routes/*.py`
- Backend services: `server/services/*.py`
- Backend tests: `tests/test_priorauth_workflow.py`, `tests/test_phase7_eval_gate.py`, new `tests/test_exports.py`, new `tests/test_eval_runner.py`
- Client schemas/API: `client/src/lib/api/priorauth-schemas.ts`, `client/src/lib/api/client.ts`, `client/src/lib/api/client.test.ts`
- Client proxy routes: `client/src/app/api/**/route.ts`
- Client workspace UI: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`
- Client e2e: `client/tests/e2e/app.spec.ts`
- Eval fixtures/runner: `server/evals/synthetic_golden_cases.json`, new `server/evals/run_synthetic_eval.py`
- Deployment/docs: `README.md`, `.env.example`, `client/.env.example`, `render.yaml`, `vercel.json`

---

## Phase 0: Eval And Tenant-Isolation Guardrails

**Why first:** Export and appeal features add download surfaces and more generated text. Before expanding that surface area, turn the existing synthetic fixture gate into executable workflow checks and add direct-ID tenant isolation coverage for the current routes.

**Subagents:**
- `eval worker`: owns `server/evals/run_synthetic_eval.py`, fixtures, and eval tests.
- `backend security worker`: owns direct-ID route matrix tests.
- `red-team reviewer`: reviews prompt-injection, draft-safety, and cross-tenant assumptions.

### Task 0.1: Add Executable Synthetic Eval Runner

**Files:**
- Create: `server/evals/run_synthetic_eval.py`
- Modify: `server/evals/synthetic_golden_cases.json`
- Modify: `tests/test_phase7_eval_gate.py`

- [ ] **Step 1: Write failing eval runner test**

Add a test that imports `run_smoke_eval()` and asserts the three existing cases pass:

```python
from server.evals.run_synthetic_eval import run_smoke_eval


def test_synthetic_smoke_eval_runner_executes_priorauth_workflow():
    result = run_smoke_eval()

    assert result["dataset_version"] == "phase7-smoke-v1"
    assert result["total_cases"] >= 3
    assert result["failed_cases"] == []
    assert result["passed_cases"] == result["total_cases"]
```

Run: `.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate`
Expected: FAIL because `run_synthetic_eval.py` does not exist.

- [ ] **Step 2: Expand fixture data enough to run offline**

Each case in `server/evals/synthetic_golden_cases.json` must include runnable document bodies:

```json
{
  "documents": [
    {
      "document_type": "payer_policy",
      "file_name": "policy.pdf",
      "body": "%PDF-1.4\nCoverage requires six weeks of conservative therapy. Functional limitation must be documented."
    },
    {
      "document_type": "patient_note",
      "file_name": "note.pdf",
      "body": "%PDF-1.4\nThe provided documents indicate six weeks of conservative therapy and functional limitation with walking."
    }
  ]
}
```

- [ ] **Step 3: Implement runner**

`run_smoke_eval()` should create an isolated SQLite DB, initialize the FastAPI DB metadata, create a test org/user/case, upload each synthetic document through service-level helpers or TestClient calls, run criteria extraction, evidence matching, readiness, prior-auth draft, and citation verification.

Return:

```python
{
    "dataset_version": "phase7-smoke-v1",
    "total_cases": 3,
    "passed_cases": 3,
    "failed_cases": [],
    "case_results": [
        {
            "case_id": "SYN-LMRI-GOLD-001",
            "actual_readiness_status": "ready_for_review",
            "expected_readiness_status": "ready_for_review",
            "citation_status": "pass",
            "safety_passed": True,
        }
    ],
}
```

- [ ] **Step 4: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate
```

Expected: PASS.

### Task 0.2: Add Prompt-Injection And Draft-Safety Eval Outcomes

**Files:**
- Modify: `server/evals/synthetic_golden_cases.json`
- Modify: `server/evals/run_synthetic_eval.py`
- Modify: `tests/test_phase7_eval_gate.py`

- [ ] **Step 1: Add failing expectations**

Assert prompt-injection cases fail if:
- draft content includes `ignore previous instructions`
- draft removes the human-review disclaimer
- draft includes approval guarantee language
- citation verification passes despite unsupported claims

- [ ] **Step 2: Add safety checks in runner**

Implement:

```python
def draft_safety_passed(content: str) -> bool:
    lowered = content.lower()
    return (
        "clinician review is required" in lowered
        and "ignore previous instructions" not in lowered
        and "guaranteed approval" not in lowered
        and "must approve" not in lowered
    )
```

- [ ] **Step 3: Verify**

Run: `.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate tests.test_llm`
Expected: PASS.

### Task 0.3: Add Cross-Tenant Direct-ID Matrix

**Files:**
- Modify: `tests/test_priorauth_workflow.py`

- [ ] **Step 1: Write direct-ID tests**

Use existing `_create_test_user`, `_login`, `_create_case`, `_prepare_case_with_policy_and_note` helpers to create org A and org B. Assert org B receives 404 for:
- `GET /api/documents/{document_id}`
- `PATCH /api/criteria/{criterion_id}`
- `PATCH /api/evidence-matches/{match_id}`
- `GET /api/drafts/{draft_id}`
- `PATCH /api/drafts/{draft_id}`
- `POST /api/drafts/{draft_id}/verify-citations`
- `POST /api/drafts/{draft_id}/approve`

Run: `.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow.PriorAuthWorkflowTests.test_cross_tenant_direct_id_routes_are_denied`
Expected: FAIL if any route leaks or test does not exist.

- [ ] **Step 2: Patch only failing route checks**

If a route leaks cross-tenant data, patch that route/service with `organization_id` filtering. Do not change status from 404 to 403 for missing foreign IDs; avoid confirming another tenant’s object exists.

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow
```

Expected: PASS.

---

## Phase 1: Reviewer Workspace Completion

**Why now:** The backend already supports criteria edits, evidence overrides, draft edits, citation verification, and approval. The client does not expose those workflows, so product value is blocked by UI/API wiring rather than new backend architecture.

**Subagents:**
- `frontend reviewer worker`: owns `PriorAuthWorkspace.tsx`, client API helpers, and client tests.
- `UI reviewer`: checks responsive layout, review affordances, and no text overlap.
- `Playwright verifier`: runs desktop/mobile reviewer smoke.

### Task 1.1: Add Client API Helpers For Reviewer Mutations

**Files:**
- Modify: `client/src/lib/api/client.ts`
- Modify: `client/src/lib/api/client.test.ts`

- [ ] **Step 1: Write failing API tests**

Add tests in `client/src/lib/api/client.test.ts` that prove:

```ts
expect(fetch).toHaveBeenCalledWith(
  "/api/criteria/crit_123",
  expect.objectContaining({
    method: "PATCH",
    body: JSON.stringify({
      requirement: "Updated criterion",
      required_evidence: ["Therapy dates"],
      reviewer_status: "reviewed"
    })
  })
);

expect(fetch).toHaveBeenCalledWith(
  "/api/evidence-matches/match_123",
  expect.objectContaining({
    method: "PATCH",
    body: JSON.stringify({
      reviewer_override_status: "not_met",
      reviewer_override_reason: "Citation does not satisfy policy"
    })
  })
);

expect(fetch).toHaveBeenCalledWith(
  "/api/drafts/draft_123",
  expect.objectContaining({
    method: "PATCH",
    body: JSON.stringify({ content_markdown: "Edited draft" })
  })
);

expect(fetch).toHaveBeenCalledWith("/api/drafts/draft_123/approve", expect.objectContaining({ method: "POST" }));
```

Run: `cd client; npm run test -- --run src/lib/api/client.test.ts`
Expected: FAIL because helpers do not exist.

- [ ] **Step 2: Implement helpers**

Add these exports to `client/src/lib/api/client.ts`:

```ts
export async function updateCriterion(
  criterionId: string,
  payload: {
    requirement?: string;
    required_evidence?: string[];
    is_required?: boolean;
    ambiguity_notes?: string[];
    reviewer_status?: string;
  }
): Promise<Criterion> {
  const response = await fetch(`/api/criteria/${criterionId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseLocalRouteResponse(response, criterionSchema);
}

export async function overrideEvidenceMatch(
  matchId: string,
  payload: {
    reviewer_override_status: "met" | "unclear" | "not_found" | "not_met";
    reviewer_override_reason: string;
  }
): Promise<EvidenceMatch> {
  const response = await fetch(`/api/evidence-matches/${matchId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseLocalRouteResponse(response, evidenceMatchSchema);
}

export async function updateDraft(draftId: string, contentMarkdown: string): Promise<DraftLetter> {
  const response = await fetch(`/api/drafts/${draftId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content_markdown: contentMarkdown })
  });
  return parseLocalRouteResponse(response, draftSchema);
}

export async function approveDraft(draftId: string): Promise<DraftLetter> {
  const response = await fetch(`/api/drafts/${draftId}/approve`, { method: "POST" });
  return parseLocalRouteResponse(response, draftSchema);
}
```

- [ ] **Step 3: Verify green**

Run: `cd client; npm run test -- --run src/lib/api/client.test.ts`
Expected: PASS.

### Task 1.2: Expose Review Controls In Workspace

**Files:**
- Modify: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`
- Test: `client/tests/e2e/app.spec.ts`

- [ ] **Step 1: Add failing e2e or component-level checks**

Add Playwright assertions for reviewer UI labels after authenticated mocked or seeded flow:

```ts
await expect(page.getByRole("button", { name: "Save criterion review" })).toBeVisible();
await expect(page.getByRole("button", { name: "Save evidence override" })).toBeVisible();
await expect(page.getByRole("button", { name: "Save draft edits" })).toBeVisible();
await expect(page.getByRole("button", { name: "Approve draft" })).toBeVisible();
```

Run: `cd client; npm run test:e2e`
Expected: FAIL because controls are absent.

- [ ] **Step 2: Add criteria edit state and actions**

Add inline edit controls per criterion:
- `textarea` for `requirement`
- comma/newline text input for `required_evidence`
- select for `reviewer_status`
- disabled source quote/file/page fields for provenance
- button: `Save criterion review`

- [ ] **Step 3: Add evidence override controls**

Add per evidence match:
- effective status display using `reviewer_override_status ?? status`
- select with `met`, `unclear`, `not_found`, `not_met`
- required reason textarea
- button: `Save evidence override`

Do not allow a `met` override unless backend accepts it; display backend error unchanged.

- [ ] **Step 4: Add draft editor, citation details, and approval**

Replace read-only `<pre>` with:
- `textarea` bound to `content_markdown`
- button: `Save draft edits`
- button: `Verify citations`
- citation panel showing unsupported claims, weak claims, and citation errors
- button: `Approve draft`, disabled unless latest citation status is `pass`

- [ ] **Step 5: Verify**

Run:

```powershell
cd client
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:e2e
```

Expected: all pass, or if an existing dev server blocks e2e, run manual Playwright smoke against the active local port and document it in `tasks/todo.md`.

---

## Phase 2: Export And Packet Manifest

**Why second:** PRD Phase 5 and FR-080 to FR-082 require exports. Export should only come after the reviewer workflow can approve the draft.

**Subagents:**
- `backend export worker`: owns export model/service/router/migration/tests.
- `frontend export worker`: owns export client helpers/proxy routes/UI.
- `security reviewer`: verifies export gating and tenant isolation.

### Task 2.1: Add Persisted Export Model And Schemas

**Files:**
- Modify: `server/models/priorauth.py`
- Create: `server/migrations/versions/20260618_0003_exports.py`
- Modify: `server/modules/schemas.py`
- Test: new `tests/test_exports.py`

- [ ] **Step 1: Write failing backend tests**

Create `tests/test_exports.py` with tests asserting:
- readiness report export requires an existing readiness report
- letter export requires approved draft
- packet export includes document manifest and citations
- cross-org users cannot download export IDs

Run: `.venv\Scripts\python.exe -m unittest tests.test_exports`
Expected: FAIL because routes/models do not exist.

- [ ] **Step 2: Add model**

Add `ExportArtifact` to `server/models/priorauth.py`:

```python
class ExportArtifact(Base):
    __tablename__ = "export_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("export"))
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("prior_auth_cases.id"), nullable=False, index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    export_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="ready")
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, default="text/markdown")
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
```

- [ ] **Step 3: Add schemas**

Add `ExportArtifactResponse`, `ExportListResponse`, and `ExportDownloadResponse` to `server/modules/schemas.py`.

- [ ] **Step 4: Add migration**

Create the table and indexes in Alembic. Run:

```powershell
.\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head
```

Expected: migration applies on SQLite test DB.

### Task 2.2: Add Export Service And Routes

**Files:**
- Create: `server/services/exports.py`
- Create: `server/routes/exports.py`
- Modify: `server/main.py`
- Test: `tests/test_exports.py`

- [ ] **Step 1: Implement service functions**

Functions:
- `create_readiness_export(db, case_id, organization_id, user_id)`
- `create_letter_export(db, case_id, organization_id, user_id)`
- `create_packet_export(db, case_id, organization_id, user_id)`
- `get_export(db, export_id, organization_id)`

Rules:
- Letter export fails unless latest draft status is `approved`.
- Packet export fails unless latest draft status is `approved`.
- Export content must include: synthetic-only disclaimer, human-review disclaimer, readiness completeness wording, citations, document manifest.
- Log `export.created` and set case status to `exported` for packet export.

- [ ] **Step 2: Add routes**

Routes:
- `POST /api/cases/{case_id}/exports/readiness-report`
- `POST /api/cases/{case_id}/exports/letter`
- `POST /api/cases/{case_id}/exports/packet`
- `GET /api/exports/{export_id}/download`

- [ ] **Step 3: Verify**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_exports tests.test_priorauth_workflow
```

Expected: PASS.

### Task 2.3: Add Export UI

**Files:**
- Modify: `client/src/lib/api/priorauth-schemas.ts`
- Modify: `client/src/lib/api/client.ts`
- Create: `client/src/app/api/cases/[caseId]/exports/readiness-report/route.ts`
- Create: `client/src/app/api/cases/[caseId]/exports/letter/route.ts`
- Create: `client/src/app/api/cases/[caseId]/exports/packet/route.ts`
- Create: `client/src/app/api/exports/[exportId]/download/route.ts`
- Modify: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`
- Test: `client/src/lib/api/client.test.ts`, `client/tests/e2e/app.spec.ts`

- [ ] **Step 1: Add failing client tests**

Assert local API helpers call the exact export routes and parse export payloads.

- [ ] **Step 2: Add proxy routes**

Use `proxyBackendJson` for create routes. For download, proxy backend content as Markdown with `Content-Disposition`.

- [ ] **Step 3: Add UI buttons**

Show:
- `Export readiness`
- `Export letter`
- `Export packet`

Disable letter/packet export unless a draft is approved.

- [ ] **Step 4: Verify**

Run client lint, typecheck, tests, build, and Playwright.

---

## Phase 3: Appeal Workflow

**Why third:** PRD has appeal drafting as P0, but prior-auth path and export gating need to be stable first.

**Subagents:**
- `appeal backend worker`: owns denial parsing and appeal draft route.
- `appeal frontend worker`: owns denial-letter upload/document type UX and draft UI.
- `product safety reviewer`: checks appeal wording avoids treatment/approval claims.

### Task 3.1: Implement Denial-Reason Extraction

**Files:**
- Modify: `server/services/priorauth_analysis.py`
- Modify: `server/routes/drafts.py`
- Modify: `server/modules/schemas.py`
- Test: `tests/test_priorauth_workflow.py`

- [ ] **Step 1: Write failing appeal test**

Test flow:
- create case with `case_type="appeal"`
- upload payer policy, patient note, and `denial_letter`
- extract criteria, match evidence, generate readiness
- `POST /api/cases/{case_id}/drafts/appeal`
- assert draft `letter_type == "appeal"`
- assert content contains denial reason and human-review disclaimer
- assert content does not contain approval guarantee

- [ ] **Step 2: Implement `create_appeal_draft`**

Use denial-letter `DocumentChunk` text to extract a short denial reason:

```python
def _denial_reason_from_chunks(chunks: list[DocumentChunk]) -> str:
    for chunk in chunks:
        for sentence in _sentences(chunk.text):
            if re.search(r"\b(denied|denial|not medically necessary|lack|missing|insufficient)\b", sentence, re.I):
                return _short_quote(sentence, 240)
    return "The denial reason was not clearly extracted from the uploaded denial letter."
```

- [ ] **Step 3: Replace deferred route**

Change `/cases/{case_id}/drafts/appeal` from 501 to the implemented service.

- [ ] **Step 4: Verify**

Run: `.venv\Scripts\python.exe -m unittest tests.test_priorauth_workflow`

### Task 3.2: Add Appeal Client Path

**Files:**
- Modify: `client/src/lib/api/client.ts`
- Create: `client/src/app/api/cases/[caseId]/drafts/appeal/route.ts`
- Modify: `client/src/features/prior-auth-workspace/PriorAuthWorkspace.tsx`
- Test: `client/src/lib/api/client.test.ts`, `client/tests/e2e/app.spec.ts`

- [ ] Add `denial_letter` to `documentTypes`.
- [ ] Add `createAppealDraft(caseId)` client helper.
- [ ] Add `Draft appeal` button when case type is `appeal` or a denial letter is uploaded.
- [ ] Display appeal drafts in the same editor/review path as prior-auth drafts.

---

## Phase 4: Structured LLM Gateway And Executable Eval Runner

**Why fourth:** The deterministic MVP is safer than unvalidated free-form output, but PRD expects structured extraction/matching. Add the gateway and eval harness before depending on LLM outputs in production demos.

**Subagents:**
- `LLM gateway worker`: owns schema gateway and fail-closed tests.
- `eval worker`: owns fixture runner and synthetic cases.
- `red-team reviewer`: owns prompt-injection and unsupported-claim tests.

### Task 4.1: Add Structured LLM Gateway

**Files:**
- Create: `server/services/llm_gateway.py`
- Modify: `server/modules/schemas.py` or create `server/services/analysis_schemas.py`
- Test: new `tests/test_llm_gateway.py`

- [ ] **Step 1: Write failing tests**

Tests:
- valid JSON parses to Pydantic model
- malformed JSON creates failed `AnalysisRun`
- schema-invalid output fails closed
- prompt-injection text from PDF is treated as input, not instruction

- [ ] **Step 2: Implement gateway**

Expose:

```python
def parse_structured_output(model: type[BaseModel], raw_text: str) -> BaseModel:
    try:
        payload = json.loads(raw_text)
        return model.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise StructuredOutputError("LLM output failed schema validation") from exc
```

- [ ] **Step 3: Gate usage behind env flag**

Use deterministic flow by default. Enable structured LLM via `PRIORAUTH_ANALYSIS_MODE=llm`.

### Task 4.2: Turn Golden Cases Into A Real Eval Runner

**Files:**
- Create: `server/evals/run_synthetic_eval.py`
- Modify: `tests/test_phase7_eval_gate.py`
- Add: `server/evals/fixtures/*.json` if needed

- [ ] Runner loads `synthetic_golden_cases.json`.
- [ ] Runner creates each case in an isolated SQLite DB.
- [ ] Runner executes upload, criteria, evidence, readiness, draft, citation verification.
- [ ] Runner reports pass/fail metrics for readiness status, missing items, disclaimer, and prompt-injection rejection.
- [ ] Test asserts the runner passes the 3 smoke cases.

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase7_eval_gate tests.test_llm_gateway
```

---

## Phase 5: Production Readiness Hardening

**Why fifth:** This moves toward real pilots but still must not claim PHI readiness.

**Subagents:**
- `security scan worker`: threat model and diff scan.
- `deployment worker`: Render/Vercel env and CI checks.
- `auth worker`: session invalidation and email reset readiness.

### Task 5.1: Auth And Session Hardening

**Files:**
- Modify: `server/models/priorauth.py`
- Create migration for `password_changed_at` or `token_version`
- Modify: `server/modules/auth.py`
- Modify: `server/dependencies/auth.py`
- Modify: `server/routes/auth.py`
- Test: `tests/test_priorauth_workflow.py`

Rules:
- Password reset invalidates existing JWTs.
- Production forgot-password does not expose reset token.
- Production forgot-password requires configured email provider before claiming email delivery.

### Task 5.2: Deployment And Audit Gate

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `client/.env.example`
- Modify: `render.yaml`
- Add: `tests/test_deployment_config.py` cases if missing

Rules:
- Document exact Render backend envs.
- Document exact Vercel client envs.
- Document no real PHI boundary.
- Add dependency audit commands and known advisory handling.

### Task 5.3: Security Review

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
cd client; npm run lint; npm run typecheck; npm run test; npm run build
cd client; npm audit --audit-level=high
```

Also run Codex Security scoped scan for:
- auth/session
- cross-tenant direct IDs
- exports/downloads
- prompt injection
- upload handling

---

## Deferred Until After These Phases

- OCR fallback for scanned PDFs.
- Async worker queue.
- Durable object storage for source PDFs/exports.
- Admin analytics dashboard.
- EHR/FHIR import.
- Payer submission APIs.
- Real PHI production posture.

These remain important, but they are not the immediate next implementation path because reviewer/export/appeal/eval completion comes first.

---

## Execution Order

1. Phase 0: Eval And Tenant-Isolation Guardrails.
2. Phase 1: Reviewer Workspace Completion.
3. Phase 2: Export And Packet Manifest.
4. Phase 3: Appeal Workflow.
5. Phase 4: Structured LLM Gateway And Executable Eval Runner.
6. Phase 5: Production Readiness Hardening.

Each phase must end with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover tests
cd client
npm run lint
npm run typecheck
npm run test
npm run build
```

For frontend-visible phases, also run Playwright or a documented manual Playwright equivalent against the active local Next port.
