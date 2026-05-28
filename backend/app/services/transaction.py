"""
Transaction Chart Service.

Multi-month accumulation/distribution analysis with money flow vs price
divergence detection.

Includes multi-entity flow analysis: Foreign / Institutional / Market Maker /
Retail / Zombie — to see who is accumulating and who is distributing
side-by-side over the same timeframe.
"""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

from app.models import ForeignFlow, Candle, BrokerDailySummary, Broker


# Entity types we expose in the multi-entity chart
ENTITIES = ["foreign", "institutional", "market_maker", "retail", "zombie"]

ENTITY_DISPLAY = {
    "foreign":       {"label": "Foreign",       "color": "#3b82f6"},
    "institutional": {"label": "Institutional", "color": "#a855f7"},
    "market_maker":  {"label": "Market Maker",  "color": "#eab308"},
    "retail":        {"label": "Retail",        "color": "#22c55e"},
    "zombie":        {"label": "Zombie",        "color": "#ec4899"},
}


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

    # ------------------------------------------------------------------ #
    # Multi-Entity Flow Chart
    # ------------------------------------------------------------------ #

    def multi_entity_chart(self, symbol: str, days: int = 90) -> dict:
        """
        Show side-by-side cumulative flow per entity (Foreign, Institutional,
        Market Maker, Retail, Zombie) plus daily net per entity.

        Identifies which entity is accumulating vs distributing.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Build broker → entity map
        brokers = self.db.query(Broker).all()
        entity_map = {}
        for b in brokers:
            if b.is_foreign:
                entity_map[b.code] = "foreign"
            elif b.cluster_label == "institutional":
                entity_map[b.code] = "institutional"
            elif b.cluster_label == "market_maker":
                entity_map[b.code] = "market_maker"
            elif b.cluster_label == "retail":
                entity_map[b.code] = "retail"
            elif b.cluster_label == "zombie":
                entity_map[b.code] = "zombie"
            else:
                entity_map[b.code] = "other"

        # Fetch all broker activity in window
        rows = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .all()
        )
        if not rows:
            return {"symbol": symbol, "entities": [], "daily_data": []}

        df = pd.DataFrame([{
            "date": r.date,
            "broker": r.broker_code,
            "buy_value": r.buy_value or 0,
            "sell_value": r.sell_value or 0,
            "net_value": r.net_value or 0,
            "net_lot": r.net_lot or 0,
        } for r in rows])
        df["entity"] = df["broker"].map(entity_map).fillna("other")

        # Aggregate per (date, entity)
        per_entity_daily = (
            df.groupby(["date", "entity"], as_index=False)
              .agg(
                  buy_value=("buy_value", "sum"),
                  sell_value=("sell_value", "sum"),
                  net_value=("net_value", "sum"),
                  net_lot=("net_lot", "sum"),
              )
        )

        # Get price overlay
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
        price_lookup = {c.date: c.close for c in candles}

        # Build entity series
        entities_data = []
        for entity in ENTITIES:
            sub = per_entity_daily[per_entity_daily["entity"] == entity].sort_values("date")
            if sub.empty:
                # Empty placeholder
                entities_data.append({
                    "entity": entity,
                    "label": ENTITY_DISPLAY[entity]["label"],
                    "color": ENTITY_DISPLAY[entity]["color"],
                    "total_buy": 0,
                    "total_sell": 0,
                    "total_net": 0,
                    "total_net_lot": 0,
                    "behavior": "INACTIVE",
                    "data": [],
                })
                continue

            sub = sub.copy()
            sub["cumulative_net"] = sub["net_value"].cumsum()

            total_buy = int(sub["buy_value"].sum())
            total_sell = int(sub["sell_value"].sum())
            total_net = int(sub["net_value"].sum())
            total_net_lot = int(sub["net_lot"].sum())

            # Behavior classification
            buy_days = int((sub["net_value"] > 0).sum())
            total_days = len(sub)
            buy_ratio = buy_days / max(total_days, 1)
            avg_daily_value = (total_buy + total_sell) / max(total_days * 2, 1)

            behavior = "NEUTRAL"
            if total_net > avg_daily_value * 5 and buy_ratio > 0.6:
                behavior = "STRONG_ACCUMULATION"
            elif total_net > avg_daily_value * 2:
                behavior = "ACCUMULATION"
            elif total_net < -avg_daily_value * 5 and buy_ratio < 0.4:
                behavior = "STRONG_DISTRIBUTION"
            elif total_net < -avg_daily_value * 2:
                behavior = "DISTRIBUTION"

            entities_data.append({
                "entity": entity,
                "label": ENTITY_DISPLAY[entity]["label"],
                "color": ENTITY_DISPLAY[entity]["color"],
                "total_buy": total_buy,
                "total_sell": total_sell,
                "total_net": total_net,
                "total_net_lot": total_net_lot,
                "buy_days": buy_days,
                "total_days": total_days,
                "behavior": behavior,
                "data": [
                    {
                        "date": row["date"].isoformat(),
                        "buy": int(row["buy_value"]),
                        "sell": int(row["sell_value"]),
                        "net": int(row["net_value"]),
                        "cumulative": int(row["cumulative_net"]),
                    }
                    for _, row in sub.iterrows()
                ],
            })

        # Build aligned daily array (date × all entities) for stacked chart
        all_dates = sorted(per_entity_daily["date"].unique())
        daily_aligned = []
        for d in all_dates:
            row = {
                "date": d.isoformat(),
                "price": price_lookup.get(d, 0),
            }
            for entity in ENTITIES:
                sub = per_entity_daily[
                    (per_entity_daily["date"] == d)
                    & (per_entity_daily["entity"] == entity)
                ]
                row[f"{entity}_net"] = int(sub["net_value"].iloc[0]) if not sub.empty else 0
            daily_aligned.append(row)

        return {
            "symbol": symbol,
            "period_days": days,
            "entities": entities_data,
            "daily_data": daily_aligned,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

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
