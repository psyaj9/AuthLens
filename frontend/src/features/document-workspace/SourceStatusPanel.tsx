import { Activity, Database, Server } from "lucide-react";

import { Panel, PanelHeader } from "@/components/ui/panel";
import { StatusPill } from "@/components/ui/status-pill";

import type { AsyncStatus, HealthStatus } from "./types";

type SourceStatusPanelProps = {
  health: HealthStatus | null;
  queryStatus: AsyncStatus;
  sources: string[];
  uploadStatus: AsyncStatus;
};

function healthTone(health: HealthStatus | null) {
  if (!health) return "loading";
  if (health.ok) return "success";
  return health.backendConfigured ? "warning" : "error";
}

function healthLabel(health: HealthStatus | null) {
  if (!health) return "Checking";
  if (health.ok) return "Connected";
  if (!health.backendConfigured) return "Needs env";
  return "Unavailable";
}

export function SourceStatusPanel({
  health,
  queryStatus,
  sources,
  uploadStatus
}: SourceStatusPanelProps) {
  return (
    <Panel className="flex min-h-[520px] flex-col" labelledBy="sources-heading">
      <PanelHeader
        action={<StatusPill tone={healthTone(health)}>{healthLabel(health)}</StatusPill>}
        id="sources-heading"
        title="Sources & status"
      />

      <div className="flex flex-1 flex-col gap-5 p-5">
        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Server aria-hidden className="h-4 w-4 text-[var(--accent)]" />
            Backend
          </h3>
          <dl className="divide-y divide-[var(--border)] rounded-md border border-[var(--border)] bg-[#fbfcfb]">
            <div className="grid grid-cols-[1fr_auto] gap-3 px-3 py-2.5 text-sm">
              <dt className="text-[var(--muted)]">Configuration</dt>
              <dd className="font-medium">
                {health?.backendConfigured ? "Set" : "Missing"}
              </dd>
            </div>
            <div className="grid grid-cols-[1fr_auto] gap-3 px-3 py-2.5 text-sm">
              <dt className="text-[var(--muted)]">Reachability</dt>
              <dd className="font-medium">
                {health?.backendReachable ? "Reachable" : "Not ready"}
              </dd>
            </div>
          </dl>
          {health?.error ? (
            <p className="mt-3 text-xs leading-5 text-[var(--warning)]">{health.error}</p>
          ) : null}
        </div>

        <div>
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Activity aria-hidden className="h-4 w-4 text-[var(--accent)]" />
            Workflow
          </h3>
          <div className="grid grid-cols-2 gap-2">
            <StatusPill
              tone={
                uploadStatus === "success"
                  ? "success"
                  : uploadStatus === "error"
                    ? "error"
                    : uploadStatus === "loading"
                      ? "loading"
                      : "idle"
              }
            >
              Upload
            </StatusPill>
            <StatusPill
              tone={
                queryStatus === "success"
                  ? "success"
                  : queryStatus === "error"
                    ? "error"
                    : queryStatus === "loading"
                      ? "loading"
                      : "idle"
              }
            >
              Query
            </StatusPill>
          </div>
        </div>

        <div className="min-h-0 flex-1">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
            <Database aria-hidden className="h-4 w-4 text-[var(--accent)]" />
            Retrieved sources
          </h3>
          {sources.length > 0 ? (
            <ol className="divide-y divide-[var(--border)] rounded-md border border-[var(--border)] bg-[#fbfcfb]">
              {sources.map((source, index) => (
                <li className="px-3 py-3 text-sm leading-6" key={`${source}-${index}`}>
                  <span className="mb-1 block text-xs font-semibold text-[var(--muted)]">
                    Source {index + 1}
                  </span>
                  {source}
                </li>
              ))}
            </ol>
          ) : (
            <div className="flex min-h-36 items-center justify-center rounded-md border border-[var(--border)] bg-[#fbfcfb] px-4 text-center text-sm text-[var(--muted)]">
              Sources will appear after an answer.
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
