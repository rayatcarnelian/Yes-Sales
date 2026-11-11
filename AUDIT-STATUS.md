# YES SALES audit status

Checked 2 Nov 2026 from the working tree. This file records what the code and the commands below actually did. Untested live calls are not described as working.

## 1. Actual implemented features

- Next.js command center: login, dashboard, CRM, company profile, supplier and buyer pipelines, research, deals, inbox, approvals, agents, commercial audit.
- FastAPI backend with local HMAC login, row-level security, and PostgreSQL migrations `0001` through `0004`.
- Company, contact, and permission records. Duplicate name-plus-country and duplicate website domain are rejected.
- Research source storage, excerpt identity checks, and rejection of an older retrieval for the same URL.
- CSV and JSON import of Grok Bot research rows, with task-ID idempotency.
- Buyer requirements, supplier offers, RFQs, explainable matches, opportunities, agreements, and commission records.
- Founder approval register for signature, price, commission, payment, and outbound send. Operators cannot decide or execute those actions.
- Alex email drafts, classification, follow-up tasks, and human handoff. Commercial send stays on the approval register.
- Opt-out, global outbound pause, per-contact rate limit, and a provider budget ceiling.
- Audit event log and a 15-case commercial audit runner.
- Node voice gateway shaped for Twilio Media Streams and xAI Realtime. It stays closed unless the voice credentials are set.

## 2. Working features

These passed the API suite on this machine, or the web build included the page:

- Local login and rejection of a wrong password.
- Supplier and buyer create, list, and one-step pipeline moves.
- Manual research import, mismatched identity rejection, and superseded-source rejection.
- Bot file import: an accepted TEST row is stored as `evidence_recorded` even when the file says `VERIFIED`. Quarantined and superseded rows do not create companies. Re-posting the same task ID does not create a second row.
- Match, RFQ, quotation version, and opportunity stage `quoting` for a TEST deal.
- Founder approval that signs a TEST agreement and binds a TEST commission. Payment execution returns `payment_not_executed`.
- Alex draft creation that stays unsent and opens a `send_outreach` approval.
- Dashboard KPI query, audit events, task retry, and budget rejection.
- Web production build of the 12 routes listed in the test results below.

The voice tests pass for the mock session only. They do not place a call.

## 3. Mocked functionality

Observed from code and `GET /integrations` on this machine while the integration keys are empty:

- Email delivery is `mock`. `OUTBOUND_ENABLED` is false.
- Voice is `mock`. `live_call_verified` is false.
- Research search returns no companies and does not invent any.
- Message classification without `XAI_API_KEY` is a local rule matcher labeled `not_configured`.
- WhatsApp and Grok Bot are `not_configured`. There is no Grok Bot client.

The commercial audit records inbound email as `mocked` and the phone case as `skipped`. Those two are not passes.

## 4. Missing functionality

- No live mailbox send has been proven.
- No live xAI request has been proven. The adapter is covered with a fake HTTP client.
- No Twilio call has been completed.
- Supabase Auth is not connected. Both Supabase settings are empty.
- Direct Grok Bot or MCP synchronization is not active.
- The product does not calculate landed cost and does not execute a payment. Both are intentional.

## 5. Build and test results

Run from `E:\M sales` on 2 Nov 2026:

| Command | Result |
|---|---|
| `.venv\Scripts\python -m pytest apps\api\tests -q` | 14 passed, 1 Starlette deprecation warning, 22.23s |
| `.venv\Scripts\python -m ruff check apps\api\app apps\api\tests` | All checks passed |
| `npm test` in `apps\voice` | 3 passed |
| `npm run typecheck` in `apps\web` | Exit 0 |
| `npm run build` in `apps\web` | Exit 0, Next.js 15.5.28, 12 routes |

The web app has no separate ESLint script. `next build` reported “Linting and checking validity of types” and finished successfully. Mypy was not run for this package.

## 6. Local run instructions

PostgreSQL 16 must already be running. Docker is not required for the commands below. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r apps\api\requirements.txt
$env:PYTHONPATH = "apps\api"
.\.venv\Scripts\python scripts\seed_demo.py
.\.venv\Scripts\python -m uvicorn app.main:app --app-dir apps\api --port 8000
```

In another terminal:

```powershell
cd apps\web
npm install
npm run dev
```

Open `http://localhost:3000/login`. Voice, optional:

```powershell
cd apps\voice
npm install
npm test
npm start
```

Copy `.env.example` to `.env` before filling any real value. This review package’s example file has empty secret fields.

## 7. Required environment variables by name only

`DATABASE_URL`, `ADMIN_DATABASE_URL`, `APP_DB_PASSWORD`, `JWT_SECRET`, `JWT_TTL_MINUTES`, `WEBHOOK_SECRET`, `SCHEDULER_TOKEN`, `VOICE_GATEWAY_TOKEN`, `OUTBOUND_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, `XAI_API_KEY`, `XAI_MODEL`, `XAI_REALTIME_URL`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `PUBLIC_VOICE_HOST`, `SUPABASE_URL`, `SUPABASE_JWT_SECRET`, `DEV_FOUNDER_EMAIL`, `DEV_FOUNDER_PASSWORD`, `DEV_OPERATOR_EMAIL`, `DEV_OPERATOR_PASSWORD`, `CORS_ORIGINS`, `NEXT_PUBLIC_API_URL`, `API_INTERNAL_URL`, `AUTO_MIGRATE`, `UPLOAD_DIR`.

No values are included here. Live email needs `OUTBOUND_ENABLED` plus the SMTP names. Live voice needs `XAI_API_KEY`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and `PUBLIC_VOICE_HOST` together.

## 8. Known issues

- No `.env` file is present. Integrations stay mock or not configured.
- Local database passwords and the staging JWT default are still hardcoded in `apps\api\app\config.py`, `scripts\seed_demo.py`, `scripts\run_commercial_audit.py`, and `docker-compose.yml`. The packaged `.env.example` has been blanked. Those source defaults are local development values, not a filled vendor key, and they should be rotated before any shared deployment.
- The login page shows the local founder and operator passwords when the host is localhost or 127.0.0.1.
- A bot import does not create a contact and does not authorize outreach.
- Human intervention time in the commercial audit is unmeasured because the signature approval was left pending. Comparable Alex-versus-human pairs are 0.
- The voice process is separate and was not running during this package build.

## 9. Current Grok Bot integration status

Manual import only. `POST /research/bot-imports` accepts JSON or CSV from a signed-in user. It is tested. A `VERIFIED` label is stored as a claim and the company remains `evidence_recorded` until a person verifies it.

There is no authenticated bot token, no MCP tool, and no unattended sync. Grok Bot cannot open the database. xAI is called only when `XAI_API_KEY` is set, and that key is empty here.
