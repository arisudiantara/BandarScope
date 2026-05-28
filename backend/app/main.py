"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.api.routes import symbols, screener, broker, foreign, sectors, watchlist

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
