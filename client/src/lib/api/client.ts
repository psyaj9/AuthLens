import { z } from "zod";

const qaResponseSchema = z.object({
  response: z.string(),
  source_documents: z.array(z.string()).default([])
});

const uploadResponseSchema = z.record(z.string(), z.unknown());

export type QaClientResponse = z.infer<typeof qaResponseSchema>;
export type UploadClientResponse = z.infer<typeof uploadResponseSchema>;

export class AuthLensApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthLensApiError";
    this.status = status;
  }
}

async function parseLocalRouteResponse<T>(
  response: Response,
  schema: z.ZodType<T>
): Promise<T> {
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      payload &&
      typeof payload === "object" &&
      "error" in payload &&
      typeof payload.error === "string"
        ? payload.error
        : "AuthLens request failed.";

    throw new AuthLensApiError(message, response.status);
  }

  return schema.parse(payload);
}

export async function askQuestion(userQuery: string): Promise<QaClientResponse> {
  const trimmedQuery = userQuery.trim();

  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_query: trimmedQuery })
  });

  return parseLocalRouteResponse(response, qaResponseSchema);
}

export async function uploadDocuments(
  files: File[]
): Promise<UploadClientResponse> {
  const body = new FormData();

  for (const file of files) {
    body.append("uploaded_files", file);
  }

  const response = await fetch("/api/upload", {
    method: "POST",
    body
  });

  return parseLocalRouteResponse(response, uploadResponseSchema);
}
