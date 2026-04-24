#!/bin/sh
set -eu

python scripts/wait_for_db.py
alembic upgrade head

if [ -n "${INITIAL_ADMIN_EMAIL:-}" ] || [ -n "${INITIAL_ADMIN_PASSWORD:-}" ] || [ -n "${INITIAL_ADMIN_FULL_NAME:-}" ]; then
  if [ -z "${INITIAL_ADMIN_EMAIL:-}" ] || [ -z "${INITIAL_ADMIN_PASSWORD:-}" ]; then
    echo "INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must both be set when bootstrap seeding is enabled." >&2
    exit 1
  fi

  export INITIAL_ADMIN_FULL_NAME="${INITIAL_ADMIN_FULL_NAME:-NeuroSlice Administrator}"
  python scripts/seed_admin.py
fi

exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
