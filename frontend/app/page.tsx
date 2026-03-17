import { getAllCreatorsWithRecords, getCreatorPicks } from "./lib/api";
import type { Pick } from "./lib/api";
import CreatorCards from "./components/CreatorCards";

const FEATURED_CREATOR_NAMES = ["Trent", "DanAI", "Harry Locks", "Gavin"];

export default async function Home() {
  let data: Awaited<ReturnType<typeof getAllCreatorsWithRecords>> = [];
  let error = false;

  try {
    data = await getAllCreatorsWithRecords();
  } catch {
    error = true;
  }

  // Build creator cards with picks
  const creators: { creator: any; record: any; picks: Pick[] }[] = [];

  if (!error && data.length > 0) {
    const addedIds = new Set<string>();

    for (const { creator, record } of data) {
      if (addedIds.has(creator.creator_id)) continue;
      addedIds.add(creator.creator_id);

      if (!FEATURED_CREATOR_NAMES.includes(creator.display_name)) continue;

      let picks: Pick[] = [];
      try {
        picks = await getCreatorPicks(creator.creator_id);
      } catch {
        // continue with empty picks
      }
      creators.push({ creator, record, picks });
    }
  }

  return (
    <div>
      {/* Hero */}
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-white tracking-tight">Pick Receipts</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Today&apos;s picks from tracked creators. Transparent W/L records, no cherrypicking.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/20 border border-red-800/50 rounded-xl p-4 text-red-400 text-sm">
          Could not connect to API. Make sure the backend is running on{" "}
          <code className="font-mono bg-red-900/30 px-1.5 py-0.5 rounded">localhost:8000</code>.
        </div>
      )}

      {!error && creators.length === 0 && (
        <div className="text-gray-600 text-sm">No creators found.</div>
      )}

      {!error && creators.length > 0 && <CreatorCards creators={creators} />}

      {/* Footer */}
      <p className="text-xs text-gray-600 mt-8">
        Picks sourced from public social media posts. Records update as outcomes are resolved.
      </p>

      {/* How it works */}
      <div className="mt-12 border-t border-gray-800 pt-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-white font-medium mb-1">1. Capture picks</div>
            <p className="text-gray-500">
              Picks are pulled from creators&apos; public social media posts and extracted using AI.
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-white font-medium mb-1">2. Verify outcomes</div>
            <p className="text-gray-500">
              Game scores are checked automatically against real results from official sports data.
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-white font-medium mb-1">3. Build the record</div>
            <p className="text-gray-500">
              W/L records and ROI are calculated transparently. ROI is measured against the -110 break-even line (52.4%).
            </p>
          </div>
        </div>
        <p className="text-xs text-gray-600 mt-4">
          For entertainment and transparency purposes only. Not financial advice.
        </p>
      </div>
    </div>
  );
}
