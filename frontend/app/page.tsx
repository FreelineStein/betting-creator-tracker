import Link from "next/link";
import { getAllCreatorsWithRecords, getCreatorPicks } from "./lib/api";
import type { Creator, CreatorRecord, Pick } from "./lib/api";
import {
  activePicks,
  computeStreak,
  formatPickDetail,
  lastResults,
  legText,
  parlayLegs,
  pctValue,
  recentSettled,
  settledNewestFirst,
  sportLabel,
} from "./lib/picks";
import HomeBoard, { type BoxLine, type Division, type PickLite, type StandingsRow } from "./components/HomeBoard";
import { SectionBar, Standfirst } from "../components/brand";

const FEATURED_CREATOR_NAMES = ["Trent", "DanAI", "Dr. Locks", "Harry Locks", "Gavin"];

function toLite(p: Pick): PickLite {
  const isParlay = p.pick_type === "parlay";
  const legs = isParlay
    ? parlayLegs(p.pick_detail as Record<string, unknown>).map((leg) => ({
        text: legText(leg),
        event: leg.event,
        result: leg.result,
      }))
    : null;
  return {
    id: p.pick_id,
    date: p.event_date ?? null,
    sport: sportLabel(p),
    title: formatPickDetail(p.pick_type, p.pick_detail as Record<string, unknown>),
    event: p.event || null,
    odds: p.odds || null,
    status: p.status,
    legs,
  };
}

function toRow(creator: Creator, record: CreatorRecord | null, picks: Pick[]): StandingsRow {
  const wins = record?.wins ?? 0;
  const losses = record?.losses ?? 0;
  const pushes = record?.pushes ?? 0;
  const total = record?.total_picks ?? picks.length;
  const settled = settledNewestFirst(picks);
  const recent = [...activePicks(picks), ...recentSettled(picks, 2)].slice(0, 3).map(toLite);
  return {
    id: creator.creator_id,
    name: creator.display_name,
    handles: creator.platforms,
    gp: wins + losses,
    wins,
    losses,
    pushes,
    pct: pctValue(record?.win_rate, wins + losses),
    roi: record && total > 0 ? record.roi : null,
    streak: computeStreak(picks),
    last5: lastResults(picks, 5),
    last: settled[0] ? toLite(settled[0]) : null,
    recent,
    total,
    allSettled: settled.slice(0, 14).map(toLite),
  };
}

function byStandings(a: StandingsRow, b: StandingsRow): number {
  if (a.pct === null && b.pct === null) return b.total - a.total;
  if (a.pct === null) return 1;
  if (b.pct === null) return -1;
  if (b.pct !== a.pct) return b.pct - a.pct;
  return b.gp - a.gp;
}

