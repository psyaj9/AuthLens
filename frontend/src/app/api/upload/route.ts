import { NextResponse } from "next/server";

import {
  backendNotConfiguredError,
  buildBackendHeaders,
  buildBackendUrl,
  getBackendApiUrl,
  normalizeBackendError,
  readJsonOrText
} from "@/lib/server/backend-proxy";

export const runtime = "nodejs";

function isFileLike(value: FormDataEntryValue): value is File {
  return (
    typeof value === "object" &&
    value !== null &&
    "arrayBuffer" in value &&
    "name" in value
  );
}

function errorResponse(error: string, status: number) {
  return NextResponse.json({ error }, { status });
}

export async function POST(request: Request) {
  const incomingFormData = await request.formData().catch(() => null);

  if (!incomingFormData) {
    return errorResponse("Upload request must be multipart form data.", 400);
  }

  const files = incomingFormData
    .getAll("uploaded_files")
    .filter(isFileLike);

  if (files.length === 0) {
    return errorResponse("Select at least one PDF before uploading.", 400);
  }

  const backendApiUrl = getBackendApiUrl();

  if (!backendApiUrl) {
    const error = backendNotConfiguredError();
    return errorResponse(error.error, error.status);
  }

  const body = new FormData();

  for (const file of files) {
    body.append("uploaded_files", file);
  }

  try {
    const backendResponse = await fetch(
      buildBackendUrl(backendApiUrl, "/api/upload_pdf/"),
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

    const payload = await readJsonOrText(backendResponse);
    return NextResponse.json(
      typeof payload === "string" ? { message: payload } : payload
    );
  } catch {
    return errorResponse("AuthLens could not upload documents.", 502);
  }
}
