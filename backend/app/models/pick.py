from sqlalchemy import Column, String, DateTime, JSON, Enum as SAEnum, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
import uuid
from app.database import Base


class PickType(str, enum.Enum):
    spread = "spread"
    moneyline = "moneyline"
    over_under = "over_under"
    prop = "prop"
    parlay = "parlay"


class PickStatus(str, enum.Enum):
    pending = "pending"    # Game hasn't happened yet
    won = "won"
    lost = "lost"
    push = "push"
    void = "void"          # Game cancelled, pick invalidated


class ExtractionMethod(str, enum.Enum):
    caption = "caption"
    subtitles = "subtitles"
    whisper = "whisper"
    ocr = "ocr"
    llm = "llm"
    manual = "manual"      # Human entered


class Pick(Base):
    """A structured bet extracted from a Source."""
    __tablename__ = "picks"

    pick_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String, ForeignKey("sources.source_id"), nullable=False)
    creator_id = Column(String, ForeignKey("creators.creator_id"), nullable=False)

    # Sport and event
    sport = Column(String)                # "NFL", "NBA", "MLB", etc.
    event = Column(String)                # "Lakers vs Celtics"
    event_date = Column(DateTime(timezone=True))
    # External game identity, pinned at submission time so resolution is a
    # direct lookup instead of fuzzy team-name matching. Null on legacy
    # picks and on submissions where no scheduled game could be found.
    event_id = Column(String, index=True)
    event_provider = Column(String)       # "espn" | "odds_api"

    # Pick details
    pick_type = Column(SAEnum(PickType))
    pick_detail = Column(JSON)            # {"team": "Lakers", "line": "-3.5"}
    odds = Column(String)                 # "-110", "+150", etc.
    units = Column(Float)                 # Units bet, if creator specifies

    # Status
    status = Column(SAEnum(PickStatus), default=PickStatus.pending, nullable=False)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())
    outcome_resolved_at = Column(DateTime(timezone=True))

    # Extraction metadata
    extraction_method = Column(SAEnum(ExtractionMethod))
    extraction_confidence = Column(Float)  # 0.0 - 1.0
    raw_text = Column(String)              # The raw text this pick was parsed from

    # Relationships
    source = relationship("Source", back_populates="picks")
    creator = relationship("Creator", back_populates="picks")

    def __repr__(self):
        return f"<Pick {self.sport} {self.event} {self.pick_type} [{self.status}]>"
