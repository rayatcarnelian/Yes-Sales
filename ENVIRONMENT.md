# Environment

Copy `.env.example` to `.env`. Leave an integration blank until that account exists. The dashboard reports each provider as `live`, `mock`, or `not_configured`.

## Database

| Variable | Purpose |
| --- | --- |
| `ADMIN_DATABASE_URL` | Migration role. Local Docker user `yes`. Bypasses RLS. Server only. |
| `DATABASE_URL` | `yes_app`, subject to RLS. |
| `APP_DB_PASSWORD` | Password assigned to `yes_app` after migration. |

Docker Compose publishes Postgres on `127.0.0.1:5432` with user `yes` / password `yes` and database `yes_sales`. Change these before any shared deployment.

The same SQL file runs in the Supabase SQL editor. Point `ADMIN_DATABASE_URL` at a direct Postgres connection that can create roles, and `DATABASE_URL` at `yes_app`. Do not put the Supabase secret or service-role key in the browser. The web app talks only to this API.

## Auth

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | Local session signing secret. |
| `JWT_TTL_MINUTES` | Local token lifetime. |
| `SUPABASE_URL` | Optional. Documented for the project; the API does not call the Supabase client SDK. |
| `SUPABASE_JWT_SECRET` | When set, bearer tokens signed by Supabase Auth are accepted if the email already exists in `users`. |
| `DEV_FOUNDER_EMAIL` / `DEV_FOUNDER_PASSWORD` | Used by `scripts/seed_demo.py` only. |
| `DEV_OPERATOR_EMAIL` / `DEV_OPERATOR_PASSWORD` | Operator seed. |

## Integrations

| Variable | Live behavior |
| --- | --- |
| `OUTBOUND_ENABLED` | Must be `true` before any SMTP send. `false` keeps email on the explicit mock path. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Live email. If outbound is enabled and SMTP is incomplete, the API refuses the send instead of pretending it was delivered. |
| `WEBHOOK_SECRET` | HMAC-SHA256 hex signature for `POST /webhooks/email/inbound` in header `X-Yes-Signature`. |
| `XAI_API_KEY` | Enables the Responses API structured-output extractor. Research still discards any value that is not in the stored excerpt. |
| `XAI_MODEL` | Default `grok-4.7`. |
| `XAI_REALTIME_URL` | Default `wss://api.x.ai/v1/realtime`. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `PUBLIC_VOICE_HOST` | All four are required before the voice gateway returns TwiML. |
| `VOICE_GATEWAY_TOKEN` | `X-Voice-Token` for `POST /internal/calls`. |
| `SCHEDULER_TOKEN` | `X-Scheduler-Token` for `POST /tasks/external`. |

Grok Bot has no verified worker API in this build. A consumer Grok subscription is not treated as API access. WhatsApp has an adapter port and no driver.

## Web

`NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000`. It is not a secret. Do not put provider keys in `NEXT_PUBLIC_*` variables.

`CORS_ORIGINS` is a comma-separated list of web origins allowed to call the API.

`AUTO_MIGRATE=true` applies `supabase/migrations/0001_init.sql` on API startup when that version is not recorded.

`UPLOAD_DIR` stores product documents under `apps/api/data/uploads`. Files are renamed to a UUID. PDF, PNG, JPEG, and plain text up to 5 MB are accepted.
