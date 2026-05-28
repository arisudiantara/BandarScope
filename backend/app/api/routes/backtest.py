"""Backtesting endpoints."""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.backtest import BacktestEngine, StrategySpec, PRESET_STRATEGIES

router = APIRouter(prefix="/backtest", tags=["backtest"])


class StrategyPayload(BaseModel):
    min_foreign_score: float = 60.0
    min_momentum_score: float = 50.0
    min_volume_anomaly: float = 1.0
    min_inventory_score: float = 0.0
    min_composite_score: float = 60.0
    sector: Optional[str] = None
    hold_days: int = Field(20, ge=1, le=180)
    max_positions: int = Field(5, ge=1, le=20)
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    rebalance_every_days: int = Field(5, ge=1, le=30)
    initial_capital: float = 100_000_000.0
    commission_pct: float = 0.0015


class BacktestRequest(BaseModel):
    strategy: StrategyPayload
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    symbols: Optional[list[str]] = None


@router.get("/presets")
def list_presets():
    """Return preset strategy templates."""
    return PRESET_STRATEGIES


@router.post("/run")
def run_backtest(payload: BacktestRequest, db: Session = Depends(get_db)):
    """Run a backtest with custom parameters."""
    engine = BacktestEngine(db)

    # Default to last 12 months if no start_date
    end_date = payload.end_date
    start_date = payload.start_date or (
        (end_date or date.today()) - timedelta(days=365)
    )

    spec = StrategySpec(**payload.strategy.model_dump())
    return engine.run(
        strategy=spec,
        start_date=start_date,
        end_date=end_date,
        symbols=payload.symbols,
    )


@router.post("/run-preset/{preset_id}")
def run_preset(
    preset_id: str,
    days: int = 365,
    db: Session = Depends(get_db),
):
    """Run a preset backtest by id."""
    preset = next((p for p in PRESET_STRATEGIES if p["id"] == preset_id), None)
    if not preset:
        return {"error": f"Preset {preset_id} not found"}

    engine = BacktestEngine(db)
    spec = StrategySpec(**preset["spec"])
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    return engine.run(strategy=spec, start_date=start_date, end_date=end_date)
