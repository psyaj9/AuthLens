import { authHeaders, proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

type RouteContext = {
  params: Promise<{ documentId: string }>;
};

export async function DELETE(request: Request, context: RouteContext) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  const { documentId } = await context.params;
  return proxyBackendJson(request, `/api/documents/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(request)
  });
}
