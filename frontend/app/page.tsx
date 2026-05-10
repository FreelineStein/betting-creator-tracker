import { getAllCreatorsWithRecords, getCreatorPicks } from "./lib/api";
import type { Pick } from "./lib/api";
import CreatorCards from "./components/CreatorCards";

const FEATURED_CREATOR_NAMES = ["Trent", "DanAI", "Dr. Locks", "Harry Locks", "Gavin"];

export default async function Home() {
  let data: Awaited<ReturnType<typeof getAllCreatorsWithRecords>> = [];
  let error = false;

  try {
    data = await getAllCreatorsWithRecords();
  } catch {
    error = true;
  }

  const featured: { creator: any; record: any; picks: Pick[] }[] = [];
  const lesserKnown: { creator: any; record: any; picks: Pick[] }[] = [];

  if (!error && data.length > 0) {
    const addedIds = new Set<string>();

    for (const { creator, record } of data) {
      if (addedIds.has(creator.creator_id)) continue;
      addedIds.add(creator.creator_id);

      let picks: Pick[] = [];
      try {
        picks = await getCreatorPicks(creator.creator_id);
      } catch {
        // continue with empty picks
      }

      if (FEATURED_CREATOR_NAMES.includes(creator.display_name)) {
        featured.push({ creator, record, picks });
      } else {
        lesserKnown.push({ creator, record, picks });
      }
    }

    featured.sort(
      (a, b) =>
        FEATURED_CREATOR_NAMES.indexOf(a.creator.display_name) -
        FEATURED_CREATOR_NAMES.indexOf(b.creator.display_name),
    );
  }

  const hasAnyCreators = featured.length > 0 || lesserKnown.length > 0;

  return (
    <div>
      {/* Hero */}
      <div className="mb-14">
        <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-4">
          Transparent Betting Records
        </div>
        <h1 className="font-display font-extrabold text-5xl sm:text-6xl tracking-display leading-[1.0] text-ink text-balance">
          Every pick. <span className="text-amber-deep">Every loss.</span> On the record.
        </h1>
        <p className="text-ink-500 mt-5 max-w-xl text-[15px] leading-relaxed">
          Your favorite creator&apos;s publicly posted picks. We surface the data —
          wins, losses, and everything in between — so you can decide who&apos;s worth tailing.
        </p>
      </div>

      {error && (
        <div className="rounded-[10px] border border-rule bg-paper-2 p-4 text-ink-700 text-sm">
          Could not connect to API. Make sure the backend is running on{" "}
          <code className="font-mono bg-paper-3 px-1.5 py-0.5 rounded text-ink">
            localhost:8000
          </code>
          .
        </div>
      )}

      {!error && !hasAnyCreators && (
        <div className="text-ink-500 text-sm">No creators found.</div>
      )}

      {!error && featured.length > 0 && (
        <section>
          <h2 className="font-display font-extrabold text-3xl tracking-display text-ink mb-5">
            Popular Creators
          </h2>
          <CreatorCards creators={featured} />
        </section>
      )}

      {!error && lesserKnown.length > 0 && (
        <section className="mt-14">
          <h2 className="font-display font-extrabold text-3xl tracking-display text-ink mb-5">
            Lesser Known Creators
          </h2>
          <CreatorCards creators={lesserKnown} />
        </section>
      )}

      <p className="text-xs text-ink-500 mt-10">
        Picks sourced from public social media posts. Records update as outcomes are resolved.
      </p>

      {/* How it works */}
      <div className="mt-14 border-t border-rule pt-10">
        <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-5">
          How it works
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          {[
            {
              n: "01",
              title: "Capture picks",
              body: "Picks are pulled from creators' public social media posts and extracted using AI.",
            },
            {
              n: "02",
              title: "Verify outcomes",
              body: "Game scores are checked automatically against real results from official sports data.",
            },
            {
              n: "03",
              title: "Build the record",
              body: "W/L records and ROI are calculated transparently. ROI is measured against the −110 break-even line (52.4%).",
            },
          ].map((step) => (
            <div
              key={step.n}
              className="rounded-[14px] border border-rule bg-paper-2 p-5 shadow-card"
            >
              <div className="font-mono text-[10px] uppercase tracking-label-x font-semibold text-amber-deep mb-2">
                {step.n}
              </div>
              <div className="font-display font-extrabold text-lg tracking-tight text-ink mb-1">
                {step.title}
              </div>
              <p className="text-ink-500 leading-relaxed">{step.body}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-ink-500 mt-6">
          For entertainment and transparency purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}
