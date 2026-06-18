"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  FileText,
  LogOut,
  Plus,
  Save,
  ShieldCheck,
  UploadCloud
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import {
  approveDraft,
  createCase,
  createPriorAuthDraft,
  extractCriteria,
  forgotPassword,
  generateReadinessReport,
  getCurrentUser,
  listCaseDocuments,
  listCases,
  listCriteria,
  listDrafts,
  listEvidence,
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
import type {
  CaseDocument,
  CaseSummary,
  CitationCheck,
  Criterion,
  DraftLetter,
  EvidenceMatch,
  ReadinessReport,
  UserProfile
} from "@/lib/api/priorauth-schemas";

type AsyncStatus = "idle" | "loading" | "success" | "error";
type AuthMode = "login" | "register" | "forgot" | "reset";
type WorkflowTab = "documents" | "criteria" | "evidence" | "readiness" | "draft";
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
  ["patient_note", "Patient note"],
  ["lab_result", "Lab result"],
  ["imaging_report", "Imaging report"],
  ["medication_history", "Medication history"],
  ["referral_letter", "Referral letter"],
  ["other", "Other"]
] as const;

const defaultCase = {
  patient_label: "SYN-LMRI-001",
  payer_name: "Example Health Plan",
  specialty: "Radiology",
  requested_service: "Lumbar spine MRI",
  service_code: "72148",
  case_type: "prior_auth" as const
};

