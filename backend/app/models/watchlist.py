"""User watchlist."""
import uuid
from sqlalchemy import Column, String, JSON, DateTime, func

from app.core.database import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    description = Column(String)
    symbols = Column(JSON, default=list)               # list of symbol codes
    color = Column(String, default="#3b82f6")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
