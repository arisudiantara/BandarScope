"""Sector & rotation endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.sector import SectorService

router = APIRouter(prefix="/sectors", tags=["sectors"])


@router.get("/activity")
def sector_activity(
    days: int = Query(5, ge=1, le=60),
    db: Session = Depends(get_db),
):
    return SectorService(db).sector_activity(days)


@router.get("/rotation")
def rotation_chart(
    period_days: int = Query(30, ge=10, le=120),
    db: Session = Depends(get_db),
):
    return SectorService(db).rrg(period_days)


@router.get("/heatmap")
def heatmap(db: Session = Depends(get_db)):
    return SectorService(db).heatmap()
