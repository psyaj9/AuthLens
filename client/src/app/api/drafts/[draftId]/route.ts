import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ draftId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  const { draftId } = await context.params;
  return proxyBackendJson(request, `/api/drafts/${draftId}`, {
    method: "GET",
    headers: authHeaders(request)
  });
}

export async function PATCH(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { draftId } = await context.params;
  return proxyBackendJson(request, `/api/drafts/${draftId}`, {
    method: "PATCH",
    body: await request.text(),
    headers: authHeaders(request, true)
  });
}
