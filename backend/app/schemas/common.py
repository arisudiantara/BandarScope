"""Common Pydantic schemas."""
from typing import Any, Optional
from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool = True
    data: Any = None
    message: Optional[str] = None


class WatchlistCreate(BaseModel):
    name: str
    description: Optional[str] = None
    symbols: list[str] = []
    color: Optional[str] = "#3b82f6"


class WatchlistUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbols: Optional[list[str]] = None
    color: Optional[str] = None
