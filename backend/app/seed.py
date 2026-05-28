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

import random
from datetime import date, timedelta
from typing import List

import numpy as np
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, Base, engine
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

# Broker codes mimicking real IDX brokers (anonymized)
BROKERS = [
    # Foreign institutional
    ("CC", "CLSA Sekuritas",         "foreign",       True,  "institutional"),
    ("CS", "Credit Suisse",          "foreign",       True,  "institutional"),
    ("DB", "Deutsche Securities",    "foreign",       True,  "institutional"),
    ("KZ", "CLSA",                   "foreign",       True,  "institutional"),
    ("ML", "Merrill Lynch",          "foreign",       True,  "institutional"),
    ("MS", "Morgan Stanley",         "foreign",       True,  "institutional"),
    ("RX", "Macquarie",              "foreign",       True,  "institutional"),
    ("ZP", "Maybank Kim Eng",        "foreign",       True,  "institutional"),
    ("AK", "UBS Securities",         "foreign",       True,  "institutional"),
    ("KI", "Ciptadana Sekuritas",    "foreign",       True,  "institutional"),
    # Domestic institutional / market makers
    ("RG", "Mandiri Sekuritas",      "domestic",      False, "market_maker"),
    ("AG", "Bahana Sekuritas",       "domestic",      False, "market_maker"),
    ("MG", "Semesta Indovest",       "domestic",      False, "market_maker"),
    ("LG", "Trimegah Sekuritas",     "domestic",      False, "market_maker"),
    ("NI", "BNI Sekuritas",          "domestic",      False, "institutional"),
    ("BR", "Sinarmas Sekuritas",     "domestic",      False, "institutional"),
    ("PD", "Indo Premier",           "domestic",      False, "institutional"),
    ("SQ", "BCA Sekuritas",          "domestic",      False, "institutional"),
    # Retail-heavy online brokers
    ("YP", "Mirae Asset Sekuritas",  "domestic",      False, "retail"),
    ("YJ", "Lotus Andalan",          "domestic",      False, "retail"),
    ("YU", "CGS-CIMB Sekuritas",     "domestic",      False, "retail"),
    ("XL", "Mahanusa Sekuritas",     "domestic",      False, "retail"),
    ("XC", "Phintraco Sekuritas",    "domestic",      False, "retail"),
    ("DR", "OCBC Sekuritas",         "domestic",      False, "retail"),
    ("FZ", "Waterfront Sekuritas",   "domestic",      False, "retail"),
    # Corporate
    ("EP", "MNC Sekuritas",          "domestic",      False, "corporate"),
    ("HG", "Henan Putihrai",         "domestic",      False, "corporate"),
    ("OD", "Danareksa Sekuritas",    "domestic",      False, "corporate"),
    # Proprietary
    ("PP", "Panin Sekuritas",        "domestic",      False, "institutional"),
    ("TF", "Universal Broker",       "domestic",      False, "institutional"),
]


# ---------------------------------------------------------------------------
# Mock generators
# ---------------------------------------------------------------------------

