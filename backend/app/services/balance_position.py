"""
Balance Position Service.

Computes percentage breakdown by entity type (foreign / institutional /
retail / corporate) per symbol over time.
"""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
from sqlalchemy.orm import Session

from app.models import BrokerDailySummary, Broker


# Map cluster_label → balance position bucket
CLUSTER_TO_BUCKET = {
    "institutional": "institutional",
    "market_maker":  "institutional",
    "retail":        "retail",
    "corporate":     "corporate",
}


class BalancePositionService:

    def __init__(self, db: Session):
        self.db = db
        # Build broker → bucket map once
        brokers = self.db.query(Broker).all()
        self.bucket_map = {}
        self.foreign_set = set()
        for b in brokers:
            self.bucket_map[b.code] = CLUSTER_TO_BUCKET.get(b.cluster_label, "other")
            if b.is_foreign:
                self.foreign_set.add(b.code)

    def get_balance(self, symbol: str, days: int = 90) -> dict:
        """Daily breakdown by entity type."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

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
            return {"symbol": symbol, "data": [], "summary": {}}

        records = []
        for r in rows:
            is_foreign = r.broker_code in self.foreign_set
            bucket = "foreign" if is_foreign else self.bucket_map.get(r.broker_code, "other")
            records.append({
                "date": r.date,
                "bucket": bucket,
                "buy_value": r.buy_value or 0,
                "sell_value": r.sell_value or 0,
            })

        df = pd.DataFrame(records)

        # Pivot per date per bucket
        pivot_buy = df.pivot_table(
            index="date", columns="bucket", values="buy_value",
            aggfunc="sum", fill_value=0
        )
        pivot_sell = df.pivot_table(
            index="date", columns="bucket", values="sell_value",
            aggfunc="sum", fill_value=0
        )

        all_buckets = ["foreign", "institutional", "retail", "corporate", "other"]
        for col in all_buckets:
            if col not in pivot_buy.columns:
                pivot_buy[col] = 0
            if col not in pivot_sell.columns:
                pivot_sell[col] = 0

        # Daily total
        pivot_buy["total"] = pivot_buy[all_buckets].sum(axis=1)
        pivot_sell["total"] = pivot_sell[all_buckets].sum(axis=1)

        # Percentages
        timeline = []
        for d in pivot_buy.index:
            total_buy = max(pivot_buy.loc[d, "total"], 1)
            total_sell = max(pivot_sell.loc[d, "total"], 1)
            row = {"date": d.isoformat()}
            for b in all_buckets:
                row[f"{b}_buy_pct"] = round(pivot_buy.loc[d, b] / total_buy * 100, 2)
                row[f"{b}_sell_pct"] = round(pivot_sell.loc[d, b] / total_sell * 100, 2)
                row[f"{b}_net_pct"] = round(
                    (pivot_buy.loc[d, b] - pivot_sell.loc[d, b])
                    / max(total_buy, total_sell) * 100, 2
                )
            timeline.append(row)

        # Summary (period totals)
        summary = {}
        for b in all_buckets:
            total_buy = pivot_buy[b].sum()
            total_sell = pivot_sell[b].sum()
            summary[b] = {
                "buy_value": int(total_buy),
                "sell_value": int(total_sell),
                "net_value": int(total_buy - total_sell),
                "buy_pct": round(total_buy / max(pivot_buy["total"].sum(), 1) * 100, 2),
                "sell_pct": round(total_sell / max(pivot_sell["total"].sum(), 1) * 100, 2),
            }

        return {
            "symbol": symbol,
            "period_days": days,
            "data": timeline,
            "summary": summary,
        }
