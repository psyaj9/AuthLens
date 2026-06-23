import { afterEach, describe, expect, it, vi } from "vitest";

import { DELETE } from "./route";

function request(path: string, init: RequestInit = {}) {
  return new Request(`http://localhost${path}`, {
    ...init,
    headers: {
      cookie: "authlens_demo_token=jwt-token",
      ...(init.headers ?? {})
    }
  });
}

describe("/api/documents/[documentId] route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    delete process.env.BACKEND_API_URL;
  });

  it("proxies document delete requests to the backend with the auth cookie token", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await DELETE(request("/api/documents/doc_123", { method: "DELETE" }), {
      params: Promise.resolve({ documentId: "doc_123" })
    });

    expect(response.status).toBe(204);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.test/api/documents/doc_123",
      expect.objectContaining({ method: "DELETE" })
    );
    const [, backendInit] = fetchMock.mock.calls[0];
    const headers = backendInit.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer jwt-token");
  });

  it("rejects cross-origin document delete requests before proxying", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await DELETE(
      request("/api/documents/doc_123", {
        method: "DELETE",
        headers: { Origin: "https://evil.example.test" }
      }),
      { params: Promise.resolve({ documentId: "doc_123" }) }
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "Request rejected."
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
