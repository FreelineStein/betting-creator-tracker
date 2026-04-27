"""
Background jobs — runs on a schedule to resolve outcomes and capture closing odds.
Submission ingestion is user-driven via /api/v1/submissions; there is no scrape job.
APScheduler keeps it simple for now. Migrate to Celery when needed.
"""
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings

log = structlog.get_logger()

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Register all background jobs."""
    # Outcome resolution doesn't need to be near-real-time — every 2h keeps
    # us well inside the 450/month Odds API free tier and leaves headroom for
    # the closing-odds capture job below.
    resolve_hours = getattr(settings, "resolve_interval_hours", 2)
    closing_odds_minutes = getattr(settings, "closing_odds_interval_minutes", 30)

    scheduler.add_job(
        resolve_pending_outcomes,
        trigger=IntervalTrigger(hours=resolve_hours),
        id="resolve_outcomes",
        replace_existing=True,
    )
    scheduler.add_job(
        capture_closing_odds,
        trigger=IntervalTrigger(minutes=closing_odds_minutes),
        id="closing_odds",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "Scheduler started",
        resolve_interval_hours=resolve_hours,
        closing_odds_interval_minutes=closing_odds_minutes,
    )


async def capture_closing_odds():
    """
    Fill in `pick.odds` for picks whose game starts in the next ~90 minutes.

    Runs every 30 min by default. The window is wide enough that a single
    miss (job runs late, network blip, etc.) gets a second chance on the
    next tick. Once a pick is filled, it's never re-fetched.

    Only `pick.odds` is mutated — every other field on the Pick row is
    preserved. Self-throttles via odds_api.check_budget(); when the budget
    is near zero the lookup quietly returns nothing and the picks stay
    null until next month.
    """
    from datetime import datetime, timedelta, timezone

    from app.database import SessionLocal
    from app.models import Pick, PickStatus
    from app.services.odds_api import (
        SPORT_KEY_MAP,
        find_odds_for_pick,
        get_odds_for_sport,
    )

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=90)

    db = SessionLocal()
    try:
        candidates = (
            db.query(Pick)
            .filter(
                Pick.status == PickStatus.pending,
                Pick.odds.is_(None),
                Pick.event_date.isnot(None),
                Pick.event_date >= now,
                Pick.event_date <= window_end,
                Pick.pick_type.in_(["moneyline", "spread", "over_under"]),
            )
            .all()
        )
        # Drop picks for sports we can't look up (e.g., parlay legs already
        # roll up into the parent type, props go through ESPN, tennis isn't
        # in SPORT_KEY_MAP yet).
        candidates = [
            p for p in candidates
            if p.sport and p.sport.upper() in SPORT_KEY_MAP
        ]

        if not candidates:
            return

        log.info("closing_odds_candidates", count=len(candidates))

        sports = {p.sport for p in candidates}
        odds_by_sport: dict[str, list] = {}
        for sport in sports:
            odds_by_sport[sport] = await get_odds_for_sport(sport)

        filled = 0
        for pick in candidates:
            games = odds_by_sport.get(pick.sport) or []
            if not games:
                continue
            team = (pick.pick_detail or {}).get("team") if isinstance(pick.pick_detail, dict) else None
            odds = find_odds_for_pick(
                team=team,
                pick_type=pick.pick_type,
                pick_detail=pick.pick_detail or {},
                games=games,
            )
            if odds:
                pick.odds = odds
                filled += 1
                log.info(
                    "closing_odds_captured",
                    pick_id=pick.pick_id,
                    sport=pick.sport,
                    team=team,
                    pick_type=pick.pick_type,
                    odds=odds,
                )

        if filled:
            db.commit()
        log.info("CLOSING_ODDS_DONE", candidates=len(candidates), filled=filled)
        if filled:
            from app.posthog_client import posthog_client
            if posthog_client:
                posthog_client.capture(
                    distinct_id="scheduler",
                    event="closing odds captured",
                    properties={
                        "candidates": len(candidates),
                        "filled": filled,
                        "$process_person_profile": False,
                    },
                )
    except Exception as e:
        db.rollback()
        log.error("closing_odds_failed", error=str(e))
    finally:
        db.close()


async def resolve_pending_outcomes():
    """Check game results and update Pick statuses."""
    from datetime import datetime, timezone
    from app.database import SessionLocal
    from app.models import Pick, PickStatus
    from app.services.odds_api import get_completed_games, find_matching_game, SPORT_KEY_MAP
    from app.services.espn_stats import get_completed_games_espn
    from app.services.outcome_resolver import (
        resolve_pick, resolve_prop, resolve_parlay_legs, scheduled_to_game_result,
    )
    from app.services.record_updater import recompute_record

    log.info("Checking pending pick outcomes")
    db = SessionLocal()
    updated_creators = set()
    resolved_count = 0

    try:
        now = datetime.now(timezone.utc)

        # Get ALL pending picks — we'll handle missing sport/date gracefully
        pending = db.query(Pick).filter(
            Pick.status == PickStatus.pending,
        ).all()

        if not pending:
            log.info("No pending picks to resolve")
            return

        # For picks without event_date, use logged_at as a proxy
        # (the pick was likely for a game around the time it was posted)
        for pick in pending:
            if pick.event_date is None and pick.logged_at:
                pick.event_date = pick.logged_at
                log.info("Using logged_at as event_date fallback", pick_id=pick.pick_id)

        # Filter to picks with past event dates
        pending = [p for p in pending if p.event_date and p.event_date < now]

        if not pending:
            log.info("No pending picks with past dates to resolve")
            return

        log.info("Found pending picks to resolve", count=len(pending))

        # Group by sport to minimize API calls. Tennis has no Odds API coverage in
        # SPORT_KEY_MAP; route it through ESPN exclusively. Picks with no sport
        # fall through to the legacy cross-sport search at the bottom.
        picks_by_sport: dict[str, list] = {}
        tennis_picks: list = []
        unknown_sport_picks: list = []
        for pick in pending:
            if pick.sport and pick.sport in SPORT_KEY_MAP:
                picks_by_sport.setdefault(pick.sport, []).append(pick)
            elif pick.sport and pick.sport.upper() == "TENNIS":
                tennis_picks.append(pick)
            else:
                unknown_sport_picks.append(pick)

        wins = losses = pushes = 0

        def _try_match_and_resolve(pick, games: list) -> bool:
            """
            Match `pick` against `games` and apply the outcome if found.
            Returns True if the pick was matched (regardless of resolution),
            so the caller knows not to retry it against the fallback source.
            """
            nonlocal wins, losses, pushes, resolved_count
            game = find_matching_game(
                event=pick.event,
                pick_detail=pick.pick_detail or {},
                event_date=pick.event_date,
                games=games,
            )
            if not game:
                return False
            new_status = resolve_pick(pick.pick_type, pick.pick_detail or {}, game)
            if new_status != PickStatus.pending:
                pick.status = new_status
                pick.outcome_resolved_at = now
                # Snap event_date to the actual game start. This corrects picks
                # whose event_date came from the logged_at fallback (parser missed
                # it) and ensures pick history groups them under the right day.
                pick.event_date = game.commence_time
                updated_creators.add(pick.creator_id)
                resolved_count += 1
                if new_status == PickStatus.won:
                    wins += 1
                elif new_status == PickStatus.lost:
                    losses += 1
                elif new_status == PickStatus.push:
                    pushes += 1
            return True

        # Resolve picks with known sports — try ESPN's free scoreboard first,
        # only fall back to The Odds API for picks ESPN couldn't match.
        for sport, sport_picks in picks_by_sport.items():
            espn_raw = await get_completed_games_espn(sport, days_back=3)
            espn_games = [scheduled_to_game_result(g) for g in espn_raw]

            unmatched = []
            for pick in sport_picks:
                if not (espn_games and _try_match_and_resolve(pick, espn_games)):
                    unmatched.append(pick)

            if not unmatched:
                continue

            odds_games = await get_completed_games(sport, days_back=3)
            if not odds_games:
                continue
            for pick in unmatched:
                _try_match_and_resolve(pick, odds_games)

        # Resolve tennis picks via ESPN only — there is no Odds API fallback.
        if tennis_picks:
            tennis_raw = await get_completed_games_espn("TENNIS", days_back=5)
            tennis_games = [scheduled_to_game_result(g) for g in tennis_raw]
            log.info("Resolving tennis picks via ESPN", count=len(tennis_picks), games=len(tennis_games))
            for pick in tennis_picks:
                if tennis_games:
                    _try_match_and_resolve(pick, tennis_games)

        # Resolve picks with unknown sport — search across all sports
        if unknown_sport_picks:
            log.info("Attempting cross-sport search for picks with unknown sport", count=len(unknown_sport_picks))
            for pick in unknown_sport_picks:
                for sport in SPORT_KEY_MAP:
                    games = await get_completed_games(sport, days_back=3)
                    if not games:
                        continue

                    game = find_matching_game(
                        event=pick.event,
                        pick_detail=pick.pick_detail or {},
                        event_date=pick.event_date,
                        games=games,
                    )

                    if game:
                        # Found it — update the sport on the pick too
                        pick.sport = sport
                        new_status = resolve_pick(pick.pick_type, pick.pick_detail or {}, game)

                        if new_status != PickStatus.pending:
                            pick.status = new_status
                            pick.outcome_resolved_at = now
                            pick.event_date = game.commence_time
                            updated_creators.add(pick.creator_id)
                            resolved_count += 1
                            log.info("Resolved unknown-sport pick", pick_id=pick.pick_id, inferred_sport=sport)

                            if new_status == PickStatus.won:
                                wins += 1
                            elif new_status == PickStatus.lost:
                                losses += 1
                            elif new_status == PickStatus.push:
                                pushes += 1
                        break  # Found the sport, stop searching

        # Resolve prop picks via ESPN box scores
        prop_picks = [p for p in pending if p.pick_type == "prop" and p.status == PickStatus.pending]
        if prop_picks:
            log.info("Resolving prop picks via ESPN", count=len(prop_picks))
            for pick in prop_picks:
                sport = pick.sport
                if not sport:
                    continue
                new_status = await resolve_prop(
                    pick.pick_detail or {},
                    sport,
                    pick.event_date,
                )
                if new_status != PickStatus.pending:
                    pick.status = new_status
                    pick.outcome_resolved_at = now
                    updated_creators.add(pick.creator_id)
                    resolved_count += 1
                    log.info("Resolved prop pick", pick_id=pick.pick_id, status=new_status.value)

                    if new_status == PickStatus.won:
                        wins += 1
                    elif new_status == PickStatus.lost:
                        losses += 1
                    elif new_status == PickStatus.push:
                        pushes += 1

        # Resolve parlay picks per-leg
        parlay_picks = [p for p in pending if p.pick_type == "parlay" and p.status == PickStatus.pending]
        if parlay_picks:
            log.info("Resolving parlay picks per-leg", count=len(parlay_picks))
            for pick in parlay_picks:
                updated_detail, new_status = await resolve_parlay_legs(
                    pick.pick_detail or {},
                    pick.event_date,
                )
                # Always update pick_detail to persist per-leg results
                from sqlalchemy.orm.attributes import flag_modified
                pick.pick_detail = updated_detail
                flag_modified(pick, "pick_detail")

                if new_status != PickStatus.pending:
                    pick.status = new_status
                    pick.outcome_resolved_at = now
                    updated_creators.add(pick.creator_id)
                    resolved_count += 1
                    log.info("Parlay resolved", pick_id=pick.pick_id, status=new_status.value)

                    if new_status == PickStatus.won:
                        wins += 1
                    elif new_status == PickStatus.lost:
                        losses += 1
                    elif new_status == PickStatus.push:
                        pushes += 1

        db.flush()

        for creator_id in updated_creators:
            recompute_record(creator_id, db)

        db.commit()
        log.info(
            "RESOLUTION_COMPLETE",
            picks_resolved=resolved_count,
            wins=wins,
            losses=losses,
            pushes=pushes,
        )

        if resolved_count > 0:
            from app.posthog_client import posthog_client
            if posthog_client:
                posthog_client.capture(
                    distinct_id="scheduler",
                    event="pick outcome resolved",
                    properties={
                        "picks_resolved": resolved_count,
                        "wins": wins,
                        "losses": losses,
                        "pushes": pushes,
                        "$process_person_profile": False,
                    },
                )

    except Exception as e:
        log.error("Outcome resolution failed", error=str(e))
        db.rollback()
    finally:
        db.close()
