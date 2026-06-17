import { MessageSquareText, Send, Sparkles } from "lucide-react";
import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";

import type { AsyncStatus } from "./types";

type QuestionWorkspaceProps = {
  answer: string;
  error?: string;
  onQuestionChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  question: string;
  status: AsyncStatus;
};

function queryTone(status: AsyncStatus) {
  if (status === "loading") return "loading";
  if (status === "success") return "success";
  if (status === "error") return "error";
  return "idle";
}

export function QuestionWorkspace({
  answer,
  error,
  onQuestionChange,
  onSubmit,
  question,
  status
}: QuestionWorkspaceProps) {
  return (
    <Panel
      aria-busy={status === "loading"}
      className="flex min-h-[520px] flex-col"
      labelledBy="workspace-heading"
    >
      <PanelHeader
        action={<StatusPill tone={queryTone(status)}>Answer</StatusPill>}
        id="workspace-heading"
        title="Workspace"
      >
        Ask against the uploaded document context.
      </PanelHeader>

      <div className="flex flex-1 flex-col gap-5 p-5">
        <form className="flex flex-col gap-3" onSubmit={onSubmit}>
          <label className="text-sm font-semibold" htmlFor="user-query">
            Question
          </label>
          <textarea
            className="min-h-32 resize-y rounded-md border border-[var(--border)] bg-white px-3 py-3 text-sm leading-6 outline-none transition placeholder:text-[#8a958e] focus:border-[var(--accent)] focus:ring-2 focus:ring-[rgba(0,122,120,0.16)]"
            id="user-query"
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder="What does the document say about eligibility?"
            value={question}
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-[var(--muted)]">
              Answers come from retrieved document chunks.
            </p>
            <Button
              className="sm:min-w-32"
              disabled={question.trim().length === 0}
              isLoading={status === "loading"}
              type="submit"
            >
              <Send aria-hidden className="h-4 w-4" />
              Ask
            </Button>
          </div>
        </form>

        {error ? (
          <p
            className="rounded-md border border-[#f0b8b3] bg-[#fff1f0] px-3 py-2 text-sm text-[var(--danger)]"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        <div
          aria-live="polite"
          className="flex min-h-0 flex-1 flex-col rounded-md border border-[var(--border)] bg-[#fbfcfb]"
          role="status"
        >
          <div className="flex items-center gap-2 border-b border-[var(--border)] px-4 py-3 text-sm font-semibold">
            <MessageSquareText aria-hidden className="h-4 w-4 text-[var(--accent)]" />
            Answer
          </div>
          <div className="flex flex-1 flex-col px-4 py-4">
            {answer ? (
              <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--foreground)]">
                {answer}
              </p>
            ) : (
              <div className="flex flex-1 items-center justify-center gap-2 text-center text-sm text-[var(--muted)]">
                <Sparkles aria-hidden className="h-4 w-4" />
                No answer yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </Panel>
  );
}
