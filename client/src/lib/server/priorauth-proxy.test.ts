import { afterEach, describe, expect, it, vi } from "vitest";

import { authCookieOptions, rejectCrossOriginMutation } from "./priorauth-proxy";

describe("prior auth proxy helpers", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks auth cookies secure in production", () => {
    vi.stubEnv("NODE_ENV", "production");

    expect(authCookieOptions(60 * 60 * 8)).toEqual({
      httpOnly: true,
      sameSite: "lax",
      secure: true,
      path: "/",
      maxAge: 60 * 60 * 8
    });
  });

  it("does not require secure auth cookies during local development", () => {
    vi.stubEnv("NODE_ENV", "development");

    expect(authCookieOptions(0)).toEqual({
      httpOnly: true,
      sameSite: "lax",
      secure: false,
      path: "/",
      maxAge: 0
    });
  });

  it("accepts same-origin mutations that arrive through forwarded host headers", () => {
    const request = new Request("http://127.0.0.1:3000/api/auth/login", {
      method: "POST",
      headers: {
        Origin: "https://authlens.example.test",
        "Sec-Fetch-Site": "same-origin",
        "X-Forwarded-Host": "authlens.example.test",
        "X-Forwarded-Proto": "https"
      }
    });

    expect(rejectCrossOriginMutation(request)).toBeNull();
  });

  it("uses a generic message when rejecting cross-origin mutations", async () => {
    const request = new Request("http://app.example.test/api/auth/login", {
      method: "POST",
      headers: {
        Origin: "https://evil.example.test"
      }
    });

    const response = rejectCrossOriginMutation(request);

    expect(response?.status).toBe(403);
    await expect(response?.json()).resolves.toEqual({ error: "Request rejected." });
  });
});
