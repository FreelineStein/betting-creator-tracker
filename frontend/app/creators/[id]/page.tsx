import Link from "next/link";
import { getCreator, getCreatorRecord, getCreatorPicks } from "../../lib/api";
import type { Creator, Pick } from "../../lib/api";
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

function formatTrackedSince(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" }).replace(" ", " '");
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

function StatusBadge({ status }: { status: Pick["status"] }) {
  if (status === "won") return <Badge variant="win">won</Badge>;
  if (status === "lost") return <Badge variant="loss">lost</Badge>;
  if (status === "push") return <Badge variant="push">push</Badge>;
  return <Badge variant="pending">{status}</Badge>;
}

function formatPickDetail(type: string, detail: Record<string, string | number>): string {
  if (type === "spread") return `${detail.team} ${detail.line}`;
  if (type === "moneyline") return `${detail.team} ML`;
  if (type === "over_under") return `${detail.direction} ${detail.total}`;
  if (type === "prop") {
    const prop = String(detail.prop ?? "").replace(/^no\s+run\b/i, "Runs");
    return `${detail.player ?? ""} ${detail.direction ?? "Over"} ${detail.line ?? ""} ${prop}`.replace(/\s+/g, " ").trim();
  }
  return JSON.stringify(detail);
}

function formatDate(dateStr: string, withYear = false): string {
  return new Date(dateStr).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: withYear ? "numeric" : undefined,
    timeZone: "America/New_York",
  });
}

