"""
Read-only diagnostic — list pending picks past their event_date.

Splits by pinned (event_id set) vs legacy (event_id null) so we can see
whether stuck picks are falling out of the legacy resolver's 3-day
lookback window or whether the pinned path itself is failing.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.audit_pending
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Pick, PickStatus  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        rows = (
            db.query(Pick)
            .filter(Pick.status == PickStatus.pending)
            .filter(Pick.event_date.isnot(None))
            .filter(Pick.event_date < now)
            .order_by(Pick.event_date.asc())
            .all()
        )
        if not rows:
            print("No past-dated pending picks.")
            return 0

        # The resolver's pinned pass requires BOTH event_id and
        # event_provider=="espn". Anything else falls through to the
        # legacy path, where days_back=3 kills 10-day-old picks.
        routed_pinned = [p for p in rows if p.event_id and p.event_provider == "espn"]
        half_pinned = [p for p in rows if p.event_id and p.event_provider != "espn"]
        legacy = [p for p in rows if not p.event_id]

        print(
            f"{len(rows)} past-dated pending picks total — "
            f"routed_pinned={len(routed_pinned)} "
            f"half_pinned (event_id but no espn provider)={len(half_pinned)} "
            f"legacy (no event_id)={len(legacy)}\n"
        )

        def _line(p):
            pt = p.pick_type.value if hasattr(p.pick_type, "value") else p.pick_type
            age_days = (now - p.event_date).days
            return (
                f"  [{p.pick_id[:8]}] {p.sport} {pt:8s} "
                f"event={p.event!r:40s} @ {p.event_date.isoformat()} "
                f"({age_days}d old) event_id={p.event_id} provider={p.event_provider}"
            )

        if half_pinned:
            print("HALF_PINNED (event_id set but provider != 'espn' — falls to legacy path):")
            for p in half_pinned:
                print(_line(p))
            print()

        if legacy:
            print("LEGACY (event_id NULL — needs days_back widened or event_id backfill):")
            for p in legacy:
                print(_line(p))
            print()

        if routed_pinned:
            print("ROUTED PINNED (event_id + provider=espn — pinned-path lookup should find these):")
            for p in routed_pinned:
                print(_line(p))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
