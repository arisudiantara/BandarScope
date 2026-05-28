"""Daily broker summary per symbol."""
from sqlalchemy import Column, String, Date, Integer, BigInteger, Float, Index

from app.core.database import Base


class BrokerDailySummary(Base):
    __tablename__ = "broker_daily_summary"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)
    broker_code = Column(String(2), nullable=False, index=True)
    broker_type = Column(String)                       # foreign/domestic/retail/etc

    buy_lot = Column(Integer, default=0)               # lots bought (1 lot = 100 shares)
    sell_lot = Column(Integer, default=0)
    net_lot = Column(Integer, default=0)               # buy - sell

    buy_value = Column(BigInteger, default=0)          # IDR
    sell_value = Column(BigInteger, default=0)
    net_value = Column(BigInteger, default=0)

    avg_buy_price = Column(Float)
    avg_sell_price = Column(Float)

    __table_args__ = (
        Index("ix_brokersum_sym_date_broker", "symbol", "date", "broker_code", unique=True),
    )
