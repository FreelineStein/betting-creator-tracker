#!/bin/bash
set -e

echo "Running migrations..."
alembic upgrade head

echo "Checking if seed needed..."
CREATOR_COUNT=$(python3 -c "
from app.database import SessionLocal
from app.models import Creator
db = SessionLocal()
count = db.query(Creator).count()
db.close()
print(count)
")

if [ "$CREATOR_COUNT" = "0" ]; then
  echo "Empty database — seeding..."
  python3 seed.py
else
  echo "Database already has $CREATOR_COUNT creators, skipping seed."
fi

echo "Starting server..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
