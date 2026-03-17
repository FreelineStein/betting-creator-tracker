import Link from "next/link";
import { getCreator, getCreatorRecord, getCreatorPicks } from "../../lib/api";
import type { Pick } from "../../lib/api";

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "𝕏",
  instagram: "📸",
  youtube: "▶️",
  tiktok: "🎵",
  reddit: "👽",
};

function StatusBadge({ status }: { status: Pick["status"] }) {
  const styles: Record<string, string> = {
    won: "bg-green-400/10 text-green-400 border-green-400/20",
    lost: "bg-red-400/10 text-red-400 border-red-400/20",
    pending: "bg-yellow-400/10 text-yellow-400 border-yellow-400/20",
    push: "bg-gray-400/10 text-gray-400 border-gray-400/20",
    void: "bg-gray-700 text-gray-500 border-gray-600",
  };
  return (
    <span className={`px-2 py-0.5 rounded border text-xs font-semibold uppercase ${styles[status] ?? ""}`}>
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
    month: "short", day: "numeric", year: "numeric",
  });
}

type Props = { params: { id: string } };

export default async function CreatorPage({ params }: Props) {
  let creator, record, picks;
  try {
    [creator, record, picks] = await Promise.all([
      getCreator(params.id),
      getCreatorRecord(params.id),
      getCreatorPicks(params.id),
    ]);
  } catch {
    return (
      <div className="text-red-400">
        Could not load creator. Make sure the backend is running.
      </div>
    );
  }

  const hasPicks = record.total_picks > 0;
  const winRatePct = Math.round(record.win_rate * 100);
  const winRateColor =
    winRatePct >= 58 ? "text-green-400" :
    winRatePct >= 52 ? "text-yellow-400" :
    "text-red-400";

  // Sport breakdown
  const sports = Object.entries(record.accuracy_by_sport || {}).sort(
    ([, a], [, b]) => (b.wins + b.losses) - (a.wins + a.losses)
  );

  const pendingPicks = picks.filter((p) => p.status === "pending");
  const resolvedPicks = picks.filter((p) => p.status !== "pending");

  return (
    <div>
      {/* Back */}
      <Link href="/" className="text-gray-500 text-sm hover:text-gray-300 transition-colors mb-6 inline-block">
        ← Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">{creator.display_name}</h1>
          <div className="flex gap-2 mt-2">
            {creator.platforms.map((p) => (
              <a
                key={p.platform}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-sm text-gray-400 hover:text-gray-200 transition-colors"
              >
                <span>{PLATFORM_ICONS[p.platform] ?? "🔗"}</span>
                <span>{p.handle}</span>
              </a>
            ))}
          </div>
        </div>
      </div>

      {/* Record card */}
      {hasPicks ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-center">
            <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Record</div>
            <div className="text-white font-bold text-lg font-mono">
              {record.wins}W-{record.losses}L-{record.pushes}P
            </div>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-center">
            <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Win Rate</div>
            <div className={`font-bold text-2xl ${winRateColor}`}>{winRatePct}%</div>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-center">
            <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">ROI</div>
            <div className={`font-bold text-2xl ${record.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
              {record.roi >= 0 ? "+" : ""}{record.roi}%
            </div>
          </div>
          <div className="bg-gray-900 rounded-xl border border-gray-800 p-4 text-center">
            <div className="text-gray-500 text-xs uppercase tracking-wider mb-1">Total Picks</div>
            <div className="text-white font-bold text-2xl">{record.total_picks}</div>
          </div>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-8 text-center">
          <p className="text-gray-400">Tracking started — picks will appear as they're posted.</p>
        </div>
      )}

      {/* Sport breakdown */}
      {sports.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">By Sport</h2>
          <div className="flex flex-wrap gap-3">
            {sports.map(([sport, stats]) => {
              const total = stats.wins + stats.losses;
              const wr = total > 0 ? Math.round((stats.wins / total) * 100) : 0;
              const color = wr >= 58 ? "text-green-400" : wr >= 52 ? "text-yellow-400" : "text-red-400";
              return (
                <div key={sport} className="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2 flex items-center gap-3">
                  <span className="text-white text-sm font-semibold">{sport}</span>
                  <span className="text-gray-500 text-xs font-mono">{stats.wins}W-{stats.losses}L</span>
                  <span className={`text-xs font-bold ${color}`}>{wr}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pending picks */}
      {pendingPicks.length > 0 && (
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-yellow-400 uppercase tracking-wider mb-3">
            🟡 Active Picks ({pendingPicks.length})
          </h2>
          <div className="space-y-2">
            {pendingPicks.map((pick) => (
              <PickRow key={pick.pick_id} pick={pick} />
            ))}
          </div>
        </div>
      )}

      {/* Pick history */}
      <div>
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Pick History
        </h2>
        {resolvedPicks.length === 0 ? (
          <p className="text-gray-600 text-sm">No resolved picks yet.</p>
        ) : (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="grid grid-cols-12 px-4 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider border-b border-gray-800">
              <div className="col-span-2">Date</div>
              <div className="col-span-2">Sport</div>
              <div className="col-span-4">Pick</div>
              <div className="col-span-2">Odds</div>
              <div className="col-span-2">Result</div>
            </div>
            {resolvedPicks.map((pick) => (
              <div
                key={pick.pick_id}
                className="grid grid-cols-12 px-4 py-3 border-b border-gray-800 last:border-0 text-sm items-center"
              >
                <div className="col-span-2 text-gray-500 text-xs">{formatDate(pick.event_date)}</div>
                <div className="col-span-2 text-gray-300">{pick.sport}</div>
                <div className="col-span-4 text-white">
                  {formatPickDetail(pick.pick_type, pick.pick_detail)}
                  <div className="text-xs text-gray-500">{pick.event}</div>
                </div>
                <div className="col-span-2 text-gray-300 font-mono text-xs">{pick.odds}</div>
                <div className="col-span-2"><StatusBadge status={pick.status} /></div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PickRow({ pick }: { pick: Pick }) {
  function formatPickDetail(type: string, detail: Record<string, string | number>): string {
    if (type === "spread") return `${detail.team} ${detail.line}`;
    if (type === "moneyline") return `${detail.team} ML`;
    if (type === "over_under") return `${detail.direction} ${detail.total}`;
    if (type === "prop") return `${detail.player} ${detail.direction ?? "Over"} ${detail.line} ${detail.prop}`;
    return JSON.stringify(detail);
  }

  return (
    <div className="bg-gray-900 border border-yellow-500/20 rounded-lg px-4 py-3 flex items-center justify-between">
      <div>
        <div className="text-white font-medium">
          {formatPickDetail(pick.pick_type, pick.pick_detail)}
        </div>
        <div className="text-gray-500 text-xs mt-0.5">{pick.sport} · {pick.event}</div>
      </div>
      <div className="flex items-center gap-3 text-sm">
        <span className="text-gray-400 font-mono">{pick.odds}</span>
        <span className="text-yellow-400 text-xs font-semibold uppercase">Pending</span>
      </div>
    </div>
  );
}
