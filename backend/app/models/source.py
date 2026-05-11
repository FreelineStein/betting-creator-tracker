from sqlalchemy import Boolean, Column, String, DateTime, JSON, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.database import Base


class Platform(str, enum.Enum):
    instagram = "instagram"
    twitter = "twitter"
    youtube = "youtube"
    tiktok = "tiktok"
    reddit = "reddit"


class PostType(str, enum.Enum):
    reel = "reel"
    tweet = "tweet"
    comment = "comment"
    reddit_post = "reddit_post"
    reddit_comment = "reddit_comment"
    youtube_video = "youtube_video"
    tiktok_video = "tiktok_video"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"
    needs_review = "needs_review"


class Source(Base):
    """A single post, reel, tweet, or comment from which picks may be extracted."""
    __tablename__ = "sources"

    source_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    creator_id = Column(String, ForeignKey("creators.creator_id"), nullable=False)

    platform = Column(SAEnum(Platform), nullable=False)
    post_type = Column(SAEnum(PostType), nullable=False)
    post_url = Column(String, nullable=False)
    posted_at = Column(DateTime(timezone=True))

    # Whatever raw text/transcript we managed to extract
    raw_content = Column(Text)

    extraction_status = Column(
        SAEnum(ExtractionStatus),
        default=ExtractionStatus.pending,
        nullable=False
    )

    # Populated after successful or failed extraction
    extraction_attempts = Column(JSON, default=list)  # List of ExtractionAttempt dicts

    # User-driven "this submission's picks don't look right" flag. Surfaced via
    # GET /admin/flagged for batch review; independent of extraction_status,
    # which describes how the parser fared, not whether the result was right.
    flagged_for_review = Column(Boolean, nullable=False, default=False, server_default="false")

    scraped_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    creator = relationship("Creator", back_populates="sources")
    picks = relationship("Pick", back_populates="source")

    def __repr__(self):
        return f"<Source {self.platform} {self.post_type} {self.source_id[:8]}>"
