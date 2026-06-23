import { expect, test, type Page } from "@playwright/test";

type WorkspaceMockOptions = {
  caseType?: "prior_auth" | "appeal";
  documents?: Array<Record<string, unknown>>;
  drafts?: Array<Record<string, unknown>>;
  role?: "admin" | "coordinator" | "clinician_reviewer" | "viewer";
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
        role: options.role ?? "clinician_reviewer",
        organization: { id: "org_1", name: "Review Clinic", plan: "test" }
      })
    });
  });
  await page.route(/\/api\/cases$/, async (route) => {
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
  await page.route("**/api/cases/case_1/reports/latest", async (route) => {
    await route.fulfill({ status: 404 });
  });
  await page.route("**/api/cases/case_1/audit", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ events: [] })
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
        file_name: "syn-lmri-review-prior-auth-packet.pdf",
        mime_type: "application/pdf",
        content_markdown: "# Packet",
        manifest_json: { synthetic_only: true },
        created_at: "2026-06-18T00:00:00Z"
      })
    });
  });
}

async function openCase(page: Page, caseId = "case_1") {
  await page.getByTestId(`case-card-${caseId}`).click();
}

async function goToWorkflowStep(
  page: Page,
  step: "criteria" | "evidence" | "readiness" | "draft" | "review"
) {
  await page.getByTestId(`workflow-step-${step}`).click();
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

    await expect(page.getByRole("heading", { name: "Case Registry" })).toBeVisible();
    await openCase(page);
    await expect(page.getByRole("heading", { name: "Lumbar spine MRI" })).toBeVisible();
    await expect(page.getByText("SYN-LMRI-REVIEW")).toBeVisible();

    await goToWorkflowStep(page, "criteria");
    await expect(page.getByRole("button", { name: "Save criterion review" })).toBeVisible();
    await expect(page.getByText("policy.pdf, page 1")).toBeVisible();

    await goToWorkflowStep(page, "evidence");
    await expect(page.getByRole("button", { name: "Save evidence override" })).toBeVisible();
    await expect(page.getByText("Six weeks of therapy are documented.")).toBeVisible();

    await goToWorkflowStep(page, "draft");
    await expect(page.getByRole("button", { name: "Save draft edits" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Verify citations" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve draft" })).toBeDisabled();

    await page.getByRole("button", { name: "Verify citations" }).click();
    await expect(page.getByText("Unsupported claims")).toBeVisible();
    await goToWorkflowStep(page, "draft");
    await expect(page.getByRole("button", { name: "Approve draft" })).toBeEnabled();

    await page.getByRole("button", { name: "Approve draft" }).click();
    await goToWorkflowStep(page, "review");
    await expect(page.getByRole("button", { name: "Export readiness" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Export letter" })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Export packet" })).toBeEnabled();

    await page.getByRole("button", { name: "Export packet" }).click();
    await expect(page.getByRole("link", { name: /syn-lmri-review-prior-auth-packet\.pdf/i })).toBeVisible();
  });

  test("generates appeal drafts from appeal cases with denial letters", async ({ page }) => {
    await mockAuthenticatedReviewerWorkspace(page, {
      caseType: "appeal",
      role: "coordinator",
      documents: [
        {
          id: "doc_denial_1",
          case_id: "case_1",
          document_type: "denial_letter",
          file_name: "denial.pdf",
          sha256: "checksum",
          mime_type: "application/pdf",
          page_count: 1,
          processing_status: "completed",
          extraction_method: "text",
          created_at: "2026-06-18T00:00:00Z",
          updated_at: "2026-06-18T00:00:00Z"
        }
      ],
      drafts: []
    });
    await page.goto("/");

    await openCase(page);
    await expect(page.getByText("SYN-LMRI-APPEAL")).toBeVisible();
    await goToWorkflowStep(page, "draft");
    await expect(page.getByRole("button", { name: "Draft appeal" })).toBeVisible();

    await page.getByRole("button", { name: "Draft appeal" }).click();
    await expect(page.getByText("Denial reason identified from payer letter")).toBeVisible();
    await expect(page.getByText("[denial.pdf, page 1]")).toBeVisible();
    await expect(page.getByText("Clinician review is required")).toBeVisible();
  });

  test("clears generated readiness details when switching to a blank case", async ({ page }) => {
    const caseOne = {
      id: "case_ready",
      patient_label: "SYN-LMRI-READY",
      payer_name: "Example Health Plan",
      plan_name: null,
      specialty: "Radiology",
      requested_service: "Lumbar spine MRI",
      service_code: "72148",
      diagnosis_summary: null,
      case_type: "prior_auth",
      status: "ready_for_review",
      readiness_score: 90,
      missing_required_criteria_count: 0,
      assigned_to_user_id: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    };
    const caseTwo = {
      ...caseOne,
      id: "case_blank",
      patient_label: "SYN-LMRI-BLANK",
      status: "draft",
      readiness_score: null
    };
    const readinessPanel = page.getByTestId("readiness-step");

    await page.route("**/api/auth/me", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          id: "user_1",
          email: "coordinator@example.test",
          name: "Coordinator",
          role: "coordinator",
          organization: { id: "org_1", name: "Review Clinic", plan: "test" }
        })
      });
    });
    await page.route(/\/api\/cases$/, async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ cases: [caseOne, caseTwo] })
      });
    });
    for (const caseId of ["case_ready", "case_blank"]) {
      await page.route(`**/api/cases/${caseId}/documents`, async (route) => {
        await route.fulfill({ contentType: "application/json", body: JSON.stringify({ documents: [] }) });
      });
      await page.route(`**/api/cases/${caseId}/criteria`, async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            criteria:
              caseId === "case_ready"
                ? [
                    {
                      id: "crit_ready_1",
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
                      reviewer_status: "reviewed"
                    }
                  ]
                : []
          })
        });
      });
      await page.route(`**/api/cases/${caseId}/evidence`, async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            matches:
              caseId === "case_ready"
                ? [
                    {
                      id: "match_ready_1",
                      criterion_id: "crit_ready_1",
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
                : []
          })
        });
      });
      await page.route(`**/api/cases/${caseId}/drafts`, async (route) => {
        await route.fulfill({ contentType: "application/json", body: JSON.stringify({ drafts: [] }) });
      });
      await page.route(`**/api/cases/${caseId}/reports/latest`, async (route) => {
        await route.fulfill({ status: 404 });
      });
    }
    await page.route("**/api/cases/case_ready/reports/readiness", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          id: "report_ready_1",
          case_id: "case_ready",
          readiness_score: 90,
          overall_status: "ready_for_review",
          summary: "Case one readiness summary.",
          highest_risk_items: [],
          recommended_next_steps: ["Submit after clinician review."],
          report_json: {},
          created_at: "2026-06-18T00:00:00Z"
        })
      });
    });
    await page.goto("/");

    await openCase(page, "case_ready");
    await goToWorkflowStep(page, "readiness");
    await expect(page.getByRole("button", { name: "Generate", exact: true })).toBeEnabled();
    await page.getByRole("button", { name: "Generate", exact: true }).click();
    await expect(readinessPanel.getByText("Case one readiness summary.")).toBeVisible();
    await expect(readinessPanel.getByTestId("readiness-score")).toHaveText("90");

    await page.getByRole("button", { name: "Cases" }).first().click();
    await openCase(page, "case_blank");
    await goToWorkflowStep(page, "readiness");

    await expect(page.getByText("SYN-LMRI-BLANK")).toBeVisible();
    await expect(readinessPanel.getByText("Generate a readiness report after matching evidence.")).toBeVisible();
    await expect(readinessPanel.getByText("Case one readiness summary.")).toBeHidden();
    await expect(readinessPanel.getByTestId("readiness-score")).toHaveText("-");
  });

  test("lets coordinators delete uploaded documents from a case", async ({ page }) => {
    const documents = [
      {
        id: "doc_note_1",
        case_id: "case_1",
        document_type: "patient_note",
        file_name: "note.pdf",
        sha256: "checksum",
        mime_type: "application/pdf",
        page_count: 1,
        processing_status: "indexed",
        extraction_method: "text",
        created_at: "2026-06-18T00:00:00Z",
        updated_at: "2026-06-18T00:00:00Z"
      }
    ];
    let deleteRequested = false;
    await mockAuthenticatedReviewerWorkspace(page, {
      role: "coordinator",
      documents
    });
    await page.route("**/api/documents/doc_note_1", async (route) => {
      deleteRequested = true;
      documents.length = 0;
      await route.fulfill({ status: 204 });
    });
    await page.goto("/");

    await openCase(page);
    await expect(page.getByText("note.pdf")).toBeVisible();
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId("document-row-doc_note_1").getByRole("button", { name: "Delete" }).click();

    expect(deleteRequested).toBe(true);
    await expect(page.getByText("Document deleted.")).toBeVisible();
    await expect(page.getByText("note.pdf")).toBeHidden();
  });
});
