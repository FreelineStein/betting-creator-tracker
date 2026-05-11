"use client";

import Link from "next/link";
import { usePostHog } from "posthog-js/react";
import type { Pick, Creator, CreatorRecord } from "../lib/api";
import { StatTile } from "../../components/brand";

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
  SOCCER: "⚽",
  TENNIS: "🎾",
  UFC: "🥊",
  PGA: "⛳",
};

// Banner gradients per dominant sport — sport-tinted, with an amber radial top-left.
const SPORT_BANNER: Record<string, [string, string, string]> = {
  NBA: ["#C2410C", "#E89F35", "#7A4F0F"],
  NFL: ["#15275C", "#1F3A8A", "#0E1A40"],
  CFB: ["#15275C", "#1F3A8A", "#0E1A40"],
  NCAAF: ["#15275C", "#1F3A8A", "#0E1A40"],
  MLB: ["#7A1F1F", "#B45309", "#3F1010"],
  WBC: ["#7A1F1F", "#B45309", "#3F1010"],
  NHL: ["#0F4C75", "#1F6FB8", "#072339"],
  SOCCER: ["#1F5C2E", "#3B8C4E", "#0F2E18"],
  TENNIS: ["#5C7A1F", "#A2C24F", "#3B4F12"],
  UFC: ["#2A1A1F", "#4A2A30", "#1A0E12"],
  PGA: ["#1F4A2F", "#2E6B45", "#0F2A1A"],
  default: ["#1F3A8A", "#2E4A9F", "#15275C"],
};

function bannerFor(sport: string | null): string {
  const [a, b, c] = SPORT_BANNER[sport ?? "default"] ?? SPORT_BANNER.default;
  return `radial-gradient(circle at 22% 50%, rgba(255,179,71,0.22), transparent 60%), linear-gradient(135deg, ${a} 0%, ${b} 50%, ${c} 100%)`;
}

function dominantSport(
  accuracy: Record<string, { wins: number; losses: number }> | null | undefined,
): string | null {
  if (!accuracy) return null;
  let top: string | null = null;
  let max = -1;
  for (const [sport, stats] of Object.entries(accuracy)) {
    const n = (stats.wins ?? 0) + (stats.losses ?? 0);
    if (n > max) {
      max = n;
      top = sport;
    }
  }
  return max > 0 ? top : null;
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

function formatTrackedSince(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  // "Mar '25"
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" }).replace(" ", " '");
}

// All "today" / "last N days" comparisons on the card use America/New_York,
// matching the date formatter elsewhere and the way US sports schedules read.
// Comparing YYYY-MM-DD strings is safe — ISO dates sort chronologically.
function etDateStr(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-CA", { timeZone: "America/New_York" });
}

function shiftET(daysOffset: number): string {
  return new Date(Date.now() + daysOffset * 86_400_000).toLocaleDateString(
    "en-CA",
    { timeZone: "America/New_York" },
  );
}

function earliestLoggedAt(picks: Pick[]): string | null {
  let earliest: number | null = null;
  let earliestIso: string | null = null;
  for (const p of picks) {
    if (!p.logged_at) continue;
    const t = new Date(p.logged_at).getTime();
    if (Number.isNaN(t)) continue;
    if (earliest === null || t < earliest) {
      earliest = t;
      earliestIso = p.logged_at;
    }
  }
  return earliestIso;
}

type Streak = { kind: "win" | "loss"; count: number } | null;

function computeStreak(picks: Pick[]): Streak {
  const resolved = picks
    .filter((p) => p.status === "won" || p.status === "lost")
    .slice()
    .sort(
      (a, b) =>
        new Date(b.event_date ?? b.logged_at).getTime() -
        new Date(a.event_date ?? a.logged_at).getTime(),
    );
  if (resolved.length === 0) return null;
  const kind = resolved[0].status === "won" ? "win" : "loss";
  let count = 0;
  for (const p of resolved) {
    const matches = (kind === "win" && p.status === "won") || (kind === "loss" && p.status === "lost");
    if (!matches) break;
    count++;
  }
  return { kind, count };
}

function StreakChip({ streak }: { streak: NonNullable<Streak> }) {
  const isWin = streak.kind === "win";
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-label"
      style={{
        background: "rgba(20,19,15,0.45)",
        border: "1px solid rgba(255,255,255,0.12)",
        backdropFilter: "blur(8px)",
        color: "rgba(245,242,236,0.95)",
      }}
    >
      <span
        className="inline-block rounded-full"
        style={{
          width: 6,
          height: 6,
          background: isWin ? "#FFB347" : "#A8A096",
          boxShadow: isWin ? "0 0 0 4px rgba(255,179,71,0.30)" : "none",
        }}
      />
      {isWin ? "W" : "L"}
      {streak.count}
    </span>
  );
}

