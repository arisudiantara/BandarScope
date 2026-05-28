"""
Yearly Smart Money Heatmap.

Generates monthly aggregates per symbol for the last N months (default 12)
showing smart money behavior across time.

Two views:

1. Per-symbol:
   - Rows = months (Jan, Feb, ..., Dec)
   - Cols = metrics (price_return, foreign_net, bandar_net_lot, retail_net_lot,
                     volume_anomaly, behavior_score)
   - Identifies seasonal patterns: "MEDC paling sering akumulasi di Q1"

2. Universe-wide (cross-section):
   - Rows = symbols (top N by activity)
   - Cols = months
   - Cell value = behavior_score (-100 distribution → +100 accumulation)
   - Visualize which stocks bandar are rotating into / out of each month
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Candle, ForeignFlow, BrokerDailySummary, Symbol, Broker,
)


# Behavior score mapping
def _behavior_to_score(score: float) -> str:
    if score >= 60:   return "STRONG_ACCUM"
    if score >= 25:   return "ACCUMULATION"
    if score >= -25:  return "NEUTRAL"
    if score >= -60:  return "DISTRIBUTION"
    return "STRONG_DIST"


class YearlyHeatmapService:

    def __init__(self, db: Session):
        self.db = db
        brokers = self.db.query(Broker).all()
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }
        self.retail_set = {b.code for b in brokers if b.cluster_label == "retail"}

    # ------------------------------------------------------------------ #
    # Per-symbol monthly heatmap
    # ------------------------------------------------------------------ #

    def per_symbol(self, symbol: str, months: int = 12) -> dict:
        """Monthly aggregates for a single symbol."""
        end_date = self.db.query(func.max(Candle.date)).scalar()
        if not end_date:
            return {"symbol": symbol, "months": []}

        start_date = end_date - timedelta(days=months * 31 + 5)

        candles = (
            self.db.query(Candle)
            .filter(
                Candle.symbol == symbol,
                Candle.date >= start_date,
                Candle.date <= end_date,
            )
            .order_by(Candle.date)
            .all()
        )
        if not candles:
            return {"symbol": symbol, "months": []}

        cdf = pd.DataFrame([{
            "date": c.date, "close": c.close, "volume": c.volume, "value": c.value,
        } for c in candles])
        cdf["date"] = pd.to_datetime(cdf["date"])
        cdf["ym"] = cdf["date"].dt.to_period("M")

        # Foreign
        ff = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol == symbol,
                ForeignFlow.date >= start_date,
                ForeignFlow.date <= end_date,
            )
            .all()
        )
        ffdf = pd.DataFrame([{
            "date": f.date, "net": f.foreign_net_value,
        } for f in ff])
        if not ffdf.empty:
            ffdf["date"] = pd.to_datetime(ffdf["date"])
            ffdf["ym"] = ffdf["date"].dt.to_period("M")

        # Brokers
        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "broker": r.broker_code,
            "net_lot": r.net_lot, "net_value": r.net_value,
        } for r in bds])
        if not bdf.empty:
            bdf["date"] = pd.to_datetime(bdf["date"])
            bdf["ym"] = bdf["date"].dt.to_period("M")

        # Aggregate per month
        monthly_agg = cdf.groupby("ym").agg(
            month_start=("date", "min"),
            month_end=("date", "max"),
            open_close=("close", "first"),
            close_close=("close", "last"),
            high=("close", "max"),
            low=("close", "min"),
            avg_volume=("volume", "mean"),
            total_value=("value", "sum"),
            trading_days=("close", "count"),
        ).reset_index()

        monthly_agg["price_return_pct"] = (
            (monthly_agg["close_close"] / monthly_agg["open_close"] - 1) * 100
        ).round(2)

        # Foreign net per month
        if not ffdf.empty:
            ff_monthly = ffdf.groupby("ym")["net"].sum().reset_index()
            ff_monthly.columns = ["ym", "foreign_net"]
            monthly_agg = monthly_agg.merge(ff_monthly, on="ym", how="left")
        else:
            monthly_agg["foreign_net"] = 0
        monthly_agg["foreign_net"] = monthly_agg["foreign_net"].fillna(0).astype(int)

        # Bandar / retail net lot per month
        if not bdf.empty:
            bandar_lot = (
                bdf[bdf["broker"].isin(self.bandar_set)]
                .groupby("ym")["net_lot"].sum().reset_index()
            )
            bandar_lot.columns = ["ym", "bandar_net_lot"]
            retail_lot = (
                bdf[bdf["broker"].isin(self.retail_set)]
                .groupby("ym")["net_lot"].sum().reset_index()
            )
            retail_lot.columns = ["ym", "retail_net_lot"]
            monthly_agg = monthly_agg.merge(bandar_lot, on="ym", how="left")
            monthly_agg = monthly_agg.merge(retail_lot, on="ym", how="left")
        else:
            monthly_agg["bandar_net_lot"] = 0
            monthly_agg["retail_net_lot"] = 0
        monthly_agg[["bandar_net_lot", "retail_net_lot"]] = (
            monthly_agg[["bandar_net_lot", "retail_net_lot"]].fillna(0).astype(int)
        )

        # Compute monthly behavior score (-100 to +100)
        monthly_agg["behavior_score"] = monthly_agg.apply(
            lambda r: self._behavior_score(r), axis=1
        ).round(1)
        monthly_agg["behavior_label"] = monthly_agg["behavior_score"].apply(
            _behavior_to_score
        )

        # Take last N months
        monthly_agg = monthly_agg.tail(months).copy()
        monthly_agg["ym_str"] = monthly_agg["ym"].astype(str)

        result = []
        for _, row in monthly_agg.iterrows():
            result.append({
                "month": row["ym_str"],
                "trading_days": int(row["trading_days"]),
                "open": float(row["open_close"]),
                "close": float(row["close_close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "price_return_pct": float(row["price_return_pct"]),
                "avg_volume": int(row["avg_volume"]),
                "total_value": int(row["total_value"]),
                "foreign_net": int(row["foreign_net"]),
                "bandar_net_lot": int(row["bandar_net_lot"]),
                "retail_net_lot": int(row["retail_net_lot"]),
                "behavior_score": float(row["behavior_score"]),
                "behavior_label": row["behavior_label"],
            })

        # Compute summary stats
        summary = self._summarize_monthly(result)

        return {
            "symbol": symbol,
            "months": result,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    # Universe-wide cross-section
    # ------------------------------------------------------------------ #

    def universe_cross_section(
        self,
        months: int = 12,
        top_n: int = 30,
    ) -> dict:
        """
        Behavior matrix: rows=symbols, cols=months, value=behavior_score.
        Top N selected by total absolute behavior over period.
        """
        end_date = self.db.query(func.max(Candle.date)).scalar()
        if not end_date:
            return {"matrix": [], "months": []}

        start_date = end_date - timedelta(days=months * 31 + 5)

        # Pull all data once
        symbols = [s.code for s in self.db.query(Symbol).filter(Symbol.is_active == True).all()]

        # Candles
        c_rows = (
            self.db.query(Candle)
            .filter(
                Candle.date >= start_date,
                Candle.date <= end_date,
            )
            .all()
        )
        cdf = pd.DataFrame([{
            "date": c.date, "symbol": c.symbol, "close": c.close,
            "volume": c.volume,
        } for c in c_rows])
        if cdf.empty:
            return {"matrix": [], "months": []}
        cdf["date"] = pd.to_datetime(cdf["date"])
        cdf["ym"] = cdf["date"].dt.to_period("M")

        # Foreign
        ff_rows = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.date >= start_date,
                ForeignFlow.date <= end_date,
            )
            .all()
        )
        ffdf = pd.DataFrame([{
            "date": f.date, "symbol": f.symbol, "net": f.foreign_net_value,
        } for f in ff_rows])
        if not ffdf.empty:
            ffdf["date"] = pd.to_datetime(ffdf["date"])
            ffdf["ym"] = ffdf["date"].dt.to_period("M")

        # Brokers (only bandar)
        bds_rows = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
                BrokerDailySummary.broker_code.in_(self.bandar_set),
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol, "net_lot": r.net_lot,
        } for r in bds_rows])
        if not bdf.empty:
            bdf["date"] = pd.to_datetime(bdf["date"])
            bdf["ym"] = bdf["date"].dt.to_period("M")

        # Aggregate per (symbol, ym)
        price_agg = cdf.groupby(["symbol", "ym"]).agg(
            open_close=("close", "first"),
            close_close=("close", "last"),
            avg_volume=("volume", "mean"),
        ).reset_index()
        price_agg["price_return_pct"] = (
            (price_agg["close_close"] / price_agg["open_close"] - 1) * 100
        )

        if not ffdf.empty:
            ff_agg = ffdf.groupby(["symbol", "ym"])["net"].sum().reset_index()
            ff_agg.columns = ["symbol", "ym", "foreign_net"]
            price_agg = price_agg.merge(ff_agg, on=["symbol", "ym"], how="left")
        else:
            price_agg["foreign_net"] = 0
        price_agg["foreign_net"] = price_agg["foreign_net"].fillna(0)

        if not bdf.empty:
            b_agg = bdf.groupby(["symbol", "ym"])["net_lot"].sum().reset_index()
            b_agg.columns = ["symbol", "ym", "bandar_net_lot"]
            price_agg = price_agg.merge(b_agg, on=["symbol", "ym"], how="left")
        else:
            price_agg["bandar_net_lot"] = 0
        price_agg["bandar_net_lot"] = price_agg["bandar_net_lot"].fillna(0)

        # Compute behavior score per (symbol, ym)
        price_agg["behavior_score"] = price_agg.apply(
            lambda r: self._behavior_score(r), axis=1
        ).round(1)

        # Get list of months sorted
        all_months = sorted(price_agg["ym"].unique())[-months:]
        month_strs = [str(m) for m in all_months]

        # Filter to those months
        filtered = price_agg[price_agg["ym"].isin(all_months)].copy()
        filtered["ym_str"] = filtered["ym"].astype(str)

        # Pivot: rows=symbol, cols=month_str
        pivot = filtered.pivot_table(
            index="symbol",
            columns="ym_str",
            values="behavior_score",
            aggfunc="first",
            fill_value=0,
        )

        # Rank symbols by total absolute behavior (most active)
        pivot["__abs_total"] = pivot.abs().sum(axis=1)
        pivot = pivot.sort_values("__abs_total", ascending=False).head(top_n)
        pivot = pivot.drop(columns="__abs_total")

        # Get symbol metadata
        sym_meta = {
            s.code: {"name": s.name, "sector": s.sector}
            for s in self.db.query(Symbol).filter(Symbol.code.in_(pivot.index)).all()
        }

        # Build matrix output
        matrix = []
        for sym in pivot.index:
            cells = []
            for m in month_strs:
                if m in pivot.columns:
                    cells.append({
                        "month": m,
                        "score": float(pivot.loc[sym, m]),
                        "label": _behavior_to_score(float(pivot.loc[sym, m])),
                    })
                else:
                    cells.append({"month": m, "score": 0, "label": "NEUTRAL"})

            meta = sym_meta.get(sym, {})
            matrix.append({
                "symbol": sym,
                "name": meta.get("name", sym),
                "sector": meta.get("sector"),
                "cells": cells,
                "avg_score": round(float(np.mean([c["score"] for c in cells])), 1),
            })

        return {
            "months": month_strs,
            "month_count": len(month_strs),
            "symbol_count": len(matrix),
            "matrix": matrix,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _behavior_score(row) -> float:
        """
        Compute behavior score from monthly aggregates.

        Score = weighted blend of:
        - foreign_net direction (35%)
        - bandar_net_lot direction (35%)
        - price_return_pct (30%, but capped)

        Returns -100..+100 where:
            +60+: strong accumulation (smart money buying + price rising)
            +25..+60: moderate accumulation
            -25..+25: neutral
            -60..-25: moderate distribution
            -100..-60: strong distribution
        """
        # Normalize foreign_net relative to typical magnitude
        # (just sign weight here, 50pts toward each direction)
        foreign_net = row.get("foreign_net", 0)
        bandar_lot = row.get("bandar_net_lot", 0)
        price_ret = row.get("price_return_pct", 0)

        # Convert raw values to -1..+1 signals
        # (rough magnitude-based, not perfectly normalized — sufficient for relative ranking)
        f_sig = np.tanh(foreign_net / 5e10) if foreign_net != 0 else 0
        b_sig = np.tanh(bandar_lot / 50000) if bandar_lot != 0 else 0
        p_sig = np.tanh(price_ret / 10)  # 10% return → ~+0.76

        score = (f_sig * 35) + (b_sig * 35) + (p_sig * 30)
        return float(np.clip(score, -100, 100))

    @staticmethod
    def _summarize_monthly(months: list[dict]) -> dict:
        """Build summary stats from per-symbol monthly data."""
        if not months:
            return {}

        scores = [m["behavior_score"] for m in months]
        accum_months = [m for m in months if m["behavior_score"] > 25]
        dist_months = [m for m in months if m["behavior_score"] < -25]

        # Best & worst month
        best = max(months, key=lambda m: m["behavior_score"])
        worst = min(months, key=lambda m: m["behavior_score"])

        # Streak detection
        current_streak = YearlyHeatmapService._compute_streak(months)

        # Foreign cumulative
        cum_foreign = sum(m["foreign_net"] for m in months)
        cum_bandar = sum(m["bandar_net_lot"] for m in months)

        return {
            "avg_behavior_score": round(float(np.mean(scores)), 1),
            "accumulation_months": len(accum_months),
            "distribution_months": len(dist_months),
            "best_month": {
                "month": best["month"],
                "score": best["behavior_score"],
                "label": best["behavior_label"],
            },
            "worst_month": {
                "month": worst["month"],
                "score": worst["behavior_score"],
                "label": worst["behavior_label"],
            },
            "current_streak": current_streak,
            "cumulative_foreign_net": int(cum_foreign),
            "cumulative_bandar_lot": int(cum_bandar),
        }

    @staticmethod
    def _compute_streak(months: list[dict]) -> dict:
        """Find current consecutive streak of accumulation/distribution."""
        if not months:
            return {"type": "NONE", "length": 0}

        latest = months[-1]
        if latest["behavior_score"] > 25:
            target_type = "ACCUMULATION"
            check = lambda s: s > 25
        elif latest["behavior_score"] < -25:
            target_type = "DISTRIBUTION"
            check = lambda s: s < -25
        else:
            return {"type": "NEUTRAL", "length": 0}

        length = 0
        for m in reversed(months):
            if check(m["behavior_score"]):
                length += 1
            else:
                break

        return {"type": target_type, "length": length}
