import { describe, expect, it, vi } from "vitest";

type RouteHandler<TParams extends Record<string, string>> = (
  request: Request,
  context: { params: Promise<TParams> }
) => Promise<Response>;

function request(path: string, init: RequestInit = {}) {
  return new Request(`http://localhost${path}`, {
    ...init,
    headers: {
      cookie: "authlens_demo_token=jwt-token",
      ...(init.headers ?? {})
    }
  });
}

async function expectCreateExportProxy(
  handler: RouteHandler<{ caseId: string }>,
  path: string,
  expectedBackendPath: string
) {
  process.env.BACKEND_API_URL = "https://backend.example.test";
  const fetchMock = vi.fn().mockResolvedValue(
    Response.json({
      id: "export_123",
      case_id: "case_123",
      export_type: "packet",
      status: "ready",
      file_name: "packet.pdf",
      mime_type: "application/pdf",
      content_markdown: "# Packet",
      manifest_json: { synthetic_only: true },
      created_at: "2026-06-18T00:00:00Z"
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  const response = await handler(request(path, { method: "POST" }), {
    params: Promise.resolve({ caseId: "case_123" })
  });

  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledWith(
    `https://backend.example.test${expectedBackendPath}`,
    expect.objectContaining({ method: "POST" })
  );
  const [, backendInit] = fetchMock.mock.calls[0];
  const headers = backendInit.headers as Headers;
  expect(headers.get("Authorization")).toBe("Bearer jwt-token");
}

describe("export proxy routes", () => {
  it("proxies readiness, letter, and packet export creation", async () => {
    const readinessRoute = await import("./cases/[caseId]/exports/readiness-report/route");
    const letterRoute = await import("./cases/[caseId]/exports/letter/route");
    const packetRoute = await import("./cases/[caseId]/exports/packet/route");

    await expectCreateExportProxy(
      readinessRoute.POST,
      "/api/cases/case_123/exports/readiness-report",
      "/api/cases/case_123/exports/readiness-report"
    );
    await expectCreateExportProxy(
      letterRoute.POST,
      "/api/cases/case_123/exports/letter",
      "/api/cases/case_123/exports/letter"
    );
    await expectCreateExportProxy(
      packetRoute.POST,
      "/api/cases/case_123/exports/packet",
      "/api/cases/case_123/exports/packet"
    );
  });

  it("rejects cross-origin export creation before proxying", async () => {
    const packetRoute = await import("./cases/[caseId]/exports/packet/route");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await packetRoute.POST(
      request("/api/cases/case_123/exports/packet", {
        method: "POST",
        headers: { Origin: "https://evil.example.test" }
      }),
      { params: Promise.resolve({ caseId: "case_123" }) }
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "Request rejected."
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("downloads export PDFs as attachments through the backend", async () => {
    process.env.BACKEND_API_URL = "https://backend.example.test";
    const pdfBytes = new TextEncoder().encode("%PDF-1.7\n% AuthLens packet\n%%EOF");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(pdfBytes, {
        headers: {
          "content-type": "application/pdf",
          "content-disposition": 'attachment; filename="packet.pdf"',
          "x-content-type-options": "nosniff"
        }
      })
    );
    vi.stubGlobal("fetch", fetchMock);
    const downloadRoute = await import("./exports/[exportId]/download/route");

    const response = await downloadRoute.GET(request("/api/exports/export_123/download"), {
      params: Promise.resolve({ exportId: "export_123" })
    });

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("application/pdf");
    expect(response.headers.get("content-disposition")).toBe('attachment; filename="packet.pdf"');
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
    const downloadedBytes = new Uint8Array(await response.arrayBuffer());
    expect(new TextDecoder().decode(downloadedBytes)).toBe("%PDF-1.7\n% AuthLens packet\n%%EOF");
    expect(fetchMock).toHaveBeenCalledWith(
      "https://backend.example.test/api/exports/export_123/download",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("rejects export download without an auth cookie", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const downloadRoute = await import("./exports/[exportId]/download/route");

    const response = await downloadRoute.GET(new Request("http://localhost/api/exports/export_123/download"), {
      params: Promise.resolve({ exportId: "export_123" })
    });

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ error: "Authentication required." });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
