/**
 * Pick formatting and record arithmetic shared by the standings, the creator
 * game log and the submit panel. Dates and "today" are Eastern time, the way
 * US sports schedules read.
 */
import type { Pick } from "./api";

export const BREAK_EVEN_PCT = 52.4;

const ET = "America/New_York";

const SPORT_LABEL: Record<string, string> = {
  NFL: "NFL",
  CFB: "CFB",
  NCAAF: "CFB",
  NBA: "NBA",
  CBB: "CBB",
  NCAAB: "CBB",
  WNBA: "WNBA",
  MLB: "MLB",
  WBC: "WBC",
  NHL: "NHL",
  SOCCER: "SOC",
  TENNIS: "TEN",
  UFC: "UFC",
  PGA: "PGA",
};

export function sportLabel(p: { sport: string | null; league?: string | null }): string {
  if (!p.sport) return "—";
  if (p.sport === "SOCCER" && p.league && p.league.length <= 8) return p.league.toUpperCase();
  return SPORT_LABEL[p.sport] ?? p.sport;
}

export type Leg = {
  text?: string;
  type?: string;
  detail?: Record<string, unknown>;
  sport?: string;
  league?: string;
  event?: string;
  result?: string;
};

export function formatPickDetail(type: string, detail: Record<string, unknown> | undefined): string {
  const d = detail ?? {};
  switch (type) {
    case "spread":
      return `${d.team ?? ""} ${d.line ?? ""}`.trim();
    case "moneyline":
      return `${d.team ?? ""} ML`.trim();
    case "over_under":
      return `${d.direction ?? "Over"} ${d.total ?? ""}`.trim();
    case "prop": {
      const prop = String(d.prop ?? "").replace(/^no\s+run\b/i, "Runs");
      return `${d.player ?? ""} ${d.direction ?? "Over"} ${d.line ?? ""} ${prop}`
        .replace(/\s+/g, " ")
        .trim();
    }
    case "parlay":
      return `${parlayLegs(d).length}-leg parlay`;
    default:
      return type;
  }
}

export function parlayLegs(detail: Record<string, unknown> | undefined): Leg[] {
  const raw = (detail?.legs as unknown[] | undefined) ?? [];
  return raw.map((leg) => (typeof leg === "string" ? { text: leg } : (leg as Leg)));
}

export function legText(leg: Leg): string {
  if (leg.text) return leg.text;
  if (leg.type) return formatPickDetail(leg.type, leg.detail);
  return "leg";
}

export function formatDateET(iso: string | null | undefined, withYear = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: withYear ? "numeric" : undefined,
    timeZone: ET,
  });
}

export function formatTimeET(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: ET });
}

export function formatDatelineET(date = new Date()): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: ET,
  });
}

/** YYYY-MM-DD in ET; safe to compare as strings. */
export function etDateStr(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-CA", { timeZone: ET });
}

export function shiftET(daysOffset: number): string {
  return new Date(Date.now() + daysOffset * 86_400_000).toLocaleDateString("en-CA", {
    timeZone: ET,
  });
}

export function formatTrackedSince(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
}

export function earliestLoggedAt(picks: Pick[]): string | null {
  let earliest: number | null = null;
  let iso: string | null = null;
  for (const p of picks) {
    if (!p.logged_at) continue;
    const t = new Date(p.logged_at).getTime();
    if (Number.isNaN(t)) continue;
    if (earliest === null || t < earliest) {
      earliest = t;
      iso = p.logged_at;
    }
  }
  return iso;
}

export function dominantSport(
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

export type Settled = "won" | "lost" | "push";

export function isSettled(p: Pick): p is Pick & { status: Settled } {
  return p.status === "won" || p.status === "lost" || p.status === "push";
}

function eventTime(p: Pick): number {
  const t = new Date(p.event_date ?? p.logged_at).getTime();
  return Number.isNaN(t) ? 0 : t;
}

/** Settled picks, newest first. */
export function settledNewestFirst(picks: Pick[]): (Pick & { status: Settled })[] {
  return picks
    .filter(isSettled)
    .slice()
    .sort((a, b) => eventTime(b) - eventTime(a));
}

export type Streak = { kind: "W" | "L"; count: number } | null;

export function computeStreak(picks: Pick[]): Streak {
  const resolved = settledNewestFirst(picks).filter((p) => p.status !== "push");
  if (resolved.length === 0) return null;
  const kind = resolved[0].status === "won" ? "W" : "L";
  let count = 0;
  for (const p of resolved) {
    const match = (kind === "W" && p.status === "won") || (kind === "L" && p.status === "lost");
    if (!match) break;
    count++;
  }
  return { kind, count };
}

/** Last n settled results, oldest first (so a strip reads left to right). */
export function lastResults(picks: Pick[], n = 5): Settled[] {
  return settledNewestFirst(picks)
    .slice(0, n)
    .map((p) => p.status)
    .reverse();
}

/** Pending picks whose game is today or later (ET), soonest first. */
export function activePicks(picks: Pick[]): Pick[] {
  const today = shiftET(0);
  return picks
    .filter((p) => {
      if (p.status !== "pending") return false;
      const d = etDateStr(p.event_date);
      return d !== null && d >= today;
    })
    .slice()
    .sort((a, b) => eventTime(a) - eventTime(b));
}

/** Settled picks from the last `daysBack` days through today (ET), newest first. */
export function recentSettled(picks: Pick[], daysBack = 2): (Pick & { status: Settled })[] {
  const cutoff = shiftET(-daysBack);
  return settledNewestFirst(picks).filter((p) => {
    const d = etDateStr(p.event_date);
    return d !== null && d >= cutoff;
  });
}

export function roiText(roi: number): string {
  return `${roi >= 0 ? "+" : ""}${roi}%`;
}

export function pctValue(winRate: number | null | undefined, totalPicks: number): number | null {
  if (!totalPicks || winRate === null || winRate === undefined) return null;
  return Math.round(winRate * 1000) / 10;
}
