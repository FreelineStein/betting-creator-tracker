#!/bin/bash
# Start the full local dev stack
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "⚡ Starting Betting Creator Tracker"
echo ""

# 1. Start Postgres
echo "▶ Starting Postgres..."
docker compose up -d db
sleep 2

# 2. Backend setup
echo "▶ Setting up backend..."
cd "$BACKEND"
if [ ! -d "venv" ]; then
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt -q
fi

# Copy .env if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  # Set DB URL for local Docker Postgres
  sed -i '' 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:postgres@localhost:5432/betting_creator_tracker|' .env
fi

# Run migrations
echo "▶ Running migrations..."
./venv/bin/alembic upgrade head

# Seed data if DB is empty
CREATOR_COUNT=$(./venv/bin/python3 -c "
from dotenv import load_dotenv; load_dotenv()
from app.database import SessionLocal
from app.models import Creator
db = SessionLocal()
print(db.query(Creator).count())
db.close()
" 2>/dev/null || echo "0")

if [ "$CREATOR_COUNT" = "0" ]; then
  echo "▶ Seeding sample data..."
  ./venv/bin/python3 seed.py
fi

# 3. Start backend in background
echo "▶ Starting API on http://localhost:8000 ..."
./venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# 4. Frontend setup
echo "▶ Setting up frontend..."
cd "$FRONTEND"
if [ ! -d "node_modules" ]; then
  npm install --silent
fi

echo "▶ Starting frontend on http://localhost:3000 ..."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Frontend: http://localhost:3000"
echo "  API:      http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Trap to kill API on exit
trap "kill $API_PID 2>/dev/null" EXIT

npm run dev
