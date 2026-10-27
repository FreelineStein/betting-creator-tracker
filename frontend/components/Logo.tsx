import Image from "next/image";
import Link from "next/link";

type LogoProps = {
  /** Rendered height in px; width follows the artwork's aspect. */
  height?: number;
  /** Wrap in a Link to /. */
  linked?: boolean;
  className?: string;
};

// public/logo.png is the receipt mark + stacked PICK/RECEIPTS wordmark, cut
// out of its black ground so it sits on any dark surface.
const LOGO_W = 803;
const LOGO_H = 267;

export function Logo({ height = 44, linked = true, className = "" }: LogoProps) {
  const mark = (
    <Image
      src="/logo.png"
      alt="PickReceipts"
      width={LOGO_W}
      height={LOGO_H}
      priority
      className={className}
      style={{ height, width: "auto" }}
    />
  );

  if (!linked) return mark;
  return (
    <Link href="/" aria-label="PickReceipts home" className="inline-flex">
      {mark}
    </Link>
  );
}
