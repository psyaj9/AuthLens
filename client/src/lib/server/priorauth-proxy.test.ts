import { afterEach, describe, expect, it, vi } from "vitest";

import { authCookieOptions } from "./priorauth-proxy";

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
});
