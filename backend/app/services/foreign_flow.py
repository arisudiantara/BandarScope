"""
Foreign Flow Service.

Tracks foreign net buy/sell with divergence detection.
"""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
from sqlalchemy.orm import Session

from app.models import ForeignFlow, Candle


class ForeignFlowService:

    def __init__(self, db: Session):
        self.db = db

    def get_flow(self, symbol: str, days: int = 90) -> dict:
        """Daily foreign flow + cumulative + divergence detection."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        rows = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol == symbol,
                ForeignFlow.date >= start_date,
                ForeignFlow.date <= end_date,
            )
            .order_by(ForeignFlow.date)
            .all()
        )

        if not rows:
            return {"symbol": symbol, "data": [], "summary": {}}

        df = pd.DataFrame([{
            "date": r.date,
            "buy": r.foreign_buy_value,
            "sell": r.foreign_sell_value,
            "net": r.foreign_net_value,
            "cum": r.cumulative_net,
            "price": r.close_price,
        } for r in rows])

        # Re-compute cumulative based on the filtered window
        df["cum_window"] = df["net"].cumsum()

        # Divergence detection (last 20 days)
        divergence = self._detect_divergence(df)

        # Summary
        summary = {
            "net_total": int(df["net"].sum()),
            "buy_total": int(df["buy"].sum()),
            "sell_total": int(df["sell"].sum()),
            "net_5d": int(df["net"].tail(5).sum()),
            "net_20d": int(df["net"].tail(20).sum()),
            "buy_days": int((df["net"] > 0).sum()),
            "sell_days": int((df["net"] < 0).sum()),
            "divergence": divergence,
        }

        return {
            "symbol": symbol,
            "period_days": days,
            "data": [
                {
                    "date": row["date"].isoformat(),
                    "buy": int(row["buy"]),
                    "sell": int(row["sell"]),
                    "net": int(row["net"]),
                    "cumulative": int(row["cum_window"]),
                    "price": float(row["price"]),
                }
                for _, row in df.iterrows()
            ],
            "summary": summary,
        }

    @staticmethod
    def _detect_divergence(df: pd.DataFrame, window: int = 20) -> dict:
        """
        Detect price vs flow divergence.

        BULLISH_DIVERGENCE: price down/flat, foreign cumulative up
        BEARISH_DIVERGENCE: price up, foreign cumulative down
        """
        if len(df) < window:
            return {"type": None, "strength": 0}

        recent = df.tail(window)
        price_change = (recent["price"].iloc[-1] / recent["price"].iloc[0] - 1) * 100
        flow_change = recent["net"].sum()
        flow_norm = flow_change / max(abs(recent["buy"].sum()) + abs(recent["sell"].sum()), 1)

        div_type = None
        strength = 0.0

        if price_change < -1.5 and flow_norm > 0.05:
            div_type = "BULLISH_DIVERGENCE"
            strength = abs(price_change) + (flow_norm * 100)
        elif price_change > 2.0 and flow_norm < -0.05:
            div_type = "BEARISH_DIVERGENCE"
            strength = price_change + abs(flow_norm * 100)

        return {
            "type": div_type,
            "strength": round(strength, 2),
            "price_change_pct": round(price_change, 2),
            "flow_normalized": round(flow_norm * 100, 2),
            "interpretation": {
                "BULLISH_DIVERGENCE": "Foreign accumulating despite weak price — potential bottoming.",
                "BEARISH_DIVERGENCE": "Foreign selling into strength — potential top forming.",
                None: "No significant divergence detected.",
            }[div_type],
        }
