import Link from "next/link";
import { getAllCreatorsWithRecords, getCreatorPicks } from "./lib/api";
import type { Pick } from "./lib/api";

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "\u{1D54F}",
  instagram: "\uD83D\uDCF8",
  youtube: "\u25B6\uFE0F",
  tiktok: "\uD83C\uDFB5",
  reddit: "\uD83D\uDC7D",
};

const FEATURED_CREATOR_NAMES = ["Trent", "DanAI", "Harry Locks", "Gavin"];

const SPORT_ICONS: Record<string, string> = {
  NFL: "\uD83C\uDFC8",
  CFB: "\uD83C\uDFC8",
  NCAAF: "\uD83C\uDFC8",
  NBA: "\uD83C\uDFC0",
  CBB: "\uD83C\uDFC0",
  NCAAB: "\uD83C\uDFC0",
  WNBA: "\uD83C\uDFC0",
  MLB: "\u26BE",
  WBC: "\u26BE",
  NHL: "\uD83C\uDFD2",
  MLS: "\u26BD",
  UFC: "\uD83E\uDD4A",
  PGA: "\u26F3",
};

const STATUS_STYLES: Record<string, string> = {
  won: "bg-green-500/10 text-green-400 border-green-500/20",
  lost: "bg-red-500/10 text-red-400 border-red-500/20",
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  push: "bg-gray-500/10 text-gray-400 border-gray-500/20",
  void: "bg-gray-800 text-gray-500 border-gray-700",
};

function StatusPill({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold uppercase tracking-wide ${STATUS_STYLES[status] ?? STATUS_STYLES.pending}`}>
      {status}
    </span>
  );
}

function formatPickDetail(type: string, detail: Record<string, string | number>): string {
  if (type === "spread") return `${detail.team} ${detail.line}`;
  if (type === "moneyline") return `${detail.team} ML`;
  if (type === "over_under") return `${detail.direction} ${detail.total}`;
  if (type === "prop") return `${detail.player} ${detail.direction ?? "Over"} ${detail.line} ${detail.prop}`;
  return JSON.stringify(detail);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function StatValue({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className="text-[10px] text-gray-500 uppercase tracking-wider font-medium">{label}</div>
      <div className={`text-sm font-bold font-mono ${color ?? "text-white"}`}>{value}</div>
    </div>
  );
}

interface CreatorCardData {
  creator: any;
  record: any;
  picks: Pick[];
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

  // Build creator cards with picks
  const creators: CreatorCardData[] = [];

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
          Transparent W/L records for sports betting creators. No cherrypicking.
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

      {/* Creator Cards */}
      <div className="space-y-6">
        {creators.map(({ creator, record, picks }) => {
          const recentPicks = picks.slice(0, 5);
          const pendingPicks = picks.filter((p) => p.status === "pending");
          const winRate = hasRecord(record) ? Math.round(record!.win_rate * 100) : null;
          const winRateColor =
            winRate !== null && winRate >= 58 ? "text-green-400" :
            winRate !== null && winRate >= 52 ? "text-yellow-400" :
            winRate !== null ? "text-red-400" : "text-gray-600";

          return (
            <div
              key={creator.creator_id}
              className="bg-gray-900/50 backdrop-blur rounded-2xl border border-gray-800/80 overflow-hidden"
            >
              {/* Creator Header */}
              <div className="px-6 pt-5 pb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
                    {creator.display_name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-white font-semibold text-lg leading-tight">{creator.display_name}</h2>
                    <div className="flex gap-2 mt-0.5">
                      {creator.platforms.map((p: any) => (
                        <a
                          key={p.platform}
                          href={p.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-gray-500 hover:text-gray-300 transition-colors text-xs"
                        >
                          {PLATFORM_ICONS[p.platform] ?? "🔗"} {p.handle}
                        </a>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Stats bar */}
                {hasRecord(record) ? (
                  <div className="flex items-center gap-5">
                    <StatValue label="Record" value={`${record!.wins}-${record!.losses}-${record!.pushes}`} />
                    <StatValue label="Win %" value={`${winRate}%`} color={winRateColor} />
                    <StatValue
                      label="ROI"
                      value={`${record!.roi >= 0 ? "+" : ""}${record!.roi}%`}
                      color={record!.roi >= 0 ? "text-green-400" : "text-red-400"}
                    />
                  </div>
                ) : (
                  <span className="text-gray-600 text-xs">Tracking started</span>
                )}
              </div>

              {/* Active Picks Banner */}
              {pendingPicks.length > 0 && (
                <div className="mx-6 mb-3 px-3 py-1.5 bg-yellow-500/5 border border-yellow-500/15 rounded-lg flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse" />
                  <span className="text-yellow-400/80 text-[11px] font-medium uppercase tracking-wide">
                    {pendingPicks.length} active {pendingPicks.length === 1 ? "pick" : "picks"}
                  </span>
                </div>
              )}

              {/* Picks List */}
              {recentPicks.length > 0 ? (
                <div className="border-t border-gray-800/60">
                  {recentPicks.map((pick, i) => (
                    <div
                      key={pick.pick_id}
                      className={`px-6 py-3 flex items-center justify-between gap-4 ${
                        i < recentPicks.length - 1 ? "border-b border-gray-800/40" : ""
                      } hover:bg-gray-800/20 transition-colors`}
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        <div className="text-[11px] text-gray-600 font-mono w-12 shrink-0">
                          {formatDate(pick.event_date)}
                        </div>
                        <div className="text-base w-6 shrink-0 text-center" title={pick.sport}>
                          {SPORT_ICONS[pick.sport] ?? "\uD83C\uDFC6"}
                        </div>
                        <div className="min-w-0">
                          <div className="text-white text-sm font-medium truncate">
                            {formatPickDetail(pick.pick_type, pick.pick_detail)}
                          </div>
                          <div className="text-gray-600 text-xs truncate">
                            {pick.event}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {pick.odds && (
                          <span className="text-gray-500 font-mono text-xs">{pick.odds}</span>
                        )}
                        <StatusPill status={pick.status} />
                      </div>
                    </div>
                  ))}

                  {/* View all link */}
                  {picks.length > 5 && (
                    <div className="px-6 py-2.5 border-t border-gray-800/40">
                      <Link
                        href={`/creators/${creator.creator_id}`}
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
                      >
                        View all {picks.length} picks →
                      </Link>
                    </div>
                  )}
                </div>
              ) : (
                <div className="border-t border-gray-800/60 px-6 py-6 text-center">
                  <p className="text-gray-600 text-sm">No picks yet — tracking will begin as picks are posted.</p>
                </div>
              )}

              {/* Footer link (when ≤ 5 picks) */}
              {recentPicks.length > 0 && picks.length <= 5 && (
                <div className="px-6 py-2.5 border-t border-gray-800/40">
                  <Link
                    href={`/creators/${creator.creator_id}`}
                    className="text-xs text-blue-400 hover:text-blue-300 transition-colors font-medium"
                  >
                    Full history →
                  </Link>
                </div>
              )}
            </div>
          );
        })}
      </div>

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
