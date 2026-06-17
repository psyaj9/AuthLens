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
});
