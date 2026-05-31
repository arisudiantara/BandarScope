"""Market Summary Pro endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.market_summary_pro import (
    MarketSummaryProService,
    MarketSummaryFilter,
    ANALYSIS_METHODS,
    NORMALIZATION_METHODS,
    PERIODS,
    UNIVERSE_FILTERS,
    PROBABILITY_TIERS,
)

router = APIRouter(prefix="/market-summary-pro", tags=["market-summary-pro"])


class ScanPayload(BaseModel):
    universe: str = "ALL"
    watchlist_id: Optional[str] = None
    analysis_method: str = "smart_money"
    period: str = "daily"
    normalization: str = "normalized"

    min_accumulation: Optional[float] = None
    min_foreign_flow: Optional[float] = None
    min_volume_spike: Optional[float] = None
    min_momentum: Optional[float] = None
    min_liquidity: Optional[float] = None
    min_trend: Optional[float] = None
    min_probability: Optional[float] = None

    require_above_ma5: Optional[bool] = None
    require_above_ma20: Optional[bool] = None
    require_above_ma50: Optional[bool] = None
    require_above_ma200: Optional[bool] = None

    apply_noise_filter: bool = True
    show_rejected: bool = False

    sort_by: str = "probability_score"
    sort_desc: bool = True
    limit: int = Field(200, ge=10, le=1000)


@router.post("/scan")
def scan(payload: ScanPayload, db: Session = Depends(get_db)):
    """Run the full Market Summary Pro scan."""
    if payload.analysis_method not in ANALYSIS_METHODS:
        raise HTTPException(
            400, f"Invalid analysis_method. Must be one of: {ANALYSIS_METHODS}"
        )
    if payload.normalization not in NORMALIZATION_METHODS:
        raise HTTPException(
            400, f"Invalid normalization. Must be one of: {NORMALIZATION_METHODS}"
        )
    f = MarketSummaryFilter(**payload.model_dump())
    return MarketSummaryProService(db).scan(f)


@router.post("/scan.csv", response_class=PlainTextResponse)
def scan_csv(payload: ScanPayload, db: Session = Depends(get_db)):
    """Scan + return CSV export."""
    f = MarketSummaryFilter(**payload.model_dump())
    result = MarketSummaryProService(db).scan(f)
    return MarketSummaryProService.to_csv(result)


@router.get("/config")
def config():
    """Return all valid filter values for the frontend."""
    return {
        "analysis_methods": [
            {"id": "non_retail_flow",      "name": "Non-Retail Flow",         "description": "Inverted retail flow — kontrarian retail signal"},
            {"id": "foreign_flow",         "name": "Foreign Flow Analysis",   "description": "Foreign net flow per period, normalized"},
            {"id": "broker_accumulation",  "name": "Broker Accumulation",     "description": "Bandar (institutional + market maker) net activity"},
            {"id": "smart_money",          "name": "Smart Money Analysis",    "description": "Composite: foreign + bandar combined"},
            {"id": "sector_rotation",      "name": "Sector Rotation",         "description": "Stock return vs IHSG (sector rotation signal)"},
            {"id": "relative_strength",    "name": "Relative Strength",       "description": "Outperform vs IHSG (RS analysis)"},
            {"id": "momentum",             "name": "Momentum Analysis",       "description": "Pure price ROC per period"},
            {"id": "composite_score",      "name": "Composite Score",         "description": "Multi-factor opportunity composite"},
        ],
        "normalization_methods": [
            {"id": "raw",               "name": "Raw",                "description": "Actual values (-100..+100 from formula)"},
            {"id": "normalized",        "name": "Normalized",         "description": "Clipped -100..+100 (default)"},
            {"id": "z_score",           "name": "Z-Score",            "description": "Z-score across universe per period"},
            {"id": "percentile",        "name": "Percentile",         "description": "Rank percentile within universe"},
            {"id": "relative_strength", "name": "Relative Strength",  "description": "Each value minus universe mean"},
        ],
        "periods": [
            {"id": "daily",      "name": "Daily"},
            {"id": "weekly",     "name": "Weekly"},
            {"id": "monthly",    "name": "Monthly"},
            {"id": "quarterly",  "name": "Quarterly"},
            {"id": "yearly",     "name": "Yearly"},
            {"id": "cumulative", "name": "Cumulative"},
        ],
        "universes": [
            {"id": u, "name": u} for u in UNIVERSE_FILTERS
        ],
        "probability_tiers": [
            {"min": low, "max": high, "tier": tier, "label": label}
            for low, high, tier, label in PROBABILITY_TIERS
        ],
    }
