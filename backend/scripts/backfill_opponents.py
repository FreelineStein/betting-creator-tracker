"""
Backfill `event` for picks that were saved before the opponent-resolution
deploy — anything stored as e.g. "Cavs vs Opponent" or just "Cavs" gets
upgraded to "Cavs vs Pistons" via The Odds API.

Usage:

    DATABASE_URL='<railway public postgres url>' THE_ODDS_API_KEY='...' \
        ./venv/bin/python -m scripts.backfill_opponents --dry-run

Drop --dry-run to commit. Add --yes to skip the prompt.

Reads THE_ODDS_API_KEY the same way the live backend does (via .env or
the explicit env var). Calls /sports/{key}/events once per sport (cached
for 30min in-process), so the cost is bounded by the number of distinct
sports across stale picks.

Parlays are handled too — each leg's `event` is updated independently.
"""
import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

# Allow `python -m scripts.backfill_opponents` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Pick  # noqa: E402
from app.services.odds_api import find_opponent, get_upcoming_games  # noqa: E402

PLACEHOLDER_TOKENS = {"opponent", "tbd", "unknown", "other", "n/a"}


def event_needs_lookup(event: Optional[str], team: Optional[str]) -> bool:
    if not event:
        return bool(team)
    cleaned = event.strip().lower()
    if any(tok in cleaned for tok in PLACEHOLDER_TOKENS):
        return True
    return " vs " not in cleaned and " vs. " not in cleaned and " @ " not in cleaned


def team_from_pick_row(pick: Pick) -> Optional[str]:
    detail = pick.pick_detail or {}
    team = detail.get("team")
    if team:
        return str(team).strip()
    if pick.event:
        first = pick.event.split(" vs ")[0].split(" @ ")[0].strip()
        if first.lower() not in PLACEHOLDER_TOKENS:
            return first
    return None


def team_from_leg(leg: dict) -> Optional[str]:
    detail = leg.get("detail") or {}
    team = detail.get("team")
    if team:
        return str(team).strip()
    event = leg.get("event")
    if event:
        first = event.split(" vs ")[0].split(" @ ")[0].strip()
        if first.lower() not in PLACEHOLDER_TOKENS:
            return first
    return None


async def run(dry_run: bool, skip_confirm: bool) -> int:
    db = SessionLocal()
    try:
        all_picks = db.query(Pick).all()

        # First pass — figure out which picks/legs need lookup, grouped by sport.
        sports_needed: set[str] = set()
        candidates: list[tuple[Pick, str]] = []         # (pick, team) for top-level picks
        leg_candidates: list[tuple[Pick, int, str]] = [] # (pick, leg_index, team) for parlay legs

        for pick in all_picks:
            if pick.sport:
                team = team_from_pick_row(pick)
                if team and event_needs_lookup(pick.event, team):
                    candidates.append((pick, team))
                    sports_needed.add(pick.sport)
            if pick.pick_type == "parlay":
                legs = (pick.pick_detail or {}).get("legs") or []
                for i, leg in enumerate(legs):
                    sport = leg.get("sport")
                    team = team_from_leg(leg)
                    if sport and team and event_needs_lookup(leg.get("event"), team):
                        leg_candidates.append((pick, i, team))
                        sports_needed.add(sport)

        print("=== Plan ===")
        print(f"Total picks scanned:           {len(all_picks)}")
        print(f"Top-level picks needing lookup: {len(candidates)}")
        print(f"Parlay legs needing lookup:     {len(leg_candidates)}")
        print(f"Sports to query:                {sorted(sports_needed) or '(none)'}")

        if not candidates and not leg_candidates:
            print("\nNothing to do — every pick already has both teams.")
            return 0

        # Fetch upcoming games once per sport.
        games_by_sport = {}
        for sport in sports_needed:
            games_by_sport[sport] = await get_upcoming_games(sport)
            print(f"  {sport}: {len(games_by_sport[sport])} upcoming games loaded")

        # Plan updates.
        pick_updates = []
        leg_updates = []
        for pick, team in candidates:
            found = find_opponent(team, games_by_sport.get(pick.sport, []))
            if found:
                opponent, commence = found
                pick_updates.append((pick, team, opponent, commence))

        for pick, leg_idx, team in leg_candidates:
            sport = pick.pick_detail["legs"][leg_idx].get("sport")
            found = find_opponent(team, games_by_sport.get(sport, []))
            if found:
                opponent, _commence = found
                leg_updates.append((pick, leg_idx, team, opponent))

        print(f"\nResolved opponents for {len(pick_updates)} picks, {len(leg_updates)} legs.")
        unresolved = (len(candidates) - len(pick_updates)) + (len(leg_candidates) - len(leg_updates))
        if unresolved:
            print(f"Unresolved (no upcoming game matched): {unresolved}")

        # Show a preview.
        if pick_updates:
            print("\n--- Sample pick updates ---")
            for pick, team, opp, commence in pick_updates[:8]:
                print(f"  {pick.pick_id[:8]}  {pick.sport}  {pick.event!r:30s} -> {team} vs {opp}")
        if leg_updates:
            print("\n--- Sample leg updates ---")
            for pick, idx, team, opp in leg_updates[:8]:
                cur = pick.pick_detail["legs"][idx].get("event")
                print(f"  {pick.pick_id[:8]}#leg{idx}  {cur!r:30s} -> {team} vs {opp}")

        if dry_run:
            print("\n[dry-run] No changes written.")
            return 0

        if not skip_confirm:
            response = input("\nApply these updates? Type 'yes' to confirm: ").strip().lower()
            if response != "yes":
                print("Aborted.")
                return 1

        # Apply.
        for pick, team, opp, commence in pick_updates:
            pick.event = f"{team} vs {opp}"
            if pick.event_date is None:
                pick.event_date = commence

        for pick, idx, team, opp in leg_updates:
            legs = pick.pick_detail.get("legs", [])
            legs[idx]["event"] = f"{team} vs {opp}"
            pick.pick_detail = {**pick.pick_detail, "legs": legs}
            flag_modified(pick, "pick_detail")

        db.commit()
        print(f"\nUpdated {len(pick_updates)} picks and {len(leg_updates)} parlay legs.")
        return 0
    except Exception as e:
        db.rollback()
        print(f"\nFailed: {e}", file=sys.stderr)
        return 2
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing.")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation.")
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run, skip_confirm=args.yes))


if __name__ == "__main__":
    sys.exit(main())
