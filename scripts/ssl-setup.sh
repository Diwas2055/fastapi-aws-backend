#!/bin/bash
# SSL setup script - supports both self-signed (local) and Let's Encrypt (production)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SSL_DIR="$PROJECT_ROOT/infrastructure/ssl"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
elif [ -f "$PROJECT_ROOT/.env.local" ]; then
    set -a
    source "$PROJECT_ROOT/.env.local"
    set +a
fi

DOMAIN_NAME="${DOMAIN_NAME:-localhost}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-admin@example.com}"
CERTBOT_DATA="$PROJECT_ROOT/infrastructure/certbot"

mkdir -p "$SSL_DIR"
mkdir -p "$CERTBOT_DATA/conf"
mkdir -p "$CERTBOT_DATA/www"

if [ "$DOMAIN_NAME" = "localhost" ] || [ -z "$DOMAIN_NAME" ]; then
    echo "Generating self-signed SSL certificates for local development..."
    openssl genrsa -out "$SSL_DIR/privkey.pem" 2048
    openssl req -new -x509 -key "$SSL_DIR/privkey.pem" -out "$SSL_DIR/fullchain.pem" -days 365 \
        -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"
    chmod 600 "$SSL_DIR/privkey.pem"
    chmod 644 "$SSL_DIR/fullchain.pem"
    echo "Self-signed certificates generated in $SSL_DIR"
    echo "  - privkey.pem (private key)"
    echo "  - fullchain.pem (certificate)"
    echo ""
    echo "Note: Browsers will show a security warning for self-signed certificates."
    echo "For production, set DOMAIN_NAME to your actual domain and run this script again."
else
    echo "Obtaining Let's Encrypt certificates for $DOMAIN_NAME..."
    echo "Make sure:"
    echo "  1. Port 80 is open to the internet"
    echo "  2. DNS for $DOMAIN_NAME points to this server"
    echo "  3. Nginx is running and reachable"
    echo ""

    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo "Installing certbot..."
        if [ -f /etc/debian_version ]; then
            apt-get update && apt-get install -y certbot
        elif [ -f /etc/redhat-release ]; then
            yum install -y certbot
        else
            echo "Please install certbot manually for your OS"
            exit 1
        fi
    fi

    # Obtain certificate
    certbot certonly \
        --webroot \
        --webroot-path="$CERTBOT_DATA/www" \
        --email "$CERTBOT_EMAIL" \
        --agree-tos \
        --no-eff-email \
        --force-renewal \
        -d "$DOMAIN_NAME"

    # Copy certificates to SSL directory
    LE_CERT_PATH="/etc/letsencrypt/live/$DOMAIN_NAME"
    if [ -d "$LE_CERT_PATH" ]; then
        cp "$LE_CERT_PATH/fullchain.pem" "$SSL_DIR/fullchain.pem"
        cp "$LE_CERT_PATH/privkey.pem" "$SSL_DIR/privkey.pem"
        chmod 600 "$SSL_DIR/privkey.pem"
        chmod 644 "$SSL_DIR/fullchain.pem"
        echo "Certificates copied to $SSL_DIR"
        echo "Reload nginx to apply new certificates:"
        echo "  docker-compose exec nginx nginx -s reload"
    else
        echo "Error: Certificate not found at $LE_CERT_PATH"
        exit 1
    fi
fi
