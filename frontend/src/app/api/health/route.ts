import { NextResponse } from "next/server";

import {
  backendNotConfiguredError,
  buildBackendHeaders,
  buildBackendUrl,
  getBackendApiUrl
} from "@/lib/server/backend-proxy";

export const dynamic = "force-dynamic";

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
    const response = await fetch(buildBackendUrl(backendApiUrl, "/docs"), {
      method: "GET",
      headers: buildBackendHeaders(),
      cache: "no-store",
      signal: controller.signal
    });
    const backendReachable = response.status < 500;

    return NextResponse.json(
      {
        ok: backendReachable,
        backendConfigured: true,
        backendReachable
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
