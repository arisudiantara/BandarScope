"""Watchlist CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Watchlist
from app.schemas.common import WatchlistCreate, WatchlistUpdate

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("")
def list_watchlists(db: Session = Depends(get_db)):
    rows = db.query(Watchlist).order_by(Watchlist.name).all()
    return [{
        "id": r.id, "name": r.name, "description": r.description,
        "symbols": r.symbols or [], "color": r.color,
    } for r in rows]


@router.post("", status_code=201)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db)):
    w = Watchlist(
        name=payload.name,
        description=payload.description,
        symbols=payload.symbols,
        color=payload.color,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"id": w.id, "name": w.name, "symbols": w.symbols, "color": w.color}


@router.patch("/{wid}")
def update_watchlist(wid: str, payload: WatchlistUpdate, db: Session = Depends(get_db)):
    w = db.query(Watchlist).filter(Watchlist.id == wid).first()
    if not w:
        raise HTTPException(404, "Watchlist not found")
    if payload.name is not None: w.name = payload.name
    if payload.description is not None: w.description = payload.description
    if payload.symbols is not None: w.symbols = payload.symbols
    if payload.color is not None: w.color = payload.color
    db.commit()
    return {"id": w.id, "name": w.name, "symbols": w.symbols, "color": w.color}


@router.delete("/{wid}", status_code=204)
def delete_watchlist(wid: str, db: Session = Depends(get_db)):
    w = db.query(Watchlist).filter(Watchlist.id == wid).first()
    if not w:
        raise HTTPException(404, "Watchlist not found")
    db.delete(w)
    db.commit()
