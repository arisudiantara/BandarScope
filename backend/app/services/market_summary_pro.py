"""
Market Summary Pro — institutional-grade money flow grid.

Generates a heatmap-style table where each row is a stock and each cell is a
normalized money-flow score for a specific period (last 6 days dn-5..dn-0
and last 6 weeks wn-5..wn-0).

8 Analysis Methods supported, each with its own formula engine:
1. non_retail_flow         — inverted retail flow (smart money kontrarian)
2. foreign_flow            — foreign net flow normalized
3. broker_accumulation     — institutional broker net lot
4. smart_money             — composite (foreign + bandar)
5. sector_rotation         — relative sector flow
6. relative_strength       — return vs IHSG
7. momentum                — price ROC
8. composite_score         — opportunity score per period

Normalization options:
- raw                      — actual values
- normalized               — clipped -100..+100
- z_score                  — across universe per period
- percentile               — rank within universe
- relative_strength        — vs IHSG benchmark

Plus:
- 5 MA flags (above MA5/10/20/50/100/200) with pct distance
- 6 component scores (accum/distrib/momentum/trend/liquidity/instit)
- Smart money signals (Hidden Accum, Vol Expansion, Distribution Warning, etc)
- Probability Score (proprietary 0-100)
- Noise Reduction System with explanation per rejection
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional, Literal

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Candle, ForeignFlow, BrokerDailySummary, Broker, Symbol, AIScore, Watchlist,
)


# ============================================================
# Constants
# ============================================================

ANALYSIS_METHODS = [
    "non_retail_flow",
    "foreign_flow",
    "broker_accumulation",
    "smart_money",
    "sector_rotation",
    "relative_strength",
    "momentum",
    "composite_score",
]

NORMALIZATION_METHODS = [
    "raw", "normalized", "z_score", "percentile", "relative_strength",
]

PERIODS = ["daily", "weekly", "monthly", "quarterly", "yearly", "cumulative"]

UNIVERSE_FILTERS = [
    "ALL", "WATCHLIST", "COMPOSITE", "LQ45", "IDX30", "KOMPAS100", "ISSI", "JII70",
    "IDXENERGY", "IDXBASIC", "IDXINDUST", "IDXCYCLIC", "IDXNONCYC", "IDXHEALTH",
    "IDXFINANCE", "IDXPROPERTY", "IDXTECHNO", "IDXINFRA", "IDXTRANS",
]

PROBABILITY_TIERS = [
    (90, 100, "INSTITUTIONAL_ACCUMULATION", "Institutional Accumulation"),
    (80,  90, "STRONG_OPPORTUNITY", "Strong Opportunity"),
    (70,  80, "WATCHLIST", "Watchlist"),
    (60,  70, "NEUTRAL", "Neutral"),
    (0,   60, "AVOID", "Avoid"),
]


@dataclass
class MarketSummaryFilter:
    universe: str = "ALL"
    watchlist_id: Optional[str] = None
    analysis_method: str = "smart_money"
    period: str = "daily"
    normalization: str = "normalized"

    # Filter thresholds
    min_accumulation: Optional[float] = None
    min_foreign_flow: Optional[float] = None
    min_volume_spike: Optional[float] = None
    min_momentum: Optional[float] = None
    min_liquidity: Optional[float] = None
    min_trend: Optional[float] = None
    min_probability: Optional[float] = None

    # MA filters
    require_above_ma5: Optional[bool] = None
    require_above_ma20: Optional[bool] = None
    require_above_ma50: Optional[bool] = None
    require_above_ma200: Optional[bool] = None

    # Noise reduction
    apply_noise_filter: bool = True
    show_rejected: bool = False

    # Sort & limit
    sort_by: str = "probability_score"
    sort_desc: bool = True
    limit: int = 200


# ============================================================
# Service
# ============================================================

class MarketSummaryProService:

    def __init__(self, db: Session):
        self.db = db
        brokers = self.db.query(Broker).all()
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }
        self.retail_set = {b.code for b in brokers if b.cluster_label == "retail"}
        self.foreign_broker_set = {b.code for b in brokers if b.is_foreign}

    # ------------------------------------------------------------------ #
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------ #

    def scan(self, f: MarketSummaryFilter) -> dict:
        latest_date = self.db.query(func.max(Candle.date)).scalar()
        if not latest_date:
            return {"error": "No data"}

        # ── Step 1: Resolve universe symbols ──────────────────────────
        symbols_meta = self._resolve_universe(f)
        if not symbols_meta:
            return {"error": f"Empty universe: {f.universe}"}
        symbol_codes = [s.code for s in symbols_meta]

        # ── Step 2: Bulk-fetch raw data ───────────────────────────────
        # Need enough lookback for weekly aggregation (6 weeks ~ 30 trading days)
        load_days = 250  # ~12 months
        load_start = latest_date - timedelta(days=load_days)

        raw = self._bulk_fetch(symbol_codes, load_start, latest_date)
        if raw["candles"].empty:
            return {"rows": [], "as_of": latest_date.isoformat()}

        # ── Step 3: Compute IHSG benchmark series ─────────────────────
        ihsg_daily, ihsg_weekly = self._build_benchmark(raw["candles"])

        # ── Step 4: Build per-symbol data dict ────────────────────────
        # Compute all metrics per symbol
        rows_raw = []
        for sym in symbol_codes:
            row = self._build_row(
                sym=sym,
                meta=next((s for s in symbols_meta if s.code == sym), None),
                raw=raw,
                ihsg_daily=ihsg_daily,
                ihsg_weekly=ihsg_weekly,
                analysis_method=f.analysis_method,
                target_date=latest_date,
            )
            if row is not None:
                rows_raw.append(row)

        # ── Step 5: Apply normalization across the universe ───────────
        rows_raw = self._apply_normalization(rows_raw, f.normalization)

        # ── Step 6: Compute Probability Score per row ─────────────────
        for row in rows_raw:
            self._compute_probability(row)

        # ── Step 7: Smart money signals & Noise flags ─────────────────
        for row in rows_raw:
            self._compute_signals(row)
            self._compute_noise_flags(row)

        # ── Step 8: Apply user filters ────────────────────────────────
        accepted, rejected = self._apply_user_filters(rows_raw, f)

        # ── Step 9: Sort & limit ──────────────────────────────────────
        sort_key = f.sort_by
        accepted.sort(
            key=lambda x: (x.get(sort_key) or 0),
            reverse=f.sort_desc,
        )
        accepted = accepted[: f.limit]

        # ── Step 10: Build summary ────────────────────────────────────
        summary = self._build_summary(accepted, rejected)

        result = {
            "as_of": latest_date.isoformat(),
            "analysis_method": f.analysis_method,
            "period": f.period,
            "normalization": f.normalization,
            "universe": f.universe,
            "rows": accepted,
            "summary": summary,
        }
        if f.show_rejected:
            result["rejected"] = rejected[:50]
        return result

    # ------------------------------------------------------------------ #
    # Universe resolver
    # ------------------------------------------------------------------ #

    def _resolve_universe(self, f: MarketSummaryFilter) -> list[Symbol]:
        u = (f.universe or "ALL").upper()
        q = self.db.query(Symbol).filter(Symbol.is_active == True)

        if u == "WATCHLIST" and f.watchlist_id:
            wl = self.db.query(Watchlist).filter(Watchlist.id == f.watchlist_id).first()
            if wl and wl.symbols:
                q = q.filter(Symbol.code.in_(wl.symbols))
        elif u == "LQ45":
            q = q.filter(Symbol.is_lq45 == True)
        elif u == "IDX30":
            q = q.filter(Symbol.is_idx30 == True)
        elif u == "KOMPAS100":
            q = q.filter(Symbol.is_kompas100 == True)
        elif u == "ISSI":
            q = q.filter(Symbol.is_issi == True)
        elif u == "JII70":
            q = q.filter(Symbol.is_jii70 == True)
        elif u == "COMPOSITE":
            q = q.filter(Symbol.is_composite == True)
        elif u == "IDXENERGY":     q = q.filter(Symbol.is_idxenergy == True)
        elif u == "IDXBASIC":      q = q.filter(Symbol.is_idxbasic == True)
        elif u == "IDXINDUST":     q = q.filter(Symbol.is_idxindust == True)
        elif u == "IDXCYCLIC":     q = q.filter(Symbol.is_idxcyclic == True)
        elif u == "IDXNONCYC":     q = q.filter(Symbol.is_idxnoncyc == True)
        elif u == "IDXHEALTH":     q = q.filter(Symbol.is_idxhealth == True)
        elif u == "IDXFINANCE":    q = q.filter(Symbol.is_idxfinance == True)
        elif u == "IDXPROPERTY":   q = q.filter(Symbol.is_idxproperty == True)
        elif u == "IDXTECHNO":     q = q.filter(Symbol.is_idxtechno == True)
        elif u == "IDXINFRA":      q = q.filter(Symbol.is_idxinfra == True)
        elif u == "IDXTRANS":      q = q.filter(Symbol.is_idxtrans == True)
        # ALL = no filter

        return q.all()

    # ------------------------------------------------------------------ #
    # Bulk data fetcher
    # ------------------------------------------------------------------ #

    def _bulk_fetch(self, symbols: list[str], start: date, end: date) -> dict:
        candles = (
            self.db.query(Candle)
            .filter(
                Candle.symbol.in_(symbols),
                Candle.date >= start,
                Candle.date <= end,
            )
            .all()
        )
        cdf = pd.DataFrame([{
            "symbol": c.symbol, "date": c.date,
            "open": c.open, "high": c.high, "low": c.low, "close": c.close,
            "volume": c.volume, "value": c.value,
        } for c in candles])

        ff = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol.in_(symbols),
                ForeignFlow.date >= start,
                ForeignFlow.date <= end,
            )
            .all()
        )
        ffdf = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol,
            "net": r.foreign_net_value,
        } for r in ff])

        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol.in_(symbols),
                BrokerDailySummary.date >= start,
                BrokerDailySummary.date <= end,
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol, "broker": r.broker_code,
            "net_lot": r.net_lot, "net_value": r.net_value,
            "buy_value": r.buy_value, "sell_value": r.sell_value,
        } for r in bds])

        # Latest scores cache for reuse
        scores = (
            self.db.query(AIScore)
            .filter(AIScore.symbol.in_(symbols), AIScore.date == end)
            .all()
        )
        scores_map = {s.symbol: s for s in scores}

        return {
            "candles": cdf,
            "foreign": ffdf,
            "brokers": bdf,
            "scores": scores_map,
        }

    # ------------------------------------------------------------------ #
    # Benchmark builder
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_benchmark(cdf: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """IHSG proxy = value-weighted average close across universe."""
        if cdf.empty:
            return pd.Series(dtype=float), pd.Series(dtype=float)
        daily = (
            cdf.groupby("date")
               .apply(lambda x: (x["close"] * x["value"]).sum() / max(x["value"].sum(), 1))
               .sort_index()
        )
        # Weekly resample
        ts = pd.to_datetime(daily.index)
        daily.index = ts
        weekly = daily.resample("W-FRI").last().dropna()
        return daily, weekly

    # ------------------------------------------------------------------ #
    # Per-row builder
    # ------------------------------------------------------------------ #

    def _build_row(
        self,
        sym: str,
        meta: Optional[Symbol],
        raw: dict,
        ihsg_daily: pd.Series,
        ihsg_weekly: pd.Series,
        analysis_method: str,
        target_date: date,
    ) -> Optional[dict]:
        # Per-symbol slices
        cdf = raw["candles"][raw["candles"]["symbol"] == sym].sort_values("date")
        if len(cdf) < 6:
            return None
        ffdf = (raw["foreign"][raw["foreign"]["symbol"] == sym].sort_values("date")
                if not raw["foreign"].empty else pd.DataFrame())
        bdf = (raw["brokers"][raw["brokers"]["symbol"] == sym].sort_values("date")
               if not raw["brokers"].empty else pd.DataFrame())

        cdf = cdf.copy()
        cdf["date"] = pd.to_datetime(cdf["date"])
        cdf = cdf.set_index("date")

        latest = cdf.iloc[-1]

        # ── Daily flow series (last 6 trading days, dn-5..dn-0) ──
        daily_flow = self._compute_period_flow(
            cdf=cdf, ffdf=ffdf, bdf=bdf,
            ihsg=ihsg_daily, period_index=cdf.index,
            n_periods=6, analysis_method=analysis_method,
            granularity="daily",
        )

        # ── Weekly flow series (last 6 weeks, wn-5..wn-0) ──
        weekly_index = self._weekly_index(cdf.index)
        weekly_flow = self._compute_period_flow(
            cdf=cdf, ffdf=ffdf, bdf=bdf,
            ihsg=ihsg_weekly, period_index=weekly_index,
            n_periods=6, analysis_method=analysis_method,
            granularity="weekly",
        )

        # ── MA flags ──
        close_series = cdf["close"]
        ma5  = close_series.rolling(5,   min_periods=2).mean().iloc[-1]
        ma10 = close_series.rolling(10,  min_periods=3).mean().iloc[-1]
        ma20 = close_series.rolling(20,  min_periods=5).mean().iloc[-1]
        ma50 = close_series.rolling(50,  min_periods=10).mean().iloc[-1]
        ma100= close_series.rolling(100, min_periods=20).mean().iloc[-1]
        ma200= close_series.rolling(200, min_periods=40).mean().iloc[-1]

        def above(ma):
            return float(latest["close"]) > float(ma) if pd.notna(ma) else False

        def dist(ma):
            if pd.isna(ma) or ma <= 0:
                return None
            return round((float(latest["close"]) / float(ma) - 1) * 100, 2)

        # ── Component scores from existing AIScore (avoid recomputing) ──
        score_row = raw["scores"].get(sym)
        if score_row:
            accumulation = float(score_row.accumulation_score or 50)
            distribution = float(score_row.distribution_score or 50)
            momentum = float(score_row.momentum_score or 50)
            trend = float(score_row.trend_score or 50)
            liquidity = float(score_row.liquidity_score or 50)
            opportunity = float(score_row.opportunity_score or 50)
            foreign_strength = float(score_row.foreign_strength_score or 50)
            inventory_score = float(score_row.inventory_score or 50)
            star_rating = int(score_row.star_rating or 0)
            wyckoff_stage = int(score_row.wyckoff_stage or 1)
            wyckoff_label = score_row.wyckoff_stage_label or "ACCUMULATION"
            verdict = score_row.verdict or "ORANGE_X"
            retail_non_flow = float(score_row.retail_non_flow_score or 50)
            fomo_risk = float(score_row.fomo_risk_score or 0)
            trade_readiness = float(score_row.trade_readiness_score or 0)
            trade_signal = score_row.trade_readiness_signal or "WAIT"
        else:
            accumulation = distribution = momentum = trend = liquidity = 50
            opportunity = foreign_strength = inventory_score = 50
            retail_non_flow = 50
            star_rating = 0
            wyckoff_stage = 1
            wyckoff_label = "ACCUMULATION"
            verdict = "ORANGE_X"
            fomo_risk = 0
            trade_readiness = 0
            trade_signal = "WAIT"

        # Institutional Activity Score (synthesized)
        institutional_score = float(np.clip(
            (inventory_score * 0.5) + (foreign_strength * 0.5), 0, 100
        ))

        # Pct change (1D)
        pct_1d = 0.0
        if len(cdf) >= 2:
            prev_close = float(cdf.iloc[-2]["close"])
            if prev_close > 0:
                pct_1d = (float(latest["close"]) / prev_close - 1) * 100

        # 5D & 20D return (for noise / display)
        ret_5d = 0.0
        if len(cdf) >= 6:
            old = float(cdf.iloc[-6]["close"])
            if old > 0:
                ret_5d = (float(latest["close"]) / old - 1) * 100

        ret_20d = 0.0
        if len(cdf) >= 21:
            old = float(cdf.iloc[-21]["close"])
            if old > 0:
                ret_20d = (float(latest["close"]) / old - 1) * 100

        # Volume spike
        avg_vol_20 = float(cdf["volume"].tail(20).mean())
        volume_spike = float(latest["volume"]) / avg_vol_20 if avg_vol_20 > 0 else 1
        avg_value_20 = float(cdf["value"].tail(20).mean())

        return {
            # Identity
            "symbol": sym,
            "name": meta.name if meta else sym,
            "sector": meta.sector if meta else None,
            "is_lq45": bool(meta.is_lq45) if meta else False,
            "is_idx30": bool(meta.is_idx30) if meta else False,
            "market_cap": int(meta.market_cap) if meta and meta.market_cap else 0,

            # Quote
            "price": float(latest["close"]),
            "pct_change": round(pct_1d, 2),
            "ret_5d": round(ret_5d, 2),
            "ret_20d": round(ret_20d, 2),
            "volume": int(latest["volume"]),
            "value": int(latest["value"]),
            "volume_spike": round(volume_spike, 2),
            "avg_value_20d": int(avg_value_20),

            # Money flow grids (raw values; normalization applied later)
            "daily_flow": daily_flow,        # [d-5, d-4, d-3, d-2, d-1, d-0]
            "weekly_flow": weekly_flow,      # [w-5, w-4, w-3, w-2, w-1, w-0]
            "daily_flow_raw": list(daily_flow),
            "weekly_flow_raw": list(weekly_flow),

            # MA section
            "above_ma5":  above(ma5),
            "above_ma10": above(ma10),
            "above_ma20": above(ma20),
            "above_ma50": above(ma50),
            "above_ma100":above(ma100),
            "above_ma200":above(ma200),
            "dist_ma5":  dist(ma5),
            "dist_ma10": dist(ma10),
            "dist_ma20": dist(ma20),
            "dist_ma50": dist(ma50),
            "dist_ma100":dist(ma100),
            "dist_ma200":dist(ma200),

            # Component scores
            "accumulation_score": accumulation,
            "distribution_score": distribution,
            "momentum_score": momentum,
            "trend_score": trend,
            "liquidity_score": liquidity,
            "institutional_score": round(institutional_score, 1),
            "foreign_strength_score": foreign_strength,
            "retail_non_flow_score": retail_non_flow,
            "opportunity_score": opportunity,
            "fomo_risk_score": fomo_risk,
            "trade_readiness_score": trade_readiness,
            "trade_readiness_signal": trade_signal,
            "star_rating": star_rating,
            "wyckoff_stage": wyckoff_stage,
            "wyckoff_label": wyckoff_label,
            "verdict": verdict,

            # placeholders — populated later
            "probability_score": 0,
            "probability_tier": "NEUTRAL",
            "probability_label": "Neutral",
            "signals": [],
            "noise_flags": [],
            "is_noise": False,
        }

    # ------------------------------------------------------------------ #
    # Period flow computation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _weekly_index(daily_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
        """Build a weekly index (Friday close) from a daily index."""
        if len(daily_index) == 0:
            return pd.DatetimeIndex([])
        # Resample to weekly Friday end-of-period
        s = pd.Series(1, index=daily_index)
        weekly = s.resample("W-FRI").last().dropna()
        return weekly.index

    def _compute_period_flow(
        self,
        cdf: pd.DataFrame,
        ffdf: pd.DataFrame,
        bdf: pd.DataFrame,
        ihsg: pd.Series,
        period_index: pd.DatetimeIndex,
        n_periods: int,
        analysis_method: str,
        granularity: str,
    ) -> list[float]:
        """
        Compute the flow score for each of the last `n_periods`.

        Returns a list of length `n_periods`, oldest first
        (e.g. [d-5, d-4, ..., d-0] or [w-5, ..., w-0]).
        """
        # Get the last n_periods anchor dates
        if granularity == "daily":
            anchors = list(period_index[-n_periods:])
            window_size = 1
        else:  # weekly
            anchors = list(period_index[-n_periods:])
            window_size = 5  # 5 trading days per week

        out = []
        for anchor_dt in anchors:
            if granularity == "weekly":
                # Window = last 5 trading days ending at anchor
                window_end = anchor_dt
                window_start = anchor_dt - timedelta(days=window_size + 2)
                slice_cdf = cdf.loc[(cdf.index > pd.Timestamp(window_start)) &
                                     (cdf.index <= pd.Timestamp(window_end))]
                # Weekly metrics aggregated
                value = self._compute_method_value(
                    cdf_window=slice_cdf,
                    ffdf=self._slice_by_date(ffdf, window_start, window_end),
                    bdf=self._slice_by_date(bdf, window_start, window_end),
                    ihsg=ihsg, anchor=anchor_dt,
                    analysis_method=analysis_method,
                )
            else:
                # Daily — single bar
                if anchor_dt not in cdf.index:
                    out.append(0.0)
                    continue
                idx_pos = cdf.index.get_loc(anchor_dt)
                # We may need previous bar for ROC/momentum
                lookback_start = max(0, idx_pos - 5)
                slice_cdf = cdf.iloc[lookback_start:idx_pos + 1]
                value = self._compute_method_value(
                    cdf_window=slice_cdf,
                    ffdf=self._slice_by_date(
                        ffdf, slice_cdf.index[0], slice_cdf.index[-1]
                    ),
                    bdf=self._slice_by_date(
                        bdf, slice_cdf.index[0], slice_cdf.index[-1]
                    ),
                    ihsg=ihsg, anchor=anchor_dt,
                    analysis_method=analysis_method,
                )
            out.append(round(float(value), 2))

        return out

    @staticmethod
    def _slice_by_date(
        df: pd.DataFrame, start, end,
    ) -> pd.DataFrame:
        if df is None or df.empty:
            return df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        return df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]

    def _compute_method_value(
        self,
        cdf_window: pd.DataFrame,
        ffdf: pd.DataFrame,
        bdf: pd.DataFrame,
        ihsg: pd.Series,
        anchor: pd.Timestamp,
        analysis_method: str,
    ) -> float:
        """Method-specific formula for one period bar."""
        if cdf_window.empty:
            return 0.0

        latest = cdf_window.iloc[-1]
        avg_value = max(float(cdf_window["value"].mean()), 1)

        if analysis_method == "non_retail_flow":
            # Inverted retail signal — proxy: -retail flow
            # We don't have retail flow directly per day; use bdf retail brokers
            retail_brokers_set = self.retail_set
            if not bdf.empty:
                retail = bdf[bdf["broker"].isin(retail_brokers_set)]
                retail_net = float(retail["net_value"].sum())
            else:
                retail_net = 0.0
            # Invert and normalize
            return float(np.clip(-retail_net / avg_value * 50, -100, 100))

        elif analysis_method == "foreign_flow":
            net = float(ffdf["net"].sum()) if not ffdf.empty else 0
            return float(np.clip(net / avg_value * 50, -100, 100))

        elif analysis_method == "broker_accumulation":
            # Bandar broker net value normalized
            if not bdf.empty:
                bandar = bdf[bdf["broker"].isin(self.bandar_set)]
                net = float(bandar["net_value"].sum())
            else:
                net = 0.0
            return float(np.clip(net / avg_value * 50, -100, 100))

        elif analysis_method == "smart_money":
            # Composite: foreign + bandar
            f_net = float(ffdf["net"].sum()) if not ffdf.empty else 0
            if not bdf.empty:
                bandar = bdf[bdf["broker"].isin(self.bandar_set)]
                b_net = float(bandar["net_value"].sum())
            else:
                b_net = 0.0
            combined = (f_net + b_net) / avg_value * 50
            return float(np.clip(combined, -100, 100))

        elif analysis_method == "sector_rotation":
            # Stock return for the window vs IHSG
            if len(cdf_window) < 2:
                return 0.0
            stock_ret = (latest["close"] / cdf_window.iloc[0]["close"] - 1) * 100
            try:
                ih_window = ihsg.loc[ihsg.index >= cdf_window.index[0]]
                if len(ih_window) >= 2:
                    bench_ret = (ih_window.iloc[-1] / ih_window.iloc[0] - 1) * 100
                else:
                    bench_ret = 0
            except Exception:
                bench_ret = 0
            return float(np.clip((stock_ret - bench_ret) * 5, -100, 100))

        elif analysis_method == "relative_strength":
            # Same as sector_rotation in formula but emphasizes outperformance
            if len(cdf_window) < 2:
                return 0.0
            stock_ret = (latest["close"] / cdf_window.iloc[0]["close"] - 1) * 100
            try:
                ih_window = ihsg.loc[ihsg.index >= cdf_window.index[0]]
                if len(ih_window) >= 2:
                    bench_ret = (ih_window.iloc[-1] / ih_window.iloc[0] - 1) * 100
                else:
                    bench_ret = 0
            except Exception:
                bench_ret = 0
            rs = stock_ret - bench_ret
            return float(np.clip(rs * 10, -100, 100))

        elif analysis_method == "momentum":
            # Pct change for the window
            if len(cdf_window) < 2:
                return 0.0
            roc = (latest["close"] / cdf_window.iloc[0]["close"] - 1) * 100
            return float(np.clip(roc * 5, -100, 100))

        elif analysis_method == "composite_score":
            # Pseudo opportunity: blend volume + foreign + price change
            if len(cdf_window) < 2:
                return 0.0
            roc = (latest["close"] / cdf_window.iloc[0]["close"] - 1) * 100
            f_net = float(ffdf["net"].sum()) if not ffdf.empty else 0
            f_norm = f_net / avg_value
            vol_change = (
                float(cdf_window["volume"].tail(3).mean())
                / max(float(cdf_window["volume"].head(3).mean()), 1) - 1
            ) * 100
            composite = (roc * 1.5) + (f_norm * 30) + (vol_change * 0.3)
            return float(np.clip(composite, -100, 100))

        return 0.0

    # ------------------------------------------------------------------ #
    # Normalization across universe
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_normalization(rows: list[dict], method: str) -> list[dict]:
        if method == "raw":
            return rows  # values are already raw normalized to -100..+100 by formula

        if method == "normalized":
            # Already in -100..+100 range
            return rows

        if not rows:
            return rows

        # Build matrix: rows × periods (daily 6 cols)
        n = len(rows)

        if method == "z_score":
            # For each period column, compute z-score across universe
            for kind in ["daily_flow", "weekly_flow"]:
                arrs = np.array([r[kind] for r in rows], dtype=float)
                if arrs.size == 0:
                    continue
                # Per-column z-score
                mean = arrs.mean(axis=0)
                std = arrs.std(axis=0)
                z = (arrs - mean) / np.where(std > 0, std, 1)
                z = np.clip(z * 25, -100, 100)  # scale z to -100..+100
                for i, r in enumerate(rows):
                    r[kind] = [round(float(v), 2) for v in z[i]]

        elif method == "percentile":
            # Per-period percentile rank
            for kind in ["daily_flow", "weekly_flow"]:
                arrs = np.array([r[kind] for r in rows], dtype=float)
                if arrs.size == 0:
                    continue
                # rankdata per column
                ranks = np.zeros_like(arrs)
                for col in range(arrs.shape[1]):
                    col_vals = arrs[:, col]
                    order = col_vals.argsort()
                    rank = np.empty_like(order, dtype=float)
                    rank[order] = np.arange(len(order))
                    ranks[:, col] = (rank / max(len(rank) - 1, 1)) * 100
                # Center around 50
                ranks = ranks - 50  # → -50..+50
                ranks = ranks * 2   # → -100..+100
                for i, r in enumerate(rows):
                    r[kind] = [round(float(v), 2) for v in ranks[i]]

        elif method == "relative_strength":
            # Mean across the universe per period; subtract
            for kind in ["daily_flow", "weekly_flow"]:
                arrs = np.array([r[kind] for r in rows], dtype=float)
                if arrs.size == 0:
                    continue
                mean = arrs.mean(axis=0)
                rel = arrs - mean
                rel = np.clip(rel, -100, 100)
                for i, r in enumerate(rows):
                    r[kind] = [round(float(v), 2) for v in rel[i]]

        return rows

    # ------------------------------------------------------------------ #
    # Probability Score (proprietary)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_probability(row: dict) -> None:
        """
        Proprietary 0-100 score combining multiple factors.

        Weights:
            - Accumulation Score:  20%
            - Foreign Strength:    18%
            - Trend Score:         15%
            - Liquidity Score:     12%
            - Institutional Score: 10%
            - Momentum Score:       8%
            - Retail Non-Flow:      8%
            - Opportunity Score:    9%
            - FOMO penalty:        -15% × (fomo_risk / 100)

        Stage adjustments:
            - Stage 2 (Early Breakout): +5
            - Stage 5 (Distribution): -25
            - Stage 4 (Late Trend): -10
        """
        score = (
            row["accumulation_score"] * 0.20 +
            row["foreign_strength_score"] * 0.18 +
            row["trend_score"] * 0.15 +
            row["liquidity_score"] * 0.12 +
            row["institutional_score"] * 0.10 +
            row["momentum_score"] * 0.08 +
            row["retail_non_flow_score"] * 0.08 +
            row["opportunity_score"] * 0.09
        )
        score -= row["fomo_risk_score"] * 0.15

        # Stage adjustment
        stage = row["wyckoff_stage"]
        if stage == 2:
            score += 5
        elif stage == 4:
            score -= 10
        elif stage == 5:
            score -= 25

        # Cap to 0-100
        score = float(np.clip(score, 0, 100))

        # Tier
        for low, high, tier, label in PROBABILITY_TIERS:
            if low <= score < high:
                row["probability_tier"] = tier
                row["probability_label"] = label
                break
        else:
            if score >= 100:
                row["probability_tier"] = "INSTITUTIONAL_ACCUMULATION"
                row["probability_label"] = "Institutional Accumulation"

        row["probability_score"] = round(score, 1)

    # ------------------------------------------------------------------ #
    # Smart Money Signals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_signals(row: dict) -> None:
        """Detect smart money signals + provide explanation."""
        signals = []

        # 1. Hidden Accumulation
        if (row["accumulation_score"] >= 65 and
            row["wyckoff_stage"] == 1 and
            row["fomo_risk_score"] < 30 and
            row["liquidity_score"] >= 50):
            signals.append({
                "code": "HIDDEN_ACCUM",
                "label": "Hidden Accumulation",
                "color": "green",
                "explanation": (
                    f"Akumulasi tersembunyi: bandar masuk perlahan tanpa "
                    f"menggerakan harga (FOMO {row['fomo_risk_score']:.0f}/100, "
                    f"likuiditas baik). Setup early-bird."
                ),
            })

        # 2. Volume Expansion
        if row["volume_spike"] >= 1.5 and row["accumulation_score"] >= 55:
            signals.append({
                "code": "VOL_EXPANSION",
                "label": "Volume Expansion",
                "color": "green",
                "explanation": (
                    f"Volume meledak {row['volume_spike']:.2f}x rata-rata, "
                    f"akumulasi terkonfirmasi."
                ),
            })

        # 3. Low Volatility Accumulation
        if (row["wyckoff_stage"] == 1 and
            abs(row["pct_change"]) < 1.5 and
            row["accumulation_score"] >= 60):
            signals.append({
                "code": "LOW_VOL_ACCUM",
                "label": "Low Vol Accumulation",
                "color": "cyan",
                "explanation": (
                    "Range harga sempit, smart money aktif. Compression sebelum breakout."
                ),
            })

        # 4. Breakout Preparation
        if (row["wyckoff_stage"] == 2 and
            row["above_ma20"] and
            row["volume_spike"] >= 1.2):
            signals.append({
                "code": "BREAKOUT_PREP",
                "label": "Breakout Preparation",
                "color": "blue",
                "explanation": (
                    "Stage 2 + di atas MA20 + volume mulai expand. Persiapan breakout."
                ),
            })

        # 5. Distribution Warning
        if (row["distribution_score"] >= 65 and
            row["wyckoff_stage"] in (4, 5)):
            signals.append({
                "code": "DIST_WARNING",
                "label": "Distribution Warning",
                "color": "red",
                "explanation": (
                    f"Distribusi terdeteksi (score {row['distribution_score']:.0f}), "
                    f"stage {row['wyckoff_stage']}. Hindari long, evaluasi exit."
                ),
            })

        # 6. False Breakout Risk
        if (row["above_ma20"] and
            row["fomo_risk_score"] >= 60 and
            row["volume_spike"] < 1.2):
            signals.append({
                "code": "FALSE_BREAKOUT_RISK",
                "label": "False Breakout Risk",
                "color": "orange",
                "explanation": (
                    f"Harga di atas MA20 tapi FOMO {row['fomo_risk_score']:.0f}/100 + "
                    f"volume tipis. Risiko false breakout."
                ),
            })

        # 7. Liquidity Trap
        if row["liquidity_score"] < 30:
            signals.append({
                "code": "LIQ_TRAP",
                "label": "Liquidity Trap",
                "color": "red",
                "explanation": (
                    f"Likuiditas sangat rendah (score {row['liquidity_score']:.0f}). "
                    f"Hindari — sulit exit posisi."
                ),
            })

        # 8. Retail FOMO Warning (contrarian)
        if (row["retail_non_flow_score"] <= 35 and
            row["wyckoff_stage"] >= 3):
            signals.append({
                "code": "RETAIL_FOMO",
                "label": "Retail FOMO Trap",
                "color": "red",
                "explanation": (
                    f"Retail FOMO buying tinggi (non-flow {row['retail_non_flow_score']:.0f}), "
                    f"stage {row['wyckoff_stage']}. Smart money keluar via retail demand."
                ),
            })

        row["signals"] = signals

    # ------------------------------------------------------------------ #
    # Noise Reduction System
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_noise_flags(row: dict) -> None:
        """Flag rows that should be excluded as noise. Each flag has explanation."""
        flags = []

        # 1. Illiquid
        if row["avg_value_20d"] < 1_000_000_000:  # < 1B IDR avg daily
            flags.append({
                "code": "NOISE_ILLIQUID",
                "label": "Illiquid",
                "explanation": (
                    f"Avg daily value 20D hanya Rp {row['avg_value_20d']/1e9:.2f}M "
                    f"(< 1M). Sulit exit posisi besar."
                ),
            })

        # 2. One-day pump
        if row["pct_change"] > 7 and row["volume_spike"] > 3:
            flags.append({
                "code": "NOISE_ONE_DAY_PUMP",
                "label": "One-Day Pump",
                "explanation": (
                    f"Hari ini +{row['pct_change']:.1f}% dengan volume "
                    f"{row['volume_spike']:.1f}x rata-rata. Risiko pump-and-dump."
                ),
            })

        # 3. Pumped (5D extended)
        if row["ret_5d"] > 25:
            flags.append({
                "code": "NOISE_PUMPED",
                "label": "Pumped (5D)",
                "explanation": (
                    f"5D return {row['ret_5d']:+.1f}% — sudah extended, risk-reward jelek."
                ),
            })

        # 4. Retail FOMO spike
        if (row["retail_non_flow_score"] <= 30 and
            row["pct_change"] > 5):
            flags.append({
                "code": "NOISE_RETAIL_FOMO",
                "label": "Retail FOMO Spike",
                "explanation": (
                    "Spike harga didorong retail FOMO — bukan smart money."
                ),
            })

        # 5. Dead-cat bounce
        if (row["ret_20d"] < -15 and
            row["pct_change"] > 4 and
            row["wyckoff_stage"] in (4, 5)):
            flags.append({
                "code": "NOISE_DEAD_CAT",
                "label": "Dead Cat Bounce",
                "explanation": (
                    f"20D return {row['ret_20d']:.1f}% (downtrend), tapi hari ini bounce. "
                    f"Counter-trend, low probability."
                ),
            })

        # 6. False momentum (low liquidity + price rise)
        if (row["liquidity_score"] < 40 and
            row["pct_change"] > 3):
            flags.append({
                "code": "NOISE_FALSE_MOMENTUM",
                "label": "False Momentum",
                "explanation": (
                    f"Likuiditas rendah ({row['liquidity_score']:.0f}) dengan harga naik. "
                    f"Bisa jadi gorengan/manipulasi."
                ),
            })

        row["noise_flags"] = flags
        row["is_noise"] = len(flags) > 0

    # ------------------------------------------------------------------ #
    # User filters
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_user_filters(
        rows: list[dict], f: MarketSummaryFilter,
    ) -> tuple[list[dict], list[dict]]:
        accepted = []
        rejected = []

        for r in rows:
            # Noise filter
            if f.apply_noise_filter and r["is_noise"]:
                rejected.append(r)
                continue

            # Threshold filters
            if f.min_accumulation is not None and r["accumulation_score"] < f.min_accumulation:
                continue
            if f.min_foreign_flow is not None and r["foreign_strength_score"] < f.min_foreign_flow:
                continue
            if f.min_volume_spike is not None and r["volume_spike"] < f.min_volume_spike:
                continue
            if f.min_momentum is not None and r["momentum_score"] < f.min_momentum:
                continue
            if f.min_liquidity is not None and r["liquidity_score"] < f.min_liquidity:
                continue
            if f.min_trend is not None and r["trend_score"] < f.min_trend:
                continue
            if f.min_probability is not None and r["probability_score"] < f.min_probability:
                continue

            # MA filters
            if f.require_above_ma5 is not None and r["above_ma5"] != f.require_above_ma5:
                continue
            if f.require_above_ma20 is not None and r["above_ma20"] != f.require_above_ma20:
                continue
            if f.require_above_ma50 is not None and r["above_ma50"] != f.require_above_ma50:
                continue
            if f.require_above_ma200 is not None and r["above_ma200"] != f.require_above_ma200:
                continue

            accepted.append(r)
        return accepted, rejected

    # ------------------------------------------------------------------ #
    # Summary builder
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_summary(accepted: list[dict], rejected: list[dict]) -> dict:
        tier_counts = {tier: 0 for _, _, tier, _ in PROBABILITY_TIERS}
        for r in accepted:
            t = r.get("probability_tier", "NEUTRAL")
            if t in tier_counts:
                tier_counts[t] += 1

        sector_counts = {}
        for r in accepted:
            s = r.get("sector") or "OTHER"
            sector_counts[s] = sector_counts.get(s, 0) + 1

        return {
            "total_in_universe": len(accepted) + len(rejected),
            "accepted": len(accepted),
            "rejected_as_noise": len(rejected),
            "tier_distribution": tier_counts,
            "sector_distribution": sector_counts,
        }

    # ------------------------------------------------------------------ #
    # CSV Export
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_csv(scan_result: dict) -> str:
        """Render scan result as CSV string."""
        import csv
        from io import StringIO

        rows = scan_result.get("rows", [])
        if not rows:
            return ""

        out = StringIO()
        cols = [
            "symbol", "name", "sector", "price", "pct_change",
            "volume", "value", "market_cap",
            "probability_score", "probability_tier",
            "accumulation_score", "distribution_score",
            "foreign_strength_score", "trend_score",
            "liquidity_score", "momentum_score", "institutional_score",
            "wyckoff_stage", "wyckoff_label", "verdict",
            "above_ma5", "above_ma10", "above_ma20",
            "above_ma50", "above_ma100", "above_ma200",
            "dist_ma20", "dist_ma200",
            "volume_spike", "fomo_risk_score",
            "trade_readiness_signal", "star_rating",
        ]
        writer = csv.writer(out)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r.get(c, "") for c in cols])
        return out.getvalue()
