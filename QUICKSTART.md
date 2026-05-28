# BandarScope — Quick Start Guide

## Prasyarat

- **Python 3.11+** (cek: `python3 --version`)
- **Node.js 18+** (cek: `node --version`)
- **npm** atau **pnpm**

## Cara Menjalankan (3 Langkah)

### Opsi A: Pakai Setup Script (Otomatis)

```bash
chmod +x setup.sh
./setup.sh
```

Script akan: install Python + npm deps, generate mock data, dan kasih instruksi untuk start server.

### Opsi B: Manual (Lebih Kontrol)

#### 1. Backend (Terminal 1)

```bash
cd backend

# Buat virtual env
python3 -m venv venv
source venv/bin/activate           # Linux/Mac
# venv\Scripts\activate            # Windows

# Install dependencies
pip install -r requirements.txt

# Generate mock data (~30 detik, 50 saham × 120 hari)
python -m app.seed

# Start API server
uvicorn app.main:app --reload --port 8000
```

Backend siap di **http://localhost:8000**
API docs: **http://localhost:8000/docs**

#### 2. Frontend (Terminal 2)

```bash
cd frontend

# Setup env
cp .env.local.example .env.local

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend siap di **http://localhost:3000**

---

## Yang Bisa Kamu Eksplor

### 1. Dashboard (`/`)
Market summary, smart money picks, distribution warnings, sector capital flow

### 2. Screener (`/screener`)
- 5 preset siap pakai: *Smart Money Accumulation*, *Stealth Accumulation*, *Breakout Setup*, *Distribution Warning*, *Foreign Inflow Leaders*
- 8 filter komposit: BandarScore, Foreign Net, Inventory, Momentum, Volume Anomaly, Signal, Sector, Price
- Sort by 6 metrik berbeda

### 3. Sectors (`/sectors`)
- Ranking 8 sektor IDX
- Capital inflow vs outflow
- Flow signal: `INFLOW_RISING`, `INFLOW_BUILDING`, `OUTFLOW_DEFYING`, `OUTFLOW_DECLINING`

### 4. Rotation (RRG) (`/rotation`)
- Sector Rotation Graph (Leading / Improving / Weakening / Lagging)
- Period: 14D / 30D / 60D / 90D
- Tail history per sektor

### 5. Heatmap (`/heatmap`)
- Treemap semua saham
- Color: pct change · Size: traded value
- Click saham → masuk detail

### 6. Stock Detail (`/stock/[SYMBOL]`)
**Halaman terlengkap** — coba akses `/stock/BBCA` atau `/stock/MEDC`:

- 7 score panel (Bandar, Foreign, Inventory, Volume, Momentum, Consistency, Signal)
- Price chart dengan volume
- **Inventory Chart** dengan stealth accumulation detection
- Top accumulators & distributors (broker breakdown)
- **Foreign Flow Chart** dengan divergence detection
- **Transaction Chart** (multi-month) dengan hidden accumulation detection
- **Balance Position Chart** (foreign / institutional / retail / corporate)

### 7. Watchlist (`/watchlist`)
- 2 watchlist default sudah dibuat: *Blue Chip*, *Bandar Watch*
- CRUD watchlist
- Live BandarScore per saham

### 8. Alerts (`/alerts`)
5 alert template: *Bandar Breakout*, *Stealth Accumulation*, *Foreign Inflow Surge*, *Distribution Warning*, *Sector Enters Leading*

---

## Arsitektur Modul yang Sudah Diimplementasi

| Modul | Backend Service | Frontend Chart | Status |
|---|---|---|---|
| Market Summary Screener | `services/screener.py` | `app/screener/page.tsx` | Done |
| Sector Activity | `services/sector.py` (activity) | `app/sectors/page.tsx` | Done |
| Rotation Chart (RRG) | `services/sector.py` (rrg) | `components/charts/RRGChart.tsx` | Done |
| Transaction Chart | `services/transaction.py` | `components/charts/TransactionChart.tsx` | Done |
| Done Detail | `services/broker_flow.py` (done_detail_summary) | (rendered in stock detail) | Done |
| Balance Position Chart | `services/balance_position.py` | `components/charts/BalancePositionChart.tsx` | Done |
| Inventory Chart | `services/broker_flow.py` (inventory_lines) | `components/charts/InventoryChart.tsx` | Done |
| Foreign Flow | `services/foreign_flow.py` | `components/charts/ForeignFlowChart.tsx` | Done |
| Heatmap | `services/sector.py` (heatmap) | `components/charts/HeatmapChart.tsx` | Done |

---

## Algoritma Inti

### Composite BandarScore (0-100)

```
BandarScore = 
  ForeignFlowScore  × 0.25 +
  InventoryScore    × 0.25 +
  VolumeAnomalyScore × 0.20 +
  MomentumScore     × 0.15 +
  ConsistencyScore  × 0.15
