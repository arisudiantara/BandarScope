"""Screener endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.screener import ScreenerService, ScreenerFilter

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("")
def run_screener(
    bandar_score_min: float | None = Query(None),
    bandar_score_max: float | None = Query(None),
    foreign_net_min: float | None = Query(None),
    foreign_net_days: int = Query(20),
    inventory_score_min: float | None = Query(None),
    momentum_score_min: float | None = Query(None),
    volume_anomaly_min: float | None = Query(None),
    smart_money_signal: str | None = Query(None),
    sector: str | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    verdict: str | None = Query(None, description="GREEN_CHECK / ORANGE_X / RED_MINUS"),
    retail_non_flow_min: float | None = Query(None, description="0-100"),
    retail_non_flow_label: str | None = Query(None,
        description="POSITIVE_NONFLOW / NEUTRAL / NEGATIVE_NONFLOW"),
    sort_by: str = Query("bandar_score"),
    sort_desc: bool = Query(True),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    f = ScreenerFilter(
        bandar_score_min=bandar_score_min,
        bandar_score_max=bandar_score_max,
        foreign_net_min=foreign_net_min,
        foreign_net_days=foreign_net_days,
        inventory_score_min=inventory_score_min,
        momentum_score_min=momentum_score_min,
        volume_anomaly_min=volume_anomaly_min,
        smart_money_signal=smart_money_signal,
        sector=sector,
        price_min=price_min,
        price_max=price_max,
        verdict=verdict,
        retail_non_flow_min=retail_non_flow_min,
        retail_non_flow_label=retail_non_flow_label,
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=limit,
    )
    return ScreenerService(db).scan(f)


@router.get("/presets")
def screener_presets():
    """Predefined screener templates."""
    return [
        {
            "id": "verdict_green",
            "name": "Verdict Hijau ✓",
            "description": "Akumulasi konsisten — inventory line garis lurus naik",
            "filters": {
                "verdict": "GREEN_CHECK",
                "sort_by": "bandar_score",
            },
        },
        {
            "id": "retail_dumping_smart_buying",
            "name": "Retail Buang, Smart Money Beli",
            "description": "Retail Non-Flow tinggi (kontrarian positif) + bandar akumulasi",
            "filters": {
                "retail_non_flow_label": "POSITIVE_NONFLOW",
                "verdict": "GREEN_CHECK",
                "sort_by": "retail_non_flow_score",
            },
        },
        {
            "id": "smart_money_buy",
            "name": "Smart Money Accumulation",
            "description": "BandarScore>70, Foreign Net>0, Inventory>65",
            "filters": {
                "bandar_score_min": 70,
                "foreign_net_min": 0,
                "inventory_score_min": 65,
                "smart_money_signal": "accumulation",
                "sort_by": "bandar_score",
            },
        },
        {
            "id": "stealth_accumulation",
            "name": "Stealth Accumulation",
            "description": "Inventory rising, momentum still low",
            "filters": {
                "inventory_score_min": 70,
                "momentum_score_min": 30,
                "smart_money_signal": "accumulation",
                "sort_by": "inventory_score",
            },
        },
        {
            "id": "breakout_setup",
            "name": "Breakout Setup",
            "description": "Volume anomaly + strong momentum",
            "filters": {
                "volume_anomaly_min": 1.5,
                "momentum_score_min": 65,
                "bandar_score_min": 60,
                "sort_by": "momentum_score",
            },
        },
        {
            "id": "verdict_red_warning",
            "name": "Verdict Merah −",
            "description": "Distribusi konsisten — exit candidates",
            "filters": {
                "verdict": "RED_MINUS",
                "sort_by": "bandar_score",
                "sort_desc": False,
            },
        },
        {
            "id": "retail_fomo_trap",
            "name": "Retail FOMO Trap",
            "description": "Retail buy berlebihan — potensi distribution top",
            "filters": {
                "retail_non_flow_label": "NEGATIVE_NONFLOW",
                "smart_money_signal": "distribution",
                "sort_by": "retail_non_flow_score",
                "sort_desc": False,
            },
        },
        {
            "id": "distribution_warning",
            "name": "Distribution Warning",
            "description": "Smart money distributing — exit candidates",
            "filters": {
                "smart_money_signal": "distribution",
                "bandar_score_max": 35,
                "sort_by": "bandar_score",
                "sort_desc": False,
            },
        },
        {
            "id": "foreign_inflow",
            "name": "Foreign Inflow Leaders",
            "description": "Highest 20-day foreign net buy",
            "filters": {
                "foreign_net_min": 1_000_000_000,
                "sort_by": "foreign_score",
            },
        },
    ]
