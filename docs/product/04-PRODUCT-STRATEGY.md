# 04 — Product strategy

**Date:** 3 November 2026  
**Decision owner:** Founder. This file records the recommendation. It is not a claim that a customer has agreed.

## Decision

Primary strategy is a **vertical workflow**, delivered in an **integration-first** way, with the **first shop onboarded manually**.

YES SALES should not try to become a general AI operating system, and it should not try to outbuild HighLevel. The brokerage OS stays the founder's internal tool. The sellable product is a separate, narrower workflow on the same codebase.

## Answers to the ten strategy questions

### 1. Vertical, general platform, or integration-first?

Vertical for the customer promise. Integration-first for anything that is already a commodity: model APIs, WhatsApp, calendars, and later subscription payments. A general platform is the long-term constraint to leave room for, not the thing to build now.

Sequence: prove one detailing workflow by doing the setup ourselves (services strategy), then sell the same configuration to a second and third shop (vertical SaaS). Agency resale waits until that template no longer needs custom engineering.

### 2. Smallest commercially valuable MVP

A shop-branded website chat, plus an owner screen, that can:

1. Answer from approved services, hours, and prices only.
2. Ask for vehicle, service, preferred time, and optional photos.
3. Store a booking or quotation **request**. It does not confirm the slot.
4. Notify the owner and allow a person to take over.
5. Keep the transcript on that business's record.

If the first real shop will not use website chat, the MVP is not "add every channel." The MVP stops, and the channel assumption is recorded as failed before WhatsApp is purchased.

### 3. What we build

- Subscriber business, staff membership, and permission checks.
- Role configuration for two roles at first: Receptionist and Booking/Quotation request.
- Approved knowledge items with version and status.
- Enquiry and request records.
- A small website widget and an owner review queue.
- Usage limits and an evaluation set.

### 4. What we buy or integrate

- A model API. xAI is already sketched in the codebase. It is not mandatory for every customer, and it is the wrong default if a smaller model answers FAQs reliably.
- Google Calendar read-only availability, only after request capture works.
- Official WhatsApp, only after a pilot requires it.
- A Malaysian or international payment processor, only after the legal billing entity is ready.

### 5. What we keep

The current FastAPI and Next.js application, Postgres, approvals, audit log, task idempotency, opt-out persistence, tool allow-lists, and the habit of labeling mock providers. The brokerage screens stay available to the founder. They are not the customer navigation.

### 6. What is risky in the current architecture

- One workspace for every row.
- `companies` means a supplier or buyer, not a subscriber. Reusing it as the tenant will mix two businesses.
- Admin-database writes bypass row-level security. Fine for a narrow opt-out. Dangerous as a general habit.
- JWT in `localStorage`, no MFA, and default secrets in source.
- A worker that only runs when something calls `/tasks/process`.
- Voice and WhatsApp code that can be mistaken for a live channel.

### 7. Why a customer would pay monthly

Not because there are ten AI employees. Because missed WhatsApp and web enquiries turn into empty bays, and the owner currently answers the same coating and price questions at night.

A shop pays if, in a month, the assistant captures real requests the owner would have missed or handled after hours, quotes only approved prices, and does not create a mess the owner has to undo. Willingness to pay is unmeasured. RM199 / RM499 / RM999 per month are hypotheses from the brief, not prices.

### 8. Differentiation that can survive

HighLevel, Fresha, respond.io, and Urable will keep beating us at breadth. A plausible narrow advantage:

- Setup done for a Malaysian shop, in English and Malay, on a website the shop owns.
- The assistant is not allowed to invent a price or confirm a bay.
- The owner sees the request and the cost of the assistant in one place.
- The same detailing template is reused for the next shop without a new software project.

That advantage dies if onboarding stays a custom build, or if we add modules instead of finishing one workflow.

### 9. Assumptions a real shop must confirm

| Assumption | How it fails |
| --- | --- |
| The owner will let an assistant answer customers | They want the tool only as a personal copilot |
| Website chat is a real enquiry source | Customers only message WhatsApp or Instagram |
| Owners will approve a service list and prices | Prices are negotiated every time and cannot be written down |
| A request, rather than an instant booking, is acceptable | They already live in a calendar tool and will not look at a second queue |
| They will pay after the founder's setup help ends | They valued the founder, not the software |
| Malay and English cover the first shops | A third language shows up in week one |
| Operating cost stays inside the subscription | Photo-heavy chats or a large model blow the margin |

None of these are validated. Outreach names are not validation.

### 10. Three greatest risks

1. **Building the platform before a shop uses the workflow.** The repository can grow while revenue stays zero.
2. **Putting a second business on a database that cannot isolate tenants.** One leak ends the company.
3. **Unit economics against tools that already cost $20–$110 a month.** A frontier model, a WhatsApp BSP, and founder support can consume a RM199 subscription.

## What we will not do on the back of this strategy

- Implement all ten agent roles.
- Animate an office.
- Turn on live outbound email, voice, or WhatsApp without a separate approval.
- Quote a customer a subscription price until one pilot has a measured cost and a stated willingness to pay.
- Treat this document as permission to start the multi-tenant migration. That migration needs an explicit founder yes.
