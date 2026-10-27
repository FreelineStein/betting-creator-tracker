import Link from "next/link";
import { getCreator, getCreatorRecord, getCreatorPicks } from "../../lib/api";
import type { Creator, Pick } from "../../lib/api";
import {
  Avatar,
  FormChips,
  Panel,
  ResultChip,
  SectionHead,
  Stat,
  pctText,
  pctTone,
  roiTone,
} from "../../../components/brand";
import {
  activePicks,
  computeStreak,
  dominantSport,
  earliestLoggedAt,
  etDateStr,
  formatDateET,
  formatPickDetail,
  formatTimeET,
  formatTrackedSince,
  lastResults,
  legText,
  parlayLegs,
  pctValue,
  roiText,
  shiftET,
  sportLabel,
} from "../../lib/picks";

type Props = { params: { id: string } };

function handleLabel(p: { platform: string; handle: string }): string {
  const bare = p.handle.replace(/^@/, "");
  const platform =
    p.platform === "twitter"
      ? "X"
      : p.platform.charAt(0).toUpperCase() + p.platform.slice(1);
  return `@${bare} on ${platform}`;
}

export default async function CreatorPage({ params }: Props) {
  let creator: Creator, record, picks: Pick[];
  try {
    [creator, record, picks] = await Promise.all([
      getCreator(params.id),
      getCreatorRecord(params.id),
      getCreatorPicks(params.id),
    ]);
  } catch {
    return (
      <div className="rounded-card border border-line bg-panel px-5 py-4 text-[15px] text-fg-2">
        <p className="font-semibold text-fg">Could not load this creator.</p>
        <p>
          Try again in a minute, or go back to the{" "}
          <Link href="/" className="u-link font-semibold text-win">
            standings
          </Link>
          .
        </p>
      </div>
    );
  }

  const hasPicks = record.total_picks > 0;
  const gp = record.wins + record.losses;
  const pct = pctValue(record.win_rate, gp);
  const streak = computeStreak(picks);
  const last5 = lastResults(picks, 5);
  // The picks endpoint returns the 50 most recent; only derive "tracked since"
  // when the window holds the creator's whole history.
  const windowIsComplete = picks.length >= record.total_picks;
  const trackedSince = windowIsComplete ? formatTrackedSince(earliestLoggedAt(picks)) : null;
  const mainSport = dominantSport(record.accuracy_by_sport);

  const sports = Object.entries(record.accuracy_by_sport || {}).sort(
    ([, a], [, b]) => b.wins + b.losses - (a.wins + a.losses),
  );

  const todayET = shiftET(0);
  const pending = activePicks(picks);
  const history = picks
    .filter((p) => {
      if (p.status !== "pending") return true;
      const d = etDateStr(p.event_date);
      return d === null || d < todayET;
    })
    .slice()
    .sort((a, b) => {
      const at = a.event_date ? new Date(a.event_date).getTime() : 0;
      const bt = b.event_date ? new Date(b.event_date).getTime() : 0;
      return bt - at;
    });

  const meta = [
    ...creator.platforms.map((p) => ({ text: handleLabel(p), href: p.url })),
    ...(trackedSince ? [{ text: `Tracked since ${trackedSince}`, href: null }] : []),
    ...(mainSport ? [{ text: `Mostly ${sportLabel({ sport: mainSport, league: null })}`, href: null }] : []),
  ];

  return (
    <div>
      <Link href="/" className="u-link inline-flex items-center gap-1.5 text-[14px] font-semibold text-fg-2 hover:text-fg">
        <span aria-hidden="true">←</span> Standings
      </Link>

      <header className="mt-6 flex items-center gap-4 sm:gap-5">
        <Avatar src={creator.profile_image_url} name={creator.display_name} size={76} />
        <div className="min-w-0">
          <h1 className="font-display text-[clamp(34px,5vw,56px)] font-extrabold uppercase leading-[1.0] text-fg text-balance">
            {creator.display_name}
          </h1>
          {meta.length > 0 && (
            <p className="mt-1.5 text-[15px] text-fg-2">
              {meta.map((m, i) => (
                <span key={m.text}>
                  {i > 0 && <span className="mx-1.5 text-fg-3">·</span>}
                  {m.href ? (
                    <a href={m.href} target="_blank" rel="noopener noreferrer" className="u-link font-semibold text-fg">
                      {m.text}
                    </a>
                  ) : (
                    m.text
                  )}
                </span>
              ))}
            </p>
          )}
        </div>
      </header>

      <section className="mt-8" aria-label="Record">
        {hasPicks ? (
          <Panel className="px-5 py-5 sm:px-6">
            <div className="grid grid-cols-3 gap-x-4 gap-y-5 sm:grid-cols-6">
              <Stat label="Record" size="lg">
                {record.wins}-{record.losses}
                {record.pushes > 0 && <span className="text-fg-3">-{record.pushes}</span>}
              </Stat>
              <Stat label="Win %" size="lg" tone={pctTone(pct)}>
                {pctText(pct)}
              </Stat>
              <Stat label="ROI" size="lg" tone={roiTone(record.roi)}>
                {roiText(record.roi)}
              </Stat>
              <Stat label="Streak" size="lg" tone={streak ? (streak.kind === "W" ? "win" : "loss") : "muted"}>
                {streak ? `${streak.kind}${streak.count}` : "—"}
              </Stat>
              <Stat label="Picks" size="lg">
                {record.total_picks}
              </Stat>
              <div>
                <div className="text-[11.5px] font-semibold uppercase tracking-[0.06em] text-fg-3">Last 5</div>
                <FormChips results={last5} size={28} className="mt-2" />
              </div>
            </div>
          </Panel>
        ) : (
          <Panel className="px-5 py-4 text-[15px] text-fg-2">
            Tracking started. The record fills in as picks are submitted and settled.
          </Panel>
        )}
        {hasPicks && (
          <p className="mt-2.5 text-[13px] text-fg-3">
            Win % in green clears the −110 break-even (52.4%); pushes are left out of it. ROI is
            percentage points above that line.
          </p>
        )}
      </section>

      <div className="mt-12 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-x-8">
        <div className="space-y-12">
          {pending.length > 0 && (
            <section aria-labelledby="ondeck-heading">
              <SectionHead id="ondeck-heading" count={pending.length} right="Settles about 15 minutes after the game">
                On deck
              </SectionHead>
              <Panel className="px-[18px]">
                <ul className="divide-y divide-line">
                  {pending.map((pick) => (
                    <li key={pick.pick_id} className="flex items-start gap-3 py-3.5">
                      <span className="mt-[7px] h-2 w-2 shrink-0 rounded-full bg-win" aria-hidden="true" />
                      <div className="min-w-0 flex-1">
                        <PickCell pick={pick} />
                      </div>
                      <div className="shrink-0 text-right text-[12.5px] text-fg-3">
                        <div>{formatDateET(pick.event_date)}</div>
                        <div>{formatTimeET(pick.event_date)}</div>
                      </div>
                    </li>
                  ))}
                </ul>
              </Panel>
            </section>
          )}

          <section aria-labelledby="log-heading">
            <SectionHead
              id="log-heading"
              right={
                windowIsComplete
                  ? `${history.length} ${history.length === 1 ? "pick" : "picks"}`
                  : `Last ${picks.length} of ${record.total_picks}`
              }
            >
              Pick history
            </SectionHead>
            {history.length === 0 ? (
              <Panel className="px-5 py-4 text-[14px] text-fg-3">No settled picks yet.</Panel>
            ) : (
              <Panel className="px-[18px]">
                <ul className="divide-y divide-line">
                  {history.map((pick) => (
                    <li key={pick.pick_id} className="flex items-start gap-3 py-3.5">
                      {pick.status === "pending" ? (
                        <span
                          className="mt-0.5 flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-chip border border-dashed border-line-2 text-[11px] font-bold text-fg-3"
                          title="Unsettled"
                        >
                          ?
                        </span>
                      ) : (
                        <ResultChip status={pick.status} className="mt-0.5" />
                      )}
                      <div className="min-w-0 flex-1">
                        <PickCell pick={pick} />
                      </div>
                      <div className="shrink-0 text-right text-[12.5px] text-fg-3">
                        <div className="whitespace-nowrap">{formatDateET(pick.event_date, true)}</div>
                        {pick.odds && <div className="tabular">{pick.odds}</div>}
                      </div>
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </section>
        </div>

        <aside className="mt-12 lg:mt-0">
          {sports.length > 0 && (
            <section aria-labelledby="sport-heading">
              <SectionHead id="sport-heading">By sport</SectionHead>
              <Panel className="px-[18px]">
                <ul className="divide-y divide-line">
                  {sports.map(([sportKey, stats]) => {
                    const n = stats.wins + stats.losses;
                    const wr = n > 0 ? Math.round((stats.wins / n) * 1000) / 10 : null;
                    return (
                      <li key={sportKey} className="flex items-center justify-between gap-3 py-3">
                        <span className="font-display text-[17px] font-bold uppercase tracking-[0.03em] text-fg">
                          {sportLabel({ sport: sportKey, league: null })}
                        </span>
                        <span className="tabular flex items-baseline gap-4 text-[15px]">
                          <span className="text-fg-2">
                            {stats.wins}-{stats.losses}
                          </span>
                          <span
                            className={`w-[54px] text-right font-display text-[18px] font-bold ${
                              pctTone(wr) === "win" ? "text-win" : pctTone(wr) === "muted" ? "text-fg-3" : "text-fg"
                            }`}
                          >
                            {pctText(wr)}
                          </span>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </Panel>
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function PickCell({ pick }: { pick: Pick }) {
  const detail = pick.pick_detail as Record<string, unknown>;
  const isParlay = pick.pick_type === "parlay";
  const legs = isParlay ? parlayLegs(detail) : [];
  const sport = sportLabel(pick);
  return (
    <div>
      <div className="text-[15.5px] font-semibold leading-snug text-fg">{formatPickDetail(pick.pick_type, detail)}</div>
      <div className="text-[13px] text-fg-3">
        {sport}
        {pick.event && ` · ${pick.event}`}
      </div>
      {legs.length > 0 && (
        <ul className="mt-1.5 space-y-1 border-l border-line-2 pl-2.5 text-[13.5px] text-fg-2">
          {legs.map((leg, j) => (
            <li key={j} className="flex flex-wrap items-center gap-x-1.5">
              {leg.result && <ResultChip status={leg.result} size={16} />}
              <span>{legText(leg)}</span>
              {leg.event && <span className="text-fg-3">· {leg.event}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
