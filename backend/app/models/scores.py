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

    __table_args__ = (
        Index("ix_score_sym_date", "symbol", "date", unique=True),
    )
