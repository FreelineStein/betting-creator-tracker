"""
Backfill pick.odds for settled picks via The Odds API historical endpoint.

Unblocked 2026-05-10 when the Odds API plan moved to 20K credits/month —
historical odds are now in-tier. One-time backfill for picks the live path
never priced (parsed before the live-fetch existed, or the creator didn't
write a price in the post and the closing-odds cron missed the window).

Targets:
    pick.odds IS NULL
    AND status IN (won, lost, push)
    AND pick_type IN (moneyline, spread, over_under)
    AND event_date IS NOT NULL
    AND sport IS IN SPORT_KEY_MAP

Groups by (sport_key, snapshot_iso) — snapshot = (event_date - 10min)
floored to the nearest 30 min. One historical fetch serves every pick in
that bucket. Each historical call costs ~30 credits (3 markets × us
region × 10x historical multiplier per The Odds API pricing), so a
backfill of a few dozen picks is well within the monthly cap.

Always run --dry-run first. Reuses the live find_odds_for_pick matcher
so the wire format and team-name logic stay in lockstep with submission.

    DATABASE_URL='<railway public postgres url>' \
    THE_ODDS_API_KEY='<key>' \
        ./venv/bin/python -m scripts.backfill_historical_odds --dry-run

    DATABASE_URL='...' THE_ODDS_API_KEY='...' \
        ./venv/bin/python -m scripts.backfill_historical_odds --yes
"""
import argparse
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Pick, PickStatus  # noqa: E402
from app.services.odds_api import SPORT_KEY_MAP, find_odds_for_pick  # noqa: E402

HISTORICAL_BASE = "https://api.the-odds-api.com/v4/historical/sports"
ESTIMATED_CREDITS_PER_CALL = 30  # 3 markets × 1 region × 10x historical


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--limit", type=int, default=None, help="Cap candidate-pick count.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--sleep", type=float, default=0.5, help="Seconds between API calls.")
    return p.parse_args()


def _floor_30min(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 30) * 30, second=0, microsecond=0)


def _pick_type_str(pick: Pick) -> str:
    pt = pick.pick_type
    return pt.value if hasattr(pt, "value") else str(pt)


def collect_candidates(db, limit):
    q = (
        db.query(Pick)
        .filter(
            Pick.odds.is_(None),
            Pick.status.in_([PickStatus.won, PickStatus.lost, PickStatus.push]),
            Pick.pick_type.in_(["moneyline", "spread", "over_under"]),
            Pick.event_date.isnot(None),
        )
        .order_by(Pick.event_date.asc())
    )
    if limit is not None:
        q = q.limit(limit)
    return q.all()


def group_by_snapshot(picks):
    groups: dict[tuple[str, str], list[Pick]] = defaultdict(list)
    for pick in picks:
        sport_key = SPORT_KEY_MAP.get(pick.sport.upper())
        if not sport_key:
            continue
        event_dt = pick.event_date
        if event_dt.tzinfo is None:
            event_dt = event_dt.replace(tzinfo=timezone.utc)
        # Snap to the nearest 30-min boundary just before kickoff. The Odds
        # API returns whichever snapshot is closest to the requested ts.
        snapshot = _floor_30min(event_dt - timedelta(minutes=10))
        iso = snapshot.strftime("%Y-%m-%dT%H:%M:%SZ")
        groups[(sport_key, iso)].append(pick)
    return groups


def fetch_historical(client, api_key, sport_key, snapshot_iso):
    resp = client.get(
        f"{HISTORICAL_BASE}/{sport_key}/odds",
        params={
            "apiKey": api_key,
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "date": snapshot_iso,
        },
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    args = parse_args()

    api_key = os.environ.get("THE_ODDS_API_KEY", "")
    if not args.dry_run and not api_key:
        print("THE_ODDS_API_KEY env var required (unless --dry-run).", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        candidates = collect_candidates(db, args.limit)
        candidates = [p for p in candidates if p.sport and p.sport.upper() in SPORT_KEY_MAP]
        if not candidates:
            print("No candidate picks. Nothing to do.")
            return 0

        groups = group_by_snapshot(candidates)
        print(
            f"Matched {len(candidates)} picks across {len(groups)} (sport, snapshot) "
            f"groups (~{len(groups) * ESTIMATED_CREDITS_PER_CALL} credits)."
        )
        preview = list(groups.items())[:8]
        for (sport_key, iso), picks in preview:
            print(f"  {sport_key} @ {iso} — {len(picks)} pick(s)")
        if len(groups) > 8:
            print(f"  ...and {len(groups) - 8} more groups")

        if args.dry_run:
            print("\nDry-run; no API calls or DB writes.")
            return 0

        if not args.yes:
            confirm = input(
                f"Run {len(groups)} historical fetches? [yes/N]: "
            ).strip().lower()
            if confirm not in ("y", "yes"):
                print("aborted.")
                return 1

        filled = 0
        empty_groups = 0
        failed_groups = 0

        with httpx.Client(timeout=30.0) as client:
            for i, ((sport_key, iso), picks) in enumerate(groups.items(), start=1):
                try:
                    payload = fetch_historical(client, api_key, sport_key, iso)
                except httpx.HTTPError as e:
                    failed_groups += 1
                    print(f"[{i}/{len(groups)}] HTTP fail {sport_key} @ {iso}: {e}")
                    time.sleep(args.sleep)
                    continue

                games = payload.get("data") or []
                if not games:
                    empty_groups += 1
                    print(f"[{i}/{len(groups)}] no snapshot data {sport_key} @ {iso}")
                    time.sleep(args.sleep)
                    continue

                group_filled = 0
                for pick in picks:
                    team = None
                    if isinstance(pick.pick_detail, dict):
                        team = pick.pick_detail.get("team")
                    odds = find_odds_for_pick(
                        team=team,
                        pick_type=_pick_type_str(pick),
                        pick_detail=pick.pick_detail or {},
                        games=games,
                    )
                    if odds:
                        pick.odds = odds
                        group_filled += 1
                        filled += 1
                print(
                    f"[{i}/{len(groups)}] {sport_key} @ {iso} — "
                    f"filled {group_filled}/{len(picks)}"
                )

                time.sleep(args.sleep)

            db.commit()

        print(
            f"\nSUMMARY: filled={filled}/{len(candidates)} "
            f"empty_groups={empty_groups} failed_groups={failed_groups}"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
