import Link from "next/link";

type LogoProps = {
  /** Font size in px of the wordmark. */
  size?: number;
  /** Wrap in a Link to /. */
  linked?: boolean;
  className?: string;
};

/**
 * Masthead wordmark. "PICK" in ink, "RECEIPTS" reversed in the press-red
 * section tab, the way a sports section tabs its name on the front.
 */
export function Logo({ size = 30, linked = true, className = "" }: LogoProps) {
  const mark = (
    <span
      className={`inline-flex items-baseline font-display font-bold uppercase leading-none tracking-[-0.01em] text-ink ${className}`}
      style={{ fontSize: size }}
    >
      <span>Pick</span>
      <span
        className="ml-[0.18em] bg-press text-news"
        style={{ padding: "0.14em 0.22em 0.06em" }}
      >
        Receipts
      </span>
    </span>
  );

  if (!linked) return mark;
  return (
    <Link href="/" aria-label="PickReceipts home" className="inline-flex">
      {mark}
    </Link>
  );
}