function StatusPill({ status }: { status: string }) {
  // Lowercase intentional — the color carries weight.
  if (status === "won") {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold tracking-label bg-amber-dim text-amber-deep border border-amber-deep/30">
        won
      </span>
    );
  }
  if (status === "lost") {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold tracking-label bg-stone-dim text-ink-500 border border-transparent">
        lost
      </span>
    );
  }
  if (status === "push") {
    return (
      <span className="inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold tracking-label bg-paper-2 text-ink-500 border border-rule">
        push
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold tracking-label text-ink-500 border border-dashed border-rule">
      {status}
    </span>
  );
}

function LegDot({ result }: { result: string }) {
  const cls =
    result === "won"
      ? "bg-amber"
      : result === "lost"
        ? "bg-stone"
        : result === "push"
          ? "bg-ink-300"
          : "bg-ink-300/40";
  return <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${cls}`} />;
}

function Avatar({ creator }: { creator: Creator }) {
  if (creator.profile_image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={creator.profile_image_url}
        alt={creator.display_name}
        className="w-[52px] h-[52px] rounded-[12px] object-cover shadow-avatar shrink-0"
      />
    );
  }
  return (
    <div
      className="w-[52px] h-[52px] rounded-[12px] bg-amber text-ink flex items-center justify-center font-display font-extrabold text-[22px] shadow-avatar shrink-0"
      aria-hidden="true"
    >
      {creator.display_name.charAt(0).toUpperCase()}
    </div>
  );
}

interface CreatorCardData {
  creator: Creator;
  record: CreatorRecord | null;
  picks: Pick[];
}

export default function CreatorCards({ creators }: { creators: CreatorCardData[] }) {
  const posthog = usePostHog();
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {creators.map(({ creator, record, picks }) => {
        const sport = dominantSport(record?.accuracy_by_sport);
        const trackedSince = formatTrackedSince(earliestLoggedAt(picks));
        // Card shows up to 3 picks total: active picks first (pending,
        // event today-or-future, soonest first), then back-fill with
        // resolved picks from the last 2 days (today + prior 2, most-recent
        // first). Past-but-still-pending picks are deliberately excluded —
        // the creator detail page already lists them in Pick History.
        const todayET = shiftET(0);
        const historyCutoffET = shiftET(-2);
        const activePicks = picks
          .filter((p) => {
            if (p.status !== "pending") return false;
            const d = etDateStr(p.event_date);
            return d !== null && d >= todayET;
          })
          .slice()
          .sort(
            (a, b) =>
              new Date(a.event_date).getTime() - new Date(b.event_date).getTime(),
          );
        const recentHistory = picks
          .filter((p) => {
            if (p.status === "pending") return false;
            const d = etDateStr(p.event_date);
            return d !== null && d >= historyCutoffET && d < todayET;
          })
          .slice()
          .sort(
            (a, b) =>
              new Date(b.event_date).getTime() - new Date(a.event_date).getTime(),
          );
        const recentPicks = [...activePicks, ...recentHistory].slice(0, 3);
        const streak = computeStreak(picks);
        const hasRecord = record !== null && record.total_picks > 0;
        const winRatePct = hasRecord ? Math.round((record as CreatorRecord).win_rate * 100) : null;

        return (
          <Link
            key={creator.creator_id}
            href={`/creators/${creator.creator_id}`}
            onClick={() =>
              posthog?.capture("creator_card_clicked", {
                creator_id: creator.creator_id,
                creator_name: creator.display_name,
                source: "card_body",
              })
            }
            className="group flex flex-col h-full bg-paper-2 rounded-card border border-rule shadow-card overflow-hidden transition-colors"
          >
            {/* Banner */}
            <div
              className="relative h-[110px] border-b border-rule"
              style={{ background: bannerFor(sport) }}
            >
              {/* 45° pinstripe overlay */}
              <div
                aria-hidden="true"
                className="absolute inset-0"
                style={{
                  backgroundImage:
                    "repeating-linear-gradient(45deg, transparent 0 8px, rgba(255,255,255,0.05) 8px 9px)",
                }}
              />
              {/* Bottom-darken — guarantees the inset white name reads on every sport gradient */}
              <div
                aria-hidden="true"
                className="absolute inset-0"
                style={{
                  background: "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.20) 100%)",
                }}
              />

              {/* Tracked-since stamp */}
              {trackedSince && (
                <span
                  className="absolute top-[14px] left-[18px] z-[1] inline-flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-label whitespace-nowrap"
                  style={{ color: "rgba(245,242,236,0.85)" }}
                >
                  <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
                    <path
                      d="M6 1l1.5 3 3.3.5-2.4 2.3.6 3.3L6 8.5 3 10.1l.6-3.3L1.2 4.5 4.5 4 6 1z"
                      fill="#FFB347"
                    />
                  </svg>
                  Tracked since {trackedSince}
                </span>
              )}

              {/* Streak chip */}
              {streak && streak.count > 0 && (
                <span className="absolute top-[12px] right-[14px] z-[1]">
                  <StreakChip streak={streak} />
                </span>
              )}

              {/* Inset avatar + name + handles */}
              <div className="absolute left-[18px] right-[14px] bottom-[12px] z-[1] flex items-end gap-3">
                <Avatar creator={creator} />
                <div className="min-w-0 pb-0.5">
                  <div
                    className="font-display font-extrabold text-[19px] leading-[1.05] tracking-tight"
                    style={{
                      color: "#F5F2EC",
                      textShadow: "0 1px 2px rgba(0,0,0,0.30)",
                    }}
                  >
                    {creator.display_name}
                  </div>
                  <div className="flex flex-wrap gap-2.5 mt-1">
                    {creator.platforms.map((p) => (
                      <span
                        key={p.platform}
                        className="font-mono text-[11px]"
                        style={{ color: "rgba(245,242,236,0.78)" }}
                      >
                        {PLATFORM_ICONS[p.platform] ?? "🔗"} {p.handle}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Body */}
            <div className="flex-1 px-[22px] pt-4 pb-[18px]">
              {hasRecord && (
                <div className="grid grid-cols-3 gap-2">
                  <StatTile
                    label="Record"
                    value={`${(record as CreatorRecord).wins}–${(record as CreatorRecord).losses}`}
                  />
                  <StatTile
                    label="Win %"
                    value={`${winRatePct}%`}
                    tone={winRatePct !== null && winRatePct >= 55 ? "positive" : "default"}
                  />
                  <StatTile
                    label="ROI"
                    value={`${(record as CreatorRecord).roi >= 0 ? "+" : ""}${(record as CreatorRecord).roi}%`}
                    tone={(record as CreatorRecord).roi >= 0 ? "positive" : "default"}
                  />
                </div>
              )}

              {recentPicks.length > 0 && (
                <div className={hasRecord ? "mt-4" : ""}>
                  {recentPicks.map((pick, i) => {
                    const isParlay =
                      pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs);
                    const legs = isParlay ? (pick.pick_detail.legs as unknown as any[]) : [];
                    return (
                      <div
                        key={pick.pick_id}
                        className={`flex items-start justify-between gap-3 py-2.5 text-[13px] text-ink ${
                          i > 0 || hasRecord ? "border-t border-rule" : ""
                        }`}
                      >
                        <div className="flex items-start gap-2.5 min-w-0">
                          <span className="font-mono text-[11px] text-ink-500 w-11 shrink-0 pt-0.5">
                            {pick.event_date ? formatDate(pick.event_date) : "Today"}
                          </span>
                          <span
                            className="text-[14px] w-5 shrink-0 text-center pt-0.5"
                            title={pick.league ?? pick.sport}
                          >
                            {SPORT_ICONS[pick.sport] ?? "🏆"}
                          </span>
                          <div className="min-w-0">
                            {isParlay ? (
                              <>
                                <div className="font-semibold text-ink">
                                  {legs.length}-Leg Parlay
                                </div>
                                <div className="mt-0.5 space-y-0.5 pl-2 border-l border-rule">
                                  {legs.map((leg: any, j: number) => {
                                    const text =
                                      typeof leg === "string"
                                        ? leg
                                        : leg.text ?? JSON.stringify(leg);
                                    const result =
                                      typeof leg === "object" ? leg.result : undefined;
                                    return (
                                      <div
                                        key={j}
                                        className="text-ink-500 text-[11px] flex items-center gap-1.5"
                                      >
                                        {result && <LegDot result={result} />}
                                        <span>{text}</span>
                                      </div>
                                    );
                                  })}
                                </div>
                              </>
                            ) : (
                              <>
                                <div className="font-semibold text-ink truncate">
                                  {formatPickDetail(pick.pick_type, pick.pick_detail)}
                                </div>
                                {pick.event && (
                                  <div className="text-ink-500 text-[12px] truncate">
                                    · {pick.event}
                                  </div>
                                )}
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-2.5 shrink-0 pt-0.5">
                          {pick.odds && (
                            <span className="font-mono text-[11px] text-ink-500">
                              {pick.odds}
                            </span>
                          )}
                          <StatusPill status={pick.status} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="bg-paper border-t border-rule-soft px-[22px] py-3 mt-auto">
              <span className="font-mono text-[11px] font-medium uppercase tracking-label text-ink-700 group-hover:text-ink transition-colors">
                Full record ({record?.total_picks ?? picks.length} picks) →
              </span>
            </div>
          </Link>
        );
      })}
    </div>
  );
}
