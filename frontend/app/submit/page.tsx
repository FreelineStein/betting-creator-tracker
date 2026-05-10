import type { Metadata } from "next";
import SubmitForm from "./SubmitForm";

export const metadata: Metadata = {
  title: "Submit a pick · PickReceipts",
  description:
    "Saw a creator post a betting pick on X? Drop the link here and we'll log it on the public record.",
};

// Cloudflare's always-pass test key. Override with NEXT_PUBLIC_TURNSTILE_SITE_KEY in production.
const TURNSTILE_TEST_SITE_KEY = "1x00000000000000000000AA";

export default function SubmitPage() {
  const siteKey =
    process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || TURNSTILE_TEST_SITE_KEY;

  return (
    <div className="max-w-xl">
      <div className="mb-10">
        <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-3">
          Submit a pick
        </div>
        <h1 className="font-display font-extrabold text-4xl sm:text-5xl tracking-display leading-[1.05] text-ink">
          Paste an <span className="text-amber-deep">X post</span> URL.
        </h1>
        <p className="text-ink-500 mt-4 text-[15px] leading-relaxed">
          We&apos;ll fetch the post, extract any picks, match them to scheduled games,
          and add them to the creator&apos;s record.
        </p>
      </div>

      <SubmitForm turnstileSiteKey={siteKey} />

      <div className="mt-10 border-t border-rule pt-6 text-xs text-ink-500 leading-relaxed">
        Submissions are anonymous and rate-limited. We never log who you are. Picks
        from creators we don&apos;t already track go through a quick review before they
        appear on the public list.
      </div>
    </div>
  );
}
