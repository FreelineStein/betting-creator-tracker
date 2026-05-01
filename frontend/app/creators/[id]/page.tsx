import Link from "next/link";
import { getCreator, getCreatorRecord, getCreatorPicks } from "../../lib/api";
import type { Pick } from "../../lib/api";
import { Badge, StatCard, WLRecord } from "../../../components/brand";

const SPORT_ICONS: Record<string, string> = {
  NFL: "🏈",
  CFB: "🏈",
  NCAAF: "🏈",
  NBA: "🏀",
  CBB: "🏀",
  NCAAB: "🏀",
  WNBA: "🏀",
  MLB: "⚾",
  WBC: "⚾",
  NHL: "🏒",
  SOCCER: "⚽",
  TENNIS: "🎾",
  UFC: "🥊",
  PGA: "⛳",
};

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "𝕏",
  instagram: "📸",
  youtube: "▶️",
  tiktok: "🎵",
  reddit: "👽",
};

function LegDot({ result }: { result: string }) {
  if (result === "won") return <span className="w-1.5 h-1.5 rounded-full bg-signal shrink-0" />;
  if (result === "lost") return <span className="w-1.5 h-1.5 rounded-full bg-alert shrink-0" />;
  if (result === "push") return <span className="w-1.5 h-1.5 rounded-full bg-ink-400 shrink-0" />;
  if (result === "pending") return <span className="w-1.5 h-1.5 rounded-full bg-white/40 shrink-0" />;
  return null;
}

function StatusBadge({ status }: { status: Pick["status"] }) {
  if (status === "won") return <Badge variant="win">won</Badge>;
  if (status === "lost") return <Badge variant="loss">lost</Badge>;
  if (status === "push") return <Badge variant="push">push</Badge>;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-ink-800/60 text-ink-400 px-2.5 py-1 text-xs font-bold uppercase tracking-label">
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

// US sports schedules are conventionally communicated in Eastern time, and
// pinning a timezone makes the date stable regardless of where the page is
// rendered (Vercel runs in UTC by default, which would otherwise show a late
// East-coast game on the next calendar day).
function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "America/New_York",
  });
}

