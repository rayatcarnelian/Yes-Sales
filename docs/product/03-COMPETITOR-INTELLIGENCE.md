# 03 — Competitor intelligence baseline

**Baseline date:** 3 November 2026  
**Scope:** First use case only — a small automotive detailing or similar service shop that needs enquiries answered and booking or quote requests captured.  
**Method:** Web search of official pricing and help pages. No accounts were created and no products were clicked through as a customer.  
**Next review:** Do not repeat this research on a timer. Open it again only when a pricing, channel, or build-versus-integrate decision is about to be made.

Figures below are vendor statements unless noted. They were not independently tested. Fresha and HighLevel prices are shown in the currency on the page retrieved (USD). Malaysian list prices were not verified. No exchange rate was applied.

## Who actually threatens the first sale

| Rank for this use case | Product | Why it matters |
| --- | --- | --- |
| 1 | Urable | Published as software for detailing, coating, tint, and wrap shops. Booking, deposits, CRM, invoices. |
| 2 | Fresha AI Concierge | Closest packaged "answer every message" add-on, at a low location price. Beauty-market product, not detailing. |
| 3 | HighLevel | Mature agency CRM plus paid AI employees. Dangerous if we try to become a general platform. Too heavy for one shop that only wants the phone answered. |
| 4 | respond.io | Real WhatsApp and shared-inbox product. Relevant the moment the pilot says the channel is WhatsApp. |
| 5 | Bookedin | Low-cost detailing scheduling. Sets the price floor for "just put booking on the website." |
| 6 | HubSpot Breeze and Intercom Fin | Show how outcome pricing and handoff are sold. Poor fit and poor price for a one-location detailing shop. |

## Urable

- **Checked:** 3 Nov 2026. https://urable.com/pricing/ and https://urable.com/
- **Confidence:** Medium. Search extract of the vendor pricing page, not a full browser render.
- **Target:** Detailing, paint-protection, wrap, tint, and ceramic shops, mobile or in-shop.
- **Core use:** Scheduling, CRM, invoicing, deposits, reminders.
- **AI:** Not listed in the pricing extract. Absence is not proof they lack it.
- **Channels:** Text and email invoicing and reminders are listed. WhatsApp was not confirmed.
- **Booking:** Online booking is described on the higher tiers. The $70 tier text does not include it. The page says booking can be configured as a request or a direct booking.
- **CRM / knowledge / handoff:** CRM and job assignment are the product. No knowledge-base or human-AI handoff was described in the extract.
- **Automation:** Reminder messaging, follow-up on the higher tier, deposits.
- **Price, vendor page:** $70, $110, and $183 per month, or $840, $1,320, and $2,200 per year. No contract claimed. Stripe, Square, and on the higher tier QuickBooks.
- **Onboarding:** Unknown. Not tested.
- **Against YES SALES:** They already speak the shop's workflow, including deposits and calendar. A generic AI receptionist does not replace that.
- **Opening:** Their public pricing extract does not show a grounded enquiry assistant that refuses to invent prices. That is a hypothesis, not a measured gap.

## Fresha

- **Checked:** 3 Nov 2026. https://www.fresha.com/pricing and https://www.fresha.com/en-GB/pricing
- **Confidence:** Medium. Two search extracts of the official pricing page agree. Local Malaysian currency was not opened.
- **Target:** Salons, spas, and similar appointment businesses. Not a detailing product.
- **AI:** Optional AI Concierge. Vendor wording: answer calls and messages. Messaging-only $29.95 per location per month. Calls and messaging $99.95 per location per month, 200 minutes included, then $0.60 per minute. "Unlimited messaging" is their claim and was not tested.
- **Booking:** Native online booking, staff calendars, deposits, no-show fees.
- **Channels:** Email notifications. SMS and WhatsApp notifications: 100 free per month, then about $0.02 per SMS or $0.04–$0.11 per WhatsApp message, as stated on the pricing extract.
- **Subscription:** Independent $19.95 per month for one bookable team member. Team $14.95 per bookable team member per month. Marketplace new-client commission 20% with a $6 minimum, separate from software. Card rates published (online 2.79% + $0.20 in the extract).
- **Against YES SALES:** If a shop only needs a bookable calendar plus a cheap message bot, Fresha's add-on is already priced near one cheap month of our draft Starter. Detailing shops are outside Fresha's published marketplace, which is the practical opening.
- **Decision use:** Do not build a salon marketplace or a payment terminal. Do treat $30–$100 per location as the price band a service owner already sees for an AI concierge.

