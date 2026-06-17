"use client";

import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ClipboardCheck,
  FileSearch,
  FileText,
  LogOut,
  Plus,
  ShieldCheck,
  UploadCloud
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";
import {
  createCase,
  createPriorAuthDraft,
  extractCriteria,
  generateReadinessReport,
  getCurrentUser,
  listCaseDocuments,
  listCases,
  listCriteria,
  listDrafts,
  listEvidence,
  loginDemoUser,
  logoutDemoUser,
  matchEvidence,
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
type WorkflowTab = "documents" | "criteria" | "evidence" | "readiness" | "draft";

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
  onLogin,
  status
}: {
  message?: string;
  onLogin: (email: string, password: string) => void;
  status: AsyncStatus;
}) {
  const [email, setEmail] = useState("coordinator@demo.authlens.test");
  const [password, setPassword] = useState("demo-password");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onLogin(email, password);
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <Panel className="w-full max-w-md" labelledBy="login-heading">
        <PanelHeader
          action={<StatusPill tone={status === "error" ? "error" : "idle"}>Demo</StatusPill>}
          id="login-heading"
          title="PriorAuth Evidence Copilot"
        >
          Synthetic or de-identified documents only.
        </PanelHeader>
        <form className="flex flex-col gap-4 p-5" onSubmit={submit}>
          <label className="flex flex-col gap-2 text-sm font-semibold">
            Email
            <input
              className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              value={email}
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-semibold">
            Password
            <input
              className="min-h-10 rounded-md border border-[var(--border)] px-3 text-sm outline-none focus:border-[var(--accent)]"
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
          {message ? (
            <p className="rounded-md border border-[#f0b8b3] bg-[#fff1f0] px-3 py-2 text-sm text-[var(--danger)]" role="alert">
              {message}
            </p>
          ) : null}
          <Button isLoading={status === "loading"} type="submit">
            <ShieldCheck aria-hidden className="h-4 w-4" />
            Sign in
          </Button>
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
  const [documents, setDocuments] = useState<CaseDocument[]>([]);
  const [drafts, setDrafts] = useState<DraftLetter[]>([]);
  const [evidence, setEvidence] = useState<EvidenceMatch[]>([]);
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
  }, []);

  useEffect(() => {
    getCurrentUser()
      .then((profile) => {
        setUser(profile);
        return refreshCases();
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
      });

      return () => {
        cancelled = true;
      };
    }
  }, [selectedCase?.id]);

  async function runAction(action: () => Promise<void>, success: string) {
    setMessage(undefined);
    setStatus("loading");
    try {
      await action();
      setStatus("success");
      setMessage(success);
    } catch (error) {
      setStatus("error");
      setMessage(messageFrom(error, "Request failed."));
    }
  }

  function handleLogin(email: string, password: string) {
    void runAction(async () => {
      const result = await loginDemoUser(email, password);
      setUser(result.user);
      await refreshCases();
    }, "Signed in.");
  }

  async function handleLogout() {
    await logoutDemoUser();
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
      await refreshCases();
    }, "Criteria extracted from payer policy.");
  }

  function handleMatchEvidence() {
    if (!selectedCase) return;
    void runAction(async () => {
      setEvidence(await matchEvidence(selectedCase.id));
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
    }, "Prior authorization draft generated.");
  }

  function handleVerifyDraft(draftId: string) {
    void runAction(async () => {
      setCitationCheck(await verifyDraftCitations(draftId));
    }, "Citation verification completed.");
  }

  if (!user) {
    return <LoginPanel message={message} onLogin={handleLogin} status={status} />;
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
                <div className="divide-y divide-[var(--border)] p-4">
                  {criteria.map((criterion) => (
                    <div className="grid gap-2 py-3 lg:grid-cols-[96px_minmax(0,1fr)_160px]" key={criterion.id}>
                      <span className="text-sm font-semibold">{criterion.criterion_code}</span>
                      <p className="text-sm leading-6">{criterion.requirement}</p>
                      <span className="text-xs text-[var(--muted)]">{criterion.source_file}, page {criterion.source_page}</span>
                    </div>
                  ))}
                </div>
              </Panel>
            ) : null}

            {activeTab === "evidence" ? (
              <Panel labelledBy="evidence-heading">
                <PanelHeader action={<Button disabled={!selectedCase || criteria.length === 0} onClick={handleMatchEvidence}><FileSearch aria-hidden className="h-4 w-4" />Match</Button>} id="evidence-heading" title="Evidence Matching" />
                <div className="overflow-x-auto p-4">
                  <table className="w-full min-w-[860px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-[var(--border)] text-left text-xs uppercase text-[var(--muted)]">
                        <th className="py-2 pr-3">Status</th>
                        <th className="py-2 pr-3">Summary</th>
                        <th className="py-2 pr-3">Quote</th>
                        <th className="py-2 pr-3">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {evidence.map((match) => (
                        <tr className="border-b border-[var(--border)] align-top" key={match.id}>
                          <td className="py-3 pr-3"><StatusPill tone={statusTone(match.status)}>{match.status}</StatusPill></td>
                          <td className="py-3 pr-3">{match.evidence_summary}</td>
                          <td className="py-3 pr-3 text-[var(--muted)]">{match.source_quote || "No source quote"} {match.source_file ? `(${match.source_file}, page ${match.source_page})` : ""}</td>
                          <td className="py-3 pr-3">{match.recommended_action}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
                  {drafts.map((draft) => (
                    <div className="rounded-md border border-[var(--border)] bg-[#fbfcfb]" key={draft.id}>
                      <div className="flex flex-col gap-3 border-b border-[var(--border)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                        <StatusPill tone={statusTone(draft.status)}>{draft.status}</StatusPill>
                        <Button onClick={() => handleVerifyDraft(draft.id)} variant="secondary">
                          <ShieldCheck aria-hidden className="h-4 w-4" />
                          Verify citations
                        </Button>
                      </div>
                      <pre className="whitespace-pre-wrap px-4 py-4 text-sm leading-7">{draft.content_markdown}</pre>
                    </div>
                  ))}
                  {citationCheck ? (
                    <div className="rounded-md border border-[var(--border)] bg-white p-4 text-sm">
                      <StatusPill tone={statusTone(citationCheck.verification_status)}>{citationCheck.verification_status}</StatusPill>
                      <p className="mt-3 text-[var(--muted)]">Unsupported claims: {citationCheck.unsupported_claims.length}</p>
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
