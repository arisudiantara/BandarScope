"""
Transaction Chart Service.

Multi-month accumulation/distribution analysis with money flow vs price
divergence detection.
"""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.models import ForeignFlow, Candle, BrokerDailySummary


class TransactionService:

    def __init__(self, db: Session):
        self.db = db

    def transaction_chart(self, symbol: str, days: int = 120) -> dict:
        """
        Multi-month transaction chart:
        - Daily price
        - Foreign net buy/sell bars
        - Cumulative foreign net line
        - Money flow index
        - Divergence markers
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Foreign flow + close
        ff = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol == symbol,
                ForeignFlow.date >= start_date,
            )
            .order_by(ForeignFlow.date)
            .all()
        )
        if not ff:
            return {"symbol": symbol, "data": []}

        df = pd.DataFrame([{
            "date": r.date,
            "buy": r.foreign_buy_value,
            "sell": r.foreign_sell_value,
            "net": r.foreign_net_value,
            "price": r.close_price,
        } for r in ff])

        # Cumulative foreign net (window-rebased)
        df["cum_foreign"] = df["net"].cumsum()

        # Money Flow Index (custom, simplified):
        # MFI = 100 * (positive_flow / (positive_flow + negative_flow)) over 14D
        df["pos_flow"] = df["net"].clip(lower=0)
        df["neg_flow"] = (-df["net"]).clip(lower=0)
        win = 14
        pos_sum = df["pos_flow"].rolling(win, min_periods=1).sum()
        neg_sum = df["neg_flow"].rolling(win, min_periods=1).sum()
        df["mfi"] = (100 * pos_sum / (pos_sum + neg_sum + 1e-9)).round(2)

        # Detect divergences using price highs/lows vs cum_foreign highs/lows
        markers = self._find_divergences(df)

        # Hidden accumulation: price flat range but cumulative foreign rises monotonically
        hidden_accum = self._detect_hidden_accumulation(df)

        return {
            "symbol": symbol,
            "period_days": days,
            "data": [
                {
                    "date": row["date"].isoformat(),
                    "price": float(row["price"]),
                    "buy": int(row["buy"]),
                    "sell": int(row["sell"]),
                    "net": int(row["net"]),
                    "cum_foreign": int(row["cum_foreign"]),
                    "mfi": float(row["mfi"]) if not pd.isna(row["mfi"]) else 50.0,
                }
                for _, row in df.iterrows()
            ],
            "divergence_markers": markers,
            "hidden_accumulation": hidden_accum,
        }

    @staticmethod
    def _find_divergences(df: pd.DataFrame) -> list[dict]:
        """Find points where price made low but cum_foreign made higher low (& vice versa)."""
        markers = []
        if len(df) < 30:
            return markers

        # Look at 30D windows
        for i in range(30, len(df), 15):
            window = df.iloc[max(0, i - 30):i]
            price_low_idx = window["price"].idxmin()
            price_high_idx = window["price"].idxmax()
            cum_low_idx = window["cum_foreign"].idxmin()
            cum_high_idx = window["cum_foreign"].idxmax()

            # Bullish divergence: price low after cum_foreign low
            if price_low_idx > cum_low_idx and (price_low_idx - cum_low_idx) >= 5:
                row = df.loc[price_low_idx]
                markers.append({
                    "date": row["date"].isoformat(),
                    "type": "BULLISH_DIVERGENCE",
                    "price": float(row["price"]),
                })

            # Bearish divergence: price high after cum_foreign high
            if price_high_idx > cum_high_idx and (price_high_idx - cum_high_idx) >= 5:
                row = df.loc[price_high_idx]
                markers.append({
                    "date": row["date"].isoformat(),
                    "type": "BEARISH_DIVERGENCE",
                    "price": float(row["price"]),
                })

        # Dedup
        seen = set()
        unique = []
        for m in markers:
            key = (m["date"], m["type"])
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    @staticmethod
    def _detect_hidden_accumulation(df: pd.DataFrame) -> dict:
        """Last 60D: price range-bound but cum_foreign rising consistently."""
        if len(df) < 60:
            return {"detected": False}

        recent = df.tail(60).copy()
        price_range = (recent["price"].max() - recent["price"].min()) / recent["price"].mean() * 100
        cum_change = recent["cum_foreign"].iloc[-1] - recent["cum_foreign"].iloc[0]
        avg_daily_value = (recent["buy"].mean() + recent["sell"].mean())

        detected = (
            price_range < 12.0
            and cum_change > 0
            and cum_change > avg_daily_value * 5
        )

        return {
            "detected": detected,
            "price_range_pct": round(float(price_range), 2),
            "cum_foreign_growth": int(cum_change),
            "interpretation": (
                "Hidden accumulation: price is consolidating but foreign cumulative net "
                "is growing significantly. Watch for breakout."
                if detected else
                "No hidden accumulation pattern."
            ),
        }
