#!/bin/bash
set -euo pipefail

# Reading Tutor - Update/Redeploy Script
#
# Pulls latest code and restarts services. Run from the project directory.
#
# Usage: sudo ./deploy/update.sh

INSTALL_DIR="/opt/reading-tutor"
SERVICE_USER="reading-tutor"

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (sudo)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ">>> Syncing application files..."
rsync -a --exclude='node_modules' --exclude='venv' --exclude='__pycache__' \
    --exclude='.git' --exclude='data' --exclude='.env' \
    "$PROJECT_DIR/" "$INSTALL_DIR/"

chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

echo ">>> Updating backend dependencies..."
cd "$INSTALL_DIR/backend"
sudo -u "$SERVICE_USER" venv/bin/pip install --quiet -r requirements.txt

echo ">>> Rebuilding frontend..."
cd "$INSTALL_DIR/frontend"
npm install --quiet
npm run build

echo ">>> Restarting services..."
systemctl restart reading-tutor-api
systemctl restart reading-tutor-worker
systemctl reload nginx

echo ">>> Done. Services restarted."
systemctl --no-pager status reading-tutor-api reading-tutor-worker | head -20
