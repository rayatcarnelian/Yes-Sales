# Architecture

YES SALES is one brokerage workspace, not a multi-tenant customer product. Founder and operator users share the operating data. Agents are task types with fixed tool permissions.

```text
Next.js command center
        |
        |  session token
        v
FastAPI  ---- PostgreSQL (RLS via yes_app)
   |  \
   |   \-- durable tasks table
   |
   +-- email adapter (SMTP live, otherwise explicit mock)
   +-- xAI Responses API (only when XAI_API_KEY is set)
   +-- voice gateway token
              |
              v
        Node voice process
           |        \
           |         \-- wss://api.x.ai/v1/realtime
           \-- Twilio Media Streams, only when configured
```

## Commercial flow

Research does not create companies by itself. A person or a later approved provider records a source URL, retrieval time, and excerpt. Extraction may only keep values that appear in that excerpt.

Supplier stages: discover, research, verify, contact_eligible, introduction, response, qualification, catalog, quotation, agreement_review, active_supplier.

Buyer stages: discover, research, verify, contact_eligible, introduction, response, requirements, qualification, match, rfq, deal.

Only the next stage is accepted. Verification requires a stored source. Contact eligibility requires an allowed contact that has not opted out.

Matching compares stored requirement and quotation fields. The result lists matches, conflicts, missing fields, and a confidence cap. It never calculates a landed cost.

Signing an agreement or binding a commission changes those rows only after a founder approval row exists. Database triggers reject a signed agreement or priced commission that lacks an approved approval. Payment execution returns `payment_not_executed`.

## Agents

| Agent | Job |
| --- | --- |
| Atlas | Enqueues tasks and reads KPIs |
| Orion | Market research task |
| Bengal | Bangladesh research task |
| Meridian | Malaysia research task |
| Hunter | Buyer research task |
| Alex | Email classification, unsent drafts, callback request |
| Ledger | Quotation and commission draft |
| Guard | Rejects extracted values that are not in the source text |

Tool calls go through `POST /agents/invoke`. A tool that is not on the agent's list is rejected and audited. No agent can sign, pay, or change banking.

## Data and security

The migration in `supabase/migrations/0001_init.sql` creates the tables, status checks, uniqueness rules, foreign keys, indexes, update timestamps, agreement and commission triggers, and row-level security.

The API uses two database roles:

- The admin URL applies migrations, checks passwords, and writes denial audits that must survive a rolled-back request. Password hashes live in `user_credentials`, which the application role cannot read.
- `yes_app` serves authenticated requests. It has no superuser or bypass-RLS rights. Each transaction sets `app.role` and `app.user_id`. Policies allow only `founder`, `operator`, and `agent`.

Local login issues an HMAC JWT with issuer `yes-sales-local`. If `SUPABASE_JWT_SECRET` is set, Supabase access tokens are also accepted, and the email must already exist in `users`.

Webhook and scheduler routes check shared HMAC tokens. The voice gateway uses its own token. Provider keys stay in server environment variables.

## Orchestration

`tasks` is the queue: idempotency key, attempts, deadline, next run time, and dead status. `POST /tasks/process` runs due work. Failures use exponential backoff. A dead task can be restarted without replaying a successful idempotency key. `POST /tasks/external` is the hook for n8n or any other scheduler.

Global pause is a row in `operating_settings`. Alex and outbound call authorization read it before sending. Live provider charges are refused when they would pass the budget ceiling. Mock sends record zero cost and are labeled `mock`.

## Alex

Alex reads stored company, contact, permission, requirement, and message rows. Offer prices are left out of that context. Classification is deterministic unless `XAI_API_KEY` is set, in which case a structured xAI response may label the message and a failure falls back to the same rules.

`POST /alex/drafts` writes an outbound message with status `draft` and a pending `send_outreach` approval. Executing that approval is the only path that sends the draft. Commercial text on `POST /messages/send` is refused. A scheduled follow-up creates another draft when it becomes due; it does not send by itself. Opt-out, a missing permission, the daily limit, and the global pause block release. Mock delivery stays `provider_mode=mock`.

A callback or human-handoff classification marks the conversation `handoff` and enqueues `callback.request`. That task notifies a person. It does not dial.

## Commercial audit

`python scripts/run_commercial_audit.py` creates fictional TEST records in `yes_sales_staging` and writes `audit/commercial-audit.json`. Each case stores its status, execution time, evidence, and, unless it passed, a reason. `mocked` and `skipped` are not passed. The audit page reads that record. When the API is connected to a different database, the page says the figures are from the staging run.

## Voice

`apps/voice` follows the xAI phone example: Twilio `<Connect><Stream>` to `/media`, then `session.update` with voice `eve` and μ-law (`audio/pcmu`) both ways to `wss://api.x.ai/v1/realtime?model=grok-voice-latest`. The bridge forwards base64 media without transcoding and closes both sockets on stop.

Without Twilio and xAI credentials, `POST /twiml` returns 503 and `POST /sessions/mock` returns `provider_mode: mock` with `live_call_verified: false`. If credentials exist, the dashboard says `configured_unverified` until a real test call is completed. This build has not completed one. Outbound callbacks require stored consent, an open budget ceiling, and pause off. The API still records `placed: false` and does not dial.
