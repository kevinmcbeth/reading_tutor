#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

DB_NAME="reading_tutor_test"
DB_USER="reading_tutor"

echo "=== Tearing Down Test Environment ==="

# 1. Kill any test API/worker processes on port 8001
echo "Stopping processes on port 8001..."
lsof -ti:8001 | xargs kill 2>/dev/null || true

# 2. Drop test database
echo "Dropping database '$DB_NAME'..."
dropdb -U "$DB_USER" --if-exists "$DB_NAME" 2>/dev/null || \
    sudo -u postgres dropdb --if-exists "$DB_NAME" || true
echo "Database dropped"

# 3. Clean test data directory
DATA_TEST_DIR="$BACKEND_DIR/data_test"
if [ -d "$DATA_TEST_DIR" ]; then
    echo "Removing test data directory..."
    rm -rf "$DATA_TEST_DIR"
    echo "Test data removed"
fi

echo "Teardown complete"
