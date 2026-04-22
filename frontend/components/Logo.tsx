import Image from "next/image";
import Link from "next/link";

type LogoProps = {
  /** Pixel height of the icon mark (and reference size for wordmark scaling). */
  height?: number;
  /** Render the receipt icon mark. */
  icon?: boolean;
  /** Render the PICKRECEIPTS wordmark. */
  wordmark?: boolean;
  /** Wrap in a Link to /. */
  linked?: boolean;
  className?: string;
};

export function Logo({
  height = 56,
  icon = true,
  wordmark = true,
  linked = true,
  className = "",
}: LogoProps) {
  const mark = (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      {icon && (
        <Image
          src="/brand-mark.png"
          alt="PickReceipts"
          width={height}
          height={height}
          priority
          className="block"
        />
      )}
      {wordmark && (
        <span
          className="font-display font-black tracking-display leading-none text-white select-none"
          style={{ fontSize: Math.round(height * 0.62) }}
        >
          PICK<span className="text-signal">RECEIPTS</span>
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
