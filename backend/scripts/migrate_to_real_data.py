"""
One-time migration: wipe all fake seed data and replace with real creators.
Run from backend/: ./venv/bin/python scripts/migrate_to_real_data.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import SessionLocal
from app.models import Pick, Source, CreatorRecord, Creator

db = SessionLocal()

print("Wiping existing data...")

picks = db.query(Pick).delete()
print(f"  Deleted {picks} picks")

sources = db.query(Source).delete()
print(f"  Deleted {sources} sources")

records = db.query(CreatorRecord).delete()
print(f"  Deleted {records} creator records")

creators = db.query(Creator).delete()
print(f"  Deleted {creators} creators")

db.commit()
db.close()

print("\nRunning seed with real creators...")
exec(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "seed.py")).read())

print(f"\nMigration complete.")
