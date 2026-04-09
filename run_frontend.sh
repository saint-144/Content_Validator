#!/usr/bin/env bash
# run_frontend.sh — Start the Next.js frontend locally
set -e

echo "=== ContentGuard Frontend — Local Setup ==="

if ! command -v node &>/dev/null; then
  echo "ERROR: Node.js not found. Install Node.js 20+"
  exit 1
fi

cd "$(dirname "$0")/frontend"

echo "Installing npm packages..."
npm install

echo ""
echo "Starting Next.js on http://localhost:8083"
echo ""
NEXT_PUBLIC_API_URL=http://localhost:8084 npm run dev