function messageFrom(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

function statusTone(status: string) {
  if (status.includes("ready") || status === "approved" || status === "met") {
    return "success";
  }
  if (status.includes("missing") || status.includes("unclear") || status === "not_found") {
    return "warning";
  }
  if (status === "not_met" || status === "fail") {
    return "error";
  }
  return "idle";
}

function listToText(items: string[]) {
  return items.join("\n");
}

function textToList(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function citationIssueText(item: Record<string, unknown>) {
  const issue = typeof item.issue === "string" ? item.issue : undefined;
  const claim = typeof item.claim === "string" ? item.claim : undefined;
  const citation = typeof item.citation === "string" ? item.citation : undefined;
  return [claim ?? citation, issue].filter(Boolean).join(": ") || JSON.stringify(item);
}

async function loadCaseArtifacts(caseId: string) {
  const [documents, criteria, evidence, drafts] = await Promise.all([
    listCaseDocuments(caseId).catch(() => []),
    listCriteria(caseId).catch(() => []),
    listEvidence(caseId).catch(() => []),
    listDrafts(caseId).catch(() => [])
  ]);

  return { criteria, documents, drafts, evidence };
}

function TabButton({
  active,
  children,
  onClick
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`rounded-md px-3 py-2 text-sm font-semibold transition ${
        active
          ? "bg-[var(--accent)] text-white"
          : "border border-[var(--border)] bg-white text-[var(--foreground)] hover:bg-[#f3f7f5]"
      }`}
      onClick={onClick}
      type="button"
    >
      {children}
    </button>
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
  const [email, setEmail] = useState("");
  const [credentialsEditable, setCredentialsEditable] = useState(false);
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [password, setPassword] = useState("");
  const [resetToken, setResetToken] = useState("");

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
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <Panel className="w-full max-w-md" labelledBy="login-heading">
        <PanelHeader
          action={<StatusPill tone={status === "error" ? "error" : "idle"}>Account</StatusPill>}
          id="login-heading"
          title="PriorAuth Evidence Copilot"
        >
          Synthetic or de-identified documents only.
        </PanelHeader>
        <form autoComplete="off" className="flex flex-col gap-4 p-5" onSubmit={submit}>
          {mode === "register" ? (
            <>
              <label className="flex flex-col gap-2 text-sm font-semibold">
                Name
                <input
                  autoComplete="name"
                  className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
                  onChange={(event) => setName(event.target.value)}
                  type="text"
                  value={name}
                />
              </label>
              <label className="flex flex-col gap-2 text-sm font-semibold">
                Organization
                <input
                  autoComplete="organization"
                  className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
                  onChange={(event) => setOrganizationName(event.target.value)}
                  type="text"
                  value={organizationName}
                />
              </label>
            </>
          ) : null}
          {mode === "reset" ? (
            <label className="flex flex-col gap-2 text-sm font-semibold">
              Reset token
              <input
                autoComplete="one-time-code"
                className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
                onChange={(event) => setResetToken(event.target.value)}
                type="text"
                value={resetToken}
              />
            </label>
          ) : (
            <label className="flex flex-col gap-2 text-sm font-semibold">
              Email
              <input
                autoComplete={mode === "login" ? "off" : "email"}
                className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
                onFocus={() => setCredentialsEditable(true)}
                onMouseDown={() => setCredentialsEditable(true)}
                onChange={(event) => setEmail(event.target.value)}
                readOnly={credentialsReadOnly}
                type="email"
                value={email}
              />
            </label>
          )}
          {mode !== "forgot" ? (
            <label className="flex flex-col gap-2 text-sm font-semibold">
              Password
              <input
                autoComplete={mode === "login" ? "off" : "new-password"}
                className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
                onFocus={() => setCredentialsEditable(true)}
                onMouseDown={() => setCredentialsEditable(true)}
                onChange={(event) => setPassword(event.target.value)}
                readOnly={credentialsReadOnly}
                type="password"
                value={password}
              />
            </label>
          ) : null}
          {message ? (
            <p
              className={`rounded-md border px-3 py-2 text-sm ${
                status === "error"
                  ? "border-[#f0b8b3] bg-[#fff1f0] text-[var(--danger)]"
                  : "border-[#bfe3ce] bg-[#f0faf4] text-[var(--success)]"
              }`}
              role={status === "error" ? "alert" : "status"}
            >
              {message}
            </p>
          ) : null}
          <Button isLoading={status === "loading"} type="submit">
            <ShieldCheck aria-hidden className="h-4 w-4" />
            {title}
          </Button>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {mode === "login" ? (
              <>
                <Button onClick={() => setMode("register")} type="button" variant="secondary">
                  Create account
                </Button>
                <Button onClick={() => setMode("forgot")} type="button" variant="secondary">
                  Forgot password
                </Button>
              </>
            ) : (
              <Button onClick={() => setMode("login")} type="button" variant="secondary">
                Sign in
              </Button>
            )}
            {mode === "forgot" ? (
              <Button onClick={() => setMode("reset")} type="button" variant="secondary">
                Reset password
              </Button>
            ) : null}
          </div>
        </form>
      </Panel>
    </main>
  );
}

export function PriorAuthWorkspace() {
  const [activeTab, setActiveTab] = useState<WorkflowTab>("documents");
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [citationCheck, setCitationCheck] = useState<CitationCheck | null>(null);
  const [criteria, setCriteria] = useState<Criterion[]>([]);
  const [criterionEdits, setCriterionEdits] = useState<Record<string, CriterionEdit>>({});
  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [drafts, setDrafts] = useState<DraftLetter[]>([]);
  const [draftEdits, setDraftEdits] = useState<Record<string, string>>({});
  const [evidence, setEvidence] = useState<EvidenceMatch[]>([]);
  const [evidenceOverrides, setEvidenceOverrides] = useState<Record<string, EvidenceOverrideEdit>>({});
  const [file, setFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState("payer_policy");
  const [message, setMessage] = useState<string>();
  const [report, setReport] = useState<ReadinessReport | null>(null);
  const [selectedCaseId, setSelectedCaseId] = useState<string>();
  const [status, setStatus] = useState<AsyncStatus>("idle");
  const [user, setUser] = useState<UserProfile | null>(null);

  const selectedCase = useMemo(
    () => cases.find((item) => item.id === selectedCaseId) ?? cases[0],
    [cases, selectedCaseId]
  );

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
    setCitationCheck(null);
  }, []);

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
    if (selectedCase?.id) {
      let cancelled = false;

      void loadCaseArtifacts(selectedCase.id).then((nextArtifacts) => {
        if (cancelled) {
          return;
        }

        setDocuments(nextArtifacts.documents);
        setCriteria(nextArtifacts.criteria);
        setEvidence(nextArtifacts.evidence);
        setDrafts(nextArtifacts.drafts);
        setCitationCheck(null);
      });

      return () => {
        cancelled = true;
      };
    }
  }, [selectedCase?.id]);

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
  }

  function handleCreateCase() {
    void runAction(async () => {
      const created = await createCase(defaultCase);
      await refreshCases();
      setSelectedCaseId(created.id);
    }, "Synthetic prior authorization case created.");
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
      setCitationCheck(null);
    }, "Prior authorization draft generated.");
  }

  function handleVerifyDraft(draftId: string) {
    void runAction(async () => {
      setCitationCheck(await verifyDraftCitations(draftId));
    }, "Citation verification completed.");
  }

  function criterionEdit(criterion: Criterion): CriterionEdit {
    return criterionEdits[criterion.id] ?? {
      requirement: criterion.requirement,
      requiredEvidenceText: listToText(criterion.required_evidence),
      reviewerStatus: criterion.reviewer_status
    };
  }

  function setCriterionEdit(criterion: Criterion, changes: Partial<CriterionEdit>) {
    setCriterionEdits((current) => ({
      ...current,
      [criterion.id]: { ...criterionEdit(criterion), ...changes }
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
        delete next[updated.id];
        return next;
      });
    }, "Criterion review saved.");
  }

  function evidenceOverride(match: EvidenceMatch): EvidenceOverrideEdit {
    return evidenceOverrides[match.id] ?? {
      status: (match.reviewer_override_status ?? match.status) as EvidenceOverrideEdit["status"],
      reason: match.reviewer_override_reason ?? ""
    };
  }

  function setEvidenceOverride(match: EvidenceMatch, changes: Partial<EvidenceOverrideEdit>) {
    setEvidenceOverrides((current) => ({
      ...current,
      [match.id]: { ...evidenceOverride(match), ...changes }
    }));
  }

  function handleSaveEvidenceOverride(match: EvidenceMatch) {
    const override = evidenceOverride(match);
    void runAction(async () => {
      const updated = await overrideEvidenceMatch(match.id, {
        reviewer_override_status: override.status,
        reviewer_override_reason: override.reason.trim()
      });
      setEvidence((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setEvidenceOverrides((current) => {
        const next = { ...current };
        delete next[updated.id];
        return next;
      });
      await refreshCases();
    }, "Evidence override saved.");
  }

  function draftEdit(draft: DraftLetter) {
    return draftEdits[draft.id] ?? draft.content_markdown;
  }

  function handleSaveDraftEdits(draft: DraftLetter) {
    const content = draftEdit(draft);
    void runAction(async () => {
      const updated = await updateDraft(draft.id, content);
      setDrafts((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setDraftEdits((current) => ({ ...current, [updated.id]: updated.content_markdown }));
      setCitationCheck(null);
    }, "Draft edits saved.");
  }

  function handleApproveDraft(draft: DraftLetter) {
    void runAction(async () => {
      const updated = await approveDraft(draft.id);
      setDrafts((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      await refreshCases();
    }, "Draft approved.");
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
    <main className="min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-4">
        <header className="flex flex-col gap-3 rounded-md border border-[var(--border)] bg-white px-4 py-4 shadow-[0_1px_2px_rgba(24,33,28,0.05)] lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-[#e8f4f2] text-[var(--accent)]">
              <ClipboardCheck aria-hidden className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-6">PriorAuth Evidence Copilot</h1>
              <p className="text-sm text-[var(--muted)]">
                {user.organization.name} / {user.role.replace("_", " ")}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <p className="rounded-md border border-[#eed2a8] bg-[#fff8eb] px-3 py-2 text-sm font-medium text-[var(--warning)]">
              Synthetic or de-identified data only.
            </p>
            <Button onClick={handleLogout} variant="secondary">
              <LogOut aria-hidden className="h-4 w-4" />
              Sign out
            </Button>
          </div>
        </header>

        {message ? (
          <p
            className={`rounded-md border px-3 py-2 text-sm ${
              status === "error"
                ? "border-[#f0b8b3] bg-[#fff1f0] text-[var(--danger)]"
                : "border-[#bfe3ce] bg-[#f0faf4] text-[var(--success)]"
            }`}
            role={status === "error" ? "alert" : "status"}
          >
            {message}
          </p>
        ) : null}

        <div className="grid min-h-[calc(100vh-150px)] grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
          <Panel className="min-h-[560px]" labelledBy="cases-heading">
            <PanelHeader
              action={<Button onClick={handleCreateCase}><Plus aria-hidden className="h-4 w-4" />Case</Button>}
              id="cases-heading"
              title="Cases"
            >
              Prior authorization work queue.
            </PanelHeader>
            <div className="flex flex-col gap-3 p-4">
              {cases.length === 0 ? (
                <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4 text-sm text-[var(--muted)]">
                  No cases yet.
                </div>
              ) : (
                cases.map((caseItem) => (
                  <button
                    className={`rounded-md border p-3 text-left transition ${
                      selectedCase?.id === caseItem.id
                        ? "border-[var(--accent)] bg-[#eef9f7]"
                        : "border-[var(--border)] bg-white hover:bg-[#f8fbf9]"
                    }`}
                    key={caseItem.id}
                    onClick={() => setSelectedCaseId(caseItem.id)}
                    type="button"
                  >
                    <span className="mb-2 flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-semibold">{caseItem.patient_label}</span>
                      <StatusPill tone={statusTone(caseItem.status)}>{caseItem.status}</StatusPill>
                    </span>
                    <span className="block text-sm text-[var(--muted)]">{caseItem.requested_service}</span>
                    <span className="mt-2 grid grid-cols-2 gap-2 text-xs text-[var(--muted)]">
                      <span>{caseItem.payer_name}</span>
                      <span>{caseItem.readiness_score ?? "No"} score</span>
                    </span>
                  </button>
                ))
              )}
            </div>
          </Panel>

          <section className="flex min-w-0 flex-col gap-4">
            <Panel labelledBy="case-heading">
              <PanelHeader
                action={
                  selectedCase ? (
                    <StatusPill tone={statusTone(selectedCase.status)}>{selectedCase.status}</StatusPill>
                  ) : undefined
                }
                id="case-heading"
                title={selectedCase ? selectedCase.patient_label : "No case selected"}
              >
                {selectedCase
                  ? `${selectedCase.payer_name} / ${selectedCase.specialty} / ${selectedCase.requested_service}`
                  : "Create a synthetic lumbar spine MRI case to begin."}
              </PanelHeader>
              <div className="flex flex-wrap gap-2 p-4">
                <TabButton active={activeTab === "documents"} onClick={() => setActiveTab("documents")}>Documents</TabButton>
                <TabButton active={activeTab === "criteria"} onClick={() => setActiveTab("criteria")}>Criteria</TabButton>
                <TabButton active={activeTab === "evidence"} onClick={() => setActiveTab("evidence")}>Evidence</TabButton>
                <TabButton active={activeTab === "readiness"} onClick={() => setActiveTab("readiness")}>Readiness</TabButton>
                <TabButton active={activeTab === "draft"} onClick={() => setActiveTab("draft")}>Draft</TabButton>
              </div>
            </Panel>

            {activeTab === "documents" ? (
              <Panel labelledBy="documents-heading">
                <PanelHeader id="documents-heading" title="Document Upload">
                  Select a type before uploading each PDF.
                </PanelHeader>
                <div className="grid gap-4 p-4 lg:grid-cols-[320px_minmax(0,1fr)]">
                  <div className="flex flex-col gap-3">
                    <select
                      className="min-h-10 rounded-md border border-[var(--border)] bg-white px-3 text-sm"
                      onChange={(event) => setDocumentType(event.target.value)}
                      value={documentType}
                    >
                      {documentTypes.map(([value, label]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                    <label className="flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed border-[#aebbb1] bg-[#fbfdfb] px-4 text-center text-sm">
                      <UploadCloud aria-hidden className="h-5 w-5 text-[var(--accent)]" />
                      {file ? file.name : "Select a PDF"}
                      <input accept="application/pdf,.pdf" className="sr-only" onChange={handleFileChange} type="file" />
                    </label>
                    <Button disabled={!selectedCase || !file} isLoading={status === "loading"} onClick={handleUpload}>
                      <UploadCloud aria-hidden className="h-4 w-4" />
                      Upload
                    </Button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[620px] border-collapse text-sm">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-[var(--muted)]">
                          <th className="py-2 pr-3">File</th>
                          <th className="py-2 pr-3">Type</th>
                          <th className="py-2 pr-3">Pages</th>
                          <th className="py-2 pr-3">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {documents.map((document) => (
                          <tr className="border-b border-[var(--border)]" key={document.id}>
                            <td className="py-3 pr-3 font-medium">{document.file_name}</td>
                            <td className="py-3 pr-3">{document.document_type}</td>
                            <td className="py-3 pr-3">{document.page_count ?? "Pending"}</td>
                            <td className="py-3 pr-3"><StatusPill tone={statusTone(document.processing_status)}>{document.processing_status}</StatusPill></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </Panel>
            ) : null}

            {activeTab === "criteria" ? (
              <Panel labelledBy="criteria-heading">
                <PanelHeader action={<Button disabled={!selectedCase} onClick={handleExtractCriteria}><FileSearch aria-hidden className="h-4 w-4" />Extract</Button>} id="criteria-heading" title="Criteria Checklist" />
                <div className="flex flex-col gap-4 p-4">
                  {criteria.map((criterion) => {
                    const edit = criterionEdit(criterion);
                    return (
                      <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4" key={criterion.id}>
                        <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold">{criterion.criterion_code}</span>
                            <StatusPill tone={statusTone(criterion.reviewer_status)}>{criterion.reviewer_status}</StatusPill>
                          </div>
                          <span className="text-xs text-[var(--muted)]">{criterion.source_file}, page {criterion.source_page}</span>
                        </div>
                        <div className="grid gap-3 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_180px]">
                          <label className="flex flex-col gap-2 text-sm font-semibold">
                            Requirement
                            <textarea
                              className="min-h-28 resize-y rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-[var(--accent)]"
                              onChange={(event) => setCriterionEdit(criterion, { requirement: event.target.value })}
                              value={edit.requirement}
                            />
                          </label>
                          <label className="flex flex-col gap-2 text-sm font-semibold">
                            Required evidence
                            <textarea
                              className="min-h-28 resize-y rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-[var(--accent)]"
                              onChange={(event) => setCriterionEdit(criterion, { requiredEvidenceText: event.target.value })}
                              value={edit.requiredEvidenceText}
                            />
                          </label>
                          <div className="flex flex-col gap-3">
                            <label className="flex flex-col gap-2 text-sm font-semibold">
                              Review status
                              <select
                                className="min-h-10 rounded-md border border-[var(--border)] bg-white px-3 text-sm font-normal"
                                onChange={(event) => setCriterionEdit(criterion, { reviewerStatus: event.target.value })}
                                value={edit.reviewerStatus}
                              >
                                <option value="unreviewed">Unreviewed</option>
                                <option value="reviewed">Reviewed</option>
                                <option value="needs_revision">Needs revision</option>
                              </select>
                            </label>
                            <Button onClick={() => handleSaveCriterionReview(criterion)}>
                              <Save aria-hidden className="h-4 w-4" />
                              Save criterion review
                            </Button>
                          </div>
                        </div>
                        <blockquote className="mt-3 rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm leading-6 text-[var(--muted)]">
                          {criterion.source_quote}
                        </blockquote>
                      </div>
                    );
                  })}
                  {criteria.length === 0 ? (
                    <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4 text-sm text-[var(--muted)]">
                      No extracted criteria yet.
                    </div>
                  ) : null}
                </div>
              </Panel>
            ) : null}

            {activeTab === "evidence" ? (
              <Panel labelledBy="evidence-heading">
                <PanelHeader action={<Button disabled={!selectedCase || criteria.length === 0} onClick={handleMatchEvidence}><FileSearch aria-hidden className="h-4 w-4" />Match</Button>} id="evidence-heading" title="Evidence Matching" />
                <div className="flex flex-col gap-4 p-4">
                  {evidence.map((match) => {
                    const override = evidenceOverride(match);
                    const effectiveStatus = match.reviewer_override_status ?? match.status;
                    return (
                      <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4" key={match.id}>
                        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
                          <div className="flex flex-col gap-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <StatusPill tone={statusTone(effectiveStatus)}>{effectiveStatus}</StatusPill>
                              {match.reviewer_override_status ? (
                                <span className="text-xs font-semibold text-[var(--muted)]">Reviewer override</span>
                              ) : null}
                            </div>
                            <p className="text-sm leading-6">{match.evidence_summary}</p>
                            <blockquote className="rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm leading-6 text-[var(--muted)]">
                              {match.source_quote || "No source quote"} {match.source_file ? `(${match.source_file}, page ${match.source_page})` : ""}
                            </blockquote>
                            <p className="text-sm leading-6 text-[var(--muted)]">{match.recommended_action}</p>
                          </div>
                          <div className="flex flex-col gap-3">
                            <label className="flex flex-col gap-2 text-sm font-semibold">
                              Override status
                              <select
                                className="min-h-10 rounded-md border border-[var(--border)] bg-white px-3 text-sm font-normal"
                                onChange={(event) =>
                                  setEvidenceOverride(match, { status: event.target.value as EvidenceOverrideEdit["status"] })
                                }
                                value={override.status}
                              >
                                <option value="met">Met</option>
                                <option value="unclear">Unclear</option>
                                <option value="not_found">Not found</option>
                                <option value="not_met">Not met</option>
                              </select>
                            </label>
                            <label className="flex flex-col gap-2 text-sm font-semibold">
                              Override reason
                              <textarea
                                className="min-h-24 resize-y rounded-md border border-[var(--border)] bg-white px-3 py-2 text-sm font-normal leading-6 outline-none focus:border-[var(--accent)]"
                                onChange={(event) => setEvidenceOverride(match, { reason: event.target.value })}
                                value={override.reason}
                              />
                            </label>
                            <Button disabled={!override.reason.trim()} onClick={() => handleSaveEvidenceOverride(match)}>
                              <Save aria-hidden className="h-4 w-4" />
                              Save evidence override
                            </Button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {evidence.length === 0 ? (
                    <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4 text-sm text-[var(--muted)]">
                      No evidence matches yet.
                    </div>
                  ) : null}
                </div>
              </Panel>
            ) : null}

            {activeTab === "readiness" ? (
              <Panel labelledBy="readiness-heading">
                <PanelHeader action={<Button disabled={!selectedCase || evidence.length === 0} onClick={handleReport}><ClipboardCheck aria-hidden className="h-4 w-4" />Generate</Button>} id="readiness-heading" title="Readiness Report">
                  Score reflects documentation completeness only.
                </PanelHeader>
                <div className="grid gap-4 p-4 lg:grid-cols-[220px_minmax(0,1fr)]">
                  <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4">
                    <p className="text-sm text-[var(--muted)]">Readiness score</p>
                    <p className="mt-2 text-4xl font-semibold">{report?.readiness_score ?? selectedCase?.readiness_score ?? "-"}</p>
                  </div>
                  <div>
                    <p className="text-sm leading-6">{report?.summary ?? "Generate a readiness report after matching evidence."}</p>
                    <ul className="mt-4 list-disc space-y-2 pl-5 text-sm text-[var(--muted)]">
                      {(report?.recommended_next_steps ?? []).map((step) => <li key={step}>{step}</li>)}
                    </ul>
                  </div>
                </div>
              </Panel>
            ) : null}

            {activeTab === "draft" ? (
              <Panel labelledBy="draft-heading">
                <PanelHeader action={<Button disabled={!selectedCase} onClick={handleDraft}><FileText aria-hidden className="h-4 w-4" />Draft</Button>} id="draft-heading" title="Prior Authorization Draft" />
                <div className="flex flex-col gap-4 p-4">
                  {drafts.map((draft) => {
                    const activeCitationCheck = citationCheck?.draft_letter_id === draft.id ? citationCheck : null;
                    const approvalReady = activeCitationCheck?.verification_status === "pass";
                    return (
                      <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb]" key={draft.id}>
                        <div className="flex flex-col gap-3 border-b border-[var(--border)] px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
                          <div className="flex flex-wrap items-center gap-2">
                            <StatusPill tone={statusTone(draft.status)}>{draft.status}</StatusPill>
                            <span className="text-xs font-semibold text-[var(--muted)]">{draft.letter_type}</span>
                          </div>
                          <div className="flex flex-col gap-2 sm:flex-row">
                            <Button onClick={() => handleSaveDraftEdits(draft)} variant="secondary">
                              <Save aria-hidden className="h-4 w-4" />
                              Save draft edits
                            </Button>
                            <Button onClick={() => handleVerifyDraft(draft.id)} variant="secondary">
                              <ShieldCheck aria-hidden className="h-4 w-4" />
                              Verify citations
                            </Button>
                            <Button disabled={!approvalReady} onClick={() => handleApproveDraft(draft)}>
                              <CheckCircle2 aria-hidden className="h-4 w-4" />
                              Approve draft
                            </Button>
                          </div>
                        </div>
                        <div className="grid gap-4 p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
                          <label className="flex flex-col gap-2 text-sm font-semibold">
                            Draft content
                            <textarea
                              className="min-h-[360px] resize-y rounded-md border border-[var(--border)] bg-white px-3 py-3 font-mono text-sm font-normal leading-7 outline-none focus:border-[var(--accent)]"
                              onChange={(event) =>
                                setDraftEdits((current) => ({ ...current, [draft.id]: event.target.value }))
                              }
                              value={draftEdit(draft)}
                            />
                          </label>
                          <div className="rounded-md border border-[var(--border)] bg-white p-4 text-sm">
                            {activeCitationCheck ? (
                              <>
                                <StatusPill tone={statusTone(activeCitationCheck.verification_status)}>
                                  {activeCitationCheck.verification_status}
                                </StatusPill>
                                <div className="mt-4 flex flex-col gap-4">
                                  <div>
                                    <p className="font-semibold">Unsupported claims</p>
                                    <ul className="mt-2 list-disc space-y-2 pl-5 text-[var(--muted)]">
                                      {activeCitationCheck.unsupported_claims.length === 0 ? <li>None</li> : null}
                                      {activeCitationCheck.unsupported_claims.map((item, index) => (
                                        <li key={`unsupported-${index}`}>{citationIssueText(item)}</li>
                                      ))}
                                    </ul>
                                  </div>
                                  <div>
                                    <p className="font-semibold">Weak support</p>
                                    <ul className="mt-2 list-disc space-y-2 pl-5 text-[var(--muted)]">
                                      {activeCitationCheck.weakly_supported_claims.length === 0 ? <li>None</li> : null}
                                      {activeCitationCheck.weakly_supported_claims.map((item, index) => (
                                        <li key={`weak-${index}`}>{citationIssueText(item)}</li>
                                      ))}
                                    </ul>
                                  </div>
                                  <div>
                                    <p className="font-semibold">Citation errors</p>
                                    <ul className="mt-2 list-disc space-y-2 pl-5 text-[var(--muted)]">
                                      {activeCitationCheck.citation_errors.length === 0 ? <li>None</li> : null}
                                      {activeCitationCheck.citation_errors.map((item, index) => (
                                        <li key={`citation-${index}`}>{citationIssueText(item)}</li>
                                      ))}
                                    </ul>
                                  </div>
                                </div>
                              </>
                            ) : (
                              <p className="text-[var(--muted)]">No citation check for this draft yet.</p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {drafts.length === 0 ? (
                    <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb] p-4 text-sm text-[var(--muted)]">
                      No drafts yet.
                    </div>
                  ) : null}
                </div>
              </Panel>
            ) : null}
          </section>
        </div>
      </div>
    </main>
  );
}
