"""
Pattern Detection Library.

Detects 8 classic bandarmology patterns from price + broker flow + foreign flow:

1. STEALTH_ACCUMULATION    — Price flat/down, institutional inventory rising
2. DISTRIBUTION_TOP        — Price near high, bandar exiting, retail FOMO
3. BREAKOUT_SETUP          — Volume contraction + inventory build, ready to fire
4. SPRING_REVERSAL         — Fake breakdown then sharp recovery (Wyckoff Spring)
5. UPTHRUST                — Fake breakout above range, then reversal
6. FOREIGN_DIVERGENCE      — Price down, foreign cumulative net up (or reverse)
7. CHANGE_OF_HANDS         — Bandar A exiting while Bandar B accumulating
8. MARKUP_CONFIRMATION     — All signals aligned: price+volume+inventory+foreign

Each detector returns:
  {
    "pattern": "STEALTH_ACCUMULATION",
    "detected": True,
    "confidence": 0-100,
    "evidence": {...},
    "interpretation": "Plain Indonesian explanation",
    "playbook": "What to do"
  }
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Candle, BrokerDailySummary, ForeignFlow, Broker, Symbol, AIScore,
)


# Catalog metadata — for the frontend pattern library page
PATTERN_CATALOG = [
    {
        "code": "STEALTH_ACCUMULATION",
        "name": "Stealth Accumulation",
        "name_id": "Akumulasi Diam-diam",
        "category": "ACCUMULATION",
        "description": (
            "Harga sideways atau turun pelan-pelan, tapi broker institusi diam-diam "
            "menambah inventory. Volume tetap rendah supaya tidak menarik perhatian. "
            "Ini fase paling awal dan paling menguntungkan untuk masuk."
        ),
        "playbook": (
            "Akumulasi bertahap. Stop loss di bawah support range. Target: tunggu "
            "konfirmasi markup (volume breakout) untuk add position."
        ),
        "win_rate_label": "70-85% (jika dikombinasi dengan konfirmasi)",
    },
    {
        "code": "DISTRIBUTION_TOP",
        "name": "Distribution Top",
        "name_id": "Distribusi di Puncak",
        "category": "DISTRIBUTION",
        "description": (
            "Harga di area resistance/all-time high, broker bandar mulai net sell, "
            "tapi retail justru FOMO membeli. Volume tinggi, foreign biasanya masih "
            "buy karena lag. Sinyal akhir trend naik."
        ),
        "playbook": (
            "Reduce position atau tighten trailing stop. Jangan add. Awasi konfirmasi "
            "markdown (close di bawah support range)."
        ),
        "win_rate_label": "60-75% sebagai exit signal",
    },
    {
        "code": "BREAKOUT_SETUP",
        "name": "Breakout Setup",
        "name_id": "Persiapan Breakout",
        "category": "ACCUMULATION",
        "description": (
            "Volume menyempit (contraction) sambil inventory institusi tetap naik "
            "perlahan. Harga membentuk pola triangle/flag. Persiapan sebelum "
            "explosive move."
        ),
        "playbook": (
            "Set buy stop di atas resistance + 1 ATR. Stop di bawah pattern. "
            "Target: 1.5-2x size pattern."
        ),
        "win_rate_label": "55-70% jika konfirmasi volume",
    },
    {
        "code": "SPRING_REVERSAL",
        "name": "Spring Reversal",
        "name_id": "Spring (Pembalikan Palsu)",
        "category": "REVERSAL",
        "description": (
            "Harga break support sementara untuk trigger stop loss retail, lalu "
            "langsung dibalas tekanan beli kuat dari bandar. Klasik Wyckoff Spring. "
            "Volume tinggi di hari spring."
        ),
        "playbook": (
            "Entry di hari berikutnya jika harga close kembali di atas support. "
            "Stop di bawah low spring. Target: top of range minimal."
        ),
        "win_rate_label": "65-80%",
    },
    {
        "code": "UPTHRUST",
        "name": "Upthrust",
        "name_id": "Upthrust (Breakout Palsu)",
        "category": "REVERSAL",
        "description": (
            "Harga breakout palsu di atas resistance untuk trigger buy stop retail, "
            "tapi langsung dibalas distribusi bandar. Klasik Wyckoff Upthrust."
        ),
        "playbook": (
            "Avoid long. Bisa entry short jika konfirmasi close balik di bawah "
            "resistance. Stop di atas high upthrust."
        ),
        "win_rate_label": "60-75% sebagai exit/short signal",
    },
    {
        "code": "FOREIGN_DIVERGENCE",
        "name": "Foreign Flow Divergence",
        "name_id": "Divergensi Foreign Flow",
        "category": "DIVERGENCE",
        "description": (
            "Harga bergerak berlawanan dengan akumulasi foreign. Bullish: harga turun "
            "tapi foreign net cumulative naik. Bearish: harga naik tapi foreign net "
            "cumulative turun."
        ),
        "playbook": (
            "Bullish divergence: cari entry di support. Bearish divergence: reduce "
            "position, awasi konfirmasi pembalikan."
        ),
        "win_rate_label": "55-70%",
    },
    {
        "code": "CHANGE_OF_HANDS",
        "name": "Change of Hands",
        "name_id": "Pertukaran Bandar",
        "category": "TRANSITION",
        "description": (
            "Satu bandar besar yang sudah lama hold (inventory tinggi) mulai jual "
            "konsisten, sementara bandar lain mulai akumulasi. Sinyal pergantian "
            "kontrol saham."
        ),
        "playbook": (
            "Wait & see. Identifikasi bandar baru — kalau punya track record bagus, "
            "bisa follow. Kalau bandar lama lebih kuat, kemungkinan markdown."
        ),
        "win_rate_label": "Mixed — depends on new bandar quality",
    },
    {
        "code": "MARKUP_CONFIRMATION",
        "name": "Markup Confirmation",
        "name_id": "Konfirmasi Fase Markup",
        "category": "TREND",
        "description": (
            "Semua sinyal sejalan: harga break resistance, volume meningkat, "
            "inventory bandar naik, foreign net buy. Fase markup terkonfirmasi. "
            "Trend bullish kuat."
        ),
        "playbook": (
            "Add position pada pullback minor. Trail stop di bawah MA20. Hold sampai "
            "muncul sinyal distribusi."
        ),
        "win_rate_label": "70-85% selama trend",
    },
]


# ============================================================
# Service
# ============================================================

class PatternService:

    def __init__(self, db: Session):
        self.db = db
        # Cache broker metadata
        brokers = self.db.query(Broker).all()
        self.foreign_set = {b.code for b in brokers if b.is_foreign}
        self.bandar_set = {
            b.code for b in brokers
            if b.cluster_label in ("market_maker", "institutional")
        }
        self.retail_set = {b.code for b in brokers if b.cluster_label == "retail"}

    # ------------------------------------------------------------------ #
    # Public entry points
    # ------------------------------------------------------------------ #

    def detect_all(self, symbol: str, lookback_days: int = 60) -> dict:
        """Run all 8 detectors on a single symbol."""
        ctx = self._build_context(symbol, lookback_days)
        if ctx is None:
            return {"symbol": symbol, "patterns": [], "no_data": True}

        results = []
        for detector in [
            self._detect_stealth_accumulation,
            self._detect_distribution_top,
            self._detect_breakout_setup,
            self._detect_spring_reversal,
            self._detect_upthrust,
            self._detect_foreign_divergence,
            self._detect_change_of_hands,
            self._detect_markup_confirmation,
        ]:
            r = detector(ctx)
            if r is not None:
                results.append(r)

        # Sort: detected first, then by confidence
        results.sort(
            key=lambda x: (-int(x["detected"]), -x["confidence"])
        )
        return {
            "symbol": symbol,
            "as_of": ctx["latest_date"].isoformat(),
            "lookback_days": lookback_days,
            "patterns": results,
        }

    def scan_universe(
        self,
        pattern_code: str,
        min_confidence: float = 60,
        limit: int = 50,
    ) -> dict:
        """Scan all symbols for a specific pattern."""
        symbols = self.db.query(Symbol).filter(Symbol.is_active == True).all()
        hits = []
        for s in symbols:
            ctx = self._build_context(s.code, lookback_days=60)
            if ctx is None:
                continue
            detector = self._dispatch(pattern_code)
            if detector is None:
                return {"error": "Unknown pattern", "pattern_code": pattern_code}
            r = detector(ctx)
            if r and r["detected"] and r["confidence"] >= min_confidence:
                hits.append({
                    "symbol": s.code,
                    "name": s.name,
                    "sector": s.sector,
                    "confidence": r["confidence"],
                    "evidence": r["evidence"],
                })
        hits.sort(key=lambda x: -x["confidence"])
        return {
            "pattern_code": pattern_code,
            "total_hits": len(hits),
            "results": hits[:limit],
        }

    @staticmethod
    def catalog() -> list[dict]:
        """Return the full pattern catalog."""
        return PATTERN_CATALOG

    # ------------------------------------------------------------------ #
    # Context builder
    # ------------------------------------------------------------------ #

    def _build_context(self, symbol: str, lookback_days: int) -> Optional[dict]:
        """Pre-fetch all data needed by detectors."""
        candles = (
            self.db.query(Candle)
            .filter(Candle.symbol == symbol)
            .order_by(Candle.date.desc())
            .limit(lookback_days)
            .all()
        )
        if len(candles) < 20:
            return None
        candles.reverse()
        cdf = pd.DataFrame([{
            "date": c.date, "open": c.open, "high": c.high, "low": c.low,
            "close": c.close, "volume": c.volume, "value": c.value,
        } for c in candles])

        latest_date = cdf["date"].iloc[-1]
        start_date = cdf["date"].iloc[0]

        # Foreign flow
        ff = (
            self.db.query(ForeignFlow)
            .filter(
                ForeignFlow.symbol == symbol,
                ForeignFlow.date >= start_date,
                ForeignFlow.date <= latest_date,
            )
            .order_by(ForeignFlow.date)
            .all()
        )
        ff_df = pd.DataFrame([{
            "date": r.date,
            "buy": r.foreign_buy_value, "sell": r.foreign_sell_value,
            "net": r.foreign_net_value,
        } for r in ff])
        if not ff_df.empty:
            ff_df["cum"] = ff_df["net"].cumsum()

        # Broker summary aggregated by broker
        bds = (
            self.db.query(BrokerDailySummary)
            .filter(
                BrokerDailySummary.symbol == symbol,
                BrokerDailySummary.date >= start_date,
                BrokerDailySummary.date <= latest_date,
            )
            .all()
        )
        bdf = pd.DataFrame([{
            "date": r.date, "broker": r.broker_code,
            "net_lot": r.net_lot, "net_value": r.net_value,
            "buy_value": r.buy_value, "sell_value": r.sell_value,
        } for r in bds])

        return {
            "symbol": symbol,
            "candles": cdf,
            "foreign": ff_df,
            "brokers": bdf,
            "latest_date": latest_date,
            "lookback_days": lookback_days,
        }

    # ------------------------------------------------------------------ #
    # Helpers shared across detectors
    # ------------------------------------------------------------------ #

    @staticmethod
    def _result(code: str, detected: bool, confidence: float,
                evidence: dict, interpretation: str) -> dict:
        meta = next((p for p in PATTERN_CATALOG if p["code"] == code), {})
        return {
            "pattern": code,
            "name": meta.get("name", code),
            "name_id": meta.get("name_id", code),
            "category": meta.get("category"),
            "detected": detected,
            "confidence": round(confidence, 1),
            "evidence": evidence,
            "interpretation": interpretation,
            "playbook": meta.get("playbook", ""),
        }

    def _bandar_inventory(self, ctx: dict) -> pd.Series:
        """Cumulative net lot across institutional/market_maker brokers."""
        if ctx["brokers"].empty:
            return pd.Series(dtype=float)
        b = ctx["brokers"][ctx["brokers"]["broker"].isin(self.bandar_set)]
        if b.empty:
            return pd.Series(dtype=float)
        daily = b.groupby("date")["net_lot"].sum().sort_index()
        return daily.cumsum()

    def _retail_inventory(self, ctx: dict) -> pd.Series:
        b = ctx["brokers"][ctx["brokers"]["broker"].isin(self.retail_set)]
        if b.empty:
            return pd.Series(dtype=float)
        daily = b.groupby("date")["net_lot"].sum().sort_index()
        return daily.cumsum()

    def _dispatch(self, code: str):
        return {
            "STEALTH_ACCUMULATION": self._detect_stealth_accumulation,
            "DISTRIBUTION_TOP": self._detect_distribution_top,
            "BREAKOUT_SETUP": self._detect_breakout_setup,
            "SPRING_REVERSAL": self._detect_spring_reversal,
            "UPTHRUST": self._detect_upthrust,
            "FOREIGN_DIVERGENCE": self._detect_foreign_divergence,
            "CHANGE_OF_HANDS": self._detect_change_of_hands,
            "MARKUP_CONFIRMATION": self._detect_markup_confirmation,
        }.get(code)

    # ------------------------------------------------------------------ #
    # 1. STEALTH_ACCUMULATION
    # ------------------------------------------------------------------ #

    def _detect_stealth_accumulation(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        if len(cdf) < 30:
            return None

        recent = cdf.tail(40)
        price_change_pct = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1) * 100
        price_range_pct = (
            (recent["close"].max() - recent["close"].min())
            / recent["close"].mean() * 100
        )

        bandar_inv = self._bandar_inventory(ctx)
        if bandar_inv.empty:
            return self._result(
                "STEALTH_ACCUMULATION", False, 0,
                {"reason": "no bandar broker activity"},
                "Tidak ada aktivitas bandar terdeteksi."
            )

        bandar_growth = bandar_inv.iloc[-1] - bandar_inv.iloc[0]

        # Volume contraction check (last 20D vs prev 20D)
        if len(recent) >= 40:
            vol_recent = recent["volume"].tail(20).mean()
            vol_prev = recent["volume"].head(20).mean()
            vol_ratio = vol_recent / vol_prev if vol_prev > 0 else 1
        else:
            vol_ratio = 1

        # Conditions
        cond_price_flat = abs(price_change_pct) < 5
        cond_range_tight = price_range_pct < 15
        cond_bandar_buy = bandar_growth > 0
        cond_volume_low = vol_ratio < 1.1

        score = (
            (40 if cond_price_flat else 0) +
            (20 if cond_range_tight else 0) +
            (30 if cond_bandar_buy else 0) +
            (10 if cond_volume_low else 0)
        )

        detected = score >= 60 and cond_bandar_buy

        evidence = {
            "price_change_pct": round(price_change_pct, 2),
            "price_range_pct": round(price_range_pct, 2),
            "bandar_lot_growth": int(bandar_growth),
            "volume_ratio_recent_vs_prev": round(vol_ratio, 2),
        }
        interp = (
            f"Selama {len(recent)} hari terakhir, harga hanya bergerak {price_change_pct:+.2f}% "
            f"dengan range {price_range_pct:.1f}%, tapi inventory bandar institusional "
            f"naik {int(bandar_growth):,} lot. "
            + ("Pola akumulasi tersembunyi terkonfirmasi." if detected
               else "Belum cukup kuat sebagai akumulasi tersembunyi.")
        )
        return self._result(
            "STEALTH_ACCUMULATION", detected, score, evidence, interp
        )

    # ------------------------------------------------------------------ #
    # 2. DISTRIBUTION_TOP
    # ------------------------------------------------------------------ #

    def _detect_distribution_top(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        if len(cdf) < 40:
            return None

        recent = cdf.tail(40)
        latest_close = recent["close"].iloc[-1]
        period_high = recent["high"].max()
        # Distance from high (smaller = more bearish for distribution)
        pct_from_high = (latest_close / period_high - 1) * 100

        bandar_inv = self._bandar_inventory(ctx)
        retail_inv = self._retail_inventory(ctx)

        # Last 20D bandar net lot direction
        bandar_recent_change = (
            bandar_inv.tail(20).iloc[-1] - bandar_inv.tail(20).iloc[0]
            if len(bandar_inv) >= 20 else 0
        )
        retail_recent_change = (
            retail_inv.tail(20).iloc[-1] - retail_inv.tail(20).iloc[0]
            if len(retail_inv) >= 20 else 0
        )

        # Volume should be elevated
        vol_recent = recent["volume"].tail(15).mean()
        vol_prev = recent["volume"].head(15).mean()
        vol_ratio = vol_recent / vol_prev if vol_prev > 0 else 1

        cond_near_high = pct_from_high > -5  # within 5% of high
        cond_bandar_sell = bandar_recent_change < 0
        cond_retail_buy = retail_recent_change > 0
        cond_high_volume = vol_ratio > 1.1

        score = (
            (30 if cond_near_high else 0) +
            (35 if cond_bandar_sell else 0) +
            (20 if cond_retail_buy else 0) +
            (15 if cond_high_volume else 0)
        )
        detected = score >= 65 and cond_bandar_sell

        evidence = {
            "pct_from_period_high": round(pct_from_high, 2),
            "bandar_lot_change_20d": int(bandar_recent_change),
            "retail_lot_change_20d": int(retail_recent_change),
            "volume_ratio": round(vol_ratio, 2),
        }
        interp = (
            f"Harga {pct_from_high:+.2f}% dari high, bandar net "
            f"{int(bandar_recent_change):+,} lot, retail net "
            f"{int(retail_recent_change):+,} lot dalam 20D terakhir. "
            + ("Pola distribusi di puncak terdeteksi." if detected
               else "Pola distribusi belum lengkap.")
        )
        return self._result("DISTRIBUTION_TOP", detected, score, evidence, interp)

    # ------------------------------------------------------------------ #
    # 3. BREAKOUT_SETUP
    # ------------------------------------------------------------------ #

    def _detect_breakout_setup(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        if len(cdf) < 40:
            return None

        recent = cdf.tail(40)

        # Volume contraction (last 10D significantly lower than prev 30D)
        vol_recent = recent["volume"].tail(10).mean()
        vol_prev = recent["volume"].head(30).mean()
        vol_contraction = vol_recent / vol_prev if vol_prev > 0 else 1

        # Price compression (last 10D range vs prev 30D range)
        recent_10 = recent.tail(10)
        prev_30 = recent.head(30)
        range_recent = recent_10["high"].max() - recent_10["low"].min()
        range_prev = prev_30["high"].max() - prev_30["low"].min()
        compression = range_recent / range_prev if range_prev > 0 else 1

        # Bandar still accumulating
        bandar_inv = self._bandar_inventory(ctx)
        bandar_change = (
            bandar_inv.tail(10).iloc[-1] - bandar_inv.tail(10).iloc[0]
            if len(bandar_inv) >= 10 else 0
        )

        # Near resistance test (latest close vs period high)
        period_high = recent.head(30)["high"].max()
        latest_close = recent["close"].iloc[-1]
        proximity = (latest_close / period_high - 1) * 100  # negative means below

        cond_vol_contract = vol_contraction < 0.8
        cond_compress = compression < 0.5
        cond_bandar_buy = bandar_change > 0
        cond_near_resistance = -8 < proximity < 2

        score = (
            (25 if cond_vol_contract else 0) +
            (30 if cond_compress else 0) +
            (25 if cond_bandar_buy else 0) +
            (20 if cond_near_resistance else 0)
        )
        detected = score >= 65

        evidence = {
            "volume_contraction_ratio": round(vol_contraction, 2),
            "price_compression_ratio": round(compression, 2),
            "bandar_lot_growth_10d": int(bandar_change),
            "proximity_to_resistance_pct": round(proximity, 2),
        }
        interp = (
            f"Volume kontraksi {vol_contraction:.2f}x, range kompres "
            f"{compression:.2f}x, bandar +{int(bandar_change):,} lot, jarak "
            f"{proximity:+.2f}% dari resistance. "
            + ("Setup breakout terkonfirmasi — siap watchlist." if detected
               else "Setup belum lengkap.")
        )
        return self._result("BREAKOUT_SETUP", detected, score, evidence, interp)

    # ------------------------------------------------------------------ #
    # 4. SPRING_REVERSAL
    # ------------------------------------------------------------------ #

    def _detect_spring_reversal(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        if len(cdf) < 30:
            return None

        # Find recent support (lowest low in days [-30:-5])
        ref_window = cdf.iloc[-30:-5]
        if ref_window.empty:
            return None
        support = ref_window["low"].min()

        # Look for spring in last 5 days
        recent_5 = cdf.tail(5)
        spring_day = None
        for idx, row in recent_5.iterrows():
            if row["low"] < support and row["close"] > support:
                spring_day = row
                break

        if spring_day is None:
            return self._result(
                "SPRING_REVERSAL", False, 0,
                {"support": float(support)},
                "Tidak ada Spring pattern terdeteksi dalam 5 hari terakhir."
            )

        # Validate: volume spike + close near high of day
        spring_vol = spring_day["volume"]
        avg_vol = cdf.tail(20)["volume"].mean()
        vol_spike = spring_vol / avg_vol if avg_vol > 0 else 1

        day_range = spring_day["high"] - spring_day["low"]
        close_position = (
            (spring_day["close"] - spring_day["low"]) / day_range
            if day_range > 0 else 0.5
        )

        # Bandar action that day
        bdf = ctx["brokers"]
        spring_bandar = 0
        if not bdf.empty:
            day_brokers = bdf[
                (bdf["date"] == spring_day["date"])
                & bdf["broker"].isin(self.bandar_set)
            ]
            spring_bandar = int(day_brokers["net_lot"].sum())

        cond_break_below = spring_day["low"] < support
        cond_close_above = spring_day["close"] > support
        cond_vol_spike = vol_spike > 1.3
        cond_strong_close = close_position > 0.6
        cond_bandar_buy = spring_bandar > 0

        score = (
            (15 if cond_break_below else 0) +
            (25 if cond_close_above else 0) +
            (20 if cond_vol_spike else 0) +
            (20 if cond_strong_close else 0) +
            (20 if cond_bandar_buy else 0)
        )
        detected = score >= 70

        evidence = {
            "support_level": float(support),
            "spring_date": spring_day["date"].isoformat(),
            "spring_low": float(spring_day["low"]),
            "spring_close": float(spring_day["close"]),
            "volume_spike": round(vol_spike, 2),
            "close_position_in_range": round(close_position, 2),
            "bandar_net_lot_that_day": spring_bandar,
        }
        interp = (
            f"Pada {spring_day['date'].isoformat()}, harga break support {support:.0f} "
            f"ke {spring_day['low']:.0f} lalu close di {spring_day['close']:.0f} "
            f"(close position {close_position:.0%} dari range), volume "
            f"{vol_spike:.2f}x rata-rata. "
            + ("Spring Reversal terkonfirmasi." if detected
               else "Spring belum cukup kuat.")
        )
        return self._result("SPRING_REVERSAL", detected, score, evidence, interp)

    # ------------------------------------------------------------------ #
    # 5. UPTHRUST
    # ------------------------------------------------------------------ #

    def _detect_upthrust(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        if len(cdf) < 30:
            return None

        ref_window = cdf.iloc[-30:-5]
        if ref_window.empty:
            return None
        resistance = ref_window["high"].max()

        recent_5 = cdf.tail(5)
        ut_day = None
        for idx, row in recent_5.iterrows():
            if row["high"] > resistance and row["close"] < resistance:
                ut_day = row
                break

        if ut_day is None:
            return self._result(
                "UPTHRUST", False, 0,
                {"resistance": float(resistance)},
                "Tidak ada Upthrust pattern terdeteksi dalam 5 hari terakhir."
            )

        ut_vol = ut_day["volume"]
        avg_vol = cdf.tail(20)["volume"].mean()
        vol_spike = ut_vol / avg_vol if avg_vol > 0 else 1

        day_range = ut_day["high"] - ut_day["low"]
        close_position = (
            (ut_day["close"] - ut_day["low"]) / day_range
            if day_range > 0 else 0.5
        )

        bdf = ctx["brokers"]
        ut_bandar = 0
        if not bdf.empty:
            day_brokers = bdf[
                (bdf["date"] == ut_day["date"])
                & bdf["broker"].isin(self.bandar_set)
            ]
            ut_bandar = int(day_brokers["net_lot"].sum())

        cond_break_above = ut_day["high"] > resistance
        cond_close_below = ut_day["close"] < resistance
        cond_vol_spike = vol_spike > 1.3
        cond_weak_close = close_position < 0.4
        cond_bandar_sell = ut_bandar < 0

        score = (
            (15 if cond_break_above else 0) +
            (25 if cond_close_below else 0) +
            (20 if cond_vol_spike else 0) +
            (20 if cond_weak_close else 0) +
            (20 if cond_bandar_sell else 0)
        )
        detected = score >= 70

        evidence = {
            "resistance_level": float(resistance),
            "upthrust_date": ut_day["date"].isoformat(),
            "upthrust_high": float(ut_day["high"]),
            "upthrust_close": float(ut_day["close"]),
            "volume_spike": round(vol_spike, 2),
            "close_position_in_range": round(close_position, 2),
            "bandar_net_lot_that_day": ut_bandar,
        }
        interp = (
            f"Pada {ut_day['date'].isoformat()}, harga break resistance {resistance:.0f} "
            f"ke {ut_day['high']:.0f} lalu close kembali ke {ut_day['close']:.0f} "
            f"(close position {close_position:.0%}), volume {vol_spike:.2f}x. "
            + ("Upthrust terkonfirmasi." if detected
               else "Upthrust belum cukup kuat.")
        )
        return self._result("UPTHRUST", detected, score, evidence, interp)

    # ------------------------------------------------------------------ #
    # 6. FOREIGN_DIVERGENCE
    # ------------------------------------------------------------------ #

    def _detect_foreign_divergence(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        ff = ctx["foreign"]
        if cdf.empty or ff.empty or len(cdf) < 20:
            return None

        recent_cdf = cdf.tail(20)
        # Align with foreign by joining on date
        merged = recent_cdf.merge(ff[["date", "cum"]], on="date", how="inner")
        if len(merged) < 10:
            return None

        price_pct = (merged["close"].iloc[-1] / merged["close"].iloc[0] - 1) * 100
        cum_change = merged["cum"].iloc[-1] - merged["cum"].iloc[0]
        avg_daily_value = ff.tail(20)["buy"].mean() + ff.tail(20)["sell"].mean()
        cum_normalized = cum_change / max(avg_daily_value, 1)

        div_type = None
        confidence = 0
        if price_pct < -1.5 and cum_normalized > 0.05:
            div_type = "BULLISH"
            confidence = min(100, (abs(price_pct) * 10) + (cum_normalized * 50))
        elif price_pct > 2.0 and cum_normalized < -0.05:
            div_type = "BEARISH"
            confidence = min(100, (price_pct * 10) + (abs(cum_normalized) * 50))

        detected = div_type is not None
        evidence = {
            "divergence_type": div_type,
            "price_change_20d_pct": round(price_pct, 2),
            "cum_foreign_change_idr": int(cum_change),
            "cum_foreign_normalized": round(cum_normalized, 3),
        }
        if div_type == "BULLISH":
            interp = (
                f"Harga turun {price_pct:.2f}% dalam 20 hari, tapi foreign cumulative "
                f"net naik. Divergence bullish — kemungkinan bottoming."
            )
        elif div_type == "BEARISH":
            interp = (
                f"Harga naik {price_pct:.2f}% dalam 20 hari, tapi foreign cumulative "
                f"net turun. Divergence bearish — kemungkinan topping."
            )
        else:
            interp = "Tidak ada divergensi signifikan antara harga dan foreign flow."
        return self._result(
            "FOREIGN_DIVERGENCE", detected, confidence, evidence, interp
        )

    # ------------------------------------------------------------------ #
    # 7. CHANGE_OF_HANDS
    # ------------------------------------------------------------------ #

    def _detect_change_of_hands(self, ctx: dict) -> dict:
        bdf = ctx["brokers"]
        if bdf.empty:
            return None

        # Compare first half and second half of lookback period
        bdf_sorted = bdf.sort_values("date")
        n = len(bdf_sorted["date"].unique())
        if n < 30:
            return None

        median_date = bdf_sorted["date"].sort_values().unique()[n // 2]

        first_half = bdf_sorted[bdf_sorted["date"] < median_date]
        second_half = bdf_sorted[bdf_sorted["date"] >= median_date]

        # Per-broker net in each half (only bandar)
        f_agg = (
            first_half[first_half["broker"].isin(self.bandar_set)]
            .groupby("broker")["net_value"].sum()
        )
        s_agg = (
            second_half[second_half["broker"].isin(self.bandar_set)]
            .groupby("broker")["net_value"].sum()
        )

        # Find broker that flipped from BUY → SELL (exiting old bandar)
        exiting = []
        entering = []
        all_brokers = set(f_agg.index) | set(s_agg.index)
        for b in all_brokers:
            f_val = f_agg.get(b, 0)
            s_val = s_agg.get(b, 0)
            # Significant flip
            if f_val > 5e9 and s_val < -3e9:
                exiting.append({"broker": b, "first_half_net": int(f_val),
                                 "second_half_net": int(s_val)})
            elif f_val < -3e9 and s_val > 5e9:
                entering.append({"broker": b, "first_half_net": int(f_val),
                                  "second_half_net": int(s_val)})
            elif abs(f_val) < 1e9 and s_val > 5e9:
                entering.append({"broker": b, "first_half_net": int(f_val),
                                  "second_half_net": int(s_val)})

        detected = len(exiting) > 0 and len(entering) > 0
        confidence = min(100, (len(exiting) + len(entering)) * 25)

        evidence = {
            "exiting_brokers": exiting[:5],
            "entering_brokers": entering[:5],
        }
        if detected:
            interp = (
                f"Terdeteksi pergantian kontrol: {len(exiting)} broker bandar exit, "
                f"{len(entering)} broker baru masuk. Periksa kualitas bandar baru "
                f"untuk evaluasi outlook."
            )
        else:
            interp = "Tidak ada pergantian bandar signifikan terdeteksi."
        return self._result("CHANGE_OF_HANDS", detected, confidence, evidence, interp)

    # ------------------------------------------------------------------ #
    # 8. MARKUP_CONFIRMATION
    # ------------------------------------------------------------------ #

    def _detect_markup_confirmation(self, ctx: dict) -> dict:
        cdf = ctx["candles"]
        ff = ctx["foreign"]
        if len(cdf) < 30 or ff.empty:
            return None

        recent = cdf.tail(20)
        prev = cdf.head(min(30, len(cdf) - 20))

        # Price breakout
        prev_high = prev["high"].max()
        latest_close = recent["close"].iloc[-1]
        breakout_pct = (latest_close / prev_high - 1) * 100

        # Volume expansion
        vol_recent = recent["volume"].tail(10).mean()
        vol_baseline = cdf["volume"].mean()
        vol_expansion = vol_recent / vol_baseline if vol_baseline > 0 else 1

        # Bandar inventory still rising
        bandar_inv = self._bandar_inventory(ctx)
        if bandar_inv.empty:
            bandar_growth = 0
        else:
            bandar_growth = bandar_inv.iloc[-1] - bandar_inv.iloc[0]

        # Foreign net positive recently
        foreign_recent_net = ff.tail(10)["net"].sum() if not ff.empty else 0

        cond_breakout = breakout_pct > 1.5
        cond_volume_exp = vol_expansion > 1.2
        cond_bandar_buy = bandar_growth > 0
        cond_foreign_buy = foreign_recent_net > 0

        score = (
            (30 if cond_breakout else 0) +
            (25 if cond_volume_exp else 0) +
            (25 if cond_bandar_buy else 0) +
            (20 if cond_foreign_buy else 0)
        )
        detected = score >= 75

        evidence = {
            "breakout_pct": round(breakout_pct, 2),
            "volume_expansion_ratio": round(vol_expansion, 2),
            "bandar_lot_growth": int(bandar_growth),
            "foreign_net_10d_idr": int(foreign_recent_net),
        }
        interp = (
            f"Harga breakout {breakout_pct:+.2f}% dari high lama, volume "
            f"{vol_expansion:.2f}x baseline, bandar +{int(bandar_growth):,} lot, "
            f"foreign 10D net Rp {int(foreign_recent_net):,}. "
            + ("Markup terkonfirmasi — trend bullish." if detected
               else "Markup belum sepenuhnya terkonfirmasi.")
        )
        return self._result(
            "MARKUP_CONFIRMATION", detected, score, evidence, interp
        )
