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

            # TODO: Parse extracted_text into structured Pick objects (next step)

        db.commit()

    except Exception as e:
        log.error("Scrape failed", creator=creator.display_name, platform=platform, error=str(e))
        db.rollback()


async def resolve_pending_outcomes():
    """Check game results and update Pick statuses."""
    # TODO: Integrate with The Odds API to resolve pending picks
    log.info("Checking pending pick outcomes")
