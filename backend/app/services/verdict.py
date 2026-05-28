"""
Verdict Service.

Computes a visual "conclusion icon" per symbol based on multi-timeframe
analysis of bandar inventory line + price trend + foreign flow.

Verdict states:
- GREEN_CHECK (✓): Consistent accumulation — bandar inventory rising in
                   straight line, multiple timeframes agree.
- ORANGE_X (✗):    Sideways / mixed — choppy, no clear direction.
- RED_MINUS (−):   Consistent distribution — inventory falling.

Also computes Retail Non-Flow Score (0-100):
- High score (70+): Retail dumping → smart money likely accumulating
- Mid (40-60):      Neutral
- Low (<30):        Retail FOMO buying → potential distribution top
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Candle, BrokerDailySummary, Broker, ForeignFlow


VERDICT_ICONS = {
    "GREEN_CHECK": "check",     # ✓ frontend renders icon
    "ORANGE_X": "x",            # ✗
    "RED_MINUS": "minus",       # −
}

VERDICT_COLORS = {
    "GREEN_CHECK": "green",
    "ORANGE_X": "orange",
    "RED_MINUS": "red",
}


@dataclass
class VerdictResult:
    verdict: str
    icon: str
    color: str
    confidence: float              # 0-100
    explanation: str

    # Inventory line analytics
    slope_5d: float
    slope_15d: float
    slope_30d: float
    r_squared_15d: float
    consistency_pct: float
    bandar_lot_growth_15d: int

    # Retail Non-Flow
    retail_non_flow_score: float
    retail_non_flow_label: str
    retail_non_flow_explanation: str
    retail_net_value_15d: int


class VerdictService:

    def __init__(self, db: Session):
        self.db = db
        brokers = self.db.query(Broker).all()
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }
        self.retail_set = {b.code for b in brokers if b.cluster_label == "retail"}

    # ------------------------------------------------------------------ #
    # Single-symbol entry point (for stock detail page)
    # ------------------------------------------------------------------ #

    def compute(self, symbol: str, lookback_days: int = 35) -> Optional[dict]:
        end_date = self.db.query(func.max(Candle.date)).scalar()
        if not end_date:
            return None
        start_date = end_date - timedelta(days=lookback_days + 10)

        # Candles
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
        if len(candles) < 15:
            return None

        cdf = pd.DataFrame([{
            "date": c.date, "close": c.close,
        } for c in candles])

        # Broker activity
        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= end_date,
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "broker": r.broker_code,
            "net_lot": r.net_lot, "net_value": r.net_value,
            "buy_value": r.buy_value, "sell_value": r.sell_value,
        } for r in bds])

        return self._compute_from_df(symbol, cdf, bdf, end_date)

    # ------------------------------------------------------------------ #
    # Batch computation (used by seed.py for the latest day)
    # ------------------------------------------------------------------ #

    def compute_universe(
        self,
        target_date: Optional[date] = None,
        lookback_days: int = 35,
    ) -> dict[str, dict]:
        """Compute verdicts for all symbols on `target_date`. Efficient single
        bulk fetch."""
        if target_date is None:
            target_date = self.db.query(func.max(Candle.date)).scalar()
        if not target_date:
            return {}
        start_date = target_date - timedelta(days=lookback_days + 10)

        candles = (
            self.db.query(Candle)
            .filter(Candle.date >= start_date, Candle.date <= target_date)
            .all()
        )
        cdf_all = pd.DataFrame([{
            "date": c.date, "symbol": c.symbol, "close": c.close,
        } for c in candles])

        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= target_date,
            )
            .all()
        )
        bdf_all = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol, "broker": r.broker_code,
            "net_lot": r.net_lot, "net_value": r.net_value,
            "buy_value": r.buy_value, "sell_value": r.sell_value,
        } for r in bds])

        results = {}
        if cdf_all.empty:
            return results

        for sym, cdf in cdf_all.groupby("symbol"):
            bdf = bdf_all[bdf_all["symbol"] == sym] if not bdf_all.empty else pd.DataFrame()
            r = self._compute_from_df(
                sym, cdf.sort_values("date").reset_index(drop=True),
                bdf, target_date,
            )
            if r is not None:
                results[sym] = r
        return results

    # ------------------------------------------------------------------ #
    # Core computation
    # ------------------------------------------------------------------ #

    def _compute_from_df(
        self,
        symbol: str,
        cdf: pd.DataFrame,
        bdf: pd.DataFrame,
        target_date: date,
    ) -> Optional[dict]:
        if len(cdf) < 15:
            return None

        # Filter broker activity for bandar/retail
        if not bdf.empty:
            bandar = bdf[bdf["broker"].isin(self.bandar_set)]
            retail = bdf[bdf["broker"].isin(self.retail_set)]
        else:
            bandar = pd.DataFrame()
            retail = pd.DataFrame()

        # Daily aggregates
        bandar_daily = (
            bandar.groupby("date")["net_lot"].sum().sort_index()
            if not bandar.empty
            else pd.Series(dtype=float)
        )
        bandar_inventory = bandar_daily.cumsum()

        retail_daily_value = (
            retail.assign(net_val=retail["buy_value"] - retail["sell_value"])
            .groupby("date")["net_val"].sum().sort_index()
            if not retail.empty
            else pd.Series(dtype=float)
        )

        # ─── Slope analysis (linear regression) ────────────────────
        slope_5d, _ = self._slope_and_r2(bandar_inventory.tail(5))
        slope_15d, r2_15d = self._slope_and_r2(bandar_inventory.tail(15))
        slope_30d, _ = self._slope_and_r2(bandar_inventory.tail(30))

        # ─── Consistency (15D buy-day ratio) ───────────────────────
        last_15 = bandar_daily.tail(15)
        buy_days = int((last_15 > 0).sum())
        total_days = max(len(last_15), 1)
        consistency = buy_days / total_days * 100

        # ─── Inventory growth (15D) ────────────────────────────────
        bandar_lot_15d = (
            int(bandar_inventory.iloc[-1] - bandar_inventory.iloc[max(0, len(bandar_inventory) - 15)])
            if len(bandar_inventory) >= 2 else 0
        )

        # ─── Verdict logic ─────────────────────────────────────────
        # Normalize slope by typical daily lot (avoid magnitude bias)
        avg_daily_abs_lot = (
            bandar_daily.abs().mean() if not bandar_daily.empty else 1
        )
        if avg_daily_abs_lot < 1:
            avg_daily_abs_lot = 1
        norm_slope_15d = slope_15d / avg_daily_abs_lot

        verdict, confidence = self._decide_verdict(
            slope_5d, slope_15d, slope_30d,
            r2_15d, consistency, norm_slope_15d,
        )

        explanation = self._explain_verdict(
            verdict, slope_15d, r2_15d, consistency,
            bandar_lot_15d,
        )

        # ─── Retail Non-Flow ───────────────────────────────────────
        retail_net_15d = (
            int(retail_daily_value.tail(15).sum())
            if not retail_daily_value.empty else 0
        )
        retail_avg_abs = (
            float(retail_daily_value.tail(15).abs().mean())
            if not retail_daily_value.empty else 1
        )
        if retail_avg_abs < 1:
            retail_avg_abs = 1

        # Inverted: retail selling = positive non-flow
        # Score: 50 + (-retail_net / (15 * retail_avg_abs)) * 25, clip 0-100
        rnf_raw = -retail_net_15d / (15 * retail_avg_abs)
        retail_non_flow_score = float(np.clip(50 + rnf_raw * 25, 0, 100))

        if retail_non_flow_score >= 65:
            rnf_label = "POSITIVE_NONFLOW"
            rnf_explanation = (
                "Retail menjual berat — smart money kemungkinan akumulasi "
                "dari tekanan jual retail (kontrarian positif)."
            )
        elif retail_non_flow_score <= 35:
            rnf_label = "NEGATIVE_NONFLOW"
            rnf_explanation = (
                "Retail FOMO membeli — potensi distribution top, smart money "
                "memberikan supply ke retail (kontrarian negatif)."
            )
        else:
            rnf_label = "NEUTRAL"
            rnf_explanation = "Aktivitas retail masih seimbang."

        return {
            "symbol": symbol,
            "as_of": target_date.isoformat(),
            "verdict": verdict,
            "icon": VERDICT_ICONS[verdict],
            "color": VERDICT_COLORS[verdict],
            "confidence": round(confidence, 1),
            "explanation": explanation,
            # Slopes
            "slope_5d": round(float(slope_5d), 2),
            "slope_15d": round(float(slope_15d), 2),
            "slope_30d": round(float(slope_30d), 2),
            "r_squared_15d": round(float(r2_15d), 3),
            "consistency_pct": round(consistency, 1),
            "buy_days_15d": buy_days,
            "bandar_lot_growth_15d": bandar_lot_15d,
            # Retail Non-Flow
            "retail_non_flow_score": round(retail_non_flow_score, 1),
            "retail_non_flow_label": rnf_label,
            "retail_non_flow_explanation": rnf_explanation,
            "retail_net_value_15d": retail_net_15d,
        }

    # ------------------------------------------------------------------ #
    # Decision logic
    # ------------------------------------------------------------------ #

    @staticmethod
    def _slope_and_r2(series: pd.Series) -> tuple[float, float]:
        """Linear regression slope and R² of a series."""
        if len(series) < 3:
            return 0.0, 0.0
        x = np.arange(len(series), dtype=float)
        y = series.values.astype(float)
        if y.std() < 1e-9:
            return 0.0, 0.0
        # numpy polyfit
        try:
            slope, intercept = np.polyfit(x, y, 1)
            y_pred = slope * x + intercept
            ss_res = ((y - y_pred) ** 2).sum()
            ss_tot = ((y - y.mean()) ** 2).sum()
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
            return float(slope), float(max(0, r2))
        except Exception:
            return 0.0, 0.0

    @staticmethod
    def _decide_verdict(
        slope_5d: float,
        slope_15d: float,
        slope_30d: float,
        r2_15d: float,
        consistency: float,
        norm_slope_15d: float,
    ) -> tuple[str, float]:
        """
        Decide verdict + confidence (0-100).

        GREEN_CHECK: slope_15d strongly positive, R² high, consistency high,
                    multi-tf agree
        RED_MINUS:   slope_15d strongly negative, R² high, multi-tf agree
        ORANGE_X:    everything else
        """
        # Direction agreement count (positive direction)
        pos_count = sum(1 for s in [slope_5d, slope_15d, slope_30d] if s > 0)
        neg_count = sum(1 for s in [slope_5d, slope_15d, slope_30d] if s < 0)

        # Threshold for "strongly trending": normalized slope vs daily avg
        STRONG = 0.15

        # GREEN_CHECK conditions
        if (
            slope_15d > 0
            and norm_slope_15d > STRONG
            and r2_15d >= 0.45
            and consistency >= 55
            and pos_count >= 2
        ):
            confidence = (
                (min(r2_15d, 1.0) * 35) +
                (min(consistency / 100, 1.0) * 30) +
                (min(abs(norm_slope_15d) / 0.5, 1.0) * 20) +
                (pos_count / 3 * 15)
            )
            return "GREEN_CHECK", min(confidence, 100)

        # RED_MINUS conditions
        if (
            slope_15d < 0
            and norm_slope_15d < -STRONG
            and r2_15d >= 0.45
            and neg_count >= 2
        ):
            confidence = (
                (min(r2_15d, 1.0) * 40) +
                (min(abs(norm_slope_15d) / 0.5, 1.0) * 30) +
                (neg_count / 3 * 30)
            )
            return "RED_MINUS", min(confidence, 100)

        # Default ORANGE_X with confidence reflecting choppiness
        confidence = 100 - min(r2_15d * 100, 100)
        return "ORANGE_X", confidence

    @staticmethod
    def _explain_verdict(
        verdict: str,
        slope_15d: float,
        r2_15d: float,
        consistency: float,
        bandar_lot_15d: int,
    ) -> str:
        if verdict == "GREEN_CHECK":
            return (
                f"Akumulasi konsisten — inventory bandar naik garis lurus "
                f"(R² {r2_15d:.2f}), {consistency:.0f}% hari net buy, "
                f"+{bandar_lot_15d:,} lot dalam 15 hari. Tren bullish kuat."
            )
        if verdict == "RED_MINUS":
            return (
                f"Distribusi konsisten — inventory bandar turun lurus "
                f"(R² {r2_15d:.2f}), bandar exit {bandar_lot_15d:,} lot "
                f"dalam 15 hari. Hindari long, awasi konfirmasi markdown."
            )
        return (
            f"Sideways / mixed — gerakan tidak konsisten "
            f"(R² {r2_15d:.2f}, konsistensi {consistency:.0f}%). "
            f"Belum ada arah jelas, tunggu konfirmasi."
        )
