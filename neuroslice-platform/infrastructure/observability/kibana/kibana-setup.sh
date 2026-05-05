#!/bin/sh
set -e

KIBANA_URL="${KIBANA_URL:-http://kibana:5601}"
INDEX_PATTERN="${INDEX_PATTERN:-logs-smart_slice.predictions-*}"

echo "[kibana-setup] Waiting for Kibana API to become available..."

until python - "$KIBANA_URL" <<'PYEOF'
import sys, urllib.request, json
url = sys.argv[1] + "/api/status"
try:
    r = urllib.request.urlopen(url, timeout=5)
    level = json.loads(r.read()).get("status", {}).get("overall", {}).get("level", "")
    sys.exit(0 if level == "available" else 1)
except Exception:
    sys.exit(1)
PYEOF
do
    echo "[kibana-setup] Kibana not available yet, retrying in 10s..."
    sleep 10
done

echo "[kibana-setup] Kibana ready — waiting 15s for internal services to stabilise..."
sleep 15

echo "[kibana-setup] Running provisioning..."

until python /provision/provision_smart_slice_dashboard.py \
    --kibana-url "$KIBANA_URL" \
    --index-pattern "$INDEX_PATTERN"
do
    echo "[kibana-setup] Provision attempt failed, retrying in 10s..."
    sleep 10
done

echo "[kibana-setup] Dashboard provisioning complete."
