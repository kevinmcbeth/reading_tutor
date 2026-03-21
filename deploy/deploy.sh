#!/bin/bash
set -euo pipefail

# Reading Tutor - Production Deployment Script
#
# Prerequisites:
#   - Ubuntu/Debian server with sudo access
#   - GPU with CUDA drivers installed (for TTS/Whisper)
#
# Usage:
#   sudo ./deploy/deploy.sh --domain reading-tutor.duckdns.org --duckdns-token YOUR_TOKEN
#   sudo ./deploy/deploy.sh --domain reading.example.com
#
# What this script does:
#   1. Installs system packages (nginx, PostgreSQL, Redis, certbot)
#   2. Creates a system user and deploys the app to /opt/reading-tutor
#   3. Sets up PostgreSQL database and user
#   4. Builds the frontend
#   5. Installs systemd services
#   6. Configures nginx with SSL (Let's Encrypt)
#   7. Sets up DuckDNS dynamic DNS (if --duckdns-token provided)

DOMAIN=""
DUCKDNS_TOKEN=""
INSTALL_DIR="/opt/reading-tutor"
DB_USER="reading_tutor"
DB_NAME="reading_tutor"
DB_PASS=""
SERVICE_USER="reading-tutor"

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --domain) DOMAIN="$2"; shift 2 ;;
        --duckdns-token) DUCKDNS_TOKEN="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ -z "$DOMAIN" ]]; then
    echo "Usage: sudo $0 --domain YOUR_DOMAIN [--duckdns-token TOKEN]"
    echo ""
    echo "Examples:"
    echo "  sudo $0 --domain reading-tutor.duckdns.org --duckdns-token abc123"
    echo "  sudo $0 --domain reading.example.com"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root (sudo)"
    exit 1
fi

# Auto-detect DuckDNS domain
IS_DUCKDNS=false
DUCKDNS_SUBDOMAIN=""
if [[ "$DOMAIN" == *.duckdns.org ]]; then
    IS_DUCKDNS=true
    DUCKDNS_SUBDOMAIN="${DOMAIN%.duckdns.org}"
    if [[ -z "$DUCKDNS_TOKEN" ]]; then
        echo "ERROR: --duckdns-token is required for .duckdns.org domains"
        echo ""
        echo "Get your token at https://www.duckdns.org after signing in."
        exit 1
    fi
fi

echo "=== Reading Tutor Production Deployment ==="
echo "Domain: $DOMAIN"
echo "Install dir: $INSTALL_DIR"
if $IS_DUCKDNS; then
    echo "DuckDNS subdomain: $DUCKDNS_SUBDOMAIN"
fi
echo ""

# Generate a random DB password
DB_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

# -------------------------------------------------------------------
# 1. Install system packages
# -------------------------------------------------------------------
echo ">>> Installing system packages..."
apt-get update -qq
apt-get install -y -qq \
    nginx \
    postgresql postgresql-contrib \
    redis-server \
    python3 python3-venv python3-pip \
    nodejs npm \
    certbot python3-certbot-nginx \
    curl \
    git

# -------------------------------------------------------------------
# 2. Set up DuckDNS (if applicable)
# -------------------------------------------------------------------
if $IS_DUCKDNS; then
    echo ">>> Setting up DuckDNS..."

    # Update IP now
    DUCKDNS_RESULT=$(curl -s "https://www.duckdns.org/update?domains=$DUCKDNS_SUBDOMAIN&token=$DUCKDNS_TOKEN&verbose=true")
    echo "  DuckDNS update response: $DUCKDNS_RESULT"

    if echo "$DUCKDNS_RESULT" | head -1 | grep -q "KO"; then
        echo "ERROR: DuckDNS update failed. Check your token and subdomain."
        exit 1
    fi

    # Create update script
    mkdir -p /opt/duckdns
    cat > /opt/duckdns/update.sh <<DUCKEOF
#!/bin/bash
curl -s "https://www.duckdns.org/update?domains=$DUCKDNS_SUBDOMAIN&token=$DUCKDNS_TOKEN" -o /opt/duckdns/last_update.log
DUCKEOF
    chmod 700 /opt/duckdns/update.sh

    # Install cron job to update every 5 minutes
    CRON_LINE="*/5 * * * * /opt/duckdns/update.sh"
    ( (crontab -l 2>/dev/null || true) | grep -v duckdns || true; echo "$CRON_LINE") | crontab -
    echo "  DuckDNS cron job installed (updates every 5 minutes)"

    # Wait a moment for DNS propagation
    echo "  Waiting 10s for DNS propagation..."
    sleep 10
fi

# -------------------------------------------------------------------
# 3. Create system user
# -------------------------------------------------------------------
echo ">>> Creating service user..."
if ! id "$SERVICE_USER" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$INSTALL_DIR" "$SERVICE_USER"
fi

# -------------------------------------------------------------------
# 4. Deploy application files
# -------------------------------------------------------------------
echo ">>> Deploying application to $INSTALL_DIR..."
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

mkdir -p "$INSTALL_DIR"
rsync -a --exclude='node_modules' --exclude='venv' --exclude='__pycache__' \
    --exclude='.git' --exclude='data' \
    "$PROJECT_DIR/" "$INSTALL_DIR/"

# Preserve data directory
mkdir -p "$INSTALL_DIR/backend/data/stories"
chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

# -------------------------------------------------------------------
# 5. Set up PostgreSQL
# -------------------------------------------------------------------
echo ">>> Setting up PostgreSQL..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

DATABASE_URL="postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"

