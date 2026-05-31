"""Screener V2 endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.services.screener import ScreenerService, ScreenerFilter
from app.models import AIScore, Candle, Symbol

router = APIRouter(prefix="/screener", tags=["screener"])


# ============================================================
# Main scan endpoint (V2)
# ============================================================

class ScanPayload(BaseModel):
    universe: Optional[str] = None
    watchlist_id: Optional[str] = None
    sector: Optional[str] = None
    sectors: Optional[list[str]] = None
    analysis_type: Optional[str] = None

    opportunity_score_min: Optional[float] = None
    opportunity_score_max: Optional[float] = None
    star_rating_min: Optional[int] = Field(None, ge=1, le=5)
    accumulation_score_min: Optional[float] = None
    distribution_score_max: Optional[float] = None
    foreign_strength_min: Optional[float] = None
    trend_score_min: Optional[float] = None
    liquidity_score_min: Optional[float] = None
    bandar_score_min: Optional[float] = None
    bandar_score_max: Optional[float] = None
    inventory_score_min: Optional[float] = None
    momentum_score_min: Optional[float] = None
    volume_anomaly_min: Optional[float] = None
    foreign_net_min: Optional[float] = None
    foreign_net_days: int = 20

    wyckoff_stages: Optional[list[int]] = None
    trend_label: Optional[str] = None
    trade_readiness_signal: Optional[str] = None
    smart_money_signal: Optional[str] = None
    verdict: Optional[str] = None
    retail_non_flow_min: Optional[float] = None
    retail_non_flow_label: Optional[str] = None
    max_fomo_risk: Optional[float] = None
    sector_rrg_quadrant: Optional[str] = None

    price_min: Optional[float] = None
    price_max: Optional[float] = None

    sort_by: str = "opportunity_score"
    sort_desc: bool = True
    limit: int = Field(100, ge=1, le=500)


@router.post("/scan")
def run_screener_v2(payload: ScanPayload, db: Session = Depends(get_db)):
    """Main V2 screener — accepts complex filter payload via POST."""
    f = ScreenerFilter(**payload.model_dump())
    return ScreenerService(db).scan(f)


# Legacy GET endpoint (for backward compat with old frontend)
@router.get("")
def run_screener_legacy(
    universe: str | None = Query(None),
    sector: str | None = Query(None),
    analysis_type: str | None = Query(None),
    opportunity_score_min: float | None = Query(None),
    star_rating_min: int | None = Query(None, ge=1, le=5),
    accumulation_score_min: float | None = Query(None),
    foreign_strength_min: float | None = Query(None),
    trend_score_min: float | None = Query(None),
    liquidity_score_min: float | None = Query(None),
    bandar_score_min: float | None = Query(None),
    bandar_score_max: float | None = Query(None),
    foreign_net_min: float | None = Query(None),
    foreign_net_days: int = Query(20),
    inventory_score_min: float | None = Query(None),
    momentum_score_min: float | None = Query(None),
    volume_anomaly_min: float | None = Query(None),
    smart_money_signal: str | None = Query(None),
    verdict: str | None = Query(None),
    retail_non_flow_min: float | None = Query(None),
    retail_non_flow_label: str | None = Query(None),
    trend_label: str | None = Query(None),
    trade_readiness_signal: str | None = Query(None),
    max_fomo_risk: float | None = Query(None),
    price_min: float | None = Query(None),
    price_max: float | None = Query(None),
    sort_by: str = Query("opportunity_score"),
    sort_desc: bool = Query(True),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    f = ScreenerFilter(
        universe=universe, sector=sector, analysis_type=analysis_type,
        opportunity_score_min=opportunity_score_min,
        star_rating_min=star_rating_min,
        accumulation_score_min=accumulation_score_min,
        foreign_strength_min=foreign_strength_min,
        trend_score_min=trend_score_min,
        liquidity_score_min=liquidity_score_min,
        bandar_score_min=bandar_score_min,
        bandar_score_max=bandar_score_max,
        foreign_net_min=foreign_net_min,
        foreign_net_days=foreign_net_days,
        inventory_score_min=inventory_score_min,
        momentum_score_min=momentum_score_min,
        volume_anomaly_min=volume_anomaly_min,
        smart_money_signal=smart_money_signal,
        verdict=verdict,
        retail_non_flow_min=retail_non_flow_min,
        retail_non_flow_label=retail_non_flow_label,
        trend_label=trend_label,
        trade_readiness_signal=trade_readiness_signal,
        max_fomo_risk=max_fomo_risk,
        price_min=price_min,
        price_max=price_max,
        sort_by=sort_by,
        sort_desc=sort_desc,
        limit=limit,
    )
    return ScreenerService(db).scan(f)


# ============================================================
# Analysis types catalog
# ============================================================

@router.get("/analysis-types")
def list_analysis_types():
    return [
        {"id": "smart_money",       "name": "Smart Money Flow",       "name_id": "Aliran Smart Money",  "description": "Saham dengan opportunity score tertinggi (composite)"},
        {"id": "non_retail_flow",   "name": "Non-Retail Flow",        "name_id": "Aliran Non-Retail",   "description": "Smart money kontrarian retail — retail jual, smart money beli"},
        {"id": "foreign_flow",      "name": "Foreign Flow",           "name_id": "Aliran Asing",         "description": "Foreign net flow multi-timeframe"},
        {"id": "market_maker",      "name": "Market Maker Analysis",  "name_id": "Analisa Market Maker", "description": "Aktivitas broker bandar (institutional + market maker)"},
        {"id": "accumulation",      "name": "Accumulation Score",     "name_id": "Skor Akumulasi",       "description": "Volume expansion, price compression, foreign accum"},
        {"id": "distribution",      "name": "Distribution Score",     "name_id": "Skor Distribusi",      "description": "Supply absorption failure, foreign exit"},
        {"id": "momentum",          "name": "Momentum Flow",          "name_id": "Aliran Momentum",      "description": "Saham dengan momentum tertinggi"},
        {"id": "relative_strength", "name": "Relative Strength",      "name_id": "Kekuatan Relatif",     "description": "Outperform vs IHSG"},
    ]


# ============================================================
# Universes catalog
# ============================================================

@router.get("/universes")
def list_universes(db: Session = Depends(get_db)):
    counts = {
        "ALL":       db.query(func.count(Symbol.code)).filter(Symbol.is_active == True).scalar() or 0,
        "LQ45":      db.query(func.count(Symbol.code)).filter(Symbol.is_lq45 == True).scalar() or 0,
        "IDX30":     db.query(func.count(Symbol.code)).filter(Symbol.is_idx30 == True).scalar() or 0,
        "KOMPAS100": db.query(func.count(Symbol.code)).filter(Symbol.is_kompas100 == True).scalar() or 0,
        "ISSI":      db.query(func.count(Symbol.code)).filter(Symbol.is_issi == True).scalar() or 0,
    }
    return [
        {"id": "ALL",       "name": "All Stocks",     "count": counts["ALL"]},
        {"id": "LQ45",      "name": "LQ45",           "count": counts["LQ45"]},
        {"id": "IDX30",     "name": "IDX30",          "count": counts["IDX30"]},
        {"id": "KOMPAS100", "name": "Kompas100",      "count": counts["KOMPAS100"]},
        {"id": "ISSI",      "name": "ISSI (Syariah)", "count": counts["ISSI"]},
        {"id": "WATCHLIST", "name": "My Watchlist",   "count": -1},  # populated client-side
    ]


# ============================================================
# Presets (Updated for V2)
# ============================================================

@router.get("/presets")
def screener_presets():
    """V2 screener templates."""
    return [
        {
            "id": "elite_setup",
            "name": "★★★★★ Elite Setup",
            "description": "Star rating ≥5 — saham dengan setup paling matang",
            "filters": {
                "star_rating_min": 5,
                "sort_by": "opportunity_score",
            },
        },
        {
            "id": "early_breakout",
            "name": "Early Breakout (Stage 2)",
            "description": "Wyckoff Stage 2 — sweet spot untuk entry",
            "filters": {
                "wyckoff_stages": [2],
                "liquidity_score_min": 50,
                "sort_by": "breakout_quality_score",
            },
        },
        {
            "id": "stealth_accumulation",
            "name": "Stealth Accumulation",
            "description": "Stage 1 dengan akumulasi diam-diam (foreign in, harga belum naik)",
            "filters": {
                "wyckoff_stages": [1],
                "accumulation_score_min": 65,
                "max_fomo_risk": 30,
                "sort_by": "accumulation_score",
            },
        },
        {
            "id": "ready_buy_today",
            "name": "Ready to Buy (Today)",
            "description": "Trade Readiness signal = READY_BUY",
            "filters": {
                "trade_readiness_signal": "READY_BUY",
                "sort_by": "trade_readiness_score",
            },
        },
        {
            "id": "foreign_inflow_block",
            "name": "Foreign Block Inflow",
            "description": "Foreign Strength tinggi multi-timeframe",
            "filters": {
                "foreign_strength_min": 70,
                "liquidity_score_min": 50,
                "sort_by": "foreign_strength_score",
            },
        },
        {
            "id": "non_retail_contrarian",
            "name": "Retail Buang, Smart Money Beli",
            "description": "Retail jual berat tapi smart money akumulasi (kontrarian)",
            "filters": {
                "retail_non_flow_label": "POSITIVE_NONFLOW",
                "verdict": "GREEN_CHECK",
                "sort_by": "retail_non_flow_score",
            },
        },
        {
            "id": "trend_followers",
            "name": "Strong Trend Followers",
            "description": "Trend score tinggi + likuiditas bagus",
            "filters": {
                "trend_label": "STRONG_BULLISH",
                "liquidity_score_min": 60,
                "sort_by": "trend_score",
            },
        },
        {
            "id": "avoid_fomo",
            "name": "Avoid FOMO Trap",
            "description": "Distribusi dengan FOMO risk tinggi (avoid list)",
            "filters": {
                "wyckoff_stages": [4, 5],
                "sort_by": "fomo_risk_score",
                "sort_desc": True,
            },
        },
        {
            "id": "lq45_top",
            "name": "LQ45 Top Picks",
            "description": "LQ45 saja, sorted by opportunity score",
            "filters": {
                "universe": "LQ45",
                "sort_by": "opportunity_score",
            },
        },
        {
            "id": "idx30_top",
            "name": "IDX30 Top Picks",
            "description": "IDX30 (top 30) saja",
            "filters": {
                "universe": "IDX30",
                "sort_by": "opportunity_score",
            },
        },
    ]


# ============================================================
# Market Health Index (overall market state)
# ============================================================

@router.get("/market-health")
def market_health(db: Session = Depends(get_db)):
    """Market-wide composite health index."""
    latest = db.query(func.max(AIScore.date)).scalar()
    if not latest:
        return {"error": "No data"}

    scores = db.query(AIScore).filter(AIScore.date == latest).all()
    if not scores:
        return {"error": "No scores"}

    n = len(scores)

    # Stage distribution
    stage_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for s in scores:
        if s.wyckoff_stage:
            stage_counts[s.wyckoff_stage] = stage_counts.get(s.wyckoff_stage, 0) + 1

    # Trend distribution
    trend_dist = {}
    for s in scores:
        lbl = s.trend_label or "NEUTRAL"
        trend_dist[lbl] = trend_dist.get(lbl, 0) + 1

    # Setup label distribution
    setup_dist = {}
    for s in scores:
        lbl = s.setup_label or "IGNORE"
        setup_dist[lbl] = setup_dist.get(lbl, 0) + 1

    avg_opp = sum((s.opportunity_score or 0) for s in scores) / n
    avg_trend = sum((s.trend_score or 0) for s in scores) / n
    avg_foreign = sum((s.foreign_strength_score or 0) for s in scores) / n
    avg_fomo = sum((s.fomo_risk_score or 0) for s in scores) / n

    # Latest day breadth
    candles = db.query(Candle).filter(Candle.date == latest).all()
    prev_date = db.query(func.max(Candle.date)).filter(Candle.date < latest).scalar()
    prev_candles = (
        db.query(Candle).filter(Candle.date == prev_date).all() if prev_date else []
    )
    prev_close = {c.symbol: c.close for c in prev_candles}

    advance = decline = 0
    for c in candles:
        p = prev_close.get(c.symbol)
        if not p or p == 0:
            continue
        if c.close > p:
            advance += 1
        elif c.close < p:
            decline += 1

    advance_ratio = advance / max(advance + decline, 1)

    # Composite health (0-100)
    health = (
        avg_opp * 0.35 +
        avg_trend * 0.25 +
        avg_foreign * 0.15 +
        advance_ratio * 100 * 0.15 +
        (100 - avg_fomo) * 0.10
    )
    health = round(float(health), 1)

    if health >= 70:
        regime = "RISK_ON"
        regime_label = "Risk On — Pasar bullish, fokus offensive"
    elif health >= 45:
        regime = "NEUTRAL"
        regime_label = "Neutral — selektif per saham"
    else:
        regime = "RISK_OFF"
        regime_label = "Risk Off — defensive, kurangi exposure"

    return {
        "as_of": latest.isoformat(),
        "health_score": health,
        "regime": regime,
        "regime_label": regime_label,
        "avg_opportunity_score": round(avg_opp, 1),
        "avg_trend_score": round(avg_trend, 1),
        "avg_foreign_strength": round(avg_foreign, 1),
        "avg_fomo_risk": round(avg_fomo, 1),
        "advance": advance,
        "decline": decline,
        "advance_ratio_pct": round(advance_ratio * 100, 1),
        "stage_distribution": stage_counts,
        "trend_distribution": trend_dist,
        "setup_distribution": setup_dist,
        "total_stocks": n,
    }
