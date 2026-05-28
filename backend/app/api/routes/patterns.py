"""Pattern Detection endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.patterns import PatternService, PATTERN_CATALOG

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("/catalog")
def catalog():
    """Static catalog of supported patterns with descriptions & playbooks."""
    return PATTERN_CATALOG


@router.get("/detect/{symbol}")
def detect(
    symbol: str,
    lookback_days: int = Query(60, ge=30, le=180),
    db: Session = Depends(get_db),
):
    """Run all 8 detectors on a single symbol."""
    return PatternService(db).detect_all(symbol.upper(), lookback_days)


@router.get("/scan/{pattern_code}")
def scan_universe(
    pattern_code: str,
    min_confidence: float = Query(60, ge=0, le=100),
    limit: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """Scan universe for a specific pattern (e.g. STEALTH_ACCUMULATION)."""
    return PatternService(db).scan_universe(
        pattern_code.upper(), min_confidence, limit
    )
