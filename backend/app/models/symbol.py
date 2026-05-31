"""Symbol & Sector models."""
from sqlalchemy import Column, String, Integer, BigInteger, Float, Boolean, Date, JSON

from app.core.database import Base


class Sector(Base):
    __tablename__ = "sectors"

    code = Column(String, primary_key=True)        # e.g. 'BANK', 'ENERGY'
    name = Column(String, nullable=False)
    name_id = Column(String)                        # Bahasa Indonesia
    color = Column(String)                          # UI color hex


class Symbol(Base):
    __tablename__ = "symbols"

    code = Column(String, primary_key=True)         # e.g. 'BBCA'
    name = Column(String, nullable=False)
    sector = Column(String, index=True)
    sub_sector = Column(String)
    board = Column(String, default="main")          # main/development/accelerate
    listing_date = Column(Date)
    market_cap = Column(BigInteger)                 # IDR
    shares_listed = Column(BigInteger)
    free_float_pct = Column(Float)
    is_active = Column(Boolean, default=True)

    # Index membership flags
    is_lq45 = Column(Boolean, default=False, index=True)
    is_idx30 = Column(Boolean, default=False, index=True)
    is_kompas100 = Column(Boolean, default=False, index=True)
    is_issi = Column(Boolean, default=False, index=True)
    is_idx_growth = Column(Boolean, default=False)
    is_idx_value = Column(Boolean, default=False)
