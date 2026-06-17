import { authHeaders, errorResponse, getAuthTokenFromRequest, proxyBackendJson } from "@/lib/server/priorauth-proxy";

export async function GET(request: Request) {
  if (!getAuthTokenFromRequest(request)) {
    return errorResponse("Not authenticated", 401);
  }
  return proxyBackendJson(request, "/api/auth/me", {
    method: "GET",
    headers: authHeaders(request)
  });
}
