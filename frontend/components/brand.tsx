/**
 * Brand primitives — PickReceipts, The Agate Page.
 *
 * Results are letters in squares: W filled, L hollow, P hollow and dashed.
 * Color never carries win/loss. Controls are boxed like classifieds.
 */
import Link from "next/link";
import type { ReactNode } from "react";
import { BREAK_EVEN_PCT } from "../app/lib/picks";

// -------------------------------------------------------------------------
// SectionBar — reversed black bar heading a table or block.
// -------------------------------------------------------------------------

export function SectionBar({
  children,
  right,
  onDeck = false,
  className = "",
}: {
  children: ReactNode;
  right?: ReactNode;
  onDeck?: boolean;
  className?: string;
}) {
  return (
    <div className={`bar ${className}`}>
      <span className={onDeck ? "on-deck" : undefined}>{children}</span>
      {right && <small>{right}</small>}
    </div>
  );
}

// -------------------------------------------------------------------------
// ResultMark — W / L / P in a square. Pending renders as the red marker.
// -------------------------------------------------------------------------

export function ResultMark({
  status,
  size = 18,
  className = "",
}: {
  status: string;
  size?: number;
  className?: string;
}) {
  const style = { width: size, height: size, fontSize: Math.round(size * 0.64) };
  // Hollow marks carry the same scan weight as the filled W: 2px at 16px and up.
  const stroke = size >= 16 ? "border-2" : "border-[1.5px]";
  if (status === "won") {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center bg-ink font-display font-bold leading-none text-news ${className}`}
        style={style}
        title="Won"
      >
        W<span className="sr-only">on</span>
      </span>
    );
  }
  if (status === "lost") {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center ${stroke} border-ink font-display font-bold leading-none text-ink ${className}`}
        style={style}
        title="Lost"
      >
        L<span className="sr-only">ost</span>
      </span>
    );
  }
  if (status === "push") {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center ${stroke} border-dashed border-ink-3 font-display font-bold leading-none text-ink-3 ${className}`}
        style={style}
        title="Push"
      >
        P<span className="sr-only">ush</span>
      </span>
    );
  }
  if (status === "void") {
    return (
      <span className={`text-[12px] uppercase tracking-[0.06em] text-ink-3 ${className}`}>
        Void
      </span>
    );
  }
  return (
    <span
      className={`on-deck whitespace-nowrap text-[12px] font-semibold uppercase tracking-[0.06em] text-ink ${className}`}
    >
      Pending
    </span>
  );
}

// -------------------------------------------------------------------------
// FormStrip — last five results as squares, newest on the right.
// -------------------------------------------------------------------------

export function FormStrip({
  results,
  size = 10,
  gap = 3,
  className = "",
}: {
  results: ("won" | "lost" | "push")[];
  size?: number;
  gap?: number;
  className?: string;
}) {
  const slots = 5;
  const padded: (("won" | "lost" | "push") | null)[] = [
    ...Array<null>(Math.max(0, slots - results.length)).fill(null),
    ...results.slice(-slots),
  ];
  const width = slots * size + (slots - 1) * gap;
  const label = results.length
    ? `Last five, oldest first: ${results
        .slice(-slots)
        .map((r) => (r === "won" ? "W" : r === "lost" ? "L" : "P"))
        .join(" ")}`
    : "No settled picks yet";
  return (
    <svg
      width={width}
      height={size}
      viewBox={`0 0 ${width} ${size}`}
      role="img"
      aria-label={label}
      className={className}
    >
      {padded.map((r, i) => {
        const x = i * (size + gap);
        if (r === "won") {
          return <rect key={i} x={x} y={0} width={size} height={size} fill="currentColor" />;
        }
        if (r === "lost") {
          return (
            <rect
              key={i}
              x={x + 1}
              y={1}
              width={size - 2}
              height={size - 2}
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            />
          );
        }
        if (r === "push") {
          return (
            <rect
              key={i}
              x={x + 0.75}
              y={0.75}
              width={size - 1.5}
              height={size - 1.5}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeDasharray="2 1.5"
              opacity={0.6}
            />
          );
        }
        return (
          <rect
            key={i}
            x={x + 0.5}
            y={0.5}
            width={size - 1}
            height={size - 1}
            fill="none"
            stroke="currentColor"
            strokeWidth={1}
            opacity={0.25}
          />
        );
      })}
    </svg>
  );
}

// -------------------------------------------------------------------------
// Pct — win percentage; bold when it clears the −110 break-even.
// -------------------------------------------------------------------------

export function Pct({ value, className = "" }: { value: number | null; className?: string }) {
  if (value === null) return <span className={`text-ink-3 ${className}`}>—</span>;
  const clears = value >= BREAK_EVEN_PCT;
  return (
    <span
      className={`${clears ? "font-bold" : "font-normal text-ink-2"} ${className}`}
      title={clears ? "Clears the −110 break-even (52.4%)" : "Below the −110 break-even (52.4%)"}
    >
      {value.toFixed(1)}
    </span>
  );
}

// -------------------------------------------------------------------------
// Buttons and boxed links — classified-ad boxes.
// -------------------------------------------------------------------------

export type ButtonVariant = "primary" | "secondary";

const BOX_BASE =
  "inline-flex items-center justify-center gap-2 border-2 border-ink px-4 py-[9px] font-display text-[14px] font-medium uppercase leading-none tracking-[0.07em] transition-colors duration-120 disabled:cursor-not-allowed disabled:opacity-40";

const BOX_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-ink text-news hover:bg-ink-2 hover:border-ink-2",
  secondary: "bg-transparent text-ink hover:bg-ink hover:text-news",
};

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
};

export function Button({ variant = "primary", className = "", children, ...rest }: ButtonProps) {
  return (
    <button className={`${BOX_BASE} ${BOX_STYLES[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}

export function BoxedLink({
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
    <Link href={href} onClick={onClick} className={`${BOX_BASE} ${BOX_STYLES[variant]} ${className}`}>
      {children}
    </Link>
  );
}

// -------------------------------------------------------------------------
// Standfirst — the one-line deck under a headline.
// -------------------------------------------------------------------------

export function Standfirst({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p className={`max-w-[62ch] text-[17px] leading-[1.45] text-ink-2 ${className}`}>{children}</p>
  );
}