export default async function Home() {
  let data: Awaited<ReturnType<typeof getAllCreatorsWithRecords>> = [];
  let error = false;

  try {
    data = await getAllCreatorsWithRecords();
  } catch {
    error = true;
  }

  const featured: StandingsRow[] = [];
  const lesserKnown: StandingsRow[] = [];
  const settledLines: BoxLine[] = [];
  const onDeckLines: BoxLine[] = [];

  if (!error && data.length > 0) {
    const seen = new Set<string>();
    for (const { creator, record } of data) {
      if (seen.has(creator.creator_id)) continue;
      seen.add(creator.creator_id);

      let picks: Pick[] = [];
      try {
        picks = await getCreatorPicks(creator.creator_id);
      } catch {
        // continue with empty picks
      }

      const row = toRow(creator, record, picks);
      (FEATURED_CREATOR_NAMES.includes(creator.display_name) ? featured : lesserKnown).push(row);

      for (const p of recentSettled(picks, 2)) {
        settledLines.push({ ...toLite(p), creatorId: creator.creator_id, creatorName: creator.display_name });
      }
      for (const p of activePicks(picks)) {
        onDeckLines.push({ ...toLite(p), creatorId: creator.creator_id, creatorName: creator.display_name });
      }
    }
  }

  featured.sort(byStandings);
  lesserKnown.sort(byStandings);
  settledLines.sort((a, b) => new Date(b.date ?? 0).getTime() - new Date(a.date ?? 0).getTime());
  onDeckLines.sort((a, b) => new Date(a.date ?? 0).getTime() - new Date(b.date ?? 0).getTime());

  // Quiet stretch (no games settled in the last two days): show the latest
  // settled picks instead of an empty column, and say so in the heading.
  const settledIsRecent = settledLines.length > 0;
  if (!settledIsRecent) {
    const perCreator = 3;
    for (const row of [...featured, ...lesserKnown]) {
      for (const p of row.allSettled.slice(0, perCreator)) {
        settledLines.push({ ...p, creatorId: row.id, creatorName: row.name });
      }
    }
    settledLines.sort((a, b) => new Date(b.date ?? 0).getTime() - new Date(a.date ?? 0).getTime());
  }

  const divisions: Division[] = [
    { id: "i", title: "Division I · Popular creators", rows: featured },
    { id: "ii", title: "Division II · Lesser known", rows: lesserKnown },
  ].filter((d) => d.rows.length > 0);

  const hasAnyCreators = divisions.length > 0;

  return (
    <div>
      <section>
        <h1 className="font-display text-[clamp(46px,8.4vw,108px)] font-bold uppercase leading-[0.9] tracking-[-0.015em] text-ink text-balance">
          Every pick. Every loss. On the record.
        </h1>
        <Standfirst className="mt-5">
          Creators&apos; publicly posted picks, settled against final scores and box scores. Find
          who is actually worth tailing before you tail.
        </Standfirst>
      </section>

      {error && (
        <div className="mt-10 border-y-2 border-ink py-4 text-[15px] text-ink-2">
          <p className="font-semibold text-ink">Could not reach the record.</p>
          <p>Try again in a minute.</p>
          {process.env.NODE_ENV === "development" && (
            <p className="mt-2 text-[13px] text-ink-3">
              Development: make sure the backend is running or NEXT_PUBLIC_API_URL points at it.
            </p>
          )}
        </div>
      )}

      {!error && !hasAnyCreators && (
        <p className="mt-10 border-y-2 border-ink py-4 text-[15px] text-ink-2">
          No creators on the record yet.{" "}
          <Link href="/submit" className="rule-link font-semibold text-ink">
            Submit the first pick.
          </Link>
        </p>
      )}

      {!error && hasAnyCreators && (
        <HomeBoard
          divisions={divisions}
          settled={settledLines.slice(0, 14)}
          settledLabel={settledIsRecent ? "Settled, last two days" : "Latest settled"}
          onDeck={onDeckLines.slice(0, 14)}
        />
      )}

      <section className="mt-20" aria-labelledby="how-heading">
        <SectionBar>
          <span id="how-heading">How the record is kept</span>
        </SectionBar>
        <div className="grid grid-cols-1 border-b border-ink sm:grid-cols-3 sm:divide-x sm:divide-rule">
          {[
            {
              head: "Capture.",
              body: "Picks come from creators' public posts on X. Anyone can submit a post; it is fetched live and the picks are read out of the text and images.",
            },
            {
              head: "Settle.",
              body: "Once the game ends, every pick is checked against final scores and box scores: spreads, moneylines, totals, props, and parlays leg by leg.",
            },
            {
              head: "Record.",
              body: "Wins, losses and pushes add up to the standings. ROI is measured against the −110 break-even line, a 52.4% win rate.",
            },
          ].map((step) => (
            <p
              key={step.head}
              className="py-4 text-[15px] leading-[1.5] text-ink-2 sm:px-5 sm:first:pl-0 sm:last:pr-0"
            >
              <strong className="font-bold text-ink">{step.head}</strong> {step.body}
            </p>
          ))}
        </div>
      </section>
    </div>
  );
}
