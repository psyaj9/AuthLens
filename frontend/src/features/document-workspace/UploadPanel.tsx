import { FileText, Trash2, UploadCloud } from "lucide-react";
import type { ChangeEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";

import type { AsyncStatus, DocumentItem } from "./types";
import { fileCountLabel, formatFileSize } from "./workflow";

type UploadPanelProps = {
  documents: DocumentItem[];
  message?: string;
  onClear: () => void;
  onFileChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onUpload: () => void;
  status: AsyncStatus;
};

function uploadTone(status: AsyncStatus) {
  if (status === "loading") return "loading";
  if (status === "success") return "success";
  if (status === "error") return "error";
  return "idle";
}

export function UploadPanel({
  documents,
  message,
  onClear,
  onFileChange,
  onUpload,
  status
}: UploadPanelProps) {
  const hasDocuments = documents.length > 0;

  return (
    <Panel className="flex min-h-[520px] flex-col" labelledBy="documents-heading">
      <PanelHeader
        action={<StatusPill tone={uploadTone(status)}>Documents</StatusPill>}
        id="documents-heading"
        title="Documents"
      >
        Synthetic or de-identified PDFs only.
      </PanelHeader>

      <div className="flex flex-1 flex-col gap-5 p-5">
        <label
          className="flex min-h-40 cursor-pointer flex-col items-center justify-center gap-3 rounded-md border border-dashed border-[#aebbb1] bg-[#fbfdfb] px-4 py-6 text-center transition hover:border-[var(--accent)] hover:bg-[#f4faf8] focus-within:border-[var(--accent)]"
          htmlFor="pdf-upload"
        >
          <span className="flex h-11 w-11 items-center justify-center rounded-md bg-[#e8f4f2] text-[var(--accent)]">
            <UploadCloud aria-hidden className="h-5 w-5" />
          </span>
          <span className="text-sm font-semibold">Select PDF files</span>
          <span className="text-xs leading-5 text-[var(--muted)]">
            Multiple files supported
          </span>
          <input
            accept="application/pdf,.pdf"
            className="sr-only"
            id="pdf-upload"
            multiple
            onChange={onFileChange}
            type="file"
          />
        </label>

        {message ? (
          <p
            className="rounded-md border border-[#eed2a8] bg-[#fff8eb] px-3 py-2 text-sm text-[var(--warning)]"
            role={status === "error" ? "alert" : "status"}
          >
            {message}
          </p>
        ) : null}

        <div className="min-h-0 flex-1">
          {hasDocuments ? (
            <ul aria-label="Selected documents" className="divide-y divide-[var(--border)]">
              {documents.map((document) => (
                <li className="flex items-center gap-3 py-3" key={document.id}>
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-[#f0f4f1] text-[var(--muted)]">
                    <FileText aria-hidden className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {document.name}
                    </span>
                    <span className="block text-xs text-[var(--muted)]">
                      {formatFileSize(document.size)}
                    </span>
                  </span>
                  <StatusPill
                    tone={
                      document.status === "uploaded"
                        ? "success"
                        : document.status === "error"
                          ? "error"
                          : "idle"
                    }
                  >
                    {document.status}
                  </StatusPill>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex min-h-36 items-center justify-center rounded-md border border-[var(--border)] bg-[#fbfcfb] px-4 text-center text-sm text-[var(--muted)]">
              No PDFs selected.
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_auto]">
          <Button
            disabled={!hasDocuments}
            isLoading={status === "loading"}
            onClick={onUpload}
          >
            <UploadCloud aria-hidden className="h-4 w-4" />
            Upload {hasDocuments ? fileCountLabel(documents.length) : "PDFs"}
          </Button>
          <Button disabled={!hasDocuments || status === "loading"} onClick={onClear} variant="secondary">
            <Trash2 aria-hidden className="h-4 w-4" />
            Clear
          </Button>
        </div>
      </div>
    </Panel>
  );
}
