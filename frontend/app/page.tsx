import Link from "next/link";
import { getAllCreatorsWithRecords } from "./lib/api";

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "𝕏",
  instagram: "📸",
  youtube: "▶️",
  tiktok: "🎵",
  reddit: "👽",
};

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

export default async function Home() {
  let data: Awaited<ReturnType<typeof getAllCreatorsWithRecords>> = [];
  let error = false;

  try {
    data = await getAllCreatorsWithRecords();
  } catch {
    error = true;
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Creator Leaderboard</h1>
        <p className="text-gray-400 mt-1">
          Transparent W/L records for sports betting creators. No cherrypicking.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-red-300 text-sm">
          ⚠️ Could not connect to API. Make sure the backend is running on{" "}
          <code className="font-mono">localhost:8000</code>.
        </div>
      )}

      {!error && data.length === 0 && (
        <div className="text-gray-500 text-sm">No creators found. Run the seed script to populate data.</div>
      )}

      {!error && data.length > 0 && (
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
          {data.map(({ creator, record }, i) => (
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
                {creator.platforms.map((p) => (
                  <span key={p.platform} title={p.platform} className="text-base">
                    {PLATFORM_ICONS[p.platform] ?? "🔗"}
                  </span>
                ))}
              </div>
              <div className="col-span-2 text-sm text-gray-300 font-mono">
                {record ? `${record.wins}W-${record.losses}L-${record.pushes}P` : "—"}
              </div>
              <div className="col-span-2">
                {record ? <WinRateBadge rate={record.win_rate} /> : <span className="text-gray-600">—</span>}
              </div>
              <div className="col-span-1">
                {record ? <ROIBadge roi={record.roi} /> : <span className="text-gray-600">—</span>}
              </div>
            </Link>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-600 mt-4">
        Records updated automatically. Picks sourced from public social media posts.
      </p>
    </div>
  );
}
