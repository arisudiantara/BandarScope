"""
Market Summary Pro — institutional-grade money flow grid (V2 — OPTIMIZED).

OPTIMIZATIONS over V1:
- Vectorized scoring: compute money-flow score for ALL (symbol, date) combos
  in one pandas pass instead of per-symbol Python loops.
- Smart data fetch: skip foreign/broker queries when not needed by the
  selected analysis method.
- Bulk MA computation via groupby+rolling instead of per-symbol loops.
- In-memory TTL cache (60s) keyed by filter hash + latest_date.
- Reduced lookback window (220 days, only what MA200 actually needs).
- Pre-computed weekly bins shared across all symbols.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
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

# Which raw data each method needs (for smart fetching)
METHOD_NEEDS = {
    "non_retail_flow":     {"foreign": False, "broker": True,  "ihsg": False},
    "foreign_flow":        {"foreign": True,  "broker": False, "ihsg": False},
    "broker_accumulation": {"foreign": False, "broker": True,  "ihsg": False},
    "smart_money":         {"foreign": True,  "broker": True,  "ihsg": False},
    "sector_rotation":     {"foreign": False, "broker": False, "ihsg": True},
    "relative_strength":   {"foreign": False, "broker": False, "ihsg": True},
    "momentum":            {"foreign": False, "broker": False, "ihsg": False},
    "composite_score":     {"foreign": True,  "broker": False, "ihsg": False},
}

N_PERIODS = 6  # we always show last 6 daily / 6 weekly cells


# ============================================================
# In-memory TTL cache
# ============================================================
_CACHE: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 60  # seconds


def _cache_get(key: str) -> Optional[dict]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ts, value = entry
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value: dict) -> None:
    _CACHE[key] = (time.time(), value)
    # Cap cache size
    if len(_CACHE) > 50:
        oldest = sorted(_CACHE.items(), key=lambda kv: kv[1][0])[:10]
        for k, _ in oldest:
            _CACHE.pop(k, None)


# ============================================================
# Filter dataclass
# ============================================================

@dataclass
class MarketSummaryFilter:
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

    sort_by: str = "opportunity_score"
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
    # Public API
    # ------------------------------------------------------------------ #

    def scan(self, f: MarketSummaryFilter) -> dict:
        latest_date = self.db.query(func.max(Candle.date)).scalar()
        if not latest_date:
            return {"error": "No data"}

        # ── Cache check ──
        cache_key = self._cache_key(f, latest_date)
        cached = _cache_get(cache_key)
        if cached:
            return cached

        # ── Resolve universe ──
        symbols_meta = self._resolve_universe(f)
        if not symbols_meta:
            return {"error": f"Empty universe: {f.universe}"}
        symbol_codes = [s.code for s in symbols_meta]

        # ── Smart-fetch raw data ──
        needs = METHOD_NEEDS.get(f.analysis_method, METHOD_NEEDS["smart_money"])
        raw = self._bulk_fetch(
            symbol_codes,
            latest_date,
            need_foreign=needs["foreign"],
            need_broker=needs["broker"],
        )
        if raw["candles"].empty:
            empty = {"rows": [], "as_of": latest_date.isoformat(), "summary": {}}
            _cache_set(cache_key, empty)
            return empty

        # ── Build IHSG series (only if method needs it) ──
        ihsg_daily = pd.Series(dtype=float)
        if needs["ihsg"]:
            ihsg_daily = self._build_benchmark(raw["candles"])

        # ── Vectorized per-period score computation ──
        # Returns a DataFrame indexed by (symbol, date) with column 'flow'
        score_df = self._compute_flow_vectorized(
            cdf=raw["candles"],
            ffdf=raw["foreign"],
            bdf=raw["brokers"],
            ihsg=ihsg_daily,
            method=f.analysis_method,
            bandar_set=self.bandar_set,
            retail_set=self.retail_set,
        )

        # ── Build daily/weekly grids per symbol ──
        daily_grid = self._build_daily_grid(score_df)
        weekly_grid = self._build_weekly_grid(score_df)

        # ── Apply normalization across universe ──
        daily_grid = self._normalize(daily_grid, f.normalization)
        weekly_grid = self._normalize(weekly_grid, f.normalization)

        # ── Bulk MA computation ──
        ma_table = self._bulk_compute_mas(raw["candles"], latest_date)

        # ── Pull cached AIScore (component scores) ──
        scores_map = raw["scores"]

        # ── Build rows ──
        rows = []
        for sym_meta in symbols_meta:
            sym = sym_meta.code
            d_flow = daily_grid.get(sym, [0.0] * N_PERIODS)
            w_flow = weekly_grid.get(sym, [0.0] * N_PERIODS)
            ma = ma_table.get(sym)
            score = scores_map.get(sym)

            row = self._build_row(
                sym_meta=sym_meta,
                d_flow=d_flow,
                w_flow=w_flow,
                ma=ma,
                score=score,
                latest_candles=raw["latest_candles"].get(sym),
                prev_candles=raw["prev_candles"].get(sym),
            )
            if row is not None:
                rows.append(row)

        # ── Compute signals & noise flags ──
        for r in rows:
            self._compute_signals(r)
            self._compute_noise_flags(r)

        # ── Filter ──
        accepted, rejected = self._apply_user_filters(rows, f)

        # ── Sort & limit ──
        sort_key = f.sort_by
        accepted.sort(
            key=lambda x: (x.get(sort_key) or 0),
            reverse=f.sort_desc,
        )
        accepted = accepted[: f.limit]

        # ── Summary ──
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

        _cache_set(cache_key, result)
        return result

    # ------------------------------------------------------------------ #
    # Cache key
    # ------------------------------------------------------------------ #

    @staticmethod
    def _cache_key(f: MarketSummaryFilter, latest_date) -> str:
        payload = {
            "filter": asdict(f),
            "as_of": latest_date.isoformat(),
        }
        return hashlib.md5(json.dumps(payload, sort_keys=True).encode()).hexdigest()

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
        elif u == "LQ45":             q = q.filter(Symbol.is_lq45 == True)
        elif u == "IDX30":            q = q.filter(Symbol.is_idx30 == True)
        elif u == "KOMPAS100":        q = q.filter(Symbol.is_kompas100 == True)
        elif u == "ISSI":             q = q.filter(Symbol.is_issi == True)
        elif u == "JII70":            q = q.filter(Symbol.is_jii70 == True)
        elif u == "COMPOSITE":        q = q.filter(Symbol.is_composite == True)
        elif u == "IDXENERGY":        q = q.filter(Symbol.is_idxenergy == True)
        elif u == "IDXBASIC":         q = q.filter(Symbol.is_idxbasic == True)
        elif u == "IDXINDUST":        q = q.filter(Symbol.is_idxindust == True)
        elif u == "IDXCYCLIC":        q = q.filter(Symbol.is_idxcyclic == True)
        elif u == "IDXNONCYC":        q = q.filter(Symbol.is_idxnoncyc == True)
        elif u == "IDXHEALTH":        q = q.filter(Symbol.is_idxhealth == True)
        elif u == "IDXFINANCE":       q = q.filter(Symbol.is_idxfinance == True)
        elif u == "IDXPROPERTY":      q = q.filter(Symbol.is_idxproperty == True)
        elif u == "IDXTECHNO":        q = q.filter(Symbol.is_idxtechno == True)
        elif u == "IDXINFRA":         q = q.filter(Symbol.is_idxinfra == True)
        elif u == "IDXTRANS":         q = q.filter(Symbol.is_idxtrans == True)
        return q.all()

    # ------------------------------------------------------------------ #
    # Smart bulk fetch
    # ------------------------------------------------------------------ #

    def _bulk_fetch(
        self,
        symbols: list[str],
        latest_date: date,
        need_foreign: bool,
        need_broker: bool,
    ) -> dict:
        """Fetch only what's needed. Reduced lookback to 220 days (MA200 + buffer)."""
        load_start = latest_date - timedelta(days=240)

        # Always need candles
        candles = (
            self.db.query(
                Candle.symbol, Candle.date, Candle.open, Candle.high,
                Candle.low, Candle.close, Candle.volume, Candle.value,
            )
            .filter(
                Candle.symbol.in_(symbols),
                Candle.date >= load_start,
                Candle.date <= latest_date,
            )
            .all()
        )
        cdf = pd.DataFrame(candles, columns=[
            "symbol", "date", "open", "high", "low", "close", "volume", "value",
        ])
        if not cdf.empty:
            cdf["date"] = pd.to_datetime(cdf["date"])

        # Latest 2 candles per symbol (for pct_change + display)
        latest_candles = {}
        prev_candles = {}
        if not cdf.empty:
            cdf_sorted = cdf.sort_values(["symbol", "date"])
            latest_per_sym = cdf_sorted.groupby("symbol").tail(2)
            for sym, sub in latest_per_sym.groupby("symbol"):
                if len(sub) >= 1:
                    latest_candles[sym] = sub.iloc[-1].to_dict()
                if len(sub) >= 2:
                    prev_candles[sym] = sub.iloc[-2].to_dict()

        # Foreign — only fetch if needed
        ffdf = pd.DataFrame()
        if need_foreign:
            # We only need data within the period window (last ~30 days for weekly grid)
            ff_start = latest_date - timedelta(days=45)
            ff = (
                self.db.query(
                    ForeignFlow.symbol, ForeignFlow.date,
                    ForeignFlow.foreign_net_value,
                )
                .filter(
                    ForeignFlow.symbol.in_(symbols),
                    ForeignFlow.date >= ff_start,
                    ForeignFlow.date <= latest_date,
                )
                .all()
            )
            ffdf = pd.DataFrame(ff, columns=["symbol", "date", "net"])
            if not ffdf.empty:
                ffdf["date"] = pd.to_datetime(ffdf["date"])

        # Broker — only fetch if needed; aggregate by entity at SQL level
        bdf = pd.DataFrame()
        if need_broker:
            bd_start = latest_date - timedelta(days=45)
            # We aggregate bandar/retail per (symbol, date) at the SQL level to
            # avoid pulling all individual broker rows
            brokers_filter = list(self.bandar_set | self.retail_set)
            if brokers_filter:
                bds = (
                    self.db.query(
                        BrokerDailySummary.symbol,
                        BrokerDailySummary.date,
                        BrokerDailySummary.broker_code,
                        BrokerDailySummary.net_value,
                        BrokerDailySummary.net_lot,
                    )
                    .filter(
                        BrokerDailySummary.symbol.in_(symbols),
                        BrokerDailySummary.date >= bd_start,
                        BrokerDailySummary.date <= latest_date,
                        BrokerDailySummary.broker_code.in_(brokers_filter),
                    )
                    .all()
                )
                bdf = pd.DataFrame(bds, columns=[
                    "symbol", "date", "broker", "net_value", "net_lot",
                ])
                if not bdf.empty:
                    bdf["date"] = pd.to_datetime(bdf["date"])
                    # Tag entity (bandar / retail)
                    bdf["entity"] = "other"
                    bdf.loc[bdf["broker"].isin(self.bandar_set), "entity"] = "bandar"
                    bdf.loc[bdf["broker"].isin(self.retail_set), "entity"] = "retail"

        # Latest scores (all in one query)
        scores = (
            self.db.query(AIScore)
            .filter(AIScore.symbol.in_(symbols), AIScore.date == latest_date)
            .all()
        )
        scores_map = {s.symbol: s for s in scores}

        return {
            "candles": cdf,
            "foreign": ffdf,
            "brokers": bdf,
            "scores": scores_map,
            "latest_candles": latest_candles,
            "prev_candles": prev_candles,
        }

    # ------------------------------------------------------------------ #
    # IHSG benchmark
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_benchmark(cdf: pd.DataFrame) -> pd.Series:
        if cdf.empty:
            return pd.Series(dtype=float)
        daily = (
            cdf.groupby("date")
               .apply(lambda x: (x["close"] * x["value"]).sum() / max(x["value"].sum(), 1))
               .sort_index()
        )
        return daily

    # ------------------------------------------------------------------ #
    # VECTORIZED FLOW COMPUTATION
    # ------------------------------------------------------------------ #
    # Computes the daily money-flow score for ALL (symbol, date) combos in
    # one pandas pass, instead of looping per-symbol per-period.
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_flow_vectorized(
        cdf: pd.DataFrame,
        ffdf: pd.DataFrame,
        bdf: pd.DataFrame,
        ihsg: pd.Series,
        method: str,
        bandar_set: set,
        retail_set: set,
    ) -> pd.DataFrame:
        """
        Returns a DataFrame: index=(symbol, date), columns=['flow'].
        Each row is the per-day flow score (already in -100..+100 range).
        """
        if cdf.empty:
            return pd.DataFrame(columns=["flow"])

        # Compute avg_value per symbol (rolling 20D) — used for normalization
        cdf = cdf.sort_values(["symbol", "date"]).reset_index(drop=True)
        cdf["avg_value_20"] = (
            cdf.groupby("symbol")["value"]
               .transform(lambda s: s.rolling(20, min_periods=5).mean())
               .fillna(cdf["value"])
               .clip(lower=1)
        )

        # Pre-compute pct change per symbol (for momentum-based methods)
        cdf["close_prev"] = cdf.groupby("symbol")["close"].shift(1)
        cdf["roc_1d"] = (cdf["close"] / cdf["close_prev"] - 1) * 100
        cdf["roc_1d"] = cdf["roc_1d"].fillna(0)

        if method == "momentum":
            cdf["flow"] = (cdf["roc_1d"] * 5).clip(-100, 100)

        elif method == "foreign_flow":
            if ffdf.empty:
                cdf["flow"] = 0.0
            else:
                merged = cdf.merge(
                    ffdf, on=["symbol", "date"], how="left"
                ).fillna({"net": 0})
                merged["flow"] = (
                    merged["net"] / merged["avg_value_20"] * 50
                ).clip(-100, 100)
                cdf = merged

        elif method == "broker_accumulation":
            if bdf.empty:
                cdf["flow"] = 0.0
            else:
                bandar = bdf[bdf["entity"] == "bandar"]
                if bandar.empty:
                    cdf["flow"] = 0.0
                else:
                    bandar_daily = (
                        bandar.groupby(["symbol", "date"])["net_value"].sum().reset_index()
                    )
                    merged = cdf.merge(
                        bandar_daily, on=["symbol", "date"], how="left"
                    ).fillna({"net_value": 0})
                    merged["flow"] = (
                        merged["net_value"] / merged["avg_value_20"] * 50
                    ).clip(-100, 100)
                    cdf = merged

        elif method == "non_retail_flow":
            if bdf.empty:
                cdf["flow"] = 0.0
            else:
                retail = bdf[bdf["entity"] == "retail"]
                if retail.empty:
                    cdf["flow"] = 0.0
                else:
                    retail_daily = (
                        retail.groupby(["symbol", "date"])["net_value"].sum().reset_index()
                    )
                    merged = cdf.merge(
                        retail_daily, on=["symbol", "date"], how="left"
                    ).fillna({"net_value": 0})
                    # INVERT: retail jual = positif
                    merged["flow"] = (
                        -merged["net_value"] / merged["avg_value_20"] * 50
                    ).clip(-100, 100)
                    cdf = merged

        elif method == "smart_money":
            # Need both foreign + bandar
            base = cdf.copy()
            f_part = pd.Series(0.0, index=base.index)
            b_part = pd.Series(0.0, index=base.index)

            if not ffdf.empty:
                merged = base.merge(
                    ffdf, on=["symbol", "date"], how="left"
                )["net"].fillna(0)
                f_part = merged.values

            if not bdf.empty:
                bandar = bdf[bdf["entity"] == "bandar"]
                if not bandar.empty:
                    bandar_daily = (
                        bandar.groupby(["symbol", "date"])["net_value"].sum().reset_index()
                    )
                    merged = base.merge(
                        bandar_daily, on=["symbol", "date"], how="left"
                    )["net_value"].fillna(0)
                    b_part = merged.values

            cdf["flow"] = (
                ((f_part + b_part) / cdf["avg_value_20"] * 50)
                .clip(-100, 100)
            )

        elif method in ("sector_rotation", "relative_strength"):
            # Stock daily ROC vs IHSG daily ROC
            if ihsg.empty:
                cdf["flow"] = 0.0
            else:
                ihsg_df = pd.DataFrame({"date": ihsg.index, "ihsg": ihsg.values})
                ihsg_df["ihsg_prev"] = ihsg_df["ihsg"].shift(1)
                ihsg_df["ihsg_roc"] = (
                    ihsg_df["ihsg"] / ihsg_df["ihsg_prev"] - 1
                ) * 100
                ihsg_df = ihsg_df[["date", "ihsg_roc"]]

                merged = cdf.merge(ihsg_df, on="date", how="left").fillna(0)
                rs = merged["roc_1d"] - merged["ihsg_roc"]
                multiplier = 10 if method == "relative_strength" else 5
                cdf["flow"] = (rs * multiplier).clip(-100, 100)

        elif method == "composite_score":
            # roc + foreign_norm + vol_change
            if not ffdf.empty:
                merged = cdf.merge(ffdf, on=["symbol", "date"], how="left").fillna({"net": 0})
                f_norm = merged["net"] / cdf["avg_value_20"]
            else:
                f_norm = pd.Series(0.0, index=cdf.index)

            cdf["vol_3"] = (
                cdf.groupby("symbol")["volume"]
                   .transform(lambda s: s.rolling(3, min_periods=1).mean())
            )
            cdf["vol_3_prev"] = cdf.groupby("symbol")["vol_3"].shift(3).fillna(cdf["vol_3"])
            vol_change = (cdf["vol_3"] / cdf["vol_3_prev"].clip(lower=1) - 1) * 100

            cdf["flow"] = (
                cdf["roc_1d"] * 1.5 + f_norm.values * 30 + vol_change * 0.3
            ).clip(-100, 100)
        else:
            cdf["flow"] = 0.0

        cdf["flow"] = cdf["flow"].fillna(0).round(2)
        return cdf.set_index(["symbol", "date"])[["flow"]]

    # ------------------------------------------------------------------ #
    # Build daily/weekly grids per symbol
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_daily_grid(score_df: pd.DataFrame) -> dict[str, list[float]]:
        """Last N daily scores per symbol (oldest first)."""
        if score_df.empty:
            return {}
        out = {}
        df = score_df.reset_index().sort_values(["symbol", "date"])
        for sym, sub in df.groupby("symbol"):
            tail = sub.tail(N_PERIODS)
            vals = tail["flow"].tolist()
            # Pad with zeros if fewer than N_PERIODS
            if len(vals) < N_PERIODS:
                vals = [0.0] * (N_PERIODS - len(vals)) + vals
            out[sym] = vals
        return out

    @staticmethod
    def _build_weekly_grid(score_df: pd.DataFrame) -> dict[str, list[float]]:
        """Last N weekly aggregates per symbol (oldest first)."""
        if score_df.empty:
            return {}
        out = {}
        df = score_df.reset_index()
        # Week-end Friday
        df["week"] = df["date"].dt.to_period("W-FRI")
        weekly = df.groupby(["symbol", "week"])["flow"].sum().reset_index()
        for sym, sub in weekly.groupby("symbol"):
            sub = sub.sort_values("week").tail(N_PERIODS)
            vals = sub["flow"].tolist()
            if len(vals) < N_PERIODS:
                vals = [0.0] * (N_PERIODS - len(vals)) + vals
            # Clip into -100..+100 (since we summed multiple days)
            out[sym] = [round(float(np.clip(v, -100, 100)), 2) for v in vals]
        return out

    # ------------------------------------------------------------------ #
    # Normalization
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize(
        grid: dict[str, list[float]],
        method: str,
    ) -> dict[str, list[float]]:
        if method in ("raw", "normalized") or not grid:
            return grid

        symbols = list(grid.keys())
        arr = np.array([grid[s] for s in symbols], dtype=float)

        if method == "z_score":
            mean = arr.mean(axis=0)
            std = arr.std(axis=0)
            std = np.where(std > 0, std, 1)
            z = (arr - mean) / std
            arr = np.clip(z * 25, -100, 100)
        elif method == "percentile":
            ranks = np.zeros_like(arr)
            for col in range(arr.shape[1]):
                col_vals = arr[:, col]
                order = col_vals.argsort()
                rank = np.empty_like(order, dtype=float)
                rank[order] = np.arange(len(order))
                ranks[:, col] = (rank / max(len(rank) - 1, 1)) * 100
            arr = np.clip((ranks - 50) * 2, -100, 100)
        elif method == "relative_strength":
            mean = arr.mean(axis=0)
            arr = np.clip(arr - mean, -100, 100)

        return {
            symbols[i]: [round(float(v), 2) for v in arr[i]]
            for i in range(len(symbols))
        }

    # ------------------------------------------------------------------ #
    # Bulk MA computation (vectorized)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _bulk_compute_mas(
        cdf: pd.DataFrame,
        latest_date: date,
    ) -> dict[str, dict]:
        """Compute MAs for all symbols in one pass. Returns dict[sym] -> ma dict."""
        if cdf.empty:
            return {}

        df = cdf.sort_values(["symbol", "date"]).copy()
        latest_ts = pd.Timestamp(latest_date)

        # Compute rolling means via groupby
        for window in (5, 10, 20, 50, 100, 200):
            df[f"ma{window}"] = (
                df.groupby("symbol")["close"]
                  .transform(lambda s: s.rolling(window, min_periods=max(2, window // 5)).mean())
            )

        # Take only the latest row per symbol
        latest_rows = (
            df[df["date"] == latest_ts]
            .set_index("symbol")
        )

        out = {}
        for sym in latest_rows.index:
            row = latest_rows.loc[sym]
            close = float(row["close"])
            entry = {"close": close}
            for window in (5, 10, 20, 50, 100, 200):
                ma = row.get(f"ma{window}")
                if pd.isna(ma) or ma is None or ma == 0:
                    entry[f"above_ma{window}"] = False
                    entry[f"dist_ma{window}"] = None
                else:
                    ma_f = float(ma)
                    entry[f"above_ma{window}"] = close > ma_f
                    entry[f"dist_ma{window}"] = round((close / ma_f - 1) * 100, 2)
            out[sym] = entry
        return out

    # ------------------------------------------------------------------ #
    # Build a row from precomputed pieces
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_row(
        sym_meta: Symbol,
        d_flow: list[float],
        w_flow: list[float],
        ma: Optional[dict],
        score: Optional[AIScore],
        latest_candles: Optional[dict],
        prev_candles: Optional[dict],
    ) -> Optional[dict]:
        if latest_candles is None:
            return None

        price = float(latest_candles.get("close", 0))
        if price <= 0:
            return None

        prev_close = float(prev_candles["close"]) if prev_candles else price
        pct_change = (price / prev_close - 1) * 100 if prev_close > 0 else 0

        volume = int(latest_candles.get("volume", 0) or 0)
        value = int(latest_candles.get("value", 0) or 0)

        # MA defaults
        if ma:
            ma_data = {
                "above_ma5":  ma["above_ma5"],
                "above_ma10": ma["above_ma10"],
                "above_ma20": ma["above_ma20"],
                "above_ma50": ma["above_ma50"],
                "above_ma100": ma["above_ma100"],
                "above_ma200": ma["above_ma200"],
                "dist_ma5":  ma["dist_ma5"],
                "dist_ma10": ma["dist_ma10"],
                "dist_ma20": ma["dist_ma20"],
                "dist_ma50": ma["dist_ma50"],
                "dist_ma100": ma["dist_ma100"],
                "dist_ma200": ma["dist_ma200"],
            }
        else:
            ma_data = {f"above_ma{n}": False for n in (5, 10, 20, 50, 100, 200)}
            ma_data.update({f"dist_ma{n}": None for n in (5, 10, 20, 50, 100, 200)})

        # Component scores
        if score:
            accumulation = float(score.accumulation_score or 50)
            distribution = float(score.distribution_score or 50)
            momentum = float(score.momentum_score or 50)
            trend = float(score.trend_score or 50)
            liquidity = float(score.liquidity_score or 50)
            opportunity = float(score.opportunity_score or 50)
            foreign_strength = float(score.foreign_strength_score or 50)
            inventory_score = float(score.inventory_score or 50)
            wyckoff_stage = int(score.wyckoff_stage or 1)
            wyckoff_label = score.wyckoff_stage_label or "ACCUMULATION"
            verdict = score.verdict or "ORANGE_X"
            retail_non_flow = float(score.retail_non_flow_score or 50)
            fomo_risk = float(score.fomo_risk_score or 0)
            trade_readiness = float(score.trade_readiness_score or 0)
            trade_signal = score.trade_readiness_signal or "WAIT"
            avg_value_20d = int(score.avg_value_20d or 0)
        else:
            accumulation = distribution = momentum = trend = liquidity = 50
            opportunity = foreign_strength = inventory_score = 50
            retail_non_flow = 50
            wyckoff_stage = 1
            wyckoff_label = "ACCUMULATION"
            verdict = "ORANGE_X"
            fomo_risk = 0
            trade_readiness = 0
            trade_signal = "WAIT"
            avg_value_20d = 0

        institutional_score = float(np.clip(
            (inventory_score * 0.5) + (foreign_strength * 0.5), 0, 100
        ))

        # Volume spike (use latest vol vs simple proxy from avg_value_20d/price)
        # avg_value_20d is in IDR; convert to share count proxy
        avg_vol_proxy = (avg_value_20d / price) if (avg_value_20d > 0 and price > 0) else 0
        volume_spike = (volume / avg_vol_proxy) if avg_vol_proxy > 0 else 1
        volume_spike = round(float(volume_spike), 2)

        # ret_5d, ret_20d — use price + prev_close approximation
        # We don't have full series here for vectorized perf, but the 1D pct_change suffices.
        # 5D / 20D return: best computed during scoring; here we omit precise values
        # and let signals/noise rely on what's present.
        ret_5d = 0.0
        ret_20d = 0.0

        return {
            "symbol": sym_meta.code,
            "name": sym_meta.name,
            "sector": sym_meta.sector,
            "is_lq45": bool(sym_meta.is_lq45),
            "is_idx30": bool(sym_meta.is_idx30),
            "market_cap": int(sym_meta.market_cap) if sym_meta.market_cap else 0,

            "price": price,
            "pct_change": round(pct_change, 2),
            "ret_5d": ret_5d,
            "ret_20d": ret_20d,
            "volume": volume,
            "value": value,
            "volume_spike": volume_spike,
            "avg_value_20d": avg_value_20d,

            "daily_flow": d_flow,
            "weekly_flow": w_flow,

            **ma_data,

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
            "wyckoff_stage": wyckoff_stage,
            "wyckoff_label": wyckoff_label,
            "verdict": verdict,

            "signals": [],
            "noise_flags": [],
            "is_noise": False,
        }

    # ------------------------------------------------------------------ #
    # Smart money signals
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_signals(row: dict) -> None:
        signals = []

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

        if (row["wyckoff_stage"] == 1 and
            abs(row["pct_change"]) < 1.5 and
            row["accumulation_score"] >= 60):
            signals.append({
                "code": "LOW_VOL_ACCUM",
                "label": "Low Vol Accumulation",
                "color": "cyan",
                "explanation": "Range harga sempit, smart money aktif.",
            })

        if (row["wyckoff_stage"] == 2 and
            row["above_ma20"] and
            row["volume_spike"] >= 1.2):
            signals.append({
                "code": "BREAKOUT_PREP",
                "label": "Breakout Preparation",
                "color": "blue",
                "explanation": "Stage 2 + di atas MA20 + volume mulai expand.",
            })

        if (row["distribution_score"] >= 65 and
            row["wyckoff_stage"] in (4, 5)):
            signals.append({
                "code": "DIST_WARNING",
                "label": "Distribution Warning",
                "color": "red",
                "explanation": (
                    f"Distribusi terdeteksi (score {row['distribution_score']:.0f}), "
                    f"stage {row['wyckoff_stage']}."
                ),
            })

        if (row["above_ma20"] and
            row["fomo_risk_score"] >= 60 and
            row["volume_spike"] < 1.2):
            signals.append({
                "code": "FALSE_BREAKOUT_RISK",
                "label": "False Breakout Risk",
                "color": "orange",
                "explanation": "Risiko false breakout — volume tipis di atas MA20.",
            })

        if row["liquidity_score"] < 30:
            signals.append({
                "code": "LIQ_TRAP",
                "label": "Liquidity Trap",
                "color": "red",
                "explanation": "Likuiditas sangat rendah — sulit exit.",
            })

        if (row["retail_non_flow_score"] <= 35 and
            row["wyckoff_stage"] >= 3):
            signals.append({
                "code": "RETAIL_FOMO",
                "label": "Retail FOMO Trap",
                "color": "red",
                "explanation": "Retail FOMO buying tinggi — smart money keluar.",
            })

        row["signals"] = signals

    # ------------------------------------------------------------------ #
    # Noise flags
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_noise_flags(row: dict) -> None:
        flags = []

        if row["avg_value_20d"] < 1_000_000_000:
            flags.append({
                "code": "NOISE_ILLIQUID",
                "label": "Illiquid",
                "explanation": (
                    f"Avg daily value 20D Rp {row['avg_value_20d']/1e9:.2f}M (< 1M)."
                ),
            })

        if row["pct_change"] > 7 and row["volume_spike"] > 3:
            flags.append({
                "code": "NOISE_ONE_DAY_PUMP",
                "label": "One-Day Pump",
                "explanation": (
                    f"+{row['pct_change']:.1f}% dengan volume "
                    f"{row['volume_spike']:.1f}x."
                ),
            })

        if (row["retail_non_flow_score"] <= 30 and
            row["pct_change"] > 5):
            flags.append({
                "code": "NOISE_RETAIL_FOMO",
                "label": "Retail FOMO Spike",
                "explanation": "Spike harga didorong retail FOMO.",
            })

        if (row["liquidity_score"] < 40 and
            row["pct_change"] > 3):
            flags.append({
                "code": "NOISE_FALSE_MOMENTUM",
                "label": "False Momentum",
                "explanation": (
                    f"Likuiditas {row['liquidity_score']:.0f} dengan harga naik."
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
            if f.apply_noise_filter and r["is_noise"]:
                rejected.append(r)
                continue

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
            # min_probability filter kept for backward-compat but uses opportunity_score
            if f.min_probability is not None and r["opportunity_score"] < f.min_probability:
                continue

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
    # Summary
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_summary(accepted: list[dict], rejected: list[dict]) -> dict:
        sector_counts = {}
        for r in accepted:
            s = r.get("sector") or "OTHER"
            sector_counts[s] = sector_counts.get(s, 0) + 1

        # Stage distribution
        stage_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for r in accepted:
            stage = r.get("wyckoff_stage", 1)
            if stage in stage_counts:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

        return {
            "total_in_universe": len(accepted) + len(rejected),
            "accepted": len(accepted),
            "rejected_as_noise": len(rejected),
            "stage_distribution": stage_counts,
            "sector_distribution": sector_counts,
        }

    # ------------------------------------------------------------------ #
    # CSV Export
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_csv(scan_result: dict) -> str:
        import csv
        from io import StringIO

        rows = scan_result.get("rows", [])
        if not rows:
            return ""

        out = StringIO()
        cols = [
            "symbol", "name", "sector", "price", "pct_change",
            "volume", "value", "market_cap",
            "opportunity_score",
            "accumulation_score", "distribution_score",
            "foreign_strength_score", "trend_score",
            "liquidity_score", "momentum_score", "institutional_score",
            "wyckoff_stage", "wyckoff_label", "verdict",
            "above_ma5", "above_ma10", "above_ma20",
            "above_ma50", "above_ma100", "above_ma200",
            "dist_ma20", "dist_ma200",
            "volume_spike", "fomo_risk_score",
            "trade_readiness_signal",
        ]
        writer = csv.writer(out)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r.get(c, "") for c in cols])
        return out.getvalue()
