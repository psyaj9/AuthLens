import {
  authHeaders,
  errorResponse,
  getAuthTokenFromRequest
} from "@/lib/server/priorauth-proxy";
import {
  backendNotConfiguredError,
  buildBackendUrl,
  getBackendApiUrl,
  normalizeBackendError
} from "@/lib/server/backend-proxy";

type RouteContext = {
  params: Promise<{ exportId: string }>;
};

export async function GET(request: Request, context: RouteContext) {
  if (!getAuthTokenFromRequest(request)) {
    return errorResponse("Authentication required.", 401);
  }
  const backendApiUrl = getBackendApiUrl();
  if (!backendApiUrl) {
    const error = backendNotConfiguredError();
    return errorResponse(error.error, error.status);
  }

  const { exportId } = await context.params;
  try {
    const backendResponse = await fetch(buildBackendUrl(backendApiUrl, `/api/exports/${exportId}/download`), {
      method: "GET",
      headers: authHeaders(request),
      cache: "no-store"
    });

    if (!backendResponse.ok) {
      const error = await normalizeBackendError(backendResponse);
      return errorResponse(error.error, error.status);
    }

    return new Response(await backendResponse.arrayBuffer(), {
      status: 200,
      headers: {
        "Content-Type": backendResponse.headers.get("content-type") ?? "application/pdf",
        "Content-Disposition": backendResponse.headers.get("content-disposition") ?? 'attachment; filename="authlens-export.pdf"',
        "X-Content-Type-Options": backendResponse.headers.get("x-content-type-options") ?? "nosniff",
      }
    });
  } catch {
    return errorResponse("AuthLens could not reach the backend.", 502);
  }
}
