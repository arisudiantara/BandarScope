"""Broker master."""
from sqlalchemy import Column, String, Integer, Boolean

from app.core.database import Base


class Broker(Base):
    __tablename__ = "brokers"

    code = Column(String(2), primary_key=True)      # e.g. 'RG', 'YP'
    name = Column(String, nullable=False)
    full_name = Column(String)
    type = Column(String)                            # foreign / domestic / retail / institutional
    is_foreign = Column(Boolean, default=False)
    cluster_label = Column(String)                   # 'market_maker','retail','institutional','corporate'
