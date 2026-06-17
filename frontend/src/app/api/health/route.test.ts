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
      error: "Backend API URL is not configured."
    });
  });

  it("reports backend reachability when configured", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("ok", { status: 200 })));

    const { GET } = await import("./route");
    const response = await GET();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({
      ok: true,
      backendConfigured: true,
      backendReachable: true
    });
  });
});
