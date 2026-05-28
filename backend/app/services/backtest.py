"""
Backtesting Engine.

Walk-forward backtest of screener strategies over historical data.

Strategy spec:
    {
        "min_foreign_score": 60,
        "min_momentum_score": 50,
        "min_volume_anomaly": 1.2,
        "hold_days": 20,
        "max_positions": 5,
        "stop_loss_pct": -8.0,           # optional
        "take_profit_pct": 15.0,         # optional
        "rebalance_every_days": 5,       # how often we run the screener
    }

Output:
    {
        "trades": [...],
        "metrics": {win_rate, avg_return, median_return, max_dd, sharpe, ...},
        "equity_curve": [{date, equity}, ...],
        "monthly_returns": [{month, return_pct}],
    }

Composite score is recomputed from raw data (candles + foreign_flow + broker_summary)
for each historical date — no dependency on AIScore table.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Candle, ForeignFlow, BrokerDailySummary, Symbol, Broker


@dataclass
class StrategySpec:
    min_foreign_score: float = 60.0
    min_momentum_score: float = 50.0
    min_volume_anomaly: float = 1.0
    min_inventory_score: float = 0.0      # bandar inventory growth
    min_composite_score: float = 60.0
    sector: Optional[str] = None
    hold_days: int = 20
    max_positions: int = 5
    stop_loss_pct: Optional[float] = None        # e.g. -8.0
    take_profit_pct: Optional[float] = None      # e.g. 15.0
    rebalance_every_days: int = 5
    initial_capital: float = 100_000_000.0       # Rp 100M
    commission_pct: float = 0.0015               # 0.15% per side (typical IDX)


class BacktestEngine:

    def __init__(self, db: Session):
        self.db = db
        # Cache broker classification
        brokers = self.db.query(Broker).all()
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }

    # ------------------------------------------------------------------ #
    # Public entrypoint
    # ------------------------------------------------------------------ #

    def run(
        self,
        strategy: StrategySpec,
        start_date: date,
        end_date: Optional[date] = None,
        symbols: Optional[list[str]] = None,
    ) -> dict:
        if end_date is None:
            end_date = self.db.query(func.max(Candle.date)).scalar()

        # 1. Load all data into memory once
        ds = self._load_dataset(start_date, end_date, symbols, strategy.sector)
        if ds["candles"].empty:
            return {"error": "No candle data in range"}

        # 2. Compute daily score panel for each symbol
        score_panel = self._compute_score_panel(ds)

        # 3. Walk forward, generate trades
        trades = self._simulate(strategy, score_panel, ds["candles"])

        # 4. Compute metrics & equity curve
        metrics = self._compute_metrics(trades, strategy)
        equity = self._equity_curve(trades, strategy)
        monthly = self._monthly_returns(equity)

        return {
            "strategy": asdict(strategy),
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "metrics": metrics,
            "trades": [self._serialize_trade(t) for t in trades],
            "equity_curve": equity,
            "monthly_returns": monthly,
        }

    # ------------------------------------------------------------------ #
    # Dataset loader
    # ------------------------------------------------------------------ #

    def _load_dataset(
        self,
        start_date: date,
        end_date: date,
        symbols: Optional[list[str]],
        sector: Optional[str],
    ) -> dict:
        # Symbol filter
        sym_q = self.db.query(Symbol)
        if symbols:
            sym_q = sym_q.filter(Symbol.code.in_(symbols))
        if sector:
            sym_q = sym_q.filter(Symbol.sector == sector)
        all_symbols = [s.code for s in sym_q.all()]
        if not all_symbols:
            return {"candles": pd.DataFrame(), "foreign": pd.DataFrame(),
                    "brokers": pd.DataFrame()}

        # Need extra lookback for rolling windows
        load_start = start_date - timedelta(days=60)

        # Candles
        c_rows = (
            self.db.query(Candle)
            .filter(
                Candle.symbol.in_(all_symbols),
                Candle.date >= load_start,
                Candle.date <= end_date,
            )
            .all()
        )
        cdf = pd.DataFrame([{
            "date": c.date, "symbol": c.symbol,
            "close": c.close, "open": c.open, "high": c.high, "low": c.low,
            "volume": c.volume, "value": c.value,
        } for c in c_rows])

        # Foreign flow
        ff_rows = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol.in_(all_symbols),
                ForeignFlow.date >= load_start,
                ForeignFlow.date <= end_date,
            )
            .all()
        )
        ffdf = pd.DataFrame([{
            "date": f.date, "symbol": f.symbol,
            "foreign_net": f.foreign_net_value,
            "foreign_buy": f.foreign_buy_value,
            "foreign_sell": f.foreign_sell_value,
        } for f in ff_rows])

        # Broker summary (only bandar brokers, aggregated per symbol/date)
        bds_rows = (
            self.db.query(
                BrokerDailySummary.date,
                BrokerDailySummary.symbol,
                BrokerDailySummary.broker_code,
                BrokerDailySummary.net_lot,
                BrokerDailySummary.net_value,
            )
            .filter(
                BrokerDailySummary.symbol.in_(all_symbols),
                BrokerDailySummary.date >= load_start,
                BrokerDailySummary.date <= end_date,
                BrokerDailySummary.broker_code.in_(self.bandar_set),
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol,
            "bandar_net_lot": r.net_lot, "bandar_net_value": r.net_value,
        } for r in bds_rows])
        if not bdf.empty:
            bdf = bdf.groupby(["date", "symbol"], as_index=False).sum()

        return {"candles": cdf, "foreign": ffdf, "brokers": bdf,
                "symbols": all_symbols, "load_start": load_start}

    # ------------------------------------------------------------------ #
    # Score panel computation (vectorized rolling)
    # ------------------------------------------------------------------ #

    def _compute_score_panel(self, ds: dict) -> pd.DataFrame:
        """
        Returns wide panel with one row per (date, symbol) and columns:
        foreign_score, momentum_score, volume_score, inventory_score, composite_score
        """
        cdf = ds["candles"].sort_values(["symbol", "date"]).copy()
        ffdf = ds["foreign"]
        bdf = ds["brokers"]

        # Per-symbol rolling computations on candles
        cdf["volume_ma20"] = cdf.groupby("symbol")["volume"].transform(
            lambda s: s.rolling(20, min_periods=5).mean()
        )
        cdf["close_20d_ago"] = cdf.groupby("symbol")["close"].shift(20)
        cdf["pct_change_20d"] = (cdf["close"] / cdf["close_20d_ago"] - 1) * 100
        cdf["volume_anomaly"] = cdf["volume"] / cdf["volume_ma20"]
        cdf["avg_value_20d"] = cdf.groupby("symbol")["value"].transform(
            lambda s: s.rolling(20, min_periods=5).mean()
        )

        # Foreign net 20D rolling
        if not ffdf.empty:
            ff = ffdf.sort_values(["symbol", "date"]).copy()
            ff["foreign_net_20d"] = ff.groupby("symbol")["foreign_net"].transform(
                lambda s: s.rolling(20, min_periods=5).sum()
            )
            cdf = cdf.merge(
                ff[["date", "symbol", "foreign_net", "foreign_net_20d"]],
                on=["date", "symbol"],
                how="left",
            )
        else:
            cdf["foreign_net"] = 0
            cdf["foreign_net_20d"] = 0

        # Bandar inventory growth (rolling 20D net)
        if not bdf.empty:
            bd = bdf.sort_values(["symbol", "date"]).copy()
            bd["bandar_net_20d"] = bd.groupby("symbol")["bandar_net_lot"].transform(
                lambda s: s.rolling(20, min_periods=5).sum()
            )
            cdf = cdf.merge(
                bd[["date", "symbol", "bandar_net_lot", "bandar_net_20d"]],
                on=["date", "symbol"],
                how="left",
            )
        else:
            cdf["bandar_net_lot"] = 0
            cdf["bandar_net_20d"] = 0

        cdf = cdf.fillna(0)

        # ─── Score normalizations ────────────────────────────────────
        # Foreign Score: foreign_net_20d normalized by avg_value_20d
        cdf["foreign_score"] = (
            (cdf["foreign_net_20d"] / cdf["avg_value_20d"].replace(0, np.nan) * 50 + 50)
            .clip(0, 100)
            .fillna(50)
        )

        # Momentum: 20D pct change → 50 + pct*3
        cdf["momentum_score"] = (50 + cdf["pct_change_20d"] * 3).clip(0, 100)

        # Volume: ratio − 1 mapped 0-100
        cdf["volume_score"] = (
            (cdf["volume_anomaly"] - 1) * 50 + 50
        ).clip(0, 100)

        # Inventory: bandar_net_20d normalized vs avg daily lot proxy
        # Use avg_value_20d/close as lot proxy (approximate)
        lot_proxy = cdf["avg_value_20d"] / (cdf["close"].replace(0, np.nan) * 100)
        cdf["inventory_score"] = (
            (cdf["bandar_net_20d"] / (lot_proxy * 20).replace(0, np.nan) * 50 + 50)
            .clip(0, 100)
            .fillna(50)
        )

        # Composite (weighted average)
        cdf["composite_score"] = (
            cdf["foreign_score"] * 0.30 +
            cdf["momentum_score"] * 0.25 +
            cdf["volume_score"] * 0.20 +
            cdf["inventory_score"] * 0.25
        )

        return cdf

    # ------------------------------------------------------------------ #
    # Simulator
    # ------------------------------------------------------------------ #

    def _simulate(
        self,
        strategy: StrategySpec,
        panel: pd.DataFrame,
        candles_full: pd.DataFrame,
    ) -> list[dict]:
        """Walk-forward: rebalance every N days, take top-K signals."""
        if panel.empty:
            return []

        # Use unique trading dates from panel, sorted
        trading_dates = sorted(panel["date"].unique())
        if not trading_dates:
            return []

        trades = []
        date_idx = 0
        last_rebalance_idx = -strategy.rebalance_every_days  # force first rebalance

        # Build close lookup: (date, symbol) → close
        close_lookup = candles_full.set_index(
            ["date", "symbol"]
        )["close"].to_dict()

        while date_idx < len(trading_dates):
            current_date = trading_dates[date_idx]

            if date_idx - last_rebalance_idx >= strategy.rebalance_every_days:
                # Run screener for this date
                today = panel[panel["date"] == current_date]
                qualified = today[
                    (today["foreign_score"] >= strategy.min_foreign_score) &
                    (today["momentum_score"] >= strategy.min_momentum_score) &
                    (today["volume_anomaly"] >= strategy.min_volume_anomaly) &
                    (today["inventory_score"] >= strategy.min_inventory_score) &
                    (today["composite_score"] >= strategy.min_composite_score)
                ].copy()
                qualified = qualified.sort_values(
                    "composite_score", ascending=False
                ).head(strategy.max_positions)

                # Open trades for each qualified symbol
                for _, row in qualified.iterrows():
                    entry_date = current_date
                    entry_price = float(row["close"])
                    if entry_price <= 0:
                        continue

                    # Determine exit using fixed hold or stop/target
                    exit_date, exit_price, exit_reason = self._compute_exit(
                        symbol=row["symbol"],
                        entry_date=entry_date,
                        entry_price=entry_price,
                        strategy=strategy,
                        trading_dates=trading_dates,
                        close_lookup=close_lookup,
                        date_idx=date_idx,
                    )
                    if exit_date is None:
                        continue  # hit end of data

                    gross_return_pct = (exit_price / entry_price - 1) * 100
                    net_return_pct = gross_return_pct - (
                        strategy.commission_pct * 100 * 2
                    )

                    trades.append({
                        "symbol": row["symbol"],
                        "entry_date": entry_date,
                        "entry_price": entry_price,
                        "exit_date": exit_date,
                        "exit_price": exit_price,
                        "gross_return_pct": gross_return_pct,
                        "return_pct": net_return_pct,
                        "exit_reason": exit_reason,
                        "score_at_entry": float(row["composite_score"]),
                    })
                last_rebalance_idx = date_idx

            date_idx += 1

        return trades

    @staticmethod
    def _compute_exit(
        symbol: str,
        entry_date,
        entry_price: float,
        strategy: StrategySpec,
        trading_dates: list,
        close_lookup: dict,
        date_idx: int,
    ):
        """Walk forward day-by-day, exit on first trigger."""
        target_idx = min(
            date_idx + strategy.hold_days,
            len(trading_dates) - 1,
        )
        for j in range(date_idx + 1, target_idx + 1):
            d = trading_dates[j]
            price = close_lookup.get((d, symbol))
            if price is None or price <= 0:
                continue
            return_pct = (price / entry_price - 1) * 100

            if (strategy.stop_loss_pct is not None
                    and return_pct <= strategy.stop_loss_pct):
                return d, price, "STOP_LOSS"

            if (strategy.take_profit_pct is not None
                    and return_pct >= strategy.take_profit_pct):
                return d, price, "TAKE_PROFIT"

            if j == target_idx:
                return d, price, "TIME_EXIT"

        return None, None, None

    # ------------------------------------------------------------------ #
    # Metrics
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_metrics(trades: list[dict], strategy: StrategySpec) -> dict:
        if not trades:
            return {
                "total_trades": 0, "win_rate_pct": 0, "avg_return_pct": 0,
                "median_return_pct": 0, "best_trade_pct": 0, "worst_trade_pct": 0,
                "avg_win_pct": 0, "avg_loss_pct": 0, "profit_factor": 0,
                "sharpe_ratio": 0, "max_drawdown_pct": 0, "total_return_pct": 0,
                "exit_breakdown": {},
            }

        df = pd.DataFrame(trades)
        wins = df[df["return_pct"] > 0]
        losses = df[df["return_pct"] <= 0]

        win_rate = len(wins) / len(df) * 100
        avg_ret = df["return_pct"].mean()
        median_ret = df["return_pct"].median()
        avg_win = wins["return_pct"].mean() if not wins.empty else 0.0
        avg_loss = losses["return_pct"].mean() if not losses.empty else 0.0

        gross_profit = wins["return_pct"].sum()
        gross_loss = abs(losses["return_pct"].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe from per-trade returns (simplified — annualization factor)
        if df["return_pct"].std() > 0:
            avg_hold = strategy.hold_days
            trades_per_year = 252 / max(avg_hold, 1)
            sharpe = (
                df["return_pct"].mean() / df["return_pct"].std()
                * np.sqrt(trades_per_year)
            )
        else:
            sharpe = 0.0

        # Total compounded return (sequential trades approximation)
        cumulative = (1 + df["return_pct"] / 100).cumprod()
        total_return_pct = (cumulative.iloc[-1] - 1) * 100

        # Max drawdown of cumulative equity
        peak = cumulative.cummax()
        dd = (cumulative / peak - 1) * 100
        max_dd = dd.min()

        exit_counts = df["exit_reason"].value_counts().to_dict()

        return {
            "total_trades": int(len(df)),
            "winners": int(len(wins)),
            "losers": int(len(losses)),
            "win_rate_pct": round(win_rate, 2),
            "avg_return_pct": round(float(avg_ret), 2),
            "median_return_pct": round(float(median_ret), 2),
            "best_trade_pct": round(float(df["return_pct"].max()), 2),
            "worst_trade_pct": round(float(df["return_pct"].min()), 2),
            "avg_win_pct": round(float(avg_win), 2),
            "avg_loss_pct": round(float(avg_loss), 2),
            "profit_factor": round(float(profit_factor), 2),
            "sharpe_ratio": round(float(sharpe), 2),
            "max_drawdown_pct": round(float(max_dd), 2),
            "total_return_pct": round(float(total_return_pct), 2),
            "exit_breakdown": {k: int(v) for k, v in exit_counts.items()},
        }

    # ------------------------------------------------------------------ #
    # Equity curve & monthly returns
    # ------------------------------------------------------------------ #

    def _equity_curve(
        self,
        trades: list[dict],
        strategy: StrategySpec,
    ) -> list[dict]:
        if not trades:
            return []

        df = pd.DataFrame(trades).sort_values("exit_date")
        equity = strategy.initial_capital
        # Each trade contributes equally based on max_positions
        per_trade_capital = equity / strategy.max_positions
        curve = []

        # Build portfolio-level equity by summing per-trade contributions
        # by exit date (simplification: assume equal capital weight)
        for _, t in df.iterrows():
            pnl = per_trade_capital * (t["return_pct"] / 100)
            equity += pnl
            curve.append({
                "date": t["exit_date"].isoformat(),
                "equity": round(equity, 2),
                "trade_return_pct": round(t["return_pct"], 2),
                "symbol": t["symbol"],
            })
        return curve

    @staticmethod
    def _monthly_returns(equity_curve: list[dict]) -> list[dict]:
        if not equity_curve:
            return []
        df = pd.DataFrame(equity_curve)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        # Last equity value per month
        monthly = df["equity"].resample("ME").last()
        monthly_pct = monthly.pct_change().fillna(0) * 100
        return [
            {"month": idx.strftime("%Y-%m"), "return_pct": round(float(v), 2)}
            for idx, v in monthly_pct.items()
        ]

    @staticmethod
    def _serialize_trade(t: dict) -> dict:
        return {
            **t,
            "entry_date": t["entry_date"].isoformat() if hasattr(t["entry_date"], "isoformat") else t["entry_date"],
            "exit_date": t["exit_date"].isoformat() if hasattr(t["exit_date"], "isoformat") else t["exit_date"],
            "entry_price": round(float(t["entry_price"]), 2),
            "exit_price": round(float(t["exit_price"]), 2),
            "gross_return_pct": round(float(t["gross_return_pct"]), 2),
            "return_pct": round(float(t["return_pct"]), 2),
            "score_at_entry": round(float(t["score_at_entry"]), 1),
        }


# ============================================================
# Preset strategies
# ============================================================

PRESET_STRATEGIES = [
    {
        "id": "smart_money_long",
        "name": "Smart Money Long",
        "description": "High composite score + foreign inflow, hold 20D",
        "spec": {
            "min_composite_score": 70,
            "min_foreign_score": 60,
            "min_momentum_score": 55,
            "min_volume_anomaly": 1.0,
            "hold_days": 20,
            "max_positions": 5,
            "rebalance_every_days": 5,
            "stop_loss_pct": -8.0,
            "take_profit_pct": 18.0,
        },
    },
    {
        "id": "stealth_accum_then_breakout",
        "name": "Stealth → Breakout",
        "description": "High inventory score, momentum just turning, longer hold",
        "spec": {
            "min_composite_score": 60,
            "min_foreign_score": 55,
            "min_momentum_score": 45,
            "min_inventory_score": 65,
            "min_volume_anomaly": 0.8,
            "hold_days": 30,
            "max_positions": 4,
            "rebalance_every_days": 10,
            "stop_loss_pct": -10.0,
        },
    },
    {
        "id": "momentum_breakout",
        "name": "Momentum Breakout",
        "description": "High momentum + volume spike, short hold",
        "spec": {
            "min_composite_score": 65,
            "min_momentum_score": 70,
            "min_volume_anomaly": 1.5,
            "hold_days": 10,
            "max_positions": 5,
            "rebalance_every_days": 3,
            "stop_loss_pct": -6.0,
            "take_profit_pct": 12.0,
        },
    },
    {
        "id": "conservative_blue_chip",
        "name": "Conservative Blue Chip",
        "description": "Lower thresholds, longer hold, BANK sector only",
        "spec": {
            "min_composite_score": 55,
            "min_foreign_score": 55,
            "min_momentum_score": 50,
            "min_volume_anomaly": 1.0,
            "hold_days": 40,
            "max_positions": 3,
            "rebalance_every_days": 10,
            "sector": "BANK",
            "stop_loss_pct": -7.0,
        },
    },
]
