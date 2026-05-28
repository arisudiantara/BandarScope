"""Daily foreign flow per symbol (denormalized for fast querying)."""
from sqlalchemy import Column, String, Date, BigInteger, Float, Integer, Index

from app.core.database import Base


class ForeignFlow(Base):
    __tablename__ = "foreign_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String, nullable=False, index=True)

    foreign_buy_value = Column(BigInteger, default=0)
    foreign_sell_value = Column(BigInteger, default=0)
    foreign_net_value = Column(BigInteger, default=0)
    cumulative_net = Column(BigInteger, default=0)     # rolling cumulative

    close_price = Column(Float)

    __table_args__ = (
        Index("ix_foreign_sym_date", "symbol", "date", unique=True),
    )
