from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Pick, PickStatus

router = APIRouter(prefix="/picks", tags=["picks"])


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
