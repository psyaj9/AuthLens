const STATUS_LABELS: Record<string, string> = {
  approved: "Approved",
  archived: "Archived",
  criteria_extracted: "Criteria extracted",
  draft: "Draft",
  evidence_matched: "Evidence matched",
  exported: "Exported",
  fail: "Fail",
  indexed: "Indexed",
  met: "Met",
  needs_more_documentation: "Needs more documentation",
  needs_revision: "Needs revision",
  not_found: "Not found",
  not_met: "Not met",
  pass: "Pass",
  prior_auth: "Prior authorization",
  ready: "Ready",
  ready_for_review: "Ready for review",
  reviewed: "Reviewed",
  unclear: "Unclear",
  unreviewed: "Unreviewed"
};

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  denial_letter: "Denial letter",
  imaging_report: "Imaging report",
  lab_result: "Lab result",
  medication_history: "Medication history",
  other: "Other",
  patient_note: "Patient note",
  payer_policy: "Payer policy",
  referral_letter: "Referral letter"
};

const CASE_TYPE_LABELS: Record<string, string> = {
  appeal: "Appeal",
  prior_auth: "Prior authorization"
};

function sentenceCaseFromMachineValue(value: string) {
  const normalized = value.replace(/[_-]+/g, " ").trim();
  if (!normalized) {
    return "Unknown";
  }
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function formatStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? sentenceCaseFromMachineValue(status);
}

export function formatDocumentTypeLabel(documentType: string) {
  return DOCUMENT_TYPE_LABELS[documentType] ?? sentenceCaseFromMachineValue(documentType);
}

export function formatCaseTypeLabel(caseType: string) {
  return CASE_TYPE_LABELS[caseType] ?? sentenceCaseFromMachineValue(caseType);
}

export function formatScoreLabel(score: number | null | undefined) {
  return typeof score === "number" ? `Readiness ${score}/100` : "No readiness score";
}

export function nextSyntheticCaseLabel(labels: string[], prefix: string) {
  const expression = new RegExp(`^${prefix.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}-(\\d+)$`, "i");
  const nextNumber =
    labels.reduce((highest, label) => {
      const match = expression.exec(label);
      return match ? Math.max(highest, Number(match[1])) : highest;
    }, 0) + 1;
  return `${prefix}-${String(nextNumber).padStart(3, "0")}`;
}
