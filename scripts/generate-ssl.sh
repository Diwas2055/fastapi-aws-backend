#!/bin/bash
# Generate self-signed SSL certificates for local development
# Run this script to create certificates for nginx HTTPS

set -e

SSL_DIR="$(dirname "$0")/../infrastructure/ssl"
mkdir -p "$SSL_DIR"

echo "Generating self-signed SSL certificate for local development..."

# Generate private key
openssl genrsa -out "$SSL_DIR/privkey.pem" 2048

# Generate certificate
openssl req -new -x509 -key "$SSL_DIR/privkey.pem" -out "$SSL_DIR/fullchain.pem" -days 365 \
    -subj "/C=US/ST=State/L=City/O=Development/CN=localhost"

# Set permissions
chmod 600 "$SSL_DIR/privkey.pem"
chmod 644 "$SSL_DIR/fullchain.pem"

echo "SSL certificates generated in $SSL_DIR"
echo "  - privkey.pem (private key)"
echo "  - fullchain.pem (certificate)"
echo ""
echo "Note: Browsers will show a security warning for self-signed certificates."
echo "For production, use Let's Encrypt or a trusted CA certificate."