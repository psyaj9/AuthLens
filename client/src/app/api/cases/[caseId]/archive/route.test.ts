import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";

function request(path: string, init: RequestInit = {}) {
  return new Request(`http://localhost${path}`, {
    ...init,
    headers: {
      cookie: "authlens_demo_token=jwt-token",
      ...(init.headers ?? {})
    }
  });
}

describe("/api/cases/[caseId]/archive route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.BACKEND_API_URL;
  });

  it("proxies case archive requests to the backend with the auth cookie token", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        id: "case_123",
        patient_label: "SYN-LMRI-001",
        payer_name: "Example Health Plan",
        plan_name: null,
        specialty: "Radiology",
        requested_service: "Lumbar spine MRI",
        service_code: "72148",
        diagnosis_summary: null,
        case_type: "prior_auth",
        status: "archived",
        readiness_score: 12,
        missing_required_criteria_count: 6,
        assigned_to_user_id: null,
        created_at: "2026-06-18T00:00:00Z",
        updated_at: "2026-06-18T00:00:00Z"
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(request("/api/cases/case_123/archive", { method: "POST" }), {
      params: Promise.resolve({ caseId: "case_123" })
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ id: "case_123", status: "archived" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.test/api/cases/case_123/archive",
      expect.objectContaining({ method: "POST" })
    );
    const [, backendInit] = fetchMock.mock.calls[0];
    const headers = backendInit.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer jwt-token");
  });

  it("rejects cross-origin archive requests before proxying", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(
      request("/api/cases/case_123/archive", {
        method: "POST",
        headers: { Origin: "https://evil.example.test" }
      }),
      { params: Promise.resolve({ caseId: "case_123" }) }
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "Cross-origin requests are not allowed."
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
