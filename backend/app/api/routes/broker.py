"""Broker flow & inventory endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.broker_flow import BrokerFlowService

router = APIRouter(prefix="/broker", tags=["broker"])


@router.get("/inventory/{symbol}")
def inventory_lines(
    symbol: str,
    days: int = Query(60, ge=10, le=365),
    top_n: int = Query(5, ge=1, le=15),
    db: Session = Depends(get_db),
):
    return BrokerFlowService(db).inventory_lines(symbol, days, top_n)


@router.get("/top-accumulators/{symbol}")
def top_accumulators(
    symbol: str,
    days: int = Query(30, ge=5, le=180),
    limit: int = Query(20, ge=5, le=50),
    db: Session = Depends(get_db),
):
    return BrokerFlowService(db).top_accumulators(symbol, days, limit)


@router.get("/done-detail/{symbol}")
def done_detail(
    symbol: str,
    days: int = Query(5, ge=1, le=30),
    db: Session = Depends(get_db),
):
    return BrokerFlowService(db).done_detail_summary(symbol, days)
