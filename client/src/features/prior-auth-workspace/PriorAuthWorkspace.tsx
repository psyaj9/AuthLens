"use client";

import { ButtonHTMLAttributes, ChangeEvent, FormEvent, MouseEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  Bell,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Clock,
  Download,
  Eye,
  FileSearch,
  FileText,
  FolderOpen,
  HelpCircle,
  LogOut,
  Plus,
  Save,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  Upload,
  Users,
  XCircle
} from "lucide-react";

import {
  approveDraft,
  archiveCase,
  createAppealDraft,
  createCase,
  createLetterExport,
  createPacketExport,
  createPriorAuthDraft,
  createReadinessExport,
  deleteDocument,
  extractCriteria,
  forgotPassword,
  generateReadinessReport,
  getCurrentUser,
  getLatestReadinessReport,
  listCaseAudit,
  listCaseDocuments,
  listCases,
  listCriteria,
  listDrafts,
  listEvidence,
  listOrganizationAudit,
  loginUser,
  logoutUser,
  matchEvidence,
  overrideEvidenceMatch,
  registerUser,
  resetPassword,
  updateCriterion,
  updateDraft,
  uploadCaseDocument,
  verifyDraftCitations
} from "@/lib/api/client";
import {
  formatCaseTypeLabel,
  formatDocumentTypeLabel,
  formatScoreLabel,
  formatStatusLabel,
  nextSyntheticCaseLabel
} from "./formatters";
import type {
  AuditEvent,
  CaseDocument,
  CaseSummary,
  CitationCheck,
  Criterion,
  DraftLetter,
  EvidenceMatch,
  ExportArtifact,
  ReadinessReport,
  UserProfile
} from "@/lib/api/priorauth-schemas";

type AsyncStatus = "idle" | "loading" | "success" | "error";
type AuthMode = "login" | "register" | "forgot" | "reset";
type WorkspaceView = "cases" | "case-detail" | "audit";
type WorkflowStep = "documents" | "criteria" | "evidence" | "readiness" | "draft" | "citations" | "review";
type CriterionEdit = {
  requirement: string;
  requiredEvidenceText: string;
  reviewerStatus: string;
};
type EvidenceOverrideEdit = {
  status: "met" | "unclear" | "not_found" | "not_met";
  reason: string;
};

const documentTypes = [
  ["payer_policy", "Payer policy"],
  ["denial_letter", "Denial letter"],
  ["patient_note", "Patient note"],
  ["lab_result", "Lab result"],
  ["imaging_report", "Imaging report"],
  ["medication_history", "Medication history"],
  ["referral_letter", "Referral letter"],
  ["other", "Other"]
] as const;

const workflowSteps: Array<{ id: WorkflowStep; label: string; short: string }> = [
  { id: "documents", label: "Documents", short: "Docs" },
  { id: "criteria", label: "Criteria", short: "Criteria" },
  { id: "evidence", label: "Evidence", short: "Evidence" },
  { id: "readiness", label: "Readiness", short: "Readiness" },
  { id: "draft", label: "Draft", short: "Draft" },
  { id: "citations", label: "Citations", short: "Citations" },
  { id: "review", label: "Review & Export", short: "Review" }
];

const defaultCase = {
  patient_label: "SYN-LMRI-001",
  payer_name: "Example Health Plan",
  specialty: "Radiology",
  requested_service: "Lumbar spine MRI",
  service_code: "72148",
  case_type: "prior_auth" as const
};

const defaultAppealCase = {
  patient_label: "SYN-LMRI-APPEAL-001",
  payer_name: "Example Health Plan",
  specialty: "Radiology",
  requested_service: "Lumbar spine MRI appeal",
  service_code: "72148",
  case_type: "appeal" as const
};

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function statusTone(status: string) {
  if (status.includes("ready") || status === "approved" || status === "met" || status === "indexed" || status === "completed" || status === "pass") {
    return "success";
  }
  if (status.includes("missing") || status.includes("unclear") || status === "not_found" || status === "needs_revision") {
    return "warning";
  }
  if (status === "not_met" || status === "fail" || status === "error") {
    return "error";
  }
  return "idle";
}

function textToList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function listToText(items: string[]) {
  return items.join("\n");
}

function initialResetTokenFromLocation() {
  if (typeof window === "undefined") {
    return "";
  }
  return new URLSearchParams(window.location.search).get("reset_token") ?? "";
}

function citationIssueText(item: Record<string, unknown>) {
  const issue = typeof item.issue === "string" ? item.issue : undefined;
  const claim = typeof item.claim === "string" ? item.claim : undefined;
  const citation = typeof item.citation === "string" ? item.citation : undefined;
  return [claim ?? citation, issue].filter(Boolean).join(": ") || JSON.stringify(item);
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

function compactId(value: string | null | undefined, fallback = "-") {
  if (!value) return fallback;
  if (value.length <= 16) return value;
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function wordCount(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).length;
}

function citationCount(value: string) {
  return (value.match(/\[[^\]]+\]/g) ?? []).length;
}

function evidenceCounts(matches: EvidenceMatch[]) {
  return matches.reduce(
    (counts, match) => {
      const effective = match.reviewer_override_status ?? match.status;
      if (effective === "met") counts.matched += 1;
      else if (effective === "unclear") counts.partial += 1;
      else counts.missing += 1;
      return counts;
    },
    { matched: 0, missing: 0, partial: 0 }
  );
}

async function loadCaseArtifacts(caseId: string) {
  const [documents, criteria, evidence, drafts, latestReport] = await Promise.all([
    listCaseDocuments(caseId).catch(() => []),
    listCriteria(caseId).catch(() => []),
    listEvidence(caseId).catch(() => []),
    listDrafts(caseId).catch(() => []),
    getLatestReadinessReport(caseId).catch(() => null)
  ]);

  return { criteria, documents, drafts, evidence, latestReport };
}

