# YES SALES QuoteDesk — Market Decision and Competitive Positioning
Date: 12 November 2026
Status: Product hypothesis / implementation blueprint, NOT market validation
Decision owner: Founder
Code baseline: rayatcarnelian/Yes-Sales @ 91a261fec30198616e7b57344f3a93b0fcf9690e

## Decision
Build a narrow, AI-assisted enquiry-to-approved-proposal workflow. NOT a generic autonomous outbound SDR, general-purpose CRM, all-in-one field service system, WhatsApp inbox clone or agent marketplace. Begin with the founder's digital-services agency as a real user, then test 3-5 businesses doing custom/project-based work.

Working brand: YES SALES QuoteDesk. Product promise: turn incomplete customer enquiries into complete, reviewable project briefs, correctly scoped, owner-approved proposals, and traceable next actions. Do not claim it converts automatically or guarantees revenue.

## What the market DOES have (verified from public vendor descriptions, 12 Nov 2026)
- Jobber AI Receptionist: 24/7 texts/calls, requests, scheduling, escalation. https://help.getjobber.com/en/articles/receptionistpowered-by-jobber-ai/
- ServiceM8: quoting, jobs, invoicing, online bookings, AI helper; Free; paid tiers starting USD 29/month on public page. https://www.servicem8.com/pricing
- Houzz Pro: AI-assisted estimates/proposals/change orders with AI-generated line items, pricing and more; Pro USD 199/month on public page. https://pro.houzz.com/pro-help/r/how-to-use-ai-to-create-an-estimate-or-proposal and https://www.houzz.com/houzz-pro/pricing
- respond.io: AI qualification, workflow actions, multiple channels, human handoff. https://respond.io/ai-agents
- Dubsado: interactive quotes/proposals, service selections, contracts, invoices. https://help.dubsado.com/en/articles/12859419-build-a-proposal-or-quote
- OneLead Malaysia: leads, follow-ups, PDF quotations, calendar. https://onelead.com.my/
- HotLead Malaysia: WhatsApp/renovation lead routing and follow-up. https://www.hotleads.my/
- iCRM Malaysia: CRM, conversations, quotations/approval, sales follow-ups. https://icrm.com.my/
- Jawabkan Malaysia: approved-price AI receptionist for contractors; live provider/claims not independently tested. https://www.jawabkan.com/whatsapp-chatbot-for-contractors-malaysia.html
- For niche custom signage/print, SignTracker and shopVOX already offer estimating and shop management. https://www.sign-tracker.com/pricing-plans/

These show overlap, NOT a demonstrably empty market. We did not perform a systematic census of every vendor or independently test competitor products. Published prices, feature claims and presence can change; recheck before quoting anyone.

## Specific opportunity worth testing
Small teams that sell custom projects over messages can have incomplete briefs, repeated back-and-forth, inconsistent quoted scope, slow responses and lost follow-ups. Hypothesis: an inexpensive, mobile-friendly, done-for-you layer that captures structured requirements, highlights missing facts, grounds price in approved rate sheets, and records human approval could be more convenient than adopting a general CRM. Its defensibility, existence and willingness to pay are UNPROVEN.

Beachhead #1: founder's website/software/automation agency (real use; does not alone prove a market).
Potential external ICP: small owner-led custom-project service firms with a nonstandard quotation process, at least five genuine new inbound project enquiries weekly, repeatable scope questions, and willingness to share anonymized records. Example categories to INTERVIEW, not presume fit: installation/fit-out, custom signage, small studios/agencies. Do not launch a separate vertical template without 3-5 conversations and one pilot agreement.

Non-ICP: a business satisfied with off-the-shelf booking software; no repeat enquiries; unwilling to review quote drafts; needs full inventory/field dispatch/accounting; cannot lawfully connect its communications; expects automated price guarantees.

## Why this product over alternatives (strategic judgment, not measured market shares)
1. Autonomous outbound SDR: easy to spam, hard to attribute, depends on data/consent/deliverability, crowded Apollo/Clay/Salesforce space. Reject as first sold product; founder can still use supervised prospecting.
2. General WhatsApp AI receptionist: crowded Jobber, respond.io, WATI, Jawabkan. Reject standalone.
3. Full field-service ERP/renovation suite: crowded, deep domain complexity, slow release. Reject.
4. Evidence-linked enquiry-to-proposal workflow with human review: aligns with current FastAPI/Postgres approvals/evidence/job-card code; small testable product surface. Select for MVP.

## Anti-claims
- We do not know which feature customers will pay for.
- Existing platform does not yet have secure multi-tenancy, live WhatsApp, or proven production customer conversations.
- A quote draft is NOT a sent quote; a sent quote is NOT an accepted quote; an accepted quote is NOT collected revenue.
- We cannot claim a 100% success probability, conversion uplift, time savings or special OpenAI selection. Measure them.
- No AI may hallucinate prices, timeline promises, scope details, customer consent or external provider delivery.

## Validation plan — running in parallel with build, before paid integrations
Conduct 5 short structured interviews: 2 owner-led agencies/studios, 3 custom project businesses. Ask for last 10 inbound requests (redacted) and current process:
- Volume and channels per week, time to useful first response, time to quotation
- Missing inputs that force repeated replies
- How pricing and approval are determined; how often scope changes
- Number/value of stale quotations; how they track follow-ups
- Current tool stack and what would make a switch or add-on undesirable
- Would they permit a 2-week shadow trial with their own redacted data?
- Show a functioning prototype; request a concrete paid pilot commitment, not a vague positive opinion

Go/no-go gate to ship external pilot: >=2 genuine pilot candidates who give real workflow examples and at least 1 who agrees in writing to trial terms. Measure founder time and qualification accuracy on 20 historic redacted enquiries first. If these conditions fail, pivot ICP or stop; do NOT respond by adding more agents.

Potential commercial model (hypothesis): charge an onboarding fee plus capped monthly subscription and clearly priced usage tiers only after costs and willingness to pay are measured. No public price yet.

## Operating metric definitions
- Qualifying enquiry: real inbound request tied to source and person/business, not spam.
- Brief completeness: required customer-specific fields present / required fields total.
- Quote turnaround: first inbound timestamp to human-approved quote ready timestamp.
- Owner time saved: measured manual minutes minus AI-assisted human minutes on matched tasks.
- Proposal accuracy: human-reviewed correct scope/terms/price source count / evaluated proposals.
- Quote acceptance: externally confirmed acceptance event / issued proposals.
- Revenue: cash actually collected, with source.
- Guardrails: cross-tenant data exposure, unauthorized send, invented price, mistaken confirmation and privacy breaches; target zero.
- Unit cost: compute + channel + infrastructure + support + onboarding amortization. Do not claim profit based on token cost alone.

## Non-goals for V1
No autonomous mass outbound; no voice; no WhatsApp Web automation; no all-channel shared inbox; no self-scheduling without calendar check; no e-signatures/payments until a customer needs them; no complex ERP; no indefinite Grok loops; no replacement of founder's brokerage historical tables.
