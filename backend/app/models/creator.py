from sqlalchemy import Column, String, Boolean, DateTime, JSON, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.database import Base


class CreatorTier(str, enum.Enum):
    tracked = "tracked"   # Named creators we actively follow
    public = "public"     # Crowd-sourced (Reddit, comments, etc.)


class Creator(Base):
    __tablename__ = "creators"

    creator_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name = Column(String, nullable=False)
    tier = Column(SAEnum(CreatorTier), nullable=False, default=CreatorTier.tracked)

    # e.g. [{"platform": "instagram", "handle": "@user", "url": "https://..."}]
    platforms = Column(JSON, default=list)

    profile_image_url = Column(String, nullable=True)
    tracking_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    sources = relationship("Source", back_populates="creator")
    picks = relationship("Pick", back_populates="creator")
    record = relationship("CreatorRecord", back_populates="creator", uselist=False)

    def __repr__(self):
        return f"<Creator {self.display_name} ({self.tier})>"
