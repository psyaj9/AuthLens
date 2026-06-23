import { describe, expect, it, vi } from "vitest";

type RouteHandler<TParams extends Record<string, string> = Record<string, never>> = (
  request: Request,
  context: { params: Promise<TParams> }
) => Promise<Response>;

function request(path: string) {
  return new Request(`http://localhost${path}`, {
    headers: {
      cookie: "authlens_demo_token=jwt-token"
    }
  });
}

async function expectAuditProxy<TParams extends Record<string, string>>(
  handler: RouteHandler<TParams>,
  path: string,
  params: TParams,
  expectedBackendPath: string
) {
  process.env.BACKEND_API_URL = "https://backend.example.test";
  const fetchMock = vi.fn().mockResolvedValue(
    Response.json({
      events: [
        {
          id: "audit_1",
          organization_id: "org_1",
          case_id: "case_123",
          user_id: "user_1",
          actor_type: "user",
          action: "draft.generated",
          entity_type: "draft_letter",
          entity_id: "draft_123",
          metadata: {},
          created_at: "2026-06-18T00:00:00Z"
        }
      ]
    })
  );
  vi.stubGlobal("fetch", fetchMock);

  const response = await handler(request(path), { params: Promise.resolve(params) });

  expect(response.status).toBe(200);
  expect(fetchMock).toHaveBeenCalledWith(
    `https://backend.example.test${expectedBackendPath}`,
    expect.objectContaining({ method: "GET" })
  );
  const [, backendInit] = fetchMock.mock.calls[0];
  const headers = backendInit.headers as Headers;
  expect(headers.get("Authorization")).toBe("Bearer jwt-token");
}

describe("audit proxy routes", () => {
  it("proxies case and organization audit reads with the auth cookie", async () => {
    const caseAuditRoute = await import("./cases/[caseId]/audit/route");
    const organizationAuditRoute = await import("./audit/route");

    await expectAuditProxy(
      caseAuditRoute.GET,
      "/api/cases/case_123/audit",
      { caseId: "case_123" },
      "/api/cases/case_123/audit"
    );
    await expectAuditProxy(
      (request) => organizationAuditRoute.GET(request),
      "/api/audit",
      {},
      "/api/audit"
    );
  });
});
