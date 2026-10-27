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
import { Lede, SectionHead } from "../components/brand";

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
  const fresh = [...activePicks(picks), ...recentSettled(picks, 2)];
  // Quiet stretch: fall back to the latest settled picks rather than an empty list.
  const recent = (fresh.length > 0 ? fresh : settled).slice(0, 3).map(toLite);
  return {
    id: creator.creator_id,
    name: creator.display_name,
    img: creator.profile_image_url ?? null,
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
    { id: "i", title: "Division I", subtitle: "Popular creators", rows: featured },
    { id: "ii", title: "Division II", subtitle: "Lesser known", rows: lesserKnown },
  ].filter((d) => d.rows.length > 0);

  const hasAnyCreators = divisions.length > 0;

  return (
    <div>
      <section>
        <h1 className="font-display text-[clamp(40px,5.6vw,68px)] font-extrabold uppercase leading-[0.98] text-fg text-balance">
          Every pick. Every loss. <span className="text-win">On the record.</span>
        </h1>
        <Lede className="mt-4">
          Creators&apos; publicly posted picks, settled against final scores and box scores. See
          who is actually worth tailing before you tail.
        </Lede>
      </section>

      {error && (
        <div className="mt-10 rounded-card border border-line bg-panel px-5 py-4 text-[15px] text-fg-2">
          <p className="font-semibold text-fg">Could not reach the record.</p>
          <p>Try again in a minute.</p>
          {process.env.NODE_ENV === "development" && (
            <p className="mt-2 text-[13px] text-fg-3">
              Development: make sure the backend is running or NEXT_PUBLIC_API_URL points at it.
            </p>
          )}
        </div>
      )}

      {!error && !hasAnyCreators && (
        <p className="mt-10 rounded-card border border-line bg-panel px-5 py-4 text-[15px] text-fg-2">
          No creators on the record yet.{" "}
          <Link href="/submit" className="u-link font-semibold text-win">
            Submit the first pick.
          </Link>
        </p>
      )}

      {!error && hasAnyCreators && (
        <HomeBoard
          divisions={divisions}
          settled={settledLines.slice(0, 12)}
          settledLabel={settledIsRecent ? "Last two days" : "Latest settled"}
          onDeck={onDeckLines.slice(0, 12)}
        />
      )}

      <section className="mt-20" aria-labelledby="how-heading">
        <SectionHead id="how-heading">How the record is kept</SectionHead>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            {
              head: "Capture",
              body: "Picks come from creators' public posts on X. Anyone can submit a post; it is fetched live and the picks are read out of the text and images.",
            },
            {
              head: "Settle",
              body: "Once the game ends, every pick is checked against final scores and box scores: spreads, moneylines, totals, props, and parlays leg by leg.",
            },
            {
              head: "Record",
              body: "Wins, losses and pushes add up to the record. ROI is measured against the −110 break-even line, a 52.4% win rate.",
            },
          ].map((step, i) => (
            <div key={step.head} className="rounded-card border border-line bg-panel px-5 py-5">
              <div className="flex items-center gap-2.5">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-win-dim font-display text-[14px] font-bold text-win">
                  {i + 1}
                </span>
                <h3 className="font-display text-[19px] font-bold uppercase tracking-[0.02em] text-fg">{step.head}</h3>
              </div>
              <p className="mt-2.5 text-[15px] leading-[1.55] text-fg-2">{step.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
