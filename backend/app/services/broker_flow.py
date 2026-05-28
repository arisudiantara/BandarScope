"""
Broker Flow Service.

Core analytics:
- Inventory line per broker (cumulative net lot)
- Top accumulators / distributors per stock
- Broker behavior classification
- Stealth accumulation detection (price flat/down + inventory rising)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import BrokerDailySummary, Candle, Broker


class BrokerFlowService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Inventory lines
    # ------------------------------------------------------------------ #

    def inventory_lines(
        self,
        symbol: str,
        days: int = 60,
        top_n_brokers: int = 5,
    ) -> dict:
        """
        Compute cumulative inventory line for top N brokers.

        Inventory[t] = inventory[t-1] + (buy_lot[t] - sell_lot[t])

        Returns lines for the top N most-active brokers (by absolute net value).
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Step 1: aggregate top brokers by absolute net value over the period
        top_brokers_q = (
            self.db.query(
                BrokerDailySummary.broker_code,
                func.sum(BrokerDailySummary.net_value).label("total_net"),
                func.sum(BrokerDailySummary.buy_lot).label("total_buy"),
                func.sum(BrokerDailySummary.sell_lot).label("total_sell"),
            )
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.broker_code)
            .all()
        )

        # Sort by absolute net value and take top N
        sorted_brokers = sorted(
            top_brokers_q,
            key=lambda x: abs(x.total_net or 0),
            reverse=True,
        )[:top_n_brokers]
        top_codes = [b.broker_code for b in sorted_brokers]

        if not top_codes:
            return {"symbol": symbol, "lines": [], "price_series": []}

        # Step 2: fetch daily series for those brokers
        daily_q = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.broker_code.in_(top_codes),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .order_by(BrokerDailySummary.date)
            .all()
        )

        df = pd.DataFrame([{
            "date": r.date,
            "broker_code": r.broker_code,
            "net_lot": r.net_lot,
            "net_value": r.net_value,
        } for r in daily_q])

        # Build broker metadata map for labels
        broker_map = {
            b.code: {"name": b.name, "type": b.type, "cluster": b.cluster_label}
            for b in self.db.query(Broker).filter(Broker.code.in_(top_codes)).all()
        }

        lines = []
        for code in top_codes:
            sub = df[df["broker_code"] == code].sort_values("date").copy()
            sub["inventory_lot"] = sub["net_lot"].cumsum()
            sub["inventory_value"] = sub["net_value"].cumsum()

            meta = broker_map.get(code, {})
            lines.append({
                "broker_code": code,
                "broker_name": meta.get("name", code),
                "broker_type": meta.get("type"),
                "cluster_label": meta.get("cluster"),
                "total_net_lot": int(sub["net_lot"].sum()),
                "total_net_value": int(sub["net_value"].sum()),
                "data": [
                    {
                        "date": row["date"].isoformat(),
                        "inventory_lot": int(row["inventory_lot"]),
                        "inventory_value": int(row["inventory_value"]),
                        "daily_net_lot": int(row["net_lot"]),
                    }
                    for _, row in sub.iterrows()
                ],
            })

        # Step 3: price series for overlay
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
        price_series = [
            {"date": c.date.isoformat(), "close": c.close, "volume": c.volume}
            for c in candles
        ]

        # Step 4: stealth accumulation detection
        stealth_signal = self._detect_stealth_accumulation(lines, price_series)

        return {
            "symbol": symbol,
            "period_days": days,
            "lines": lines,
            "price_series": price_series,
            "stealth_accumulation": stealth_signal,
        }

    @staticmethod
    def _detect_stealth_accumulation(lines: list, prices: list) -> dict:
        """
        Detect: price sideways/down BUT inventory rising = stealth accumulation.
        """
        if not lines or len(prices) < 20:
            return {"detected": False, "reason": "insufficient_data"}

        price_start = prices[0]["close"]
        price_end = prices[-1]["close"]
        price_change_pct = (price_end / price_start - 1) * 100

        # Sum total inventory growth across positive accumulators
        positive_accumulators = [
            line for line in lines
            if line["total_net_lot"] > 0
            and line["cluster_label"] in ("market_maker", "institutional")
        ]
        total_accumulated = sum(line["total_net_lot"] for line in positive_accumulators)

        detected = (
            price_change_pct < 3.0
            and total_accumulated > 0
            and len(positive_accumulators) >= 2
        )

        return {
            "detected": detected,
            "price_change_pct": round(price_change_pct, 2),
            "accumulator_count": len(positive_accumulators),
            "total_lots_accumulated": int(total_accumulated),
            "interpretation": (
                "Stealth accumulation detected: price flat/down but institutional brokers "
                "are quietly accumulating. Possible breakout setup."
                if detected else
                "No stealth accumulation pattern."
            ),
        }

    # ------------------------------------------------------------------ #
    # Top accumulators / distributors
    # ------------------------------------------------------------------ #

    def top_accumulators(
        self,
        symbol: str,
        days: int = 30,
        limit: int = 20,
    ) -> list[dict]:
        """
        Brokers ranked by net buy value over the period.
        Includes a behavior classification.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        rows = (
            self.db.query(
                BrokerDailySummary.broker_code,
                func.sum(BrokerDailySummary.buy_lot).label("buy_lot"),
                func.sum(BrokerDailySummary.sell_lot).label("sell_lot"),
                func.sum(BrokerDailySummary.buy_value).label("buy_value"),
                func.sum(BrokerDailySummary.sell_value).label("sell_value"),
                func.sum(BrokerDailySummary.net_value).label("net_value"),
                func.count(BrokerDailySummary.date).label("active_days"),
                func.avg(BrokerDailySummary.avg_buy_price).label("avg_buy_price"),
            )
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.broker_code)
            .all()
        )

        # Get broker metadata
        broker_codes = [r.broker_code for r in rows]
        brokers = {
            b.code: b for b in
            self.db.query(Broker).filter(Broker.code.in_(broker_codes)).all()
        }

        # Build days-positive count per broker (for consistency)
        positive_days_q = (
            self.db.query(
                BrokerDailySummary.broker_code,
                func.count(BrokerDailySummary.date).label("pos_days"),
            )
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
                BrokerDailySummary.net_value > 0,
            )
            .group_by(BrokerDailySummary.broker_code)
            .all()
        )
        pos_days_map = {r.broker_code: r.pos_days for r in positive_days_q}

        result = []
        for r in rows:
            broker = brokers.get(r.broker_code)
            consistency = pos_days_map.get(r.broker_code, 0) / max(r.active_days, 1)
            label = self._classify_behavior(
                net_value=r.net_value or 0,
                consistency=consistency,
                active_days=r.active_days,
            )
            result.append({
                "broker_code": r.broker_code,
                "broker_name": broker.name if broker else r.broker_code,
                "broker_type": broker.type if broker else None,
                "cluster_label": broker.cluster_label if broker else None,
                "is_foreign": broker.is_foreign if broker else False,
                "buy_lot": int(r.buy_lot or 0),
                "sell_lot": int(r.sell_lot or 0),
                "net_lot": int((r.buy_lot or 0) - (r.sell_lot or 0)),
                "buy_value": int(r.buy_value or 0),
                "sell_value": int(r.sell_value or 0),
                "net_value": int(r.net_value or 0),
                "avg_buy_price": round(r.avg_buy_price, 0) if r.avg_buy_price else None,
                "active_days": r.active_days,
                "consistency_score": round(consistency * 100, 1),
                "behavior_label": label,
            })

        # Sort by net_value desc, then take top accumulators + bottom distributors
        result.sort(key=lambda x: x["net_value"], reverse=True)
        return result[:limit]

    @staticmethod
    def _classify_behavior(net_value: int, consistency: float, active_days: int) -> str:
        if net_value > 10_000_000_000 and consistency > 0.7:
            return "STRONG_ACCUMULATION"
        elif net_value > 5_000_000_000 and consistency > 0.55:
            return "MODERATE_ACCUMULATION"
        elif net_value > 1_000_000_000 and active_days >= 10:
            return "GRADUAL_ENTRY"
        elif net_value < -10_000_000_000:
            return "ACTIVE_DISTRIBUTION"
        elif net_value < -3_000_000_000:
            return "DISTRIBUTION"
        elif active_days > 5 and consistency < 0.4:
            return "RETAIL_NOISE"
        else:
            return "NEUTRAL"

    # ------------------------------------------------------------------ #
    # Done detail (simulated tick aggregation)
    # ------------------------------------------------------------------ #

    def done_detail_summary(self, symbol: str, days: int = 5) -> dict:
        """
        Aggregated done-detail by broker pairs.
        Shows who's buying from whom.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        rows = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
            )
            .all()
        )

        broker_map = {
            b.code: b for b in
            self.db.query(Broker).all()
        }

        # Aggregate by broker
        agg = {}
        for r in rows:
            if r.broker_code not in agg:
                agg[r.broker_code] = {"buy_value": 0, "sell_value": 0}
            agg[r.broker_code]["buy_value"] += r.buy_value or 0
            agg[r.broker_code]["sell_value"] += r.sell_value or 0

        nodes = []
        for code, vals in agg.items():
            broker = broker_map.get(code)
            nodes.append({
                "broker_code": code,
                "broker_name": broker.name if broker else code,
                "cluster": broker.cluster_label if broker else "unknown",
                "is_foreign": broker.is_foreign if broker else False,
                "buy_value": vals["buy_value"],
                "sell_value": vals["sell_value"],
                "net_value": vals["buy_value"] - vals["sell_value"],
            })

        nodes.sort(key=lambda x: x["buy_value"] + x["sell_value"], reverse=True)
        return {
            "symbol": symbol,
            "period_days": days,
            "brokers": nodes[:30],
        }