## HighLevel

- **Checked:** 3 Nov 2026.
  - https://help.gohighlevel.com/support/solutions/articles/155000001156-highlevel-pricing-guide
  - https://help.gohighlevel.com/support/solutions/articles/155000006652-ai-product-pricing
  - https://www.gohighlevel.com/pricing
  - Starter-plan article modified 2 Nov 2026: https://help.gohighlevel.com/support/solutions/articles/155000009501-how-to-upgrade-a-sub-account-to-the-20-ai-employee-starter-plan
- **Confidence:** Medium-high for plan names and monthly numbers. Fair-use limits are vendor policy, not a measured allowance.
- **Target:** Agencies and the local businesses those agencies run as sub-accounts.
- **Platform price:** Agency plans cited as $97, $297, and $497 per month. The public pricing extract also shows an annual figure of $970, consistent with the $97 tier.
- **AI Employee, per sub-account, per month:** Starter $20, only on the $497 agency plan, and it does not include Conversation AI or Voice AI. Growth $50 with 1,000 Conversation AI responses and 100 Voice AI minutes. Unlimited $97, fair use. Pay-per-use has no AI subscription and bills tokens. Phone-system charges still apply on top of Voice AI.
- **Example token rates on the same help page:** GPT 4.1 Mini $0.40 / $1.60 per million input/output tokens. Several frontier models are several dollars in and tens of dollars out per million. These are HighLevel's resale rates, not our model invoice.
- **Capabilities they claim:** CRM, funnels, calendars, email, SMS, workflows, knowledge base, conversation AI, voice AI, reviews AI, white-label and rebilling on the top agency plan.
- **Onboarding:** Heavy for a shop owner. Built for an agency operator.
- **Against YES SALES:** They already sell "AI employees" inside a system that also does CRM, calendar, and follow-up. Competing feature-for-feature is a multi-year loss.
- **Opening:** A detailing owner should not have to become a HighLevel technician. Our setup can be done for them, in English and Malay, on a site they own, with stricter price and booking rules than a blank prompt.

## respond.io

- **Checked:** 3 Nov 2026. https://respond.io/pricing and https://respond.io/whatsapp-business-api
- **Confidence:** Medium. The pricing-page extract and a respond.io article do not quote the same Growth price.
- **Pricing-page extract:** Starter $79/month, Growth $159/month, Advanced $279/month, with yearly amounts that imply about 20% off. AI Agents are listed from Growth upward. Starter lists AI Prompt and AI Assist, not AI Agents. WhatsApp fees are Meta's, not included.
- **Conflict:** A respond.io article, "Best WhatsApp AI Agents for Mid-Market B2C Teams (2026)", says its prices were checked in October 2026 and quotes Growth at $199/month for 10 users and 1,000 monthly active contacts, plus $12 per extra 100 contacts, and $15 per 1,000 AI credits past 10,000. Use the live pricing page before quoting a customer. Do not pick one number and ignore the other.
- **Capabilities they state:** Shared inbox, WhatsApp Business API, website chat, email, Instagram, Messenger, workflows, AI agents that qualify and book, human takeover, 2FA on Starter, SSO on Advanced.
- **Onboarding:** Real, but a shop still needs a WhatsApp Business account, templates, and someone to run an inbox.
- **Against YES SALES:** If the job is "WhatsApp inbox for a team," they have already built it. Putting a $79–$159 tool under a RM199 subscription destroys margin.
- **Decision:** Integrate or partner later if a pilot requires WhatsApp. Do not rebuild their inbox.

## Bookedin

