#!/bin/bash
set -e
echo "=== Reading Tutor Setup ==="

# Check Python
echo "Checking Python..."
python3 --version || { echo "Python 3 required"; exit 1; }

# Check Node
echo "Checking Node.js..."
node --version || { echo "Node.js required"; exit 1; }

# Backend setup
echo "Setting up backend..."
cd "$(dirname "$0")/../backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# Create data directory
mkdir -p data/stories

# Frontend setup
echo "Setting up frontend..."
cd ../frontend
npm install

echo ""
echo "=== Setup Complete ==="
echo "Run ./scripts/dev.sh to start the application"
