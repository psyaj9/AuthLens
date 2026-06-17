import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ matchId: string }>;
};

export async function PATCH(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { matchId } = await context.params;
  return proxyBackendJson(request, `/api/evidence-matches/${matchId}`, {
    method: "PATCH",
    body: await request.text(),
    headers: authHeaders(request, true)
  });
}