```

### Inventory Line (Per Broker)

```
inventory[t] = inventory[t-1] + (buy_lot[t] - sell_lot[t])
```

Top 6 broker by absolute net value diplot vs price → langsung kelihatan
broker mana yang akumulasi konsisten.

### Stealth Accumulation Detection

Trigger ketika:
- Price change 60D < +3% (sideways/down), DAN
- Total inventory growth dari positive accumulators > 0, DAN
- Jumlah accumulator (institutional+market_maker) >= 2

### Foreign Flow Divergence

```
BULLISH_DIVERGENCE: price_change_20D < -1.5% AND flow_normalized > +0.05
BEARISH_DIVERGENCE: price_change_20D > +2.0% AND flow_normalized < -0.05
```

### RRG Quadrant

```
RS-Ratio    = (Sector Index / IHSG) × 100, smoothed 10D SMA
RS-Momentum = (RS_Ratio[t] / RS_Ratio[t-10]) × 100

Leading   : RS_Ratio ≥ 100 AND RS_Momentum ≥ 100
Weakening : RS_Ratio ≥ 100 AND RS_Momentum <  100
Lagging   : RS_Ratio <  100 AND RS_Momentum <  100
Improving : RS_Ratio <  100 AND RS_Momentum ≥ 100
```

---

## Dari MVP ke Production

### Phase 1: Real Data Integration
Ganti `app/seed.py` dengan ingestion pipeline:
- **RTI Business API** (langganan Rp 300-600rb/bulan)
- **Stockbit Premium** (jika punya akses)
- **ESPT bilateral** (institutional grade, kontak BEI)

### Phase 2: Database Migration
- SQLite → **TimescaleDB** (untuk ticks/candles)
- Tambah **ClickHouse** (untuk broker analytics)
- Tambah **Redis Cluster** (cache + pub/sub)

### Phase 3: Realtime
- Setup **Kafka** untuk tick ingestion
- Tambah **WebSocket Hub** (Socket.io di NestJS)
- Service split: `svc-tick-engine`, `svc-broker-flow`, `svc-screener`, dll.

### Phase 4: AI/ML
- Train classifier untuk broker behavior (dataset historikal)
- Anomaly detection model (LSTM autoencoder untuk volume/flow anomalies)
- Composite score model (XGBoost trained on labeled outcomes)

### Phase 5: Multi-tenant SaaS
- Auth (JWT + Google OAuth)
- Stripe billing (Free / Pro / Institutional plans)
- Rate limiting per plan tier
- Mobile app (Expo React Native)

---

## Troubleshooting

### Backend "ModuleNotFoundError"
Pastikan venv aktif: `source venv/bin/activate`

### "No symbols match your filters"
Mock data variasi pattern-nya random. Coba: BandarScore Min = 60, klik *Smart Money Accumulation* preset.

### Frontend chart tidak muncul
Buka DevTools → Network. Pastikan request ke `/api/...` return 200, bukan CORS error.
Cek `next.config.mjs` rewrite rule, dan `CORS_ORIGINS` di `backend/app/core/config.py`.

### Port conflict
- Backend port: ubah `--port 8000` di uvicorn
- Frontend port: `PORT=3001 npm run dev`
- Lalu update `NEXT_PUBLIC_API_URL` di `frontend/.env.local`
