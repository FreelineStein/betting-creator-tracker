"""
Health and status endpoints for monitoring.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.database import get_db
from app.models import Creator, Pick, PickStatus
from app.services.odds_api_budget import get_usage
from app.api.deps import require_admin

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/status")
@limiter.limit("60/minute")
def health_status(request: Request, db: Session = Depends(get_db)):
    """Public health check with system status overview."""
    try:
        creators_tracked = db.query(Creator).filter(Creator.tracking_active == True).count()
        pending_picks = db.query(Pick).filter(Pick.status == PickStatus.pending).count()
        db_status = "ok"
    except Exception:
        creators_tracked = 0
        pending_picks = 0
        db_status = "error"

    odds_usage = get_usage()

    return {
        "api": "ok",
        "database": db_status,
        "creators_tracked": creators_tracked,
        "pending_picks": pending_picks,
        "odds_api_requests_this_month": odds_usage["requests_used"],
        "odds_api_budget_remaining": odds_usage["budget_remaining"],
    }


@router.post("/resolve")
@limiter.limit("5/minute")
async def trigger_resolve(request: Request, _admin: str = Depends(require_admin)):
    """Manually trigger the outcome resolver."""
    from app.scheduler.jobs import resolve_pending_outcomes
    await resolve_pending_outcomes()
    return {"status": "resolver completed"}


@router.post("/closing-odds")
@limiter.limit("5/minute")
async def trigger_closing_odds(request: Request, _admin: str = Depends(require_admin)):
    """Manually trigger the closing-odds capture job."""
    from app.scheduler.jobs import capture_closing_odds
    await capture_closing_odds()
    return {"status": "closing-odds completed"}
