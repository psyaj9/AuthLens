import { describe, expect, it, vi } from "vitest";
import {
  approveDraft,
  askQuestion,
  AuthLensApiError,
  forgotPassword,
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

  it("registers users through the local auth route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        access_token: "jwt",
        token_type: "bearer",
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
});
