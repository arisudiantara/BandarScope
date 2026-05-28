"""Daily OHLCV candles."""
from sqlalchemy import Column, String, Date, Float, BigInteger, Integer, Index

from app.core.database import Base


class Candle(Base):
    __tablename__ = "candles_1d"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(BigInteger)        # in shares
    value = Column(BigInteger)         # in IDR
    frequency = Column(Integer)        # number of trades

    __table_args__ = (
        Index("ix_candle_symbol_date", "symbol", "date", unique=True),
    )
