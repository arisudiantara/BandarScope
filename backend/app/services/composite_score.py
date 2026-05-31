"""
Composite Score Engine — Screener V2.

Computes all next-gen scores from raw price + flow + broker data:

- Foreign Strength Score (multi-timeframe)
- Trend Score (MA20/50/100/200 alignment)
- Liquidity Quality Score
- Accumulation Score / Distribution Score (separate)
- Wyckoff Stage Classification (1-5)
- Breakout Quality Score
- Opportunity Score (final composite + star rating)
- Trade Readiness Score
- FOMO Risk Score

All scores are 0-100 unless noted otherwise.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Candle, ForeignFlow, BrokerDailySummary, Broker


# ============================================================
# Wyckoff stage labels
# ============================================================
WYCKOFF_LABELS = {
    1: "ACCUMULATION",
    2: "EARLY_BREAKOUT",
    3: "TREND_EXPANSION",
    4: "LATE_TREND",
    5: "DISTRIBUTION",
}


class CompositeScoreService:
    """Universe-wide score computer. Designed for batch use in seed/EOD jobs."""

    def __init__(self, db: Session):
        self.db = db
        brokers = self.db.query(Broker).all()
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }
        self.foreign_set = {b.code for b in brokers if b.is_foreign}

    # ------------------------------------------------------------------ #
    # Universe-wide computation (used by seed)
    # ------------------------------------------------------------------ #

    def compute_universe(
        self,
        target_date: Optional[date] = None,
        lookback_days: int = 220,
    ) -> dict[str, dict]:
        """Compute all V2 scores for all symbols at target_date."""
        if target_date is None:
            target_date = self.db.query(func.max(Candle.date)).scalar()
        if not target_date:
            return {}
        load_start = target_date - timedelta(days=lookback_days + 10)

        # Bulk fetch
        candles = (
            self.db.query(Candle)
            .filter(Candle.date >= load_start, Candle.date <= target_date)
            .all()
        )
        cdf_all = pd.DataFrame([{
            "date": c.date, "symbol": c.symbol,
            "open": c.open, "high": c.high, "low": c.low, "close": c.close,
            "volume": c.volume, "value": c.value,
            "frequency": c.frequency,
        } for c in candles])

        ff_rows = (
            self.db.query(ForeignFlow)
            .filter(ForeignFlow.date >= load_start, ForeignFlow.date <= target_date)
            .all()
        )
        ffdf_all = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol,
            "net": r.foreign_net_value,
        } for r in ff_rows])

        # Bandar broker activity (only)
        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.date >= load_start,
                BrokerDailySummary.date <= target_date,
                BrokerDailySummary.broker_code.in_(self.bandar_set),
            )
            .all()
        )
        bdf_all = pd.DataFrame([{
            "date": r.date, "symbol": r.symbol,
            "net_lot": r.net_lot, "net_value": r.net_value,
        } for r in bds])

        # Compute IHSG proxy (for relative strength) — value-weighted close
        if not cdf_all.empty:
            ihsg = (
                cdf_all.groupby("date")
                       .apply(lambda x: (x["close"] * x["value"]).sum() / max(x["value"].sum(), 1))
                       .sort_index()
            )
        else:
            ihsg = pd.Series(dtype=float)

        results = {}
        if cdf_all.empty:
            return results

        for sym, cdf in cdf_all.groupby("symbol"):
            cdf = cdf.sort_values("date").reset_index(drop=True)
            ffdf = (
                ffdf_all[ffdf_all["symbol"] == sym].sort_values("date")
                if not ffdf_all.empty else pd.DataFrame()
            )
            bdf = (
                bdf_all[bdf_all["symbol"] == sym].sort_values("date")
                if not bdf_all.empty else pd.DataFrame()
            )

            r = self._compute_for_symbol(sym, cdf, ffdf, bdf, ihsg, target_date)
            if r is not None:
                results[sym] = r
        return results

    # ------------------------------------------------------------------ #
    # Single-symbol computation
    # ------------------------------------------------------------------ #

    def _compute_for_symbol(
        self,
        symbol: str,
        cdf: pd.DataFrame,
        ffdf: pd.DataFrame,
        bdf: pd.DataFrame,
        ihsg: pd.Series,
        target_date: date,
    ) -> Optional[dict]:
        if len(cdf) < 20:
            return None

        latest = cdf.iloc[-1]

        # ───────────────────────────────────────────────────────────────
        # 1. FOREIGN STRENGTH SCORE (multi-timeframe)
        # ───────────────────────────────────────────────────────────────
        foreign_score, foreign_data = self._foreign_strength(ffdf, cdf)

        # ───────────────────────────────────────────────────────────────
        # 2. TREND SCORE (MA alignment)
        # ───────────────────────────────────────────────────────────────
        trend_score, trend_label, trend_data = self._trend_score(cdf)

        # ───────────────────────────────────────────────────────────────
        # 3. LIQUIDITY QUALITY SCORE
        # ───────────────────────────────────────────────────────────────
        liquidity_score, liquidity_label, avg_value_20d = self._liquidity_score(cdf)

        # ───────────────────────────────────────────────────────────────
        # 4. ACCUMULATION & DISTRIBUTION SCORES (separate)
        # ───────────────────────────────────────────────────────────────
        accum_score, dist_score = self._accum_distrib_scores(cdf, ffdf, bdf)

        # ───────────────────────────────────────────────────────────────
        # 5. WYCKOFF STAGE (1-5)
        # ───────────────────────────────────────────────────────────────
        wyckoff_stage, breakout_quality = self._wyckoff_stage(
            cdf, accum_score, dist_score, trend_score, foreign_score,
        )

        # ───────────────────────────────────────────────────────────────
        # 6. SECTOR / BENCHMARK STRENGTH
        # ───────────────────────────────────────────────────────────────
        relative_strength = self._relative_strength(cdf, ihsg)

        # ───────────────────────────────────────────────────────────────
        # 7. FOMO RISK
        # ───────────────────────────────────────────────────────────────
        fomo_risk, fomo_warning = self._fomo_risk(cdf)

        # ───────────────────────────────────────────────────────────────
        # 8. FINAL OPPORTUNITY SCORE (weighted blend) + STAR RATING
        # ───────────────────────────────────────────────────────────────
        opportunity_score, star_rating, setup_label = self._opportunity_score(
            accum_score=accum_score,
            foreign_score=foreign_score,
            trend_score=trend_score,
            liquidity_score=liquidity_score,
            wyckoff_stage=wyckoff_stage,
            breakout_quality=breakout_quality,
            relative_strength=relative_strength,
            fomo_risk=fomo_risk,
        )

        # ───────────────────────────────────────────────────────────────
        # 9. TRADE READINESS — "buy today?"
        # ───────────────────────────────────────────────────────────────
        readiness_score, readiness_signal, readiness_reason = self._trade_readiness(
            cdf, opportunity_score, wyckoff_stage, fomo_risk,
            liquidity_score, trend_score,
        )

        return {
            "symbol": symbol,
            "as_of": target_date.isoformat(),
            # Foreign multi-tf
            "foreign_strength_score": round(float(foreign_score), 1),
            "foreign_net_5d": int(foreign_data.get("net_5d", 0)),
            "foreign_net_10d": int(foreign_data.get("net_10d", 0)),
            "foreign_net_20d": int(foreign_data.get("net_20d", 0)),
            "foreign_net_60d": int(foreign_data.get("net_60d", 0)),
            # Trend
            "trend_score": round(float(trend_score), 1),
            "trend_label": trend_label,
            "above_ma20": round(float(trend_data["above_ma20"]), 2),
            "above_ma50": round(float(trend_data["above_ma50"]), 2),
            "above_ma100": round(float(trend_data["above_ma100"]), 2),
            "above_ma200": round(float(trend_data["above_ma200"]), 2),
            # Liquidity
            "liquidity_score": round(float(liquidity_score), 1),
            "liquidity_label": liquidity_label,
            "avg_value_20d": int(avg_value_20d),
            # Accumulation / Distribution
            "accumulation_score": round(float(accum_score), 1),
            "distribution_score": round(float(dist_score), 1),
            # Wyckoff
            "wyckoff_stage": int(wyckoff_stage),
            "wyckoff_stage_label": WYCKOFF_LABELS[wyckoff_stage],
            "breakout_quality_score": round(float(breakout_quality), 1),
            # Final composite
            "opportunity_score": round(float(opportunity_score), 1),
            "star_rating": int(star_rating),
            "setup_label": setup_label,
            # Trade readiness
            "trade_readiness_score": round(float(readiness_score), 1),
            "trade_readiness_signal": readiness_signal,
            "trade_readiness_reason": readiness_reason,
            # FOMO risk
            "fomo_risk_score": round(float(fomo_risk), 1),
            "fomo_warning": fomo_warning,
        }

    # ================================================================== #
    # Component score implementations
    # ================================================================== #

    @staticmethod
    def _foreign_strength(ffdf: pd.DataFrame, cdf: pd.DataFrame) -> tuple[float, dict]:
        """Multi-timeframe foreign net flow normalized vs avg daily value."""
        if ffdf.empty or cdf.empty:
            return 50.0, {"net_5d": 0, "net_10d": 0, "net_20d": 0, "net_60d": 0}

        avg_value = cdf["value"].tail(20).mean()
        if avg_value <= 0:
            avg_value = 1

        net_5d = float(ffdf.tail(5)["net"].sum())
        net_10d = float(ffdf.tail(10)["net"].sum())
        net_20d = float(ffdf.tail(20)["net"].sum())
        net_60d = float(ffdf.tail(60)["net"].sum())

        # Normalize by avg daily value × period_days
        score_5d = 50 + (net_5d / (avg_value * 5)) * 30
        score_10d = 50 + (net_10d / (avg_value * 10)) * 30
        score_20d = 50 + (net_20d / (avg_value * 20)) * 30
        score_60d = 50 + (net_60d / (avg_value * 60)) * 30

        # Weighted: nearer term gets more weight
        weighted = (
            score_5d * 0.35 +
            score_10d * 0.30 +
            score_20d * 0.20 +
            score_60d * 0.15
        )
        weighted = float(np.clip(weighted, 0, 100))

        return weighted, {
            "net_5d": net_5d, "net_10d": net_10d,
            "net_20d": net_20d, "net_60d": net_60d,
        }

    @staticmethod
    def _trend_score(cdf: pd.DataFrame) -> tuple[float, str, dict]:
        """MA-based trend score with explicit label."""
        close = cdf["close"]
        latest = float(close.iloc[-1])

        ma20 = close.rolling(20, min_periods=5).mean().iloc[-1]
        ma50 = close.rolling(50, min_periods=10).mean().iloc[-1]
        ma100 = close.rolling(100, min_periods=20).mean().iloc[-1]
        ma200 = close.rolling(200, min_periods=40).mean().iloc[-1]

        # Pct above each MA
        def pct_above(price: float, ma: float) -> float:
            if ma is None or pd.isna(ma) or ma <= 0:
                return 0.0
            return (price / ma - 1) * 100

        above_ma20 = pct_above(latest, ma20)
        above_ma50 = pct_above(latest, ma50)
        above_ma100 = pct_above(latest, ma100)
        above_ma200 = pct_above(latest, ma200)

        # Score: each MA contributes
        # Above + amount = bullish, alignment matters too
        flags = [above_ma20 > 0, above_ma50 > 0, above_ma100 > 0, above_ma200 > 0]
        ma_count = sum(flags)

        # MA stack alignment: MA20 > MA50 > MA100 > MA200 = perfect bullish
        mas = [ma20, ma50, ma100, ma200]
        alignment = 0
        if not any(pd.isna(m) for m in mas):
            if mas[0] > mas[1] > mas[2] > mas[3]:
                alignment = 100  # perfect bullish stack
            elif mas[0] < mas[1] < mas[2] < mas[3]:
                alignment = -100  # perfect bearish stack
            else:
                # Score based on order pairs
                pairs = [(mas[i] > mas[i + 1]) for i in range(3)]
                alignment = (sum(pairs) - sum(not p for p in pairs)) / 3 * 100

        # Combine: 60% MA position, 40% alignment
        position_score = ma_count / 4 * 100  # 0-100

        # Bias by amount above (capped at +/- 20%)
        avg_above = np.mean([above_ma20, above_ma50, above_ma100, above_ma200])
        position_score += float(np.clip(avg_above * 1.5, -25, 25))

        score = float(np.clip(position_score * 0.6 + (alignment + 100) / 2 * 0.4, 0, 100))

        # Label
        if score >= 80:
            label = "STRONG_BULLISH"
        elif score >= 60:
            label = "BULLISH"
        elif score >= 40:
            label = "NEUTRAL"
        elif score >= 20:
            label = "BEARISH"
        else:
            label = "STRONG_BEARISH"

        return score, label, {
            "above_ma20": above_ma20,
            "above_ma50": above_ma50,
            "above_ma100": above_ma100,
            "above_ma200": above_ma200,
        }

    @staticmethod
    def _liquidity_score(cdf: pd.DataFrame) -> tuple[float, str, float]:
        """Liquidity = blend of avg value, frequency, and consistency."""
        last_20 = cdf.tail(20)
        avg_value = float(last_20["value"].mean())
        avg_freq = float(last_20["frequency"].mean()) if "frequency" in last_20 else 0
        active_days = (last_20["volume"] > 0).sum()

        # Score from avg value (logarithmic — 1B = 50, 10B = 70, 100B = 90)
        if avg_value <= 0:
            value_score = 0
        else:
            value_score = float(np.clip(np.log10(max(avg_value, 1)) * 9.5 - 32, 0, 100))

        # Frequency score (>500 trades/day = strong)
        freq_score = float(np.clip(avg_freq / 1000 * 50, 0, 100))

        # Consistency score (active days)
        consistency_score = active_days / 20 * 100

        # CV of value (lower = more consistent / smoother)
        cv = (
            last_20["value"].std() / max(last_20["value"].mean(), 1)
            if last_20["value"].mean() > 0 else 1
        )
        smoothness = float(np.clip((2 - cv) * 50, 0, 100))

        score = (
            value_score * 0.45 +
            freq_score * 0.20 +
            consistency_score * 0.15 +
            smoothness * 0.20
        )
        score = float(np.clip(score, 0, 100))

        if score >= 80:
            label = "EXCELLENT"
        elif score >= 60:
            label = "GOOD"
        elif score >= 40:
            label = "MODERATE"
        elif score >= 20:
            label = "POOR"
        else:
            label = "ILLIQUID"

        return score, label, avg_value

    def _accum_distrib_scores(
        self,
        cdf: pd.DataFrame,
        ffdf: pd.DataFrame,
        bdf: pd.DataFrame,
    ) -> tuple[float, float]:
        """Separate accumulation and distribution scores (each 0-100)."""

        recent_cdf = cdf.tail(20)

        # Volume expansion (positive for accum if price flat or up)
        vol_recent = recent_cdf["volume"].tail(10).mean()
        vol_baseline = recent_cdf["volume"].head(10).mean()
        vol_change = (vol_recent / max(vol_baseline, 1) - 1) * 100  # %

        # Price compression (low volatility = good for accum setup)
        if recent_cdf["close"].mean() > 0:
            volatility = recent_cdf["close"].pct_change().tail(15).std() * 100
        else:
            volatility = 5

        # Foreign 20D net (positive = accum)
        foreign_net_20d = float(ffdf.tail(20)["net"].sum()) if not ffdf.empty else 0
        avg_value = max(recent_cdf["value"].mean(), 1)
        foreign_norm = foreign_net_20d / (avg_value * 20)  # -1..+1 typical range

        # Bandar inventory direction (positive = accum)
        if not bdf.empty:
            bandar_recent = bdf.tail(15)
            bandar_net = float(bandar_recent["net_lot"].sum())
            avg_lot_proxy = avg_value / max(recent_cdf["close"].mean(), 1) / 100
            bandar_norm = bandar_net / max(avg_lot_proxy * 15, 1)
        else:
            bandar_norm = 0

        # Price absolute change (markup vs markdown)
        price_change_20d = (
            recent_cdf["close"].iloc[-1] / recent_cdf["close"].iloc[0] - 1
        ) * 100 if len(recent_cdf) >= 2 else 0

        # ── Accumulation Score ──────────────────────────────────────
        # Higher when: foreign+, bandar+, vol expansion, price flat/up, volatility low
        accum = (
            50 +
            (foreign_norm * 25) +
            (bandar_norm * 25) +
            (vol_change * 0.2) +
            (max(0, -volatility + 3) * 3) +     # reward low vol
            (price_change_20d * 0.3)            # mild reward for up-trend
        )
        accum = float(np.clip(accum, 0, 100))

        # ── Distribution Score ──────────────────────────────────────
        # Higher when: foreign-, bandar-, vol expansion at top, price extended
        dist = (
            50 -
            (foreign_norm * 25) -
            (bandar_norm * 25) +
            (max(0, vol_change) * 0.15) +       # vol expansion at top = bad
            (max(0, price_change_20d - 10) * 1) # extended price
        )
        dist = float(np.clip(dist, 0, 100))

        return accum, dist

    @staticmethod
    def _wyckoff_stage(
        cdf: pd.DataFrame,
        accum_score: float,
        dist_score: float,
        trend_score: float,
        foreign_score: float,
    ) -> tuple[int, float]:
        """
        Classify Wyckoff stage 1-5.

        Logic:
            Stage 1 — Accumulation: low trend, high accum_score, low FOMO
            Stage 2 — Early Breakout: trend up, accum still high, vol expanding
            Stage 3 — Trend Expansion: high trend, momentum strong
            Stage 4 — Late Trend: trend high but momentum slowing
            Stage 5 — Distribution: high dist_score, foreign exit
        """
        recent = cdf.tail(40)
        if len(recent) < 20:
            return 1, 30.0

        # Recent return
        ret_20 = (recent["close"].iloc[-1] / recent["close"].iloc[-20] - 1) * 100

        # Volume slope (last 20 vs prev 20)
        vol_recent = recent["volume"].tail(15).mean()
        vol_prev = recent["volume"].head(15).mean()
        vol_expansion = vol_recent / max(vol_prev, 1)

        # Decide stage
        if dist_score > 65 and foreign_score < 45:
            stage = 5  # DISTRIBUTION
            quality = float(np.clip(dist_score, 0, 100))
        elif trend_score > 75 and ret_20 > 8 and vol_expansion < 1.05:
            stage = 4  # LATE_TREND (extended, vol drying)
            quality = float(np.clip(50 + (75 - dist_score) * 0.5, 0, 100))
        elif trend_score > 65 and ret_20 > 4:
            stage = 3  # TREND_EXPANSION
            quality = float(np.clip(60 + (trend_score - 60) * 0.8, 0, 100))
        elif accum_score > 60 and trend_score > 45 and vol_expansion > 1.15:
            stage = 2  # EARLY_BREAKOUT
            quality = float(np.clip(70 + (accum_score - 60) * 0.5, 0, 100))
        else:
            stage = 1  # ACCUMULATION (default early stage)
            quality = float(np.clip(accum_score, 0, 100))

        return stage, quality

    @staticmethod
    def _relative_strength(cdf: pd.DataFrame, ihsg: pd.Series) -> float:
        """RS vs IHSG over last 20 days."""
        if len(cdf) < 20 or len(ihsg) < 20:
            return 50.0
        try:
            stock_ret = cdf["close"].iloc[-1] / cdf["close"].iloc[-20] - 1
            ihsg_recent = ihsg.tail(20)
            bench_ret = ihsg_recent.iloc[-1] / ihsg_recent.iloc[0] - 1
            rs = (stock_ret - bench_ret) * 100  # in pct points
            return float(np.clip(50 + rs * 5, 0, 100))
        except Exception:
            return 50.0

    @staticmethod
    def _fomo_risk(cdf: pd.DataFrame) -> tuple[float, Optional[str]]:
        """High when: price extended above MA, RSI overbought, parabolic."""
        if len(cdf) < 20:
            return 0, None
        close = cdf["close"]
        ma20 = close.rolling(20, min_periods=5).mean().iloc[-1]
        latest = close.iloc[-1]
        if pd.isna(ma20) or ma20 <= 0:
            return 0, None

        pct_above_ma20 = (latest / ma20 - 1) * 100

        # 5-day return (parabolic risk)
        ret_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0

        # 10-day high
        high_10d = close.tail(10).max()
        is_at_high = (latest / high_10d) >= 0.99

        risk = 0
        warnings = []
        if pct_above_ma20 > 15:
            risk += 40
            warnings.append(f"price {pct_above_ma20:.1f}% di atas MA20 (extended)")
        elif pct_above_ma20 > 10:
            risk += 25
            warnings.append(f"price {pct_above_ma20:.1f}% di atas MA20")

        if ret_5d > 15:
            risk += 35
            warnings.append(f"5D return {ret_5d:+.1f}% (parabolic)")
        elif ret_5d > 8:
            risk += 20
            warnings.append(f"5D return {ret_5d:+.1f}%")

        if is_at_high:
            risk += 15

        risk = float(np.clip(risk, 0, 100))
        warning = " · ".join(warnings) if warnings and risk >= 50 else None
        return risk, warning

    @staticmethod
    def _opportunity_score(
        accum_score: float,
        foreign_score: float,
        trend_score: float,
        liquidity_score: float,
        wyckoff_stage: int,
        breakout_quality: float,
        relative_strength: float,
        fomo_risk: float,
    ) -> tuple[float, int, str]:
        """
        Final composite (0-100) blending all factors with stage-aware weights.

        Stage 1 (Accumulation): emphasize accum + foreign + breakout_quality
        Stage 2 (Early Breakout): emphasize breakout_quality + trend
        Stage 3 (Trend Expansion): emphasize trend + RS
        Stage 4 (Late Trend): penalize for FOMO risk, emphasize liquidity
        Stage 5 (Distribution): heavy penalty
        """
        if liquidity_score < 30:
            # Illiquid stocks immediately downgraded
            return 15.0, 1, "AVOID_ILLIQUID"

        if wyckoff_stage == 5:
            # Distribution = avoid
            score = (100 - accum_score) * 0.3 + foreign_score * 0.3 + liquidity_score * 0.4
            score = float(np.clip(score - 30, 0, 100))
            return score, 1, "AVOID"

        if wyckoff_stage == 4:
            # Late trend — selective
            score = (
                trend_score * 0.30 +
                liquidity_score * 0.25 +
                relative_strength * 0.25 +
                breakout_quality * 0.20
            )
            score -= fomo_risk * 0.4
        elif wyckoff_stage == 3:
            # Trend expansion — momentum focus
            score = (
                trend_score * 0.35 +
                relative_strength * 0.25 +
                breakout_quality * 0.15 +
                foreign_score * 0.15 +
                liquidity_score * 0.10
            )
            score -= fomo_risk * 0.25
        elif wyckoff_stage == 2:
            # Early breakout — best for entry
            score = (
                breakout_quality * 0.30 +
                accum_score * 0.20 +
                foreign_score * 0.20 +
                trend_score * 0.15 +
                liquidity_score * 0.10 +
                relative_strength * 0.05
            )
            score -= fomo_risk * 0.15
            score += 5  # bonus for being at sweet spot
        else:
            # Stage 1 — accumulation (early, but might be slow)
            score = (
                accum_score * 0.30 +
                foreign_score * 0.20 +
                breakout_quality * 0.15 +
                liquidity_score * 0.15 +
                relative_strength * 0.10 +
                trend_score * 0.10
            )

        score = float(np.clip(score, 0, 100))

        # Star rating + label
        if score >= 80:
            stars, label = 5, "ELITE_SETUP"
        elif score >= 65:
            stars, label = 4, "STRONG_SETUP"
        elif score >= 50:
            stars, label = 3, "WATCHLIST"
        elif score >= 30:
            stars, label = 2, "AVOID"
        else:
            stars, label = 1, "IGNORE"

        return score, stars, label

    @staticmethod
    def _trade_readiness(
        cdf: pd.DataFrame,
        opportunity_score: float,
        wyckoff_stage: int,
        fomo_risk: float,
        liquidity_score: float,
        trend_score: float,
    ) -> tuple[float, str, str]:
        """
        Single 0-100 score answering "buy this stock today?"

        Combines:
        - Opportunity score (foundational)
        - Stage timing (Stage 2 = best, Stage 1 = early-watch, others penalized)
        - Liquidity gate
        - FOMO penalty
        - Trend confirmation
        """
        if liquidity_score < 30:
            return 5.0, "AVOID", "Likuiditas terlalu rendah"

        # Base = opportunity score
        base = opportunity_score

        # Stage timing bonus
        if wyckoff_stage == 2:
            base += 8  # sweet spot
        elif wyckoff_stage == 1:
            base -= 5  # too early — patience
        elif wyckoff_stage == 3:
            base += 2  # acceptable
        elif wyckoff_stage == 4:
            base -= 12  # late
        elif wyckoff_stage == 5:
            base -= 25  # distribution

        # FOMO penalty
        base -= fomo_risk * 0.35

        # Trend confirmation
        if trend_score < 35:
            base -= 10  # bearish trend = risky entry

        score = float(np.clip(base, 0, 100))

        # Signal + reason
        if score >= 70:
            signal = "READY_BUY"
            reason = (
                f"Setup matang stage {wyckoff_stage} dengan trend dan likuiditas "
                f"konfirmasi. FOMO risk {fomo_risk:.0f}/100."
            )
        elif score >= 50:
            signal = "WATCH"
            reason = (
                f"Setup bagus tapi belum optimal (stage {wyckoff_stage}). "
                f"Tunggu trigger atau add pada pullback."
            )
        elif score >= 30:
            signal = "WAIT"
            reason = (
                f"Belum ada alasan kuat untuk masuk. Stage {wyckoff_stage}, "
                f"FOMO {fomo_risk:.0f}/100."
            )
        else:
            signal = "AVOID"
            reason = (
                f"Hindari — stage {wyckoff_stage} ({WYCKOFF_LABELS.get(wyckoff_stage)}), "
                f"score terlalu rendah."
            )

        return score, signal, reason
