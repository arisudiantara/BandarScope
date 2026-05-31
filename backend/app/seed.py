"""
Seed mock data for BandarScope MVP.

Generates realistic IDX-style data:
- 50 symbols across 8 sectors
- 30 brokers (foreign, domestic, retail, institutional, corporate)
- 120 days of OHLCV
- Daily broker summary with realistic accumulation/distribution patterns
- Foreign flow with divergence scenarios
- Composite AI scores
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, Base, engine

# Path to the editable broker master CSV
BROKERS_CSV_PATH = Path(__file__).parent / "data" / "brokers.csv"


def load_brokers_from_csv() -> list[tuple]:
    """
    Read brokers from CSV file (data/brokers.csv).

    Returns list of tuples: (code, name, type, is_foreign, cluster_label).

    Edit data/brokers.csv to reclassify any broker without touching code.
    Cluster labels: market_maker, institutional, retail, corporate, zombie
    """
    if not BROKERS_CSV_PATH.exists():
        raise FileNotFoundError(
            f"Broker master not found: {BROKERS_CSV_PATH}\n"
            "Please ensure data/brokers.csv exists."
        )

    rows = []
    with BROKERS_CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            code = r["code"].strip().upper()
            if not code:
                continue
            is_foreign = r["is_foreign"].strip() in ("1", "true", "True", "TRUE")
            cluster = r["cluster_label"].strip().lower()
            type_ = "foreign" if is_foreign else "domestic"
            rows.append((code, r["name"].strip(), type_, is_foreign, cluster))

    # Validate uniqueness
    seen = set()
    for r in rows:
        if r[0] in seen:
            raise ValueError(f"Duplicate broker code in CSV: {r[0]}")
        seen.add(r[0])

    return rows
from app.models import (
    Symbol, Sector, Broker, Candle,
    BrokerDailySummary, ForeignFlow, AIScore, Watchlist,
)

# Set seed for reproducibility
random.seed(42)
np.random.seed(42)


# ---------------------------------------------------------------------------
# Master data
# ---------------------------------------------------------------------------

SECTORS = [
    ("BANK",     "Financials - Banking",   "Keuangan - Perbankan",  "#3b82f6"),
    ("ENERGY",   "Energy",                  "Energi",                "#f59e0b"),
    ("CONSUMER", "Consumer Goods",          "Barang Konsumen",       "#22c55e"),
    ("TELCO",    "Telecommunication",       "Telekomunikasi",        "#8b5cf6"),
    ("PROPERTY", "Property & Real Estate",  "Properti",              "#ec4899"),
    ("MINING",   "Mining & Metals",         "Pertambangan",          "#eab308"),
    ("INFRA",    "Infrastructure",          "Infrastruktur",         "#06b6d4"),
    ("TECH",     "Technology",              "Teknologi",             "#a855f7"),
]

# Realistic IDX-style symbol universe
SYMBOLS_BY_SECTOR = {
    "BANK":     ["BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BTPS", "ARTO", "BNGA"],
    "ENERGY":   ["MEDC", "PGAS", "ADRO", "ITMG", "PTBA", "INDY", "HRUM"],
    "CONSUMER": ["UNVR", "INDF", "ICBP", "MYOR", "GGRM", "HMSP", "KLBF", "SIDO"],
    "TELCO":    ["TLKM", "EXCL", "ISAT", "FREN"],
    "PROPERTY": ["BSDE", "PWON", "SMRA", "CTRA", "LPKR"],
    "MINING":   ["ANTM", "INCO", "TINS", "MDKA", "NICL"],
    "INFRA":    ["JSMR", "WIKA", "WSKT", "PTPP", "ADHI"],
    "TECH":     ["GOTO", "BUKA", "EMTK", "MTEL", "DCII"],
}

SYMBOL_NAMES = {
    "BBCA": "Bank Central Asia", "BBRI": "Bank Rakyat Indonesia",
    "BMRI": "Bank Mandiri", "BBNI": "Bank Negara Indonesia",
    "BRIS": "Bank Syariah Indonesia", "BTPS": "Bank BTPN Syariah",
    "ARTO": "Bank Jago", "BNGA": "Bank CIMB Niaga",
    "MEDC": "Medco Energi", "PGAS": "Perusahaan Gas Negara",
    "ADRO": "Adaro Energy", "ITMG": "Indo Tambangraya",
    "PTBA": "Bukit Asam", "INDY": "Indika Energy", "HRUM": "Harum Energy",
    "UNVR": "Unilever Indonesia", "INDF": "Indofood Sukses Makmur",
    "ICBP": "Indofood CBP", "MYOR": "Mayora Indah",
    "GGRM": "Gudang Garam", "HMSP": "HM Sampoerna",
    "KLBF": "Kalbe Farma", "SIDO": "Sido Muncul",
    "TLKM": "Telkom Indonesia", "EXCL": "XL Axiata",
    "ISAT": "Indosat", "FREN": "Smartfren Telecom",
    "BSDE": "Bumi Serpong Damai", "PWON": "Pakuwon Jati",
    "SMRA": "Summarecon Agung", "CTRA": "Ciputra Development",
    "LPKR": "Lippo Karawaci",
    "ANTM": "Aneka Tambang", "INCO": "Vale Indonesia",
    "TINS": "Timah", "MDKA": "Merdeka Copper Gold", "NICL": "Nickel Industries",
    "JSMR": "Jasa Marga", "WIKA": "Wijaya Karya",
    "WSKT": "Waskita Karya", "PTPP": "PP (Persero)", "ADHI": "Adhi Karya",
    "GOTO": "GoTo Gojek Tokopedia", "BUKA": "Bukalapak.com",
    "EMTK": "Elang Mahkota Teknologi", "MTEL": "Dayamitra Telekomunikasi",
    "DCII": "DCI Indonesia",
}

# IDX index memberships (representative subset; in production, pull from BEI weekly review)
IDX30_MEMBERS = {
    "BBCA", "BBRI", "BMRI", "BBNI", "TLKM", "ASII", "UNVR", "ICBP",
    "GOTO", "ADRO", "ANTM", "MDKA", "INCO", "ITMG", "PTBA", "PGAS",
    "JSMR", "BRIS", "ARTO", "MEDC", "INDF", "KLBF", "EMTK", "MYOR",
    "BSDE", "PWON", "TINS", "EXCL", "ISAT", "MTEL",
}

LQ45_MEMBERS = IDX30_MEMBERS | {
    "GGRM", "HMSP", "BNGA", "BTPS", "HRUM", "INDY", "SMRA", "CTRA",
    "WIKA", "PTPP", "DCII", "SIDO", "FREN", "ADHI", "WSKT",
}

KOMPAS100_MEMBERS = LQ45_MEMBERS | {
    "LPKR", "BUKA", "NICL",
}

# IDX-IC sector index code → our internal sector code mapping
SECTOR_TO_IDXIC = {
    "BANK":     "idxfinance",
    "ENERGY":   "idxenergy",
    "CONSUMER": "idxnoncyc",      # most consumer staples → non-cyclic
    "TELCO":    "idxinfra",
    "PROPERTY": "idxproperty",
    "MINING":   "idxbasic",       # mining/metals → basic materials
    "INFRA":    "idxinfra",
    "TECH":     "idxtechno",
}

# JII70 = Jakarta Islamic Index 70 (Sharia compliant subset)
# Approximation: ISSI minus banks (interest-based) and tobacco
JII70_NON_MEMBERS = {
    "BBCA", "BBRI", "BMRI", "BBNI", "BNGA", "GGRM", "HMSP",
    "BTPS", "ARTO", "BRIS",  # banks & sharia banks (the latter ARE compliant but JII70 has criteria)
}

# ISSI = Indeks Saham Syariah Indonesia (most non-bank, non-tobacco, etc.)
ISSI_NON_MEMBERS = {"BBCA", "BBRI", "BMRI", "BBNI", "BNGA", "GGRM", "HMSP"}

# Broker master is loaded from data/brokers.csv — edit that file to reclassify
BROKERS = load_brokers_from_csv()


# ---------------------------------------------------------------------------
# Mock generators
# ---------------------------------------------------------------------------

def _generate_price_path(
    days: int,
    start_price: float,
    pattern: str,
    volatility: float = 0.02,
) -> tuple[np.ndarray, list[str]]:
    """
    Generate realistic price path with multi-stage cycle.

    For long-term mock (730 days), we cycle through Wyckoff phases:
    Accumulation → Markup → Distribution → Markdown → Accumulation ...

    Returns: (prices_array, daily_phase_labels)
    """
    # Define stage segments (proportions of total days)
    if pattern == "cyclical":
        # Multi-cycle: 4 phases × ~180 days each
        cycle_len = days // 2  # one full cycle ~half period
        phase_lens = [
            int(cycle_len * 0.30),  # accumulation
            int(cycle_len * 0.25),  # markup
            int(cycle_len * 0.25),  # distribution
            int(cycle_len * 0.20),  # markdown
        ]
        # Repeat to fill days
        phases = []
        while len(phases) < days:
            for label, length in zip(
                ["accumulation", "markup", "distribution", "markdown"],
                phase_lens,
            ):
                phases.extend([label] * length)
                if len(phases) >= days:
                    break
        phases = phases[:days]
    elif pattern == "long_uptrend":
        # Mostly accumulation + markup, brief distribution
        phases = (
            ["accumulation"] * int(days * 0.35) +
            ["markup"] * int(days * 0.40) +
            ["distribution"] * int(days * 0.15) +
            ["markdown"] * int(days * 0.10)
        )
        phases = phases[:days] + ["markup"] * (days - len(phases[:days]))
    elif pattern == "long_downtrend":
        phases = (
            ["distribution"] * int(days * 0.30) +
            ["markdown"] * int(days * 0.50) +
            ["accumulation"] * int(days * 0.20)
        )
        phases = phases[:days] + ["markdown"] * (days - len(phases[:days]))
    elif pattern == "stealth_then_breakout":
        # Long stealth accumulation then sharp breakout
        phases = (
            ["accumulation"] * int(days * 0.55) +
            ["markup"] * int(days * 0.30) +
            ["distribution"] * int(days * 0.10) +
            ["markdown"] * int(days * 0.05)
        )
        phases = phases[:days] + ["accumulation"] * (days - len(phases[:days]))
    elif pattern == "ranging":
        # Sideways with mini cycles
        phases = []
        mini_cycle = 30
        while len(phases) < days:
            phases.extend(["accumulation"] * mini_cycle)
            phases.extend(["distribution"] * mini_cycle)
        phases = phases[:days]
    else:
        # Single phase (legacy support)
        phases = [pattern] * days

    # Phase-specific drift & volatility
    phase_drift = {
        "accumulation": -0.0006,   # gentle decline / sideways
        "markup":        0.0040,   # strong uptrend
        "distribution":  0.0008,   # minor rise (offering)
        "markdown":     -0.0035,   # downtrend
        "sideways":      0.0,
        # Legacy aliases
        "breakout":      0.0040,
        "fade":         -0.0030,
    }
    phase_vol = {
        "accumulation": volatility * 0.8,
        "markup":        volatility * 1.2,
        "distribution":  volatility * 0.9,
        "markdown":      volatility * 1.3,
        "sideways":      volatility * 0.7,
        "breakout":      volatility * 1.2,
        "fade":          volatility * 1.3,
    }

    returns = np.zeros(days)
    for i, ph in enumerate(phases):
        d = phase_drift.get(ph, 0)
        v = phase_vol.get(ph, volatility)
        returns[i] = np.random.normal(d, v)

    # Inject occasional spikes during markup phase
    for i, ph in enumerate(phases):
        if ph == "markup" and random.random() < 0.05:
            returns[i] += 0.025
        if ph == "markdown" and random.random() < 0.05:
            returns[i] -= 0.025

    log_returns = np.cumsum(returns)
    prices = start_price * np.exp(log_returns)
    return prices, phases


def _round_idx_price(price: float) -> int:
    """IDX tick size rules (simplified)."""
    if price < 200:    tick = 1
    elif price < 500:  tick = 2
    elif price < 2000: tick = 5
    elif price < 5000: tick = 10
    else:              tick = 25
    return int(round(price / tick) * tick)


def seed_master_data(db: Session) -> None:
    """Seed sectors, symbols, brokers."""
    print("Seeding sectors...")
    for code, name, name_id, color in SECTORS:
        db.merge(Sector(code=code, name=name, name_id=name_id, color=color))

    print("Seeding symbols...")
    today = date.today()
    for sector_code, symbols in SYMBOLS_BY_SECTOR.items():
        idxic_code = SECTOR_TO_IDXIC.get(sector_code, "")
        for sym in symbols:
            sector_flags = {
                "is_idxenergy":   idxic_code == "idxenergy",
                "is_idxbasic":    idxic_code == "idxbasic",
                "is_idxindust":   idxic_code == "idxindust",
                "is_idxcyclic":   idxic_code == "idxcyclic",
                "is_idxnoncyc":   idxic_code == "idxnoncyc",
                "is_idxhealth":   idxic_code == "idxhealth",
                "is_idxfinance":  idxic_code == "idxfinance",
                "is_idxproperty": idxic_code == "idxproperty",
                "is_idxtechno":   idxic_code == "idxtechno",
                "is_idxinfra":    idxic_code == "idxinfra",
                "is_idxtrans":    idxic_code == "idxtrans",
            }
            db.merge(Symbol(
                code=sym,
                name=SYMBOL_NAMES.get(sym, sym),
                sector=sector_code,
                board="main",
                listing_date=today - timedelta(days=random.randint(365, 365 * 20)),
                market_cap=random.randint(5_000_000_000_000, 800_000_000_000_000),
                shares_listed=random.randint(1_000_000_000, 50_000_000_000),
                free_float_pct=round(random.uniform(15, 60), 2),
                is_active=True,
                is_lq45=sym in LQ45_MEMBERS,
                is_idx30=sym in IDX30_MEMBERS,
                is_kompas100=sym in KOMPAS100_MEMBERS,
                is_issi=sym not in ISSI_NON_MEMBERS,
                is_jii70=sym not in JII70_NON_MEMBERS,
                is_composite=True,  # all our universe is in COMPOSITE
                **sector_flags,
            ))

    print("Seeding brokers...")
    for code, name, btype, is_foreign, cluster in BROKERS:
        db.merge(Broker(
            code=code,
            name=name,
            full_name=name,
            type=btype,
            is_foreign=is_foreign,
            cluster_label=cluster,
        ))

    db.commit()


def seed_market_data(db: Session, history_days: int = 120) -> None:
    """Generate candles, broker summaries, foreign flow."""
    today = date.today()
    start_date = today - timedelta(days=history_days)

    # Generate dates (skip weekends)
    all_dates = []
    d = start_date
    while d <= today:
        if d.weekday() < 5:  # Mon-Fri
            all_dates.append(d)
        d += timedelta(days=1)

    print(f"Generating {len(all_dates)} trading days of data...")

    symbols = db.query(Symbol).all()
    brokers = db.query(Broker).all()
    broker_codes = [b.code for b in brokers]

    candles_buffer = []
    broker_sum_buffer = []
    foreign_flow_buffer = []
    score_buffer = []

    for sym in symbols:
        # Pick a long-term cyclical/trending pattern per symbol
        pattern = random.choices(
            ["cyclical", "long_uptrend", "long_downtrend",
             "stealth_then_breakout", "ranging"],
            weights=[3, 2.5, 1.5, 1.5, 1.5],
        )[0]

        start_price = random.choice([300, 500, 850, 1200, 2500, 3800, 5500, 8200, 12000])
        prices, phases = _generate_price_path(len(all_dates), start_price, pattern)

        # Volume baseline
        base_volume = random.randint(5_000_000, 200_000_000)

        # Broker behavior plan: select a few "bandar" brokers per symbol
        bandar_brokers = random.sample(
            [b.code for b in brokers if b.cluster_label in ("market_maker", "institutional")],
            k=random.randint(2, 4),
        )
        retail_brokers = [b.code for b in brokers if b.cluster_label == "retail"]
        foreign_brokers = [b.code for b in brokers if b.is_foreign]
        zombie_brokers = [b.code for b in brokers if b.cluster_label == "zombie"]

        # Some symbols have a "waking zombie" — broker that suddenly becomes active
        # in a specific phase (insider sleeper signal)
        waking_zombie = random.choice(zombie_brokers) if zombie_brokers and random.random() < 0.4 else None
        zombie_wake_phase = random.choice(["accumulation", "markup"]) if waking_zombie else None

        cumulative_foreign = 0

        for i, d in enumerate(all_dates):
            close = float(_round_idx_price(prices[i]))
            open_p = float(_round_idx_price(prices[i] * (1 + np.random.normal(0, 0.005))))
            high_p = float(_round_idx_price(max(close, open_p) * (1 + abs(np.random.normal(0, 0.008)))))
            low_p = float(_round_idx_price(min(close, open_p) * (1 - abs(np.random.normal(0, 0.008)))))

            volume = int(base_volume * np.random.uniform(0.5, 2.0))
            value = int(volume * close)
            frequency = int(volume / random.randint(1000, 5000))

            candles_buffer.append({
                "symbol": sym.code, "date": d,
                "open": open_p, "high": high_p, "low": low_p, "close": close,
                "volume": volume, "value": value, "frequency": frequency,
            })

            # Generate broker activity for this day
            day_foreign_buy = 0
            day_foreign_sell = 0

            # Total day's value distributed among brokers
            remaining_value = value
            broker_activities = {}

            # Current phase for this specific day
            current_phase = phases[i]

            # Bandar brokers: behavior driven by current phase
            for bcode in bandar_brokers:
                if current_phase == "accumulation":
                    bias = np.random.uniform(0.58, 0.78)  # mostly buying
                elif current_phase == "markup":
                    bias = np.random.uniform(0.50, 0.72)  # still buying, riding
                elif current_phase == "distribution":
                    bias = np.random.uniform(0.20, 0.42)  # mostly selling
                elif current_phase == "markdown":
                    bias = np.random.uniform(0.35, 0.55)  # mostly out
                else:
                    bias = np.random.uniform(0.40, 0.60)

                share = np.random.uniform(0.05, 0.18)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)

            # Foreign brokers — tend to lag behind bandar
            for bcode in foreign_brokers:
                if random.random() > 0.6:  # not all foreign brokers active daily
                    continue
                if current_phase == "accumulation":
                    bias = np.random.uniform(0.45, 0.62)
                elif current_phase == "markup":
                    bias = np.random.uniform(0.58, 0.80)  # foreign chases markup
                elif current_phase == "distribution":
                    bias = np.random.uniform(0.42, 0.62)  # still buying late
                elif current_phase == "markdown":
                    bias = np.random.uniform(0.20, 0.42)  # finally exiting
                else:
                    bias = np.random.uniform(0.45, 0.55)

                share = np.random.uniform(0.02, 0.10)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)
                day_foreign_buy += buy_value
                day_foreign_sell += sell_value

            # Retail brokers — counter-trend (provide liquidity to bandar)
            for bcode in retail_brokers:
                if random.random() > 0.5:
                    continue
                if current_phase == "accumulation":
                    bias = np.random.uniform(0.30, 0.50)  # selling to bandar
                elif current_phase == "markup":
                    bias = np.random.uniform(0.55, 0.75)  # FOMO buying
                elif current_phase == "distribution":
                    bias = np.random.uniform(0.55, 0.78)  # buying tops
                elif current_phase == "markdown":
                    bias = np.random.uniform(0.40, 0.62)  # confused
                else:
                    bias = np.random.uniform(0.40, 0.60)

                share = np.random.uniform(0.02, 0.08)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)

            # Zombie brokers — mostly inactive, but waking_zombie spikes during
            # specific phase (classic "insider sleeper" signal)
            for bcode in zombie_brokers:
                # Default: very rarely active
                base_activity_chance = 0.1
                share_range = (0.001, 0.005)
                bias = np.random.uniform(0.45, 0.55)

                # If this is the waking zombie and current phase matches,
                # become VERY active (large net buy)
                if bcode == waking_zombie and current_phase == zombie_wake_phase:
                    base_activity_chance = 0.7
                    share_range = (0.04, 0.12)
                    bias = np.random.uniform(0.65, 0.85)  # strong net buy

                if random.random() > base_activity_chance:
                    continue

                share = np.random.uniform(*share_range)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)

            # Other brokers (corporate, etc) — small random
            other_brokers = [
                b.code for b in brokers
                if b.code not in broker_activities
            ]
            for bcode in random.sample(other_brokers, k=min(len(other_brokers), random.randint(3, 8))):
                share = np.random.uniform(0.005, 0.03)
                broker_value = int(remaining_value * share)
                bias = np.random.uniform(0.4, 0.6)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)

            # Insert broker summaries
            broker_map = {b.code: b for b in brokers}
            for bcode, (bval, sval) in broker_activities.items():
                if bval == 0 and sval == 0:
                    continue
                buy_lot = int(bval / close / 100) if close > 0 else 0
                sell_lot = int(sval / close / 100) if close > 0 else 0
                broker_sum_buffer.append({
                    "date": d, "symbol": sym.code, "broker_code": bcode,
                    "broker_type": broker_map[bcode].type,
                    "buy_lot": buy_lot, "sell_lot": sell_lot,
                    "net_lot": buy_lot - sell_lot,
                    "buy_value": bval, "sell_value": sval,
                    "net_value": bval - sval,
                    "avg_buy_price": close * np.random.uniform(0.995, 1.005),
                    "avg_sell_price": close * np.random.uniform(0.995, 1.005),
                })

            # Foreign flow aggregate
            foreign_net = day_foreign_buy - day_foreign_sell
            cumulative_foreign += foreign_net
            foreign_flow_buffer.append({
                "date": d, "symbol": sym.code,
                "foreign_buy_value": day_foreign_buy,
                "foreign_sell_value": day_foreign_sell,
                "foreign_net_value": foreign_net,
                "cumulative_net": cumulative_foreign,
                "close_price": close,
            })

        # Generate AI score for the latest day per symbol
        latest_close = float(prices[-1])
        prev_close_20 = float(prices[max(0, len(prices) - 21)])
        momentum_pct = (latest_close / prev_close_20 - 1) * 100

        # Score driven by current (latest) phase
        latest_phase = phases[-1]
        phase_score_bias = {
            "accumulation": 78,
            "markup":       82,
            "distribution": 28,
            "markdown":     20,
        }
        base_score = phase_score_bias.get(latest_phase, 50) + np.random.uniform(-8, 8)

        bandar_score = float(np.clip(base_score, 0, 100))
        foreign_score = float(np.clip(base_score + np.random.uniform(-15, 15), 0, 100))
        inventory_score = float(np.clip(base_score + np.random.uniform(-10, 10), 0, 100))
        volume_score = float(np.clip(60 + np.random.uniform(-30, 30), 0, 100))
        momentum_score = float(np.clip(50 + momentum_pct * 3, 0, 100))
        consistency_score = float(np.clip(base_score + np.random.uniform(-15, 15), 0, 100))

        if latest_phase in ("accumulation", "markup"):
            signal = "accumulation"
            label = "Strong Accumulation" if bandar_score > 75 else "Moderate Accumulation"
        elif latest_phase in ("distribution", "markdown"):
            signal = "distribution"
            label = "Active Distribution" if bandar_score < 30 else "Mild Distribution"
        else:
            signal = "neutral"
            label = "Neutral / Range-bound"

        score_buffer.append({
            "date": all_dates[-1], "symbol": sym.code,
            "bandar_score": round(bandar_score, 1),
            "foreign_score": round(foreign_score, 1),
            "inventory_score": round(inventory_score, 1),
            "volume_score": round(volume_score, 1),
            "momentum_score": round(momentum_score, 1),
            "consistency_score": round(consistency_score, 1),
            "smart_money_signal": signal,
            "multi_tf_strength": round(momentum_pct * 2, 1),
            "behavior_label": label,
        })

    # Bulk insert
    print(f"Inserting {len(candles_buffer)} candles...")
    db.bulk_insert_mappings(Candle, candles_buffer)

    print(f"Inserting {len(broker_sum_buffer)} broker summary rows...")
    # Insert in chunks to avoid memory issues
    chunk_size = 5000
    for i in range(0, len(broker_sum_buffer), chunk_size):
        db.bulk_insert_mappings(BrokerDailySummary, broker_sum_buffer[i:i+chunk_size])

    print(f"Inserting {len(foreign_flow_buffer)} foreign flow rows...")
    db.bulk_insert_mappings(ForeignFlow, foreign_flow_buffer)

    print(f"Inserting {len(score_buffer)} AI scores...")
    db.bulk_insert_mappings(AIScore, score_buffer)

    db.commit()

    # ─── Step: Compute verdict + retail non-flow per symbol ─────────
    print("\nComputing verdict + retail non-flow for all symbols...")
    from app.services.verdict import VerdictService
    verdict_svc = VerdictService(db)
    verdict_map = verdict_svc.compute_universe(target_date=all_dates[-1])
    updated = 0
    for sym, v in verdict_map.items():
        score_row = (
            db.query(AIScore)
            .filter(AIScore.symbol == sym, AIScore.date == all_dates[-1])
            .first()
        )
        if not score_row:
            continue
        score_row.verdict = v["verdict"]
        score_row.verdict_explanation = v["explanation"]
        score_row.slope_5d = v["slope_5d"]
        score_row.slope_15d = v["slope_15d"]
        score_row.slope_30d = v["slope_30d"]
        score_row.r_squared_15d = v["r_squared_15d"]
        score_row.consistency_pct = v["consistency_pct"]
        score_row.retail_non_flow_score = v["retail_non_flow_score"]
        score_row.retail_non_flow_label = v["retail_non_flow_label"]
        updated += 1
    db.commit()
    print(f"  Verdict updated: {updated} symbols")

    # ─── Step: Compute V2 composite scores ──────────────────────────
    print("\nComputing V2 scores (Foreign / Trend / Liquidity / Wyckoff / Opportunity)...")
    from app.services.composite_score import CompositeScoreService
    composite_svc = CompositeScoreService(db)
    composite_map = composite_svc.compute_universe(target_date=all_dates[-1])
    updated_v2 = 0
    for sym, c in composite_map.items():
        score_row = (
            db.query(AIScore)
            .filter(AIScore.symbol == sym, AIScore.date == all_dates[-1])
            .first()
        )
        if not score_row:
            continue
        # Foreign multi-tf
        score_row.foreign_strength_score = c["foreign_strength_score"]
        score_row.foreign_net_5d = c["foreign_net_5d"]
        score_row.foreign_net_10d = c["foreign_net_10d"]
        score_row.foreign_net_20d = c["foreign_net_20d"]
        score_row.foreign_net_60d = c["foreign_net_60d"]
        # Trend
        score_row.trend_score = c["trend_score"]
        score_row.trend_label = c["trend_label"]
        score_row.above_ma20 = c["above_ma20"]
        score_row.above_ma50 = c["above_ma50"]
        score_row.above_ma100 = c["above_ma100"]
        score_row.above_ma200 = c["above_ma200"]
        # Liquidity
        score_row.liquidity_score = c["liquidity_score"]
        score_row.liquidity_label = c["liquidity_label"]
        score_row.avg_value_20d = c["avg_value_20d"]
        # Accum/Distrib
        score_row.accumulation_score = c["accumulation_score"]
        score_row.distribution_score = c["distribution_score"]
        # Wyckoff
        score_row.wyckoff_stage = c["wyckoff_stage"]
        score_row.wyckoff_stage_label = c["wyckoff_stage_label"]
        score_row.breakout_quality_score = c["breakout_quality_score"]
        # Opportunity
        score_row.opportunity_score = c["opportunity_score"]
        score_row.star_rating = c["star_rating"]
        score_row.setup_label = c["setup_label"]
        # Trade readiness
        score_row.trade_readiness_score = c["trade_readiness_score"]
        score_row.trade_readiness_signal = c["trade_readiness_signal"]
        score_row.trade_readiness_reason = c["trade_readiness_reason"]
        # FOMO
        score_row.fomo_risk_score = c["fomo_risk_score"]
        score_row.fomo_warning = c["fomo_warning"]
        updated_v2 += 1
    db.commit()
    print(f"  V2 scores updated: {updated_v2} symbols")

    # ─── Step: Compute sector RRG quadrant per symbol ───────────────
    print("\nComputing sector RRG quadrant per symbol...")
    from app.services.sector import SectorService
    sector_svc = SectorService(db)
    rrg = sector_svc.rrg(period_days=30)
    sector_quadrant_map = {
        d["code"]: (d["quadrant"], d["rs_ratio"], d["rs_momentum"])
        for d in rrg.get("data", [])
    }
    rrg_updated = 0
    for sym in db.query(Symbol).all():
        info = sector_quadrant_map.get(sym.sector)
        if not info:
            continue
        score_row = (
            db.query(AIScore)
            .filter(AIScore.symbol == sym.code, AIScore.date == all_dates[-1])
            .first()
        )
        if not score_row:
            continue
        score_row.sector_rrg_quadrant = info[0]
        score_row.sector_rs_ratio = info[1]
        score_row.sector_rs_momentum = info[2]
        rrg_updated += 1
    db.commit()
    print(f"  Sector RRG updated: {rrg_updated} symbols")


def seed_watchlists(db: Session) -> None:
    """Create demo watchlists."""
    db.merge(Watchlist(
        id="default-bluechip",
        name="Blue Chip",
        description="Saham blue chip Indonesia",
        symbols=["BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "ICBP"],
        color="#3b82f6",
    ))
    db.merge(Watchlist(
        id="default-bandar",
        name="Bandar Watch",
        description="Saham dengan akumulasi tinggi",
        symbols=["BBRI", "MEDC", "ANTM", "ADRO", "MDKA"],
        color="#22c55e",
    ))
    db.commit()


def main():
    print("Creating tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        seed_master_data(db)
        seed_market_data(db, history_days=730)   # 2 years for backtesting
        seed_watchlists(db)
        print("\nSeed complete.")
        print(f"  Symbols:   {db.query(Symbol).count()}")
        print(f"  Brokers:   {db.query(Broker).count()}")
        print(f"  Candles:   {db.query(Candle).count()}")
        print(f"  Broker Sum:{db.query(BrokerDailySummary).count()}")
        print(f"  Foreign:   {db.query(ForeignFlow).count()}")
        print(f"  AI Scores: {db.query(AIScore).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
