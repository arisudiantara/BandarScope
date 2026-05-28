"""Daily Brief endpoints."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.daily_brief import DailyBriefService

router = APIRouter(prefix="/daily-brief", tags=["daily-brief"])


@router.get("")
def get_daily_brief(
    target_date: date | None = Query(None, description="YYYY-MM-DD (defaults to latest)"),
    max_pattern_scans: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """Structured daily brief (JSON)."""
    return DailyBriefService(db).generate(
        target_date=target_date,
        max_pattern_scans=max_pattern_scans,
    )


@router.get("/markdown", response_class=PlainTextResponse)
def get_daily_brief_markdown(
    target_date: date | None = Query(None),
    max_pattern_scans: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """Markdown rendering — usable for email or PDF export."""
    svc = DailyBriefService(db)
    brief = svc.generate(target_date=target_date, max_pattern_scans=max_pattern_scans)
    return svc.to_markdown(brief)
