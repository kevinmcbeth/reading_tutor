#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Stop production service if running (so it doesn't hog port 8000)
if systemctl is-active --quiet reading-tutor-api 2>/dev/null; then
    echo "Stopping production reading-tutor-api service..."
    sudo systemctl stop reading-tutor-api
fi

# Kill anything else on port 8000
if lsof -ti:8000 >/dev/null 2>&1; then
    echo "Killing existing process on port 8000..."
    kill $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
fi

# Start backend
echo "Starting backend..."
cd "$PROJECT_DIR/backend"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=== Reading Tutor Running ==="
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
