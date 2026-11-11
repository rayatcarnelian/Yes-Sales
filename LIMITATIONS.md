# Limitations

This is an MVP for a 48-hour build, not a commercially proven brokerage platform.

- Docker was not available on the development machine. `docker-compose.yml` and the Dockerfiles are present and were not executed here. Local tests use a portable PostgreSQL 16 cluster.
- No Supabase project, xAI key, Twilio account, or SMTP account was configured. Those paths are implemented and covered with mocks or negative tests. They have not been called against live vendors in this workspace.
- Grok Bot is not integrated. There is no verified worker API, and a consumer Grok login is not used as one.
- WhatsApp Business is an adapter that returns "not connected". It is not a live channel.
- The research job uses a mock provider that returns an empty company list. It does not crawl the web and does not ask a model to invent suppliers or buyers. Company facts enter through a recorded source excerpt. xAI extraction is coded against `POST /v1/responses` with a JSON schema and is rejected unless every returned value appears in that excerpt. That live call was not made here.
- Email mock delivery writes a message row with `provider_mode=mock`. It does not leave the machine. Live SMTP is attempted only when `OUTBOUND_ENABLED=true` and the SMTP settings are complete.
- Voice mock sessions do not contact a carrier and are stored as `provider_mode=mock`. The Node bridge forwards μ-law audio only when Twilio and xAI credentials exist. That bridge was not opened against either vendor here. `live_call_verified` stays false. Credentials alone do not make calling live.
- Alex drafts are not delivered until a founder executes `send_outreach`. Classification without `XAI_API_KEY` is the deterministic matcher and is labeled `not_configured`, not live.
- There is no mass-calling endpoint.
- Payment execution always returns `payment_not_executed`. Banking changes and legal declarations are recorded as approval decisions, not sent to a bank or a registry.
- Matching does not estimate freight, duty, or landed cost.
- The queue worker runs when `POST /tasks/process` is called. It is not a separate always-on process. n8n can call `POST /tasks/external` on a schedule.
- Row-level security protects the `yes_app` role. The migration role bypasses it and must stay on the server. Supabase hosting still needs a human to apply the SQL and set the restricted role URL.
- Local passwords are seeded for development. Rotate them before anyone else can reach the API.
- Product documents are stored on the API disk, not in a private object bucket.
- One organization. No customer-facing tenant isolation beyond founder, operator, and agent roles.
- The web UI is an operating console. It does not replace the API tests.
