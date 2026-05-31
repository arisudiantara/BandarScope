"""AI / Composite analytics scores."""
from sqlalchemy import Column, String, Date, Float, Integer, Index

from app.core.database import Base


class AIScore(Base):
    __tablename__ = "ai_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    bandar_score = Column(Float, default=0)            # 0-100 composite (legacy)
    foreign_score = Column(Float, default=0)
    inventory_score = Column(Float, default=0)
    volume_score = Column(Float, default=0)
    momentum_score = Column(Float, default=0)
    consistency_score = Column(Float, default=0)

    smart_money_signal = Column(String)                # 'accumulation','distribution','neutral'
    multi_tf_strength = Column(Float)                  # -100..+100
    behavior_label = Column(String)                    # human-readable

    # Verdict — visual conclusion icon
    verdict = Column(String)                           # 'GREEN_CHECK','ORANGE_X','RED_MINUS'
    verdict_explanation = Column(String)               # short Indonesian narrative
    slope_5d = Column(Float)                           # bandar inventory slope 5D
    slope_15d = Column(Float)                          # 15D
    slope_30d = Column(Float)                          # 30D
    r_squared_15d = Column(Float)                      # trend cleanliness
    consistency_pct = Column(Float)                    # % buy days in last 15

    # Retail Non-Flow — contrarian retail signal (0-100)
    retail_non_flow_score = Column(Float, default=50)  # 50=neutral, 70+=retail dumping (positive)
    retail_non_flow_label = Column(String)             # 'POSITIVE_NONFLOW' / 'NEUTRAL' / 'NEGATIVE_NONFLOW'

    # ===== NEXT-GEN SCREENER V2 SCORES =====

    # Multi-timeframe Foreign Strength (0-100)
    foreign_strength_score = Column(Float, default=50)
    foreign_net_5d = Column(Float, default=0)          # IDR
    foreign_net_10d = Column(Float, default=0)
    foreign_net_20d = Column(Float, default=0)
    foreign_net_60d = Column(Float, default=0)

    # Trend Score (MA-based, 0-100)
    trend_score = Column(Float, default=50)
    trend_label = Column(String)                       # STRONG_BULLISH/BULLISH/NEUTRAL/BEARISH/STRONG_BEARISH
    above_ma20 = Column(Float, default=0)              # pct above MA20
    above_ma50 = Column(Float, default=0)
    above_ma100 = Column(Float, default=0)
    above_ma200 = Column(Float, default=0)

    # Liquidity Quality Score (0-100)
    liquidity_score = Column(Float, default=50)
    liquidity_label = Column(String)                   # EXCELLENT/GOOD/MODERATE/POOR/ILLIQUID
    avg_value_20d = Column(Float, default=0)

    # Accumulation/Distribution Scores (0-100, separate)
    accumulation_score = Column(Float, default=50)
    distribution_score = Column(Float, default=50)

    # Wyckoff Stage Classification
    wyckoff_stage = Column(Integer)                    # 1-5
    wyckoff_stage_label = Column(String)               # ACCUMULATION/EARLY_BREAKOUT/TREND_EXPANSION/LATE_TREND/DISTRIBUTION

    # Breakout Quality Score (0-100)
    breakout_quality_score = Column(Float, default=0)

    # FINAL COMPOSITE — Opportunity Score
    opportunity_score = Column(Float, default=0)       # 0-100, the master ranking
    star_rating = Column(Integer, default=0)           # 1-5 stars
    setup_label = Column(String)                       # ELITE_SETUP/STRONG_SETUP/WATCHLIST/AVOID/IGNORE

    # Trade Readiness — "Buy Today?"
    trade_readiness_score = Column(Float, default=0)
    trade_readiness_signal = Column(String)            # READY_BUY/WATCH/WAIT/AVOID
    trade_readiness_reason = Column(String)            # human-readable why

    # FOMO Risk (0-100, higher = more risk)
    fomo_risk_score = Column(Float, default=0)
    fomo_warning = Column(String)                      # null or warning message

    __table_args__ = (
        Index("ix_score_sym_date", "symbol", "date", unique=True),
        Index("ix_score_opp", "date", "opportunity_score"),
    )
