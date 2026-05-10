"""
Read-only probe — for each pinned pending pick, call
find_completed_game_by_event_id and report exactly what happens.

Run when the resolver's pinned path is silently leaving picks pending
and we need to find out whether ESPN returns the game, whether the ID
matches, whether `completed` is true, etc.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.probe_pinned_lookup
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Pick, PickStatus  # noqa: E402
from app.services.espn_stats import (  # noqa: E402
    find_completed_game_by_event_id,
    get_scheduled_games,
)


async def probe_one(pick: Pick) -> None:
    sport = pick.sport
    event_id = pick.event_id
    anchor = pick.event_date
    print(
        f"\n[{pick.pick_id[:8]}] {sport} {pick.pick_type} "
        f"event={pick.event!r} pinned_event_id={event_id} anchor={anchor.isoformat()}"
    )

    games = await get_scheduled_games(sport, anchor_date=anchor)
    print(f"  get_scheduled_games returned {len(games)} games")
    ids_returned = [g.game_id for g in games]
    if event_id in ids_returned:
        match = next(g for g in games if g.game_id == event_id)
        print(
            f"  ID match: {match.away_team} @ {match.home_team} "
            f"commence={match.commence_time.isoformat()} "
            f"completed={match.completed} "
            f"score={match.away_score}-{match.home_score}"
        )
    else:
        # Show what IDs came back so we can see the gap
        print(f"  pinned ID NOT in scoreboard. Returned IDs:")
        for g in games[:10]:
            print(f"    {g.game_id} — {g.away_team} @ {g.home_team} ({g.commence_time.date()})")
        if len(games) > 10:
            print(f"    ...and {len(games) - 10} more")

    sched = await find_completed_game_by_event_id(sport, event_id, anchor_date=anchor)
    if sched is None:
        print(f"  find_completed_game_by_event_id returned None")
    else:
        print(
            f"  find_completed_game_by_event_id returned "
            f"completed={sched.completed} score={sched.away_score}-{sched.home_score}"
        )


async def main() -> int:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(Pick)
            .filter(Pick.status == PickStatus.pending)
            .filter(Pick.event_id.isnot(None))
            .filter(Pick.event_provider == "espn")
            .filter(Pick.event_date.isnot(None))
            .filter(Pick.event_date < now)
            .filter(Pick.pick_type.in_(["moneyline", "spread", "over_under"]))
            .order_by(Pick.event_date.asc())
            .limit(5)
            .all()
        )
        if not rows:
            print("No straightforward pinned spread/ML picks to probe.")
            return 0
        print(f"Probing {len(rows)} pinned spread/ML/total picks...")
        for pick in rows:
            await probe_one(pick)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
