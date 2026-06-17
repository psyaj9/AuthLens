import { z } from "zod";

export const organizationSchema = z.object({
  id: z.string(),
  name: z.string(),
  plan: z.string().default("demo")
});

export const userProfileSchema = z.object({
  id: z.string(),
  email: z.string(),
  name: z.string(),
  role: z.enum(["admin", "coordinator", "clinician_reviewer", "viewer"]),
  organization: organizationSchema
});

export const authResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  user: userProfileSchema
});

export const messageResponseSchema = z.object({
  message: z.string()
});

export const forgotPasswordResponseSchema = z.object({
  message: z.string(),
  reset_token: z.string().nullable().optional()
});

export const caseSchema = z.object({
  id: z.string(),
  patient_label: z.string(),
  payer_name: z.string(),
  plan_name: z.string().nullable().optional(),
  specialty: z.string(),
  requested_service: z.string(),
  service_code: z.string().nullable().optional(),
  diagnosis_summary: z.string().nullable().optional(),
  case_type: z.enum(["prior_auth", "appeal"]),
  status: z.string(),
  readiness_score: z.number().nullable(),
  missing_required_criteria_count: z.number(),
  assigned_to_user_id: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string()
});

export const caseListSchema = z.object({
  cases: z.array(caseSchema)
});

export const documentSchema = z.object({
  id: z.string(),
  case_id: z.string(),
  document_type: z.string(),
  file_name: z.string(),
  sha256: z.string(),
  mime_type: z.string(),
  page_count: z.number().nullable(),
  processing_status: z.string(),
  extraction_method: z.string(),
  created_at: z.string(),
  updated_at: z.string()
});

export const documentListSchema = z.object({
  documents: z.array(documentSchema)
});

export const criterionSchema = z.object({
  id: z.string(),
  criterion_code: z.string(),
  criterion_type: z.string(),
  requirement: z.string(),
  required_evidence: z.array(z.string()),
  is_required: z.boolean(),
  source_file: z.string(),
  source_page: z.string(),
  source_quote: z.string(),
  confidence: z.number(),
  ambiguity_notes: z.array(z.string()),
  reviewer_status: z.string()
});

export const criteriaListSchema = z.object({
  criteria: z.array(criterionSchema),
  missing_or_ambiguous_policy_info: z.array(z.string()).default([])
});

export const evidenceMatchSchema = z.object({
  id: z.string(),
  criterion_id: z.string(),
  status: z.enum(["met", "unclear", "not_found", "not_met"]),
  evidence_summary: z.string(),
  source_file: z.string(),
  source_page: z.string(),
  source_quote: z.string(),
  why_it_matters: z.string(),
  missing_evidence: z.array(z.string()),
  conflicting_evidence: z.array(z.string()),
  recommended_action: z.string(),
  confidence: z.number(),
  reviewer_override_status: z.string().nullable().optional(),
  reviewer_override_reason: z.string().nullable().optional()
});

export const evidenceListSchema = z.object({
  matches: z.array(evidenceMatchSchema)
});

export const readinessReportSchema = z.object({
  id: z.string(),
  case_id: z.string(),
  readiness_score: z.number(),
  overall_status: z.string(),
  summary: z.string(),
  highest_risk_items: z.array(z.string()),
  recommended_next_steps: z.array(z.string()),
  report_json: z.record(z.string(), z.unknown()),
  created_at: z.string()
});

export const draftSchema = z.object({
  id: z.string(),
  case_id: z.string(),
  letter_type: z.string(),
  status: z.string(),
  content_markdown: z.string(),
  created_by: z.string(),
  approved_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string()
});

export const draftListSchema = z.object({
  drafts: z.array(draftSchema)
});

export const citationCheckSchema = z.object({
  id: z.string(),
  draft_letter_id: z.string(),
  verification_status: z.string(),
  unsupported_claims: z.array(z.record(z.string(), z.unknown())),
  weakly_supported_claims: z.array(z.record(z.string(), z.unknown())),
  citation_errors: z.array(z.record(z.string(), z.unknown())),
  safe_to_show_user: z.boolean(),
  created_at: z.string()
});

export type UserProfile = z.infer<typeof userProfileSchema>;
export type MessageResponse = z.infer<typeof messageResponseSchema>;
export type ForgotPasswordResponse = z.infer<typeof forgotPasswordResponseSchema>;
export type CaseSummary = z.infer<typeof caseSchema>;
export type CaseDocument = z.infer<typeof documentSchema>;
export type Criterion = z.infer<typeof criterionSchema>;
export type EvidenceMatch = z.infer<typeof evidenceMatchSchema>;
export type ReadinessReport = z.infer<typeof readinessReportSchema>;
export type DraftLetter = z.infer<typeof draftSchema>;
export type CitationCheck = z.infer<typeof citationCheckSchema>;
