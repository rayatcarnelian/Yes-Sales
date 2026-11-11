# Runbook

## Local Postgres without Docker

This workspace machine did not have Docker on PATH. A portable PostgreSQL 16 binary can live in `.tools/pgsql` (gitignored) with data in `.local/pgdata`.

```powershell
$env:PGPASSWORD = "yes"
& ".\.tools\pgsql\bin\pg_ctl.exe" -D ".\.local\pgdata" -l ".\.local\postgres.log" -o "-p 5432" start
& ".\.tools\pgsql\bin\psql.exe" -U yes -h 127.0.0.1 -d postgres -c "SELECT 1 FROM pg_database WHERE datname = 'yes_sales'"
```

Create `yes_sales` if that query returns no row:

```powershell
& ".\.tools\pgsql\bin\psql.exe" -U yes -h 127.0.0.1 -d postgres -c "CREATE DATABASE yes_sales"
```

Stop the cluster with `pg_ctl -D .\.local\pgdata stop`.

## Docker

When Docker is installed:

```powershell
copy .env.example .env
docker compose up --build
```

The API container runs migrations on startup because `AUTO_MIGRATE` defaults to true.

## Seed and a TEST transaction

```powershell
$env:PYTHONPATH = "apps\api"
.\.venv\Scripts\python scripts\seed_demo.py
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps\api --port 8000
.\.venv\Scripts\python scripts\simulate_transaction.py
```

The simulator creates companies whose names start with `TEST`. It does not send live email or place a phone call.

## Operations

- Pause outbound: founder `POST /settings/outbound-pause` with `{"paused": true}`, or the Agents page.
- Restart a failed task: `POST /tasks/{id}/retry`, then `POST /tasks/process`.
- Scheduler hook: `POST /tasks/external` with header `X-Scheduler-Token`.
- Inbound email: `POST /webhooks/email/inbound` with `X-Yes-Signature` set to the hex HMAC-SHA256 of the raw body using `WEBHOOK_SECRET`.
- A body containing the word `stop`, or an unsubscribe phrase, opts the matching email contact out and blocks later follow-up.
- Voice mock: `POST /calls/mock` on the API, or `POST /sessions/mock` on the voice gateway. Both say that no carrier was contacted.
- Live voice: set the Twilio and xAI variables, expose the gateway, and point the Twilio voice webhook at `https://<public host>/twiml`.

## Failure checks

- `GET /health` on port 8000 and port 3001.
- `GET /integrations` shows which adapters are live.
- `GET /audit-events` should contain a row for company creation, messages, approvals, and blocked outbound attempts.
- If `yes_app` cannot see rows, the request transaction did not set `app.role`. Login itself uses the admin role only to verify the password.

## What this system will not do

It will not send a live message while outbound is paused or `OUTBOUND_ENABLED` is false. It will not place a callback without `consent_for_callback`. It will not sign an agreement or set a commission amount without a founder approval. It will not move money.
