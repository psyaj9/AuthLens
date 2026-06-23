import { authHeaders, proxyBackendJson } from "@/lib/server/priorauth-proxy";

export async function GET(request: Request) {
  return proxyBackendJson(request, "/api/audit", {
    method: "GET",
    headers: authHeaders(request)
  });
}
