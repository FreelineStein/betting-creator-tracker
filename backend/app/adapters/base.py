"""
Adapter interface for notification-based ingestion.

An adapter receives content from an external source (Gmail, a chat bot,
a webhook) and emits RawPost objects compatible with the existing
extraction pipeline. The adapter is responsible for source-specific
parsing; everything downstream is platform-agnostic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.scrapers.base import RawPost


@dataclass
class NotificationMetadata:
    notification_id: str
    received_at: datetime
    source_platform: str
    raw_notification: Optional[str] = None


class BaseAdapter(ABC):
    @abstractmethod
    async def fetch_new_posts(
        self, since: datetime
    ) -> list[tuple[RawPost, NotificationMetadata]]:
        """Return posts received since the given timestamp.

        Implementations may be over-inclusive — DB-level dedup on
        Source.post_url is the authoritative deduplication mechanism.
        """
        ...
