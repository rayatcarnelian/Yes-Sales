# 08 — Decision log

New decisions go at the top. Do not rewrite history.

## 11 November 2026 — The export floor runs as one sales team

- **Decision:** The eight existing agents run as one floor: Atlas manages, Orion, Bengal, Meridian, and Hunter file sources, Guard checks the text, Alex classifies, and Ledger holds the numbers. One play files a source only for a company the founder already opened. It does not create a company, verify one, bind a price, take a payment, or send.
- **Copied:** A sales floor that separates research, compliance, the writer, the deal desk, and the manager. The writer does not send. The deal desk does not close.
- **Rejected:** A ninth agent. A web search that invents suppliers. Turning the production secret guard on by default. Tenant tables. Live email, WhatsApp, or voice.
- **Evidence:** `apps/api/app/services/sales_team.py`, `GET /sales-team`, and `POST /sales-team/run`.
- **Status:** Implemented for the founder's desk. M2 tenancy is still not approved.

## 4 November 2026 — The wedge is an approved job card

- **Decision:** The first thing this workspace does that the compared products do not enforce is a detailing job card. The assistant may record the car and the requested package. It cannot state a price, and it cannot say the bay is booked, unless that fact is already on an owner-approved service sheet or a founder-executed approval. The refusal is in the API and in database triggers. A prompt that says "quote RM800" does not make it true.
- **Copied:**
  - Fresha: a service menu, a requested time, and an owner who still owns the calendar. Checked 3 Nov 2026.
  - Intercom Fin: asking for a person, or not knowing the answer, is a handoff. It is not a successful reply.
  - WATI and respond.io: WhatsApp is the later Malaysian channel, through the official API. This slice has no WhatsApp client.
  - This repo: `bind_price` and `send_outreach` already refuse to proceed without founder approval. Research excerpts already reject a value that is not in the source. The job card reuses that rule.
- **Rejected:**
  - Fresha's marketplace commission and any path that confirms the slot for the owner.
  - Intercom's per-resolution charge. This slice does not charge for a handoff.
  - A WhatsApp Web automation or a BSP.
  - HighLevel sub-accounts, funnels, and rebilling. One shop inside the current workspace. No tenant key.
  - Pushing a detailing shop through the supplier and buyer stages. The shop is a company row so the current desk can open it. The job card does not enter the export pipeline.
  - A ninth agent, a live model call, or a public chat widget in this slice. The reply drafter is deterministic and may repeat only an approved sentence.
- **Evidence:** Migration `0007_job_cards.sql`, `apps/api/app/services/job_cards.py`, and the TEST Detailing Studio acceptance tests. `OUTBOUND_ENABLED` stays false. No live email, WhatsApp, or model call.
- **Status:** Implemented for one shop in the current workspace. M2 tenancy is still not approved.

## 3 November 2026 — Classify requires a session

- **Decision:** `POST /alex/classify` requires the same bearer token as the rest of the API.
- **Evidence:** The handler called `classify_message`, which posts to xAI when `XAI_API_KEY` is set. The route had no `Depends(get_current_user)`. The key is empty in this workspace, so no spend occurred. The suite already called the route with a token.
- **Alternatives:** Leave it open because classification is not a database read. Rejected. An open route becomes a bill the moment a key is configured.
- **Cost:** One route change and one assertion. Full API suite re-run: 16 passed.
- **Risk:** A future caller that used the open route will get 401. No such caller exists in the web app.
- **Status:** Implemented.

## 3 November 2026 — Do not turn the brokerage OS into the SaaS by renaming tables

- **Decision:** Keep the current command center as the founder's internal brokerage tool. Build subscriber data in new `business_id` tables when, and only when, the founder approves M2.
- **Evidence:** `companies` are suppliers and buyers. RLS checks `founder|operator|agent`, not a tenant. Migrations `0001`–`0006` encode that model.
- **Alternatives:** Multi-tenant the existing tables. Rejected for this phase because it risks the working brokerage and forces every deal row to grow a tenant key.
- **Cost:** Some duplication of contact and conversation ideas later. Cheaper than a broken migration.
- **Risk:** Two mental models in one database. Acceptable if the routes are separate.
- **Status:** Recommended. Schema work is not approved.

## 3 November 2026 — Primary strategy is a vertical workflow, integration-first

- **Decision:** First offer is an AI receptionist plus enquiry and booking/quotation requests for one automotive detailing shop. Channels and calendars are integrated, not rebuilt. A general AI workforce platform is a constraint, not the backlog.
- **Evidence:** Current code is a brokerage OS. Urable already sells detailing operations. HighLevel and respond.io already sell broad AI plus inbox. Fresha already prices an AI concierge near $30–$100 per location. Sources and confidence are in `03-COMPETITOR-INTELLIGENCE.md`.
- **Alternatives considered:**
  - Fully custom general SaaS. Rejected now. Too slow, and the incumbents are real.
  - Integration-only on HighLevel. Rejected as the company, because there is then little to own. Remains a fallback if the founder chooses to resell rather than build.
  - Agency/reseller first. Deferred until one template has been reused.
  - Managed services forever. Allowed only as the first pilot's onboarding method.
- **Cost:** Slower platform story. Faster path to one invoice.
- **Risk:** The first shops may only want WhatsApp, or may already be fine with Urable. Those are kill criteria, not reasons to widen the build.
- **Status:** Recommended. Founder has not yet signed the M2 gate.

## 3 November 2026 — Competitor research stops at this baseline

- **Decision:** No standing research cycle. Refresh only when it changes price, channel, or build-versus-buy.
- **Evidence:** The 3 Nov 2026 pass is enough to reject a general-platform build.
- **Status:** In force.

## 3 November 2026 — Pricing stays a hypothesis

- **Decision:** Do not publish RM199 / RM499 / RM999 as prices. Do not add a payment processor in M1–M5.
- **Evidence:** No willingness-to-pay interviews and no measured model or message cost for this product.
- **Status:** In force.

## Earlier decisions already encoded in the repo

These were made before this review. They stay.

- Payment execution does not move money (`payment_not_executed`).
- A bot import cannot mark a company verified or authorize outreach.
- Outbound commercial email waits for a founder `send_outreach` approval.
- Mock providers must be labeled mock.
- Live voice is not claimed unless a real call is completed. `live_call_verified` remains false.
