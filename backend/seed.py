"""
Seed the database with sample creators, picks, and records for local dev.
Run: ./venv/bin/python seed.py
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
import random
from dotenv import load_dotenv

load_dotenv()

from app.database import SessionLocal, engine
from app.database import Base
from app.models import (
    Creator, CreatorTier,
    Source, Platform, PostType, ExtractionStatus,
    Pick, PickType, PickStatus, ExtractionMethod,
    CreatorRecord,
)

# Create tables if they don't exist (safe to run on existing DB)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

SPORTS = ["NFL", "NBA", "MLB", "NHL", "CFB"]
TEAMS = {
    "NFL": [("Chiefs", "Raiders"), ("Eagles", "Cowboys"), ("49ers", "Seahawks"), ("Bills", "Patriots")],
    "NBA": [("Lakers", "Celtics"), ("Warriors", "Suns"), ("Bucks", "Heat"), ("Nuggets", "Clippers")],
    "MLB": [("Yankees", "Red Sox"), ("Dodgers", "Giants"), ("Astros", "Rangers"), ("Braves", "Mets")],
    "NHL": [("Avalanche", "Blues"), ("Rangers", "Bruins"), ("Oilers", "Flames"), ("Panthers", "Lightning")],
    "CFB": [("Alabama", "Georgia"), ("Ohio State", "Michigan"), ("Texas", "Oklahoma"), ("USC", "UCLA")],
}

CREATORS = [
    {
        "display_name": "SharpBettor99",
        "platforms": [
            {"platform": "twitter", "handle": "@SharpBettor99", "url": "https://twitter.com/SharpBettor99"},
            {"platform": "instagram", "handle": "@sharpbettor99", "url": "https://instagram.com/sharpbettor99"},
        ],
        "win_rate": 0.61,
        "total": 87,
    },
    {
        "display_name": "LineMoverMike",
        "platforms": [
            {"platform": "instagram", "handle": "@linemovermike", "url": "https://instagram.com/linemovermike"},
            {"platform": "youtube", "handle": "LineMoverMike", "url": "https://youtube.com/@linemovermike"},
        ],
        "win_rate": 0.54,
        "total": 63,
    },
    {
        "display_name": "ParlayPrince",
        "platforms": [
            {"platform": "tiktok", "handle": "@parlayprince", "url": "https://tiktok.com/@parlayprince"},
            {"platform": "twitter", "handle": "@ParlayPrince", "url": "https://twitter.com/ParlayPrince"},
        ],
        "win_rate": 0.47,
        "total": 112,
    },
    {
        "display_name": "ValueVince",
        "platforms": [
            {"platform": "twitter", "handle": "@ValueVince", "url": "https://twitter.com/ValueVince"},
        ],
        "win_rate": 0.58,
        "total": 45,
    },
    {
        "display_name": "FadeThePub",
        "platforms": [
            {"platform": "reddit", "handle": "u/FadeThePub", "url": "https://reddit.com/u/FadeThePub"},
            {"platform": "twitter", "handle": "@FadeThePub", "url": "https://twitter.com/FadeThePub"},
        ],
        "win_rate": 0.55,
        "total": 78,
    },
]


def random_pick_type():
    return random.choice([PickType.spread, PickType.moneyline, PickType.over_under, PickType.prop])


def random_odds(pick_type):
    if pick_type == PickType.moneyline:
        return random.choice(["-130", "-150", "-110", "+120", "+145", "+200", "-200"])
    return random.choice(["-110", "-115", "-105", "+100"])


def random_pick_detail(sport, pick_type):
    home, away = random.choice(TEAMS[sport])
    team = random.choice([home, away])
    if pick_type == PickType.spread:
        line = round(random.choice([-7, -6.5, -4.5, -3.5, -3, -1.5, 1.5, 3, 3.5, 4.5, 6.5, 7]), 1)
        return {"team": team, "line": f"{'+' if line > 0 else ''}{line}"}
    elif pick_type == PickType.moneyline:
        return {"team": team}
    elif pick_type == PickType.over_under:
        total = round(random.uniform(38, 58), 1)
        direction = random.choice(["Over", "Under"])
        return {"direction": direction, "total": total}
    else:
        player = f"{team} Player"
        return {"player": player, "prop": "Points", "line": str(random.randint(15, 30))}


def make_outcome(win_rate):
    r = random.random()
    if r < win_rate:
        return PickStatus.won
    elif r < win_rate + 0.05:
        return PickStatus.push
    else:
        return PickStatus.lost


now = datetime.now(timezone.utc)

for c_data in CREATORS:
    creator = Creator(
        creator_id=str(uuid.uuid4()),
        display_name=c_data["display_name"],
        tier=CreatorTier.tracked,
        platforms=c_data["platforms"],
        tracking_active=True,
    )
    db.add(creator)
    db.flush()

    wins = losses = pushes = 0
    sport_stats = {}

    total = c_data["total"]
    # Last 10 picks: mix of pending + resolved; rest are historical resolved
    for i in range(total):
        days_ago = random.randint(1, 90)
        event_date = now - timedelta(days=days_ago)
        sport = random.choice(SPORTS)
        pick_type = random_pick_type()

        is_pending = i >= total - 5 and days_ago <= 2

        source = Source(
            source_id=str(uuid.uuid4()),
            creator_id=creator.creator_id,
            platform=c_data["platforms"][0]["platform"],
            post_type=PostType.tweet if c_data["platforms"][0]["platform"] == "twitter" else PostType.reel,
            post_url=f"https://example.com/post/{uuid.uuid4().hex[:8]}",
            posted_at=event_date - timedelta(hours=random.randint(2, 24)),
            raw_content=f"{creator.display_name} pick: {sport} game",
            extraction_status=ExtractionStatus.success,
            extraction_attempts=[{"method": "caption", "success": True, "confidence": 0.85}],
        )
        db.add(source)
        db.flush()

        status = PickStatus.pending if is_pending else make_outcome(c_data["win_rate"])

        pick = Pick(
            pick_id=str(uuid.uuid4()),
            source_id=source.source_id,
            creator_id=creator.creator_id,
            sport=sport,
            event=" vs ".join(random.choice(TEAMS[sport])),
            event_date=event_date,
            pick_type=pick_type,
            pick_detail=random_pick_detail(sport, pick_type),
            odds=random_odds(pick_type),
            units=round(random.uniform(0.5, 3.0), 1),
            status=status,
            outcome_resolved_at=event_date + timedelta(hours=4) if status != PickStatus.pending else None,
            extraction_method=ExtractionMethod.caption,
            extraction_confidence=0.85,
        )
        db.add(pick)

        if status == PickStatus.won:
            wins += 1
            sport_stats.setdefault(sport, {"wins": 0, "losses": 0})
            sport_stats[sport]["wins"] += 1
        elif status == PickStatus.lost:
            losses += 1
            sport_stats.setdefault(sport, {"wins": 0, "losses": 0})
            sport_stats[sport]["losses"] += 1
        elif status == PickStatus.push:
            pushes += 1

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
    record = CreatorRecord(
        creator_id=creator.creator_id,
        total_picks=total,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=round(win_rate, 3),
        roi=round((win_rate - 0.524) * 100, 1),  # simplified ROI vs break-even
        accuracy_by_sport=sport_stats,
        last_updated=now,
    )
    db.add(record)
    print(f"  ✓ {creator.display_name}: {wins}W-{losses}L-{pushes}P ({win_rate:.1%})")

db.commit()
db.close()
print("\nSeed complete.")