# -------------------------------------------------------------------
# 6. Configure backend
# -------------------------------------------------------------------
echo ">>> Setting up backend..."
cd "$INSTALL_DIR/backend"

# Generate JWT secret
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

# Create .env file
cat > .env <<ENVEOF
DATABASE_URL=$DATABASE_URL
REDIS_URL=redis://localhost:6379
FRONTEND_URL=https://$DOMAIN
BACKEND_PORT=8000
JWT_SECRET=$JWT_SECRET
ENVEOF

# Set up Python venv and install deps
sudo -u "$SERVICE_USER" python3 -m venv venv
sudo -u "$SERVICE_USER" venv/bin/pip install --quiet -r requirements.txt

chown "$SERVICE_USER:$SERVICE_USER" .env
chmod 600 .env

# -------------------------------------------------------------------
# 7. Build frontend
# -------------------------------------------------------------------
echo ">>> Building frontend..."
cd "$INSTALL_DIR/frontend"
npm install --quiet
npm run build

# -------------------------------------------------------------------
# 8. Install systemd services
# -------------------------------------------------------------------
echo ">>> Installing systemd services..."
cp "$INSTALL_DIR/deploy/systemd/reading-tutor-api.service" /etc/systemd/system/
cp "$INSTALL_DIR/deploy/systemd/reading-tutor-worker.service" /etc/systemd/system/

systemctl daemon-reload
systemctl enable reading-tutor-api reading-tutor-worker

# -------------------------------------------------------------------
# 9. Configure nginx
# -------------------------------------------------------------------
echo ">>> Configuring nginx..."

# Create certbot webroot
mkdir -p /var/www/certbot

# Write nginx config with domain substituted
sed "s/YOUR_DOMAIN/$DOMAIN/g" \
    "$INSTALL_DIR/deploy/nginx/reading-tutor.conf" \
    > /etc/nginx/sites-available/reading-tutor.conf

# Remove default site if it exists
rm -f /etc/nginx/sites-enabled/default

ln -sf /etc/nginx/sites-available/reading-tutor.conf /etc/nginx/sites-enabled/

# -------------------------------------------------------------------
# 10. SSL certificate
# -------------------------------------------------------------------
echo ">>> Obtaining SSL certificate..."

# Temporarily allow HTTP for certbot
cat > /etc/nginx/sites-available/reading-tutor-temp.conf <<TMPEOF
server {
    listen 80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 444;
    }
}
TMPEOF
ln -sf /etc/nginx/sites-available/reading-tutor-temp.conf /etc/nginx/sites-enabled/reading-tutor-temp.conf
rm -f /etc/nginx/sites-enabled/reading-tutor.conf
nginx -t && systemctl restart nginx

# For DuckDNS, use a real email instead of admin@domain
CERT_EMAIL="admin@$DOMAIN"
if $IS_DUCKDNS; then
    CERT_EMAIL="duckdns-user@localhost"
    # certbot needs --register-unsafely-without-email for localhost emails
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" --non-interactive --agree-tos \
        --register-unsafely-without-email || {
        echo ""
        echo "WARNING: certbot failed. You can run it manually later:"
        echo "  sudo certbot certonly --webroot -w /var/www/certbot -d $DOMAIN"
        echo ""
    }
else
    certbot certonly --webroot -w /var/www/certbot \
        -d "$DOMAIN" --non-interactive --agree-tos \
        --email "$CERT_EMAIL" || {
        echo ""
        echo "WARNING: certbot failed. You can run it manually later:"
        echo "  sudo certbot --nginx -d $DOMAIN"
        echo ""
    }
fi

# Switch to full config
rm -f /etc/nginx/sites-enabled/reading-tutor-temp.conf
rm -f /etc/nginx/sites-available/reading-tutor-temp.conf
ln -sf /etc/nginx/sites-available/reading-tutor.conf /etc/nginx/sites-enabled/

# Set up automatic cert renewal
systemctl enable certbot.timer 2>/dev/null || true

# -------------------------------------------------------------------
# 11. Start services
# -------------------------------------------------------------------
echo ">>> Starting services..."
systemctl restart redis-server
systemctl restart postgresql
nginx -t && systemctl restart nginx
systemctl start reading-tutor-api
systemctl start reading-tutor-worker

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
echo ""
echo "=========================================="
echo "  Deployment Complete!"
echo "=========================================="
echo ""
echo "  URL:      https://$DOMAIN"
echo "  API Docs: https://$DOMAIN/docs"
echo ""
echo "  Services:"
echo "    systemctl status reading-tutor-api"
echo "    systemctl status reading-tutor-worker"
echo ""
echo "  Logs:"
echo "    journalctl -u reading-tutor-api -f"
echo "    journalctl -u reading-tutor-worker -f"
echo ""
echo "  Database: $DATABASE_URL"
echo "  Config:   $INSTALL_DIR/backend/.env"
echo ""
if $IS_DUCKDNS; then
    echo "  DuckDNS:"
    echo "    Subdomain: $DUCKDNS_SUBDOMAIN.duckdns.org"
    echo "    IP updates every 5 min via cron"
    echo "    Manual update: /opt/duckdns/update.sh"
    echo ""
fi
echo "  To migrate existing SQLite data:"
echo "    cd $INSTALL_DIR && python3 scripts/migrate_sqlite_to_pg.py \\"
echo "      --sqlite-path /path/to/old/data/reading_tutor.db \\"
echo "      --pg-url '$DATABASE_URL'"
echo ""
echo "  Register your first family account at https://$DOMAIN/parent"
echo ""
