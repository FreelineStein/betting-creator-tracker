# Pick Receipts

Transparent W/L records for sports betting creators. Users submit posted picks via URL; the system parses them with an LLM, resolves outcomes against live game data, and surfaces creator records with no cherrypicking.

Live at [pickreceipts.com](https://pickreceipts.com).

## Architecture

- **Backend:** Python 3 + FastAPI + SQLAlchemy + PostgreSQL, deployed on Railway.
- **Frontend:** Next.js 14 (App Router) + Tailwind, deployed on Vercel.
- **Scheduler:** APScheduler in-process (one worker, fine for MVP).

### Ingestion (user-driven, not scraped)

Anonymous users paste an X/Twitter post URL on `/submit`. The submission is gated by Cloudflare Turnstile + slowapi rate limit + URL regex + honeypot, then ingested:

1. Fetch via `publish.twitter.com/oembed`; fall back to `fxtwitter` for embedded image OCR (Claude vision).
2. Parse extracted text into structured picks via Claude Haiku (OpenAI fallback).
3. Enrich missing opponents through ESPN's free scoreboard.
4. Persist `Source` + `Pick` rows; auto-create unknown creators with `tracking_active=False` (soft gate for review).

The legacy Apify-based multi-platform scrapers (`twitter.py`, `instagram.py`, `reddit.py`, `app/pipeline/*`) are still in the tree but not on the active ingestion path.

### Outcome Resolution

A scheduled job resolves pending picks against game results, ESPN-first to stay under the Odds API budget:

1. **ESPN scoreboard** (free, no quota) — handles spread/moneyline/over_under/tennis-moneyline plus prop and parlay-leg resolution via box scores.
2. **The Odds API** — fallback for any picks ESPN couldn't match. Tennis routes through ESPN exclusively.

Closing odds are captured separately on a 30-min schedule for picks where the creator post didn't include a price.

## Project Layout

```
betting-creator-tracker/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # /submissions, /creators, /picks, /admin/*, /health/*
│   │   ├── models/            # Creator, Source, Pick, CreatorRecord
│   │   ├── scrapers/          # twitter.py (oEmbed + image OCR) is the live one
│   │   ├── pipeline/          # parser.py is live; pipeline.py + extractors are legacy
│   │   ├── services/          # tweet_ingestion, espn_stats, odds_api, outcome_resolver, ...
│   │   └── scheduler/jobs.py  # resolve_pending_outcomes (2h) + capture_closing_odds (30m)
│   ├── scripts/               # admin tools (delete_picks, clear_old_picks, ...)
│   ├── tests/
│   └── main.py
└── frontend/
    └── app/
        ├── page.tsx           # creator cards
        ├── creators/[id]/     # creator detail
        └── submit/            # anonymous URL submission form
```

## Getting Started

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in keys (ANTHROPIC_API_KEY, THE_ODDS_API_KEY, ADMIN_API_KEY, etc.)
alembic upgrade head
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Operations

Admin endpoints require `Authorization: Bearer $ADMIN_API_KEY`:

- `POST /api/v1/admin/reprocess-url` — re-run a tweet through the current pipeline (use after parser/enrichment fixes).
- `POST /api/v1/health/resolve` — manually trigger outcome resolution.
- `GET /api/v1/health/status` — public health snapshot (pending picks, Odds API usage).

Filter-driven cleanup scripts in `backend/scripts/` (`delete_picks.py`, `clear_old_picks.py`) operate against Railway with the public `DATABASE_URL`.

See `CLAUDE.md` for the full architecture reference, anti-spam layers, alias maps, and known gaps.
