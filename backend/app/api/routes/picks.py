from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
from app.database import get_db
from app.models import Pick, PickStatus, PickType, ExtractionMethod, Creator, Source
from app.models.source import Platform, PostType, ExtractionStatus

router = APIRouter(prefix="/picks", tags=["picks"])


class PickCreate(BaseModel):
    creator_id: str
    sport: str
    event: str
    event_date: datetime
    pick_type: PickType
    pick_detail: Dict[str, Any]
    odds: Optional[str] = None
    units: Optional[float] = None
    status: PickStatus = PickStatus.pending
    extraction_method: ExtractionMethod = ExtractionMethod.manual
    extraction_confidence: Optional[float] = 1.0
    raw_text: Optional[str] = None


class PickResponse(BaseModel):
    pick_id: str
    creator_id: str
    sport: str
    event: str
    event_date: datetime
    pick_type: str
    pick_detail: Dict
    odds: Optional[str]
    units: Optional[float]
    status: str
    logged_at: datetime
    extraction_method: str
    extraction_confidence: Optional[float]

    class Config:
        from_attributes = True


@router.post("/", response_model=PickResponse, status_code=201)
def create_pick(data: PickCreate, db: Session = Depends(get_db)):
    # Verify creator exists
    creator = db.query(Creator).filter(Creator.creator_id == data.creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    
    # Create a source entry for this pick (manual entry)
    source = Source(
        source_id=str(uuid.uuid4()),
        creator_id=data.creator_id,
        platform=Platform.reddit,  # Use reddit as default for manual entries
        post_type=PostType.comment,  # Use comment as default for manual entries
        post_url="",
        posted_at=datetime.now(timezone.utc),
        raw_content=data.raw_text or "",
        extraction_status=ExtractionStatus.success,
        extraction_attempts=[{"method": "manual", "success": True}],
    )
    db.add(source)
    db.flush()
    
    # Create the pick
    pick = Pick(
        pick_id=str(uuid.uuid4()),
        source_id=source.source_id,
        creator_id=data.creator_id,
        sport=data.sport,
        event=data.event,
        event_date=data.event_date,
        pick_type=data.pick_type,
        pick_detail=data.pick_detail,
        odds=data.odds,
        units=data.units,
        status=data.status,
        extraction_method=data.extraction_method,
        extraction_confidence=data.extraction_confidence,
        raw_text=data.raw_text,
    )
    db.add(pick)
    db.commit()
    db.refresh(pick)
    return pick


@router.get("/")
def list_picks(
    creator_id: Optional[str] = None,
    sport: Optional[str] = None,
    status: Optional[PickStatus] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    query = db.query(Pick)
    if creator_id:
        query = query.filter(Pick.creator_id == creator_id)
    if sport:
        query = query.filter(Pick.sport == sport)
    if status:
        query = query.filter(Pick.status == status)
    return query.order_by(Pick.logged_at.desc()).limit(limit).all()


@router.get("/{pick_id}")
def get_pick(pick_id: str, db: Session = Depends(get_db)):
    pick = db.query(Pick).filter(Pick.pick_id == pick_id).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    return pick
