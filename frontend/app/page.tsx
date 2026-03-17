import Link from "next/link";
import { getAllCreatorsWithRecords, getCreatorPicks } from "./lib/api";

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "\u{1D54F}",
  instagram: "\uD83D\uDCF8",
  youtube: "\u25B6\uFE0F",
  tiktok: "\uD83C\uDFB5",
  reddit: "\uD83D\uDC7D",
};

const FEATURED_CREATOR_NAMES = ["Trent", "DanAI", "Harry Locks", "Dr. Locks"];

function WinRateBadge({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100);
  const color =
    pct >= 58 ? "text-green-400 bg-green-400/10" :
    pct >= 52 ? "text-yellow-400 bg-yellow-400/10" :
    "text-red-400 bg-red-400/10";
  return (
    <span className={`px-2 py-0.5 rounded text-sm font-bold ${color}`}>
      {pct}%
    </span>
  );
}

function ROIBadge({ roi }: { roi: number }) {
  const color = roi >= 0 ? "text-green-400" : "text-red-400";
  return (
    <span className={`text-sm font-medium ${color}`}>
      {roi >= 0 ? "+" : ""}{roi}%
    </span>
  );
}

interface CreatorWithPicks {
  creator: any;
  record: any;
  recentPick: any;
}

function hasRecord(record: { total_picks: number } | null): boolean {
  return record !== null && record.total_picks > 0;
}

