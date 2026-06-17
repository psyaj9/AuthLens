import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  isLoading?: boolean;
  variant?: ButtonVariant;
};

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--accent)] text-[var(--accent-foreground)] hover:bg-[#006866] focus-visible:outline-[var(--accent)]",
  secondary:
    "border border-[var(--border)] bg-white text-[var(--foreground)] hover:bg-[#f3f7f5] focus-visible:outline-[var(--accent)]",
  ghost:
    "text-[var(--foreground)] hover:bg-[#edf3f0] focus-visible:outline-[var(--accent)]",
  danger:
    "bg-[var(--danger)] text-white hover:bg-[#991b12] focus-visible:outline-[var(--danger)]"
};

export function Button({
  children,
  className,
  disabled,
  isLoading = false,
  type = "button",
  variant = "primary",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-2 focus-visible:outline-offset-2",
        variants[variant],
        className
      )}
      disabled={disabled || isLoading}
      type={type}
      {...props}
    >
      {isLoading ? <Loader2 aria-hidden className="h-4 w-4 animate-spin" /> : null}
      {children}
    </button>
  );
}
