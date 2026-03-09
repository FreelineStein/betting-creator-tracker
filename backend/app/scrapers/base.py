from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class RawPost:
    """Normalized output from any scraper — feeds into the extraction pipeline."""
    platform: str
    post_type: str
    post_url: str
    posted_at: Optional[datetime]

    # Text content — populated by whatever is available on the platform
    caption: Optional[str] = None
    description: Optional[str] = None
    subtitles: Optional[str] = None
    video_url: Optional[str] = None

    # Raw metadata passthrough for extractors to use
    raw: dict = None


class BaseScraper(ABC):
    """All scrapers return a list of RawPost objects."""

    @abstractmethod
    async def fetch_recent_posts(self, handle: str, since: Optional[datetime] = None) -> list[RawPost]:
        """Fetch recent posts for a creator handle."""
        ...
