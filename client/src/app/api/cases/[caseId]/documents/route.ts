import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

export const runtime = "nodejs";

type RouteContext = {
  params: Promise<{ caseId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { caseId } = await context.params;
  return proxyBackendJson(request, `/api/cases/${caseId}/documents`, {
    method: "GET",
    headers: authHeaders(request)
  });
}

export async function POST(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { caseId } = await context.params;
  const body = await request.formData();
  return proxyBackendJson(request, `/api/cases/${caseId}/documents`, {
    method: "POST",
    body,
    headers: authHeaders(request)
  });
}
