"""Symbol & sector master endpoints."""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Symbol, Sector, Candle, AIScore

router = APIRouter(prefix="/symbols", tags=["symbols"])


@router.get("")
def list_symbols(
    sector: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Symbol)
    if sector:
        q = q.filter(Symbol.sector == sector)
    if search:
        like = f"%{search.upper()}%"
        q = q.filter((Symbol.code.ilike(like)) | (Symbol.name.ilike(like)))
    rows = q.order_by(Symbol.code).all()
    return [{
        "code": r.code, "name": r.name, "sector": r.sector,
        "board": r.board, "market_cap": r.market_cap,
        "free_float_pct": r.free_float_pct,
    } for r in rows]


@router.get("/{symbol}")
def get_symbol(symbol: str, db: Session = Depends(get_db)):
    s = db.query(Symbol).filter(Symbol.code == symbol).first()
    if not s:
        raise HTTPException(404, "Symbol not found")

    # Latest candle + score
    latest_candle = (
        db.query(Candle)
        .filter(Candle.symbol == symbol)
        .order_by(Candle.date.desc())
        .first()
    )
    latest_score = (
        db.query(AIScore)
        .filter(AIScore.symbol == symbol)
        .order_by(AIScore.date.desc())
        .first()
    )

    prev_candle = None
    if latest_candle:
        prev_candle = (
            db.query(Candle)
            .filter(Candle.symbol == symbol, Candle.date < latest_candle.date)
            .order_by(Candle.date.desc())
            .first()
        )

    pct_change = 0.0
    if latest_candle and prev_candle and prev_candle.close > 0:
        pct_change = (latest_candle.close / prev_candle.close - 1) * 100

    return {
        "code": s.code,
        "name": s.name,
        "sector": s.sector,
        "board": s.board,
        "market_cap": s.market_cap,
        "shares_listed": s.shares_listed,
        "free_float_pct": s.free_float_pct,
        "listing_date": s.listing_date.isoformat() if s.listing_date else None,
        "latest": {
            "date": latest_candle.date.isoformat() if latest_candle else None,
            "open": latest_candle.open if latest_candle else None,
            "high": latest_candle.high if latest_candle else None,
            "low": latest_candle.low if latest_candle else None,
            "close": latest_candle.close if latest_candle else None,
            "volume": latest_candle.volume if latest_candle else None,
            "value": latest_candle.value if latest_candle else None,
            "pct_change": round(pct_change, 2),
        },
        "score": {
            "bandar_score": latest_score.bandar_score if latest_score else None,
            "foreign_score": latest_score.foreign_score if latest_score else None,
            "inventory_score": latest_score.inventory_score if latest_score else None,
            "volume_score": latest_score.volume_score if latest_score else None,
            "momentum_score": latest_score.momentum_score if latest_score else None,
            "consistency_score": latest_score.consistency_score if latest_score else None,
            "smart_money_signal": latest_score.smart_money_signal if latest_score else None,
            "behavior_label": latest_score.behavior_label if latest_score else None,
            "multi_tf_strength": latest_score.multi_tf_strength if latest_score else None,
        } if latest_score else None,
    }


@router.get("/{symbol}/candles")
def get_candles(
    symbol: str,
    days: int = Query(120, ge=1, le=365),
    db: Session = Depends(get_db),
):
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    rows = (
        db.query(Candle)
        .filter(Candle.symbol == symbol, Candle.date >= start_date)
        .order_by(Candle.date)
        .all()
    )
    return [{
        "date": r.date.isoformat(),
        "open": r.open, "high": r.high, "low": r.low, "close": r.close,
        "volume": r.volume, "value": r.value, "frequency": r.frequency,
    } for r in rows]


@router.get("/sectors/list")
def list_sectors(db: Session = Depends(get_db)):
    rows = db.query(Sector).all()
    return [{
        "code": r.code, "name": r.name, "name_id": r.name_id, "color": r.color
    } for r in rows]
