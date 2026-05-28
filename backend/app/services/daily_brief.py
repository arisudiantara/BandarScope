"""
Daily Brief Generator.

Generates an end-of-day market intelligence report combining:
- Market summary (advance/decline, value, foreign net)
- Top accumulation picks (BandarScore)
- Distribution warnings
- Sector rotation snapshot (Leading / Improving / Weakening / Lagging)
- Pattern alerts across the universe
- Stocks-to-watch (multi-day persistence)

Output styles:
- structured (dict for API/UI)
- markdown (for email/PDF/Telegram)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AIScore, Symbol, ForeignFlow, Candle, Sector,
)
from app.services.sector import SectorService
from app.services.patterns import PatternService, PATTERN_CATALOG


# Patterns whose detection should be highlighted in the brief
HIGHLIGHT_PATTERNS = [
    "STEALTH_ACCUMULATION",
    "BREAKOUT_SETUP",
    "MARKUP_CONFIRMATION",
    "SPRING_REVERSAL",
    "DISTRIBUTION_TOP",
    "UPTHRUST",
    "FOREIGN_DIVERGENCE",
    "CHANGE_OF_HANDS",
]


class DailyBriefService:

    def __init__(self, db: Session):
        self.db = db
        self.sector_svc = SectorService(db)
        self.pattern_svc = PatternService(db)

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #

    def generate(
        self,
        target_date: Optional[date] = None,
        max_pattern_scans: int = 50,
    ) -> dict:
        """Build the full brief as a structured dict."""
        latest_score_date = self.db.query(func.max(AIScore.date)).scalar()
        if not latest_score_date:
            return {"error": "No data available"}
        if target_date is None:
            target_date = latest_score_date

        market = self._market_summary(target_date)
        top_accum = self._top_accumulation(target_date, limit=10)
        distribution = self._distribution_warnings(target_date, limit=5)
        rotation = self._rotation_snapshot()
        sectors = self._sector_summary()
        patterns = self._pattern_alerts(top_accum, distribution, max_pattern_scans)
        watch = self._stocks_to_watch(target_date, top_accum, distribution)

        return {
            "as_of": target_date.isoformat(),
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "market_summary": market,
            "top_accumulation": top_accum,
            "distribution_warnings": distribution,
            "sector_rotation": rotation,
            "sector_capital_flow": sectors,
            "pattern_alerts": patterns,
            "stocks_to_watch": watch,
        }

    def to_markdown(self, brief: dict) -> str:
        """Render structured brief into markdown string."""
        lines = []
        date_str = brief["as_of"]

        lines.append(f"# BandarScope Daily Brief — {date_str}")
        lines.append("")
        lines.append("> *Smart money intelligence untuk perencanaan trade besok.*")
        lines.append("")

        # ─── Executive Summary ──────────────────────────────────────
        m = brief["market_summary"]
        lines.append("## Ringkasan Pasar")
        lines.append("")
        lines.append(f"- **Advance/Decline**: {m['advance']} / {m['decline']} "
                     f"(ratio {m['advance_ratio']:.0%})")
        lines.append(f"- **Total Value**: {self._fmt_idr(m['total_value'])}")
        lines.append(f"- **Foreign Net Flow**: {self._fmt_idr(m['foreign_net'])} "
                     f"({'inflow' if m['foreign_net'] >= 0 else 'outflow'})")
        lines.append(f"- **Avg Change**: {m['avg_change']:+.2f}%")
        lines.append("")

        # Key Findings (auto-generated narrative)
        findings = self._key_findings(brief)
        if findings:
            lines.append("### Temuan Utama")
            for f in findings:
                lines.append(f"- {f}")
            lines.append("")

        # ─── Top Accumulation ──────────────────────────────────────
        lines.append("## Top Accumulation Picks")
        lines.append("")
        if brief["top_accumulation"]:
            lines.append("| # | Symbol | Sector | Close | Foreign Net 20D | "
                         "Bandar Score | Behavior |")
            lines.append("|---|---|---|---:|---:|---:|---|")
            for i, s in enumerate(brief["top_accumulation"][:8], 1):
                lines.append(
                    f"| {i} | **{s['symbol']}** | {s['sector']} | "
                    f"{s['close']:,.0f} | {self._fmt_idr(s['foreign_net'])} | "
                    f"{s['bandar_score']:.0f} | {s['behavior_label']} |"
                )
        else:
            lines.append("*Tidak ada saham dengan signal akumulasi kuat hari ini.*")
        lines.append("")

        # ─── Distribution Warnings ─────────────────────────────────
        lines.append("## Distribution Warnings")
        lines.append("")
        if brief["distribution_warnings"]:
            lines.append("| # | Symbol | Sector | Close | Foreign Net 20D | "
                         "Bandar Score | Behavior |")
            lines.append("|---|---|---|---:|---:|---:|---|")
            for i, s in enumerate(brief["distribution_warnings"][:5], 1):
                lines.append(
                    f"| {i} | **{s['symbol']}** | {s['sector']} | "
                    f"{s['close']:,.0f} | {self._fmt_idr(s['foreign_net'])} | "
                    f"{s['bandar_score']:.0f} | {s['behavior_label']} |"
                )
        else:
            lines.append("*Tidak ada warning distribusi signifikan hari ini.*")
        lines.append("")

        # ─── Sector Rotation ───────────────────────────────────────
        lines.append("## Sector Rotation (RRG)")
        lines.append("")
        rotation = brief["sector_rotation"]
        for q in ["leading", "improving", "weakening", "lagging"]:
            secs = rotation.get(q, [])
            if not secs:
                continue
            label = q.upper()
            lines.append(f"**{label}**: " + ", ".join(
                f"`{s['code']}` (RS {s['rs_ratio']:.1f} / Mom {s['rs_momentum']:.1f})"
                for s in secs
            ))
        lines.append("")

        # ─── Sector Capital Flow ───────────────────────────────────
        lines.append("## Capital Flow per Sektor")
        lines.append("")
        lines.append("| Rank | Sector | Foreign Net 5D | Momentum | Flow |")
        lines.append("|---|---|---:|---:|---|")
        for s in brief["sector_capital_flow"][:8]:
            lines.append(
                f"| #{s['rank']} | {s['name']} | {self._fmt_idr(s['foreign_net_5d'])} "
                f"| {s['momentum_pct']:+.2f}% | {s['flow_label'].replace('_', ' ')} |"
            )
        lines.append("")

        # ─── Pattern Alerts ────────────────────────────────────────
        lines.append("## Pattern Alerts")
        lines.append("")
        if brief["pattern_alerts"]:
            for p in brief["pattern_alerts"][:8]:
                lines.append(
                    f"- **{p['symbol']}** ({p['sector']}) — "
                    f"`{p['pattern']}` (confidence {p['confidence']:.0f})  "
                )
                lines.append(f"  > {p['interpretation']}")
            lines.append("")
        else:
            lines.append("*Tidak ada pattern signifikan terdeteksi.*")
            lines.append("")

        # ─── Stocks to Watch ───────────────────────────────────────
        lines.append("## Stocks to Watch")
        lines.append("")
        if brief["stocks_to_watch"]:
            for s in brief["stocks_to_watch"]:
                lines.append(
                    f"- **{s['symbol']}** — {s['note']}"
                )
            lines.append("")
        else:
            lines.append("*Belum ada watchlist khusus.*")
            lines.append("")

        # ─── Footer ────────────────────────────────────────────────
        lines.append("---")
        lines.append(f"*Generated by BandarScope at "
                     f"{brief['generated_at']}.* "
                     f"*Disclaimer: research only, not investment advice.*")

        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _market_summary(self, target_date: date) -> dict:
        prev_date = self.db.query(func.max(Candle.date))\
            .filter(Candle.date < target_date).scalar()

        latest = self.db.query(Candle).filter(Candle.date == target_date).all()
        prev = {c.symbol: c for c in self.db.query(Candle)
                .filter(Candle.date == prev_date).all()}

        advance = decline = unchanged = 0
        total_value = 0
        pct_changes = []
        for c in latest:
            p = prev.get(c.symbol)
            if not p or p.close == 0:
                continue
            pct = (c.close / p.close - 1) * 100
            pct_changes.append(pct)
            if pct > 0:
                advance += 1
            elif pct < 0:
                decline += 1
            else:
                unchanged += 1
            total_value += c.value or 0

        ff_today = (
            self.db.query(func.sum(ForeignFlow.foreign_net_value))
            .filter(ForeignFlow.date == target_date)
            .scalar()
        ) or 0

        ratio = advance / max(advance + decline, 1)
        return {
            "advance": advance,
            "decline": decline,
            "unchanged": unchanged,
            "advance_ratio": ratio,
            "total_value": int(total_value),
            "foreign_net": int(ff_today),
            "avg_change": float(pd.Series(pct_changes).mean()) if pct_changes else 0.0,
        }

    def _top_accumulation(self, target_date: date, limit: int = 10) -> list[dict]:
        return self._fetch_screener_rows(
            target_date, signal="accumulation",
            min_score=70, sort_desc=True, limit=limit,
        )

    def _distribution_warnings(self, target_date: date, limit: int = 5) -> list[dict]:
        return self._fetch_screener_rows(
            target_date, signal="distribution",
            max_score=35, sort_desc=False, limit=limit,
        )

    def _fetch_screener_rows(
        self,
        target_date: date,
        signal: str,
        min_score: float | None = None,
        max_score: float | None = None,
        sort_desc: bool = True,
        limit: int = 10,
    ) -> list[dict]:
        q = (
            self.db.query(AIScore, Symbol)
            .join(Symbol, Symbol.code == AIScore.symbol)
            .filter(AIScore.date == target_date)
            .filter(AIScore.smart_money_signal == signal)
        )
        if min_score is not None:
            q = q.filter(AIScore.bandar_score >= min_score)
        if max_score is not None:
            q = q.filter(AIScore.bandar_score <= max_score)

        rows = q.all()

        # Foreign net 20D
        symbols = [r.AIScore.symbol for r in rows]
        if not symbols:
            return []
        ff_start = target_date - timedelta(days=30)
        ff_q = (
            self.db.query(
                ForeignFlow.symbol,
                func.sum(ForeignFlow.foreign_net_value).label("foreign_net"),
            )
            .filter(
                ForeignFlow.symbol.in_(symbols),
                ForeignFlow.date > ff_start,
                ForeignFlow.date <= target_date,
            )
            .group_by(ForeignFlow.symbol)
            .all()
        )
        ff_map = {r.symbol: int(r.foreign_net or 0) for r in ff_q}

        # Latest close
        candles = (
            self.db.query(Candle)
            .filter(
                Candle.symbol.in_(symbols),
                Candle.date == target_date,
            )
            .all()
        )
        candle_map = {c.symbol: c for c in candles}

        result = []
        for r in rows:
            sym = r.AIScore.symbol
            cdl = candle_map.get(sym)
            result.append({
                "symbol": sym,
                "name": r.Symbol.name,
                "sector": r.Symbol.sector,
                "close": cdl.close if cdl else 0,
                "foreign_net": ff_map.get(sym, 0),
                "bandar_score": r.AIScore.bandar_score,
                "smart_money_signal": r.AIScore.smart_money_signal,
                "behavior_label": r.AIScore.behavior_label,
                "momentum_score": r.AIScore.momentum_score,
                "inventory_score": r.AIScore.inventory_score,
            })
        result.sort(key=lambda x: x["bandar_score"], reverse=sort_desc)
        return result[:limit]

    def _rotation_snapshot(self, period_days: int = 30) -> dict:
        rrg = self.sector_svc.rrg(period_days)
        out = {"leading": [], "improving": [], "weakening": [], "lagging": []}
        for d in rrg.get("data", []):
            q = d.get("quadrant")
            if q in out:
                out[q].append({
                    "code": d["code"],
                    "name": d["name"],
                    "rs_ratio": d["rs_ratio"],
                    "rs_momentum": d["rs_momentum"],
                })
        return out

    def _sector_summary(self) -> list[dict]:
        return self.sector_svc.sector_activity(days=5)

    def _pattern_alerts(
        self,
        top_accum: list[dict],
        distribution: list[dict],
        max_scans: int,
    ) -> list[dict]:
        """Run pattern detection on top symbols (limited for performance)."""
        # Combine top accum + distribution warnings; dedupe
        symbols_to_scan = []
        seen = set()
        for s in top_accum + distribution:
            if s["symbol"] not in seen:
                symbols_to_scan.append(s)
                seen.add(s["symbol"])
            if len(symbols_to_scan) >= max_scans:
                break

        alerts = []
        for s in symbols_to_scan:
            try:
                result = self.pattern_svc.detect_all(s["symbol"], lookback_days=60)
            except Exception:
                continue
            for p in result.get("patterns", []):
                if p["detected"] and p["confidence"] >= 65 \
                        and p["pattern"] in HIGHLIGHT_PATTERNS:
                    alerts.append({
                        "symbol": s["symbol"],
                        "sector": s["sector"],
                        "pattern": p["pattern"],
                        "name": p["name"],
                        "confidence": p["confidence"],
                        "interpretation": p["interpretation"],
                    })
        # Sort by confidence
        alerts.sort(key=lambda x: -x["confidence"])
        return alerts[:15]

    def _stocks_to_watch(
        self,
        target_date: date,
        top_accum: list[dict],
        distribution: list[dict],
    ) -> list[dict]:
        """
        Symbols deserving attention:
        - High BandarScore + breakout setup
        - Sustained accumulation (multi-day)
        - Pattern + score alignment
        """
        watch = []
        # Pick top 3 high-conviction longs
        for s in top_accum[:3]:
            note = (
                f"BandarScore {s['bandar_score']:.0f}, foreign 20D "
                f"{self._fmt_idr(s['foreign_net'])}. {s['behavior_label']}."
            )
            watch.append({
                "symbol": s["symbol"],
                "side": "LONG",
                "note": note,
            })
        # Pick top 2 high-conviction shorts (or exits)
        for s in distribution[:2]:
            note = (
                f"BandarScore drop ke {s['bandar_score']:.0f}. "
                f"Pertimbangkan exit / hindari entry."
            )
            watch.append({
                "symbol": s["symbol"],
                "side": "EXIT",
                "note": note,
            })
        return watch

    def _key_findings(self, brief: dict) -> list[str]:
        """Auto-generated narrative bullets summarizing the day."""
        findings = []
        m = brief["market_summary"]

        # 1. Market breadth narrative
        if m["advance_ratio"] >= 0.65:
            findings.append(
                f"Pasar **risk-on** dengan advance ratio {m['advance_ratio']:.0%}. "
                f"Mayoritas saham bullish."
            )
        elif m["advance_ratio"] <= 0.35:
            findings.append(
                f"Pasar **risk-off** dengan advance ratio hanya {m['advance_ratio']:.0%}. "
                f"Tekanan jual dominan."
            )
        else:
            findings.append(
                f"Pasar **mixed** ({m['advance_ratio']:.0%} advance) — selektif "
                f"per saham."
            )

        # 2. Foreign flow narrative
        if abs(m["foreign_net"]) > 100_000_000_000:
            direction = "inflow" if m["foreign_net"] > 0 else "outflow"
            findings.append(
                f"Foreign **{direction}** signifikan: "
                f"{self._fmt_idr(m['foreign_net'])} hari ini."
            )

        # 3. Top sector narrative
        sectors = brief["sector_capital_flow"]
        if sectors:
            top_sector = sectors[0]
            if top_sector["foreign_net_5d"] > 0:
                findings.append(
                    f"Sektor **{top_sector['name']}** memimpin inflow 5D "
                    f"({self._fmt_idr(top_sector['foreign_net_5d'])})."
                )

        # 4. Rotation narrative
        rotation = brief["sector_rotation"]
        leading = rotation.get("leading", [])
        improving = rotation.get("improving", [])
        if leading:
            findings.append(
                f"**Leading**: {len(leading)} sektor (kuat & akselerasi). "
                f"**Improving**: {len(improving)} sektor (early bird signal)."
            )

        # 5. Pattern alert narrative
        alerts = brief["pattern_alerts"]
        if alerts:
            stealth_count = sum(
                1 for a in alerts if a["pattern"] == "STEALTH_ACCUMULATION"
            )
            breakout_count = sum(
                1 for a in alerts if a["pattern"] == "BREAKOUT_SETUP"
            )
            if stealth_count > 0:
                findings.append(
                    f"**{stealth_count} stealth accumulation** terdeteksi — "
                    f"bandar bergerak diam-diam."
                )
            if breakout_count > 0:
                findings.append(
                    f"**{breakout_count} breakout setup** siap meledak — "
                    f"prioritas watchlist."
                )

        return findings

    @staticmethod
    def _fmt_idr(value: int | float) -> str:
        abs_v = abs(value)
        sign = "-" if value < 0 else ""
        if abs_v >= 1e12:
            return f"{sign}Rp {abs_v/1e12:.2f}T"
        if abs_v >= 1e9:
            return f"{sign}Rp {abs_v/1e9:.2f}M"
        if abs_v >= 1e6:
            return f"{sign}Rp {abs_v/1e6:.2f}Jt"
        if abs_v >= 1e3:
            return f"{sign}Rp {abs_v/1e3:.1f}rb"
        return f"{sign}Rp {abs_v:.0f}"
