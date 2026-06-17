import { NextResponse } from "next/server";

import { authHeaders, getAuthTokenFromRequest, proxyBackendJson } from "@/lib/server/priorauth-proxy";

export async function GET(request: Request) {
  if (!getAuthTokenFromRequest(request)) {
    return NextResponse.json(null);
  }
  const response = await proxyBackendJson(request, "/api/auth/me", {
    method: "GET",
    headers: authHeaders(request)
  });
  if (response.status === 401) {
    return NextResponse.json(null);
  }
  return response;
}