- **Checked:** 3 Nov 2026, using a vendor blog dated 13 October 2025 and a support article. The live pricing page was not separately fetched, so these numbers can be stale.
- **Confidence:** Low-medium.
- **Target:** Service scheduling, with a detailing landing page: https://bookedin.com/auto-detailing-scheduling-software/
- **Price in the Oct 2025 blog:** Plus from $24 per month, or $19 per month billed annually, for one calendar. Higher calendar counts cost more.
- **Free plan, support article:** 50 bookings per month, booking page, email confirmations, client list. No SMS reminders, deposits, or calendar sync on that free plan.
- **AI:** Not part of the retrieved pages.
- **Decision use:** Booking software alone is cheap. We should not price YES SALES as a calendar. We also should not build one until a pilot outgrows Google Calendar or a tool like this.

## HubSpot Breeze Customer Agent

- **Checked:** 3 Nov 2026.
  - https://www.hubspot.com/products/artificial-intelligence/ai-customer-service-agent
  - https://www.hubspot.com/products/artificial-intelligence/credits
  - https://legal.hubspot.com/hubspot-product-and-services-catalog
  - Outcome announcement dated 13 April 2026: https://www.hubspot.com/company-news/hubspots-customer-agent-and-prospecting-agent-now-you-pay-when-the-task-is-complete
- **Confidence:** Medium-high on the credit math. Seat prices are from HubSpot's catalog and can vary by contract.
- **Price:** Customer Agent stated at $0.50 per resolved text conversation and $0.50 per voice minute. Credits are $0.01 each, so 50 credits match $0.50. Catalog core seats: Starter $20, Professional $50, Enterprise $75 per month. The product page says Professional or Enterprise is required for Customer Agent. Resolution claims (65% resolved, 39% faster) are HubSpot's, not ours.
- **Fit:** Wrong first product for a detailing shop. Useful as a pricing pattern: charge when a conversation is actually resolved, and do not charge when the customer immediately asks for a person.

## Intercom Fin

- **Checked:** 3 Nov 2026.
  - https://www.intercom.com/pricing
  - Outcome definition updated 23 September 2026: https://www.intercom.com/help/en/articles/8205718-fin-ai-agent-outcomes
- **Confidence:** Medium-high on $0.99 per outcome. Seat price on the pricing extract shows a discounted $19 and a $29 figure for Essential. A separate help article still describes an older $49 plan with 50 included resolutions. That older article was not used as the current price.
- **Rules they publish:** One outcome charge per conversation. No charge when the customer asks for a human, Fin cannot answer, or Fin escalates on frustration. Qualification can be $9.99. Fin Voice is sales-assisted.
- **Fit:** Support teams that already live in Intercom. Not a detailing operating system.
- **Lesson:** Escalation is not a failure to hide. It is how a serious product avoids charging for, and taking responsibility for, work the model should not finish.

## Build / buy / integrate

| Need | Decision | Why |
| --- | --- | --- |
| Detailing calendar, deposits, invoices | INTEGRATE or DEFER | Urable and Bookedin already do this. Confirm availability later with Google Calendar. Do not build a shop-management suite. |
| Website chat for a site we control | BUILD | Small, and it matches the founder's existing website work. No vendor fee inside the subscription. |
| Shared inbox and WhatsApp | INTEGRATE later | respond.io or the official WhatsApp Business Platform. Not a from-scratch inbox. |
| Voice | DEFER | HighLevel, Fresha, and Intercom already price minutes. Our gateway has never completed a live call. |
| Workflow engine | DEFER a general one | Keep the existing task table for our own jobs. Do not adopt a new orchestration vendor for the pilot. |
| CRM for the pilot | BUILD a thin enquiry record | The shop needs the lead and the transcript. It does not need the brokerage pipeline. |
| Payments for our subscription | DEFER | No payment processor until the business and legal setup exists. |
| Agency white-label | DEFER | HighLevel already won that shape. Revisit after three similar shops are on one template. |

## What this baseline is not

It is not a feature backlog. It is not proof that any vendor's AI is accurate. It is enough to refuse a general-platform build.
