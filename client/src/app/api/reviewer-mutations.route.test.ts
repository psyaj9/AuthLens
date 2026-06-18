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

async function expectProxyCall<TParams extends Record<string, string>>(
  handler: RouteHandler<TParams>,
  path: string,
  params: TParams,
  expectedBackendPath: string,
  init: RequestInit = {}
) {
  process.env.BACKEND_API_URL = "https://backend.example.test";
  const fetchMock = vi.fn().mockResolvedValue(Response.json({ ok: true }));
  vi.stubGlobal("fetch", fetchMock);

  const response = await handler(request(path, init), { params: Promise.resolve(params) });

  expect(response.status).toBe(200);
  await expect(response.json()).resolves.toEqual({ ok: true });
  expect(fetchMock).toHaveBeenCalledWith(
    `https://backend.example.test${expectedBackendPath}`,
    expect.objectContaining({ method: init.method })
  );
  const [, backendInit] = fetchMock.mock.calls[0];
  const headers = backendInit.headers as Headers;
  expect(headers.get("Authorization")).toBe("Bearer jwt-token");
  if (init.body !== undefined) {
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(backendInit.body).toBe(init.body);
  }
}

async function expectCrossOriginRejection<TParams extends Record<string, string>>(
  handler: RouteHandler<TParams>,
  path: string,
  params: TParams,
  init: RequestInit = {}
) {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  const response = await handler(
    request(path, {
      ...init,
      headers: {
        Origin: "https://evil.example.test",
        ...(init.headers ?? {})
      }
    }),
    { params: Promise.resolve(params) }
  );

  expect(response.status).toBe(403);
  await expect(response.json()).resolves.toEqual({
    error: "Cross-origin requests are not allowed."
  });
  expect(fetchMock).not.toHaveBeenCalled();
}

describe("reviewer mutation proxy routes", () => {
  it("proxies criteria review updates with auth and body forwarding", async () => {
    const { PATCH } = await import("./criteria/[criterionId]/route");

    await expectProxyCall(
      PATCH,
      "/api/criteria/crit_123",
      { criterionId: "crit_123" },
      "/api/criteria/crit_123",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewer_status: "reviewed" })
      }
    );
  });

  it("proxies evidence overrides with auth and body forwarding", async () => {
    const { PATCH } = await import("./evidence-matches/[matchId]/route");

    await expectProxyCall(
      PATCH,
      "/api/evidence-matches/match_123",
      { matchId: "match_123" },
      "/api/evidence-matches/match_123",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reviewer_override_status: "not_met",
          reviewer_override_reason: "Citation does not satisfy policy"
        })
      }
    );
  });

  it("proxies draft edits, citation checks, and approvals", async () => {
    const appealDraftRoute = await import("./cases/[caseId]/drafts/appeal/route");
    const draftRoute = await import("./drafts/[draftId]/route");
    const citationRoute = await import("./drafts/[draftId]/verify-citations/route");
    const approveRoute = await import("./drafts/[draftId]/approve/route");

    await expectProxyCall(
      appealDraftRoute.POST,
      "/api/cases/case_123/drafts/appeal",
      { caseId: "case_123" },
      "/api/cases/case_123/drafts/appeal",
      { method: "POST" }
    );
    await expectProxyCall(
      draftRoute.PATCH,
      "/api/drafts/draft_123",
      { draftId: "draft_123" },
      "/api/drafts/draft_123",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content_markdown: "Edited draft" })
      }
    );
    await expectProxyCall(
      citationRoute.POST,
      "/api/drafts/draft_123/verify-citations",
      { draftId: "draft_123" },
      "/api/drafts/draft_123/verify-citations",
      { method: "POST" }
    );
    await expectProxyCall(
      approveRoute.POST,
      "/api/drafts/draft_123/approve",
      { draftId: "draft_123" },
      "/api/drafts/draft_123/approve",
      { method: "POST" }
    );
  });

  it("rejects cross-origin reviewer mutations before proxying", async () => {
    const criteriaRoute = await import("./criteria/[criterionId]/route");
    const evidenceRoute = await import("./evidence-matches/[matchId]/route");
    const appealDraftRoute = await import("./cases/[caseId]/drafts/appeal/route");
    const draftRoute = await import("./drafts/[draftId]/route");
    const citationRoute = await import("./drafts/[draftId]/verify-citations/route");
    const approveRoute = await import("./drafts/[draftId]/approve/route");

    await expectCrossOriginRejection(
      criteriaRoute.PATCH,
      "/api/criteria/crit_123",
      { criterionId: "crit_123" },
      { method: "PATCH", body: "{}" }
    );
    await expectCrossOriginRejection(
      evidenceRoute.PATCH,
      "/api/evidence-matches/match_123",
      { matchId: "match_123" },
      { method: "PATCH", body: "{}" }
    );
    await expectCrossOriginRejection(
      appealDraftRoute.POST,
      "/api/cases/case_123/drafts/appeal",
      { caseId: "case_123" },
      { method: "POST" }
    );
    await expectCrossOriginRejection(
      draftRoute.PATCH,
      "/api/drafts/draft_123",
      { draftId: "draft_123" },
      { method: "PATCH", body: "{}" }
    );
    await expectCrossOriginRejection(
      citationRoute.POST,
      "/api/drafts/draft_123/verify-citations",
      { draftId: "draft_123" },
      { method: "POST" }
    );
    await expectCrossOriginRejection(
      approveRoute.POST,
      "/api/drafts/draft_123/approve",
      { draftId: "draft_123" },
      { method: "POST" }
    );
  });
}
);
