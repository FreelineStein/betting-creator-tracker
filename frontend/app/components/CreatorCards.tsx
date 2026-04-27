"use client";

import Link from "next/link";
import type { Pick } from "../lib/api";
import { Badge, WLRecord } from "../../components/brand";

const PLATFORM_ICONS: Record<string, string> = {
  twitter: "\u{1D54F}",
  instagram: "📸",
  youtube: "▶️",
  tiktok: "🎵",
  reddit: "👽",
};

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
  MLS: "⚽",
  UFC: "🥊",
  PGA: "⛳",
};

function statusToBadgeVariant(status: string): "win" | "loss" | "push" | null {
  if (status === "won") return "win";
  if (status === "lost") return "loss";
  if (status === "push") return "push";
  return null;
}

function StatusPill({ status }: { status: string }) {
  const variant = statusToBadgeVariant(status);
  if (variant) {
    return <Badge variant={variant}>{status}</Badge>;
  }
  // pending/void — neutral, no semantic color per brand
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

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "America/New_York",
  });
}

function isActive(dateStr: string | null, fallback: string): boolean {
  // Active = event hasn't happened yet, OR event/log is the current calendar day.
  // Falls back to logged_at when event_date is missing (legacy picks).
  const ts = new Date(dateStr ?? fallback);
  if (Number.isNaN(ts.getTime())) return false;
  if (ts.getTime() >= Date.now()) return true;
  return ts.toLocaleDateString() === new Date().toLocaleDateString();
}

function LegDot({ result }: { result: string }) {
  if (result === "won") return <span className="w-1.5 h-1.5 rounded-full bg-signal shrink-0" />;
  if (result === "lost") return <span className="w-1.5 h-1.5 rounded-full bg-alert shrink-0" />;
  if (result === "push") return <span className="w-1.5 h-1.5 rounded-full bg-ink-400 shrink-0" />;
  if (result === "pending") return <span className="w-1.5 h-1.5 rounded-full bg-white/40 shrink-0" />;
  return null;
}

function winRateTone(winRate: number | null): string {
  if (winRate === null) return "text-ink-600";
  if (winRate >= 58) return "text-signal";
  if (winRate >= 52) return "text-ink-400";
  return "text-alert";
}

function StatColumn({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="text-center">
      <div className="font-mono text-[9px] text-ink-400 uppercase tracking-label">{label}</div>
      <div className="mt-0.5">{children}</div>
    </div>
  );
}

function hasRecord(record: { total_picks: number } | null): boolean {
  return record !== null && record.total_picks > 0;
}

interface CreatorCardData {
  creator: any;
  record: any;
  picks: Pick[];
}

