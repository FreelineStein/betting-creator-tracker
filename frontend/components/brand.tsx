/**
 * Brand primitives — PickReceipts Stadium Card direction.
 *
 * No red/green anywhere — wins are amber, losses are stone/ink, pushes/pending
 * are neutral. Status pills are lowercase intentionally; the color carries weight.
 */
import type { ReactNode } from "react";

// -------------------------------------------------------------------------
// Badge — status pills
// -------------------------------------------------------------------------

export type BadgeVariant =
  | "win"
  | "loss"
  | "push"
  | "pending"
  | "streak-win"
  | "streak-loss";

const BADGE_STYLES: Record<BadgeVariant, string> = {
  win: "bg-amber-dim text-amber-deep border border-amber-deep/30",
  loss: "bg-stone-dim text-ink-500 border border-transparent",
  push: "bg-paper-2 text-ink-500 border border-rule",
  pending: "bg-transparent text-ink-500 border border-dashed border-rule",
  "streak-win": "bg-amber-dim text-amber-deep border border-amber/40",
  "streak-loss": "bg-stone-dim text-ink-700 border border-stone/30",
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
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold tracking-label ${BADGE_STYLES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

// -------------------------------------------------------------------------
// WLRecord — "<W>–<L>" in display weight, both sides ink (no green/red).
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
  const sizeClass = { sm: "text-sm", md: "text-base", lg: "text-3xl" }[size];
  return (
    <span
      className={`font-display font-extrabold tabular tracking-tight ${sizeClass} ${className}`}
    >
      <span className="text-ink">{w}</span>
      <span className="text-ink-500 mx-0.5">–</span>
      <span className="text-ink">{l}</span>
    </span>
  );
}

// -------------------------------------------------------------------------
// StatCard — big paper-2 tile, ink number, amber-deep when positive.
// `win`/`positive` both map to amber-deep; `loss`/`default` stay ink.
// -------------------------------------------------------------------------

export type StatTone = "default" | "positive" | "win" | "loss";

const STAT_TONE: Record<StatTone, string> = {
  default: "text-ink",
  positive: "text-amber-deep",
  win: "text-amber-deep",
  loss: "text-ink",
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
      className={`rounded-[14px] border border-rule bg-paper-2 p-5 shadow-card ${className}`}
    >
      <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500">
        {label}
      </div>
      <div
        className={`mt-2 font-display text-4xl font-extrabold tabular tracking-tight leading-none ${STAT_TONE[tone]}`}
      >
        {value}
      </div>
      {sub && <div className="mt-1.5 text-xs text-ink-500">{sub}</div>}
    </div>
  );
}

// -------------------------------------------------------------------------
// StatTile — compact card-internal stat (used inside the creator card body)
// -------------------------------------------------------------------------

export function StatTile({
  label,
  value,
  tone = "default",
  className = "",
}: {
  label: string;
  value: ReactNode;
  tone?: StatTone;
  className?: string;
}) {
  return (
    <div
      className={`rounded-[10px] border border-rule bg-paper-3 px-3 py-2.5 text-center ${className}`}
    >
      <div className="font-mono text-[9px] uppercase tracking-label-x font-medium text-ink-500">
        {label}
      </div>
      <div
        className={`mt-1 font-display text-[22px] font-extrabold tabular tracking-tight leading-none ${STAT_TONE[tone]}`}
      >
        {value}
      </div>
    </div>
  );
}

// -------------------------------------------------------------------------
// Button — primary (ink fill), accent (amber fill), secondary (paper outlined),
// outline (ink outlined), danger (amber-deep outlined), ghost (transparent).
// -------------------------------------------------------------------------

export type ButtonVariant =
  | "primary"
  | "accent"
  | "secondary"
  | "outline"
  | "danger"
  | "ghost";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-ink text-paper border border-ink hover:bg-ink-700",
  accent: "bg-amber text-ink border border-amber hover:bg-amber-deep hover:text-paper",
  secondary: "bg-paper-2 text-ink border border-rule hover:border-ink-500",
  outline: "bg-transparent text-ink border border-ink hover:bg-paper-3",
  danger:
    "bg-transparent text-amber-deep border border-amber-deep/60 hover:bg-amber-dim",
  ghost: "bg-transparent text-ink-700 border border-transparent hover:bg-paper-3",
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
      className={`inline-flex items-center justify-center gap-2 rounded-[10px] px-[18px] py-[11px] font-sans text-sm font-semibold tracking-tight transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
