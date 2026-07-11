#!/usr/bin/env bash
# dev.sh – start the Aktenfux backend API and React frontend together for development.
#
# Usage:
#   ./dev.sh
#
# Requirements:
#   - Python virtual environment activated (or `afu` on PATH)
#   - Node.js / npm installed
#
# The backend listens on http://127.0.0.1:8000
# The frontend listens on http://localhost:5173
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install frontend dependencies if node_modules is missing
if [ ! -d "$SCRIPT_DIR/webapp/node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install --prefix "$SCRIPT_DIR/webapp"
fi

cleanup() {
    echo ""
    echo "Stopping backend and frontend..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Starting Aktenfux backend..."
afu gui --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Starting Aktenfux frontend..."
npm run dev --prefix "$SCRIPT_DIR/webapp" &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both."

wait "$BACKEND_PID" "$FRONTEND_PID"
