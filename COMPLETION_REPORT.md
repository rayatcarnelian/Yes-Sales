# YES SALES completion report

Local operating platform for one organization. Live vendor calls were not made. Provider modes below come from `GET /integrations` on the running API.

## Commands

| Check | Result |
| --- | --- |
| `pytest -q` in `apps/api` | 11 passed, 1 Starlette deprecation warning, 8.28s |
| `ruff check app tests ../../scripts` | All checks passed |
| `mypy app` | Success: no issues found in 22 source files |
| `node --test` in `apps/voice` | 2 passed (mock session labeled; live carrier stays not configured) |
| `npx tsc --noEmit` in `apps/web` | Exit 0 |
| `npm run build` in `apps/web` | Succeeded earlier in this build (Next.js 15.5.28, lint and types clean, 11 routes) |
| `scripts/simulate_transaction.py` against `http://127.0.0.1:8000` | Completed: supplier `936a566f-785e-4f1d-a328-492a92eccf7c`, buyer `038e5ce5-5342-41e4-9d30-92e288bfd371`, match score `1.0000`, confidence cap `0.7000` (documentation missing), agreement result `agreement_signed`, verified suppliers `1`, pipeline value `18000.00`. Response had no `landed_cost`. |
| Docker Compose | Not run. Docker is not installed on this machine. Postgres 16.10 portable binaries serve `127.0.0.1:5432`. |

## Browser

The command center at `http://localhost:3000` was signed in as the seeded founder and showed database KPIs: 1 verified supplier, 1 qualified buyer, 1 RFQ, 1 quotation, 1 match, pipeline value `18000.00`, outbound pause false.

CRM created **TEST UI Mill** (`5d907cf0-6686-46c8-8a93-2015c880698c`, country BD, role supplier). The profile saved contact Desk at `desk-ui@example.com` as not eligible. Advancing the supplier moved discover to research (`POST /transitions` 200). The next step, verify, returned 422 and the page showed “A research source is required before verification.”

Deals loaded with `GET /opportunities` 200. Approvals listed `sign_agreement` as approved for the TEST transaction. Agent control showed pause false and budget `0.000000 / 25.00` USD. Pause was turned on in the UI (`Paused: true`) and then set back to false with `POST /settings/outbound-pause`, which returned `outbound_paused: false`.

`GET /integrations`: email `mock`, voice `mock`, llm `not_configured`, whatsapp `not_configured`, grok_bot `not_configured`, database `live`, `outbound_enabled` false.

## Acceptance coverage

Pytest against `yes_sales_test` covers supplier and buyer qualification with illegal jumps rejected, research URL and retrieval time with extraction rejected when the excerpt does not support the field, duplicate company and contact rejection, outreach blocked without permission, mock email plus inbound opt-out and a blocked follow-up, webhook signature failure, rate limit, global pause, match reasons and missing data, quotation versions, voice mock `provider_mode=mock`, founder approval versus operator denial, unsigned binding denial, idempotent task apply, dead-letter restart, budget ceiling, and KPI counts equal to SQL. Consequential actions write `audit_events`.

## Not done

Cloud deploy was not executed. No Supabase, xAI, Twilio, or SMTP credentials were present. See `LIMITATIONS.md`.
