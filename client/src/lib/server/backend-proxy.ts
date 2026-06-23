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
const TRUTHY_ENV_VALUES = new Set(["1", "true", "yes", "on"]);
const FALSY_ENV_VALUES = new Set(["0", "false", "no", "off"]);
export const CLIENT_REQUEST_FAILED_ERROR = "Request failed.";
export const CLIENT_REQUEST_REJECTED_ERROR = "Request rejected.";

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

export function legacyQaEnabled() {
  const configured = process.env.ENABLE_LEGACY_QA?.trim().toLowerCase();
  if (configured) {
    if (TRUTHY_ENV_VALUES.has(configured)) return true;
    if (FALSY_ENV_VALUES.has(configured)) return false;
  }

  return process.env.NODE_ENV !== "production" && process.env.VERCEL_ENV !== "production";
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

function firstHeaderValue(value: string | null) {
  return value?.split(",")[0]?.trim() || undefined;
}

function normalizeProtocol(value: string | undefined) {
  const protocol = value?.trim().replace(/:$/, "").toLowerCase();
  return protocol === "http" || protocol === "https" ? protocol : undefined;
}

function originFromHost(protocol: string | undefined, host: string | undefined) {
  const safeProtocol = normalizeProtocol(protocol);
  if (!safeProtocol || !host || /\s/.test(host)) return undefined;

  try {
    return new URL(`${safeProtocol}://${host}`).origin;
  } catch {
    return undefined;
  }
}

function normalizeOrigin(value: string | null) {
  if (!value) return undefined;

  try {
    const origin = new URL(value).origin;
    return origin === "null" ? undefined : origin;
  } catch {
    return undefined;
  }
}

function requestOriginCandidates(request: Request) {
  const requestUrl = new URL(request.url);
  const candidates = new Set([requestUrl.origin]);
  const requestProtocol = normalizeProtocol(requestUrl.protocol);
  const host = firstHeaderValue(request.headers.get("host"));
  const forwardedHost = firstHeaderValue(request.headers.get("x-forwarded-host"));
  const forwardedProto =
    normalizeProtocol(firstHeaderValue(request.headers.get("x-forwarded-proto"))) ??
    requestProtocol;

  const hostOrigin = originFromHost(requestProtocol, host);
  if (hostOrigin) candidates.add(hostOrigin);

  const forwardedOrigin = originFromHost(forwardedProto, forwardedHost);
  if (forwardedOrigin) candidates.add(forwardedOrigin);

  return candidates;
}

export function isCrossOriginMutation(request: Request) {
  const origin = normalizeOrigin(request.headers.get("origin"));
  if (request.headers.has("origin") && (!origin || !requestOriginCandidates(request).has(origin))) {
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
  try {
    await readJsonOrText(response.clone());
  } catch {
    // Client-facing errors stay generic; backend details belong in server logs.
  }

  return {
    error: CLIENT_REQUEST_FAILED_ERROR,
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
    error: CLIENT_REQUEST_FAILED_ERROR,
    status: 503
  };
}
