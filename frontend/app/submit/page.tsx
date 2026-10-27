import type { Metadata } from "next";
import SubmitForm from "./SubmitForm";
import { Standfirst } from "../../components/brand";

export const metadata: Metadata = {
  title: "Submit a pick · PickReceipts",
  description:
    "Saw a creator post a betting pick on X? Drop the link here and we'll log it on the public record.",
};

// Cloudflare's always-pass test key. Override with NEXT_PUBLIC_TURNSTILE_SITE_KEY in production.
const TURNSTILE_TEST_SITE_KEY = "1x00000000000000000000AA";

export default function SubmitPage() {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || TURNSTILE_TEST_SITE_KEY;

  return (
    <div className="max-w-2xl">
      <h1 className="font-display text-[clamp(40px,7vw,80px)] font-bold uppercase leading-[0.9] tracking-[-0.015em] text-ink text-balance">
        Saw a pick on X? Put it on the record.
      </h1>
      <Standfirst className="mt-5">
        Paste the post&apos;s link. We fetch it, read the picks out of the text and images, match
        them to scheduled games, and add them to the creator&apos;s standings.
      </Standfirst>

      <div className="mt-10">
        <SubmitForm turnstileSiteKey={siteKey} />
      </div>

      <p className="mt-10 border-t border-ink pt-4 text-[13px] leading-relaxed text-ink-3">
        Submissions are anonymous and rate-limited. New creators appear in Division II until they
        build a track record.
      </p>
    </div>
  );
}