function ButtonLike({
  children,
  className,
  disabled,
  onClick,
  type = "button",
  variant = "primary",
  ...buttonProps
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  children: React.ReactNode;
  type?: "button" | "submit";
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success";
}) {
  const variants = {
    danger: "border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20",
    ghost: "border-transparent bg-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--muted)]",
    primary: "border-[var(--primary)] bg-[var(--primary)] text-[var(--primary-foreground)] hover:bg-[#d8b957]",
    secondary: "border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] hover:border-[var(--primary)]/40 hover:text-[var(--primary)]",
    success: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300 hover:bg-emerald-500/20"
  };

  return (
    <button
      className={cx(
        "inline-flex min-h-8 items-center justify-center gap-2 rounded border px-3 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-45 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]",
        variants[variant],
        className
      )}
      disabled={disabled}
      onClick={onClick}
      type={type}
      {...buttonProps}
    >
      {children}
    </button>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  const classes = {
    error: "border-rose-500/30 bg-rose-500/12 text-rose-300",
    idle: "border-[var(--border)] bg-[var(--muted)] text-[var(--muted-foreground)]",
    success: "border-emerald-500/25 bg-emerald-500/12 text-emerald-300",
    warning: "border-amber-500/30 bg-amber-500/12 text-amber-300"
  }[tone];

  return (
    <span className={cx("inline-flex items-center rounded border px-2 py-1 font-mono text-[11px] font-semibold leading-none", classes)}>
      {formatStatusLabel(status)}
    </span>
  );
}

function DocTypePill({ type }: { type: string }) {
  const classes: Record<string, string> = {
    denial_letter: "bg-rose-500/12 text-rose-300",
    imaging_report: "bg-cyan-500/12 text-cyan-300",
    lab_result: "bg-teal-500/12 text-teal-300",
    patient_note: "bg-blue-500/12 text-blue-300",
    payer_policy: "bg-violet-500/12 text-violet-300",
    referral_letter: "bg-amber-500/12 text-amber-300"
  };
  return (
    <span className={cx("inline-flex rounded px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.18em]", classes[type] ?? "bg-[var(--muted)] text-[var(--muted-foreground)]")}>
      {formatDocumentTypeLabel(type)}
    </span>
  );
}

function EvidenceBadge({ status }: { status: string }) {
  if (status === "met") {
    return <span className="inline-flex items-center gap-1.5 font-mono text-xs text-emerald-300"><CheckCircle2 className="size-3.5" />Matched</span>;
  }
  if (status === "unclear") {
    return <span className="inline-flex items-center gap-1.5 font-mono text-xs text-amber-300"><AlertTriangle className="size-3.5" />Partial</span>;
  }
  return <span className="inline-flex items-center gap-1.5 font-mono text-xs text-rose-300"><XCircle className="size-3.5" />Missing</span>;
}

function ReadinessGauge({ score }: { score: number | null | undefined }) {
  const value = typeof score === "number" ? Math.max(0, Math.min(100, score)) : 0;
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const color = value >= 80 ? "#34d399" : value >= 60 ? "#fbbf24" : "#fb7185";

  return (
    <div className="relative flex size-36 shrink-0 items-center justify-center">
      <svg aria-hidden className="absolute inset-0 -rotate-90" height="144" viewBox="0 0 144 144" width="144">
        <circle cx="72" cy="72" fill="none" r={radius} stroke="rgba(201,168,76,0.09)" strokeWidth="10" />
        <circle
          cx="72"
          cy="72"
          fill="none"
          r={radius}
          stroke={color}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth="10"
        />
      </svg>
      <div className="relative z-10 text-center">
        <div className="font-mono text-3xl font-semibold" data-testid="readiness-score" style={{ color }}>
          {typeof score === "number" ? Math.round(score) : "-"}
        </div>
        <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">Readiness</div>
      </div>
    </div>
  );
}

function LoginPanel({
  message,
  onForgotPassword,
  onLogin,
  onRegister,
  onResetPassword,
  status
}: {
  message?: string;
  onForgotPassword: (email: string) => void;
  onLogin: (email: string, password: string) => void;
  onRegister: (payload: { email: string; password: string; name: string; organization_name: string }) => void;
  onResetPassword: (resetToken: string, password: string) => void;
  status: AsyncStatus;
}) {
  const [initialResetToken] = useState(initialResetTokenFromLocation);
  const [email, setEmail] = useState("");
  const [credentialsEditable, setCredentialsEditable] = useState(Boolean(initialResetToken));
  const [mode, setMode] = useState<AuthMode>(initialResetToken ? "reset" : "login");
  const [name, setName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState(initialResetToken);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === "register") {
      onRegister({ email, password, name, organization_name: organizationName });
    } else if (mode === "forgot") {
      onForgotPassword(email);
    } else if (mode === "reset") {
      onResetPassword(resetToken, password);
    } else {
      onLogin(email, password);
    }
  }

  const title = mode === "register" ? "Create account" : mode === "forgot" ? "Forgot password" : mode === "reset" ? "Reset password" : "Sign in";
  const credentialsReadOnly = mode === "login" && !credentialsEditable;

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--background)] px-4 py-8 text-[var(--foreground)]">
      <section aria-labelledby="login-heading" className="w-full max-w-md rounded border border-[var(--border)] bg-[var(--card)] shadow-2xl shadow-black/25">
        <div className="border-b border-[var(--border)] px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="flex size-8 items-center justify-center rounded border border-[var(--primary)]/40 bg-[var(--primary)]/12 text-[var(--primary)]">
              <Shield className="size-4" />
            </div>
            <h1 className="font-serif text-xl font-semibold" id="login-heading">PriorAuth Evidence Copilot</h1>
          </div>
          <p className="mt-3 text-sm text-[var(--muted-foreground)]">Synthetic or de-identified documents only.</p>
        </div>
        <form autoComplete="off" className="flex flex-col gap-4 p-5" onSubmit={submit}>
          {mode === "register" ? (
            <>
              <DarkField label="Name" onChange={setName} type="text" value={name} />
              <DarkField label="Organization" onChange={setOrganizationName} type="text" value={organizationName} />
            </>
          ) : null}
          {mode === "reset" ? (
            <DarkField label="Reset token" onChange={setResetToken} type="text" value={resetToken} />
          ) : (
            <DarkField
              autoComplete={mode === "login" ? "off" : "email"}
              label="Email"
              onChange={setEmail}
              onFocus={() => setCredentialsEditable(true)}
              readOnly={credentialsReadOnly}
              type="email"
              value={email}
            />
          )}
          {mode !== "forgot" ? (
            <DarkField
              autoComplete={mode === "login" ? "off" : "new-password"}
              label="Password"
              onChange={setPassword}
              onFocus={() => setCredentialsEditable(true)}
              readOnly={credentialsReadOnly}
              type="password"
              value={password}
            />
          ) : null}
          {message ? (
            <p
              className={cx(
                "rounded border px-3 py-2 text-sm",
                status === "error"
                  ? "border-rose-500/30 bg-rose-500/12 text-rose-300"
                  : "border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
              )}
              role={status === "error" ? "alert" : "status"}
            >
              {message}
            </p>
          ) : null}
          <ButtonLike disabled={status === "loading"} type="submit">
            <ShieldCheck className="size-4" />
            {title}
          </ButtonLike>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {mode === "login" ? (
              <>
                <ButtonLike onClick={() => setMode("register")} variant="secondary">Create account</ButtonLike>
                <ButtonLike onClick={() => setMode("forgot")} variant="secondary">Forgot password</ButtonLike>
              </>
            ) : (
              <ButtonLike onClick={() => setMode("login")} variant="secondary">Sign in</ButtonLike>
            )}
            {mode === "forgot" ? <ButtonLike onClick={() => setMode("reset")} variant="secondary">Reset password</ButtonLike> : null}
          </div>
        </form>
      </section>
    </main>
  );
}

function DarkField({
  autoComplete,
  label,
  onChange,
  onFocus,
  readOnly,
  type,
  value
}: {
  autoComplete?: string;
  label: string;
  onChange: (value: string) => void;
  onFocus?: () => void;
  readOnly?: boolean;
  type: string;
  value: string;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm font-semibold">
      {label}
      <input
        autoComplete={autoComplete}
        className="min-h-10 rounded border border-[var(--border)] bg-[var(--input-background)] px-3 text-sm text-[var(--foreground)] outline-none transition placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)]"
        onChange={(event) => onChange(event.target.value)}
        onFocus={onFocus}
        onMouseDown={onFocus}
        readOnly={readOnly}
        type={type}
        value={value}
      />
    </label>
  );
}

