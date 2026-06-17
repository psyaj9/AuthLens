import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleDashed, Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type StatusTone = "idle" | "loading" | "success" | "warning" | "error";

type StatusPillProps = {
  children: ReactNode;
  tone?: StatusTone;
};

const toneClasses: Record<StatusTone, string> = {
  idle: "border-[var(--border)] bg-[#f7faf8] text-[var(--muted)]",
  loading: "border-[#b9d8d7] bg-[#eff8f7] text-[var(--accent)]",
  success: "border-[#bfe3ce] bg-[#f0faf4] text-[var(--success)]",
  warning: "border-[#eed2a8] bg-[#fff8eb] text-[var(--warning)]",
  error: "border-[#f0b8b3] bg-[#fff1f0] text-[var(--danger)]"
};

function Icon({ tone }: { tone: StatusTone }) {
  if (tone === "loading") {
    return <Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />;
  }

  if (tone === "success") {
    return <CheckCircle2 aria-hidden className="h-3.5 w-3.5" />;
  }

  if (tone === "warning" || tone === "error") {
    return <AlertTriangle aria-hidden className="h-3.5 w-3.5" />;
  }

  return <CircleDashed aria-hidden className="h-3.5 w-3.5" />;
}

export function StatusPill({ children, tone = "idle" }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold",
        toneClasses[tone]
      )}
    >
      <Icon tone={tone} />
      {children}
    </span>
  );
}
