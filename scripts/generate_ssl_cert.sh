#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SSL_DIR="$ROOT_DIR/ssl"
CERT_FILE="$SSL_DIR/lumigen.crt"
KEY_FILE="$SSL_DIR/lumigen.key"
DAYS=3650

mkdir -p "$SSL_DIR"

if [ -f "$CERT_FILE" ] || [ -f "$KEY_FILE" ]; then
  echo "WARNING: SSL certificate or key already exists in $SSL_DIR"
  echo "  Cert: $CERT_FILE"
  echo "  Key:  $KEY_FILE"
  echo ""
  echo "Remove them first if you want to regenerate:"
  echo "  rm $CERT_FILE $KEY_FILE"
  exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
  echo "ERROR: openssl is not installed. Install it first:"
  echo "  Ubuntu/Debian: sudo apt install openssl"
  echo "  macOS:         brew install openssl"
  echo "  Windows:       choco install openssl"
  exit 1
fi

echo "Generating self-signed SSL certificate (valid for $DAYS days)..."
openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$KEY_FILE" \
  -out "$CERT_FILE" \
  -subj "/C=DE/ST=NRW/L=Cologne/O=Lumigen/OU=Dev/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  2>/dev/null

chmod 600 "$KEY_FILE"
chmod 644 "$CERT_FILE"

echo ""
echo "Self-signed certificate generated successfully."
echo "  Certificate: $CERT_FILE"
echo "  Private key: $KEY_FILE"
echo ""
echo "Add these lines to your .env file to enable HTTPS:"
echo "  SSL_CERT_FILE=$CERT_FILE"
echo "  SSL_KEY_FILE=$KEY_FILE"
echo ""
echo "NOTE: Browsers will show a security warning for self-signed certificates."
echo "      Click 'Advanced' -> 'Proceed to localhost' to accept it."