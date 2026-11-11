# 05 — Target architecture and migration

**Date:** 3 November 2026  
**Status:** Proposed. No schema has been applied for this design.

## Decision

Keep one Next.js app, one FastAPI app, and one Postgres database. Add the customer product beside the brokerage model. Do not split into microservices. Do not convert supplier and buyer tables into tenants.

```text
Owner browser / website widget
        |
        |  session, or a public widget key bound to one business
        v
FastAPI
        |
        +-- brokerage routes (current, founder workspace only)
        +-- business routes (new; every query carries business_id)
        |
        v
PostgreSQL
        yes_app role, row-level security
        brokerage policies stay role-based
        new tables require app.business_id
```

The model API, email, WhatsApp, and calendar sit behind server-side tools. The widget never holds provider secrets.

## Tenant rule

Every new customer table includes `business_id`. The request session sets `app.business_id` from the authenticated membership, not from the client payload. Policies use that setting. Admin-role code may not read a business table unless the function also receives the business id and writes an audit row.

File paths, cache keys, logs, and background jobs include the business id. A job without one does not run against customer data.

The existing `yes_app_visible()` check stays for the brokerage tables. It is the wrong check for customer data, because every staff role can see every brokerage row.

## Modules, in the order they earn their place

| Module | Now | First implementation |
| --- | --- | --- |
| A. Identity and businesses | Design only | `businesses`, `memberships`, roles owner / staff |
| B. AI workforce | Design only | Two role presets. A registry, not a new service per role |
| C. Knowledge | Design only | Services, hours, FAQs, policies. Status: draft or approved. Version retained |
| D. Conversations | Later | Website chat first. Email and WhatsApp are adapters, not new inboxes |
| E. CRM | Thin | Contact and enquiry on the business. Do not reuse brokerage pipeline stages |
| F. Workflows | Thin | Booking request and quotation request with statuses requested, drafted, approved, declined |
| G. Integrations | Existing adapters stay mocked | No new provider until a pilot needs it |
| H. Billing | Not built | Entitlement flags can exist before a payment processor |
| I. Analytics | Not built | Count conversations, requests, handoffs, and model cost |
| J. Security | Extend current audit | Business id on new audit events. Export and deletion before the second paying customer |

## Role contract

A role record can set display name, knowledge scopes, tools, channels, hours, languages, escalation, and a monthly budget. It cannot set its own authority.

Initial tools:

| Role | May | May not |
| --- | --- | --- |
| Receptionist | Read approved knowledge. Create an enquiry. Hand off to a person. | Send outbound marketing. Change prices. Read another business. |
| Booking / quotation | Create a request in `requested` or `drafted`. Attach customer-supplied vehicle details. | Set status `approved`. Invent a price. Write a calendar event. |

Prices shown to a customer are copied from an approved knowledge row. If no row matches, the assistant says it will ask the shop. Slot confirmation waits until a calendar tool returns a free window and a person, or a later explicit rule, accepts it.

## Execution path

Customer message, business id, channel check, role, approved knowledge, tool schema, business rule, execute or escalate, store, audit, meter.

Idempotency keys stay. Retries stay bounded. Prompt text is untrusted input. Tool choice is a server allow-list, the same idea as today's `assert_tool`, with the allow-list stored per role instead of hardcoded to eight brokerage agents.

## Knowledge rules

Each item stores source, business id, status, version, and updated time. A draft cannot override an approved item. Contradictions are shown to the owner, not merged by the model. Retrieval for a business filters `business_id` and `status=approved` in SQL before any prompt is built.

## Migration plan

1. Leave migrations `0001`–`0006` untouched in behavior.
2. Add new tables in a later migration after founder approval. No backfill of brokerage companies into businesses.
3. Ship the new routes behind a feature flag defaulting off.
4. Point the widget at the new routes only.
5. Keep founder login on the current command center.

Rollback is "flag off and stop serving the widget." It does not require dropping brokerage data.

## Security work that belongs with the new tables

- Membership on every customer route.
- MFA for the owner before real customer data is stored. The current login is not enough.
- httpOnly session cookie instead of `localStorage` before the widget and dashboard share a browser with untrusted content.
- Secrets only in the environment of the deployment, with the local defaults refused when a production flag is on.
- Retention and deletion for enquiry photos and transcripts.
- A privacy notice the shop can show. The platform is not "PDPA compliant" because a notice exists.

Malaysia’s Personal Data Protection Act 2010 (Act 709) applies to personal data in commercial transactions. The Department of Personal Data Protection states the seven principles, controller registration, a data protection officer, and breach notification as controller duties. Official texts checked 3 Nov 2026 include the Act reprint PDF hosted by pdp.gov.my and the August 2025 DPO guideline. That guideline says a controller or processor appoints a DPO above 20,000 data subjects, above 10,000 where sensitive personal data including financial information is involved, or where processing is regular and systematic monitoring. Penalty language in the reprint is a fine up to RM1 million, imprisonment up to three years, or both, for contravening the principles. This is a reading of public documents, not a legal opinion. Marketing consent, WhatsApp template rules, and any AI-disclosure duty still need qualified advice before go-live.

## What this architecture deliberately does not include

A second runtime, a vector database as a required service, an agent framework, Kubernetes, or a per-customer Grok subscription. Keyword or structured lookup is the right first retrieval method for a few dozen services and FAQs. Add embeddings only when that lookup fails in evaluation.
