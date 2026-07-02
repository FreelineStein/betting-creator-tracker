# CLAUDE.md — PickReceipts (Betting Creator Tracker)

This file is self-contained architecture/reference for the repo (stack, structure, data flow, admin tooling, commands). The vault mirror at `/Users/jacobstein/Brain/Projects/Pick-Receipts/CLAUDE.md` holds the higher-level goal, current-state narrative, and the *why* behind key decisions — check it for that context; don't duplicate it here.

## Project Goal

Track sports betting creators across social media. Ingest their public posts, extract picks via an LLM-driven pipeline, build transparent W/L records, and surface tail/fade signals weighted by historical accuracy.

## Stack

- **Backend:** Python 3 + FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Next.js 14 (App Router) + Tailwind, deployed on Vercel
- **Infra:** Railway (backend + Postgres), Vercel (frontend)
- **Scheduler:** APScheduler (in-process, fine for the single-worker MVP deploy)
- **Anti-spam (submissions):** Cloudflare Turnstile + slowapi rate limit + honeypot + URL regex

## Project Structure

```
betting-creator-tracker/
├── backend/
│   ├── main.py                        # FastAPI app entry point
│   ├── app/
│   │   ├── config.py                  # Settings from env vars (env-var indirection pattern)
│   │   ├── models/
│   │   │   ├── creator.py             # Creator profile + tier + platforms JSON + tracking_active
│   │   │   ├── source.py              # One ingested post — platform, post_url (unique), raw_content
│   │   │   ├── pick.py                # One bet — sport, type, detail, status, extraction_method
│   │   │   └── record.py              # Aggregated W/L/push record per creator
│   │   ├── api/
│   │   │   ├── deps.py                # require_admin (Bearer token check)
│   │   │   └── routes/
│   │   │       ├── submissions.py     # POST /submissions — anonymous user pick submission (Turnstile + rate-limit + honeypot)
│   │   │       ├── scrape.py          # POST /scrape/tweets — admin batch URL submission
│   │   │       ├── creators.py        # CRUD + record recompute
│   │   │       ├── picks.py           # CRUD + parlay leg updates; DELETE recomputes record
│   │   │       ├── admin.py           # POST /admin/reprocess-url — re-run a URL through current pipeline
│   │   │       └── health.py          # /health/status + manual /resolve trigger
│   │   ├── scrapers/
│   │   │   ├── base.py                # RawPost dataclass + BaseScraper ABC
│   │   │   ├── twitter.py             # oEmbed via publish.twitter.com + fxtwitter image extraction + Claude vision OCR; concurrency-bounded
│   │   │   ├── instagram.py           # Apify (legacy, not used in submission flow)
│   │   │   └── reddit.py              # Reddit JSON API (legacy)
│   │   ├── pipeline/
│   │   │   ├── pipeline.py            # Legacy cascade orchestrator (caption→subtitles→whisper→OCR→LLM); unreachable now that scrape_all_creators is gone — kept as a reference for a future ingestion path
│   │   │   ├── parser.py              # ParsedPick dataclass + LLM pick parsing (Anthropic / OpenAI fallback)
│   │   │   └── extractors/            # caption, subtitles, whisper, ocr, llm
│   │   ├── services/
│   │   │   ├── tweet_ingestion.py     # Shared per-tweet flow: caption→image-OCR→parse→opponent enrichment→DB writes
│   │   │   ├── creator_lookup.py      # find_or_create_creator_by_twitter_handle (auto-create with tracking_active=False)
│   │   │   ├── turnstile.py           # Cloudflare Turnstile siteverify
│   │   │   ├── espn_stats.py          # ESPN scoreboard + box-score client; opponent enrichment via get_scheduled_games + find_opponent_in_schedule; nickname alias map
│   │   │   ├── outcome_resolver.py    # spread/moneyline/over_under via The Odds API; props via ESPN; per-leg parlay
│   │   │   ├── odds_api.py            # The Odds API client (completed game scores)
│   │   │   ├── odds_api_budget.py     # In-memory monthly request counter (450/month cap)
│   │   │   └── record_updater.py      # recompute_record(creator_id, db) — derives totals from Pick history
│   │   └── scheduler/
│   │       └── jobs.py                # resolve_pending_outcomes (every 2h, ESPN-first then Odds API fallback) + capture_closing_odds (every 30m)
│   ├── scripts/                       # Admin / cleanup tools (run with DATABASE_URL set)
│   │   ├── clear_old_picks.py         # Bulk delete by --before cutoff + recompute records
│   │   ├── delete_picks.py            # Filter-driven delete (--id / --creator / --team / --event / --sport / --status / --before)
│   │   ├── seed.py                    # Seed initial creators
│   │   ├── cleanup_creators.py
│   │   └── migrate_to_real_data.py
│   ├── migrations/                    # Alembic
│   ├── tests/
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── page.tsx                   # Homepage — creator cards (filtered to active picks)
    │   ├── creators/[id]/page.tsx     # Creator detail (full pick history)
    │   ├── submit/                    # /submit — anonymous URL submission form
    │   │   ├── page.tsx               # Server shell, reads NEXT_PUBLIC_TURNSTILE_SITE_KEY
    │   │   └── SubmitForm.tsx         # Client form + Turnstile widget + honeypot + success panel
    │   ├── lib/api.ts                 # Typed API client (incl. submitPick)
    │   └── components/
    │       ├── CreatorCards.tsx       # Homepage card with isActive filter
    │       └── ...
    └── components/
        ├── Logo.tsx
        └── brand.tsx                  # Button, Badge, StatCard, WLRecord
```

