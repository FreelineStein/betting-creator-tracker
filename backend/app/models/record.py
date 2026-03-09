from sqlalchemy import Column, String, DateTime, JSON, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class CreatorRecord(Base):
    """
    Aggregated W/L record per creator. Derived from Pick outcomes.
    Recomputed when picks are resolved — do not treat as source of truth.
    """
    __tablename__ = "creator_records"

    creator_id = Column(String, ForeignKey("creators.creator_id"), primary_key=True)

    total_picks = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    pushes = Column(Integer, default=0)

    win_rate = Column(Float)              # wins / (wins + losses)
    roi = Column(Float)                   # Return on investment (if units tracked)

    # Per-sport breakdown: {"NFL": {"wins": 5, "losses": 3}, "NBA": {...}}
    accuracy_by_sport = Column(JSON, default=dict)

    last_updated = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator = relationship("Creator", back_populates="record")

    def __repr__(self):
        return f"<CreatorRecord {self.creator_id} {self.wins}W-{self.losses}L>"
