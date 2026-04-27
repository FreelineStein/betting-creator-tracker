"""
Wipe historical picks and orphaned sources before a cutoff date, then
recompute every affected creator's W/L record.

Defaults to "today's UTC midnight" (everything strictly before today goes).
Run against Railway:

    DATABASE_URL=postgres://... \
        ./venv/bin/python -m scripts.clear_old_picks

Use --dry-run first to see what would happen.
Use --before 2026-04-26T00:00:00+00:00 to override the cutoff.
Use --yes to skip the interactive confirmation (e.g. for CI / one-shot runs).
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python scripts/clear_old_picks.py` from the backend dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Creator, CreatorRecord, Pick, Source  # noqa: E402
from app.services.record_updater import recompute_record  # noqa: E402


def utc_today_midnight() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--before",
        type=str,
        default=None,
        help="ISO timestamp cutoff (default: today's UTC midnight). Picks with logged_at < this are deleted.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing.")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cutoff = (
        datetime.fromisoformat(args.before)
        if args.before
        else utc_today_midnight()
    )
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)

    db = SessionLocal()
    try:
        total_picks = db.query(Pick).count()
        total_sources = db.query(Source).count()
        total_creators = db.query(Creator).count()

        old_picks = db.query(Pick).filter(Pick.logged_at < cutoff)
        old_pick_count = old_picks.count()

        # Sources older than the cutoff that have NO surviving picks afterward.
        # We only delete a source if every pick attached to it is being deleted.
        candidate_sources = db.query(Source).filter(Source.scraped_at < cutoff).all()
        sources_to_delete = []
        for source in candidate_sources:
            surviving = (
                db.query(Pick)
                .filter(Pick.source_id == source.source_id, Pick.logged_at >= cutoff)
                .count()
            )
            if surviving == 0:
                sources_to_delete.append(source.source_id)

        # Creators whose records will need recomputing — anyone who owned a deleted pick.
        affected_creator_ids = {
            row[0]
            for row in db.query(Pick.creator_id).filter(Pick.logged_at < cutoff).distinct()
        }

        print("=== Plan ===")
        print(f"Cutoff (delete logged_at < this): {cutoff.isoformat()}")
        print(f"Current totals: {total_picks} picks · {total_sources} sources · {total_creators} creators")
        print(f"Picks to delete:               {old_pick_count}")
        print(f"Sources to delete (orphaned):  {len(sources_to_delete)}")
        print(f"Creator records to recompute:  {len(affected_creator_ids)}")

        if args.dry_run:
            print("\n[dry-run] No changes written.")
            return 0

        if not args.yes:
            response = input("\nProceed? Type 'yes' to confirm: ").strip().lower()
            if response != "yes":
                print("Aborted.")
                return 1

        # Order matters: picks first (children), then sources (parents).
        deleted_picks = old_picks.delete(synchronize_session=False)

        deleted_sources = 0
        if sources_to_delete:
            deleted_sources = (
                db.query(Source)
                .filter(Source.source_id.in_(sources_to_delete))
                .delete(synchronize_session=False)
            )

        # Reset records for creators whose pick history just changed (will rebuild
        # from whatever picks remain, including future ones).
        for creator_id in affected_creator_ids:
            recompute_record(creator_id, db)

        db.commit()

        remaining_picks = db.query(Pick).count()
        remaining_sources = db.query(Source).count()

        print("\n=== Done ===")
        print(f"Deleted picks:    {deleted_picks}")
        print(f"Deleted sources:  {deleted_sources}")
        print(f"Records recomputed for {len(affected_creator_ids)} creator(s)")
        print(f"Remaining: {remaining_picks} picks · {remaining_sources} sources")
        return 0
    except Exception as e:
        db.rollback()
        print(f"\nFailed: {e}", file=sys.stderr)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
