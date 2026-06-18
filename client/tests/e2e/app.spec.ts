import { expect, test, type Page } from "@playwright/test";

type WorkspaceMockOptions = {
  caseType?: "prior_auth" | "appeal";
  documents?: Array<Record<string, unknown>>;
  drafts?: Array<Record<string, unknown>>;
};

async function mockAuthenticatedReviewerWorkspace(page: Page, options: WorkspaceMockOptions = {}) {
  const caseType = options.caseType ?? "prior_auth";
  const initialDrafts = options.drafts ?? [
    {
      id: "draft_1",
      case_id: "case_1",
      letter_type: "prior_auth",
      status: "draft",
      content_markdown: "Clinician review is required before submission.\n[note.pdf, page 2]",
      created_by: "ai",
      approved_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    }
  ];
  const casePayload = {
    id: "case_1",
    patient_label: caseType === "appeal" ? "SYN-LMRI-APPEAL" : "SYN-LMRI-REVIEW",
    payer_name: "Example Health Plan",
    plan_name: null,
    specialty: "Radiology",
    requested_service: "Lumbar spine MRI",
    service_code: "72148",
    diagnosis_summary: null,
    case_type: caseType,
    status: "ready_for_review",
    readiness_score: 100,
    missing_required_criteria_count: 0,
    assigned_to_user_id: null,
    created_at: "2026-06-18T00:00:00Z",
    updated_at: "2026-06-18T00:00:00Z"
  };

  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "user_1",
        email: "reviewer@example.test",
        name: "Reviewer",
        role: "clinician_reviewer",
        organization: { id: "org_1", name: "Review Clinic", plan: "test" }
      })
    });
  });
  await page.route("**/api/cases", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ cases: [casePayload] })
    });
  });
  await page.route("**/api/cases/case_1/documents", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ documents: options.documents ?? [] })
    });
  });
  await page.route("**/api/cases/case_1/criteria", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        criteria: [
          {
            id: "crit_1",
            criterion_code: "C1",
            criterion_type: "documentation",
            requirement: "Coverage requires six weeks of conservative therapy.",
            required_evidence: ["Therapy dates"],
            is_required: true,
            source_file: "policy.pdf",
            source_page: "1",
            source_quote: "Coverage requires six weeks of conservative therapy.",
            confidence: 0.82,
            ambiguity_notes: [],
            reviewer_status: "unreviewed"
          }
        ]
      })
    });
  });
  await page.route("**/api/cases/case_1/evidence", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        matches: [
          {
            id: "match_1",
            criterion_id: "crit_1",
            status: "met",
            evidence_summary: "Patient documentation supports C1.",
            source_file: "note.pdf",
            source_page: "2",
            source_quote: "Six weeks of therapy are documented.",
            why_it_matters: "Reviewer should confirm the citation.",
            missing_evidence: [],
            conflicting_evidence: [],
            recommended_action: "Clinician reviewer should confirm the cited evidence before submission.",
            confidence: 0.86,
            reviewer_override_status: null,
            reviewer_override_reason: null
          }
        ]
      })
    });
  });
  await page.route("**/api/cases/case_1/drafts", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ drafts: initialDrafts })
    });
  });
  await page.route("**/api/cases/case_1/drafts/appeal", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "draft_appeal_1",
        case_id: "case_1",
        letter_type: "appeal",
        status: "draft",
        content_markdown:
          "Denial reason identified from payer letter: not medically necessary [denial.pdf, page 1]\nClinician review is required before appeal submission.\n[note.pdf, page 2]",
        created_by: "ai",
        approved_at: null,
        created_at: "2026-06-18T00:00:00Z",
        updated_at: "2026-06-18T00:00:00Z"
      })
    });
  });
  await page.route("**/api/drafts/draft_1/verify-citations", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "cite_1",
        draft_letter_id: "draft_1",
        verification_status: "pass",
        unsupported_claims: [],
        weakly_supported_claims: [],
        citation_errors: [],
        safe_to_show_user: true,
        created_at: "2026-06-18T00:00:00Z"
      })
    });
  });
  await page.route("**/api/drafts/draft_1/approve", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "draft_1",
        case_id: "case_1",
        letter_type: "prior_auth",
        status: "approved",
        content_markdown: "Clinician review is required before submission.\n[note.pdf, page 2]",
        created_by: "ai",
        approved_at: "2026-06-18T00:00:00Z",
        created_at: "2026-06-18T00:00:00Z",
        updated_at: "2026-06-18T00:00:00Z"
      })
    });
  });
  await page.route("**/api/cases/case_1/exports/packet", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "export_1",
        case_id: "case_1",
        export_type: "packet",
        status: "ready",
        file_name: "syn-lmri-review-prior-auth-packet.md",
        mime_type: "text/markdown",
        content_markdown: "# Packet",
        manifest_json: { synthetic_only: true },
        created_at: "2026-06-18T00:00:00Z"
      })
    });
  });
}

