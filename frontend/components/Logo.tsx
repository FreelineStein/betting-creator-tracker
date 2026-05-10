import Link from "next/link";

type LogoProps = {
  /** Pixel height of the icon mark (and reference size for wordmark scaling). */
  height?: number;
  /** Render the PR icon mark. */
  icon?: boolean;
  /** Render the PickReceipts wordmark. */
  wordmark?: boolean;
  /** Wrap in a Link to /. */
  linked?: boolean;
  className?: string;
};

export function Logo({
  height = 40,
  icon = true,
  wordmark = true,
  linked = true,
  className = "",
}: LogoProps) {
  const iconSize = height;
  const wordSize = Math.round(height * 0.6);
  const markFontSize = Math.round(iconSize * 0.5);

  const mark = (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      {icon && (
        <span
          aria-hidden="true"
          className="relative inline-flex items-center justify-center overflow-hidden rounded-[10px] bg-ink text-amber"
          style={{ width: iconSize, height: iconSize }}
        >
          <span
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at 25% 30%, rgba(255,179,71,0.32), transparent 55%)",
            }}
          />
          <span
            className="relative font-display font-extrabold leading-none"
            style={{ fontSize: markFontSize, letterSpacing: "-0.04em" }}
          >
            PR
          </span>
        </span>
      )}
      {wordmark && (
        <span
          className="font-display font-extrabold tracking-display leading-none text-ink select-none"
          style={{ fontSize: wordSize }}
        >
          Pick<span className="text-amber-deep">Receipts</span>
        </span>
      )}
    </span>
  );

  if (!linked) return mark;
  return (
    <Link href="/" aria-label="PickReceipts home" className="inline-flex items-center">
      {mark}
    </Link>
  );
}
