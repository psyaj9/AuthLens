import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ caseId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { caseId } = await context.params;
  return proxyBackendJson(request, `/api/cases/${caseId}`, {
    method: "GET",
    headers: authHeaders(request)
  });
}

export async function PATCH(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { caseId } = await context.params;
  return proxyBackendJson(request, `/api/cases/${caseId}`, {
    method: "PATCH",
    body: await request.text(),
    headers: authHeaders(request, true)
  });
}
