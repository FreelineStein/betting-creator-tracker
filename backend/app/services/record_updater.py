"""
CreatorRecord updater — recomputes a creator's W/L record from their Pick history.
Called after any picks are resolved.
"""
import structlog
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Pick, PickStatus, CreatorRecord

log = structlog.get_logger()


def recompute_record(creator_id: str, db: Session) -> CreatorRecord:
    """
    Recompute a creator's aggregated record from scratch.
    Always derives from Pick data — never trust cached values as source of truth.
    """
    picks = db.query(Pick).filter(
        Pick.creator_id == creator_id,
        Pick.status.in_([PickStatus.won, PickStatus.lost, PickStatus.push]),
    ).all()

    wins = sum(1 for p in picks if p.status == PickStatus.won)
    losses = sum(1 for p in picks if p.status == PickStatus.lost)
    pushes = sum(1 for p in picks if p.status == PickStatus.push)
    total = wins + losses + pushes

    win_rate = wins / (wins + losses) if (wins + losses) > 0 else None

    # ROI: simplified vs break-even (~52.4% win rate at -110)
    roi = round((win_rate - 0.524) * 100, 1) if win_rate is not None else None

    # Per-sport breakdown
    accuracy_by_sport: dict = {}
    for pick in picks:
        sport = pick.sport or "Unknown"
        if sport not in accuracy_by_sport:
            accuracy_by_sport[sport] = {"wins": 0, "losses": 0, "pushes": 0}
        if pick.status == PickStatus.won:
            accuracy_by_sport[sport]["wins"] += 1
        elif pick.status == PickStatus.lost:
            accuracy_by_sport[sport]["losses"] += 1
        elif pick.status == PickStatus.push:
            accuracy_by_sport[sport]["pushes"] += 1

    # Upsert the record
    record = db.query(CreatorRecord).filter(
        CreatorRecord.creator_id == creator_id
    ).first()

    if not record:
        record = CreatorRecord(creator_id=creator_id)
        db.add(record)

    record.total_picks = total
    record.wins = wins
    record.losses = losses
    record.pushes = pushes
    record.win_rate = round(win_rate, 4) if win_rate is not None else None
    record.roi = roi
    record.accuracy_by_sport = accuracy_by_sport
    record.last_updated = datetime.now(timezone.utc)

    log.info(
        "Record updated",
        creator_id=creator_id,
        wins=wins,
        losses=losses,
        pushes=pushes,
        win_rate=f"{win_rate:.1%}" if win_rate else "N/A",
    )

    return record
