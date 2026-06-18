import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  delete process.env.BACKEND_API_URL;
  vi.unstubAllGlobals();
  vi.resetModules();
});

function authRequest(path: string, body: Record<string, string>) {
  return new Request(`http://localhost${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("browser auth proxy routes", () => {
  it("sets the login cookie without returning the bearer token in JSON", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          access_token: "jwt-token",
          user: { id: "user_123", email: "user@example.test" }
        })
      )
    );

    const loginRoute = await import("./auth/login/route");
    const response = await loginRoute.POST(
      authRequest("/api/auth/login", {
        email: "user@example.test",
        password: "test-password"
      })
    );

    await expect(response.json()).resolves.toEqual({
      user: { id: "user_123", email: "user@example.test" }
    });
    expect(response.headers.get("set-cookie")).toContain("authlens_demo_token=jwt-token");
  });

  it("sets the register cookie without returning the bearer token in JSON", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({
          access_token: "jwt-token",
          user: { id: "user_123", email: "user@example.test" }
        })
      )
    );

    const registerRoute = await import("./auth/register/route");
    const response = await registerRoute.POST(
      authRequest("/api/auth/register", {
        email: "user@example.test",
        password: "test-password",
        name: "Test User",
        organization_name: "Test Org"
      })
    );

    await expect(response.json()).resolves.toEqual({
      user: { id: "user_123", email: "user@example.test" }
    });
    expect(response.status).toBe(201);
    expect(response.headers.get("set-cookie")).toContain("authlens_demo_token=jwt-token");
  });
});
