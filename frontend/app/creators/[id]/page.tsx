import Link from "next/link";
import { getCreator, getCreatorRecord, getCreatorPicks } from "../../lib/api";
import type { Creator, Pick } from "../../lib/api";
import { FormStrip, Pct, ResultMark, SectionBar } from "../../../components/brand";
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
      <div className="border-y-2 border-ink py-4 text-[15px] text-ink-2">
        <p className="font-semibold text-ink">Could not load this creator.</p>
        <p>
          Try again in a minute, or go back to the{" "}
          <Link href="/" className="rule-link font-semibold text-ink">
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
      <Link
        href="/"
        className="rule-link font-display text-[13px] font-medium uppercase tracking-[0.1em] text-ink"
      >
        Back to standings
      </Link>

      <header className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex items-end gap-5">
          {creator.profile_image_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={creator.profile_image_url}
              alt=""
              width={84}
              height={84}
              className="h-[72px] w-[72px] shrink-0 border-2 border-ink object-cover grayscale contrast-125 sm:h-[84px] sm:w-[84px]"
            />
          )}
          <div className="min-w-0">
            <h1 className="font-display text-[clamp(40px,7vw,80px)] font-bold uppercase leading-[0.9] tracking-[-0.015em] text-ink text-balance">
              {creator.display_name}
            </h1>
            {meta.length > 0 && (
              <p className="mt-2 text-[14px] text-ink-2">
                {meta.map((m, i) => (
                  <span key={m.text}>
                    {i > 0 && <span className="mx-1.5 text-ink-3">·</span>}
                    {m.href ? (
                      <a
                        href={m.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="rule-link font-semibold text-ink"
                      >
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
        </div>
      </header>

      <section className="mt-8" aria-label="Record">
        {hasPicks ? (
          <table className="agate">
            <thead>
              <tr>
                <th className="num">GP</th>
                <th className="num">W</th>
                <th className="num">L</th>
                <th className="num hidden sm:table-cell">P</th>
                <th className="num">Pct</th>
                <th className="num">ROI</th>
                <th className="num">Strk</th>
                <th className="hidden sm:table-cell">L5</th>
                <th className="num hidden sm:table-cell">Picks</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="num font-display text-[30px] font-bold leading-none sm:text-[36px]">{gp}</td>
                <td className="num font-display text-[30px] font-bold leading-none sm:text-[36px]">{record.wins}</td>
                <td className="num font-display text-[30px] font-bold leading-none sm:text-[36px]">{record.losses}</td>
                <td className="num hidden font-display text-[30px] font-bold leading-none text-ink-3 sm:table-cell sm:text-[36px]">
                  {record.pushes}
                </td>
                <td className="num font-display text-[30px] leading-none sm:text-[36px]">
                  <Pct value={pct} />
                </td>
                <td className="num font-display text-[30px] font-bold leading-none sm:text-[36px]">
                  {roiText(record.roi)}
                </td>
                <td className="num font-display text-[30px] font-bold leading-none sm:text-[36px]">
                  {streak ? `${streak.kind}${streak.count}` : "—"}
                </td>
                <td className="hidden sm:table-cell">
                  <FormStrip results={last5} size={14} gap={4} className="block text-ink" />
                </td>
                <td className="num hidden font-display text-[30px] font-bold leading-none sm:table-cell sm:text-[36px]">
                  {record.total_picks}
                </td>
              </tr>
            </tbody>
          </table>
        ) : (
          <p className="border-y-2 border-ink py-4 text-[15px] text-ink-2">
            Tracking started. The record fills in as picks are submitted and settled.
          </p>
        )}
        {hasPicks && (
          <p className="mt-2 text-[12px] text-ink-3">
            Pct in bold clears the −110 break-even (52.4%). ROI is percentage points above that
            line. Pushes are excluded from GP and Pct.
          </p>
        )}
      </section>

      <div className="mt-12 lg:grid lg:grid-cols-12 lg:gap-x-10">
        <div className="space-y-12 lg:col-span-8">
          {pending.length > 0 && (
            <section aria-labelledby="ondeck-heading">
              <SectionBar onDeck right="Settles about 15 minutes after the game ends">
                <span id="ondeck-heading">On deck · {pending.length}</span>
              </SectionBar>
              <table className="agate">
                <thead>
                  <tr>
                    <th>Game</th>
                    <th>Pick</th>
                    <th className="num">Odds</th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map((pick) => (
                    <tr key={pick.pick_id}>
                      <td className="w-[88px] whitespace-nowrap align-top text-[12px] text-ink-3">
                        <div>{formatDateET(pick.event_date)}</div>
                        <div>{formatTimeET(pick.event_date)}</div>
                      </td>
                      <td className="align-top">
                        <PickCell pick={pick} />
                      </td>
                      <td className="num w-[56px] align-top text-ink-3">{pick.odds}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          <section aria-labelledby="log-heading">
            <SectionBar
              right={
                windowIsComplete
                  ? `${history.length} ${history.length === 1 ? "pick" : "picks"}`
                  : `Last ${picks.length} of ${record.total_picks} picks`
              }
            >
              <span id="log-heading">Game log</span>
            </SectionBar>
            {history.length === 0 ? (
              <p className="border-b border-ink py-3 text-[13px] text-ink-3">No settled picks yet.</p>
            ) : (
              <table className="agate">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Pick</th>
                    <th className="num hidden sm:table-cell">Odds</th>
                    <th className="w-[52px]">Result</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((pick) => (
                    <tr key={pick.pick_id}>
                      <td className="w-[58px] whitespace-nowrap align-top text-[12px] text-ink-3 sm:w-[92px]">
                        <span className="sm:hidden">{formatDateET(pick.event_date)}</span>
                        <span className="hidden sm:inline">{formatDateET(pick.event_date, true)}</span>
                      </td>
                      <td className="align-top">
                        <PickCell pick={pick} />
                        {pick.odds && (
                          <div className="text-[12px] text-ink-3 sm:hidden">{pick.odds}</div>
                        )}
                      </td>
                      <td className="num hidden w-[56px] align-top text-ink-3 sm:table-cell">
                        {pick.odds}
                      </td>
                      <td className="align-top">
                        {pick.status === "pending" ? (
                          <span className="text-[12px] uppercase tracking-[0.06em] text-ink-3">
                            Unsettled
                          </span>
                        ) : (
                          <ResultMark status={pick.status} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </div>

        <aside className="mt-12 lg:col-span-4 lg:mt-0">
          {sports.length > 0 && (
            <section aria-labelledby="sport-heading">
              <SectionBar>
                <span id="sport-heading">By sport</span>
              </SectionBar>
              <table className="agate">
                <thead>
                  <tr>
                    <th>Sport</th>
                    <th className="num">W</th>
                    <th className="num">L</th>
                    <th className="num">Pct</th>
                  </tr>
                </thead>
                <tbody>
                  {sports.map(([sportKey, stats]) => {
                    const n = stats.wins + stats.losses;
                    const wr = n > 0 ? Math.round((stats.wins / n) * 1000) / 10 : null;
                    return (
                      <tr key={sportKey}>
                        <td className="font-semibold uppercase tracking-[0.04em]">
                          {sportLabel({ sport: sportKey, league: null })}
                        </td>
                        <td className="num">{stats.wins}</td>
                        <td className="num">{stats.losses}</td>
                        <td className="num">
                          <Pct value={wr} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
      <div className="text-[14px] leading-snug">
        <span className="mr-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-ink-3">
          {sport}
        </span>
        <span className="font-semibold text-ink">{formatPickDetail(pick.pick_type, detail)}</span>
        {pick.event && <span className="text-ink-3"> · {pick.event}</span>}
      </div>
      {legs.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 border-l border-ink pl-2.5 text-[13px] text-ink-2">
          {legs.map((leg, j) => (
            <li key={j} className="flex flex-wrap items-center gap-x-1.5">
              {leg.result && <ResultMark status={leg.result} size={13} />}
              <span>{legText(leg)}</span>
              {leg.event && <span className="text-ink-3">· {leg.event}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
