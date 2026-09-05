@echo off
REM ==========================================================================
REM  AgentSeva - Cloudflare Tunnel launcher for instant HTTPS webhook testing.
REM
REM  Exposes the local backend (http://localhost:8000) on a public https URL
REM  so Razorpay can deliver real webhooks to your machine during development.
REM
REM  Prerequisite: install cloudflared once -
REM     winget install --id Cloudflare.cloudflared
REM     (or download from https://github.com/cloudflare/cloudflared/releases)
REM
REM  After it prints a https://<random>.trycloudflare.com URL, register it in
REM  the Razorpay Dashboard -> Settings -> Webhooks as:
REM     https://<random>.trycloudflare.com/api/v1/webhooks/razorpay
REM  and set the same secret in .env as RAZORPAY_WEBHOOK_SECRET.
REM ==========================================================================

setlocal
set BACKEND_PORT=8000

where cloudflared >nul 2>nul
if errorlevel 1 (
    echo [ERROR] cloudflared not found on PATH.
    echo         Install it with:  winget install --id Cloudflare.cloudflared
    echo         Then re-run this script.
    exit /b 1
)

echo Starting Cloudflare tunnel to http://localhost:%BACKEND_PORT% ...
echo (Press Ctrl+C to stop.)
echo.
cloudflared tunnel --url http://localhost:%BACKEND_PORT%

endlocal
