import { describe, expect, it, vi } from "vitest";

describe("GET /api/health", () => {
  it("reports missing backend configuration without exposing backend details", async () => {
    delete process.env.BACKEND_API_URL;

    const { GET } = await import("./route");
    const response = await GET();

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      backendConfigured: false,
      backendReachable: false,
      error: "Request failed."
    });
  });

  it("reports backend reachability when configured", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          status: "ok",
          service: "authlens-api",
          environment: "test",
          dependencies: {
            pinecone: "not_checked",
            groq: "not_checked",
            google: "not_checked"
          }
        })
      )
    );

    const { GET } = await import("./route");
    const response = await GET();

    expect(fetch).toHaveBeenCalledWith(
      "https://backend.example.test/api/health/",
      expect.objectContaining({ method: "GET" })
    );
    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      backendConfigured: true,
      backendReachable: true
    });
  });

  it("treats non-health backend responses as unavailable", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(Response.json({ detail: "Not Found" }, { status: 404 }))
    );

    const { GET } = await import("./route");
    const response = await GET();

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      backendConfigured: true,
      backendReachable: false,
      error: "Backend health check failed."
    });
  });
});
