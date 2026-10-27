import type { Metadata } from "next";
import SubmitForm from "./SubmitForm";
import { Lede, Panel } from "../../components/brand";

export const metadata: Metadata = {
  title: "Submit a pick · PickReceipts",
  description:
    "Saw a creator post a betting pick on X? Drop the link here and we'll log it on the public record.",
};

// Cloudflare's always-pass test key. Override with NEXT_PUBLIC_TURNSTILE_SITE_KEY in production.
const TURNSTILE_TEST_SITE_KEY = "1x00000000000000000000AA";

const STEPS = [
  { head: "Paste the post", body: "Any public X post with a pick in it. The link looks like x.com/handle/status/…" },
  { head: "We read it", body: "The post is fetched live and the picks are read out of the text and any bet-slip images." },
  { head: "We match the game", body: "Each pick is pinned to a scheduled game. Anything we can't match is held for review, not guessed." },
  { head: "It settles", body: "About 15 minutes after the game ends, the pick is graded and the creator's record updates." },
];

export default function SubmitPage() {
  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY || TURNSTILE_TEST_SITE_KEY;

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-x-12">
      <div>
        <h1 className="font-display text-[clamp(36px,5vw,60px)] font-extrabold uppercase leading-[1.0] text-fg text-balance">
          Saw a pick on X? <span className="text-win">Put it on the record.</span>
        </h1>
        <Lede className="mt-4">
          Paste the post&apos;s link. We fetch it, read the picks, match them to scheduled games, and
          add them to the creator&apos;s record.
        </Lede>

        <Panel className="mt-8 px-5 py-6 sm:px-7 sm:py-7">
          <SubmitForm turnstileSiteKey={siteKey} />
        </Panel>

        <p className="mt-4 text-[13.5px] leading-relaxed text-fg-3">
          Submissions are anonymous and rate-limited. New creators appear in Division II until they
          build a track record.
        </p>
      </div>

      <aside className="mt-12 lg:mt-[6px]" aria-labelledby="how-submit">
        <h2 id="how-submit" className="mb-3.5 font-display text-[22px] font-bold uppercase leading-none tracking-[0.02em] text-fg">
          What happens next
        </h2>
        <Panel className="px-5 py-2">
          <ol className="divide-y divide-line">
            {STEPS.map((s, i) => (
              <li key={s.head} className="flex gap-3.5 py-4">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-win-dim font-display text-[14px] font-bold text-win">
                  {i + 1}
                </span>
                <div>
                  <div className="font-semibold text-fg">{s.head}</div>
                  <p className="mt-0.5 text-[14px] leading-[1.5] text-fg-2">{s.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>
      </aside>
    </div>
  );
}
