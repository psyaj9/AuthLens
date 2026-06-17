import { NextResponse } from "next/server";

import {
  AUTH_COOKIE_NAME,
  errorResponse,
  proxyBackendJson
} from "@/lib/server/priorauth-proxy";

export async function POST(request: Request) {
  const body = await request.text();
  const response = await proxyBackendJson(request, "/api/auth/login", {
    method: "POST",
    body,
    headers: { "Content-Type": "application/json" }
  });
  if (!response.ok) {
    return response;
  }

  const payload = await response.json().catch(() => null);
  if (!payload || typeof payload.access_token !== "string") {
    return errorResponse("Backend returned an unexpected auth response.", 502);
  }

  const nextResponse = NextResponse.json(payload);
  nextResponse.cookies.set(AUTH_COOKIE_NAME, payload.access_token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return nextResponse;
}
