# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: a sports bettor who just saw a creator's pick on X (Twitter), usually on a phone, and wants to see that creator's real win/loss record before tailing or fading the pick. They arrive mid-scroll, skeptical, and decide in seconds whether the record is worth trusting. (Confirmed 2026-10-26.)

Secondary: the same bettor as a contributor, pasting an X post URL on /submit so a pick gets logged on the public record. Submissions are anonymous.

Admin work (approving creators, reprocessing posts) happens through the API and scripts, not through the site.

## Product Purpose

PickReceipts tracks sports-betting creators across their public social posts, extracts their picks with an LLM pipeline, settles each pick against real game results, and publishes a transparent win/loss record per creator. Creators cherry-pick wins and bury losses; PickReceipts keeps the receipt on every pick so followers can see who is actually accurate.

Success for a visitor: find the creator, read the record, and leave with a confident tail / fade / ignore decision.

## Positioning

The only record that is built from the creator's own public posts and settled against official results, not self-reported. Every pick on the site links back to a real post, and every settled pick was checked against a real score or box score. A creator cannot curate it.

## Operating Context

- Picks enter through anonymous URL submission on /submit (Cloudflare Turnstile, rate limit, honeypot). The tweet is fetched live via oEmbed; images are OCR'd; picks are parsed and pinned to a scheduled game at submission time.
- Picks that cannot be pinned to a scheduled game go to `needs_review` and are shown to the submitter as "pending review", not added to the record.
- A scheduler settles pending picks after games end: spreads, moneylines and totals against final scores, player props against box scores, parlays leg by leg. Settlement typically lands within about 15 minutes of game end.
- New creators mentioned in a submitted post are auto-created and active immediately (the earlier approval gate was removed). On the site they surface under the "lesser known" tier until they build a record.
- Sports covered today: NBA, NFL, CFB, MLB, NHL, soccer (several leagues), plus occasional tennis, UFC, golf.
- Dates and "today" on the site are expressed in US Eastern time, matching how US sports schedules read.

## Capabilities and Constraints

- Data per creator: display name, platform handles with links, optional profile image, tier, record (wins, losses, pushes, total picks, win rate, ROI), accuracy by sport, pick list (up to 50 most recent via the API).
- Data per pick: sport, league, event ("Team vs Team"), event date, pick type (spread, moneyline, over_under, prop, parlay), structured detail, odds, status (pending, won, lost, push, void), logged time. Parlay legs carry their own text, event and result.
- ROI is reported as percentage points above the −110 break-even rate (52.4%).
- Live creator set is small (about ten creators, four with profile images). Design must hold with 1 to 20 creators and with creators that have zero resolved picks.
- Stack: Next.js 14 App Router + Tailwind on Vercel; FastAPI + Postgres on Railway. The frontend talks to the API only; no auth, no user accounts, no comments.
- Not built and not to be implied: YouTube/TikTok ingestion, alerts, following, odds comparison, pick selling, any paid tier.
- Terminology: "creator" (not influencer or capper on the site), "pick", "record", "tail" / "fade", "settle" for outcome resolution, "on the record".
- Ingestion is user-submission only; the site must keep inviting submissions because that is how the record grows.

## Brand Commitments

- Name: PickReceipts (one word, capital P and R). Domain pickreceipts.com.
- Voice (from the March 2026 brand guide, still current): transparent, direct, accountable. Short sentences, concrete numbers, no editorializing. Established lines: "Every pick. Every loss. On the record." / "They said it was a lock. We kept the receipt." / "Real records. No excuses. No exceptions."
- Legal/footer copy that must survive: "Picks sourced from public social media posts." and "For entertainment and transparency purposes only. Not financial advice."
- Visual world: free hand, confirmed 2026-10-26. Neither the March brand guide palette (black, signal green, alert orange, Barlow Condensed) nor the May 2026 "Stadium Card" palette (warm paper, amber, cobalt, Manrope) is binding. The green receipt logo PNG is an available asset, not a requirement.

## Evidence on Hand

- Real logo asset: `frontend/public/brand-mark.png` (white receipt icon with green check / orange cross line items and "PICK RECEIPTS" wordmark; transparent background, designed for dark grounds). Same file as `favicon.png`.
- Prior brand guide: `~/Downloads/pickreceipts_brand_guide.html` (March 2026, v1.0). Historical reference only.
- Prior design handoff for the May look: `handoffs/design_handoff_creator_card/` with screenshots. Anti-reference for this redesign.
- Live data at the production API (see repo CLAUDE.md) with real creators and real settled picks; no need to invent fixture data for screenshots.
- No testimonials, press, user counts or traffic figures exist. Do not fabricate any.

## Product Principles

- The record is the product. Numbers and settled outcomes lead; commentary never does.
- Show losses as plainly as wins. Nothing on the site may visually bury a loss.
- Every number should be traceable: pick → post → game → result.
- Decide-in-seconds on a phone. A visitor from X gets the verdict on a creator above the fold.
- Submission is the growth loop; it must feel like contributing to a public ledger, not filing a report.

## Accessibility & Inclusion

No formal standard mandated. Practical floor: WCAG AA contrast for text, keyboard-reachable cards and form, win/loss never conveyed by color alone (text or shape must carry it), motion respectful of `prefers-reduced-motion`.
