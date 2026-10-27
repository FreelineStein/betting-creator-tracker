"use client";

import Link from "next/link";
import { Fragment, useId, useState } from "react";
import { usePostHog } from "posthog-js/react";
import { FormStrip, Pct, ResultMark, SectionBar } from "../../components/brand";
import { formatDateET, roiText, type Settled, type Streak } from "../lib/picks";

export type PickLite = {
  id: string;
  date: string | null;
  sport: string;
  title: string;
  event: string | null;
  odds: string | null;
  status: string;
  legs: { text: string; event?: string; result?: string }[] | null;
};

export type StandingsRow = {
  id: string;
  name: string;
  handles: { platform: string; handle: string; url: string }[];
  gp: number;
  wins: number;
  losses: number;
  pushes: number;
  pct: number | null;
  roi: number | null;
  streak: Streak;
  last5: Settled[];
  last: PickLite | null;
  recent: PickLite[];
  total: number;
  allSettled: PickLite[];
};

export type Division = { id: string; title: string; rows: StandingsRow[] };

export type BoxLine = PickLite & { creatorId: string; creatorName: string };

function handleText(h: { platform: string; handle: string }): string {
  const bare = h.handle.replace(/^@/, "");
  return h.platform === "twitter" ? `@${bare}` : `@${bare} (${h.platform})`;
}

export default function HomeBoard({
  divisions,
  settled,
  settledLabel,
  onDeck,
}: {
  divisions: Division[];
  settled: BoxLine[];
  settledLabel: string;
  onDeck: BoxLine[];
}) {
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const posthog = usePostHog();
  const findId = useId();

  const needle = q.trim().toLowerCase();
  const matches = (r: StandingsRow) =>
    !needle ||
    r.name.toLowerCase().includes(needle) ||
    r.handles.some((h) => h.handle.toLowerCase().replace(/^@/, "").includes(needle.replace(/^@/, "")));

  const filtered = divisions
    .map((d) => ({ ...d, rows: d.rows.filter(matches) }))
    .filter((d) => d.rows.length > 0);
  const matchedIds = new Set(filtered.flatMap((d) => d.rows.map((r) => r.id)));
  const totalCreators = divisions.reduce((n, d) => n + d.rows.length, 0);
  const shownCreators = filtered.reduce((n, d) => n + d.rows.length, 0);
  const keep = (lines: BoxLine[]) => (needle ? lines.filter((l) => matchedIds.has(l.creatorId)) : lines);

  function toggle(id: string) {
    setOpenId((cur) => {
      const next = cur === id ? null : id;
      if (next) posthog?.capture("standings_row_expanded", { creator_id: id });
      return next;
    });
  }

  return (
    <div>
      <div className="mt-9 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <label htmlFor={findId} className="block w-full sm:max-w-sm">
          <span className="block font-display text-[13px] font-medium uppercase tracking-[0.1em] text-ink">
            Find a creator
          </span>
          <input
            id={findId}
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Name or @handle"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="mt-1 w-full border-0 border-b-2 border-ink bg-transparent px-0 py-2 text-[19px] leading-tight text-ink placeholder:text-ink-3 focus:shadow-[0_3px_0_0_var(--ink)] focus:outline-none focus-visible:outline-none"
          />
        </label>
        <p className="text-[12px] uppercase tracking-[0.08em] text-ink-3" aria-live="polite">
          {needle
            ? `${shownCreators} of ${totalCreators} creators match`
            : `${totalCreators} creators on the record`}
        </p>
      </div>

      <div className="mt-8 lg:grid lg:grid-cols-12 lg:gap-x-10">
        <div className="space-y-10 lg:col-span-8">
          {filtered.length === 0 && (
            <p className="border-b border-ink py-4 text-[15px] text-ink-2">
              No creator on the record matches &ldquo;{q.trim()}&rdquo;. If they have posted a pick on
              X,{" "}
              <Link href="/submit" className="rule-link font-semibold text-ink">
                submit it
              </Link>{" "}
              and they join the standings.
            </p>
          )}
          {filtered.map((d) => (
            <StandingsTable
              key={d.id}
              division={d}
              openId={openId}
              onToggle={toggle}
              onOpenCreator={(row) =>
                posthog?.capture("creator_card_clicked", {
                  creator_id: row.id,
                  creator_name: row.name,
                  source: "standings_row",
                })
              }
            />
          ))}
          <p className="text-[12px] leading-relaxed text-ink-3">
            GP counts settled picks; pushes are excluded from W, L and PCT. PCT in bold clears the
            −110 break-even line (52.4%). ROI is percentage points above that line. Strk is the
            current run of wins or losses. L5 reads oldest to newest, filled squares are wins.
          </p>
        </div>

        <aside className="mt-12 space-y-10 lg:col-span-4 lg:mt-0">
          {/* Settled receipts lead the column unless something is actually on deck. */}
          {(keep(onDeck).length > 0 ? ["deck", "box"] : ["box", "deck"]).map((key) =>
            key === "deck" ? (
              <BoxScores
                key="deck"
                title="On deck"
                right="Pending, today onward"
                onDeck
                lines={keep(onDeck)}
                empty="Nothing on deck. Submit a pick to put one on the board."
              />
            ) : (
              <BoxScores
                key="box"
                title="Box scores"
                right={settledLabel}
                lines={keep(settled)}
                empty="No picks settled in the last two days."
              />
            ),
          )}
        </aside>
      </div>
    </div>
  );
}

