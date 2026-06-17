import { proxyBackendJson, rejectCrossOriginMutation } from "@/lib/server/priorauth-proxy";

export async function POST(request: Request) {
  const crossOriginResponse = rejectCrossOriginMutation(request);
  if (crossOriginResponse) return crossOriginResponse;

  return proxyBackendJson(request, "/api/auth/reset-password", {
    method: "POST",
    body: await request.text(),
    headers: { "Content-Type": "application/json" }
  });
}