export default async function Home() {
  let data: Awaited<ReturnType<typeof getAllCreatorsWithRecords>> = [];
  let error = false;

  try {
    data = await getAllCreatorsWithRecords();
  } catch {
    error = true;
  }

  // Split into featured and other creators, fetch picks for featured
  let featuredCreators: CreatorWithPicks[] = [];
  let otherCreators = data;

  if (!error && data.length > 0) {
    featuredCreators = [];
    otherCreators = [];
    const addedIds = new Set<string>();

    for (const { creator, record } of data) {
      if (addedIds.has(creator.creator_id)) continue; // Skip duplicates
      addedIds.add(creator.creator_id);

      if (FEATURED_CREATOR_NAMES.includes(creator.display_name)) {
        let recentPick = null;
        try {
          const picks = await getCreatorPicks(creator.creator_id);
          recentPick = picks.length > 0 ? picks[0] : null;
        } catch {
          // Silently fail if picks can't be fetched
        }
        featuredCreators.push({ creator, record, recentPick });
      } else {
        otherCreators.push({ creator, record });
      }
    }
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">🧾 Pick Receipts</h1>
        <p className="text-gray-400 mt-1">
          Transparent W/L records for sports betting creators. No cherrypicking.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300 text-sm">
          Could not connect to API. Make sure the backend is running on{" "}
          <code className="font-mono">localhost:8000</code>.
        </div>
      )}

      {!error && data.length === 0 && (
        <div className="text-gray-500 text-sm">No creators found.</div>
      )}

      {/* Featured Creators Grid */}
      {!error && featuredCreators.length > 0 && (
        <div className="mb-12">
          <h2 className="text-xl font-semibold text-white mb-4">Featured Creators</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {featuredCreators.map(({ creator, record, recentPick }) => (
              <div
                key={creator.creator_id}
                className="bg-gray-900 rounded-lg border border-gray-800 p-6 hover:border-gray-700 transition-colors"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-bold text-white">{creator.display_name}</h3>
                    <div className="flex gap-2 mt-1">
                      {creator.platforms.map((p: any) => (
                        <a
                          key={p.platform}
                          href={p.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-400 hover:text-white transition-colors text-sm"
                          title={p.handle}
                        >
                          {PLATFORM_ICONS[p.platform] ?? "🔗"} {p.handle}
                        </a>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-3 mb-4 p-3 bg-gray-800/50 rounded">
                  <div>
                    <div className="text-xs text-gray-500 uppercase">Record</div>
                    <div className="text-sm font-mono text-white">
                      {hasRecord(record) ? `${record!.wins}W-${record!.losses}L` : <span className="text-gray-600 font-sans text-xs">Tracking started</span>}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 uppercase">Win Rate</div>
                    <div>
                      {hasRecord(record) ? <WinRateBadge rate={record!.win_rate} /> : <span className="text-gray-600 text-xs">--</span>}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 uppercase">ROI</div>
                    <div>
                      {hasRecord(record) ? <ROIBadge roi={record!.roi} /> : <span className="text-gray-600 text-xs">--</span>}
                    </div>
                  </div>
                </div>

                {/* Recent Pick Dropdown + View History Link */}
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    {recentPick && (
                      <details className="text-sm">
                        <summary className="cursor-pointer text-gray-300 hover:text-white font-medium">
                          📌 Most Recent Pick
                        </summary>
                        <div className="mt-3 p-3 bg-gray-800/30 rounded text-gray-300 space-y-1 text-xs">
                          <div>
                            <span className="text-gray-500">Sport:</span> <span className="font-mono">{recentPick.sport}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Event:</span> <span className="font-mono">{recentPick.event}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Type:</span> <span className="font-mono">{recentPick.pick_type}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Status:</span>{" "}
                            <span
                              className={`font-bold ${
                                recentPick.status === "won"
                                  ? "text-green-400"
                                  : recentPick.status === "lost"
                                    ? "text-red-400"
                                    : "text-yellow-400"
                              }`}
                            >
                              {recentPick.status.toUpperCase()}
                            </span>
                          </div>
                          {recentPick.odds && (
                            <div>
                              <span className="text-gray-500">Odds:</span> <span className="font-mono">{recentPick.odds}</span>
                            </div>
                          )}
                        </div>
                      </details>
                    )}
                  </div>
                  <Link
                    href={`/creators/${creator.creator_id}`}
                    className="text-sm text-blue-400 hover:text-blue-300 transition-colors whitespace-nowrap"
                  >
                    View history →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Other Creators Table */}
      {!error && otherCreators.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold text-white mb-4">Other Creators</h2>
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            {/* Header */}
            <div className="grid grid-cols-12 px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-800">
              <div className="col-span-1">#</div>
              <div className="col-span-4">Creator</div>
              <div className="col-span-2">Platforms</div>
              <div className="col-span-2">Record</div>
              <div className="col-span-2">Win Rate</div>
              <div className="col-span-1">ROI</div>
            </div>

            {/* Rows */}
            {otherCreators.map(({ creator, record }, i) => (
              <Link
                key={creator.creator_id}
                href={`/creators/${creator.creator_id}`}
                className="grid grid-cols-12 px-6 py-4 border-b border-gray-800 last:border-0 hover:bg-gray-800/50 transition-colors items-center"
              >
                <div className="col-span-1 text-gray-500 font-mono text-sm">{i + 1}</div>
                <div className="col-span-4">
                  <span className="font-semibold text-white">{creator.display_name}</span>
                </div>
                <div className="col-span-2 flex gap-1 text-sm">
                  {creator.platforms.map((p: any) => (
                    <span key={p.platform} title={p.platform} className="text-base">
                      {PLATFORM_ICONS[p.platform] ?? "🔗"}
                    </span>
                  ))}
                </div>
                <div className="col-span-2 text-sm text-gray-300 font-mono">
                  {hasRecord(record)
                    ? `${record!.wins}W-${record!.losses}L-${record!.pushes}P`
                    : <span className="text-gray-600 font-sans text-xs">Tracking started</span>
                  }
                </div>
                <div className="col-span-2">
                  {hasRecord(record) ? <WinRateBadge rate={record!.win_rate} /> : <span className="text-gray-600 text-xs">--</span>}
                </div>
                <div className="col-span-1">
                  {hasRecord(record) ? <ROIBadge roi={record!.roi} /> : <span className="text-gray-600 text-xs">--</span>}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-600 mt-4">
        Picks sourced from public social media posts. Records update as outcomes are resolved.
      </p>

      {/* How it works */}
      <div className="mt-12 border-t border-gray-800 pt-8">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">How it works</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-white font-medium mb-1">1. Capture picks</div>
            <p className="text-gray-500">
              Picks are pulled from creators' public social media posts and extracted using AI.
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
