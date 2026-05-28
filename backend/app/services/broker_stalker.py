"""
Broker Stalker Service.

Cross-symbol analysis: pick a broker code, find every symbol they're
accumulating or distributing.

Use case:
- "Broker CC sedang akumulasi saham apa minggu ini?"
- "Broker YP (retail) lagi distribusi mana aja?"
- Filter by broker cluster (foreign / institutional / retail / market_maker / zombie)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import BrokerDailySummary, Broker, Symbol, Candle


class BrokerStalkerService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # Stalk a single broker across all symbols
    # ------------------------------------------------------------------ #

    def stalk_broker(
        self,
        broker_code: str,
        days: int = 20,
        limit: int = 50,
        min_net_value: float = 100_000_000,    # min Rp 100M to include
    ) -> dict:
        """Find what a broker is accumulating / distributing across all symbols."""
        broker = (
            self.db.query(Broker)
            .filter(Broker.code == broker_code.upper())
            .first()
        )
        if not broker:
            return {"error": f"Broker {broker_code} not found"}

        end_date = self.db.query(func.max(Candle.date)).scalar()
        if not end_date:
            return {"broker": broker_code, "results": []}
        start_date = end_date - timedelta(days=days)

        # Aggregate per symbol
        rows = (
            self.db.query(
                BrokerDailySummary.symbol,
                func.sum(BrokerDailySummary.buy_lot).label("buy_lot"),
                func.sum(BrokerDailySummary.sell_lot).label("sell_lot"),
                func.sum(BrokerDailySummary.buy_value).label("buy_value"),
                func.sum(BrokerDailySummary.sell_value).label("sell_value"),
                func.sum(BrokerDailySummary.net_value).label("net_value"),
                func.count(BrokerDailySummary.date).label("active_days"),
                func.avg(BrokerDailySummary.avg_buy_price).label("avg_buy_price"),
            )
            .filter(
                BrokerDailySummary.broker_code == broker_code.upper(),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.symbol)
            .all()
        )

        if not rows:
            return {
                "broker": {
                    "code": broker.code,
                    "name": broker.name,
                    "type": broker.type,
                    "cluster_label": broker.cluster_label,
                    "is_foreign": broker.is_foreign,
                },
                "period_days": days,
                "results": [],
            }

        symbol_codes = [r.symbol for r in rows]

        # Get symbol metadata
        symbols = {
            s.code: s for s in
            self.db.query(Symbol).filter(Symbol.code.in_(symbol_codes)).all()
        }

        # Latest close per symbol
        latest_candles = (
            self.db.query(Candle)
            .filter(Candle.symbol.in_(symbol_codes), Candle.date == end_date)
            .all()
        )
        close_map = {c.symbol: c.close for c in latest_candles}

        # Buy-day count per symbol
        buy_days_q = (
            self.db.query(
                BrokerDailySummary.symbol,
                func.count(BrokerDailySummary.date).label("buy_days"),
            )
            .filter(
                BrokerDailySummary.broker_code == broker_code.upper(),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
                BrokerDailySummary.net_value > 0,
            )
            .group_by(BrokerDailySummary.symbol)
            .all()
        )
        buy_days_map = {r.symbol: r.buy_days for r in buy_days_q}

        results = []
        for r in rows:
            if abs(r.net_value or 0) < min_net_value:
                continue
            sym = r.symbol
            sym_meta = symbols.get(sym)
            buy_days = buy_days_map.get(sym, 0)
            consistency = (
                buy_days / r.active_days if r.active_days > 0 else 0
            )
            close = close_map.get(sym, 0)
            label = self._classify(
                r.net_value or 0, consistency, r.active_days, days,
            )

            results.append({
                "symbol": sym,
                "name": sym_meta.name if sym_meta else sym,
                "sector": sym_meta.sector if sym_meta else None,
                "close": close,
                "buy_lot": int(r.buy_lot or 0),
                "sell_lot": int(r.sell_lot or 0),
                "net_lot": int((r.buy_lot or 0) - (r.sell_lot or 0)),
                "buy_value": int(r.buy_value or 0),
                "sell_value": int(r.sell_value or 0),
                "net_value": int(r.net_value or 0),
                "avg_buy_price": (
                    round(float(r.avg_buy_price), 0)
                    if r.avg_buy_price else None
                ),
                "active_days": r.active_days,
                "buy_days": buy_days,
                "consistency_pct": round(consistency * 100, 1),
                "behavior_label": label,
            })

        # Sort by absolute net value
        results.sort(key=lambda x: x["net_value"], reverse=True)
        return {
            "broker": {
                "code": broker.code,
                "name": broker.name,
                "type": broker.type,
                "cluster_label": broker.cluster_label,
                "is_foreign": broker.is_foreign,
            },
            "period_days": days,
            "as_of": end_date.isoformat(),
            "total_symbols": len(results),
            "results": results[:limit],
        }

    # ------------------------------------------------------------------ #
    # List all brokers (for picker)
    # ------------------------------------------------------------------ #

    def list_brokers(self) -> list[dict]:
        """Return all brokers with cluster/foreign metadata for the picker."""
        brokers = (
            self.db.query(Broker)
            .order_by(Broker.cluster_label, Broker.code)
            .all()
        )
        return [{
            "code": b.code,
            "name": b.name,
            "type": b.type,
            "cluster_label": b.cluster_label,
            "is_foreign": b.is_foreign,
        } for b in brokers]

    # ------------------------------------------------------------------ #
    # Per-broker inventory line for a single symbol (used for chart)
    # ------------------------------------------------------------------ #

    def broker_inventory_for_symbol(
        self,
        broker_code: str,
        symbol: str,
        days: int = 90,
    ) -> dict:
        """Get cumulative inventory line for one (broker, symbol) pair."""
        end_date = self.db.query(func.max(Candle.date)).scalar()
        if not end_date:
            return {"data": []}
        start_date = end_date - timedelta(days=days)

        rows = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.broker_code == broker_code.upper(),
                BrokerDailySummary.symbol == symbol.upper(),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .order_by(BrokerDailySummary.date)
            .all()
        )

        if not rows:
            return {
                "broker": broker_code,
                "symbol": symbol,
                "data": [],
            }

        df = pd.DataFrame([{
            "date": r.date,
            "net_lot": r.net_lot,
            "net_value": r.net_value,
        } for r in rows])
        df["inventory_lot"] = df["net_lot"].cumsum()
        df["inventory_value"] = df["net_value"].cumsum()

        candles = (
            self.db.query(Candle)
            .filter(
                Candle.symbol == symbol.upper(),
                Candle.date >= start_date,
                Candle.date <= end_date,
            )
            .order_by(Candle.date)
            .all()
        )
        price_series = [
            {"date": c.date.isoformat(), "close": c.close}
            for c in candles
        ]

        return {
            "broker": broker_code,
            "symbol": symbol,
            "period_days": days,
            "data": [
                {
                    "date": row["date"].isoformat(),
                    "daily_net_lot": int(row["net_lot"]),
                    "daily_net_value": int(row["net_value"]),
                    "inventory_lot": int(row["inventory_lot"]),
                    "inventory_value": int(row["inventory_value"]),
                }
                for _, row in df.iterrows()
            ],
            "price_series": price_series,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _classify(
        net_value: float,
        consistency: float,
        active_days: int,
        period_days: int,
    ) -> str:
        if net_value > 5_000_000_000 and consistency > 0.7:
            return "STRONG_ACCUMULATION"
        if net_value > 1_000_000_000 and consistency > 0.55:
            return "ACCUMULATION"
        if net_value > 0 and active_days >= period_days * 0.5:
            return "GRADUAL_ENTRY"
        if net_value < -5_000_000_000:
            return "STRONG_DISTRIBUTION"
        if net_value < -1_000_000_000:
            return "DISTRIBUTION"
        return "NEUTRAL"
