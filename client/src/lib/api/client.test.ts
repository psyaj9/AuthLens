import { describe, expect, it, vi } from "vitest";
import {
  approveDraft,
  archiveCase,
  askQuestion,
  AuthLensApiError,
  createAppealDraft,
  createCase,
  createLetterExport,
  createPacketExport,
  createPriorAuthDraft,
  createReadinessExport,
  deleteDocument,
  forgotPassword,
  getLatestReadinessReport,
  listCaseAudit,
  listOrganizationAudit,
  loginUser,
  overrideEvidenceMatch,
  registerUser,
  resetPassword,
  updateCriterion,
  updateDraft,
  uploadDocuments
} from "./client";

describe("client API client", () => {
  it("posts questions to the local Next.js API route without exposing the backend URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        response: "Coverage requires signed evidence.",
        source_documents: ["Section 2.1"]
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await askQuestion("  What evidence is required?  ");

    expect(result.response).toBe("Coverage requires signed evidence.");
    expect(result.source_documents).toEqual(["Section 2.1"]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/query",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: "What evidence is required?" })
      })
    );
  });

  it("uploads PDFs with the backend field name expected by FastAPI", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ accepted: true }));
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["pdf-bytes"], "evidence.pdf", {
      type: "application/pdf"
    });

    await uploadDocuments([file]);

    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/upload",
      expect.objectContaining({ method: "POST" })
    );
    expect(init.body).toBeInstanceOf(FormData);
    expect(init.body.getAll("uploaded_files")).toEqual([file]);
  });

  it("surfaces normalized route errors with status codes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ error: "Backend unavailable" }, { status: 503 }))
    );

    await expect(askQuestion("Will this work?")).rejects.toMatchObject({
      name: "AuthLensApiError",
      message: "Backend unavailable",
      status: 503
    });
    expect(AuthLensApiError).toBeDefined();
  });

  it("logs in through the local auth route without expecting bearer tokens in JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        user: {
          id: "user_1",
          email: "owner@example.test",
          name: "Owner",
          role: "admin",
          organization: { id: "org_1", name: "Practice", plan: "self_service" }
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await loginUser("owner@example.test", "registered-password");

    expect(result.user.email).toBe("owner@example.test");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "owner@example.test",
          password: "registered-password"
        })
      })
    );
  });

  it("registers users through the local auth route without expecting bearer tokens in JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        user: {
          id: "user_1",
          email: "owner@example.test",
          name: "Owner",
          role: "admin",
          organization: { id: "org_1", name: "Practice", plan: "self_service" }
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await registerUser({
      email: "owner@example.test",
      password: "registered-password",
      name: "Owner",
      organization_name: "Practice"
    });

    expect(result.user.email).toBe("owner@example.test");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/register",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: "owner@example.test",
          password: "registered-password",
          name: "Owner",
          organization_name: "Practice"
        })
      })
    );
  });

  it("requests and consumes password reset tokens through local auth routes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          message: "If an account exists, password reset instructions have been prepared.",
          reset_token: "reset-token"
        })
      )
      .mockResolvedValueOnce(Response.json({ message: "Password reset complete." }));
    vi.stubGlobal("fetch", fetchMock);

    const forgotResult = await forgotPassword("owner@example.test");
    const resetResult = await resetPassword("reset-token", "new-password");

    expect(forgotResult.reset_token).toBe("reset-token");
    expect(resetResult.message).toBe("Password reset complete.");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/auth/forgot-password",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "owner@example.test" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/auth/reset-password",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_token: "reset-token", password: "new-password" })
      })
    );
  });

  it("creates appeal cases and draft letters through local case routes", async () => {
    const casePayload = {
      id: "case_123",
      patient_label: "SYN-LMRI-APPEAL",
      payer_name: "Example Health Plan",
      plan_name: null,
      specialty: "Radiology",
      requested_service: "Lumbar spine MRI appeal",
      service_code: "72148",
      diagnosis_summary: null,
      case_type: "appeal",
      status: "new",
      readiness_score: null,
      missing_required_criteria_count: 0,
      assigned_to_user_id: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    };
    const draftPayload = {
      id: "draft_appeal_123",
      case_id: "case_123",
      letter_type: "appeal",
      status: "draft",
      content_markdown: "Clinician review is required before appeal submission.",
      created_by: "ai",
      approved_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(casePayload))
      .mockResolvedValueOnce(Response.json(draftPayload));
    vi.stubGlobal("fetch", fetchMock);

    const createdCase = await createCase({
      patient_label: "SYN-LMRI-APPEAL",
      payer_name: "Example Health Plan",
      specialty: "Radiology",
      requested_service: "Lumbar spine MRI appeal",
      service_code: "72148",
      case_type: "appeal"
    });
    const appealDraft = await createAppealDraft("case_123");

    expect(createdCase.case_type).toBe("appeal");
    expect(appealDraft.letter_type).toBe("appeal");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/cases",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_label: "SYN-LMRI-APPEAL",
          payer_name: "Example Health Plan",
          specialty: "Radiology",
          requested_service: "Lumbar spine MRI appeal",
          service_code: "72148",
          case_type: "appeal"
        })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/cases/case_123/drafts/appeal",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("archives cases through the local case route", async () => {
    const archivedCase = {
      id: "case_123",
      patient_label: "SYN-LMRI-001",
      payer_name: "Example Health Plan",
      plan_name: null,
      specialty: "Radiology",
      requested_service: "Lumbar spine MRI",
      service_code: "72148",
      diagnosis_summary: null,
      case_type: "prior_auth",
      status: "archived",
      readiness_score: 12,
      missing_required_criteria_count: 6,
      assigned_to_user_id: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(archivedCase));
    vi.stubGlobal("fetch", fetchMock);

    const result = await archiveCase("case_123");

    expect(result.status).toBe("archived");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cases/case_123/archive",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("deletes uploaded documents through the local document route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteDocument("doc_123");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/documents/doc_123",
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("updates criteria review state through the local route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        id: "crit_123",
        criterion_code: "C1",
        criterion_type: "documentation",
        requirement: "Updated criterion",
        required_evidence: ["Therapy dates"],
        is_required: true,
        source_file: "policy.pdf",
        source_page: "1",
        source_quote: "Original payer criterion",
        confidence: 0.82,
        ambiguity_notes: [],
        reviewer_status: "reviewed"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await updateCriterion("crit_123", {
      requirement: "Updated criterion",
      required_evidence: ["Therapy dates"],
      reviewer_status: "reviewed"
    });

    expect(result.reviewer_status).toBe("reviewed");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/criteria/crit_123",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          requirement: "Updated criterion",
          required_evidence: ["Therapy dates"],
          reviewer_status: "reviewed"
        })
      })
    );
  });

  it("saves evidence reviewer overrides through the local route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        id: "match_123",
        criterion_id: "crit_123",
        status: "met",
        evidence_summary: "Patient note supports the criterion.",
        source_file: "note.pdf",
        source_page: "2",
        source_quote: "Six weeks of therapy are documented.",
        why_it_matters: "Reviewer should confirm the citation.",
        missing_evidence: [],
        conflicting_evidence: [],
        recommended_action: "Review citation.",
        confidence: 0.8,
        reviewer_override_status: "not_met",
        reviewer_override_reason: "Citation does not satisfy policy"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await overrideEvidenceMatch("match_123", {
      reviewer_override_status: "not_met",
      reviewer_override_reason: "Citation does not satisfy policy"
    });

    expect(result.reviewer_override_status).toBe("not_met");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/evidence-matches/match_123",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer_override_status: "not_met",
          reviewer_override_reason: "Citation does not satisfy policy"
        })
      })
    );
  });

  it("edits and approves drafts through local routes", async () => {
    const draftPayload = {
      id: "draft_123",
      case_id: "case_123",
      letter_type: "prior_auth",
      status: "needs_revision",
      content_markdown: "Edited draft",
      created_by: "ai",
      approved_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(draftPayload))
      .mockResolvedValueOnce(Response.json({ ...draftPayload, status: "approved" }));
    vi.stubGlobal("fetch", fetchMock);

    const editedDraft = await updateDraft("draft_123", "Edited draft");
    const approvedDraft = await approveDraft("draft_123");

    expect(editedDraft.content_markdown).toBe("Edited draft");
    expect(approvedDraft.status).toBe("approved");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/drafts/draft_123",
      expect.objectContaining({
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_markdown: "Edited draft" })
      })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/drafts/draft_123/approve",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("creates prior authorization drafts through local case routes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        id: "draft_123",
        case_id: "case_123",
        letter_type: "prior_auth",
        status: "draft",
        content_markdown: "Clinician review is required before submission.",
        created_by: "ai",
        approved_at: null,
        created_at: "2026-06-18T00:00:00Z",
        updated_at: "2026-06-18T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const draft = await createPriorAuthDraft("case_123");

    expect(draft.letter_type).toBe("prior_auth");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cases/case_123/drafts/prior-auth",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("creates export artifacts through local case routes", async () => {
    const exportPayload = {
      id: "export_123",
      case_id: "case_123",
      export_type: "packet",
      status: "ready",
      file_name: "syn-lmri-packet.pdf",
      mime_type: "application/pdf",
      content_markdown: "# Packet",
      manifest_json: { synthetic_only: true },
      created_at: "2026-06-18T00:00:00Z"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ ...exportPayload, export_type: "readiness_report" }))
      .mockResolvedValueOnce(Response.json({ ...exportPayload, export_type: "letter" }))
      .mockResolvedValueOnce(Response.json(exportPayload));
    vi.stubGlobal("fetch", fetchMock);

    await createReadinessExport("case_123");
    await createLetterExport("case_123");
    const packet = await createPacketExport("case_123");

    expect(packet.export_type).toBe("packet");
    expect(packet.file_name).toBe("syn-lmri-packet.pdf");
    expect(packet.mime_type).toBe("application/pdf");
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/cases/case_123/exports/readiness-report",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/cases/case_123/exports/letter",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/cases/case_123/exports/packet",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("loads the latest readiness report and treats a missing report as empty state", async () => {
    const reportPayload = {
      id: "report_123",
      case_id: "case_123",
      readiness_score: 78,
      overall_status: "needs_more_documentation",
      summary: "Case is not submission-ready.",
      highest_risk_items: ["EDSS score missing."],
      recommended_next_steps: ["Upload EDSS documentation."],
      report_json: { source: "deterministic" },
      created_at: "2026-06-18T00:00:00Z"
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(reportPayload))
      .mockResolvedValueOnce(Response.json({ error: "Readiness report not found" }, { status: 404 }));
    vi.stubGlobal("fetch", fetchMock);

    const report = await getLatestReadinessReport("case_123");
    const missing = await getLatestReadinessReport("case_empty");

    expect(report?.case_id).toBe("case_123");
    expect(report?.readiness_score).toBe(78);
    expect(missing).toBeNull();
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/cases/case_123/reports/latest", {
      cache: "no-store"
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/cases/case_empty/reports/latest", {
      cache: "no-store"
    });
  });

  it("loads case and organization audit events through local routes", async () => {
    const auditPayload = {
      events: [
        {
          id: "audit_1",
          organization_id: "org_1",
          case_id: "case_123",
          user_id: "user_1",
          actor_type: "user",
          action: "draft.generated",
          entity_type: "draft_letter",
          entity_id: "draft_123",
          metadata: { words: 847 },
          created_at: "2026-06-18T00:00:00Z"
        }
      ]
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(auditPayload))
      .mockResolvedValueOnce(Response.json({ events: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const caseEvents = await listCaseAudit("case_123");
    const orgEvents = await listOrganizationAudit();

    expect(caseEvents).toHaveLength(1);
    expect(caseEvents[0].metadata).toEqual({ words: 847 });
    expect(orgEvents).toEqual([]);
    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/cases/case_123/audit", {
      cache: "no-store"
    });
    expect(fetchMock).toHaveBeenNthCalledWith(2, "/api/audit", {
      cache: "no-store"
    });
  });
});