export function PriorAuthWorkspace() {
  const [activeStep, setActiveStep] = useState<WorkflowStep>("documents");
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [caseSearch, setCaseSearch] = useState("");
  const [citationCheck, setCitationCheck] = useState<CitationCheck | null>(null);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [criterionEdits, setCriterionEdits] = useState<Record<string, CriterionEdit>>({});
  const [documentType, setDocumentType] = useState("payer_policy");
  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<DraftLetter[]>([]);
  const [evidence, setEvidence] = useState<EvidenceMatch[]>([]);
  const [evidenceOverrides, setEvidenceOverrides] = useState<Record<string, EvidenceOverrideEdit>>({});
  const [exportArtifacts, setExportArtifacts] = useState<ExportArtifact[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string>();
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string>();
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [view, setView] = useState<WorkspaceView>("cases");

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? cases[0],
    [cases, selectedCaseId]
  );
  const activeReport = report?.case_id === selectedCase?.id ? report : null;
  const approvedDraftAvailable = drafts.some((draft) => draft.case_id === selectedCase?.id && draft.status === "approved");
  const latestDraft = useMemo(() => drafts.find((draft) => draft.case_id === selectedCase?.id) ?? null, [drafts, selectedCase?.id]);
  const activeCitationCheck = latestDraft && citationCheck?.draft_letter_id === latestDraft.id ? citationCheck : null;
  const approvalReady = activeCitationCheck?.verification_status === "pass";
  const canManageCases = user?.role === "admin" || user?.role === "coordinator";
  const canReview = user?.role === "admin" || user?.role === "clinician_reviewer";
  const canGenerateDraft = canManageCases;
  const canExport = user?.role === "admin" || user?.role === "coordinator" || user?.role === "clinician_reviewer";
  const counts = evidenceCounts(evidence);

  const refreshCases = useCallback(async () => {
    const nextCases = await listCases();
    setCases(nextCases);
    setSelectedCaseId((current) => current ?? nextCases[0]?.id);
  }, []);

  const refreshCaseArtifacts = useCallback(async (caseId: string) => {
    const nextArtifacts = await loadCaseArtifacts(caseId);
    setDocuments(nextArtifacts.documents);
    setCriteria(nextArtifacts.criteria);
    setEvidence(nextArtifacts.evidence);
    setDrafts(nextArtifacts.drafts);
    setReport(nextArtifacts.latestReport);
    setCitationCheck(null);
  }, []);

  function resetCaseScopedState() {
    setDocuments([]);
    setCriteria([]);
    setEvidence([]);
    setDrafts([]);
    setCriterionEdits({});
    setEvidenceOverrides({});
    setDraftEdits({});
    setCitationCheck(null);
    setExportArtifacts([]);
    setReport(null);
    setAuditEvents([]);
  }

  useEffect(() => {
    getCurrentUser()
      .then((profile) => {
        setUser(profile);
        if (profile) {
          return refreshCases();
        }
        return undefined;
      })
      .catch(() => setUser(null));
  }, [refreshCases]);

  useEffect(() => {
    if (!selectedCase?.id) return;
    let cancelled = false;

    void loadCaseArtifacts(selectedCase.id).then((nextArtifacts) => {
      if (cancelled) return;
      setDocuments(nextArtifacts.documents);
      setCriteria(nextArtifacts.criteria);
      setEvidence(nextArtifacts.evidence);
      setDrafts(nextArtifacts.drafts);
      setReport(nextArtifacts.latestReport);
      setCitationCheck(null);
      setExportArtifacts([]);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedCase?.id]);

  useEffect(() => {
    if (!user || view !== "audit") return;
    let cancelled = false;
    const loadAudit = user.role === "admin"
      ? listOrganizationAudit()
      : selectedCase?.id
        ? listCaseAudit(selectedCase.id)
        : Promise.resolve([]);

    void loadAudit
      .then((events) => {
        if (!cancelled) setAuditEvents(events);
      })
      .catch(() => {
        if (!cancelled) setAuditEvents([]);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedCase?.id, user, view]);

  async function runAction(action: () => Promise<string | void>, success: string) {
    setMessage(undefined);
    setStatus("loading");
    try {
      const nextMessage = await action();
      setStatus("success");
      setMessage(nextMessage ?? success);
    } catch (error) {
      setStatus("error");
      setMessage(messageFrom(error, "Request failed."));
    }
  }

  function handleLogin(email: string, password: string) {
    void runAction(async () => {
      const result = await loginUser(email, password);
      setUser(result.user);
      await refreshCases();
    }, "Signed in.");
  }

  function handleRegister(payload: { email: string; password: string; name: string; organization_name: string }) {
    void runAction(async () => {
      const result = await registerUser(payload);
      setUser(result.user);
      await refreshCases();
    }, "Account created.");
  }

  function handleForgotPassword(email: string) {
    void runAction(async () => {
      const result = await forgotPassword(email);
      return result.reset_token ? `${result.message} Reset token: ${result.reset_token}` : result.message;
    }, "Password reset requested.");
  }

  function handleResetPassword(resetToken: string, password: string) {
    void runAction(async () => {
      await resetPassword(resetToken, password);
    }, "Password reset complete.");
  }

  async function handleLogout() {
    await logoutUser();
    setUser(null);
    setCases([]);
    setSelectedCaseId(undefined);
    setView("cases");
    resetCaseScopedState();
  }

  function handleCreateCase(caseType: "prior_auth" | "appeal") {
    void runAction(async () => {
      const base = caseType === "appeal" ? defaultAppealCase : defaultCase;
      const prefix = caseType === "appeal" ? "SYN-LMRI-APPEAL" : "SYN-LMRI";
      const created = await createCase({
        ...base,
        patient_label: nextSyntheticCaseLabel(
          cases.map((caseItem) => caseItem.patient_label),
          prefix
        )
      });
      await refreshCases();
      resetCaseScopedState();
      setSelectedCaseId(created.id);
      setActiveStep("documents");
      setView("case-detail");
    }, caseType === "appeal" ? "Synthetic appeal case created." : "Synthetic prior authorization case created.");
  }

  function handleArchiveCase(caseItem: CaseSummary, event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    const confirmed = window.confirm(`Delete ${caseItem.patient_label} from the active work queue?`);
    if (!confirmed) return;

    void runAction(async () => {
      await archiveCase(caseItem.id);
      const remainingCases = cases.filter((item) => item.id !== caseItem.id);
      setCases(remainingCases);
      if (selectedCase?.id === caseItem.id) {
        setSelectedCaseId(remainingCases[0]?.id);
        resetCaseScopedState();
        setView("cases");
      }
      await refreshCases();
    }, "Case deleted from the active work queue.");
  }

  function handleSelectCase(caseItem: CaseSummary) {
    resetCaseScopedState();
    setSelectedCaseId(caseItem.id);
    setActiveStep("documents");
    setView("case-detail");
    void refreshCaseArtifacts(caseItem.id);
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }

  function handleUpload() {
    if (!selectedCase || !file) {
      setMessage("Select a case and PDF before uploading.");
      setStatus("error");
      return;
    }
    void runAction(async () => {
      await uploadCaseDocument(selectedCase.id, documentType, file);
      setFile(null);
      await refreshCaseArtifacts(selectedCase.id);
      await refreshCases();
    }, "Document uploaded and indexed.");
  }

  function handleDeleteDocument(document: CaseDocument) {
    if (!selectedCase) return;
    const confirmed = window.confirm(
      `Delete ${document.file_name} from this case? Generated criteria, evidence, readiness reports, drafts, and exports will need to be regenerated.`
    );
    if (!confirmed) return;

    void runAction(async () => {
      await deleteDocument(document.id);
      resetCaseScopedState();
      await refreshCaseArtifacts(selectedCase.id);
      await refreshCases();
    }, "Document deleted.");
  }

  function handleExtractCriteria() {
    if (!selectedCase) return;
    void runAction(async () => {
      setCriteria(await extractCriteria(selectedCase.id));
      setCriterionEdits({});
      await refreshCases();
    }, "Criteria extracted from payer policy.");
  }

  function handleMatchEvidence() {
    if (!selectedCase) return;
    void runAction(async () => {
      setEvidence(await matchEvidence(selectedCase.id));
      setEvidenceOverrides({});
      await refreshCases();
    }, "Evidence matched against criteria.");
  }

  function handleReport() {
    if (!selectedCase) return;
    void runAction(async () => {
      setReport(await generateReadinessReport(selectedCase.id));
      await refreshCases();
    }, "Readiness report generated.");
  }

  function handleDraft() {
    if (!selectedCase) return;
    void runAction(async () => {
      const draft = await createPriorAuthDraft(selectedCase.id);
      setDrafts([draft, ...drafts.filter((item) => item.id !== draft.id)]);
      setDraftEdits((current) => ({ ...current, [draft.id]: draft.content_markdown }));
      await refreshCases();
    }, "Prior authorization draft generated.");
  }

  function handleAppealDraft() {
    if (!selectedCase) return;
    void runAction(async () => {
      const draft = await createAppealDraft(selectedCase.id);
      setDrafts([draft, ...drafts.filter((item) => item.id !== draft.id)]);
      setDraftEdits((current) => ({ ...current, [draft.id]: draft.content_markdown }));
      await refreshCases();
    }, "Appeal draft generated.");
  }

  function handleVerifyDraft(draftId: string) {
    void runAction(async () => {
      setCitationCheck(await verifyDraftCitations(draftId));
      await refreshCases();
      setActiveStep("citations");
    }, "Citation verification complete.");
  }

  function criterionEdit(criterion: Criterion): CriterionEdit {
    return (
      criterionEdits[criterion.id] ?? {
        requirement: criterion.requirement,
        requiredEvidenceText: listToText(criterion.required_evidence),
        reviewerStatus: criterion.reviewer_status
      }
    );
  }

  function setCriterionEdit(criterion: Criterion, patch: Partial<CriterionEdit>) {
    setCriterionEdits((current) => ({
      ...current,
      [criterion.id]: {
        ...criterionEdit(criterion),
        ...patch
      }
    }));
  }

  function handleSaveCriterionReview(criterion: Criterion) {
    const edit = criterionEdit(criterion);
    void runAction(async () => {
      const updated = await updateCriterion(criterion.id, {
        requirement: edit.requirement,
        required_evidence: textToList(edit.requiredEvidenceText),
        reviewer_status: edit.reviewerStatus
      });
      setCriteria((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setCriterionEdits((current) => {
        const next = { ...current };
        delete next[criterion.id];
        return next;
      });
      await refreshCases();
    }, "Criterion review saved.");
  }

  function evidenceOverride(match: EvidenceMatch): EvidenceOverrideEdit {
    return (
      evidenceOverrides[match.id] ?? {
        reason: match.reviewer_override_reason ?? "",
        status: (match.reviewer_override_status ?? match.status) as EvidenceOverrideEdit["status"]
      }
    );
  }

  function setEvidenceOverride(match: EvidenceMatch, patch: Partial<EvidenceOverrideEdit>) {
    setEvidenceOverrides((current) => ({
      ...current,
      [match.id]: {
        ...evidenceOverride(match),
        ...patch
      }
    }));
  }

  function handleSaveEvidenceOverride(match: EvidenceMatch) {
    const override = evidenceOverride(match);
    void runAction(async () => {
      const updated = await overrideEvidenceMatch(match.id, {
        reviewer_override_reason: override.reason,
        reviewer_override_status: override.status
      });
      setEvidence((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setEvidenceOverrides((current) => {
        const next = { ...current };
        delete next[match.id];
        return next;
      });
      await refreshCases();
    }, "Evidence override saved.");
  }

  function draftEdit(draft: DraftLetter) {
    return draftEdits[draft.id] ?? draft.content_markdown;
  }

  function handleSaveDraftEdits(draft: DraftLetter) {
    void runAction(async () => {
      const updated = await updateDraft(draft.id, draftEdit(draft));
      setDrafts((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setCitationCheck(null);
      await refreshCases();
    }, "Draft edits saved.");
  }

  function handleApproveDraft(draft: DraftLetter) {
    void runAction(async () => {
      const approved = await approveDraft(draft.id);
      setDrafts((current) => current.map((item) => (item.id === approved.id ? approved : item)));
      await refreshCases();
    }, "Draft approved.");
  }

  function handleCreateExport(kind: "readiness" | "letter" | "packet") {
    if (!selectedCase) return;
    void runAction(async () => {
      const artifact =
        kind === "readiness"
          ? await createReadinessExport(selectedCase.id)
          : kind === "letter"
            ? await createLetterExport(selectedCase.id)
            : await createPacketExport(selectedCase.id);
      setExportArtifacts((current) => [artifact, ...current.filter((item) => item.id !== artifact.id)]);
      await refreshCases();
    }, "Export artifact generated.");
  }

  function exportAuditCsv() {
    const headers = ["created_at", "actor_type", "action", "entity_type", "entity_id", "case_id", "user_id", "detail"];
    const csvCell = (value: string) => {
      const protectedValue = /^[\t\r\n=+\-@]/.test(value) || /^\s+[=+\-@]/.test(value) ? `'${value}` : value;
      return `"${protectedValue.replace(/"/g, '""')}"`;
    };
    const csv = [
      headers.join(","),
      ...auditEvents.map((event) =>
        headers
          .map((header) => {
            const raw = header === "detail" ? auditDetail(event) : String((event as unknown as Record<string, unknown>)[header] ?? "");
            return csvCell(raw);
          })
          .join(",")
      )
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "authlens-audit-events.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  if (!user) {
    return (
      <LoginPanel
        message={message}
        onForgotPassword={handleForgotPassword}
        onLogin={handleLogin}
        onRegister={handleRegister}
        onResetPassword={handleResetPassword}
        status={status}
      />
    );
  }

  return (
    <main className="flex min-h-screen bg-[var(--background)] text-[var(--foreground)]">
      <Sidebar
        activeView={view}
        caseCount={cases.length}
        onLogout={handleLogout}
        onNavigate={setView}
        user={user}
      />
      <section className="min-w-0 flex-1 overflow-hidden">
        {message ? <GlobalMessage message={message} status={status} /> : null}
        {view === "cases" ? (
          <CaseRegistry
            canManageCases={canManageCases}
            caseSearch={caseSearch}
            cases={cases}
            onArchiveCase={handleArchiveCase}
            onCreateCase={handleCreateCase}
            onSearchChange={setCaseSearch}
            onSelectCase={handleSelectCase}
          />
        ) : null}
        {view === "case-detail" ? (
          <CaseDetail
            activeCitationCheck={activeCitationCheck}
            activeReport={activeReport}
            activeStep={activeStep}
            approvalReady={approvalReady}
            approvedDraftAvailable={approvedDraftAvailable}
            canExport={canExport}
            canGenerateDraft={canGenerateDraft}
            canManageCases={canManageCases}
            canReview={canReview}
            citationCheck={citationCheck}
            counts={counts}
            criteria={criteria}
            criterionEdit={criterionEdit}
            documentType={documentType}
            documents={documents}
            draftEdit={draftEdit}
            drafts={drafts}
            evidence={evidence}
            evidenceOverride={evidenceOverride}
            exportArtifacts={exportArtifacts}
            file={file}
            latestDraft={latestDraft}
            onApproveDraft={handleApproveDraft}
            onBack={() => setView("cases")}
            onCreateExport={handleCreateExport}
            onDeleteDocument={handleDeleteDocument}
            onDocumentTypeChange={setDocumentType}
            onDraft={handleDraft}
            onExtractCriteria={handleExtractCriteria}
            onFileChange={handleFileChange}
            onGenerateReadiness={handleReport}
            onGenerateAppealDraft={handleAppealDraft}
            onMatchEvidence={handleMatchEvidence}
            onSaveCriterionReview={handleSaveCriterionReview}
            onSaveDraftEdits={handleSaveDraftEdits}
            onSaveEvidenceOverride={handleSaveEvidenceOverride}
            onSetActiveStep={setActiveStep}
            onSetCriterionEdit={setCriterionEdit}
            onSetDraftEdit={(draftId, value) => setDraftEdits((current) => ({ ...current, [draftId]: value }))}
            onSetEvidenceOverride={setEvidenceOverride}
            onUpload={handleUpload}
            onVerifyDraft={handleVerifyDraft}
            selectedCase={selectedCase}
            status={status}
          />
        ) : null}
        {view === "audit" ? (
          <AuditView
            events={auditEvents}
            onExportCsv={exportAuditCsv}
            scopeLabel={user.role === "admin" ? "Organisation audit" : selectedCase ? selectedCase.patient_label : "Select a case"}
          />
        ) : null}
      </section>
      <button
        aria-label="Help"
        className="fixed bottom-4 right-4 flex size-9 items-center justify-center rounded-full bg-white text-[#111827] shadow-lg"
        type="button"
      >
        <HelpCircle className="size-5" />
      </button>
    </main>
  );
}

function GlobalMessage({ message, status }: { message: string; status: AsyncStatus }) {
  return (
    <div className="pointer-events-none fixed left-1/2 top-4 z-50 w-[min(640px,calc(100vw-2rem))] -translate-x-1/2">
      <p
        className={cx(
          "rounded border px-4 py-3 text-sm shadow-xl shadow-black/30",
          status === "error"
            ? "border-rose-500/30 bg-rose-500/15 text-rose-200"
            : "border-emerald-500/25 bg-emerald-500/15 text-emerald-200"
        )}
        role={status === "error" ? "alert" : "status"}
      >
        {message}
      </p>
    </div>
  );
}

function Sidebar({
  activeView,
  caseCount,
  onLogout,
  onNavigate,
  user
}: {
  activeView: WorkspaceView;
  caseCount: number;
  onLogout: () => void;
  onNavigate: (view: WorkspaceView) => void;
  user: UserProfile;
}) {
  const nav = [
    { count: caseCount, icon: FolderOpen, id: "cases" as WorkspaceView, label: "Cases" },
    { count: null, icon: Activity, id: "audit" as WorkspaceView, label: "Audit Log" }
  ];

  return (
    <aside className="hidden h-screen w-[220px] shrink-0 flex-col border-r border-[var(--border)] bg-[var(--sidebar)] lg:flex">
      <div className="border-b border-[var(--sidebar-border)] px-5 py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex size-7 items-center justify-center rounded border border-[var(--primary)]/40 bg-[var(--primary)]/12 text-[var(--primary)]">
            <Shield className="size-3.5" />
          </div>
          <span className="font-serif text-[17px] font-semibold">AuthLens</span>
        </div>
        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">Organisation</div>
          <div className="mt-1 truncate text-xs font-medium">{user.organization.name}</div>
        </div>
      </div>
      <nav className="flex-1 px-3 py-4">
        <div className="px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">Workspace</div>
        {nav.map(({ count, icon: Icon, id, label }) => {
          const active = activeView === id || (activeView === "case-detail" && id === "cases");
          return (
            <button
              className={cx(
                "mb-1 flex w-full items-center justify-between rounded border px-2.5 py-2 text-sm transition",
                active
                  ? "border-[var(--primary)]/25 bg-[var(--primary)]/10 text-[var(--primary)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              )}
              key={id}
              onClick={() => onNavigate(id)}
              type="button"
            >
              <span className="flex items-center gap-2.5">
                <Icon className="size-3.5" />
                {label}
              </span>
              {count !== null ? <span className="font-mono text-[10px] text-[var(--muted-foreground)]">{count}</span> : null}
            </button>
          );
        })}
        <div className="mt-6 px-2 pb-2 font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--muted-foreground)]">Tools</div>
        {[
          { icon: FileText, label: "Documents" },
          { icon: BarChart3, label: "Analytics" },
          { icon: Users, label: "Team" }
        ].map(({ icon: Icon, label }) => (
          <button className="mb-1 flex w-full items-center gap-2.5 rounded px-2.5 py-2 text-sm text-[var(--muted-foreground)] transition hover:bg-[var(--muted)] hover:text-[var(--foreground)]" key={label} type="button">
            <Icon className="size-3.5" />
            {label}
          </button>
        ))}
      </nav>
      <div className="border-t border-[var(--sidebar-border)] px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex size-6 items-center justify-center rounded-full border border-[var(--primary)]/40 bg-[var(--primary)]/15 font-mono text-[10px] text-[var(--primary)]">
            {user.name.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-xs font-semibold">{user.name}</div>
            <div className="font-mono text-[10px] text-[var(--muted-foreground)]">{formatStatusLabel(user.role)}</div>
          </div>
          <button aria-label="Sign out" className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]" onClick={onLogout} type="button">
            <LogOut className="size-3.5" />
          </button>
          <Settings className="size-3 text-[var(--muted-foreground)]" />
        </div>
      </div>
    </aside>
  );
}

function CaseRegistry({
  canManageCases,
  caseSearch,
  cases,
  onArchiveCase,
  onCreateCase,
  onSearchChange,
  onSelectCase
}: {
  canManageCases: boolean;
  caseSearch: string;
  cases: CaseSummary[];
  onArchiveCase: (caseItem: CaseSummary, event: MouseEvent<HTMLButtonElement>) => void;
  onCreateCase: (caseType: "prior_auth" | "appeal") => void;
  onSearchChange: (value: string) => void;
  onSelectCase: (caseItem: CaseSummary) => void;
}) {
  const filtered = cases.filter((caseItem) => {
    const haystack = [caseItem.patient_label, caseItem.payer_name, caseItem.requested_service, caseItem.status].join(" ").toLowerCase();
    return haystack.includes(caseSearch.toLowerCase());
  });
  const active = cases.filter((item) => !["approved", "archived", "exported"].includes(item.status)).length;
  const approved = cases.filter((item) => item.status === "approved" || item.status === "exported").length;
  const appealing = cases.filter((item) => item.case_type === "appeal").length;
  const missingDocs = cases.filter((item) => item.missing_required_criteria_count > 0 || item.status === "needs_more_documentation").length;
  const stats = [
    { label: "Total Cases", note: "Current queue", value: cases.length },
    { label: "Active", note: "+ live work", value: active },
    { label: "Approved", note: cases.length ? `${Math.round((approved / cases.length) * 100)}% rate` : "0% rate", value: approved },
    { label: "Appealing", note: "Appeal cases", value: appealing },
    { label: "Missing Docs", note: "Action needed", value: missingDocs }
  ];

  return (
    <div className="h-screen overflow-y-auto">
      <header className="border-b border-[var(--border)] px-6 py-8 xl:px-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted-foreground)]">Prior Authorization</p>
            <h1 className="mt-2 font-serif text-2xl font-semibold">Case Registry</h1>
          </div>
          <div className="flex items-center gap-2">
            <ButtonLike aria-label="Notifications" className="px-3" variant="secondary">
              <Bell className="size-3.5" />
              <span className="size-1.5 rounded-full bg-amber-300" />
            </ButtonLike>
            <ButtonLike disabled={!canManageCases} onClick={() => onCreateCase("prior_auth")}>
              <Plus className="size-3.5" />
              New Case
            </ButtonLike>
            <ButtonLike disabled={!canManageCases} onClick={() => onCreateCase("appeal")} variant="secondary">
              Appeal
            </ButtonLike>
          </div>
        </div>
        <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {stats.map((stat) => (
            <div className="rounded border border-[var(--border)] bg-[var(--card)] px-4 py-3" key={stat.label}>
              <div className="font-mono text-xl font-semibold">{stat.value}</div>
              <div className="mt-1 text-xs text-[var(--muted-foreground)]">{stat.label}</div>
              <div className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]/70">{stat.note}</div>
            </div>
          ))}
        </div>
      </header>
      <div className="px-6 py-6 xl:px-8">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="relative w-full max-w-sm">
            <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-[var(--muted-foreground)]" />
            <span className="sr-only">Search cases</span>
            <input
              className="w-full rounded border border-[var(--border)] bg-[var(--card)] py-2 pl-9 pr-3 font-mono text-xs outline-none placeholder:text-[var(--muted-foreground)]/60 focus:border-[var(--primary)]/50"
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search cases, payers, services..."
              value={caseSearch}
            />
          </label>
          <ButtonLike variant="secondary">Filter</ButtonLike>
          <div className="ml-auto font-mono text-xs text-[var(--muted-foreground)]">{filtered.length} cases</div>
        </div>
        <div className="overflow-x-auto rounded border border-[var(--border)]">
          <table className="w-full min-w-[980px] text-xs">
            <thead>
              <tr className="bg-[#17233b] text-left">
                {["Case ID", "Patient", "Payer", "Service", "Status", "Assigned", "Created", ""].map((heading) => (
                  <th className="px-4 py-3 font-mono text-[10px] font-medium uppercase tracking-[0.22em] text-[var(--muted-foreground)]" key={heading}>{heading}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((caseItem, index) => (
                <tr
                  className={cx("group cursor-pointer border-t border-[var(--border)] transition hover:bg-[var(--card)]/80", index % 2 === 1 && "bg-[#0e1625]")}
                  key={caseItem.id}
                  onClick={() => onSelectCase(caseItem)}
                >
                  <td className="px-4 py-3 font-mono text-[11px]">
                    <button
                      aria-label={`Open case ${caseItem.patient_label}`}
                      className="text-left text-[var(--primary)] underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--primary)]"
                      data-testid={`case-card-${caseItem.id}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        onSelectCase(caseItem);
                      }}
                      type="button"
                    >
                      {compactId(caseItem.id, caseItem.patient_label)}
                    </button>
                  </td>
                  <td className="px-4 py-3">{caseItem.patient_label}</td>
                  <td className="px-4 py-3 text-[var(--muted-foreground)]">{caseItem.payer_name}</td>
                  <td className="max-w-[220px] px-4 py-3"><span className="block truncate">{caseItem.requested_service}</span></td>
                  <td className="px-4 py-3"><StatusBadge status={caseItem.status} /></td>
                  <td className="px-4 py-3 font-mono text-[var(--muted-foreground)]">{caseItem.assigned_to_user_id ? compactId(caseItem.assigned_to_user_id) : "-"}</td>
                  <td className="px-4 py-3 font-mono text-[var(--muted-foreground)]">{formatDate(caseItem.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      {canManageCases ? (
                        <button
                          aria-label={`Delete ${caseItem.patient_label}`}
                          className="text-rose-300 opacity-0 transition hover:text-rose-200 group-hover:opacity-100"
                          onClick={(event) => onArchiveCase(caseItem, event)}
                          type="button"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      ) : null}
                      <ChevronRight className="inline size-3.5 text-[var(--muted-foreground)]" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 ? <div className="p-6 text-sm text-[var(--muted-foreground)]">No cases match the current search.</div> : null}
        </div>
      </div>
    </div>
  );
}

function CaseDetail(props: {
  activeCitationCheck: CitationCheck | null;
  activeReport: ReadinessReport | null;
  activeStep: WorkflowStep;
  approvalReady: boolean;
  approvedDraftAvailable: boolean;
  canExport: boolean;
  canGenerateDraft: boolean;
  canManageCases: boolean;
  canReview: boolean;
  citationCheck: CitationCheck | null;
  counts: { matched: number; missing: number; partial: number };
  criteria: Criterion[];
  criterionEdit: (criterion: Criterion) => CriterionEdit;
  documentType: string;
  documents: CaseDocument[];
  draftEdit: (draft: DraftLetter) => string;
  drafts: DraftLetter[];
  evidence: EvidenceMatch[];
  evidenceOverride: (match: EvidenceMatch) => EvidenceOverrideEdit;
  exportArtifacts: ExportArtifact[];
  file: File | null;
  latestDraft: DraftLetter | null;
  onApproveDraft: (draft: DraftLetter) => void;
  onBack: () => void;
  onCreateExport: (kind: "readiness" | "letter" | "packet") => void;
  onDeleteDocument: (document: CaseDocument) => void;
  onDocumentTypeChange: (documentType: string) => void;
  onDraft: () => void;
  onExtractCriteria: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onGenerateAppealDraft: () => void;
  onGenerateReadiness: () => void;
  onMatchEvidence: () => void;
  onSaveCriterionReview: (criterion: Criterion) => void;
  onSaveDraftEdits: (draft: DraftLetter) => void;
  onSaveEvidenceOverride: (match: EvidenceMatch) => void;
  onSetActiveStep: (step: WorkflowStep) => void;
  onSetCriterionEdit: (criterion: Criterion, patch: Partial<CriterionEdit>) => void;
  onSetDraftEdit: (draftId: string, value: string) => void;
  onSetEvidenceOverride: (match: EvidenceMatch, patch: Partial<EvidenceOverrideEdit>) => void;
  onUpload: () => void;
  onVerifyDraft: (draftId: string) => void;
  selectedCase?: CaseSummary;
  status: AsyncStatus;
}) {
  const { activeStep, onSetActiveStep, selectedCase } = props;
  if (!selectedCase) {
    return <div className="p-8 text-sm text-[var(--muted-foreground)]">No case selected.</div>;
  }
  const activeIndex = workflowSteps.findIndex((step) => step.id === activeStep);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <CaseHeader onBack={props.onBack} selectedCase={selectedCase} />
      <WorkflowStepper
        activeStep={activeStep}
        counts={props.counts}
        criteria={props.criteria}
        documents={props.documents}
        drafts={props.drafts}
        evidence={props.evidence}
        onSetActiveStep={onSetActiveStep}
        report={props.activeReport}
      />
      <div className="flex-1 overflow-y-auto px-6 py-6 xl:px-8">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted-foreground)]">Step {activeIndex + 1} of {workflowSteps.length}</p>
            <h2 className="mt-1 font-serif text-xl font-semibold">{workflowSteps[activeIndex]?.label ?? "Workflow"}</h2>
          </div>
          <div className="flex items-center gap-2">
            {activeIndex > 0 ? (
              <ButtonLike onClick={() => onSetActiveStep(workflowSteps[activeIndex - 1].id)} variant="secondary">Previous</ButtonLike>
            ) : null}
            {activeIndex < workflowSteps.length - 1 ? (
              <ButtonLike onClick={() => onSetActiveStep(workflowSteps[activeIndex + 1].id)}>Continue <ChevronRight className="size-3.5" /></ButtonLike>
            ) : null}
          </div>
        </div>
        {activeStep === "documents" ? <DocumentsStep {...props} /> : null}
        {activeStep === "criteria" ? <CriteriaStep {...props} /> : null}
        {activeStep === "evidence" ? <EvidenceStep {...props} /> : null}
        {activeStep === "readiness" ? <ReadinessStep {...props} /> : null}
        {activeStep === "draft" ? <DraftStep {...props} /> : null}
        {activeStep === "citations" ? <CitationsStep {...props} /> : null}
        {activeStep === "review" ? <ReviewStep {...props} /> : null}
      </div>
    </div>
  );
}

function CaseHeader({ onBack, selectedCase }: { onBack: () => void; selectedCase: CaseSummary }) {
  return (
    <header className="border-b border-[var(--border)] px-6 pb-5 pt-6 xl:px-8">
      <button className="mb-4 flex items-center gap-1.5 font-mono text-[11px] text-[var(--muted-foreground)] transition hover:text-[var(--primary)]" onClick={onBack} type="button">
        <ArrowLeft className="size-3" />
        Cases
      </button>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted-foreground)]">{formatCaseTypeLabel(selectedCase.case_type)} Case</p>
          <h1 className="mt-2 font-serif text-2xl font-semibold">{selectedCase.requested_service}</h1>
        </div>
        <div className="text-right">
          <StatusBadge status={selectedCase.status} />
          <p className="mt-2 font-mono text-[10px] text-[var(--muted-foreground)]">{selectedCase.payer_name}</p>
        </div>
      </div>
      <div className="mt-6 grid overflow-hidden rounded border border-[var(--border)] bg-[var(--border)] md:grid-cols-3 xl:grid-cols-6">
        {[
          ["Case ID", compactId(selectedCase.id, selectedCase.patient_label)],
          ["Patient ID", selectedCase.patient_label],
          ["CPT Code", selectedCase.service_code ?? "-"],
          ["ICD-10", selectedCase.diagnosis_summary ?? "-"],
          ["Assigned", selectedCase.assigned_to_user_id ? compactId(selectedCase.assigned_to_user_id) : "-"],
          ["Created", formatDate(selectedCase.created_at)]
        ].map(([label, value]) => (
          <div className="bg-[var(--card)] px-4 py-3" key={label}>
            <div className="font-mono text-[9px] uppercase tracking-[0.22em] text-[var(--muted-foreground)]">{label}</div>
            <div className="mt-1 truncate font-mono text-[11px] text-[var(--foreground)]">{value}</div>
          </div>
        ))}
      </div>
    </header>
  );
}

function WorkflowStepper({
  activeStep,
  criteria,
  documents,
  drafts,
  evidence,
  onSetActiveStep,
  report
}: {
  activeStep: WorkflowStep;
  counts: { matched: number; missing: number; partial: number };
  criteria: Criterion[];
  documents: CaseDocument[];
  drafts: DraftLetter[];
  evidence: EvidenceMatch[];
  onSetActiveStep: (step: WorkflowStep) => void;
  report: ReadinessReport | null;
}) {
  const completed: Record<WorkflowStep, boolean> = {
    citations: false,
    criteria: criteria.length > 0,
    documents: documents.length > 0,
    draft: drafts.length > 0,
    evidence: evidence.length > 0,
    readiness: Boolean(report),
    review: drafts.some((draft) => draft.status === "approved")
  };
  const activeIndex = workflowSteps.findIndex((step) => step.id === activeStep);

  return (
    <div className="overflow-x-auto border-b border-[var(--border)] px-6 py-4 xl:px-8">
      <div className="flex min-w-[920px] items-center gap-2">
        {workflowSteps.map((step, index) => {
          const isActive = activeStep === step.id;
          const isDone = completed[step.id] || index < activeIndex;
          return (
            <div className="flex min-w-0 flex-1 items-center" key={step.id}>
              <button
                className={cx(
                  "flex min-w-0 flex-1 items-center gap-2 rounded border px-3 py-2 text-left transition",
                  isActive
                    ? "border-[var(--primary)]/30 bg-[var(--primary)]/10 text-[var(--primary)]"
                    : isDone
                      ? "border-transparent text-emerald-300 hover:bg-emerald-500/5"
                      : "border-transparent text-[var(--muted-foreground)] hover:bg-[var(--muted)]"
                )}
                data-testid={`workflow-step-${step.id}`}
                onClick={() => onSetActiveStep(step.id)}
                type="button"
              >
                <span className={cx(
                  "flex size-5 shrink-0 items-center justify-center rounded-full font-mono text-[10px] font-semibold",
                  isActive ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : isDone ? "border border-emerald-500/30 bg-emerald-500/15 text-emerald-300" : "border border-[var(--border)] bg-[var(--muted)]"
                )}>
                  {isDone && !isActive ? <Check className="size-3" /> : index + 1}
                </span>
                <span className="truncate text-[11px]">{step.short}</span>
              </button>
              {index < workflowSteps.length - 1 ? <ChevronRight className="mx-1 size-3 shrink-0 text-[var(--border)]" /> : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DocumentsStep({
  canManageCases,
  documentType,
  documents,
  file,
  onDeleteDocument,
  onDocumentTypeChange,
  onFileChange,
  onUpload,
  selectedCase,
  status
}: Parameters<typeof CaseDetail>[0]) {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-3 md:grid-cols-[240px_minmax(0,1fr)_120px]">
        <select
          className="min-h-10 rounded border border-[var(--border)] bg-[var(--card)] px-3 text-xs outline-none focus:border-[var(--primary)]"
          onChange={(event) => onDocumentTypeChange(event.target.value)}
          value={documentType}
        >
          {documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center rounded border border-dashed border-[var(--primary)]/25 bg-transparent px-4 text-center text-sm transition hover:border-[var(--primary)]/50">
          <Upload className="mb-2 size-5 text-[var(--primary)]/70" />
          <span>{file ? file.name : "Drop PDFs here or browse files"}</span>
          <span className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">Accepted: PDF - Max 50 MB per file</span>
          <input accept="application/pdf,.pdf" className="sr-only" onChange={onFileChange} type="file" />
        </label>
        <ButtonLike disabled={!selectedCase || !file || status === "loading"} onClick={onUpload}>
          <Upload className="size-3.5" />
          Upload
        </ButtonLike>
      </div>
      <div className="flex flex-col gap-2">
        {documents.map((document) => (
          <div className="flex items-center gap-4 rounded border border-[var(--border)] bg-[var(--card)] px-4 py-3" data-testid={`document-row-${document.id}`} key={document.id}>
            <FileText className="size-4 shrink-0 text-[var(--muted-foreground)]" />
            <div className="min-w-0 flex-1">
              <div className="truncate text-xs font-semibold">{document.file_name}</div>
              <div className="mt-1 flex flex-wrap items-center gap-3">
                <DocTypePill type={document.document_type} />
                <span className="font-mono text-[10px] text-[var(--muted-foreground)]">{document.page_count ?? "Pending"} pp - {document.extraction_method}</span>
              </div>
            </div>
            <div className="text-right">
              <StatusBadge status={document.processing_status} />
              <div className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">{formatDate(document.created_at)}</div>
            </div>
            <Eye className="size-3.5 text-[var(--muted-foreground)]" />
            {canManageCases ? (
              <button aria-label="Delete" className="text-rose-300 hover:text-rose-200" onClick={() => onDeleteDocument(document)} type="button">
                <Trash2 className="size-3.5" />
              </button>
            ) : null}
          </div>
        ))}
        {documents.length === 0 ? <EmptyState>No documents uploaded yet.</EmptyState> : null}
      </div>
    </div>
  );
}

function CriteriaStep({
  canReview,
  criteria,
  criterionEdit,
  onExtractCriteria,
  onSaveCriterionReview,
  onSetCriterionEdit,
  selectedCase
}: Parameters<typeof CaseDetail>[0]) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-[var(--muted-foreground)]">Extracted payer policy criteria and source provenance.</p>
        <ButtonLike disabled={!selectedCase} onClick={onExtractCriteria}>
          <FileSearch className="size-3.5" />
          Extract
        </ButtonLike>
      </div>
      {criteria.map((criterion) => {
        const edit = criterionEdit(criterion);
        return (
          <div className="rounded border border-[var(--border)] bg-[var(--card)]" key={criterion.id}>
            <div className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
              <span className="rounded border border-[var(--primary)]/25 bg-[var(--primary)]/10 px-2 py-1 font-mono text-[10px] text-[var(--primary)]">{criterion.criterion_code}</span>
              <p className="min-w-0 flex-1 truncate text-xs font-semibold">{criterion.requirement}</p>
              <span className="font-mono text-[10px] text-rose-300">{criterion.is_required ? "Required" : "Optional"}</span>
              <ChevronRight className="size-3 text-[var(--muted-foreground)]" />
            </div>
            <div className="grid gap-3 px-4 py-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_190px]">
              <label className="flex flex-col gap-2 text-xs font-semibold">
                Requirement
                <textarea className="min-h-28 resize-y rounded border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-[var(--primary)]" onChange={(event) => onSetCriterionEdit(criterion, { requirement: event.target.value })} value={edit.requirement} />
              </label>
              <label className="flex flex-col gap-2 text-xs font-semibold">
                Required evidence
                <textarea className="min-h-28 resize-y rounded border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-[var(--primary)]" onChange={(event) => onSetCriterionEdit(criterion, { requiredEvidenceText: event.target.value })} value={edit.requiredEvidenceText} />
              </label>
              <div className="flex flex-col gap-3">
                <label className="flex flex-col gap-2 text-xs font-semibold">
                  Review status
                  <select className="min-h-9 rounded border border-[var(--border)] bg-[var(--input-background)] px-3 text-xs" onChange={(event) => onSetCriterionEdit(criterion, { reviewerStatus: event.target.value })} value={edit.reviewerStatus}>
                    <option value="unreviewed">Unreviewed</option>
                    <option value="reviewed">Reviewed</option>
                    <option value="needs_revision">Needs revision</option>
                  </select>
                </label>
                <ButtonLike disabled={!canReview} onClick={() => onSaveCriterionReview(criterion)}>
                  <Save className="size-3.5" />
                  Save criterion review
                </ButtonLike>
              </div>
            </div>
            <div className="px-4 pb-4">
              <p className="font-mono text-[10px] text-[var(--muted-foreground)]">Source: {criterion.source_file}, page {criterion.source_page}</p>
              <blockquote className="mt-2 rounded border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-xs leading-6 text-[var(--muted-foreground)]">{criterion.source_quote}</blockquote>
            </div>
          </div>
        );
      })}
      {criteria.length === 0 ? <EmptyState>No extracted criteria yet.</EmptyState> : null}
    </div>
  );
}

function EvidenceStep({
  canReview,
  criteria,
  counts,
  evidence,
  evidenceOverride,
  onMatchEvidence,
  onSaveEvidenceOverride,
  onSetEvidenceOverride,
  selectedCase
}: Parameters<typeof CaseDetail>[0]) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-4 font-mono text-xs">
          <span className="flex items-center gap-1.5 text-emerald-300"><CheckCircle2 className="size-3.5" />{counts.matched} Matched</span>
          <span className="flex items-center gap-1.5 text-amber-300"><AlertTriangle className="size-3.5" />{counts.partial} Partial</span>
          <span className="flex items-center gap-1.5 text-rose-300"><XCircle className="size-3.5" />{counts.missing} Missing</span>
        </div>
        <ButtonLike disabled={!selectedCase || criteria.length === 0} onClick={onMatchEvidence}>
          <FileSearch className="size-3.5" />
          Match
        </ButtonLike>
      </div>
      {evidence.map((match) => {
        const criterion = criteria.find((item) => item.id === match.criterion_id);
        const effectiveStatus = (match.reviewer_override_status ?? match.status) as string;
        const override = evidenceOverride(match);
        return (
          <div
            className={cx(
              "rounded border px-4 py-3",
              effectiveStatus === "met"
                ? "border-emerald-500/20 bg-emerald-500/8"
                : effectiveStatus === "unclear"
                  ? "border-amber-500/25 bg-amber-500/8"
                  : "border-rose-500/25 bg-rose-500/8"
            )}
            key={match.id}
          >
            <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_280px]">
              <div>
                <div className="flex items-start gap-3">
                  <span className="rounded border border-[var(--border)] bg-[var(--card)] px-2 py-1 font-mono text-[10px] text-[var(--muted-foreground)]">{criterion?.criterion_code ?? compactId(match.criterion_id)}</span>
                  <p className="min-w-0 flex-1 text-xs leading-6">{criterion?.requirement ?? match.evidence_summary}</p>
                  <EvidenceBadge status={effectiveStatus} />
                </div>
                <blockquote className="ml-10 mt-3 border-l-2 border-[var(--primary)]/35 pl-3">
                  <p className="text-xs italic leading-6 text-[var(--muted-foreground)]">{match.source_quote || "No supporting evidence found in uploaded documents."}</p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]/75">
                    {match.source_file || "No source"} - p. {match.source_page || "-"} - {Math.round(match.confidence * 100)}% confidence
                  </p>
                </blockquote>
                <p className="ml-10 mt-3 text-xs leading-6 text-[var(--muted-foreground)]">{match.recommended_action}</p>
              </div>
              <div className="flex flex-col gap-3">
                <label className="flex flex-col gap-2 text-xs font-semibold">
                  Override status
                  <select className="min-h-9 rounded border border-[var(--border)] bg-[var(--input-background)] px-3 text-xs" onChange={(event) => onSetEvidenceOverride(match, { status: event.target.value as EvidenceOverrideEdit["status"] })} value={override.status}>
                    <option value="met">Met</option>
                    <option value="unclear">Unclear</option>
                    <option value="not_found">Not found</option>
                    <option value="not_met">Not met</option>
                  </select>
                </label>
                <label className="flex flex-col gap-2 text-xs font-semibold">
                  Override reason
                  <textarea className="min-h-20 resize-y rounded border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-xs leading-5 outline-none focus:border-[var(--primary)]" onChange={(event) => onSetEvidenceOverride(match, { reason: event.target.value })} value={override.reason} />
                </label>
                <ButtonLike disabled={!canReview || !override.reason.trim()} onClick={() => onSaveEvidenceOverride(match)}>
                  <Save className="size-3.5" />
                  Save evidence override
                </ButtonLike>
              </div>
            </div>
          </div>
        );
      })}
      {evidence.length === 0 ? <EmptyState>No evidence matches yet.</EmptyState> : null}
    </div>
  );
}

function ReadinessStep({
  activeReport,
  counts,
  criteria,
  onGenerateReadiness,
  selectedCase
}: Parameters<typeof CaseDetail>[0]) {
  const score = activeReport?.readiness_score ?? selectedCase?.readiness_score ?? null;
  const gaps = activeReport?.highest_risk_items ?? [];
  const nextSteps = activeReport?.recommended_next_steps ?? [];

  return (
    <section aria-labelledby="readiness-heading" className="flex flex-col gap-6" data-testid="readiness-step">
      <h3 className="sr-only" id="readiness-heading">Readiness</h3>
      <div className="flex flex-col gap-8 xl:flex-row xl:items-center">
        <ReadinessGauge score={score} />
        <div className="grid flex-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            { label: "Criteria", sub: "evaluated", value: criteria.length },
            { color: "text-emerald-300", label: "Matched", sub: "full evidence", value: counts.matched },
            { color: "text-amber-300", label: "Partial", sub: "needs supplement", value: counts.partial },
            { color: "text-rose-300", label: "Missing", sub: `${selectedCase?.missing_required_criteria_count ?? counts.missing} required`, value: selectedCase?.missing_required_criteria_count ?? counts.missing }
          ].map((item) => (
            <div className="rounded border border-[var(--border)] bg-[var(--card)] px-4 py-3" key={item.label}>
              <div className={cx("font-mono text-xl font-semibold", item.color)}>{item.value}</div>
              <div className="mt-1 text-xs text-[var(--muted-foreground)]">{item.label}</div>
              <div className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]/70">{item.sub}</div>
            </div>
          ))}
        </div>
        <ButtonLike disabled={!selectedCase || criteria.length === 0} onClick={onGenerateReadiness}>
          <ClipboardCheck className="size-3.5" />
          Generate
        </ButtonLike>
      </div>
      <section>
        <h3 className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--muted-foreground)]">Documentation Gaps</h3>
        <div className="flex flex-col gap-2">
          {gaps.map((gap, index) => (
            <div className={cx("flex items-start gap-3 rounded border px-4 py-3 text-xs", index === 0 ? "border-rose-500/25 bg-rose-500/10 text-rose-200" : "border-amber-500/25 bg-amber-500/10 text-amber-200")} key={gap}>
              {index === 0 ? <XCircle className="mt-0.5 size-3.5 shrink-0" /> : <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />}
              <p className="leading-6">{gap}</p>
            </div>
          ))}
          {gaps.length === 0 ? <EmptyState>Generate a readiness report after matching evidence.</EmptyState> : null}
        </div>
      </section>
      <section className="rounded border border-[var(--border)] bg-[var(--card)] px-5 py-4">
        <h3 className="mb-2 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--muted-foreground)]">Recommendation</h3>
        <p className="text-xs leading-6">{activeReport?.summary ?? "Readiness score reflects documentation completeness only."}</p>
        {nextSteps.length > 0 ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs leading-6 text-[var(--muted-foreground)]">
            {nextSteps.map((step) => <li key={step}>{step}</li>)}
          </ul>
        ) : null}
      </section>
    </section>
  );
}

function DraftStep({
  activeCitationCheck,
  approvalReady,
  canGenerateDraft,
  canReview,
  draftEdit,
  drafts,
  onApproveDraft,
  onDraft,
  onGenerateAppealDraft,
  onSaveDraftEdits,
  onSetDraftEdit,
  onVerifyDraft,
  selectedCase
}: Parameters<typeof CaseDetail>[0]) {
  const canAppeal = selectedCase?.case_type === "appeal";
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-end gap-2">
        <ButtonLike disabled={!selectedCase || selectedCase.case_type !== "prior_auth" || !canGenerateDraft} onClick={onDraft}>
          <FileText className="size-3.5" />
          Draft prior auth
        </ButtonLike>
        <ButtonLike disabled={!selectedCase || !canAppeal || !canGenerateDraft} onClick={onGenerateAppealDraft} variant="secondary">
          <FileText className="size-3.5" />
          Draft appeal
        </ButtonLike>
      </div>
      {drafts.map((draft) => (
        <div className="rounded border border-[var(--border)] bg-[var(--card)]" key={draft.id}>
          <div className="flex flex-col gap-3 border-b border-[var(--border)] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={draft.status} />
              <span className="font-mono text-[10px] text-[var(--muted-foreground)]">{formatCaseTypeLabel(draft.letter_type)} - {wordCount(draft.content_markdown)} words - {citationCount(draft.content_markdown)} citations</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <ButtonLike onClick={() => onSaveDraftEdits(draft)} variant="secondary">
                <Save className="size-3.5" />
                Save draft edits
              </ButtonLike>
              <ButtonLike onClick={() => onVerifyDraft(draft.id)} variant="secondary">
                <ShieldCheck className="size-3.5" />
                Verify citations
              </ButtonLike>
              <ButtonLike disabled={!canReview || !approvalReady} onClick={() => onApproveDraft(draft)} variant="success">
                <CheckCircle2 className="size-3.5" />
                Approve draft
              </ButtonLike>
            </div>
          </div>
          <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <label className="flex flex-col gap-2 text-xs font-semibold">
              Draft content
              <textarea
                className="min-h-[420px] resize-y rounded border border-[var(--border)] bg-[#0e1625] px-5 py-4 font-mono text-xs font-normal leading-7 text-[var(--foreground)] outline-none focus:border-[var(--primary)]"
                onChange={(event) => onSetDraftEdit(draft.id, event.target.value)}
                value={draftEdit(draft)}
              />
            </label>
            <CitationSummary citationCheck={activeCitationCheck?.draft_letter_id === draft.id ? activeCitationCheck : null} />
          </div>
        </div>
      ))}
      {drafts.length === 0 ? <EmptyState>No drafts yet.</EmptyState> : null}
    </div>
  );
}

function CitationsStep({ citationCheck }: Parameters<typeof CaseDetail>[0]) {
  return (
    <div className="flex flex-col gap-4">
      <CitationSummary citationCheck={citationCheck} expanded />
    </div>
  );
}

function CitationSummary({ citationCheck, expanded = false }: { citationCheck: CitationCheck | null; expanded?: boolean }) {
  if (!citationCheck) {
    return <div className="rounded border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted-foreground)]">No citation check for this draft yet.</div>;
  }
  const sections = [
    ["Unsupported claims", citationCheck.unsupported_claims],
    ["Weak support", citationCheck.weakly_supported_claims],
    ["Citation errors", citationCheck.citation_errors]
  ] as const;

  return (
    <div className="rounded border border-[var(--border)] bg-[var(--card)] p-4 text-sm">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <StatusBadge status={citationCheck.verification_status} />
        <span className="font-mono text-[10px] text-[var(--muted-foreground)]">Run ID: {compactId(citationCheck.id)}</span>
      </div>
      <div className={cx("grid gap-4", expanded && "xl:grid-cols-3")}>
        {sections.map(([label, items]) => (
          <section key={label}>
            <h3 className="font-semibold">{label}</h3>
            <ul className="mt-2 list-disc space-y-2 pl-5 text-[var(--muted-foreground)]">
              {items.length === 0 ? <li>None</li> : null}
              {items.map((item, index) => <li key={`${label}-${index}`}>{citationIssueText(item)}</li>)}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}

function ReviewStep({
  activeCitationCheck,
  activeReport,
  approvalReady,
  approvedDraftAvailable,
  canExport,
  counts,
  criteria,
  documents,
  exportArtifacts,
  latestDraft,
  onApproveDraft,
  onCreateExport,
  selectedCase
}: Parameters<typeof CaseDetail>[0]) {
  const draftSummary = latestDraft ? `v1 - ${wordCount(latestDraft.content_markdown)} words, ${citationCount(latestDraft.content_markdown)} citations` : "No draft";
  const citationSummary = activeCitationCheck
    ? `${formatStatusLabel(activeCitationCheck.verification_status)} - ${activeCitationCheck.unsupported_claims.length + activeCitationCheck.weakly_supported_claims.length + activeCitationCheck.citation_errors.length} issues`
    : "No citation check";

  return (
    <div className="flex flex-col gap-5">
      {!approvedDraftAvailable ? (
        <div className="flex items-start gap-3 rounded border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-amber-200">
          <Clock className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="text-xs font-semibold">Approval Gate - Pending Clinician Review</p>
            <p className="mt-2 text-xs leading-6">This packet cannot be exported or submitted until a clinician reviews and approves. Review the draft letter and citation report before approving.</p>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3 rounded border border-emerald-500/25 bg-emerald-500/10 px-5 py-4 text-emerald-200">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="text-xs font-semibold">Approved - Ready to Export</p>
            <p className="mt-2 text-xs leading-6">A clinician-approved draft is available for the selected case.</p>
          </div>
        </div>
      )}
      <div className="rounded border border-[var(--border)] bg-[var(--card)] px-5 py-4">
        <h3 className="mb-4 font-mono text-[10px] uppercase tracking-[0.22em] text-[var(--muted-foreground)]">Packet Summary</h3>
        <div className="grid gap-3 text-xs">
          {[
            { ok: documents.length > 0, label: "Documents indexed", value: `${documents.length} files` },
            { ok: criteria.length > 0, label: "Criteria extracted", value: `${criteria.length} criteria` },
            { ok: counts.missing === 0 && counts.partial === 0, label: "Evidence matching", value: `${counts.matched} matched, ${counts.partial} partial, ${counts.missing} missing` },
            { ok: (activeReport?.readiness_score ?? selectedCase?.readiness_score ?? 0) >= 80, label: "Readiness score", value: formatScoreLabel(activeReport?.readiness_score ?? selectedCase?.readiness_score) },
            { ok: Boolean(latestDraft), label: "Draft letter", value: draftSummary },
            { ok: activeCitationCheck?.verification_status === "pass", label: "Citation verification", value: citationSummary }
          ].map((item) => (
            <div className="flex items-center justify-between gap-4" key={item.label}>
              <div className="flex items-center gap-2.5 text-[var(--muted-foreground)]">
                {item.ok ? <Check className="size-3.5 text-emerald-300" /> : <AlertTriangle className="size-3.5 text-amber-300" />}
                <span>{item.label}</span>
              </div>
              <span className="text-right font-mono text-[11px]">{item.value}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ButtonLike disabled={!latestDraft || !approvalReady} onClick={() => latestDraft && onApproveDraft(latestDraft)} variant="success">
          <ThumbsUp className="size-3.5" />
          Approve Packet
        </ButtonLike>
        <ButtonLike variant="danger">
          <ThumbsDown className="size-3.5" />
          Return for Revision
        </ButtonLike>
        <p className="font-mono text-[10px] text-[var(--muted-foreground)]">Your decision will be recorded in the audit log.</p>
      </div>
      <div className="rounded border border-[var(--border)] bg-[var(--card)] p-4">
        <div className="mb-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="text-sm font-semibold">Exports</h3>
            <p className="mt-1 text-xs text-[var(--muted-foreground)]">PDF artifacts are generated after review gates pass.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <ButtonLike disabled={!canExport || !selectedCase || selectedCase.readiness_score == null} onClick={() => onCreateExport("readiness")} variant="secondary">
              <Download className="size-3.5" />
              Export readiness
            </ButtonLike>
            <ButtonLike disabled={!canExport || !approvedDraftAvailable} onClick={() => onCreateExport("letter")} variant="secondary">
              <Download className="size-3.5" />
              Export letter
            </ButtonLike>
            <ButtonLike disabled={!canExport || !approvedDraftAvailable} onClick={() => onCreateExport("packet")}>
              <Download className="size-3.5" />
              Export packet
            </ButtonLike>
          </div>
        </div>
        {exportArtifacts.length > 0 ? (
          <div className="grid gap-2">
            {exportArtifacts.map((artifact) => (
              <a className="flex items-center justify-between gap-3 rounded border border-[var(--border)] bg-[var(--input-background)] px-3 py-2 text-sm font-semibold text-[var(--primary)] hover:bg-[var(--muted)]" href={`/api/exports/${artifact.id}/download`} key={artifact.id}>
                <span>{artifact.file_name}</span>
                <Download className="size-4" />
              </a>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AuditView({ events, onExportCsv, scopeLabel }: { events: AuditEvent[]; onExportCsv: () => void; scopeLabel: string }) {
  const typeClass: Record<string, string> = {
    ai: "border-violet-500/25 bg-violet-500/12 text-violet-300",
    case: "border-emerald-500/25 bg-emerald-500/12 text-emerald-300",
    system: "border-blue-500/25 bg-blue-500/12 text-blue-300",
    upload: "border-amber-500/25 bg-amber-500/12 text-amber-300",
    user: "border-emerald-500/25 bg-emerald-500/12 text-emerald-300"
  };

  return (
    <div className="h-screen overflow-y-auto px-6 py-8 xl:px-8">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[var(--muted-foreground)]">Compliance</p>
          <h1 className="mt-2 font-serif text-2xl font-semibold">Audit Log</h1>
          <p className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]">{scopeLabel}</p>
        </div>
        <ButtonLike disabled={events.length === 0} onClick={onExportCsv} variant="secondary">
          <Download className="size-3.5" />
          Export CSV
        </ButtonLike>
      </div>
      <div className="mb-6 flex flex-wrap gap-3">
        {["AI", "System", "Upload", "Case"].map((label) => (
          <span className={cx("rounded border px-2 py-1 font-mono text-[10px]", typeClass[label.toLowerCase()] ?? typeClass.system)} key={label}>{label}</span>
        ))}
      </div>
      <div className="relative">
        <div className="absolute bottom-0 left-[5.5rem] top-0 w-px bg-[var(--border)]" />
        {events.map((event) => {
          const style = typeClass[event.actor_type] ?? typeClass[event.action.split(".")[0]] ?? typeClass.system;
          return (
            <div className="group flex items-start gap-6" key={event.id}>
              <div className="w-20 shrink-0 text-right font-mono text-[10px] leading-5 text-[var(--muted-foreground)]">{formatDateTime(event.created_at)}</div>
              <div className="relative mt-2 flex w-3 shrink-0 items-center justify-center">
                <div className={cx("relative z-10 size-2 rounded-full border", style)} />
              </div>
              <div className="flex-1 pb-5">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <span className="text-xs font-semibold">{formatActionLabel(event.action)}</span>
                  <span className={cx("rounded border px-1.5 py-0.5 font-mono text-[9px]", style)}>{event.actor_type}</span>
                </div>
                <p className="text-xs text-[var(--muted-foreground)]">{auditDetail(event)}</p>
                <p className="mt-1 font-mono text-[10px] text-[var(--muted-foreground)]/60">by {event.user_id ? compactId(event.user_id) : event.actor_type}</p>
              </div>
            </div>
          );
        })}
        {events.length === 0 ? <EmptyState>No audit events available for this scope.</EmptyState> : null}
      </div>
    </div>
  );
}

function formatActionLabel(action: string) {
  return action.replace(/[._-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function auditDetail(event: AuditEvent) {
  const values = Object.entries(event.metadata)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`);
  return values.length > 0 ? values.join(" - ") : `${event.entity_type} ${event.entity_id ? compactId(event.entity_id) : ""}`.trim();
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="rounded border border-[var(--border)] bg-[var(--card)] p-4 text-sm text-[var(--muted-foreground)]">{children}</div>;
}
