import { describe, expect, it, vi } from "vitest";
import { askQuestion, AuthLensApiError, uploadDocuments } from "./client";

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
});
