"""
Sector Activity & Rotation Service.

- Sector summary (capital flow, momentum, foreign flow)
- RRG (Relative Rotation Graph) with 4 quadrants:
  Leading / Improving / Weakening / Lagging
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Sector, Symbol, Candle, ForeignFlow, AIScore


class SectorService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Sector activity summary
    # ------------------------------------------------------------------ #

    def sector_activity(self, days: int = 5) -> list[dict]:
        """Per-sector aggregate flow + momentum."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        ago_date = end_date - timedelta(days=days * 4)  # baseline for rel strength

        # Sector → symbol map
        symbols = self.db.query(Symbol).all()
        sym_to_sector = {s.code: s.sector for s in symbols}
        sectors_meta = {s.code: s for s in self.db.query(Sector).all()}

        # Foreign flow per sector
        ff = (
            self.db.query(ForeignFlow)
            .filter(ForeignFlow.date >= start_date)
            .all()
        )
        ff_df = pd.DataFrame([{
            "symbol": r.symbol,
            "date": r.date,
            "net": r.foreign_net_value,
        } for r in ff])
        ff_df["sector"] = ff_df["symbol"].map(sym_to_sector)

        # Candles for momentum & value
        candles = (
            self.db.query(Candle)
            .filter(Candle.date >= ago_date)
            .all()
        )
        candle_df = pd.DataFrame([{
            "symbol": c.symbol, "date": c.date,
            "close": c.close, "value": c.value, "volume": c.volume,
        } for c in candles])
        candle_df["sector"] = candle_df["symbol"].map(sym_to_sector)

        # AI scores
        latest_score_date = self.db.query(func.max(AIScore.date)).scalar()
        scores = (
            self.db.query(AIScore)
            .filter(AIScore.date == latest_score_date)
            .all()
        )
        score_df = pd.DataFrame([{
            "symbol": s.symbol,
            "bandar": s.bandar_score,
            "momentum": s.momentum_score,
        } for s in scores])
        score_df["sector"] = score_df["symbol"].map(sym_to_sector)

        # Compute per sector
        result = []
        for sector_code, meta in sectors_meta.items():
            sec_symbols = [s.code for s in symbols if s.sector == sector_code]
            symbol_count = len(sec_symbols)

            # Foreign net flow
            sec_ff = ff_df[ff_df["sector"] == sector_code]
            foreign_net = int(sec_ff["net"].sum()) if not sec_ff.empty else 0
            foreign_net_5d = int(
                sec_ff[sec_ff["date"] >= end_date - timedelta(days=5)]["net"].sum()
            ) if not sec_ff.empty else 0

            # Total value traded
            sec_cdl = candle_df[candle_df["sector"] == sector_code]
            total_value = int(
                sec_cdl[sec_cdl["date"] >= start_date]["value"].sum()
            ) if not sec_cdl.empty else 0

            # Momentum: avg pct change of (latest close vs close `days` ago)
            momentum_pct = 0.0
            if not sec_cdl.empty:
                pct_changes = []
                for sym, sub in sec_cdl.groupby("symbol"):
                    sub = sub.sort_values("date")
                    if len(sub) >= days + 1:
                        old = sub.iloc[-min(days + 1, len(sub))]["close"]
                        new = sub.iloc[-1]["close"]
                        if old > 0:
                            pct_changes.append((new / old - 1) * 100)
                momentum_pct = float(np.mean(pct_changes)) if pct_changes else 0.0

            # Avg AI scores
            sec_scores = score_df[score_df["sector"] == sector_code]
            avg_bandar = float(sec_scores["bandar"].mean()) if not sec_scores.empty else 0
            avg_momentum_score = float(sec_scores["momentum"].mean()) if not sec_scores.empty else 0

            # Inflow / outflow classification
            if foreign_net > 0 and momentum_pct > 0:
                flow_label = "INFLOW_RISING"
            elif foreign_net > 0 and momentum_pct <= 0:
                flow_label = "INFLOW_BUILDING"  # absorbing weakness
            elif foreign_net < 0 and momentum_pct > 0:
                flow_label = "OUTFLOW_DEFYING"  # selling but price up
            else:
                flow_label = "OUTFLOW_DECLINING"

            result.append({
                "code": sector_code,
                "name": meta.name,
                "name_id": meta.name_id,
                "color": meta.color,
                "symbol_count": symbol_count,
                "total_value": total_value,
                "foreign_net": foreign_net,
                "foreign_net_5d": foreign_net_5d,
                "momentum_pct": round(momentum_pct, 2),
                "avg_bandar_score": round(avg_bandar, 1),
                "avg_momentum_score": round(avg_momentum_score, 1),
                "flow_label": flow_label,
            })

        # Rank
        result.sort(key=lambda x: x["foreign_net"], reverse=True)
        for i, r in enumerate(result, 1):
            r["rank"] = i

        return result

    # ------------------------------------------------------------------ #
    # RRG (Relative Rotation Graph)
    # ------------------------------------------------------------------ #

    def rrg(self, period_days: int = 30, benchmark: str = "IHSG") -> dict:
        """
        Compute RRG positions for sectors.

        RS-Ratio (x-axis):     relative strength of sector vs benchmark (100 = neutral)
        RS-Momentum (y-axis):  rate-of-change of RS-Ratio (100 = neutral)

        Quadrants:
            Leading   = (RS > 100, Mom > 100)  → strong & accelerating
            Weakening = (RS > 100, Mom < 100)  → strong but losing momentum
            Lagging   = (RS < 100, Mom < 100)  → weak & declining
            Improving = (RS < 100, Mom > 100)  → weak but accelerating
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days * 3)

        # Build IHSG proxy: market-wide value-weighted index
        candles = (
            self.db.query(Candle)
            .filter(Candle.date >= start_date)
            .all()
        )
        if not candles:
            return {"data": [], "as_of": None}

        candle_df = pd.DataFrame([{
            "symbol": c.symbol, "date": c.date,
            "close": c.close, "value": c.value,
        } for c in candles])

        symbols = self.db.query(Symbol).all()
        sym_to_sector = {s.code: s.sector for s in symbols}
        candle_df["sector"] = candle_df["symbol"].map(sym_to_sector)

        # Build daily index per sector (value-weighted average of close pct changes)
        # Simpler: build a sector index = weighted avg of close (rebased to 100 at start)
        sector_indices = {}
        for sector_code, sub in candle_df.groupby("sector"):
            daily = (
                sub.groupby("date")
                   .apply(lambda x: (x["close"] * x["value"]).sum() / max(x["value"].sum(), 1))
                   .sort_index()
            )
            if len(daily) < period_days + 5:
                continue
            rebased = daily / daily.iloc[0] * 100
            sector_indices[sector_code] = rebased

        # Build benchmark (IHSG proxy) = total market value-weighted
        benchmark_daily = (
            candle_df.groupby("date")
                     .apply(lambda x: (x["close"] * x["value"]).sum() / max(x["value"].sum(), 1))
                     .sort_index()
        )
        benchmark_rebased = benchmark_daily / benchmark_daily.iloc[0] * 100

        # Compute RS-Ratio per sector
        sectors_meta = {s.code: s for s in self.db.query(Sector).all()}

        rrg_data = []
        for sector_code, idx in sector_indices.items():
            # Align dates
            common = idx.index.intersection(benchmark_rebased.index)
            if len(common) < period_days + 5:
                continue
            idx_a = idx.loc[common]
            bench_a = benchmark_rebased.loc[common]

            rs_raw = idx_a / bench_a * 100
            # Smooth RS-Ratio (10-day SMA)
            rs_ratio = rs_raw.rolling(10, min_periods=1).mean()
            # Momentum = ROC of rs_ratio (10-day)
            rs_momentum = (rs_ratio / rs_ratio.shift(10) * 100).fillna(100)

            current_ratio = float(rs_ratio.iloc[-1])
            current_momentum = float(rs_momentum.iloc[-1])

            # Quadrant
            if current_ratio >= 100 and current_momentum >= 100:
                quadrant = "leading"
            elif current_ratio >= 100 and current_momentum < 100:
                quadrant = "weakening"
            elif current_ratio < 100 and current_momentum < 100:
                quadrant = "lagging"
            else:
                quadrant = "improving"

            # Tail: last 8 points
            tail = []
            for i in range(min(8, len(rs_ratio))):
                ix = -8 + i
                if abs(ix) <= len(rs_ratio):
                    tail.append([
                        round(float(rs_ratio.iloc[ix]), 2),
                        round(float(rs_momentum.iloc[ix]), 2),
                    ])

            meta = sectors_meta.get(sector_code)
            rrg_data.append({
                "code": sector_code,
                "name": meta.name if meta else sector_code,
                "color": meta.color if meta else "#888",
                "rs_ratio": round(current_ratio, 2),
                "rs_momentum": round(current_momentum, 2),
                "quadrant": quadrant,
                "tail": tail,
            })

        return {
            "as_of": end_date.isoformat(),
            "period_days": period_days,
            "benchmark": benchmark,
            "data": rrg_data,
        }

    # ------------------------------------------------------------------ #
    # Heatmap (market-wide grid of all symbols)
    # ------------------------------------------------------------------ #

    def heatmap(self) -> list[dict]:
        """Latest-day heatmap: symbol × pct_change × value × sector."""
        latest_date = self.db.query(func.max(Candle.date)).scalar()
        if not latest_date:
            return []
        prev_date = self.db.query(func.max(Candle.date))\
            .filter(Candle.date < latest_date).scalar()

        symbols = {s.code: s for s in self.db.query(Symbol).all()}
        scores = {
            s.symbol: s for s in
            self.db.query(AIScore).filter(AIScore.date == latest_date).all()
        }

        # Latest + previous candle
        latest = {c.symbol: c for c in self.db.query(Candle).filter(Candle.date == latest_date).all()}
        prev = {c.symbol: c for c in self.db.query(Candle).filter(Candle.date == prev_date).all()}

        result = []
        for sym, c in latest.items():
            p = prev.get(sym)
            pct = 0.0
            if p and p.close > 0:
                pct = (c.close / p.close - 1) * 100
            score = scores.get(sym)
            sym_meta = symbols.get(sym)
            result.append({
                "symbol": sym,
                "name": sym_meta.name if sym_meta else sym,
                "sector": sym_meta.sector if sym_meta else "OTHER",
                "close": c.close,
                "pct_change": round(pct, 2),
                "value": c.value,
                "volume": c.volume,
                "bandar_score": score.bandar_score if score else 0,
                "smart_money_signal": score.smart_money_signal if score else "neutral",
            })
        return result