function Avatar({ creator }: { creator: Creator }) {
  if (creator.profile_image_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={creator.profile_image_url}
        alt={creator.display_name}
        className="w-[68px] h-[68px] rounded-[14px] object-cover shadow-avatar shrink-0"
      />
    );
  }
  return (
    <div
      className="w-[68px] h-[68px] rounded-[14px] bg-amber text-ink flex items-center justify-center font-display font-extrabold text-[28px] shadow-avatar shrink-0"
      aria-hidden="true"
    >
      {creator.display_name.charAt(0).toUpperCase()}
    </div>
  );
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
      <div className="rounded-[10px] border border-rule bg-paper-2 p-4 text-ink-700 text-sm">
        Could not load creator. Make sure the backend is running.
      </div>
    );
  }

  const hasPicks = record.total_picks > 0;
  const winRatePct = hasPicks ? Math.round(record.win_rate * 100) : 0;
  const sport = dominantSport(record.accuracy_by_sport);
  const trackedSince = formatTrackedSince(earliestLoggedAt(picks));
  const streak = computeStreak(picks);

  const sports = Object.entries(record.accuracy_by_sport || {}).sort(
    ([, a], [, b]) => b.wins + b.losses - (a.wins + a.losses),
  );

  // "Today" boundary in ET, since US sports schedules read in ET and the
  // formatter elsewhere on this page also pins to America/New_York.
  // Comparing YYYY-MM-DD strings is safe — ISO dates sort chronologically.
  const todayET = new Date().toLocaleDateString("en-CA", {
    timeZone: "America/New_York",
  });
  function isTodayOrFutureET(iso: string | null): boolean {
    if (!iso) return false;
    const d = new Date(iso).toLocaleDateString("en-CA", {
      timeZone: "America/New_York",
    });
    return d >= todayET;
  }

  // Active = pending AND event hasn't fallen into the past (ET). A pending
  // pick whose game already happened belongs in history; either the resolver
  // hasn't caught it yet or it's structurally unresolvable.
  const pendingPicks = picks.filter(
    (p) => p.status === "pending" && isTodayOrFutureET(p.event_date),
  );
  const historyPicks = picks
    .filter(
      (p) => p.status !== "pending" || !isTodayOrFutureET(p.event_date),
    )
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
        className="font-mono text-[11px] uppercase tracking-label-x font-medium text-ink-500 hover:text-ink transition-colors mb-6 inline-block"
      >
        ← Leaderboard
      </Link>

      {/* Hero banner */}
      <div className="bg-paper-2 rounded-card border border-rule shadow-card overflow-hidden mb-8">
        <div
          className="relative h-[150px] border-b border-rule"
          style={{ background: bannerFor(sport) }}
        >
          <div
            aria-hidden="true"
            className="absolute inset-0"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, transparent 0 8px, rgba(255,255,255,0.05) 8px 9px)",
            }}
          />
          <div
            aria-hidden="true"
            className="absolute inset-0"
            style={{
              background: "linear-gradient(180deg, transparent 0%, rgba(0,0,0,0.20) 100%)",
            }}
          />

          {trackedSince && (
            <span
              className="absolute top-4 left-5 z-[1] inline-flex items-center gap-1.5 font-mono text-[10px] font-medium uppercase tracking-label whitespace-nowrap"
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

          {streak && streak.count > 0 && (
            <span className="absolute top-3.5 right-[18px] z-[1]">
              <StreakChip streak={streak} />
            </span>
          )}

          <div className="absolute left-6 right-5 bottom-[18px] z-[1] flex items-end gap-4">
            <Avatar creator={creator} />
            <div className="min-w-0 pb-1">
              <h1
                className="font-display font-extrabold text-[32px] leading-[1.05] tracking-display"
                style={{ color: "#F5F2EC", textShadow: "0 2px 4px rgba(0,0,0,0.35)" }}
              >
                {creator.display_name}
              </h1>
              <div className="flex flex-wrap gap-3 mt-1.5">
                {creator.platforms.map((p) => (
                  <a
                    key={p.platform}
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-[12px] hover:underline"
                    style={{ color: "rgba(245,242,236,0.78)" }}
                  >
                    {PLATFORM_ICONS[p.platform] ?? "🔗"} {p.handle}
                  </a>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stat cards */}
      {hasPicks ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 mb-8">
          <StatCard
            label="Record"
            value={<WLRecord w={record.wins} l={record.losses} size="lg" />}
            sub={record.pushes > 0 ? `${record.pushes} push${record.pushes === 1 ? "" : "es"}` : "All-time"}
          />
          <StatCard
            label="Win Rate"
            value={`${winRatePct}%`}
            tone={winRatePct >= 55 ? "positive" : "default"}
            sub="Verified picks"
          />
          <StatCard
            label="ROI"
            value={`${record.roi >= 0 ? "+" : ""}${record.roi}%`}
            tone={record.roi >= 0 ? "positive" : "default"}
            sub="vs −110 break-even"
          />
          <StatCard label="Total Picks" value={record.total_picks} sub="All-time tracked" />
        </div>
      ) : (
        <div className="rounded-[14px] border border-rule bg-paper-2 p-6 mb-8 text-center shadow-card">
          <p className="text-ink-500">Tracking started — picks will appear as they&apos;re posted.</p>
        </div>
      )}

      {/* By Sport */}
      {sports.length > 0 && (
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-3">
            By Sport
          </div>
          <div className="flex flex-wrap gap-2.5">
            {sports.map(([sportKey, stats]) => {
              const total = stats.wins + stats.losses;
              const wr = total > 0 ? Math.round((stats.wins / total) * 100) : 0;
              const wrColor = wr >= 55 ? "text-amber-deep" : "text-ink-500";
              return (
                <div
                  key={sportKey}
                  className="bg-paper-2 border border-rule rounded-[10px] px-3.5 py-2 flex items-center gap-3"
                >
                  <span className="font-display font-extrabold text-sm tracking-tight text-ink">
                    {SPORT_ICONS[sportKey] ?? ""} {sportKey}
                  </span>
                  <WLRecord w={stats.wins} l={stats.losses} size="sm" />
                  <span className={`font-mono tabular text-xs font-semibold ${wrColor}`}>
                    {wr}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Active picks */}
      {pendingPicks.length > 0 && (
        <div className="mb-8">
          <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-700 mb-1.5 flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-amber pulse-amber" />
            Active Picks ({pendingPicks.length})
          </div>
          <p className="text-xs text-ink-500 mb-3">
            Picks settle within ~15 minutes after the game ends.
          </p>
          <div className="space-y-2">
            {pendingPicks.map((pick) => (
              <PickRow key={pick.pick_id} pick={pick} />
            ))}
          </div>
        </div>
      )}

      {/* Pick history */}
      <div>
        <div className="font-mono text-[10px] uppercase tracking-label-x font-medium text-ink-500 mb-3">
          Pick History
        </div>
        {historyPicks.length === 0 ? (
          <p className="text-ink-500 text-sm">No resolved picks yet.</p>
        ) : (
          <div className="bg-paper-2 rounded-[14px] border border-rule shadow-card overflow-hidden">
            <div className="grid grid-cols-12 px-4 py-3 font-mono text-[9px] uppercase tracking-label-x font-medium text-ink-500 border-b border-rule bg-paper-3">
              <div className="col-span-2">Date</div>
              <div className="col-span-1">Sport</div>
              <div className="col-span-5">Pick</div>
              <div className="col-span-2">Odds</div>
              <div className="col-span-2">Result</div>
            </div>
            {historyPicks.map((pick) => (
              <div
                key={pick.pick_id}
                className="grid grid-cols-12 px-4 py-3 border-b border-rule last:border-0 text-sm items-center text-ink"
              >
                <div className="col-span-2 font-mono text-[11px] text-ink-500">
                  {pick.event_date ? formatDate(pick.event_date, true) : "—"}
                </div>
                <div className="col-span-1 text-base" title={pick.league ?? pick.sport}>
                  {SPORT_ICONS[pick.sport] ?? pick.sport}
                </div>
                <div className="col-span-5">
                  {pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs) ? (
                    <>
                      <div className="font-semibold">
                        {pick.pick_detail.legs.length}-Leg Parlay
                      </div>
                      <div className="mt-1 space-y-0.5 pl-3 border-l border-rule">
                        {pick.pick_detail.legs.map((leg: any, j: number) => {
                          const text = typeof leg === "string" ? leg : leg.text ?? JSON.stringify(leg);
                          const result = typeof leg === "object" ? leg.result : undefined;
                          const legEvent = typeof leg === "object" ? leg.event : undefined;
                          return (
                            <div
                              key={j}
                              className="text-ink-500 text-xs flex items-center gap-1.5"
                            >
                              {result && <LegDot result={result} />}
                              <span>{text}</span>
                              {legEvent && <span className="text-ink-300">· {legEvent}</span>}
                            </div>
                          );
                        })}
                      </div>
                      {pick.event && (
                        <div className="text-xs text-ink-500 mt-1">
                          {pick.league ? `${pick.league} · ` : ""}
                          {pick.event}
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="font-semibold">
                        {formatPickDetail(pick.pick_type, pick.pick_detail)}
                      </span>
                      {pick.event && (
                        <span className="text-xs text-ink-500 ml-2">{pick.event}</span>
                      )}
                    </>
                  )}
                </div>
                <div className="col-span-2 font-mono tabular text-xs text-ink-500">
                  {pick.odds}
                </div>
                <div className="col-span-2">
                  <StatusBadge status={pick.status} />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PickRow({ pick }: { pick: Pick }) {
  return (
    <div className="bg-paper-2 border border-rule rounded-[10px] px-4 py-3 flex items-center justify-between shadow-card">
      <div>
        {pick.pick_type === "parlay" && Array.isArray(pick.pick_detail.legs) ? (
          <>
            <div className="text-ink font-semibold">
              {SPORT_ICONS[pick.sport] ?? ""} {pick.pick_detail.legs.length}-Leg Parlay
            </div>
            <div className="mt-1 space-y-0.5 pl-3 border-l border-rule">
              {pick.pick_detail.legs.map((leg: any, j: number) => {
                const text = typeof leg === "string" ? leg : leg.text ?? JSON.stringify(leg);
                const result = typeof leg === "object" ? leg.result : undefined;
                const legEvent = typeof leg === "object" ? leg.event : undefined;
                return (
                  <div key={j} className="text-ink-500 text-xs flex items-center gap-1.5">
                    {result && <LegDot result={result} />}
                    <span>{text}</span>
                    {legEvent && <span className="text-ink-300">· {legEvent}</span>}
                  </div>
                );
              })}
            </div>
            <div className="text-ink-500 text-xs mt-1">
              {pick.league ?? pick.sport}
              {pick.event ? ` · ${pick.event}` : ""}
            </div>
          </>
        ) : (
          <>
            <div className="text-ink font-semibold">
              {SPORT_ICONS[pick.sport] ?? ""} {formatPickDetail(pick.pick_type, pick.pick_detail)}
            </div>
            <div className="text-ink-500 text-xs mt-0.5">
              {pick.league ?? pick.sport} · {pick.event}
            </div>
          </>
        )}
      </div>
      <div className="flex items-center gap-3 text-sm">
        {pick.event_date && (
          <span className="font-mono text-[11px] text-ink-500">{formatDate(pick.event_date)}</span>
        )}
        <span className="font-mono tabular text-ink-500">{pick.odds}</span>
        <Badge variant="pending">pending</Badge>
      </div>
    </div>
  );
}
