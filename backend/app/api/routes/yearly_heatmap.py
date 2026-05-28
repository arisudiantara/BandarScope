"""Yearly Smart Money Heatmap endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.yearly_heatmap import YearlyHeatmapService

router = APIRouter(prefix="/yearly-heatmap", tags=["yearly-heatmap"])


@router.get("/symbol/{symbol}")
def per_symbol(
    symbol: str,
    months: int = Query(12, ge=3, le=24),
    db: Session = Depends(get_db),
):
    """Per-symbol monthly heatmap with behavior labels & summary stats."""
    return YearlyHeatmapService(db).per_symbol(symbol.upper(), months)


@router.get("/universe")
def universe_cross_section(
    months: int = Query(12, ge=3, le=24),
    top_n: int = Query(30, ge=10, le=100),
    db: Session = Depends(get_db),
):
    """Universe-wide behavior matrix (top N symbols × months)."""
    return YearlyHeatmapService(db).universe_cross_section(months, top_n)
