#!/usr/bin/env bash
set -euo pipefail

export RAZORPAY_MODE="${RAZORPAY_MODE:-mock}"
: "${DATABASE_URL:?Managed DATABASE_URL is required}"
export SECRET_KEY="${SECRET_KEY:-${SESSION_SECRET:?SESSION_SECRET is required}}"

exec python -m uvicorn app.main:app \
  --app-dir backend \
  --host 0.0.0.0 \
  --port 5000 \
  --proxy-headers \
  --forwarded-allow-ips="*"