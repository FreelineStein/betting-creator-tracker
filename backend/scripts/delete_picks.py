"""
Delete picks by flexible filter, then recompute affected creator records.

Pick the bad picks via any combination of filters; everything is AND'd
together. Always run with --dry-run first to preview, then add --yes (or
just answer 'yes' to the prompt) to commit.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.delete_picks --team Lakers --dry-run

Filters:
  --id <uuid>             Exact pick_id (most precise; can repeat).
  --creator-id <uuid>     All picks for a specific creator_id.
  --creator-name <str>    All picks for a creator whose display_name matches (case-insensitive substring).
  --team <str>            Picks whose pick_detail.team contains the given string (case-insensitive).
  --event <str>           Picks whose `event` contains the given string (case-insensitive).
  --sport <str>           Sport abbreviation (e.g. NBA).
  --pick-type <str>       spread / moneyline / over_under / prop / parlay
  --status <str>          pending / won / lost / push / void
  --before <iso>          Only picks logged before this timestamp.
  --after  <iso>          Only picks logged after this timestamp.
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import or_  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Creator, Pick  # noqa: E402
from app.services.record_updater import recompute_record  # noqa: E402


def parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--id", action="append", default=[], help="Pick UUID. Repeat to delete several specific picks.")
    parser.add_argument("--creator-id", default=None)
    parser.add_argument("--creator-name", default=None)
    parser.add_argument("--team", default=None)
    parser.add_argument("--event", default=None)
    parser.add_argument("--sport", default=None)
    parser.add_argument("--pick-type", default=None)
    parser.add_argument("--status", default=None)
    parser.add_argument("--before", type=parse_iso, default=None)
    parser.add_argument("--after", type=parse_iso, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args()


def matches_team(pick: Pick, needle: str) -> bool:
    """Case-insensitive containment on pick_detail.team (or any leg.detail.team for parlays)."""
    target = needle.lower()
    detail = pick.pick_detail or {}
    direct = (detail.get("team") or "").lower()
    if target in direct:
        return True
    for leg in detail.get("legs") or []:
        leg_detail = leg.get("detail") or {}
        if target in (leg_detail.get("team") or "").lower():
            return True
    return False


def filter_picks(args: argparse.Namespace, picks: Iterable[Pick]) -> list[Pick]:
    needle_event = args.event.lower() if args.event else None
    needle_team = args.team if args.team else None
    out = []
    for p in picks:
        if needle_event and needle_event not in (p.event or "").lower():
            continue
        if needle_team and not matches_team(p, needle_team):
            continue
        out.append(p)
    return out


def main() -> int:
    args = parse_args()
    has_filter = any([
        args.id, args.creator_id, args.creator_name, args.team, args.event,
        args.sport, args.pick_type, args.status, args.before, args.after,
    ])
    if not has_filter:
        print("Refusing to run without any filter — that would delete every pick.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        query = db.query(Pick)

        if args.id:
            query = query.filter(Pick.pick_id.in_(args.id))
        if args.creator_id:
            query = query.filter(Pick.creator_id == args.creator_id)
        if args.creator_name:
            matches = (
                db.query(Creator.creator_id)
                .filter(Creator.display_name.ilike(f"%{args.creator_name}%"))
                .all()
            )
            ids = [m[0] for m in matches]
            if not ids:
                print(f"No creators match name like {args.creator_name!r}.")
                return 0
            query = query.filter(Pick.creator_id.in_(ids))
        if args.sport:
            query = query.filter(Pick.sport == args.sport.upper())
        if args.pick_type:
            query = query.filter(Pick.pick_type == args.pick_type)
        if args.status:
            query = query.filter(Pick.status == args.status)
        if args.before:
            query = query.filter(Pick.logged_at < args.before)
        if args.after:
            query = query.filter(Pick.logged_at > args.after)

        # Substring filters (event/team) are applied in Python because pick_detail
        # lives in JSON and Postgres JSON containment varies between dialects.
        candidates = filter_picks(args, query.all())

        if not candidates:
            print("No picks match those filters.")
            return 0

        print(f"=== Plan ({len(candidates)} pick(s) to delete) ===")
        for p in candidates:
            team = (p.pick_detail or {}).get("team")
            print(
                f"  {p.pick_id[:8]}  {p.sport or '—':5s}  {p.pick_type:9s}  "
                f"{(p.event or team or '?')!r:40s}  status={p.status.value if hasattr(p.status,'value') else p.status}  "
                f"logged={p.logged_at.isoformat() if p.logged_at else '?'}"
            )

        affected_creators = {p.creator_id for p in candidates}
        print(f"\nCreator records to recompute: {len(affected_creators)}")

        if args.dry_run:
            print("\n[dry-run] No changes written.")
            return 0

        if not args.yes:
            response = input("\nDelete these picks? Type 'yes' to confirm: ").strip().lower()
            if response != "yes":
                print("Aborted.")
                return 1

        deleted = 0
        for p in candidates:
            db.delete(p)
            deleted += 1
        db.flush()

        for cid in affected_creators:
            recompute_record(cid, db)

        db.commit()
        print(f"\nDeleted {deleted} pick(s). Recomputed {len(affected_creators)} record(s).")
        return 0
    except Exception as e:
        db.rollback()
        print(f"\nFailed: {e}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
