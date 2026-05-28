"""AI / Composite analytics scores."""
from sqlalchemy import Column, String, Date, Float, Integer, Index

from app.core.database import Base


class AIScore(Base):
    __tablename__ = "ai_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    bandar_score = Column(Float, default=0)            # 0-100 composite
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

    __table_args__ = (
        Index("ix_score_sym_date", "symbol", "date", unique=True),
    )
