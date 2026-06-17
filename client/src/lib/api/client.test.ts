import { describe, expect, it, vi } from "vitest";
import {
  askQuestion,
  AuthLensApiError,
  forgotPassword,
  registerUser,
  resetPassword,
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
});
