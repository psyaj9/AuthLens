import { authHeaders, proxyBackendJson } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ draftId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { draftId } = await context.params;
  return proxyBackendJson(request, `/api/drafts/${draftId}/verify-citations`, {
    method: "POST",
    headers: authHeaders(request)
  });
}