## Data Flow

```
USER SUBMISSION (primary ingestion path)
  User pastes X URL on /submit
    → Turnstile + URL regex + honeypot + 10/hr per-IP rate limit
      → POST /api/v1/submissions
        → TwitterScraper.fetch_tweets() via publish.twitter.com/oembed
          → find_or_create_creator_by_twitter_handle (soft-gate new creators)
            → ingest_tweet_for_creator:
                  caption → if no picks, fxtwitter image URL → Claude vision OCR
                    → parse_picks (Claude Haiku / GPT-4o-mini fallback)
                      → enrich opponents via ESPN scoreboard (free, no quota)
                        → DB: Source + Pick rows

SCHEDULER (every 15m)
  resolve_pending_outcomes
    → pending picks with past event_date
      → The Odds API (spread/moneyline/over_under) + ESPN box scores (props) + per-leg parlay resolution
        → outcome_resolver → record_updater
```

## Key Data Models

- **Creator** — profile, tier (`tracked` / `public`), platforms JSON, profile_image_url, **tracking_active** (auto-created creators land at `False` and are hidden from public lists / scheduler until approved)
- **Source** — one ingested post; `post_url` is the dedup key; `extraction_status` ∈ {pending, success, failed, needs_review}
- **Pick** — one bet; `pick_type` ∈ {spread, moneyline, over_under, prop, parlay}; parlay `pick_detail.legs[]` are independently resolvable
- **CreatorRecord** — 1-to-1 with Creator; rebuild from Pick history via `recompute_record`

## Submission Flow Anti-spam

Layered defense, in order of cost (cheapest fail-fast first):

1. **Honeypot field** — hidden form input named `website`. Real users never fill it; bots that auto-fill all fields will. Non-empty value returns silent 200 without processing.
2. **URL regex** — strict match on `https?://(www\.|mobile\.)?(twitter\.com|x\.com)/<handle>/status/<digits>`. Rejects fxtwitter proxies, off-platform links, malformed URLs.
3. **slowapi rate limit** — `@limiter.limit("10/hour")` per IP. In-memory; fine for the single-worker Railway deploy.
4. **Cloudflare Turnstile** — server-side token verification against the secret key. Frontend renders the widget; backend POSTs to `challenges.cloudflare.com/turnstile/v0/siteverify`.
5. **Authoritative live fetch** — oEmbed call itself. If X returns 404 or no parseable text, the submission is rejected with a friendly error.

## Opponent Resolution

After parsing, picks where the parser only captured one team (e.g., post says "Cavs ML") get enriched via ESPN's free scoreboard:

- `get_scheduled_games(sport, days_back=1, days_ahead=5)` walks today ±1/+4 days
- `find_opponent_in_schedule(team, games)` matches via case-insensitive containment + a curated `_NICKNAME_ALIASES` map (Cavs→Cavaliers, Mavs→Mavericks, Avs→Avalanche, Sixers→76ers, Habs→Canadiens, etc.)
- On success, `pick_detail.team` is normalized to the canonical short name and `event` is set to "<Team> vs <Opponent>"; `event_date` defaults to the game's commence_time when the parser missed it
- Misses log a `team_alias_miss` warning so we can see what aliases to add

