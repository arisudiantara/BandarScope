"""Broker Stalker endpoints — cross-symbol broker tracking."""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.broker_stalker import BrokerStalkerService

router = APIRouter(prefix="/broker-stalker", tags=["broker-stalker"])


class StalkMultiPayload(BaseModel):
    codes: list[str] = Field(..., min_length=1)
    days: int = Field(20, ge=1, le=365)
    limit: int = Field(50, ge=1, le=500)
    min_net_value: float = Field(100_000_000, ge=0)


@router.get("/brokers")
def list_brokers(db: Session = Depends(get_db)):
    """List all brokers (for the picker UI)."""
    return BrokerStalkerService(db).list_brokers()


@router.get("/stalk/{broker_code}")
def stalk_broker(
    broker_code: str,
    days: int = Query(20, ge=5, le=180),
    limit: int = Query(50, ge=10, le=200),
    min_net_value: float = Query(100_000_000, description="Min |net_value| to include"),
    db: Session = Depends(get_db),
):
    """Find what a broker is accumulating/distributing across all symbols."""
    result = BrokerStalkerService(db).stalk_broker(
        broker_code, days, limit, min_net_value
    )
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/stalk-multi")
def stalk_multi(
    payload: StalkMultiPayload,
    db: Session = Depends(get_db),
):
    """
    Aggregate stalking across MULTIPLE brokers.

    Example body:
    {
      "codes": ["XC", "XL", "YP"],
      "days": 20,
      "limit": 50,
      "min_net_value": 100000000
    }
    """
    result = BrokerStalkerService(db).stalk_brokers(
        payload.codes,
        payload.days,
        payload.limit,
        payload.min_net_value,
    )
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/inventory/{broker_code}/{symbol}")
def broker_inventory_for_symbol(
    broker_code: str,
    symbol: str,
    days: int = Query(90, ge=20, le=365),
    db: Session = Depends(get_db),
):
    """Cumulative inventory line for one (broker, symbol) pair."""
    return BrokerStalkerService(db).broker_inventory_for_symbol(
        broker_code, symbol, days
    )