function StandingsTable({
  division,
  openId,
  onToggle,
  onOpenCreator,
}: {
  division: Division;
  openId: string | null;
  onToggle: (id: string) => void;
  onOpenCreator: (row: StandingsRow) => void;
}) {
  return (
    <section aria-labelledby={`division-${division.id}`}>
      <SectionBar right={`${division.rows.length} ${division.rows.length === 1 ? "creator" : "creators"}`}>
        <span id={`division-${division.id}`}>{division.title}</span>
      </SectionBar>
      <table className="agate">
        <thead>
          <tr>
            <th className="num w-7">#</th>
            <th>Creator</th>
            <th className="num hidden sm:table-cell">GP</th>
            <th className="num">W</th>
            <th className="num">L</th>
            <th className="num">Pct</th>
            <th className="num hidden sm:table-cell">ROI</th>
            <th className="num">Strk</th>
            <th className="hidden md:table-cell">L5</th>
            <th className="hidden md:table-cell">Last</th>
            <th className="w-9">
              <span className="sr-only">Recent picks</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {division.rows.map((r, i) => {
            const open = openId === r.id;
            const detailId = `recent-${r.id}`;
            return (
              <Fragment key={r.id}>
                <tr
                  className={`is-link ${open ? "is-open" : ""}`}
                  onClick={() => onToggle(r.id)}
                >
                  <td className="num text-ink-3">{i + 1}</td>
                  <td>
                    <Link
                      href={`/creators/${r.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenCreator(r);
                      }}
                      className="rule-link text-[15px] font-semibold text-ink"
                    >
                      {r.name}
                    </Link>
                    {r.handles.length > 0 && (
                      <div className="mt-0.5 text-[12px] text-ink-3">
                        {r.handles.map(handleText).join(" · ")}
                      </div>
                    )}
                  </td>
                  <td className="num hidden sm:table-cell">{r.gp}</td>
                  <td className="num font-semibold">{r.wins}</td>
                  <td className="num font-semibold">{r.losses}</td>
                  <td className="num">
                    <Pct value={r.pct} />
                  </td>
                  <td className="num hidden sm:table-cell">{r.roi === null ? "—" : roiText(r.roi)}</td>
                  <td className="num">{r.streak ? `${r.streak.kind}${r.streak.count}` : "—"}</td>
                  <td className="hidden md:table-cell">
                    <FormStrip results={r.last5} className="block text-ink" />
                  </td>
                  <td className="hidden md:table-cell">
                    {r.last ? (
                      <span className="inline-flex items-center gap-2 whitespace-nowrap">
                        <ResultMark status={r.last.status} size={16} />
                        <span className="max-w-[16ch] truncate">{r.last.title}</span>
                        <span className="text-[12px] text-ink-3">{formatDateET(r.last.date)}</span>
                      </span>
                    ) : (
                      <span className="text-ink-3">—</span>
                    )}
                  </td>
                  <td className="text-right">
                    <button
                      type="button"
                      aria-expanded={open}
                      aria-controls={detailId}
                      aria-label={`${open ? "Hide" : "Show"} recent picks for ${r.name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggle(r.id);
                      }}
                      className="inline-flex h-[22px] w-[22px] items-center justify-center border-[1.5px] border-ink text-ink transition-colors duration-120 hover:bg-ink hover:text-news"
                    >
                      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                        <path d="M1 6h10" stroke="currentColor" strokeWidth="1.75" />
                        {!open && <path d="M6 1v10" stroke="currentColor" strokeWidth="1.75" />}
                      </svg>
                    </button>
                  </td>
                </tr>
                {open && (
                  <tr id={detailId}>
                    <td colSpan={11} className="bg-news-3 pt-0">
                      <RecentPicks row={r} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function RecentPicks({ row }: { row: StandingsRow }) {
  return (
    <div className="border-t border-ink pt-2 pb-1 pl-[26px]">
      {row.recent.length === 0 ? (
        <p className="py-1 text-[13px] text-ink-3">No picks on the record yet.</p>
      ) : (
        <ul className="divide-y divide-rule">
          {row.recent.map((p) => (
            <li key={p.id} className="flex items-start gap-3 py-2 text-[13px]">
              <span className="w-[46px] shrink-0 text-ink-3">{formatDateET(p.date)}</span>
              <span className="w-[42px] shrink-0 font-semibold uppercase tracking-[0.04em]">
                {p.sport}
              </span>
              <span className="min-w-0 flex-1">
                <span className="font-semibold">{p.title}</span>
                {p.event && <span className="text-ink-3"> · {p.event}</span>}
                {p.legs && p.legs.length > 0 && (
                  <ul className="mt-1 space-y-0.5 border-l border-ink pl-2 text-[12px] text-ink-2">
                    {p.legs.map((leg, j) => (
                      <li key={j} className="flex flex-wrap items-center gap-x-1.5">
                        {leg.result && <ResultMark status={leg.result} size={12} />}
                        <span>{leg.text}</span>
                        {leg.event && <span className="text-ink-3">· {leg.event}</span>}
                      </li>
                    ))}
                  </ul>
                )}
              </span>
              {p.odds && <span className="shrink-0 text-ink-3">{p.odds}</span>}
              <ResultMark status={p.status} size={16} className="shrink-0" />
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 pb-1">
        <Link
          href={`/creators/${row.id}`}
          className="rule-link font-display text-[13px] font-medium uppercase tracking-[0.08em] text-ink"
        >
          Full game log · {row.total} {row.total === 1 ? "pick" : "picks"}
        </Link>
      </div>
    </div>
  );
}

function BoxScores({
  title,
  right,
  lines,
  empty,
  onDeck = false,
}: {
  title: string;
  right?: string;
  lines: BoxLine[];
  empty: string;
  onDeck?: boolean;
}) {
  return (
    <section>
      <SectionBar right={right} onDeck={onDeck}>
        {title}
      </SectionBar>
      {lines.length === 0 ? (
        <p className="border-b border-ink py-3 text-[13px] text-ink-3">{empty}</p>
      ) : (
        <table className="agate">
          <thead className="sr-only">
            <tr>
              <th>Date</th>
              <th>Creator and pick</th>
              <th>Odds</th>
              {!onDeck && <th>Result</th>}
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <tr key={l.id}>
                <td className="w-[52px] whitespace-nowrap align-top text-[12px] text-ink-3">
                  {formatDateET(l.date)}
                </td>
                <td className="align-top">
                  <div className="text-[13px]">
                    <Link
                      href={`/creators/${l.creatorId}`}
                      className="rule-link font-semibold text-ink"
                    >
                      {l.creatorName}
                    </Link>
                    <span className="ml-1.5 text-[11px] font-semibold uppercase tracking-[0.04em] text-ink-3">
                      {l.sport}
                    </span>
                  </div>
                  <div className="text-[13px] font-semibold leading-snug">{l.title}</div>
                  {l.event && <div className="text-[12px] text-ink-3">{l.event}</div>}
                </td>
                <td className="num w-[48px] align-top text-[12px] text-ink-3">{l.odds ?? ""}</td>
                {!onDeck && (
                  <td className="w-[26px] align-top">
                    <ResultMark status={l.status} size={16} />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
