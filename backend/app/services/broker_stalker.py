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

    def last_trading_day(self) -> Optional[date]:
        """Return the most recent trading date in the candles table."""
        return self.db.query(func.max(Candle.date)).scalar()

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
    # Stalk MULTIPLE brokers — aggregate flow across selected brokers
    # ------------------------------------------------------------------ #

    def stalk_brokers(
        self,
        broker_codes: list[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50,
        min_net_value: float = 100_000_000,
    ) -> dict:
        """
        Combined stalking across multiple brokers within a date range.

        Default behavior:
        - end_date = last trading day in DB
        - start_date = end_date (single-day analysis = "today's flow")

        For each symbol, aggregates net flow from ALL selected brokers
        and shows which symbols they are *collectively* accumulating /
        distributing.

        Use cases:
        - "Combined retail flow" → select all retail brokers
        - "Foreign block consensus" → select 3-4 foreign brokers
        - "Bandar group activity" → select market_maker brokers
        """
        codes = [c.strip().upper() for c in broker_codes if c and c.strip()]
        if not codes:
            return {"error": "No broker codes provided"}

        # Validate brokers exist
        broker_rows = (
            self.db.query(Broker)
            .filter(Broker.code.in_(codes))
            .all()
        )
        if not broker_rows:
            return {"error": f"None of the broker codes exist: {codes}"}

        valid_codes = [b.code for b in broker_rows]
        missing = set(codes) - set(valid_codes)

        # Resolve date range — default = last trading day (1 day)
        last_trading_day = self.last_trading_day()
        if not last_trading_day:
            return {"brokers": [], "results": []}

        if end_date is None:
            end_date = last_trading_day
        if start_date is None:
            start_date = end_date

        if start_date > end_date:
            return {"error": "start_date must be <= end_date"}

        days = (end_date - start_date).days + 1

        # Aggregate per symbol across ALL selected brokers
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
                BrokerDailySummary.broker_code.in_(valid_codes),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.symbol)
            .all()
        )

        if not rows:
            return {
                "brokers": [self._broker_dict(b) for b in broker_rows],
                "missing_codes": list(missing),
                "broker_summary": [],
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "as_of": end_date.isoformat(),
                "last_trading_day": last_trading_day.isoformat(),
                "total_symbols": 0,
                "results": [],
            }

        symbol_codes = [r.symbol for r in rows]

        # Symbol metadata
        symbols = {
            s.code: s
            for s in self.db.query(Symbol)
            .filter(Symbol.code.in_(symbol_codes))
            .all()
        }

        # Latest close
        latest_candles = (
            self.db.query(Candle)
            .filter(Candle.symbol.in_(symbol_codes), Candle.date == end_date)
            .all()
        )
        close_map = {c.symbol: c.close for c in latest_candles}

        # Buy-day count per symbol (across selected brokers, daily aggregated)
        # We want days where the COMBINED net was positive
        daily_combined = (
            self.db.query(
                BrokerDailySummary.symbol,
                BrokerDailySummary.date,
                func.sum(BrokerDailySummary.net_value).label("daily_net"),
            )
            .filter(
                BrokerDailySummary.broker_code.in_(valid_codes),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.symbol, BrokerDailySummary.date)
            .all()
        )
        buy_days_map: dict[str, int] = {}
        for r in daily_combined:
            if (r.daily_net or 0) > 0:
                buy_days_map[r.symbol] = buy_days_map.get(r.symbol, 0) + 1

        # Per-broker contribution per symbol (for drill-down later)
        contrib_rows = (
            self.db.query(
                BrokerDailySummary.symbol,
                BrokerDailySummary.broker_code,
                func.sum(BrokerDailySummary.net_value).label("net_value"),
                func.sum(BrokerDailySummary.net_lot).label("net_lot"),
            )
            .filter(
                BrokerDailySummary.broker_code.in_(valid_codes),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(
                BrokerDailySummary.symbol,
                BrokerDailySummary.broker_code,
            )
            .all()
        )
        contrib_map: dict[str, list[dict]] = {}
        for c in contrib_rows:
            contrib_map.setdefault(c.symbol, []).append({
                "broker_code": c.broker_code,
                "net_value": int(c.net_value or 0),
                "net_lot": int(c.net_lot or 0),
            })
        # Sort each symbol's contributors by absolute net
        for sym, lst in contrib_map.items():
            lst.sort(key=lambda x: abs(x["net_value"]), reverse=True)

        # Build result rows
        results = []
        for r in rows:
            if abs(r.net_value or 0) < min_net_value:
                continue

            sym = r.symbol
            sym_meta = symbols.get(sym)

            # Active days here = unique (broker, date) combinations
            buy_days = buy_days_map.get(sym, 0)
            # total_days computed from contribution data
            total_days = max(
                len(daily_combined and [c for c in daily_combined if c.symbol == sym] or []),
                1,
            )
            consistency = buy_days / total_days if total_days > 0 else 0
            close = close_map.get(sym, 0)
            label = self._classify(
                r.net_value or 0, consistency, total_days, days,
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
                "active_days": total_days,
                "buy_days": buy_days,
                "consistency_pct": round(consistency * 100, 1),
                "behavior_label": label,
                "contributors": contrib_map.get(sym, []),
            })

        results.sort(key=lambda x: x["net_value"], reverse=True)

        # Summary stats per broker (which broker contributed most overall)
        broker_summary = self._compute_broker_summary(
            broker_rows, valid_codes, start_date, end_date,
        )

        return {
            "brokers": [self._broker_dict(b) for b in broker_rows],
            "missing_codes": list(missing),
            "broker_summary": broker_summary,
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "as_of": end_date.isoformat(),
            "last_trading_day": last_trading_day.isoformat(),
            "total_symbols": len(results),
            "results": results[:limit],
        }

    def _broker_dict(self, b: Broker) -> dict:
        return {
            "code": b.code,
            "name": b.name,
            "type": b.type,
            "cluster_label": b.cluster_label,
            "is_foreign": b.is_foreign,
        }

    def _compute_broker_summary(
        self,
        broker_rows: list,
        valid_codes: list[str],
        start_date,
        end_date,
    ) -> list[dict]:
        """Per-broker totals across all symbols (drill-down view)."""
        rows = (
            self.db.query(
                BrokerDailySummary.broker_code,
                func.sum(BrokerDailySummary.buy_value).label("buy_value"),
                func.sum(BrokerDailySummary.sell_value).label("sell_value"),
                func.sum(BrokerDailySummary.net_value).label("net_value"),
                func.count(func.distinct(BrokerDailySummary.symbol)).label("symbol_count"),
                func.count(BrokerDailySummary.date).label("activity_count"),
            )
            .filter(
                BrokerDailySummary.broker_code.in_(valid_codes),
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .group_by(BrokerDailySummary.broker_code)
            .all()
        )
        broker_map = {b.code: b for b in broker_rows}
        out = []
        for r in rows:
            b = broker_map.get(r.broker_code)
            out.append({
                "code": r.broker_code,
                "name": b.name if b else r.broker_code,
                "cluster_label": b.cluster_label if b else None,
                "is_foreign": b.is_foreign if b else False,
                "buy_value": int(r.buy_value or 0),
                "sell_value": int(r.sell_value or 0),
                "net_value": int(r.net_value or 0),
                "symbol_count": r.symbol_count,
                "activity_count": r.activity_count,
            })
        out.sort(key=lambda x: x["net_value"], reverse=True)
        return out

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
