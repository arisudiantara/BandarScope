"""Verdict + Retail Non-Flow endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.verdict import VerdictService

router = APIRouter(prefix="/verdict", tags=["verdict"])


@router.get("/{symbol}")
def get_verdict(symbol: str, db: Session = Depends(get_db)):
    """Detailed verdict + retail non-flow analysis for a single symbol."""
    result = VerdictService(db).compute(symbol.upper())
    if result is None:
        raise HTTPException(404, f"Insufficient data for {symbol}")
    return result
