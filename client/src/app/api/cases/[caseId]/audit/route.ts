import { authHeaders, proxyBackendJson } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ caseId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { caseId } = await context.params;
  return proxyBackendJson(request, `/api/cases/${encodeURIComponent(caseId)}/audit`, {
    method: "GET",
    headers: authHeaders(request)
  });
}
