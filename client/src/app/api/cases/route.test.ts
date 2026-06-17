import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

describe("/api/cases route", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("rejects cross-origin state-changing requests before proxying", async () => {
    const fetchMock = vi.spyOn(global, "fetch");
    const request = new Request("http://app.test/api/cases", {
      method: "POST",
      headers: {
        Origin: "https://evil.test",
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ patient_label: "SYN-LMRI-CSRF" })
    });

    const response = await POST(request);

    await expect(response.json()).resolves.toEqual({
      error: "Cross-origin requests are not allowed."
    });
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
