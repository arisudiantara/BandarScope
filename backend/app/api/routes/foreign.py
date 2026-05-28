"""Foreign flow endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.foreign_flow import ForeignFlowService
from app.services.transaction import TransactionService
from app.services.balance_position import BalancePositionService

router = APIRouter(tags=["flow"])


@router.get("/foreign/{symbol}")
def foreign_flow(
    symbol: str,
    days: int = Query(90, ge=10, le=365),
    db: Session = Depends(get_db),
):
    return ForeignFlowService(db).get_flow(symbol, days)


@router.get("/transaction/{symbol}")
def transaction_chart(
    symbol: str,
    days: int = Query(120, ge=30, le=365),
    db: Session = Depends(get_db),
):
    return TransactionService(db).transaction_chart(symbol, days)


@router.get("/multi-entity/{symbol}")
def multi_entity_chart(
    symbol: str,
    days: int = Query(90, ge=20, le=365),
    db: Session = Depends(get_db),
):
    """Multi-entity flow: foreign / institutional / market_maker / retail / zombie."""
    return TransactionService(db).multi_entity_chart(symbol, days)


@router.get("/balance/{symbol}")
def balance_position(
    symbol: str,
    days: int = Query(90, ge=10, le=365),
    db: Session = Depends(get_db),
):
    return BalancePositionService(db).get_balance(symbol, days)
