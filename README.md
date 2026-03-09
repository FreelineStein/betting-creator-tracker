# Betting Creator Tracker

Track sports betting creators across social media. Log their picks, build a transparent W/L record, and surface tail/fade signals weighted by historical accuracy.

## Architecture

- **Backend:** Python + FastAPI + SQLAlchemy + PostgreSQL
- **Pipeline:** Cascading extraction (caption → subtitles → Whisper → OCR → LLM)
- **Scrapers:** Apify (Instagram, TikTok, Twitter), native APIs (Reddit, YouTube)
- **Scheduler:** APScheduler (migrate to Celery when needed)
- **Frontend:** Next.js

## Project Structure

```
betting-creator-tracker/
├── backend/
│   ├── app/
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── api/routes/     # FastAPI route handlers
│   │   ├── pipeline/       # Extraction pipeline + extractors
│   │   ├── scrapers/       # Platform scraper wrappers
│   │   └── scheduler/      # Background job definitions
│   ├── migrations/         # Alembic DB migrations
│   ├── tests/
│   └── main.py
└── frontend/               # Next.js app
```

## Getting Started

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys

# Run DB migrations
alembic upgrade head

# Start API
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```