def _generate_price_path(
    days: int,
    start_price: float,
    pattern: str,
    volatility: float = 0.02,
) -> np.ndarray:
    """
    Generate realistic price path.
    Patterns: 'accumulation', 'distribution', 'sideways', 'breakout', 'fade'
    """
    drift_map = {
        "accumulation": -0.0008,   # gentle decline (stealth)
        "distribution": 0.0006,    # slight rise (offering)
        "sideways":     0.0,
        "breakout":     0.004,     # strong uptrend
        "fade":         -0.003,    # downtrend
    }
    drift = drift_map.get(pattern, 0.0)

    returns = np.random.normal(drift, volatility, days)

    # Add a few momentum days
    if pattern == "breakout":
        spike_days = np.random.choice(days, size=max(1, days // 20), replace=False)
        returns[spike_days] += 0.025
    elif pattern == "accumulation":
        # late-stage spike (bandar finally pushing up)
        if days > 60:
            returns[-15:] += 0.005

    log_returns = np.cumsum(returns)
    prices = start_price * np.exp(log_returns)
    return prices


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
        for sym in symbols:
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
        # Pick a behavioral pattern per symbol
        pattern = random.choices(
            ["accumulation", "distribution", "sideways", "breakout", "fade"],
            weights=[3, 2, 3, 1.5, 1.5],
        )[0]

        start_price = random.choice([300, 500, 850, 1200, 2500, 3800, 5500, 8200, 12000])
        prices = _generate_price_path(len(all_dates), start_price, pattern)

        # Volume baseline
        base_volume = random.randint(5_000_000, 200_000_000)

        # Broker behavior plan: select a few "bandar" brokers per symbol
        bandar_brokers = random.sample(
            [b.code for b in brokers if b.cluster_label in ("market_maker", "institutional")],
            k=random.randint(2, 4),
        )
        retail_brokers = [b.code for b in brokers if b.cluster_label == "retail"]
        foreign_brokers = [b.code for b in brokers if b.is_foreign]

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

            # Bandar brokers: weighted toward buying in accumulation pattern
            for bcode in bandar_brokers:
                if pattern == "accumulation":
                    bias = np.random.uniform(0.55, 0.78)  # mostly buying
                elif pattern == "distribution":
                    bias = np.random.uniform(0.22, 0.45)  # mostly selling
                elif pattern == "breakout":
                    bias = np.random.uniform(0.50, 0.85)
                else:
                    bias = np.random.uniform(0.40, 0.60)

                share = np.random.uniform(0.05, 0.18)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)

            # Foreign brokers
            for bcode in foreign_brokers:
                if random.random() > 0.6:  # not all foreign brokers active daily
                    continue
                # Foreign tend to follow trend with lag
                if pattern == "accumulation":
                    bias = np.random.uniform(0.50, 0.72)
                elif pattern == "distribution":
                    bias = np.random.uniform(0.30, 0.50)
                elif pattern == "breakout":
                    bias = np.random.uniform(0.55, 0.80)
                elif pattern == "fade":
                    bias = np.random.uniform(0.20, 0.45)
                else:
                    bias = np.random.uniform(0.45, 0.55)

                share = np.random.uniform(0.02, 0.10)
                broker_value = int(remaining_value * share)
                buy_value = int(broker_value * bias)
                sell_value = broker_value - buy_value
                broker_activities[bcode] = (buy_value, sell_value)
                day_foreign_buy += buy_value
                day_foreign_sell += sell_value

            # Retail brokers — provide liquidity (opposite of bandar usually)
            for bcode in retail_brokers:
                if random.random() > 0.5:
                    continue
                if pattern == "accumulation":
                    bias = np.random.uniform(0.30, 0.55)  # selling to bandar
                elif pattern == "distribution":
                    bias = np.random.uniform(0.50, 0.75)  # buying from bandar
                else:
                    bias = np.random.uniform(0.40, 0.60)

                share = np.random.uniform(0.02, 0.08)
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

        # Compute scores based on pattern
        pattern_score_bias = {
            "accumulation": 78, "breakout": 85, "sideways": 50,
            "distribution": 25, "fade": 18,
        }
        base_score = pattern_score_bias[pattern] + np.random.uniform(-10, 10)

        bandar_score = float(np.clip(base_score, 0, 100))
        foreign_score = float(np.clip(base_score + np.random.uniform(-15, 15), 0, 100))
        inventory_score = float(np.clip(base_score + np.random.uniform(-10, 10), 0, 100))
        volume_score = float(np.clip(60 + np.random.uniform(-30, 30), 0, 100))
        momentum_score = float(np.clip(50 + momentum_pct * 3, 0, 100))
        consistency_score = float(np.clip(base_score + np.random.uniform(-15, 15), 0, 100))

        if pattern in ("accumulation", "breakout"):
            signal = "accumulation"
            label = "Strong Accumulation" if bandar_score > 75 else "Moderate Accumulation"
        elif pattern in ("distribution", "fade"):
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
        seed_market_data(db, history_days=120)
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
