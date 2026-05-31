"""
Market Summary Screener V2 — Next-gen Smart Money Screener.

Filter dimensions:
- Universe: ALL / WATCHLIST / LQ45 / IDX30 / KOMPAS100 / ISSI
- Sector: 8 IDX sectors
- Analysis Type: changes default sort + emphasizes specific scores
- Composite filters: opportunity_score, accumulation_score, distribution_score,
  trend_score, liquidity_score, foreign_strength_score, etc.
- Wyckoff stage filter (1-5)
- Star rating filter
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AIScore, Symbol, ForeignFlow, Candle, BrokerDailySummary, Broker, Watchlist,
)


# ============================================================
# Analysis Type — controls default sort & display emphasis
# ============================================================
ANALYSIS_TYPE_DEFAULTS = {
    "non_retail_flow":     {"sort_by": "retail_non_flow_score",   "sort_desc": True},
    "foreign_flow":        {"sort_by": "foreign_strength_score",  "sort_desc": True},
    "market_maker":        {"sort_by": "inventory_score",         "sort_desc": True},
    "smart_money":         {"sort_by": "opportunity_score",       "sort_desc": True},
    "accumulation":        {"sort_by": "accumulation_score",      "sort_desc": True},
    "distribution":        {"sort_by": "distribution_score",      "sort_desc": True},
    "momentum":            {"sort_by": "momentum_score",          "sort_desc": True},
    "relative_strength":   {"sort_by": "trend_score",             "sort_desc": True},
}


@dataclass
class ScreenerFilter:
    # Universe
    universe: Optional[str] = None              # 'ALL', 'LQ45', 'IDX30', 'KOMPAS100', 'ISSI', 'WATCHLIST'
    watchlist_id: Optional[str] = None          # if universe == 'WATCHLIST'

    # Sector / industry
    sector: Optional[str] = None
    sectors: Optional[list[str]] = None         # multi-select

    # Analysis type — affects sort + emphasis
    analysis_type: Optional[str] = None         # see ANALYSIS_TYPE_DEFAULTS

    # Component score filters
    opportunity_score_min: Optional[float] = None
    opportunity_score_max: Optional[float] = None
    star_rating_min: Optional[int] = None       # 1-5
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

    # Wyckoff stage filter
    wyckoff_stages: Optional[list[int]] = None  # e.g. [1,2] for accum + early breakout

    # Trend label filter
    trend_label: Optional[str] = None

    # Trade readiness
    trade_readiness_signal: Optional[str] = None  # READY_BUY/WATCH/WAIT/AVOID

    # Existing labels
    smart_money_signal: Optional[str] = None
    verdict: Optional[str] = None
    retail_non_flow_min: Optional[float] = None
    retail_non_flow_label: Optional[str] = None

    # FOMO filter
    max_fomo_risk: Optional[float] = None       # exclude FOMO traps

    # Sector RRG filter
    sector_rrg_quadrant: Optional[str] = None   # 'leading','improving','weakening','lagging'

    # Price
    price_min: Optional[float] = None
    price_max: Optional[float] = None

    # Sort
    sort_by: str = "opportunity_score"
    sort_desc: bool = True
    limit: int = 100


class ScreenerService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Main scan
    # ------------------------------------------------------------------ #

    def scan(self, f: ScreenerFilter) -> dict:
        # Apply analysis type defaults if user didn't override sort
        if f.analysis_type and f.analysis_type in ANALYSIS_TYPE_DEFAULTS:
            defaults = ANALYSIS_TYPE_DEFAULTS[f.analysis_type]
            if f.sort_by == "opportunity_score":  # i.e. user didn't pick custom
                f.sort_by = defaults["sort_by"]
                f.sort_desc = defaults["sort_desc"]

        latest_date = self.db.query(func.max(AIScore.date)).scalar()
        if not latest_date:
            return {"count": 0, "results": [], "as_of": None}

        # Build base query
        q = (
            self.db.query(AIScore, Symbol)
            .join(Symbol, Symbol.code == AIScore.symbol)
            .filter(AIScore.date == latest_date)
            .filter(Symbol.is_active == True)
        )

        # Universe filter
        q = self._apply_universe_filter(q, f)

        # Sector filter
        if f.sectors:
            q = q.filter(Symbol.sector.in_(f.sectors))
        elif f.sector:
            q = q.filter(Symbol.sector == f.sector)

        # Component score filters
        if f.opportunity_score_min is not None:
            q = q.filter(AIScore.opportunity_score >= f.opportunity_score_min)
        if f.opportunity_score_max is not None:
            q = q.filter(AIScore.opportunity_score <= f.opportunity_score_max)
        if f.star_rating_min is not None:
            q = q.filter(AIScore.star_rating >= f.star_rating_min)
        if f.accumulation_score_min is not None:
            q = q.filter(AIScore.accumulation_score >= f.accumulation_score_min)
        if f.distribution_score_max is not None:
            q = q.filter(AIScore.distribution_score <= f.distribution_score_max)
        if f.foreign_strength_min is not None:
            q = q.filter(AIScore.foreign_strength_score >= f.foreign_strength_min)
        if f.trend_score_min is not None:
            q = q.filter(AIScore.trend_score >= f.trend_score_min)
        if f.liquidity_score_min is not None:
            q = q.filter(AIScore.liquidity_score >= f.liquidity_score_min)
        if f.bandar_score_min is not None:
            q = q.filter(AIScore.bandar_score >= f.bandar_score_min)
        if f.bandar_score_max is not None:
            q = q.filter(AIScore.bandar_score <= f.bandar_score_max)
        if f.inventory_score_min is not None:
            q = q.filter(AIScore.inventory_score >= f.inventory_score_min)
        if f.momentum_score_min is not None:
            q = q.filter(AIScore.momentum_score >= f.momentum_score_min)
        if f.smart_money_signal:
            q = q.filter(AIScore.smart_money_signal == f.smart_money_signal)
        if f.verdict:
            q = q.filter(AIScore.verdict == f.verdict)
        if f.retail_non_flow_min is not None:
            q = q.filter(AIScore.retail_non_flow_score >= f.retail_non_flow_min)
        if f.retail_non_flow_label:
            q = q.filter(AIScore.retail_non_flow_label == f.retail_non_flow_label)
        if f.wyckoff_stages:
            q = q.filter(AIScore.wyckoff_stage.in_(f.wyckoff_stages))
        if f.trend_label:
            q = q.filter(AIScore.trend_label == f.trend_label)
        if f.trade_readiness_signal:
            q = q.filter(AIScore.trade_readiness_signal == f.trade_readiness_signal)
        if f.max_fomo_risk is not None:
            q = q.filter(AIScore.fomo_risk_score <= f.max_fomo_risk)
        if f.sector_rrg_quadrant:
            q = q.filter(AIScore.sector_rrg_quadrant == f.sector_rrg_quadrant)

        rows = q.all()
        if not rows:
            return {"count": 0, "results": [], "as_of": latest_date.isoformat()}

        symbols = [r.AIScore.symbol for r in rows]

        # Foreign net flow over period (for screener column)
        ff_start = latest_date - timedelta(days=f.foreign_net_days + 5)
        ff_q = (
            self.db.query(
                ForeignFlow.symbol,
                func.sum(ForeignFlow.foreign_net_value).label("foreign_net"),
            )
            .filter(
                ForeignFlow.symbol.in_(symbols),
                ForeignFlow.date > ff_start,
                ForeignFlow.date <= latest_date,
            )
            .group_by(ForeignFlow.symbol)
            .all()
        )
        foreign_map = {r.symbol: int(r.foreign_net or 0) for r in ff_q}

        # Latest candle + 20D avg volume
        candle_q = (
            self.db.query(Candle)
            .filter(
                Candle.symbol.in_(symbols),
                Candle.date > latest_date - timedelta(days=30),
                Candle.date <= latest_date,
            )
            .order_by(Candle.symbol, Candle.date)
            .all()
        )
        candle_df = pd.DataFrame([{
            "symbol": c.symbol, "date": c.date,
            "close": c.close, "volume": c.volume, "value": c.value,
            "open": c.open, "high": c.high, "low": c.low,
        } for c in candle_q])

        latest_candle = {}
        avg_volume_20d = {}
        prev_close = {}
        if not candle_df.empty:
            for sym, sub in candle_df.groupby("symbol"):
                sub = sub.sort_values("date")
                latest_candle[sym] = sub.iloc[-1].to_dict()
                avg_volume_20d[sym] = float(sub["volume"].tail(20).mean())
                if len(sub) >= 2:
                    prev_close[sym] = float(sub.iloc[-2]["close"])

        # Build result rows
        results = []
        for r in rows:
            sym = r.AIScore.symbol
            sym_meta = r.Symbol
            score = r.AIScore
            cdl = latest_candle.get(sym, {})
            avg_vol = avg_volume_20d.get(sym, 0)
            curr_vol = cdl.get("volume", 0) or 0
            volume_anomaly = curr_vol / avg_vol if avg_vol > 0 else 0
            close = cdl.get("close", 0) or 0
            pct_change = 0.0
            if prev_close.get(sym, 0) > 0:
                pct_change = (close / prev_close[sym] - 1) * 100
            foreign_net = foreign_map.get(sym, 0)

            # Apply remaining filters
            if f.foreign_net_min is not None and foreign_net < f.foreign_net_min:
                continue
            if f.volume_anomaly_min is not None and volume_anomaly < f.volume_anomaly_min:
                continue
            if f.price_min is not None and close < f.price_min:
                continue
            if f.price_max is not None and close > f.price_max:
                continue

            results.append({
                "symbol": sym,
                "name": sym_meta.name,
                "sector": sym_meta.sector,
                "is_lq45": sym_meta.is_lq45,
                "is_idx30": sym_meta.is_idx30,
                "is_kompas100": sym_meta.is_kompas100,
                "is_issi": sym_meta.is_issi,
                "close": close,
                "pct_change": round(pct_change, 2),
                "volume": int(curr_vol),
                "value": int(cdl.get("value", 0) or 0),
                "volume_anomaly": round(volume_anomaly, 2),
                "foreign_net": foreign_net,
                # Legacy scores
                "bandar_score": score.bandar_score,
                "foreign_score": score.foreign_score,
                "inventory_score": score.inventory_score,
                "volume_score": score.volume_score,
                "momentum_score": score.momentum_score,
                "consistency_score": score.consistency_score,
                "smart_money_signal": score.smart_money_signal,
                "behavior_label": score.behavior_label,
                "multi_tf_strength": score.multi_tf_strength,
                # Verdict
                "verdict": score.verdict or "ORANGE_X",
                "verdict_explanation": score.verdict_explanation or "",
                "slope_15d": score.slope_15d or 0,
                "r_squared_15d": score.r_squared_15d or 0,
                "consistency_pct": score.consistency_pct or 0,
                # Retail non-flow
                "retail_non_flow_score": score.retail_non_flow_score or 50,
                "retail_non_flow_label": score.retail_non_flow_label or "NEUTRAL",
                # V2 — Foreign multi-tf
                "foreign_strength_score": score.foreign_strength_score or 50,
                "foreign_net_5d": score.foreign_net_5d or 0,
                "foreign_net_10d": score.foreign_net_10d or 0,
                "foreign_net_20d": score.foreign_net_20d or 0,
                "foreign_net_60d": score.foreign_net_60d or 0,
                # V2 — Trend
                "trend_score": score.trend_score or 50,
                "trend_label": score.trend_label or "NEUTRAL",
                "above_ma20": score.above_ma20 or 0,
                "above_ma50": score.above_ma50 or 0,
                "above_ma200": score.above_ma200 or 0,
                # V2 — Liquidity
                "liquidity_score": score.liquidity_score or 50,
                "liquidity_label": score.liquidity_label or "MODERATE",
                "avg_value_20d": score.avg_value_20d or 0,
                # V2 — Accum/Distrib
                "accumulation_score": score.accumulation_score or 50,
                "distribution_score": score.distribution_score or 50,
                # V2 — Wyckoff
                "wyckoff_stage": score.wyckoff_stage or 1,
                "wyckoff_stage_label": score.wyckoff_stage_label or "ACCUMULATION",
                "breakout_quality_score": score.breakout_quality_score or 0,
                # V2 — Final composite
                "opportunity_score": score.opportunity_score or 0,
                "star_rating": score.star_rating or 0,
                "setup_label": score.setup_label or "IGNORE",
                # V2 — Trade readiness
                "trade_readiness_score": score.trade_readiness_score or 0,
                "trade_readiness_signal": score.trade_readiness_signal or "WAIT",
                "trade_readiness_reason": score.trade_readiness_reason or "",
                # V2 — FOMO
                "fomo_risk_score": score.fomo_risk_score or 0,
                "fomo_warning": score.fomo_warning,
                # V2 — Sector RRG
                "sector_rrg_quadrant": score.sector_rrg_quadrant,
                "sector_rs_ratio": score.sector_rs_ratio,
                "sector_rs_momentum": score.sector_rs_momentum,
            })

        # Sort & limit
        results.sort(
            key=lambda x: (x.get(f.sort_by) or 0),
            reverse=f.sort_desc,
        )
        results = results[:f.limit]

        return {
            "count": len(results),
            "as_of": latest_date.isoformat(),
            "filter": {k: v for k, v in f.__dict__.items() if v is not None and v != ""},
            "analysis_type": f.analysis_type,
            "results": results,
        }

    # ------------------------------------------------------------------ #
    # Universe filter
    # ------------------------------------------------------------------ #

    def _apply_universe_filter(self, q, f: ScreenerFilter):
        if not f.universe or f.universe.upper() == "ALL":
            return q
        u = f.universe.upper()
        if u == "LQ45":
            return q.filter(Symbol.is_lq45 == True)
        if u == "IDX30":
            return q.filter(Symbol.is_idx30 == True)
        if u == "KOMPAS100":
            return q.filter(Symbol.is_kompas100 == True)
        if u == "ISSI":
            return q.filter(Symbol.is_issi == True)
        if u == "WATCHLIST" and f.watchlist_id:
            wl = (
                self.db.query(Watchlist)
                .filter(Watchlist.id == f.watchlist_id)
                .first()
            )
            if wl and wl.symbols:
                return q.filter(Symbol.code.in_(wl.symbols))
        return q
