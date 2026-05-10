"""
Read-only diagnostic — list settled picks where pick.odds is still NULL.

Run after `backfill_historical_odds.py` to inspect the picks the matcher
couldn't price. Surfaces sport, team, line/total, event_date, and event
so you can eyeball whether the miss is an alias gap, a line mismatch,
or a game outside the Odds API archive window.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.audit_null_odds
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Pick, PickStatus  # noqa: E402


def main() -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(Pick)
            .filter(
                Pick.odds.is_(None),
                Pick.status.in_([PickStatus.won, PickStatus.lost, PickStatus.push]),
                Pick.pick_type.in_(["moneyline", "spread", "over_under"]),
                Pick.event_date.isnot(None),
            )
            .order_by(Pick.event_date.asc())
            .all()
        )
        if not rows:
            print("No settled picks with NULL odds. Backfill caught everything.")
            return 0

        print(f"{len(rows)} settled pick(s) still missing odds:\n")
        for p in rows:
            pt = p.pick_type.value if hasattr(p.pick_type, "value") else p.pick_type
            detail = p.pick_detail or {}
            team = detail.get("team")
            line = detail.get("line")
            total = detail.get("total")
            direction = detail.get("direction")
            line_str = f"line={line}" if line is not None else ""
            total_str = f"total={total}" if total is not None else ""
            dir_str = f"dir={direction}" if direction else ""
            extras = " ".join(s for s in (line_str, total_str, dir_str) if s)
            print(
                f"  [{p.pick_id[:8]}] {p.sport} {pt:11s} team={team!r:30s} "
                f"{extras:20s} event={p.event!r} @ {p.event_date.isoformat()} "
                f"status={p.status.value}"
            )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
