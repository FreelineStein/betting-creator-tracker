/**
 * Brand primitives — see brand guide v1.0 (PickReceipts).
 *
 * Every component here maps to a section of the guide. Keep it that way:
 * if the guide changes, this is the single file to update.
 */
import type { ReactNode } from "react";

// -------------------------------------------------------------------------
// Badge — section 05, Status Badges
// -------------------------------------------------------------------------

export type BadgeVariant = "win" | "loss" | "push" | "streak-win" | "streak-loss";

const BADGE_STYLES: Record<BadgeVariant, string> = {
  win: "bg-signal-dim text-forest",
  loss: "bg-alert-dim text-alert-deep",
  push: "bg-ink-100/10 text-ink-400",
  "streak-win": "bg-signal/20 text-signal border border-signal/40",
  "streak-loss": "bg-alert/15 text-alert border border-alert/30",
};

export function Badge({
  variant,
  children,
  className = "",
}: {
  variant: BadgeVariant;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-label ${BADGE_STYLES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

// -------------------------------------------------------------------------
// WLRecord — section 05, "<W>–<L>" formatted with mono, signal W, alert L
// (Named WLRecord to avoid shadowing TypeScript's built-in Record<K, V>.)
// -------------------------------------------------------------------------

export function WLRecord({
  w,
  l,
  size = "md",
  className = "",
}: {
  w: number;
  l: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizeClass = { sm: "text-sm", md: "text-base", lg: "text-2xl" }[size];
  return (
    <span className={`font-mono tabular font-bold ${sizeClass} ${className}`}>
      <span className="text-signal">{w}</span>
      <span className="text-ink-400 mx-0.5">–</span>
      <span className="text-alert">{l}</span>
    </span>
  );
}

// -------------------------------------------------------------------------
// StatCard — section 05, Dashboard Stat Cards (dark surface variant)
// -------------------------------------------------------------------------

export type StatTone = "default" | "win" | "loss";

const STAT_TONE: Record<StatTone, string> = {
  default: "text-white",
  win: "text-signal",
  loss: "text-alert",
};

export function StatCard({
  label,
  value,
  sub,
  tone = "default",
  className = "",
}: {
  label: string;
  value: ReactNode;
  sub?: string;
  tone?: StatTone;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-ink-800 bg-ink-800/30 p-6 ${className}`}
    >
      <div className="font-mono text-[10px] uppercase tracking-label text-ink-400">
        {label}
      </div>
      <div
        className={`mt-2 font-display text-4xl font-black tabular tracking-display ${STAT_TONE[tone]}`}
      >
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-ink-400">{sub}</div>}
    </div>
  );
}

// -------------------------------------------------------------------------
// Button — section 05, Buttons
// -------------------------------------------------------------------------

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "danger"
  | "ghost";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-signal text-pitch hover:bg-signal/90",
  secondary:
    "bg-transparent text-white border border-ink-400 hover:border-white",
  outline:
    "bg-transparent text-signal border border-signal hover:bg-signal/10",
  danger:
    "bg-transparent text-alert border border-alert hover:bg-alert/10",
  ghost: "bg-ink-800/60 text-white hover:bg-ink-800",
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({
  variant = "primary",
  className = "",
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-bold uppercase tracking-label transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
