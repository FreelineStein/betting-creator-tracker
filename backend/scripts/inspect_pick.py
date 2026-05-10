"""
Read-only — print a Pick row in full so we can see pick_detail (incl.
parlay leg results) without dropping into psql.

    DATABASE_URL='<railway public postgres url>' \
        ./venv/bin/python -m scripts.inspect_pick <pick_id_prefix>

Pass any prefix of the pick_id (the first 8 chars from audit output
work fine).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Pick  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: scripts/inspect_pick.py <pick_id_prefix>", file=sys.stderr)
        return 2
    prefix = sys.argv[1]

    db = SessionLocal()
    try:
        rows = db.query(Pick).filter(Pick.pick_id.like(f"{prefix}%")).all()
        if not rows:
            print(f"No pick matches prefix {prefix!r}.")
            return 1
        if len(rows) > 1:
            print(f"{len(rows)} picks match prefix {prefix!r}. Showing all.\n")

        for p in rows:
            pt = p.pick_type.value if hasattr(p.pick_type, "value") else p.pick_type
            print(f"pick_id      : {p.pick_id}")
            print(f"creator_id   : {p.creator_id}")
            print(f"source_id    : {p.source_id}")
            print(f"sport        : {p.sport}    league: {p.league}")
            print(f"event        : {p.event}")
            print(f"event_date   : {p.event_date}")
            print(f"event_id     : {p.event_id}    provider: {p.event_provider}")
            print(f"pick_type    : {pt}")
            print(f"status       : {p.status.value}")
            print(f"odds         : {p.odds}    units: {p.units}")
            print(f"pick_detail  :")
            print(json.dumps(p.pick_detail, indent=2, default=str))
            if pt == "parlay":
                legs = (p.pick_detail or {}).get("legs", [])
                print(f"\nleg summary ({len(legs)} legs):")
                for i, leg in enumerate(legs, 1):
                    if not isinstance(leg, dict):
                        continue
                    print(
                        f"  [{i}] sport={leg.get('sport')} type={leg.get('type')} "
                        f"event_id={leg.get('event_id')} provider={leg.get('event_provider')} "
                        f"result={leg.get('result') or 'pending'}"
                    )
                    print(f"      text: {leg.get('text')}")
                    print(f"      detail: {leg.get('detail')}")
            print()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
