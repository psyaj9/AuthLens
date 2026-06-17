import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type PanelProps = {
  children: ReactNode;
  className?: string;
  labelledBy?: string;
};

export function Panel({ children, className, labelledBy }: PanelProps) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={cn(
        "min-h-0 rounded-md border border-[var(--border)] bg-[var(--panel)] shadow-[0_1px_2px_rgba(24,33,28,0.05)]",
        className
      )}
    >
      {children}
    </section>
  );
}

type PanelHeaderProps = {
  action?: ReactNode;
  children?: ReactNode;
  eyebrow?: string;
  id: string;
  title: string;
};

export function PanelHeader({
  action,
  children,
  eyebrow,
  id,
  title
}: PanelHeaderProps) {
  return (
    <div className="border-b border-[var(--border)] px-5 py-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          {eyebrow ? (
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-[var(--muted)]">
              {eyebrow}
            </p>
          ) : null}
          <h2 className="text-base font-semibold leading-6" id={id}>
            {title}
          </h2>
        </div>
        {action}
      </div>
      {children ? <div className="mt-2 text-sm text-[var(--muted)]">{children}</div> : null}
    </div>
  );
}
