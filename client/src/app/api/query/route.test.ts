import { describe, expect, it, vi } from "vitest";

describe("POST /api/query", () => {
  it("validates the query and proxies it to the FastAPI field name", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        response: "Use de-identified documents.",
        source_documents: ["Policy A"]
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: "  What can I upload? " })
      })
    );

    await expect(response.json()).resolves.toEqual({
      response: "Use de-identified documents.",
      source_documents: ["Policy A"]
    });
    expect(response.status).toBe(200);
    const [, init] = fetchMock.mock.calls[0];
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.test/api/queries/",
      expect.objectContaining({ method: "POST" })
    );
    expect(init.body.get("user_query")).toBe("What can I upload?");
  });

  it("sanitizes source labels before returning them to the browser", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          response: "Use de-identified documents.",
          source_documents: [
            "C:\\server\\uploads\\patient-note.pdf",
            "/app/server/uploads/patient-note.pdf",
            "/tmp/radiology.pdf"
          ]
        })
      )
    );

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: "What can I upload?" })
      })
    );

    await expect(response.json()).resolves.toEqual({
      response: "Use de-identified documents.",
      source_documents: ["patient-note.pdf", "radiology.pdf"]
    });
  });

  it("returns a normalized validation error for blank queries", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: "   " })
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "Enter a question before asking AuthLens."
    });
    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects mismatched Origin before proxying the query", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: "https://evil.example.test"
        },
        body: JSON.stringify({ user_query: "What can I upload?" })
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "Cross-origin requests are not allowed."
    });
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects cross-site fetch metadata before proxying the query", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Sec-Fetch-Site": "cross-site"
        },
        body: JSON.stringify({ user_query: "What can I upload?" })
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "Cross-origin requests are not allowed."
    });
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns a generic error when the backend fetch fails", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("getaddrinfo backend.example.test"))
    );

    const { POST } = await import("./route");
    const response = await POST(
      new Request("http://localhost/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: "What can I upload?" })
      })
    );

    await expect(response.json()).resolves.toEqual({
      error: "AuthLens could not reach the backend."
    });
    expect(response.status).toBe(502);
  });
});