export default function CreatorCards({ creators }: { creators: CreatorCardData[] }) {
  return (
    <div className="space-y-6">
      {creators.map(({ creator, record, picks }) => {
        const activePicks = picks.filter((p) => isActive(p.event_date, p.logged_at));
        const recentPicks = activePicks.slice(0, 5);
        const pendingPicks = activePicks.filter((p) => p.status === "pending");
        const winRate = hasRecord(record) ? Math.round(record!.win_rate * 100) : null;
        const winRateColor = winRateTone(winRate);

        return (
          <div
            key={creator.creator_id}
            className="bg-ink-800/30 rounded-2xl border border-ink-800 overflow-hidden"
          >
            {/* Creator Header */}
            <div className="px-6 pt-5 pb-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                {creator.profile_image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={creator.profile_image_url}
                    alt={creator.display_name}
                    className="w-10 h-10 rounded-full object-cover"
                  />
                ) : (
                  <div className="w-10 h-10 rounded-full bg-ink-800 border border-ink-800 flex items-center justify-center text-signal font-display font-black text-lg">
                    {creator.display_name.charAt(0)}
                  </div>
                )}
                <div>
                  <h2 className="font-sans font-bold text-xl leading-none text-white">
                    {creator.display_name}
                  </h2>
                  <div className="flex gap-2 mt-1.5">
                    {creator.platforms.map((p: any) => (
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

              {/* Stats bar */}
              {hasRecord(record) ? (
                <div className="flex items-center gap-5">
                  <StatColumn label="Record">
                    <WLRecord w={record!.wins} l={record!.losses} size="sm" />
                  </StatColumn>
                  <StatColumn label="Win %">
                    <span className={`font-mono tabular text-sm font-bold ${winRateColor}`}>
                      {winRate}%
                    </span>
                  </StatColumn>
                  <StatColumn label="ROI">
                    <span
                      className={`font-mono tabular text-sm font-bold ${
                        record!.roi >= 0 ? "text-signal" : "text-alert"
                      }`}
                    >
                      {record!.roi >= 0 ? "+" : ""}
                      {record!.roi}%
                    </span>
                  </StatColumn>
                </div>
              ) : (
                <span className="font-mono text-[10px] uppercase tracking-label text-ink-400">
                  Tracking started
                </span>
              )}
            </div>

            {/* Active Picks Banner */}
            {pendingPicks.length > 0 && (
              <div className="mx-6 mb-3 px-3 py-1.5 bg-ink-800/60 border border-ink-800 rounded-lg flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                <span className="font-mono text-[10px] uppercase tracking-label text-ink-400">
                  {pendingPicks.length} active {pendingPicks.length === 1 ? "pick" : "picks"}
                </span>
              </div>
            )}

            {/* Picks List */}
            {recentPicks.length > 0 ? (
              <div className="border-t border-ink-800">
                {recentPicks.map((pick, i) => (
                  <div
                    key={pick.pick_id}
                    className={`px-6 py-3 flex items-start justify-between gap-4 ${
                      i < recentPicks.length - 1 ? "border-b border-ink-800/60" : ""
                    } hover:bg-ink-800/40 transition-colors`}
                  >
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="font-mono text-[11px] text-ink-400 w-12 shrink-0">
                        {pick.event_date ? formatDate(pick.event_date) : "Today"}
                      </div>
                      <div className="text-base w-6 shrink-0 text-center" title={pick.sport}>
                        {SPORT_ICONS[pick.sport] ?? "🏆"}
                      </div>
                      <div className="min-w-0">
                        {pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs) ? (
                          <>
                            <div className="text-white text-sm font-semibold">
                              {pick.pick_detail.legs.length}-Leg Parlay
                            </div>
                            <div className="mt-1 space-y-0.5 pl-3 border-l border-ink-800">
                              {pick.pick_detail.legs.map((leg: any, j: number) => {
                                const text = typeof leg === "string" ? leg : leg.text ?? JSON.stringify(leg);
                                const result = typeof leg === "object" ? leg.result : undefined;
                                return (
                                  <div key={j} className="text-ink-400 text-xs flex items-center gap-1.5">
                                    {result && <LegDot result={result} />}
                                    {text}
                                  </div>
                                );
                              })}
                            </div>
                            {pick.event && (
                              <div className="text-ink-600 text-xs mt-1">{pick.event}</div>
                            )}
                          </>
                        ) : (
                          <>
                            <div className="text-white text-sm font-semibold truncate">
                              {formatPickDetail(pick.pick_type, pick.pick_detail)}
                            </div>
                            <div className="text-ink-600 text-xs truncate">{pick.event}</div>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      {pick.odds && (
                        <span className="font-mono tabular text-ink-400 text-xs">{pick.odds}</span>
                      )}
                      <StatusPill status={pick.status} />
                    </div>
                  </div>
                ))}

                {/* View all link */}
                {activePicks.length > 5 && (
                  <div className="px-6 py-2.5 border-t border-ink-800/60">
                    <Link
                      href={`/creators/${creator.creator_id}`}
                      className="font-mono text-[11px] uppercase tracking-label text-signal hover:text-signal/80 transition-colors"
                    >
                      View all {activePicks.length} active picks →
                    </Link>
                  </div>
                )}
              </div>
            ) : (
              <div className="border-t border-ink-800 px-6 py-6 text-center">
                <p className="text-ink-400 text-sm">No active picks.</p>
              </div>
            )}

            {/* Footer link */}
            {picks.length > 0 && (
              <div className="px-6 py-2.5 border-t border-ink-800/60">
                <Link
                  href={`/creators/${creator.creator_id}`}
                  className="font-mono text-[11px] uppercase tracking-label text-signal hover:text-signal/80 transition-colors"
                >
                  Full history ({picks.length} picks) →
                </Link>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
