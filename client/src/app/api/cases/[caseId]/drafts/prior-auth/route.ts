import { authHeaders, proxyBackendJson } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ caseId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { caseId } = await context.params;
  return proxyBackendJson(request, `/api/cases/${caseId}/drafts/prior-auth`, {
    method: "POST",
    headers: authHeaders(request)
  });
}
