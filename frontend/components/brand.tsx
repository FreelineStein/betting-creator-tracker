/**
 * Brand primitives — PickReceipts dark app shell.
 *
 * Results are lettered chips: W on lime, L on orange, P neutral. The letter
 * always rides with the color, so a result never depends on color alone.
 */
import Link from "next/link";
import type { ReactNode } from "react";
import { BREAK_EVEN_PCT } from "../app/lib/picks";

// -------------------------------------------------------------------------
// SectionHead — condensed caps heading with an optional count or caption.
// -------------------------------------------------------------------------

export function SectionHead({
  children,
  count,
  right,
  className = "",
  id,
}: {
  children: ReactNode;
  count?: number;
  right?: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <div className={`mb-3.5 flex items-baseline justify-between gap-3 ${className}`}>
      <h2 id={id} className="font-display text-[22px] font-bold uppercase leading-none tracking-[0.02em] text-fg">
        {children}
        {count !== undefined && (
          <span className="ml-2 align-[2px] font-sans text-[14px] font-medium tracking-normal text-fg-3">
            {count}
          </span>
        )}
      </h2>
      {right && <span className="text-[13px] text-fg-3">{right}</span>}
    </div>
  );
}

// -------------------------------------------------------------------------
// Panel — the one container: rounded, hairline border, no shadow.
// -------------------------------------------------------------------------

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-card border border-line bg-panel ${className}`}>{children}</div>;
}

// -------------------------------------------------------------------------
// ResultChip — W / L / P on a tinted chip. Pending gets an outlined pill.
// -------------------------------------------------------------------------

const CHIP_TONE: Record<string, string> = {
  won: "bg-win-dim text-win",
  lost: "bg-loss-dim text-loss",
  push: "bg-panel-3 text-fg-3",
};

export function ResultChip({
  status,
  size = 26,
  className = "",
}: {
  status: string;
  size?: number;
  className?: string;
}) {
  if (status === "won" || status === "lost" || status === "push") {
    const letter = status === "won" ? "W" : status === "lost" ? "L" : "P";
    const word = status === "won" ? "Won" : status === "lost" ? "Lost" : "Push";
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-chip font-display font-bold leading-none ${CHIP_TONE[status]} ${className}`}
        style={{ width: size, height: size, fontSize: Math.round(size * 0.54) }}
        title={word}
      >
        <span aria-hidden="true">{letter}</span>
        <span className="sr-only">{word}</span>
      </span>
    );
  }
  if (status === "void") {
    return <span className={`text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-3 ${className}`}>Void</span>;
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-line-2 px-2 py-[3px] text-[11.5px] font-semibold uppercase tracking-[0.06em] text-fg-2 ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-win" aria-hidden="true" />
      Pending
    </span>
  );
}

// -------------------------------------------------------------------------
// FormChips — last N results as chips, oldest to newest left to right.
// -------------------------------------------------------------------------

export function FormChips({
  results,
  slots = 5,
  size = 26,
  className = "",
}: {
  results: ("won" | "lost" | "push")[];
  slots?: number;
  size?: number;
  className?: string;
}) {
  const shown = results.slice(-slots);
  const label = shown.length
    ? `Last ${shown.length}, oldest first: ${shown.map((r) => (r === "won" ? "W" : r === "lost" ? "L" : "P")).join(" ")}`
    : "No settled picks yet";
  return (
    <span role="img" aria-label={label} className={`flex gap-1 ${className}`}>
      {Array.from({ length: slots - shown.length }).map((_, i) => (
        <span
          key={`e${i}`}
          className="shrink-0 rounded-chip border border-dashed border-line"
          style={{ width: size, height: size }}
        />
      ))}
      {shown.map((r, i) => (
        <ResultChip key={i} status={r} size={size} />
      ))}
    </span>
  );
}

// -------------------------------------------------------------------------
// Stat — small caps label over a condensed figure.
// -------------------------------------------------------------------------

export function Stat({
  label,
  children,
  tone = "default",
  size = "md",
  className = "",
}: {
  label: string;
  children: ReactNode;
  tone?: "default" | "win" | "loss" | "muted";
  size?: "md" | "lg";
  className?: string;
}) {
  const toneClass =
    tone === "win" ? "text-win" : tone === "loss" ? "text-loss" : tone === "muted" ? "text-fg-3" : "text-fg";
  return (
    <div className={className}>
      <div className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-fg-3">{label}</div>
      <div
        className={`tabular font-display font-bold leading-[1.1] ${toneClass} ${
          size === "lg" ? "text-[30px] sm:text-[38px]" : "text-[24px]"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

export function pctTone(value: number | null): "win" | "default" | "muted" {
  if (value === null) return "muted";
  return value >= BREAK_EVEN_PCT ? "win" : "default";
}

export function roiTone(value: number | null): "win" | "loss" | "muted" | "default" {
  if (value === null) return "muted";
  return value > 0 ? "win" : value < 0 ? "loss" : "default";
}

export function pctText(value: number | null): string {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

// -------------------------------------------------------------------------
// Buttons and button links.
// -------------------------------------------------------------------------

export type ButtonVariant = "primary" | "secondary";

const BTN_BASE =
  "inline-flex items-center justify-center gap-2 rounded-control px-[18px] py-[10px] text-[15px] font-bold leading-tight transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40";

const BTN_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-win text-black hover:bg-[#bdfa7e]",
  secondary: "border border-line-2 bg-panel text-fg hover:border-fg-3 hover:bg-panel-2",
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({ variant = "primary", className = "", children, ...rest }: ButtonProps) {
  return (
    <button className={`${BTN_BASE} ${BTN_STYLES[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function ButtonLink({
  href,
  variant = "secondary",
  className = "",
  children,
  onClick,
}: {
  href: string;
  variant?: ButtonVariant;
  className?: string;
  children: ReactNode;
  onClick?: () => void;
}) {
  return (
    <Link href={href} onClick={onClick} className={`${BTN_BASE} ${BTN_STYLES[variant]} ${className}`}>
      {children}
    </Link>
  );
}

// -------------------------------------------------------------------------
// Avatar — profile image or initials on a panel disc.
// -------------------------------------------------------------------------

export function Avatar({ src, name, size = 48 }: { src: string | null | undefined; name: string; size?: number }) {
  const initials = name
    .replace(/[^A-Za-z0-9 ]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  return (
    <span
      className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-line bg-panel-2 font-display font-bold text-fg-3"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.36) }}
      aria-hidden="true"
    >
      {initials}
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="" className="absolute inset-0 h-full w-full object-cover" loading="lazy" />
      )}
    </span>
  );
}

// -------------------------------------------------------------------------
// Lede — the one-line deck under a headline.
// -------------------------------------------------------------------------

export function Lede({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <p className={`max-w-[58ch] text-[17px] leading-[1.5] text-fg-2 ${className}`}>{children}</p>;
}