test.describe("PriorAuth Evidence Copilot", () => {
  test("renders account login as the first screen without static credentials", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "PriorAuth Evidence Copilot" })
    ).toBeVisible();
    await expect(
      page.getByText("Synthetic or de-identified documents only.").first()
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toHaveValue("");
    await expect(page.getByLabel("Password")).toHaveValue("");
    await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Forgot password" })).toBeVisible();
  });

  test("keeps account login usable on mobile", async ({ page }) => {
    await page.goto("/");

    await expect(
      page.getByRole("heading", { name: "PriorAuth Evidence Copilot" })
    ).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Sign in" })
    ).toBeVisible();
  });

  test("shows reviewer controls for criteria, evidence, drafts, and citations", async ({ page }) => {
    await mockAuthenticatedReviewerWorkspace(page);
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "SYN-LMRI-REVIEW" })).toBeVisible();

    await page.getByRole("button", { name: "Criteria" }).click();
    await expect(page.getByRole("button", { name: "Save criterion review" })).toBeVisible();
    await expect(page.getByText("policy.pdf, page 1")).toBeVisible();

    await page.getByRole("button", { name: "Evidence" }).click();
    await expect(page.getByRole("button", { name: "Save evidence override" })).toBeVisible();
    await expect(page.getByText("Six weeks of therapy are documented.")).toBeVisible();

    await page.getByRole("button", { name: "Draft" }).click();
    await expect(page.getByRole("button", { name: "Save draft edits" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Verify citations" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve draft" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Export readiness" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Export letter" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Export packet" })).toBeDisabled();

    await page.getByRole("button", { name: "Verify citations" }).click();
    await expect(page.getByText("Unsupported claims")).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve draft" })).toBeEnabled();

    await page.getByRole("button", { name: "Approve draft" }).click();
    await expect(page.getByRole("button", { name: "Export letter" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Export packet" })).toBeEnabled();

    await page.getByRole("button", { name: "Export packet" }).click();
    await expect(page.getByRole("link", { name: /syn-lmri-review-prior-auth-packet\.md/i })).toBeVisible();
  });

  test("generates appeal drafts from appeal cases with denial letters", async ({ page }) => {
    await mockAuthenticatedReviewerWorkspace(page, {
      caseType: "appeal",
      documents: [
        {
          id: "doc_denial_1",
          case_id: "case_1",
          document_type: "denial_letter",
          file_name: "denial.pdf",
          checksum_sha256: "checksum",
          page_count: 1,
          processing_status: "completed",
          created_at: "2026-06-18T00:00:00Z",
          updated_at: "2026-06-18T00:00:00Z"
        }
      ],
      drafts: []
    });
    await page.goto("/");

    await expect(page.getByRole("heading", { name: "SYN-LMRI-APPEAL" })).toBeVisible();
    await page.getByRole("button", { name: "Draft" }).click();
    await expect(page.getByRole("button", { name: "Draft appeal" })).toBeVisible();

    await page.getByRole("button", { name: "Draft appeal" }).click();
    await expect(page.getByText("Denial reason identified from payer letter")).toBeVisible();
    await expect(page.getByText("[denial.pdf, page 1]")).toBeVisible();
    await expect(page.getByText("Clinician review is required")).toBeVisible();
  });
});