## Outcome Resolution

| Pick type    | Resolver | Notes |
|--------------|----------|-------|
| Spread       | The Odds API completed scores | `find_matching_game` via team-name containment |
| Moneyline    | The Odds API completed scores | |
| Over/Under   | The Odds API completed scores | |
| Prop         | ESPN box score (`espn_stats.find_player_stat`) | NBA/NFL/NHL/MLB; combo props supported |
| Parlay       | Per-leg, then aggregated by `_parlay_status_from_legs` | A single losing leg loses the parlay |

ROI is reported as percentage points above the −110 break-even rate (52.4%).

## Admin Tooling

All admin operations require `Authorization: Bearer $ADMIN_API_KEY`.

- **`POST /api/v1/admin/reprocess-url`** body `{"url": "..."}` — fetches the tweet, deletes existing Source+Picks for that URL (any twitter.com/x.com variant), re-ingests under the current pipeline, recomputes the creator's record. Use after any parser/enrichment/alias improvement to retroactively apply.
- **`DELETE /api/v1/picks/{id}`** — single pick delete; recomputes the creator's record after.
- **`backend/scripts/delete_picks.py`** — filter-driven CLI: `--id`, `--creator-id`, `--creator-name`, `--team`, `--event`, `--sport`, `--pick-type`, `--status`, `--before`, `--after`. Refuses to run with no filter. Always `--dry-run` first.
- **`backend/scripts/clear_old_picks.py`** — bulk delete picks before a UTC cutoff, deletes orphaned sources, recomputes affected records.

## External Services & API Keys

| Service        | Env Var (`*_ENV` indirection used everywhere) | Used For                                   |
|----------------|-----------------------------------------------|--------------------------------------------|
| Anthropic      | `ANTHROPIC_API_KEY`                           | Pick parsing (claude-haiku-4-5) + image OCR |
| OpenAI         | `OPENAI_API_KEY`                              | Parser fallback                            |
| Apify          | `APIFY_API_TOKEN`                             | Legacy scrapers (Instagram/Reddit; not used by submissions) |
| The Odds API   | `THE_ODDS_API_KEY`                            | Outcome resolution (450/month budget)      |
| ESPN           | none — public                                  | Opponent enrichment + prop box scores      |
| Cloudflare     | `TURNSTILE_SECRET_KEY` (server) / `NEXT_PUBLIC_TURNSTILE_SITE_KEY` (frontend) | Submission anti-spam |
| Admin          | `ADMIN_API_KEY`                               | Bearer auth for write endpoints            |

System tools required for the legacy video pipeline (only on the scheduler path, not the submission path): `yt-dlp`, `ffmpeg`, `faster-whisper`, `easyocr`.

CORS allowlist: `ALLOWED_ORIGINS` (comma-separated). Production includes `https://pickreceipts.com` and `https://www.pickreceipts.com`.

## Known Gaps

- YouTube and TikTok ingestion not implemented (would each need a scraper + auth)
- Submission rate-limit / Turnstile budget are in-memory; both reset on every Railway redeploy. Fine at MVP scale.
- `team_alias_miss` log is the only feedback loop for missing nicknames — no automated alias generation
- No admin UI; admin work happens via curl + admin key or via me running the scripts when prompted
- LLM-based opponent inference for completed games not in ESPN's window will fail silently (returns no opponent fill-in)
- Auto-created creators sit at `tracking_active=False` indefinitely until manually flipped — no notification flow for review

## Commands

```bash
# Backend (assumes venv created from requirements.txt)
cd backend && source venv/bin/activate
uvicorn main:app --reload          # local dev server on :8000
alembic upgrade head               # run migrations
pytest tests/                      # run tests

# Backend admin scripts (run against Railway with public DATABASE_URL)
DATABASE_URL='postgresql://...@caboose.proxy.rlwy.net:.../railway' \
  ./venv/bin/python -m scripts.delete_picks --team Lakers --dry-run
DATABASE_URL='...' ./venv/bin/python -m scripts.clear_old_picks --before "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)" --yes

# Reprocess a URL through the current pipeline
curl -X POST https://believable-mindfulness-production-12eb.up.railway.app/api/v1/admin/reprocess-url \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://x.com/handle/status/..."}'

# Frontend
cd frontend
npm run dev                        # localhost:3000 — uses test Turnstile keys by default
```
