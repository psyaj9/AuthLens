"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";
import { ShieldAlert } from "lucide-react";

import { askQuestion, uploadDocuments } from "@/lib/api/client";

import { QuestionWorkspace } from "./QuestionWorkspace";
import { SourceStatusPanel } from "./SourceStatusPanel";
import { UploadPanel } from "./UploadPanel";
import type { AsyncStatus, DocumentItem, HealthStatus } from "./types";
import { createDocumentItems, fileCountLabel, isSupportedPdf } from "./workflow";

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function DocumentWorkspace() {
  const [answer, setAnswer] = useState("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [question, setQuestion] = useState("");
  const [queryError, setQueryError] = useState<string>();
  const [queryStatus, setQueryStatus] = useState<AsyncStatus>("idle");
  const [sources, setSources] = useState<string[]>([]);
  const [uploadMessage, setUploadMessage] = useState<string>();
  const [uploadStatus, setUploadStatus] = useState<AsyncStatus>("idle");

  useEffect(() => {
    let active = true;

    fetch("/api/health", { cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as HealthStatus;
        if (active) {
          setHealth(payload);
        }
      })
      .catch(() => {
        if (active) {
          setHealth({
            ok: false,
            backendConfigured: false,
            backendReachable: false,
            error: "Health check failed."
          });
        }
      });

    return () => {
      active = false;
    };
  }, []);

  const visibleUploadMessage = useMemo(() => {
    if (uploadMessage) {
      return uploadMessage;
    }

    if (files.length > 0 && uploadStatus === "idle") {
      return `${fileCountLabel(files.length)} ready.`;
    }

    return undefined;
  }, [files.length, uploadMessage, uploadStatus]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? []);
    const supportedFiles = selectedFiles.filter(isSupportedPdf);

    setAnswer("");
    setQueryError(undefined);
    setSources([]);
    setUploadStatus("idle");

    if (supportedFiles.length === 0) {
      setFiles([]);
      setDocuments([]);
      setUploadMessage(
        selectedFiles.length > 0 ? "Select PDF files only." : undefined
      );
      return;
    }

    setFiles(supportedFiles);
    setDocuments(createDocumentItems(supportedFiles, "queued"));
    setUploadMessage(
      supportedFiles.length === selectedFiles.length
        ? undefined
        : "Unsupported files were skipped."
    );
    event.target.value = "";
  }

  async function handleUpload() {
    if (files.length === 0) {
      setUploadMessage("Select at least one PDF before uploading.");
      setUploadStatus("error");
      return;
    }

    setUploadMessage(undefined);
    setUploadStatus("loading");

    try {
      await uploadDocuments(files);
      setDocuments(createDocumentItems(files, "uploaded"));
      setUploadStatus("success");
      setUploadMessage(`${fileCountLabel(files.length)} uploaded.`);
    } catch (error) {
      setDocuments(createDocumentItems(files, "error"));
      setUploadStatus("error");
      setUploadMessage(errorMessage(error, "Document upload failed."));
    }
  }

  async function handleQuestionSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (trimmedQuestion.length === 0) {
      setQueryStatus("error");
      setQueryError("Enter a question before asking AuthLens.");
      return;
    }

    setQueryError(undefined);
    setQueryStatus("loading");

    try {
      const result = await askQuestion(trimmedQuestion);
      setAnswer(result.response);
      setSources(result.source_documents);
      setQueryStatus("success");
    } catch (error) {
      setAnswer("");
      setSources([]);
      setQueryStatus("error");
      setQueryError(errorMessage(error, "Question request failed."));
    }
  }

  function clearDocuments() {
    setDocuments([]);
    setFiles([]);
    setUploadMessage(undefined);
    setUploadStatus("idle");
  }

  return (
    <main className="min-h-screen px-4 py-4 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-[1440px] flex-col gap-4">
        <header className="flex flex-col gap-3 rounded-md border border-[var(--border)] bg-white px-4 py-4 shadow-[0_1px_2px_rgba(24,33,28,0.05)] sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-[#e8f4f2] text-[var(--accent)]">
              <ShieldAlert aria-hidden className="h-5 w-5" />
            </span>
            <div>
              <h1 className="text-lg font-semibold leading-6">AuthLens</h1>
              <p className="text-sm text-[var(--muted)]">Document QA workspace</p>
            </div>
          </div>
          <p className="rounded-md border border-[#eed2a8] bg-[#fff8eb] px-3 py-2 text-sm font-medium text-[var(--warning)]">
            Synthetic or de-identified PDFs only.
          </p>
        </header>

        <div className="grid min-h-[calc(100vh-128px)] grid-cols-1 gap-4 lg:grid-cols-[320px_minmax(0,1fr)_320px]">
          <UploadPanel
            documents={documents}
            message={visibleUploadMessage}
            onClear={clearDocuments}
            onFileChange={handleFileChange}
            onUpload={handleUpload}
            status={uploadStatus}
          />
          <QuestionWorkspace
            answer={answer}
            error={queryError}
            onQuestionChange={setQuestion}
            onSubmit={handleQuestionSubmit}
            question={question}
            status={queryStatus}
          />
          <SourceStatusPanel
            health={health}
            queryStatus={queryStatus}
            sources={sources}
            uploadStatus={uploadStatus}
          />
        </div>
      </div>
    </main>
  );
}
