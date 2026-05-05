#!/bin/sh
set -e

ES_URL="${ES_URL:-http://elasticsearch:9200}"

echo "[es-setup] Waiting for Elasticsearch to accept connections..."

until python /provision/provision_smart_slice_schema.py --es-url "$ES_URL" --skip-live-index-update; do
    echo "[es-setup] Elasticsearch not ready, retrying in 10s..."
    sleep 10
done

echo "[es-setup] Schema provisioning complete."
