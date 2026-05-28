"""
Market Summary Screener Service.

Composite-score-based screening over the symbol universe.
Filters on:
- BandarScore (composite)
- Foreign net flow
- Inventory accumulation
- Volume anomaly
- Momentum
- Sector
- Multi-timeframe strength
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AIScore, Symbol, ForeignFlow, Candle, BrokerDailySummary, Broker,
)


@dataclass
class ScreenerFilter:
    bandar_score_min: Optional[float] = None
    bandar_score_max: Optional[float] = None
    foreign_net_min: Optional[float] = None        # IDR over `foreign_net_days`
    foreign_net_days: int = 20
    inventory_score_min: Optional[float] = None
    momentum_score_min: Optional[float] = None
    volume_anomaly_min: Optional[float] = None     # e.g. 1.5 = 1.5x avg
    smart_money_signal: Optional[str] = None       # 'accumulation','distribution','neutral'
    sector: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    # NEW: verdict + retail non-flow
    verdict: Optional[str] = None                  # 'GREEN_CHECK','ORANGE_X','RED_MINUS'
    retail_non_flow_min: Optional[float] = None    # 0-100
    retail_non_flow_label: Optional[str] = None    # 'POSITIVE_NONFLOW',...
    sort_by: str = "bandar_score"
    sort_desc: bool = True
    limit: int = 50


class ScreenerService:

    def __init__(self, db: Session):
        self.db = db

    def scan(self, f: ScreenerFilter) -> dict:
        """Run screener and return enriched rows."""

        # Step 1: latest score per symbol (latest date)
        latest_date = self.db.query(func.max(AIScore.date)).scalar()
        if not latest_date:
            return {"count": 0, "results": [], "as_of": None}

        scores_q = (
            self.db.query(AIScore, Symbol)
            .join(Symbol, Symbol.code == AIScore.symbol)
            .filter(AIScore.date == latest_date)
        )

        if f.sector:
            scores_q = scores_q.filter(Symbol.sector == f.sector)
        if f.bandar_score_min is not None:
            scores_q = scores_q.filter(AIScore.bandar_score >= f.bandar_score_min)
        if f.bandar_score_max is not None:
            scores_q = scores_q.filter(AIScore.bandar_score <= f.bandar_score_max)
        if f.inventory_score_min is not None:
            scores_q = scores_q.filter(AIScore.inventory_score >= f.inventory_score_min)
        if f.momentum_score_min is not None:
            scores_q = scores_q.filter(AIScore.momentum_score >= f.momentum_score_min)
        if f.smart_money_signal:
            scores_q = scores_q.filter(AIScore.smart_money_signal == f.smart_money_signal)
        if f.verdict:
            scores_q = scores_q.filter(AIScore.verdict == f.verdict)
        if f.retail_non_flow_min is not None:
            scores_q = scores_q.filter(AIScore.retail_non_flow_score >= f.retail_non_flow_min)
        if f.retail_non_flow_label:
            scores_q = scores_q.filter(AIScore.retail_non_flow_label == f.retail_non_flow_label)

        rows = scores_q.all()
        if not rows:
            return {"count": 0, "results": [], "as_of": latest_date.isoformat()}

        symbols = [r.AIScore.symbol for r in rows]

        # Step 2: foreign net flow over period
        ff_start = latest_date - timedelta(days=f.foreign_net_days)
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

        # Step 3: latest candle + 20D average volume
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
        } for c in candle_q])

        latest_candle = {}
        avg_volume_20d = {}
        if not candle_df.empty:
            for sym, sub in candle_df.groupby("symbol"):
                sub = sub.sort_values("date")
                latest_candle[sym] = sub.iloc[-1].to_dict()
                avg_volume_20d[sym] = float(sub["volume"].tail(20).mean())

        # Step 4: build result rows
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
                "close": close,
                "volume": int(curr_vol),
                "value": int(cdl.get("value", 0) or 0),
                "volume_anomaly": round(volume_anomaly, 2),
                "foreign_net": foreign_net,
                "bandar_score": score.bandar_score,
                "foreign_score": score.foreign_score,
                "inventory_score": score.inventory_score,
                "volume_score": score.volume_score,
                "momentum_score": score.momentum_score,
                "consistency_score": score.consistency_score,
                "smart_money_signal": score.smart_money_signal,
                "behavior_label": score.behavior_label,
                "multi_tf_strength": score.multi_tf_strength,
                # NEW: verdict + retail non-flow
                "verdict": score.verdict or "ORANGE_X",
                "verdict_explanation": score.verdict_explanation or "",
                "slope_15d": score.slope_15d or 0,
                "r_squared_15d": score.r_squared_15d or 0,
                "consistency_pct": score.consistency_pct or 0,
                "retail_non_flow_score": score.retail_non_flow_score or 50,
                "retail_non_flow_label": score.retail_non_flow_label or "NEUTRAL",
            })

        # Step 5: sort & limit
        sort_key = f.sort_by
        results.sort(
            key=lambda x: (x.get(sort_key) or 0),
            reverse=f.sort_desc,
        )
        results = results[: f.limit]

        return {
            "count": len(results),
            "as_of": latest_date.isoformat(),
            "filter": f.__dict__,
            "results": results,
        }
