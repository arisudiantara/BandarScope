"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.routes import (
    symbols, screener, broker, foreign, sectors, watchlist,
    verdict, daily_brief, patterns, backtest, yearly_heatmap,
    broker_stalker,
)

# Auto-create tables on startup (dev convenience)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Institutional-grade IDX bandarmology & broker flow analytics platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["health"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# Mount routers
app.include_router(symbols.router, prefix="/api")
app.include_router(screener.router, prefix="/api")
app.include_router(broker.router, prefix="/api")
app.include_router(foreign.router, prefix="/api")
app.include_router(sectors.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")

# Sprint 1 routes
app.include_router(verdict.router, prefix="/api")
app.include_router(daily_brief.router, prefix="/api")
app.include_router(patterns.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(yearly_heatmap.router, prefix="/api")
app.include_router(broker_stalker.router, prefix="/api")
