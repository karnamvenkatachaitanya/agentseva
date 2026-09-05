# Running AgentSeva on Replit

The `Start application` workflow runs both services:

- React/Vite frontend on port 5000 (the Replit web preview)
- FastAPI backend on internal port 8000
- Vite proxies same-origin `/api` requests to FastAPI

The app defaults to offline Razorpay mock mode and uses the workspace's managed
PostgreSQL database, so no external credentials are required. The existing
`SESSION_SECRET` is used as the backend signing secret. Live Hugging Face chat
or Razorpay transactions require adding the corresponding credentials and
explicitly changing `RAZORPAY_MODE`.

To run manually:

```bash
bash scripts/start-replit.sh
```

## Production

Publishing builds the Vite frontend and serves it from the FastAPI process on
port 5000. The production command is:

```bash
bash scripts/start-production.sh
```

The deployment uses the Hugging Face secret, Razorpay mock mode, and Replit's
managed PostgreSQL database. Schema changes are applied to development by
`python scripts/sync-development-db.py`; Replit's Publish flow diffs the
development schema and applies it to production. Runtime startup never creates
or alters tables. Add future schema changes as versioned revisions under
`backend/migrations/`; do not use `Base.metadata.create_all()` as the migration
workflow. Orders and audit history survive restarts and redeployments, and the
deployment can use Autoscale.
