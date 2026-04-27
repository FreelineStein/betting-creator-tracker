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

    featured.sort((a, b) =>
      FEATURED_CREATOR_NAMES.indexOf(a.creator.display_name) -
      FEATURED_CREATOR_NAMES.indexOf(b.creator.display_name)
    );
  }

  const hasAnyCreators = featured.length > 0 || lesserKnown.length > 0;

  return (
    <div>
      {/* Hero */}
      <div className="mb-12">
        <div className="font-mono text-[10px] uppercase tracking-label text-ink-400 mb-3">
          Transparent Betting Records
        </div>
        <h1 className="font-display font-black text-5xl sm:text-6xl tracking-display leading-none text-white">
          Every pick.{" "}
          <span className="text-signal">Every loss.</span>{" "}
          On the record.
        </h1>
        <p className="text-ink-400 mt-4 max-w-xl">
          Your favorite creator&apos;s publicly posted picks. We surface the data — wins, losses, and everything in between — so you can decide who&apos;s worth tailing.
        </p>
      </div>

      {error && (
        <div className="bg-alert-dim border border-alert/40 rounded-xl p-4 text-alert-deep text-sm">
          Could not connect to API. Make sure the backend is running on{" "}
          <code className="font-mono bg-alert/10 px-1.5 py-0.5 rounded text-alert">
            localhost:8000
          </code>
          .
        </div>
      )}

      {!error && !hasAnyCreators && (
        <div className="text-ink-600 text-sm">No creators found.</div>
      )}

      {!error && featured.length > 0 && (
        <section>
          <h2 className="font-display font-black text-3xl tracking-display text-white mb-5">
            Popular Creators
          </h2>
          <CreatorCards creators={featured} />
        </section>
      )}

      {!error && lesserKnown.length > 0 && (
        <section className="mt-12">
          <h2 className="font-display font-black text-3xl tracking-display text-white mb-5">
            Lesser Known Creators
          </h2>
          <CreatorCards creators={lesserKnown} />
        </section>
      )}

      <p className="text-xs text-ink-600 mt-8">
        Picks sourced from public social media posts. Records update as outcomes are resolved.
      </p>

      {/* How it works */}
      <div className="mt-12 border-t border-ink-800 pt-8">
        <div className="font-mono text-[10px] uppercase tracking-label text-ink-400 mb-4">
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
              className="rounded-xl border border-ink-800 bg-ink-800/30 p-5"
            >
              <div className="font-mono text-[10px] uppercase tracking-label text-signal mb-2">
                {step.n}
              </div>
              <div className="font-display font-black text-lg tracking-display text-white mb-1">
                {step.title}
              </div>
              <p className="text-ink-400 leading-relaxed">{step.body}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-ink-600 mt-6">
          For entertainment and transparency purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}
