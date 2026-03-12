from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
from app.database import get_db
from app.models import Creator, CreatorTier, CreatorRecord, Pick, PickStatus

router = APIRouter(prefix="/creators", tags=["creators"])


class CreatorCreate(BaseModel):
    display_name: str
    tier: CreatorTier = CreatorTier.tracked
    platforms: list[dict] = []


class CreatorResponse(BaseModel):
    creator_id: str
    display_name: str
    tier: str
    platforms: list
    tracking_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[CreatorResponse])
def list_creators(
    tier: Optional[CreatorTier] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    query = db.query(Creator)
    if tier:
        query = query.filter(Creator.tier == tier)
    if active_only:
        query = query.filter(Creator.tracking_active == True)
    return query.all()


@router.post("/", response_model=CreatorResponse, status_code=201)
def create_creator(data: CreatorCreate, db: Session = Depends(get_db)):
    creator = Creator(**data.model_dump())
    db.add(creator)
    db.commit()
    db.refresh(creator)
    return creator


@router.get("/{creator_id}", response_model=CreatorResponse)
def get_creator(creator_id: str, db: Session = Depends(get_db)):
    creator = db.query(Creator).filter(Creator.creator_id == creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return creator


def calculate_creator_record(creator_id: str, db: Session):
    """Calculate creator W/L record from their picks."""
    creator = db.query(Creator).filter(Creator.creator_id == creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    picks = db.query(Pick).filter(Pick.creator_id == creator_id).all()
    
    # Calculate stats
    wins = len([p for p in picks if p.status == PickStatus.won])
    losses = len([p for p in picks if p.status == PickStatus.lost])
    pushes = len([p for p in picks if p.status == PickStatus.push])
    total = len(picks)
    
    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
    roi = (win_rate - 0.524) * 100  # simplified ROI
    
    # Group by sport
    accuracy_by_sport = {}
    for pick in picks:
        sport = pick.sport or "Unknown"
        if sport not in accuracy_by_sport:
            accuracy_by_sport[sport] = {"wins": 0, "losses": 0}
        if pick.status == PickStatus.won:
            accuracy_by_sport[sport]["wins"] += 1
        elif pick.status == PickStatus.lost:
            accuracy_by_sport[sport]["losses"] += 1
    
    # Create or update record
    record = db.query(CreatorRecord).filter(CreatorRecord.creator_id == creator_id).first()
    if record:
        record.total_picks = total
        record.wins = wins
        record.losses = losses
        record.pushes = pushes
        record.win_rate = round(win_rate, 3)
        record.roi = round(roi, 1)
        record.accuracy_by_sport = accuracy_by_sport
        record.last_updated = datetime.now(timezone.utc)
    else:
        record = CreatorRecord(
            creator_id=creator_id,
            total_picks=total,
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=round(win_rate, 3),
            roi=round(roi, 1),
            accuracy_by_sport=accuracy_by_sport,
            last_updated=datetime.now(timezone.utc),
        )
        db.add(record)
    
    db.commit()
    db.refresh(record)
    return record


@router.get("/{creator_id}/record")
def get_creator_record(creator_id: str, db: Session = Depends(get_db)):
    record = db.query(CreatorRecord).filter(CreatorRecord.creator_id == creator_id).first()
    if not record:
        # Auto-calculate if doesn't exist
        record = calculate_creator_record(creator_id, db)
    return record


@router.post("/{creator_id}/record/recalculate")
def recalculate_creator_record(creator_id: str, db: Session = Depends(get_db)):
    """Recalculate W/L record based on picks."""
    record = calculate_creator_record(creator_id, db)
    return {"status": "success", "record": record}
