#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

DB_NAME="reading_tutor_test"
DB_USER="reading_tutor"
export ENV_FILE="$BACKEND_DIR/.env.test"

echo "=== Reading Tutor Test Environment ==="

# 1. Create test database if it doesn't exist
if psql -U "$DB_USER" -lqt 2>/dev/null | cut -d\| -f1 | grep -qw "$DB_NAME"; then
    echo "Database '$DB_NAME' already exists"
else
    echo "Creating database '$DB_NAME'..."
    createdb -U "$DB_USER" "$DB_NAME" 2>/dev/null || \
        sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
    echo "Database created"
fi

# 2. Seed test data
echo "Seeding test data..."
cd "$BACKEND_DIR"
python tests/seed_test_db.py

# 3. Start API server on test port
echo "Starting API server on port 8001 with mock services..."
cd "$BACKEND_DIR"
uvicorn main:app --host 0.0.0.0 --port 8001 &
API_PID=$!
echo "API PID: $API_PID"

# 4. Start arq worker
echo "Starting arq worker..."
cd "$BACKEND_DIR"
arq worker.WorkerSettings &
WORKER_PID=$!
echo "Worker PID: $WORKER_PID"

# Wait for API to be ready
echo "Waiting for API to be ready..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8001/docs > /dev/null 2>&1; then
        echo "API is ready!"
        break
    fi
    sleep 1
done

echo ""
echo "Test environment is running:"
echo "  API:    http://localhost:8001"
echo "  API PID:    $API_PID"
echo "  Worker PID: $WORKER_PID"
echo ""
echo "To stop: kill $API_PID $WORKER_PID"
echo "To teardown: scripts/teardown_test_env.sh"
