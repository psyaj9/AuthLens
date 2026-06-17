import { NextResponse } from "next/server";

import {
  backendNotConfiguredError,
  buildBackendHeaders,
  buildBackendUrl,
  getBackendApiUrl
} from "@/lib/server/backend-proxy";

export const dynamic = "force-dynamic";

function isBackendHealthPayload(payload: unknown) {
  return (
    payload !== null &&
    typeof payload === "object" &&
    "status" in payload &&
    payload.status === "ok" &&
    "service" in payload &&
    payload.service === "authlens-api"
  );
}

export async function GET() {
  const backendApiUrl = getBackendApiUrl();

  if (!backendApiUrl) {
    const error = backendNotConfiguredError();
    return NextResponse.json(
      {
        ok: false,
        backendConfigured: false,
        backendReachable: false,
        error: error.error
      },
      { status: error.status }
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);

  try {
    const response = await fetch(buildBackendUrl(backendApiUrl, "/api/health/"), {
      method: "GET",
      headers: buildBackendHeaders(),
      cache: "no-store",
      signal: controller.signal
    });
    const payload = await response.json().catch(() => null);
    const backendReachable = response.ok && isBackendHealthPayload(payload);

    return NextResponse.json(
      {
        ok: backendReachable,
        backendConfigured: true,
        backendReachable,
        error: backendReachable ? undefined : "Backend health check failed."
      },
      { status: backendReachable ? 200 : 503 }
    );
  } catch {
    return NextResponse.json(
      {
        ok: false,
        backendConfigured: true,
        backendReachable: false,
        error: "Backend is not reachable."
      },
      { status: 503 }
    );
  } finally {
    clearTimeout(timeout);
  }
}
