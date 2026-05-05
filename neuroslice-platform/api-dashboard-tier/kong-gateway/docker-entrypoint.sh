#!/bin/sh
# Pre-process the kong.yml.template before handing off to the official Kong
# entrypoint.  This allows runtime injection of secrets and optional config
# without baking them into the image.
#
# Variables consumed:
#   DASHBOARD_JWT_SECRET   — HS256 secret shared with auth-service (required)
#   KONG_EXTRA_CORS_ORIGIN — optional extra CORS origin for deployed frontends
#
# No external tools required beyond sh and sed (both present in kong:3.7).
set -e

TEMPLATE=/etc/kong/kong.yml.template
PROCESSED=/etc/kong/kong.yml

KONG_JWT_SECRET="${DASHBOARD_JWT_SECRET:-change-me-jwt-secret-min-32-chars}"

# Step 1 — handle the optional extra CORS origin placeholder.
# The template contains the literal comment "# EXTRA_CORS_PLACEHOLDER" on a
# line by itself.  If KONG_EXTRA_CORS_ORIGIN is set, replace that comment
# with the actual YAML list entry.  Otherwise, remove the comment line.
if [ -n "${KONG_EXTRA_CORS_ORIGIN:-}" ]; then
    sed "s|        # EXTRA_CORS_PLACEHOLDER|        - ${KONG_EXTRA_CORS_ORIGIN}|" \
        "$TEMPLATE" > /tmp/kong-cors-processed.yml
else
    sed '/# EXTRA_CORS_PLACEHOLDER/d' "$TEMPLATE" > /tmp/kong-cors-processed.yml
fi

# Step 2 — substitute $KONG_JWT_SECRET using sed.
# Escape characters that are special in the sed replacement field (\ | &)
# so that a secret containing those characters is inserted literally.
ESCAPED_SECRET=$(printf '%s\n' "$KONG_JWT_SECRET" | sed 's/[\\|&]/\\&/g')
sed "s|\\\$KONG_JWT_SECRET|${ESCAPED_SECRET}|g" \
    /tmp/kong-cors-processed.yml > "$PROCESSED"

echo "[neuroslice-entrypoint] kong.yml generated from template."

# Hand off to the official Kong Docker entrypoint with the original CMD args.
exec /docker-entrypoint.sh "$@"
