import { NextResponse } from "next/server";
import { z } from "zod";

import {
  backendNotConfiguredError,
  buildBackendHeaders,
  buildBackendUrl,
  getBackendApiUrl,
  isCrossOriginMutation,
  legacyQaEnabled,
  normalizeBackendError,
  parseQaResponse
} from "@/lib/server/backend-proxy";

const querySchema = z.object({
  user_query: z
    .string()
    .trim()
    .min(1, "Enter a question before asking AuthLens.")
});

async function readQueryPayload(request: Request) {
  const contentType = request.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return request.json();
  }

  const formData = await request.formData();
  return {
    user_query: formData.get("user_query")
  };
}

function errorResponse(error: string, status: number) {
  return NextResponse.json({ error }, { status });
}

function safeSourceLabel(source: string) {
  const normalized = source.replace(/\\/g, "/");
  const label = normalized.split("/").filter(Boolean).pop();
  return label || "Unknown source";
}

function sanitizeSources(sources: string[]) {
  return Array.from(new Set(sources.map(safeSourceLabel)));
}

export async function POST(request: Request) {
  if (isCrossOriginMutation(request)) {
    return errorResponse("Cross-origin requests are not allowed.", 403);
  }

  if (!legacyQaEnabled()) {
    return errorResponse("Legacy PDF Q&A is disabled.", 403);
  }

  const payload = await readQueryPayload(request).catch(() => null);
  const parsed = querySchema.safeParse(payload);

  if (!parsed.success) {
    return errorResponse("Enter a question before asking AuthLens.", 400);
  }

  const backendApiUrl = getBackendApiUrl();

  if (!backendApiUrl) {
    const error = backendNotConfiguredError();
    return errorResponse(error.error, error.status);
  }

  const body = new FormData();
  body.set("user_query", parsed.data.user_query);

  try {
    const backendResponse = await fetch(
      buildBackendUrl(backendApiUrl, "/api/queries/"),
      {
        method: "POST",
        headers: buildBackendHeaders(),
        body,
        cache: "no-store"
      }
    );

    if (!backendResponse.ok) {
      const error = await normalizeBackendError(backendResponse);
      return errorResponse(error.error, error.status);
    }

    const responsePayload = await backendResponse.json();
    const parsedResponse = parseQaResponse(responsePayload);
    return NextResponse.json({
      ...parsedResponse,
      source_documents: sanitizeSources(parsedResponse.source_documents)
    });
  } catch {
    return errorResponse("AuthLens could not reach the backend.", 502);
  }
}