function winRateTone(pct: number): "win" | "loss" | "default" {
  if (pct >= 58) return "win";
  if (pct < 52) return "loss";
  return "default";
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
      <div className="bg-alert-dim border border-alert/40 rounded-xl p-4 text-alert-deep text-sm">
        Could not load creator. Make sure the backend is running.
      </div>
    );
  }

  const hasPicks = record.total_picks > 0;
  const winRatePct = Math.round(record.win_rate * 100);
  const wrTone = winRateTone(winRatePct);

  const sports = Object.entries(record.accuracy_by_sport || {}).sort(
    ([, a], [, b]) => b.wins + b.losses - (a.wins + a.losses)
  );

  const pendingPicks = picks.filter((p) => p.status === "pending");
  // Sort resolved picks newest → oldest by event_date so the history reads
  // top-to-bottom as most-recent-first. Picks missing event_date (legacy
  // rows) fall to the end.
  const resolvedPicks = picks
    .filter((p) => p.status !== "pending")
    .slice()
    .sort((a, b) => {
      const at = a.event_date ? new Date(a.event_date).getTime() : 0;
      const bt = b.event_date ? new Date(b.event_date).getTime() : 0;
      return bt - at;
    });

  return (
    <div>
      {/* Back link */}
      <Link
        href="/"
        className="font-mono text-[11px] uppercase tracking-label text-ink-400 hover:text-signal transition-colors mb-6 inline-block"
      >
        ← Leaderboard
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div className="flex items-center gap-4">
          {creator.profile_image_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={creator.profile_image_url}
              alt={creator.display_name}
              className="w-14 h-14 rounded-full object-cover"
            />
          ) : (
            <div className="w-14 h-14 rounded-full bg-ink-800 border border-ink-800 flex items-center justify-center text-signal font-display font-black text-2xl">
              {creator.display_name.charAt(0)}
            </div>
          )}
          <div>
            <h1 className="font-sans font-bold text-3xl leading-none text-white">
              {creator.display_name}
            </h1>
            <div className="flex gap-3 mt-3">
              {creator.platforms.map((p) => (
                <a
                  key={p.platform}
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-[11px] text-ink-400 hover:text-signal transition-colors"
                >
                  {PLATFORM_ICONS[p.platform] ?? "🔗"} {p.handle}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Record cards */}
      {hasPicks ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          <StatCard
            label="Record"
            value={<WLRecord w={record.wins} l={record.losses} size="lg" />}
            sub={record.pushes > 0 ? `${record.pushes} push${record.pushes === 1 ? "" : "es"}` : undefined}
          />
          <StatCard label="Win Rate" value={`${winRatePct}%`} tone={wrTone} sub="Verified picks" />
          <StatCard
            label="ROI"
            value={`${record.roi >= 0 ? "+" : ""}${record.roi}%`}
            tone={record.roi >= 0 ? "win" : "loss"}
            sub="vs −110 break-even"
          />
          <StatCard label="Total Picks" value={record.total_picks} sub="All-time tracked" />
        </div>
      ) : (
        <div className="bg-ink-800/30 border border-ink-800 rounded-xl p-6 mb-8 text-center">
          <p className="text-ink-400">Tracking started — picks will appear as they&apos;re posted.</p>
        </div>
      )}

      {/* Sport breakdown */}
      {sports.length > 0 && (
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-label text-ink-400 mb-3">
            By Sport
          </div>
          <div className="flex flex-wrap gap-3">
            {sports.map(([sport, stats]) => {
              const total = stats.wins + stats.losses;
              const wr = total > 0 ? Math.round((stats.wins / total) * 100) : 0;
              const wrColor =
                wr >= 58 ? "text-signal" : wr >= 52 ? "text-ink-400" : "text-alert";
              return (
                <div
                  key={sport}
                  className="bg-ink-800/30 border border-ink-800 rounded-lg px-4 py-2 flex items-center gap-3"
                >
                  <span className="font-display font-black text-sm tracking-display text-white">
                    {sport}
                  </span>
                  <WLRecord w={stats.wins} l={stats.losses} size="sm" />
                  <span className={`font-mono tabular text-xs font-bold ${wrColor}`}>{wr}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pending picks */}
      {pendingPicks.length > 0 && (
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-label text-white mb-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            Active Picks ({pendingPicks.length})
          </div>
          <div className="space-y-2">
            {pendingPicks.map((pick) => (
              <PickRow key={pick.pick_id} pick={pick} />
            ))}
          </div>
        </div>
      )}

      {/* Pick history */}
      <div>
        <div className="font-mono text-[10px] uppercase tracking-label text-ink-400 mb-3">
          Pick History
        </div>
        {resolvedPicks.length === 0 ? (
          <p className="text-ink-600 text-sm">No resolved picks yet.</p>
        ) : (
          <div className="bg-ink-800/30 rounded-xl border border-ink-800 overflow-hidden">
            <div className="grid grid-cols-12 px-4 py-2 font-mono text-[10px] uppercase tracking-label text-ink-400 border-b border-ink-800">
              <div className="col-span-2">Date</div>
              <div className="col-span-2">Sport</div>
              <div className="col-span-4">Pick</div>
              <div className="col-span-2">Odds</div>
              <div className="col-span-2">Result</div>
            </div>
            {resolvedPicks.map((pick, i) => {
              const prev = i > 0 ? resolvedPicks[i - 1] : null;
              const isNewDay =
                !!prev &&
                formatDate(prev.event_date) !== formatDate(pick.event_date);
              return (
              <div
                key={pick.pick_id}
                className={`grid grid-cols-12 px-4 py-3 border-b border-ink-800/60 last:border-0 text-sm items-center ${
                  isNewDay ? "border-t border-t-ink-800/80 mt-1 pt-4" : ""
                }`}
              >
                <div className="col-span-2 font-mono text-xs text-ink-400">
                  {formatDate(pick.event_date)}
                </div>
                <div className="col-span-2 text-base" title={pick.league ?? pick.sport}>
                  {SPORT_ICONS[pick.sport] ?? pick.sport}
                </div>
                <div className="col-span-4 text-white">
                  {pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs) ? (
                    <>
                      <div className="font-semibold">
                        {pick.pick_detail.legs.length}-Leg Parlay
                      </div>
                      <div className="mt-1 space-y-0.5 pl-3 border-l border-ink-800">
                        {pick.pick_detail.legs.map((leg: any, j: number) => {
                          const text = typeof leg === "string" ? leg : leg.text ?? JSON.stringify(leg);
                          const result = typeof leg === "object" ? leg.result : undefined;
                          const legEvent = typeof leg === "object" ? leg.event : undefined;
                          return (
                            <div key={j} className="text-ink-400 text-xs flex items-center gap-1.5">
                              {result && <LegDot result={result} />}
                              <span>{text}</span>
                              {legEvent && (
                                <span className="text-ink-600">· {legEvent}</span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                      {pick.event && (
                        <div className="text-xs text-ink-600 mt-1">
                          {pick.league ? `${pick.league} · ` : ""}{pick.event}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      {formatPickDetail(pick.pick_type, pick.pick_detail)}
                      <div className="text-xs text-ink-600">
                        {pick.league ? `${pick.league} · ` : ""}{pick.event}
                      </div>
                    </>
                  )}
                </div>
                <div className="col-span-2 font-mono tabular text-xs text-ink-400">
                  {pick.odds}
                </div>
                <div className="col-span-2">
                  <StatusBadge status={pick.status} />
                </div>
              </div>
              );
            })}
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
    <div className="bg-ink-800/30 border border-ink-800 rounded-lg px-4 py-3 flex items-center justify-between">
      <div>
        {pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs) ? (
          <>
            <div className="text-white font-semibold">
              {pick.pick_detail.legs.length}-Leg Parlay
            </div>
            <div className="mt-1 space-y-0.5 pl-3 border-l border-ink-800">
              {pick.pick_detail.legs.map((leg: any, j: number) => {
                const text = typeof leg === "string" ? leg : leg.text ?? JSON.stringify(leg);
                const result = typeof leg === "object" ? leg.result : undefined;
                const legEvent = typeof leg === "object" ? leg.event : undefined;
                return (
                  <div key={j} className="text-ink-400 text-xs flex items-center gap-1.5">
                    {result && <LegDot result={result} />}
                    <span>{text}</span>
                    {legEvent && (
                      <span className="text-ink-600">· {legEvent}</span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="text-ink-600 text-xs mt-1">
              {pick.league ?? pick.sport}
              {pick.event ? ` · ${pick.event}` : ""}
            </div>
          </>
        ) : (
          <>
            <div className="text-white font-semibold">
              {formatPickDetail(pick.pick_type, pick.pick_detail)}
            </div>
            <div className="text-ink-600 text-xs mt-0.5">
              {pick.league ?? pick.sport} · {pick.event}
            </div>
          </>
        )}
      </div>
      <div className="flex items-center gap-3 text-sm">
        {pick.event_date && (
          <span className="font-mono text-[11px] text-ink-400">
            {formatDate(pick.event_date)}
          </span>
        )}
        <span className="font-mono tabular text-ink-400">{pick.odds}</span>
        <span className="font-mono text-[10px] uppercase tracking-label text-white">Pending</span>
      </div>
    </div>
  );
}
