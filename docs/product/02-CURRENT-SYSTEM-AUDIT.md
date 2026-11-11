# 02 — Current system audit

**Checked:** 3 November 2026, from the working tree at `E:\M sales`.  
**Method:** Read the application source, migrations `0001`–`0006`, tests, and prior notes. Ran the API suite and the voice mock tests. Did not call xAI, Twilio, SMTP, Supabase, or WhatsApp. Did not rebuild the web app today.

`AUDIT-STATUS.md` (2 November 2026) is historical. It predates migrations `0005` and `0006` and records 14 API tests. This file replaces it for the current tree.

## Stack

| Layer | What is in the repo |
| --- | --- |
| Web | Next.js 15, React 19, TypeScript, Tailwind. Command-center pages only. Token stored in `localStorage`. |
| API | FastAPI 0.115, SQLAlchemy 2, Pydantic 2, PyJWT. Version string `4.0.0`. |
| Data | PostgreSQL. SQL migrations in `supabase/migrations`. Two roles: migration/admin and `yes_app`. |
| Voice | Separate Node process aimed at Twilio Media Streams and xAI Realtime. |
| Tests | `apps/api/tests/test_acceptance.py` against local database `yes_sales_test`. Voice mock tests in `apps/voice`. No web test suite. |
| Deploy | `docker-compose.yml` exists. Docker was not run in this review. No verified production deployment. |

## Security model that actually exists

Row-level security is on, and `yes_app` cannot bypass it. Visibility is `yes_app_visible()`: the session role must be `founder`, `operator`, or `agent`. There is no `business_id` and no tenant policy.

That is staff-role isolation inside one workspace. It does not separate customers.

Other facts:

- Local passwords use PBKDF2-SHA256. Login issues an HMAC JWT (`iss=yes-sales-local`) lasting 720 minutes by default.
- Supabase tokens are accepted only when `SUPABASE_JWT_SECRET` is set, and only if the email already exists in `users`. Both Supabase settings default empty.
- There is no MFA.
- Founder-only gates exist for user creation, pause, budget, opt-out clearing, and binding approvals. Operators are not a full second policy layer on every read.
- `user_credentials` is hidden from `yes_app`. Some sensitive writes use the admin connection on purpose, including opt-out persistence. That pattern is safe only while those writes stay narrow.
- Default database passwords, JWT secret, webhook secret, and scheduler token are hardcoded for local development in `apps/api/app/config.py`. The login page shows the seeded founder and operator passwords when the host is `localhost` or `127.0.0.1`.
- Product files are stored on the API disk under `data/uploads`, not in a private bucket.
- `POST /alex/classify` required no session before this review. It calls xAI whenever `XAI_API_KEY` is set. As of this audit it requires a bearer token. See `09-TEST-AND-RELEASE-STATUS.md`.

## Capability ledger

Status words mean what they say. "Implemented" is not "tested", and "tested" here means the local suite or a direct code path inspected on 3 November 2026.

| Capability | Status | Evidence |
| --- | --- | --- |
| Local login and wrong-password rejection | WORKING AND TESTED | API suite, 3 Nov 2026 |
| Founder / operator / agent roles | WORKING AND TESTED | Approval and settings tests. Not a customer permission model. |
| CRM companies, contacts, permissions | WORKING AND TESTED | Create, duplicate rejection, permission flags |
| Supplier and buyer stage gates | WORKING AND TESTED | Illegal jumps rejected |
| Research source, excerpt, extraction guard | WORKING AND TESTED | Values absent from the excerpt are rejected. Live xAI extraction was not called. |
| Bot file import and task replay | WORKING AND TESTED | `VERIFIED` is stored as a claim. Company stays unverified. Same task plus company identity replays. |
| Independent verification of imported facts | PARTIAL | Claim text is kept in `claim_evidence`. It is not fetched from the source URL and not promoted to a research excerpt. |
| Alex draft, classification, approval before send | WORKING AND TESTED | Draft stays unsent. Commercial `POST /messages/send` is refused. Classification without an API key is deterministic and labeled `not_configured`. |
| Opt-out survives a blocked send | WORKING AND TESTED | `persist_opt_out` commits on the admin connection and reads the row back. Suite asserts `opted_out` after the block. |
| Inbound email webhook | WORKING AND TESTED for the signed mock path | Bad signature returns 401. No live mailbox. |
| Outbound email | MOCKED in this environment | `OUTBOUND_ENABLED` defaults false. Mock sends are labeled `provider_mode=mock`. Live SMTP code exists and was not called. |
| Global pause, daily limit, budget ceiling | WORKING AND TESTED | Pause, 429, and budget rejection are in the suite. |
| Task queue, idempotency, retry, dead letter | WORKING AND TESTED | Worker runs only when `POST /tasks/process` is called. It is not a resident process. |
| Approvals for signature, price, commission, payment | WORKING AND TESTED | Database triggers back the agreement and commission rules. Payment execution returns `payment_not_executed` on purpose. |
| Dashboard KPIs and audit events | WORKING AND TESTED | API assertions. Browser walkthrough was not repeated today. |
| Commercial audit runner | IMPLEMENTED | Prior runs exist under `audit/`. Not re-run today. Mocked and skipped cases are defined as not passed. |
| xAI text adapter | IMPLEMENTED BUT UNTESTED live | Unit test uses a fake HTTP client. `llm` mode is `not_configured` when the key is empty. |
| Voice gateway | MOCKED | 3 voice tests passed. They do not place a call. `live_call_verified` is forced false even if credentials exist. |
| WhatsApp | MISSING as a channel | `WhatsAppChannel.deliver` raises not-connected. Send path returns 501 only after earlier blocks. No Cloud API client. |
| Grok bots / MCP | MISSING | Manual import only. No bot credential and no database access for external agents. |
| Website chat widget | MISSING | |
| Subscriber businesses, staff membership, billing | MISSING | |
| MFA, data export, deletion workflow, object storage | MISSING | |
| Calendar booking confirmation | MISSING | |
| Production deployment | BLOCKED | No evidence of a deployed environment in this review. |

## What the seven bots are in this codebase

`AGENT_TOOLS` in `apps/api/app/domain.py` is a fixed allow-list for Atlas, Orion, Bengal, Meridian, Hunter, Alex, Ledger, and Guard. `POST /agents/invoke` rejects any other tool and writes an audit event. These are task names inside one workspace. They are not customer-configurable employees, and they are not the external Grok workspace.

## Historical findings, re-checked

| Earlier concern | Current state on 3 Nov 2026 |
| --- | --- |
| Research identity and import deduplication | Improved, not finished. Unique index is task id + company identity + country (`0006`). No cross-source entity resolution. |
| Opt-out lost on error rollback | Addressed in `persist_opt_out`, with tests. |
| Weak verification of imported evidence | Still true. Imports do not retrieve the URL. |
| Email mocked | Still true in this environment. |
| AI agents not directly integrated | Still true for live model calls. Tool ACL is real. |
| WhatsApp and telephone not proven live | Still true. |
| No subscription system | Still true. |
| No verified production deployment | Still true. |

## Reuse judgment

Keep the application. Do not rewrite it into a multi-tenant SaaS by renaming brokerage tables.

Reusable: API/web split, migration style, role-checked actions, approval register, audit log, idempotent tasks, provider-mode labeling, budget ceiling, opt-out commit pattern, extraction guard, pytest against Postgres.

Not the customer domain: supplier/buyer stages, RFQ matching, commissions, the seven research agents, and `companies` as a stand-in for a subscriber. A company row is a counterparty in the brokerage, not a tenant.
