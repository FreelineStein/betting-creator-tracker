"use client";

import Link from "next/link";
import { useId, useState } from "react";
import { usePostHog } from "posthog-js/react";
import {
  Avatar,
  FormChips,
  ResultChip,
  SectionHead,
  Stat,
  pctText,
  pctTone,
  roiTone,
} from "../../components/brand";
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
  img: string | null;
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

export type Division = { id: string; title: string; subtitle: string; rows: StandingsRow[] };

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
      <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-5">
        <label
          htmlFor={findId}
          className="flex h-[52px] w-full items-center gap-3 rounded-control border border-line bg-panel px-4 transition-colors duration-150 focus-within:border-win sm:max-w-[380px]"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" className="shrink-0 text-fg-3">
            <circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M13 13l4.5 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          <span className="sr-only">Find a creator</span>
          <input
            id={findId}
            type="search"
            autoComplete="off"
            spellCheck={false}
            placeholder="Find a creator by name or @handle"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="w-full bg-transparent text-[16px] font-medium text-fg placeholder:text-fg-3 focus:outline-none focus-visible:outline-none"
          />
        </label>
        <p className="text-[13px] text-fg-3" aria-live="polite">
          {needle
            ? `${shownCreators} of ${totalCreators} creators match`
            : `${totalCreators} creators on the record`}
        </p>
      </div>

      <div className="mt-10 lg:grid lg:grid-cols-[minmax(0,1fr)_320px] lg:gap-x-8">
        <div className="space-y-10">
          {filtered.length === 0 && (
            <p className="rounded-card border border-line bg-panel px-5 py-4 text-[15px] text-fg-2">
              No creator on the record matches &ldquo;{q.trim()}&rdquo;. If they have posted a pick on
              X,{" "}
              <Link href="/submit" className="u-link font-semibold text-win">
                submit it
              </Link>{" "}
              and they join the standings.
            </p>
          )}
          {filtered.map((d) => (
            <section key={d.id} aria-labelledby={`division-${d.id}`}>
              <SectionHead id={`division-${d.id}`} count={d.rows.length} right={d.subtitle}>
                {d.title}
              </SectionHead>
              <ol className="space-y-2.5">
                {d.rows.map((r, i) => (
                  <CreatorCard
                    key={r.id}
                    row={r}
                    rank={i + 1}
                    open={openId === r.id}
                    onToggle={() => toggle(r.id)}
                    onOpenCreator={() =>
                      posthog?.capture("creator_card_clicked", {
                        creator_id: r.id,
                        creator_name: r.name,
                        source: "standings_row",
                      })
                    }
                  />
                ))}
              </ol>
            </section>
          ))}
          <p className="text-[13px] leading-relaxed text-fg-3">
            Win % in green clears the −110 break-even line (52.4%); pushes are left out of it. ROI is
            percentage points above that line. Form reads oldest to newest.
          </p>
        </div>

        <aside className="mt-12 space-y-10 lg:mt-0">
          {/* Pending picks lead the column only when something is actually on deck. */}
          {(keep(onDeck).length > 0 ? ["deck", "box"] : ["box", "deck"]).map((key) =>
            key === "deck" ? (
              <PickColumn
                key="deck"
                title="On deck"
                right="Pending"
                onDeck
                lines={keep(onDeck)}
                empty="Nothing pending right now. Submit a pick to put one on the board."
              />
            ) : (
              <PickColumn
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

function CreatorCard({
  row: r,
  rank,
  open,
  onToggle,
  onOpenCreator,
}: {
  row: StandingsRow;
  rank: number;
  open: boolean;
  onToggle: () => void;
  onOpenCreator: () => void;
}) {
  const detailId = `recent-${r.id}`;
  return (
    <li
      className={`rounded-card border bg-panel transition-colors duration-150 ${
        open ? "border-line-2 bg-panel-2" : "border-line hover:border-line-2 hover:bg-panel-2"
      }`}
    >
      <div
        onClick={onToggle}
        className="grid cursor-pointer grid-cols-[48px_minmax(0,1fr)_auto] items-center gap-x-4 gap-y-3 px-4 py-4 sm:px-[18px] md:grid-cols-[48px_minmax(0,1fr)_84px_76px_70px_auto_30px]"
      >
        <span className="relative">
          <Avatar src={r.img} name={r.name} size={48} />
          <span className="absolute -bottom-1 -left-1 flex h-[20px] min-w-[20px] items-center justify-center rounded-full border-2 border-panel bg-panel-3 px-1 font-display text-[11px] font-bold text-fg-2">
            {rank}
          </span>
        </span>

        <div className="min-w-0">
          <Link
            href={`/creators/${r.id}`}
            onClick={(e) => {
              e.stopPropagation();
              onOpenCreator();
            }}
            className="u-link block truncate text-[17px] font-bold leading-tight text-fg"
          >
            {r.name}
          </Link>
          {r.handles.length > 0 && (
            <div className="mt-0.5 truncate text-[13.5px] text-fg-3">{r.handles.map(handleText).join(" · ")}</div>
          )}
        </div>

        <button
          type="button"
          aria-expanded={open}
          aria-controls={detailId}
          aria-label={`${open ? "Hide" : "Show"} recent picks for ${r.name}`}
          onClick={(e) => {
            e.stopPropagation();
            onToggle();
          }}
          className="flex h-[30px] w-[30px] items-center justify-center justify-self-end rounded-chip border border-line-2 text-fg-2 transition-colors duration-150 hover:border-fg-3 hover:text-fg md:order-last"
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            aria-hidden="true"
            className={`transition-transform duration-150 ${open ? "rotate-180" : ""}`}
          >
            <path d="M2 4.5l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        <div className="col-span-3 grid grid-cols-3 gap-3 md:col-span-3 md:contents">
          <Stat label="Record">
            {r.wins}-{r.losses}
            {r.pushes > 0 && <span className="text-fg-3">-{r.pushes}</span>}
          </Stat>
          <Stat label="Win %" tone={pctTone(r.pct)}>
            {pctText(r.pct)}
          </Stat>
          <Stat label="ROI" tone={roiTone(r.roi)}>
            {r.roi === null ? "—" : roiText(r.roi)}
          </Stat>
        </div>

        <div className="col-span-3 flex items-center justify-between gap-3 md:col-span-1 md:justify-end">
          <span className="text-[12px] font-semibold uppercase tracking-[0.06em] text-fg-3 md:hidden">
            Form{r.streak ? ` · ${r.streak.kind}${r.streak.count}` : ""}
          </span>
          <FormChips results={r.last5} />
        </div>
      </div>

      {open && (
        <div id={detailId} className="border-t border-line px-4 pb-4 pt-1 sm:px-[18px]">
          <RecentPicks row={r} />
        </div>
      )}
    </li>
  );
}

function RecentPicks({ row }: { row: StandingsRow }) {
  return (
    <div>
      {row.recent.length === 0 ? (
        <p className="py-3 text-[14px] text-fg-3">No picks on the record yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {row.recent.map((p) => (
            <li key={p.id} className="flex items-start gap-3 py-3 text-[14px]">
              <ResultChip status={p.status} size={24} className="mt-0.5" />
              <span className="min-w-0 flex-1">
                <span className="block font-semibold text-fg">{p.title}</span>
                <span className="block text-[13px] text-fg-3">
                  {p.sport} · {formatDateET(p.date)}
                  {p.event && ` · ${p.event}`}
                  {p.odds && ` · ${p.odds}`}
                </span>
                {p.legs && p.legs.length > 0 && <Legs legs={p.legs} />}
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link
        href={`/creators/${row.id}`}
        className="u-link mt-1 inline-block text-[14px] font-bold text-win"
      >
        Full record · {row.total} {row.total === 1 ? "pick" : "picks"} →
      </Link>
    </div>
  );
}

function Legs({ legs }: { legs: { text: string; event?: string; result?: string }[] }) {
  return (
    <ul className="mt-1.5 space-y-1 border-l border-line-2 pl-2.5 text-[13px] text-fg-2">
      {legs.map((leg, j) => (
        <li key={j} className="flex flex-wrap items-center gap-x-1.5">
          {leg.result && <ResultChip status={leg.result} size={16} />}
          <span>{leg.text}</span>
          {leg.event && <span className="text-fg-3">· {leg.event}</span>}
        </li>
      ))}
    </ul>
  );
}

function PickColumn({
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
      <SectionHead right={right}>{title}</SectionHead>
      <div className="rounded-card border border-line bg-panel px-[18px]">
        {lines.length === 0 ? (
          <p className="py-4 text-[14.5px] text-fg-2">
            {empty}
            {onDeck && (
              <>
                {" "}
                <Link href="/submit" className="u-link font-semibold text-win">
                  Submit a pick
                </Link>
              </>
            )}
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {lines.map((l) => (
              <li key={l.id} className="flex items-start gap-3 py-3">
                {onDeck ? (
                  <span className="mt-[7px] h-2 w-2 shrink-0 rounded-full bg-win" aria-hidden="true" />
                ) : (
                  <ResultChip status={l.status} size={24} className="mt-0.5" />
                )}
                <div className="min-w-0">
                  <div className="text-[12.5px] text-fg-3">
                    <Link href={`/creators/${l.creatorId}`} className="u-link font-semibold text-fg">
                      {l.creatorName}
                    </Link>
                    {" · "}
                    {l.sport} · {formatDateET(l.date)}
                    {l.odds && ` · ${l.odds}`}
                  </div>
                  <div className="text-[15.5px] font-semibold leading-snug text-fg">{l.title}</div>
                  {l.event && <div className="text-[13px] text-fg-3">{l.event}</div>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
