# 10 — Credit and cost controls

**Date:** 3 November 2026  
**Purpose:** Stop unbounded model and messaging spend, including spend that happens during development.

## What can spend money today

| Path | Spends when | Current control |
| --- | --- | --- |
| xAI extraction or classification | `XAI_API_KEY` is non-empty | Key is empty in this workspace. Classify now requires a logged-in user. There is still no per-user token cap. |
| SMTP | `OUTBOUND_ENABLED` and SMTP settings | Defaults off. Mock sends record zero cost. |
| Twilio and xAI Realtime voice | Voice credentials and a placed call | Not configured. Outbound request path records `placed: false`. |
| WhatsApp | Not implemented | Returns not connected. No Meta bill from this code. |
| Grok bots outside this repo | Someone uses them in another product | This application cannot see or stop that spend. Do not point those agents at a database. |
| HighLevel, respond.io, Fresha, Urable | A subscription is purchased | None is connected. Do not add one without a written monthly ceiling. |

The existing `operating_settings` budget ceiling is a real control for the brokerage worker. It is one global number, default $25 in the test seed, not a per-customer meter. `provider_usage` stores mode and cost. Mock email writes cost 0.

## Development budget

Until the founder sets a different number:

- Automated tests must not call a paid model, mailbox, or telephone API.
- A live model check is a single opt-in run, with a ceiling of **USD 5** for the whole experiment, then stop.
- No new SaaS subscription for inbox, voice, or scheduling as part of M1–M4.
- Competitor research is the 3 Nov 2026 baseline. Further browsing needs a decision that the baseline cannot answer.

## Runtime rules for the future product

These are design rules. They are not implemented.

1. Every business has a monthly assistant budget in currency, defaulting closed (no live model) until the owner sets it.
2. Every role has a max tool calls and a max model turns per conversation.
3. FAQ lookup and slot rules are ordinary code. The model is used when the code cannot answer.
4. A smaller model is the default for classification and extraction. A larger model requires an explicit role setting and a higher budget.
5. When the budget is exhausted, the assistant stops and the conversation is handed to a person. It does not silently continue on pay-per-use.
6. Usage is stored per business: model, input size, output size, tool name, and estimated cost. Estimated is labeled estimated until a provider invoice reconciles it.
7. "Unlimited" is not a plan we sell.

## Pricing hypotheses, not prices

The brief suggested Starter RM199, Growth RM499, and Pro RM999 per month. Do not quote these.

Public anchors checked 3 Nov 2026, in the vendor's currency, not converted:

- Bookedin Plus was advertised from about $19–$24 per month for scheduling alone (vendor blog, Oct 2025).
- Fresha software from $14.95–$19.95 per bookable person, plus an AI Concierge at $29.95 or $99.95 per location.
- Urable at $70, $110, and $183 per month for detailing operations software.
- HighLevel AI Employee Growth at $50 per sub-account on top of an agency plan from $97.
- respond.io published cards at $79, $159, and $279 per month, with a conflicting $199 Growth figure in their own article.
- HubSpot Customer Agent at $0.50 per resolved text conversation, seat extra.
- Intercom Fin at $0.99 per outcome, seat extra.

A RM199 plan can work only if the channel is our widget, the model is cheap, conversation volume is low, and the founder is not spending hours per week inside the account. WhatsApp fees or a $79 inbox vendor do not fit under that hypothesis. The honest first commercial test is a setup fee plus a monthly price chosen after one shop's actual message volume and model cost are known.

## Metrics worth collecting once a pilot exists

Collected subscription revenue. Model cost. Message cost. Hosting cost. Hours of founder support. Conversations. Requests captured. Handoff rate. Wrong answers. Whether the owner paid the second month.

Do not record pipeline "value" from the brokerage demo as revenue.
