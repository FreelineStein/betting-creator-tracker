"""
Background jobs — runs on a schedule to scrape creators and process picks.
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
    scrape_hours = getattr(settings, "scrape_interval_hours", 4)
    # Outcome resolution doesn't need to be near-real-time — every 2h keeps
    # us well inside the 450/month Odds API free tier and leaves headroom for
    # the new submit-time odds enrichment.
    resolve_hours = getattr(settings, "resolve_interval_hours", 2)

    # Scrape tracked creators
    scheduler.add_job(
        scrape_all_creators,
        trigger=IntervalTrigger(hours=scrape_hours),
        id="scrape_creators",
        replace_existing=True,
    )

    # Resolve pending pick outcomes
    scheduler.add_job(
        resolve_pending_outcomes,
        trigger=IntervalTrigger(hours=resolve_hours),
        id="resolve_outcomes",
        replace_existing=True,
    )

    scheduler.start()
    log.info(
        "Scheduler started",
        scrape_interval_hours=scrape_hours,
        resolve_interval_hours=resolve_hours,
    )


def _get_extraction_method(attempts: list[dict]):
    """Determine which extractor actually succeeded from the attempts log."""
    from app.models import ExtractionMethod
    for attempt in attempts:
        if attempt.get("success") and attempt.get("confidence", 0) >= 0.6:
            method_name = attempt.get("method", "caption")
            if method_name in ExtractionMethod.__members__:
                return ExtractionMethod(method_name)
    return ExtractionMethod.caption


async def scrape_all_creators():
    """Fetch recent posts for all active tracked creators and run extraction pipeline."""
    from app.database import SessionLocal
    from app.models import Creator, CreatorTier

    log.info("Starting creator scrape job")
    db = SessionLocal()
    try:
        creators = db.query(Creator).filter(
            Creator.tracking_active == True,
            Creator.tier == CreatorTier.tracked,
        ).all()

        for creator in creators:
            for platform_config in (creator.platforms or []):
                await _scrape_creator_platform(creator, platform_config, db)

    finally:
        db.close()


async def _scrape_creator_platform(creator, platform_config: dict, db):
    from app.scrapers import SCRAPER_MAP
    from app.pipeline import run_extraction_pipeline
    from app.models import Source, ExtractionStatus

    platform = platform_config.get("platform")
    handle = platform_config.get("handle")
    if not platform or not handle:
        return

    # Skip platforms without automated scraping (e.g., Twitter uses oEmbed via manual URL submission)
    if platform == "twitter":
        log.info("Skipping Twitter — uses manual URL submission via /scrape/tweets", creator=creator.display_name)
        return

    if platform == "instagram":
        log.warning("Instagram scraping not available — skipping", creator=creator.display_name)
        return

    scraper_cls = SCRAPER_MAP.get(platform)
    if not scraper_cls:
        log.warning("No scraper for platform", platform=platform)
        return

    try:
        scraper = scraper_cls()
        posts = await scraper.fetch_recent_posts(handle)

        posts_found = len(posts)
        picks_extracted = 0

        for post in posts:
            # Skip if already scraped
            existing = db.query(Source).filter(Source.post_url == post.post_url).first()
            if existing:
                continue

            source = Source(
                creator_id=creator.creator_id,
                platform=platform,
                post_type=post.post_type,
                post_url=post.post_url,
                posted_at=post.posted_at,
            )
            db.add(source)
            db.flush()

            # Run extraction pipeline
            raw_metadata = {
                "caption": post.caption,
                "description": post.description,
                "subtitles": post.subtitles,
                "video_url": post.video_url,
                **(post.raw or {}),
            }
            extracted_text, attempts = await run_extraction_pipeline(post.post_url, raw_metadata)

            source.raw_content = extracted_text
            source.extraction_attempts = attempts
            source.extraction_status = (
                ExtractionStatus.success if extracted_text else ExtractionStatus.needs_review
            )

            # Parse extracted text into structured Pick objects
            if extracted_text:
                from app.pipeline.parser import parse_picks
                from app.models import Pick, PickStatus

                parsed_picks = await parse_picks(extracted_text, source_url=post.post_url)
                for parsed in parsed_picks:
                    pick = Pick(
                        source_id=source.source_id,
                        creator_id=creator.creator_id,
                        sport=parsed.sport,
                        event=parsed.event,
                        event_date=parsed.event_date,
                        pick_type=parsed.pick_type,
                        pick_detail=parsed.pick_detail,
                        odds=parsed.odds,
                        units=parsed.units,
                        status=PickStatus.pending,
                        extraction_method=_get_extraction_method(attempts),
                        extraction_confidence=parsed.confidence,
                        raw_text=parsed.raw_text,
                    )
                    db.add(pick)
                    picks_extracted += 1

        db.commit()
        log.info(
            "SCRAPE_COMPLETE",
            creator=creator.display_name,
            platform=platform,
            posts_found=posts_found,
            picks_extracted=picks_extracted,
        )

    except Exception as e:
        log.error(
            "SCRAPER_FAILURE",
            creator=creator.display_name,
            platform=platform,
            error=str(e),
        )
        db.rollback()


async def resolve_pending_outcomes():
    """Check game results and update Pick statuses."""
    from datetime import datetime, timezone
    from app.database import SessionLocal
    from app.models import Pick, PickStatus
    from app.services.odds_api import get_completed_games, find_matching_game, SPORT_KEY_MAP
    from app.services.outcome_resolver import resolve_pick, resolve_prop, resolve_parlay_legs
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

        # Group by sport to minimize API calls
        # For picks with no sport, try searching across all sports
        picks_by_sport: dict[str, list] = {}
        unknown_sport_picks: list = []
        for pick in pending:
            if pick.sport and pick.sport in SPORT_KEY_MAP:
                picks_by_sport.setdefault(pick.sport, []).append(pick)
            else:
                unknown_sport_picks.append(pick)

        wins = losses = pushes = 0

        # Resolve picks with known sports
        for sport, sport_picks in picks_by_sport.items():
            games = await get_completed_games(sport, days_back=3)
            if not games:
                continue

            for pick in sport_picks:
                game = find_matching_game(
                    event=pick.event,
                    pick_detail=pick.pick_detail or {},
                    event_date=pick.event_date,
                    games=games,
                )

                if not game:
                    continue

                new_status = resolve_pick(pick.pick_type, pick.pick_detail or {}, game)

                if new_status != PickStatus.pending:
                    pick.status = new_status
                    pick.outcome_resolved_at = now
                    updated_creators.add(pick.creator_id)
                    resolved_count += 1

                    if new_status == PickStatus.won:
                        wins += 1
                    elif new_status == PickStatus.lost:
                        losses += 1
                    elif new_status == PickStatus.push:
                        pushes += 1

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

    except Exception as e:
        log.error("Outcome resolution failed", error=str(e))
        db.rollback()
    finally:
        db.close()
