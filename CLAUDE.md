# CLAUDE.md — Betting Creator Tracker

## Project Goal

Track sports betting creators across social media. Scrape their posts, extract picks via a cascading pipeline, build transparent W/L records, and surface tail/fade signals weighted by historical accuracy.

## Stack

- **Backend:** Python 3 + FastAPI + SQLAlchemy + PostgreSQL
- **Frontend:** Next.js (deployed on Vercel)
- **Infra:** Railway (backend + Postgres), Vercel (frontend)
- **Scheduler:** APScheduler (planned migration to Celery)

## Project Structure

```
betting-creator-tracker/
├── backend/
│   ├── main.py                        # FastAPI app entry point
│   ├── app/
│   │   ├── config.py                  # Settings from env vars
│   │   ├── models/
│   │   │   ├── creator.py             # Creator profile + tier + platforms JSON
│   │   │   ├── source.py              # Scraped post record (platform, URL, raw content)
│   │   │   ├── pick.py                # Individual pick (sport, type, detail, status)
│   │   │   └── record.py              # Aggregated W/L/push record per creator
│   │   ├── api/routes/                # FastAPI route handlers
│   │   ├── scrapers/
│   │   │   ├── base.py                # RawPost dataclass + BaseScraper ABC
│   │   │   ├── twitter.py             # Apify twitter-scraper actor
│   │   │   ├── instagram.py           # Apify instagram-reel-scraper actor
│   │   │   └── reddit.py              # Reddit public JSON API
│   │   ├── pipeline/
│   │   │   ├── pipeline.py            # Cascade orchestrator (confidence threshold 0.6)
│   │   │   ├── caption.py             # CaptionExtractor — text from caption/description
│   │   │   ├── subtitles.py           # SubtitleExtractor — auto-captions/transcripts
│   │   │   ├── whisper.py             # WhisperExtractor — faster-whisper on video audio
│   │   │   ├── ocr.py                 # OCRExtractor — easyocr on video frames via ffmpeg
│   │   │   ├── llm.py                 # LLMExtractor — last-resort LLM summarization
│   │   │   └── parser.py              # ParsedPick output + LLM pick parsing
│   │   ├── services/
│   │   │   ├── outcome_resolver.py    # Determines W/L/push from game scores
│   │   │   ├── record_updater.py      # Recomputes CreatorRecord from pick history
│   │   │   └── odds_api.py            # The Odds API client for game scores
│   │   └── scheduler/
│   │       └── jobs.py                # scrape_all_creators (2h), resolve_pending_outcomes (30m)
│   ├── migrations/                    # Alembic
│   ├── tests/
│   ├── seed.py
│   └── requirements.txt
└── frontend/                          # Next.js app
    ├── app/
    ├── components/
    └── package.json
```

## Data Flow

```
Scheduler (every 2h)
  → Scraper (platform-specific) → RawPost
    → Extraction Pipeline (cascade: caption → subtitles → whisper → OCR → LLM)
      → Parser (LLM call) → ParsedPick
        → DB: Source + Pick records

Scheduler (every 30m)
  → Query pending picks with past event_date
    → The Odds API (game scores)
      → Outcome Resolver (W/L/push)
        → Record Updater (recompute CreatorRecord)
```

## Key Data Models

- **Creator**: profile, tier (tracked/public), platforms JSON array, tracking_active flag
- **Source**: one scraped post — platform, post_url (unique), raw_content, extraction_status/attempts
- **Pick**: one bet — sport, event, pick_type (spread/moneyline/over_under/prop/parlay), pick_detail JSON, odds, units, status (pending/won/lost/push/void), extraction_method, confidence
- **CreatorRecord**: 1-to-1 with Creator — wins, losses, pushes, win_rate, roi, accuracy_by_sport JSON

## Scraper Architecture

All scrapers implement `BaseScraper.fetch_recent_posts(handle, since) → list[RawPost]`.

`RawPost` is the normalized interchange format: platform, post_type, post_url, posted_at, caption, description, subtitles, video_url, raw metadata.

| Platform  | Method                        | Status      |
|-----------|-------------------------------|-------------|
| Twitter/X | Apify `twitter-scraper`       | Implemented |
| Instagram | Apify `instagram-reel-scraper`| Implemented |
| Reddit    | Public JSON API               | Implemented |
| YouTube   | YouTube Data API              | Not started |
| TikTok    | Apify or unofficial API       | Not started |

## Extraction Pipeline

Cascading design — tries extractors cheapest-first, stops when confidence ≥ 0.6:

1. **CaptionExtractor** (0.5–1.0) — regex keyword scoring on caption/description text
2. **SubtitleExtractor** (0.8) — auto-captions or transcript fields
3. **WhisperExtractor** (0.85) — faster-whisper transcription of video audio via yt-dlp
4. **OCRExtractor** (0.7) — easyocr on video frames extracted by ffmpeg at 1fps
5. **LLMExtractor** (0.5–1.0) — last resort, gathers all available text and calls LLM

Parser uses Claude Haiku (or GPT-4o-mini fallback) to structure extracted text into `ParsedPick` objects.

## Outcome Resolution

- **Moneyline, Spread, Over/Under**: Fully implemented via The Odds API scores
- **Props**: Not yet implemented (needs player stats API)
- **Parlays**: Not yet implemented (needs leg-by-leg resolution)
- ROI calculated as percentage points above 52.4% break-even (standard -110 juice)

## External Services & API Keys

| Service        | Env Var               | Used For                          |
|----------------|----------------------|-----------------------------------|
| Anthropic      | `ANTHROPIC_API_KEY`  | Pick parsing (claude-haiku-4-5)   |
| OpenAI         | `OPENAI_API_KEY`     | Fallback for parsing              |
| Apify          | `APIFY_API_TOKEN`    | Twitter + Instagram scraping      |
| The Odds API   | `THE_ODDS_API_KEY`   | Game scores for outcome resolution|
| Reddit         | Public API (no auth) | Reddit scraping                   |
| YouTube        | `YOUTUBE_API_KEY`    | Future YouTube scraper            |

System tools required: `yt-dlp`, `ffmpeg`, `faster-whisper`, `easyocr`.

## Known Gaps

- YouTube and TikTok scrapers not yet built
- Props and parlay outcome resolution not yet implemented
- Extraction method tracking is hardcoded to `caption` in jobs.py (should pass through from pipeline)
- Failed extraction notifications are log-only (no webhook/Discord integration)
- Pipeline not yet battle-tested on real diverse content across platforms

## Commands

```bash
# Backend
cd backend && source venv/bin/activate
uvicorn main:app --reload
alembic upgrade head          # run migrations
pytest tests/                 # run tests

# Frontend
cd frontend
npm run dev
```
