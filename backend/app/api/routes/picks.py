from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import Pick, PickStatus, PickType, ExtractionMethod, Creator, Source
from app.models.source import Platform, PostType, ExtractionStatus
from app.api.deps import require_admin

limiter = Limiter(key_func=get_remote_address)
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
@limiter.limit("10/minute")
def create_pick(request: Request, data: PickCreate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    creator = db.query(Creator).filter(Creator.creator_id == data.creator_id).first()
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    source = Source(
        source_id=str(uuid.uuid4()),
        creator_id=data.creator_id,
        platform=Platform.reddit,
        post_type=PostType.comment,
        post_url="",
        posted_at=datetime.now(timezone.utc),
        raw_content=data.raw_text or "",
        extraction_status=ExtractionStatus.success,
        extraction_attempts=[{"method": "manual", "success": True}],
    )
    db.add(source)
    db.flush()

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
@limiter.limit("60/minute")
def list_picks(
    request: Request,
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
    return query.order_by(Pick.logged_at.desc()).limit(min(limit, 100)).all()


@router.get("/{pick_id}")
@limiter.limit("60/minute")
def get_pick(request: Request, pick_id: str, db: Session = Depends(get_db)):
    pick = db.query(Pick).filter(Pick.pick_id == pick_id).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    return pick


class PickUpdate(BaseModel):
    status: Optional[PickStatus] = None
    event: Optional[str] = None
    event_date: Optional[datetime] = None
    odds: Optional[str] = None
    pick_detail: Optional[Dict[str, Any]] = None


@router.patch("/{pick_id}")
@limiter.limit("10/minute")
def update_pick(request: Request, pick_id: str, data: PickUpdate, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    pick = db.query(Pick).filter(Pick.pick_id == pick_id).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] in (PickStatus.won, PickStatus.lost, PickStatus.push):
        updates["outcome_resolved_at"] = datetime.now(timezone.utc)
    for field, value in updates.items():
        setattr(pick, field, value)
    db.commit()
    db.refresh(pick)
    return pick


class LegUpdate(BaseModel):
    leg_index: int
    result: str  # "won", "lost", "push"


@router.patch("/{pick_id}/legs")
@limiter.limit("10/minute")
def update_parlay_leg(
    request: Request,
    pick_id: str,
    data: LegUpdate,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    """Update the result of a specific parlay leg by index."""
    pick = db.query(Pick).filter(Pick.pick_id == pick_id).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    if pick.pick_type != "parlay":
        raise HTTPException(status_code=400, detail="Pick is not a parlay")

    legs = (pick.pick_detail or {}).get("legs", [])
    if data.leg_index < 0 or data.leg_index >= len(legs):
        raise HTTPException(status_code=400, detail="Invalid leg index")
    if data.result not in ("won", "lost", "push", "pending"):
        raise HTTPException(status_code=400, detail="Invalid result. Must be: won, lost, push, pending")

    legs[data.leg_index]["result"] = data.result

    # Determine overall parlay status
    from app.services.outcome_resolver import _parlay_status_from_legs
    overall = _parlay_status_from_legs(legs)

    pick.pick_detail = {**pick.pick_detail, "legs": legs}
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(pick, "pick_detail")

    if overall != PickStatus.pending:
        pick.status = overall
        pick.outcome_resolved_at = datetime.now(timezone.utc)
    elif pick.status != PickStatus.pending:
        # If we reset a leg to pending, reset overall too
        pick.status = PickStatus.pending
        pick.outcome_resolved_at = None

    db.commit()
    db.refresh(pick)
    return pick


@router.delete("/{pick_id}")
@limiter.limit("10/minute")
def delete_pick(request: Request, pick_id: str, db: Session = Depends(get_db), _admin: str = Depends(require_admin)):
    from app.services.record_updater import recompute_record

    pick = db.query(Pick).filter(Pick.pick_id == pick_id).first()
    if not pick:
        raise HTTPException(status_code=404, detail="Pick not found")
    creator_id = pick.creator_id
    db.delete(pick)
    db.flush()
    # Keep W/L consistent — if a resolved pick was deleted, the creator's
    # totals would otherwise drift until the next scheduled recompute.
    recompute_record(creator_id, db)
    db.commit()
    return {"status": "deleted", "pick_id": pick_id, "creator_id": creator_id}
