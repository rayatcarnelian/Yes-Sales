# 06 — Implementation roadmap

**Date:** 3 November 2026  
**Rule:** A milestone starts when the previous exit condition is true, not when the list reaches it. M2 and later are not approved to build.

Estimates are engineering time for the founder plus this codebase, not calendar promises. Uncertainty is high wherever a vendor or a pilot is involved.

## M0 — Audit and decisions

**State:** Done on 3 Nov 2026, subject to the founder accepting or rejecting the strategy.

**Exit:** These ten documents exist. Competitor baseline is dated. No further competitive research without a decision that needs it.

## M1 — Reliable core of the current app

**State:** In progress. One fix landed during M0: `POST /alex/classify` now requires a bearer token, because that route can spend an xAI key.

**Remaining, and the only implementation authorized by this review:**

| Task | Depends on | Acceptance | Effort | Uncertainty |
| --- | --- | --- | --- | --- |
| 1. Route census test | None | A test fails if a new route is anonymous. Allowed exceptions: `/health`, `/auth/login`, signed inbound email, voice gateway token, scheduler token. `/alex/classify` without a bearer token stays 401. | 0.5–1 day | Low |
| 2. Production secret guard | Founder agrees the flag name | With the flag off, the current suite still passes. With the flag on, the process refuses the default JWT, webhook, scheduler, and database passwords from `config.py`. Tests leave the flag off. | 0.5 day | Low |
| 3. Founder decision on the data split | Documents 04 and 05 | Decision log records yes or no to "new `business_id` tables, brokerage tables unchanged." No migration is written before yes. | Founder decision | None for code |

**Explicitly not in M1:** live SMTP, Twilio, WhatsApp, Supabase Auth, deleting the login hint before the secret guard exists, rewriting the UI.

**Exit:** Census test green, secret guard available and off by default, founder decision recorded.

## M2 — Tenant foundation

**Depends on:** M1 task 3 = yes.  
**Modules:** identity tables, session business id, RLS on new tables only.  
**Database:** additive migration. No change to brokerage primary keys.  
**Tests:** two businesses, cross-read and cross-write denied for API and for a tool call.  
**Security:** membership required. No provider keys.  
**Effort:** 1–2 weeks. Uncertainty medium.  
**Exit:** Unauthorized cross-business access fails in an automated test.

## M3 — Configurable runtime for two roles

**Depends on:** M2.  
**Modules:** role registry, approved knowledge, tool allow-list, handoff, usage row.  
**Tests:** unknown price not answered with a number; closed-day rule; business A text absent from business B; draft knowledge not retrieved; tool outside the role denied.  
**Cost:** evaluation uses fixtures. A live model run is a separate, budgeted check, not the default test.  
**Effort:** 2–3 weeks. Uncertainty high, mostly on prompt and retrieval behavior.  
**Exit:** Both fixture businesses pass the evaluation set with the model stubbed, and one budgeted live run is recorded if a key is provided.

## M4 — Enquiry to owner action

**Depends on:** M3.  
**Scope:** website widget, enquiry fields, booking/quote request, owner queue, notification that does not pretend to be live email unless SMTP is actually configured.  
**Tests:** one scripted customer conversation creates one request and one audit trail. Duplicate widget posts do not create duplicate requests.  
**Effort:** 2–3 weeks. Uncertainty medium.  
**Exit:** A person can play the customer and the owner on two test businesses and the data does not cross.

## M5 — Channels beyond the widget

**Depends on:** a pilot saying website chat is insufficient, plus founder approval of the vendor bill.  
**Order:** authorized email, then official WhatsApp, then calendar read, then voice.  
**Exit:** provider evidence of a test message, a failed webhook, an opt-out, and a human takeover. Not a mock label.

## M6 — Paid pilot

**Depends on:** M4 in real use, a legal billing path, and a price the founder is willing to say out loud.  
**Exit:** one shop uses the workflow and pays. Cost per conversation is measured. Support hours are written down.

## M7 — Second and third shop

**Depends on:** M6 evidence that the template, not the founder, did the work.  
**Exit:** the next shop is configured without a schema change.

## External requirements before M5 or M6

| Item | Needed for | Not needed yet |
| --- | --- | --- |
| Model API key and a spend cap | Any live answer | Fixture tests |
| SMTP or a transactional email account | Owner notification that really sends | On-screen queue |
| WhatsApp Business account in the customer's name | WhatsApp | Website chat |
| Google Calendar OAuth | Slot checks | Request capture |
| Payment entity and processor | Charging a subscriber | Pilot design |
| Counsel on PDPA notice, processor terms, and marketing consent | First real customer data | Local synthetic tests |

## Credit and API cost during the build

Default tests stay on Postgres and stubs. A live model call is opt-in, capped, and recorded in `10-CREDIT-AND-COST-CONTROLS.md`. No recurring vendor is added in M1–M4.
