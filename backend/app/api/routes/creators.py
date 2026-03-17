from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import Creator, CreatorTier, CreatorRecord, Pick, PickStatus, Source
from app.api.deps import require_admin

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/creators", tags=["creators"])


class CreatorCreate(BaseModel):
    display_name: str = Field(max_length=100)
    tier: CreatorTier = CreatorTier.tracked
    platforms: list[dict] = Field(default=[], max_length=10)


class CreatorResponse(BaseModel):
    creator_id: str
    display_name: str
    tier: str
    platforms: list
    tracking_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[CreatorResponse])
@limiter.limit("60/minute")
def list_creators(
    request: Request,
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
@limiter.limit("10/minute")
def create_creator(request: Request, data: CreatorCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    creator = Creator(**data.model_dump())
    db.add(creator)
    db.commit()
    db.refresh(creator)
    return creator


@router.get("/{creator_id}", response_model=CreatorResponse)
@limiter.limit("60/minute")
def get_creator(request: Request, creator_id: str, db: Session = Depends(get_db)):
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

    wins = len([p for p in picks if p.status == PickStatus.won])
    losses = len([p for p in picks if p.status == PickStatus.lost])
    pushes = len([p for p in picks if p.status == PickStatus.push])
    total = len(picks)

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else 0
    roi = (win_rate - 0.524) * 100

    accuracy_by_sport = {}
    for pick in picks:
        sport = pick.sport or "Unknown"
        if sport not in accuracy_by_sport:
            accuracy_by_sport[sport] = {"wins": 0, "losses": 0}
        if pick.status == PickStatus.won:
            accuracy_by_sport[sport]["wins"] += 1
        elif pick.status == PickStatus.lost:
            accuracy_by_sport[sport]["losses"] += 1

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
@limiter.limit("60/minute")
def get_creator_record(request: Request, creator_id: str, db: Session = Depends(get_db)):
    record = db.query(CreatorRecord).filter(CreatorRecord.creator_id == creator_id).first()
    if not record:
        record = calculate_creator_record(creator_id, db)
    return record


@router.delete("/{creator_id}")
@limiter.limit("10/minute")
def delete_creator(request: Request, creator_id: str, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    creator = db.query(Creator).filter(Creator.creator_id == creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    picks = db.query(Pick).filter(Pick.creator_id == creator_id).delete()
    sources = db.query(Source).filter(Source.creator_id == creator_id).delete()
    records = db.query(CreatorRecord).filter(CreatorRecord.creator_id == creator_id).delete()
    db.delete(creator)
    db.commit()

    return {"status": "deleted", "display_name": creator.display_name, "deleted_picks": picks, "deleted_sources": sources}


@router.post("/{creator_id}/record/recalculate")
@limiter.limit("10/minute")
def recalculate_creator_record(request: Request, creator_id: str, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    """Recalculate W/L record based on picks."""
    record = calculate_creator_record(creator_id, db)
    return {"status": "success", "record": record}
