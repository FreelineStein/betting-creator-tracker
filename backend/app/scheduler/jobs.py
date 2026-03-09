"""
Background jobs — runs on a schedule to scrape creators and process picks.
APScheduler keeps it simple for now. Migrate to Celery when needed.
"""
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = structlog.get_logger()

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """Register all background jobs."""

    # Scrape tracked creators every 2 hours
    scheduler.add_job(
        scrape_all_creators,
        trigger=IntervalTrigger(hours=2),
        id="scrape_creators",
        replace_existing=True,
    )

    # Resolve pending pick outcomes every 30 minutes
    scheduler.add_job(
        resolve_pending_outcomes,
        trigger=IntervalTrigger(minutes=30),
        id="resolve_outcomes",
        replace_existing=True,
    )

    scheduler.start()
    log.info("Scheduler started")


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

    scraper_cls = SCRAPER_MAP.get(platform)
    if not scraper_cls:
        log.warning("No scraper for platform", platform=platform)
        return

    try:
        scraper = scraper_cls()
        posts = await scraper.fetch_recent_posts(handle)

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
                from app.models import Pick, PickStatus, ExtractionMethod

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
                        extraction_method=ExtractionMethod.caption,  # Will use actual method once pipeline tracks it
                        extraction_confidence=parsed.confidence,
                        raw_text=parsed.raw_text,
                    )
                    db.add(pick)
                    log.info(
                        "Pick logged",
                        creator=creator.display_name,
                        sport=parsed.sport,
                        pick_type=parsed.pick_type,
                        event=parsed.event,
                    )

        db.commit()

    except Exception as e:
        log.error("Scrape failed", creator=creator.display_name, platform=platform, error=str(e))
        db.rollback()


async def resolve_pending_outcomes():
    """Check game results and update Pick statuses."""
    from datetime import datetime, timezone, timedelta
    from app.database import SessionLocal
    from app.models import Pick, PickStatus
    from app.services.odds_api import get_completed_games, find_matching_game, SPORT_KEY_MAP
    from app.services.outcome_resolver import resolve_pick
    from app.services.record_updater import recompute_record

    log.info("Checking pending pick outcomes")
    db = SessionLocal()
    updated_creators = set()

    try:
        # Get all pending picks with a known event date in the past
        now = datetime.now(timezone.utc)
        pending = db.query(Pick).filter(
            Pick.status == PickStatus.pending,
            Pick.event_date.isnot(None),
            Pick.event_date < now,
            Pick.sport.isnot(None),
        ).all()

        if not pending:
            log.info("No pending picks to resolve")
            return

        log.info("Found pending picks to resolve", count=len(pending))

        # Group by sport to minimize API calls
        picks_by_sport: dict[str, list] = {}
        for pick in pending:
            picks_by_sport.setdefault(pick.sport, []).append(pick)

        for sport, sport_picks in picks_by_sport.items():
            if sport not in SPORT_KEY_MAP:
                continue

            # Fetch completed games for this sport (last 3 days)
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
                    log.info("No matching game found for pick", pick_id=pick.pick_id, event=pick.event)
                    continue

                new_status = resolve_pick(pick.pick_type, pick.pick_detail or {}, game)

                if new_status != PickStatus.pending:
                    pick.status = new_status
                    pick.outcome_resolved_at = now
                    updated_creators.add(pick.creator_id)
                    log.info(
                        "Pick resolved",
                        pick_id=pick.pick_id,
                        event=pick.event,
                        result=new_status,
                    )

        db.flush()

        # Recompute records for any creators whose picks were resolved
        for creator_id in updated_creators:
            recompute_record(creator_id, db)

        db.commit()
        log.info("Outcome resolution complete", resolved=len(updated_creators))

    except Exception as e:
        log.error("Outcome resolution failed", error=str(e))
        db.rollback()
    finally:
        db.close()
