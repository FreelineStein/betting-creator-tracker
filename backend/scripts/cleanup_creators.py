"""
Remove fake/duplicate creators from production DB.
Keeps only the 4 real featured creators.
Run from backend/: python scripts/cleanup_creators.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models import Pick, Source, CreatorRecord, Creator

KEEP_IDS = {
    "3140d455-39ca-453c-bc36-dbbb4cb8772b",  # Trent
    "8b889814-f34d-4ff2-b377-173aa012095a",  # DanAI
    "254eb711-ba38-41e9-9aea-fa699892b100",  # Harry Locks
    "5e27ae57-cd6b-4179-8485-acb6c914c5d8",  # Dr. Locks
}

db = SessionLocal()

all_creators = db.query(Creator).all()
to_delete = [c for c in all_creators if c.creator_id not in KEEP_IDS]

print(f"Found {len(all_creators)} creators, removing {len(to_delete)}:")
for c in to_delete:
    print(f"  - {c.display_name} ({c.creator_id})")

    # Delete picks, sources, and records for this creator
    picks = db.query(Pick).filter(Pick.creator_id == c.creator_id).delete()
    sources = db.query(Source).filter(Source.creator_id == c.creator_id).delete()
    records = db.query(CreatorRecord).filter(CreatorRecord.creator_id == c.creator_id).delete()
    db.query(Creator).filter(Creator.creator_id == c.creator_id).delete()

    print(f"    Deleted {picks} picks, {sources} sources, {records} records")

db.commit()
db.close()

print(f"\nCleanup complete. {len(KEEP_IDS)} creators remain.")
