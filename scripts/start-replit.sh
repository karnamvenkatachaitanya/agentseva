#!/usr/bin/env bash
set -euo pipefail

cleanup() {
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

export RAZORPAY_MODE="${RAZORPAY_MODE:-mock}"
: "${DATABASE_URL:?DATABASE_URL is required; attach the managed PostgreSQL database}"
export SECRET_KEY="${SECRET_KEY:-${SESSION_SECRET}}"
export VITE_API_TARGET="http://127.0.0.1:8000"

(
  cd backend
  exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

for _ in {1..30}; do
  if curl --silent --fail http://127.0.0.1:8000/api/v1/health >/dev/null; then
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    wait "$BACKEND_PID"
  fi
  sleep 0.2
done

(
  cd frontend
  exec npm run dev -- --host 0.0.0.0 --port 5000
) &
FRONTEND_PID=$!

wait -n "$BACKEND_PID" "$FRONTEND_PID"