from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models import Creator, CreatorTier, CreatorRecord

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


@router.get("/{creator_id}/record")
def get_creator_record(creator_id: str, db: Session = Depends(get_db)):
    record = db.query(CreatorRecord).filter(CreatorRecord.creator_id == creator_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="No record found for this creator")
    return record
