#!/usr/bin/env bash
# BandarScope - One-shot setup script
# Usage: ./setup.sh

set -e

echo "=========================================="
echo "  BandarScope MVP — Setup"
echo "=========================================="

# ---------- Backend ----------
echo ""
echo "[1/3] Setting up backend..."
cd backend

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate

echo "  Installing Python dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "  Generating mock data (this takes ~30s)..."
python -m app.seed

deactivate
cd ..

# ---------- Frontend ----------
echo ""
echo "[2/3] Setting up frontend..."
cd frontend

if [ ! -f ".env.local" ]; then
  cp .env.local.example .env.local
fi

echo "  Installing npm dependencies (this may take a minute)..."
npm install

cd ..

# ---------- Done ----------
echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "Run the platform in two terminals:"
echo ""
echo "  Terminal 1 (Backend):"
echo "    cd backend"
echo "    source venv/bin/activate"
echo "    uvicorn app.main:app --reload --port 8000"
echo ""
echo "  Terminal 2 (Frontend):"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo "API docs:  http://localhost:8000/docs"
echo ""
