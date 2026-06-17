import { z } from "zod";
import {
  authResponseSchema,
  caseListSchema,
  caseSchema,
  citationCheckSchema,
  criteriaListSchema,
  documentListSchema,
  documentSchema,
  draftListSchema,
  draftSchema,
  evidenceListSchema,
  readinessReportSchema,
  userProfileSchema,
  type CaseDocument,
  type CaseSummary,
  type CitationCheck,
  type Criterion,
  type DraftLetter,
  type EvidenceMatch,
  type ReadinessReport,
  type UserProfile
} from "./priorauth-schemas";

const qaResponseSchema = z.object({
  response: z.string(),
  source_documents: z.array(z.string()).default([])
});

const uploadResponseSchema = z.record(z.string(), z.unknown());

export type QaClientResponse = z.infer<typeof qaResponseSchema>;
export type UploadClientResponse = z.infer<typeof uploadResponseSchema>;
export type LoginResponse = z.infer<typeof authResponseSchema>;

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

export async function loginDemoUser(
  email: string,
  password: string
): Promise<LoginResponse> {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  return parseLocalRouteResponse(response, authResponseSchema);
}

export async function logoutDemoUser(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export async function getCurrentUser(): Promise<UserProfile | null> {
  const response = await fetch("/api/auth/me", { cache: "no-store" });
  return parseLocalRouteResponse(response, userProfileSchema.nullable());
}

export async function listCases(): Promise<CaseSummary[]> {
  const response = await fetch("/api/cases", { cache: "no-store" });
  const payload = await parseLocalRouteResponse(response, caseListSchema);
  return payload.cases;
}

export async function createCase(payload: {
  patient_label: string;
  payer_name: string;
  specialty: string;
  requested_service: string;
  service_code?: string;
  case_type: "prior_auth";
}): Promise<CaseSummary> {
  const response = await fetch("/api/cases", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  return parseLocalRouteResponse(response, caseSchema);
}

export async function listCaseDocuments(caseId: string): Promise<CaseDocument[]> {
  const response = await fetch(`/api/cases/${caseId}/documents`, {
    cache: "no-store"
  });
  const payload = await parseLocalRouteResponse(response, documentListSchema);
  return payload.documents;
}

export async function uploadCaseDocument(
  caseId: string,
  documentType: string,
  file: File
): Promise<CaseDocument> {
  const body = new FormData();
  body.set("document_type", documentType);
  body.set("file", file);
  const response = await fetch(`/api/cases/${caseId}/documents`, {
    method: "POST",
    body
  });
  return parseLocalRouteResponse(response, documentSchema);
}

export async function extractCriteria(caseId: string): Promise<Criterion[]> {
  const response = await fetch(`/api/cases/${caseId}/criteria/extract`, {
    method: "POST"
  });
  const payload = await parseLocalRouteResponse(response, criteriaListSchema);
  return payload.criteria;
}

export async function listCriteria(caseId: string): Promise<Criterion[]> {
  const response = await fetch(`/api/cases/${caseId}/criteria`, {
    cache: "no-store"
  });
  const payload = await parseLocalRouteResponse(response, criteriaListSchema);
  return payload.criteria;
}

export async function matchEvidence(caseId: string): Promise<EvidenceMatch[]> {
  const response = await fetch(`/api/cases/${caseId}/evidence/match`, {
    method: "POST"
  });
  const payload = await parseLocalRouteResponse(response, evidenceListSchema);
  return payload.matches;
}

export async function listEvidence(caseId: string): Promise<EvidenceMatch[]> {
  const response = await fetch(`/api/cases/${caseId}/evidence`, {
    cache: "no-store"
  });
  const payload = await parseLocalRouteResponse(response, evidenceListSchema);
  return payload.matches;
}

export async function generateReadinessReport(
  caseId: string
): Promise<ReadinessReport> {
  const response = await fetch(`/api/cases/${caseId}/reports/readiness`, {
    method: "POST"
  });
  return parseLocalRouteResponse(response, readinessReportSchema);
}

export async function createPriorAuthDraft(caseId: string): Promise<DraftLetter> {
  const response = await fetch(`/api/cases/${caseId}/drafts/prior-auth`, {
    method: "POST"
  });
  return parseLocalRouteResponse(response, draftSchema);
}

export async function listDrafts(caseId: string): Promise<DraftLetter[]> {
  const response = await fetch(`/api/cases/${caseId}/drafts`, {
    cache: "no-store"
  });
  const payload = await parseLocalRouteResponse(response, draftListSchema);
  return payload.drafts;
}

export async function verifyDraftCitations(
  draftId: string
): Promise<CitationCheck> {
  const response = await fetch(`/api/drafts/${draftId}/verify-citations`, {
    method: "POST"
  });
  return parseLocalRouteResponse(response, citationCheckSchema);
}
