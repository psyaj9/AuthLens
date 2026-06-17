import "server-only";

import { z } from "zod";

export type NormalizedBackendError = {
  error: string;
  status: number;
};

export type QaResponse = {
  response: string;
  source_documents: string[];
};

const qaResponseSchema = z.object({
  response: z.string().min(1),
  source_documents: z
    .preprocess((value) => {
      if (!Array.isArray(value)) {
        return [];
      }

      return value.map((item) =>
        typeof item === "string" ? item : JSON.stringify(item)
      );
    }, z.array(z.string()))
    .default([])
});

const LOCAL_DEV_BACKEND_API_URL = "http://127.0.0.1:8000";

export function getBackendApiUrl() {
  const value = process.env.BACKEND_API_URL?.trim();
  if (value && value.length > 0) {
    return value;
  }

  if (process.env.NODE_ENV === "development") {
    return LOCAL_DEV_BACKEND_API_URL;
  }

  return null;
}

export function getInternalApiToken() {
  const value = process.env.INTERNAL_API_TOKEN?.trim();
  return value && value.length > 0 ? value : undefined;
}

export function buildBackendUrl(baseUrl: string, path: string) {
  const base = baseUrl.replace(/\/+$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${suffix}`;
}

export function buildBackendHeaders(
  token = getInternalApiToken()
): Record<string, string> {
  if (!token) {
    return {};
  }

  return {
    Authorization: `Bearer ${token}`
  };
}

export function isCrossOriginMutation(request: Request) {
  const origin = request.headers.get("origin");
  const requestOrigin = new URL(request.url).origin;
  if (origin && origin !== requestOrigin) {
    return true;
  }

  const fetchSite = request.headers.get("sec-fetch-site");
  return Boolean(fetchSite && fetchSite !== "same-origin" && fetchSite !== "none");
}

export async function readJsonOrText(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

export async function normalizeBackendError(
  response: Response
): Promise<NormalizedBackendError> {
  let message = `Backend request failed with status ${response.status}.`;

  try {
    const payload = await readJsonOrText(response.clone());

    if (typeof payload === "string" && payload.trim().length > 0) {
      message = payload.trim();
    } else if (
      payload &&
      typeof payload === "object" &&
      "error" in payload &&
      typeof payload.error === "string" &&
      payload.error.trim().length > 0
    ) {
      message = payload.error.trim();
    } else if (
      payload &&
      typeof payload === "object" &&
      "detail" in payload &&
      typeof payload.detail === "string" &&
      payload.detail.trim().length > 0
    ) {
      message = payload.detail.trim();
    }
  } catch {
    message = "Backend returned an unreadable error response.";
  }

  return {
    error: message,
    status: response.status || 502
  };
}

export function parseQaResponse(payload: unknown): QaResponse {
  const parsed = qaResponseSchema.safeParse(payload);

  if (!parsed.success) {
    throw new Error("Backend returned an unexpected answer format.");
  }

  return parsed.data;
}

export function backendNotConfiguredError(): NormalizedBackendError {
  return {
    error: "Backend API URL is not configured.",
    status: 503
  };
}
