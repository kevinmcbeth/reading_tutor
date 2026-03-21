#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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
