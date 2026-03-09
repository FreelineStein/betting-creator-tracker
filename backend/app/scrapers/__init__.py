from app.scrapers.instagram import InstagramScraper
from app.scrapers.twitter import TwitterScraper
from app.scrapers.reddit import RedditScraper

SCRAPER_MAP = {
    "instagram": InstagramScraper,
    "twitter": TwitterScraper,
    "reddit": RedditScraper,
}

__all__ = ["InstagramScraper", "TwitterScraper", "RedditScraper", "SCRAPER_MAP"]
