import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ criterionId: string }>;
};

export async function PATCH(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { criterionId } = await context.params;
  return proxyBackendJson(request, `/api/criteria/${criterionId}`, {
    method: "PATCH",
    body: await request.text(),
    headers: authHeaders(request, true)
  });
}
