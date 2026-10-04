#!/bin/bash
# Issue the initial Let's Encrypt certificate.
#
# nginx will not start without a certificate, and certbot cannot validate
# without nginx serving the ACME challenge. This breaks the deadlock by
# planting a self-signed placeholder, starting nginx, requesting the real
# certificate, then reloading.
#
# Run once, from the repository root, after DNS points at this host.

set -e

# One certificate covering both hostnames (a SAN certificate), stored
# under live/$DOMAIN and referenced by both nginx server blocks.
DOMAIN="${DOMAIN:-brainvar.haseebakhlaq.com}"
API_DOMAIN="${API_DOMAIN:-api.brainvar.haseebakhlaq.com}"
EMAIL="${EMAIL:-haseebdeveloper2000@gmail.com}"   # expiry notices go here
STAGING="${STAGING:-0}"            # export STAGING=1 to test without hitting rate limits
COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"

mkdir -p certbot/conf certbot/www

if [ -d "certbot/conf/live/$DOMAIN" ]; then
  echo "A certificate for $DOMAIN already exists. Delete certbot/conf/live/$DOMAIN to reissue."
  exit 0
fi

echo "### Copying recommended TLS parameters out of the certbot image..."
# Taken from the image rather than a GitHub raw URL, because those paths move.
docker run --rm -v "$PWD/certbot/conf:/out" --entrypoint sh certbot/certbot -c '
  cp /opt/certbot/src/certbot/src/certbot/_internal/plugins/nginx/tls_configs/options-ssl-nginx.conf /out/
  cp /opt/certbot/src/certbot/src/certbot/ssl-dhparams.pem /out/'
test -s certbot/conf/options-ssl-nginx.conf || { echo "Failed to obtain TLS parameters"; exit 1; }

echo "### Creating a placeholder certificate so nginx can start..."
mkdir -p "certbot/conf/live/$DOMAIN"
# --entrypoint is required: the image's default entrypoint is `certbot`, so
# without it these arguments are handed to certbot instead of openssl.
docker run --rm -v "$PWD/certbot/conf:/etc/letsencrypt" \
  --entrypoint openssl certbot/certbot \
  req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout "/etc/letsencrypt/live/$DOMAIN/privkey.pem" \
    -out "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" \
    -subj "/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:$API_DOMAIN"

echo "### Starting nginx..."
$COMPOSE up -d nginx

echo "### Removing the placeholder..."
docker run --rm -v "$PWD/certbot/conf:/etc/letsencrypt" \
  --entrypoint sh certbot/certbot -c "\
    rm -rf /etc/letsencrypt/live/$DOMAIN \
           /etc/letsencrypt/archive/$DOMAIN \
           /etc/letsencrypt/renewal/$DOMAIN.conf"

echo "### Requesting the real certificate..."
STAGING_ARG=""
[ "$STAGING" != "0" ] && STAGING_ARG="--staging"

$COMPOSE run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    $STAGING_ARG \
    --email $EMAIL \
    -d $DOMAIN \
    -d $API_DOMAIN \
    --rsa-key-size 4096 \
    --agree-tos \
    --no-eff-email \
    --force-renewal" certbot

echo "### Reloading nginx..."
$COMPOSE exec nginx nginx -s reload

echo
echo "Done. https://$DOMAIN and https://$API_DOMAIN should now serve a valid certificate."
