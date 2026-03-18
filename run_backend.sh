#!/usr/bin/env bash
# run_local.sh — Start the backend locally without Docker
set -e

echo "=== ContentGuard Backend — Local Setup ==="

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.11+"
  exit 1
fi

cd "$(dirname "$0")/backend"

# Create venv if missing
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Copy env if missing
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Created backend/.env from template."
  echo "    Edit backend/.env and set your ANTHROPIC_API_KEY and DATABASE_URL"
  echo ""
fi

echo ""
echo "Starting FastAPI server on http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8000
