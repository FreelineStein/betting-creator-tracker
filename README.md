# 🧾 Pick Receipts

Transparent W/L records for sports betting creators. Track picks across social media, build verifiable records, and identify winners vs. faders with no cherrypicking.

## Architecture

- **Backend:** Python + FastAPI + SQLAlchemy + PostgreSQL
- **Pipeline:** Cascading extraction (caption → subtitles → Whisper → OCR → LLM)
- **Scrapers:** Apify (Instagram, TikTok, Twitter), native APIs (Reddit, YouTube)
- **Scheduler:** APScheduler (migrate to Celery when needed)
- **Frontend:** Next.js

## Project Structure

```
pick-receipts/
├── backend/
│   ├── app/
│   │   ├── models/         # Creator, Pick, Source, Record models
│   │   ├── api/routes/     # /creators, /picks endpoints
│   │   ├── pipeline/       # Extraction pipeline (caption, OCR, LLM, etc.)
│   │   ├── scrapers/       # Instagram, Twitter, YouTube, Reddit
│   │   └── scheduler/      # Background jobs
│   ├── migrations/         # Database migrations
│   ├── tests/
│   └── main.py
└── frontend/               # Next.js + Tailwind
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
