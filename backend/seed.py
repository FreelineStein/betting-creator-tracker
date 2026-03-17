"""
Seed the database with real creators.
Idempotent — skips creators that already exist by display_name.
Run: ./venv/bin/python seed.py
"""
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from app.database import SessionLocal, engine, Base
from app.models import Creator, CreatorTier, CreatorRecord

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

REAL_CREATORS = [
    {
        "display_name": "Trent",
        "platforms": [
            {"platform": "twitter", "handle": "@BookitWithTrent", "url": "https://twitter.com/BookitWithTrent"},
        ],
    },
    {
        "display_name": "DanAI",
        "platforms": [
            {"platform": "twitter", "handle": "@DanGambleAI", "url": "https://twitter.com/DanGambleAI"},
        ],
    },
    {
        "display_name": "Gavin",
        "platforms": [
            {"platform": "twitter", "handle": "@gavinmchughh", "url": "https://twitter.com/gavinmchughh"},
        ],
    },
    {
        "display_name": "Harry Locks",
        "platforms": [
            {"platform": "twitter", "handle": "@HarryLockPicks", "url": "https://twitter.com/HarryLockPicks"},
        ],
    },
]

db = SessionLocal()

now = datetime.now(timezone.utc)
created = 0
skipped = 0

for c_data in REAL_CREATORS:
    existing = db.query(Creator).filter(Creator.display_name == c_data["display_name"]).first()
    if existing:
        print(f"  - {c_data['display_name']}: already exists, skipping")
        skipped += 1
        continue

    creator = Creator(
        creator_id=str(uuid.uuid4()),
        display_name=c_data["display_name"],
        tier=CreatorTier.tracked,
        platforms=c_data["platforms"],
        tracking_active=True,
    )
    db.add(creator)
    db.flush()

    # Initialize empty record
    record = CreatorRecord(
        creator_id=creator.creator_id,
        total_picks=0,
        wins=0,
        losses=0,
        pushes=0,
        win_rate=0.0,
        roi=0.0,
        accuracy_by_sport={},
        last_updated=now,
    )
    db.add(record)

    print(f"  + {c_data['display_name']}: created ({creator.creator_id})")
    created += 1

db.commit()
db.close()
print(f"\nSeed complete. Created: {created}, Skipped: {skipped}")
