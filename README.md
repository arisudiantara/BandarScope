# BandarScope

Institutional-grade IDX (Indonesian Stock Exchange) analytics platform inspired by Neo BDM, Stockbit Screener, and TradingView.

Detects accumulation/distribution activity from foreign institutions, market makers, retailers, and corporate entities using broker flow analytics.

## Modules

- **Market Summary Screener** — Composite Bandar Score, foreign flow, smart money signals
- **Sector Activity** — Hottest sectors, capital inflow/outflow, momentum ranking
- **Rotation Chart (RRG)** — Leading / Improving / Weakening / Lagging quadrants
- **Transaction Chart** — Multi-month foreign accumulation, divergence detection
- **Done Detail Visualization** — Tick-by-tick broker flow
- **Balance Position Chart** — Foreign / Institutional / Retail / Corporate breakdown
- **Inventory Chart** — Broker accumulation lines, stealth accumulation detection

## Tech Stack

- **Backend**: FastAPI (Python 3.11), SQLAlchemy, Pandas, NumPy
- **Database**: SQLite (MVP) → TimescaleDB + ClickHouse (production)
- **Frontend**: Next.js 14, TypeScript, Tailwind CSS, Lightweight Charts, ECharts
- **Realtime**: WebSocket (production)

## Quick Start

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.seed   # generate mock data
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Access:
- Backend API docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## Project Structure

```
bandarscope/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routes
│   │   ├── core/         # Config, database
│   │   ├── models/       # SQLAlchemy models
│   │   ├── services/     # Business logic
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── seed.py       # Mock data generator
│   │   └── main.py       # FastAPI app
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── app/          # Next.js pages
    │   ├── components/   # React components
    │   └── lib/          # API client, utils
    └── package.json
```

## Disclaimer

This is a demonstration platform with **synthetic mock data**. For production use:
1. Subscribe to a real IDX data feed (RTI Business, ESPT, or BEI bilateral)
2. Replace mock data generator with real ingestion pipeline
3. Migrate from SQLite to TimescaleDB + ClickHouse
4. Add authentication, rate limiting, and proper deployment infrastructure

## Customizing Broker Master

Daftar 90 broker tersimpan di `backend/app/data/brokers.csv`. Edit file ini untuk reclassify broker (foreign / institutional / market_maker / retail / corporate / zombie). Detail lengkap di `backend/app/data/README.md`.

Setelah edit CSV, jalankan:
```bash
python -m app.seed
```
