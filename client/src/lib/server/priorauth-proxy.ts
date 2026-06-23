import "server-only";

import { NextResponse } from "next/server";

import {
  backendNotConfiguredError,
  buildBackendUrl,
  CLIENT_REQUEST_FAILED_ERROR,
  CLIENT_REQUEST_REJECTED_ERROR,
  getBackendApiUrl,
  isCrossOriginMutation,
  normalizeBackendError,
  readJsonOrText
} from "./backend-proxy";

export const AUTH_COOKIE_NAME = "authlens_demo_token";

function parseCookie(header: string | null, name: string) {
  const cookies = header?.split(";") ?? [];
  for (const cookie of cookies) {
    const [rawKey, ...valueParts] = cookie.trim().split("=");
    if (rawKey === name) {
      return decodeURIComponent(valueParts.join("="));
    }
  }
  return undefined;
}

export function getAuthTokenFromRequest(request: Request) {
  return parseCookie(request.headers.get("cookie"), AUTH_COOKIE_NAME);
}

export function authCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge
  };
}

export function authHeaders(request: Request, json = false): Headers {
  const headers = new Headers();
  const token = getAuthTokenFromRequest(request);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (json) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

export function errorResponse(error: string, status: number) {
  return NextResponse.json({ error }, { status });
}

export function rejectCrossOriginMutation(request: Request) {
  if (isCrossOriginMutation(request)) {
    return errorResponse(CLIENT_REQUEST_REJECTED_ERROR, 403);
  }

  return null;
}

export async function proxyBackendJson(
  request: Request,
  path: string,
  init: RequestInit = {}
) {
  const backendApiUrl = getBackendApiUrl();
  if (!backendApiUrl) {
    const error = backendNotConfiguredError();
    return errorResponse(error.error, error.status);
  }

  try {
    const backendResponse = await fetch(buildBackendUrl(backendApiUrl, path), {
      ...init,
      headers: init.headers ?? authHeaders(request, init.body !== undefined),
      cache: "no-store"
    });

    if (!backendResponse.ok) {
      const error = await normalizeBackendError(backendResponse);
      return errorResponse(error.error, error.status);
    }

    if (backendResponse.status === 204) {
      return new Response(null, { status: 204 });
    }

    const payload = await readJsonOrText(backendResponse);
    return NextResponse.json(typeof payload === "string" ? { message: payload } : payload);
  } catch {
    return errorResponse(CLIENT_REQUEST_FAILED_ERROR, 502);
  }
}
